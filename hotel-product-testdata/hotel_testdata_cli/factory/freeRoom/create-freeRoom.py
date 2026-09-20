#!/usr/bin/env python3
"""
闲置房充值（子产品生产，W10）

工具：rechargeV2（闲置房充值，HTTP 直连 EB 网关）
url：POST http://eb.hotel.test.sankuai.com/api/v1/ebooking/vacantHouse/rechargeV2
鉴权：Cookie ebbsid=<bsid>，由 tdm-cli 免密登录换取（tdm token blogin --skip-password -u <商家账号> --raw）

⚠️ 闲置房是"子产品"，依赖一个已成功上线的**母产品**（境内全日房，只有境内有闲置房场景），
   必须先按 W1（factory/fullday/create-fullday.py）创建母产品拿到 goodsId，再执行本脚本。

⚠️ 商家必须先开通资金池，否则接口返回"成功"但 data=null（假成功，充值被静默跳过）。
   本脚本对 data=null 会直接报错并提示开资金池命令；调用后自动用 mcoin countByParam 验证记录数。

⚠️ --recharge-scheme：0=先充值（需 Moka 估值 mock），1=先售卖（默认，无需 mock）。

前置依赖（首次使用需安装，见 SKILL.md 初始化章节）：
- merchant-testdata-cli（命令名 merchant-testdata-cli）：按 partnerId 查询商家账号登录名
- tdm-cli：商家免密登录换 bsid

使用方式：
  # 已知 login_name，跳过账号查询
  python3 create-freeRoom.py \\
    --poi-id 5142338 --partner-id 4374834 --customer-id 1026936262 \\
    --goods-id 411377656 --goods-name "张敏(测试房型)-不含早-入住当天18点前可付费取消-无延期大于四倍" \\
    --login-name merchant_test_xxx

  # 未提供 customer-id 时自动用工具464（partnerId → platformCustomerId）换算
  python3 create-freeRoom.py \\
    --poi-id 5142338 --partner-id 4374834 \\
    --goods-id 411377656 --goods-name "母产品商品名"

  # 仅打印参数，不实际调用
  python3 create-freeRoom.py --poi-id 5142338 --partner-id 4374834 --goods-id 411377656 --goods-name x --dry-run
"""

import argparse
import importlib.util as ilu
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


def _load_module(rel_path: str, name: str):
    spec = ilu.spec_from_file_location(name, os.path.join(ROOT, rel_path))
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_vh_iface = _load_module("interface/freeRoom/interface.py", "free_room_interface")
_infra_iface = _load_module("interface/infra/interface.py", "infra_interface")

build_recharge_body = _vh_iface.build_recharge_body
call_recharge_free_room = _vh_iface.call_recharge_free_room
count_free_room_records = _vh_iface.count_free_room_records
query_merchant_account = _vh_iface.query_merchant_account
ensure_account_registered = _vh_iface.ensure_account_registered
FreeRoomError = _vh_iface.FreeRoomError

call_transform_customer_id = _infra_iface.call_transform_customer_id

from scripts.du_runner import get_result  # noqa
from scripts.utils import get_operator  # noqa


