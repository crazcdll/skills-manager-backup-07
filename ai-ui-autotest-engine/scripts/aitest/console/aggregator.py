#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件归一化：把引擎的多种产物（audit 事件 / 步骤记录 / SOP 阶段）统一成
前端唯一的 UI 事件模型。

UI 事件契约：
    {
      "ts": "2026-09-24T16:31:44",       # 时间
      "level": "info|success|warn|error|fatal",
      "kind": "stage|step|event|raw",
      "task": "<ws>", "run": "<run>",
      "device": "<serial>",              # 可空
      "stage": "<stage_id>",             # 可空
      "case_index": 0,                   # 可空
      "sid": "S1",                       # 可空
      "event": "<audit event>",          # 可空
      "text": "展示用短文本",
      "details": { ... 原样透传 ... }
    }
"""
import time

# audit event → 默认级别（severity 字段存在时以其为准）
_AUDIT_LEVEL = {
    "error.raised": "error",
    "login.failed": "error",
    "device.failed": "warn",
    "soft_failure": "warn",
    "engine.page.ready.timeout": "warn",
    "engine.open.url.retry": "warn",
    "engine.inspect.tree.retry": "warn",
    "engine.action.retry": "warn",
    "engine.assert.retry": "warn",
    "ack.hook.auto.complete.failed": "warn",
    "run.archived": "success",
    "run.initialized": "success",
    "environment.prepared": "success",
    "device.created": "success",
}

_AUDIT_DESC = {
    "run.initialized": lambda d: f"运行初始化完成（预期 {d.get('expected_cases', '?')} 个用例）",
    "run.archived": lambda d: f"运行数据归档：{d.get('archive_dir', '')}",
    "evidence.registered": lambda d: f"证据注册：{d.get('evidence_type', '')}（{d.get('method', '')}）",
    "acknowledged": lambda d: f"门禁确认：{d.get('key', '')}",
    "device.created": lambda d: f"设备创建成功：{d.get('sandbox_id', '')}",
    "device.failed": lambda d: f"设备命令失败：{d.get('code', '')} - {d.get('message', '')}",
    "environment.prepared": lambda d: f"环境准备完成：{d.get('env', '')} 环境（{d.get('auth_method', '')}）",
    "error.raised": lambda d: f"错误终止：{d.get('code', '')} [{d.get('category', '')}] {d.get('message', '')}",
    "soft_failure": lambda d: f"可容忍失败：{d.get('code', '')}（{d.get('category', '')}）",
    "login.failed": lambda d: f"登录失败：{d.get('method', '')} 环境 {d.get('env', '')}",
    "ack.hook.auto.completed": lambda d: f"Hook 自动完成：{d.get('hook_id', '')}",
    "ack.hook.auto.complete.failed": lambda d: f"Hook 自动完成失败：{d.get('error', '')}",
    "record_event": lambda d: f"AI 分析记录：{d.get('evidence_type', '')}",
}


def _iso(ts=None):
    return ts or time.strftime("%Y-%m-%dT%H:%M:%S")


def describe_command(details):
    """command.executed 的可读描述（对齐报告 timeline 的口径）。"""
    cmd = details.get("cmd", "")
    sid = details.get("sid", "")
    action = details.get("action", "")
    url = details.get("url", "")
    text = details.get("text", "")
    if cmd == "open-url" and url:
        return f"打开页面：{url[:80] + ('…' if len(url) > 80 else '')}"
    if cmd == "step":
        return f"执行步骤{f' [{sid}]' if sid else ''}：{action or '执行'}"
    if cmd in ("tap-text", "tap"):
        return f"点击元素：{text or details.get('target', '')}"
    if cmd == "screenshot":
        return "截图取证"
    if cmd == "assert-text":
        return "文本断言"
    if cmd == "log-record":
        return "记录日志"
    if cmd == "ack":
        return f"确认门禁：{details.get('key', '')}"
    if cmd == "flow-advance":
        return "推进阶段"
    if cmd == "flow-next":
        return "获取下一步指令"
    parts = [p for p in (cmd, f"步骤{sid}" if sid else "", action) if p]
    return " ".join(parts) if parts else cmd


def audit_event(task, run, device, rec):
    ev = rec.get("event", "")
    details = rec.get("details", {}) or {}
    level = _AUDIT_LEVEL.get(ev, "info")
    sev = rec.get("severity")
    if sev in ("warn", "error", "fatal"):
        level = sev
    desc_fn = _AUDIT_DESC.get(ev)
    if ev == "command.executed":
        text = describe_command(details)
    elif desc_fn:
        text = desc_fn(details)
    else:
        text = ev
    return {
        "ts": rec.get("ts") or _iso(),
        "level": level,
        "kind": "event",
        "task": task, "run": run,
        "device": device or details.get("serial") or "",
        "stage": details.get("stage") or "",
        "case_index": details.get("case_index"),
        "sid": details.get("sid") or "",
        "event": ev,
        "text": text,
        "details": details,
    }


def stage_event(task, run, device, stage):
    st = stage.get("status", "pending")
    level = {"failed": "error", "completed": "success", "running": "info"}.get(st, "info")
    dur = stage.get("duration_ms")
    suffix = f"（{dur}ms）" if dur else ""
    return {
        "ts": stage.get("completed_at") or stage.get("started_at") or _iso(),
        "level": level,
        "kind": "stage",
        "task": task, "run": run,
        "device": device or "",
        "stage": stage.get("id", ""),
        "case_index": stage.get("case_index"),
        "event": "sop_stage",
        "text": f"[{stage.get('id', '')}] {stage.get('desc', '')} → {st}{suffix}",
        "details": stage,
    }


def step_event(task, run, case_index, device, rec):
    ok = rec.get("ok")
    level = "success" if ok == 1 else ("error" if ok == 0 else "info")
    sid = rec.get("sid") or ""
    desc = rec.get("d", "")
    status = rec.get("status") or ("PASS" if ok == 1 else ("FAIL" if ok == 0 else "—"))
    ms = rec.get("ms")
    suffix = f" · {ms}ms" if ms else ""
    return {
        "ts": rec.get("ts") or _iso(),
        "level": level,
        "kind": "step",
        "task": task, "run": run,
        "device": device or "",
        "stage": "",
        "case_index": case_index,
        "sid": sid,
        "event": "step",
        "text": f"[{sid}] {desc} → {status}{suffix}",
        "details": rec,
    }


def raw_event(task, run, cmd, stream, line, level="info", device=""):
    return {
        "ts": _iso(),
        "level": level,
        "kind": "raw",
        "task": task, "run": run,
        "device": device or "",
        "stage": "",
        "case_index": None,
        "sid": "",
        "event": "raw",
        "text": line,
        "details": {"cmd": cmd, "stream": stream},
    }
