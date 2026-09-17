#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告时间线：SOP 阶段 / 审计事件 → 统一 timeline 事件列表。"""
from report.steps import _stage_report


def _build_timeline_events(context, case_index, audit_events, check_deps):
    """构建统一 timeline 事件列表，合并所有数据源，按时间排序。

    事件类型（_type 字段）：
      - sop_stage:    SOP 阶段推进
      - audit_event:  运行时 audit 事件（run-events.jsonl 中的非 SOP 事件）
      - error:        flow-context 中的错误记录
      - check_deps:   前置依赖检测结果
    """
    events = []

    # 1. SOP 阶段事件
    for stage in context.get("sop", {}).get("stages", []):
        sc = stage.get("case_index")
        if sc is None or sc == case_index:
            events.append(_stage_report(stage))

    # 2. SOP 阶段已覆盖的事件类型（不再重复入 timeline）
    _SOP_COVERED_EVENTS = {
        "case.initialized", "step.started", "step.completed",
        "step.failed", "step.retry", "evidence_registered",
    }

    # 3. Audit 事件（黑名单模式：SOP 已覆盖的跳过，其余全部入 timeline）
    for entry in audit_events:
        evt = entry.get("event", "")
        if evt in _SOP_COVERED_EVENTS:
            continue
        detail = entry.get("details", {})
        # evidence.registered 从 details 中提取关键字段展开
        if evt == "evidence.registered":
            d = detail or {}
            events.append({
                "_type": "evidence",
                "event": "evidence_registered",
                "desc": f"证据: {d.get('evidence_type', '')} ({d.get('method', '')})",
                "ts": entry.get("ts", ""),
                "evidence_type": d.get("evidence_type", ""),
                "method": d.get("method", ""),
                "status": d.get("evidence_status", ""),
                "stage": d.get("stage", ""),
                "artifacts": d.get("artifacts", []),
                "details": d,
                "severity": entry.get("severity", "info"),
            })
        else:
            events.append({
                "_type": "audit_event",
                "event": evt,
                "desc": _audit_event_desc(evt, detail),
                "ts": entry.get("ts", ""),
                "details": detail,
                "severity": entry.get("severity", "info"),
            })

    # 4. Error 事件
    for err in context.get("errors", []):
        events.append({
            "_type": "error",
            "event": "stage_error",
            "desc": err.get("error", ""),
            "ts": err.get("ts", ""),
            "stage": err.get("stage", ""),
            "severity": "error",
        })

    # 5. Check-deps 事件（仅注入一次，不区分 case_index）
    if check_deps and case_index == 0:
        failed = [c for c in check_deps.get("checks", []) if not c.get("ok")]
        events.append({
            "_type": "check_deps",
            "event": "check_deps_result",
            "desc": f"前置依赖检测{'通过' if check_deps.get('ok') else '失败'}: "
                    f"{len(check_deps.get('checks', [])) - len(failed)}/{len(check_deps.get('checks', []))} 项通过",
            "ts": check_deps.get("checked_at", ""),
            "ok": check_deps.get("ok"),
            "total": len(check_deps.get("checks", [])),
            "passed": len(check_deps.get("checks", [])) - len(failed),
            "failed": len(failed),
            "checks": [
                {"name": c.get("name"), "ok": c.get("ok"), "detail": c.get("detail", "")}
                for c in check_deps.get("checks", [])
            ],
            "severity": "info" if check_deps.get("ok") else "error",
        })

    # 按时间戳排序
    events.sort(key=lambda e: e.get("ts") or "")
    return events


def _audit_event_desc(event, details):
    """将 audit event 类型转为人类可读描述。

    command_executed 事件从 details 中提取 cmd/sid/action 等字段生成可读描述，
    使时间线不再显示无意义的 'command_executed' + 'INFO'。
    """
    # command.executed 是最高频事件，优先处理
    if event == "command.executed":
        cmd = details.get("cmd", "")
        sid = details.get("sid", "")
        action = details.get("action", "")
        url = details.get("url", "")
        text = details.get("text", "")

        # 根据命令类型组装描述
        if cmd == "open-url" and url:
            # 截断过长 URL，保留关键信息
            url_short = url[:80] + ("..." if len(url) > 80 else "")
            return f"打开页面: {url_short}"
        elif cmd == "step":
            action_label = action or "执行"
            sid_label = f" [{sid}]" if sid else ""
            return f"执行步骤{sid_label}: {action_label}"
        elif cmd == "tap-text":
            target = text or details.get("target", "")
            return f"点击元素: {target}"
        elif cmd == "screenshot":
            return "截图取证"
        elif cmd == "assert-text":
            return "文本断言"
        elif cmd == "log-record":
            return "记录日志"
        elif cmd == "ack":
            key = details.get("key", "")
            return f"确认门禁: {key}"
        elif cmd == "flow-advance":
            return "推进阶段"
        elif cmd == "flow-next":
            return "获取下一步指令"
        else:
            parts = [cmd]
            if sid:
                parts.append(f"步骤{sid}")
            if action:
                parts.append(action)
            return " ".join(parts) if any(p for p in [cmd, sid, action]) else cmd

    desc_map = {
        "run.initialized": "运行初始化完成",
        "run.archived": "运行数据归档",
        "evidence_registered": f"证据注册: {details.get('type', '')}",
        "acknowledged": f"门禁确认: {details.get('key', '')}",
        "ack.hook.auto.completed": f"Hook 自动完成: {details.get('hook_id', '')}",
        "ack.hook.auto.complete.failed": f"Hook 自动完成失败: {details.get('error', '')}",
        "login.failed": f"登录失败: {details.get('method', '')} 环境 {details.get('env', '')}",
        "device.created": f"设备创建成功: {details.get('sandbox_id', '')}",
        "device.failed": f"设备命令失败: {details.get('code', '')} - {details.get('message', '')}",
        "environment.prepared": f"环境准备完成: {details.get('env', '')} 环境 ({details.get('auth_method', '')})",
        "record_event": f"AI 分析记录: {details.get('evidence_type', '')}",
        "engine.action.retry": f"引擎重试: {details.get('action', '')} ({details.get('detail', '')})",
        "engine.assert.retry": f"断言重试: {details.get('retry_type', '')} ({details.get('retry_rounds', '')}轮)",
        "engine.page.ready.timeout": f"page_ready 超时 ({details.get('timeout', '')}s)",
        "engine.open.url.retry": f"open-url 重试: {details.get('reason', '')}",
        "engine.inspect.tree.retry": f"inspect-tree 重试失败: {details.get('last_reason', '')}",
        "error.raised": f"错误终止: {details.get('code', '')} [{details.get('category', '')}] {details.get('message', '')}",
        "soft_failure": f"可容忍失败: {details.get('code', '')} ({details.get('category', '')})",
    }
    return desc_map.get(event, event)
