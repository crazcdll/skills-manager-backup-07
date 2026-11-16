#!/usr/bin/env python3
"""
Supabase Storage 文件下载脚本（base64 解码保存）

将 MCP storage_download 返回的 base64 内容解码并保存为本地文件。

用法:
    # 从 base64 字符串保存文件
    python storage_download.py base64 <base64_string> <output_path>

    # 从包含 base64 的文件保存（适用于数据过长无法作为命令行参数的情况）
    python storage_download.py base64file <base64_file_path> <output_path>

示例:
    python storage_download.py base64 "aGVsbG8gd29ybGQ=" ./output.txt
    python storage_download.py base64file ./response_base64.txt ./output.png
"""

import sys
import os
import base64
import argparse


def save_from_base64(base64_data: str, output_path: str) -> None:
    """从 base64 字符串保存文件"""
    print(f"正在解码 base64 数据...")

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 清理 base64 字符串（去除可能的空白和换行）
    base64_clean = base64_data.strip().replace("\n", "").replace("\r", "").replace(" ", "")

    try:
        file_bytes = base64.b64decode(base64_clean)
    except Exception as e:
        print(f"❌ base64 解码失败: {e}")
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(file_bytes)

    final_size = os.path.getsize(output_path)
    print(f"✅ 保存完成！文件大小: {final_size / 1024:.2f} KB")
    print(f"   保存到: {os.path.abspath(output_path)}")


def save_from_base64_file(base64_file: str, output_path: str) -> None:
    """从包含 base64 内容的文件保存"""
    if not os.path.isfile(base64_file):
        print(f"错误: base64 文件不存在 - {base64_file}")
        sys.exit(1)

    print(f"正在读取 base64 文件: {base64_file}")
    with open(base64_file, "r") as f:
        base64_data = f.read()

    save_from_base64(base64_data, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="从 Supabase Storage 下载的 base64 数据保存为文件"
    )
    subparsers = parser.add_subparsers(dest="mode", help="保存模式")

    # 子命令: base64
    b64_parser = subparsers.add_parser("base64", help="从 base64 字符串保存")
    b64_parser.add_argument("base64_data", help="base64 编码的文件内容")
    b64_parser.add_argument("output_path", help="保存文件的本地路径")

    # 子命令: base64file
    b64file_parser = subparsers.add_parser("base64file", help="从 base64 文件保存")
    b64file_parser.add_argument("base64_file", help="包含 base64 内容的文件路径")
    b64file_parser.add_argument("output_path", help="保存文件的本地路径")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    if args.mode == "base64":
        save_from_base64(args.base64_data, args.output_path)
    elif args.mode == "base64file":
        save_from_base64_file(args.base64_file, args.output_path)


if __name__ == "__main__":
    main()
