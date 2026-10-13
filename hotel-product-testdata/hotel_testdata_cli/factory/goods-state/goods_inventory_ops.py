#!/usr/bin/env python3
"""
factory/goods-state/goods_inventory_ops.py
────────────────────────────────────────────
库存/房态操作模块（Inventory & Room-state operations）

负责对**已上线**商品设置库存/房态特殊状态，支持房型维度、产品维度两套接口形态：
  - b-closed / b-closed-goods : B端关房——将指定日期范围设置为关房（invSwitch=0），
                                 同时保留非零库存余量（体现"有库存但关房不可订"）
  - b-full   / b-full-goods   : B端满房——将指定日期范围保持开房（invSwitch=1），
                                 但库存余量置0（体现"开房可订但库存耗尽"）

维度说明（由 dimension 参数区分，二者调用的是同一个 batchUpdateInventory 接口，
仅 changeType/modifyInventorySubjectsModel 不同）：
  - dimension="room"（默认，changeType=1）：按 room_id + goods_type 传
    day_room_ids/hour_room_ids，适用于门店默认的"房型维度"房态管理模式，
    对应 b-closed / b-full 两个状态值
  - dimension="goods"（changeType=2）：直接按 goods_id 传 goods_ids，
    适用于门店已通过 change-room-status-dimension.py 切换为"产品维度"后，
    对应 b-closed-goods / b-full-goods 两个状态值；未切换维度的门店调用
    大概率被后端拒绝或不生效

⚠️⚠️⚠️ 预留房是"房型级共享"数据，不是挂在单个商品上的（真实踩坑，详见各函数
docstring 及 w10-goods-state.md）：凡是走过"新建商品自动补库存"分支的房型/商品，
预留房量会被设为非零值，此后执行 b-closed/b-full（含 *-goods 产品维度）可能因
"库存余量 < 预留房量"被服务端拒绝（errCode 53007/200012038/200012039）。
本模块已内置统一自动兜底（_is_reserved_room_conflict + _clear_reserved_room）：
命中该类错误后自动清零预留房再重试，且**清零必须走房型维度**——产品维度下会先
通过 _query_room_id_and_type 反查 goodsId 对应的 roomId 再改用房型维度清零
（产品维度直接清零 RPC 返回成功但对预留房实际不生效），调用方（含 AI）无需感知。

使用方式（由 factory/ops/goods-state.py 在商品已上线后调用）：
    from factory.goods_state.goods_inventory_ops import apply_inventory_state

    apply_inventory_state(
        goods_state="b-closed",      # b-closed / b-full / b-closed-goods / b-full-goods 由
                                      # factory/ops/goods-state.py 统一映射为 dimension 参数后调用
        partner_id=args.partner_id,
        poi_id=args.poi_id,
        room_id=args.room_id,        # dimension="room" 时必传
        goods_type=1,                # 1=全日房  2=钟点房（影响 day/hour_room_ids 选择）
        swimlane=args.swimlane,
        dimension="room",            # 或 "goods"
        goods_id=args.goods_id,      # dimension="goods" 时必传
    )

后续扩展：
  - 新增状态（如 b-limited 限量等）只需在本文件添加处理函数，
    并在 apply_inventory_state 中添加分支，无需修改 factory/ops/goods-state.py。
"""

import importlib.util as ilu
import os
import datetime
from typing import Optional


# ════════════════════════════════════════════════════════════════════════════
# 接口层加载
# ════════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# goods-state/ 目录在 factory/ 下，往上两级是 hotel_testdata_cli/
_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))


