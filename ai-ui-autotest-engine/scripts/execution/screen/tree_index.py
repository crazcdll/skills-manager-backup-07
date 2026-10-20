#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可操作目标索引（Actionable Target Index）。

把视图树归一为「按语义取目标」的唯一模型，并提供统一的渲染/选取出口（禁止各处分头拼装）：

    UiNode[] ──build_targets──► ActionableTarget[]（内存，稳定 schema）
                                     │
                                     ├─ render_targets_md    → 全量 markdown（落盘给 AI，按需 read_file）
                                     ├─ render_candidates    → 聚焦候选（同进程内联进 hook 文本）
                                     ├─ render_neighborhood  → 锚点邻域（find-icon / find-input 的结构查询）
                                     ├─ resolve_anchor_clickable → 锚点行唯一可点击目标（tap --action-anchor）
                                     ├─ resolve_anchor_editable  → 锚点行输入框（input-text；识别不到转 hook）
                                     ├─ render_anchor_row        → 锚点行成员（含宽度，供「截图+结构」推断坐标）
                                     └─ render_anchor_resolution → tap 锚点 handoff 文本

载体选择准则：
  · 全貌（100+ 项，用于「是否存在 / 在哪个分区 / 是否消失」判断）→ 落 md 文件
  · 聚焦（≤ limit 项，用于「该点/该输入哪一个」）→ 内联进 hook 文本，避免 AI 多一次 read_file
  · 邻域（锚点行附近，用于「无文案图标/输入框靠周边反推」）→ 扁平候选 + 祖先链
所有出口都从同一份 targets 派生，因此目录/候选/邻域描述永不脱节。

ActionableTarget 字段：
  id            str   稳定编号 e1/e2/...（按 y 从上到下、x 从左到右排序）
  role          str   button | input | image | checkbox | toggle | scrollable | text
  text          str   展示文本（merged_text 优先，跨节点聚合）
  class_name    str   短类名（去包名前缀，保留语义，如 EditText）
  bounds        list  [x1,y1,x2,y2]
  center        list  [cx,cy]（点击坐标）
  clickable     bool
  scrollable    bool
  scroll_dir    str|None
  in_viewport   bool
  viewport_offset int  视口外偏移
  context       list  前 2 个目标 id（顺序上下文）
  parent_chain  list  祖先链（由外到内，仅收录也在目标集合中的祖先）——
                      用于表达「同一行/同一容器」的结构关系，替代专用的邻域 JSON 树
  source        str   来源渲染层（native / webview / ...），供 AI 与报告区分上下文

