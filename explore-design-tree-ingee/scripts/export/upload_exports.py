#!/usr/bin/env python3
"""
CDN Uploader - 将导出的切图批量上传到美团 CDN

读取 _exports.json，对没有 cdnUrl 的条目上传到 CDN，并将 cdnUrl 写回 _exports.json。
增量上传：已有 cdnUrl 的条目自动跳过，无需重复上传。

用法:
    python upload_exports.py <exports_json> --token <SSO_TOKEN>
    python upload_exports.py <exports_json> --token <SSO_TOKEN> --dry-run

示例:
    python upload_exports.py .d2c/188096019228285/_exports.json --token $SSO_TOKEN
    python upload_exports.py .d2c/188096019228285/_exports.json --token $SSO_TOKEN --dry-run
"""

import json
import argparse
import mimetypes
import os
import sys
import urllib.request
import uuid
from typing import Dict, List, Optional, Tuple


UPLOAD_URL = "https://rmf.vip.sankuai.com/biz-helper/venus/upload-image"


def _build_multipart(
    fields: List[Tuple[str, str]],
    file_name: str,
    file_data: bytes,
    file_content_type: str,
) -> Tuple[str, bytes]:
    """构建 multipart/form-data body，返回 (boundary, body_bytes)"""
    boundary = uuid.uuid4().hex
    parts: List[bytes] = []

    for name, value in fields:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode()
    )
    parts.append(f"Content-Type: {file_content_type}\r\n\r\n".encode())
    parts.append(file_data)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    return boundary, b"".join(parts)


def upload_image(file_path: str, token: str) -> Optional[str]:
    """上传单张图片，返回 CDN URL，失败返回 None"""
    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_data = f.read()

    fields = [
        ("renterKey", "nib_martket"),
        ("teamId", "2"),
        ("source", "1"),
        ("resourceType", "1"),
    ]

    boundary, body = _build_multipart(fields, filename, file_data, mime_type)

    req = urllib.request.Request(
        UPLOAD_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "Origin": "https://maker.sankuai.com",
            "Referer": "https://maker.sankuai.com/",
            "access-token": token,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == 200:
                return data["data"]["originalLink"]
            print(f"  x 上传失败: {data}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"  x 请求异常: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="将导出的切图批量上传到美团 CDN，写入 cdnUrl 字段",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("exports_json", help="_exports.json 路径")
    parser.add_argument("--token", required=True, help="SSO Token（通过 mt-sso exchange 获取）")
    parser.add_argument("--dry-run", action="store_true", help="只列出待上传项，不实际上传")
    args = parser.parse_args()

    # 读取 _exports.json
    try:
        with open(args.exports_json, "r", encoding="utf-8") as f:
            manifest: Dict = json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.exports_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败 - {e}", file=sys.stderr)
        sys.exit(1)

    # 确定切图所在的基准目录（_exports.json 的同级目录）
    base_dir = os.path.dirname(os.path.abspath(args.exports_json))

    # 统计
    total = len(manifest)
    skip = sum(1 for v in manifest.values() if v.get("cdnUrl"))
    pending = total - skip

    print(json.dumps({
        "exports_json": args.exports_json,
        "total": total,
        "already_uploaded": skip,
        "pending": pending,
        "dry_run": args.dry_run,
    }, ensure_ascii=False, indent=2))

    if pending == 0:
        print("\n所有切图已有 cdnUrl，无需上传。")
        return

    if args.dry_run:
        print("\n待上传条目（dry-run，不实际上传）:")
        for node_id, info in manifest.items():
            if not info.get("cdnUrl"):
                print(f"  [{node_id}] {info['file']} ({info.get('nodeName', '')})")
        return

    # 执行上传
    uploaded = 0
    failed = 0
    for node_id, info in manifest.items():
        if info.get("cdnUrl"):
            continue  # 已上传，跳过

        file_rel = info["file"]
        file_abs = os.path.join(base_dir, file_rel)

        if not os.path.exists(file_abs):
            print(f"  ! 文件不存在，跳过: {file_abs}", file=sys.stderr)
            failed += 1
            continue

        print(f"  ^ 上传 [{node_id}] {info.get('nodeName', '')} ...", end=" ", flush=True)
        cdn_url = upload_image(file_abs, args.token)
        if cdn_url:
            info["cdnUrl"] = cdn_url
            print(f"ok {cdn_url}")
            uploaded += 1
        else:
            failed += 1

    # 写回 _exports.json
    with open(args.exports_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "status": "done",
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skip,
        "file": args.exports_json,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
