#!/usr/bin/env python3
"""全版本 Raptor 逐条目环比（Round-over-Round）的无状态纯计算工具。

本工具除 stdin/argv 和 stdout 外不做任何 I/O：不读写
`current_observation.json`，也不感知 Observation 的 Lifecycle 或
Severity。它只回答一个范围很窄、结果确定的问题："与上一轮相比，本轮
全版本逐条目数据中，哪些聚类涨幅超过阈值，或是本轮新出现的？"

设计考量：
- 业务判定（命中列表如何映射到 `notice`/`warning`）留给 Skill/Agent；
  本脚本只返回事实。
- 保持为独立文件（而不是 observation_state.py 的子命令），是为了在
  文件层面明确"状态转换"与"纯计算"的边界。
- 调用方负责取得上一轮的行数据（例如通过 `observation_state.py read`
  拿到 `rounds_summary[-1].all_versions.rows`）并传入；本脚本自身
  不读取状态。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Ignore statuses per Raptor STATUS enum: 3=已解决 (RESOLVED), 4=完全忽略
# (IGNORED), 5=暂时忽略 (MUTED). Aligned with the legacy alert-rules.md /
# trade-stability-alert-diagnosis-sdlc filtering convention.
IGNORED_STATUSES = {3, 4, 5}
IGNORED_CATEGORIES = {"resourceError"}

# Initial thresholds carried over from the legacy alert-rules.md P1 tier.
# Not yet re-validated against this skill's own observed data; adjust here
# if real-world rounds show these are too sensitive or too lax.
ERROR_WARN_GROWTH_RATE = 0.5  # user_count 涨幅 >= 50%
ERROR_WARN_GROWTH_ABS = 3  # 且增量 >= 3
INFO_GROWTH_RATE = 2.0  # count 涨幅 >= 200%
INFO_GROWTH_ABS = 5  # 且绝对量 >= 5

HIT_RULE_NEW_APPEARED = "new_appeared"
HIT_RULE_USER_COUNT_SURGE = "user_count_surge"
HIT_RULE_COUNT_SURGE = "count_surge"


class DiffError(RuntimeError):
    pass


def _read_json_arg(raw: str, label: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiffError(f"invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(value, list):
        raise DiffError(f"{label} must be a JSON array")
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw Raptor row into the minimal shape this tool needs.

    Returns None if the row should be excluded (ignored status/category) or
    is missing its cluster identity (`main`).
    """
    main = row.get("main") or row.get("cluster")
    if not main:
        return None
    status = row.get("STATUS", row.get("status", 0))
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    if status in IGNORED_STATUSES:
        return None
    category = row.get("CATEGORY") or row.get("category")
    if category in IGNORED_CATEGORIES:
        return None
    level = str(row.get("LEVEL") or row.get("level") or "INFO").upper()
    count = row.get("COUNT", row.get("count", 0))
    user_count = row.get("USER_COUNT", row.get("user_count", 0))
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    try:
        user_count = int(user_count)
    except (TypeError, ValueError):
        user_count = 0
    return {
        "cluster": str(main),
        "level": level,
        "count": count,
        "user_count": user_count,
        "status": status,
    }


def _index_by_cluster(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows:
        normalized = _normalize_row(raw)
        if normalized is None:
            continue
        # If duplicate cluster names appear across pages, keep the one with
        # the larger count (defensive; callers should already de-dupe).
        existing = indexed.get(normalized["cluster"])
        if existing is None or normalized["count"] > existing["count"]:
            indexed[normalized["cluster"]] = normalized
    return indexed


def diff_clusters(
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current = _index_by_cluster(current_rows)
    previous = _index_by_cluster(previous_rows)

    hits: list[dict[str, Any]] = []
    for cluster, row in current.items():
        prev = previous.get(cluster)
        level = row["level"]
        count = row["count"]
        user_count = row["user_count"]

        if prev is None:
            if level == "ERROR":
                hits.append(
                    {
                        "cluster": cluster,
                        "level": level,
                        "count": count,
                        "user_count": user_count,
                        "prev_count": 0,
                        "prev_user_count": 0,
                        "hit_rule": HIT_RULE_NEW_APPEARED,
                    }
                )
            continue

        prev_count = prev["count"]
        prev_user_count = prev["user_count"]

        if level in ("ERROR", "WARN"):
            growth_abs = user_count - prev_user_count
            growth_rate = (
                growth_abs / prev_user_count if prev_user_count > 0 else (
                    float("inf") if user_count > 0 else 0.0
                )
            )
            if growth_rate >= ERROR_WARN_GROWTH_RATE and growth_abs >= ERROR_WARN_GROWTH_ABS:
                hits.append(
                    {
                        "cluster": cluster,
                        "level": level,
                        "count": count,
                        "user_count": user_count,
                        "prev_count": prev_count,
                        "prev_user_count": prev_user_count,
                        "user_count_growth_rate": None if growth_rate == float("inf") else round(growth_rate, 3),
                        "user_count_growth_abs": growth_abs,
                        "hit_rule": HIT_RULE_USER_COUNT_SURGE,
                    }
                )
        else:  # INFO or any other level treated as INFO-tier
            growth_abs = count - prev_count
            growth_rate = (
                growth_abs / prev_count if prev_count > 0 else (
                    float("inf") if count > 0 else 0.0
                )
            )
            if growth_rate >= INFO_GROWTH_RATE and growth_abs >= INFO_GROWTH_ABS:
                hits.append(
                    {
                        "cluster": cluster,
                        "level": level,
                        "count": count,
                        "user_count": user_count,
                        "prev_count": prev_count,
                        "prev_user_count": prev_user_count,
                        "count_growth_rate": None if growth_rate == float("inf") else round(growth_rate, 3),
                        "count_growth_abs": growth_abs,
                        "hit_rule": HIT_RULE_COUNT_SURGE,
                    }
                )

    # Stable, deterministic ordering: ERROR first, then by user_count desc.
    level_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    hits.sort(key=lambda item: (level_order.get(item["level"], 3), -item["user_count"]))
    return hits


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--current-rows-json",
        required=True,
        help="JSON array of this round's filtered all-versions rows (raw Raptor row shape or normalized shape).",
    )
    parser.add_argument(
        "--previous-rows-json",
        required=True,
        help="JSON array of the previous round's filtered all-versions rows. Pass '[]' if there is no previous round.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        current_rows = _read_json_arg(args.current_rows_json, "current-rows-json")
        previous_rows = _read_json_arg(args.previous_rows_json, "previous-rows-json")
        hits = diff_clusters(current_rows, previous_rows)
    except DiffError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # defensive: never crash with a non-JSON output
        print(json.dumps({"ok": False, "error": f"internal error: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "hits": hits}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
