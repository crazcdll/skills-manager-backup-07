"""tap / tap-text handler — 坐标点击与文本点击。

reason_code 驱动：失败时返回结构化 reason_code，由 engine 路由到对应 Hook。
不再执行内部滚动或模糊文本匹配 —— 这些委托给 ViewportPrecondition 和 AI Hook。
"""

import json
import time

from core.errors import soft_fail
from context import get_platform_ops, get_app_descriptor
from screen_state.screen_layout import ScreenLayout
from screen_state.inspect_tree import (
    inspect_tree_find_center, invalidate_cache,
    dump_inspect_tree, parse_inspect_tree,
    is_debug_overlay, _overlapping_clickables,
    hit_nodes_at, _find_clickable_center,
)
from actions.handlers.base import _auto_scroll_coords_to_viewport

# ─── Reason Code 定义 ────────────────────────────────────────────
# 与 core/sop/on_fail.py 中的 REASON_CODE_HOOK_MAP 联动

_REASON_LABELS = {
    "MISSING_COORDS": "缺少坐标参数（需 --action-x/--action-y）",
    "TEXT_NOT_FOUND": "在视图树中未精确命中（L0/L1），需 AI 语义匹配",
    "UNRESOLVED": "精确命中文本节点但自身不可点击且无可用祖先",
    "AMBIGUOUS": "精确命中多个候选目标，需 AI 判断",
    "TEXT_OUT_OF_VIEWPORT": "目标已在视图树中找到但不在可视区域内",
    "BLOCKED": "目标被调试控件完全遮挡",
    "TAP_FAILED": "设备 tap 执行失败",
    "DEBUG_OVERLAP": "坐标位置命中调试控件",
}


def _handoff(reason_code, action_arg="", **kw):
    """标准化 handoff 返回 — 机器→AI 的正常交接点，不是失败。

    ok=None（PENDING）让引擎知道这是等待 AI 决策的 handoff，
    而非设备/参数错误（FAIL）。Engine 收到 ok=None 后不会退出、
    不会叠加 on_fail 故障排查指引，只走 reason hook 提示 AI 处理。
    """
    ctx = {"action": "tap-text" if action_arg else "tap",
           "arg": action_arg, "reason": reason_code}
    ctx.update(kw)
    label = _REASON_LABELS.get(reason_code, reason_code)
    msg = f"tap-text '{action_arg}' {label}" if action_arg else f"tap {label}"
    return {
        "ok": None,
        "reason": msg,
        "ctx": ctx,
        "inspect_tree_impact": "none",
    }


def _fail(reason_code, action_arg="", **kw):
    """标准化失败返回，仅用于真正的失败场景（设备/参数错误）。

    与 _handoff 的区别：ok=False（FAIL），Engine 会触发 on_fail 路径。
    """
    ctx = {"action": "tap-text" if action_arg else "tap",
           "arg": action_arg, "reason": reason_code}
    ctx.update(kw)
    label = _REASON_LABELS.get(reason_code, reason_code)
    msg = f"tap-text '{action_arg}' {label}" if action_arg else f"tap {label}"
    return {
        "ok": False,
        "reason": msg,
        "ctx": ctx,
        "inspect_tree_impact": "none",
    }


# ─── 通用工具 ────────────────────────────────────────────────────

def _dedup_candidates(candidates):
    """去重候选列表（按 center 坐标去重）。"""
    seen = set()
    unique = []
    for cd in candidates:
        key = tuple(cd["center"])
        if key not in seen:
            seen.add(key)
            unique.append(cd)
    return unique


def _unique_substring_tap_target(nodes, query):
    """action_arg 是某个节点文案的子串、且候选文案形态唯一时，返回 (center, matched_text)。

    与断言策略的 T1.5「唯一子串 → 语义等价」口径一致：形态唯一时结论是确定的，
    直接定位并点击，不再消耗一轮 AI hook（实测单次 ~50s）。
    多形态语义不确定 → 返回 (None, "")，交 AI 消歧。

    只考虑「节点文案包含 query」方向——反向（节点文案是 query 的子串）会把更短、
    更泛的节点误当目标（如 action_arg「已优惠¥184」命中页面「已优惠」）。
    """
    if not nodes or not query:
        return None, ""
    texts = {}
    for n in nodes:
        for t in ((n.get("all_text") or "").strip(),
                  (n.get("content_desc") or "").strip()):
            if t and query in t:
                texts.setdefault(t, n)
    if len(texts) != 1:
        return None, ""
    text, node = next(iter(texts.items()))
    return _find_clickable_center(nodes, node), text


