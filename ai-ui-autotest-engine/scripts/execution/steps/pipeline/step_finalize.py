"""步骤收口：失败分析、Review 指引、flow-context 回写、AI checklist。"""
import os
from execution.engine.flow.step_scheduler import (
    update_step_result as fc_update_step,
    apply_followup_result as fc_apply_followup,
)
from execution.engine.flow.flow_context import load_context as fc_load
from shared.observability.runtime_audit import append_event


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
def _pending_required_hooks(root_dir, current_sid):
    """当前步骤下未完成的必需 hooks（唯一实现，供 review 指引与 AI checklist 共用）。"""
    if not current_sid:
        return []
    flow_context = fc_load(root_dir)
    if not flow_context:
        return []
    for step in flow_context.get("steps", []):
        if step.get("sid") == current_sid:
            return [h for h in step.get("hooks", [])
                    if h.get("required") and not h.get("completed")]
    return []


def _print_step_review_guidance(is_review_required, step_result, assertions_dict,
                                current_sid, root_dir):
    """打印 Review 指引信息。

    区分两种「需复核」：
      - 有必需 hook 待处理（PENDING / 失败 / 断言待判定）→ 按 hooks 指引继续；
      - 仅命中或判定非字面精确（语义等价 / 视觉 / 唯一子串兜底）→ 已标记待人工复核，
        但无 hook，不阻断流程。措辞必须区分，否则会误导为「按 hooks 处理」却无 hook。
    """
    if not is_review_required:
        print("  ✅ [T1 PASS] 程序化精确匹配全部通过，无需人工介入，直接 flow-next 推进")
        return
    if step_result is None:
        print("  📍 [PENDING] T1 程序化匹配未命中，需 T2 AI 语义匹配或 T3 视觉确认")
    elif _pending_required_hooks(root_dir, current_sid):
        print("  [REVIEW] 数据已收集，按 hooks 指引完成断言验证后 flow-next 推进")
    else:
        print("  📌 [REVIEW] 非字面精确命中（语义等价 / 视觉 / 唯一子串兜底），已标记待人工复核；"
              "本步无 hook 需处理，可直接 flow-next 推进")
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
    if run.for_sid:
        # 归属型兜底（--for-sid）：只落记录（steps.jsonl）+ 事件，不改父步骤结论/hooks。
        # 结论权在断言与 AI override —— 若在此写结论，兜底点击会「提前宣布该步通过」。
        append_event(run.root_dir, "step.fallback", {
            "case_index": run.case_index, "sid": run.for_sid,
            "action": args.step_action or "", "result": run.step_result,
            "screenshot": run.screenshot_name,
        })
    elif run.retry_parent_sid:
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
                           "action_type": args.step_action or "",
                           "action_arg": getattr(args, "action_arg", None) or "",
                       })
        append_event(run.root_dir, "step.completed", {
            "case_index": run.case_index, "sid": run.current_sid, "result": run.step_result, "screenshot": run.screenshot_name,
        })
def _print_ai_checklist(root_dir, current_sid, retry_parent_sid):
    """打印 AI 后续操作清单（hooks 驱动）。"""
    if retry_parent_sid:
        return
    pending_hooks = _pending_required_hooks(root_dir, current_sid)
    if not pending_hooks:
        return
    first_hook = pending_hooks[0]
    first_hook_id = first_hook["id"]
    remaining_hook_count = len(pending_hooks) - 1
    hint = f"STEP [AI_CHECKLIST] {first_hook_id}"
    if remaining_hook_count > 0:
        hint += f"（后续还有 {remaining_hook_count} 个 hook 待完成）"
    print(hint)
    print(f"  hook [TODO] {first_hook_id}: {first_hook.get('desc', '')}")
    print(f"  → 详情: <入口> hook-info --hook-id {first_hook_id} --sid {current_sid}")
    print(f"  → 完成后: <入口> flow-next --done-hooks {first_hook_id}")
