#!/usr/bin/env python3
"""
子命令：hotel-testdata oversea-fullday

境外全日房端到端上单（薄封装，复用 fullday 流程）。

与 fullday 的差异只有两个参数的预置：
  - overseas      强制 True（本命令语义即"境外"）
  - partner_type  自动置为 3（境外非女娲），避免漏传造成"境外商品挂境内供应商"

流程、路径推断（A/B/C/D）、batchCreateGoods、上线、库存补偿、缓存刷新、
数据池写入全部复用 cli/commands/fullday.py 的 _run。

⚠️ 境外商品参数模板提醒（本命令不自动注入，需按需 --set）：
  fullday 模板默认是境内参数（salePrice 定价、无 priceSameTag）。境外商品
  需要按 W1 文档「境外多人多价/同价」节补充：
    - goodsDetailList.0.goodsBaseInfo.priceSameTag（0=多价 1=同价）
    - goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility（1~6）
    - priceInfo 整块替换（priceFactorInfos 梯度价，priceInfo.priceInfo 须为 null）
  若 VPOI 已切底价模式，价格字段须用 basePrice 并补 priceChangeMode=9 等
  （详见 w1-create-fullday.md「境外产品价格模式」节）。

路径 B/D（已提供 partnerId）不新建供应商，行为与 fullday --overseas 一致。

用法示例：
  # 境外全日房（路径A 全新，partnerType 自动=3）
  hotel-testdata oversea-fullday

  # 已有境外 partnerId + poiId（路径B）
  hotel-testdata oversea-fullday --partner-id 4550589 --poi-id 1085927256096396

  # 多人同价（境外默认推荐，priceInfo 整块替换示例见 w1 文档）
  hotel-testdata oversea-fullday \\
    --set goodsDetailList.0.goodsBaseInfo.priceSameTag=1 \\
    --set goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility=2

  # dry-run
  hotel-testdata oversea-fullday --dry-run
"""

import argparse

from hotel_testdata_cli.cli.commands.fullday import _add_arguments, _run

# 境外非女娲供应商类型
_OVERSEAS_PARTNER_TYPE = 3


def _oversea_run(args: argparse.Namespace) -> None:
    """复用 fullday 的 _run，仅预置境外相关参数。"""
    args.overseas = True
    args.partner_type = _OVERSEAS_PARTNER_TYPE
    print("  🌏 [oversea-fullday] 境外场景：overseas=True，partnerType 自动置为 3（境外非女娲）")
    print("  ⚠️  [oversea-fullday] 商品参数默认仍为境内模板；境外多人价格需按需 --set "
          "priceSameTag/maxAdultAdmissibility/priceFactorInfos（见 w1-create-fullday.md 境外节）")
    _run(args)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """向主解析器注册 oversea-fullday 子命令（薄封装，复用 fullday 参数与流程）。"""
    p = subparsers.add_parser(
        "oversea-fullday",
        help="境外全日房端到端上单（overseas+partnerType=3，复用 fullday 流程）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    _add_arguments(p)
    p.set_defaults(func=_oversea_run, overseas=True)

