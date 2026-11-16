#!/usr/bin/env python3
"""
运维操作 - 废除商品

接口：MeGoodsFacade#destroyGoods
协议：Thrift RPC
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade
method：destroyGoods

对应历史 HTTP 入口（已标记 INVALID_METHOD_5，遗留接口，不使用）：
  POST /api/gw/v1/product/goods/destroyGoods
  body: {"poiId":"93492913","partnerId":4357960,"reason":"test","goodsId":1038993392,"preGoodsId":"..."}

⚠️ 服务端强约束：仅"暂停/下线"状态（goodsStatus=3）的商品才能废除，
   在线商品（goodsStatus=2）直接调用会报「仅暂停状态产品，才可以废除」。
   本脚本默认要求商品已下线；可加 --auto-offline 让脚本先调用
   batchOnlineSwitch（status=3）下线，再执行废除。

⚠️ 废除操作不可逆（goodsStatus=8），请勿对非测试数据误用。

使用方式：
  # 废除已下线的商品
  python3 destroy-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-id 600000632131

  # 商品仍在线时，先自动下线再废除
  python3 destroy-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-id 600000632131 --auto-offline

  # 自定义废除原因
  python3 destroy-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-id 600000632131 --reason "测试数据清理"

  # 仅打印参数不执行（dry-run）
  python3 destroy-goods.py --partner-id 4550589 --poi-id 1085927256096396 --goods-id 600000632131 --dry-run
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
        "ops_interface",
        os.path.join(ROOT, "interface/ops/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
call_destroy_goods      = _iface.call_destroy_goods
call_online_switch      = _iface.call_online_switch
DEFAULT_DESTROY_REASON  = _iface.DEFAULT_DESTROY_REASON


def _show_schema():
    print(f"""=== 废除商品（destroy-goods）参数说明 ===

接口：MeGoodsFacade#destroyGoods（Thrift）
appkey ：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade
method ：destroyGoods

【必填参数】
  --partner-id    INT    供应商ID（partnerId）
  --poi-id        STR    门店ID（poiId，字符串格式）
  --goods-id      INT    商品ID（goodsId）；与 --pre-goods-id 至少传一个

【可选参数】
  --pre-goods-id  STR    预产品ID（preGoodsId）；与 --goods-id 至少传一个
  --reason        STR    废除原因（默认："{DEFAULT_DESTROY_REASON}"）
  --auto-offline         废除前自动先下线商品（调用 batchOnlineSwitch status=3）
  --swimlane      STR    泳道名称（不传=主干）
  --dry-run              仅打印参数，不执行

【重要约束】
  ⚠️ 仅"暂停/下线"状态（goodsStatus=3）的商品才能废除。
     在线商品（goodsStatus=2）直接调用会报「仅暂停状态产品，才可以废除」。
     商品必须先下线，若不确定当前状态，加 --auto-offline 让脚本自动处理。
  ⚠️ 废除（goodsStatus=8）为不可逆操作，请勿对非测试数据误用。
  ⚠️ 下线动作在特定条件下（如该商品是门店/战区下最后一个在线商品）
     可能触发人工审批流程（PrepayGoodsOfflineAuditProcess），
     此时 --auto-offline 下线会失败或长期停留在"审核中"，
     构造测试数据时建议保证门店下有其他在线商品，避免触发审批。

【使用示例】
  # 废除已处于下线状态的商品
  python3 factory/ops/destroy-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131

  # 商品仍在线，先自动下线再废除
  python3 factory/ops/destroy-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131 --auto-offline

  # dry-run 仅查看参数
  python3 factory/ops/destroy-goods.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131 --dry-run
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="废除商品（MeGoodsFacade#destroyGoods）")
    parser.add_argument("--partner-id",   required=True, type=int, help="供应商ID（partnerId）")
    parser.add_argument("--poi-id",       required=True,            help="门店ID（poiId，字符串）")
    parser.add_argument("--goods-id",     default=None, type=int,  help="商品ID（goodsId），与 --pre-goods-id 至少传一个")
    parser.add_argument("--pre-goods-id", default=None,             help="预产品ID（preGoodsId），与 --goods-id 至少传一个")
    parser.add_argument("--reason",       default=DEFAULT_DESTROY_REASON, help="废除原因")
    parser.add_argument("--auto-offline", action="store_true",
                        help="废除前自动先下线商品（batchOnlineSwitch status=3）")
    parser.add_argument("--swimlane",     default="", help="泳道（默认主干）")
    parser.add_argument("--dry-run",      action="store_true", help="仅打印参数不执行")
    args = parser.parse_args()

    if args.goods_id is None and not args.pre_goods_id:
        print("[ERROR] --goods-id 和 --pre-goods-id 至少传一个", file=sys.stderr)
        sys.exit(1)

    print("=== 废除商品（destroyGoods）===")
    print(f"  partnerId   : {args.partner_id}")
    print(f"  poiId       : {args.poi_id}")
    print(f"  goodsId     : {args.goods_id}")
    print(f"  preGoodsId  : {args.pre_goods_id}")
    print(f"  reason      : {args.reason}")
    print(f"  swimlane    : {args.swimlane or '主干'}")
    print(f"  autoOffline : {args.auto_offline}")

    # ── 可选：先下线 ──────────────────────────────────────────────────────
    if args.auto_offline:
        if args.goods_id is None:
            print("\n[ERROR] --auto-offline 需要提供 --goods-id（preGoodsId 无法用于下线接口）", file=sys.stderr)
            sys.exit(1)

        print("\n── Step 1: 自动下线（batchOnlineSwitch status=3）──────────────")
        switch_resp = call_online_switch(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            goods_ids=[args.goods_id],
            status=3,
            swimlane=args.swimlane,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            sw_data = switch_resp.get("data") or {}
            if sw_data.get("failCount", 0) > 0 or sw_data.get("successCount", 0) == 0:
                details = sw_data.get("details") or []
                reason = details[0].get("reason", "未知原因") if details else "未知原因"
                print(f"\n❌ 自动下线失败：{reason}", file=sys.stderr)
                print("   若原因含「审核」字样，说明该商品下线触发了人工审批流程，", file=sys.stderr)
                print("   无法通过脚本自动完成，请更换测试商品或等待审批通过后重试。", file=sys.stderr)
                sys.exit(1)
            print("  ✅ 下线成功")
        print("\n── Step 2: 废除商品（destroyGoods）──────────────────────────")

    # ── 废除 ──────────────────────────────────────────────────────────────
    resp = call_destroy_goods(
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        goods_id=args.goods_id,
        pre_goods_id=args.pre_goods_id,
        reason=args.reason,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    print(f"\n原始返回：\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    data = resp.get("data")
    if data is True or resp.get("success") is True:
        print(f"\n✅ 废除成功  goodsId={args.goods_id}")
    else:
        print(f"\n❌ 废除失败：{resp}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

