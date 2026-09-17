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

from core.util.paths import get_active_case
from core.util.case_utils import resolve_case_path
from core.flow.flow_context import read_meta_fields
from core.sop.constants import FLOW_CONTEXT_FILENAME
from core.errors import AutotestError, ContractError, UsageError, soft_fail


def resolve_active_context(args, need_serial=False):
    """从 active_case 解析 case 目录名设置到 args.dir。need_serial=True 时校验设备已创建。"""
    case_name = get_active_case()
    if not case_name:
        raise UsageError("未设置 active_case，请先执行 flow-init")

    args.dir = case_name
    run_dir = resolve_case_path(case_name)
    fc_path = os.path.join(run_dir, FLOW_CONTEXT_FILENAME)
    meta = read_meta_fields(fc_path)

    if need_serial and not meta.get("device_serial", ""):
        raise UsageError("device_serial 为空（设备未创建），请先完成 B1_device")


def auto_log_command(args):
    """自动记录设备交互命令执行到 run-events.jsonl 时间线。"""
    try:
        case_name = get_active_case()
        if not case_name:
            return
        run_dir = resolve_case_path(case_name)
        cmd = getattr(args, "cmd", "?")
        details = {"cmd": cmd}
        for key in ("sid", "action", "text", "url", "reason"):
            val = getattr(args, key, None)
            if val:
                details[key] = val
        from core.audit.runtime_audit import append_event
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
    from infra.adb import ensure_adb

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
# 错误出口
# ═══════════════════════════════════════════════════════════════════

_REPORTED_CODES = set()  # 进程内按错误码去重，避免重复上报


def _emit_error(args, err, severity="error", exc=None):
    """统一错误出口：打印 → 落审计时间线 → 平台上报。"""
    cmd = getattr(args, "cmd", "?")
    if exc is not None and os.environ.get("CLI_DEBUG") == "1":
        import traceback
        sys.stderr.write(
            f"UNCAUGHT ERROR: {cmd} 命令异常: {err}\n{traceback.format_exc()}\n"
        )
    else:
        sys.stderr.write(f"❌ {cmd} 执行失败: {err}\n")
    _record_error(err, severity)


def _record_error(err, severity):
    """错误落盘与上报（best-effort，绝不反向抛出）。"""
    # 1) 审计时间线：让失败在 run-events.jsonl 中可追溯
    try:
        from core.audit.runtime_audit import append_event
        case_name = get_active_case()
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
        from core.audit.exception_reporter import report_exception
        report_exception(
            event="engine_error",
            message=getattr(err, "message", str(err)),
            category=getattr(err, "category", "unknown"),
            severity=severity,
            code=code,
            stage=getattr(err, "stage", ""),
            raw=getattr(err, "detail", "") or str(err),
        )
    except Exception:
        pass
