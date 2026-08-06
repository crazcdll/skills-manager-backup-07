#!/usr/bin/env python3
"""非通兑超团 SPU 提交接口。

直接调用研发 Thrift RPC（与套餐共用同一已注册 OCTO 接口）：
  appkey  : com.sankuai.hotel.biz.platform
  service : com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method  : submitSpu(java.lang.Long userId, SpuModel)
  返回    : MeBaseResult

与旧 MtaSpuFacadeImpl 三参数版本的区别：
  - MeResourceFacade#submitSpu 是标准对外接口，已注册 OCTO，可直接 Thrift 调用
  - 旧 MtaSpuFacadeImpl#submitSpu(partnerId, SpuModel, Boolean) 未注册 OCTO，
    只能通过 HTTP 网关间接调用；现已切换为 MeResourceFacade 直调
  - 第三个 Boolean 参数不再需要——SpuModel 内已包含 autoPublish 等全部业务字段
  - 第一个参数为 userId（操作人），partnerId 在 SpuModel 内

当前登录用户由 invoke() 通过 trace_context.meUser 注入（@Login4Me 切面读取）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.runner import invoke  # noqa

APPKEY = "com.sankuai.hotel.biz.platform"
XGOODS_QUERY_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
XGOODS_QUERY_METHOD = "querySpuXgoodsList"
# 超团 SPU 提交 RPC（与套餐共用 MeResourceFacade，已注册 OCTO）
SUBMIT_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
SUBMIT_METHOD = "submitSpu"
USER_ID_TYPE = "java.lang.Long"
SPU_MODEL_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.model.spu.SpuModel"
)
# 第一个参数为 userId（操作人 ID），与套餐接口 submit_spu_interface.py 一致
SUBMIT_USER_ID = "2196240"
XGOODS_QUERY_TYPE = (
    "com.meituan.hotel.biz.platform.goods.model.xgoods.XgoodsListQueryParam"
)
# 查询 SPU 详情 RPC（与 submitSpu 共用同一 MeResourceFacade，已注册 OCTO）
# 方法签名：getSpuDetail(Long partnerId, Long spuId, Boolean needQueryUniversalImage)
# 返回 MeBaseResult<SpuModel>，在线状态见 data.spuBaseModel.status（0=下架 1=上架 2=归档）
DETAIL_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
DETAIL_METHOD = "getSpuDetail"
LONG_TYPE = "java.lang.Long"
BOOLEAN_TYPE = "java.lang.Boolean"

# 编辑已有 SPU（与 submitSpu 共用同一 MeResourceFacade，已注册 OCTO）
# 方法签名：editSpu(Long partnerId, SpuModel spuModel) —— SpuModel.spuBaseModel.spuId 必填
# 返回 MeBaseResult<SpuOperateResultModel>
EDIT_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
EDIT_METHOD = "editSpu"
PARTNER_ID_TYPE = "java.lang.Long"

# 上下线 SPU（与 submitSpu 共用同一 MeResourceFacade，已注册 OCTO）
# 方法签名：updateSpuStatus(UpdateSpuStatusParam param)
# UpdateSpuStatusParam 关键字段：spuId、partnerId、poiId、status（0=下架 1=上架 2=归档）
# 返回 MeBaseResult<Boolean>
STATUS_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
STATUS_METHOD = "updateSpuStatus"
UPDATE_STATUS_PARAM_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.model.spu.UpdateSpuStatusParam"
)


def validate(partner_id: str, spu_model: dict) -> None:
    """校验 submitSpu 入参（userId + SpuModel）及非通兑超团核心约束。

    SpuModel 标准嵌套结构：
      spuBaseModel.{partnerId, poiId, title, spuType, relatedGoodsNum, relatedPoiNum, ...}
      superDealModel.superDealBaseModel.{spuExchangeType, linePrice, spuSaleStrategyList, ...}
      superDealModel.superDealCouponModel.superDealGiftCardModel.mtPrice
      relatedGoodsList (顶层)
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

    model_partner_id = base.get("partnerId")
    if model_partner_id is None:
        errors.append("spuBaseModel.partnerId 必填")
    # partnerId 校验保留但不与 userId 比较（userId 是操作人，partnerId 在 SpuModel 内）

    if not base.get("poiId"):
        errors.append("spuBaseModel.poiId 必填")
    if not base.get("title"):
        errors.append("spuBaseModel.title 必填")
    if base.get("spuType") != 1:
        errors.append("非通兑超团 spuBaseModel.spuType 必须为 1（超级团购）")

    related_goods = spu_model.get("relatedGoodsList") or []
    if not related_goods:
        errors.append("relatedGoodsList 不能为空")
    if base.get("relatedGoodsNum") != len(related_goods):
        errors.append("spuBaseModel.relatedGoodsNum 必须等于 relatedGoodsList 的实际数量")

    related_poi_num = len(
        {str(item.get("poiId") or base.get("poiId")) for item in related_goods}
    )
    if base.get("relatedPoiNum") != related_poi_num:
        errors.append("spuBaseModel.relatedPoiNum 必须等于关联商品涉及的门店数量")

    # ── superDealModel 路径 ────────────────────────────────────────────
    super_deal = spu_model.get("superDealModel") or {}
    sd_base = super_deal.get("superDealBaseModel") or {}

    if sd_base.get("spuExchangeType") != 1:
        errors.append("非通兑超团 superDealModel.superDealBaseModel.spuExchangeType 必须为 1")

    sale_strategies = sd_base.get("spuSaleStrategyList") or []
    sale_channels = {item.get("saleChannel") for item in sale_strategies}
    if not {1, 2}.issubset(sale_channels):
        errors.append("superDealBaseModel.spuSaleStrategyList 必须同时包含美团和点评渠道（saleChannel=1/2）")

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

    if errors:
        raise ValueError(
            "非通兑超团参数校验失败（共 %d 项）：\n%s"
            % (len(errors), "\n".join(f"  - {error}" for error in errors))
        )


