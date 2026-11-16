#!/usr/bin/env python3
"""
场景层：查询超团 SPU 详情（含在线状态）

接口：MeResourceFacade#getSpuDetail(Long partnerId, Long spuId, Boolean needQueryUniversalImage)
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
method：getSpuDetail
返回：MeBaseResult<SpuModel>

⚠️ 与 MeResourceFacade#querySpuListPage 的关键区别：
  querySpuListPage 按 partnerId+poiId+spuType 分页查询，对超团（spuType=1）
  查询不可靠，实测恒返回 totalCount=0、list=[]，不能用它验证超团入库/上线。
  getSpuDetail 按 partnerId+spuId 精确查询单条 SPU，是超团验证在线状态的
  可靠方式，非通兑/通兑超团（乃至套餐）均可使用。

使用方式：
  # 查询超团详情（默认摘要模式）
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705

  # 打印完整原始 JSON
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705 --raw

  # 定时重试直到查到数据（入库有异步延迟时使用，最多重试 8 次，每次间隔 15s）
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705 --wait
"""

import argparse
import importlib.util as ilu
import json
import sys
import os
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


def _load_interface():
    spec = ilu.spec_from_file_location(
        "super_deal_interface",
        os.path.join(ROOT, "interface/super-deal/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
get_spu_detail = _iface.get_spu_detail


def _show_schema():
    print("""=== 查询超团 SPU 详情（query-spu）参数说明 ===

接口：MeResourceFacade#getSpuDetail（Thrift RPC 直调，与 submitSpu 共用同一
已注册 OCTO 的 MeResourceFacade）

【必填参数】
  --partner-id    INT    供应商ID（partnerId）
  --spu-id        INT    超团/套餐 SPU ID（submitSpu 返回的 spuId）

【可选参数】
  --swimlane      STR    泳道名称（不传=主干）
  --need-universal-image  是否需要查询通兑图片（默认 false）
  --raw                   打印完整原始 JSON（不做摘要）
  --wait                  查不到/未上线时自动重试（最多 8 次，每次间隔 15s，约 2 分钟）

【为什么不用 querySpuListPage】
  querySpuListPage 按 partnerId+poiId+spuType 分页查询，对超团（spuType=1）
  查询不可靠，实测无论传不传 spuId、加不加 onLineStatus 过滤，均恒返回
  totalCount=0、list=[]（RPC 本身成功，只是查不出数据）。
  getSpuDetail 按 partnerId+spuId 精确查询单条 SPU，实测能正确返回超团完整
  详情（含关联的全日房/非房、审核状态、魔盒ID等），是更可靠的验证方式。

【输出字段说明（默认摘要模式）】
  spuId           SPU ID
  status          SPU 在线状态：0=下架 1=上架 2=归档
  submitStatus    提交状态
  spuExchangeType 超团兑换类型：0=通兑 1=非通兑（仅超团有效）
  auditStatus     基础信息审核状态（spuAuditModel.auditStatus）
  couponAuditStatus / giftCardAuditStatus / sieveAuditStatus  超团各子模块审核状态（均为4代表通过）
  mboxId          魔盒ID（非空代表魔盒已生成）
  relatedGoodsList 关联的全日房/直连商品列表（goodsId + goodsName + status）

【使用示例】
  # 查询超团详情（默认摘要）
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705

  # 打印完整原始 JSON（用于排查具体字段）
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705 --raw

  # 创建后异步入库延迟场景：自动重试直到查到数据
  python3 factory/super-deal/query-spu.py --partner-id 4571710 --spu-id 2257202705 --wait
""")


def _print_summary(data: dict) -> None:
    base = data.get("spuBaseModel") or {}
    audit = data.get("spuAuditModel") or {}
    super_deal = data.get("superDealModel") or {}
    sd_base = super_deal.get("superDealBaseModel") or {}
    coupon = super_deal.get("superDealCouponModel") or {}
    gift_card = coupon.get("superDealGiftCardModel") or {}
    sieve = coupon.get("superDealSieveModel") or {}
    related_goods = data.get("relatedGoodsList") or []

    print(f"\n  spuId           : {base.get('spuId')}")
    print(f"  status          : {base.get('status')}  (0=下架 1=上架 2=归档)")
    print(f"  submitStatus    : {base.get('submitStatus')}")
    print(f"  title           : {base.get('title')}")
    print(f"  partnerId       : {base.get('partnerId')}")
    print(f"  poiId           : {base.get('poiId')}")
    print(f"  autoPublish     : {base.get('autoPublish')}")
    print(f"  spuExchangeType : {sd_base.get('spuExchangeType')}  (0=通兑 1=非通兑)")

    print(f"\n  【审核状态】")
    print(f"    spuAuditModel.auditStatus     : {audit.get('auditStatus')}")
    print(f"    superDealCouponModel.couponAuditStatus  : {coupon.get('couponAuditStatus')}  (4=通过)")
    print(f"    superDealGiftCardModel.giftCardAuditStatus : {gift_card.get('giftCardAuditStatus')}  (4=通过)")
    print(f"    superDealSieveModel.sieveAuditStatus    : {sieve.get('sieveAuditStatus')}  (4=通过)")
    print(f"    mboxId (魔盒ID)                : {coupon.get('mboxId')}  (非空代表魔盒已生成)")

    if related_goods:
        print(f"\n  【关联商品 relatedGoodsList】")
        for item in related_goods:
            print(f"    goodsId={item.get('goodsId')}  status={item.get('status')}  "
                  f"poiId={item.get('poiId')}  goodsName={item.get('goodsName')}")


def main():
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="查询超团 SPU 详情（MeResourceFacade#getSpuDetail）")
    parser.add_argument("--partner-id", required=True, type=int, help="供应商ID（partnerId）")
    parser.add_argument("--spu-id",     required=True, type=int, help="SPU ID（submitSpu 返回的 spuId）")
    parser.add_argument("--need-universal-image", action="store_true", help="是否查询通兑图片（默认 false）")
    parser.add_argument("--swimlane",   default="", help="泳道（默认主干）")
    parser.add_argument("--raw",        action="store_true", help="打印完整原始返回（JSON）")
    parser.add_argument("--wait",       action="store_true",
                         help="查不到/data为空时自动重试（最多8次，每次间隔15s，约2分钟），用于覆盖异步入库延迟")
    args = parser.parse_args()

    print("=== 查询超团 SPU 详情（getSpuDetail）===")
    print(f"  partnerId : {args.partner_id}")
    print(f"  spuId     : {args.spu_id}")
    print(f"  swimlane  : {args.swimlane or '主干'}")

    max_retries = 8 if args.wait else 1
    resp = None
    for attempt in range(1, max_retries + 1):
        resp = get_spu_detail(
            partner_id=args.partner_id,
            spu_id=args.spu_id,
            need_query_universal_image=args.need_universal_image,
            swimlane=args.swimlane,
        )
        data = resp.get("data")
        if isinstance(data, dict) and data.get("spuBaseModel"):
            break
        if attempt < max_retries:
            print(f"  ⏳ 尚未查到 SPU 数据（第{attempt}/{max_retries}次），等待15s后重试...")
            time.sleep(15)

    data = (resp or {}).get("data")
    if not isinstance(data, dict) or not data.get("spuBaseModel"):
        print(f"\n❌ 未查到 spuId={args.spu_id} 的详情，原始响应：")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        sys.exit(1)

    if args.raw:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    else:
        _print_summary(data)


if __name__ == "__main__":
    main()

