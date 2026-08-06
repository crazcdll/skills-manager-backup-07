#!/usr/bin/env python3
"""
上传本地文件到 S3Plus 临时 URL
用法: python3 upload-to-s3.py <local_file_path>

参数:
  local_file_path  本地文件路径

凭证由脚本内部 `meigen status --json` 获取（FR-022），不作为命令行参数流经宿主 agent。

上传流程：
  1. 调用加签接口获取上传参数（AWSAccessKeyId, policy, signature, key）
  2. 使用参数调用 S3 上传接口（multipart/form-data）
  3. 拼接可访问的 URL

成功时输出图片 URL 到 stdout，失败时输出 ERROR: <原因> 并以非零退出码退出。
"""

from __future__ import annotations

import sys
import os
import json
import uuid
import mimetypes
import ssl
import urllib.request
import urllib.error

from common import get_access_token, get_credentials


# ─── SSL ────────────────────────────────────────────────────────

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _get_file_extension(file_path: str) -> str:
    """获取文件扩展名（不含点号）。"""
    ext = os.path.splitext(file_path)[1]
    if ext and ext.startswith('.'):
        return ext[1:].lower()
    return "jpg"  # 默认扩展名


def _get_upload_sign(access_token: str, file_path: str) -> dict:
    """调用加签接口获取上传参数。token 由调用方传入（已由 get_access_token 获取）。"""

    # 生成 key：skillopen/{uuid}.{format}
    file_ext = _get_file_extension(file_path)
    object_key = f"skillopen/{uuid.uuid4()}.{file_ext}"

    print(f"[STEP] 📝 请求加签参数...", file=sys.stderr, flush=True)
    print(f"[STEP] 🔑 key: {object_key}", file=sys.stderr, flush=True)

    payload = json.dumps({
        "key": object_key,
        "npmVersion": "V2"
    }).encode("utf-8")

    client_id = get_credentials().client_id or "2a7394863a"

    req = urllib.request.Request(
        "https://aidesign.meituan.com/febffapi/uploadapi/getUploadBucketSign/aigc-warehouse",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"{client_id}_ssoid={access_token}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
            result = json.loads(resp.read().decode("utf-8"))

            if result.get("code") != 0:
                error_msg = result.get("message", "未知错误")
                print(f"ERROR: 加签失败 - {error_msg}", file=sys.stderr)
                sys.exit(1)

            data = result.get("data", {})
            print(f"[STEP] ✅ 加签成功", file=sys.stderr, flush=True)

            return {
                "AWSAccessKeyId": data.get("AWSAccessKeyId"),
                "policy": data.get("policy"),
                "signature": data.get("signature"),
                "key": data.get("key"),
                "object_key": object_key
            }

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"ERROR: 加签请求失败 HTTP {e.code} - {e.reason}. Body: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: 网络错误 - {e.reason}", file=sys.stderr)
        sys.exit(1)


def _upload_to_s3(file_path: str, sign_params: dict) -> str:
    """调用 S3 上传接口。"""

    print(f"[STEP] 📤 上传文件到 S3...", file=sys.stderr, flush=True)

    # 读取文件内容
    with open(file_path, "rb") as f:
        file_content = f.read()

    # 获取文件名和 MIME 类型
    file_name = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # 构建 multipart/form-data
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"

    def build_form_field(name: str, value: str) -> bytes:
        return f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")

    def build_file_field(name: str, filename: str, content_type: str, content: bytes) -> bytes:
        header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n"
        return header.encode("utf-8") + content + b"\r\n"

    body = b""
    body += build_form_field("AWSAccessKeyId", sign_params["AWSAccessKeyId"])
    body += build_form_field("policy", sign_params["policy"])
    body += build_form_field("signature", sign_params["signature"])
    body += build_form_field("key", sign_params["key"])
    body += build_file_field("file", file_name, mime_type, file_content)
    body += f"--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "https://s3plus.sankuai.com/aigc-warehouse/",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as resp:
            # 上传成功，HTTP 200 即可
            print(f"[STEP] ✅ 上传成功", file=sys.stderr, flush=True)

            # 拼接 URL
            object_key = sign_params["object_key"]
            url = f"https://s3plus.sankuai.com/aigc-warehouse/{object_key}"

            return url

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"ERROR: S3 上传失败 HTTP {e.code} - {e.reason}. Body: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: 网络错误 - {e.reason}", file=sys.stderr)
        sys.exit(1)


def upload(local_file: str) -> str:
    """上传本地文件到 S3 并返回 URL。token 由脚本内部 meigen status --json 获取（FR-022）。"""

    if not os.path.exists(local_file):
        print(f"ERROR: 文件不存在: {local_file}", file=sys.stderr)
        sys.exit(1)

    access_token = get_access_token()
    sign_params = _get_upload_sign(access_token, local_file)
    url = _upload_to_s3(local_file, sign_params)

    return url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 upload-to-s3.py <local_file_path>", file=sys.stderr)
        sys.exit(1)

    url = upload(sys.argv[1])
    print(url)