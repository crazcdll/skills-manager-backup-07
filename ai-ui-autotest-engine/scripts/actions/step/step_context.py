"""步骤执行上下文：初始化、sid 冲突/重试识别、参数契约校验。"""
import os
from core.util.case_utils import current_case_workspace, resolve_case_path
from core.errors import FlowStateError, UsageError
from core.sop.actions import validate_action_args
from core.flow.flow_context import load_context as fc_load


def _detect_retry_parent_sid(sid, flow_context):
    """判断 sid 是否为已声明步骤的重试。"""
    if not sid or not flow_context:
        return None
    for step in flow_context.get("steps", []):
        parent_sid = step.get("sid", "")
        if not parent_sid or parent_sid == sid:
            continue
        if sid.startswith(parent_sid):
            suffix = sid[len(parent_sid):]
            if suffix and suffix.isalpha():
                parent_status = step.get("status", "")
                if parent_status == "completed":
                    continue
                return parent_sid
    return None
def _init_step_context(args):
    """初始化步骤执行上下文。"""
    root_dir = resolve_case_path(getattr(args, "dir", None))
    flow_context = fc_load(root_dir)
    if flow_context is None:
        raise FlowStateError("STEP ABORT: flow-context.json 不存在")
    case_workspace = current_case_workspace(root_dir, flow_context)
    os.makedirs(case_workspace, exist_ok=True)
    case_index = flow_context.get("current_case", {}).get("index")
    return root_dir, flow_context, case_workspace, case_index
def _resolve_sid_conflict(args, flow_context):
    """检查 sid 冲突。"""
    sid_arg = getattr(args, "sid", None)
    step_definition = None
    retry_parent_sid = None
    if sid_arg and flow_context:
        for step in flow_context.get("steps", []):
            if step.get("sid") == sid_arg:
                step_definition = step
                if step.get("status") in ("completed", "failed"):
                    existing_result = step.get("ok")
                    existing_verdict = {1: "PASS", 2: "WARN", 0: "FAIL"}.get(existing_result, existing_result)
                    raise FlowStateError(
                        f"STEP ABORT: sid [{sid_arg}] 已有结果（{existing_verdict}，完成于 {step.get('completed_at')}），"
                        f"禁止重跑。如需补充说明用 log-record，如需追加终态发现用 "
                        f"override-step-result --sid {sid_arg} --pass/--fail/--ok。"
                    )
                break
        if step_definition is None:
            retry_parent_sid = _detect_retry_parent_sid(sid_arg, flow_context)
    return sid_arg, step_definition, retry_parent_sid
def _validate_step_parameters(step_definition, args):
    """校验步骤参数契约。"""
    step_kind = step_definition.get("kind", "ui") if step_definition else "ui"
    if step_kind == "ui" and args.step_action:
        validation_error = validate_action_args(args.step_action, args)
        if validation_error:
            raise UsageError(f"STEP ABORT: action={args.step_action} {validation_error}")
        if args.step_type == "assert" and not getattr(args, "asserts", None):
            raise UsageError(
                "STEP ABORT: --step-type assert 必须提供 --asserts JSON 数组，"
                "否则断言不会被执行、步骤会被静默判定为 PASS"
            )
