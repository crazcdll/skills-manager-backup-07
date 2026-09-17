"""Native 视图树能力入口（facade）。

原 `inspect_tree.py`（1014 行）已按职责拆分到同层模块：

    tree_parse.py         解析 + 几何 + 滚动裁剪 + 调试控件判定
    tree_source.py        采集 + 缓存（dump / 8s 缓存 / invalidate）
    tree_match.py         多级匹配（mText / contentDescription / 子串）+ 最佳点击目标
    tree_neighborhood.py  邻域结构树（无文案图标定位）
    tree_hit.py           坐标命中 + 遮挡规避
    tree_query.py         对外查询 API（文案/图标/输入框/滚动/文本列表）+ 探针名记录

本模块保留为**统一入口**，对外 API 不变——调用方
`from screen_state.inspect_tree import dump_inspect_tree, invalidate_cache, ...`
零改动（含历史上已被跨模块引用的私有符号 `_center_of` / `_find_best_nodes` /
`_overlapping_clickables`，此处一并再导出以避免改动既有调用点）。

分层依赖（单向）：
    tree_parse ← tree_source / tree_match / tree_neighborhood / tree_hit ← tree_query
"""
from screen_state.tree_hit import _overlapping_clickables, hit_nodes_at
from screen_state.tree_match import (
    MATCH_EXACT, MATCH_EXACT_DESC, MATCH_SUBSTR,
    _find_best_nodes,
    find_substring_candidates,
)
from screen_state.tree_neighborhood import build_neighborhood_tree
from screen_state.tree_parse import _center_of, is_debug_overlay, parse_inspect_tree
from screen_state.tree_query import (
    find_anchor_neighborhood,
    inspect_tree_find_blur_anchor,
    inspect_tree_find_by_id,
    inspect_tree_find_center,
    inspect_tree_find_scroll_target,
    inspect_tree_find_text,
    inspect_tree_has_text,
    last_hit_probe_name,
    list_text_nodes,
    native_find_center,
    native_find_scroll_target,
    native_has_text,
    native_list_texts,
)
from screen_state.tree_source import (
    dump_inspect_tree,
    get_current_nodes,
    invalidate_cache,
)

__all__ = [
    # 采集 / 缓存
    "dump_inspect_tree", "get_current_nodes", "invalidate_cache",
    # 解析 / 几何
    "parse_inspect_tree", "is_debug_overlay", "_center_of",
    # 匹配
    "MATCH_EXACT", "MATCH_EXACT_DESC", "MATCH_SUBSTR",
    "find_substring_candidates", "_find_best_nodes",
    # 邻域
    "build_neighborhood_tree",
    # 命中
    "hit_nodes_at", "_overlapping_clickables",
    # 查询 API
    "inspect_tree_find_text", "native_has_text", "inspect_tree_has_text",
    "native_find_center", "inspect_tree_find_center",
    "native_find_scroll_target", "inspect_tree_find_scroll_target",
    "inspect_tree_find_blur_anchor", "inspect_tree_find_by_id",
    "native_list_texts", "list_text_nodes", "find_anchor_neighborhood",
    "last_hit_probe_name",
]
