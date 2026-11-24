#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-init / flow-add-case / case-init CLI 命令。

职责：解析 CLI 参数 → 调用初始化层 → 格式化输出。
"""
import json
import os

from aitest.shared.errors import FlowStateError, PayloadError, UsageError
from aitest.shared.paths import SKILL_DIR, resolve_input_path
from aitest.shared.case_utils import append_source_notes, resolve_case_path, resolve_mis
from aitest.shared.paths import set_active_run, get_active_run
from aitest.shared.json_utils import write_json_atomic, read_json
from aitest.shared.observability.usage_reporter import report_usage
from aitest.shared.observability.runtime_audit import append_event
from aitest.execution.engine.flow.flow_context import load_context, save_context
from aitest.execution.engine.flow.flow_init import init_from_steps_json, validate_steps_json
from aitest.execution.engine.flow.steps_builder import build_steps_json as _build_steps_json
from aitest.execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from aitest.execution.engine.flow.commands.validate_cmd import _format_json_error


def _input_missing_hint(requested, resolved, error):
    """--input 文件不存在时给出可用文件，避免链错文件名后无法自救。"""
    hint = (
        f"读取文件失败: {error}\n"
        f"  --input: {requested}\n"
        "  提示：--input 应传 `steps-generate --tag <case_id>` 产出的文件名"
        "（steps-input-<case_id>.json）；裸文件名会在当前 workspace 的 tmp/ 下解析。"
    )
    try:
        files = sorted(
            name
            for name in os.listdir(os.path.dirname(resolved))
            if name.startswith("steps-input") and name.endswith(".json")
        )
    except OSError:
        files = []
    if files:
        hint += "\n  当前 workspace 可用输入：" + "、".join(files)
    return hint


def _cmd_flow_init(args):
    """flow-init --input <steps-input.json> --dir <case> --flow-name <name> [--mis <mis>]"""
    mis = getattr(args, "mis", "") or resolve_mis()
    flow_name = getattr(args, "flow_name", "") or ""
    report_usage("flow-init", mis=mis, desc=f"flow_name={flow_name}")

    if not getattr(args, "json", None):
        raise UsageError("需要 --input 参数")

    raw = resolve_input_path(args.json)
    try:
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise PayloadError(_input_missing_hint(args.json, raw, e)) from e

    try:
        ai_input = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PayloadError(_format_json_error(e, raw)) from e

    try:
        validate_steps_json(ai_input)
    except ValueError as e:
        raise PayloadError(str(e)) from e

    run_dir = resolve_case_path(args.dir)
    os.makedirs(run_dir, exist_ok=True)

    steps_json_path = os.path.join(run_dir, "steps-input.json")
    with open(steps_json_path, "w", encoding="utf-8") as f:
        f.write(raw)

    try:
        ctx = init_from_steps_json(
            run_dir, steps_json_path,
            flow_name=getattr(args, "flow_name", "") or "",
            device_serial=None,
            env_info=None,
            user_mis=mis,
            run_type=getattr(args, "run_type", "") or "",
        )
    except ValueError as e:
        raise PayloadError(str(e)) from e

    set_active_run(args.dir)
    cases_manifest = ctx.get("cases_manifest", [])
    print(f"FLOW-INIT OK: {len(cases_manifest)} cases, {len(ctx['steps'])} steps in case 0")
    print(f"  Batch: {ctx['meta']['flow_name']}")
    print(f"  Run dir: {run_dir}")
    print(f"  JSON: {os.path.join(run_dir, FLOW_CONTEXT_FILENAME)}")
    print(f"  SOP stages: {len(ctx['sop']['stages'])}")
    for cm in cases_manifest:
        print(f"  Case {cm['index']}: {cm['case_name']} — {cm['run_id']}")


def _cmd_flow_add_case(args):
    """flow-add-case [--dir <run>] --input <case.json> [--case-index N]

    向已存在的 steps-input.json 中追加一个 case。
    `--dir` 可省略：缺省取本 workspace 当前活跃 run（`flow-init --dir` 写入的值）。
    追加完成后需重新执行 flow-init 以更新 flow-context。
    """
    if not getattr(args, "json", None):
        raise UsageError("需要 --input 参数")

    raw = resolve_input_path(args.json)
    try:
        with open(raw, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise PayloadError(_input_missing_hint(args.json, raw, e)) from e
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PayloadError(f"JSON 语法错误: {e}") from e

    # 兼容两种入参：① 单 case 对象；② steps-generate 产出的 steps-input（含 cases[]）。
    # 后者让调用方（编排层 / 子 Agent）不必再手工从 steps-input 里抽出 cases[0]。
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        cases = payload["cases"]
        if not cases:
            raise PayloadError("--input 是 steps-input，但 cases 为空")
        idx = getattr(args, "case_index", 0) or 0
        if idx < 0 or idx >= len(cases):
            raise PayloadError(f"--case-index {idx} 越界（steps-input 共 {len(cases)} 个 case）")
        new_case = cases[idx]
        if not isinstance(new_case, dict):
            raise PayloadError(f"--case-index {idx} 不是合法 case 对象")
    else:
        new_case = payload

    case_id = new_case.get("case_id", "")
    if not case_id:
        raise PayloadError("新 case 必须提供 case_id")
    landing_scheme = new_case.get("landing_scheme", "")
    if not landing_scheme:
        raise PayloadError(f"Case {case_id} 缺少 landing_scheme")
    steps = new_case.get("steps", [])
    try:
        _build_steps_json(steps)
    except ValueError as e:
        raise PayloadError(f"Case {case_id} steps 校验失败: {e}") from e

    run_name = (getattr(args, "dir", "") or "").strip() or get_active_run()
    if not run_name:
        raise UsageError(
            "需要 --dir（当前 workspace 没有活跃 run）：先执行 flow-init --dir <run> 创建/切换 run"
        )
    run_dir = resolve_case_path(run_name)
    steps_json_path = os.path.join(run_dir, "steps-input.json")

    if not os.path.isfile(steps_json_path):
        raise PayloadError(
            f"steps-input.json 不存在 ({steps_json_path})；请先执行 flow-init 创建初始 batch"
        )

    ai_input = read_json(steps_json_path, default={})
    existing_cases = ai_input.get("cases", [])
    new_index = len(existing_cases)
    ai_input["cases"].append(new_case)

    write_json_atomic(steps_json_path, ai_input)

    print(f"FLOW-ADD-CASE OK: {case_id} (index={new_index})")
    print(f"  Case: {new_case.get('case_name', f'Case {new_index}')}")
    print(f"  Steps: {len(steps)}")
    print(f"  Total cases in steps-input.json: {len(ai_input['cases'])}")
    print(f"  下一步: 重新执行 flow-init --dir {run_name} --input {steps_json_path} 以更新 flow-context")


def _cmd_case_init(args):
    """case-init --case-index <index>

    切换到指定 case：加载该 case 的 steps/landing_scheme 到 flow-context.json。
    case 目录从 active_run 自动获取。
    """
    run_dir = resolve_case_path(args.dir)
    ctx = load_context(run_dir)
    if ctx is None:
        raise FlowStateError("flow-context.json 不存在，需先执行 flow-init")

    ci = args.case_index
    cases_manifest = ctx.get("cases_manifest", [])
    if ci < 0 or ci >= len(cases_manifest):
        raise UsageError(f"case-index {ci} 超出范围（共 {len(cases_manifest)} 个 case）")

    manifest = cases_manifest[ci]

    steps_json_path = ctx["meta"]["steps_json_path"]
    # 方案 A：steps_json_path 在 flow-init 时已固化为「解析后」的唯一事实来源
    # （原文另存 steps-input.raw.json），此处及后续所有读者一律纯读，
    # 不得再做占位符解析（由 dev/check_architecture.py 规则6 强制）。
    ai_input = read_json(steps_json_path, default={})
    cases = ai_input.get("cases", [])
    case_data = cases[ci]

    steps_json = _build_steps_json(case_data.get("steps", []))

    ctx["current_case"] = {
        "index": ci,
        "case_id": manifest["case_id"],
        "case_name": manifest["case_name"],
        "dir": manifest["dir"],
        "workspace_dir": manifest["workspace_dir"],
        "run_id": manifest["run_id"],
        "output_dir": manifest["output_dir"],
        "landing_scheme": manifest["landing_scheme"],
    }

    ctx["steps"] = steps_json
    ctx["current_step_index"] = 0

    workspace_dir = os.path.join(run_dir, manifest["workspace_dir"])
    os.makedirs(workspace_dir, exist_ok=True)

    # ── 输入原文随日志落盘 ──────────────────────────────────────
    # 平台需要展示「输入的原始 JSON」：优先取 flow-init 留存的原始快照
    # （`steps-input.raw.json`，占位符未替换），保证展示的就是上游真实产物；
    # 快照缺失时回落到解析后的 steps-input.json。报告只读日志，不再按路径重查，
    # 也不读取任何渲染产物。
    source_path = steps_json_path
    raw_snapshot = os.path.join(os.path.dirname(steps_json_path), "steps-input.raw.json")
    if os.path.isfile(raw_snapshot):
        source_path = raw_snapshot
    source_entries = []
    try:
        with open(source_path, "r", encoding="utf-8") as _f:
            steps_text = _f.read()
    except OSError:
        steps_text = ""
    if steps_text:
        source_entries.append({
            "source": "steps_input",
            "desc": "steps-input.json（原始输入）",
            "note": steps_text,
        })
    embedded_sources = append_source_notes(workspace_dir, source_entries)
    if embedded_sources:
        print(f"  📄 输入原文已随日志落盘: {', '.join(embedded_sources)}")

    for cs in ctx.get("cases_summary", []):
        if cs["case_id"] == manifest["case_id"]:
            cs["status"] = "in_progress"

    save_context(run_dir, ctx)
    append_event(run_dir, "case.initialized", {"index": ci, "case_id": manifest["case_id"]})

    print(f"CASE-INIT OK: Case {ci} — {manifest['case_name']}")
    print(f"  Case ID: {manifest['case_id']}")
    print(f"  Steps: {len(steps_json)}")
    print(f"  Run ID: {manifest['run_id']}")
    print(f"  Landing: {manifest['landing_scheme'][:80]}")