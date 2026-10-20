"""节点匹配：多级匹配（mText / contentDescription / 子串）与最佳点击目标选择。"""
from execution.screen.tree_parse import _bounds_of, _center_of, is_debug_overlay


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
    """【召回口径】text 与 query 的重叠是否足以构成候选（给 AI 看的线索）。

    宽松：LCS ≥ min(len(query), MIN_SUBSTR_OVERLAP)。仅用于**展示/召回**
    （render_candidates / render_neighborhood / find_anchor），让 AI 拿到更多线索。
    判定（断言 pass/semantic、gone 残留、scroll 定位）必须用 _is_containment ——
    见下方说明。
    """
    if not query or not text:
        return False
    return _longest_common_substring_len(query, text) >= min(len(query), MIN_SUBSTR_OVERLAP)


def _is_containment(query, text):
    """【判定口径】互为包含**且重叠足够长**时，才认定「语义等价 / 仍有残留」。

    两个必要条件（缺一不可）：
      1. 互为包含（`query in text` 或 `text in query`）—— 排除"共享无关字符"的误判：
         · 「房型设施详情」vs「房型详情」→ 被判"仍有残留" → gone 假 PENDING；
         · 「满30减10」vs「满30减8」→ 被判"语义等价" → present 假 pass（更危险）。
      2. 完全相等，或被包含方长度 ≥ MIN_SUBSTR_OVERLAP —— 排除**单字符**节点被当作残留。
         实测（本 Skill 真实运行）：expect「入离时间」与页面独立节点「间」互为包含，
         若只判包含关系，会把无关单字当作残留 → gone 断言再次落入假 PENDING。
         保护"重叠足够长"与"互为包含"是**互补**的，缺一都会有误报。

    真阳性（如 expect「没有更多了」/ 页面「- 没有更多了 -」、RN 跨节点聚合文本、
    expect「9月28日」/ 页面「9月28日周一」）都能被覆盖，因此无需依赖 LCS 阈值。

    判定与召回分离：展示/召回用 _has_meaningful_overlap（宽松），判定用本函数（严格）。
    """
    if not query or not text:
        return False
    if query == text:
        return True
    if query in text or text in query:
        return min(len(query), len(text)) >= MIN_SUBSTR_OVERLAP
    return False

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
    """子串回退候选：query 与节点文本**互为包含**（见 _is_containment）。

    这是**判定口径**（不是召回）：仅当二者互为包含时才构成「语义等价 / 仍有残留」
    的候选；共享无关字符（「房型详情」vs「房型设施详情」）不算，必须交 AI。
    调用方（scroll-until / 断言策略 / tap 唯一子串兜底）必须自行处理多候选：
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
        if _is_containment(query, t) or _is_containment(query, cd):
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
def _point_in_bounds(point, node):
    """点 (cx, cy) 是否落在节点边界内（含边界）；缺几何信息返回 False。"""
    b = _bounds_of(node)
    if not b or not point:
        return False
    x1, y1, x2, y2 = b
    return x1 <= point[0] <= x2 and y1 <= point[1] <= y2


def _find_clickable_center(nodes, node):
    """从 node 出发上溯可点击祖先取**点击坐标**（跳过调试控件），全程无可点击节点则返回 None。

    取点规则（唯一实现，供 tap-text / find-center 共用）：
      · 命中节点**自身几何中心落在**该可点击祖先边界内 → 用**节点中心**：
        节点中心就是可点击区域内的真实文本位置，触摸事件会冒泡给可点击祖先；
      · 否则 → 回退**可点击祖先中心**。

    为什么不能一律取祖先中心：可点击祖先常是**远大于文本**的容器（典型：通栏横幅 +
    右侧按钮），祖先中心会落在容器空白处 → 点击落空。实测：美团首页底部登录横幅，
    「去登录」按钮在右侧 (1101,2377)，而祖先（通栏）中心 (628,2378) 相距 ~470px，
    导致点击无效、无法进入登录页。
    """
    node_center = _center_of(node)
    cur = node
    while cur is not None:
        if cur["clickable"] and not is_debug_overlay(cur):
            c = _center_of(cur)
            if c:
                if node_center and _point_in_bounds(node_center, cur):
                    return node_center
                return c
        cur = nodes[cur["parent"]] if cur["parent"] is not None else None
    return None
