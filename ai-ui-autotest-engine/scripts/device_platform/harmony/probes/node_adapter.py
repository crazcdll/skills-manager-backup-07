#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOS uitest dumpLayout → UiNode 适配器。

将 `hdc shell uitest dumpLayout` 输出的原始 JSON 解析为 screen_state.node_model
定义的统一 UiNode 字典列表，字段语义与 Android node_adapter 对齐（见
screen_state/node_model.py 顶部的三端字段映射对照表）。

选型说明：uitest dumpLayout 直接提供 clickable/enabled/selected/focused/
scrollable/checkable&checked 等标准无障碍属性，语义清晰可靠；父容器
（尤其 MRN/自绘 Custom 类型节点）会自动把子树文本聚合到自身 text 属性，
天然覆盖 Android 侧需要手写 merged_text 兜底的场景。

dumpLayout 原始 JSON 结构：
  {
    "attributes": {
        "text": str, "clickable": "true"/"false", "bounds": "[x1,y1][x2,y2]",
        "type": str, "id": str, "accessibilityId": str, "description": str,
        "enabled"/"selected"/"focused"/"scrollable"/"checkable"/"checked": ...,
        "hierarchy": str,  # 形如 "ROOT836,0,0,1,..."，节点路径标识
        "hashcode": str,   # 形如 "836:19583"，节点唯一标识
        ...
    },
    "children": [ {同结构}, ... ]
  }

parse_tree() 是本模块唯一对外入口，供 screen_state.inspect_tree 按平台分派调用。
"""
import re

from screen_state.node_model import build_merged_text

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_tree(raw):
    """HarmonyOS uitest dumpLayout 原始 JSON → UiNode 列表（前序 DFS 顺序）。

    Args:
        raw: dump_inspect_tree() 采集到的原始 dict（dumpLayout 输出的树根节点，
             顶层为 {"attributes": {...}, "children": [...]}）。
    Returns:
        list[dict]: UiNode 字典列表，已填充 merged_text。
    """
    nodes = []
    _walk(raw, 0, None, nodes)
    build_merged_text(nodes)
    return nodes


def _parse_bounds(bounds_str):
    """"[x1,y1][x2,y2]" → (x, y, w, h)，解析失败返回 (None, None, None, None)。"""
    if not bounds_str:
        return None, None, None, None
    m = _BOUNDS_RE.search(bounds_str)
    if not m:
        return None, None, None, None
    x1, y1, x2, y2 = (int(v) for v in m.groups())
    return x1, y1, x2 - x1, y2 - y1


def _norm_text(v):
    """空串/None 统一归一为 None，避免下游把空串当作"有文本"参与匹配。"""
    if v is None:
        return None
    v = v.strip() if isinstance(v, str) else v
    return v if v else None


def _walk(node, depth, parent_idx, nodes):
    attrs = node.get("attributes", {}) or {}

    x, y, w, h = _parse_bounds(attrs.get("bounds"))

    text = _norm_text(attrs.get("text"))
    content_desc = _norm_text(attrs.get("description"))

    # m_id 优先取业务侧设置的 id（对齐 Android resource-id 语义），
    # 缺失时回退 accessibilityId（uitest 分配的运行时序号，仍具备within-dump
    # 唯一性，可用于日志/调试定位，但跨次采集不稳定，不应长期持久化引用）。
    m_id = _norm_text(attrs.get("id")) or _norm_text(attrs.get("accessibilityId"))

    idx = len(nodes)
    nodes.append({
        "text": text,
        "content_desc": content_desc,
        "all_text": text if text else content_desc,
        "merged_text": "",  # 子节点文本合并（由 build_merged_text 填充）
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "clickable": attrs.get("clickable") == "true",
        "scrollable": attrs.get("scrollable") == "true",
        "scroll_dir": attrs.get("scrollDirection"),  # "horizontal" / "vertical"
        "depth": depth,
        "parent": parent_idx,
        "children_idx": [],  # 子节点索引列表，由 _walk 填充
        "class_name": attrs.get("type", ""),
        "m_id": m_id,
        # 鸿蒙特有透传字段（Android 侧无对应值，保留 None 而非报错）：
        # 供后续扩展 enabled/selected 等状态类断言时按需读取，
        # 当前匹配引擎（screen_state.inspect_tree）不依赖这些字段。
        "enabled": attrs.get("enabled") == "true",
        "selected": attrs.get("selected") == "true",
        "hierarchy": attrs.get("hierarchy"),
        "hashcode": attrs.get("hashcode"),
    })

    for child in node.get("children", []):
        child_idx = len(nodes)  # 子节点 append 后的索引
        _walk(child, depth + 1, idx, nodes)
        # 回填：子节点已添加，将子节点索引记录到当前节点的 children_idx
        nodes[idx]["children_idx"].append(child_idx)
