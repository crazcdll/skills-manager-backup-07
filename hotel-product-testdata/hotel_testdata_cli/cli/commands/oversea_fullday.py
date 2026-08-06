#!/usr/bin/env python3
"""
子命令：hotel-testdata oversea-fullday

境外全日房端到端上单（占位，逻辑待实现）

TODO: 实现境外全日房上单流程（参考 fullday.py）
"""

import argparse


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "oversea-fullday",
        help="境外全日房端到端上单（🚧 开发中，逻辑待实现）",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> None:
    print("🚧 境外全日房命令尚未实现，敬请期待。")

