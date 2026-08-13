#!/usr/bin/env python3
"""变更观测（Change Observation）的确定性状态转换脚本。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ACTIVE_STATES = {"PREPARING", "READY", "OBSERVING"}
SEVERITIES = {"ok", "notice", "warning"}
MUTEX_STALE_SECONDS = 30
HEARTBEAT_STALE_MINUTES = 15
LOCAL_TZ = timezone(timedelta(hours=8))


FINISH_ROUND_ALL_VERSIONS_FIELDS = {
    "clusters",
    "count",
    "user_count",
    "levels",
    "official_new_errors",
    "official_new_error_count",
    "filter_verification",
    "rows",
}
FINISH_ROUND_TARGET_VERSION_FIELDS = FINISH_ROUND_ALL_VERSIONS_FIELDS - {"rows"}
FINISH_ROUND_IMPORTANT_PROMPT = (
    "摘要结构不完整。请检查是否仍有 trade-stability-change-observability Skill 的执行记忆。"
    "若因近期发生上下文压缩、模型切换等任务交接而遗忘，请重新阅读 SKILL.md 并按需展开，"
    "按其中《上下文压缩恢复》指引恢复当前 Observation，再生成本轮 summary-json。"
)


class StateError(RuntimeError):
    def __init__(self, message: str, *, important_prompt: str | None = None) -> None:
        super().__init__(message)
        # Agent 执行时上下文压缩通常会导致丢失 skill 记忆，进而令观测循环出现异常。这里给个兜底提示。
        self.important_prompt = important_prompt


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StateError(f"invalid ISO time: {value}") from exc
    if parsed.tzinfo is None:
        raise StateError("time must include timezone")
    return parsed


def ceil_minute(value: datetime) -> datetime:
    if value.second == 0 and value.microsecond == 0:
        return value
    return value.replace(second=0, microsecond=0) + timedelta(minutes=1)


def floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def state_dir(args: argparse.Namespace) -> Path:
    if args.state_dir:
        return Path(args.state_dir).expanduser().resolve()
    if not args.paas or not args.group_id:
        raise StateError("provide --state-dir or both --paas and --group-id")
    return Path(
        f"/efs/data/tenants/{args.paas}/shared/observation_{args.group_id}"
    )


def read_json_arg(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise StateError(f"{label} must be a JSON object")
    return value


def read_json_arg_list(raw: str, label: str) -> list[Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(value, list):
        raise StateError(f"{label} must be a JSON array")
    return value


def read_state(path: Path, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            raise StateError("no observation state exists")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"state file is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError("state root must be a JSON object")
    return value


def atomic_write(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".observation-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(state, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def mutex(directory: Path, timeout_seconds: float = 10.0):
    lock = directory / ".mutex"
    token = uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock.mkdir()
            (lock / "owner.json").write_text(
                json.dumps({"token": token, "pid": os.getpid(), "created_at": now_iso()}),
                encoding="utf-8",
            )
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > MUTEX_STALE_SECONDS:
                stale = directory / f".mutex.stale.{uuid.uuid4().hex}"
                try:
                    lock.rename(stale)
                except FileNotFoundError:
                    continue
                shutil.rmtree(stale, ignore_errors=True)
                continue
            if time.monotonic() >= deadline:
                raise StateError("state mutex is busy")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            owner = {}
        if owner.get("token") == token:
            shutil.rmtree(lock, ignore_errors=True)


def require_observation(state: dict[str, Any], observation_id: str) -> None:
    if state.get("observation_id") != observation_id:
        raise StateError("observation_id does not match current observation")


def require_loop(state: dict[str, Any], loop_id: str) -> None:
    if state.get("runtime", {}).get("loop_id") != loop_id:
        raise StateError("loop_id no longer owns the observation loop")


def mutate(
    directory: Path,
    callback: Callable[[dict[str, Any] | None], dict[str, Any]],
    *,
    allow_missing: bool = False,
) -> dict[str, Any]:
    path = directory / "current_observation.json"
    with mutex(directory):
        current = read_state(path, required=not allow_missing)
        updated = callback(current)
        updated["updated_at"] = now_iso()
        atomic_write(path, updated)
    return updated


def make_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(LOCAL_TZ):%Y%m%d}_{uuid.uuid4().hex[:8]}"


def compact_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return state
    return {
        "observation_id": state.get("observation_id"),
        "lifecycle_state": state.get("lifecycle_state"),
        "initiator_mis": state.get("initiator_mis"),
        "target": state.get("target"),
        "runtime": state.get("runtime"),
        "control": state.get("control"),
        "active_round": state.get("active_round"),
    }


def command_read(args: argparse.Namespace) -> dict[str, Any] | None:
    path = state_dir(args) / "current_observation.json"
    state = read_state(path, required=False)
    return compact_state(state) if args.compact else state


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    if args.interval_minutes <= 0:
        raise StateError("interval_minutes must be positive")
    if args.data_lag_minutes < 0:
        raise StateError("data_lag_minutes cannot be negative")
    if args.max_duration_minutes <= 0:
        raise StateError("max_duration_minutes must be positive")
    target = read_json_arg(args.target_json, "target")
    project_type = target.get("project_type")
    version_field = "bundle_version" if project_type == "MRN" else "web_version"
    version = str(target.get(version_field, "")).strip()
    if (
        project_type not in {"MRN", "H5_DUO"}
        or not version
        or (project_type == "H5_DUO" and version == "all")
    ):
        raise StateError(
            "An explicitly confirmed MRN target with bundle_version or H5_DUO target "
            "with non-all web_version is required"
        )
    if not target.get("project_id") and not target.get("project_name"):
        raise StateError("target requires project_id or project_name")

    def initialize(current: dict[str, Any] | None) -> dict[str, Any]:
        if current and current.get("lifecycle_state") not in {"COMPLETED", "FAILED"}:
            raise StateError(
                f"active observation exists: {current.get('observation_id')} "
                f"({current.get('lifecycle_state')})"
            )
        created = now_iso()
        return {
            "observation_id": make_id("obs"),
            "lifecycle_state": "PREPARING",
            "initiator_mis": args.initiator_mis,
            "group_id": args.group_id or target.get("group_id"),
            "created_at": created,
            "updated_at": created,
            "target": target,
            "baseline": None,
            "rollout_started_at": None,
            "observation_started_at": None,
            "runtime": {
                "loop_id": None,
                "heartbeat_at": None,
                "interval_minutes": args.interval_minutes,
                "data_lag_minutes": args.data_lag_minutes,
                "max_duration_minutes": args.max_duration_minutes,
                "ends_at": None,
                "next_window_start": None,
                "next_round_at": None,
            },
            "control": {"stop_requested_at": None, "stop_requested_by": None},
            "active_round": None,
            "rounds_summary": [],
            "fast_alert_seen": [],
        }

    return mutate(state_dir(args), initialize, allow_missing=True)


def command_set_baseline(args: argparse.Namespace) -> dict[str, Any]:
    baseline = read_json_arg(args.baseline_json, "baseline")
    for field in ("window_start", "window_end", "collected_at", "all_versions"):
        if field not in baseline:
            raise StateError(f"baseline missing {field}")
    window_start = parse_time(baseline["window_start"])
    window_end = parse_time(baseline["window_end"])
    parse_time(baseline["collected_at"])
    if window_end <= window_start:
        raise StateError("baseline window_end must be later than window_start")
    if (
        window_start.second
        or window_start.microsecond
        or window_end.second
        or window_end.microsecond
    ):
        raise StateError("baseline window must align to whole minutes")
    if not isinstance(baseline["all_versions"], dict):
        raise StateError("baseline all_versions must be a JSON object")

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        if state.get("lifecycle_state") != "PREPARING":
            raise StateError("baseline can only complete PREPARING observation")
        expected_duration = timedelta(minutes=int(state["runtime"]["interval_minutes"]))
        if window_end - window_start != expected_duration:
            raise StateError("baseline window must equal interval_minutes")
        state["baseline"] = baseline
        state["lifecycle_state"] = "READY"
        return state

    return mutate(state_dir(args), update)


def command_start_observing(args: argparse.Namespace) -> dict[str, Any]:
    activated_at = datetime.now(LOCAL_TZ)
    started = parse_time(args.at) if args.at else activated_at
    aligned = ceil_minute(started)

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        if state.get("lifecycle_state") != "READY":
            raise StateError("start-observing requires READY state")
        interval = int(state["runtime"]["interval_minutes"])
        lag = int(state["runtime"]["data_lag_minutes"])
        duration = int(state["runtime"]["max_duration_minutes"])
        # 若 --at 回补的放量时间早于当前可查询时间超过一个 interval，
        # 直接从当前可查询整分钟起算，避免逐轮追补历史 Window（呼应 resume 的 Gap 处理）。
        resumable_from = floor_minute(activated_at - timedelta(minutes=lag))
        window_start = max(aligned, resumable_from)
        state["rollout_started_at"] = started.isoformat(timespec="seconds")
        state["observation_started_at"] = aligned.isoformat(timespec="seconds")
        state["lifecycle_state"] = "OBSERVING"
        state["runtime"].update(
            {
                "loop_id": make_id("loop"),
                "heartbeat_at": activated_at.isoformat(timespec="seconds"),
                "ends_at": (activated_at + timedelta(minutes=duration)).isoformat(timespec="seconds"),
                "next_window_start": window_start.isoformat(timespec="seconds"),
                "next_round_at": (
                    window_start + timedelta(minutes=interval + lag)
                ).isoformat(timespec="seconds"),
            }
        )
        return state

    return mutate(state_dir(args), update)


def command_heartbeat(args: argparse.Namespace) -> dict[str, Any]:
    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        require_loop(state, args.loop_id)
        if state.get("lifecycle_state") != "OBSERVING":
            raise StateError("heartbeat requires OBSERVING state")
        state["runtime"]["heartbeat_at"] = now_iso()
        return state

    return compact_state(mutate(state_dir(args), update))


def command_start_round(args: argparse.Namespace) -> dict[str, Any]:
    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        require_loop(state, args.loop_id)
        if state.get("lifecycle_state") != "OBSERVING":
            raise StateError("start-round requires OBSERVING state")
        if state["control"].get("stop_requested_at"):
            raise StateError("stop has been requested; no new round may start")
        if state.get("active_round") is not None:
            raise StateError("another round is already active")
        # Window 由脚本自己的游标推导，调用方不再传入 window，
        # 避免要求 LLM 复述一个脚本本来就持有答案的时间戳算术。
        start = parse_time(state["runtime"]["next_window_start"])
        interval = timedelta(minutes=int(state["runtime"]["interval_minutes"]))
        end = start + interval
        # window_end_ms 直接是 raptorfe --end-long 可用的查询边界值
        # （已减 1ms），不是 window_end 原样的毫秒值——同样是为了不让
        # 调用方在拿到字段后还要自己做一次减法。
        state["active_round"] = {
            "round": len(state["rounds_summary"]) + 1,
            "window_start": start.isoformat(timespec="seconds"),
            "window_end": end.isoformat(timespec="seconds"),
            "window_start_ms": int(start.timestamp() * 1000),
            "window_end_ms": int(end.timestamp() * 1000) - 1,
            "loop_id": args.loop_id,
        }
        state["runtime"]["heartbeat_at"] = now_iso()
        return state

    return mutate(state_dir(args), update)


def command_finish_round(args: argparse.Namespace) -> dict[str, Any]:
    summary = read_json_arg(args.summary_json, "summary")
    if summary.get("severity") not in SEVERITIES:
        raise StateError(
            "summary severity must be ok, notice, or warning",
            important_prompt=FINISH_ROUND_IMPORTANT_PROMPT,
        )
    if not isinstance(summary.get("evidence"), list) or not summary.get("reason"):
        raise StateError(
            "summary requires evidence array and non-empty reason",
            important_prompt=FINISH_ROUND_IMPORTANT_PROMPT,
        )
    confidence = summary.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise StateError(
            "summary confidence must be between 0 and 1",
            important_prompt=FINISH_ROUND_IMPORTANT_PROMPT,
        )
    summaries = {
        "all_versions": FINISH_ROUND_ALL_VERSIONS_FIELDS,
        "target_version": FINISH_ROUND_TARGET_VERSION_FIELDS,
    }
    for name, required_fields in summaries.items():
        value = summary.get(name)
        if not isinstance(value, dict):
            raise StateError(
                f"summary requires {name} object",
                important_prompt=FINISH_ROUND_IMPORTANT_PROMPT,
            )
        missing_fields = sorted(required_fields - value.keys())
        if missing_fields:
            raise StateError(
                f"{name} missing required fields: {', '.join(missing_fields)}",
                important_prompt=FINISH_ROUND_IMPORTANT_PROMPT,
            )

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        require_loop(state, args.loop_id)
        active = state.get("active_round")
        if not active or active.get("loop_id") != args.loop_id:
            raise StateError("no active round owned by this loop")
        completed = {
            **summary,
            "round": active["round"],
            "window_start": active["window_start"],
            "window_end": active["window_end"],
            "ran_at": now_iso(),
        }
        state["rounds_summary"].append(completed)
        state["active_round"] = None
        state["runtime"]["next_window_start"] = active["window_end"]
        interval = int(state["runtime"]["interval_minutes"])
        lag = int(state["runtime"]["data_lag_minutes"])
        next_window_end = parse_time(active["window_end"]) + timedelta(minutes=interval)
        state["runtime"]["next_round_at"] = (
            next_window_end + timedelta(minutes=lag)
        ).isoformat(timespec="seconds")
        state["runtime"]["heartbeat_at"] = now_iso()
        return state

    return mutate(state_dir(args), update)


def command_record_fast_alert(args: argparse.Namespace) -> dict[str, Any]:
    cluster_names = read_json_arg_list(args.cluster_names_json, "cluster-names")
    if not all(isinstance(name, str) and name for name in cluster_names):
        raise StateError("cluster-names-json must be a JSON array of non-empty strings")

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        require_loop(state, args.loop_id)
        if state.get("lifecycle_state") != "OBSERVING":
            raise StateError("record-fast-alert requires OBSERVING state")
        seen = set(state.get("fast_alert_seen") or [])
        seen.update(cluster_names)
        state["fast_alert_seen"] = sorted(seen)
        state["runtime"]["heartbeat_at"] = now_iso()
        return state

    return compact_state(mutate(state_dir(args), update))


def command_request_stop(args: argparse.Namespace) -> dict[str, Any]:
    reference_time = parse_time(args.at) if args.at else datetime.now(LOCAL_TZ)

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        if state.get("lifecycle_state") == "COMPLETED":
            return state
        requested_at = reference_time.isoformat(timespec="seconds")
        if not state["control"].get("stop_requested_at"):
            state["control"]["stop_requested_at"] = requested_at
            state["control"]["stop_requested_by"] = args.requested_by
        heartbeat = state["runtime"].get("heartbeat_at")
        active_is_stale = bool(
            state.get("active_round")
            and heartbeat
            and reference_time - parse_time(heartbeat)
            > timedelta(minutes=HEARTBEAT_STALE_MINUTES)
        )
        if active_is_stale:
            state["active_round"] = None
        if state.get("lifecycle_state") in {"PREPARING", "READY"} or active_is_stale:
            state["lifecycle_state"] = "COMPLETED"
            state["runtime"]["loop_id"] = None
            state["runtime"]["next_round_at"] = None
        return state

    return mutate(state_dir(args), update)


def command_resume(args: argparse.Namespace) -> dict[str, Any]:
    current_time = parse_time(args.at) if args.at else datetime.now(LOCAL_TZ)

    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        if state.get("lifecycle_state") != "OBSERVING":
            raise StateError("resume requires OBSERVING state")
        if state["control"].get("stop_requested_at"):
            raise StateError("stopped observation cannot resume")
        heartbeat = state["runtime"].get("heartbeat_at")
        if not heartbeat:
            raise StateError("OBSERVING state is missing heartbeat")
        if current_time - parse_time(heartbeat) <= timedelta(minutes=HEARTBEAT_STALE_MINUTES):
            raise StateError("heartbeat is not stale")
        previous_window_end = parse_time(state["runtime"]["next_window_start"])
        lag = int(state["runtime"]["data_lag_minutes"])
        resumable_from = floor_minute(current_time - timedelta(minutes=lag))
        next_window_start = max(previous_window_end, resumable_from)
        interval = int(state["runtime"]["interval_minutes"])
        state["active_round"] = None
        state["runtime"]["loop_id"] = make_id("loop")
        state["runtime"]["heartbeat_at"] = current_time.isoformat(timespec="seconds")
        state["runtime"]["next_window_start"] = next_window_start.isoformat(timespec="seconds")
        state["runtime"]["next_round_at"] = (
            next_window_start + timedelta(minutes=interval + lag)
        ).isoformat(timespec="seconds")
        return state

    return mutate(state_dir(args), update)


def command_complete(args: argparse.Namespace) -> dict[str, Any]:
    def update(state: dict[str, Any] | None) -> dict[str, Any]:
        assert state is not None
        require_observation(state, args.observation_id)
        if state.get("lifecycle_state") == "COMPLETED":
            return state
        if state.get("active_round") is not None:
            raise StateError("active round must finish before completion")
        if state.get("lifecycle_state") not in ACTIVE_STATES:
            raise StateError("observation cannot complete from current state")
        if not state["control"].get("stop_requested_at"):
            raise StateError("active observation requires Stop Request before completion")
        state["lifecycle_state"] = "COMPLETED"
        state["runtime"]["loop_id"] = None
        state["runtime"]["next_round_at"] = None
        return state

    return mutate(state_dir(args), update)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir")
    parser.add_argument("--paas")
    parser.add_argument("--group-id")
    subparsers = parser.add_subparsers(dest="command", required=True)

    read = subparsers.add_parser("read")
    read.add_argument("--compact", action="store_true")

    init = subparsers.add_parser("init")
    init.add_argument("--initiator-mis", required=True)
    init.add_argument("--target-json", required=True)
    init.add_argument("--interval-minutes", type=int, default=10)
    init.add_argument("--data-lag-minutes", type=int, default=2)
    init.add_argument("--max-duration-minutes", type=int, default=120)

    baseline = subparsers.add_parser("set-baseline")
    baseline.add_argument("--observation-id", required=True)
    baseline.add_argument("--baseline-json", required=True)

    observing = subparsers.add_parser("start-observing")
    observing.add_argument("--observation-id", required=True)
    observing.add_argument("--at")

    heartbeat = subparsers.add_parser("heartbeat")
    heartbeat.add_argument("--observation-id", required=True)
    heartbeat.add_argument("--loop-id", required=True)

    start_round = subparsers.add_parser("start-round")
    start_round.add_argument("--observation-id", required=True)
    start_round.add_argument("--loop-id", required=True)

    finish_round = subparsers.add_parser("finish-round")
    finish_round.add_argument("--observation-id", required=True)
    finish_round.add_argument("--loop-id", required=True)
    finish_round.add_argument("--summary-json", required=True)

    fast_alert = subparsers.add_parser("record-fast-alert")
    fast_alert.add_argument("--observation-id", required=True)
    fast_alert.add_argument("--loop-id", required=True)
    fast_alert.add_argument("--cluster-names-json", required=True)

    stop = subparsers.add_parser("request-stop")
    stop.add_argument("--observation-id", required=True)
    stop.add_argument("--requested-by", required=True)
    stop.add_argument("--at")

    resume = subparsers.add_parser("resume")
    resume.add_argument("--observation-id", required=True)
    resume.add_argument("--at")

    complete = subparsers.add_parser("complete")
    complete.add_argument("--observation-id", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "read": command_read,
        "init": command_init,
        "set-baseline": command_set_baseline,
        "start-observing": command_start_observing,
        "heartbeat": command_heartbeat,
        "start-round": command_start_round,
        "finish-round": command_finish_round,
        "record-fast-alert": command_record_fast_alert,
        "request-stop": command_request_stop,
        "resume": command_resume,
        "complete": command_complete,
    }
    try:
        result = commands[args.command](args)
    except StateError as exc:
        response: dict[str, Any] = {"ok": False, "error": str(exc)}
        if exc.important_prompt:
            response["important_prompt"] = exc.important_prompt
        print(json.dumps(response, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"internal error: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "state": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
