#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选择器（Selector）—— 把「怎么找一个控件」从代码变成**数据**。

【定位】本模块是"按语义选目标"的**唯一入口**：`resolve(nodes, selectors)`。

【为什么需要】同一份"页面描述"（`PageSpec`）要能被 Android / HarmonyOS / iOS 共用，
而各平台暴露的东西不同：Android 有 resource-id、鸿蒙几乎只有角色/文案（实测登录页仅
normalTextInput/navRoot/ffpRoot 三个 id）。把这些差异表达成**选择器的先后顺序**
（先 id → 再角色 → 再文案 → 再行锚点），平台差异就退化成**数据**，
业务层（登录动作等）不再写任何 `if platform == ...` 或散落的兜底分支。

【与"唯一目标模型"的关系】`execution/screen/tree_index.py` 是"按语义取目标"的模型层；
本模块只负责**选择**（选出哪个节点），**取点规则**复用
`tree_match._find_clickable_center` —— 命中节点自身中心若落在可点击祖先边界内就用节点中心
（否则祖先中心），保证全引擎坐标语义唯一。

【支持的选择器】`{"by": ..., "value": ...}`，按序尝试、命中即停：

  {"by": "id",                    "value": "passport_mobile_phone"}
  {"by": "role",                  "value": ["TextInput", "EditText"]}      # class 关键词
  {"by": "text",                  "value": "获取验证码"}                     # 精确优先→唯一子串
  {"by": "left_clickable_in_row", "value": "我已阅读并同意"}                  # 行内**左侧**最近可点击

新增选择器 = 在 `_RESOLVERS` 加一条，业务层与 PageSpec 无需改动。
"""
from execution.screen.tree_match import _find_clickable_center, find_substring_candidates

# 行判定容差：与 tree_index 的"同一视觉行"口径一致（±60px）
_ROW_Y_TOL = 60


def _text_of(node) -> str:
    return (node.get("all_text") or node.get("text") or node.get("content_desc") or "").strip()


def _pack(nodes, node, strategy):
    """节点 → 解析结果（含**唯一点击取点**）；不可点击且无坐标时返回 None。"""
    point = _find_clickable_center(nodes, node)
    if not point:
        return None
    return {
        "point": point,
        "text": _text_of(node),
        "class_name": node.get("class_name") or "",
        "m_id": node.get("m_id") or "",
        "clickable": bool(node.get("clickable")),
        "checked": node.get("checked"),
        "strategy": strategy,
    }


# ═══════════════════════════════════════════════════════════════════
# 各选择器实现（新增 = 加一条）
# ═══════════════════════════════════════════════════════════════════

def _by_id(nodes, value, **_):
    for n in nodes:
        if (n.get("m_id") or "") == value:
            return _pack(nodes, n, {"by": "id", "value": value})
    return None


def _by_role(nodes, value, **_):
    keywords = value if isinstance(value, (list, tuple)) else [value]
    for n in nodes:
        cls = n.get("class_name") or ""
        if any(k and k in cls for k in keywords):
            return _pack(nodes, n, {"by": "role", "value": list(keywords)})
    return None


def _by_text(nodes, value, **_):
    # 精确优先：文案完全相等；否则退回"唯一子串"（与断言层同口径）
    for n in nodes:
        if _text_of(n) == value:
            return _pack(nodes, n, {"by": "text", "value": value})
    candidates = find_substring_candidates(nodes, value)
    if len(candidates) == 1:
        return _pack(nodes, candidates[0][2], {"by": "text", "value": value})
    return None


def _by_left_clickable_in_row(nodes, value, row_tol=_ROW_Y_TOL, **_):
    """锚点文案**同行且位于其左侧**的最近可点击元素。

    典型用途：协议勾选框 —— 「我已阅读并同意」左侧的那个小图标就是 checkbox，
    它既没有 resource-id、也没有文案，只能靠"行 + 相对位置"表达。
    """
    anchor, anchor_y, anchor_x = None, None, None
    for n in nodes:
        if value in _text_of(n):
            center = _find_clickable_center(nodes, n)
            if center:
                anchor, anchor_y, anchor_x = n, center[1], n.get("x")
                break
    if anchor is None or anchor_x is None:
        return None
    best = None
    for n in nodes:
        if not n.get("clickable"):
            continue
        center = _find_clickable_center(nodes, n)
        if not center or abs(center[1] - anchor_y) > row_tol or center[0] >= anchor_x:
            continue
        if best is None or center[0] > best[1][0]:
            best = (n, center)
    if best is None:
        return None
    return _pack(nodes, best[0], {"by": "left_clickable_in_row", "value": value})


# selector.by → 实现（唯一注册表）
_RESOLVERS = {
    "id": _by_id,
    "role": _by_role,
    "text": _by_text,
    "left_clickable_in_row": _by_left_clickable_in_row,
}


def resolve_one(nodes, selector, **kw):
    """按**单个**选择器解析；不支持/未命中返回 None。"""
    fn = _RESOLVERS.get((selector or {}).get("by"))
    if fn is None:
        return None
    return fn(nodes, (selector or {}).get("value"), **kw)


def resolve(nodes, selectors, **kw):
    """按选择器列表**顺序尝试**，命中即停；全部未命中返回 None。"""
    for selector in selectors or ():
        hit = resolve_one(nodes, selector, **kw)
        if hit:
            return hit
    return None


def supports(node_or_text: str, selectors) -> bool:
    """页面身份判定：`text` 型选择器命中即认为在该页面（供 PageSpec.identity 使用）。

    只接受 `text` 型：身份判定必须基于**页面内容**（跨端可靠），
    窗口名/平台标记另行显式判定（见 `PageSpec.markers`）。
    """
    value = node_or_text or ""
    for selector in selectors or ():
        if (selector or {}).get("by") == "text" and (selector or {}).get("value") in value:
            return True
    return False


__all__ = ["resolve", "resolve_one", "supports", "_RESOLVERS"]
