#!/usr/bin/env python3
"""
场景层：查询商品详情

接口：MeGoodsFacade#queryGoodsInfo
协议：Thrift RPC
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade
method：queryGoodsInfo

对应前端请求：
  POST /api/gw/v1/product/goods/queryGoodsInfo
  body: {"partnerId":4550589,"poiId":"1085927256096396","goodsIds":[600000673882]}

使用方式：
  # 查询单个商品
  python3 factory/ops/query-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000784334

  # 查询多个商品
  python3 factory/ops/query-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000784334 600000784335

  # 仅打印取消规则
  python3 factory/ops/query-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-ids 600000784334 --field rpCancelModel
"""

import argparse
import importlib.util as ilu
import json
import sys
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


def _load_interface():
    spec = ilu.spec_from_file_location(
        "fullday_interface",
        os.path.join(ROOT, "interface/fullday/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
query_goods_info = _iface.query_goods_info


def _show_schema():
    print("""=== 查询商品详情（query-goods）参数说明 ===

【必填参数】
  --partner-id    INT    供应商ID（partnerId）
  --poi-id        STR    门店ID（poiId）
  --goods-ids     INT+   商品ID列表，空格分隔，如：600000784334 600000784335

【可选参数】
  --swimlane      STR    泳道名称（不传=主干）
  --field         STR    只打印指定字段，常用值：
                           rpCancelModel      取消规则
                           rpBreakFastModel   早餐规则
                           rpGuaranteeModel   担保规则
                           goodsBaseInfo      商品基础信息
                           priceInfo          价格信息
  --raw                  打印完整原始 JSON（不做摘要）

【输出字段说明（默认摘要模式）】
  goodsId         商品ID
  goodsName       商品名称
  goodsStatus     商品状态（2=在线 3=下线 8=废除）
  goodsType       商品类型（1=全日房 2=钟点房）
  paymentType     付款类型（0=预付 1=现付担保 2=现付非担保）
  contractNo      合同编号
  roomId          房型ID
  roomName        房型名称
  rpCancelModel   取消规则（cancelItemType: 0=不可取消 1=可取消）
  rpBreakFastModel 早餐规则（num: 0=无 1=单份 2=双份）

【使用示例】
  # 查询单个商品（默认摘要）
  python3 factory/ops/query-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000784334

  # 只打印取消规则
  python3 factory/ops/query-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000784334 --field rpCancelModel

  # 打印完整原始 JSON
  python3 factory/ops/query-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-ids 600000784334 --raw
""")


def _print_goods_summary(goods: dict) -> None:
    """打印商品核心信息摘要。"""
    base  = goods.get("goodsBaseInfo") or {}
    rp    = goods.get("rpInfo") or {}
    room  = goods.get("roomInfo") or {}

    print(f"\n  goodsId     : {base.get('goodsId')}")
    print(f"  goodsName   : {base.get('goodsName')}")
    print(f"  goodsStatus : {base.get('goodsStatus')}  (2=在线 3=下线 8=废除)")
    print(f"  goodsType   : {base.get('goodsType')}  (1=全日房 2=钟点房)")
    print(f"  paymentType : {base.get('paymentType')}  (0=预付 1=现付担保 2=现付非担保)")
    print(f"  contractNo  : {base.get('contractNo')}")
    print(f"  roomId      : {room.get('roomId')}  roomName: {room.get('roomName')}")

    # 取消规则
    cancel = rp.get("rpCancelModel") or {}
    normal_cancel  = cancel.get("normalRule") or {}
    weekend_cancel = cancel.get("weekendRule")
    print(f"\n  【取消规则】")
    print(f"    normalRule  cancelItemType={normal_cancel.get('cancelItemType')}  "
          f"(0=不可取消 1=可取消)")
    if normal_cancel.get("cancelItemType") == 1:
        print(f"              moveUpCancelDays={normal_cancel.get('moveUpCancelDays')}  "
              f"moveUpCancelHour={normal_cancel.get('moveUpCancelHour')}")
    if weekend_cancel is not None:
        print(f"    weekendRule cancelItemType={weekend_cancel.get('cancelItemType')}  "
              f"(0=不可取消 1=可取消)")
        if weekend_cancel.get("cancelItemType") == 1:
            print(f"              moveUpCancelDays={weekend_cancel.get('moveUpCancelDays')}  "
                  f"moveUpCancelHour={weekend_cancel.get('moveUpCancelHour')}")
    else:
        print(f"    weekendRule (null，平日周末相同)")

    # 早餐规则
    breakfast = rp.get("rpBreakFastModel") or {}
    normal_bf  = (breakfast.get("normalRule") or {})
    weekend_bf = breakfast.get("weekendRule")
    print(f"\n  【早餐规则】")
    print(f"    normalRule  num={normal_bf.get('num')}  (0=无 1=单份 2=双份)")
    if weekend_bf is not None:
        print(f"    weekendRule num={weekend_bf.get('num')}")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="查询商品详情（MeGoodsFacade#queryGoodsInfo）")
    parser.add_argument("--partner-id", required=True, type=int, help="供应商ID（partnerId）")
    parser.add_argument("--poi-id",     required=True,            help="门店ID（poiId）")
    parser.add_argument("--goods-ids",  required=True, type=int, nargs="+",
                        help="商品ID列表，空格分隔，如 600000784334 600000784335")
    parser.add_argument("--swimlane",   default="", help="泳道（默认主干）")
    parser.add_argument("--field",      default="", help="只打印指定字段，如 rpCancelModel / rpBreakFastModel")
    parser.add_argument("--raw",        action="store_true", help="打印完整原始返回（JSON）")
    args = parser.parse_args()

    print(f"=== 查询商品详情（queryGoodsInfo）===")
    print(f"  partnerId : {args.partner_id}")
    print(f"  poiId     : {args.poi_id}")
    print(f"  goodsIds  : {args.goods_ids}")
    print(f"  swimlane  : {args.swimlane or '主干'}")

    resp = query_goods_info(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        goods_ids=args.goods_ids,
        swimlane=args.swimlane,
    )

    # 业务错误检查
    if not resp.get("success", True):
        err = resp.get("error") or {}
        msg = err.get("msg") if isinstance(err, dict) else str(err)
        print(f"\n❌ 查询失败：{msg or resp}", file=sys.stderr)
        sys.exit(1)

    goods_list = resp.get("data") or []
    if not goods_list:
        print("\n⚠️  未查到任何商品（data 为空）")
        sys.exit(0)

    # --raw：打印完整原始 JSON
    if args.raw:
        print(f"\n原始返回：\n{json.dumps(resp, ensure_ascii=False, indent=2)}")
        return

    # --field：只打印指定字段
    if args.field:
        for goods in goods_list:
            gid  = (goods.get("goodsBaseInfo") or {}).get("goodsId", "?")
            rp   = goods.get("rpInfo") or {}
            base = goods.get("goodsBaseInfo") or {}
            # 优先从 rpInfo 找，其次从 goodsBaseInfo 找
            val  = rp.get(args.field) or base.get(args.field)
            print(f"\n  goodsId={gid}  {args.field}=")
            print(f"  {json.dumps(val, ensure_ascii=False, indent=4)}")
        return

    # 默认：打印摘要
    print(f"\n共查到 {len(goods_list)} 个商品：")
    for goods in goods_list:
        _print_goods_summary(goods)

    print()


if __name__ == "__main__":
    main()

