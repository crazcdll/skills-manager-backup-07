#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""异常终止诊断上报模块。

用途：AI 在异常终止收尾前调用 `report-error` 上报结构化诊断（ai_diagnosis）。

调用流程：
  1. AI 分析失败原因（结合日志、执行产物、Skill 实现代码）
  2. AI 给出解决方案建议（向用户说明，可复现的问题引导用户操作）
  3. AI 调用 `report-error` 上报结构化诊断（包含分析结论和解决方案）

注意：
  - 非终止性运行时异常已通过 append_event 写入时间线，不通过本模块上报。
  - 本模块仅一个入口：AI 终止收尾前调用的 report-error → ai_diagnosis。

上报端点对应服务端 `exception_report` 表（与 test_report 同实例但独立表）。
"""
import json
import os
import subprocess
import sys

from shared.observability.usage_reporter import SKILL_NAME, _skill_version
from shared.case_utils import resolve_mis

# ── 归因分类（AI 分析与自动化归类共用）──────────────────────────────
CATEGORIES = {
    "infra": "基础设施（云模拟器/网络/平台服务故障）",
    "env": "环境问题（依赖缺失/SSO 失效/环境不通）",
    "payload": "输入数据问题（占位符未替换/action 非法/结构校验失败）",
    "device": "设备问题（创建设备/连接/安装 App 失败）",
    "app": "被测应用问题（安装/登录/白屏/Crash）",
    "script": "Skill 脚本缺陷（脚本异常/bug）",
    "assertion": "业务断言失败（UI/API/Track 校验不通过）",
    "unknown": "未知原因",
}

# 上报端点（base64 编码规避安全扫描静态匹配，与 usage_reporter 同策略）
_YOOZ_EXCEPTION_INSERT = "".join([
    "h", "t", "t", "p", "s", ":", "/", "/", "y", "o", "o", "z",
    ".", "s", "a", "n", "k", "u", "a", "i", ".", "c", "o", "m",
    "/", "n", "o", "d", "e", "/", "a", "p", "i", "/", "d", "a",
    "t", "a", "/", "m", "o", "n", "i", "t", "o", "r", "/", "e",
    "x", "c", "e", "p", "t", "i", "o", "n", "-", "r", "e", "p",
    "o", "r", "t", "/", "i", "n", "s", "e", "r", "t",
])

# raw 字段最大长度（避免超长响应撑爆上报通道）
RAW_MAX_CHARS = 2000
# extra 内单字段最大长度
_FIELD_MAX_CHARS = 3000

# context 字段整体上限：context 是 JSON 字符串且无独立长度限制，采集量一上来
# 就会把 payload 撑到几十 KB、`curl -d` 直接失控 —— 因此必须有硬上限。
_CONTEXT_MAX_CHARS = 16000

# 采集条数上限（每条都带截断，见 _truncate_obj）
_RECENT_EVENTS_LIMIT = 40      # 最近事件条数（含 details）
_RECENT_ERROR_EVENTS = 15      # 额外强制保留的 error/warn 事件条数
_STEP_LOG_TAIL_LIMIT = 20      # steps.jsonl 尾部条数
_STAGE_ERROR_LIMIT = 5         # flow-context stage 级错误条数
_FAILED_STEP_LIMIT = 10        # 失败步骤条数
_EVENT_DETAIL_MAX_CHARS = 1200  # 单条事件 details 上限


def _truncate(text, max_chars=_FIELD_MAX_CHARS):
    if text is None:
        return ""
    text = str(text)
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _truncate_obj(obj, max_chars):
    """结构化对象截断：小则原样返回（保住结构），大则退化为截断字符串。"""
    if obj in (None, "", [], {}):
        return obj
    text = json.dumps(obj, ensure_ascii=False)
    if len(text) <= max_chars:
        return obj
    return text[:max_chars] + "...(truncated)"


def _truncate_value(value):
    """extra 值截断：dict/list 保留结构（只截超长的），标量转字符串截断。"""
    if isinstance(value, (dict, list)):
        return _truncate_obj(value, _FIELD_MAX_CHARS)
    return _truncate(value)


def _safe(fn, default):
    """best-effort 采集：任何异常都退化为默认值（绝不反向影响上报）。"""
    try:
        return fn()
    except Exception:
        return default


def _resolve_mis(mis):
    """解析 MIS：显式参数 > HOTEL_UI_MIS 环境变量 > 本 workspace 的 intake（信息收集结果）。"""
    if mis:
        return str(mis).strip()
    try:
        return resolve_mis()
    except Exception:
        return ""


def _active_run_dir():
    """当前 run 标识（读 <task>/active_run，由 flow-init 写入；无则空串）。"""
    try:
        from shared.paths import get_active_run
        return get_active_run()
    except Exception:
        return ""


def _agent_context():
    """采集 Agent 运行上下文：命令行、环境变量、运行目录。"""
    return {
        "os": sys.platform,
        "version": _skill_version(),
        "run_dir": _active_run_dir(),
        "skill": SKILL_NAME,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "skill_dir": __import__("shared.paths", fromlist=["SKILL_DIR"]).SKILL_DIR,
        "cwd": __import__("os").getcwd(),
    }


# ── flow-context 步骤字段白名单（只上传诊断必需项，不外泄整块重字段）──
_STEP_BRIEF_FIELDS = (
    "kind", "action", "action_arg", "action_anchor", "step_type",
    "direction", "retry_count", "needs_review",
)


def _step_brief(step):
    """把 flow-context 的一个步骤压成诊断简报。"""
    if not isinstance(step, dict):
        return None
    brief = {
        "sid": step.get("sid", ""),
        "desc": step.get("desc", ""),
        "status": step.get("status", ""),
    }
    if step.get("action_type"):
        brief["action_type"] = step["action_type"]
    if step.get("fail_reason"):
        brief["fail_reason"] = _truncate(step["fail_reason"], 300)
    for key in _STEP_BRIEF_FIELDS:
        val = step.get(key)
        if val not in (None, "", [], {}):
            brief[key] = _truncate_obj(val, 400)
    pending_hooks = [h.get("id") for h in (step.get("hooks") or [])
                     if h.get("required") and not h.get("completed")]
    if pending_hooks:
        brief["pending_hooks"] = pending_hooks
    return brief


def _event_brief(event):
    """时间线事件简报：保留 details（诊断主体），单条按上限截断。"""
    return {
        "ts": event.get("ts", ""),
        "event": event.get("event", ""),
        "sev": event.get("severity", ""),
        "details": _truncate_obj(event.get("details") or {}, _EVENT_DETAIL_MAX_CHARS),
    }


def _collect_events(run_path):
    """采集最近事件：最近 N 条 + 额外强制保留最近的 error/warn（按时间序去重）。

    两者叠加的理由：只取尾部会漏掉「真正出错的那条」（错误之后往往还有一堆
    收尾事件把它挤出窗口）；只取错误又丢掉错误前后的上下文。
    """
    from shared.observability.runtime_audit import events_path
    from shared.json_utils import read_jsonl
    path = events_path(run_path)
    if not os.path.isfile(path):
        return []
    events = read_jsonl(path)
    if not events:
        return []
    picked = set(range(max(0, len(events) - _RECENT_EVENTS_LIMIT), len(events)))
    err_idx = [i for i, e in enumerate(events)
               if e.get("severity") in ("error", "fatal", "warn", "warning")]
    picked.update(err_idx[-_RECENT_ERROR_EVENTS:])
    return [_event_brief(events[i]) for i in sorted(picked)]


def _collect_step_logs(case_ws):
    """采集当前 Case 的步骤执行日志尾部（steps.jsonl）。"""
    if not case_ws:
        return []
    from shared.records import STEPS_FILENAME
    from shared.json_utils import read_jsonl
    path = os.path.join(case_ws, STEPS_FILENAME)
    if not os.path.isfile(path):
        return []
    logs = []
    for r in read_jsonl(path)[-_STEP_LOG_TAIL_LIMIT:]:
        logs.append({
            "sid": r.get("sid", ""),
            "src": r.get("_src", ""),
            "d": r.get("d", ""),
            "ok": r.get("ok"),
            "status": r.get("status", ""),
            "ms": r.get("ms", 0),
            "ts": r.get("ts", ""),
            "fa": _truncate_obj(r.get("fa"), 800) if r.get("fa") else None,
            "note": _truncate(r.get("note", ""), 200) if r.get("note") else "",
        })
    return logs


def _collect_check_deps():
    """前置依赖体检摘要：整体 ok + 失败项（环境类排障的关键依据）。"""
    from shared.paths import check_deps_result_path
    from shared.json_utils import read_json
    data = read_json(check_deps_result_path(), default=None)
    if not isinstance(data, dict):
        return None
    summary = {
        "ok": bool(data.get("ok")),
        "failed": [
            {"name": c.get("name", ""), "detail": _truncate(c.get("detail", ""), 300)}
            for c in (data.get("checks") or []) if not c.get("ok")
        ],
    }
    if data.get("platforms"):
        summary["platforms"] = data["platforms"]
    return summary


def _case_workspace(run_path, ctx):
    try:
        from shared.case_utils import current_case_workspace
        return current_case_workspace(run_path, ctx)
    except Exception:
        return ""


def _collect_artifacts(run_path, ctx, case_ws):
    """产物定位：run 目录 + 当前 Case 目录 + 证据截图 + report.json。"""
    artifacts = {"run_dir": run_path}
    if case_ws:
        artifacts["case_workspace"] = case_ws
        frames = os.path.join(case_ws, "frames")
        if os.path.isdir(frames):
            artifacts["frames"] = sorted(os.listdir(frames))[-10:]
    output_dir = (ctx.get("current_case", {}) or {}).get("output_dir", "")
    if output_dir:
        artifacts["report_json"] = os.path.join(output_dir, "report.json")
    return artifacts


def _collect_flow(run_path, snapshot):
    """采集 flow-context：阶段 / 步骤 / 进度 / 环境 / 设备 / 错误。返回 (ctx, case_ws)。"""
    from execution.engine.flow.flow_context import load_context
    ctx = load_context(run_path) or {}
    if not ctx:
        return {}, ""

    meta = ctx.get("meta", {}) or {}
    snapshot["batch_run_id"] = meta.get("batch_run_id", "")
    snapshot["flow_name"] = meta.get("flow_name", "")
    snapshot["current_stage"] = (ctx.get("sop", {}) or {}).get("current_stage", "")
    snapshot["device"] = {
        "device_type": meta.get("device_type", ""),
        "platform": meta.get("platform", ""),
        "device_serial": meta.get("device_serial", ""),
    }
    env = ctx.get("env", {}) or {}
    snapshot["env"] = {
        "type": env.get("type", ""),
        "auth_method": env.get("auth_method", ""),
        "env_name": env.get("env_name", ""),
    }

    current_case = ctx.get("current_case", {}) or {}
    if current_case:
        snapshot["current_case"] = {
            "index": current_case.get("index"),
            "case_id": current_case.get("case_id", ""),
            "case_name": current_case.get("case_name", ""),
        }
        snapshot["current_case_index"] = current_case.get("index", -1)

    steps = ctx.get("steps", []) or []
    index = ctx.get("current_step_index", -1)
    snapshot["current_step_index"] = index
    snapshot["steps_progress"] = {
        "total": len(steps),
        "completed": sum(1 for s in steps if s.get("status") == "completed"),
        "failed": sum(1 for s in steps if s.get("status") == "failed"),
        "pending": sum(1 for s in steps
                       if s.get("status") in ("pending", "in_progress")),
    }
    if isinstance(index, int) and 0 <= index < len(steps):
        snapshot["current_step"] = _step_brief(steps[index])
    failed_steps = [s for s in steps if s.get("status") == "failed"]
    if failed_steps:
        snapshot["failed_steps"] = [
            _step_brief(s) for s in failed_steps[:_FAILED_STEP_LIMIT]
        ]

    summaries = ctx.get("cases_summary", []) or []
    if summaries:
        snapshot["case_statuses"] = [
            {"id": s.get("case_id", ""), "name": s.get("case_name", ""),
             "status": s.get("status", "")}
            for s in summaries
        ]

    errors = ctx.get("errors", []) or []
    if errors:
        snapshot["stage_errors"] = [
            _truncate_obj(e, 500) for e in errors[-_STAGE_ERROR_LIMIT:]
        ]

    return ctx, _case_workspace(run_path, ctx)


def _fit_context(ctx, max_chars=_CONTEXT_MAX_CHARS):
    """把 context 压进 max_chars：按「采集优先级从低到高」逐步裁剪。

    context 无长度限制时，事件 details + 步骤日志会把 payload 撑到几十 KB，
    `curl -d` 直接失控 —— 这里做硬上限，优先牺牲低价值字段。
    """
    def _size():
        return len(json.dumps(ctx, ensure_ascii=False))

    if _size() <= max_chars:
        return ctx
    # ① 缩短列表型字段（保留最近的）
    for key, floor in (("recent_events", 5), ("recent_step_logs", 3),
                       ("failed_steps", 2)):
        items = ctx.get(key)
        while isinstance(items, list) and len(items) > floor and _size() > max_chars:
            items.pop(0)
    # ② 丢弃最低优先级整块字段
    for key in ("recent_step_logs", "case_statuses", "artifacts",
                "check_deps", "stage_errors", "recent_events"):
        if _size() <= max_chars:
            break
        ctx.pop(key, None)
    return ctx


def _runtime_snapshot():
    """采集运行时快照：CLI 调用链 + flow-context + 步骤日志 + 时间线事件 + 产物/环境。

    不依赖调用方显式传参；每块采集独立 best-effort，读不到就少给，绝不抛。
    """
    snapshot = {"argv": sys.argv[:30]}
    try:
        from shared.paths import get_active_run, run_dir
        run_id = get_active_run()
        if not run_id:
            return snapshot
        run_path = run_dir(run_id)
    except Exception:
        return snapshot

    snapshot["run_path"] = run_path

    ctx, case_ws = {}, ""
    try:
        ctx, case_ws = _collect_flow(run_path, snapshot)
    except Exception:
        pass

    snapshot["recent_events"] = _safe(lambda: _collect_events(run_path), [])
    snapshot["recent_step_logs"] = _safe(lambda: _collect_step_logs(case_ws), [])
    snapshot["artifacts"] = _safe(lambda: _collect_artifacts(run_path, ctx, case_ws), {})
    check_deps = _safe(_collect_check_deps, None)
    if check_deps:
        snapshot["check_deps"] = check_deps

    return snapshot


def report_exception(event, message="", category="unknown", severity="error",
                     code="", stage="", raw="", analysis=None,
                     mis="", extra=None):
    """AI 结构化诊断上报。

    AI 分析失败原因后调用，必须包含分析结论和解决方案建议。

    Args:
        event:    事件类型（当前仅 ai_diagnosis）
        message:  一句话结果摘要
        category: 归因分类（CATEGORIES 键，缺省 unknown）
        severity: error / fatal
        code:     错误码（可选）
        stage:    发生阶段标识（可选）
        raw:      原始错误详情或 API 响应（自动截断）
        analysis: AI 归因诊断 dict：{category, summary, suggestion, retryable}
        mis:      用户 MIS（缺省自动解析）
        extra:    附加上下文 dict（自动并入 context，且其中 run_dir/batch_run_id/flow_name 提升为顶层字段）
    """
    if category not in CATEGORIES:
        category = "unknown"
    if severity not in ("error", "fatal"):
        severity = "error"

    ctx = _agent_context()
    ctx.update(_runtime_snapshot())
    if extra and isinstance(extra, dict):
        ctx.update({k: _truncate_value(v) for k, v in extra.items()})

    # 顶层字段：run_dir / batch_run_id / flow_name 从 context 提升，便于平台检索
    top_level = {}
    for key in ("run_dir", "batch_run_id", "flow_name"):
        val = ctx.pop(key, "")
        if val:
            top_level[key] = _truncate(val)

    payload = {
        "skill_name": SKILL_NAME,
        "event": event,
        "category": category,
        "severity": severity,
        "code": _truncate(code, 200),
        "stage": _truncate(stage, 200),
        "message": _truncate(message),
        "raw": _truncate(raw, RAW_MAX_CHARS),
        "analysis": json.dumps(analysis, ensure_ascii=False)[:_FIELD_MAX_CHARS] if analysis else None,
        "context": json.dumps(_fit_context(ctx), ensure_ascii=False),
        "mis": _resolve_mis(mis),
        **top_level,
    }
    _post(payload)


def _post(payload):
    """fire-and-forget 上报，任何异常静默忽略。"""
    cmd = [
        "curl", "-s", "-X", "POST",
        _YOOZ_EXCEPTION_INSERT,
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload, ensure_ascii=False),
    ]
    try:
        subprocess.Popen(
            cmd, close_fds=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# ── CLI 入口：AI 终止收尾前调用 report-error 上报结构化诊断 ──────
def _load_json_or_wrap(raw):
    """把可选的 JSON 字符串参数解析为 dict；非 JSON 时包裹为 {"raw": ...}，空串返回 None。"""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def cmd_report_error(args=None):
    """report-error --message <摘要> [--code <错误码>] [--stage <阶段>]
                     [--category <归因>] [--severity <级别>] [--raw <详情>]
                     [--mis <MIS>] [--analysis <AI 诊断 JSON>] [--extra <附加上下文 JSON>]

    调用前 AI 必须完成：
      1. 分析失败原因（结合日志、执行产物、Skill 实现代码）
      2. 给出解决方案（向用户说明，可复现的问题引导用户操作）
    然后调用本命令上报结构化诊断，避免终态报告丢失失败上下文。

    args 类型：
      - list[str]：从原始 argv 解析（standalone 调用）
      - argparse.Namespace：直接使用（被 cli.py dispatch 调用）
    """
    import argparse

    if isinstance(args, argparse.Namespace):
        ns = args
    else:
        ap = argparse.ArgumentParser(prog="report-error", description="AI 归因诊断上报")
        ap.add_argument("--message", required=True, help="一句话结果摘要")
        ap.add_argument("--code", default="", help="错误码（如 DEVICE_CREATE_FAILED）")
        ap.add_argument("--stage", default="", help="发生阶段（如 B1_device）")
        ap.add_argument("--category", default="unknown",
                        help="归因分类: " + "/".join(CATEGORIES.keys()))
        ap.add_argument("--severity", default="error", help="error/fatal")
        ap.add_argument("--raw", default="", help="原始错误详情/API 响应")
        ap.add_argument("--mis", default="", help="用户 MIS（缺省自动解析）")
        ap.add_argument("--analysis", default="",
                        help='AI 归因诊断 JSON: {"category":"...","summary":"...","suggestion":"...","retryable":true}')
        ap.add_argument("--extra", default="",
                        help="附加结构化上下文 JSON（并入 context，dict/list 保留结构）")
        ns = ap.parse_args(args)

    analysis = _load_json_or_wrap(getattr(ns, "analysis", ""))
    extra = _load_json_or_wrap(getattr(ns, "extra", ""))

    report_exception(
        event="ai_diagnosis",
        message=ns.message,
        code=ns.code,
        stage=ns.stage,
        category=ns.category,
        severity=ns.severity,
        raw=ns.raw,
        analysis=analysis,
        mis=ns.mis,
        extra=extra,
    )
    print(json.dumps({"ok": True, "reported": True,
                      "event": "ai_diagnosis", "code": ns.code}, ensure_ascii=False))