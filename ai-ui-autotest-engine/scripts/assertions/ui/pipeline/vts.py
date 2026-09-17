#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VTS（View Tree Scan）—— 视图树元素索引构建与锚点定位。

核心能力：
1. build_element_index：从 UiNode 构建结构化元素索引 e1/e2/e3...（含类型推导、空间排序、邻域上下文）
2. locate_anchor：快速判断目标文本是否在视图树中存在（T1 程序化匹配）
3. locate_anchor_substring：子串回退，判定「expect 是页面复合文案的子串」这类语义等价
4. locate_anchor_gone：检查文本是否已从视图树消失（带重试）
"""

from __future__ import annotations
import time
from screen_state.inspect_tree import (
    get_current_nodes,
    find_substring_candidates, MATCH_SUBSTR,
    _find_best_nodes, invalidate_cache,
)


# ─── 元素类型推导（跨平台，含 RN） ────────────────────────────────────────

_UI_TYPE_RULES = [
    # 原生 Android
    ("Button", True, "button"),
    ("EditText", True, "input"),
    ("ImageView", True, "image"),
    ("CheckBox", True, "checkbox"),
    ("Switch", True, "toggle"),
    ("ToggleButton", True, "toggle"),
    # React Native
    ("RecceTextView", True, "text"),
    ("RecceEditText", True, "input"),
    ("MTRecceImageView", True, "image"),
    ("RCTRoundImageView", True, "image"),
    ("RCTImageView", True, "image"),
    ("ReactImageView", True, "image"),
    ("ReactTextView", True, "text"),
    ("AppCompatTextView", True, "text"),
    ("AppCompatButton", True, "button"),
    ("AppCompatImageButton", True, "button"),
    ("AppCompatImageView", True, "image"),
    # iOS / Harmony 通用
    ("UITextField", True, "input"),
    ("UITextView", True, "input"),
    ("UIButton", True, "button"),
    ("UIImageView", True, "image"),
    ("UISwitch", True, "toggle"),
    ("HarmonyButton", True, "button"),
    ("HarmonyText", True, "text"),
    ("HarmonyImage", True, "image"),
    ("HarmonyInput", True, "input"),
]


def _classify_node(node):
    """从 UiNode 推导语义类型。

    优先级：clickable > class_name 关键词匹配 > 默认 text。
    """
    cls = node.get("class_name", "").rsplit(".", 1)[-1]

    # 可点击优先识别为 button（包括空文本的可点击区域如浮层关闭按钮）
    if node.get("clickable"):
        return "button"

    # 按关键词匹配
    for keyword, match_end, etype in _UI_TYPE_RULES:
        if match_end:
            if cls == keyword or cls.endswith(keyword):
                return etype
        else:
            if keyword in cls:
                return etype

    return "text"


def _is_meaningful(node):
    """节点是否值得进入 Element Index。

    保留条件：有文本 / 可点击 / 是输入框 / 是图片。
    过滤条件：无文本且不可点击的纯布局容器、调试控件。
    """
    cls = node.get("class_name", "").rsplit(".", 1)[-1].lower()

    # 调试控件过滤
    if any(k in cls for k in ("debug", "overlay")):
        return False

    # 有文本 → 保留
    if node.get("all_text") or node.get("merged_text"):
        return True

    # 可点击（空按钮，如图标/浮层关闭）→ 保留
    if node.get("clickable"):
        return True

    # 输入框 → 保留
    if "edittext" in cls or "input" in cls:
        return True

    # 图片 → 保留
    if any(k in cls for k in ("imageview", "image")):
        return True

    return False


def _get_element_text(node):
    """获取节点的最佳展示文本。

    优先用 merged_text（聚合子节点拆分文本，如 RN "9"+"月"+"18"+"日" → "9月18日"），
    其次用 all_text（自身文本）。
    """
    merged = (node.get("merged_text") or "").strip()
    if merged:
        return merged
    return (node.get("all_text") or "").strip()


def _build_context(elements, idx, window=2):
    """构建 idx 元素的邻域上下文：前 window 个元素的 id 列表。"""
    ctx = []
    start = max(0, idx - window)
    for j in range(start, idx):
        ctx.append(elements[j]["id"])
    return ctx


def _get_viewport():
    """从平台获取屏幕尺寸。"""
    try:
        from context import get_platform_ops as _get_ops
        ops = _get_ops()
        return ops.screen_size()
    except Exception:
        return None


def write_element_catalog(index: dict, catalog_path: str):
    """将 element_index 格式化为 AI 友好的 markdown 目录文件。

    替代原有的 JSON 侧写文件，AI 直接读此文件即可完成语义匹配，
    无需额外 grep/脚本过滤 JSON。

    目录内容按视口分区（视口内 / 视口下方 / 视口上方），
    每个元素一行含 ID/类型/文案/坐标/视口偏移和可点击状态。

    Args:
        index: build_element_index() 返回的 dict
        catalog_path: 输出文件路径（以 .catalog.md 结尾）
    """
    if not index.get("available"):
        return

    elements = index.get("elements", [])
    total = index.get("total", 0)
    viewport = index.get("viewport")  # [width, height]

    # 视口边界估算（与 ScreenLayout 默认值一致）
    vp_top = 90
    vp_bottom = (viewport[1] - 120) if viewport else (1280 - 120)

    # 按 in_viewport 分组
    in_viewport = []
    below = []
    above = []
    clickable = []

    for e in elements:
        text = e.get("text", "").strip()
        cy = e["center"][1] if e.get("center") else 0

        if e["in_viewport"]:
            in_viewport.append(e)
            if e["clickable"] and text:
                clickable.append(e)
        elif cy < vp_top:
            above.append(e)
        else:
            below.append(e)

    # ── 构建 markdown ──
    lines = []
    lines.append(f"## 页面元素目录（共 {total} 项）")
    if viewport:
        lines.append(f"> 视口尺寸: {viewport[0]}×{viewport[1]}，"
                     f"视口区域 y=[{vp_top},{vp_bottom}]")
    lines.append("")

    # 视口内
    lines.append(f"### 📍 视口内可见（{len(in_viewport)} 项）")
    lines.append("")
    lines.append("| ID | 类型 | 文案 | center | 可点击 |")
    lines.append("|----|------|------|--------|--------|")
    for e in in_viewport:
        text = e.get("text", "")[:60].replace("|", "\\|")
        center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
        clk = "✅" if e["clickable"] else ""
        lines.append(f"| {e['id']} | {e['type']} | {text} | {center} | {clk} |")
    lines.append("")

    # 视口下方
    if below:
        lines.append(f"### 🔽 视口下方（{len(below)} 项，距视口底部偏移）")
        lines.append("")
        lines.append("| ID | 类型 | 文案 | 偏移(↓px) | center |")
        lines.append("|----|------|------|----------|--------|")
        for e in below:
            text = e.get("text", "")[:60].replace("|", "\\|")
            cy = e["center"][1] if e.get("center") else 0
            offset = max(0, cy - vp_bottom)
            center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
            lines.append(f"| {e['id']} | {e['type']} | {text} | ↓{offset} | {center} |")
        lines.append("")

    # 视口上方
    if above:
        lines.append(f"### 🔼 视口上方（{len(above)} 项，距视口顶部偏移）")
        lines.append("")
        lines.append("| ID | 类型 | 文案 | 偏移(↑px) | center |")
        lines.append("|----|------|------|----------|--------|")
        for e in above:
            text = e.get("text", "")[:60].replace("|", "\\|")
            cy = e["center"][1] if e.get("center") else 0
            offset = vp_top - cy
            center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
            lines.append(f"| {e['id']} | {e['type']} | {text} | ↑{offset} | {center} |")
        lines.append("")

    # 可点击元素
    if clickable:
        lines.append(f"### ⚡ 可点击元素（{len(clickable)} 项）")
        lines.append("")
        lines.append("| 文案 | ID | 位置 |")
        lines.append("|------|----|------|")
        for e in clickable:
            text = e.get("text", "")[:50].replace("|", "\\|")
            pos = "可见" if e["in_viewport"] else "下方"
            lines.append(f"| {text} | {e['id']} | {pos} |")
        lines.append("")

    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build_element_index(nodes=None, wait_sec=3):
    """从 UiNode 列表构建 Element Index（元素索引）。

    核心流程：
      1. 通过 get_current_nodes() 获取 UiNode 列表（自动缓存）
      2. 过滤无意义节点（纯布局容器、调试控件）
      3. 推导语义类型（button/text/input/image/checkbox/toggle）
      4. merged_text 聚合拆分文本（RN 跨节点渲染场景）
      5. 按空间排序（y 从上到下，x 从左到右）
      6. 编号 e1/e2/...
      7. 构建邻域上下文（相邻元素 ID 引用）

    Args:
        nodes: 可选，手动传入 UiNode 列表（不传则自动从 get_current_nodes 获取）
        wait_sec: dump_inspect_tree 的超时时间

    Returns:
        dict: {
            "available": bool,
            "total": int,
            "viewport": [width, height] | None,
            "elements": [
                {
                    "id": "e1",
                    "type": "button" | "text" | "input" | "image" | "checkbox" | "toggle",
                    "text": str,              # 展示文本（merged_text 优先）
                    "bounds": [x1,y1,x2,y2],  # 空间位置
                    "center": [cx, cy],       # 点击坐标
                    "clickable": bool,
                    "in_viewport": bool,
                    "context": ["e0"],         # 邻域上下文（上方元素 ID）
                },
            ]
        }
    """
    if nodes is None:
        nodes = get_current_nodes(wait_sec=wait_sec)
        if nodes is None:
            return {"available": False, "total": 0, "elements": []}

    viewport = _get_viewport()

    # 1) 过滤
    candidates = []
    for n in nodes:
        if not _is_meaningful(n):
            continue
        text = _get_element_text(n)
        candidates.append((n, text))

    # 2) 构建元素条目
    raw_elements = []
    for n, text in candidates:
        etype = _classify_node(n)
        center = [n["x"] + n["w"] // 2, n["y"] + n["h"] // 2] if n["x"] is not None else None
        bounds = [n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]] if n["x"] is not None else None

        raw_elements.append({
            "type": etype,
            "text": text[:100],
            "bounds": bounds,
            "center": center,
            "clickable": n["clickable"],
            "in_viewport": n.get("in_viewport", True),
        })

    # 3) 空间排序（从上到下，从左到右）
    raw_elements.sort(key=lambda e: (
        e["bounds"][1] if e["bounds"] else 0,
        e["bounds"][0] if e["bounds"] else 0,
    ))

    # 4) 编号 + 邻域上下文
    elements = []
    for i, e in enumerate(raw_elements):
        e["id"] = f"e{i + 1}"
        if e["bounds"]:
            e["bounds"] = [int(v) for v in e["bounds"]]
        if e["center"]:
            e["center"] = [int(v) for v in e["center"]]
        elements.append(e)

    # 排序后统一编号并构建邻域上下文
    for i, e in enumerate(elements):
        e["id"] = f"e{i + 1}"
        e["context"] = _build_context(elements, i)

    result = {
        "available": True,
        "total": len(elements),
        "elements": elements,
    }
    if viewport:
        result["viewport"] = list(viewport)

    return result


def get_element_index(wait_sec=3):
    """获取当前页面的元素索引（build_element_index 的别名，语义更直观）。"""
    return build_element_index(wait_sec=wait_sec)


# ─── 锚点定位（T1 程序化匹配） ──────────────────────────────────────────

def locate_anchor(text: str, wait_sec: int = 3) -> dict:
    """定位锚点节点，返回基础位置信息。

    内部使用 get_current_nodes() 共享缓存，避免重复 dump + parse。

    Args:
        text: 目标文本
        wait_sec: 等待超时

    Returns:
        dict with keys: found, in_viewport, nodes_info
    """
    try:
        all_nodes = get_current_nodes(wait_sec=wait_sec)
        if all_nodes is None:
            return {"found": False, "in_viewport": False, "nodes_info": None}
        ranked = _find_best_nodes(all_nodes, text)
    except Exception as e:
        return {"found": False, "in_viewport": False, "nodes_info": None, "error": str(e)}

    if not ranked:
        return {"found": False, "in_viewport": False, "nodes_info": None}

    best_node = ranked[0][2]
    in_viewport = best_node.get("in_viewport", True)
    nodes_info = {
        "count": len(ranked),
        "match_level": ranked[0][0],
        "in_viewport": in_viewport,
        "text": best_node.get("all_text", "")[:60],
    }

    return {"found": True, "in_viewport": in_viewport, "nodes_info": nodes_info}


def locate_anchor_substring(text: str, wait_sec: int = 3) -> dict:
    """子串回退定位：找出页面中与 text 互为子串的节点。

    T1 只做 L0/L1 精确匹配，所以「- 没有更多了 -」这类带装饰符/被拆分的节点
    必定落到 AI hook —— 即使语义等价关系是确定的。本函数补这一次机器判定：
      候选文案形态唯一（去重后只有一种）→ 语义等价，可直判 pass/semantic；
      多种形态 → 语义不确定，交回 AI。

    Returns:
        {"matched": bool, "unique": bool, "texts": [候选文案],
         "node": 最佳候选节点 | None, "match_level": MATCH_SUBSTR}
    """
    try:
        all_nodes = get_current_nodes(wait_sec=wait_sec)
    except Exception:
        all_nodes = None
    empty = {"matched": False, "unique": False, "texts": [], "node": None,
             "match_level": MATCH_SUBSTR}
    if all_nodes is None:
        return empty

    candidates = find_substring_candidates(all_nodes, text)
    if not candidates:
        return empty

    nodes = [node for _level, _idx, node in candidates]
    texts = []
    for node in nodes:
        node_text = (node.get("text") or node.get("content_desc") or "").strip()
        if node_text and node_text not in texts:
            texts.append(node_text)
    if not texts:
        return empty
    return {
        "matched": True,
        "unique": len(texts) == 1,
        "texts": texts,
        "node": nodes[0],
        "match_level": MATCH_SUBSTR,
    }


def locate_anchor_gone(text: str, wait_sec: int = 3, max_retry: int = 2) -> dict:
    """检查锚点是否已从视图树消失（带重试）。

    多次采集视图树，确认目标文本是否已消失。

    Args:
        text: 目标文本
        wait_sec: 每次等待超时
        max_retry: 最大重试次数

    Returns:
        dict with keys: gone, retry_count, error
    """
    for attempt in range(max_retry + 1):
        try:
            result = locate_anchor(text, wait_sec=wait_sec)
        except Exception as e:
            return {"gone": False, "retry_count": attempt, "error": str(e)}

        if not result["found"]:
            return {"gone": True, "retry_count": attempt}

        if attempt < max_retry:
            time.sleep(2.0)
            invalidate_cache()

    return {"gone": False, "retry_count": max_retry}