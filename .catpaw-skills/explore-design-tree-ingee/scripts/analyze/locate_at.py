#!/usr/bin/env python3
"""
D2C Point Locator - 坐标反查节点链

视觉 Diff 发现"截图某处不对"时，反查该位置的节点（从最具体到最外层），
直接定位要修的节点 id。

用法:
    python locate_at.py <json_file> <x> <y> [--from-png] [--max N]

坐标默认为设计稿 px（root 左上角为原点）。若坐标是从 2x 截图上读的像素值，
加 --from-png 自动按截图/设计稿比例换算。
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import load_json, build_node_index, compute_abs_boxes, parse_px, semantic_payload, node_name


def main():
    parser = argparse.ArgumentParser(description="坐标反查节点链")
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument("x", type=float, help="X 坐标")
    parser.add_argument("y", type=float, help="Y 坐标")
    parser.add_argument("--from-png", action="store_true",
                        help="坐标来自 Frame 截图像素（自动按截图比例换算为设计稿 px）")
    parser.add_argument("--max", type=int, default=8, dest="max_results", help="返回数量上限（默认 8）")
    args = parser.parse_args()

    data = load_json(args.json_file)
    x, y = args.x, args.y

    if args.from_png:
        # Ingee 截图优先用 preview.png，fallback 同名 .png
        json_dir = os.path.dirname(os.path.abspath(args.json_file))
        preview_path = os.path.join(json_dir, "preview.png")
        default_png = os.path.splitext(os.path.abspath(args.json_file))[0] + ".png"
        png_path = preview_path if os.path.exists(preview_path) else default_png
        try:
            from PIL import Image
            img = Image.open(png_path)
            root_w = parse_px(data.get("style", {}).get("width"))
            scale = img.width / root_w if root_w else 1.0
            x, y = x / scale, y / scale
        except Exception as e:
            print(f"警告: 无法读取截图换算比例（{e}），按设计稿 px 处理", file=sys.stderr)

    boxes = compute_abs_boxes(data)
    index = build_node_index(data)

    hits = []
    for node_id, (bx, by, bw, bh) in boxes.items():
        if bw and bh and bx <= x <= bx + bw and by <= y <= by + bh:
            hits.append((bw * bh, node_id, [bx, by, bw, bh]))
    hits.sort(key=lambda t: t[0])  # 面积升序：最具体的在前

    results = []
    for _, node_id, box in hits[: args.max_results]:
        node = index.get(node_id, {})
        entry = {
            "id": node_id,
            "name": node_name(node),
            "tag": node.get("tag"),
            "absBox": [round(v, 1) for v in box],
        }
        semantic = semantic_payload(node)
        if semantic.get("role"):
            entry["role"] = semantic["role"]
        if node.get("textContent"):
            entry["textContent"] = node["textContent"]
        results.append(entry)

    print(json.dumps({
        "point": [round(x, 1), round(y, 1)],
        "note": "flex 流内节点无法静态推导坐标，不在结果中；命中按面积从小到大排列",
        "total": len(hits),
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