def query_spu_xgoods_list(
    partner_id: str,
    poi_id: str,
    page_num: int = 1,
    page_size: int = 100,
    swimlane: str = "",
) -> list:
    """查询门店下可供超团关联的完整非房模型列表。"""
    query_param = {
        "partnerId": int(partner_id),
        "poiId": int(poi_id),
        "pageNum": page_num,
        "pageSize": page_size,
    }
    response = invoke(
        appkey=APPKEY,
        service=XGOODS_QUERY_SERVICE,
        method=XGOODS_QUERY_METHOD,
        parameter_values=[
            json.dumps(query_param, ensure_ascii=False, separators=(",", ":"))
        ],
        parameter_types=[XGOODS_QUERY_TYPE],
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=True,
        progress_hint=f"查询可关联非房（partnerId={partner_id}, poiId={poi_id}）...",
    )

    data = response.get("data")
    if isinstance(data, list):
        paging_data = data
    elif isinstance(data, dict):
        paging_data = data.get("pagingData")
    else:
        paging_data = response.get("pagingData")
    if paging_data is None:
        raise ValueError(
            "querySpuXgoodsList 响应中缺少 data.pagingData："
            + json.dumps(response, ensure_ascii=False)
        )
    if not isinstance(paging_data, list):
        raise ValueError("querySpuXgoodsList 的 pagingData 必须为数组")
    return paging_data


def get_spu_detail(
    partner_id: str,
    spu_id: str,
    need_query_universal_image: bool = False,
    swimlane: str = "",
    timeout_ms: int = 15000,
) -> dict:
    """调用 MeResourceFacade#getSpuDetail 查询 SPU 详情（含在线状态）。

    与 submitSpu/querySpuXgoodsList 共用同一已注册 OCTO 的 MeResourceFacade，
    可靠性优于 querySpuListPage（后者对超团 spuType=1 查询不可靠，恒返回空列表）。

    返回 MeBaseResult<SpuModel> 原始响应，关键字段：
      data.spuBaseModel.status         SPU 在线状态：0=下架 1=上架 2=归档
      data.spuBaseModel.submitStatus   提交状态
      data.spuAuditModel.auditStatus   审核状态
      data.relatedGoodsList            关联的全日房/直连商品列表
      data.superDealModel.superDealCouponModel.mboxId  魔盒ID（非空代表魔盒已生成）
    """
    return invoke(
        appkey=APPKEY,
        service=DETAIL_SERVICE,
        method=DETAIL_METHOD,
        parameter_values=[
            int(partner_id),
            int(spu_id),
            bool(need_query_universal_image),
        ],
        parameter_types=[LONG_TYPE, LONG_TYPE, BOOLEAN_TYPE],
        swimlane=swimlane,
        timeout_ms=timeout_ms,
        raise_on_biz_error=False,
        progress_hint=f"查询SPU详情（partnerId={partner_id}, spuId={spu_id}）...",
    )


