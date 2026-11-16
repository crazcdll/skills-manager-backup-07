#!/usr/bin/env python3
"""
场景层：切换房态管理维度（房型维度 → 产品维度）
直调研发级 MeGoodsFacade#changeRoomStatusDimension

═══════════════════════════════════════════════════════════════════════════
⚠️⚠️⚠️ 高风险不可逆操作，使用前必须完全理解以下三点 ⚠️⚠️⚠️
═══════════════════════════════════════════════════════════════════════════

1. 切换后不可逆转——不支持从「产品维度」切回「房型维度」，没有反向接口。
2. 切换后 B 端存在两套独立数据：在「房型」维度的库存/房态之外，多出一层
   「产品」维度的库存/房态，两个维度可以分别单独设置和维护。
3. C 端取用时做两个维度的交集判断：房型维度库存售罄或关房时，即使产品维度
   房态为开、有库存，C 端也买不了；只有两个维度都"开房且有库存"，C 端才可售。

本操作是**门店级**（VPOI）操作，不是商品级/房型级操作，一旦对某个 poiId 执行，
该门店下所有房型/产品都会受影响。请勿在非测试专用门店上执行。

═══════════════════════════════════════════════════════════════════════════
异步生效说明
═══════════════════════════════════════════════════════════════════════════

接口调用成功只代表「切换任务已提交」，服务端内部：
  1. 先将门店维度状态置为 ROOM_DIMENSION_CHANGING（切换中）
  2. 异步线程逐个房型迁移库存/房态数据到产品维度
  3. 完成后维度状态最终变为 ROOM_DIMENSION_CHANGE_SUCCESS（产品维度）
     或 ROOM_DIMENSION_CHANGE_FAILED（切换失败）

目前没有已知的对外查询接口可以轮询这个维度状态，本脚本调用成功后
**无法立即确认切换是否真正完成**，需要调用方自行等待一段时间，
或让用户在 ME/MTA 前端页面自行核实最终状态。

═══════════════════════════════════════════════════════════════════════════
与 update-inventory.py / goods-state.py 的关系
═══════════════════════════════════════════════════════════════════════════

本脚本只负责"切换维度"这个动作本身，不涉及具体的开关房/库存操作：
  - 切换前（房型维度）：用 update-inventory.py --day-room-ids/--hour-room-ids 操作
  - 切换后（产品维度）：需要按 goodsId 维度操作开关房（当前 update-inventory.py /
    factory/goods-state/goods_inventory_ops.py 尚未支持传 goodsId 维度参数，
    接口层 interface/inventory/interface.py 虽已支持 changeType=2 + goodsIdList，
    但场景层的 open_and_set_inventory() 仍硬编码 change_type=1，如需按产品维度
    操作开关房，需先扩展该函数，暂不在本脚本职责范围内）

=== 使用示例 ===

# 1. 切换指定门店的房态管理维度（房型 → 产品，不可逆！）
python3 factory/inventory/change-room-status-dimension.py \\
  --partner-id 4576342 --poi-id 1090269458133536

# 2. 泳道支持
python3 factory/inventory/change-room-status-dimension.py \\
  --partner-id 4576342 --poi-id 1090269458133536 \\
  --swimlane user-zhangsan

# 3. dry-run（只打印参数不执行，强烈建议先 dry-run 确认门店/供应商无误）
python3 factory/inventory/change-room-status-dimension.py \\
  --partner-id 4576342 --poi-id 1090269458133536 \\
  --dry-run

注意：
  - 本脚本不做任何交互式二次确认（供 agent/自动化调用），调用前请务必让用户
    明确知晓"不可逆"这一后果，不要在用户未确认的情况下擅自对生产/共享门店执行。
  - 仅支持 partnerId + poiId 两个参数，没有 goodsId/roomId 维度的入参
    （接口本身就是门店级操作）。
"""

import argparse
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

