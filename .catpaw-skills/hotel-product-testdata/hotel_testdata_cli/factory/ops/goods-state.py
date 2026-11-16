#!/usr/bin/env python3
"""
运维操作 - 对已有商品设置特殊状态
入口：factory/ops/goods-state.py

将「创建商品」与「设置特殊状态」完全解耦：
  - create-fullday.py / create-hourly.py 只负责创建商品 + 正常上线
  - 本脚本独立对「已上线的现有商品」做状态变更，不依赖建品流程

支持的 --state 值：

  【产品状态（由 goods_product_ops 处理）】
  offline              → 对已上线商品调用 batchOnlineSwitch(status=3) 下线（goodsStatus=3，可逆）
  abolish              → 下线 → destroyGoods（goodsStatus=8，不可逆）

  【价格状态（由 goods_price_ops 处理）】
  merchant-auditing    → 对已上线商品改价5倍触发商家价格审核（待 BD 审核）
  merchant-audit-rejected → 同上 + 主动执行商家审核驳回
  BD-auditing          → 对已上线商品以 BD 身份改价5倍触发 BD 价格审核（默认使用全局固定测试账号，已实测）
  BD-audit-rejected    → 同上 + 主动执行 BD 审核驳回

  【库存/房态状态（由 goods_inventory_ops 处理）】
  b-closed             → 房型维度：将指定日期范围关房（invSwitch=0），保留非零库存余量（默认299），需 --room-id --goods-type
  b-full               → 房型维度：将指定日期范围库存置0（开房但满房，invSwitch=1 + 库存0），需 --room-id --goods-type
  b-closed-goods       → 产品维度：同 b-closed，但按 --goods-id 直接操作（changeType=2），需门店已切换为产品维度
  b-full-goods         → 产品维度：同 b-full，但按 --goods-id 直接操作（changeType=2），需门店已切换为产品维度

=== 使用示例 ===

# 1. 废除商品（下线 + destroyGoods）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state abolish

# 2. 触发商家价格审核（商品须已上线，当前售价=200元则改价到1000元触发审核）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state merchant-auditing \\
  --current-price-yuan 200.0

# 3. 触发商家价格审核 + 主动驳回
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state merchant-audit-rejected \\
  --current-price-yuan 200.0

# 3.5 触发 BD 价格审核（BD 身份改价，默认使用全局固定测试账号 crstest，无需传
#     --bd-sso-user/--bd-sso-password；若需要换账号可显式传覆盖）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state BD-auditing \\
  --current-price-yuan 200.0 --audit-reason "测试数据构造"

# 3.6 指定日期段触发商家价格审核（仅 2026-09-01~2026-09-05 这段日期进入审核，非整商品）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state merchant-auditing \\
  --current-price-yuan 200.0 --start-date 2026-09-01 --end-date 2026-09-05

# 4. B端关房（将未来两年的房态设置为关房，库存余量默认保留299，体现"有库存但关房"）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state b-closed \\
  --room-id 77671480 --goods-type 1

# 4.1 B端关房 + 自定义保留库存余量
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state b-closed \\
  --room-id 77671480 --goods-type 1 --limit-change-value 100

# 5. B端满房（将未来两年的库存余量置0）
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state b-full \\
  --room-id 77671480 --goods-type 2

# 5.1 产品维度关房（门店已通过 change-room-status-dimension.py 切换为产品维度后才可用，
#     不需要 --room-id，直接按 --goods-id 操作）
python3 factory/ops/goods-state.py \\
  --partner-id 4576342 --poi-id 1090269458133536 \\
  --goods-id 600000632131 --state b-closed-goods

# 5.2 产品维度满房
python3 factory/ops/goods-state.py \\
  --partner-id 4576342 --poi-id 1090269458133536 \\
  --goods-id 600000632131 --state b-full-goods

# 6. 泳道支持
python3 factory/ops/goods-state.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --goods-id 600000632131 --state abolish \\
  --swimlane user-zhangsan

注意：
  - merchant-auditing / merchant-audit-rejected / BD-auditing / BD-audit-rejected
    需传 --current-price-yuan（当前售价，单位元）
    若不传则使用默认值（全日房200元，钟点房80元，通过 --goods-type 区分）
  - merchant-auditing / merchant-audit-rejected 可选传 --start-date / --end-date 指定
    改价/审核生效的日期段（不传默认仅当天）。⚠️ 商家改价审核已实测确认是**按此日期段**
    进入审核（非整商品）。BD-auditing / BD-audit-rejected 也支持传同样参数，具体是否
    整商品进审待用真实 BD 账号重新验证（旧结论基于已证伪的方案）。
  - BD-auditing / BD-audit-rejected 默认使用全局固定测试账号 crstest（不按 partnerId 绑定
    权限，已实测），无需传 --bd-sso-user / --bd-sso-password；如需换用其他 BD 账号可显式
    传这两个参数覆盖，可选传 --bd-client-id / --bd-client-secret / --audit-reason
    （不传 audit-reason 默认"测试数据构造"）
  - b-closed / b-full 需传 --room-id 和 --goods-type（1=全日房，2=钟点房）
  - b-closed 可选传 --limit-change-value 自定义关房期间保留的库存余量（默认299，
    必须>0 才能体现"有库存但关房"）；b-full 库存固定为0，不受此参数影响
  - b-closed-goods / b-full-goods 是「产品维度」版本，不需要 --room-id/--goods-type，
    直接用 --goods-id 操作；⚠️ 仅当门店已通过
    factory/inventory/change-room-status-dimension.py 切换为产品维度后才生效，
    未切换维度的门店调用大概率会被后端拒绝或不生效
  - abolish 不需要额外参数
"""

