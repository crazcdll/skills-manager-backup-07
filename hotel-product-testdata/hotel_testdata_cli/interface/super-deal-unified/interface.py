#!/usr/bin/env python3
"""通兑超团 SPU 提交接口。

直接调用研发 Thrift RPC（与套餐/非通兑超团共用同一已注册 OCTO 接口）：
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

通兑与非通兑的关键区别：
  - spuExchangeType=0（非通兑为 1）
  - poiId=null（非通兑为真实单门店 ID）
  - relatedGoodsList 包含 ≥2 个不同门店的全日房
  - autoPublish=false（需 BPM 审核；非通兑为 true 自动上线）
  - superDealSieveModel.topPoiList 包含所有通兑门店 poiId
  - 响应同步返回 spuId（data.spuId）

⚠️ online_switch 仍走 MTA HTTP 网关（研发未提供对应 RPC）。
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.runner import invoke  # noqa

APPKEY = "com.sankuai.hotel.biz.platform"
# 超团 SPU 提交 RPC（与套餐共用 MeResourceFacade，已注册 OCTO）
SUBMIT_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
SUBMIT_METHOD = "submitSpu"
USER_ID_TYPE = "java.lang.Long"
SPU_MODEL_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.model.spu.SpuModel"
)
# 第一个参数为 userId（操作人 ID），与套餐接口 submit_spu_interface.py 一致
SUBMIT_USER_ID = "2196240"
# online_switch 仍走 MTA HTTP 网关（研发未提供对应 RPC）
ONLINE_SWITCH_URL = "https://mta.hotel.test.sankuai.com/api/v1/mta/prepay/partner/{partner_id}/spu/onlineSwitch"

# 上下线 SPU（与 submitSpu 共用同一 MeResourceFacade，已注册 OCTO，与非通兑超团/套餐一致）
# 方法签名：updateSpuStatus(UpdateSpuStatusParam param)
# UpdateSpuStatusParam 关键字段：spuId、partnerId、poiId、status（0=下架 1=上架 2=归档）
# 返回 MeBaseResult<Boolean>
STATUS_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
STATUS_METHOD = "updateSpuStatus"
UPDATE_STATUS_PARAM_TYPE = (
    "com.meituan.hotel.biz.platform.goods.facade.model.spu.UpdateSpuStatusParam"
)


def validate(partner_id: str, spu_model: dict) -> None:
    """校验通兑超团核心约束。

    SpuModel 标准嵌套结构：
      spuBaseModel.{partnerId, poiId(null), title, spuType, relatedGoodsNum, relatedPoiNum}
      superDealModel.superDealBaseModel.{spuExchangeType=0, linePrice, spuSaleStrategyList}
      superDealModel.superDealCouponModel.{superDealGiftCardModel.mtPrice, superDealSieveModel.topPoiList}
      relatedGoodsList (顶层，每个含 poiIdStr + goodsId)
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

    if not base.get("title"):
        errors.append("spuBaseModel.title 必填")

    # 通兑 poiId 应为 null
    if base.get("poiId") is not None:
        errors.append("通兑超团 spuBaseModel.poiId 必须为 null（不绑定单门店）")

    # ── superDealModel 路径 ────────────────────────────────────────────
    super_deal = spu_model.get("superDealModel") or {}
    sd_base = super_deal.get("superDealBaseModel") or {}

    if sd_base.get("spuExchangeType") != 0:
        errors.append("通兑超团 superDealModel.superDealBaseModel.spuExchangeType 必须为 0")

    # ── relatedGoodsList（顶层）──────────────────────────────────────
    related_goods = spu_model.get("relatedGoodsList") or []
    if len(related_goods) < 2:
        errors.append(
            f"通兑超团 relatedGoodsList 至少需要 2 个门店的商品（当前: {len(related_goods)}）"
        )

    # 检查每个商品都有 poiIdStr 和 goodsId
    for idx, item in enumerate(related_goods):
        if not item.get("poiIdStr"):
            errors.append(f"relatedGoodsList[{idx}].poiIdStr 必填")
        if not item.get("goodsId"):
            errors.append(f"relatedGoodsList[{idx}].goodsId 必填")

    # 检查涉及门店数 ≥2
    poi_ids = {
        str(item.get("poiIdStr"))
        for item in related_goods
        if item.get("poiIdStr")
    }
    if len(poi_ids) < 2:
        errors.append(
            f"通兑超团 relatedGoodsList 涉及门店数必须 ≥2（当前: {len(poi_ids)}）"
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

    # topPoiList 校验
    sieve_model = coupon_model.get("superDealSieveModel") or {}
    top_poi_list = sieve_model.get("topPoiList") or []
    if len(top_poi_list) < 2:
        errors.append(
            f"superDealSieveModel.topPoiList 至少需要 2 个门店 ID（当前: {len(top_poi_list)}）"
        )

    if errors:
        raise ValueError(
            "通兑超团参数校验失败（共 %d 项）：\n%s"
            % (len(errors), "\n".join(f"  - {e}" for e in errors))
        )


def call_raw(
    partner_id: str,
    spu_model: dict,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """直接调用 MeResourceFacade#submitSpu RPC 提交通兑超团。

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
        progress_hint=f"通过 RPC 提交通兑超团（partnerId={partner_id}）...",
    )


def extract_spu_id(response: dict) -> str:
    """从 submitSpu RPC 响应中提取 spuId。

    MeBaseResult 响应格式：{"data": {"spuId": 2257105845, ...}, "code": 0, "success": true}
    """
    data = response.get("data")
    if isinstance(data, dict):
        spu_id = data.get("spuId")
        if spu_id is not None:
            return str(spu_id)
    # 兼容非通兑的顶层提取
    for key in ("spuId", "id", "productId"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    if isinstance(data, (int, str)) and str(data) not in ("", "None", "null"):
        return str(data)
    return ""


def online_switch(partner_id: str, spu_id: str, status: int = 1, swimlane: str = "") -> dict:
    """通过 MTA HTTP 网关切换 SPU 上下线状态。

    POST /api/v1/mta/prepay/partner/{partnerId}/spu/onlineSwitch
    payload: {"partnerId":"<partnerId>","poiId":"","spuId":<spuId>,"status":<status>}
      status: 1=上线, 2=下线

    通过 mtcurl CLI 携带浏览器 ssoid 发起请求。
    """
    url = ONLINE_SWITCH_URL.format(partner_id=int(partner_id))
    body = json.dumps({
        "partnerId": str(partner_id),
        "poiId": "",
        "spuId": int(spu_id),
        "status": status,
    }, ensure_ascii=False, separators=(",", ":"))

    mtcurl = shutil.which("mtcurl")
    if not mtcurl:
        raise RuntimeError(
            "缺少 mtcurl，无法携带 MTA 网关要求的浏览器 ssoid；请安装："
            "UV_INDEX_URL=https://pypi.sankuai.com/simple/ uv tool install mt-curl-cli"
        )
    command = [
        mtcurl, "--test-env", "-X", "POST",
        "-H", "Content-Type: application/json",
    ]
    if swimlane:
        command.extend(["-H", f"M-Swimlane:{swimlane}"])
    command.extend(["-d", body, "-m", "30", url])

    action_text = "上线" if status == 1 else "下线"
    print(f"⏳ 通过 MTA 网关{action_text}通兑超团（spuId={spu_id}, partnerId={partner_id}）...", flush=True)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"MTA 网关返回非 JSON 内容：{completed.stdout[:500]}"
        ) from error
    if result.get("status") not in (0, None):
        raise RuntimeError(
            result.get("message") or json.dumps(result, ensure_ascii=False)
        )
    return result


def update_spu_status(
    partner_id: str,
    spu_id: str,
    poi_id: str = "",
    status: int = 1,
    swimlane: str = "",
    dry_run: bool = False,
    timeout_ms: int = 30000,
) -> dict:
    """调用 MeResourceFacade#updateSpuStatus RPC 直接上/下线通兑超团 SPU（Thrift 直调）。

    与非通兑超团/套餐共用同一已注册 OCTO 的 MeResourceFacade 接口，方法签名一致：
      updateSpuStatus(UpdateSpuStatusParam param)
      UpdateSpuStatusParam 关键字段：spuId、partnerId、poiId、status
        status: 0=下架 1=上架/上线 2=归档
    返回 MeBaseResult<Boolean>。
    业务错误由 invoke() 的 raise_on_biz_error 自动抛出 InvokeError。

    ⚠️ 仅适用于基本信息模块/关联选单/关联魔盒均已正常入库、只是需要显式上下线切换的场景
    （即 mboxId 非空、couponAuditStatus/giftCardAuditStatus/sieveAuditStatus 均为 4）。
    若 SPU 仍处于「基本信息模块未入库」（13001提交审核失败）等未完全入库状态，直调本函数
    大概率会复现同样报错，应先走 edit_spu 修复（见 super-deal/interface.py 的 edit_spu 文档）。

    相比 online_switch（走 MTA HTTP 网关，依赖 mtcurl + 浏览器 ssoid），本函数直接走
    Thrift RPC，更稳定、不依赖浏览器登录态，优先使用本函数。
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
        progress_hint=f"通过 RPC 变更通兑超团 SPU 状态（partnerId={partner_id}, spuId={spu_id}, status={status}）...",
    )

