#!/usr/bin/env python3
"""
download_ingee.py — 从印迹 MCP 拉取设计稿数据并转换为可分析格式

将数据还原为 .d2c/{imageId}/ 目录结构，自动完成：
  - Ingee → IMD 格式归一化（_normalize.py）
  - _ready.json 快速索引写入
  - Semantic companion 生成

用法:
    python download_ingee.py <ingee_url>
    python download_ingee.py --image-id <id> --layer-id <id>
    python download_ingee.py <url> --outdir .d2c

示例:
    python download_ingee.py "https://ingee.meituan.com/#/artboard/1416266/pos_t?layerId=743%3A043823"
    python download_ingee.py --image-id 1416266 --layer-id "743:043823"
"""

import json
import argparse
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

# Internal domain uses self-signed cert
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

MCP_BASE = "https://d2c.ai.test.sankuai.com/mcp"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))


def mcp_call(tool_name: str, arguments: dict, timeout: int = 60) -> dict:
    """Call Ingee MCP via HTTP."""
    # Initialize first
    init_body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ingee-mcp-new", "version": "1.0.0"},
        }
    }).encode()

    init_req = urllib.request.Request(MCP_BASE, data=init_body, headers=MCP_HEADERS)
    try:
        with urllib.request.urlopen(init_req, timeout=timeout, context=_SSL_CTX) as resp:
            resp.read()  # consume init response
    except Exception as e:
        print(f"  ! MCP 初始化失败: {e}", file=sys.stderr)

    # Call tool
    call_body = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }).encode()

    call_req = urllib.request.Request(MCP_BASE, data=call_body, headers=MCP_HEADERS)
    try:
        with urllib.request.urlopen(call_req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read().decode()
            # SSE response may have data: prefix
            result = None
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str:
                        try:
                            result = json.loads(data_str)
                        except json.JSONDecodeError:
                            pass
            if result is None:
                # Maybe it's direct JSON
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    pass

            if result is None:
                print(f"  ! 无法解析 MCP 响应: {raw[:200]}...", file=sys.stderr)
                return {}

            if "result" in result:
                content = result["result"].get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        try:
                            return json.loads(item["text"])
                        except json.JSONDecodeError:
                            return {"_raw": item["text"]}
            return result
    except Exception as e:
        print(f"  ! MCP 调用失败 ({tool_name}): {e}", file=sys.stderr)
        return {}


def parse_ingee_url(url: str) -> dict:
    """Extract imageId and layerId from an Ingee URL.

    URL format: https://ingee.meituan.com/#/artboard/{imageId}/pos_t?layerId=743%3A043823
    """
    parsed = urlparse(url)
    fragment = parsed.fragment or ""

    # Match /artboard/{imageId}/...
    import re
    image_match = re.search(r'/artboard/(\d+)', fragment)
    image_id = image_match.group(1) if image_match else None

    # Parse query params from fragment or query
    query_str = ""
    if "?" in fragment:
        query_str = fragment.split("?", 1)[1]
    elif parsed.query:
        query_str = parsed.query

    params = parse_qs(query_str)
    layer_ids = params.get("layerId", [])
    layer_id = layer_ids[0] if layer_ids else None

    # Unescape layerId (%3A → :)
    if layer_id:
        from urllib.parse import unquote
        layer_id = unquote(layer_id)

    return {"imageId": image_id, "layerId": layer_id}


def download_design(
    image_id: str,
    layer_id: Optional[str] = None,
    out_dir: Path = Path(".d2c"),
    tree_index: Optional[str] = None,
) -> int:
    """Download design from Ingee MCP and normalize."""
    target = out_dir / image_id
    target.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 印迹设计稿 {image_id}")

    # 1. Get design file data
    print(f"  获取设计稿数据...")
    call_args = {"imageId": image_id}
    if layer_id:
        call_args["layerId"] = layer_id

    raw_data = mcp_call("ingee_get_file_data", call_args, timeout=120)

    # If layer-specific query failed, fall back to full data
    if (not raw_data or (isinstance(raw_data, dict) and raw_data.get("_raw")) or
        (isinstance(raw_data, dict) and "error" in raw_data)):
        if layer_id:
            print(f"  ⚠ layerId {layer_id} 查询失败，回退到全量下载...")
            raw_data = mcp_call("ingee_get_file_data", {"imageId": image_id}, timeout=120)

    if not raw_data or (isinstance(raw_data, dict) and raw_data.get("_raw")):
        print(f"  ✗ 获取设计稿数据失败", file=sys.stderr)
        return 0

    if isinstance(raw_data, dict) and "error" in raw_data:
        print(f"  ✗ 获取设计稿数据失败: {raw_data.get('error')}", file=sys.stderr)
        return 0

    # Determine frame name from first tree
    root_node = raw_data.get("layersTree") or raw_data.get("layers_tree")
    trees = raw_data.get("trees", [])
    if not root_node:
        root_node = trees[0] if trees else {}
    frame_name = root_node.get("objectName", "design")

    safe_name = frame_name.strip().replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")

    # 2. Save raw JSON
    raw_path = target / f"{safe_name}.json"
    raw_path.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ raw: {raw_path}")

    # 3. Normalize (with multi-tree support)
    from _normalize import normalize_ingee_data, count_nodes, count_exportable, count_cdn
    normalized = normalize_ingee_data(raw_data, tree_index=tree_index)

    normalized_path = target / f"{safe_name}.semantic.json"
    normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ normalized: {normalized_path}")

    # 4. Write _ready.json with per-tree stats
    total_nodes = count_nodes(normalized)
    export_count = count_exportable(normalized)
    cdn_count = count_cdn(normalized)

    meta = normalized.get("_meta", {})
    tree_summaries = meta.get("trees", [])

    is_partial = bool(layer_id)
    ready = {
        "frameName": frame_name,
        "imageId": image_id,
        "layerId": layer_id,
        "partial": is_partial,
        "jsonPath": str(raw_path),
        "semanticPath": str(normalized_path),
        "totalNodes": total_nodes,
        "exportCount": export_count,
        "cdnCount": cdn_count,
        "treeCount": meta.get("treeCount", 1),
        "trees": tree_summaries,
        "imageUrls": raw_data.get("image_urls", []),
    }
    ready_path = target / "_ready.json"
    ready_path.write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. Print summary
    print(f"  ✓ _ready.json: {total_nodes} nodes, {export_count} exportable, {cdn_count} cdn")
    if tree_summaries:
        print(f"  📊 {len(tree_summaries)} trees:")
        for ts in tree_summaries:
            has_text = ts["totalNodes"] > 0
            content_flag = "📝" if ts["totalNodes"] > 5 else "📄"
            print(f"     [{ts['index']}] {ts['name']} ({ts['type']}) — "
                  f"{ts['totalNodes']} nodes, {ts['exportCount']} exportable {content_flag}")

    # 6. Export artboard preview image via ingee_export_image
    if layer_id:
        preview_layer = layer_id
    else:
        # Prefer artboard-level ID from imagePath (covers full canvas including all trees)
        artboard_layer = ""
        image_path_url = raw_data.get("imagePath", "")
        if image_path_url:
            import re as _re
            # imagePath format: .../1776221172364-878:083768.png  → extract "878:083768"
            _m = _re.search(r'-(\d+:\d+)\.png', image_path_url)
            if _m:
                artboard_layer = _m.group(1)
        preview_layer = artboard_layer or (trees[0] if trees else root_node).get("objectId", "")

    if preview_layer:
        print(f"  📸 导出画板预览图 (layerId: {preview_layer})...")
        try:
            export_resp = mcp_call("ingee_export_image", {
                "imageId": image_id,
                "layerId": preview_layer,
                "localPath": str(target / "preview.png"),
            }, timeout=30)
            preview_url = export_resp.get("imageUrl", "")
            if preview_url:
                # Download the image
                preview_req = urllib.request.Request(preview_url)
                preview_path = target / "preview.png"
                with urllib.request.urlopen(preview_req, timeout=30, context=_SSL_CTX) as resp:
                    preview_path.write_bytes(resp.read())
                preview_size = preview_path.stat().st_size
                print(f"  ✓ preview.png: {preview_size // 1024}KB")
                ready["previewPath"] = str(preview_path)
                ready["previewUrl"] = preview_url
                # Re-write _ready.json with preview info
                ready_path.write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                print(f"  ⚠ 预览图导出无 imageUrl: {export_resp}")
        except Exception as e:
            print(f"  ⚠ 预览图导出失败: {e}", file=sys.stderr)

    # 7. Update _index.json
    index_path = out_dir / "_index.json"
    index = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if "documents" not in index:
        index["documents"] = {}

    index["documents"][image_id] = {
        "name": frame_name,
        "source": "ingee",
        "file": str(raw_path.relative_to(out_dir)),
        "semanticFile": str(normalized_path.relative_to(out_dir)),
        "treeCount": meta.get("treeCount", 1),
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    if is_partial:
        print(f"\n  ⚠ 当前仅拉取 layerId={layer_id} 所属子树，完整画板请不带 layerId 重新拉取")

    return 1


def main():
    parser = argparse.ArgumentParser(
        description="从印迹 MCP 拉取设计稿数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", nargs="?", help="印迹设计稿 URL")
    parser.add_argument("--image-id", help="设计稿 imageId（如果提供则不需要 URL）")
    parser.add_argument("--layer-id", help="图层 layerId（可选）")
    parser.add_argument("--outdir", default=".d2c", help="本地输出目录（默认 .d2c）")
    parser.add_argument("--tree-index", default="all",
                        help="归一化哪些树: 'all'（默认全部）或逗号分隔的索引如 '0,2'")
    args = parser.parse_args()

    if args.url:
        parsed = parse_ingee_url(args.url)
        image_id = parsed["imageId"]
        layer_id = parsed["layerId"]
        if not image_id:
            print(f"错误: 无法从 URL 解析 imageId: {args.url}", file=sys.stderr)
            sys.exit(1)
    elif args.image_id:
        image_id = args.image_id
        layer_id = args.layer_id
    else:
        parser.print_help()
        sys.exit(1)

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = download_design(image_id, layer_id, out_dir, tree_index=args.tree_index)
    if count > 0:
        print(f"\n✓ 完成 → {out_dir / image_id}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
