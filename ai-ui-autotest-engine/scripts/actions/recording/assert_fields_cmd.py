"""assert-fields 命令：AI 断言 API/Track 步骤的字段级别结果。"""

import json

from core.errors import FlowStateError, PayloadError, UsageError
from core.util.case_utils import resolve_case_path, current_case_workspace, resolve_mis
from core.flow.flow_context import load_context as fc_load, save_context as fc_save
from core.flow.step_scheduler import (
    apply_followup_result as fc_apply_followup,
    mark_hook_done as fc_mark_hook_done,
)
from core.util.records import StepRecord, SRC_ASSERT_FIELDS
from actions.recording.common import _resolve_duration
from actions.track_step_executor import select_candidate


# API/Track 步骤对应的 hook ID 映射
_HOOK_KIND_MAP = {
    "api": "verify_api_fields",
    "track": "verify_track_fields",
}


def _sync_resolved_fields(root_dir, flow_context, sid, field_results):
    """把 assert-fields 解析出的**真实字段路径**回写到步骤的 api_assert.expected_fields。

    生成期 Flow 通常只给语义（如「价格字段」「评论列表数据」），真实 JSON 路径
    只有执行后经 response-search 才能确定。回写后 flow-context 与报告口径一致，
    消除「声明是语义名、判定是真实路径」的割裂。原始声明另存 `declared_fields` 溯源。

    配对规则：按索引一一对应，**条数不一致时不回写**（无法安全配对，宁可保留原声明）。
    返回 True 表示已回写。
    """
    if not flow_context:
        return False
    for step in flow_context.get("steps", []):
        if step.get("sid") != sid:
            continue
        api_assert = step.get("api_assert")
        if not isinstance(api_assert, dict):
            return False
        declared = api_assert.get("expected_fields") or []
        if not isinstance(declared, list) or len(declared) != len(field_results):
            return False
        resolved = []
        for i, fr in enumerate(field_results):
            old = declared[i] if isinstance(declared[i], dict) else {}
            resolved.append({
                "source": old.get("source", "response"),
                "field": fr.get("field", ""),
                "expected": fr.get("expected") or old.get("expected", ""),
            })
        if declared and not api_assert.get("declared_fields"):
            api_assert["declared_fields"] = declared
        api_assert["expected_fields"] = resolved
        fc_save(root_dir, flow_context)
        return True
    return False


def _get_step(flow_context, sid):
    """按 sid 取 flow-context 中的步骤定义。"""
    for step in (flow_context or {}).get("steps", []):
        if step.get("sid") == sid:
            return step
    return None


def _get_track_fields(flow_context, sid):
    """取步骤断言里的 track_fields（埋点匹配上下文）。"""
    step = _get_step(flow_context, sid)
    return ((step or {}).get("assertions") or {}).get("track_fields") or {}


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

    picked = getattr(args, "picked", None)
    track_fields = _get_track_fields(flow_context, sid)
    appmock_url = None

    # ── 埋点多候选：必须显式消歧 ────────────────────────────────
    # 候选文件保存了每个候选的原始事件；选定后重建最终证据，报告口径与判定一致。
    if track_fields.get("ambiguous"):
        if picked is None:
            raise UsageError(
                "ASSERT-FIELDS ABORT: 埋点命中多个候选，必须用 --picked <序号> 显式选定目标事件"
                f"（候选文件: {track_fields.get('candidates_path') or '(无)'}）"
            )
        mis = resolve_mis(flow_context.get("meta", {}).get("user_mis", ""))
        chosen, appmock_url = select_candidate(
            case_workspace, sid,
            track_fields.get("candidates_path", ""),
            picked,
            expected_fields=track_fields.get("expected_fields") or None,
            mis=mis,
        )
        print(f"ASSERT-FIELDS [{sid}]: 已选定候选 #{picked} "
              f"(nm={chosen.get('nm')}, val_bid={chosen.get('val_bid') or '(无)'})")
    elif picked is not None:
        raise UsageError(
            "ASSERT-FIELDS ABORT: 本步骤为唯一命中，无需 --picked（仅多候选消歧时使用）"
        )

    all_pass = all(r.get("pass", False) for r in field_results)
    total = len(field_results)
    passed = sum(1 for r in field_results if r.get("pass", False))
    failed = total - passed
    ok = 1 if all_pass else 0
    duration, _ = _resolve_duration(args, case_workspace)

    # 回写真实字段路径 → flow-context（必须在 mark_hook_done 之前，避免后者重载覆盖）
    synced = _sync_resolved_fields(root_dir, flow_context, sid, field_results)

    record = StepRecord(
        sid=sid,
        src=SRC_ASSERT_FIELDS,
        type="assert-fields",
        desc=desc,
        ok=ok,
        status="PASS" if all_pass else "FAIL",
        ms=duration,
        # fa.field_results 是报告层的读取契约：
        #   report/schema.build_evidence → evidence.raw.field_results
        #   → report/steps._expand_field_results_to_fields（展开为 api_assert.<真实路径>）
        failure={"field_results": field_results},
        extra={"assert_fields": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "picked": picked,
            "results": field_results,
        }},
    )
    if appmock_url:
        record.extra["appmock_url"] = appmock_url
    record.append(case_workspace)

    # 结论写回步骤：埋点多候选步骤初始为 PENDING，只有在这里才被定案。
    # 否则 mark_hook_done 会把「所有 required hook 已完成」的 PENDING 步骤无条件
    # 修正为 PASS（_finalize_effect_pending_step），掩盖选错候选 / 字段不匹配的失败。
    if _get_step(flow_context, sid) is not None:
        fc_apply_followup(root_dir, sid, ok)

    # 从 flow-context 查询步骤定义，确定正确的 hook_id
    hook_id = "verify_api_fields"  # 默认使用 API hook
    step = _get_step(flow_context, sid)
    if step is not None:
        kind = step.get("kind", "api")
        hook_id = _HOOK_KIND_MAP.get(kind, "verify_api_fields")
    fc_mark_hook_done(root_dir, sid, hook_id)

    print(f"ASSERT-FIELDS [{sid}]: {desc} → {'✅ PASS' if all_pass else '❌ FAIL'} ({passed}/{total})")
    print(f"  字段路径回写 flow-context: {'已同步' if synced else '未回写（条数不匹配或非 api 步骤）'}")
