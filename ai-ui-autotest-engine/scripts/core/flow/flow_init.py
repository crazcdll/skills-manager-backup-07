#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-context.json 初始化层：从 steps-input.json 构建完整执行上下文。

职责：steps-input.json 结构/语义校验、Debug 浮窗抑制参数注入、构建 flow-context.json。
"""
import json
import os
import sys
import time

from urllib.parse import urlparse, parse_qs, urlunparse

from core.util.case_utils import resolve_case_path
from core.util.paths import SKILL_DIR, OUTPUT_DIR
from core.util.json_utils import read_json
from core.audit.runtime_audit import create_run_manifest
from core.flow.flow_context import save_context
from core.sop.on_fail import (
    DEFAULT_RULES,
    DEFAULT_SUCCESS_MARKERS,
)
from core.sop.stages import make_fresh_sop_stages
from core.flow.steps_builder import build_steps_json, validate_steps_json

# ═══════════════════════════════════════════════════════════════════
# Debug 浮窗抑制参数
# ═══════════════════════════════════════════════════════════════════

# 各容器类型的 debug 浮窗关闭参数，自动注入到 landing_scheme 中，避免遮挡截图
_DEBUG_VIEW_SUPPRESS_PARAMS = {
    # MRN 新架构
    "mrn_disable_debugview": "true",
    # MSC 容器
    "disableRedBox": "1",
    "disableDebugView": "true",
    # 金服容器
    "__recce_dev_show__": "false",
}

def _inject_debug_suppress_params(scheme: str) -> str:
    """向 scheme 跳链追加 debug 浮窗抑制参数（已存在的不覆盖）。"""
    if not scheme or "://" not in scheme:
        return scheme
    parsed = urlparse(scheme)
    existing = parse_qs(parsed.query, keep_blank_values=True)
    append_parts = []
    for key, val in _DEBUG_VIEW_SUPPRESS_PARAMS.items():
        if key not in existing:
            append_parts.append(f"{key}={val}")
    if not append_parts:
        return scheme
    sep = "&" if parsed.query else ""
    new_query = parsed.query + sep + "&".join(append_parts)
    return urlunparse(parsed._replace(query=new_query))




# ═══════════════════════════════════════════════════════════════════
# 初始化 flow-context.json
# ═══════════════════════════════════════════════════════════════════

def init_from_steps_json(run_dir, steps_json_path, flow_name="", device_serial=None,
                          env_info=None, user_mis=""):
    """读取 AI 生成的 steps-input.json（batch 格式），包装成完整 flow-context.json。
    每个 case 有自己的 steps/landing_scheme，env 为 batch 级共享。
    """
    run_dir = resolve_case_path(run_dir)

    try:
        with open(steps_json_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        ai_input = json.loads(raw_text)
    except json.JSONDecodeError as e:
        msg = f"steps-input.json JSON 语法错误: {e.msg} (行 {e.lineno} 列 {e.colno})"
        lines = raw_text.splitlines()
        if 1 <= e.lineno <= len(lines):
            err_line = lines[e.lineno - 1]
            start = max(0, e.colno - 1 - 60)
            end = min(len(err_line), e.colno - 1 + 60)
            snippet = err_line[start:end]
            pointer = " " * (e.colno - 1 - start) + "^"
            msg += f"\n  出错位置: ...{snippet}..."
            msg += f"\n            {pointer}"
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

    batch_name = ai_input.get("batch_name", flow_name or os.path.basename(steps_json_path))

    device_cfg = ai_input.get("device", {}) or {}
    device_type = device_cfg.get("type", "sandbox")
    device_platform = device_cfg.get("platform", "android")
    device_app = device_cfg.get("app", "meituan")
    device_auto_install = bool(device_cfg.get("auto_install", False))

    # ══════════════════════════════════════════════════════════
    #  结构 + 语义校验（复用 validate_steps_json，含设备组合硬校验，无副作用）
    # ══════════════════════════════════════════════════════════
    merged_env, _, cases = validate_steps_json(ai_input, env_info=env_info)

    # ══════════════════════════════════════════════════════════
    #  ③ 占位符完整性校验 + 统一替换：扫描 steps-input.json 全部字段中的 {xxx} 和 {T+N}，
    #    检查是否已在 env_answers.json 中解析（硬性门禁，不可跳过），
    #    全部解析后自动替换为实际值，无需外部 placeholder-substitute 步骤
    #    {T+N} 日期占位符由 resolve_placeholders 自动解析，无需用户输入
    # ══════════════════════════════════════════════════════════
    from core.placeholder.placeholder_resolver import extract_placeholders_from_steps, resolve_placeholders
    from core.util.case_utils import read_env_answers
    env_answers = read_env_answers()

    # 预填充：AI 审校时在 params 中填写的具体值（非 None、非 __date__）直接注入 env_answers
    for case in ai_input.get("cases", []):
        for name, value in (case.get("params", {}) or {}).items():
            if value is not None and value != "__date__":
                if name not in env_answers:
                    env_answers[name] = value

    case_placeholders = extract_placeholders_from_steps(ai_input)
    unresolved = []
    for case_id, placeholders in case_placeholders.items():
        for ph in placeholders:
            if ph not in env_answers:
                unresolved.append((case_id, ph))
    if unresolved:
        lines = [f"  Case {case_id}: {ph}" for case_id, ph in unresolved]
        msg = (
            f"Flow 原文包含未解析的占位符:\n" + "\n".join(lines) + "\n"
            f"请先通过 `placeholder-required --steps-input <path>` 收集用户输入，\n"
            f"再重新执行 flow-init。"
        )
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

    # 统一替换所有占位符：{T+N} → 自动日期，{xxx} → env_answers 值
    ai_input = resolve_placeholders(ai_input, env_answers)


    # 从替换后的完整数据中重新提取 cases（替换前提取的 cases 仍指向原始数据，
    # 里面的 landing_scheme 等字段未经日期替换，直接使用会导致日期占位符残留）
    cases = ai_input.get("cases", [])

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    batch_ts = time.strftime("%Y%m%dT%H%M%S")

    # batch 级统一 run_id 和 output_dir（一个 batch = 一条执行记录）
    batch_run_id = f"run-{batch_ts}"
    batch_output_dir = os.path.join(OUTPUT_DIR, batch_run_id)

    # 构建 cases_manifest 和 cases_summary
    cases_manifest = []
    cases_summary = []
    for i, case in enumerate(cases):
        case_id = case.get("case_id", f"case-{i+1:02d}")
        case_name = case.get("case_name", f"Case {i+1}")
        case_id_name = case_id
        case_tag = f"case_{i+1:02d}"
        case_workspace_dir = case_tag
        case_output_dir = os.path.join(batch_output_dir, case_tag)
        landing_scheme = case.get("landing_scheme", merged_env.get("landing_scheme", ""))
        landing_scheme = _inject_debug_suppress_params(landing_scheme)
        # 注：结构校验已由 validate_steps_json 完成，此处仅构建 manifest
        manifest_entry = {
            "index": i,
            "case_id": case_id,
            "case_name": case_name,
            "dir": case_id_name,
            "case_tag": case_tag,
            "workspace_dir": case_workspace_dir,
            "run_id": batch_run_id,
            "output_dir": case_output_dir,
            "landing_scheme": landing_scheme,
        }

        # flow_source 归一化为绝对路径，并读取原始内容供下游报告使用
        raw_source = case.get("flow_source", "")
        if raw_source:
            if os.path.isabs(raw_source):
                manifest_entry["flow_source"] = os.path.normpath(raw_source)
            else:
                manifest_entry["flow_source"] = os.path.normpath(os.path.join(SKILL_DIR, raw_source))
            # 在 flow-init 时就将原始 Flow 内容读入 manifest，
            # 避免 preflight-clean/post-clean 清空 .run-input/ 后报告无原始语义文件
            flow_path = manifest_entry["flow_source"]
            if os.path.isfile(flow_path):
                try:
                    with open(flow_path, "r", encoding="utf-8") as _f:
                        _content = _f.read()
                    if _content:
                        manifest_entry["flow_content"] = _content
                except OSError:
                    pass
        else:
            manifest_entry["flow_source"] = ""

        cases_manifest.append(manifest_entry)
        cases_summary.append({
            "case_id": case_id,
            "case_name": case_name,
            "dir": case_id_name,
            "status": "pending",
        })

    # 构建 SOP stages（展开所有 case 的循环体）
    sop_stages = make_fresh_sop_stages(cases_manifest, device_type=device_type)
    if sop_stages:
        sop_stages[0]["status"] = "in_progress"
        sop_stages[0]["started_at"] = now

    # 加载第一个 case 的 steps 到 ctx
    first_case = cases[0]
    first_manifest = cases_manifest[0]
    steps_json = build_steps_json(first_case.get("steps", []))

    ctx = {
        "meta": {
            "skill": "ai-ui-autotest-engine",
            "batch_name": batch_name,
            "batch_ts": batch_ts,
            "batch_run_id": batch_run_id,
            "batch_output_dir": batch_output_dir,
            "flow_name": batch_name,
            "started_at": now,
            "run_start_ts": time.time(),
            "last_updated": now,
            "device_serial": device_serial or "",
            "platform": device_platform,
            "device_type": device_type,
            "app": device_app,
            "device_auto_install": device_auto_install,
            "run_dir": run_dir,
            "steps_json_path": os.path.abspath(steps_json_path),
            "user_mis": user_mis or "",
            "device_info": "",
        },
        "env": merged_env,
        "cases_manifest": cases_manifest,
        "cases_summary": cases_summary,
        "current_case": {
            "index": 0,
            "case_id": first_manifest["case_id"],
            "case_name": first_manifest["case_name"],
            "dir": first_manifest["dir"],
            "workspace_dir": first_manifest["workspace_dir"],
            "run_id": first_manifest["run_id"],
            "output_dir": first_manifest["output_dir"],
            "landing_scheme": first_manifest["landing_scheme"],
        },
        "runtime": {
            "acks": {},
        },
        "sop": {
            "current_stage": sop_stages[0]["id"] if sop_stages else "",
            "stages": sop_stages,
        },
        "current_step_index": 0,
        "steps": steps_json,
        "rules": dict(DEFAULT_RULES),
        "success_markers": dict(DEFAULT_SUCCESS_MARKERS),
        "errors": [],
    }

    save_context(run_dir, ctx)
    create_run_manifest(run_dir, ctx, steps_json_path)
    return ctx
