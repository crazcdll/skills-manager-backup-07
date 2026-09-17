#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android inspect-tree → UiNode 适配器。

将 imeituan `control inspect-tree` 输出的原始 JSON（exportedProperties 分组
属性结构）解析为 screen_state.node_model 定义的统一 UiNode 字典列表。

inspect-tree JSON 节点结构：
  - class: 类名
  - id: resource-id
  - exportedProperties: 分组属性
    - text.mText: 主文本
    - accessibility.getContentDescription(): 无障碍描述
    - layout.locationOnScreen: "[x, y]" 屏幕绝对坐标
    - layout.width / layout.height: 尺寸
    - misc.isClickable: 是否可点击
    - misc.isScrollable: 是否可滚动
  - children: 子节点数组

parse_tree() 是本模块唯一对外入口，供 screen_state.inspect_tree 按平台分派调用。
"""
import re

from screen_state.node_model import build_merged_text


# ─── 滚动方向推断 ──────────────────────────────────────────────────
# Android class name → 滚动方向映射

_SCROLL_CLASS_MAP = {
    "HorizontalScrollView": "horizontal",
    "ViewPager": "horizontal",
    "RecyclerView": "vertical",
    "ScrollView": "vertical",
    "ListView": "vertical",
    "NestedScrollView": "vertical",
}


def _infer_scroll_dir(class_name):
    """根据 Android class name 推断容器滚动方向。"""
    for cls, direction in _SCROLL_CLASS_MAP.items():
        if cls in class_name:
            return direction
    return None


def parse_tree(raw):
    """Android inspect-tree 原始 JSON → UiNode 列表（前序 DFS 顺序）。

    Args:
        raw: dump_inspect_tree() 采集到的原始 dict（inspect-tree 树根节点）。
    Returns:
        list[dict]: UiNode 字典列表，已填充 merged_text。
    """
    nodes = []
    _walk(raw, 0, None, nodes)
    build_merged_text(nodes)
    return nodes


def _walk(node, depth, parent_idx, nodes):
    props = node.get("exportedProperties", {})
    layout = props.get("layout", {})
    loc = layout.get("locationOnScreen", "")

    x = y = None
    m = re.findall(r'-?\d+', str(loc))
    if len(m) >= 2:
        x, y = int(m[0]), int(m[1])

    text_raw = (props.get("text") or {}).get("mText")
    text = None if text_raw in ("null", None, "") else text_raw

    desc_raw = (props.get("accessibility") or {}).get("getContentDescription()")
    content_desc = None
    if desc_raw and desc_raw.strip() not in ("null", "", "none"):
        content_desc = desc_raw.strip()

    m_id = node.get("id")
    if m_id in ("NO_ID", "", None):
        m_id = None

    misc = props.get("misc") or {}

    idx = len(nodes)
    nodes.append({
        "text": text,
        "content_desc": content_desc,
        "all_text": text if text else content_desc,
        "merged_text": "",
        "x": x,
        "y": y,
        "w": int(layout["width"]) if layout.get("width") is not None else None,
        "h": int(layout["height"]) if layout.get("height") is not None else None,
        "clickable": misc.get("isClickable") == "true",
        "scrollable": misc.get("isScrollable") == "true",
        "scroll_dir": _infer_scroll_dir(node.get("class", "")),
        "depth": depth,
        "parent": parent_idx,
        "children_idx": [],
        "class_name": node.get("class", ""),
        "m_id": m_id,
    })

    for child in node.get("children", []):
        child_idx = len(nodes)
        _walk(child, depth + 1, idx, nodes)
        nodes[idx]["children_idx"].append(child_idx)