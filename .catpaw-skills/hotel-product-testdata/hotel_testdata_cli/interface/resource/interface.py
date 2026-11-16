#!/usr/bin/env python3
"""
接口层：S3 文件上传能力（测试环境）

通过 mssapi-mt SDK 直接在本地生成预签名 URL，
走 msstest.sankuai.com，由 KMS 自动管理 AK/SK，无需 access-token。

依赖：
    pip install mssapi-mt==1.5.3 -i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com

典型用法：
    from interface.resource.interface import generate_pre_signed_url, upload

    # 仅生成预签名 URL
    url = generate_pre_signed_url(file_name="template.csv")
    print(url)

    # 一键生成预签名 + 上传
    result = upload(local_file_path="/tmp/template.csv", file_name="template.csv")
"""

import os
import subprocess
import sys
from typing import Optional

# ── 测试环境 S3 配置 ──────────────────────────────────────────────────────────
S3_HOST      = "msstest.sankuai.com"
KMS_APPKEY   = "com.sankuai.hotel.biz.platform"
DEFAULT_BUCKET = "biz-platform-goods-copy"
# 预签名有效期（秒），默认 1 小时
PRESIGN_EXPIRES = 3600


# ════════════════════════════════════════════════════════════════════════════
# 内部工具函数
# ════════════════════════════════════════════════════════════════════════════

def _get_connection(kms_appkey: str = KMS_APPKEY):
    """
    创建 mssapi S3Connection（测试环境）。
    使用 kms_appkey 让 KMS 自动获取 AK/SK，无需手动维护密钥。
    """
    try:
        import mssapi
    except ImportError:
        raise RuntimeError(
            "mssapi-mt 未安装，请运行：\n"
            "pip install mssapi-mt==1.5.3 "
            "-i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com"
        )
    return mssapi.connect_s3(
        kms_appkey=kms_appkey,
        host=S3_HOST,
        is_secure=False,   # 测试环境 SDK 连接走 HTTP（签名 URL 输出时手动换成 https）
    )


