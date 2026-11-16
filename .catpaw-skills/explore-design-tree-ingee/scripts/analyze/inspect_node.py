#!/usr/bin/env python3
"""
D2C Node Inspector - 获取指定节点的详细属性

用法:
    python inspect_node.py <json_file> <node_id> [--no-children] [--max-depth N] [--collapse] [--compact]
"""

import json
import sys
import argparse
from typing import Dict

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import (
    build_node_index, build_parent_index, load_json, node_name,
    should_collapse, collapsed_fields, export_marker_fields,
    should_collapse_deco, semantic_payload,
    compact_style,
)


def extract_node_detail(node: Dict, current_depth: int = 0, max_depth: int = 2,
                        collapse: bool = False, expand_deco: bool = False,
                        compact: bool = False) -> Dict:
    is_collapsed = should_collapse(node, collapse)
    semantic = semantic_payload(node)

    detail = {
        "id": node.get("id", "unknown"),
        "name": node_name(node),
        "tag": "img" if is_collapsed else node.get("tag", "unknown"),
    }

    if not compact and semantic:
        detail["semantic"] = semantic

    if is_collapsed:
        detail.update(collapsed_fields(node))
        style = node.get("style", {})
        pos_style = {k: v for k, v in style.items() if k in ("width", "height", "left", "top")}
        if pos_style:
            detail["style"] = compact_style(style) if compact else pos_style
        if not compact:
            children = node.get("children", [])
            if children:
                detail["children_count"] = len(children)
        return detail

    is_deco_folded = should_collapse_deco(node) and not expand_deco
    if is_deco_folded:
        if "style" in node:
            detail["style"] = compact_style(node["style"]) if compact else node["style"]
        if not compact:
            children = node.get("children", [])
            if children:
                detail["children_count"] = len(children)
                detail["_deco_folded"] = True
        return detail

    if "style" in node:
        detail["style"] = compact_style(node["style"]) if compact else node["style"]

    if "textContent" in node and node["textContent"]:
        detail["textContent"] = node["textContent"]

    if not compact and "textSegments" in node:
        detail["textSegments"] = node["textSegments"]

    if "src" in node and node["src"]:
        detail["src"] = node["src"]

    if not compact:
        extra_assets = export_marker_fields(node)
        if extra_assets and "assets" not in detail:
            detail.update(extra_assets)

    children = node.get("children", [])
    if children:
        if current_depth < max_depth:
            detail["children"] = [
                extract_node_detail(child, current_depth + 1, max_depth, collapse, expand_deco, compact)
                for child in children
            ]
        else:
            if not compact:
                detail["children_count"] = len(children)
                detail["has_more"] = True

    return detail


def main():
    parser = argparse.ArgumentParser(description="获取指定节点的详细属性")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("node_id", help="目标节点的 ID")
    parser.add_argument("--no-children", action="store_true", help="不包含子节点详细信息")
    parser.add_argument("--max-depth", type=int, default=2, help="限制返回的树深度 (默认: 2)")
    parser.add_argument("--collapse", action="store_true", help="坍缩模式")
    parser.add_argument("--expand-deco", action="store_true",
                        help="展开 deco 节点的 children（默认折叠）")
    parser.add_argument("--with-parent", action="store_true",
                        help="附加父节点布局信息和兄弟节点摘要")
    parser.add_argument("--compact", action="store_true",
                        help="精简模式：去除 children_count/has_more/textSegments/_sizing/_layoutSummary")

    args = parser.parse_args()
    data = load_json(args.json_file)
    index = build_node_index(data)

    target_node = index.get(args.node_id)
    if not target_node:
        print(f"错误: 未找到 ID 为 '{args.node_id}' 的节点", file=sys.stderr)
        sys.exit(1)

    max_depth = 0 if args.no_children else args.max_depth
    detail = extract_node_detail(target_node, current_depth=0, max_depth=max_depth,
                                 collapse=args.collapse, expand_deco=args.expand_deco,
                                 compact=args.compact)

    if args.with_parent:
        parent_index = build_parent_index(data)
        parent = parent_index.get(args.node_id)
        if parent:
            style = parent.get("style", {})
            css = compact_style(style) if args.compact else style
            layout_keys = ("display", "flexDirection", "gap", "alignItems",
                           "justifyContent", "padding", "flexWrap")
            layout = {k: css[k] for k in layout_keys if k in css}
            siblings = []
            for child in parent.get("children", []):
                cid = child.get("id", "")
                cs = child.get("style", {})
                cs = compact_style(cs) if args.compact else cs
                sib = {"id": cid, "name": node_name(child), "tag": child.get("tag", "unknown")}
                if "width" in cs: sib["width"] = cs["width"]
                if "height" in cs: sib["height"] = cs["height"]
                if child.get("_layoutRole"): sib["_layoutRole"] = child["_layoutRole"]
                if cid == args.node_id: sib["_current"] = True
                siblings.append(sib)
            parent_info = {
                "id": parent.get("id", "unknown"),
                "name": node_name(parent),
                "layout": layout if layout else None,
                "siblings": siblings,
            }
            if not args.compact:
                parent_info["_sizing"] = parent.get("_sizing")
                parent_info["_layoutSummary"] = parent.get("_layoutSummary")
            detail["_parent"] = parent_info

    print(json.dumps(detail, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
