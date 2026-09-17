"""步骤动作执行：委派到 actions.handlers 的 handler，返回 tri-state 结果。"""
from actions.handlers import get_handler
from core.audit.runtime_audit import append_event


def _execute_action_handler(args, root_dir, case_index, sid_arg):
    """执行操作并返回执行结果。

    返回值 action_ok 为 tri-state:
      True  = 执行通过
      False = 执行失败（设备/参数错误）
      None  = handoff（等待 AI 通过 reason hook 决策）
    """
    action = args.step_action
    action_arg = getattr(args, 'action_arg', None) or ""
    handler = get_handler(action)
    if handler:
        result = handler(action_arg, args)
        action_ok = result["ok"]  # True / False / None — tri-state
        failure_reason = result.get("reason", "")
        failure_context = result.get("ctx", {})
        inspect_tree_impact = result.get("inspect_tree_impact", "unknown")
        retry_metadata = failure_context.get("_retry")
        if retry_metadata:
            append_event(root_dir, "engine.action.retry", {
                "case_index": case_index, "sid": sid_arg, "action": action,
                "retry_count": retry_metadata.get("count", 0),
                "detail": retry_metadata.get("detail", ""),
                "attempts": retry_metadata.get("attempts"),
                "action_arg": action_arg,
            })
    else:
        print(f"  UNKNOWN action: {action}")
        action_ok = False
        failure_reason = f"未知 action: {action}"
        failure_context = {"action": action, "reason": "UNKNOWN_ACTION"}
        inspect_tree_impact = "unknown"
    return action_ok, failure_reason, failure_context, inspect_tree_impact
