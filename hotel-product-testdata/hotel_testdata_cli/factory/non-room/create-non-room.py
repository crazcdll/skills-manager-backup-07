#!/usr/bin/env python3
"""
商品构造 - 创建非房商品（xGoods）

服务：com.sankuai.hotel.biz.platform
接口：MeResourceFacade#submitXgoods
协议：Thrift RPC 直调（同步，直接返回 xGoodsId）

前置：供应商（partnerId）+ 门店（poiId）已存在

使用方式：
  # 创建非房（默认餐饮类型）
  python3 create-non-room.py --partner-id 4549232 --poi-id 1085918666100285

  # 创建景点/门票类型
  python3 create-non-room.py --partner-id 4549232 --poi-id 1085918666100285 --type scenic

  # 创建玩乐/一日游类型
  python3 create-non-room.py --partner-id 4549232 --poi-id 1085918666100285 --type tour

  # 自定义商品名（⚠️ 不超过 20 字符）
  python3 create-non-room.py --partner-id 4549232 --poi-id 123 \
      --product-name 早餐券

  # 指定泳道
  python3 create-non-room.py --partner-id 4549232 --poi-id 123 --swimlane xxx

  # 查看字段说明
  python3 create-non-room.py --show-schema

  # 仅打印参数不执行
  python3 create-non-room.py --partner-id 4549232 --poi-id 123 --dry-run
"""

import argparse
import importlib.util as ilu
import sys
import os
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)

# interface/non-room 目录名含连字符，不能用普通 import，用 importlib 动态加载
def _load_interface():
    spec = ilu.spec_from_file_location(
        "nonroom_interface",
        os.path.join(ROOT, "interface/non-room/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_iface = _load_interface()

from scripts.utils import get_operator  # noqa


MTA_LINK = "https://mta.hotel.test.sankuai.com/v2/index.html#/non-room/list"


def _show_schema():
    print("""=== 非房商品（xGoods）创建参数说明 ===

服务：com.sankuai.hotel.biz.platform
接口：MeResourceFacade#submitXgoods（同步，直接返回 xGoodsId）

【必填参数】
  --partner-id   STR  供应商ID
  --poi-id       STR  门店ID（单门店）

【可选参数】
  --type         STR  商品类型模板：catering（餐饮，默认）| scenic（景点/门票）| tour（玩乐/一日游）
  --product-name STR  商品名称（默认：<mis>非房_<时间戳后5位>；⚠️ 不能超过 20 字符）
  --swimlane     STR  泳道名称（默认主干）
  --dry-run          仅打印参数，不执行

【注意事项】
  ✅ 同步接口，直接返回 xGoodsId，无需等待大象推送
  ⚠️ 创建成功后需通过 factory/audit/non-room/audit.py 完成审核才可上线

【使用示例】
  # 餐饮类（默认）
  python3 factory/non-room/create-non-room.py \\
    --partner-id 4549232 --poi-id 1085918666100285

  # 景点/门票类
  python3 factory/non-room/create-non-room.py \\
    --partner-id 4549232 --poi-id 1085918666100285 --type scenic

  # 玩乐/一日游类
  python3 factory/non-room/create-non-room.py \\
    --partner-id 4549232 --poi-id 1085918666100285 --type tour

  # 指定泳道
  python3 factory/non-room/create-non-room.py \\
    --partner-id 4549232 --poi-id 1085918666100285 --swimlane xxx
""")


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="创建非房商品（xGoods）- 直接 RPC")
    parser.add_argument("--partner-id", required=True, help="供应商ID（partnerId）")
    parser.add_argument("--poi-id", required=True, help="门店ID（poiId）")
    parser.add_argument("--type", default="catering",
                        choices=["catering", "scenic", "tour"],
                        help="商品类型模板：catering=餐饮（默认）| scenic=景点/门票 | tour=玩乐/一日游")
    parser.add_argument("--product-name", default=None,
                        help="商品名称（默认：<mis>非房_<时间戳后5位>；不超过 20 字符）")
    parser.add_argument("--swimlane", default="", help="泳道名称（默认主干）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    operator = get_operator()
    # ⚠️ name 限制 20 字符：<mis>非房_<后5位时间戳> = len(mis)+4+5，mis超11字符时截断前缀
    _ts = str(int(time.time()))[-5:]
    _prefix = operator[:11] if len(operator) > 11 else operator
    product_name = args.product_name or f"{_prefix}非房_{_ts}"

    TYPE_LABEL = {"catering": "餐饮", "scenic": "景点/门票", "tour": "玩乐/一日游"}
    print(f"\n=== 创建非房（MeResourceFacade#submitXgoods）===")
    print(f"  partnerId  : {args.partner_id}")
    print(f"  poiId      : {args.poi_id}")
    print(f"  类型       : {args.type}（{TYPE_LABEL.get(args.type, args.type)}）")
    print(f"  商品名称   : {product_name}")
    print(f"  泳道       : {args.swimlane or '主干'}")

    resp = _iface.call(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        product_name=product_name,
        xgoods_type=args.type,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    # 从响应中提取 xGoodsId
    xgoods_id = (
        resp.get("xGoodsId")
        or resp.get("xgoodsId")
        or resp.get("id")
        or resp.get("data")
    )
    if xgoods_id:
        print(f"\n✅ 非房创建成功")
    else:
        print(f"\n⚠️  非房创建完成，xGoodsId 未在响应中找到，请检查原始返回")

    print(f"\n{'='*50}")
    print(f"  📋 构造结果汇总（非房）")
    print(f"{'='*50}")
    print(f"  partnerId : {args.partner_id}")
    print(f"  poiId     : {args.poi_id}")
    print(f"  商品名称  : {product_name}")
    print(f"  xGoodsId  : {xgoods_id or '(请查看原始响应)'}")
    print(f"  MTA查询   : {MTA_LINK}?partnerId={args.partner_id}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