def _load_update_inventory():
    """加载 factory/inventory/update-inventory.py 模块，复用 open_and_set_inventory 函数。"""
    spec = ilu.spec_from_file_location(
        "update_inventory",
        os.path.join(_ROOT, "factory/inventory/update-inventory.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_fullday_interface():
    """加载 interface/fullday/interface.py 模块，复用 query_goods_info 反查 roomId/goodsType。"""
    spec = ilu.spec_from_file_location(
        "fullday_interface",
        os.path.join(_ROOT, "interface/fullday/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════════════════

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


# 用于识别"库存余量 < 预留房余量"这一类特定业务错误的关键字，命中后触发
# 自动清零预留房 + 重试兜底，不命中则按原异常直接失败。
# 已实测覆盖的错误码/文案：
#   errCode=53007      （b-full 房型维度）"房型剩余房量不能小于预留房量剩余房量"
#   errCode=200012038  （b-full 产品维度）"更新失败！更新后房型下所有产品的可售总量之和小于预留房量"
#   errCode=200012039  （b-closed 产品维度）"关房失败！关房后房型下所有产品的可售总量之和小于预留房量"
_RESERVED_ROOM_CONFLICT_KEYWORDS = ("预留房量", "预留房余量", "53007", "200012038", "200012039")


def _is_reserved_room_conflict(exc: Exception) -> bool:
    msg = str(exc)
    return any(kw in msg for kw in _RESERVED_ROOM_CONFLICT_KEYWORDS)


def _query_room_id_and_type(partner_id: str, poi_id: str, goods_id: int, swimlane: str):
    """
    产品维度（dimension="goods"）下反查该 goodsId 对应的 roomId / goodsType。

    ⚠️⚠️⚠️ 真实业务约束（2026-08-18 实测踩坑，务必知悉）：
      预留房量是**房型级共享**数据（服务端报错原文"房型下所有产品的可售总量之和小于
      预留房量"），不是挂在单个商品上的。因此清零预留房必须走**房型维度**
      （day_room_ids/hour_room_ids，changeType=1），若直接用产品维度
      （goods_ids，changeType=2）传 count=0 清零，RPC 会返回成功但预留房实际
      不受影响，导致后续操作反复报同样的冲突错误。

      本函数通过 MeGoodsFacade#queryGoodsInfo 反查 goodsId 对应的
      roomInfo.roomId + goodsBaseInfo.goodsType，供清零预留房时改用房型维度调用。

    返回：(room_id: int, goods_type: int) 或 (None, None)（查询失败/查不到时）
    """
    try:
        fullday_iface = _load_fullday_interface()
        resp = fullday_iface.query_goods_info(
            partner_id=partner_id,
            poi_id=poi_id,
            goods_ids=[int(goods_id)],
            swimlane=swimlane,
        )
        if not resp.get("success", True):
            return None, None
        goods_list = resp.get("data") or []
        if not goods_list:
            return None, None
        goods = goods_list[0]
        room_id = (goods.get("roomInfo") or {}).get("roomId")
        goods_type = (goods.get("goodsBaseInfo") or {}).get("goodsType")
        if room_id is None or goods_type is None:
            return None, None
        return int(room_id), int(goods_type)
    except Exception:
        return None, None


def _clear_reserved_room(
    upd_mod,
    partner_id: str,
    poi_id: str,
    start_date: str,
    end_date: str,
    swimlane: str,
    is_goods_dim: bool,
    room_id: Optional[int],
    goods_type: Optional[int],
    goods_id: Optional[int],
) -> None:
    """
    清零指定日期范围的预留房（countType=1021，库存总量不变，预留房绝对量设为0）。

    ⚠️ 预留房是房型级共享数据，产品维度（goods_ids）清零对其不生效（RPC 返回
    成功但预留房实际未清零），必须优先尝试用房型维度（day_room_ids/hour_room_ids）
    调用。因此：
      - dimension="room"：直接用传入的 room_id/goods_type 走房型维度
      - dimension="goods"：先反查该 goods_id 对应的 room_id/goods_type，
        查到则改走房型维度清零；查不到（反查失败）才退化为产品维度尝试
        （大概率不生效，仅作为无法反查时的兜底，不保证成功）
    """
    query_room_id, query_goods_type = room_id, goods_type
    if is_goods_dim and (query_room_id is None or query_goods_type is None):
        query_room_id, query_goods_type = _query_room_id_and_type(
            partner_id=partner_id, poi_id=poi_id, goods_id=goods_id, swimlane=swimlane,
        )

    if query_room_id is not None and query_goods_type is not None:
        # ✅ 优先用房型维度清零（预留房的真实归属维度，实测有效）
        print(f"  🔄 自动清零预留房（房型维度，roomId={query_room_id}，countType=1021，预留房绝对量设为0）后重试...")
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            day_room_ids=[query_room_id] if query_goods_type == 1 else [],
            hour_room_ids=[query_room_id] if query_goods_type == 2 else [],
            goods_ids=[],
            start_date=start_date,
            end_date=end_date,
            inv_switch=-1,           # 不变，避免误改房态
            count_type=1021,         # 库存总量不变，仅设置预留房绝对量
            limit_change_value=299,  # 该 countType 下库存总量语义不变，传值仅满足参数校验
            count=0,                 # 预留房绝对量清零
            swimlane=swimlane,
        )
    else:
        # ⚠️ 反查失败（罕见），退化为产品维度尝试，大概率对房型级共享预留房不生效
        print(f"  ⚠️ 反查 goodsId={goods_id} 对应的 roomId 失败，退化为产品维度清零预留房（可能不生效）...")
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            day_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 1 else []),
            hour_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 2 else []),
            goods_ids=[int(goods_id)] if is_goods_dim else [],
            start_date=start_date,
            end_date=end_date,
            inv_switch=-1,
            count_type=1021,
            limit_change_value=299,
            count=0,
            swimlane=swimlane,
        )


