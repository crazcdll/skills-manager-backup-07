#!/usr/bin/env python3
"""60s sleep-loop 小循环唤醒时使用的快速预警核检脚本。

这是一个固定的单一用途脚本，目的是让高频的 60s 小循环保持低开销：
一次调用拉取目标 MRN bundleVersion 或 H5_DUO webVersion 在最近短窗口内的官方近一周首现
（`newErrors`），与 `fast_alert_seen` 做过滤去重，只返回真正未告警过
的新异常。它不产出 severity，也不会像正常 Round 那样跑完整的双查询。

I/O 边界：
- 只读 `current_observation.json` 取 `target` 和 `fast_alert_seen`，
  不写状态；状态更新统一走 `observation_state.py record-fast-alert`。
- 通过子进程调用 `raptorfe` CLI（假定已在 PATH 中，与本 Skill 其余部分
  一致），带硬超时；不直接对 Raptor 发起 HTTP 请求。
- 只查单页（`offset=0`，`limit=200`）。这是高频预警，不是权威的 Round
  查询：即使本次漏查，下一次唤醒仍能发现真实的首现异常，且 Raptor 的
  newErrors 语义（对比上周同期）不依赖 Window 长度。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

IGNORED_STATUSES = {3, 4, 5}
IGNORED_CATEGORIES = {"resourceError"}
LOCAL_TZ = timezone(timedelta(hours=8))
DEFAULT_WINDOW_MINUTES = 5
DEFAULT_TIMEOUT_MS = 30_000


class FastCheckError(RuntimeError):
    pass


def floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def state_dir(args: argparse.Namespace) -> Path:
    if args.state_dir:
        return Path(args.state_dir).expanduser().resolve()
    if not args.paas or not args.group_id:
        raise FastCheckError("provide --state-dir or both --paas and --group-id")
    return Path(f"/efs/data/tenants/{args.paas}/shared/observation_{args.group_id}")


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FastCheckError("no observation state exists")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FastCheckError(f"state file is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise FastCheckError("state root must be a JSON object")
    return value


def normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
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


def call_raptorfe(
    *,
    raptorfe_bin: str,
    project_id: Any,
    project_type: str,
    version: str,
    start_ms: int,
    end_ms: int,
    timeout_ms: int,
) -> dict[str, Any]:
    cmd = [
        raptorfe_bin,
        "-t",
        str(timeout_ms),
        "web",
        "error",
        "get-summary-table",
        "--project-id",
        str(project_id),
        "--start-long",
        str(start_ms),
        "--end-long",
        str(end_ms),
        "--web-version",
        "all" if project_type == "MRN" else version,
        "--sort-field",
        "DATE",
        "--page-size",
        "200",
        "--limit",
        "200",
        "--offset",
        "0",
        "--time-size",
        "MINUTE",
    ]
    if project_type == "MRN":
        cmd.extend(["--query-param", json.dumps({"TAG4": [version]}, ensure_ascii=False)])
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FastCheckError(f"raptorfe call timed out: {exc}") from exc
    except OSError as exc:
        raise FastCheckError(f"failed to invoke raptorfe: {exc}") from exc
    if completed.returncode != 0:
        raise FastCheckError(
            f"raptorfe exited with {completed.returncode}: {completed.stderr.strip()[:500]}"
        )
    stdout = completed.stdout
    json_start = stdout.find("{")
    if json_start == -1:
        raise FastCheckError(
            f"raptorfe returned no JSON in stdout: {stdout.strip()[:500]}"
        )
    try:
        payload = json.loads(stdout[json_start:])
    except json.JSONDecodeError as exc:
        raise FastCheckError(f"raptorfe returned non-JSON output: {exc}") from exc
    if not isinstance(payload, dict):
        raise FastCheckError("raptorfe JSON root must be an object")
    return payload


def extract_new_error_alerts(
    payload: dict[str, Any],
    seen: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise FastCheckError("raptorfe response missing data object")
    new_errors = data.get("newErrors")
    if new_errors is None:
        new_errors = []
    if not isinstance(new_errors, list):
        raise FastCheckError("raptorfe response newErrors must be a list")
    new_error_names = {str(name) for name in new_errors}

    rows = data.get("table", {}).get("rows", []) if isinstance(data.get("table"), dict) else []
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows if isinstance(rows, list) else []:
        normalized = normalize_row(raw) if isinstance(raw, dict) else None
        if normalized is None:
            continue
        indexed[normalized["cluster"]] = normalized

    alerts: list[dict[str, Any]] = []
    for name in sorted(new_error_names):
        if name in seen:
            continue
        row = indexed.get(name)
        if row is None:
            # newErrors 命中但该行在本页被过滤（ignored status/category）
            # 或分页未覆盖到；不生成告警，避免污染已忽略异常。
            continue
        alerts.append(
            {
                "cluster": name,
                "level": row["level"],
                "count": row["count"],
                "user_count": row["user_count"],
            }
        )

    level_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    alerts.sort(key=lambda item: (level_order.get(item["level"], 3), -item["user_count"]))
    return alerts, sorted(new_error_names)


def run(args: argparse.Namespace) -> dict[str, Any]:
    directory = state_dir(args)
    state = read_state(directory / "current_observation.json")

    if state.get("lifecycle_state") != "OBSERVING":
        raise FastCheckError("fast-check requires OBSERVING state")

    target = state.get("target") or {}
    project_id = target.get("project_id") or target.get("project_name")
    project_type = target.get("project_type")
    version = target.get("bundle_version") if project_type == "MRN" else target.get("web_version")
    if (
        project_type not in {"MRN", "H5_DUO"}
        or not project_id
        or not version
        or (project_type == "H5_DUO" and str(version) == "all")
    ):
        raise FastCheckError("observation target missing supported project type, project_id, or version")

    seen = set(state.get("fast_alert_seen") or [])

    lag = int((state.get("runtime") or {}).get("data_lag_minutes", 2))
    window_minutes = args.window_minutes
    now = datetime.now(LOCAL_TZ)
    end = floor_minute(now - timedelta(minutes=lag))
    start = end - timedelta(minutes=window_minutes)

    payload = call_raptorfe(
        raptorfe_bin=args.raptorfe_bin,
        project_id=project_id,
        project_type=str(project_type),
        version=str(version),
        start_ms=to_ms(start),
        end_ms=to_ms(end) - 1,
        timeout_ms=args.timeout_ms,
    )
    alerts, checked_names = extract_new_error_alerts(payload, seen)

    return {
        "ok": True,
        "observation_id": state.get("observation_id"),
        "window_start": start.isoformat(timespec="seconds"),
        "window_end": end.isoformat(timespec="seconds"),
        "checked_new_error_names": checked_names,
        "alerts": alerts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir")
    parser.add_argument("--paas")
    parser.add_argument("--group-id")
    parser.add_argument("--window-minutes", type=int, default=DEFAULT_WINDOW_MINUTES)
    parser.add_argument("--raptorfe-bin", default="raptorfe")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except FastCheckError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # defensive: never crash with non-JSON output
        print(json.dumps({"ok": False, "error": f"internal error: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
