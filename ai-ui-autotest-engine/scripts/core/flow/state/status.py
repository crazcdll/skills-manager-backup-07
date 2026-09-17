#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态查询：恢复信息、下一步动作、case 跳过与推进。

依赖关系：
  status → flow_context → core.sop.on_fail
  status → step_scheduler
"""
import time

from core.flow.flow_context import (
    load_context, save_context,
    _find_stage, _evaluate_condition,
)
from core.flow.step_scheduler import (
    _has_incomplete_required_hooks,
    _find_next_pending_step_index,
    _build_step_command,
)
from core.sop.hook_templates import HOOK_TEMPLATES
from core.sop.on_fail import _get_on_fail_policy


def _advance_to_next_case(ctx, now, verdict, error_msg):
    """结束当前 case 并推进到下一个 case。

    verdict 写入 cases_summary：failed/blocked。
    跳过当前 case 的 C3 走查步骤，保留 C4_report 及之后的收尾阶段。
    """
    current_case = ctx.get("current_case", {})
    current_ci = current_case.get("index", 0)

    for cs in ctx.get("cases_summary", []):
        if cs.get("case_id") == current_case.get("case_id"):
            cs["status"] = verdict
            cs["error"] = error_msg
            break

    case_suffix = f"_{current_ci}"
    stages = ctx.get("sop", {}).get("stages", [])
    report_idx = next((i for i, s in enumerate(stages)
                       if s.get("id") == f"C4_report{case_suffix}"), None)
    if report_idx is not None:
        for s in stages[:report_idx]:
            if s.get("id", "").endswith(case_suffix) and s.get("status") in ("pending", "in_progress"):
                s["status"] = "skipped"

    next_stage = None
    for s in stages:
        if s.get("status") in ("completed", "skipped", "failed"):
            continue
        next_stage = s
        break

    if next_stage:
        next_stage["status"] = "in_progress"
        next_stage["started_at"] = now
        ctx["sop"]["current_stage"] = next_stage["id"]
    else:
        ctx["sop"]["current_stage"] = "done"

    if next_stage and next_stage["id"].endswith(case_suffix):
        return

    next_ci = current_ci + 1
    for manifest in ctx.get("cases_manifest", []):
        if manifest.get("index") == next_ci:
            ctx["current_case"] = {
                "index": next_ci,
                "case_id": manifest.get("case_id", ""),
                "case_name": manifest.get("case_name", ""),
                "dir": manifest.get("dir", ""),
                "workspace_dir": manifest.get("workspace_dir", ""),
                "run_id": manifest.get("run_id", ""),
                "output_dir": manifest.get("output_dir", ""),
                "landing_scheme": manifest.get("landing_scheme", ""),
            }
            break


def skip_current_case(run_dir, reason):
    """AI 主动结束当前 case（前置不成立、页面异常等无意义场景）。"""
    ctx = load_context(run_dir)
    if ctx is None:
        return {"ok": False, "reason": "flow-context.json 不存在"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    current_case = ctx.get("current_case", {})

    for step in ctx.get("steps", []):
        if step.get("status") == "pending":
            step["status"] = "skipped"

    ctx.setdefault("errors", []).append({
        "stage": ctx.get("sop", {}).get("current_stage", ""),
        "error": reason,
        "ts": now,
    })

    _advance_to_next_case(ctx, now, verdict="blocked", error_msg=reason)
    ctx["meta"]["last_updated"] = now
    save_context(run_dir, ctx)

    return {
        "ok": True,
        "case_id": current_case.get("case_id", ""),
        "case_name": current_case.get("case_name", ""),
        "reason": reason,
        "next_stage": ctx["sop"]["current_stage"],
    }


def get_recovery_info(run_dir):
    """获取当前执行状态。返回 dict 含 SOP 阶段、步骤进度、未完成 hooks。"""
    ctx = load_context(run_dir)
    if ctx is None:
        return {"has_context": False}

    steps = ctx.get("steps", [])
    idx = ctx.get("current_step_index", 0)
    total = len(steps)
    completed = sum(1 for s in steps if s["status"] == "completed")
    failed = sum(
        1 for s in steps
        if s["status"] == "failed"
        and any(h.get("required") and not h.get("completed") for h in s.get("hooks", []))
    )
    failed_resolved = sum(
        1 for s in steps
        if s["status"] == "failed"
        and not any(h.get("required") and not h.get("completed") for h in s.get("hooks", []))
    )

    current = None
    pending_hooks = []
    next_action = "流程已全部完成"

    sop_stage = ctx.get("sop", {}).get("current_stage", "")
    current_stage_def = _find_stage(ctx, sop_stage)

    if sop_stage == "aborted":
        errors = ctx.get("errors", [])
        error_summary = "; ".join(e.get("error", "") for e in errors[-3:]) if errors else ""
        next_action = f"流程已终止（环境准备失败）：{error_summary}"
    elif sop_stage.startswith("C3_walkthrough_"):
        if idx < total:
            current = steps[idx]
            if current["status"] == "pending":
                next_action = f"执行步骤 {current['sid']}: {current['desc']}"
            elif current["status"] == "failed":
                incomplete = [h for h in current.get("hooks", [])
                              if h.get("required") and not h.get("completed")]
                if incomplete:
                    pending_hooks = incomplete
                    next_action = (f"步骤 {current['sid']} 失败，"
                                   f"需先完成 {len(incomplete)} 个未完成操作: "
                                   + ", ".join(h["id"] for h in incomplete))
                else:
                    next_action = f"步骤 {current['sid']} 失败但 hooks 已完成，继续下一步"
            elif current["status"] == "completed":
                next_action = f"步骤 {current['sid']} 已完成，继续下一步"
        else:
            next_action = "所有步骤已完成，推进到下一阶段"
    elif sop_stage == "done":
        next_action = "全流程已完成"
    else:
        if current_stage_def:
            next_action = f"执行阶段 {sop_stage}: {current_stage_def.get('desc', '')}"

    cases_manifest = ctx.get("cases_manifest", [])
    current_case = ctx.get("current_case", {})

    return {
        "has_context": True,
        "batch_total_cases": len(cases_manifest),
        "batch_current_case_index": current_case.get("index", 0),
        "batch_current_case_name": current_case.get("case_name", ""),
        "flow_name": ctx.get("meta", {}).get("flow_name", ""),
        "device_serial": ctx.get("meta", {}).get("device_serial", ""),
        "started_at": ctx.get("meta", {}).get("started_at", ""),
        "sop_stage": sop_stage,
        "sop_stage_desc": current_stage_def.get("desc", "") if current_stage_def else "",
        "current_step": current,
        "current_step_index": idx,
        "completed_count": completed,
        "failed_count": failed,
        "failed_resolved_count": failed_resolved,
        "total_steps": total,
        "pending_hooks": pending_hooks,
        "next_action": next_action,
        "cases_summary": ctx.get("cases_summary", []),
    }


def get_next_action(run_dir):
    """计算 AI 下一步该执行什么，返回结构化指引。

    这是 flow-next 命令的核心逻辑：
    1. 如果在 SOP 阶段（非 C3_walkthrough）→ 返回该阶段的命令模板
    2. 如果在 Step 3 走查 → 返回当前步骤的完整 step 命令
    3. 全流程完成 → 返回完成信息
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return {"action": "error", "message": "flow-context.json 不存在，需先执行 flow-init"}

    sop_stage_id = ctx.get("sop", {}).get("current_stage", "")

    if sop_stage_id == "done":
        return {"action": "done", "message": "全流程已完成"}

    if sop_stage_id == "aborted":
        errors = ctx.get("errors", [])
        error_summary = "; ".join(e.get("error", "") for e in errors[-3:]) if errors else ""
        return {"action": "aborted", "message": f"流程已终止（环境准备失败）：{error_summary}", "errors": errors}

    if sop_stage_id.startswith("C3_walkthrough_"):
        idx = ctx.get("current_step_index", 0)
        steps = ctx.get("steps", [])
        current_case = ctx.get("current_case", {})

        pending_idx = _find_next_pending_step_index(ctx)
        if pending_idx >= len(steps):
            return {
                "action": "sop_advance",
                "message": f"Case {current_case.get('index', 0)} 所有走查步骤已完成，推进到下一阶段",
                "stage_id": sop_stage_id,
            }
        idx = pending_idx
        step = steps[idx]

        if idx != ctx.get("current_step_index", 0):
            ctx["current_step_index"] = idx
            save_context(run_dir, ctx)

        if _has_incomplete_required_hooks(step) and step.get("status") in ("completed", "failed", "in_progress", "pending"):
            incomplete = [h for h in step.get("hooks", [])
                          if h.get("required") and not h.get("completed")]
            status_label = {
                "completed": "已执行", "failed": "失败",
                "in_progress": "待确认", "pending": "待确认",
            }.get(step["status"], "未知状态")
            first_hook = incomplete[0]
            remaining_count = len(incomplete) - 1
            msg = f"步骤 {step['sid']} {status_label}，需完成 hook: {first_hook['id']}"
            if remaining_count > 0:
                msg += f"（后续还有 {remaining_count} 个 hook）"
            return {
                "action": "complete_hooks",
                "message": msg,
                "hooks": [first_hook],
                "step_sid": step["sid"],
            }

        cmd = _build_step_command(step, ctx)

        if cmd is None:
            action = step.get("action")
            anchor = step.get("action_anchor", "")
            find_cmd = "find-input" if action == "input-text" else "find-icon"
            return {
                "action": "locate_first",
                "sid": step["sid"],
                "desc": step["desc"],
                "message": f"步骤 {step['sid']} 的 {action} 需先定位坐标，锚点：{anchor}",
                "locate_command": f'python3 scripts/cli.py {find_cmd} "{anchor}"',
                "next_command_template": f"python3 scripts/cli.py step --sid {step['sid']} {action} --action-x <x> --action-y <y>",
                "case_index": current_case.get("index", 0),
                "case_name": current_case.get("case_name", ""),
            }

        return {
            "action": "execute_step",
            "sid": step["sid"],
            "desc": step["desc"],
            "command": cmd,
            "asserts": step.get("asserts", []),
            "pre_hooks": [h for h in HOOK_TEMPLATES.get("pre_step", []) if h.get("auto")],
            "case_index": current_case.get("index", 0),
            "case_name": current_case.get("case_name", ""),
        }

    stage = _find_stage(ctx, sop_stage_id)
    if not stage:
        return {"action": "error", "message": f"未找到阶段 {sop_stage_id}"}

    cond = stage.get("condition", "")
    should_exec, reason = _evaluate_condition(ctx, cond)
    if cond and not should_exec:
        return {
            "action": "sop_skip",
            "stage_id": stage["id"],
            "stage_desc": stage.get("desc", ""),
            "message": f"阶段 {stage['id']} 条件不满足（{reason}），直接 flow-advance 跳过",
        }

    result = {
        "action": "execute_sop_stage",
        "stage_id": stage["id"],
        "stage_desc": stage.get("desc", ""),
        "on_fail": _get_on_fail_policy(stage),
        "needs_visual_check": stage.get("needs_visual_check", False),
        "visual_check_hint": stage.get("visual_check_hint", ""),
        "notes": stage.get("notes", ""),
        "terminal": stage.get("terminal", False),
    }

    from core.flow.lifecycle.advance import _render_template

    if stage.get("build_cmd") == "env_prepare":
        result["commands"] = ["python3 scripts/cli.py env-prepare"]
    else:
        commands = []
        if stage.get("cmd"):
            commands.append(_render_template(stage["cmd"], ctx))
        if stage.get("cmds"):
            commands.extend(_render_template(c, ctx) for c in stage["cmds"])
        if stage.get("cmd_template"):
            if stage.get("iterable") == "mock_ids":
                mock_ids = ctx.get("env", {}).get("mock_ids", [])
                for mid in mock_ids:
                    tmpl = stage["cmd_template"]
                    cmd = tmpl.replace("{mock_id}", str(mid))
                    cmd = _render_template(cmd, ctx)
                    commands.append(cmd)
            else:
                commands.append(_render_template(stage["cmd_template"], ctx))
        result["commands"] = commands

    marker_table = ctx.get("success_markers", {})
    mk = stage.get("success_marker")
    mks = stage.get("success_markers", [])
    if mk:
        result["success_markers"] = [marker_table.get(mk, mk)]
    else:
        result["success_markers"] = [marker_table.get(m, m) for m in mks]

    if stage.get("requires_ack"):
        result["requires_ack"] = stage["requires_ack"]

    return result