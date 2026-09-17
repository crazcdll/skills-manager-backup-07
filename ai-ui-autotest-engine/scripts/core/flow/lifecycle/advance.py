#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段推进：模板渲染、当前阶段查询、推进、终结。

依赖关系：
  advance → flow_context → core.sop.constants
  advance → environment.validators.env_validator（环境类型映射唯一事实来源）
  advance → step_scheduler
"""
import time

from core.flow.flow_context import (
    load_context, save_context,
    _find_stage, _evaluate_condition, _run_completion_check,
)
from environment.validators.env_validator import ENV_TYPE_MAP


def _render_template(template, ctx):
    """将命令模板中的 {variable} 替换为 flow-context.json 中的实际值。

    契约：本函数只处理「从 flow-context 取值」的占位符。
    iterable 类占位符（如 B3_mock_enable 的 {mock_id}）由调用方
    （status.get_next_action 的 mock_ids 展开）在调用本函数**之前**逐项替换，
    因此不在此声明；未声明的占位符会原样保留（fail-loud），而不是静默渲染为空串。
    """
    meta = ctx.get("meta", {})
    env = ctx.get("env", {})

    mock_ids = env.get("mock_ids", [])
    mock_ids_str = ",".join(str(m) for m in mock_ids) if mock_ids else ""

    current_case = ctx.get("current_case", {})

    replacements = {
        "{env_type}": ENV_TYPE_MAP.get(env.get("type", ""), env.get("type", "")),
        "{account}": env.get("account", ""),
        # 类型字符串的凭证在 flow-init → validate_auth_config 后存于 `_password_raw`
        # （`password` 键已被 pop），故此处读 `_password_raw`；缺失（如 qahome）时渲染为空。
        "{password}": env.get("_password_raw", ""),
        "{flow_name}": meta.get("flow_name", ""),
        "{landing_scheme}": current_case.get("landing_scheme", env.get("landing_scheme", "")),
        "{mock_ids_str}": mock_ids_str,
        "{device}": meta.get("device_info", ""),
        "{steps_json_path}": meta.get("steps_json_path", ""),
        "{run_id}": current_case.get("run_id", ""),
        "{output_dir}": current_case.get("output_dir", ""),
    }
    result = template
    for k, v in replacements.items():
        result = result.replace(k, str(v) if v is not None else "")
    return result


def get_current_stage(run_dir):
    """返回当前 SOP 阶段定义。"""
    ctx = load_context(run_dir)
    if ctx is None:
        return None
    current_id = ctx.get("sop", {}).get("current_stage", "")
    return _find_stage(ctx, current_id)


def advance_stage(run_dir, force=False, _ctx=None):
    """当前阶段标记 completed，推进到下一个 pending 阶段。

    跳过 condition 不满足的阶段；completion_check 校验失败时拒绝推进。
    """
    ctx = _ctx if _ctx is not None else load_context(run_dir)
    if ctx is None:
        return None

    stages = ctx.get("sop", {}).get("stages", [])
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    skipped_this_call = []

    current_id = ctx.get("sop", {}).get("current_stage", "")
    current = _find_stage(ctx, current_id)
    if current:
        cond = current.get("condition", "")
        should_exec, cond_reason = _evaluate_condition(ctx, cond)
        if cond and not should_exec:
            current["status"] = "skipped"
            current["skip_reason"] = cond_reason
            skipped_this_call.append(current)
        else:
            if not force:
                ok, reason = _run_completion_check(ctx, current)
                if not ok:
                    return {"error": "evidence_missing", "stage_id": current_id, "reason": reason}
            current["status"] = "completed"
        current["completed_at"] = now

    for stage in stages:
        if stage.get("status") in ("completed", "skipped"):
            continue
        cond = stage.get("condition", "")
        should_exec, cond_reason = _evaluate_condition(ctx, cond)
        if cond and not should_exec:
            stage["status"] = "skipped"
            stage["skip_reason"] = cond_reason
            skipped_this_call.append(stage)
            continue
        stage["status"] = "in_progress"
        stage["started_at"] = now
        ctx["sop"]["current_stage"] = stage["id"]
        save_context(run_dir, ctx)
        stage["_advance_skipped"] = skipped_this_call
        return stage

    ctx["sop"]["current_stage"] = "done"
    save_context(run_dir, ctx)
    return None


def finalize_flow(run_dir):
    """标记终结阶段完成，设置 current_stage=done。

    abort 路径：current_stage 已为 "aborted" 时不覆盖为 "done"，
    报告由 fail_stage 在调用 flow-finalize 之前已生成。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return {"ok": False, "reason": "flow-context.json 不存在"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    current_id = ctx.get("sop", {}).get("current_stage", "")

    if current_id == "aborted":
        ctx.setdefault("meta", {})["last_updated"] = now
        save_context(run_dir, ctx)
        return {"ok": True, "stage_id": "aborted", "finalized_at": now, "skipped": True}

    current = _find_stage(ctx, current_id)
    if current:
        current["status"] = "completed"
        current["completed_at"] = now

    ctx["sop"]["current_stage"] = "done"

    for cs in ctx.get("cases_summary", []):
        if cs.get("status") == "in_progress":
            cs["status"] = "completed"

    ctx.setdefault("meta", {})["last_updated"] = now
    save_context(run_dir, ctx)

    return {"ok": True, "stage_id": current_id, "finalized_at": now}