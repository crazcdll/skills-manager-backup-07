#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言锚点定位（T1/T1.5 程序化匹配）。

职责边界（单一职责，勿越界）：
  本模块只回答「文本是否命中 / 是否消失」，服务断言策略（present / gone）。
  「按语义取可操作目标（含 AI 目录、候选渲染）」是采集层能力，见
  screen_state/tree_index.py —— 目标模型不在这里定义，避免 actions 反向依赖断言包。
"""

from __future__ import annotations
import time

from execution.screen.inspect_tree import (
    get_current_nodes,
    find_substring_candidates, MATCH_SUBSTR,
    _find_best_nodes, invalidate_cache,
)


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
