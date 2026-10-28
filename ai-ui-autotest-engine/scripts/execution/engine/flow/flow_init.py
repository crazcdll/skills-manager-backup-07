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

from shared.case_utils import resolve_case_path, resolve_flow_content
from shared.paths import (
    ENV_TRANSPORT_PORT,
    allocate_run_output_dir,
    report_batch_id,
)
from shared.json_utils import read_json, write_json_atomic
from shared.placeholders import (
    DATE_PLACEHOLDER_RE,
    collect_case_placeholder_text,
    find_unresolved_placeholders,
)
from shared.observability.runtime_audit import create_run_manifest
from execution.engine.flow.flow_context import save_context
from execution.engine.sop.on_fail import (
    DEFAULT_RULES,
    DEFAULT_SUCCESS_MARKERS,
)
from execution.engine.sop.stages import make_fresh_sop_stages
from execution.engine.flow.steps_builder import build_steps_json, validate_steps_json
from provisioning.validators.config_validator import extract_flow_appmock_ids


def _resolve_case_mock_ids(case, flow_path):
    """解析单个 case 的场景 mockId 集合（case 级）。

    优先级：显式 `case.mock_ids`（AI/用户提供）> Flow md 的「可测性环境」AppMock 行。
    两者都没有 → 空集（该 case 不启用任何场景 Mock）。
    """
    explicit = case.get("mock_ids")
    if isinstance(explicit, list):
        out = []
        for x in explicit:
            s = str(x).strip()
            if s and s not in out:
                out.append(s)
        return out
    if flow_path:
        return extract_flow_appmock_ids(flow_path)
    return []


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
    #    检查是否已在 intake 中解析（硬性门禁，不可跳过），
    #    全部解析后自动替换为实际值，无需外部 placeholder-substitute 步骤
    #    {T+N} 日期占位符由 resolve_placeholders 自动解析，无需用户输入
    # ══════════════════════════════════════════════════════════
    from execution.engine.placeholder.placeholder_resolver import extract_placeholders_from_steps, resolve_placeholders
    from shared.intake import read_intake
    answers = read_intake()

    # 预填充：AI 审校时在 params 中填写的具体值直接注入 intake。
    # 日期不允许走 params（否则 answer 插入的 {T+N} 会绕过 scheme 的日期解析），
    # 生成期已由 steps-generate 拒绝，这里再做一次执行期硬门禁。
    for case in ai_input.get("cases", []):
        for name, value in (case.get("params", {}) or {}).items():
            if value is None:
                continue
            if not isinstance(value, str):
                if name not in answers:
                    answers[name] = value
                continue
            if value == "__date__":
                raise ValueError(
                    f"Case {case.get('case_id')}: params.{name}=__date__ 已废弃；"
                    f"请把日期直接写成 landing_scheme/steps 中的 "
                    f"{{T+10:%Y-%m-%d}}"
                )
            if DATE_PLACEHOLDER_RE.search(value):
                raise ValueError(
                    f"Case {case.get('case_id')}: params.{name} 不能承载日期表达式；"
                    "请把日期直接写成 landing_scheme/steps 中的 {T+10:%Y-%m-%d}"
                )
            if name not in answers:
                answers[name] = value

    case_placeholders = extract_placeholders_from_steps(ai_input)
    unresolved = []
    for case_id, placeholders in case_placeholders.items():
        for ph in placeholders:
            if ph not in answers:
                unresolved.append((case_id, ph))
    if unresolved:
        lines = [f"  Case {case_id}: {ph}" for case_id, ph in unresolved]
        msg = (
            f"Flow 原文包含未解析的占位符:\n" + "\n".join(lines) + "\n"
            f"请先通过 `input-next` → `input-answer` 收集占位符值，\n"
            f"再重新执行 flow-init。"
        )
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

    # 统一替换所有占位符：{T±N} → 自动日期，{xxx} → intake 值
    ai_input = resolve_placeholders(ai_input, answers)

    # 解析后硬门禁：执行字段里不允许再残留任何 {T+N} / {xxx}。
    # 这一步确保“App 收到 {}”永远不会成为产品失败，而是在初始化阶段直接报配置错误。
    resolved_cases = ai_input.get("cases", [])
    residual = []
    for case in resolved_cases:
        for ph in find_unresolved_placeholders(collect_case_placeholder_text(case)):
            residual.append((case.get("case_id"), ph))
    if residual:
        lines = [f"  Case {case_id}: {ph}" for case_id, ph in residual]
        msg = (
            "解析后仍存在未替换的占位符:\n" + "\n".join(lines) + "\n"
            "日期请直接写成 {T+10:%Y-%m-%d}（不要经 params/answer 间接插入）；"
            "其他占位符请先通过 `input-next` → `input-answer` 收集。"
        )
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

    # ══════════════════════════════════════════════════════════
    #  ④ 固化「解析后的 steps-input」为唯一事实来源（方案 A）
    #    落盘的 steps_json_path 从此只含已解析值；原始（含占位符）版本
    #    另存为 steps-input.raw.json 以备溯源。
    #    这样运行期所有读者（case-init / 报告等）只需纯读，禁止再各自解析
    #    —— 否则 C0 case-init 重载原始文件会覆盖本处解析结果（历史回归根因），
    #    由 dev/check_architecture.py 规则6 强制。
    # ══════════════════════════════════════════════════════════
    if steps_json_path and os.path.isfile(steps_json_path):
        raw_snapshot = os.path.join(os.path.dirname(steps_json_path), "steps-input.raw.json")
        if not os.path.isfile(raw_snapshot):
            with open(raw_snapshot, "w", encoding="utf-8") as _f:
                _f.write(raw_text)
        write_json_atomic(steps_json_path, ai_input)

    # 使用替换后的完整数据（替换前提取的 cases 仍指向原始数据，
    # 里面的 landing_scheme 等字段未经日期替换，直接使用会导致日期占位符残留）
    cases = resolved_cases

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    batch_ts = time.strftime("%Y%m%dT%H%M%S")

    # 报告目录：reports/<batch>/<run>[-rN]。
    # 同一编排的所有 shard 共享 batch_id（便于控制台聚合），但各自独立 run 目录
    # （并发不串台；重试落 -r2 保留上一轮证据）。
    run_key = os.path.basename(os.path.normpath(run_dir))
    batch_id = report_batch_id()
    batch_output_dir = allocate_run_output_dir(batch_id, run_key)
    batch_run_id = f"{batch_id}--{os.path.basename(batch_output_dir)}"

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

        # 原始 Flow 原文：flow-init 时一次性读取并内嵌（flow_source 缺失时按
        # case_id/case_name 在 $STATE/run/tasks/<task>/inputs/flows/ 兜底匹配）。避免 preflight/post-clean
        # 清空本 workspace 的 inputs/ 后报告无原始语义文件。flow_source_name 供 case-init 落日志
        # 与报告 desc 使用。
        flow_path, flow_content, flow_name = resolve_flow_content(
            case.get("flow_source", ""),
            name_hints=[case_id, case_name],
        )
        manifest_entry["flow_source"] = flow_path
        manifest_entry["flow_source_name"] = flow_name or f"{case_name}.md"
        manifest_entry["mock_ids"] = _resolve_case_mock_ids(case, flow_path)
        if flow_content:
            manifest_entry["flow_content"] = flow_content

        cases_manifest.append(manifest_entry)
        cases_summary.append({
            "case_id": case_id,
            "case_name": case_name,
            "dir": case_id_name,
            "status": "pending",
        })

    # 场景 Mock：所有 case 的 union（B0_mock_preflight 的条件与快照集合）
    mock_union = []
    for _m in cases_manifest:
        for _mid in (_m.get("mock_ids") or []):
            if _mid not in mock_union:
                mock_union.append(_mid)

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
            "batch_id": batch_id,
            "run_name": run_key,
            "batch_run_id": batch_run_id,
            "batch_output_dir": batch_output_dir,
            "flow_name": batch_name,
            "started_at": now,
            "date_base": os.environ.get("AI_UITEST_DATE_BASE", "").strip() or now[:10],
            "transport_port": int(os.environ[ENV_TRANSPORT_PORT])
            if os.environ.get(ENV_TRANSPORT_PORT, "").strip().isdigit() else 0,
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
            "mock_union": mock_union,
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
    create_run_manifest(run_dir, ctx)
    return ctx
