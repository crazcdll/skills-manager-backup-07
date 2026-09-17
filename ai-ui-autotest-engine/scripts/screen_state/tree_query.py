"""对外查询 API：文案/图标/输入框定位、滚动到目标、文本列表、探针名记录。"""
import sys
from screen_state.tree_parse import _bounds_of, _center_of, _geometry, is_debug_overlay
from screen_state.tree_source import get_current_nodes
from screen_state.tree_match import MATCH_EXACT, _find_best_nodes, _find_clickable_center, _select_best_tap_target, find_substring_candidates
from screen_state.tree_neighborhood import build_neighborhood_tree
from screen_state.tree_hit import _overlapping_clickables, _safe_center


def inspect_tree_find_text(text, wait_sec=6, max_attempts=1):
    """在视图树中查找文本，返回 {"found","count","nodes","match_level","indices","total_nodes"}。

    仅做 L0/L1 精确匹配（见 _match_node）。模糊匹配由 AI Hook 处理。
    indices 为匹配节点在 DFS 列表中的原始索引，total_nodes 为整棵树节点总数。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return {"found": False, "count": 0, "nodes": [], "match_level": None,
                "indices": [], "total_nodes": 0}
    ranked = _find_best_nodes(nodes, text)
    return {
        "found": bool(ranked),
        "count": len(ranked),
        "nodes": [n for _, _, n in ranked],
        "match_level": ranked[0][0] if ranked else None,
        "indices": [idx for _, idx, _ in ranked],
        "total_nodes": len(nodes),
    }
def native_has_text(text, wait_sec=6, max_attempts=1):
    """文本是否存在于 native 视图树中，返回 bool。"""
    return inspect_tree_find_text(text, wait_sec=wait_sec, max_attempts=max_attempts)["found"]
def inspect_tree_has_text(text, wait_sec=6, max_attempts=1):
    """文本存在性判断，依次询问 Probe 链。

    任一渲染层命中即返回 True。
    """
    global _last_hit_probe_name
    from context import get_probes
    for probe in get_probes():
        try:
            if probe.find_text(text):
                _last_hit_probe_name = probe.probe_name
                return True
        except Exception as e:
            sys.stderr.write(f"  ⚠️  {probe.probe_name} 探针查询失败: {e}\n")
    _last_hit_probe_name = None
    return False
_last_hit_probe_name = None
def last_hit_probe_name():
    """返回最近一次命中的探针名称标识，未命中返回 None。"""
    return _last_hit_probe_name
def native_find_center(text, wait_sec=6, max_attempts=1, detail=False):
    """文本 → native 视图树中可点击元素屏幕中心坐标 (cx, cy)，找不到返回 None。

    仅做 L0/L1 精确匹配。不再执行子串/去标点等模糊匹配，
    未命中时调用方应路由到 AI Hook（resolve_text_not_found / resolve_target_unresolved 等）。

    detail=True 时返回包含 center/clickable/tapped_parent/candidates/overlap/
    match_level/matched_text/unresolved/subtree 的 dict；
    detail=False 时返回 (cx, cy) 或 None。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return None if not detail else None
    result = _select_best_tap_target(nodes, text)
    if result is None:
        return None if not detail else None
    target, match_level = result
    center = _find_clickable_center(nodes, target)
    if center is None:
        if not detail:
            return None
        subtree, _hit_count = build_neighborhood_tree(nodes, target)
        # 即使不可点击，也要计算节点自有的中心和视口状态
        self_center = _center_of(target)
        out_of_viewport = not target.get("in_viewport", True) if self_center else False
        vp_offset = target.get("viewport_offset", 0) if out_of_viewport else 0
        return {
            "center": self_center,
            "clickable": False,
            "tapped_parent": False,
            "debug_adjusted": False,
            "candidates": [],
            "overlap": [],
            "match_level": match_level,
            "matched_text": target.get("all_text", ""),
            "unresolved": True,
            "unresolved_reason": "no_clickable_ancestor",
            "subtree": subtree,
            "out_of_viewport": out_of_viewport,
            "viewport_offset": vp_offset,
        }
    self_center = _center_of(target)
    tapped_parent = (self_center != center) if self_center else False

    debug_adjusted = False
    debug_hits = _overlapping_clickables(
        [n for n in nodes if is_debug_overlay(n)], center)
    if debug_hits:
        target_bounds = _bounds_of(target)
        safe = _safe_center(target_bounds, [h["bounds"] for h in debug_hits]) if target_bounds else None
        if safe:
            center = safe
            debug_adjusted = True
            debug_hits = []

    if not detail:
        return center

    candidates = []
    ranked = _find_best_nodes(nodes, text)
    best_level = ranked[0][0] if ranked else None
    for lv, _idx, n in ranked:
        if lv != best_level:
            break
        c = _find_clickable_center(nodes, n)
        if c:
            candidates.append({
                "text": n.get("all_text", ""),
                "center": c,
                "clickable": n.get("clickable", False),
            })

    # 标注目标节点的视口状态
    out_of_viewport = not target.get("in_viewport", True) if _center_of(target) else False
    vp_offset = target.get("viewport_offset", 0) if out_of_viewport else 0

    overlap = debug_hits

    return {
        "center": center,
        "clickable": target.get("clickable", False),
        "tapped_parent": tapped_parent,
        "debug_adjusted": debug_adjusted,
        "candidates": candidates,
        "overlap": overlap,
        "match_level": match_level,
        "matched_text": target.get("all_text", ""),
        "unresolved": False,
        "subtree": None,
        "out_of_viewport": out_of_viewport,
        "viewport_offset": vp_offset,
    }
