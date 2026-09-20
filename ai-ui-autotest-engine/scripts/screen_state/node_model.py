#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UiNode 统一节点模型 — 跨平台视图树的公共契约。

各平台通过 adapter 将原始树转换为统一 UiNode 字典，智能匹配引擎只依赖此结构。
点击率语义在不同平台不完全等价，接入新平台时请结合 API 实际语义核对。
"""


def build_merged_text(nodes):
    """后处理：为每个节点填充 merged_text（平台无关，供各 adapter 复用）。

    只拼接当前节点自身 all_text + 直接子节点（不递归到孙节点）的 all_text，
    按 DOM 顺序合并。用于 find-text 断言时匹配被渲染引擎拆分到同层多个文本
    子节点的文案（如父节点 text=None，子节点1 text="2"，子节点2 text="间"
    → 父节点 merged_text="2间"）。

    不递归到孙节点：避免拥有大量子孙的容器节点（尤其根节点）携带整个子树
    文案，导致文本匹配产生与查询语义无关的假阳性命中。

    Args:
        nodes: list[dict]，adapter 已产出的 UiNode 列表（parent/children_idx
            已构建完毕），本函数原地修改每个节点的 merged_text 字段。
    """
    for node in nodes:
        parts = []
        if node.get("all_text"):
            parts.append(node["all_text"])
        for ci in node.get("children_idx", []):
            if ci >= len(nodes):
                continue
            child_text = nodes[ci].get("all_text")
            if child_text:
                parts.append(child_text)
        node["merged_text"] = "".join(parts)


def new_node(*, text=None, content_desc=None, x=None, y=None, w=None, h=None,
             clickable=False, depth=0, parent=None, class_name="", m_id=None,
             checked=None):
    """构造一个符合 UiNode 契约的节点字典（children_idx/merged_text 由调用方/
    build_merged_text 填充），供各平台 adapter 统一调用，避免手写字典遗漏字段。

    checked: 勾选态三值语义 —— True/False 为真实状态，None 表示该平台/节点未暴露
             勾选属性（不可判定），供复选框类操作前读状态、避免盲点取反。
    """
    return {
        "text": text,
        "content_desc": content_desc,
        "all_text": text if text else content_desc,
        "merged_text": "",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "clickable": bool(clickable),
        "checked": checked,
        "depth": depth,
        "parent": parent,
        "children_idx": [],
        "class_name": class_name or "",
        "m_id": m_id,
    }