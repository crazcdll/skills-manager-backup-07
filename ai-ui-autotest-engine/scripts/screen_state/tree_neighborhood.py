"""邻域结构树：围绕目标的上下文档 JSON，供无文案图标定位。"""
from screen_state.tree_parse import _bounds_of, _center_of, is_debug_overlay


_NEIGHBORHOOD_Y_RANGE = 150  # 邻域纵向半径（像素）：与目标 y 中心距离在此范围内的节点算"邻近"
def _short_class_name(class_name):
    """类名只取最后一段（去掉包名前缀），减少输出噪音。"""
    if not class_name:
        return "?"
    return class_name.rsplit(".", 1)[-1].rsplit("$", 1)[-1]
def _is_meaningful(node):
    """节点是否值得单独展示：有文本或可点击（纯布局壳节点二者都不满足）。"""
    return bool(node.get("all_text")) or bool(node.get("clickable"))
def _neighborhood_indices(nodes, target, y_range=_NEIGHBORHOOD_Y_RANGE):
    """找与 target 纵向邻近的"有意义"节点索引集合（含 target 自身）。

    只用 y 中心距离筛选（不叠加 x 轴限制）：同一行内横向排列的元素 y 坐标
    本来就接近，单一 y 阈值已能覆盖横向同排场景（已用真实页面数据验证），
    避免引入第二个阈值参数增加调参负担。
    """
    tb = _bounds_of(target)
    if tb is None:
        return set()
    tcy = (tb[1] + tb[3]) // 2
    keep = set()
    for i, n in enumerate(nodes):
        if n is target:
            keep.add(i)
            continue
        if not _is_meaningful(n) or is_debug_overlay(n):
            continue
        b = _bounds_of(n)
        if b is None:
            continue
        ncy = (b[1] + b[3]) // 2
        if abs(ncy - tcy) <= y_range:
            keep.add(i)
    return keep
def _node_to_json(node, is_hit):
    """节点自身信息 → dict。is_hit=False（骨架占位节点）时只标记类名，不带业务字段。"""
    if not is_hit:
        return {"class": _short_class_name(node.get("class_name")) + "(骨架)"}
    obj = {"class": _short_class_name(node.get("class_name"))}
    text = node.get("all_text")
    if text:
        obj["text"] = text[:40]
    if node.get("clickable"):
        obj["clickable"] = True
        c = _center_of(node)
        if c:
            obj["tap"] = list(c)
    b = _bounds_of(node)
    if b:
        obj["bounds"] = list(b)
    return obj
def _build_neighborhood_json(nodes, idx, keep):
    """递归构造以 idx 为根的邻域 JSON 树，剪掉不含任何命中节点的分支。

    命中节点（idx in keep）保留完整字段；非命中节点仅在其子树内有命中节点
    时才作为骨架保留（用于连接结构），子树全无命中时整体返回 None（剪枝）。
    非命中的单子节点骨架自动折叠（直接返回子节点结果），避免无意义的
    单层嵌套膨胀输出。
    """
    node = nodes[idx]
    children = []
    for ci in node.get("children_idx", []):
        child = _build_neighborhood_json(nodes, ci, keep)
        if child is not None:
            children.append(child)

    is_hit = idx in keep
    if not is_hit and not children:
        return None
    if not is_hit and len(children) == 1:
        return children[0]

    obj = _node_to_json(node, is_hit)
    if children:
        obj["children"] = children
    return obj
def build_neighborhood_tree(nodes, target, y_range=_NEIGHBORHOOD_Y_RANGE):
    """以 target 为锚点构造周边结构的邻域 JSON 树（见模块顶部策略说明）。

    返回 (tree_dict, hit_count)：tree_dict 从整棵树根节点（DFS 索引 0）开始
    构造，只包含命中邻域的节点及连接它们的必要骨架；hit_count 为命中的
    "有意义"节点数，供调用方判断结果是否过于稀疏/密集从而调整 y_range。
    target 无合法 bounds 时返回 (None, 0)。
    """
    if _bounds_of(target) is None or not nodes:
        return None, 0
    keep = _neighborhood_indices(nodes, target, y_range=y_range)
    tree = _build_neighborhood_json(nodes, 0, keep)
    return tree, len(keep)