def inspect_tree_find_center(text, wait_sec=6, max_attempts=1, detail=False):
    """文本 → 可点击元素屏幕中心坐标，依次询问 Probe 链。

    native 命中时返回其完整结果（含 candidates/overlap 等诊断字段）。
    """
    native = native_find_center(text, wait_sec=wait_sec,
                                max_attempts=max_attempts, detail=detail)
    if native is not None:
        if detail and isinstance(native, dict):
            native.setdefault("probe_name", "native")
        return native

    from context import get_probes
    for probe in get_probes():
        if probe.probe_name == "native":
            continue
        try:
            center = probe.find_center(text)
        except Exception as e:
            sys.stderr.write(f"  ⚠️  {probe.probe_name} 探针定位失败: {e}\n")
            continue
        if not center:
            continue
        if not detail:
            return center
        return {
            "center": center,
            "clickable": True,
            "tapped_parent": False,
            "debug_adjusted": False,
            "candidates": [{"text": text, "center": center, "clickable": True}],
            "overlap": [],
            "probe_name": probe.probe_name,
            "match_level": MATCH_EXACT,
            "matched_text": text,
            "unresolved": False,
            "subtree": None,
            "out_of_viewport": False,
            "viewport_offset": 0,
        }
    return None
def native_find_scroll_target(text, wait_sec=6, max_attempts=1, detail=False):
    """文本 → 节点自身几何中心坐标（不要求可点击），专供 scroll-until 使用。

    与 native_find_center 的区别：
      - 不要求节点可点击，不执行祖先上溯
      - 返回节点自身的几何中心 + 视口状态（in_viewport / viewport_offset）
      - 适用场景：纯展示文本（static label）的滚动定位

    detail=True 时返回 dict，包含 center/out_of_viewport/viewport_offset；
    detail=False 时返回 (cx, cy) 或 None。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return None if not detail else None
    ranked = _find_best_nodes(nodes, text)
    if not ranked:
        # 子串回退：scroll-until 锚点常为完整文案的子串/前缀，
        # 如 "薇薇新娘" ⊂ "薇薇新娘 | 魅致婚纱摄影(双井总店)"
        substring_ranked = find_substring_candidates(nodes, text)
        if not substring_ranked:
            return None if not detail else None
        # 多候选 → handoff AI 消歧
        if len(substring_ranked) > 1:
            if not detail:
                return None
            candidates_info = []
            for _lv, _idx, n in substring_ranked:
                c = _center_of(n)
                candidates_info.append({
                    "text": n.get("text", n.get("content_desc", "")),
                    "center": c,
                    "bounds": n.get("bounds"),
                    "in_viewport": n.get("in_viewport", True),
                    "viewport_offset": n.get("viewport_offset", 0),
                })
            return {
                "center": None,
                "unresolved": True,
                "unresolved_reason": "substring_ambiguous",
                "matched_text": text,
                "candidates_count": len(candidates_info),
                "candidates": candidates_info,
            }
        # 唯一候选 → 走精确匹配同流程
        target = substring_ranked[0][2]
    else:
        target = ranked[0][2]  # (level, index, node) → node
    center = _center_of(target)
    if center is None:
        if not detail:
            return None
        return {
            "center": None,
            "unresolved": True,
            "unresolved_reason": "no_coordinates",
            "matched_text": target.get("all_text", ""),
        }
    out_of_viewport = not target.get("in_viewport", True)
    vp_offset = target.get("viewport_offset", 0) if out_of_viewport else 0
    if not detail:
        return center
    return {
        "center": center,
        "clickable": target.get("clickable", False),
        "out_of_viewport": out_of_viewport,
        "viewport_offset": vp_offset,
        "matched_text": target.get("all_text", ""),
        "unresolved": False,
    }
def inspect_tree_find_scroll_target(text, wait_sec=6, max_attempts=1, detail=False):
    """文本 → 节点中心坐标，依次询问 Probe 链，专供 scroll-until 使用。

    不要求节点可点击（与 inspect_tree_find_center 的核心区别）。
    """
    native = native_find_scroll_target(text, wait_sec=wait_sec,
                                       max_attempts=max_attempts, detail=detail)
    if native is not None:
        if detail and isinstance(native, dict):
            native.setdefault("probe_name", "native")
        return native

    from context import get_probes
    for probe in get_probes():
        if probe.probe_name == "native":
            continue
        try:
            center = probe.find_center(text)
        except Exception as e:
            sys.stderr.write(f"  ⚠️  {probe.probe_name} 探针定位失败: {e}\n")
            continue
        if not center:
            continue
        if not detail:
            return center
        return {
            "center": center,
            "clickable": True,
            "out_of_viewport": False,
            "viewport_offset": 0,
            "probe_name": probe.probe_name,
            "unresolved": False,
        }
    return None
def inspect_tree_find_blur_anchor(anchor_text, wait_sec=6, max_attempts=1):
    """为输入框失焦找一个安全的点击锚点：文本匹配到 anchor_text 附近的节点，

    只在 clickable=False 的候选中选（纯展示文本，点击不会触发跳转/弹窗等
    副作用），返回节点自身坐标——不像 inspect_tree_find_center 那样沿祖先链
    上溯找可点击容器，因为失焦场景要的恰恰是"不可点击"。

    返回 {"center": (cx,cy), "text": str} 或 None（无 clickable=False 候选）。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return None
    ranked = _find_best_nodes(nodes, anchor_text)
    for _level, _idx, node in ranked:
        if node.get("clickable"):
            continue
        center = _center_of(node)
        if center:
            return {"center": center, "text": node.get("all_text") or anchor_text}
    return None
