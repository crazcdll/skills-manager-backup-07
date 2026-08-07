#!/usr/bin/env python3
"""
S3Plus Upload Script
Upload files to Meituan S3Plus (MSS) storage service.
Based on: https://km.sankuai.com/collabpage/58102733
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import requests

# 环境配置
ENV_HOSTS = {
    "test": "msstest.vip.sankuai.com",
    "prod-corp": "s3plus-corp.sankuai.com",
    "prod": "s3plus.sankuai.com",
}

# 默认配置
DEFAULT_ACCESS_KEY = os.getenv("S3PLUS_ACCESS_KEY", "SRV_ZKi0rdLIrmKK6sndPAJvDlxT6Znmcd0l")
DEFAULT_ACCESS_SECRET = os.getenv("S3PLUS_ACCESS_SECRET", "YLmrhwszKqLS97zN4F5thNqMjuWaB8Kn")
DEFAULT_BUCKET = os.getenv("S3PLUS_BUCKET", "supabase-bucket")
DEFAULT_HOST = "s3plus-bj02.vip.sankuai.com"


def gmttime(offset_seconds: int = 0) -> str:
    now = time.time() + offset_seconds
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now))


def calculate_content_md5(file_path: Path) -> str:
    md5_hash = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return base64.b64encode(md5_hash.digest()).decode("utf-8")


def build_string_to_sign(method, content_md5, content_type, date, canonicalized_amz_headers, canonicalized_resource):
    return f"{method}\n{content_md5}\n{content_type}\n{date}\n{canonicalized_amz_headers}{canonicalized_resource}"


def build_authorization(access_key, access_secret, string_to_sign):
    signature = base64.b64encode(
        hmac.new(
            access_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")
    return f"AWS {access_key}:{signature}"


def build_parser():
    parser = argparse.ArgumentParser(description="Upload file to Meituan S3Plus and return URL")
    parser.add_argument("--env", choices=sorted(ENV_HOSTS.keys()), default="test")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--access-key", default=DEFAULT_ACCESS_KEY)
    parser.add_argument("--access-secret", default=DEFAULT_ACCESS_SECRET)
    parser.add_argument("--file", required=True)
    parser.add_argument("--object-name")
    parser.add_argument("--content-type", default="text/html; charset=utf-8")
    parser.add_argument("--skip-md5", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--output", choices=("url", "json"), default="url")
    parser.add_argument("--date-skew-seconds", type=int, default=0)
    return parser


def upload(args):
    host = args.host
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    object_name = args.object_name or f"/{file_path.name}"
    if not object_name.startswith("/"):
        object_name = "/" + object_name

    content_type = args.content_type if args.content_type else "application/octet-stream"
    date = gmttime(args.date_skew_seconds)
    content_md5 = "" if args.skip_md5 else calculate_content_md5(file_path)

    canonicalized_resource = f"/{args.bucket}{object_name}"
    string_to_sign = build_string_to_sign(
        "PUT", content_md5, content_type, date, "", canonicalized_resource
    )
    authorization = build_authorization(args.access_key, args.access_secret, string_to_sign)

    url = f"https://{host}/{args.bucket}{object_name}"
    headers = {
        "Host": host,
        "Date": date,
        "Content-Type": content_type,
        "Authorization": authorization,
    }
    if content_md5:
        headers["Content-MD5"] = content_md5

    with file_path.open("rb") as f:
        resp = requests.put(
            url,
            data=f,
            headers=headers,
            timeout=args.timeout,
            verify=not args.insecure,
        )

    public_url = f"https://{host}/{args.bucket}{object_name}"
    return resp.status_code, resp.text, public_url, {
        "status_code": resp.status_code,
        "url": public_url,
        "object_name": object_name,
        "bucket": args.bucket,
        "host": host,
    }


def main():
    parser = build_parser()
    args = parser.parse_args()

    status_code, resp_text, public_url, result = upload(args)

    if status_code in (200, 201, 204):
        if args.output == "json":
            print(json.dumps({"success": True, **result}, ensure_ascii=False))
        else:
            print(public_url)
    else:
        if args.output == "json":
            print(json.dumps({"success": False, "status_code": status_code, "error": resp_text}, ensure_ascii=False))
        else:
            print(f"ERROR: Upload failed with status {status_code}: {resp_text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
