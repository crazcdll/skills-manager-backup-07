"""步骤执行管道：把原 `_cmd_step` 的线性 22 步流程拆为独立阶段函数。

每个阶段只读写 `StepRun`、不返回值；`_cmd_step` 只负责按序调用。
阶段内部逻辑与拆分前**逐字一致**，仅把局部变量替换为 `run.*` 字段。

阶段顺序（与原 _cmd_step 的步骤编号一一对应）：
    warn_on_drift            6) 偏移检测
    run_action               10) 执行操作（含 debug 截图）
    wait_page                11) 页面稳定等待
    capture                  12) 截图（在断言之前）
    collect_assertions       13) 断言数据收集
    merge_assertion_failures 14) 动作失败 + 断言不可用 → 合并
    compute_result           15) 耗时 + tri-state 结论 + review 判定
    write_record             16~17) 构建并落盘 StepRecord
    print_summary            18) 打印步骤结果
"""
import time

from actions.step.step_action import _execute_action_handler
from actions.step.step_assert import (
    _collect_unavailable_assertions, _execute_assertion_pipeline,
)
from actions.step.step_capture import _take_step_screenshot
from actions.step.step_finalize import _build_failure_analysis
from actions.step.step_guards import _check_prior_drift
from assertions.constants import STEP_OK_STATUS
from assertions.engine import compute_step_ok
from core.sop.hook_router import compute_review_required
from core.util.records import (
    StepRecord, SRC_STEP, SRC_RETRY, SHOT_STEP, frame_path,
)
from screen_state.page_stability import wait_page_stable


def warn_on_drift(run):
    """6) 偏移检测：上一步有未完成 hook 时给出操作指引（不阻断）。"""
    drift_msg, prior_sid = _check_prior_drift(run.root_dir, getattr(run.args, "sid", ""))
    if not drift_msg:
        return
    print(f"STEP [DRIFT_WARNING] {drift_msg}")
    print(f"  ⚠️ 请先完成上一步 [{prior_sid}] 的后续操作，再执行当前步骤")
    print(f"  如上一步弹窗未关闭：用 find-icon --anchor <邻近文案> 从结构树中读出关闭按钮坐标 + "
          f"step tap --action-x <x> --action-y <y> 关闭 + log-record 记录")
    print(f"  完成后用 python3 scripts/cli.py flow-next --done-hooks <hook_id> 标记")


def run_action(run):
    """10) 执行操作（assert-text 无操作，跳过）+ 可选 debug 截图。"""
    args = run.args
    if run.action_ok is True and args.step_action and args.step_action != "assert-text":
        (run.action_ok, run.action_failure_reason,
         run.failure_context, run.inspect_tree_impact) = _execute_action_handler(
            args, run.root_dir, run.case_index, run.sid_arg,
        )
        if getattr(args, "debug_shot", False):
            debug_name = f"{args.sid or 'step'}_after_action.png"
            if run.case_index is not None:
                debug_name = f"case_{run.case_index + 1:02d}_{debug_name}"
            debug_path = frame_path(run.case_workspace, debug_name)
            run.ops.screenshot(debug_path)
            print(f"  🔍 DEBUG-SHOT -> {debug_path}")


def wait_page(run):
    """11) 页面稳定等待。"""
    if getattr(run.args, "page_ready", False):
        wait_page_stable()


def capture(run):
    """12) 截图（在断言执行之前，确保 visual 断言与 hook 阶段拿到真实截图）。"""
    run.screenshot_name, run.screenshot_path = _take_step_screenshot(
        run.args, run.case_workspace, run.case_index, run.ops,
    )


def collect_assertions(run):
    """13) 断言数据收集（T1 程序化匹配；判定留给 hook 阶段的 AI）。"""
    (run.assertion_results, run.assertions_dict,
     run.execute_results) = _execute_assertion_pipeline(
        run.args, run.ops, run.case_workspace, run.screenshot_path,
        run.sid_arg, run.inspect_tree_impact,
    )


def merge_assertion_failures(run):
    """14) 动作失败 + 断言数据不可用 → 合并失败原因与上下文。"""
    run.unavailable_assertions, run.assertion_failure_reason = _collect_unavailable_assertions(
        run.assertion_results
    )
    if run.unavailable_assertions and run.action_ok is False:
        run.action_failure_reason = (
            run.action_failure_reason + "; " + run.assertion_failure_reason
            if run.action_failure_reason else run.assertion_failure_reason
        )
        run.failure_context = {
            "action": "assert",
            "reason": "ASSERT_FAIL",
            "fails": [f.get("expect", "") for f in run.unavailable_assertions],
        }


def compute_result(run):
    """15) 耗时 + 结论（tri-state）+ 是否需要 review。"""
    run.duration_ms = int((time.time() - run.step_start) * 1000)
    raw_asserts = getattr(run.args, "asserts", None)
    if run.action_ok is None:
        run.step_result = None                       # PENDING — handoff
    elif run.action_ok and raw_asserts:
        run.step_result = compute_step_ok(run.execute_results)
    else:
        run.step_result = 1 if run.action_ok else 0
    run.is_review_required = compute_review_required(run.step_result, run.failure_context)


def write_record(run):
    """16~17) 构建并落盘 StepRecord（统一写入契约）。"""
    args = run.args
    failure_analysis = _build_failure_analysis(
        run.action_ok, run.action_failure_reason, run.failure_context,
        run.unavailable_assertions, run.assertion_failure_reason, run.screenshot_name,
    )
    record = StepRecord(
        sid=run.effective_sid or "",
        src=SRC_RETRY if run.retry_parent_sid else SRC_STEP,
        type=args.step_type or "misc",
        desc=args.desc or "",
        ok=run.step_result,
        status=STEP_OK_STATUS.get(run.step_result, ""),
        ms=run.duration_ms,
        asserts=run.assertion_results or [],
        failure=failure_analysis,
    )
    record.shot(run.screenshot_name, label="步骤截图", kind=SHOT_STEP)
    if run.action_ok is True and run.failure_context.get("low_confidence_warning"):
        record.note = run.failure_context["low_confidence_warning"]
    if run.retry_parent_sid:
        record.extra["retry_sid"] = run.sid_arg
    record.extra["review_required"] = run.is_review_required
    record.append(run.case_workspace)
    run.record = record


def print_summary(run):
    """18) 打印步骤结果摘要。"""
    args = run.args
    if run.step_result is None:
        display = "📍 PENDING"
    elif run.step_result == 1:
        display = "✅ PASS"
    elif run.step_result == 2:
        display = "⚠️ WARN"
    else:
        display = "❌ FAIL"
    hint = f" | 截图: {run.screenshot_name}" if run.screenshot_name else ""
    print(f"STEP [{args.step_type or 'misc'}] {display} | {args.desc} | {run.duration_ms}ms{hint}")
    if run.screenshot_name:
        print(f"STEP 截图: {run.screenshot_name}")
