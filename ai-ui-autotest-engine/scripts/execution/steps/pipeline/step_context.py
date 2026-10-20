"""步骤执行上下文：初始化、sid 冲突/重试识别、参数契约校验。"""
import os
from shared.case_utils import current_case_workspace, resolve_case_path
from shared.errors import FlowStateError, UsageError
from execution.engine.sop.actions import NON_IDEMPOTENT_ACTIONS, validate_action_args
from execution.engine.flow.flow_context import load_context as fc_load


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
def _reject_non_idempotent_rerun(args, step, sid):
    """拒绝「不可重跑动作」的原地重跑（已执行过的步骤）。

    为什么必须拦：这些动作重跑会产生**不可撤销**的副作用 —— 实测 `back` 原地重跑
    （弹窗已关时多退一页）把页面退出了目标页，后续断言全部失准。

    「已执行过」用 flow-context 的 `started_at` 判定（_cmd_step 在执行动作前写入），
    比 status 可靠：flow-init 把所有步骤初始化为 pending，status 分不出「未执行」。
    """
    action = getattr(args, "step_action", None)
    if action not in NON_IDEMPOTENT_ACTIONS or not step.get("started_at"):
        return
    raise FlowStateError(
        f"STEP ABORT: sid [{sid}] 的动作 {action} 不可原地重跑 —— 它已执行过"
        f"（started_at={step.get('started_at')}），重跑会累积不可撤销的副作用"
        f"（back 多退一页 / input 重复叠加）。\n"
        f"  请按 hooks 收口本次执行：\n"
        f"    · 断言待判定 → override-step-result --sid {sid} --assert-verdict '...'\n"
        f"    · 确需再执行一次 → 换新 sid：step --sid {sid}b {action} ...（记为父步骤 retry）\n"
        f"    · 页面已偏离目标页 → 用 open-url 恢复落地页后再继续后续步骤"
    )


def _resolve_sid_conflict(args, flow_context):
    """解析 sid 归属：声明执行（--sid）/ 归属型兜底（--for-sid）/ 重试（--sid <父SID><字母>）。

    返回 (sid_arg, step_definition, retry_parent_sid, for_sid)。

    三种形态的语义差异（决定记录如何进报告）：
      · --sid S1        → 本命令就是声明步骤 S1，走完整管道，可改写结论；
      · --for-sid S1    → 兜底操作归属 S1：记录进 S1 的证据/attempts，**不改其结论**
                          （结论权在断言与 AI override）；必须指向已声明 SID；
      · --sid S1b       → 重试 S1：映射到父 S1 并参与结论（重跑语义）。
    """
    sid_arg = getattr(args, "sid", None)
    for_sid = getattr(args, "for_sid", None)
    step_definition = None
    retry_parent_sid = None

    if for_sid:
        if not flow_context:
            raise FlowStateError("STEP ABORT: flow-context.json 不存在，无法解析 --for-sid")
        declared = [s.get("sid") for s in flow_context.get("steps", [])]
        if for_sid not in declared:
            raise UsageError(
                f"STEP ABORT: --for-sid {for_sid} 不是已声明的步骤 SID；"
                f"兜底操作必须归属到已声明步骤（可用: {', '.join(x for x in declared if x)}）"
            )
        # 不走 retry 路径：兜底只归属证据，不参与结论映射。
        return for_sid, step_definition, retry_parent_sid, for_sid

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
                _reject_non_idempotent_rerun(args, step, sid_arg)
                break
        if step_definition is None:
            retry_parent_sid = _detect_retry_parent_sid(sid_arg, flow_context)
    return sid_arg, step_definition, retry_parent_sid, None
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


def _ensure_step_desc(args):
    """为未提供 --desc 的步骤补全可读描述（原地写回 args.desc）。

    声明步骤由 SOP 传入 --desc；独立/兜底操作（坐标点击、滚动到目标、返回等）
    在 hook 指引里通常不带 --desc，若直接落盘会得到一条 desc 为空的孤立 finding，
    在报告里表现为一条没有描述的多余记录。这里按 action + 参数派生描述：
    既保证记录可读，也不强制每个调用点都手写 --desc（否则会打断既有 hook 指引）。
    """
    if (getattr(args, "desc", "") or "").strip():
        return
    action = getattr(args, "step_action", "") or "step"
    arg = (getattr(args, "action_arg", "") or "").strip()
    anchor = (getattr(args, "action_anchor", "") or "").strip()
    url = (getattr(args, "url", "") or "").strip()
    ax = getattr(args, "action_x", None)
    ay = getattr(args, "action_y", None)
    if action == "open-url" and url:
        desc = f"open-url {url}"
    elif action in ("tap-text", "scroll-until") and arg:
        desc = f"{action} 「{arg}」"
    elif action in ("input-text", "blur-input") and anchor:
        desc = f"{action} @「{anchor}」"
    elif action == "tap" and anchor:
        # 锚点形态：action_anchor 是锚点文案（无文案图标所在行）
        desc = f"tap @「{anchor}」"
    elif action == "tap" and ax is not None and ay is not None:
        desc = f"tap @({ax},{ay})"
    elif action == "scroll-edge":
        desc = f"scroll-edge {getattr(args, 'direction', '') or 'down'}"
    else:
        desc = action
    args.desc = desc
