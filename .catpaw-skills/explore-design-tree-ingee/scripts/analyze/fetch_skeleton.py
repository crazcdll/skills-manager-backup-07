#!/usr/bin/env python3
"""
D2C Skeleton Fetcher - 获取设计稿的轻量级骨架树

用法:
    python fetch_skeleton.py <json_file> [--max-depth N] [--root-id ID] [--collapse] [--compact]
"""

import json
import argparse
from typing import Dict, Optional

import sys
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import (
    build_node_index, load_json, node_name, precompute_hints,
    should_collapse, collapsed_fields, semantic_badges,
    compact_style,
)


def extract_skeleton(node: Dict, current_depth: int, max_depth: int,
                     summary_cache: Optional[Dict[int, Dict]] = None,
                     collapse: bool = False, compact: bool = False) -> Dict:
    children = node.get("children", [])
    is_collapsed = should_collapse(node, collapse)

    skeleton = {
        "id": node.get("id", "unknown"),
        "name": node_name(node),
        "type": "img" if is_collapsed else node.get("tag", "unknown"),
    }

    if is_collapsed:
        skeleton.update(collapsed_fields(node))
        if not compact and summary_cache is not None:
            skeleton["summary"] = {"exported": True}
        return skeleton

    if not compact and summary_cache is not None:
        summary = summary_cache.get(id(node))
        if summary:
            skeleton["summary"] = {k: v for k, v in summary.items()}

    if not compact:
        badges = semantic_badges(node)
        if badges:
            skeleton["semantic"] = {"badges": badges}

    if current_depth < max_depth and children:
        skeleton["children"] = [
            extract_skeleton(child, current_depth + 1, max_depth, summary_cache, collapse, compact)
            for child in children
        ]
    elif children:
        if not compact:
            skeleton["has_more"] = True

    if not compact:
        skeleton["children_count"] = len(children)

    # Compact: strip verbose width/height decoration from collapsed nodes
    if compact and is_collapsed:
        style = node.get("style", {})
        cs = compact_style(style)
        if cs:
            skeleton["style"] = cs

    return skeleton


def main():
    parser = argparse.ArgumentParser(description="获取设计稿的轻量级骨架树")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("--max-depth", type=int, default=3, help="限制返回的树深度 (默认: 3)")
    parser.add_argument("--root-id", type=str, default=None, help="指定某个节点 ID 作为根节点开始")
    parser.add_argument("--no-summary", action="store_true", help="禁用 summary 字段")
    parser.add_argument("--no-hint", action="store_true", help="兼容旧参数，等同于 --no-summary")
    parser.add_argument("--collapse", action="store_true", help="坍缩模式：有 _exportSrc 的节点显示为 img 叶子")
    parser.add_argument("--compact", action="store_true", help="精简模式：去除 children_count/has_more/summary/semantic.badges")

    args = parser.parse_args()
    data = load_json(args.json_file)

    root_node = data
    if args.root_id:
        index = build_node_index(data)
        root_node = index.get(args.root_id)
        if not root_node:
            print(f"错误: 未找到 ID 为 '{args.root_id}' 的节点", file=sys.stderr)
            sys.exit(1)

    summary_cache = None
    if not args.no_summary and not args.no_hint and not args.compact:
        summary_cache = precompute_hints(root_node)

    skeleton = extract_skeleton(
        root_node, current_depth=1, max_depth=args.max_depth,
        summary_cache=summary_cache, collapse=args.collapse, compact=args.compact,
    )
    print(json.dumps(skeleton, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
