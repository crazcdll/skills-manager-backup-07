"""assert-fields 命令：AI 断言 API/Track 步骤的字段级别结果。"""

import json
from core.errors import FlowStateError, PayloadError, UsageError
from core.util.case_utils import resolve_case_path, current_case_workspace
from core.flow.flow_context import load_context as fc_load
from core.flow.step_scheduler import mark_hook_done as fc_mark_hook_done
from core.util.records import StepRecord, SRC_ASSERT_FIELDS
from actions.recording.common import _resolve_duration


# API/Track 步骤对应的 hook ID 映射
_HOOK_KIND_MAP = {
    "api": "verify_api_fields",
    "track": "verify_track_fields",
}


def _cmd_assert_fields(args):
    """assert-fields 命令入口。"""
    root_dir = resolve_case_path(args.dir)
    flow_context = fc_load(root_dir)
    if flow_context is None:
        raise FlowStateError("ASSERT-FIELDS ABORT: flow-context.json 不存在")
    case_workspace = current_case_workspace(root_dir, flow_context)

    sid = getattr(args, "sid", None)
    if not sid:
        raise UsageError("ASSERT-FIELDS ABORT: --sid 是必填参数")

    desc = getattr(args, "desc", "")
    results_str = getattr(args, "results", None)
    if not results_str:
        raise UsageError("ASSERT-FIELDS ABORT: --results 是必填参数")

    try:
        field_results = json.loads(results_str)
    except json.JSONDecodeError as e:
        raise PayloadError(f"ASSERT-FIELDS ABORT: --results JSON 解析失败: {e}") from e

    if not isinstance(field_results, list):
        raise PayloadError("ASSERT-FIELDS ABORT: --results 必须是 JSON 数组")

    all_pass = all(r.get("pass", False) for r in field_results)
    total = len(field_results)
    passed = sum(1 for r in field_results if r.get("pass", False))
    failed = total - passed
    ok = 1 if all_pass else 0
    duration, _ = _resolve_duration(args, case_workspace)

    record = StepRecord(
        sid=sid,
        src=SRC_ASSERT_FIELDS,
        type="assert-fields",
        desc=desc,
        ok=ok,
        status="PASS" if all_pass else "FAIL",
        ms=duration,
        extra={"assert_fields": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": field_results,
        }},
    )
    record.append(case_workspace)

    # 从 flow-context 查询步骤定义，确定正确的 hook_id
    hook_id = "verify_api_fields"  # 默认使用 API hook
    if flow_context:
        for step in flow_context.get("steps", []):
            if step.get("sid") == sid:
                kind = step.get("kind", "api")
                hook_id = _HOOK_KIND_MAP.get(kind, "verify_api_fields")
                break
    fc_mark_hook_done(root_dir, sid, hook_id)

    print(f"ASSERT-FIELDS [{sid}]: {desc} → {'✅ PASS' if all_pass else '❌ FAIL'} ({passed}/{total})")
