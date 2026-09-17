"""坐标命中与遮挡规避：命中节点、覆盖检测、安全落点。"""
from screen_state.tree_parse import _bounds_of, _center_of, _geometry
from screen_state.tree_source import get_current_nodes


def hit_nodes_at(x, y, wait_sec=1, max_attempts=1, limit=3):
    """查询坐标 (x,y) 命中的视图树节点，按匹配精度排序返回。
    
    用于 tap 操作后验证是否命中目标，替代两处重复的验证逻辑。
    
    Returns:
        list[dict]: 命中节点列表，每项含 class/id/text/clickable/center/bounds；
                      为空列表表示未命中任何节点。
    """
    nodes = get_current_nodes(wait_sec=wait_sec)
    if nodes is None:
        return []
    tx, ty = int(x), int(y)
    hits = []
    for n in nodes:
        b = _bounds_of(n)
        if not b:
            continue
        x1, y1, x2, y2 = b
        if x1 <= tx <= x2 and y1 <= ty <= y2:
            g = _geometry(n)
            gcx, gcy = (g[0], g[1]) if g else (0, 0)
            m_text = n.get("all_text") or ""
            hits.append({
                "class": n.get("class_name", "?"),
                "id": n.get("m_id", ""),
                "text": m_text[:35],
                "clickable": n.get("clickable", False),
                "center": f"({gcx},{gcy})",
                "bounds": f"[{x1},{y1},{x2},{y2}]",
            })
    if hits:
        def _dist(h):
            try:
                parts = h["center"].strip("()").split(",")
                return abs(int(parts[0].strip()) - tx) + abs(int(parts[1].strip()) - ty)
            except (ValueError, IndexError):
                return 9999
        hits.sort(key=_dist)
    return hits[:limit]
def _overlapping_clickables(nodes, point):
    """返回 bounding box 覆盖 point 的可点击节点，按面积升序排列。"""
    px, py = point
    hits = []
    for n in nodes:
        if not n.get("clickable"):
            continue
        b = _bounds_of(n)
        if b is None:
            continue
        x1, y1, x2, y2 = b
        if x1 <= px <= x2 and y1 <= py <= y2:
            hits.append({
                "text": n.get("all_text") or "",
                "class_name": n.get("class_name", ""),
                "center": _center_of(n),
                "bounds": b,
                "area": (x2 - x1) * (y2 - y1),
            })
    hits.sort(key=lambda h: h["area"])
    return hits
def _safe_center(bounds, blockers):
    """目标 bounds 内躲开 blockers 的安全点击坐标，找不到返回 None。

    blockers 是与 bounds 相交的其他节点 bounds 列表。逐个遮挡物按四个方向
    （左/右/上/下）切出目标 bounds 中未被其覆盖的最大剩余矩形，取面积最大者，
    取其几何中心。多个遮挡物时逐个应用同一策略，缩小候选矩形。
    """
    x1, y1, x2, y2 = bounds
    cur = bounds
    for bx1, by1, bx2, by2 in blockers:
        cx1, cy1, cx2, cy2 = cur
        if bx2 <= cx1 or bx1 >= cx2 or by2 <= cy1 or by1 >= cy2:
            continue  # 与当前候选矩形不相交，跳过
        strips = []
        if bx1 > cx1:
            strips.append((cx1, cy1, bx1, cy2))
        if bx2 < cx2:
            strips.append((bx2, cy1, cx2, cy2))
        if by1 > cy1:
            strips.append((cx1, cy1, cx2, by1))
        if by2 < cy2:
            strips.append((cx1, by2, cx2, cy2))
        if not strips:
            return None
        cur = max(strips, key=lambda s: (s[2] - s[0]) * (s[3] - s[1]))
    fx1, fy1, fx2, fy2 = cur
    if fx2 <= fx1 or fy2 <= fy1:
        return None
    return (fx1 + fx2) // 2, (fy1 + fy2) // 2
