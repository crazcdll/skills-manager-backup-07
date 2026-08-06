#!/usr/bin/env python3
"""
Explore Design Tree post-processing entrypoint.

    python scripts/postprocess.py normalize <raw_json>

为 raw JSON 生成:
  - sibling semantic companion: *.semantic.json
  - sibling meta file: *.semantic.meta.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _semantic import normalize_file, semantic_json_path, semantic_meta_path


def cmd_normalize(args) -> int:
    input_path = os.path.abspath(args.raw_json)
    if input_path.endswith(".semantic.json"):
        print("错误: normalize 需要 raw JSON 输入，不要直接传 *.semantic.json", file=sys.stderr)
        return 1

    out_path = os.path.abspath(args.output) if args.output else semantic_json_path(input_path)
    meta_path = os.path.abspath(args.meta_output) if args.meta_output else semantic_meta_path(input_path)

    semantic_path, written_meta = normalize_file(input_path, output_path=out_path, meta_path=meta_path)
    summary = {
        "status": "ok",
        "input": input_path,
        "semantic": semantic_path,
        "meta": written_meta,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explore Design Tree 后处理入口")
    sub = parser.add_subparsers(dest="command", required=True)

    normalize = sub.add_parser("normalize", help="为 raw JSON 生成语义 companion 文件")
    normalize.add_argument("raw_json", help="raw 设计稿 JSON 路径")
    normalize.add_argument("--output", help="指定 semantic 输出路径（默认 sibling *.semantic.json）")
    normalize.add_argument("--meta-output", help="指定 meta 输出路径（默认 sibling *.semantic.meta.json）")
    normalize.set_defaults(func=cmd_normalize)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
