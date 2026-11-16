#!/usr/bin/env python3
"""
factory/goods-state/goods_product_ops.py
─────────────────────────────────────────
产品状态操作模块（Product-level state operations）

负责处理商品生命周期中的产品状态变更，包括：
  - offline          : 不在线——对已上线商品调用 batchOnlineSwitch(status=3) 下线，
                        最终 goodsStatus=3（下线/未上线），可逆（可再上线）
  - abolish          : 废除——自动先下线再调用 destroyGoods，最终 goodsStatus=8（不可逆）

⚠️ 建品与状态变更已完全解耦：调用本模块前商品必须已经存在且已上线
   （即已按 create-fullday.py / create-hourly.py 正常建品+上线流程跑完），
   offline 不是"建品时跳过上线"，而是对一个已上线商品真正执行下线动作。

使用方式（由 factory/ops/goods-state.py 调用）：
    from factory.goods_state.goods_product_ops import apply_product_state

    apply_product_state(
        goods_state="offline",   # 或 "abolish"
        iface=iface,
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        goods_id=goods_id,
        swimlane=args.swimlane,
    )

支持的 goods_state 值：
  offline  → offline_goods()
  abolish  → abolish_goods()

后续扩展：
  - 其他产品生命周期状态（如 suspend）只需在本文件新增处理函数，
    并在 apply_product_state 中添加对应分支即可，
    无需修改 create-fullday.py / create-hourly.py。
"""

from typing import Optional


# ════════════════════════════════════════════════════════════════════════════
# 对外统一入口
# ════════════════════════════════════════════════════════════════════════════

def apply_product_state(
    goods_state: str,
    iface,
    partner_id: str,
    poi_id: str,
    goods_id: str,
    swimlane: str,
) -> None:
    """
    产品状态统一入口。

    根据 goods_state 分发到对应的处理函数：
      offline  → offline_goods
      abolish  → abolish_goods

    参数：
        goods_state  - 目标产品状态（见上方枚举）
        iface        - 建品脚本的 iface 对象（含 _load_ops_interface / query_goods_info 等方法）
        partner_id   - 供应商ID（字符串）
        poi_id       - 门店ID（字符串）
        goods_id     - 目标商品ID（字符串）
        swimlane     - 泳道名称（不传=主干）

    不支持的状态值会抛出 ValueError。
    """
    if goods_state == "offline":
        offline_goods(
            iface=iface,
            partner_id=partner_id,
            poi_id=poi_id,
            goods_id=goods_id,
            swimlane=swimlane,
        )
    elif goods_state == "abolish":
        abolish_goods(
            iface=iface,
            partner_id=partner_id,
            poi_id=poi_id,
            goods_id=goods_id,
            swimlane=swimlane,
        )
    else:
        raise ValueError(
            f"goods_product_ops 不支持的 goods_state='{goods_state}'，"
            f"支持值：offline / abolish"
        )


# ════════════════════════════════════════════════════════════════════════════
# offline：对已上线商品执行下线（batchOnlineSwitch status=3）
# ════════════════════════════════════════════════════════════════════════════

def offline_goods(
    iface,
    partner_id: str,
    poi_id: str,
    goods_id: str,
    swimlane: str,
) -> None:
    """
    goods-state=offline：对已上线商品调用 batchOnlineSwitch(status=3) 下线。

    语义：商品已按建品流程正常上线，本操作使其转为下线态（goodsStatus=3）。
    与 abolish 的区别：offline 是可逆的（之后可通过 online-switch 重新上线），
    abolish 会在下线基础上进一步调用 destroyGoods，不可逆。

    ⚠️ 下线动作在特定条件下（如该商品是门店/战区下最后一个在线商品）
       可能触发人工审批流程（PrepayGoodsOfflineAuditProcess），此时下线不会
       立即成功，脚本会打印原因并退出，不做重试。

    参数：
        iface      - 建品脚本的 iface 对象（需含 _load_ops_interface 方法）
        partner_id - 供应商ID（字符串）
        poi_id     - 门店ID（字符串）
        goods_id   - 目标商品ID（字符串）
        swimlane   - 泳道名称
    """
    ops = iface._load_ops_interface()

    print("\n── 目标状态: offline（不在线）──────────────────────────────")
    print("── 下线（batchOnlineSwitch status=3）─────────────────────")
    try:
        switch_resp = ops.call_online_switch(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_ids=[int(goods_id)],
            status=3,
            swimlane=swimlane,
        )
        sw_data = switch_resp.get("data") or {}
        if sw_data.get("failCount", 0) > 0 or sw_data.get("successCount", 0) == 0:
            details = sw_data.get("details") or []
            reason = details[0].get("reason", "未知原因") if details else "未知原因"
            print(f"  ❌ 下线失败：{reason}")
            print("  若原因含「审核」字样，说明该商品下线触发了人工审批流程，")
            print("  无法通过脚本自动完成下线，请更换测试商品或等待审批通过后重试。")
            return
        print(f"  ✅ 下线成功  goodsId={goods_id}  （goodsStatus=3）")
        print(f"  如需之后手动上线：python3 factory/ops/online-switch.py "
              f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} --status 2")
    except Exception as e:
        print(f"  ❌ 下线异常：{e}")
        print(f"  💡 可手动执行：python3 factory/ops/online-switch.py "
              f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} --status 3")


