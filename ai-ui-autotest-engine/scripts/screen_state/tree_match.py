"""节点匹配：多级匹配（mText / contentDescription / 子串）与最佳点击目标选择。"""
from screen_state.tree_parse import _center_of, is_debug_overlay


# 匹配级别（机器匹配契约，跨模块引用：locators / tap / 断言策略）
# 只做精确匹配，模糊/语义匹配一律由 AI Hook 处理。
MATCH_EXACT = 0        # 精确匹配（mText == query）
MATCH_EXACT_DESC = 1   # 精确匹配 contentDescription
MATCH_SUBSTR = 2       # 子串回退（仅用于语义等价判定，见 find_substring_candidates）

# 子串候选的最小有效重叠字符数。
# 单字符重叠不构成语义等价：expect「入离时间」与无关文案「1间」/「房间将整晚保留」
# 只共享「间」，把它当成「入离时间仍在页面上」的残留证据是误报（gone 断言因此
# 频繁落入 AI hook）。因此要求至少重叠 min(len(query), MIN_SUBSTR_OVERLAP) 个连续字符。
MIN_SUBSTR_OVERLAP = 2


def _longest_common_substring_len(a, b):
    """a 与 b 的最长公共连续子串长度（文案很短，O(len(a)*len(b)) 足够）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def _has_meaningful_overlap(query, text):
    """text 与 query 的重叠是否足以构成语义等价候选（见 MIN_SUBSTR_OVERLAP）。"""
    if not query or not text:
        return False
    return _longest_common_substring_len(query, text) >= min(len(query), MIN_SUBSTR_OVERLAP)

def _match_node(node, query):
    """对单个节点做精确匹配，返回匹配等级（越小越优先），不匹配返回 None。

    仅支持 L0/L1 精确匹配。不再进行子串/去标点容错等模糊匹配，
    这些场景由 AI Hook 通过 resolve_text_not_found / resolve_target_unresolved 等处理。
    """
    # L0: 精确匹配 mText
    if node.get("text") and node["text"] == query:
        return MATCH_EXACT
    # L1: 精确匹配 contentDescription
    if node.get("content_desc") and node["content_desc"] == query:
        return MATCH_EXACT_DESC
    return None
def _find_best_nodes(nodes, query):
    """在节点列表中搜索 query，返回按匹配优先级排序的 (level, index, node) 列表。

    仅做 L0/L1 精确匹配。模糊/语义匹配由 AI Hook 处理。
    """
    results = []
    for i, n in enumerate(nodes):
        level = _match_node(n, query)
        if level is not None:
            results.append((level, i, n))
    results.sort(key=lambda x: (x[0], x[1]))
    return results
def find_substring_candidates(nodes, query):
    """子串回退候选：query 与节点文本存在「有效重叠」（见 _has_meaningful_overlap）。

    调用方（scroll-until / 断言策略）必须自行处理多候选：
      - 候选文案形态唯一 → 语义等价，可直接使用；
      - 多种形态 → 语义不确定，交 AI 判定。
    结果按文本长度接近度排序，越接近的越优先。
    """
    if not query:
        return []
    results = []
    for i, n in enumerate(nodes):
        t = n.get("text") or ""
        cd = n.get("content_desc") or ""
        if not t and not cd:
            continue
        if _has_meaningful_overlap(query, t) or _has_meaningful_overlap(query, cd):
            results.append((MATCH_SUBSTR, i, n))
    results.sort(key=lambda x: (abs(len(x[2].get("text") or x[2].get("content_desc") or "") - len(query)), x[1]))
    return results
def _select_best_tap_target(nodes, query):
    """从匹配节点中选择最优点击目标，返回 (node, match_level) 或 None。

    选择策略：
    1. 取匹配优先级最高的一批节点（同一 level）
    2. 在这批节点中，优先选自身 clickable 且有坐标的
    3. 其次选有可点击祖先的（结构定位，非语义匹配）
    4. 最后取 DFS 序第一个有坐标的
    """
    ranked = _find_best_nodes(nodes, query)
    if not ranked:
        return None
    best_level = ranked[0][0]
    candidates = [(i, n) for lv, i, n in ranked if lv == best_level]
    # 优先级 1: 自身 clickable 且有有效坐标
    for i, n in candidates:
        if n["clickable"] and _center_of(n):
            return n, best_level
    # 优先级 2: 有可点击祖先（跳过调试控件节点，不把它当作可用祖先）
    for i, n in candidates:
        if _center_of(n) is None:
            continue
        cur = n
        while cur["parent"] is not None:
            cur = nodes[cur["parent"]]
            if cur["clickable"] and _center_of(cur) and not is_debug_overlay(cur):
                return n, best_level
    # 优先级 3: 取第一个有坐标的
    for i, n in candidates:
        if _center_of(n):
            return n, best_level
    return None
def _find_clickable_center(nodes, node):
    """从 node 出发上溯可点击祖先取中心坐标（跳过调试控件），全程无可点击节点则返回 None（不再回退到 node 自身几何中心这一不可靠坐标）。"""
    cur = node
    while cur is not None:
        if cur["clickable"] and not is_debug_overlay(cur):
            c = _center_of(cur)
            if c:
                return c
        cur = nodes[cur["parent"]] if cur["parent"] is not None else None
    return None
