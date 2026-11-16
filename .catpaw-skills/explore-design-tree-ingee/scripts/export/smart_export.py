#!/usr/bin/env python3
"""
smart_export.py — 智能切图导出

解决 ingee_export_image 直接导出 SVG 叶子节点时裁切不全的问题。
当目标节点是 SVG 叶子且父容器只包含该节点时，自动向上使用父容器 ID 导出，
确保 icon 完整不缺边。

用法:
    python smart_export.py <semantic_json> <node_id> [--outdir exports] [--image-id <id>]
    python smart_export.py <semantic_json> --batch <id1,id2,...> [--outdir exports]

示例:
    python smart_export.py .d2c/1417736/xxx.semantic.json "878:087539/171:27491/171:27244/171:30018"
    python smart_export.py .d2c/1417736/xxx.semantic.json --batch "878:xxx,878:yyy" --outdir icons
"""

import json
import os
import sys
import argparse
import ssl
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SKILL_DIR)  # scripts/ dir for download_ingee
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))

# SVG-like types that are likely to be cropped too tight
SVG_TAGS = {"svg"}
SVG_MG_TYPES = {"PEN", "VECTOR", "BOOLEAN_OPERATION", "LINE", "STAR", "POLYGON", "ELLIPSE"}


def _find_node_with_parent(root: dict, target_id: str, parent=None) -> Tuple[Optional[dict], Optional[dict]]:
    """Recursively find a node by ID and return (node, parent)."""
    if isinstance(root, dict):
        if root.get("id") == target_id:
            return root, parent
        for child in root.get("children", []):
            result = _find_node_with_parent(child, target_id, root)
            if result[0] is not None:
                return result
    return None, None


def smart_export_id(semantic_data: dict, node_id: str) -> Tuple[str, str]:
    """
    Given a node ID, determine the best ID to use for ingee_export_image.
    
    Rules:
    1. If node is SVG/PEN type AND parent has only 1 child → use parent ID
    2. If after step 1, the new node is still SVG with single-child parent → keep going up
    3. Otherwise use the original ID
    
    Returns: (export_id, reason)
        export_id: the node ID to actually export
        reason: explanation of what happened
    """
    current_id = node_id
    hops = 0
    max_hops = 3  # safety limit to prevent going too far up

    while hops < max_hops:
        node, parent = _find_node_with_parent(semantic_data, current_id)

        if node is None:
            return node_id, f"node {current_id} not found, using original"

        tag = node.get("tag", "")
        mg_type = node.get("_mgType", "")
        is_svg_like = tag in SVG_TAGS or mg_type in SVG_MG_TYPES

        if not is_svg_like:
            # Current node is not SVG-like, good to export as-is
            if hops == 0:
                return current_id, "not SVG-like, using as-is"
            else:
                return current_id, f"promoted {hops} level(s) from {node_id}"

        # Node is SVG-like, check parent
        if parent is None:
            return current_id, "no parent found, using as-is"

        parent_children = parent.get("children", [])
        if len(parent_children) == 1:
            # Parent wraps only this node → go up
            current_id = parent.get("id", current_id)
            hops += 1
            continue
        elif len(parent_children) <= 3 and all(
            c.get("tag") in SVG_TAGS or c.get("_mgType") in SVG_MG_TYPES
            for c in parent_children
        ):
            # Parent has a few SVG children that together form one icon → use parent
            current_id = parent.get("id", current_id)
            hops += 1
            return current_id, f"promoted {hops} level(s) (parent groups {len(parent_children)} SVG parts)"
        else:
            # Parent has mixed children, stop here
            if hops == 0:
                return current_id, "SVG leaf but parent has mixed children, using as-is"
            else:
                return current_id, f"promoted {hops} level(s) from {node_id}"

    return current_id, f"promoted {hops} level(s), hit max hops"


def export_node(
    semantic_path: str,
    node_id: str,
    image_id: str,
    out_dir: str = "exports",
    name: Optional[str] = None,
) -> dict:
    """
    Smart export a node: auto-promote SVG leaves, then call ingee_export_image.
    
    Returns dict with: {export_id, reason, url, local_path, name}
    """
    from download_ingee import mcp_call

    with open(semantic_path, encoding="utf-8") as f:
        data = json.load(f)

    # Auto-detect imageId from _meta if not provided
    if not image_id:
        image_id = data.get("_meta", {}).get("imageId", "")

    export_id, reason = smart_export_id(data, node_id)

    # Determine name
    if not name:
        node, _ = _find_node_with_parent(data, export_id)
        name = (node.get("name", export_id) if node else export_id)
        # Sanitize
        name = name.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")

    os.makedirs(out_dir, exist_ok=True)
    local_path = os.path.join(out_dir, f"{name}.png")

    # Call MCP
    resp = mcp_call("ingee_export_image", {
        "imageId": image_id,
        "layerId": export_id,
        "localPath": local_path,
    })

    url = resp.get("imageUrl", "")

    # Download if URL returned
    if url:
        try:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
                Path(local_path).write_bytes(r.read())
        except Exception as e:
            print(f"  ⚠ 下载失败: {e}", file=sys.stderr)

    result = {
        "original_id": node_id,
        "export_id": export_id,
        "promoted": export_id != node_id,
        "reason": reason,
        "url": url,
        "local_path": local_path,
        "name": name,
    }

    promoted_tag = " (↑ promoted)" if result["promoted"] else ""
    print(f"  ✓ {name}{promoted_tag}: {url or '(no url)'}")
    if result["promoted"]:
        print(f"    {reason}")

    return result


def main():
    parser = argparse.ArgumentParser(description="智能切图导出")
    parser.add_argument("semantic_json", help="归一化 JSON 路径")
    parser.add_argument("node_id", nargs="?", help="要导出的节点 ID")
    parser.add_argument("--batch", help="批量导出，逗号分隔的节点 ID")
    parser.add_argument("--image-id", help="设计稿 imageId（默认从 _meta 读取）")
    parser.add_argument("--outdir", default="exports", help="输出目录")
    parser.add_argument("--name", help="输出文件名（不含扩展名）")
    args = parser.parse_args()

    with open(args.semantic_json, encoding="utf-8") as f:
        data = json.load(f)

    image_id = args.image_id or data.get("_meta", {}).get("imageId", "")

    if args.batch:
        node_ids = [nid.strip() for nid in args.batch.split(",") if nid.strip()]
        print(f"\n📸 批量智能导出 {len(node_ids)} 个节点 → {args.outdir}/")
        results = []
        for nid in node_ids:
            r = export_node(args.semantic_json, nid, image_id, args.outdir)
            results.append(r)

        promoted = sum(1 for r in results if r["promoted"])
        print(f"\n✓ 完成: {len(results)} 个, 其中 {promoted} 个自动提升了导出层级")

        # 打印 CDN 链接汇总
        print(f"\n📋 CDN 链接汇总:")
        for r in results:
            if r.get("url"):
                print(f"  {r['name']}: {r['url']}")

    elif args.node_id:
        print(f"\n📸 智能导出 → {args.outdir}/")
        export_node(args.semantic_json, args.node_id, image_id, args.outdir, args.name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
