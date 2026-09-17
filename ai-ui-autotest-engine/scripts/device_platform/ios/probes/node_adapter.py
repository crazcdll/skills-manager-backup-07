#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iOS XCUITest XML / WDA 视图树 → UiNode 适配器。

将 WDA /source 接口输出的 XCUITest XML 树解析为 screen_state.node_model 定义的
统一 UiNode 字典列表（前序 DFS 顺序，parent/children_idx 树结构已构建，
merged_text 已填充），供 screen_state/inspect_tree.py 的智能匹配引擎使用。

字段映射对照（详见 screen_state/node_model.py 顶部的三端字段映射表）：
  - UiNode['text']              <-- XCUIElementTypeStaticText / Other 的 value 或 label
  - UiNode['all_text']          <-- text（UiNode 契约约定）
  - UiNode['x/y/w/h']           <-- x, y, width, height 属性
  - UiNode['clickable']         <-- XCUIElementTypeButton/Cell/Switch 或 accessible=true
  - UiNode['class_name']        <-- XCUIElementTypeXXX 标签名
  - UiNode['m_id']              <-- name / identifier 属性
  - UiNode['parent/children_idx'] <-- DFS 遍历时构建的树结构

输入支持两种格式：
  1. str: 直接的 WDA XML 字符串
  2. dict: dump_inspect_tree 写入的 JSON 格式
     {"code": 0, "data": {"xml": "..."}} 或 WDA 响应的 {"value": "..."}
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any


# ─── iOS XCUIElementType → 滚动方向映射 ────────────────────────────
# WDA XML 没有直接的 scrollable 属性，从元素类型推断

_SCROLLABLE_TAGS = {
    "XCUIElementTypeScrollView": "both",
    "XCUIElementTypeTable": "vertical",
    "XCUIElementTypeCollectionView": "both",
    "XCUIElementTypeWebView": "vertical",
    "XCUIElementTypeTextView": "vertical",
    "XCUIElementTypePageIndicator": "horizontal",
}


def parse_tree(raw_data: Any) -> List[Dict[str, Any]]:
    """解析 WDA 输出的 XML 或包含 XML 的 dict 为标准 UiNode 列表。

    Args:
        raw_data: XML 字符串，或包含 XML 的 dict（支持两种格式：
            {"code": 0, "data": {"xml": "..."}} 或 {"value": "..."}）
    Returns:
        list[dict]: UiNode 字典列表，已填充 parent/children_idx/merged_text。
    """
    if not raw_data:
        return []

    xml_text = _extract_xml(raw_data)
    if not xml_text or "<XCUIElementType" not in xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    nodes = []
    _traverse_xml(root, nodes, depth=0, parent_idx=None)

    # 回填 children_idx（DFS 过程中子节点已 append，但需要回填到父节点）
    for i, node in enumerate(nodes):
        p = node.get("parent")
        if p is not None and p < i:
            nodes[p]["children_idx"].append(i)

    # 构建 merged_text，供 inspect_tree 的文本合并匹配使用
    from screen_state.node_model import build_merged_text
    build_merged_text(nodes)

    return nodes


def _extract_xml(raw_data: Any) -> str:
    """从 str 或 dict 中提取 XML 文本。"""
    if isinstance(raw_data, str):
        return raw_data

    if isinstance(raw_data, dict):
        # 格式1: {"value": "<XCUIElementType...>"}（WDA 原始响应）
        xml_text = raw_data.get("value", "")
        if xml_text:
            return xml_text

        # 格式2: {"code": 0, "data": {"xml": "<XCUIElementType...>"}}（自定义写入格式）
        data = raw_data.get("data", {})
        if isinstance(data, dict):
            xml_text = data.get("xml", "")
            if xml_text:
                return xml_text

    return ""


def _traverse_xml(elem: ET.Element, nodes: List[Dict[str, Any]],
                  depth: int = 0, parent_idx: int = None):
    """DFS 遍历 XML 元素树，构建 UiNode 列表（前序，idx 即位 nodes 下标）。"""
    idx = len(nodes)
    tag = elem.tag
    attrib = elem.attrib

    # 解析坐标
    try:
        x = int(float(attrib.get("x", 0)))
        y = int(float(attrib.get("y", 0)))
        w = int(float(attrib.get("width", 0)))
        h = int(float(attrib.get("height", 0)))
    except (ValueError, TypeError):
        x = y = w = h = 0

    # 提取文本：value 优先，fallback 到 label
    val = attrib.get("value", "")
    lbl = attrib.get("label", "")
    name = attrib.get("name", "")

    text = None
    if val and val != name:
        text = val.strip()
    elif lbl:
        text = lbl.strip()
    elif val:
        text = val.strip()

    # 文本为空时保持 None 而不是空字符串（UiNode 契约约定）
    text = text if text else None

    # 判断是否可点击
    tag_lower = tag.lower()
    clickable = (
        "button" in tag_lower
        or "cell" in tag_lower
        or "switch" in tag_lower
        or attrib.get("accessible") == "true"
        or attrib.get("traits", "").find("Button") >= 0
    )

    scroll_info = _SCROLLABLE_TAGS.get(tag)

    node = {
        "text": text,
        "content_desc": None,       # XCUITest 无独立的 contentDescription 字段
        "all_text": text,           # UiNode 契约：text 优先，否则 content_desc
        "merged_text": "",          # 由 build_merged_text 后处理填充
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "clickable": clickable,
        "scrollable": scroll_info is not None,
        "scroll_dir": scroll_info,
        "depth": depth,
        "parent": parent_idx,
        "children_idx": [],         # 由调用方在遍历完成后回填
        "class_name": tag,
        "m_id": name or attrib.get("identifier", None) or None,
    }

    nodes.append(node)

    for child in elem:
        _traverse_xml(child, nodes, depth=depth + 1, parent_idx=idx)
