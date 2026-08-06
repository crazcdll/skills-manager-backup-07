#!/usr/bin/env python3
"""
S3 文件上传脚本（测试环境）

通过 mssapi-mt SDK 直接在本地生成预签名 URL，上传到 msstest.sankuai.com，
由 KMS 自动管理 AK/SK，无需 access-token。

使用示例：

  # 仅生成预签名 URL（不上传）
  python upload-to-s3.py \\
    --file-name "goodsId文件类型模版.csv" \\
    --pre-sign-only

  # 完整上传（生成预签名 URL → PUT 上传）
  python upload-to-s3.py \\
    --file-name "goodsId文件类型模版.csv" \\
    --local-file "/tmp/template.csv"

  # 已有预签名 URL，直接上传
  python upload-to-s3.py \\
    --file-name "template.csv" \\
    --upload-with-url "http://msstest.sankuai.com/..." \\
    --local-file "/tmp/template.csv"

  # 自定义桶名 / kms_appkey / 有效期
  python upload-to-s3.py \\
    --file-name "template.csv" \\
    --local-file "/tmp/template.csv" \\
    --bucket-name "biz-platform-goods-copy" \\
    --kms-appkey "com.sankuai.hotel.biz.platform" \\
    --expires-in 7200

  # dry-run（仅打印，不发请求）
  python upload-to-s3.py \\
    --file-name "test.csv" \\
    --local-file "/tmp/test.csv" \\
    --dry-run
"""

import argparse
import os
import sys

# ── 路径修正：支持直接运行和作为模块引用两种方式 ────────────────────────────
_SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _SKILL_ROOT not in sys.path:
    sys.path.insert(0, _SKILL_ROOT)

from interface.resource.interface import (  # noqa
    generate_pre_signed_url,
    upload,
    S3_HOST,
    KMS_APPKEY,
    DEFAULT_BUCKET,
    PRESIGN_EXPIRES,
)


# ════════════════════════════════════════════════════════════════════════════
# CLI 参数定义
# ════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upload-to-s3",
        description=f"S3 文件上传工具（测试环境 {S3_HOST}，KMS 自动管理 AK/SK）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填：目标文件名 ───────────────────────────────────────────────────────
    parser.add_argument(
        "--file-name", "-f",
        required=True,
        metavar="FILENAME",
        help="S3 对象 key（上传目标文件名），支持中文，如 goodsId文件类型模版.csv",
    )

    # ── 操作模式（三选一）─────────────────────────────────────────────────────
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--local-file", "-l",
        metavar="PATH",
        help="本地文件路径（完整上传：生成预签名 URL → PUT 上传）",
    )
    mode_group.add_argument(
        "--pre-sign-only",
        action="store_true",
        help="仅生成预签名 URL，不上传文件（用于调试或手动上传）",
    )
    mode_group.add_argument(
        "--upload-with-url",
        metavar="PRE_SIGNED_URL",
        help="已有预签名 URL，跳过生成步骤直接上传（需同时指定 --local-file）",
    )

    # ── 可选：S3 / KMS 配置 ────────────────────────────────────────────────────
    parser.add_argument(
        "--bucket-name", "-b",
        default=DEFAULT_BUCKET,
        metavar="BUCKET",
        help=f"S3 桶名（默认 {DEFAULT_BUCKET}）",
    )
    parser.add_argument(
        "--kms-appkey",
        default=KMS_APPKEY,
        metavar="APPKEY",
        help=f"KMS appkey，用于自动获取 AK/SK（默认 {KMS_APPKEY}）",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=PRESIGN_EXPIRES,
        metavar="SECONDS",
        help=f"预签名 URL 有效期（秒，默认 {PRESIGN_EXPIRES}=1小时）",
    )

    # ── 辅助 ───────────────────────────────────────────────────────────────────
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="仅打印参数，不发送实际请求",
    )

    return parser


# ════════════════════════════════════════════════════════════════════════════
# 主逻辑
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = build_parser()

    # --upload-with-url 需要同时传 --local-file，特殊处理绕过互斥组限制
    if "--upload-with-url" in sys.argv:
        args, _ = parser.parse_known_args()
        if not args.local_file:
            parser.error("--upload-with-url 需要同时指定 --local-file")
    else:
        args = parser.parse_args()

    print("=" * 60)
    print(f"  🪣  S3 上传工具（{S3_HOST}）")
    print("=" * 60)
    print(f"  bucket     : {args.bucket_name}")
    print(f"  file_name  : {args.file_name}")
    print(f"  kms_appkey : {args.kms_appkey}")
    print(f"  expires_in : {args.expires_in}s")
    print("=" * 60)

    try:
        # ── 模式一：仅生成预签名 URL ──────────────────────────────────────────
        if args.pre_sign_only:
            print("\n📌 模式：仅生成预签名 URL\n")
            url = generate_pre_signed_url(
                file_name=args.file_name,
                bucket_name=args.bucket_name,
                kms_appkey=args.kms_appkey,
                expires_in=args.expires_in,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                print("\n" + "=" * 60)
                print("  ✅ 预签名 URL 生成成功")
                print("=" * 60)
                print(f"  preSignedUrl: {url}")
                print("=" * 60)

        # ── 模式二：已有预签名 URL，直接上传 ──────────────────────────────────
        elif args.upload_with_url:
            print("\n📌 模式：使用已有预签名 URL 上传\n")
            # 复用 _put_file（直接 import）
            from interface.resource.interface import _put_file  # noqa
            if args.dry_run:
                print(f"[dry-run] PUT {args.upload_with_url[:80]}...")
                print(f"  本地文件: {args.local_file}")
            else:
                file_size = os.path.getsize(args.local_file)
                print(f"⏳ 正在上传（{args.local_file}，{file_size} bytes）...")
                _put_file(args.upload_with_url, args.local_file)
                print(f"✅ 上传成功")
            _print_done(args.local_file, args.bucket_name, args.file_name)

        # ── 模式三：完整上传（生成预签名 → 上传）─────────────────────────────
        else:
            print("\n📌 模式：完整上传（生成预签名 URL → PUT 上传）\n")
            result = upload(
                local_file_path=args.local_file,
                file_name=args.file_name,
                bucket_name=args.bucket_name,
                kms_appkey=args.kms_appkey,
                expires_in=args.expires_in,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                print("\n" + "=" * 60)
                print("  ✅ 上传完成")
                print("=" * 60)
                print(f"  本地文件   : {result['local_file_path']}")
                print(f"  S3 桶      : {result['bucket_name']}")
                print(f"  S3 文件名  : {result['file_name']}")
                dl_url = result.get('download_url', '')
                print(f"\n  📥 下载链接（有效期1小时）:")
                print(f"  {dl_url}")
                print("=" * 60)

    except FileNotFoundError as e:
        print(f"\n❌ 文件不存在: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ 参数错误: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n❌ 执行失败: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 已取消", file=sys.stderr)
        sys.exit(130)


def _print_done(local_file: str, bucket_name: str, file_name: str) -> None:
    print("\n" + "=" * 60)
    print("  ✅ 上传完成")
    print("=" * 60)
    print(f"  本地文件 : {local_file}")
    print(f"  S3 目标  : bucket={bucket_name}, key={file_name}")
    print("=" * 60)


if __name__ == "__main__":
    main()

