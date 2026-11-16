#!/usr/bin/env python3
"""
D2C Leaf Extractor - 提取指定节点下的所有叶子节点

用法:
    python extract_leaves.py <json_file> <node_id> [--include-path] [--max-leaves N] [--collapse] [--compact]
"""

import json
import sys
import argparse
from typing import Dict, List, Optional

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import (
    build_node_index, load_json, node_name,
    should_collapse, collapsed_fields, export_marker_fields,
    compact_style,
)


def extract_leaf_detail(node: Dict, path: Optional[List[str]] = None,
                        collapse: bool = False, compact: bool = False) -> Dict:
    is_collapsed = should_collapse(node, collapse)

    detail = {
        "id": node.get("id", "unknown"),
        "name": node_name(node),
        "tag": "img" if is_collapsed else node.get("tag", "unknown"),
    }

    if not compact and path is not None:
        detail["path"] = " > ".join(path)

    if is_collapsed:
        detail.update(collapsed_fields(node))
        style = node.get("style", {})
        pos_style = {k: v for k, v in style.items() if k in ("width", "height", "left", "top")}
        if pos_style:
            detail["style"] = compact_style(style) if compact else pos_style
        return detail

    if "style" in node:
        detail["style"] = compact_style(node["style"]) if compact else node["style"]

    if not compact:
        detail.update(export_marker_fields(node))

    if "textContent" in node and node["textContent"]:
        detail["textContent"] = node["textContent"]

    if not compact and "textSegments" in node:
        detail["textSegments"] = node["textSegments"]

    if "src" in node and node["src"]:
        detail["src"] = node["src"]

    return detail


def collect_leaves(node: Dict, include_path: bool = False, current_path: Optional[List[str]] = None,
                   leaves: Optional[List[Dict]] = None, max_leaves: Optional[int] = None,
                   collapse: bool = False, compact: bool = False) -> List[Dict]:
    if leaves is None:
        leaves = []
    if current_path is None:
        current_path = []

    if max_leaves is not None and len(leaves) >= max_leaves:
        return leaves

    node_id = node.get("id", "unknown")
    path = current_path + [node_id] if include_path else None

    if should_collapse(node, collapse):
        leaves.append(extract_leaf_detail(node, path, collapse=True, compact=compact))
        return leaves

    children = node.get("children", [])
    if not children:
        leaves.append(extract_leaf_detail(node, path, collapse=collapse, compact=compact))
    else:
        for child in children:
            if max_leaves is not None and len(leaves) >= max_leaves:
                break
            collect_leaves(
                child, include_path=include_path,
                current_path=current_path + [node_id] if include_path else None,
                leaves=leaves, max_leaves=max_leaves, collapse=collapse, compact=compact,
            )

    return leaves


def main():
    parser = argparse.ArgumentParser(description="提取指定节点下的所有叶子节点")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("node_id", help="目标节点的 ID")
    parser.add_argument("--include-path", action="store_true", help="包含路径信息")
    parser.add_argument("--max-leaves", type=int, default=None, help="限制返回数量")
    parser.add_argument("--collapse", action="store_true", help="坍缩模式")
    parser.add_argument("--compact", action="store_true",
                        help="精简模式：去除 path/textSegments，压缩 style")

    args = parser.parse_args()
    data = load_json(args.json_file)
    index = build_node_index(data)

    target_node = index.get(args.node_id)
    if not target_node:
        print(f"错误: 未找到 ID 为 '{args.node_id}' 的节点", file=sys.stderr)
        sys.exit(1)

    leaves = collect_leaves(
        target_node, include_path=args.include_path,
        max_leaves=args.max_leaves, collapse=args.collapse, compact=args.compact,
    )

    output = {
        "root_id": args.node_id,
        "root_name": node_name(target_node),
        "total_leaves": len(leaves),
        "leaves": leaves,
    }
    if args.max_leaves and len(leaves) >= args.max_leaves:
        output["truncated"] = True
        if not args.compact:
            output["note"] = f"结果已截断，仅返回前 {args.max_leaves} 个叶子节点"

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
