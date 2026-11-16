#!/usr/bin/env python3
"""
D2C Node Searcher - 按条件搜索设计稿节点

用法:
    python search_nodes.py <json_file> [搜索条件]

示例:
    python search_nodes.py .d2c/design.json --text "¥"
    python search_nodes.py .d2c/design.json --exportable --compact
"""

import json
import sys
import argparse
import re
from typing import Dict, List, Optional

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import (
    load_json, node_name,
    should_collapse, collapsed_fields, export_marker_fields,
    semantic_role, recommendation_strategy,
    semantic_payload,
    export_facts,
    compact_style,
)


def build_path(ancestors: List[str], current_name: str) -> str:
    return " > ".join(ancestors + [current_name])


def matches_criteria(node: Dict, text: Optional[str], node_type: Optional[str],
                     name_pattern: Optional[str], has_image: bool, exportable: bool,
                     style_filters: Optional[List[str]] = None,
                     role: Optional[str] = None, prefer: Optional[str] = None,
                     why: Optional[str] = None, has_cdn: bool = False) -> bool:
    if text:
        if text.lower() not in node.get("textContent", "").lower():
            return False
    if node_type:
        if node.get("tag", "").lower() != node_type.lower():
            return False
    if name_pattern:
        if not re.search(name_pattern, node_name(node), re.IGNORECASE):
            return False
    if has_image:
        tag = node.get("tag", "")
        if tag != "img" and not node.get("src") and not node.get("style", {}).get("backgroundImage"):
            return False
    if exportable:
        if not export_facts(node).get("candidate"):
            return False
    if role:
        if semantic_role(node) != role:
            return False
    if prefer:
        if recommendation_strategy(node) != prefer:
            return False
    if why:
        semantic = semantic_payload(node)
        if why not in semantic.get("why", []):
            return False
    if has_cdn:
        from _common import primary_export
        export = primary_export(node)
        if not export or not export.get("src"):
            return False
    if style_filters:
        node_style = node.get("style", {})
        for sf in style_filters:
            key, _, value = sf.partition("=")
            if str(node_style.get(key, "")) != value:
                return False
    return True


def search_nodes(node: Dict, text: Optional[str], node_type: Optional[str],
                 name_pattern: Optional[str], has_image: bool, exportable: bool,
                 max_results: int, ancestors: List[str] = None,
                 collapse: bool = False, style_filters: Optional[List[str]] = None,
                 role: Optional[str] = None, prefer: Optional[str] = None,
                 why: Optional[str] = None, compact: bool = False,
                 has_cdn: bool = False) -> List[Dict]:
    if ancestors is None:
        ancestors = []

    results = []
    name = node_name(node)

    if matches_criteria(
        node, text, node_type, name_pattern, has_image, exportable,
        style_filters, role=role, prefer=prefer, why=why, has_cdn=has_cdn,
    ):
        is_collapsed = should_collapse(node, collapse)
        result = {
            "id": node.get("id", "unknown"),
            "name": name,
            "type": "img" if is_collapsed else node.get("tag", "unknown"),
        }

        if not compact:
            result["path"] = build_path(ancestors, name)

        node_role = semantic_role(node)
        node_prefer = recommendation_strategy(node)
        if node_role:
            result["role"] = node_role
        if node_prefer:
            result["prefer"] = node_prefer
        if not compact:
            node_why = semantic_payload(node).get("why", [])
            if node_why:
                result["why"] = node_why

        if is_collapsed:
            result.update(collapsed_fields(node))
        else:
            if node.get("textContent"):
                result["textContent"] = node["textContent"]
            if node.get("src"):
                result["src"] = node["src"]

            export = export_facts(node)
            if export:
                if compact:
                    result["exportable"] = True
                else:
                    result["export"] = export

            if not compact:
                result.update(export_marker_fields(node))

            style = node.get("style", {})
            if style:
                cs = compact_style(style) if compact else style
                useful_keys = [
                    "fontSize", "fontWeight", "color", "backgroundColor",
                    "width", "height", "padding",
                    "display", "flexDirection", "justifyContent", "alignItems",
                    "borderRadius", "border",
                ]
                useful_style = {k: cs[k] for k in useful_keys if k in cs}
                if useful_style:
                    result["style"] = useful_style

        # 附加 CDN 链接
        cdn_src = node.get("_exportSrc")
        if cdn_src:
            result["cdn"] = cdn_src

        results.append(result)

    if len(results) >= max_results:
        return results[:max_results]

    current_path = ancestors + [name]
    for child in node.get("children", []):
        if len(results) >= max_results:
            break
        results.extend(search_nodes(
            child, text, node_type, name_pattern, has_image, exportable,
            max_results - len(results), current_path, collapse,
            style_filters=style_filters, role=role, prefer=prefer, why=why,
            compact=compact, has_cdn=has_cdn,
        ))

    return results[:max_results]


def main():
    parser = argparse.ArgumentParser(description="按条件搜索设计稿节点")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("--text", type=str, default=None, help="搜索 textContent 包含关键词的节点")
    parser.add_argument("--type", type=str, default=None, help="搜索指定类型的节点")
    parser.add_argument("--name", type=str, default=None, help="搜索名称匹配的节点（支持正则）")
    parser.add_argument("--has-image", action="store_true", help="搜索包含图片的节点")
    parser.add_argument("--exportable", action="store_true", help="搜索可导出切图的节点")
    parser.add_argument("--has-cdn", action="store_true", help="搜索有 CDN 链接（_exportSrc）的节点")
    parser.add_argument("--role", type=str, default=None, help="按 semantic.role 搜索")
    parser.add_argument("--prefer", type=str, default=None, help="按 semantic.prefer 搜索")
    parser.add_argument("--strategy", type=str, default=None, help="兼容旧参数，等同于 --prefer")
    parser.add_argument("--why", type=str, default=None, help="按 semantic.why 搜索")
    parser.add_argument("--risk", type=str, default=None, help="兼容旧参数，等同于 --why")
    parser.add_argument("--style", type=str, action="append", default=None,
                        help="按样式匹配 (格式: key=value，可多次使用)")
    parser.add_argument("--max-results", type=int, default=20, help="限制返回数量（默认: 20）")
    parser.add_argument("--collapse", action="store_true", help="坍缩模式")
    parser.add_argument("--compact", action="store_true",
                        help="精简模式：去除 path/why/export 嵌套/style 细节")

    args = parser.parse_args()

    if not any([
        args.text, args.type, args.name, args.has_image,
        args.exportable, args.has_cdn, args.style, args.role, args.prefer, args.strategy, args.why, args.risk,
    ]):
        print("错误: 请至少提供一个搜索条件", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    data = load_json(args.json_file)

    prefer = args.prefer or args.strategy
    why = args.why or args.risk

    results = search_nodes(
        data, text=args.text, node_type=args.type, name_pattern=args.name,
        has_image=args.has_image, exportable=args.exportable,
        max_results=args.max_results, collapse=args.collapse, style_filters=args.style,
        role=args.role, prefer=prefer, why=why, compact=args.compact,
        has_cdn=args.has_cdn,
    )

    query = {}
    if args.text: query["text"] = args.text
    if args.type: query["type"] = args.type
    if args.name: query["name"] = args.name
    if args.has_image: query["has_image"] = True
    if args.exportable: query["exportable"] = True
    if args.has_cdn: query["has_cdn"] = True
    if args.role: query["role"] = args.role
    if prefer: query["prefer"] = prefer
    if why: query["why"] = why
    if args.style: query["style"] = args.style

    output = {"query": query, "total": len(results), "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
