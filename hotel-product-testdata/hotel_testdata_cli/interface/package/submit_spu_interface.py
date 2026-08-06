#!/usr/bin/env python3
"""
接口层：套餐创建 V2（MeResourceFacade#submitSpu）

直接 Thrift RPC 调用（同步接口）：
  appKey : com.sankuai.hotel.biz.platform
  service: com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method : submitSpu

与旧版 工具10（DataUnity 异步）的区别：
  - 本接口为研发级同步接口，直接返回 spuId，无需等待大象推送
  - 支持在创建套餐时直接关联 xGoodsId（非房）和 goodsId（全日房产品）
  - 接口层不感知业务编排，仅负责参数组装和 RPC 调用

前置依赖（调用方负责准备）：
  - partnerId / poiId（门店/供应商）
  - xGoodsId（非房 ID，通过 factory/non-room/create-non-room.py 创建）
  - goodsId / goodsName / realRoomName（全日房产品，通过创建全日房或用户传入）
"""

import copy
import json
import os
import sys
import time
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# ── 接口配置 ────────────────────────────────────────────────────────────────
APPKEY  = "com.sankuai.hotel.biz.platform"
SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
METHOD  = "submitSpu"

# ── 从 schema.json 加载默认模板 ──────────────────────────────────────────
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "../../factory/package/schema.json")


def _load_default_template() -> dict:
    """从 schema.json 读取默认请求模板。"""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    template = schema.get("default_template", {})
    # 过滤掉 _ 开头的注释字段
    return {k: v for k, v in template.items() if not k.startswith("_")}


# ════════════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════════════

def _make_xgoods_model(
    partner_id: str,
    poi_id: str,
    xgoods_id: int,
    xgoods_name: str,
    weight: int = 0,
) -> dict:
    """
    构建 relateXgoodsInfoModels 单元。

    参数：
        partner_id  - 供应商ID（str）
        poi_id      - 门店ID（str）
        xgoods_id   - 非房 ID（int）
        xgoods_name - 非房名称（str，用于填写 name 字段）
        weight      - 排列权重（默认 0）
    """
    return {
        "basicInfoModel": {
            "extAttrs": {},
            "partnerId": int(partner_id),
            "poiId": str(poi_id),
            "xgoodsId": int(xgoods_id),
            "name": xgoods_name,
            "priType": 22,
            "secType": 158004,
            "content": "双人适用。9:00开餐至17:00，凭确认短信直接使用。",
            "onlineStatus": 1,
            "auditStatus": 3,
            "flowStatus": 3,
            "images": [
                {
                    "type": 102,
                    "imageModels": [
                        {
                            "statusCode": 1,
                            "verifyDesc": None,
                            "subVerifyDesc": None,
                            "hitKey": None,
                            "machineAudit": None,
                            "type": None,
                            "imageId": 1359476616925367,
                            "rank": 1,
                            "url": "http://p0.inf.test.sankuai.com/testhubble/16f2742cecedadffa05a62242424ff61547081.jpg",
                            "imageSize": "1536x2048",
                            "onlineStatus": 1,
                        }
                    ],
                }
            ],
            "relateVpoiGoods": {
                "xgoodsId": int(xgoods_id),
                "relationVpoiList": [
                    {
                        "partnerId": int(partner_id),
                        "relatedPoiList": [
                            {
                                "poiId": str(poi_id),
                                "partnerId": int(partner_id),
                            }
                        ],
                    }
                ],
            },
            "parentXgoods": True,
            "crossVpoi": False,
            "xgoodsTags": [{"tagCode": 1, "tagName": "核心", "tagStatus": 1}],
        },
        "bindPoiInfoModel": {
            "extAttrs": None,
            "bindPoiId": None,
            "cityName": None,
            "cityId": None,
            "bindPoiName": None,
            "bindPoiAddress": None,
            "bindPoiDistance": None,
            "partnerPhoneNumber": None,
            "provinceId": None,
            "provinceName": None,
            "bindPoiIdStr": None,
        },
        "priceModel": {
            "marketPrice": None,
            "salePrice": None,
            "priceProofUrls": [],
            "priceProofType": None,
        },
        "itemInfoModel": {
            "extAttrs": {},
            "itemContents": [],
            "itemProofUrls": None,
            "priceProofType": None,
        },
        "ruleModel": {
            "showType": 0,
            "useRuleModel": {
                "extAttrs": {
                    "needVerifyIdCard": "0",
                    "useWayEnDesc": "",
                    "ticketInfoList": "",
                },
                "quantityRule": 3,
                "businessHours": [
                    {
                        "startTime": "9:00",
                        "endTime": "17:00",
                        "startDate": None,
                        "endDate": None,
                        "effectWeek": [1, 2, 3, 4, 5, 6, 7],
                    }
                ],
                "suitableCount": {
                    "adultMax": 2,
                    "adultMin": 2,
                    "child": 0,
                    "older": 0,
                    "countType": 1,
                },
                "ageLimit": {
                    "ageLimitType": 0,
                    "adultMaxAge": None,
                    "adultMinAge": None,
                    "childMaxAge": None,
                    "childMinAge": None,
                    "olderMaxAge": None,
                    "olderMinAge": None,
                },
                "useWay": 1,
                "certificate": None,
                "contactsInfo": {"contactsInfoTypes": [1, 2]},
                "touristsInfo": {"featureType": 1, "touristsInfoTypes": []},
            },
            "bookingRuleModel": {
                "extAttrs": None,
                "bookingType": 1,
                "preBookingDays": None,
                "preBookingTime": None,
                "preBookingHours": None,
            },
        },
        "weight": weight,
    }


