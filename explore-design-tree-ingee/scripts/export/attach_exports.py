#!/usr/bin/env python3
"""
D2C Export Attacher - 将已导出的切图路径关联到设计稿 JSON 节点

读取 _exports.json 清单，为 JSON 树中对应节点添加 _exportSrc 等提示字段。
不删除任何已有字段或 children —— 纯增量标注。

用法:
    python attach_exports.py <json_file> [--manifest PATH] [--dry-run]

示例:
    python attach_exports.py .d2c/188096019228285/主态-有匹配订单.json
    python attach_exports.py .d2c/188096019228285/主态-有匹配订单.json --dry-run
"""

import json
import argparse
import os
import sys
from typing import Dict, Optional

RENDER_HINT = "whole-node-image-available"
CHILDREN_HINT = "same-module"


def find_and_attach(node: Dict, manifest: Dict, stats: Dict):
    """递归遍历节点树，为匹配的节点添加 _exportSrc 和渲染提示"""
    node_id = node.get("id", "")
    if node_id in manifest:
        export_info = manifest[node_id]
        # 优先使用 CDN URL，本地路径作为兜底
        node["_exportSrc"] = export_info.get("cdnUrl") or export_info["file"]
        node["_renderHint"] = RENDER_HINT
        node["_childrenHint"] = CHILDREN_HINT
        node["_exportLocal"] = export_info["file"]
        if export_info.get("cdnUrl"):
            node["_exportCdn"] = export_info["cdnUrl"]
        if export_info.get("format"):
            node["_exportFormat"] = export_info["format"]
        if export_info.get("scale") and export_info["scale"] > 1:
            node["_exportScale"] = export_info["scale"]
        stats["attached"] += 1
        if export_info.get("cdnUrl"):
            stats["cdn"] += 1
        else:
            stats["local"] += 1

    for child in node.get("children", []):
        find_and_attach(child, manifest, stats)


def main():
    parser = argparse.ArgumentParser(
        description="将已导出的切图路径关联到设计稿 JSON 节点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s .d2c/188096019228285/主态-有匹配订单.json
  %(prog)s .d2c/188096019228285/主态-有匹配订单.json --dry-run
  %(prog)s .d2c/188096019228285/主态-有匹配订单.json --manifest .d2c/188096019228285/_exports.json
        """
    )
    parser.add_argument("json_file", help="设计稿 JSON 文件路径")
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="导出清单路径（默认：与 json_file 同目录的 _exports.json）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出会修改的节点，不实际写入文件"
    )

    args = parser.parse_args()

    # 读取 JSON
    try:
        with open(args.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.json_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {e}", file=sys.stderr)
        sys.exit(1)

    # 查找 manifest
    manifest_path = args.manifest
    if not manifest_path:
        json_dir = os.path.dirname(os.path.abspath(args.json_file))
        manifest_path = os.path.join(json_dir, "_exports.json")

    if not os.path.exists(manifest_path):
        print(f"错误: 导出清单不存在 - {manifest_path}", file=sys.stderr)
        print("提示: 请先通过 EXPORT_NODE + d2c_server 导出切图", file=sys.stderr)
        sys.exit(1)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: 清单 JSON 解析失败 - {e}", file=sys.stderr)
        sys.exit(1)

    if not manifest:
        print("清单为空，无需处理")
        sys.exit(0)

    # 执行关联
    stats = {"attached": 0, "cdn": 0, "local": 0}
    find_and_attach(data, manifest, stats)

    if args.dry_run:
        # 输出会被标记的节点
        print(json.dumps({
            "mode": "dry-run",
            "manifest_entries": len(manifest),
            "attached": stats["attached"],
            "details": {
                nid: {
                    "src": info.get("cdnUrl") or info["file"],
                    "hasCdn": bool(info.get("cdnUrl")),
                    "renderHint": RENDER_HINT,
                    "childrenHint": CHILDREN_HINT,
                } for nid, info in manifest.items()
            }
        }, ensure_ascii=False, indent=2))
    else:
        with open(args.json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": "ok",
            "manifest_entries": len(manifest),
            "attached": stats["attached"],
            "cdn_src": stats["cdn"],
            "local_src": stats["local"],
            "file": args.json_file,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