role 与断言 verdict 无关：role 描述「这是什么元素」，verdict 描述「结论怎么判出来的」。
"""
from __future__ import annotations

import os

from execution.screen.tree_source import get_current_nodes
from execution.screen.tree_match import _has_meaningful_overlap
from execution.screen.tree_parse import is_debug_overlay


# ─── 目标角色推导（跨平台，含 RN） ─────────────────────────────────────
# 按 class 关键词匹配（match_end=True 表示相等或后缀匹配）。
# 注意：结构性角色（输入框/可滚动容器）必须优先于 clickable 判定 ——
# 输入框通常 clickable=True，若让 clickable 优先就会把 EditText 误判成 button，
# 导致「找可编辑元素」的 profile 永远命中不到。
_ROLE_RULES = [
    # 输入框
    ("EditText", True, "input"),
    ("TextInput", True, "input"),
    ("RecceEditText", True, "input"),
    ("UITextField", True, "input"),
    ("UITextView", True, "input"),
    ("HarmonyInput", True, "input"),
    # 可滚动容器
    ("ScrollView", True, "scrollable"),
    ("RecyclerView", True, "scrollable"),
    ("ListView", True, "scrollable"),
    ("GridView", True, "scrollable"),
    ("ViewPager", True, "scrollable"),
    # 其它原生
    ("Button", True, "button"),
    ("ImageView", True, "image"),
    ("CheckBox", True, "checkbox"),
    ("Switch", True, "toggle"),
    ("ToggleButton", True, "toggle"),
    # React Native
    ("RecceTextView", True, "text"),
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
    ("UIButton", True, "button"),
    ("UIImageView", True, "image"),
    ("UISwitch", True, "toggle"),
    ("HarmonyButton", True, "button"),
    ("HarmonyText", True, "text"),
    ("HarmonyImage", True, "image"),
]

_ROLE_LABELS = {
    "input": "输入框",
    "scrollable": "可滚动",
    "button": "按钮",
    "image": "图片",
    "checkbox": "勾选",
    "toggle": "开关",
    "text": "文本",
}


# React Native 视图类统一前缀：剥掉后保留「组件路径」，如
#   com.facebook.react.views.textinput.f → textinput.f
#   com.facebook.react.views.text.j      → text.j
# 直接取最后一段会丢语义（→ "f"），导致 role 规则匹配不到 RN 的 TextInput。
_REACT_VIEWS_PREFIX = "com.facebook.react.views."


def _short_class(class_name):
    """短类名（去包名 / 内部类前缀），保留可读语义。"""
    if not class_name:
        return "?"
    if class_name.startswith(_REACT_VIEWS_PREFIX):
        return class_name[len(_REACT_VIEWS_PREFIX):]
    return class_name.rsplit(".", 1)[-1].rsplit("$", 1)[-1]


def _role_of(node):
    """从 UiNode 推导语义角色。

    优先级：**节点显式声明的 role**（非 native 渲染层如 DOM 由 tagName 直接判定，
    比按类名猜更准）> class 关键词（结构性角色优先）> scrollable > clickable > text。
    class 关键词比较**大小写无关**：native 类名大小写混排（EditText/ReactTextView），
    DOM 的 class_name 是 tag（input/button），两者需要同一套规则。
    """
    explicit = (node.get("role") or "").strip()
    if explicit:
        return explicit
    raw = node.get("class_name", "") or ""
    cls_lower = _short_class(raw).lower()
    cls_full = raw.lower()
    for keyword, match_end, role in _ROLE_RULES:
        kw = keyword.lower()
        # 后缀精确（原生 EditText / Button …）；同时按「类名含关键词」兜底 ——
        # RN 组件类常带混淆尾段（com.facebook.react.views.textinput.f），
        # 只判后缀会把输入框漏判成 button/text。
        if match_end:
            if (cls_lower == kw or cls_lower.endswith(kw)
                    or kw in cls_lower or kw in cls_full):
                return role
        elif kw in cls_lower or kw in cls_full:
            return role
    if node.get("scrollable"):
        return "scrollable"
    if node.get("clickable"):
        return "button"
    return "text"


def _is_target(node):
    """节点是否值得进入目标集合。

    保留：有文本 / 可点击 / 可滚动 / 是输入框 / 是图片。
    过滤：无文本且不可点击的纯布局容器、调试控件。
    """
    raw = node.get("class_name", "") or ""
    cls = _short_class(raw).lower()
    cls_full = raw.lower()
    # 调试浮层（Recce / MRN debug / AppMock「MOCK」角标等）不是页面内容：
    # 留在候选里会把 AI 引向「点了会弹窗/跳转」的假目标。
    # 关键词兜底 + app 描述符声明的精确前缀（如 kernel.net.utils.b$a 本身不含 debug 字样）。
    if any(k in cls or k in cls_full for k in ("debug", "overlay")):
        return False
    if is_debug_overlay(node):
        return False
    if node.get("all_text") or node.get("merged_text"):
        return True
    if node.get("clickable") or node.get("scrollable"):
        return True
    # 输入框：类名后缀（EditText）与混淆路径（textinput.f）都要认
    if any(k in cls or k in cls_full for k in ("edittext", "textinput", "input")):
        return True
    if any(k in cls or k in cls_full for k in ("imageview", "image")):
        return True
    return False


def _best_text(node):
    """最佳展示文本：merged_text（聚合子节点拆分文本，如 RN "9"+"月" → "9月"）优先。"""
    merged = (node.get("merged_text") or "").strip()
    if merged:
        return merged
    return (node.get("all_text") or "").strip()


def _get_viewport():
    """从平台获取屏幕尺寸。"""
    try:
        from shared.context import get_platform_ops as _get_ops
        return _get_ops().screen_size()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# 构建
# ═══════════════════════════════════════════════════════════════════

def build_targets(nodes=None, wait_sec=3):
    """视图树 → 可操作目标集合。

    Returns:
        dict: {"available": bool, "total": int, "viewport": [w,h]|None,
               "targets": [ActionableTarget, ...]}
    """
    if nodes is None:
        nodes = get_current_nodes(wait_sec=wait_sec)
        if nodes is None:
            return {"available": False, "total": 0, "targets": []}

    viewport = _get_viewport()

    entries = []
    for node_idx, n in enumerate(nodes):
        if not _is_target(n):
            continue
        x, y, w, h = n.get("x"), n.get("y"), n.get("w"), n.get("h")
        has_coords = x is not None and y is not None
        entries.append((node_idx, {
            "role": _role_of(n),
            "text": _best_text(n)[:100],
            "class_name": _short_class(n.get("class_name", "")),
            "source": n.get("source") or "native",
            "bounds": [x, y, x + w, y + h] if has_coords else None,
            "center": [x + (w or 0) // 2, y + (h or 0) // 2] if has_coords else None,
            "clickable": bool(n.get("clickable")),
            "scrollable": bool(n.get("scrollable")),
            "scroll_dir": n.get("scroll_dir"),
            "in_viewport": n.get("in_viewport", True),
            "viewport_offset": int(n.get("viewport_offset", 0) or 0),
        }))

    # 空间排序：y 从上到下，x 从左到右
    entries.sort(key=lambda pair: (
        pair[1]["bounds"][1] if pair[1]["bounds"] else 0,
        pair[1]["bounds"][0] if pair[1]["bounds"] else 0,
    ))

    targets = []
    idx2id = {}
    for i, (node_idx, e) in enumerate(entries):
        e["id"] = f"e{i + 1}"
        if e["bounds"]:
            e["bounds"] = [int(v) for v in e["bounds"]]
        if e["center"]:
            e["center"] = [int(v) for v in e["center"]]
        # 顺序上下文：前 2 个目标 id
        e["context"] = [targets[j]["id"] for j in range(max(0, i - 2), i)]
        targets.append(e)
        idx2id[node_idx] = e["id"]

    # 祖先链：仅收录也在目标集合中的祖先（表达「同一行/同一容器」结构关系）
    for node_idx, e in entries:
        chain, seen, p = [], set(), nodes[node_idx].get("parent")
        while p is not None and 0 <= p < len(nodes) and p not in seen:
            seen.add(p)
            if p in idx2id:
                chain.append(idx2id[p])
            p = nodes[p].get("parent")
        e["parent_chain"] = list(reversed(chain))

    result = {"available": True, "total": len(targets), "targets": targets}
    if viewport:
        result["viewport"] = list(viewport)
    return result


# ═══════════════════════════════════════════════════════════════════
# 出口 1：全量 markdown（落盘给 AI）
# ═══════════════════════════════════════════════════════════════════

def render_targets_md(targets, source=""):
    """目标集合 → AI 友好的全量 markdown 目录。

    固定按视口分区（视口内 / 下方 / 上方）+ 可点击元素清单；不裁剪任何目标，
    因为「是否存在 / 是否消失」这类判断必须看到全貌。
    """
    if not targets or not targets.get("available"):
        return ""
    items = targets.get("targets", [])
    viewport = targets.get("viewport")
    vp_top = 90
    vp_bottom = (viewport[1] - 120) if viewport else (1280 - 120)

    in_vp, below, above, clickable = [], [], [], []
    for e in items:
        cy = e["center"][1] if e.get("center") else 0
        if e["in_viewport"]:
            in_vp.append(e)
            if e["clickable"] and e.get("text"):
                clickable.append(e)
        elif cy < vp_top:
            above.append(e)
        else:
            below.append(e)

    def _role_cell(e):
        label = _ROLE_LABELS.get(e["role"], e["role"])
        if e.get("scrollable"):
            label += "(可滚动)"
        # 非 native 渲染层（如 H5 DOM）显式标注来源，供 AI 判断上下文
        if e.get("source", "native") != "native":
            label += f"({e['source']})"
        return label

    lines = [f"## 页面元素目录（共 {len(items)} 项）"]
    if source:
        lines.append(f"> source: {source}")
    if viewport:
        lines.append(f"> 视口尺寸: {viewport[0]}×{viewport[1]}，视口区域 y=[{vp_top},{vp_bottom}]")
    lines.append("")

    lines.append(f"### 📍 视口内可见（{len(in_vp)} 项）")
    lines.append("")
    lines.append("| ID | 类型 | 文案 | center | 可点击 |")
    lines.append("|----|------|------|--------|--------|")
    for e in in_vp:
        text = (e.get("text") or "")[:60].replace("|", "\\|")
        center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
        lines.append(f"| {e['id']} | {_role_cell(e)} | {text} | {center} | {'✅' if e['clickable'] else ''} |")
    lines.append("")

    if below:
        lines.append(f"### 🔽 视口下方（{len(below)} 项，距视口底部偏移）")
        lines.append("")
        lines.append("| ID | 类型 | 文案 | 偏移(↓px) | center |")
        lines.append("|----|------|------|----------|--------|")
        for e in below:
            text = (e.get("text") or "")[:60].replace("|", "\\|")
            cy = e["center"][1] if e.get("center") else 0
            center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
            lines.append(f"| {e['id']} | {_role_cell(e)} | {text} | ↓{max(0, cy - vp_bottom)} | {center} |")
        lines.append("")

    if above:
        lines.append(f"### 🔼 视口上方（{len(above)} 项，距视口顶部偏移）")
        lines.append("")
        lines.append("| ID | 类型 | 文案 | 偏移(↑px) | center |")
        lines.append("|----|------|------|----------|--------|")
        for e in above:
            text = (e.get("text") or "")[:60].replace("|", "\\|")
            cy = e["center"][1] if e.get("center") else 0
            center = f"[{e['center'][0]},{e['center'][1]}]" if e.get("center") else "-"
            lines.append(f"| {e['id']} | {_role_cell(e)} | {text} | ↑{max(0, vp_top - cy)} | {center} |")
        lines.append("")

    if clickable:
        lines.append(f"### ⚡ 可点击元素（{len(clickable)} 项）")
        lines.append("")
        lines.append("| 文案 | ID | 位置 |")
        lines.append("|------|----|------|")
        for e in clickable:
            text = (e.get("text") or "")[:50].replace("|", "\\|")
            lines.append(f"| {text} | {e['id']} | {'可见' if e['in_viewport'] else '下方'} |")
        lines.append("")

    return "\n".join(lines)


def dump_index(sid, source, nodes=None, wait_sec=3, diag_dir=None):
    """构建 + 全量落盘（AI 视图）。统一命名 `element_index_{sid}.catalog.md`。

    这是 AI 目录的**唯一写入口**：断言与动作都从这里产出，避免多份命名/互相覆盖。

    Returns:
        (targets, md_path)：md_path 为空串表示未落盘（不可用 / 无 sid / 写盘失败）。
    """
    targets = build_targets(nodes=nodes, wait_sec=wait_sec)
    if not targets.get("available") or not sid:
        return targets, ""
    if diag_dir is None:
        try:
            from shared.case_utils import active_case_diagnostics_dir
            diag_dir = active_case_diagnostics_dir()
        except Exception:
            diag_dir = None
    if not diag_dir:
        return targets, ""
    md = render_targets_md(targets, source=source)
    if not md:
        return targets, ""
    path = os.path.join(diag_dir, f"element_index_{sid}.catalog.md")
    try:
        os.makedirs(diag_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
    except Exception as e:  # noqa: BLE001 — 落盘失败不得影响流程
        print(f"  ⚠️ 元素目录落盘失败: {e}")
        return targets, ""
    return targets, path


# ═══════════════════════════════════════════════════════════════════
# 出口 2：聚焦候选（同进程内联进 hook 文本）
# ═══════════════════════════════════════════════════════════════════

_PROFILE_EMPTY_HINT = {
    # 引擎只做**字面**召回（LCS≥MIN_SUBSTR_OVERLAP）；"没有候选"≠"语义不相关"，
    # 因此措辞不得宣称"无语义重叠"，并指向元素目录交给 AI 做语义匹配。
    "substring": "（无：没有与「{anchor}」字面重叠（连续≥2字）的目标；引擎只做字面匹配，语义相近请查元素目录）",
    "editable": "（无：未识别出 role=input 的目标；页面上可能没有输入框，或 class 未匹配规则）",
    "non_clickable": "（无：页面没有可用于失焦的不可点击文本目标）",
    "clickable": "（无：页面没有可点击目标）",
    "clickable_near": "（无：目标行附近没有可点击目标）",
}

# 几何兜底阈值（像素）：仅在**拿不到「视觉行」结构**时使用 ——
#   · _row_members 的最后一级兜底（视觉行 → 结构祖先 → 本阈值）；
#   · render_candidates 的 clickable_near 在无锚点文案（只有 anchor_y）时按它粗筛。
# 主判据是「同一视觉行」（bounds 纵向重叠）；固定像素带会把相邻字段卷进来。
_NEAR_Y_RANGE = 150


def _candidate_line(index, e, tag=""):
    flag = "✅" if e.get("clickable") else "  "
    text = (e.get("text") or "").strip()
    label = f"「{text[:80]}」" if text else f"<无文案 {e.get('class_name') or '?'}>"
    src = e.get("source", "native")
    suffix = "" if src == "native" else f"[{src}]"
    center = e.get("center")
    pos = f" @ center=({center[0]},{center[1]}) tap=({center[0]},{center[1]})" if center else ""
    prefix = f"【{tag}】" if tag else ""
    return f"   [{index}] {flag}{prefix}{label}{suffix}{pos}"


def _covered_by_clickable(entry, items):
    """落点是否被某个可点击目标覆盖 —— 「失焦必须落在惰性区域」的几何判据。

    与 `tree_hit._overlapping_clickables`（原始节点版）同口径：纯文本常嵌在整行按钮里，
    点它的坐标会命中覆盖在上面的可点击容器 → 触发跳转/弹窗（实测点「预计到店」文本的
    坐标，打开了「预计到店」时间选择弹窗）。候选清单必须先剔除这类目标，否则 AI 从清单
    里二次选中的仍是引擎（inspect_tree_find_blur_anchor）必然拒绝的候选 → 空转。
    """
    center = entry.get("center")
    if not center:
        return True   # 无坐标 → 不能作为落点
    cx, cy = center
    for other in items:
        if other is entry or not other.get("clickable"):
            continue
        b = other.get("bounds")
        if not b:
            continue
        x1, y1, x2, y2 = b
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return True
    return False


def render_candidates(targets, profile, anchor="", anchor_y=None, limit=10):
    """聚焦候选 → 可直接内联进 hook 文本的字符串。

    profile:
      substring      与 anchor 互为子串 / 有效重叠的目标（tap/scroll 的文案口径差异）
      editable       role=input 的目标；命中 0 条时输出文本目标清单，避免 AI 失去线索
      clickable      可点击目标
      clickable_near 锚点行（同一视觉行）的可点击目标；无锚点文案时按 anchor_y ± _NEAR_Y_RANGE 粗筛
      non_clickable  有文案但不可点击的目标（blur 失焦锚点）
    """
    items = (targets or {}).get("targets") or []
    empty_hint = _PROFILE_EMPTY_HINT.get(profile, "（无候选）").format(anchor=anchor)

    if profile == "substring":
        if not anchor:
            return empty_hint
        picked = [
            e for e in items
            if e.get("text") and _has_meaningful_overlap(anchor, e["text"])
        ]
        # 可点击优先，其次文案长度最接近（越接近越可能是完整目标）
        picked.sort(key=lambda e: (not e["clickable"], abs(len(e["text"]) - len(anchor))))
    elif profile == "editable":
        picked = [e for e in items if e["role"] == "input"]
        if not picked:
            # 兜底：role 未识别时不静默，给出页面文本目标清单供人工判断
            picked = sorted(
                [e for e in items if e.get("text")],
                key=lambda e: e["center"][1] if e.get("center") else 0,
            )[:limit]
            lines = [empty_hint, "   ↳ 以下是页面上的文本目标（按 y 排序，供人工判断哪个是输入框）："]
            lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
                      for i, e in enumerate(picked, 1)]
            return "\n".join(lines)
    elif profile == "clickable":
        picked = [e for e in items if e["clickable"]]
    elif profile == "clickable_near":
        anchor_target = find_anchor(targets, anchor) if anchor else None
        if anchor_target is not None:
            # 与 tap / input 同源：同一视觉行
            picked = [e for e in _row_members(items, anchor_target) if e["clickable"]]
        elif anchor_y is None:
            picked = [e for e in items if e["clickable"]]
        else:
            picked = [
                e for e in items
                if e["clickable"] and e.get("center")
                and abs(e["center"][1] - anchor_y) <= _NEAR_Y_RANGE
            ]
    elif profile == "non_clickable":
        # blur 失焦锚点：不可点击 **且** 落点未被可点击容器覆盖（惰性区域）。
        # 与 inspect_tree_find_blur_anchor 的落点校验同口径 —— 否则清单会给出引擎必然拒绝的
        # 候选，AI 反复选中同一个「藏在按钮行里的文本」而空转。
        # 仅保留「当前可见」的候选：视口外的点不到（点了也不会生效），排除后清单只
        # 呈现输入框附近的真实惰性文本，不再混入页首/页尾与浮层噪声。（浮层在 _is_target 已剔除）
        picked = [e for e in items
                  if not e["clickable"] and e.get("text")
                  and e.get("in_viewport", True)
                  and not _covered_by_clickable(e, items)]
    else:
        return empty_hint

    if not picked:
        return empty_hint
    total = len(picked)
    picked = picked[:limit]
    lines = [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], ""))
             for i, e in enumerate(picked, 1)]
    if total > len(picked):
        lines.append(f"   （仅列前 {len(picked)} 条；完整目录见 element_index_<sid>.catalog.md）")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 出口 3：锚点邻域（find-icon / find-input 的结构查询）
# ═══════════════════════════════════════════════════════════════════

def find_anchor(targets, anchor_text):
    """在目标集合中定位锚点：精确文案优先，其次有效重叠；未命中返回 None。"""
    items = (targets or {}).get("targets") or []
    if not items or not anchor_text:
        return None
    exact = next((e for e in items if e.get("text") and e["text"] == anchor_text), None)
    if exact is not None:
        return exact
    return next((e for e in items
                 if e.get("text") and _has_meaningful_overlap(anchor_text, e["text"])), None)


def render_neighborhood(targets, anchor_text, profile="clickable",
                        y_range=_NEAR_Y_RANGE, limit=12):
    """锚点周边结构（扁平候选 + 祖先链）——替代专用的邻域 JSON 树。

    适用「目标节点自身无法自证语义，需结合周边文案上下文反推」：
    find-icon（无文案图标）与 find-input（输入框）都靠它。结构关系用 parent_chain
    表达（同一行/同一容器），而不是另一套嵌套树结构。

    profile:
      clickable  列锚点行（同一视觉行）可点击目标（找无文案图标 / 整行容器）
      editable   列 role=input 目标（找输入框）
    """
    items = (targets or {}).get("targets") or []
    if not items:
        return "   （目标索引不可用）"

    anchor = find_anchor(targets, anchor_text)

    lines = []
    if anchor is None:
        lines.append(f"   （未在目标集合中命中锚点「{anchor_text}」；以下为页面可点击目标，供人工判断）")
        picked = [e for e in items if e["clickable"]][:limit]
        lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
                  for i, e in enumerate(picked, 1)]
        return "\n".join(lines)

    chain = anchor.get("parent_chain") or []
    chain_desc = " → ".join(chain) if chain else "（无目标级祖先）"
    lines.append(f"   锚点「{anchor['text']}」（{anchor['id']}，"
                 f"{_ROLE_LABELS.get(anchor['role'], anchor['role'])}）祖先链: {chain_desc}")

    row = _row_members(items, anchor, y_range)
    if profile == "editable":
        picked = [e for e in row if e["role"] == "input"]
        if not picked:
            # role 未识别：页面输入框可能不是原生 EditText（如 MRN 的字段需先点击
            # 才出现输入框，或渲染为容器/按钮）。此时退回「锚点行的文本 / 可点击目标」，
            # 让 AI 有线索可判断；只回一个锚点等于什么都没给（与 render_candidates 同口径）。
            picked = [e for e in row if e.get("text") or e["clickable"]]
    else:
        picked = [e for e in row if e["clickable"]]
    # 锚点自身也列出（若非候选），便于建立「文案 → 控件」的对应
    if anchor["id"] not in {e["id"] for e in picked}:
        picked = [anchor] + picked

    if not picked:
        lines.append("   锚点行内无匹配目标")
        return "\n".join(lines)

    lines.append(f"   锚点行候选（同一视觉行，✅=可点击）：")
    lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
              for i, e in enumerate(picked[:limit], 1)]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 出口 4：锚点行唯一可点击目标（tap --action-anchor 的确定性选取）
# ═══════════════════════════════════════════════════════════════════
#
# 「点击无文案图标」的唯一确定性表达：给出图标**所在行**的可点击目标。
# 与断言侧 T1.5「形态唯一 → 语义等价」同一判据 —— 形态唯一时结论确定，
# 直接点击；多形态 / 无形态时不擅自择优，返回候选交 AI 消歧（不产生假结论）。
#
# 为什么不引入方位/序号：行内几何属于组件语义（会渗进 Flow 与契约），且按几何择优
# 点错是静默的；「唯一才自动」覆盖结构可判定的一类，同类多图标行的语义判定走
# 既有的视觉通道（读图 + 断言），不在此编码组件语义。
# ───────────────────────────────────────────────────────────────────

def _dedup_by_center(items):
    """目标按 center 去重（同一图标常由按钮 + 图片两个节点表达）。"""
    seen, unique = set(), []
    for e in items:
        key = tuple(e.get("center") or [])
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def resolve_anchor_clickable(targets, anchor_text, y_range=_NEAR_Y_RANGE):
    """锚点行可点击目标解析 —— `tap --action-anchor` 的**唯一选取实现**。

    语义（与 T1.5「形态唯一才自动」同口径）：
      · 锚点行内可点击目标**恰好 1 个** → `picked` 返回该目标（可直接点击）；
      · 0 个 / ≥2 个 / 锚点未命中 → `picked` 为 None，`candidates` 交 AI 消歧。

    「行」判定与 input-text 的 resolve_anchor_editable **同源**（_row_members）：
    优先「同一视觉行」（bounds 纵向重叠），再退化为结构（共同祖先）/像素带。
    引擎判定所用的行，与展示给 AI 的候选行必须一致，否则会出现
    「引擎自动点了 A，候选清单里却是 B」的脱节（选取与渲染同源）。

    Returns:
        dict: {
            found       bool           锚点是否命中目标集合
            anchor      dict | None    锚点目标
            y_range     int            几何兜底行带（px；仅当无「视觉行」结构时使用）
            candidates  list           锚点行内可点击目标（去重、按 y 排序）
            picked      dict | None    形态唯一时的唯一目标，否则 None
        }
    """
    result = {"found": False, "anchor": None, "y_range": y_range,
              "candidates": [], "picked": None}
    items = (targets or {}).get("targets") or []
    if not items or not anchor_text:
        return result
    anchor = find_anchor(targets, anchor_text)
    if anchor is None:
        return result
    result["found"] = True
    result["anchor"] = anchor

    picked = _dedup_by_center(
        [e for e in _row_members(items, anchor, y_range) if e["clickable"]]
    )
    result["candidates"] = picked
    if len(picked) == 1:
        result["picked"] = picked[0]
    return result


# ═══════════════════════════════════════════════════════════════════
# 出口 5：锚点 → 输入框（input-text 的确定性选取）
# ═══════════════════════════════════════════════════════════════════
#
# Flow 只能给「输入框附近的锚点」或「一句语义描述」，真正的输入框要由引擎在
# 锚点所在**行/容器**内自己找出来（与 resolve_anchor_clickable 同源同口径）：
#   · 行内 role=input 恰好 1 个 → picked，可直接输入；
#   · 0 个 / ≥2 个 → 不擅自择优（盲输入会落到错误元素），转专用 hook 交 AI：
#       - ≥2：AI 从同行可编辑候选中按上下文选定；
#       - 0 ：字段可能是「需先点击才出现输入框的容器」或「选择器按钮」，
#             退化给锚点行的文本/可点击目标，由 AI 读图判定字段形态。
# 「行」判定统一走 _row_members：**同一视觉行**（bounds 纵向重叠）→ 结构祖先 → 像素带。
# 固定像素带会把相邻行一起卷进来，使「唯一」几乎永不成立（历史缺陷）。
# resolve_anchor_clickable / render_neighborhood / render_candidates(clickable_near) 同源。
# ═══════════════════════════════════════════════════════════════════

_ROW_Y_TOL = 12  # 同一「行」允许的纵向偏差（px）


def _y_overlap(a_bounds, b_bounds, tol=_ROW_Y_TOL):
    """两个 bounds 的纵向是否重叠（同行判定）。"""
    if not a_bounds or not b_bounds:
        return False
    return min(a_bounds[3], b_bounds[3]) + tol >= max(a_bounds[1], b_bounds[1])


def _row_members(items, anchor, y_range=_NEAR_Y_RANGE):
    """锚点所在「行」的成员。

    行判定优先级：
      1) **同一视觉行**：与锚点 bounds 纵向重叠（tol 内）——表单字段行的主判据；
      2) 结构兜底：与锚点共享目标级祖先（parent_chain 交集）；
      3) 几何兜底：|cy-锚点cy| ≤ y_range。

    只用结构会把整个表单容器当成「一行」（行容器通常不可点击、不在目标集合里）；
    只用固定像素带又会把相邻字段卷进来。因此以「视觉行」为主判据。
    """
    def _b(e):
        return e.get("bounds")

    line = [e for e in items if e.get("center") and _y_overlap(_b(e), _b(anchor))]
    if line:
        return line
    anchor_chain = set(anchor.get("parent_chain") or [])
    if anchor_chain:
        structural = [e for e in items if e.get("center")
                      and (anchor_chain & set(e.get("parent_chain") or []))]
        if structural:
            return structural
    ay = anchor["center"][1] if anchor.get("center") else None
    if ay is None:
        return []
    return [e for e in items if e.get("center")
            and abs(e["center"][1] - ay) <= y_range]


def _row_width(e):
    b = e.get("bounds") or [0, 0, 0, 0]
    return max(0, int(b[2]) - int(b[0]))


def resolve_anchor_editable(targets, anchor_text, y_range=_NEAR_Y_RANGE):
    """锚点 → 输入框解析 —— `input-text` 的**唯一选取实现**。

    Returns:
        dict: {
            found       bool           锚点是否命中目标集合（精确优先，其次语义重叠）
            anchor      dict | None    锚点目标
            y_range     int            几何兜底行带（px）
            candidates  list           锚点行内的可编辑（role=input）目标
            picked      dict | None    形态唯一时的输入框，否则 None
            guess       list           0/多候选时「疑似输入区域」候选（同行成员按宽度降序）
            fallback    list          同行内的「文本/可点击」目标（供 AI 判字段形态）
        }

    `guess` 是「识别不到输入框」时的**结构推断线索**：同行内越宽、越靠右的成员通常是
    输入区域，配合截图即可定坐标（见 render_anchor_row）。仅为线索，**不自动输入**。
    """
    result = {"found": False, "anchor": None, "y_range": y_range,
              "candidates": [], "picked": None, "guess": [], "fallback": []}
    items = (targets or {}).get("targets") or []
    if not items or not anchor_text:
        return result
    anchor = find_anchor(targets, anchor_text)
    if anchor is None:
        return result
    result["found"] = True
    result["anchor"] = anchor

    row = _row_members(items, anchor, y_range)
    candidates = _dedup_by_center([e for e in row if e["role"] == "input"])
    result["candidates"] = candidates
    if len(candidates) == 1:
        result["picked"] = candidates[0]
        return result

    # 0 个 / ≥2 个：给 AI 结构化线索（宽度降序 = 越宽越像输入区域）+ 同行文本/可点击
    result["guess"] = _dedup_by_center(sorted(row, key=_row_width, reverse=True))[:10]
    result["fallback"] = _dedup_by_center(
        [e for e in row if e.get("text") or e["clickable"]]
    )
    return result


def render_anchor_row(targets, anchor_text, y_range=_NEAR_Y_RANGE, limit=10):
    """渲染锚点行/容器成员（含宽度，按宽度降序）——「截图 + 结构」推断输入框坐标的线索。

    识别不到 role=input 时，AI 需要「锚点行里哪块区域最像输入框」：
    同行内越宽、越靠右的成员通常是输入区域；结合截图目测即可定坐标，
    再用 input-text 的**坐标形态**回写输入（不要用坐标点击代替输入）。
    """
    items = (targets or {}).get("targets") or []
    if not items or not anchor_text:
        return "   （目标索引不可用）"
    anchor = find_anchor(targets, anchor_text)
    if anchor is None:
        lines = [f"   （未命中锚点「{anchor_text}」；以下为页面可点击目标）"]
        lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
                  for i, e in enumerate([x for x in items if x["clickable"]][:limit], 1)]
        return "\n".join(lines)
    row = _dedup_by_center(sorted(_row_members(items, anchor, y_range),
                                  key=_row_width, reverse=True))
    lines = [f"   锚点「{anchor.get('text') or anchor.get('id')}」行成员"
             f"（按宽度降序，宽≈输入区域；✅=可点击，坐标为设备绝对坐标）："]
    for i, e in enumerate(row[:limit], 1):
        lines.append(_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
                     + f" width={_row_width(e)}")
    return "\n".join(lines)


def render_anchor_resolution(resolution, targets=None, limit=10):
    """渲染锚点行解析结果（handoff 文本），与 resolve_anchor_clickable 同源。

    锚点未命中时退回「页面可点击目标」清单（不静默给空），
    让 AI 至少能据此完成坐标点击或换锚点，而不是拿到一句空话。
    """
    lines = []
    if not resolution.get("found"):
        lines.append("   （未在目标集合中命中锚点；以下为页面可点击目标，供人工判断）")
        picked = _dedup_by_center([e for e in ((targets or {}).get("targets") or [])
                                   if e.get("clickable")])[:limit]
        lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
                  for i, e in enumerate(picked, 1)]
        return "\n".join(lines)

    anchor = resolution["anchor"]
    lines.append(f"   锚点「{anchor['text'] or ('<无文案 ' + (anchor.get('class_name') or '?') + '>')}」"
                 f"（{anchor['id']}，{_ROLE_LABELS.get(anchor['role'], anchor['role'])}）")

    cands = resolution.get("candidates") or []
    if not cands:
        lines.append("   （锚点行没有可点击目标；请读截图确认页面状态，"
                     "或用 find-icon --anchor 复核）")
        return "\n".join(lines)

    lines.append(f"   锚点行可点击目标（同一视觉行，✅=可点击；坐标可直接 tap）：")
    lines += [_candidate_line(i, e, tag=_ROLE_LABELS.get(e["role"], e["role"]))
              for i, e in enumerate(cands[:limit], 1)]
    if len(cands) > limit:
        lines.append(f"   （仅列前 {limit} 条）")
    return "\n".join(lines)
