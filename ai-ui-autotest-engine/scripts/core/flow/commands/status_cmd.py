#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-status / flow-case-status CLI 命令。

职责：解析 CLI 参数 → 查询执行状态 → 格式化输出。
"""
from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path
from core.flow.flow_context import load_context
from core.flow.state import get_recovery_info


def _cmd_flow_status(args):
    """flow-status [--sid SID]: 获取执行状态；带 --sid 时输出单步骤精简详情。"""
    run_dir = resolve_case_path(getattr(args, "dir", None))

    sid = getattr(args, "sid", None)
    if sid:
        _print_step_status(run_dir, sid)
        return

    info = get_recovery_info(run_dir)
    if not info.get("has_context"):
        print("FLOW-STATUS: 无 flow-context.json，需先执行 flow-init")
        return

    steps_progress = f"{info.get('completed_count', 0)}/{info.get('total_steps', 0)}"
    print(f"FLOW-STATUS: {info.get('flow_name', '')}")
    print(f"  Steps: {steps_progress} (completed/total)")
    print(f"  Stage: {info.get('sop_stage', '')} ({info.get('sop_stage_desc', '')})")
    print(f"  Next action: {info.get('next_action', '')}")
    print(f"  Run dir: {run_dir}")
    if info.get("pending_hooks"):
        print(f"  Pending hooks: {len(info['pending_hooks'])}")
        for h in info["pending_hooks"][:5]:
            print(f"    - {h}")
        if len(info["pending_hooks"]) > 5:
            print(f"    ... and {len(info['pending_hooks']) - 5} more")


def _print_step_status(run_dir, sid):
    """单步骤精简详情：状态/断言/pending hooks，供 AI 替代 grep 大文件查询。"""
    ctx = load_context(run_dir)
    if ctx is None:
        print("FLOW-STATUS ERROR: flow-context.json 不存在，需先执行 flow-init")
        return
    step = next((s for s in ctx.get("steps", []) if s.get("sid") == sid), None)
    if step is None:
        print(f"FLOW-STATUS ERROR: 未找到步骤 {sid}")
        return
    hooks = step.get("hooks", [])
    pending = [h["id"] for h in hooks if h.get("required") and not h.get("completed")]
    print(f"STEP {sid} | {step.get('status', 'pending')} | ok={step.get('ok')} | {step.get('desc', '')}")
    if step.get("fail_reason"):
        print(f"  fail_reason: {step['fail_reason']}")
    assertions = step.get("assertions") or {}
    for category, items in assertions.items():
        for it in items:
            print(
                f"  assert[{category}] {it.get('id', '')} {it.get('expect', '')}"
                f" → {it.get('result', '?')} ({it.get('verdict') or '-'})"
            )
    if pending:
        print(f"  pending hooks: {', '.join(pending)}")
        print(f"  详情: python3 scripts/cli.py hook-info --hook-id {pending[0]} --sid {sid}")
    else:
        print("  pending hooks: 无")


def _cmd_flow_case_status(args):
    """flow-case-status: 显示 batch 执行进度。"""
    run_dir = resolve_case_path(args.dir)
    ctx = load_context(run_dir)
    if ctx is None:
        raise FlowStateError("flow-context.json 不存在")

    cases_summary = ctx.get("cases_summary", [])
    current_case = ctx.get("current_case", {})
    current_index = current_case.get("index", 0)

    print(f"CASE-STATUS: Case {current_index + 1}/{len(cases_summary)}")
    for i, cs in enumerate(cases_summary):
        marker = "→" if i == current_index else " "
        status = cs.get("status", "pending")
        label = {"in_progress": "进行中", "completed": "✅ 完成",
                 "failed": "❌ 失败", "blocked": "⛔ 阻塞",
                 "pending": "待开始", "skipped": "⏭ 跳过"}.get(status, status)
        print(f"  {marker} Case {i}: {cs.get('case_name', f'Case {i+1}')} [{label}]")