#!/usr/bin/env python3
"""
子命令：hotel-testdata agent-fullday

代理商品（第三方渠道供应商）端到端上单，境内/境外均支持。

与 fullday 的唯一差异：新建供应商时 entity_type 固定为 1（第三方渠道/代理）。
流程、路径推断（A/B/C/D）、batchCreateGoods、上线、库存补偿、缓存刷新、
数据池写入全部复用 cli/commands/fullday.py，本文件仅做语义化封装：

  - entity_type 强制为 1（本命令语义即"代理"，无需手动传 --entity-type）
  - --overseas 时自动把 partner_type 置为 3（境外非女娲），避免漏传造成
    "境外商品挂境内供应商"的脏数据；境内默认 2（境内自采预付）不变
  - --pool 查数据池时固定叠加 117=第三方渠道 标签，只复用代理供应商
    （避免命中普通集团/单体供应商导致代理语义丢失）

路径 B/D（已提供 partnerId）不新建供应商，entity_type 不参与，行为与
fullday 完全一致。

用法示例：
  # 境内代理商品（路径A 全新）
  hotel-testdata agent-fullday

  # 境外代理商品（路径A 全新，partnerType 自动=3）
  hotel-testdata agent-fullday --overseas

  # 已有 partnerId + poiId（路径B，此时与 fullday 行为一致）
  hotel-testdata agent-fullday --partner-id 4550589 --poi-id 1085927256096396

  # 其余参数（--set / --pool / --dry-run / --swimlane 等）与 fullday 完全相同
  hotel-testdata agent-fullday --overseas --pool --dry-run
"""

import argparse

from hotel_testdata_cli.cli.commands.fullday import _add_arguments, _run

# 代理供应商固定实体类型：1=第三方渠道
_AGENT_ENTITY_TYPE = 1
# 境外非女娲供应商类型
_OVERSEAS_PARTNER_TYPE = 3


def _agent_run(args: argparse.Namespace) -> None:
    """复用 fullday 的 _run，仅预置代理相关参数。"""
    args.entity_type = _AGENT_ENTITY_TYPE
    if args.overseas:
        args.partner_type = _OVERSEAS_PARTNER_TYPE
        print("  🌏 [agent-fullday] 境外场景：partnerType 自动置为 3（境外非女娲）")
    print("  🏷  [agent-fullday] 代理商品：entityType=1（第三方渠道）")
    _run(args)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """向主解析器注册 agent-fullday 子命令（薄封装，复用 fullday 参数与流程）。"""
    p = subparsers.add_parser(
        "agent-fullday",
        help="代理商品端到端上单（entityType=1 第三方渠道；境内/境外，复用 fullday 流程）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    _add_arguments(p)
    # entity-type 由本命令语义固定，隐藏其 help 干扰但仍可被显式覆盖校验拦截
    p.set_defaults(func=_agent_run, entity_type=_AGENT_ENTITY_TYPE)