# ════════════════════════════════════════════════════════════════════════════
# abolish：下线 → 废除（goodsStatus=8，不可逆）
# ════════════════════════════════════════════════════════════════════════════

def abolish_goods(
    iface,
    partner_id: str,
    poi_id: str,
    goods_id: str,
    swimlane: str,
) -> None:
    """
    goods-state=abolish：对已上线商品执行「下线 → 废除」两步动作。

    服务端强约束：仅"暂停/下线"状态（goodsStatus=3）的商品才能废除，
    因此必须先调用 batchOnlineSwitch(status=3) 下线，成功后再调用 destroyGoods。

    ⚠️ 下线动作在特定条件下（如该商品是门店/战区下最后一个在线商品）
       可能触发人工审批流程（PrepayGoodsOfflineAuditProcess），此时下线不会
       立即成功，废除也就无法进行，脚本会打印原因并退出，不做重试。

    参数：
        iface      - 建品脚本的 iface 对象（需含 _load_ops_interface 方法）
        partner_id - 供应商ID（字符串）
        poi_id     - 门店ID（字符串）
        goods_id   - 目标商品ID（字符串）
        swimlane   - 泳道名称
    """
    ops = iface._load_ops_interface()

    print("\n── 目标状态: abolish（废除）──────────────────────────────")
    print("── Step A: 下线（batchOnlineSwitch status=3）────────────────")
    try:
        switch_resp = ops.call_online_switch(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_ids=[int(goods_id)],
            status=3,
            swimlane=swimlane,
        )
        sw_data = switch_resp.get("data") or {}
        if sw_data.get("failCount", 0) > 0 or sw_data.get("successCount", 0) == 0:
            details = sw_data.get("details") or []
            reason = details[0].get("reason", "未知原因") if details else "未知原因"
            print(f"  ❌ 下线失败：{reason}")
            print("  若原因含「审核」字样，说明该商品下线触发了人工审批流程，")
            print("  无法通过脚本自动完成废除，请更换测试商品或等待审批通过后手动执行：")
            print(f"    python3 factory/ops/destroy-goods.py --partner-id {partner_id} "
                  f"--poi-id {poi_id} --goods-id {goods_id}")
            return
        print("  ✅ 下线成功")
    except Exception as e:
        print(f"  ❌ 下线异常：{e}")
        print(f"  💡 可手动执行：python3 factory/ops/destroy-goods.py --partner-id {partner_id} "
              f"--poi-id {poi_id} --goods-id {goods_id} --auto-offline")
        return

    print("\n── Step B: 废除（destroyGoods）───────────────────────────")
    try:
        destroy_resp = ops.call_destroy_goods(
            partner_id=int(partner_id),
            poi_id=str(poi_id),
            goods_id=int(goods_id),
            swimlane=swimlane,
        )
        if destroy_resp.get("data") is True or destroy_resp.get("success") is True:
            print(f"  ✅ 废除成功  goodsId={goods_id}  （goodsStatus=8）")
        else:
            print(f"  ❌ 废除失败：{destroy_resp}")
    except Exception as e:
        print(f"  ❌ 废除异常：{e}")
        print(f"  💡 可手动执行：python3 factory/ops/destroy-goods.py --partner-id {partner_id} "
              f"--poi-id {poi_id} --goods-id {goods_id}")

