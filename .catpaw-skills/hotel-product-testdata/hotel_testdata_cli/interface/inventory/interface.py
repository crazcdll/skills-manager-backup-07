#!/usr/bin/env python3
"""
接口层：房态 & 库存修改
接口：MeInventoryFacade#batchUpdateInventory
协议：Thrift RPC
appKey：com.sankuai.hotel.biz.platform
service：com.meituan.hotel.biz.platform.goods.facade.standard.MeInventoryFacade
method：batchUpdateInventory

=== 参数结构 ===

BatchUpdateInventoryParam
  ├── partnerId            Long     供应商ID
  ├── poiId                Long     门店ID
  ├── changeType           Integer  库存维度：1=房型(ROOM), 2=产品(GOODS)
  ├── modifyInventoryModelList  List<ModifyInventoryModel>
  │     └── ModifyInventoryModel
  │           ├── modifyInventorySubjectsModel
  │           │     ├── dayRoomIdList   List<Integer>  全日房房型ID列表
  │           │     ├── hourRoomIdList  List<Integer>  钟点房房型ID列表
  │           │     └── goodsIdList     List<Long>     产品ID列表（changeType=2时用）
  │           └── unifiedOperateInvDateModel
  │                 ├── modifyDates  List<DateModel>  日期范围（startDate/endDate）
  │                 └── modifyParamByEffectWeeks  List<ModifyWeekInvModel>
  │                       ├── effectWeek  List<Integer>  生效星期 1-7（1=周一…7=周日）
  │                       └── updateInventoryUnifyInvUnitParam
  │                             ├── invSwitch        int  -1=不变, 0=关房, 1=开房
  │                             ├── countType        int  4位编码，见 InvCountTypeEnum
  │                             ├── limitChangeValue int  库存余量变更值（正整数，≤999）
  │                             └── count            int  预留房剩余量变更值（正整数）
  └── extendParam          PrepayExtendParam（可选）

=== countType 常用值 ===

  1520  调整库存剩余量（设置 limitChangeValue 为目标余量），预留房不变
  1920  库存不限量，预留房不变
  1121  同时设置库存总量和预留房绝对量

=== 注意 ===
  - batchUpdateInventory 流程不会强制覆盖 invSwitch（与 batchCreateGoods 不同）
  - 传 invSwitch=1（开房）时，会直接把房态置为"开"（可售卖状态）
  - limitChangeValue 最大 999；count 必须 > 0（即使语义上被忽略时也需传正整数）
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.runner import invoke, InvokeError  # noqa

APPKEY   = "com.sankuai.hotel.biz.platform"
SERVICE  = "com.meituan.hotel.biz.platform.goods.facade.standard.MeInventoryFacade"
METHOD   = "batchUpdateInventory"
# batchUpdateInventory(BatchUpdateInventoryParam param) —— 单参数复杂结构体
# body 模式下 DataUnity 无法自动推断该结构体参数类型，须走显式 parameterTypes 模式
BATCH_UPDATE_INVENTORY_PARAM_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.param.goods.BatchUpdateInventoryParam"
)


def call_batch_update_inventory(
    partner_id: int,
    poi_id: int,
    change_type: int,
    modify_inventory_model_list: list,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    直调 MeInventoryFacade#batchUpdateInventory，修改房态和/或库存。

    参数：
        partner_id                  - 供应商ID
        poi_id                      - 门店ID（int）
        change_type                 - 库存维度：1=房型(ROOM), 2=产品(GOODS)
        modify_inventory_model_list - 修改模型列表，每项结构见模块文档
        swimlane                    - 泳道（空字符串=主干）
        dry_run                     - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：InvokeError（业务失败）
    """
    params = {
        "partnerId":  int(partner_id),
        "poiId":      int(poi_id),
        "changeType": int(change_type),
        "modifyInventoryModelList": modify_inventory_model_list,
    }

    import json as _json
    return invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=None,
        parameter_values=[
            _json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        ],
        parameter_types=[BATCH_UPDATE_INVENTORY_PARAM_TYPE],
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint="修改房态/库存（batchUpdateInventory）...",
    )


