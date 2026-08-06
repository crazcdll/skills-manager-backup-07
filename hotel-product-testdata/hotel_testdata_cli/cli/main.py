#!/usr/bin/env python3
"""
hotel-testdata CLI 主入口

用法：
  hotel-testdata <子命令> [选项]

可用子命令：
  fullday         境内全日房端到端上单（自动构造基础实体 → batchCreateGoods → 上线 → 存数据池）
  hourly          钟点房端到端上单（仅境内；自动构造基础实体 → batchCreateGoods → 上线 → 存数据池）
  oversea-fullday 境外全日房端到端上单

路径说明（基础实体构造阶段，fullday/hourly 自动推断）：
  路径A  什么 ID 都没有
           不加 --pool → 直接建POI + 私海认领 + 建供应商 → 等60s + 轮询查合同 → 建房型 → 存数据池
           加 --pool   → 先查数据池：
                          命中：只取partnerId → ⛔询问用户确认 →
                                确认：建POI + 私海认领 + 绑定门店 → 查/建合同 → 建房型
                                拒绝：同未命中，全新建供应商
                          未命中：同不加 --pool（新建后存数据池）

  路径B  有 partnerId + poiId  → 私海认领 + 绑定门店 → 查/建合同 → 建房型

  路径C  只有 poiId
           不加 --pool → 私海认领 + 建供应商 → 等60s + 轮询查合同 → 建房型 → 存数据池
           加 --pool   → 先查数据池：
                          命中：私海认领 + 绑定门店 → 查/建合同 → 建房型
                          未命中：同不加 --pool（新建后存数据池）
  路径D  只有 partnerId        → 建POI + 私海认领 + 绑定门店 → 查/建合同 → 建房型

示例：
  # 全日房 - 路径A（全新，不传任何 ID）
  hotel-testdata fullday

  # 全日房 - 路径A（优先查数据池复用，未命中再全新建）
  hotel-testdata fullday --pool

  # 全日房 - 路径B（已有供应商 + 门店）
  hotel-testdata fullday --partner-id 4550589 --poi-id 1085927256096396

  # 全日房 - 路径C（只有门店 ID，不查数据池直接新建供应商）
  hotel-testdata fullday --poi-id 1085927256096396

  # 全日房 - 路径C（只有门店 ID，优先查数据池）
  hotel-testdata fullday --poi-id 1085927256096396 --pool

  # 全日房 - 路径D（只有供应商 ID）
  hotel-testdata fullday --partner-id 4550589

  支持参数： --room-id 77671480 --room-name "标准大床房"

  # 钟点房 - 路径A（全新）
  hotel-testdata hourly

  # 钟点房 - 路径A（优先查数据池）
  hotel-testdata hourly --pool

  # 钟点房 - 路径B（已有供应商 + 门店）
  hotel-testdata hourly --partner-id 4550100 --poi-id 1090235108219575

  # 钟点房 - 路径C（只有门店 ID，优先查数据池）
  hotel-testdata hourly --poi-id 1090235108219575 --pool

  # 钟点房 - 路径D（只有供应商 ID）
  hotel-testdata hourly --partner-id 4550100

  # 只打印参数不执行
  hotel-testdata fullday --dry-run

  # 查看子命令详细帮助
  hotel-testdata fullday --help
  hotel-testdata hourly  --help
"""

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotel-testdata",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    try:
        from importlib.metadata import version as _pkg_version
        _ver = _pkg_version("mt-hotel-testdata-cli")
    except Exception:
        _ver = "unknown"
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"hotel-testdata {_ver}",
    )

    subparsers = parser.add_subparsers(
        title="子命令",
        dest="command",
        metavar="<subcommand>",
    )

    # ── 注册子命令 ─────────────────────────────────────────────────────────
    from hotel_testdata_cli.cli.commands.fullday import add_subparser as _add_fullday
    _add_fullday(subparsers)

    from hotel_testdata_cli.cli.commands.hourly import add_subparser as _add_hourly
    _add_hourly(subparsers)

    from hotel_testdata_cli.cli.commands.oversea_fullday import add_subparser as _add_oversea_fullday
    _add_oversea_fullday(subparsers)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

