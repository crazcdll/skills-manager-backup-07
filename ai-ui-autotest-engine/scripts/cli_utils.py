#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 共享工具 —— 上下文解析、时间线记录、统一错误边界。

主流程在 cli.py 中集中定义 parser + 查表分发，本模块提供通用编排逻辑。

【错误边界】

`run_with_guard` 是全进程唯一的「异常 → 进程退出码」转换点：

    业务/核心层 raise AutotestError  →  边界分类 → 打印 → 落审计 → 上报 → 退出码

因此除本模块（边界）外，任何模块都不得调用 `sys.exit`。
"""

import os
import sys

from shared.paths import get_active_run, get_active_task, require_active_task
from shared.workspace import render_text, render_cmd
from shared.case_utils import resolve_case_path
from execution.engine.flow.flow_context import read_meta_fields
from execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from shared import exit_codes
from shared.errors import (
    AutotestError, ContractError, DeviceError, UsageError, soft_fail, support_hint,
)


def resolve_active_context(args, need_serial=False):
    """从 active_run 解析 run 目录名设置到 args.dir。need_serial=True 时校验设备已创建。"""
    require_active_task()   # 无 workspace → 先报根因（请先 ws-init）
    case_name = get_active_run()
    if not case_name:
        raise UsageError(f"未设置 active_run，请先执行 {render_cmd('flow-init')}")

    args.dir = case_name
    run_dir = resolve_case_path(case_name)
    fc_path = os.path.join(run_dir, FLOW_CONTEXT_FILENAME)
    meta = read_meta_fields(fc_path)

    if need_serial and not meta.get("device_serial", ""):
        raise UsageError("device_serial 为空（设备未创建），请先完成 B1_device")


def auto_log_command(args):
    """自动记录设备交互命令执行到 run-events.jsonl 时间线。"""
    try:
        case_name = get_active_run()
        if not case_name:
            return
        run_dir = resolve_case_path(case_name)
        cmd = getattr(args, "cmd", "?")
        details = {"cmd": cmd}
        for key in ("sid", "action", "text", "url", "reason"):
            val = getattr(args, key, None)
            if val:
                details[key] = val
        from shared.observability.runtime_audit import append_event
        append_event(run_dir, "command.executed", details)
    except Exception as e:
        # 时间线记录失败可容忍，但必须留痕（不静默）
        soft_fail("infra", "COMMAND_LOG_FAILED", e)


def run_with_guard(args, dispatch_fn):
    """命令分发 + 统一异常边界（唯一的进程退出码决定点）。

    命令 handler 有两种表达失败的方式，都由本边界收口：

    1. **抛异常**（错误）— AutotestError 按其身份 code/category/exit_code 收口；
       其它未预期异常归类为 ContractError（script 缺陷），退出码 1。
    2. **返回退出码**（负面结果 / 判定）— handler 返回非 0 int 时，边界据此退出。
       适用于「正常执行的负面结论」：如 find-text 未命中、shell 透传设备命令返回码。
       handler 返回 None 或 0 表示成功。

    业务/核心层（非命令 handler）一律用第 1 种方式：只 raise，不返回码。
    """
    # 设备预检：仅在有 workspace 时执行。`ws-init` 等 workspace-free 命令不需要设备
    # 能力，跳过可避免无意义的工具链解析（历史上此处曾因读取 workspace 级缓存而在
    # 冷启动时崩溃；缓存已改为用户级，这里保留门禁以维持"无 workspace 不触设备"的语义）。
    if get_active_task():
        from devices.toolchain.adb import ensure_adb

        ensure_adb(install=False)

    try:
        code = dispatch_fn(args)
    except AutotestError as err:
        _emit_error(args, err, severity="error")
        raise SystemExit(err.exit_code)
    except Exception as exc:  # noqa: BLE001 — 未预期异常兜底，归因 script
        err = ContractError(f"{type(exc).__name__}: {exc}")
        _emit_error(args, err, severity="fatal", exc=exc)
        raise SystemExit(err.exit_code)

    if isinstance(code, int) and code != 0:
        raise SystemExit(code)


# ═══════════════════════════════════════════════════════════════════
# 独立动作命令的结果收口（tri-state → 退出码 / 异常）
# ═══════════════════════════════════════════════════════════════════
#
# 动作 handler（handle_tap_text / handle_input_text / handle_blur_input /
# handle_scroll_to_target）返回 tri-state：True=完成 / None=handoff / False=真失败。
# 独立命令过去各写各的收口，导致三套语义并存：
#   · 把 handoff 当设备错误抛（误导诊断）；
#   · 静默返回 None → 退出码 0 → 被当成成功（违反 dispatch 的既有警告）；
#   · 自定义 UsageError（类别也不对）。
# 本函数是这三类结果的**唯一收口**，与 run_with_guard 的退出语义对齐。

# handoff 的下一步建议：按 reason_code 给「怎么换策略」，而不是让调用方猜。
_HANDOFF_HINTS = {
    "TEXT_NOT_FOUND": "文案与页面不一致：用候选里的真实节点文案重试",
    "AMBIGUOUS": "匹配到多个候选：结合截图选定一个，改用坐标点击",
    "UNRESOLVED": "命中了但解析不出目标控件：从候选中选定真实目标（如输入框同行标签）后重试",
    "SUBSTRING_AMBIGUOUS": "子串匹配出多个候选：选定语义正确的元素后用其真实文案重跑",
    "TEXT_OUT_OF_VIEWPORT": "目标不在视口：先 scroll-until 滚动到位再重试",
    "TARGET_Y_OUT_OF_VIEWPORT": "目标 y 不在视口：先纵向滚动定位该行，再横向滚动",
    "SCROLL_TARGET_NOT_FOUND": "精确定位未命中：读元素目录找到真实文案后重跑",
    "VERTICAL_SCROLL_EXHAUSTED": "纵向滚动耗尽仍未进入视口：读截图判断是否已到边界",
    "HORIZONTAL_SCROLL_EXHAUSTED": "横向滚动耗尽：确认横向容器是否存在/已到边界",
    "BLOCKED": "目标被调试控件遮挡：先 dismiss-recce，或改用安全坐标",
    "ANCHOR_NOT_FOUND": "锚点未找到：从候选中选一个不可点击文本作为失焦锚点",
}


def _print_handoff(cmd_name, action_arg, reason, ctx):
    """打印 handoff 交接说明：原因 + 候选 + 元素目录 + 下一步建议。

    handler 已把 candidate_list / element_index_path 放进 ctx —— 直接展示，
    避免「只报未完成却不说怎么改」。
    """
    label = f" '{action_arg}'" if action_arg else ""
    print(f"{cmd_name} HANDOFF{label}: {reason or '需换策略后重试'}"
          f"（已交接给调用方决策，不是设备错误）")
    candidates = ctx.get("candidate_list")
    if candidates:
        print("  🔍 候选：")
        for line in str(candidates).splitlines():
            print(line)
    if ctx.get("element_index_path"):
        print(f"  📋 完整元素目录: {ctx['element_index_path']}")
    hint = _HANDOFF_HINTS.get(reason)
    if hint:
        print(f"  💡 {hint}")
    print(f"  ℹ️  退出码 {exit_codes.HANDOFF} = 未完成待决策（换策略后可重试）")


def finish_action_result(cmd_name, action_arg, result):
    """独立动作命令的统一结果收口（tri-state → 退出码 / 异常）。

      ok=True   → 完成：返回 None（调用方 return 后进程退出码 0）
      ok=None   → handoff：打印交接说明，返回 exit_codes.HANDOFF（≠ 错误）
      ok=False  → 真失败（设备/参数）：raise DeviceError，走统一错误出口

    Returns:
        int | None: 非零退出码（handoff）；完成返回 None。
    """
    result = result or {}
    ok = result.get("ok")
    if ok is True:
        return None
    ctx = result.get("ctx") or {}
    if ok is None:
        _print_handoff(cmd_name, action_arg, ctx.get("reason") or "", ctx)
        return exit_codes.HANDOFF
    raise DeviceError(result.get("reason") or f"{cmd_name} 执行失败")


# ═══════════════════════════════════════════════════════════════════
# 错误出口
# ═══════════════════════════════════════════════════════════════════

_REPORTED_CODES = set()  # 进程内按错误码去重，避免重复上报


def _emit_error(args, err, severity="error", exc=None):
    """统一错误出口：打印 → 落审计时间线 → 平台上报。"""
    cmd = getattr(args, "cmd", "?")
    if exc is not None and os.environ.get("CLI_DEBUG") == "1":
        import traceback
        sys.stderr.write(
            f"UNCAUGHT ERROR: {cmd} 命令异常: {render_text(err)}\n{traceback.format_exc()}\n"
        )
    else:
        sys.stderr.write(f"❌ {cmd} 执行失败: {render_text(err)}\n")
        _print_support_hint(err)
    _record_error(err, severity)


def _print_support_hint(err):
    """**仅当错误是终止语义（exit_code == ABORT）时**提示联系开发者。

    为什么不在所有报错上都提示：绝大多数报错是瞬时的，AI 会重试或换策略；每次提示
    会形成噪音。只有 ABORT（环境/前置不可用，"快速失败收尾"= 会话即将中断）才值得
    求助。

    而流程级中断（SOP 阶段失败 → 流程终止）不是错误而是状态，另由 `flow-fail` /
    `flow-next` 输出同一句提示（见 fail_cmd / status），文案同源于 support_hint()。
    """
    if getattr(err, "exit_code", None) != exit_codes.ABORT:
        return
    code = getattr(err, "code", "") or "UNEXPECTED"
    sys.stderr.write(f"   🆘 {support_hint(code)}\n")


def _record_error(err, severity):
    """错误落盘与上报（best-effort，绝不反向抛出）。"""
    # 1) 审计时间线：让失败在 run-events.jsonl 中可追溯
    try:
        from shared.observability.runtime_audit import append_event
        case_name = get_active_run()
        if case_name:
            append_event(resolve_case_path(case_name), "error.raised",
                         err.to_audit(), severity=severity)
    except Exception:
        pass

    # 2) 平台上报：引擎侧自动上报（AI 侧的 report-error 是另一入口）
    code = getattr(err, "code", "")
    if code in _REPORTED_CODES:
        return
    _REPORTED_CODES.add(code)
    try:
        from shared.observability.exception_reporter import report_exception
        report_exception(
            event="engine_error",
            message=getattr(err, "message", str(err)),
            category=getattr(err, "category", "unknown"),
            severity=severity,
            code=code,
            stage=getattr(err, "stage", ""),
            raw=getattr(err, "detail", "") or str(err),
            # 结构化错误身份（code/category/stage/detail/retryable）随上下文一并上报，
            # 与 raw 的单句摘要互补：raw 给「人看的一句话」，error_audit 给「机器可解析的字段」。
            extra={"error_audit": err.to_audit()},
        )
    except Exception:
        pass