def _put_file(pre_signed_url: str, file_path: str, timeout: int = 120) -> None:
    """
    用 curl 向预签名 URL 发起 PUT 上传文件。

    异常：
        FileNotFoundError - 本地文件不存在
        RuntimeError      - 上传失败（非 200/204）
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"本地文件不存在: {file_path}")

    cmd = [
        "curl", "-s", "-L",             # -L 跟随 307 重定向（测试环境可能跳转）
        "-o", "/dev/null", "-w", "%{http_code}",
        "-X", "PUT",
        "-H", "Content-Type: text/csv",  # 与签名时纳入的 header 保持一致
        "--upload-file", file_path,
        pre_signed_url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"S3 上传超时（{timeout}s），文件：{file_path}")

    http_code = r.stdout.strip()
    if r.returncode != 0:
        raise RuntimeError(f"curl 执行失败（exit={r.returncode}）: {r.stderr[:200]}")
    if http_code not in ("200", "204"):
        raise RuntimeError(f"S3 上传失败，HTTP 状态码: {http_code}\nstderr: {r.stderr[:300]}")


# ════════════════════════════════════════════════════════════════════════════
# 公开接口
# ════════════════════════════════════════════════════════════════════════════

def generate_pre_signed_url(
    file_name: str,
    bucket_name: str = DEFAULT_BUCKET,
    kms_appkey: str = KMS_APPKEY,
    expires_in: int = PRESIGN_EXPIRES,
    method: str = "PUT",
    dry_run: bool = False,
) -> str:
    """
    用 mssapi-mt SDK 直接生成 S3 预签名 URL（测试环境）。

    参数：
        file_name   - S3 对象 key（上传目标路径/文件名，支持中文）
        bucket_name - S3 桶名（默认 biz-platform-goods-copy）
        kms_appkey  - KMS appkey，用于自动获取 AK/SK
        expires_in  - 预签名有效期秒数（默认 3600=1小时）
        method      - HTTP 方法（默认 PUT 用于上传；GET 用于下载）
        dry_run     - True 时只打印不执行

    返回：预签名 URL 字符串（可直接 PUT 上传）

    异常：
        ValueError   - 参数非法
        RuntimeError - mssapi-mt 未安装或 KMS 获取 AK/SK 失败
    """
    if not file_name:
        raise ValueError("file_name 不能为空")

    if dry_run:
        print(f"\n[dry-run] 生成测试环境预签名 URL")
        print(f"  host       : {S3_HOST}")
        print(f"  bucket     : {bucket_name}")
        print(f"  key        : {file_name}")
        print(f"  kms_appkey : {kms_appkey}")
        print(f"  method     : {method}")
        print(f"  expires_in : {expires_in}s")
        return ""

    print(f"⏳ 正在生成预签名 URL（bucket={bucket_name}, key={file_name}）...")

    conn   = _get_connection(kms_appkey)
    # validate=False：跳过 HEAD 验桶请求，避免在本机网络下因 502 报错
    bucket = conn.get_bucket(bucket_name, validate=False)
    key    = bucket.new_key(file_name)
    # PUT 上传时将 Content-Type 纳入签名，这样 curl 带相同 header 才能通过校验
    headers = {"Content-Type": "text/csv"} if method == "PUT" else {}
    url    = key.generate_url(
        expires_in=expires_in,
        method=method,
        query_auth=True,
        force_http=True,   # 签名基于 http://，上传时必须与此保持一致
        headers=headers,
    )
    # GET 下载 URL 对外展示时换成 https（仅展示，不影响签名验证）
    if method == "GET":
        url = url.replace("http://", "https://", 1)

    print(f"✅ 预签名 URL 生成成功")
    print(f"   {url}")
    return url


def upload(
    local_file_path: str,
    file_name: Optional[str] = None,
    bucket_name: str = DEFAULT_BUCKET,
    kms_appkey: str = KMS_APPKEY,
    expires_in: int = PRESIGN_EXPIRES,
    dry_run: bool = False,
) -> dict:
    """
    生成预签名 URL 并上传文件到测试环境 S3（一键完成）。

    参数：
        local_file_path - 本地文件绝对路径，如 "/tmp/template.csv"
        file_name       - S3 对象 key（None 时取本地文件名）
        bucket_name     - S3 桶名（默认 biz-platform-goods-copy）
        kms_appkey      - KMS appkey
        expires_in      - 预签名有效期秒数（默认 3600）
        dry_run         - True 时只打印不执行

    返回：
        {
            "pre_signed_url": "http://msstest.sankuai.com/...",
            "download_url": "https://msstest.sankuai.com/...",
            "bucket_name": "biz-platform-goods-copy",
            "file_name": "template.csv",
            "local_file_path": "/tmp/template.csv",
            "upload_success": True,
        }

    异常：
        FileNotFoundError - 本地文件不存在
        ValueError        - 参数非法
        RuntimeError      - SDK 未安装 / KMS 失败 / 上传失败
    """
    if not file_name:
        file_name = os.path.basename(local_file_path)

    # 步骤一：生成预签名 URL
    pre_signed_url = generate_pre_signed_url(
        file_name=file_name,
        bucket_name=bucket_name,
        kms_appkey=kms_appkey,
        expires_in=expires_in,
        method="PUT",
        dry_run=dry_run,
    )

    if dry_run:
        return {"dry_run": True, "bucket_name": bucket_name, "file_name": file_name}

    # 步骤二：PUT 上传
    file_size = os.path.getsize(local_file_path)
    print(f"⏳ 正在上传文件（{local_file_path}，{file_size} bytes）...")
    _put_file(pre_signed_url, local_file_path)
    print(f"✅ 文件上传成功: {local_file_path}")

    # 步骤三：生成 GET 下载 URL
    download_url = generate_pre_signed_url(
        file_name=file_name,
        bucket_name=bucket_name,
        kms_appkey=kms_appkey,
        expires_in=expires_in,
        method="GET",
    )

    return {
        "pre_signed_url": pre_signed_url,
        "download_url": download_url,
        "bucket_name": bucket_name,
        "file_name": file_name,
        "local_file_path": local_file_path,
        "upload_success": True,
    }