def _make_goods_model(
    goods_id: int,
    goods_name: str,
    real_room_name: str,
    goods_source: int = 1,
    noPersist: int = 0,
    status: int = 2,
    latest_booking_days: int = -1,
) -> dict:
    """
    构建 relatedGoodsList 单元（关联全日房产品）。

    参数：
        goods_id           - 全日房产品ID（int）
        goods_name         - 产品名称（str）
        real_room_name     - 真实房型名称（str）
        goods_source       - 商品来源（1=预付）
        noPersist          - 是否不持久化（0=持久化）
        status             - 产品状态（2=上架）
        latest_booking_days - 最晚预订天数（-1=不限）
    """
    return {
        "goodsId": int(goods_id),
        "goodsName": str(goods_name),
        "goodsSource": int(goods_source),
        "noPersist": int(noPersist),
        "status": int(status),
        "latestBookingDays": int(latest_booking_days),
        "realRoomName": str(real_room_name),
    }


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数
# ════════════════════════════════════════════════════════════════════════════

def call(
    partner_id: str,
    poi_id: str,
    xgoods_id: int,
    xgoods_name: str,
    goods_id: int,
    goods_name: str,
    real_room_name: str,
    title: str = "",
    check_days: int = 2,
    goods_source: int = 1,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    直接 Thrift RPC 调用 MeResourceFacade#submitSpu 创建套餐（同步接口）。

    套餐名称（giftsName/title）不支持用户自定义任意值，但 nameCustomerType=DEFAULT（默认值 0，
    本接口固定使用）分支下后端也不会自动拼接兜底：不传则落库为空字符串。
    如需一个非空的展示名称，需调用方自行按约定格式拼接后传入（如 "<门店名><间夜数>晚+<非房名>"）。

    参数：
        partner_id      - 供应商ID（str）
        poi_id          - 门店ID（str）
        xgoods_id       - 非房 ID（int，由 create-non-room.py 创建后获得）
        xgoods_name     - 非房名称（str）
        goods_id        - 全日房/直连产品ID（int）
        goods_name      - 产品名称（str）
        real_room_name  - 真实房型名称（str）
        title           - 套餐展示名称（giftsName/title，默认空字符串；建议调用方按
                          "<门店名><间夜数>晚+<非房名>" 格式拼接后传入）
        check_days      - 套餐包含的入住晚数（默认 2 晚）
        goods_source    - 商品来源（1=预付自建，2=直连落地，3=直连不落地；默认 1）
        swimlane        - 泳道（空=主干）
        dry_run         - True 时只打印不执行

    返回：接口原始响应 dict（同步接口，成功时包含 spuId）
    """
    from scripts.runner import invoke as rpc_invoke  # noqa

    # ── 从模板加载基础结构 ────────────────────────────────────────────────
    template = _load_default_template()
    params = copy.deepcopy(template)

    # ── 填充动态字段 ──────────────────────────────────────────────────────
    # spuBaseModel
    # 注意：nameCustomerType=DEFAULT 分支下 title 非必填，但不传不会被后端自动拼接，
    # 落库即为空字符串；如需非空展示名称需由调用方自行拼接后传入
    params["spuBaseModel"]["partnerId"] = int(partner_id)
    params["spuBaseModel"]["poiId"] = str(poi_id)
    params["spuBaseModel"]["giftsName"] = title or ""
    params["spuBaseModel"]["title"] = title or ""

    # dayTripModel
    params["dayTripModel"]["spuCheckDays"] = check_days

    # relateXgoodsInfoModels（非房关联）
    params["relateXgoodsInfoModels"] = [
        _make_xgoods_model(
            partner_id=partner_id,
            poi_id=poi_id,
            xgoods_id=xgoods_id,
            xgoods_name=xgoods_name,
        )
    ]

    # relatedGoodsList（全日房/直连产品关联）
    params["relatedGoodsList"] = [
        _make_goods_model(
            goods_id=goods_id,
            goods_name=goods_name,
            real_room_name=real_room_name,
            goods_source=goods_source,
        )
    ]

    # submitSpu 接口签名：submitSpu(java.lang.Long userId, SpuModel)
    # parameter_values 中复杂对象需传 JSON 字符串，基础类型直接传字符串
    import json as _json
    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=None,
        parameter_values=["2196240", _json.dumps(params, ensure_ascii=False)],
        parameter_types=["java.lang.Long", "com.meituan.hotel.biz.platform.goods.facade.model.spu.SpuModel"],
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=(
            f"直调 MeResourceFacade#submitSpu"
            f"（partnerId={partner_id}, poiId={poi_id}）..."
        ),
    )


def call_with_raw_params(
    raw_params: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    使用完整原始参数调用 submitSpu（高级用法，支持完全自定义请求体）。

    参数：
        raw_params - 完整请求 dict，与 submitSpu 接口参数格式一致
        swimlane   - 泳道（空=主干）
        dry_run    - True 时只打印不执行
    """
    from scripts.runner import invoke as rpc_invoke  # noqa

    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=raw_params,
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"直调 MeResourceFacade#submitSpu（自定义参数）...",
    )


