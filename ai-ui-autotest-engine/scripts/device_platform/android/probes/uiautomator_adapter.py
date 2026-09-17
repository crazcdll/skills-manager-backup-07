#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uiautomator XML → imeituan 兼容 JSON 适配器。

将 adb shell uiautomator dump 输出的 XML 视图树转换为与 imeituan
`control inspect-tree` 相同的 JSON 结构（class/id/exportedProperties/children），
使 parse_inspect_tree() → node_adapter.parse_tree() 无需任何改动即可消费。

uiautomator XML 节点属性：
  - text, content-desc, resource-id, class, package
  - clickable, checkable, checked, enabled, focusable, focused, scrollable
  - bounds="[x1,y1][x2,y2]"
  - children: 子 <node> 元素

转换后的 JSON 结构（与 imeituan 一致）：
  {
    "class": "android.widget.TextView",
    "id": "com.sankuai.meituan:id/button",
    "exportedProperties": {
      "text": {"mText": "去登录"},
      "accessibility": {"getContentDescription()": "..."},
      "layout": {
        "locationOnScreen": "[x, y]",
        "width": "w",
        "height": "h"
      },
      "misc": {"isClickable": "true"}
    },
    "children": [...]
  }
"""
import re
import xml.etree.ElementTree as ET


def parse_uiautomator_xml(xml_content: str) -> dict:
    """uiautomator dump XML → imeituan 兼容的 JSON 树根节点。

    Args:
        xml_content: uiautomator dump 输出的原始 XML 字符串。

    Returns:
        dict: 根节点 JSON（与 imeituan inspect-tree 结构一致），
              可直接传给 parse_inspect_tree() → node_adapter.parse_tree()。
    """
    root = ET.fromstring(xml_content)
    # 根是 <hierarchy>，其下第一个 <node> 是视图树根
    hierarchy_node = root.find(".//node")
    if hierarchy_node is None:
        return {"class": "android.widget.FrameLayout", "id": None,
                "exportedProperties": {}, "children": []}
    return _convert_node(hierarchy_node)


def _convert_node(xml_node) -> dict:
    """单个 uiautomator <node> → imeituan JSON 节点。"""
    attrs = xml_node.attrib

    # 解析 bounds="[x1,y1][x2,y2]"
    bounds_str = attrs.get("bounds", "")
    x = y = None
    w = h = None
    m = re.findall(r'-?\d+', bounds_str)
    if len(m) >= 4:
        x1, y1, x2, y2 = int(m[0]), int(m[1]), int(m[2]), int(m[3])
        x, y = x1, y1
        w = x2 - x1
        h = y2 - y1

    # 文本
    text = attrs.get("text") or None
    if text == "":
        text = None

    # content-desc
    content_desc = attrs.get("content-desc") or None
    if content_desc in ("", "none"):
        content_desc = None

    # resource-id
    m_id = attrs.get("resource-id") or None
    if m_id in ("", "android:id/widget_frame"):
        m_id = None

    # clickable
    clickable = attrs.get("clickable", "false") == "true"

    # 坐标字符串
    loc_str = f"[{x}, {y}]" if x is not None else ""

    node_json = {
        "class": attrs.get("class", ""),
        "id": m_id,
        "exportedProperties": {
            "text": {"mText": text} if text else {},
            "accessibility": {"getContentDescription()": content_desc} if content_desc else {},
            "layout": {
                "locationOnScreen": loc_str,
                "width": str(w) if w is not None else None,
                "height": str(h) if h is not None else None,
            },
            "misc": {"isClickable": "true" if clickable else "false"},
        },
        "children": [],
    }

    # 递归子节点
    for child in xml_node:
        if child.tag == "node":
            node_json["children"].append(_convert_node(child))

    return node_json