def _record_substring_fallback(args, target, actual, center):
    """把「子串唯一兜底」这一 action 口径差异写入运行时间线，保证可追溯。

    兜底成功后不再生成 TEXT_NOT_FOUND hook，若不在此留痕，报告中就看不到
    「action_arg 与页面实际文案不一致」这一事实（此前由 hook 的 anomaly 承载）。
    """
    try:
        from core.audit.runtime_audit import append_event
        from core.util.case_utils import resolve_case_path
        run_dir = resolve_case_path(getattr(args, "dir", None))
        if not run_dir:
            return
        append_event(run_dir, "tap_text.substring_fallback", {
            "action": "tap-text", "target": target, "actual": actual,
            "center": list(center),
        })
    except Exception as e:  # noqa: BLE001 — 留痕失败不得影响点击结果
        soft_fail("infra", "TAP_SUBSTRING_FALLBACK_AUDIT_FAILED", e)


def _low_confidence_warning(text, info):
    """低置信度匹配告警：match_level 非 L0/L1 精确命中时输出提醒。

    info 为 inspect_tree_find_center(detail=True) 的返回 dict。
    当 match_level 为 MATCH_SUBSTR (2) 及以上（非精确匹配）时，提示 AI
    确认目标是否正确。
    """
    if not info or not isinstance(info, dict):
        return None
    match_level = info.get("match_level")
    # 0=精确匹配, 1=contentDescription 精确匹配 → 不告警
    if match_level is not None and match_level >= 2:
        matched_text = info.get("matched_text", "")
        return (f"⚠️  低置信度匹配: " +
                (f"命中「{matched_text}」(level={match_level})" if matched_text else f"level={match_level}") +
                f"，请结合截图确认目标文案是否正确")
    # probe 探针匹配（非 native）= 匹配质量不可控，输出 mild warning
    probe_name = info.get("probe_name", "native")
    if probe_name != "native":
        return f"⚠️  通过 {probe_name} 探针匹配，请确认截图中的目标是否正确"
    return None


# ═══════════════════════════════════════════════════════════════════
# 坐标点击 handler
# ═══════════════════════════════════════════════════════════════════