# ════════════════════════════════════════════════════════════════════════════
# 对外统一入口
# ════════════════════════════════════════════════════════════════════════════

def apply_inventory_state(
    goods_state: str,
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_type: int,
    swimlane: str,
    start_date: str = "",
    end_date: str = "",
    limit_change_value: int = 299,
    dimension: str = "room",
    goods_id: Optional[int] = None,
) -> None:
    """
    库存/房态状态统一入口。

    根据 goods_state 分发到对应的处理函数：
      b-closed  → set_b_closed（关房，保留非零库存余量）
      b-full    → set_b_full（满房，库存余量固定为0）

    参数：
        goods_state         - 目标房态状态（见上方枚举）
        partner_id          - 供应商ID（字符串）
        poi_id              - 门店ID（字符串）
        room_id             - 逻辑房型ID（int），仅 dimension="room"（默认）时必传
        goods_type          - 商品类型：1=全日房  2=钟点房（决定 day_room_ids/hour_room_ids 的选择，
                               仅 dimension="room" 时生效）
        swimlane            - 泳道名称
        start_date          - 库存修改起始日期（默认今天）
        end_date            - 库存修改截止日期（默认两年后）
        limit_change_value  - 仅 b-closed 生效：关房期间保留的库存余量（默认299，
                               体现"有库存但关房"；b-full 固定为0，不受此参数影响）
        dimension           - 房态管理维度："room"（默认，房型维度，changeType=1）
                               或 "goods"（产品维度，changeType=2，需门店已通过
                               change-room-status-dimension.py 切换为产品维度）
        goods_id            - 商品ID，仅 dimension="goods" 时必传（与 room_id 互斥）

    不支持的状态值会抛出 ValueError。
    """
    if dimension not in ("room", "goods"):
        raise ValueError(f"dimension 只支持 'room' 或 'goods'，当前传入：{dimension!r}")
    if dimension == "goods" and not goods_id:
        raise ValueError("dimension='goods' 时必须传 goods_id")
    if dimension == "room" and not room_id:
        raise ValueError("dimension='room'（默认）时必须传 room_id")

    if goods_state == "b-closed":
        set_b_closed(
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_type=goods_type,
            swimlane=swimlane,
            start_date=start_date,
            end_date=end_date,
            limit_change_value=limit_change_value,
            dimension=dimension,
            goods_id=goods_id,
        )
    elif goods_state == "b-full":
        set_b_full(
            partner_id=partner_id,
            poi_id=poi_id,
            room_id=room_id,
            goods_type=goods_type,
            swimlane=swimlane,
            start_date=start_date,
            end_date=end_date,
            dimension=dimension,
            goods_id=goods_id,
        )
    else:
        raise ValueError(
            f"goods_inventory_ops 不支持的 goods_state='{goods_state}'，"
            f"支持值：b-closed / b-full"
        )


# ════════════════════════════════════════════════════════════════════════════
# b-closed：B端关房（有库存但关房，C端不可见）
# ════════════════════════════════════════════════════════════════════════════