def build_modify_model(
    day_room_ids: list = None,
    hour_room_ids: list = None,
    goods_ids: list = None,
    start_date: str = "",
    end_date: str = "",
    effect_weeks: list = None,
    inv_switch: int = -1,
    count_type: int = 1520,
    limit_change_value: int = 299,
    count: int = 1,
) -> dict:
    """
    构造单个 ModifyInventoryModel 便利函数。

    参数：
        day_room_ids        - 全日房房型ID列表（与 hour_room_ids/goods_ids 至少一个非空）
        hour_room_ids       - 钟点房房型ID列表
        goods_ids           - 商品ID列表（changeType=2 时用）
        start_date          - 日期范围起始（格式 YYYY-MM-DD）
        end_date            - 日期范围截止（格式 YYYY-MM-DD）
        effect_weeks        - 生效星期列表，默认 [1,2,3,4,5,6,7]（全周）
        inv_switch          - 房态：-1=不变, 0=关房, 1=开房
        count_type          - 库存变化模式（默认 1520：设置余量，预留房不变）
        limit_change_value  - 库存余量目标值（正整数，≤999，默认 299）
        count               - 预留房变更值（正整数，countType 第4位=0 时被忽略，默认 1）
    """
    if effect_weeks is None:
        effect_weeks = [1, 2, 3, 4, 5, 6, 7]

    return {
        "modifyInventorySubjectsModel": {
            "dayRoomIdList":  [int(r) for r in (day_room_ids or [])],
            "hourRoomIdList": [int(r) for r in (hour_room_ids or [])],
            "goodsIdList":    [int(g) for g in (goods_ids or [])],
        },
        "unifiedOperateInvDateModel": {
            "modifyDates": [{"startDate": start_date, "endDate": end_date}],
            "modifyParamByEffectWeeks": [
                {
                    "effectWeek": effect_weeks,
                    "updateInventoryUnifyInvUnitParam": {
                        "invSwitch":        int(inv_switch),
                        "countType":        int(count_type),
                        "limitChangeValue": int(limit_change_value),
                        "count":            int(count),
                    },
                }
            ],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 房态管理维度切换：房型维度 → 产品维度
# 接口：MeGoodsFacade#changeRoomStatusDimension（与 batchUpdateInventory 不同 Facade）
# ══════════════════════════════════════════════════════════════════════════════

DIMENSION_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"


def call_change_room_status_dimension(
    partner_id: str,
    poi_id: str,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    切换房态管理维度：房型维度 → 产品维度（MeGoodsFacade#changeRoomStatusDimension）。

    ⚠️⚠️⚠️ 高风险不可逆操作 ⚠️⚠️⚠️
      1. 切换后不支持切回房型维度（无逆向接口）。
      2. 切换后需在「产品」维度做开/关房，同一房型下有多个产品时要逐个维护，
         不再是"改一个房型、所有产品共享房态"。
      3. 库存/超售仍然是房型维度（同房型下产品共享库存），只有"开关房态"这一件事
         变成了产品维度，其余不受影响。
      4. 该接口只是**发起**切换（异步）：请求成功仅代表任务已提交，服务端会：
         - 先把维度状态置为「切换中」（ROOM_DIMENSION_CHANGING）
         - 异步线程逐个房型迁移库存/房态数据到产品维度
         - 完成后维度状态最终变为「产品维度」（ROOM_DIMENSION_CHANGE_SUCCESS）
           或「切换失败」（ROOM_DIMENSION_CHANGE_FAILED）
         本接口和本函数都**不做轮询确认**（无对外暴露的维度状态查询接口），
         调用方需要自行等待一段时间或在前端页面确认最终是否切换成功。

    抓包依据（2026-08-18，HTTP 网关 `/api/gw/v1/product/vpoi/changeRoomStatusDimension`，
    与 Thrift `MeGoodsFacade#changeRoomStatusDimension` 底层走同一个
    `RoomStatusServiceImpl.changeRoomStatusDimension` 核心逻辑）：
      请求：{"poiId": "1090269458133536", "partnerId": 4576342}
      响应：{"code": 10000, "data": "hotel_sc_dealing_new_changeRoom_...", "success": true}
      （data 是本次切换任务的流水号/标识字符串，非 goodsId，无法用于轮询）

    参数：
        partner_id  - 供应商ID
        poi_id      - 门店ID（mtPoiId）
        swimlane    - 泳道（空字符串=主干）
        dry_run     - True 时只打印不执行

    返回：RPC 原始响应 dict（data 字段是切换任务标识字符串）
    异常：InvokeError（业务失败，如参数缺失、已切换过、手工直连门店不允许切换等）
    """
    params = {
        "partnerId": int(partner_id),
        "poiId": str(poi_id),
    }
    return invoke(
        appkey=APPKEY,
        service=DIMENSION_SERVICE,
        method="changeRoomStatusDimension",
        params=params,
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint="切换房态管理维度（房型→产品，不可逆）...",
    )

