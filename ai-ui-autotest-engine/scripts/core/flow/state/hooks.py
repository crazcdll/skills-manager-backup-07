#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ack 处理：Ack-Hook 联动、门禁确认写入。
"""
import os
import time

from core.audit.runtime_audit import append_event, verified_evidence, register_evidence
from core.flow.flow_context import load_context, save_context

_EFFECT_VERIFIED_PREFIX = "effect_verified_"
_EFFECT_VERIFIED_HOOK_ID = "verify_effect"


def _resolve_hook_from_ack_key(ctx, key):
    """从 ack key 解析关联的 (sid, hook_id)。

    支持的 key 格式：
    - effect_verified_{sid} → (sid, "verify_effect")
    - 其他 → (None, None)
    """
    if key and key.startswith(_EFFECT_VERIFIED_PREFIX):
        sid = key[len(_EFFECT_VERIFIED_PREFIX):]
        for step in ctx.get("steps", []):
            if step.get("sid") == sid:
                for h in step.get("hooks", []):
                    if h["id"] == _EFFECT_VERIFIED_HOOK_ID and not h.get("completed"):
                        return sid, _EFFECT_VERIFIED_HOOK_ID
                break
    return None, None


def ack_generic(run_dir, key, result_data=None):
    """通用门禁确认：AI 完成 requires_ack 动作后调用。

    当 key 匹配 effect_verified_{sid} 时自动完成 verify_effect hook 并修正状态。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return {"ok": False, "reason": "no_context", "detail": "flow-context.json 不存在"}
    if not key:
        return {"ok": False, "reason": "missing_key", "detail": "--key 不能为空"}

    meta = ctx.setdefault("meta", {})
    runtime = ctx.setdefault("runtime", {})
    env = ctx.get("env", {})
    if key == "login_completed":
        if env.get("type") == "D":
            pass
        else:
            evidence = meta.get("login_evidence") or {}
            evidence_path = evidence.get("path", "") if isinstance(evidence, dict) else ""
            if evidence_path:
                if not os.path.isfile(evidence_path):
                    return {"ok": False, "reason": "login_evidence_missing",
                            "detail": "凭证登录视觉证据不存在或不可读取"}
                evidence["status"] = "verified"
                evidence["verified_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                meta["login_evidence"] = evidence
                register_evidence(run_dir, "login", "password_visual", "verified",
                                  [evidence_path], stage="B2_login")
            elif not verified_evidence(run_dir, "login"):
                return {"ok": False, "reason": "login_evidence_missing",
                        "detail": "未找到已验证的登录证据"}

    hook_sid, hook_id = _resolve_hook_from_ack_key(ctx, key)
    hook_auto_completed = None
    if hook_sid and hook_id:
        from core.flow.step_scheduler import mark_hook_done
        success, remaining = mark_hook_done(run_dir, hook_sid, hook_id)
        if success:
            hook_auto_completed = {"sid": hook_sid, "hook_id": hook_id}
            append_event(run_dir, "ack.hook.auto.completed",
                         {"key": key, "sid": hook_sid, "hook_id": hook_id})
            ctx = load_context(run_dir)
            if ctx is None:
                return {"ok": False, "reason": "no_context_after_mark_hook",
                        "detail": "mark_hook_done 后 flow-context.json 丢失"}
            runtime = ctx.setdefault("runtime", {})
        else:
            hook_auto_completed = {"sid": hook_sid, "hook_id": hook_id, "error": str(remaining)}
            append_event(run_dir, "ack.hook.auto.complete.failed",
                         {"key": key, "sid": hook_sid, "hook_id": hook_id, "error": str(remaining)})

    acks = runtime.setdefault("acks", {})
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    acks[key] = True
    acks[f"{key}_at"] = now
    if result_data is not None:
        # 键名必须是 ack_evidence：evidence["assertions"] 是「断言结果列表」的权威字段
        # （report.steps 按 list 遍历），复用同名键会让 ack 的 dict 把它覆盖掉。
        # 该值由 report.case_report.build_case 落到 case.notes（source="ack"）供报告展示。
        ctx.setdefault("evidence", {}).setdefault("ack_evidence", {})[key] = result_data
    save_context(run_dir, ctx)
    append_event(run_dir, "acknowledged", {"key": key, "result": result_data} if result_data else {"key": key})

    result = {"ok": True, "key": key, "acked_at": now}
    if hook_auto_completed and "error" not in hook_auto_completed:
        result["hook_auto_completed"] = hook_auto_completed
    return result