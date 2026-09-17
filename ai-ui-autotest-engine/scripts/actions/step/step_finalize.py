"""步骤收口：失败分析、Review 指引、flow-context 回写、AI checklist。"""
import os
from core.flow.step_scheduler import (
    update_step_result as fc_update_step,
    apply_followup_result as fc_apply_followup,
)
from core.flow.flow_context import load_context as fc_load
from core.audit.runtime_audit import append_event


def _build_failure_analysis(action_ok, action_failure_reason, failure_context,
                             unavailable_assertions, assertion_failure_reason, screenshot_name):
    """构建故障分析字典。

    action_ok tri-state: True=通过, False=失败, None=handoff（handoff 不视为失败）
    """
    if action_ok is False:  # 真失败
        failure_analysis = {"error": action_failure_reason}
        failure_analysis.update(failure_context)
        if screenshot_name:
            failure_analysis["screenshot"] = screenshot_name
        return failure_analysis
    if unavailable_assertions:
        failure_analysis = {
            "assert_fails": [f.get("expect", "") for f in unavailable_assertions],
            "assert_reason": assertion_failure_reason,
        }
        if screenshot_name:
            failure_analysis["screenshot"] = screenshot_name
        return failure_analysis
    return None
def _print_step_review_guidance(is_review_required, step_result, assertions_dict, current_sid):
    """打印 Review 指引信息。"""
    if not is_review_required:
        print("  ✅ [T1 PASS] 程序化匹配全部通过，无需 AI 介入，直接 flow-next 推进")
        return
    if step_result is None:
        print("  📍 [PENDING] T1 程序化匹配未命中，需 T2 AI 语义匹配或 T3 视觉确认")
    else:
        print("  [REVIEW] 数据已收集，按 hooks 指引完成断言验证后 flow-next 推进")
    if assertions_dict and current_sid:
        text_items = assertions_dict.get("text", [])
        if text_items:
            sidecar_path = (text_items[0].get("evidence") or {}).get("sidecar", "")
            if sidecar_path and os.path.isfile(sidecar_path):
                print(f"  📐 元素目录已写入 sidecar: {sidecar_path}（AI 分析时用 read_file 查看）")
def _update_flow_context_after_step(run):
    """更新 flow-context.json 并记录 audit 事件。

    run.action_ok: tri-state — True=通过, False=失败, None=handoff（待AI决策）
    """
    args = run.args
    is_handoff = run.action_ok is None
    is_fail = run.action_ok is False
    needs_ai_followup = run.failure_context.get("needs_ai_followup", False) if (is_handoff or is_fail) else False
    raw_asserts = getattr(args, "asserts", None)
    if run.retry_parent_sid:
        fc_apply_followup(run.root_dir, run.retry_parent_sid, run.step_result)
        append_event(run.root_dir, "step.retry", {
            "case_index": run.case_index, "parent_sid": run.retry_parent_sid,
            "retry_sid": run.sid_arg, "result": run.step_result, "screenshot": run.screenshot_name,
        })
    else:
        fc_update_step(run.root_dir, run.current_sid, run.step_result,
                       args.step_action or "",
                       screenshot=run.screenshot_name, fail_reason=run.action_failure_reason,
                       needs_ai_followup=needs_ai_followup,
                       action_x=getattr(args, "action_x", None), action_y=getattr(args, "action_y", None),
                       effect_desc=args.desc or "",
                       assertions=run.assertions_dict if raw_asserts else None,
                       step_context={
                           "failure_context": run.failure_context if (is_handoff or is_fail) else None,
                           "screenshot_name": run.screenshot_name or "",
                           "screenshot_path": run.screenshot_path or "",
                           "action_arg": getattr(args, "action_arg", None) or "",
                       })
        append_event(run.root_dir, "step.completed", {
            "case_index": run.case_index, "sid": run.current_sid, "result": run.step_result, "screenshot": run.screenshot_name,
        })
def _print_ai_checklist(root_dir, current_sid, retry_parent_sid):
    """打印 AI 后续操作清单（hooks 驱动）。"""
    if retry_parent_sid:
        return
    flow_context = fc_load(root_dir)
    if not flow_context:
        return
    pending_hook_ids = []
    for step in flow_context.get("steps", []):
        if step.get("sid") == current_sid:
            for hook in step.get("hooks", []):
                if hook.get("required") and not hook.get("completed"):
                    pending_hook_ids.append(hook["id"])
            break
    if not pending_hook_ids:
        return
    first_hook_id = pending_hook_ids[0]
    remaining_hook_count = len(pending_hook_ids) - 1
    hint = f"STEP [AI_CHECKLIST] {first_hook_id}"
    if remaining_hook_count > 0:
        hint += f"（后续还有 {remaining_hook_count} 个 hook 待完成）"
    print(hint)
    first_incomplete_hook = None
    for step in flow_context.get("steps", []):
        if step.get("sid") == current_sid:
            incomplete_hooks = [h for h in step.get("hooks", []) if h.get("required") and not h.get("completed")]
            first_incomplete_hook = incomplete_hooks[0] if incomplete_hooks else None
            break
    if first_incomplete_hook:
        desc = first_incomplete_hook.get("desc", "")
        print(f"  hook [TODO] {first_incomplete_hook['id']}: {desc}")
        print(f"  → 详情: python3 scripts/cli.py hook-info --hook-id {first_incomplete_hook['id']} --sid {current_sid}")
    print(f"  → 完成后: python3 scripts/cli.py flow-next --done-hooks {first_hook_id}")