def set_b_closed(
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_type: int,
    swimlane: str,
    start_date: str = "",
    end_date: str = "",
    limit_change_value: int = 299,
    dimension: str = "room",
    goods_id: Optional[int] = None,
) -> None:
    """
    goods-state=b-closed：商品上线后将所有日期设置为关房（invSwitch=0），且保留库存余量。

    状态特征：
      - 商品处于上线态（goodsStatus=2）
      - 库存余量 > 0（默认 299，与"新建商品补库存"的默认值一致，代表"有库存"）
      - 所有日期 invSwitch=0（关房）
      - C端报价接口查询不到该商品（因房态关闭，非因无库存）

    ⚠️ 与 b-full 的核心区别就在这里：b-closed 是"有库存但关房不可订"，
       b-full 是"开房可订但库存耗尽"，二者的 C 端不可见原因不同，
       因此 limit_change_value 必须传非零值，不能像 b-full 一样置 0。

    实现：
      调用 MeInventoryFacade#batchUpdateInventory（invSwitch=0，同时设置库存余量为非零值）
      复用 factory/inventory/update-inventory.py 的 open_and_set_inventory 函数。

      注意：countType=1520（设置库存剩余量）会真实覆盖 limitChangeValue，
      并不存在"库存完全不下发变化"的 countType 取值（个位=0 只代表"预留房不变"，
      与库存余量无关）。因此"有库存"要靠显式传一个非零的 limit_change_value 实现，
      而不是寄希望于"不传就不生效"。

    参数：
        partner_id          - 供应商ID（字符串）
        poi_id              - 门店ID（字符串）
        room_id             - 逻辑房型ID（int）
        goods_type          - 1=全日房（用 day_room_ids）  2=钟点房（用 hour_room_ids）
        swimlane            - 泳道名称
        start_date          - 关房日期起始（默认今天）
        end_date            - 关房日期截止（默认两年后）
        limit_change_value  - 关房期间保留的库存余量（默认 299，必须 > 0 才能体现"有库存"）
    """
    if not start_date:
        start_date = _today()
    if not end_date:
        end_date = _two_years_later()

    is_goods_dim = dimension == "goods"

    print("\n── 目标状态: b-closed（B端关房，保留库存）──────────────────────")
    print(f"  将日期范围 {start_date} ~ {end_date} 的房态设置为关房（invSwitch=0）")
    if is_goods_dim:
        print(f"  维度=产品维度（changeType=2），商品ID={goods_id}")
    else:
        print(f"  维度=房型维度（changeType=1），房型ID={room_id}，商品类型={'全日房' if goods_type == 1 else '钟点房'}")
    print(f"  库存余量将保留为 {limit_change_value}（体现「有库存但关房」）")

    def _do_set_closed(upd_mod) -> None:
        # 关房：invSwitch=0；库存余量显式设为非零值（默认 299），
        # 与 b-full（limit_change_value=0）形成对比，确保"有库存"而非"库存耗尽"
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            day_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 1 else []),
            hour_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 2 else []),
            goods_ids=[int(goods_id)] if is_goods_dim else [],
            start_date=start_date,
            end_date=end_date,
            inv_switch=0,       # 关房
            count_type=1520,    # 设置库存余量模式
            limit_change_value=limit_change_value,   # 保留非零库存余量（默认299）
            count=1,
            swimlane=swimlane,
        )

    try:
        upd_mod = _load_update_inventory()

        try:
            _do_set_closed(upd_mod)
        except Exception as first_err:
            if not _is_reserved_room_conflict(first_err):
                raise
            # ── 自动兜底：命中"可售总量之和 < 预留房量"冲突，先清零预留房再重试一次 ──
            # ⚠️ 预留房是房型级共享数据，产品维度清零对其不生效，必须优先反查
            # roomId 后改用房型维度清零（详见 _clear_reserved_room 说明）
            print(f"  ⚠️ 检测到预留房冲突（{first_err}）")
            _clear_reserved_room(
                upd_mod, partner_id=partner_id, poi_id=poi_id,
                start_date=start_date, end_date=end_date, swimlane=swimlane,
                is_goods_dim=is_goods_dim, room_id=room_id, goods_type=goods_type, goods_id=goods_id,
            )
            print(f"  ✅ 预留房已清零，重新执行关房设置...")
            _do_set_closed(upd_mod)
            print(f"  📋 提示：本次触发了「预留房自动清零」兜底逻辑，已自动修复，无需手动处理。")

        if is_goods_dim:
            print(f"  ✅ 关房成功（产品维度）  商品ID={goods_id}  日期范围={start_date}~{end_date}  库存余量={limit_change_value}")
            print(f"  📋 商品已处于「上线+关房+有库存」状态（goodsStatus=2，invSwitch=0，inventory={limit_change_value}）")
            print(f"  💡 如需恢复开房：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} "
                  f"--inv-switch 1 --limit-change-value 299")
        else:
            print(f"  ✅ 关房成功  房型={room_id}  日期范围={start_date}~{end_date}  库存余量={limit_change_value}")
            print(f"  📋 商品已处于「上线+关房+有库存」状态（goodsStatus=2，invSwitch=0，inventory={limit_change_value}）")
            print(f"  💡 如需恢复开房：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} "
                  f"{'--day-room-ids' if goods_type == 1 else '--hour-room-ids'} {room_id} "
                  f"--inv-switch 1 --limit-change-value 299")
    except Exception as e:
        print(f"  ❌ 关房失败：{e}")
        if is_goods_dim:
            print(f"  💡 可手动执行：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} "
                  f"--start-date {start_date} --end-date {end_date} "
                  f"--inv-switch 0 --limit-change-value {limit_change_value}")
        else:
            print(f"  💡 可手动执行：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} "
                  f"{'--day-room-ids' if goods_type == 1 else '--hour-room-ids'} {room_id} "
                  f"--start-date {start_date} --end-date {end_date} "
                  f"--inv-switch 0 --limit-change-value {limit_change_value}")


