#!/usr/bin/env python3
"""
场景层：房态 & 库存修改（直调研发级 MeInventoryFacade#batchUpdateInventory）

=== 适用场景 ===

1. 商品发布上线时提示"最近90天内至少30天同时有价格和库存"——需先开房并设置库存
2. 手动调整某日期区间的房态（开/关房）
3. 手动补充某日期区间的库存余量
4. 上述场景完成后，再重新调用 factory/hourly/create-hourly.py 或
   factory/fullday/create-fullday.py 进行发布上线

=== 与 batchCreateGoods 的区别 ===

batchCreateGoods（上单）流程会强制将 invSwitch 覆盖为 0（关房），
batchUpdateInventory（改房态/库存）流程**不会**强制覆盖，传什么生效什么。

=== ⚠️ 初次添加库存 vs 后续修改库存（countType 选择指南）===

后端对 countType 的第4位（个位）有如下含义：
  0 = 预留房「不变」
  1 = 预留房「设置绝对量」

⚠️ 【重要】该房型/房间从未设置过库存时（初次添加），
   countType 不能带「不变」语义（个位=0），否则报错：
     「初次添加库存,不能选择不变」
   此时必须使用 countType=1121（同时设置库存总量+预留房绝对量）。

已有库存记录后（后续修改），可使用：
  1520  设置库存剩余量（最常用，预留房不变）
  1920  库存不限量（预留房不变）
  1120  设置库存总量（预留房不变）

快速判断：
  - 新建商品/新开房型  → 先用 --count-type 1121
  - 补库存/日常调整   → 用默认 --count-type 1520 即可

=== 使用示例 ===

# 1a. 开房 + 初次设置库存（新建商品/从未有过库存记录，必须用 count-type 1121）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1

# 1b. 开房 + 修改已有库存余量（已有库存记录时用默认 count-type 1520）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --limit-change-value 299

# 2a. 全日房开房 + 初次设置库存（新建商品时用 count-type 1121）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --day-room-ids 12345 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1

# 2b. 全日房开房 + 修改已有库存
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --day-room-ids 12345 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --limit-change-value 299

# 3. 仅关房（不动库存）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 0

# 4. 仅设置库存余量（不动房态）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch -1 --limit-change-value 200

# 5. 只改工作日（周一到周五）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --limit-change-value 299 \\
  --effect-weeks 1 2 3 4 5

# 6. 泳道支持
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --limit-change-value 299 \\
  --swimlane user-zhangsan

# 7. dry-run（只打印参数不执行）
python3 factory/inventory/update-inventory.py \\
  --partner-id 4550589 --poi-id 1085927256096396 \\
  --hour-room-ids 77671480 \\
  --start-date 2026-05-21 --end-date 2028-05-21 \\
  --inv-switch 1 --limit-change-value 299 \\
  --dry-run
"""

import argparse
import datetime
import importlib.util as ilu
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)


# ══════════════════════════════════════════════════════════════════════════════
# 接口层加载
# ══════════════════════════════════════════════════════════════════════════════

