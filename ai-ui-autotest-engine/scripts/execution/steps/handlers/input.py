#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""input-text / blur-input handler — 文本输入与失焦。

input-text 纯语义模式：action_arg 为 JSON 格式，自动定位锚点+滚动+输入。
失败时返回结构化 reason_code，复用 tap-text 的 Hook 路由。
"""
import json
import time

from shared.context import get_platform_ops
from execution.screen.screen_layout import ScreenLayout
from execution.screen.inspect_tree import (
    dump_inspect_tree, parse_inspect_tree, _center_of,
    inspect_tree_find_blur_anchor,
)
from execution.steps.handlers.base import (
    _auto_scroll_coords_to_viewport, make_action_hit,
)
from execution.assertions.constants import VERDICT_SEMANTIC
from execution.screen.tree_index import (
    dump_index, render_candidates, render_anchor_row, resolve_anchor_editable,
)

# ─── Reason Code 定义 ────────────────────────────────────────────
# TEXT_NOT_FOUND / UNRESOLVED / TEXT_OUT_OF_VIEWPORT / ANCHOR_NOT_FOUND 由
# execution/engine/sop/on_fail.py 的 reason_hook_template 按 **(意图, reason)** 路由到
# input / blur 的专用 Hook 模板（不再复用点击类模板 —— 输入不能用坐标点击替代）。

_REASON_LABELS = {
    "MISSING_INPUT_TEXT": "缺少输入文本",
    "MISSING_ANCHOR": "缺少锚点文案",
    "ANCHOR_NOT_FOUND": "失焦锚点在页面中找不到，或其落点被可点击区域覆盖（点它会触发跳转/弹窗），需 AI 从候选里选定惰性文本锚点",
    "TEXT_NOT_FOUND": "锚点文案在视图树中未精确命中（L0/L1），需 AI 语义匹配",
    "TEXT_OUT_OF_VIEWPORT": "锚点已在视图树中找到但不在可视区域内",
    "INPUT_FAILED": "设备文本输入执行失败",
    "INPUT_TARGET_UNRESOLVED": "锚点行内无法唯一确定输入框（可能无输入框 / 需先点击展开 / 是选择器），需 AI 自行定位",
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
# 输入 handler — 锚点定位（引擎自己在锚点行内找输入框）
# ═══════════════════════════════════════════════════════════════════
#
# 两种形态（与 tap 的锚点/坐标两形态对称）：
#   · 锚点形态（声明步骤用）：action_arg = '{"anchor":"<锚点或语义描述>","text":"<值>"}'
#   · 坐标兜底（hook 用）   ：--action-x/--action-y + action_arg = '{"text":"<值>"}'
#
# 流程（锚点形态）:
#   1. 解析 JSON，取 anchor/text
#   2. resolve_anchor_editable(targets, anchor) 在锚点所在行/容器内找 role=input
#   3. 锚点未命中          → TEXT_NOT_FOUND         → on_input_anchor_not_found Hook
#   4. 行内 0/≥2 个输入框  → INPUT_TARGET_UNRESOLVED → on_input_box_resolve Hook（AI 自己找框）
#   5. 唯一但视口外        → TEXT_OUT_OF_VIEWPORT    → on_input_anchor_viewport Hook
#   6. 唯一且可见          → 滚动安全 → 聚焦清空 → 输入
# ═══════════════════════════════════════════════════════════════════

def handle_input_text(action_arg, args):
    """语义化文本输入：由锚点/语义描述**自己找到输入框** → 清空 → 输入新值。

    两种形态（与 tap 的锚点/坐标两形态对称）：
      · 锚点形态（声明步骤用）：action_arg = '{"anchor":"<锚点或语义描述>","text":"<值>"}'
        Flow 只给「输入框附近的锚点」或「一句语义描述」，引擎在锚点所在**行/容器**内
        自行定位 role=input 目标；定位不到不盲输入，转专用 hook 由 AI 自己找输入框。
      · 坐标形态（hook 兜底用）：--action-x/--action-y 指定输入框坐标 + action_arg='{"text":"<值>"}'
        AI 读图 / find-input 找到输入框后回写坐标 —— 仍是「输入」，不是坐标点击。
    """
    sid = getattr(args, "sid", "") or ""

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
                      hint="action_arg 需为 JSON {\"anchor\":..., \"text\":...} 或 {\"text\":...}")
    if not text:
        return _fail("MISSING_INPUT_TEXT", anchor or "")

    ax = getattr(args, "action_x", None)
    ay = getattr(args, "action_y", None)

    # ── 形态 B：坐标兜底（AI 已找到输入框坐标）──────────────────
    if not anchor:
        if ax is None or ay is None:
            return _fail("MISSING_ANCHOR", text,
                         hint="需 anchor（锚点/语义描述）或 --action-x/--action-y（输入框坐标）")
        return _input_at(sid, int(ax), int(ay), text)

    # ── 形态 A：锚点/语义描述 → 引擎自己在锚点行内找输入框 ──────
    targets, md_path = dump_index(sid, "action=input-text", wait_sec=1)
    if not targets.get("available"):
        return _fail("INPUT_FAILED", anchor, hint="视图树不可用，稍后重试")

    resolution = resolve_anchor_editable(targets, anchor)

    # 锚点未命中 → 给子串/语义重叠候选帮 AI 修正锚点
    if not resolution["found"]:
        print(f"  INPUT-TEXT TEXT_NOT_FOUND: '{anchor}'")
        return _handoff("TEXT_NOT_FOUND", anchor,
                        candidate_list=render_candidates(targets, "substring", anchor=anchor),
                        element_index_path=md_path or "",
                        input_text=text)

    # 锚点行内无法唯一确定输入框（0 或 ≥2）→ 不盲输入，交专用 hook
    picked = resolution["picked"]
    if picked is None:
        print(f"  INPUT-TEXT INPUT_TARGET_UNRESOLVED: 锚点「{anchor}」行内无法唯一确定输入框"
              f"（可编辑候选 {len(resolution['candidates'])} 个）")
        return _handoff("INPUT_TARGET_UNRESOLVED", anchor,
                        center=resolution["anchor"].get("center"),
                        candidate_count=len(resolution["candidates"]),
                        candidate_list=render_anchor_row(targets, anchor),
                        element_index_path=md_path or "",
                        input_text=text)

    cx, cy = picked["center"]

    # 输入框在视口外 → 先滚动再输入
    if not picked.get("in_viewport", True):
        return _handoff("TEXT_OUT_OF_VIEWPORT", anchor,
                        center=[cx, cy],
                        viewport_offset=picked.get("viewport_offset", 0),
                        element_index_path=md_path or "",
                        input_text=text)

    return _input_at(sid, cx, cy, text, anchor=anchor,
                     matched_text=(resolution["anchor"].get("text") or ""))


def _input_at(sid, cx, cy, text, anchor="", matched_text=""):
    """在指定坐标「聚焦 + 清空 + 输入」——锚点形态与坐标兜底形态共用。"""
    from execution.steps.text_input import input_text as _do_input, edittext_clear

    _layout = ScreenLayout.from_ops(get_platform_ops())
    cx, cy = _auto_scroll_coords_to_viewport(cx, cy, _layout, label="INPUT")
    label = anchor or f"({cx},{cy})"
    print(f"  INPUT-TEXT '{label}' -> '{text}' @({cx},{cy})")

    edittext_clear({"_cx": cx, "_cy": cy})
    time.sleep(0.3)
    ops = get_platform_ops()
    ops.tap(cx, cy)
    time.sleep(0.4)

    if not _do_input(text):
        return _fail("INPUT_FAILED", text, center=[cx, cy], anchor=anchor)

    # 锚点与页面文案口径不一致（语义重叠命中）→ 标记待人工复核
    _hit = None
    if anchor and matched_text and matched_text != anchor:
        _hit = make_action_hit(
            VERDICT_SEMANTIC, anchor, matched_text,
            f"锚点「{anchor}」与页面文案「{matched_text}」语义重叠（用于定位输入框）",
        )
        print(f"  ⚠️  {_hit['reason']} —— 已标记待人工复核")
    return {"ok": True, "reason": "",
            "ctx": {"action_hit": _hit} if _hit else {},
            "inspect_tree_impact": "full"}


# ═══════════════════════════════════════════════════════════════════
# 失焦 handler
# ═══════════════════════════════════════════════════════════════════

def handle_blur_input(action_arg, args):
    """输入框失焦：点击输入框外部区域。"""
    ops = get_platform_ops()
    anchor = action_arg or ""
    sid = getattr(args, "sid", "") or ""

    if anchor:
        hit = inspect_tree_find_blur_anchor(anchor)
        if not hit:
            # 锚点找不到属于「不确定」场景 → handoff AI，而非硬失败
            _targets, _md_path = dump_index(sid, "action=blur-input", wait_sec=1)
            return _handoff("ANCHOR_NOT_FOUND", anchor,
                            candidate_list=render_candidates(_targets, "non_clickable", anchor=anchor),
                            element_index_path=_md_path or "")
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