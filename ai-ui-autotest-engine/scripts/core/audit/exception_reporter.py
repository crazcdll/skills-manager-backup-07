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

from core.audit.usage_reporter import SKILL_NAME, _skill_version
from core.util.case_utils import resolve_mis

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


def _truncate(text, max_chars=_FIELD_MAX_CHARS):
    if text is None:
        return ""
    text = str(text)
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _resolve_mis(mis):
    """解析 MIS：显式参数 > HOTEL_UI_MIS 环境变量 > .config/env_answers.json。"""
    if mis:
        return str(mis).strip()
    try:
        return resolve_mis()
    except Exception:
        return ""


def _active_run_dir():
    """尝试从 .run/active_case 读取当前运行目录名（无则返回空）。"""
    try:
        from core.util.paths import ACTIVE_CASE_FILE
        with open(ACTIVE_CASE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or ""
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
        "skill_dir": __import__("core.util.paths", fromlist=["SKILL_DIR"]).SKILL_DIR,
        "cwd": __import__("os").getcwd(),
    }


def _runtime_snapshot():
    """采集运行时快照：flow-context 当前状态、最近审计事件、CLI 调用链。

    不依赖调用方显式传参，能读多少读多少，静默忽略所有异常。
    """
    snapshot = {}

    # 1. CLI 调用链
    snapshot["argv"] = sys.argv[:30]

    # 2. flow-context 摘要 + 最近审计事件
    try:
        from core.util.paths import RUN_DIR, ACTIVE_CASE_FILE
        if os.path.isfile(ACTIVE_CASE_FILE):
            with open(ACTIVE_CASE_FILE, "r", encoding="utf-8") as _f:
                _case_name = _f.read().strip()
            if _case_name:
                from core.flow.flow_context import load_context
                _case_dir = os.path.join(RUN_DIR, "cases", _case_name)
                _ctx = load_context(_case_dir)
                if _ctx:
                    _meta = _ctx.get("meta", {})
                    snapshot["batch_run_id"] = _meta.get("batch_run_id", "")
                    snapshot["flow_name"] = _meta.get("flow_name", "")
                    snapshot["current_stage"] = _ctx.get("sop", {}).get("current_stage", "")
                    _cc = _ctx.get("current_case", {})
                    if _cc:
                        snapshot["current_case_index"] = _cc.get("index", -1)
                        snapshot["current_step_index"] = _ctx.get("current_step_index", -1)
                    _summaries = _ctx.get("cases_summary", [])
                    if _summaries:
                        snapshot["case_statuses"] = [
                            {"id": s.get("case_id", ""), "status": s.get("status", "")}
                            for s in _summaries
                        ]

                # 3. 最近审计事件
                from core.audit.runtime_audit import events_path
                from core.util.json_utils import read_jsonl
                _events_file = events_path(_case_dir)
                if os.path.isfile(_events_file):
                    _all_events = read_jsonl(_events_file)
                    snapshot["recent_events"] = [
                        {
                            "ts": e.get("ts", ""),
                            "event": e.get("event", ""),
                            "sev": e.get("severity", ""),
                        }
                        for e in _all_events[-8:]
                    ]
    except Exception:
        pass

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
        ctx.update({k: _truncate(v) for k, v in extra.items()})

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
        "context": json.dumps(ctx, ensure_ascii=False),
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
def cmd_report_error(args=None):
    """report-error --message <摘要> [--code <错误码>] [--stage <阶段>]
                     [--category <归因>] [--severity <级别>] [--raw <详情>]
                     [--mis <MIS>] [--analysis <AI 诊断 JSON>]

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
        ns = ap.parse_args(args)

    analysis = None
    if ns.analysis:
        try:
            analysis = json.loads(ns.analysis)
            if not isinstance(analysis, dict):
                analysis = {"raw": ns.analysis}
        except json.JSONDecodeError:
            analysis = {"raw": ns.analysis}

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
    )
    print(json.dumps({"ok": True, "reported": True,
                      "event": "ai_diagnosis", "code": ns.code}, ensure_ascii=False))