def call_raw(
    partner_id: str,
    spu_model: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """直接调用 MeResourceFacade#submitSpu RPC 提交非通兑超团。

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
        progress_hint=f"通过 RPC 提交非通兑超团（partnerId={partner_id}）...",
    )


def edit_spu(
    partner_id: str,
    spu_model: dict,
    swimlane: str = "",
    dry_run: bool = False,
    timeout_ms: int = 30000,
) -> dict:
    """调用 MeResourceFacade#editSpu RPC 编辑提交已有 SPU。

    两参数版本：editSpu(Long partnerId, SpuModel spuModel)。
    与 submitSpu 的关键区别：spu_model.spuBaseModel.spuId 必须传入目标已有 SPU 的
    spuId（submitSpu 创建时会主动 pop 掉该字段，editSpu 反而要求必填），
    后端据此判定为"更新"而非"新建"。
    第一个参数为 partnerId（与 submitSpu 的 userId 不同，这里官方签名即 partnerId）。
    返回 MeBaseResult<SpuOperateResultModel>。
    业务错误由 invoke() 的 raise_on_biz_error 自动抛出 InvokeError。

    ⚠️ 字段来源：spuId 需从 get_spu_detail() 查询结果的 spuBaseModel.spuId 获取，
    建议以 get_spu_detail 返回的完整 SpuModel 为基础做增量修改后再传入本函数，
    避免因字段缺失被后端判定为"清空"某些模块。

    ✅ 已实测验证的关键用途（2026-07-22）：submitSpu 提交后 SPU 长期停留在
    status=0（下架）且 spuAuditModel.auditMsg 出现"13001提交审核失败"/
    "基本信息模块未入库"时，官方报错提示为"请点击编辑按钮，不修改任何信息重新提交
    一次"——直调 update_spu_status(status=1) 会复现同样的 13001 报错（因为基本信息
    模块本身未入库，无法直接上线）。正确修复方式：
      1. get_spu_detail() 取回完整 SpuModel（含 spuId）
      2. 不做任何字段修改，原样传给 edit_spu()
      3. edit_spu 成功后等待约 20-30s，SPU 会自动完成入库+上架（status 0→1），
         无需额外调用 update_spu_status
    """
    base = (spu_model or {}).get("spuBaseModel") or {}
    if not base.get("spuId"):
        raise ValueError("editSpu 要求 spuModel.spuBaseModel.spuId 必填（目标已有 SPU 的 spuId）")
    return invoke(
        appkey=APPKEY,
        service=EDIT_SERVICE,
        method=EDIT_METHOD,
        parameter_values=[
            int(partner_id),
            json.dumps(spu_model, ensure_ascii=False, separators=(",", ":")),
        ],
        parameter_types=[PARTNER_ID_TYPE, SPU_MODEL_TYPE],
        swimlane=swimlane,
        timeout_ms=timeout_ms,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"通过 RPC 编辑提交 SPU（partnerId={partner_id}, spuId={base.get('spuId')}）...",
    )


def update_spu_status(
    partner_id: str,
    spu_id: str,
    poi_id: str = "",
    status: int = 1,
    swimlane: str = "",
    dry_run: bool = False,
    timeout_ms: int = 30000,
) -> dict:
    """调用 MeResourceFacade#updateSpuStatus RPC 手动上/下线 SPU。

    方法签名：updateSpuStatus(UpdateSpuStatusParam param)，单个复合对象入参。
    UpdateSpuStatusParam 关键字段：spuId、partnerId、poiId、status。
      status: 0=下架 1=上架/上线 2=归档
    返回 MeBaseResult<Boolean>。

    ⚠️ 已实测验证（2026-07-22）：若 SPU 停留在 status=0 的原因是"基本信息模块未
    入库"（spuAuditModel.auditMsg 含"13001提交审核失败"），直接调用本函数
    status=1 会失败，报错与官方一致：
      "1、基本信息模块未入库，13001提交审核失败
       2、请点击编辑按钮，不修改任何信息重新提交一次，如果操作后仍无法上线，
          请联系工作人员"
    此时应先调用 edit_spu()（见其文档字符串的修复步骤），SPU 会在 editSpu 成功
    后自动完成入库+上架，无需再调用本函数。
    本函数仅适用于基本信息模块已正常入库、但仍需要显式上/下线切换的场景。
    """
    param = {
        "spuId": int(spu_id),
        "partnerId": int(partner_id),
        "status": int(status),
    }
    if poi_id:
        param["poiId"] = str(poi_id)
    return invoke(
        appkey=APPKEY,
        service=STATUS_SERVICE,
        method=STATUS_METHOD,
        parameter_values=[
            json.dumps(param, ensure_ascii=False, separators=(",", ":"))
        ],
        parameter_types=[UPDATE_STATUS_PARAM_TYPE],
        swimlane=swimlane,
        timeout_ms=timeout_ms,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"通过 RPC 变更 SPU 状态（partnerId={partner_id}, spuId={spu_id}, status={status}）...",
    )