# ════════════════════════════════════════════════════════════════════════════
# b-full：B端满房（开房但库存为 0，C端因无余量不返回）
# ════════════════════════════════════════════════════════════════════════════

def set_b_full(
    partner_id: str,
    poi_id: str,
    room_id: int,
    goods_type: int,
    swimlane: str,
    start_date: str = "",
    end_date: str = "",
    dimension: str = "room",
    goods_id: Optional[int] = None,
) -> None:
    """
    goods-state=b-full：B端满房——商品上线后将所有日期库存置为 0，但保持开房状态。

    状态特征：
      - 商品处于上线态（goodsStatus=2）
      - 房态为开房（invSwitch=1）
      - 库存余量为 0/0/0（limitChangeValue=0）
      - C端报价接口因库存耗尽而不返回该商品

    维度支持：
      - dimension="room"（默认）：按 room_id + goods_type 选 day_room_ids/hour_room_ids，
        changeType=1（房型维度）
      - dimension="goods"：按 goods_id 直接传 goods_ids，changeType=2（产品维度），
        需门店已通过 change-room-status-dimension.py 切换为产品维度才能生效

    实现：
      调用 MeInventoryFacade#batchUpdateInventory（invSwitch=1，limitChangeValue=0）
      使用 count_type=1520（设置库存余量，预留房不变）

    ⚠️⚠️⚠️ 真实业务约束（2026-08-18 实测踩坑，务必知悉）：
      凡是走过"新建商品自动补库存"分支（建品时上线失败提示"最近90天内至少30天同时
      有价格和库存"，脚本自动调用 batchUpdateInventory 用 countType=1121 补货）的
      房型/商品，预留房量会被同时设为非零值（默认 count=1）。此后若直接对同一房型/
      商品执行 b-full（limitChangeValue=0），服务端会强约束"库存余量 ≥ 预留房余量"，
      报错：「房型剩余房量不能小于预留房量剩余房量，房型余量0，预留房余量1」
      （errCode=53007）。

      本函数已内置自动兜底：捕获到该特定错误后，会自动先调用一次
      count_type=1021（库存总量不变，预留房绝对量设为0）把预留房清零，
      再重新执行一次 b-full 请求，调用方无需感知、无需手动处理。
      仅当自动兜底仍失败时才会把原始错误暴露给调用方。

    参数：
        partner_id  - 供应商ID（字符串）
        poi_id      - 门店ID（字符串）
        room_id     - 逻辑房型ID（int），仅 dimension="room" 时使用
        goods_type  - 1=全日房（用 day_room_ids）  2=钟点房（用 hour_room_ids），仅 dimension="room" 时使用
        swimlane    - 泳道名称
        start_date  - 满房日期起始（默认今天）
        end_date    - 满房日期截止（默认两年后）
        dimension   - "room"（默认，房型维度）或 "goods"（产品维度）
        goods_id    - 商品ID，仅 dimension="goods" 时必传
    """
    if not start_date:
        start_date = _today()
    if not end_date:
        end_date = _two_years_later()

    is_goods_dim = dimension == "goods"

    print("\n── 目标状态: b-full（B端满房）──────────────────────────────")
    print(f"  将日期范围 {start_date} ~ {end_date} 的库存余量设置为 0（开房但无库存）")
    if is_goods_dim:
        print(f"  维度=产品维度（changeType=2），商品ID={goods_id}")
    else:
        print(f"  维度=房型维度（changeType=1），房型ID={room_id}，商品类型={'全日房' if goods_type == 1 else '钟点房'}")

    def _do_set_full(upd_mod) -> None:
        upd_mod.open_and_set_inventory(
            partner_id=partner_id,
            poi_id=poi_id,
            day_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 1 else []),
            hour_room_ids=[] if is_goods_dim else ([int(room_id)] if goods_type == 2 else []),
            goods_ids=[int(goods_id)] if is_goods_dim else [],
            start_date=start_date,
            end_date=end_date,
            inv_switch=1,           # 开房（invSwitch=1）
            count_type=1520,        # 设置库存余量模式（已有库存时使用）
            limit_change_value=0,   # 库存余量置为 0 → 满房
            count=1,
            swimlane=swimlane,
        )

    try:
        upd_mod = _load_update_inventory()

        try:
            # 满房：开房（invSwitch=1）但库存余量设为 0
            # count_type=1520 = 设置库存剩余量（limitChangeValue），预留房不变
            _do_set_full(upd_mod)
        except Exception as first_err:
            if not _is_reserved_room_conflict(first_err):
                raise
            # ── 自动兜底：命中"库存余量 < 预留房余量"冲突，先清零预留房再重试一次 ──
            # ⚠️ 预留房是房型级共享数据，产品维度清零对其不生效，必须优先反查
            # roomId 后改用房型维度清零（详见 _clear_reserved_room 说明）
            print(f"  ⚠️ 检测到预留房冲突（{first_err}）")
            _clear_reserved_room(
                upd_mod, partner_id=partner_id, poi_id=poi_id,
                start_date=start_date, end_date=end_date, swimlane=swimlane,
                is_goods_dim=is_goods_dim, room_id=room_id, goods_type=goods_type, goods_id=goods_id,
            )
            print(f"  ✅ 预留房已清零，重新执行满房设置...")
            _do_set_full(upd_mod)
            print(f"  📋 提示：本次触发了「预留房自动清零」兜底逻辑，说明该房型/商品此前")
            print(f"     走过\"新建商品自动补库存\"分支（countType=1121），已自动修复，无需手动处理。")

        if is_goods_dim:
            print(f"  ✅ 满房设置成功（产品维度）  商品ID={goods_id}  日期范围={start_date}~{end_date}")
            print(f"  📋 商品已处于「上线+开房+库存0」状态（goodsStatus=2，invSwitch=1，inventory=0）")
            print(f"  💡 如需恢复库存：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} "
                  f"--inv-switch 1 --limit-change-value 299")
        else:
            print(f"  ✅ 满房设置成功  房型={room_id}  日期范围={start_date}~{end_date}")
            print(f"  📋 商品已处于「上线+开房+库存0」状态（goodsStatus=2，invSwitch=1，inventory=0）")
            print(f"  💡 如需恢复库存：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} "
                  f"{'--day-room-ids' if goods_type == 1 else '--hour-room-ids'} {room_id} "
                  f"--inv-switch 1 --limit-change-value 299")
    except Exception as e:
        print(f"  ❌ 满房设置失败：{e}")
        if is_goods_dim:
            print(f"  💡 可手动执行：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} --goods-ids {goods_id} "
                  f"--start-date {start_date} --end-date {end_date} "
                  f"--inv-switch 1 --limit-change-value 0")
        else:
            print(f"  💡 可手动执行：python3 factory/inventory/update-inventory.py "
                  f"--partner-id {partner_id} --poi-id {poi_id} "
                  f"{'--day-room-ids' if goods_type == 1 else '--hour-room-ids'} {room_id} "
                  f"--start-date {start_date} --end-date {end_date} "
                  f"--inv-switch 1 --limit-change-value 0")

