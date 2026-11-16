#!/usr/bin/env python3
"""商促通兑超团 SPU 提交接口。

直接调用研发 Thrift RPC（与非通兑/普通通兑超团共用同一已注册 OCTO 接口）：
  appkey  : com.sankuai.hotel.biz.platform
  service : com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method  : submitSpu(java.lang.Long userId, SpuModel)
  返回    : MeBaseResult

MTA 前端（mta.hotel 网关 /api/v1/mta/prepay/partner/{partnerId}/spu/submit）创建
商促通兑超团时，后端最终也是调到同一个 submitSpu RPC——网关的扁平 DTO 会被
转换为标准嵌套 SpuModel（商促关联字段映射到
superDealModel.superDealRelatedModel.spuPromoActivityModel），因此本 skill
直接走 RPC 直调，不依赖 mtcurl + 浏览器 ssoid。

字段映射依据（线上成功抓包 traceId=0a15e4e7844b1789030427605，spuId=2257594710，
partnerId=4570390 的网关请求 → 嵌套 SpuModel）：
  网关扁平 relatePromoActivityModel{promoActivityId, sieveGoodsId}
    → superDealRelatedModel.spuPromoActivityModel{promoActivityId, sieveGoodsId}
  网关扁平 spuExchangeType=2 → superDealBaseModel.spuExchangeType=2
  网关扁平 linePrice         → superDealBaseModel.linePrice
  网关扁平 superDealCouponModel（扁平内嵌）→ superDealModel.superDealCouponModel

商促通兑超团关键特征（与普通通兑 spuExchangeType=0 的差异）：
  - spuExchangeType=2（非通兑=1，普通通兑=0，商促通兑=2）
  - poiId=null、relatedGoodsList=[]（不绑定固定门店和产品，
    无需走全日房 W1 / 非房 W3 前置流程）
  - superDealRelatedModel.spuPromoActivityModel 必填（关联商促活动 +
    选择选单，promoActivityId/sieveGoodsId 必须由用户提供，
    且必须是测试环境真实存在的活动/选单 ID）
  - autoPublish=false（需 auditProduct 审核 + updateSpuStatus 上线，
    与普通通兑一致，复用 factory/audit/super-deal-unified/audit.py）
  - superDealSieveModel.topPoiList=[]（选单覆盖门店由后端按商促活动
    动态解析，不在创建时指定）
  - mBoxId=null（响应会返回 bizacctid，由后端自动创建）

⚠️ 网关请求里的 writeNewSellStrategy=true / zlActivityModelList / activityIds
   等字段为网关层 DTO 字段，标准嵌套 SpuModel 无对应字段，直调 RPC 无需传。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.runner import invoke  # noqa

APPKEY = "com.sankuai.hotel.biz.platform"
# 超团 SPU 提交 RPC（与套餐/非通兑/普通通兑共用 MeResourceFacade，已注册 OCTO）
SUBMIT_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
SUBMIT_METHOD = "submitSpu"
USER_ID_TYPE = "java.lang.Long"
SPU_MODEL_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.model.spu.SpuModel"
)
# 第一个参数为 userId（操作人 ID），与非通兑/普通通兑一致
SUBMIT_USER_ID = "2196240"


def validate(partner_id: str, spu_model: dict) -> None:
    """校验商促通兑超团核心约束。

    SpuModel 标准嵌套结构（商促通兑）：
      spuBaseModel.{partnerId, poiId(null), title, spuType=1, autoPublish=false}
      superDealModel.superDealBaseModel.{spuExchangeType=2, linePrice, spuSaleStrategyList}
      superDealModel.superDealRelatedModel.spuPromoActivityModel.{promoActivityId, sieveGoodsId}
      superDealModel.superDealCouponModel.superDealGiftCardModel.mtPrice
      relatedGoodsList=[]（顶层，不关联产品）
    """
    errors = []

    if not partner_id:
        errors.append("RPC 第一个参数 userId 必填")
    else:
        try:
            int(partner_id)
        except (TypeError, ValueError):
            errors.append(f"userId={partner_id!r} 必须为整数")

    if not isinstance(spu_model, dict):
        raise ValueError("SpuModel 必须为 JSON 对象")

    # ── spuBaseModel 路径 ──────────────────────────────────────────────
    base = spu_model.get("spuBaseModel") or {}

    if base.get("partnerId") is None:
        errors.append("spuBaseModel.partnerId 必填")

    if not base.get("title"):
        errors.append("spuBaseModel.title 必填")

    # 商促通兑 poiId 应为 null（不绑定单门店）
    if base.get("poiId") is not None:
        errors.append("商促通兑超团 spuBaseModel.poiId 必须为 null（不绑定单门店）")

    # ── superDealModel 路径 ────────────────────────────────────────────
    super_deal = spu_model.get("superDealModel") or {}
    sd_base = super_deal.get("superDealBaseModel") or {}

    if sd_base.get("spuExchangeType") != 2:
        errors.append("商促通兑超团 superDealModel.superDealBaseModel.spuExchangeType 必须为 2")

    # ── spuPromoActivityModel（商促核心必填字段）──────────────────────
    sd_related = super_deal.get("superDealRelatedModel") or {}
    promo = sd_related.get("spuPromoActivityModel") or {}
    if not promo.get("promoActivityId"):
        errors.append(
            "superDealRelatedModel.spuPromoActivityModel.promoActivityId 必填"
            "（关联商促活动 ID，须由用户提供）"
        )
    if not promo.get("sieveGoodsId"):
        errors.append(
            "superDealRelatedModel.spuPromoActivityModel.sieveGoodsId 必填"
            "（选择选单 ID，须由用户提供）"
        )

    # ── relatedGoodsList（顶层，商促必须为空）─────────────────────────
    related_goods = spu_model.get("relatedGoodsList") or []
    if related_goods:
        errors.append(
            f"商促通兑超团 relatedGoodsList 必须为空（不关联固定产品，当前: {len(related_goods)} 个）"
        )

    # 销售策略
    sale_strategies = sd_base.get("spuSaleStrategyList") or []
    sale_channels = {item.get("saleChannel") for item in sale_strategies}
    if not {1, 2}.issubset(sale_channels):
        errors.append(
            "superDealBaseModel.spuSaleStrategyList 必须同时包含美团和点评渠道（saleChannel=1/2）"
        )

    # 价格校验
    coupon_model = super_deal.get("superDealCouponModel") or {}
    gift_card = coupon_model.get("superDealGiftCardModel") or {}
    sale_price = gift_card.get("mtPrice")
    line_price = sd_base.get("linePrice")
    if not isinstance(sale_price, int) or sale_price <= 0:
        errors.append("superDealCouponModel.superDealGiftCardModel.mtPrice 必须为正整数，单位为分")
    if not isinstance(line_price, int) or line_price <= 0:
        errors.append("superDealBaseModel.linePrice 必须为正整数，单位为分")
    elif isinstance(sale_price, int) and line_price < sale_price:
        errors.append("linePrice 不能小于 mtPrice")

    # topPoiList 校验（商促不绑定门店，应为空）
    sieve_model = coupon_model.get("superDealSieveModel") or {}
    top_poi_list = sieve_model.get("topPoiList") or []
    if top_poi_list:
        errors.append(
            f"商促通兑超团 superDealSieveModel.topPoiList 必须为空（选单门店由后端按商促活动动态解析，当前: {len(top_poi_list)} 个）"
        )

    if errors:
        raise ValueError(
            "商促通兑超团参数校验失败（共 %d 项）：\n%s"
            % (len(errors), "\n".join(f"  - {e}" for e in errors))
        )


def call_raw(
    partner_id: str,
    spu_model: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """直接调用 MeResourceFacade#submitSpu RPC 提交商促通兑超团。

    两参数版本：submitSpu(Long userId, SpuModel spuModel)。
    第一个参数为 userId（操作人），partnerId 在 SpuModel 内。
    当前登录用户由 invoke() 通过 trace_context.meUser 注入。
    业务错误由 invoke() 的 raise_on_biz_error 自动抛出 InvokeError。
    """
    validate(partner_id, spu_model)
    return invoke(
        appkey=APPKEY,
        service=SUBMIT_SERVICE,
        method=SUBMIT_METHOD,
        parameter_values=[
            SUBMIT_USER_ID,
            json.dumps(spu_model, ensure_ascii=False, separators=(",", ":")),
        ],
        parameter_types=[USER_ID_TYPE, SPU_MODEL_TYPE],
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"通过 RPC 提交商促通兑超团（partnerId={partner_id}）...",
    )


def extract_spu_id(response: dict) -> str:
    """从 submitSpu RPC 响应中提取 spuId。

    MeBaseResult 响应格式：{"data": {"spuId": 2257594710, ...}, "code": 0, "success": true}
    """
    data = response.get("data")
    if isinstance(data, dict):
        spu_id = data.get("spuId")
        if spu_id is not None:
            return str(spu_id)
    # 兼容顶层提取
    for key in ("spuId", "id", "productId"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    if isinstance(data, (int, str)) and str(data) not in ("", "None", "null"):
        return str(data)
    return ""