def handle_tap(action_arg, args):
    """精确坐标点击，坐标来源于 --action-x/--action-y。"""
    ax = getattr(args, "action_x", None)
    ay = getattr(args, "action_y", None)
    if ax is None or ay is None:
        print("STEP ACTION FAIL: tap 需要 --action-x/--action-y 精确坐标")
        print("  💡 无文案图标：先执行 find-icon --anchor \"<锚点文案>\" 查询结构邻域树，"
              "读出目标节点的 tap 坐标后再用 --action-x/--action-y 执行")
        return _fail("MISSING_COORDS", "",
                     hint="使用 find-icon --anchor 取坐标后重试")
    tx, ty = ax, ay

    # 视口安全：坐标超出视口时尝试自动滚动（被动安全，非语义滚动）
    _tap_layout = get_platform_ops()
    _tap_layout = ScreenLayout.from_ops(_tap_layout)
    tx, ty = _auto_scroll_coords_to_viewport(tx, ty, _tap_layout, label="TAP")

    # 调试控件遮挡检查
    raw = dump_inspect_tree(wait_sec=1, max_attempts=1)
    if raw:
        nodes = parse_inspect_tree(raw)
        debug_nodes = [n for n in nodes if is_debug_overlay(n)]
        if debug_nodes:
            hits = _overlapping_clickables(debug_nodes, (tx, ty))
            if hits:
                from actions.assertion_utils import auto_dismiss_recce
                dismissed = auto_dismiss_recce()
                if dismissed:
                    invalidate_cache()
                    time.sleep(0.5)
                    raw2 = dump_inspect_tree(wait_sec=1, max_attempts=1)
                    if raw2:
                        nodes2 = parse_inspect_tree(raw2)
                        debug_nodes2 = [n for n in nodes2 if is_debug_overlay(n)]
                        hits2 = _overlapping_clickables(debug_nodes2, (tx, ty))
                        if not hits2:
                            print(f"  TAP-SAFETY: Recce 已移除，坐标 ({tx},{ty}) 安全")
                        else:
                            h = hits2[0]
                            print(f"  TAP-SAFETY WARNING: ({tx},{ty}) 仍命中调试控件"
                                  f"「{h['text']}」({h['class_name']})"
                                  f"center={h['center']} bounds={h['bounds']} area={h['area']}")
                            print(f"  💡 请换用 tap-text 或调整坐标后重试")
                            return _fail("DEBUG_OVERLAP", "",
                                         x=tx, y=ty,
                                         hit={"text": h["text"],
                                              "class_name": h["class_name"],
                                              "bounds": list(h["bounds"])})
                else:
                    h = hits[0]
                    print(f"  TAP-SAFETY BLOCKED: ({tx},{ty}) 命中已知调试控件"
                          f"「{h['text']}」({h['class_name']})"
                          f"center={h['center']} bounds={h['bounds']} area={h['area']}")
                    print(f"  💡 请换用 tap-text 或调整坐标后重试（或先 dismiss-recce）")
                    return _fail("DEBUG_OVERLAP", "",
                                 x=tx, y=ty,
                                 hit={"text": h["text"],
                                      "class_name": h["class_name"],
                                      "bounds": list(h["bounds"])})

    ops = get_platform_ops()
    if not ops.tap(tx, ty):
        time.sleep(0.5)
        if not ops.tap(tx, ty):
            print(f"  TAP FAIL @ ({tx},{ty})")
            return _fail("TAP_FAILED", "",
                         x=tx, y=ty,
                         _retry={"count": 1, "detail": "tap_failed"})
        print(f"  TAP (retry) @ ({tx},{ty})")
    print(f"  TAP @ ({tx},{ty})")

    hits = hit_nodes_at(tx, ty)
    if hits:
        print(f"  [TAP-HIT] ({tx},{ty}) 命中 {len(hits)} 个节点:")
        for h in hits:
            c = "✅可点击" if h["clickable"] else " "
            t = f' text="{h["text"]}"' if h["text"] else ""
            print(f"    → {h['class']} id={h['id']} {c}{t}")
            print(f"       center={h['center']} bounds={h['bounds']}")
    else:
        print(f"  [TAP-HIT] ({tx},{ty}) 未命中任何节点")

    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "none"}


# ═══════════════════════════════════════════════════════════════════
# 文本点击 handler — reason_code 驱动架构
# ═══════════════════════════════════════════════════════════════════
#
# 流程：
#   1. inspect_tree_find_center (L0/L1 精确匹配)
#   2. 根据 match 结果返回 reason_code，每个 code 路由到独立 Hook:
#      - TEXT_NOT_FOUND   → resolve_text_not_found hook（子串扫描元素索引取坐标）
#      - UNRESOLVED       → resolve_target_unresolved hook（结构邻域树分析）
#      - AMBIGUOUS        → resolve_target_ambiguous hook（多候选消歧）
#      - TEXT_OUT_OF_VIEWPORT → resolve_target_viewport hook（滚动）
#      - BLOCKED          → resolve_target_blocked hook（避开遮挡）
#      - TAP_FAILED       → on_fail hook（设备重试）
#   3. 匹配成功 + 可见 → 直接 tap，成功返回
# ═══════════════════════════════════════════════════════════════════

