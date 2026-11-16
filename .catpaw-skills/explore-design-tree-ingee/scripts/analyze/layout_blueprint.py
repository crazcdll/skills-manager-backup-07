#!/usr/bin/env python3
"""
D2C Layout Blueprint - 输出设计稿的 ASCII 布局结构树

用法:
    python layout_blueprint.py <json_file> [--root-id ID] [--max-depth N] [--collapse] [--compact]

示例:
    python layout_blueprint.py .d2c/design.json
    python layout_blueprint.py .d2c/design.json --root-id 626:015347 --max-depth 5
    python layout_blueprint.py .d2c/design.json --compact
"""

import sys
import argparse
from typing import Dict, List, Optional

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import (
    build_node_index, load_json, node_name,
    should_collapse, collapsed_fields, export_facts, semantic_badges,
)


def _strip_px(value: str) -> str:
    if isinstance(value, str) and value.endswith("px"):
        return value[:-2]
    return str(value)


def build_descriptor(node: Dict, collapse: bool = False) -> str:
    if should_collapse(node, collapse):
        style = node.get("style", {})
        w = _strip_px(style.get("width", "?"))
        h = _strip_px(style.get("height", "?"))
        return f"[img {w}×{h}]"

    if node.get("textContent"):
        return "[span]"

    tag = node.get("tag", "")
    if tag == "img" or node.get("src"):
        style = node.get("style", {})
        w = _strip_px(style.get("width", "?"))
        h = _strip_px(style.get("height", "?"))
        return f"[img {w}×{h}]"

    if export_facts(node).get("candidate"):
        style = node.get("style", {})
        w = _strip_px(style.get("width", "?"))
        h = _strip_px(style.get("height", "?"))
        return f"[slice {w}×{h}]"

    style = node.get("style", {})

    if style.get("display") == "flex":
        fd = style.get("flexDirection", "row")
        direction = "COL" if fd == "column" else "ROW"
        parts = [direction]
        gap = style.get("gap")
        if gap is not None:
            parts.append(f"gap={_strip_px(gap)}")
        sizing = node.get("_sizing")
        if sizing:
            parts.append(f"{sizing.get('w', '?')}×{sizing.get('h', '?')}")
        else:
            w = style.get("width")
            h = style.get("height")
            if w is not None or h is not None:
                w_str = _strip_px(w) if w is not None else "?"
                h_str = _strip_px(h) if h is not None else "?"
                parts.append(f"{w_str}×{h_str}")
        return f"[{' '.join(parts)}]"

    children = node.get("children", [])
    if children:
        w = _strip_px(style.get("width", "?"))
        h = _strip_px(style.get("height", "?"))
        return f"[BLOCK {w}×{h}]"

    w = style.get("width")
    h = style.get("height")
    if w is not None or h is not None:
        w_str = _strip_px(w) if w is not None else "?"
        h_str = _strip_px(h) if h is not None else "?"
        return f"[BLOCK {w_str}×{h_str}]"
    return "[BLOCK]"


def build_annotation(node: Dict, compact: bool = False) -> str:
    parts = []
    text = node.get("textContent")

    if text:
        max_len = 15 if compact else 20
        segments = node.get("textSegments")

        if len(text) > max_len:
            display = f'"{text[:max_len]}..."'
            annotation = f"{display} ← truncated"
        else:
            display = f'"{text}"'
            annotation = display

        if not compact and segments and len(segments) > 1:
            annotation += f" ← {len(segments)} segments"
        parts.append(annotation)

    if not compact:
        badges = semantic_badges(node)
        if badges:
            parts.append("[" + ",".join(badges) + "]")

    return " ".join(parts)


def render_tree(node: Dict, prefix: str = "", is_last: bool = True,
                depth: int = 0, max_depth: Optional[int] = None,
                collapse: bool = False, compact: bool = False,
                lines: Optional[List[str]] = None) -> List[str]:
    if lines is None:
        lines = []

    descriptor = build_descriptor(node, collapse)
    annotation = build_annotation(node, compact)
    name = node_name(node)

    if depth == 0:
        line = f"{descriptor} {name}"
    else:
        connector = "└── " if is_last else "├── "
        line = f"{prefix}{connector}{descriptor} {name}"

    if annotation:
        line += f"  {annotation}"

    lines.append(line)

    if should_collapse(node, collapse):
        return lines

    if max_depth is not None and depth >= max_depth:
        return lines

    children = node.get("children", [])
    for i, child in enumerate(children):
        child_is_last = (i == len(children) - 1)
        if depth == 0:
            child_prefix = ""
        else:
            child_prefix = prefix + ("    " if is_last else "│   ")
        render_tree(child, child_prefix, child_is_last,
                    depth + 1, max_depth, collapse, compact, lines)

    return lines


def main():
    parser = argparse.ArgumentParser(description="输出设计稿的 ASCII 布局结构树")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("--root-id", type=str, default=None, help="从指定节点开始渲染")
    parser.add_argument("--max-depth", type=int, default=None, help="限制渲染深度")
    parser.add_argument("--collapse", action="store_true", help="坍缩模式")
    parser.add_argument("--compact", action="store_true",
                        help="精简模式：max-depth 默认 2，文本截断更短，无 badges")

    args = parser.parse_args()
    data = load_json(args.json_file)

    if args.root_id:
        index = build_node_index(data)
        root = index.get(args.root_id)
        if not root:
            print(f"错误: 未找到 ID 为 '{args.root_id}' 的节点", file=sys.stderr)
            sys.exit(1)
    else:
        root = data

    # Compact: default to max_depth=2 instead of unlimited
    max_depth = args.max_depth
    if max_depth is None and args.compact:
        max_depth = 2

    root_name = node_name(root)
    root_id = root.get("id", "unknown")
    print(f"# Layout Blueprint: {root_name} ({root_id})")

    lines = render_tree(root, max_depth=max_depth, collapse=args.collapse, compact=args.compact)
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
