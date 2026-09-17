#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""input-text / blur-input handler — 文本输入与失焦。

input-text 纯语义模式：action_arg 为 JSON 格式，自动定位锚点+滚动+输入。
失败时返回结构化 reason_code，复用 tap-text 的 Hook 路由。
"""
import json
import time

from context import get_platform_ops
from screen_state.screen_layout import ScreenLayout
from screen_state.inspect_tree import (
    dump_inspect_tree, parse_inspect_tree, _center_of,
    inspect_tree_find_blur_anchor,
)
from actions.handlers.base import _auto_scroll_coords_to_viewport

# ─── Reason Code 定义 ────────────────────────────────────────────
# TEXT_NOT_FOUND / TEXT_OUT_OF_VIEWPORT / UNRESOLVED 与 core/sop/on_fail.py
# 中的 REASON_CODE_HOOK_MAP 联动，复用 tap.py 的 Hook 模板。

_REASON_LABELS = {
    "MISSING_INPUT_TEXT": "缺少输入文本",
    "MISSING_ANCHOR": "缺少锚点文案",
    "TEXT_NOT_FOUND": "锚点文案在视图树中未精确命中（L0/L1），需 AI 语义匹配",
    "UNRESOLVED": "精确命中锚点但不可解析为输入框",
    "TEXT_OUT_OF_VIEWPORT": "锚点已在视图树中找到但不在可视区域内",
    "INPUT_FAILED": "设备文本输入执行失败",
}


def _handoff(reason_code, action_arg="", **kw):
    """标准化 handoff 返回 — 机器→AI 的正常交接点，不是失败。

    适用于 TEXT_NOT_FOUND / TEXT_OUT_OF_VIEWPORT / UNRESOLVED
    等需要 AI 决策的场景。ok=None 告知 Engine 这是 handoff（PENDING），
    不会触发 on_fail 故障排查指引。
    """
    ctx = {"action": "input-text", "arg": action_arg, "reason": reason_code}
    ctx.update(kw)
    label = _REASON_LABELS.get(reason_code, reason_code)
    msg = f"input-text '{action_arg}' {label}" if action_arg else f"input-text {label}"
    return {
        "ok": None, "reason": msg, "ctx": ctx,
        "inspect_tree_impact": "none",
    }


def _fail(reason_code, action_arg="", **kw):
    """标准化失败返回，仅用于真正的失败场景（设备/参数错误）。"""
    ctx = {"action": "input-text", "arg": action_arg, "reason": reason_code}
    ctx.update(kw)
    label = _REASON_LABELS.get(reason_code, reason_code)
    msg = f"input-text '{action_arg}' {label}" if action_arg else f"input-text {label}"
    return {
        "ok": False, "reason": msg, "ctx": ctx,
        "inspect_tree_impact": "none",
    }


# ═══════════════════════════════════════════════════════════════════
# 输入 handler — 纯语义模式
# ═══════════════════════════════════════════════════════════════════
#
# action_arg 格式: '{"anchor":"手机号","text":"138xxxx"}'
#
# 流程:
#   1. 解析 JSON
#   2. inspect_tree_find_center(anchor) 定位
#   3. 未命中 → TEXT_NOT_FOUND → resolve_text_not_found Hook
#   4. 视口外 → TEXT_OUT_OF_VIEWPORT → resolve_target_viewport Hook
#   5. 命中 + 可见 → 自动滚动安全 → 输入
# ═══════════════════════════════════════════════════════════════════

def handle_input_text(action_arg, args):
    """语义化文本输入：通过锚点文案定位输入框 → 清空 → 输入新值。

    action_arg 格式: '{"anchor":"手机号","text":"138xxxx"}'
    定位+滚动+输入一次完成，无需前置 find-input。
    """
    from actions.text_input import input_text as _do_input, edittext_clear

    # ── 解析 JSON action_arg ──────────────────────────────────
    text = (action_arg or "").strip()
    if not text:
        return _fail("MISSING_INPUT_TEXT", "")

    anchor = None
    try:
        payload = json.loads(text)
        if payload and isinstance(payload, dict):
            anchor = (payload.get("anchor") or "").strip()
            text = (payload.get("text") or "").strip()
    except (json.JSONDecodeError, TypeError):
        return _fail("MISSING_ANCHOR", text,
                      hint="action_arg 需为 JSON {\"anchor\":..., \"text\":...}")

    if not anchor:
        return _fail("MISSING_ANCHOR", text,
                      hint="缺少 anchor 字段，无法定位输入框")
    if not text:
        return _fail("MISSING_INPUT_TEXT", anchor)

    # ── 定位锚点 ──────────────────────────────────────────────
    from screen_state.inspect_tree import inspect_tree_find_center as _find_center
    info = _find_center(anchor, detail=True)

    # TEXT_NOT_FOUND
    if info is None:
        print(f"  INPUT-TEXT TEXT_NOT_FOUND: '{anchor}'")
        return _handoff("TEXT_NOT_FOUND", anchor, input_text=text)

    # UNRESOLVED
    if info.get("unresolved"):
        return _handoff("UNRESOLVED", anchor,
                         matched_text=info.get("matched_text", "") or "",
                         subtree=info.get("subtree"), input_text=text)

    cx, cy = info["center"]

    # TEXT_OUT_OF_VIEWPORT
    if info.get("out_of_viewport"):
        return _handoff("TEXT_OUT_OF_VIEWPORT", anchor,
                         center=[cx, cy],
                         viewport_offset=info.get("viewport_offset", 0),
                         input_text=text)

    # ── 命中 + 可见 → 滚动安全 → 输入 ──────────────────────────
    _layout = ScreenLayout.from_ops(get_platform_ops())
    cx, cy = _auto_scroll_coords_to_viewport(cx, cy, _layout, label="INPUT")
    print(f"  INPUT-TEXT '{anchor}' -> '{text}' @({cx},{cy})")

    edittext_clear({"_cx": cx, "_cy": cy})
    time.sleep(0.3)
    ops = get_platform_ops()
    ops.tap(cx, cy)
    time.sleep(0.4)

    ok = _do_input(text)
    if not ok:
        return _fail("INPUT_FAILED", text, center=[cx, cy], anchor=anchor)
    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}


# ═══════════════════════════════════════════════════════════════════
# 失焦 handler
# ═══════════════════════════════════════════════════════════════════

def handle_blur_input(action_arg, args):
    """输入框失焦：点击输入框外部区域。"""
    ops = get_platform_ops()
    anchor = action_arg or ""

    if anchor:
        hit = inspect_tree_find_blur_anchor(anchor)
        if not hit:
            return {"ok": False,
                    "reason": f"blur-input 未找到锚点 '{anchor}'",
                    "ctx": {"action": "blur-input", "arg": anchor,
                            "reason": "ANCHOR_NOT_FOUND"},
                    "inspect_tree_impact": "none"}
        cx, cy = hit["center"]
        ops.tap(cx, cy)
        time.sleep(0.5)
        return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}

    # 无锚点：自动找一个不可点击文案作为失焦目标
    raw = dump_inspect_tree(wait_sec=3, max_attempts=1)
    if raw:
        nodes = parse_inspect_tree(raw)
        for node in nodes:
            if node.get("clickable"):
                continue
            t = (node.get("all_text") or "").strip()
            if len(t) < 2:
                continue
            center = _center_of(node)
            if not center:
                continue
            cx, cy = center
            if cy < 400 and cx > 100:
                ops.tap(cx, cy)
                time.sleep(0.5)
                return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}

    ops.tap(92, 685)
    time.sleep(0.5)
    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "full"}