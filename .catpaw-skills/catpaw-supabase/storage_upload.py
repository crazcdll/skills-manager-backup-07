#!/usr/bin/env python3
"""
Supabase Storage 小文件上传脚本（通过 MCP 接口，base64 编码）

适用于文件大小 < 1MB 的场景。读取本地文件 → base64 编码 → 构造 JSON-RPC 请求 → POST 到 MCP 服务器完成上传。

用法:
    python storage_upload.py --token <access_token> --project-id <id> --bucket <bucket> --path <remote_path> [--content-type <mime>] [--upsert] [--url <mcp_url>] <local_file>

示例:
    python storage_upload.py --token "eyJ..." --project-id 123 --bucket documents --path "reports/Q1.pdf" ./report.pdf
    python storage_upload.py --token "eyJ..." --project-id 123 --bucket avatars --path "user/avatar.png" --content-type image/png --upsert ./avatar.png

说明:
    - token 为用户身份 access_token，每次调用必须传入，脚本不做任何存储
    - 文件 ≥ 1MB 时请改用 storage_upload_url + curl PUT 方式
"""

import sys
import os
import base64
import json
import mimetypes
import argparse

try:
    import requests
except ImportError:
    print("错误: 需要安装 requests 库。请运行: pip install requests")
    sys.exit(1)

DEFAULT_MCP_URL = "https://kubeplex-mcp.sankuai.com/mcp/supabase/message"


def guess_content_type(file_path: str) -> str:
    """根据文件扩展名推断 MIME 类型"""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def upload_file(token: str, project_id: int, bucket: str, remote_path: str,
                local_file: str, content_type: str = None, upsert: bool = False,
                mcp_url: str = DEFAULT_MCP_URL) -> None:
    """读取文件 → base64 → 调用 MCP storage_upload"""
    if not os.path.isfile(local_file):
        print(f"错误: 文件不存在 - {local_file}")
        sys.exit(1)

    file_size = os.path.getsize(local_file)
    if file_size >= 1 * 1024 * 1024:
        print(f"警告: 文件大小 {file_size / 1024 / 1024:.2f} MB >= 1MB，建议改用 storage_upload_url + curl PUT")

    if not content_type:
        content_type = guess_content_type(local_file)

    print(f"文件: {local_file}")
    print(f"大小: {file_size / 1024:.1f} KB")
    print(f"Content-Type: {content_type}")
    print(f"目标: bucket={bucket}, path={remote_path}")

    # 读取并编码
    with open(local_file, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("ascii")

    # 构造 JSON-RPC 请求
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "storage_upload",
            "arguments": {
                "projectId": project_id,
                "bucket": bucket,
                "path": remote_path,
                "data": data_b64,
                "contentType": content_type,
                "upsert": upsert,
            }
        }
    }

    print("\n正在上传...")
    resp = requests.post(
        mcp_url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"❌ HTTP 请求失败！状态码: {resp.status_code}")
        print(f"响应: {resp.text[:500]}")
        sys.exit(1)

    result = resp.json()
    if "error" in result:
        print(f"❌ MCP 错误: {json.dumps(result['error'], ensure_ascii=False)}")
        sys.exit(1)

    print(f"✅ 上传成功！")
    if "result" in result:
        print(f"响应: {json.dumps(result['result'], ensure_ascii=False, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="通过 MCP 上传小文件到 Supabase Storage")
    parser.add_argument("local_file", help="本地文件路径")
    parser.add_argument("--token", required=True, help="用户身份 access_token")
    parser.add_argument("--project-id", type=int, required=True, help="项目 ID")
    parser.add_argument("--bucket", required=True, help="Storage bucket 名称")
    parser.add_argument("--path", required=True, help="远程存储路径")
    parser.add_argument("--content-type", "-t", default=None, help="文件 MIME 类型（不指定时自动推断）")
    parser.add_argument("--upsert", action="store_true", help="若文件已存在则覆盖")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP 服务端 URL（默认使用内置地址）")

    args = parser.parse_args()
    upload_file(args.token, args.project_id, args.bucket, args.path,
                args.local_file, args.content_type, args.upsert, args.url)


if __name__ == "__main__":
    main()