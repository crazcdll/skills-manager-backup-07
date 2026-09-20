"""Step 执行引擎：公共管道（设备检查 → action → wait → screenshot → assert → log）。

截图在断言之前执行，确保 visual 断言和 hook 阶段能拿到真实截图。
断言引擎只收集数据（元素索引/截图），AI 在 hook 阶段做判定。

本模块只保留「步骤编排」：`_cmd_step` 按序调用各阶段函数。
阶段实现分别在：
    step_context.py   上下文 / sid 冲突 / 参数校验
    step_guards.py    漂移检测 / 设备连通性 / Recce 清理
    step_action.py    动作执行（tri-state）
    step_capture.py   截图
    step_assert.py    断言数据收集
    step_finalize.py  失败分析 / Review 指引 / flow-context 回写 / AI checklist
    step_pipeline.py  上述阶段的按序编排单元
    step_run.py       运行状态容器（StepRun）
"""
import time

from core.errors import StepAssertionError
from context import get_platform_ops
from screen_state.inspect_tree import invalidate_cache
from actions.api_step_executor import execute_api_step
from actions.track_step_executor import execute_track_step
from core.flow.step_scheduler import set_step_started as fc_set_step_started
from core.audit.runtime_audit import append_event
from actions.step.step_context import (
    _ensure_step_desc, _init_step_context, _resolve_sid_conflict,
    _validate_step_parameters,
)
from actions.step.step_finalize import (
    _print_ai_checklist, _print_step_review_guidance, _update_flow_context_after_step,
)
from actions.step.step_guards import _check_device_connectivity, _dismiss_recce_layer
from actions.step.step_pipeline import (
    capture, collect_assertions, compute_result, merge_assertion_failures,
    print_summary, run_action, wait_page, warn_on_drift, write_record,
)
from actions.step.step_run import StepRun


def _dispatch_non_ui_step(step_definition, root_dir, case_workspace, flow_context, args):
    """将非 UI 步骤（api/track）分发到独立执行器。

    返回 (handled, exit_code)：api/track 是终态步骤，执行器已完整处理该步
    （含落盘 / 更新 flow-context），handled=True 时调用方必须立即返回，
    不得再进入 UI 管道（否则会重复截图 / 重复记日志 / 覆盖步骤结果）。
    """
    kind = step_definition.get("kind", "ui") if step_definition else "ui"
    if kind == "api":
        return True, execute_api_step(root_dir, case_workspace, flow_context, step_definition, args)
    if kind == "track":
        return True, execute_track_step(root_dir, case_workspace, flow_context, step_definition, args)
    return False, None


def _cmd_step(args):
    """操作 → 等待 → 截图 → 断言 → 日志。按 kind 分发（ui/api/track）。

    本函数只做「编排」：每个编号对应原流程的一个阶段，具体实现见各 step_* 模块。
    """
    # 0) 作废视图树缓存：保证每个 step 开始都能读到最新页面状态
    invalidate_cache()

    # 1~3) 上下文初始化 / sid 冲突检查 / 参数契约校验
    _ensure_step_desc(args)
    root_dir, flow_context, case_workspace, case_index = _init_step_context(args)
    run = StepRun(args=args, root_dir=root_dir, flow_context=flow_context,
                  case_workspace=case_workspace, case_index=case_index,
                  step_start=time.time())
    (run.sid_arg, run.step_definition,
     run.retry_parent_sid) = _resolve_sid_conflict(args, flow_context)
    run.effective_sid = run.retry_parent_sid or getattr(args, "sid", None)
    run.current_sid = run.effective_sid or ""
    _validate_step_parameters(run.step_definition, args)

    # 4) 记录步骤开始
    if run.sid_arg:
        fc_set_step_started(root_dir, run.sid_arg)
        append_event(root_dir, "step.started", {"case_index": case_index, "sid": run.sid_arg})

    # 5) 分发非 UI 步骤（api/track）—— 终态步骤，处理完直接收口
    handled, code = _dispatch_non_ui_step(
        run.step_definition, root_dir, case_workspace, flow_context, args
    )
    if handled:
        return code

    # 6~9) 偏移检测 / 设备连通性检查 / Recce 调试浮层清理
    warn_on_drift(run)
    run.ops = get_platform_ops()
    _check_device_connectivity(run.ops, root_dir, case_workspace, args, case_index)
    _dismiss_recce_layer(args)

    # 10~18) 操作 → 等待 → 截图 → 断言 → 结论 → 落盘 → 打印
    run_action(run)
    wait_page(run)
    capture(run)
    collect_assertions(run)
    merge_assertion_failures(run)
    compute_result(run)
    write_record(run)
    print_summary(run)

    # 19~21) Review 指引 / flow-context 回写 / AI 后续操作清单
    _print_step_review_guidance(run.is_review_required, run.step_result,
                                run.assertions_dict, run.current_sid)
    _update_flow_context_after_step(run)
    _print_ai_checklist(run.root_dir, run.current_sid, run.retry_parent_sid)

    # 22) 退出码：handoff（None）正常继续，只有真失败（False）才退出
    if run.action_ok is False:
        raise StepAssertionError(f"步骤执行失败: sid={run.current_sid}")
