#!/usr/bin/env python3
"""
D2C Node Cropper - 按节点绝对包围盒裁剪 Frame 截图

逐模块 Diff 的配套工具：实现一个模块后，用本工具裁出该模块的设计稿截图，
与当前实现的截图直接对比，不用在整张长图里肉眼定位。

用法:
    python crop_node.py <json_file> <node_id> [--png PATH] [--out PATH] [--padding N]

示例:
    python crop_node.py .d2c/doc/frame.json "117:218614"
    python crop_node.py .d2c/doc/frame.json "117:218614" --padding 20
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import (
    load_json, build_node_index, build_parent_index, compute_abs_boxes,
    parse_px, resolve_ref_or_die, box_or_die,
)


def main():
    parser = argparse.ArgumentParser(description="按节点绝对包围盒裁剪 Frame 截图")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("node_ref", help="目标节点引用（id / text:子串 / name:子串）")
    parser.add_argument("--up", type=int, default=0, metavar="N",
                        help="解析后向上爬 N 层父节点")
    parser.add_argument("--png", help="Frame 截图路径（默认与 JSON 同名 .png）")
    parser.add_argument("--out", help="输出路径（默认 同目录 crops/{nodeId}.png）")
    parser.add_argument("--padding", type=int, default=0, help="裁剪外扩边距（设计稿 px）")
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("错误: 需要 Pillow（pip install Pillow）", file=sys.stderr)
        sys.exit(1)

    data = load_json(args.json_file)
    index = build_node_index(data)
    parents = build_parent_index(data)
    boxes = compute_abs_boxes(data)

    node = resolve_ref_or_die(args.node_ref, index, parents, args.up)
    node_id = node["id"]
    box_or_die(node, boxes, parents)  # 校验有绝对盒，否则报最近定位祖先

    # Ingee 截图优先用 preview.png（与 JSON 同目录），fallback 同名 .png
    json_dir = os.path.dirname(os.path.abspath(args.json_file))
    preview_path = os.path.join(json_dir, "preview.png")
    default_png = os.path.splitext(os.path.abspath(args.json_file))[0] + ".png"
    png_path = args.png or (preview_path if os.path.exists(preview_path) else default_png)
    if not os.path.exists(png_path):
        print(f"错误: 截图不存在 - {png_path}", file=sys.stderr)
        print(f"提示: 可用 --png 指定截图路径，或确认 preview.png 已由 download_ingee.py 生成", file=sys.stderr)
        sys.exit(1)

    img = Image.open(png_path)
    root_w = parse_px(data.get("style", {}).get("width"))
    scale = img.width / root_w if root_w else 1.0

    x, y, w, h = boxes[node_id]
    pad = args.padding
    left = max(0, round((x - pad) * scale))
    top = max(0, round((y - pad) * scale))
    right = min(img.width, round((x + w + pad) * scale))
    bottom = min(img.height, round((y + h + pad) * scale))
    if right <= left or bottom <= top:
        print(f"错误: 节点包围盒在截图范围外 (design box: {[x, y, w, h]})", file=sys.stderr)
        sys.exit(1)

    out_path = args.out
    if not out_path:
        safe_id = node_id.replace(":", "-").replace("/", "_")
        out_path = os.path.join(os.path.dirname(png_path), "crops", f"{safe_id}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.crop((left, top, right, bottom)).save(out_path)

    print(json.dumps({
        "out": out_path,
        "designBox": [round(v, 1) for v in (x, y, w, h)],
        "pixelBox": [left, top, right, bottom],
        "scale": round(scale, 2),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