# ════════════════════════════════════════════════════════════════════════════
# 查询套餐列表页（querySpuListPage）
# ════════════════════════════════════════════════════════════════════════════

QUERY_METHOD = "querySpuListPage"


def query_spu_list_page(
    partner_id,
    poi_id,
    spu_id=None,
    spu_type: int = 0,
    page_num: int = 1,
    page_size: int = 10,
    spu_second_type=None,
    on_line_status=None,
    goods_id=None,
    xgoods_id=None,
    swimlane: str = "",
    timeout_ms: int = 10000,
) -> dict:
    """
    查询套餐列表分页（MeResourceFacade#querySpuListPage）。

    用于验证 submitSpu 创建的套餐 B 端数据是否生效：
      - data.list[0].spuBaseModel.status == 1       （已上线）
      - data.list[0].spuAuditModel.auditStatus == 4  （审核通过）

    参数：
        partner_id      - 供应商ID
        poi_id          - 门店ID（字符串或整数）
        spu_id          - 套餐ID（精确筛选，可选）
        spu_type        - 套餐类型（0=普通套餐，默认 0）
        page_num        - 页码（默认 1）
        page_size       - 每页条数（默认 10）
        spu_second_type - 二级类型（可选）
        on_line_status  - 上线状态筛选（可选）
        goods_id        - 关联全日房ID（可选）
        xgoods_id       - 关联非房ID（可选）
        swimlane        - 泳道（空字符串=主干）
        timeout_ms      - 超时毫秒（默认 10000）

    返回：完整响应 dict，含 data.list 及分页信息
    """
    from scripts.runner import invoke as rpc_invoke  # noqa

    params = {
        "poiId":         str(poi_id),
        "partnerId":     int(partner_id),
        "spuType":       spu_type,
        "pageNum":       page_num,
        "pageSize":      page_size,
        "spuSecondType": spu_second_type,
        "onLineStatus":  on_line_status,
        "goodsId":       int(goods_id) if goods_id is not None else None,
        "xgoodsId":      int(xgoods_id) if xgoods_id is not None else None,
        "spuId":         int(spu_id) if spu_id is not None else None,
    }

    hint = f"查询套餐列表 partnerId={partner_id} poiId={poi_id}"
    if spu_id:
        hint += f" spuId={spu_id}"

    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=QUERY_METHOD,
        params=params,
        swimlane=swimlane,
        timeout_ms=timeout_ms,
        raise_on_biz_error=False,
        progress_hint=hint + "...",
    )