def main():
    # ── 快速辅助命令 ─────────────────────────────────────────────────────────
    if "--show-schema" in sys.argv:
        schema_path = os.path.join(_SCRIPT_DIR, "schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            print(f.read())
        return

    # ── 参数解析 ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="闲置房充值（子产品生产，W10）")
    parser.add_argument("--poi-id", required=True, help="门店ID（poiId）")
    parser.add_argument("--partner-id", required=True, help="供应商ID（partnerId）")
    parser.add_argument("--customer-id", default=None,
                         help="客户ID（业务 customerId）。不传则自动用工具464由 partnerId 换算")
    parser.add_argument("--goods-id", required=True,
                         help="母产品 goodsId（须是已成功上线的境内全日房，见 W1）")
    parser.add_argument("--goods-name", required=True, help="母产品商品名（展示用）")
    parser.add_argument("--login-name", default=None,
                         help="已知商家账号登录名时直接传入，跳过 merchant-testdata-cli 账号查询")
    parser.add_argument("--pre-goods-id", default="", help="前置商品ID（默认空字符串）")
    parser.add_argument("--start-days", type=int, default=0, help="售卖开始：今天+N天（默认0）")
    parser.add_argument("--end-days", type=int, default=365, help="售卖结束：今天+N天（默认365）")
    parser.add_argument("--no-sell-rule", default="5,6,7", help="不可售规则（默认5,6,7）")
    parser.add_argument("--auto-re-purchase", action="store_true", help="是否自动复购（默认false）")
    parser.add_argument("--recharge-scheme", type=int, default=1,
                         help="充值方案：0=先充值（需 Moka 估值 mock），1=先售卖（默认，无需 mock）")
    parser.add_argument("--min", dest="min_num", type=int, default=3, help="单次充值最小间夜数（默认3）")
    parser.add_argument("--max", dest="max_num", type=int, default=20, help="单次充值最大间夜数（默认20）")
    parser.add_argument("--free-room-num", type=int, default=10, help="赠送房间数量（默认10）")
    parser.add_argument("--simple-value", type=int, default=10000, help="单价/分（默认10000）")
    parser.add_argument("--total-value", type=int, default=100000, help="总价值/分（默认100000）")
    parser.add_argument("--sale-on-holidays", type=int, default=1, help="节假日是否可售（默认1）")
    parser.add_argument("--daily-sale-threshold", type=int, default=-1, help="每日销售阈值（默认-1不限制）")
    parser.add_argument("--swimlane", default="", help="泳道名称（默认主干）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印参数，不实际调用")
    args = parser.parse_args()

    print("=== 闲置房充值（子产品生产，W10）===")
    print(f"  poiId       : {args.poi_id}")
    print(f"  partnerId   : {args.partner_id}")

    # customerId 未提供时，用工具464（客户ID互查）由 partnerId 换算 platformCustomerId
    customer_id = args.customer_id
    if not customer_id:
        print(f"  [自动换算] 未传 --customer-id，调用工具464 由 partnerId={args.partner_id} 换算 platformCustomerId ...")
        resp = call_transform_customer_id(
            origin_customer_id_str=str(args.partner_id),
            platform_customer_id_str=None,
            biz_line="3",
            dry_run=False,
        )
        customer_id = get_result(resp, "platformCustomerId")
        if not customer_id:
            print("[ERROR] 工具464 未返回 platformCustomerId，请手动通过 --customer-id 指定，完整响应：",
                  file=sys.stderr)
            print(json.dumps(resp, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(f"  [自动换算] customerId = {customer_id}")
    print(f"  customerId  : {customer_id}")
    print(f"  goodsId(母产品) : {args.goods_id}")
    print(f"  goodsName   : {args.goods_name}")

    body = build_recharge_body(
        poi_id=args.poi_id,
        partner_id=args.partner_id,
        customer_id=customer_id,
        goods_id=args.goods_id,
        goods_name=args.goods_name,
        start_time_days=args.start_days,
        end_time_days=args.end_days,
        no_sell_rule=args.no_sell_rule,
        auto_re_purchase=args.auto_re_purchase,
        recharge_scheme=args.recharge_scheme,
        min_num=args.min_num,
        max_num=args.max_num,
        free_room_num=args.free_room_num,
        simple_value=args.simple_value,
        total_value=args.total_value,
        pre_goods_id=args.pre_goods_id,
        sale_on_holidays=args.sale_on_holidays,
        daily_sale_threshold=args.daily_sale_threshold,
    )

    print(f"\n[请求体]\n{json.dumps(body, ensure_ascii=False, indent=2)}")

    # 商家账号：优先用户直接指定 --login-name，否则走 merchant-testdata-cli 按 partnerId 查询
    login_name = args.login_name
    if not login_name and not args.dry_run:
        print(f"\n[账号查询] 调用 merchant-testdata-cli 按 partnerId={args.partner_id} 查询商家账号 ...")
        try:
            account = query_merchant_account(str(args.partner_id))
        except FreeRoomError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            print("  → 若提示未录入测试账号管理平台，可执行：", file=sys.stderr)
            print(f"    merchant-testdata-cli hotel account --action add --partner-id {args.partner_id}", file=sys.stderr)
            sys.exit(1)
        login_name = account["login_name"]
        print(f"  login_name = {login_name}（mid={account.get('mid')}）")

    try:
        resp = call_recharge_free_room(
            body=body,
            login_name=login_name,
            partner_id=args.partner_id,
            swimlane=args.swimlane,
            dry_run=args.dry_run,
        )
    except FreeRoomError as e:
        print(f"[ERROR] 闲置房充值失败: {e}", file=sys.stderr)
        if e.detail:
            print(json.dumps(e.detail, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return

    print(f"\n[响应]\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    # 接口层已对 data=null 的假成功直接报错；走到这里说明 data 非空
    if resp.get("status") == 0 and resp.get("data"):
        # 调用后验证：mcoin countByParam 查置换记录数（partnerId + poiId）
        count = count_free_room_records(args.poi_id, args.partner_id, swimlane=args.swimlane)
        if count is not None and count > 0:
            print(f"\n✅ 闲置房充值成功：置换记录数 countByParam = {count}（已落库），子产品已生成。")
        elif count is not None:
            print("\n⚠️ 接口返回成功但置换记录数为 0，请到 EB 闲置房管理页或查日志人工核对。")
        else:
            print("\n✅ 接口返回成功（置换记录查询未通过，请到 EB 闲置房管理页人工核对）。")
    else:
        print(f"\n⚠️ 响应未明确标识成功（status={resp.get('status')}, data={resp.get('data')}），请人工核对响应体。")


if __name__ == "__main__":
    main()