import argparse
import importlib.util as ilu
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# ops/ 目录在 factory/ 下，往上两级是 hotel_testdata_cli/
_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
_FACTORY_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "../"))
sys.path.insert(0, _ROOT)


# ════════════════════════════════════════════════════════════════════════════
# 模块加载
# ════════════════════════════════════════════════════════════════════════════

def _load_goods_state_module(name: str):
    """懒加载 factory/goods-state/ 下的子模块。"""
    path = os.path.join(_FACTORY_DIR, f"goods-state/{name}.py")
    spec = ilu.spec_from_file_location(name, path)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_fullday_iface():
    """加载全日房 interface（含 query_goods_info / _load_ops_interface 等方法）。"""
    spec = ilu.spec_from_file_location(
        "goods_interface",
        os.path.join(_ROOT, "interface/fullday/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ════════════════════════════════════════════════════════════════════════════
# 参数解析
# ════════════════════════════════════════════════════════════════════════════

_PRODUCT_STATES   = {"offline", "abolish"}
_PRICE_STATES     = {"merchant-auditing", "merchant-audit-rejected",
                     "BD-auditing", "BD-audit-rejected"}
_INVENTORY_STATES_ROOM  = {"b-closed", "b-full"}       # 房型维度（changeType=1）
_INVENTORY_STATES_GOODS = {"b-closed-goods", "b-full-goods"}  # 产品维度（changeType=2）
_INVENTORY_STATES = _INVENTORY_STATES_ROOM | _INVENTORY_STATES_GOODS

_ALL_STATES = _PRODUCT_STATES | _PRICE_STATES | _INVENTORY_STATES

# 产品维度 state → 房型维度 state 的映射（复用同一套 apply_inventory_state 处理逻辑）
_GOODS_DIM_STATE_MAP = {
    "b-closed-goods": "b-closed",
    "b-full-goods":   "b-full",
}


def _show_schema():
    print("""=== 商品状态变更（goods-state）参数说明 ===

【必填参数】
  --partner-id      STR    供应商ID
  --poi-id          STR    门店ID
  --goods-id        STR    目标商品ID（goodsId）
  --state           STR    目标状态（见下方枚举）

【状态枚举】
  产品状态（goods_product_ops）：
    offline              下线（batchOnlineSwitch status=3，goodsStatus=3，可逆）
    abolish              下线 + 废除（goodsStatus=8，不可逆）

  价格状态（goods_price_ops）：
    merchant-auditing    对已上线商品改价5倍触发商家价格审核（待 BD 审核）
    merchant-audit-rejected  同上 + 主动执行商家审核驳回
    BD-auditing          对已上线商品以 BD 身份改价5倍触发 BD 价格审核（默认使用全局固定测试账号 crstest，已实测）
    BD-audit-rejected    同上 + 主动执行 BD 审核驳回

  库存/房态状态（goods_inventory_ops）：
    b-closed             房型维度关房，保留非零库存（invSwitch=0 + limitChangeValue默认299，需传 --room-id --goods-type）
    b-full               房型维度满房，库存余量置0（invSwitch=1 + limitChangeValue=0，需传 --room-id --goods-type）
    b-closed-goods       产品维度关房，同 b-closed 但直接按 --goods-id 操作（changeType=2），需门店已切换为产品维度
    b-full-goods         产品维度满房，同 b-full 但直接按 --goods-id 操作（changeType=2），需门店已切换为产品维度

【可选参数】
  --current-price-yuan  FLOAT  当前售价（元），merchant-auditing/merchant-audit-rejected/
                               BD-auditing/BD-audit-rejected 需要
                               不传则根据 --goods-type 使用默认值（全日房200元/钟点房80元）
  --goods-type          INT    商品类型：1=全日房（默认）  2=钟点房
                               影响：① 价格状态默认售价  ② 库存状态 day/hour_room_ids 选择
  --room-id             INT    逻辑房型ID（b-closed / b-full 必填；b-closed-goods / b-full-goods 不需要）
  --start-date          STR    两种用途：
                               1) b-closed/b-full：库存/房态修改起始日期（默认今天）
                               2) merchant-auditing/merchant-audit-rejected/BD-auditing/
                                  BD-audit-rejected：改价生效开始日期（默认今天）。
                                  ⚠️ 商家审核已实测按此日期段进入审核，BD 审核是否
                                  整商品待重新验证
  --end-date            STR    对应 --start-date 的结束日期（b-closed/b-full 默认两年后，
                               价格状态默认=--start-date）
  --bd-sso-user         STR    BD 员工 SSO 账号（mis，仅 BD-auditing/BD-audit-rejected 生效，
                               不传默认使用全局固定测试账号 crstest，已实测）
  --bd-sso-password     STR    BD 员工 SSO 密码（仅 BD-auditing/BD-audit-rejected 生效，不传默认 Ceshi123）
  --bd-client-id        STR    SSO 客户端 ID（可选，不传默认 hotel_sc）
  --bd-client-secret    STR    SSO 客户端密钥（可选，不传用默认值）
  --audit-reason        STR    BD 改价审核理由（仅 BD-auditing/BD-audit-rejected 生效，默认"测试数据构造"）
  --swimlane            STR    泳道名称（不传=主干）

【使用示例】
  # 废除商品
  python3 factory/ops/goods-state.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131 --state abolish

  # 触发商家价格审核（当前售价200元）
  python3 factory/ops/goods-state.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131 --state merchant-auditing \\
    --current-price-yuan 200.0

    # 全日房关房
  python3 factory/ops/goods-state.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --goods-id 600000632131 --state b-closed \\
    --room-id 77671480 --goods-type 1

  # 产品维度关房（门店已切换为产品维度后才可用，不需要 --room-id）
  python3 factory/ops/goods-state.py \\
    --partner-id 4576342 --poi-id 1090269458133536 \\
    --goods-id 600000632131 --state b-closed-goods
""")


def main():
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="对已有商品设置特殊状态（与建品流程完全解耦）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填参数 ──────────────────────────────────────────────────────────
    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id", required=True, help="供应商ID")
    g_req.add_argument("--poi-id",     required=True, help="门店ID")
    g_req.add_argument("--goods-id",   required=True, help="目标商品ID")
    g_req.add_argument("--state",      required=True, choices=sorted(_ALL_STATES),
                       help="目标状态（详见 --show-schema）")

    # ── 可选参数 ──────────────────────────────────────────────────────────
    g_opt = parser.add_argument_group("可选参数")
    g_opt.add_argument("--current-price-yuan", type=float, default=None,
                       help="当前售价（元）。merchant-auditing/merchant-audit-rejected 需要，"
                            "不传则按 --goods-type 使用默认值")
    g_opt.add_argument("--goods-type", type=int, default=1, choices=[1, 2],
                       help="商品类型：1=全日房（默认）  2=钟点房")
    g_opt.add_argument("--room-id", type=int, default=None,
                       help="逻辑房型ID（b-closed / b-full 必填）")
    g_opt.add_argument("--start-date", default="",
                       help="库存/房态修改起始日期（YYYY-MM-DD，默认今天）")
    g_opt.add_argument("--end-date", default="",
                       help="库存/房态修改截止日期（YYYY-MM-DD，默认两年后）")
    g_opt.add_argument("--bd-sso-user", default=None,
                       help="BD 员工 SSO 账号（mis，仅 BD-auditing/BD-audit-rejected 生效，"
                            "不传默认使用全局固定测试账号 crstest，已实测）")
    g_opt.add_argument("--bd-sso-password", default=None,
                       help="BD 员工 SSO 密码（仅 BD-auditing/BD-audit-rejected 生效，不传默认 Ceshi123）")
    g_opt.add_argument("--bd-client-id", default=None,
                       help="SSO 客户端 ID（可选，不传默认 hotel_sc）")
    g_opt.add_argument("--bd-client-secret", default=None,
                       help="SSO 客户端密钥（可选，不传用默认值）")
    g_opt.add_argument("--audit-reason", default=None,
                       help="BD 改价审核理由（仅 BD-auditing/BD-audit-rejected 生效，默认\"测试数据构造\"）")
    g_opt.add_argument("--limit-change-value", type=int, default=299,
                       help="仅 b-closed 生效：关房期间保留的库存余量（默认299，体现\"有库存但关房\"；"
                            "b-full 固定为0，不受此参数影响）")

    # ── 执行控制 ──────────────────────────────────────────────────────────
    g_exec = parser.add_argument_group("执行控制")
    g_exec.add_argument("--swimlane", default="", help="泳道名称（不传=主干）")

    # ── 帮助命令 ──────────────────────────────────────────────────────────
    g_help = parser.add_argument_group("帮助命令")
    g_help.add_argument("--show-schema", action="store_true",
                        help="打印参数说明并退出")

    args = parser.parse_args()

    # ── 前置校验 ──────────────────────────────────────────────────────────
    if args.state in _INVENTORY_STATES_ROOM and args.room_id is None:
        parser.error(f"--state {args.state} 需要传 --room-id（逻辑房型ID）")
    # ⚠️ BD-auditing/BD-audit-rejected 不再强制要求传 --bd-sso-user/--bd-sso-password：
    # 不传时会一路透传 None 到 interface.py 的 call_update_price_v2，由其内置的
    # DEFAULT_BD_SSO_*（全局固定测试账号 crstest，2026-08-19 已实测）提供默认值。

    print("═" * 60)
    print("  商品状态变更（factory/ops/goods-state.py）")
    print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
    print(f"  商品ID: {args.goods_id}")
    print(f"  目标状态: {args.state}")
    print(f"  泳道: {args.swimlane or '主干'}")
    print("═" * 60)

    # ── 分发到各子模块 ────────────────────────────────────────────────────

    if args.state in _PRODUCT_STATES:
        # 产品状态操作（offline / abolish）
        iface = _load_fullday_iface()
        mod = _load_goods_state_module("goods_product_ops")
        mod.apply_product_state(
            goods_state=args.state,
            iface=iface,
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            goods_id=args.goods_id,
            swimlane=args.swimlane,
        )

    elif args.state in _PRICE_STATES:
        # 价格状态操作（merchant-auditing / merchant-audit-rejected / BD-* ）
        iface = _load_fullday_iface()
        mod = _load_goods_state_module("goods_price_ops")

        # 构造一个"最小 params"，只包含价格字段（让 extract_price_fen_from_create_params 能读到）
        default_price_yuan = 80.0 if args.goods_type == 2 else 200.0
        current_price_yuan = args.current_price_yuan if args.current_price_yuan is not None \
            else default_price_yuan
        current_price_fen = int(current_price_yuan * 100)

        fake_params = {
            "goodsDetailList": [{
                "goodsBaseInfo": {"goodsType": args.goods_type},
                "priceInfo": {
                    "unifiedDatePriceInfos": {
                        "weekPriceInfos": [{
                            "priceInfo": {"salePrice": current_price_fen}
                        }]
                    }
                }
            }]
        }

        mod.apply_price_state(
            goods_state=args.state,
            iface=iface,
            params=fake_params,
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            room_id=0,          # 独立脚本模式：已上线，跳过上线步骤，room_id 不影响
            goods_id=args.goods_id,
            goods_type=args.goods_type,
            swimlane=args.swimlane,
            online_fn=None,     # 传 None = 跳过上线步骤（商品已上线）
            bd_sso_user=args.bd_sso_user,
            bd_sso_password=args.bd_sso_password,
            bd_client_id=args.bd_client_id,
            bd_client_secret=args.bd_client_secret,
            audit_reason=args.audit_reason,
            start_date=args.start_date or None,
            end_date=args.end_date or None,
        )

    elif args.state in _INVENTORY_STATES:
        # 库存/房态操作（房型维度 b-closed/b-full，产品维度 b-closed-goods/b-full-goods）
        mod = _load_goods_state_module("goods_inventory_ops")
        is_goods_dim = args.state in _INVENTORY_STATES_GOODS
        real_state = _GOODS_DIM_STATE_MAP[args.state] if is_goods_dim else args.state
        mod.apply_inventory_state(
            goods_state=real_state,
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            room_id=args.room_id,
            goods_type=args.goods_type,
            swimlane=args.swimlane,
            start_date=args.start_date,
            end_date=args.end_date,
            limit_change_value=args.limit_change_value,
            dimension="goods" if is_goods_dim else "room",
            goods_id=int(args.goods_id) if is_goods_dim else None,
        )

    else:
        print(f"❌ 未知 state='{args.state}'，支持值：{sorted(_ALL_STATES)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