def _load_inventory_iface():
    """加载库存/房态 interface（含 call_change_room_status_dimension 方法）。"""
    spec = ilu.spec_from_file_location(
        "inventory_interface",
        os.path.join(ROOT, "interface/inventory/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════════
# 核心调用函数（供其他脚本复用）
# ══════════════════════════════════════════════════════════════════════════════

def change_room_status_dimension(
    partner_id: str,
    poi_id: str,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    切换指定门店的房态管理维度：房型维度 → 产品维度。

    ⚠️ 不可逆，调用前务必让用户明确知晓后果（见本文件头部文档）。

    参数：
        partner_id  - 供应商ID
        poi_id      - 门店ID（mtPoiId）
        swimlane    - 泳道（空字符串=主干）
        dry_run     - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：InvokeError（业务失败）
    """
    iface = _load_inventory_iface()
    return iface.call_change_room_status_dimension(
        partner_id=partner_id,
        poi_id=poi_id,
        swimlane=swimlane,
        dry_run=dry_run,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 主入口（CLI）
# ══════════════════════════════════════════════════════════════════════════════

def _show_schema():
    print("""=== 切换房态管理维度（change-room-status-dimension）参数说明 ===

【必填参数】
  --partner-id      STR    供应商ID（partnerId）
  --poi-id          STR    门店ID（poiId，mtPoiId）

【执行控制】
  --swimlane        STR    泳道名称（不传=主干）
  --dry-run                只打印参数，不执行

【⚠️ 高风险不可逆，务必先读完以下说明再执行】
  1. 切换后不支持从产品维度切回房型维度（无反向接口）。
  2. 切换后 B 端有两套独立数据：房型维度库存/房态 + 产品维度库存/房态，
     两个维度可分别单独设置。
  3. C 端按两个维度取交集：房型售罄/关房时，即使产品开房有库存也买不了，
     两个维度都"开房且有库存"才可售。
  4. 接口调用成功只代表"任务已提交"，服务端异步执行迁移，
     本脚本不轮询确认最终是否切换成功。

【使用示例】
  # 切换房态管理维度（房型→产品，不可逆！）
  python3 factory/inventory/change-room-status-dimension.py \\
    --partner-id 4576342 --poi-id 1090269458133536

  # 先 dry-run 确认参数无误
  python3 factory/inventory/change-room-status-dimension.py \\
    --partner-id 4576342 --poi-id 1090269458133536 --dry-run
""")


def main():
    if "--show-schema" in sys.argv:
        _show_schema()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="切换房态管理维度：房型维度 → 产品维度（不可逆，MeGoodsFacade#changeRoomStatusDimension）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    g_req = parser.add_argument_group("必填参数")
    g_req.add_argument("--partner-id", required=True, help="供应商ID")
    g_req.add_argument("--poi-id",     required=True, help="门店ID（mtPoiId）")

    g_exec = parser.add_argument_group("执行控制")
    g_exec.add_argument("--swimlane", default="", help="泳道名称（不传=主干）")
    g_exec.add_argument("--dry-run",  action="store_true", help="只打印参数，不执行")

    g_help = parser.add_argument_group("帮助命令")
    g_help.add_argument("--show-schema", action="store_true", help="打印参数说明并退出")

    args = parser.parse_args()

    print("═" * 70)
    print("  ⚠️  切换房态管理维度：房型维度 → 产品维度（不可逆！）")
    print("═" * 70)
    print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
    print(f"  泳道: {args.swimlane or '主干'}")
    print("  ⚠️ 切换后不支持切回房型维度；切换后 B 端存在房型+产品两套独立库存/房态；")
    print("     C 端取两维度交集：任一维度售罄/关房即不可售。")
    print("═" * 70)

    try:
        resp = change_room_status_dimension(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            swimlane=args.swimlane,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"\n❌ 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return

    print(f"\n[RPC 原始返回]\n{json.dumps(resp, ensure_ascii=False, indent=2)}")

    success = resp.get("success")
    data    = resp.get("data")

    if success is True:
        print("\n" + "═" * 70)
        print("  ✅ 切换任务已提交（异步执行中）")
        print("═" * 70)
        print(f"  供应商: {args.partner_id}  门店: {args.poi_id}")
        print(f"  任务标识: {data}")
        print("  📋 当前状态：切换中（ROOM_DIMENSION_CHANGING），服务端正在异步")
        print("     迁移库存/房态数据到产品维度，本脚本不轮询确认最终结果。")
        print("  💡 如需确认是否切换成功，请稍等片刻后在 ME/MTA 前端页面核实，")
        print("     或联系 RD 提供的维度状态查询方式。")
        print("  ⚠️ 该操作不可逆，切换成功后该门店将永久使用产品维度房态管理。")
        print("═" * 70)
    else:
        msg = resp.get("error") or resp.get("message") or resp.get("msg") or str(resp)
        print(f"\n❌ 切换未成功: {msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