def handle_tap_text(action_arg, args):
    """文本点击：通过 inspect-tree L0/L1 精确匹配 → 点击。

    不再执行内部模糊匹配、相似文本收集或自动滚动。
    未精确命中或目标不可见时返回结构化 reason_code，
    由 engine 路由到对应 AI Hook 处理。
    """
    info = inspect_tree_find_center(action_arg, detail=True)

    # ── TEXT_NOT_FOUND: L0/L1 均未命中 ──────────────────────────
    if info is None:
        # 自动扫描视图树做子串匹配，将候选直接输出供 AI 参考
        _nodes = None
        try:
            from screen_state.inspect_tree import get_current_nodes
            _nodes = get_current_nodes(wait_sec=1)
        except Exception as e:
            soft_fail("device", "TAP_SUBSTRING_HINT_SCAN_FAILED", e)

        # 唯一子串兜底：action_arg 恰好是唯一一个节点文案的子串 → 结论确定，直接点击。
        # 避免为一处文案口径差异（页面「已优惠¥184」vs action_arg「已优惠」）白等一轮
        # AI hook。多形态 / 无可点击祖先时不兜底，仍走下面的 handoff。
        _center, _matched = _unique_substring_tap_target(_nodes, action_arg)
        if _center:
            _ops = get_platform_ops()
            if _ops.tap(*_center):
                print(f"  TAP-TEXT 唯一子串命中: '{action_arg}' → 「{_matched}」 @ {tuple(_center)}")
                _record_substring_fallback(args, action_arg, _matched, _center)
                return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "unknown"}
            print(f"  TAP-TEXT 唯一子串命中但 tap 失败: '{action_arg}' @ {tuple(_center)}，转 AI 处理")

        _substring_hints = []
        if _nodes:
            for _n in _nodes:
                _text = (_n.get("all_text") or "").strip()
                if _text and action_arg in _text:
                    _cx = _n.get("x", 0) + (_n.get("w", 0) or 0) // 2
                    _cy = _n.get("y", 0) + (_n.get("h", 0) or 0) // 2
                    _kl = _n.get("clickable", False)
                    _substring_hints.append({
                        "text": _text[:80],
                        "clickable": _kl,
                        "center": [_cx, _cy] if (_n.get("x") is not None and _n.get("y") is not None) else None,
                        "bounds": [_n.get("x"), _n.get("y"),
                                   _n.get("x", 0) + _n.get("w", 0),
                                   _n.get("y", 0) + _n.get("h", 0)],
                    })
        print(f"STEP ACTION FAIL: TEXT_NOT_FOUND '{action_arg}'")
        if _substring_hints:
            print(f"  🔍 视图树中发现 {len(_substring_hints)} 个包含目标子串的节点：")
            for _i, _h in enumerate(_substring_hints[:10], 1):
                _coords = f" @ {_h['center']}" if _h['center'] else ""
                _kl = "✅可点击" if _h['clickable'] else "  "
                print(f"     [{_i}] {_kl}「{_h['text']}」{_coords}")
            if len(_substring_hints) > 10:
                print(f"     ... 还有 {len(_substring_hints) - 10} 个匹配")
        else:
            print(f"  💡 页面上未精确命中「{action_arg}」，视图树中也未发现包含该子串的节点")
        print(f"  💡 以上候选列表已通过 hook 传给 AI 分析，不再额外写 sidecar 文件")
        return _handoff("TEXT_NOT_FOUND", action_arg,
                         substring_hints=[
                             {"text": h["text"][:60],
                              "clickable": h["clickable"],
                              "center": h["center"]}
                             for h in _substring_hints[:10]
                         ])

    # ── UNRESOLVED: 精确命中但不可点击且无可用祖先 ──────────────
    if info.get("unresolved"):
        # 优先级：目标也在视口外 → 先报告 TEXT_OUT_OF_VIEWPORT，
        # 让 AI 先滚动使目标可见后再评估可点击性
        if info.get("out_of_viewport"):
            _c = info.get("center")
            _cy = _c[1] if _c else "坐标缺失"
            _vp_off = info.get("viewport_offset", 0)
            print(f"  TAP-TEXT VIEWPORT: 「{action_arg}」"
                  f"{'y=' + str(_cy) if isinstance(_cy, int) else _cy} 超出视口"
                  f"（偏移 {_vp_off}px），"
                  f"且文本节点不可点击，需 AI 先滚动再确认")
            # 同时传入 subtree/matched_text 供 AI 滚动后参考
            return _handoff("TEXT_OUT_OF_VIEWPORT", action_arg,
                             center=list(_c) if isinstance(_c, (list, tuple)) else None,
                             viewport_offset=_vp_off,
                             subtree=info.get("subtree"),
                             matched_text=info.get("matched_text", ""))
        # 纯 UNRESOLVED：在视口内但不可点击
        subtree = info.get("subtree")
        print(f"STEP ACTION AMBIGUOUS: '{action_arg}' 命中文本节点但自身不可点击，"
              f"且未找到可点击的祖先容器")
        if subtree:
            print(f"  目标周边的结构邻域（JSON 树，class 带\"(骨架)\"的节点仅用于连接结构，"
                  f"本身不是候选目标）：")
            print(f"  {json.dumps(subtree, ensure_ascii=False)}")
        print(f"  💡 请结合上方结构判断真实点击目标（可能是同级/子级的其他控件，如 CheckBox），"
              f"用 step tap --action-x <x> --action-y <y> 指定坐标重试")
        return _handoff("UNRESOLVED", action_arg,
                         matched_text=info.get("matched_text", "") or "",
                         subtree=subtree)

    c = info["center"]
    cx, cy = c
    tapped_parent = info.get("tapped_parent", False)

    # ── AMBIGUOUS: 多个候选目标（精确命中了多处） ──────────────
    candidates = info.get("candidates", [])
    unique = _dedup_candidates(candidates)
    if len(unique) > 1:
        print(f"STEP ACTION AMBIGUOUS: '{action_arg}' 匹配到 {len(unique)} 个可点击目标")
        for i, cd in enumerate(unique, 1):
            _cx, _cy = cd["center"]
            print(f"  [{i}] 「{cd['text']}」@ ({_cx},{_cy}) clickable={cd['clickable']}")
        print(f"  💡 请结合截图和步骤描述，用 step tap --action-x <x> --action-y <y> "
              f"--desc '坐标点击兜底：<实际文案>' 选择正确目标")
        return _handoff("AMBIGUOUS", action_arg,
                         candidates=[{"text": cd["text"], "center": list(cd["center"])}
                                     for cd in unique])

    # ── TEXT_OUT_OF_VIEWPORT: 目标在视口外，触发 ViewportPrecondition ──
    # 程序不再内部调用 _auto_scroll_to_viewport —— 由 engine 路由到
    # resolve_target_viewport hook，AI 确认截图 + 调用 scroll-until 处理
    out_of_viewport = info.get("out_of_viewport", False)
    if out_of_viewport:
        vp_offset = info.get("viewport_offset", 0)
        print(f"  TAP-TEXT VIEWPORT: 「{action_arg}」y={cy} 超出视口，"
              f"偏移 {vp_offset}px，需 AI 处理")
        return _handoff("TEXT_OUT_OF_VIEWPORT", action_arg,
                         center=[cx, cy],
                         viewport_offset=vp_offset)

    # ── BLOCKED: 被调试控件遮挡 ────────────────────────────────
    overlap = info.get("overlap", [])
    if overlap:
        recce_prefixes = [p for p in get_app_descriptor().debug_overlay_prefixes
                          if "recce" in p]
        recce_overlaps = [h for h in overlap
                          if any(h["class_name"].startswith(p) for p in recce_prefixes)]
        if recce_overlaps:
            from actions.assertion_utils import auto_dismiss_recce
            dismissed = auto_dismiss_recce()
            if dismissed:
                invalidate_cache()
                info2 = inspect_tree_find_center(action_arg, detail=True)
                if info2 and info2.get("center") and not info2.get("overlap"):
                    c = info2["center"]
                    cx, cy = c
                    tapped_parent = info2.get("tapped_parent", False)
                    overlap = []  # Recce 移除后不再遮挡，继续 tap
                else:
                    return _handoff("BLOCKED", action_arg,
                                     tapped_center=[cx, cy],
                                     overlap=[{"text": h["text"],
                                               "class_name": h["class_name"],
                                               "center": list(h["center"]),
                                               "bounds": list(h["bounds"])}
                                              for h in overlap])
            else:
                return _handoff("BLOCKED", action_arg,
                                tapped_center=[cx, cy],
                                overlap=[{"text": h["text"],
                                          "class_name": h["class_name"],
                                          "center": list(h["center"]),
                                          "bounds": list(h["bounds"])}
                                         for h in overlap])
        else:
            return _handoff("BLOCKED", action_arg,
                            tapped_center=[cx, cy],
                            overlap=[{"text": h["text"],
                                      "class_name": h["class_name"],
                                      "center": list(h["center"]),
                                      "bounds": list(h["bounds"])}
                                     for h in overlap])

    # ── TAP EXECUTION ───────────────────────────────────────────
    ops = get_platform_ops()
    if not ops.tap(cx, cy):
        time.sleep(0.5)
        if not ops.tap(cx, cy):
            print(f"  TAP FAIL '{action_arg}' @ ({cx},{cy})")
            return _fail("TAP_FAILED", action_arg,
                         center=[cx, cy],
                         _retry={"count": 1, "detail": "tap_failed"})

    if tapped_parent:
        print(f"  TAP '{action_arg}' @ ({cx},{cy}) (文本节点不可点击，已上溯到可点击父容器)")
    else:
        print(f"  TAP '{action_arg}' @ ({cx},{cy})")

    return {"ok": True, "reason": "", "ctx": {}, "inspect_tree_impact": "unknown"}