def inspect_tree_find_by_id(m_id, wait_sec=6, max_attempts=1):
    """按 resource-id（m_id）精确查找节点，返回中心坐标和详情。

    用于验证码输入框等有稳定 resource-id 但无文案的元素定位。
    返回 {"center": (cx,cy), "m_id": str, "class_name": str, "text": str | None}
    或 None（未找到该 ID 或坐标缺失）。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return None
    for n in nodes:
        if n.get("m_id") == m_id:
            center = _center_of(n)
            if center:
                return {
                    "center": center,
                    "m_id": m_id,
                    "class_name": n.get("class_name"),
                    "text": n.get("text"),
                    "clickable": n.get("clickable", False),
                }
    return None
def native_list_texts(wait_sec=6, max_attempts=1):
    """列出 native 视图树中的全部可见文本。"""
    return [it["text"] for it in list_text_nodes(wait_sec=wait_sec,
                                                 max_attempts=max_attempts)]
def list_text_nodes(keyword=None, clickable_only=False, wait_sec=6, max_attempts=1):
    """列出带文案的节点，可按关键字子串过滤。

    Returns:
        list[dict]: 每项含 text/clickable/cx/cy/w/h，按 y 坐标排序。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return []
    items = []
    for n in nodes:
        text = (n.get("all_text") or "").strip()
        if not text:
            continue
        if keyword and keyword not in text:
            continue
        clickable = n.get("clickable", False)
        if clickable_only and not clickable:
            continue
        geo = _geometry(n)
        if geo is None:
            continue
        cx, cy, w, h = geo
        items.append({"text": text[:80], "clickable": clickable,
                      "cx": cx, "cy": cy, "w": w, "h": h})
    items.sort(key=lambda it: it["cy"])
    return items
def find_anchor_neighborhood(anchor_text, wait_sec=6, max_attempts=1):
    """以锚点文案为中心，返回其周边结构的邻域 JSON 树。

    通用定位手段，服务于"目标节点自身无法自证语义、需结合周边文案上下文反推"
    的场景（无文案图标定位、输入框多候选消歧等）：节点自身信息不足以判断，
    但父容器/兄弟节点的文案足以反推业务含义，因此不做距离排序、不内部择优、
    不截断候选，直接返回锚点周边结构树交给调用方（AI）判断。树中每个
    clickable 节点自带 "tap": [cx, cy]，非骨架节点自带 "text"。

    anchor_text 命中多个节点时，每个命中位置各自返回一棵邻域树，不擅自择优。

    Returns:
        dict: {"found": bool, "matches": [{"anchor_text": str, "tree": dict, "hit_count": int}, ...]}
        anchor_text 完全找不到时 found=False，matches 为空列表。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return {"found": False, "matches": []}
    ranked = _find_best_nodes(nodes, anchor_text)
    if not ranked:
        return {"found": False, "matches": []}
    matches = []
    for _level, _idx, anchor_node in ranked:
        tree, hit_count = build_neighborhood_tree(nodes, anchor_node)
        if tree is None:
            continue
        matches.append({
            "anchor_text": anchor_node.get("all_text"),
            "tree": tree,
            "hit_count": hit_count,
        })
        return {"found": bool(matches), "matches": matches}
