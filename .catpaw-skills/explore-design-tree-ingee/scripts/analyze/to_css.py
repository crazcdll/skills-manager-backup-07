#!/usr/bin/env python3
"""
D2C CSS Renderer - 把节点 style 渲染为可直接粘贴的 CSS

消灭"读 JSON 手抄 CSS"的转录错误。属性按 定位→盒模型→布局→间距→视觉→排版
分组排序；`_hug` 标注的维度输出为注释（测量值，勿写死）。

用法:
    python to_css.py <json_file> <node_id> [--selector SEL] [--with-children]
"""

import sys
import os
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import load_json, build_node_index, build_parent_index, node_name, resolve_ref_or_die

PROP_ORDER = [
    "position", "left", "top", "right", "bottom", "zIndex",
    "width", "height",
    "display", "flexDirection", "justifyContent", "alignItems", "gap",
    "flexWrap", "flexGrow", "alignSelf", "overflow",
    "padding", "margin",
    "background", "backgroundColor", "border", "borderRadius", "boxShadow",
    "opacity", "transform",
    "fontFamily", "fontSize", "fontWeight", "lineHeight", "color",
    "textAlign", "textDecoration",
]
_ORDER = {k: i for i, k in enumerate(PROP_ORDER)}


def kebab(prop: str) -> str:
    return re.sub(r"([A-Z])", r"-\1", prop).lower()


def render_block(node: dict, selector: str) -> str:
    style = node.get("style", {})
    hug = node.get("_hug", "")
    lines = [f"{selector} {{"]
    for prop in sorted(style.keys(), key=lambda k: _ORDER.get(k, 999)):
        value = style[prop]
        if prop == "width" and "w" in hug:
            lines.append(f"  /* width: {value};  hug — 由内容撑开，勿写死 */")
            continue
        if prop == "height" and "h" in hug:
            lines.append(f"  /* height: {value};  hug — 由内容撑开，勿写死 */")
            continue
        lines.append(f"  {kebab(prop)}: {value};")
    lines.append("}")
    return "\n".join(lines)


def selector_for(node: dict, fallback_prefix: str = "node") -> str:
    name = node.get("name") or ""
    slug = re.sub(r"[^a-z0-9一-鿿]+", "-", name.lower()).strip("-")
    if not slug:
        slug = (node.get("id") or fallback_prefix).replace(":", "-").replace("/", "_")
    return f".{slug}"


def main():
    parser = argparse.ArgumentParser(description="把节点 style 渲染为 CSS")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("node_ref", help="目标节点引用（id / text:子串 / name:子串）")
    parser.add_argument("--up", type=int, default=0, metavar="N",
                        help="解析后向上爬 N 层父节点")
    parser.add_argument("--selector", help="自定义选择器（默认按节点名生成）")
    parser.add_argument("--with-children", action="store_true", help="附带直接子节点的 CSS 块")
    args = parser.parse_args()

    data = load_json(args.json_file)
    index = build_node_index(data)
    parents = build_parent_index(data)
    node = resolve_ref_or_die(args.node_ref, index, parents, args.up)

    blocks = [f"/* {node_name(node)} ({node.get('id')}) */",
              render_block(node, args.selector or selector_for(node))]

    if args.with_children:
        for child in node.get("children", []):
            blocks.append("")
            blocks.append(f"/* └ {node_name(child)} ({child.get('id')}) */")
            blocks.append(render_block(child, selector_for(child)))

    print("\n".join(blocks))


if __name__ == "__main__":
    main()
