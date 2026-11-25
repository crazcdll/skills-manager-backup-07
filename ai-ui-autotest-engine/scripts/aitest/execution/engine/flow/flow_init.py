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

from aitest.shared.case_utils import resolve_case_path
from aitest.shared.paths import (
    ENV_TRANSPORT_PORT,
    allocate_run_output_dir,
    report_batch_id,
)
from aitest.shared.json_utils import read_json, write_json_atomic
from aitest.shared.placeholders import (
    collect_case_placeholder_text,
    date_base,
    find_unresolved_placeholders,
    resolve_date_offset,
    validate_var_spec,
)
from aitest.shared.observability.runtime_audit import create_run_manifest
from aitest.execution.engine.flow.flow_context import save_context
from aitest.execution.engine.sop.on_fail import (
    DEFAULT_RULES,
    DEFAULT_SUCCESS_MARKERS,
)
from aitest.execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from aitest.execution.engine.sop.stages import make_fresh_sop_stages
from aitest.execution.engine.flow.steps_builder import build_steps_json, validate_steps_json


def _resolve_case_mock_ids(case):
    """解析单个 case 的场景 mockId 集合（仅取显式 `case.mock_ids`）。

    steps.json 的 `env.mock_ids` 已由上游写入 case，这里不做任何
    文件解析兜底 —— 缺失即空集（该 case 不启用场景 Mock）。
    """
    explicit = case.get("mock_ids")
    if not isinstance(explicit, list):
        return []
    out = []
    for x in explicit:
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
    return out


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
                          env_info=None, user_mis="", run_type=""):
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

    # 批次名优先级：显式 `--flow-name` > steps-input 的 batch_name > 文件名。
    # 多 Case 批次由 `flow-add-case` 组装时，batch_name 恒为首个 steps.json 的 title，
    # 若不显式覆盖，平台报告行标题会变成「流程01-1 …」而不是整批的名字。
    batch_name = (
        (flow_name or "").strip()
        or str(ai_input.get("batch_name") or "").strip()
        or os.path.basename(steps_json_path)
    )

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
    #  ③ 变量落地 + 占位符完整性校验 + 统一替换：
    #    vars.value → 直接作为答案；vars.date → 按批次基线算成字面日期；
    #    vars.ask → 必须先由 input-next 收集。全部落成 answers 后一次性替换。
    # ══════════════════════════════════════════════════════════
    from aitest.execution.engine.placeholder.placeholder_resolver import extract_placeholders_from_steps, resolve_placeholders
    from aitest.shared.intake import read_intake
    answers = read_intake()

    # 预填充：value 直接注入；date 算成字面值；ask 交给提问流程。
    # 确定性声明（value/date）以 steps-input 为准（覆盖 intake 里的陈旧同名值），
    # ask 变量才以 intake 用户回答为准。
    base = date_base()
    spec_errors = []
    seen_vars = {}
    for case in ai_input.get("cases", []):
        case_id = case.get("case_id")
        for name, spec in (case.get("vars", {}) or {}).items():
            spec_errors.extend(
                validate_var_spec(name, spec, where=f"{case_id}: vars.{name}")
            )
            if not isinstance(spec, dict):
                continue
            if spec.get("ask") is True:
                kind, value = "ask", None
            elif "value" in spec:
                kind, value = "value", spec["value"]
            else:
                kind, value = "date", resolve_date_offset(
                    spec["date"], spec.get("format"), now=base
                )
            prev = seen_vars.get(name)
            if prev is not None and prev != (kind, value):
                spec_errors.append(
                    f"vars.{name} 在多个 Case 中声明不一致：{prev} vs {(kind, value)}"
                    "（同名变量必须同义）"
                )
            seen_vars[name] = (kind, value)
            if kind != "ask":
                answers[name] = value
    if spec_errors:
        msg = "steps-input vars 声明非法:\n" + "\n".join(f"  - {e}" for e in spec_errors)
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

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

    # 统一替换所有占位符：{xxx} → 变量值（vars.value / vars.date / intake.ask）
    ai_input = resolve_placeholders(ai_input, answers)

    # 解析后硬门禁：执行字段里不允许再残留任何 {xxx}。
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
            "所有变量请先在 env.vars 声明：固定值用 value，执行前填写用 ask，"
            "相对日期用 date（offset 天 + format），并通过 `input-next` → `input-answer` 收集。"
        )
        sys.stderr.write(f"[flow_init] {msg}\n")
        raise ValueError(msg)

    # 落地页唯一事实源：`env.scheme`（或 case.landing_scheme）注入 debug 抑制参数后，
    # 同步写回首步 open-url。否则 manifest 的 landing_scheme 与步骤实际跳转是两套 URL
    # （一个带 mrn_disable_debugview，一个不带），会漂移成「报告里有落地页、实际参数不同」。
    for case in resolved_cases:
        steps = case.get("steps") or []
        first = steps[0] if steps else None
        if not (isinstance(first, dict) and first.get("action") == "open-url"):
            continue
        raw_scheme = case.get("landing_scheme") or merged_env.get("landing_scheme", "") \
            or first.get("action_arg") or ""
        landing = _inject_debug_suppress_params(raw_scheme)
        if landing:
            first["action_arg"] = landing
            case.setdefault("landing_scheme", landing)

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

    # 同一 run 目录重复 flow-init（典型场景：flow-add-case 追加 Case 后重建上下文）
    # 必须**沿用**既有批次身份：否则会另起 batch_id → 分配新报告目录 → 平台多出一条
    # 空报告行，且已 Open 的台账/已 Append 的 Case 全部对不上。
    prev_ctx = read_json(os.path.join(run_dir, FLOW_CONTEXT_FILENAME), default=None)
    prev_meta = (prev_ctx or {}).get("meta") or {}
    prev_output_dir = str(prev_meta.get("batch_output_dir") or "").strip()
    reused_meta = prev_meta if (prev_output_dir and os.path.isdir(prev_output_dir)) else {}

    batch_ts = reused_meta.get("batch_ts") or time.strftime("%Y%m%dT%H%M%S")
    started_at = reused_meta.get("started_at") or now

    # 报告目录：reports/<batch>/<run>[-rN]。
    # 同一编排的所有 shard 共享 batch_id（便于控制台聚合），但各自独立 run 目录
    # （并发不串台；重试落 -r2 保留上一轮证据）。
    run_key = os.path.basename(os.path.normpath(run_dir))
    if reused_meta:
        batch_id = str(reused_meta.get("batch_id") or report_batch_id())
        batch_output_dir = prev_output_dir
        batch_run_id = str(reused_meta.get("batch_run_id") or "") or (
            f"{batch_id}--{os.path.basename(batch_output_dir)}"
        )
    else:
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

        # 场景 Mock：case 级声明（steps.json 的 `env.mock_ids`）。
        # 本层不读任何外部文档：配置全部来自 steps.json，避免第二份事实。
        manifest_entry["mock_ids"] = _resolve_case_mock_ids(case)

        cases_manifest.append(manifest_entry)
        cases_summary.append({
            "case_id": case_id,
            "case_name": case_name,
            "dir": case_id_name,
            "status": "pending",
        })

    # 场景 Mock：所有 case 的 union（B0_mock_preflight 的条件与物化集合）
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
            # 运行类型：由编排层/CLI 通过环境变量透传，报告行按此维度筛选
            "run_type": str(run_type or reused_meta.get("run_type")
                            or os.environ.get("AI_UITEST_RUN_TYPE", "").strip() or "adhoc"),
            "started_at": started_at,
            "date_base": reused_meta.get("date_base")
            or os.environ.get("AI_UITEST_DATE_BASE", "").strip() or now[:10],
            "transport_port": int(os.environ[ENV_TRANSPORT_PORT])
            if os.environ.get(ENV_TRANSPORT_PORT, "").strip().isdigit()
            else int(reused_meta.get("transport_port") or 0),
            "run_start_ts": reused_meta.get("run_start_ts") or time.time(),
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

    # 重跑 flow-init 时保留设备/会话运行态：device setup 已写入的 session_id 若被清空，
    # 后续设备命令会因为「未绑定会话」直接失败。
    if reused_meta:
        for _key in ("session_id", "device_serial", "device_info"):
            if reused_meta.get(_key) and not ctx["meta"].get(_key):
                ctx["meta"][_key] = reused_meta[_key]

    save_context(run_dir, ctx)
    create_run_manifest(run_dir, ctx)
    return ctx