def _load_interface():
    spec = ilu.spec_from_file_location(
        "inventory_interface",
        os.path.join(ROOT, "interface/inventory/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════════════════

def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _two_years_later() -> str:
    """
    服务端限制：endDate 只能在昨天至未来2年内（不含边界）。
    取 today + 2年 - 1天，确保不超出上限。
    """
    today = datetime.date.today()
    try:
        end = today.replace(year=today.year + 2) - datetime.timedelta(days=1)
    except ValueError:
        # 2月29日特殊处理
        end = today.replace(year=today.year + 2, month=3, day=1) - datetime.timedelta(days=1)
    return end.strftime("%Y-%m-%d")


INV_SWITCH_DESC = {-1: "不变", 0: "关房", 1: "开房"}
COUNT_TYPE_DESC = {
    # ── 初次添加库存（该房型从未有过库存记录）必须用以下类型 ─────────────────────
    1121: "【初次/已有均可】设置库存总量 + 设置预留房绝对量",
    # ── 已有库存记录后可用（个位=0 代表预留房不变，初次会报错）─────────────────
    1520: "【已有库存】设置库存剩余量（limitChangeValue），预留房不变",
    1920: "【已有库存】库存不限量，预留房不变",
    1120: "【已有库存】设置库存总量，预留房不变",
    1021: "【已有库存】库存总量不变，设置预留房绝对量",
}


# ══════════════════════════════════════════════════════════════════════════════
# 核心调用函数（供 factory/hourly/create-hourly.py 等复用）
# ══════════════════════════════════════════════════════════════════════════════

def open_and_set_inventory(
    partner_id,
    poi_id,
    day_room_ids: list = None,
    hour_room_ids: list = None,
    start_date: str = "",
    end_date: str = "",
    inv_switch: int = 1,
    count_type: int = 1520,
    limit_change_value: int = 299,
    count: int = 1,
    effect_weeks: list = None,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    直调 MeInventoryFacade#batchUpdateInventory，修改房态和/或库存。

    此函数供 create-hourly.py / create-fullday.py 等脚本复用，也可直接调用。

    默认行为（inv_switch=1 + count_type=1520 + limit_change_value=299）：
      - 开房（invSwitch=1）
      - 设置库存余量为 299（满足上线校验"90天内至少30天有库存"）
      - 预留房不变（count 字段被忽略，传 1 仅满足 @Positive 约束）

    参数：
        partner_id          - 供应商ID
        poi_id              - 门店ID
        day_room_ids        - 全日房房型ID列表（与 hour_room_ids 至少一个非空）
        hour_room_ids       - 钟点房房型ID列表
        start_date          - 日期范围起始（默认今天）
        end_date            - 日期范围截止（默认两年后）
        inv_switch          - 房态：-1=不变, 0=关房, 1=开房
        count_type          - 库存变化模式（默认 1520）
        limit_change_value  - 库存余量目标值（默认 299）
        count               - 预留房变更值（默认 1，语义上可能被忽略）
        effect_weeks        - 生效星期列表（默认 [1..7] 全周）
        swimlane            - 泳道
        dry_run             - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：InvokeError（业务失败），ValueError（参数校验失败）
    """
    if not start_date:
        start_date = _today()
    if not end_date:
        end_date = _two_years_later()
    if effect_weeks is None:
        effect_weeks = [1, 2, 3, 4, 5, 6, 7]

    if not day_room_ids and not hour_room_ids:
        raise ValueError("day_room_ids 和 hour_room_ids 至少需要一个非空")

    iface = _load_interface()

    modify_model = iface.build_modify_model(
        day_room_ids=day_room_ids or [],
        hour_room_ids=hour_room_ids or [],
        start_date=start_date,
        end_date=end_date,
        effect_weeks=effect_weeks,
        inv_switch=inv_switch,
        count_type=count_type,
        limit_change_value=limit_change_value,
        count=count,
    )

    return iface.call_batch_update_inventory(
        partner_id=int(partner_id),
        poi_id=int(poi_id),
        change_type=1,  # 1=房型维度（ROOM）
        modify_inventory_model_list=[modify_model],
        swimlane=swimlane,
        dry_run=dry_run,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 主入口（CLI）
# ══════════════════════════════════════════════════════════════════════════════

def _show_schema():
    print("""=== 房态 & 库存修改（update-inventory）参数说明 ===

【必填参数】
  --partner-id        INT    供应商ID（partnerId）
  --poi-id            INT    门店ID（poiId）

【房型参数（至少填一个）】
  --hour-room-ids     INT+   钟点房房型ID列表，空格分隔，如：77671480 77671481
  --day-room-ids      INT+   全日房房型ID列表，空格分隔，如：12345 12346

【日期参数】
  --start-date        STR    日期范围起始（YYYY-MM-DD，默认今天）
  --end-date          STR    日期范围截止（YYYY-MM-DD，默认两年后）
  --effect-weeks      INT+   生效星期（1=周一…7=周日，默认全周 1 2 3 4 5 6 7）

【房态/库存参数】
  --inv-switch        INT    房态：-1=不变, 0=关房, 1=开房（默认 1）
  --count-type        INT    库存变化模式（默认 1520，见下方枚举）
  --limit-change-value INT   库存余量目标值，正整数 ≤999（默认 299）
  --count             INT    预留房变更值（默认 1，countType 个位=0 时被忽略）

【countType 枚举（重要！初次添加库存必须用 1121）】
  1121  【初次/已有均可】设置库存总量 + 设置预留房绝对量
        ⚠️ 该房型从未设置过库存时（初次添加），必须用此值，否则报错"初次添加库存,不能选择不变"
  1520  【已有库存】设置库存剩余量（limitChangeValue），预留房不变  ← 最常用
  1920  【已有库存】库存不限量，预留房不变
  1120  【已有库存】设置库存总量，预留房不变
  1021  【已有库存】库存总量不变，设置预留房绝对量

  快速判断：
    新建商品 / 新开房型  → 先用 --count-type 1121 --count 1
    补库存 / 日常调整   → 用默认 --count-type 1520

【执行控制】
  --swimlane          STR    泳道名称（不传=主干）
  --dry-run                  只打印参数，不执行

【与 batchCreateGoods 的区别】
  batchCreateGoods（上单）流程会强制将 invSwitch 覆盖为 0（关房）；
  batchUpdateInventory（本脚本）不会强制覆盖，传什么生效什么。

【使用示例】
  # 新建商品后初次设置库存（必须用 count-type 1121）
  python3 factory/inventory/update-inventory.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --day-room-ids 12345 \\
    --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1

  # 钟点房开房 + 初次设置库存
  python3 factory/inventory/update-inventory.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --hour-room-ids 77671480 \\
    --inv-switch 1 --count-type 1121 --limit-change-value 299 --count 1

  # 后续补充库存（已有库存记录）
  python3 factory/inventory/update-inventory.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --day-room-ids 12345 \\
    --inv-switch 1 --limit-change-value 299

  # 仅关房（不动库存）
  python3 factory/inventory/update-inventory.py \\
    --partner-id 4550589 --poi-id 1085927256096396 \\
    --day-room-ids 12345 --inv-switch 0
""")


def main():
    # 快速检测帮助类命令（避免 required 参数报错）
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="房态 & 库存修改（直调研发级 RPC：MeInventoryFacade#batchUpdateInventory）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── 必填参数 ──────────────────────────────────────────────────────────────
    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id", required=True, type=int, help="供应商ID（partnerId）")
    g_req.add_argument("--poi-id",     required=True, type=int, help="门店ID（poiId）")

    # ── 房型参数（二选一或同时填）────────────────────────────────────────────
    g_room = parser.add_argument_group("房型参数（至少填一个）")
    g_room.add_argument("--hour-room-ids", type=int, nargs="+", default=[],
                        help="钟点房房型ID列表，空格分隔，如：77671480")
    g_room.add_argument("--day-room-ids",  type=int, nargs="+", default=[],
                        help="全日房房型ID列表，空格分隔，如：12345")

    # ── 日期参数 ──────────────────────────────────────────────────────────────
    g_date = parser.add_argument_group("日期参数")
    g_date.add_argument("--start-date", default="",
                        help="日期范围起始（YYYY-MM-DD，默认今天）")
    g_date.add_argument("--end-date",   default="",
                        help="日期范围截止（YYYY-MM-DD，默认两年后）")
    g_date.add_argument("--effect-weeks", type=int, nargs="+", default=[1,2,3,4,5,6,7],
                        choices=[1,2,3,4,5,6,7],
                        help="生效星期（1=周一…7=周日，默认全周）")

    # ── 房态/库存参数 ─────────────────────────────────────────────────────────
    g_inv = parser.add_argument_group("房态/库存参数")
    g_inv.add_argument("--inv-switch", type=int, default=1, choices=[-1, 0, 1],
                       help="-1=不变, 0=关房, 1=开房（默认 1）")
    g_inv.add_argument("--count-type", type=int, default=1520,
                       help="库存变化模式（默认 1520：设置余量，预留房不变）")
    g_inv.add_argument("--limit-change-value", type=int, default=299,
                       help="库存余量目标值，正整数 ≤999（默认 299）")
    g_inv.add_argument("--count", type=int, default=1,
                       help="预留房变更值（默认 1，countType 第4位=0 时被忽略）")

    # ── 执行控制 ──────────────────────────────────────────────────────────────
    g_exec = parser.add_argument_group("执行控制")
    g_exec.add_argument("--swimlane", default="", help="泳道名称（不传=主干）")
    g_exec.add_argument("--dry-run",  action="store_true", help="只打印参数，不执行")
    g_exec.add_argument("--no-hint",  action="store_true", help="静默末尾的重新上线提示（被其他脚本调用时使用）")

    args = parser.parse_args()

    if not args.hour_room_ids and not args.day_room_ids:
        parser.error("至少填一个房型ID：--hour-room-ids 或 --day-room-ids")

    start_date = args.start_date or _today()
    end_date   = args.end_date   or _two_years_later()

    print("═" * 60)
    print("  房态 & 库存修改（直调研发级 RPC）")
    print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
    if args.hour_room_ids:
        print(f"  钟点房房型: {args.hour_room_ids}")
    if args.day_room_ids:
        print(f"  全日房房型: {args.day_room_ids}")
    print(f"  日期范围: {start_date} ~ {end_date}")
    print(f"  生效星期: {args.effect_weeks}")
    print(f"  房态: {args.inv_switch}（{INV_SWITCH_DESC.get(args.inv_switch, '?')}）")
    ct_desc = COUNT_TYPE_DESC.get(args.count_type, f"countType={args.count_type}")
    print(f"  countType: {args.count_type}（{ct_desc}）")
    if args.inv_switch != 0:  # 关房时库存无意义，不打印
        print(f"  库存余量(limitChangeValue): {args.limit_change_value}")
    print(f"  泳道: {args.swimlane or '主干'}")
    print("═" * 60)

    if args.dry_run:
        print("\n[dry-run] 将调用以下参数：")
        iface = _load_interface()
        modify_model = iface.build_modify_model(
            day_room_ids=args.day_room_ids,
            hour_room_ids=args.hour_room_ids,
            start_date=start_date,
            end_date=end_date,
            effect_weeks=args.effect_weeks,
            inv_switch=args.inv_switch,
            count_type=args.count_type,
            limit_change_value=args.limit_change_value,
            count=args.count,
        )
        full_params = {
            "partnerId":  args.partner_id,
            "poiId":      args.poi_id,
            "changeType": 1,
            "modifyInventoryModelList": [modify_model],
        }
        print(json.dumps(full_params, ensure_ascii=False, indent=2))
        print("\n[dry-run] 模拟完成，未实际执行。")
        return

    try:
        resp = open_and_set_inventory(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            day_room_ids=args.day_room_ids,
            hour_room_ids=args.hour_room_ids,
            start_date=start_date,
            end_date=end_date,
            effect_weeks=args.effect_weeks,
            inv_switch=args.inv_switch,
            count_type=args.count_type,
            limit_change_value=args.limit_change_value,
            count=args.count,
            swimlane=args.swimlane,
            dry_run=False,
        )
    except Exception as e:
        print(f"\n❌ 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[RPC 原始返回]\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    # 判断结果
    success = resp.get("success")
    data    = resp.get("data")

    if success is True or data is True:
        switch_label = INV_SWITCH_DESC.get(args.inv_switch, str(args.inv_switch))
        print("\n" + "═" * 60)
        print("  ✅ 房态/库存修改成功")
        print("═" * 60)
        if args.hour_room_ids:
            print(f"  钟点房房型: {args.hour_room_ids}")
        if args.day_room_ids:
            print(f"  全日房房型: {args.day_room_ids}")
        print(f"  房态变更  : {switch_label}")
        if args.inv_switch != 0:
            print(f"  库存余量  : {args.limit_change_value}")
        print(f"  日期范围  : {start_date} ~ {end_date}")
        print("═" * 60)
        if not args.no_hint:
            print("\n💡 提示：房态/库存修改完成后，可重新执行 create-hourly.py 或 create-fullday.py 发布上线。")
    else:
        msg = resp.get("message") or resp.get("msg") or str(resp)
        print(f"\n❌ 修改未成功: {msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

