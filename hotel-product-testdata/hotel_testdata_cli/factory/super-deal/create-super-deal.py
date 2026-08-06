#!/usr/bin/env python3
"""通过 MeResourceFacade#submitSpu 创建非通兑超团。

直接调用研发 Thrift RPC（与套餐共用同一已注册 OCTO 接口）：
  appkey  : com.sankuai.hotel.biz.platform
  service : com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method  : submitSpu(Long userId, SpuModel spuModel)

以 ME 成功抓包的完整 SpuModel 为模板输入，避免用旧 DataUnity
工具参数猜测研发 DTO。可通过 --payload-file 或 --payload-json 传入模板，脚本
负责覆盖本次构造的动态字段、校验并调用 Thrift RPC。

====================================================================
【前置说明：专属全日房需先单独创建，与套餐（W4）编排方式一致】

  本脚本不再自动创建专属全日房，必须先按 W1 流程
  （factory/fullday/create-fullday.py）单独创建好一条全日房，
  再通过 --goods-id 传入本脚本，脚本仅负责组装 relatedGoodsList
  并提交超团。

  全日房的售价必须满足超团公式：
    全日房基础卖价 = 超团价格(mtPrice) ÷ 间夜(roomNights)

  可先用 --calc-fullday-price 打印出这个价格以及可直接粘贴给
  create-fullday.py 的 --set 参数（见下方【使用示例】），减少手工
  换算 JSON 出错的概率。
====================================================================
"""

from __future__ import annotations

import argparse
import copy
import importlib.util as ilu
import json
import os
import sys
import time
from datetime import datetime, time as datetime_time, timedelta
from zoneinfo import ZoneInfo

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../../"))
sys.path.insert(0, ROOT)
SCHEMA_PATH = os.path.join(_SCRIPT_DIR, "schema.json")
CHINA_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_BANNER_IMAGES = [
    {"imageId": 1360259154665908, "url": "http://p1.meituan.net/hotelbiz/6125bbbb8068e34ca66444ae0a11a329475602.jpg", "rank": 1},
    {"imageId": 1360253579469350, "url": "http://p0.inf.test.sankuai.com/testhubble/b44e5f8e32047452045e051bfd08553537344.webp", "rank": 2},
    {"imageId": 1360253026902519, "imageSize": "4500x3000", "url": "http://p0.inf.test.sankuai.com/testhubble/16f2742cecedadffa05a62242424ff61547081.jpg", "rank": 3},
    {"imageId": 1360253024940375, "imageSize": "4500x3000", "url": "http://p0.inf.test.sankuai.com/testhubble/92220727a92b3c08502db0d92ce631d23516508.jpg", "rank": 4},
    {"imageId": 1360253021540918, "imageSize": "4500x3000", "url": "http://p0.inf.test.sankuai.com/testhubble/f036040082546b522b60e50516f1dad23284125.jpg", "rank": 5},
]
DEFAULT_IMAGE_TEXT_MODULES = [
    {"type": 0, "imageModels": [{"imageId": 1360253018472876, "imageSize": "4500x3000", "url": "http://p0.inf.test.sankuai.com/testhubble/34d3522ec127fe4fb9d38651cc037be0108735.jpg", "rank": 1}]},
    {"type": 1, "imageModels": [{"imageId": 1360253579469350, "url": "http://p0.inf.test.sankuai.com/testhubble/b44e5f8e32047452045e051bfd08553537344.webp", "rank": 1}]},
]
DEFAULT_SALE_STRATEGIES = [
    {"saleChannel": 1, "saleTerminal": terminal, "saleStrategy": [1, 2, 3], "blackWhiteStatus": 1}
    for terminal in (1, 2, 3)
] + [
    {"saleChannel": 2, "saleTerminal": terminal, "saleStrategy": [0, 1], "blackWhiteStatus": 1}
    for terminal in (1, 2)
]


def _load_module(module_name: str, relative_path: str):
    spec = ilu.spec_from_file_location(module_name, os.path.join(ROOT, relative_path))
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_interface():
    spec = ilu.spec_from_file_location(
        "super_deal_interface",
        os.path.join(ROOT, "interface/super-deal/interface.py"),
    )
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_interface()
_infra_iface = _load_module("infra_interface", "interface/infra/interface.py")
_query_contract = _load_module("query_contract", "factory/infra/query-contract.py")

# 上线后刷新 SPU 缓存（best-effort，失败不中断主流程）
from scripts.refresh_spu_cache import refresh_spu_cache  # noqa: E402


def _show_schema() -> None:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        print(file.read())


def _default_spu_template() -> dict:
    """返回不绑定供应商、门店、住宿商品和非房的默认超团模板。

    模板遵循标准 SpuModel 嵌套结构（MeResourceFacade#submitSpu 接口）：
      顶层 7 字段：spuBaseModel / spuImageInfoModel / spuAuditModel /
                   relatedGoodsList / relateXgoodsInfoModels / dayTripModel / superDealModel
      超团业务字段全部在 superDealModel 内：
        superDealBaseModel.{spuExchangeType, linePrice, spuSaleStrategyList, ...}
        superDealCouponModel.superDealGiftCardModel.mtPrice
        spuActivityStockModel
        spuBaseAddPriceModelList
    """
    return {
        # ── 1. spuBaseModel: SPU 通用基础信息 ────────────────────────
        "spuBaseModel": {
            "spuType": 1,                      # 1=超级团购
            "spuSecondType": 0,
            "status": 0,                       # 0=下架
            "title": "",                       # build_spu_model 填充
            "partnerId": None,                 # build_spu_model 填充
            "poiId": None,                     # build_spu_model 填充 (String)
            "autoPublish": True,               # 非通兑=自动发布
            "relatedPoiNum": 1,               # build_spu_model 填充
            "relatedGoodsNum": 0,              # build_spu_model 填充
            "giftsName": "",
            "serviceTel": "",
            "customerName": "",
            "nameCustomerType": 0,
            "spuRelatedGoodsType": 1,
        },
        # ── 2. spuImageInfoModel: 图片信息 ────────────────────────────
        "spuImageInfoModel": {
            "spuBannerImages": copy.deepcopy(DEFAULT_BANNER_IMAGES),
            "imageTextModules": copy.deepcopy(DEFAULT_IMAGE_TEXT_MODULES),
            "imageTextType": 2,
        },
        # ── 3. spuAuditModel: 审核信息 ────────────────────────────────
        "spuAuditModel": None,
        # ── 4. relatedGoodsList: 关联产品（build_spu_model 填充）────────
        "relatedGoodsList": [],
        # ── 5. relateXgoodsInfoModels: 关联非房 ──────────────────────
        "relateXgoodsInfoModels": [],
        # ── 6. dayTripModel: 套餐信息（超团不用）─────────────────────
        "dayTripModel": None,
        # ── 7. superDealModel: 超团专属业务字段 ────────────────────────
        "superDealModel": {
            # 7.1 superDealBaseModel: 超团基础信息
            "superDealBaseModel": {
                "preCheckDays": 0,
                "linePrice": None,              # build_spu_model 填充
                "spuExchangeType": 1,          # 1=非通兑
                "spuServiceType": None,
                "marketingLabels": [],
                "recommendations": [],
                "spuSaleStrategyList": copy.deepcopy(DEFAULT_SALE_STRATEGIES),
            },
            # 7.2 superDealRelatedModel: 超团关联信息
            "superDealRelatedModel": {
                "spuRelatedGoodsType": 1,
            },
            # 7.3 distinctionAddPrice: 是否分门店加价
            "distinctionAddPrice": False,
            # 7.4 spuDistinctAddPriceModelList: 分门店加价
            "spuDistinctAddPriceModelList": None,
            # 7.5 spuBaseAddPriceModelList: 统一加价 (build_spu_model 填充)
            "spuBaseAddPriceModelList": None,
            # 7.6 superDealCouponModel: 营销/券信息
            "superDealCouponModel": {
                "mBoxId": None,
                "couponAuditStatus": None,
                "auditMsg": None,
                "couponTitle": None,           # build_spu_model 填充
                "subTitle": None,             # build_spu_model 填充
                "startDate": None,            # build_spu_model 填充
                "endDate": None,              # build_spu_model 填充
                "marketVisible": False,
                "topAppType": [0, 1, 3, 4, 100],
                "personBindLimit": None,       # build_spu_model 填充
                "needGuestFlag": 0,
                "needGuestInfo": [],
                "payLimitTime": 30,
                "couponInventoryModel": {
                    "startDateTime": None,    # build_spu_model 填充
                    "spuSellTimeType": 1,
                    "inventoryAmount": None,  # build_spu_model 填充
                    "endDateTime": None,      # build_spu_model 填充
                },
                "superDealGiftCardModel": {
                    "giftCardId": None,
                    "mtPrice": None,          # build_spu_model 填充
                    "roomNights": None,       # build_spu_model 填充
                    "splitRoomNight": None,   # build_spu_model 填充
                    "checkInScenes": None,
                    "superDealGiftUseModel": {
                        "startTime": None,     # build_spu_model 填充
                        "endTime": None,       # build_spu_model 填充
                        "periodDays": None,    # build_spu_model 填充
                        "periodType": 1,
                        "availableCheckInWeekList": None,
                        "availableCheckInDateList": None,  # build_spu_model 填充
                        "autoExpiredRefund": True,
                        "purchaseNoteGenerateType": 1,
                        "briefDesc": "部分日期不可订，请以实际兑换日期为准",
                    },
                },
                "superDealSieveModel": {"sieveModelList": None, "topPoiList": None},
            },
            # 7.7 spuModuleAuditMap: 模块审核状态
            "spuModuleAuditMap": None,
            # 7.8 spuActivityStockModel: 团购库存 (build_spu_model 填充)
            "spuActivityStockModel": {"totalCount": None},
            # 7.9 spuTagModelList: 团购标签
            "spuTagModelList": None,
        },
    }


def _load_payload(payload_file: str, payload_json: str) -> dict:
    if payload_file:
        with open(payload_file, encoding="utf-8") as file:
            payload = json.load(file)
    elif payload_json:
        payload = json.loads(payload_json)
    else:
        payload = _default_spu_template()
    if not isinstance(payload, dict):
        raise ValueError("SpuModel 模板必须为 JSON 对象")
    return payload


def _parse_date(value: str, end_of_day: bool = False) -> int:
    date_value = datetime.strptime(value, "%Y-%m-%d").date()
    clock = datetime_time(23, 59, 59) if end_of_day else datetime_time.min
    return int(datetime.combine(date_value, clock, tzinfo=CHINA_TZ).timestamp() * 1000)


def _collect_identity_values(value, key_names: set[str]) -> set[str]:
    """收集快照中所有业务身份字段，用于防止跨供应商/门店误复用快照。"""
    values = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in key_names and item not in (None, ""):
                values.add(str(item))
            else:
                values.update(_collect_identity_values(item, key_names))
    elif isinstance(value, list):
        for item in value:
            values.update(_collect_identity_values(item, key_names))
    return values


def _validate_snapshot_identity(template: dict, partner_id: str, poi_id: str) -> None:
    """首版只允许原实体快照复用；跨实体必须先接入商品/非房详情动态查询。"""
    partner_ids = _collect_identity_values(template, {"partnerId"})
    poi_ids = _collect_identity_values(template, {"poiId", "poiIdStr"})
    if partner_ids - {str(partner_id)}:
        raise ValueError(
            f"Payload 含其他 partnerId={sorted(partner_ids)}，当前首版禁止跨供应商改写快照"
        )
    if poi_ids - {str(poi_id)}:
        raise ValueError(
            f"Payload 含其他 poiId={sorted(poi_ids)}，当前首版禁止跨门店改写快照"
        )


def _query_contract_no(partner_id: str) -> str:
    """按 partnerId 查询生效合同编号，供 --calc-fullday-price 打印提示使用。

    专属全日房本身的合同编号由用户在执行 W1 create-fullday.py 时通过
    --set contractNo=... 自行传入/查询，本函数仅用于 --calc-fullday-price
    命令附带打印，方便直接复制粘贴。
    """
    resp = _infra_iface.query_contract_by_partner_id(partner_id=partner_id, dry_run=False)
    contract_no = _query_contract._extract_contract_no_from_du584(resp)
    if not contract_no or str(contract_no).lower() == "null":
        raise ValueError("无法从工具584响应中提取 contractNo，请手动查询后自行传给 create-fullday.py")
    return contract_no


def calculate_fullday_price(sale_price: int, room_nights: int, overseas: bool = False,
                             max_adult: int | None = None) -> dict:
    """根据超团公式计算专属全日房基础卖价，供 --calc-fullday-price 独立换算使用。

    公式：基础卖价 = 超团价格(mtPrice) ÷ 间夜(roomNights)

    加价日历(addPrice) 不写入全日房 weekPriceInfos，仅保留在 SPU 的
    spuBaseAddPriceModelList，由后端兑换时自行计算「基础价 + 加价」。
    原因：batchCreateGoods 在卖价/底价模式下均不支持多组不同价格的
    weekPriceInfos（会报「保存草稿失败」），因此全日房统一用单组全周
    基础卖价。

    境外商品使用多人同价模式（priceSameTag=1），各成人档位 basePrice 相同，
    priceInfo 传 null，priceFactorInfos 按人数分档。

    返回:
        {
            "base_price": int,           # 基础卖价，单位分
            "week_price_infos": list,    # 单组全周 weekPriceInfos
            "extra_overrides": dict,     # 境外时额外的 overrides（境内为空）
            "warnings": list[str],       # 警告信息
        }
    """
    base_price = sale_price // room_nights
    remainder = sale_price % room_nights
    warnings = []

    if remainder != 0:
        warnings.append(
            f"超团价格 {sale_price}分 ÷ 间夜 {room_nights} 不整除，"
            f"基础卖价向下取整为 {base_price}分（余 {remainder}分）"
        )

    extra_overrides = {}

    if overseas:
        # 境外：多人同价（priceSameTag=1），各档 basePrice 相同
        max_adult = max_adult or 2
        price_factor_infos = [
            {
                "salePrice": "",
                "basePrice": str(base_price),
                "subPrice": "",
                "baseAddRatio": "10000",
                "priceFactors": {
                    "guestFactor": {"adultCount": n, "childAges": None, "childCount": 0}
                },
            }
            for n in range(1, max_adult + 1)
        ]
        week_price_infos = [{
            "inWeek": [1, 2, 3, 4, 5, 6, 7],
            "priceInfo": None,
            "priceFactorInfos": price_factor_infos,
        }]
        extra_overrides = {
            "goodsDetailList.0.goodsBaseInfo.priceSameTag": 1,
            "goodsDetailList.0.goodsBaseInfo.maxAdultAdmissibility": max_adult,
            "goodsDetailList.0.priceInfo.priceRecordWay": 3,
            "goodsDetailList.0.priceInfo.ratioConfig.newRatio": "10000",
            "goodsDetailList.0.priceInfo.ratioConfig.ratioType": 2,
        }
    else:
        # 境内：单组全周基础卖价
        week_price_infos = [{
            "inWeek": [1, 2, 3, 4, 5, 6, 7],
            "priceInfo": {
                "salePrice": str(base_price),
                "basePrice": "",
                "subPrice": "",
                "subRatio": "1100",
            },
            "priceFactorInfos": None,
        }]

    return {
        "base_price": base_price,
        "week_price_infos": week_price_infos,
        "extra_overrides": extra_overrides,
        "warnings": warnings,
    }


def _print_calc_fullday_price(sale_price: int, room_nights: int, overseas: bool,
                               max_adult: int | None, contract_no: str | None) -> None:
    """`--calc-fullday-price` 命令实现：打印价格公式换算结果 + 可直接粘贴的 --set 片段。

    本脚本不再自动创建全日房，创建前需要人工/Agent 先按超团公式算出全日房
    基础卖价。该命令把换算过程和 create-fullday.py 的 --set 参数一次性打印
    出来，减少手工拼接嵌套 JSON 出错的概率，用法见文件头部【使用示例】。
    """
    price_info = calculate_fullday_price(sale_price, room_nights, overseas, max_adult)
    base_price = price_info["base_price"]
    max_adult = max_adult or 2

    print("📐 超团专属全日房价格换算")
    print(f"  超团价格(mtPrice) = {sale_price}分 ({sale_price / 100:.2f}元)")
    print(f"  间夜(roomNights)   = {room_nights}")
    print(f"  基础卖价 = {sale_price} ÷ {room_nights} = {base_price}分 ({base_price / 100:.2f}元)")
    if overseas:
        print(f"  境外多人同价：1~{max_adult}人 basePrice 均为 {base_price}分 ({base_price / 100:.2f}元)")
    else:
        print(f"  全日房统一卖价 = {base_price}分 ({base_price / 100:.2f}元)（全周单组）")
    for warning in price_info["warnings"]:
        print(f"  ⚠️ {warning}")

    week_price_json = json.dumps(price_info["week_price_infos"], ensure_ascii=False)
    print("\n可直接粘贴给 create-fullday.py 的 --set 参数：")
    print(f"  --set 'goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos={week_price_json}'")
    if contract_no:
        print(f"  --set goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}")
    for key, value in price_info["extra_overrides"].items():
        print(f"  --set {key}={value}")
    print(
        "\n⚠️ 全日房 goodsName 建议包含“超级团购”字样，例如：\n"
        "  --goods-name \"<房型名>-<早餐/取消描述>-超级团购<时间戳>\"\n"
        "创建完成并确认 [Step 6] 上线成功（batchOnlineSwitch status=2）后，"
        "再把拿到的 goodsId 传给本脚本的 --goods-id。"
    )


def _build_related_goods(model: dict, goods_id_list: list, args: argparse.Namespace) -> None:
    """用已创建好的全日房/直连商品 goodsId 组装 relatedGoodsList。

    专属全日房和直连商品统一走本函数：goodsId 必须由调用方提前创建好
    （专属全日房走 W1 factory/fullday/create-fullday.py，直连商品走
    zl-hotel-testdata skill），本脚本不再自动创建全日房。
    """
    related = []
    for gid in goods_id_list:
        related.append({
            "goodsId": gid,
            "goodsName": "",
            "goodsSource": 1,
            "goodsType": 1,
            "latestBookingDays": -1,
            "noPersist": 0,
            "realRoomName": "",
            "status": 2,
        })
    model["relatedGoodsList"] = related
    # 嵌套路径：spuBaseModel.relatedGoodsNum / relatedPoiNum
    base = model.setdefault("spuBaseModel", {})
    base["relatedGoodsNum"] = len(related)
    base["relatedPoiNum"] = 1
    if getattr(args, "direct_goods", False):
        # 直连商品 paymentType=0（非预付），超团活动库存只支持预付，因此不传 spuActivityStockModel
        super_deal = model.get("superDealModel") or {}
        super_deal.pop("spuActivityStockModel", None)
        print(f"  ℹ️ 直连商品模式：已移除 spuActivityStockModel（直连商品 paymentType=0，超团活动库存只支持预付）")
    print(f"  ✅ 使用已创建好的 goodsId 组装 relatedGoodsList: {goods_id_list}")


def _is_available_xgoods(item: dict) -> bool:
    """仅接受审核完成、在线、核心且尚未关联住宿商品的非房。"""
    basic = item.get("basicInfoModel") or {}
    relation = basic.get("relateVpoiGoods") or {}
    return (
        basic.get("auditStatus") == 3
        and basic.get("flowStatus") == 3
        and basic.get("onlineStatus") == 1
        and basic.get("parentXgoods") is True
        and basic.get("priType") == 22
        and basic.get("secType") == 158004
        and not (basic.get("relatedGoodsList") or [])
        and not (relation.get("goodsList") or [])
        and all(
            not (poi.get("relatedGoodsList") or [])
            for group in (relation.get("relationVpoiList") or [])
            for poi in (group.get("relatedPoiList") or [])
        )
    )


def _select_available_xgoods(items: list) -> dict:
    candidates = [item for item in items if _is_available_xgoods(item)]
    if not candidates:
        raise ValueError(
            "当前 partnerId + poiId 下没有审核通过、在线且未关联住宿商品的核心非房；"
            "请先按 W3 创建并审核非房后重试"
        )
    return max(
        candidates,
        key=lambda item: str((item.get("basicInfoModel") or {}).get("gmtModified") or ""),
    )


def _remove_json_refs(value):
    """移除查询响应序列化产生、离开原响应后失效的 $ref 节点。"""
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            return None
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _remove_json_refs(item)) is not None
        }
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _remove_json_refs(item)) is not None]
    return value


def _bind_xgoods_to_related_goods(xgoods: dict, model: dict) -> dict:
    """把目标住宿商品关系注入查询所得非房快照。"""
    related_goods = model.get("relatedGoodsList") or []
    if not related_goods:
        raise ValueError("自动关联非房前 relatedGoodsList 不能为空")

    snapshot = _remove_json_refs(copy.deepcopy(xgoods))
    basic = snapshot.get("basicInfoModel") or {}
    relation = basic.get("relateVpoiGoods") or {}
    goods_ids = [item.get("goodsId") for item in related_goods if item.get("goodsId")]
    relation["goodsList"] = goods_ids
    basic["relatedGoodsList"] = [{"goodsId": goods_id} for goods_id in goods_ids]

    relation_goods = [
        {
            "canUntie": False,
            "goodsId": item["goodsId"],
            "goodsName": item.get("goodsName") or "",
            "goodsStatus": 0,
            "hasGift": False,
            "noPersistent": item.get("noPersist", 0),
        }
        for item in related_goods
        if item.get("goodsId")
    ]
    # 嵌套路径：spuBaseModel.partnerId / poiId
    base = model.get("spuBaseModel") or {}
    poi_model = {
        "partnerId": int(base.get("partnerId") or 0),
        "poiId": str(base.get("poiId") or ""),
        "poiIdStr": str(base.get("poiId") or ""),
        "relatedGoodsList": relation_goods,
    }
    relation_vpoi_list = relation.get("relationVpoiList") or []
    if not relation_vpoi_list:
        raise ValueError("非房快照缺少 relateVpoiGoods.relationVpoiList")
    for relation_vpoi in relation_vpoi_list:
        relation_vpoi["partnerId"] = int(base.get("partnerId") or 0)
        relation_vpoi["relatedPoiList"] = [copy.deepcopy(poi_model)]
        relation_vpoi["vpoiModels"] = [copy.deepcopy(poi_model)]

    relation["xgoodsId"] = basic.get("xgoodsId")
    basic["relateVpoiGoods"] = relation
    # 嵌套路径：spuBaseModel.partnerId / poiId
    _base = model.get("spuBaseModel") or {}
    basic["partnerId"] = int(_base.get("partnerId") or 0)
    basic["poiId"] = str(_base.get("poiId") or "")
    basic["poiIdStr"] = str(_base.get("poiId") or "")
    snapshot["basicInfoModel"] = basic
    return snapshot


def _select_xgoods_by_id(items: list, xgoods_id: int) -> dict:
    """按 xgoodsId 精确匹配非房，不强制可用性校验（仅告警）。"""
    for item in items:
        basic = item.get("basicInfoModel") or {}
        if basic.get("xgoodsId") == xgoods_id:
            if not _is_available_xgoods(item):
                print(
                    f"  ⚠️ 非房 xgoodsId={xgoods_id} 未通过可用性校验"
                    f"（可能未审核/未在线/已关联其他住宿商品），仍按用户指定继续绑定"
                )
            return item
    raise ValueError(
        f"在 partnerId + poiId 下未查询到 xgoodsId={xgoods_id} 的非房产品；"
        f"请确认非房产品 ID 正确且属于该供应商/门店"
    )


def _refresh_xgoods_snapshot(model: dict, args: argparse.Namespace) -> None:
    # 非房创建审核后 querySpuXgoodsList 可能未立即索引，需重试
    max_retries = 6
    for attempt in range(1, max_retries + 1):
        items = _iface.query_spu_xgoods_list(
            partner_id=args.partner_id,
            poi_id=args.poi_id,
            swimlane=args.swimlane,
        )
        if args.xgoods_id:
            try:
                selected = _select_xgoods_by_id(items, args.xgoods_id)
                print(f"  按指定 xgoodsId 绑定非房: xgoodsId={args.xgoods_id}")
                break
            except ValueError:
                if attempt < max_retries:
                    print(f"  ⏳ 非房 xgoodsId={args.xgoods_id} 未被索引，等待 10s 后重试（{attempt}/{max_retries}）...")
                    time.sleep(10)
                    continue
                raise
        else:
            try:
                selected = _select_available_xgoods(items)
                xgoods_id = (selected.get("basicInfoModel") or {}).get("xgoodsId")
                print(f"  自动选择非房: xgoodsId={xgoods_id}")
                break
            except ValueError:
                if attempt < max_retries:
                    print(f"  ⏳ 暂无可用非房，等待 10s 后重试（{attempt}/{max_retries}）...")
                    time.sleep(10)
                    continue
                raise
    model["relateXgoodsInfoModels"] = [_bind_xgoods_to_related_goods(selected, model)]


def _create_and_audit_xgoods(args: argparse.Namespace) -> int:
    """调用 W3 脚本创建非房产品并审核通过，返回 xgoodsId 供超团绑定。

    复用 W3 流程（references/workflows/w3-create-non-room.md）：
      1. subprocess 调用 factory/non-room/create-non-room.py 创建非房（同步返回 xGoodsId）
      2. subprocess 调用 factory/audit/gift/audit.py 审核非房（configKey=xGoods）
      3. 返回 xgoodsId，后续由 _refresh_xgoods_snapshot 查询快照并绑定
    """
    import re
    import subprocess

    nonroom_script = os.path.join(ROOT, "factory/non-room/create-non-room.py")
    audit_script = os.path.join(ROOT, "factory/audit/gift/audit.py")

    print("\n  📦 调用 W3 创建非房产品并绑定到超团...")

    # Step 1：创建非房
    create_cmd = [
        sys.executable, nonroom_script,
        "--partner-id", str(args.partner_id),
        "--poi-id", str(args.poi_id),
        "--type", "catering",
    ]
    if args.swimlane:
        create_cmd.extend(["--swimlane", args.swimlane])
    print(f"  ⏳ 创建非房（W3 create-non-room.py）...")
    print(f"     命令: {' '.join(create_cmd)}")
    result = subprocess.run(create_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        raise ValueError(
            f"W3 创建非房失败（退出码 {result.returncode}）: {result.stderr.strip()}"
        )
    # 从输出解析 xGoodsId（格式：xGoodsId  : <id>）
    match = re.search(r"xGoodsId\s*:\s*(\d+)", result.stdout)
    if not match:
        raise ValueError(
            f"W3 创建非房输出中未找到 xGoodsId:\n{result.stdout}"
        )
    xgoods_id = int(match.group(1))
    print(f"  ✅ 非房创建成功: xgoodsId={xgoods_id}")

    # Step 2：审核非房
    audit_cmd = [
        sys.executable, audit_script,
        "--xgoods-id", str(xgoods_id),
        "--partner-id", str(args.partner_id),
        "--shop-id", str(args.poi_id),
    ]
    print(f"  ⏳ 审核非房（W3 audit/gift/audit.py）...")
    print(f"     命令: {' '.join(audit_cmd)}")
    audit_result = subprocess.run(audit_cmd, capture_output=True, text=True)
    print(audit_result.stdout)
    if audit_result.returncode != 0:
        raise ValueError(
            f"W3 审核非房失败（退出码 {audit_result.returncode}）: {audit_result.stderr.strip()}"
        )
    print(f"  ✅ 非房审核完成: xgoodsId={xgoods_id}")
    return xgoods_id


def _extract_spu_id(response: dict) -> str:
    for key in ("spuId", "id", "productId"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    data = response.get("data")
    if isinstance(data, (int, str)) and str(data) not in ("", "None", "null"):
        return str(data)
    if isinstance(data, dict):
        for key in ("spuId", "id", "productId"):
            if data.get(key) not in (None, ""):
                return str(data[key])
    return ""


def build_spu_model(template: dict, args: argparse.Namespace) -> dict:
    """以真实抓包模板为基础，仅覆盖本次构造的动态字段。

    SpuModel 嵌套结构路径映射：
      spuBaseModel.{title, partnerId, poiId, relatedGoodsNum, relatedPoiNum}
      superDealModel.superDealBaseModel.{linePrice, spuExchangeType}
      superDealModel.superDealCouponModel.{couponTitle, personBindLimit, superDealGiftCardModel.mtPrice, ...}
      superDealModel.spuActivityStockModel.totalCount
      superDealModel.spuBaseAddPriceModelList
    """
    _validate_snapshot_identity(template, args.partner_id, args.poi_id)
    model = copy.deepcopy(template)

    # ── spuBaseModel: 通用基础信息 ──────────────────────────────
    base = model.setdefault("spuBaseModel", {})
    # 注意：新建时不传 spuId（让后端自动生成），否则可能被误判为更新
    base.pop("spuId", None)
    base["title"] = args.product_name or f"{args.partner_id}非通兑超团_{int(time.time())}"
    base["partnerId"] = int(args.partner_id)
    base["poiId"] = str(args.poi_id)
    base["relatedGoodsNum"] = len(model.get("relatedGoodsList") or [])
    base["relatedPoiNum"] = 1
    base["spuType"] = 1
    base["autoPublish"] = True

    # ── superDealModel: 超团专属业务字段 ────────────────────────
    super_deal = model.setdefault("superDealModel", {})

    # superDealBaseModel
    sd_base = super_deal.setdefault("superDealBaseModel", {})
    sd_base["linePrice"] = args.line_price
    sd_base["spuExchangeType"] = 1

    # spuActivityStockModel
    super_deal["spuActivityStockModel"] = {"totalCount": args.total_count}

    # superDealCouponModel
    coupon = super_deal.setdefault("superDealCouponModel", {})
    title = base["title"]
    coupon["subTitle"] = title[:20]
    coupon["couponTitle"] = title[:20]
    coupon["personBindLimit"] = args.person_bind_limit

    # 券售卖时间 = 当前时间 ~ sell_end
    now_ms = int(datetime.now(CHINA_TZ).timestamp() * 1000)
    sell_end = args.sell_end or (datetime.now(CHINA_TZ) + timedelta(days=30)).strftime("%Y-%m-%d")
    sell_end_ms = _parse_date(sell_end, end_of_day=True)
    coupon["startDate"] = now_ms
    coupon["endDate"] = sell_end_ms

    inventory = coupon.setdefault("couponInventoryModel", {})
    inventory["inventoryAmount"] = args.inventory
    inventory["startDateTime"] = now_ms
    inventory["endDateTime"] = sell_end_ms

    gift_card = coupon.setdefault("superDealGiftCardModel", {})
    gift_card["mtPrice"] = args.sale_price
    gift_card["roomNights"] = args.room_nights
    gift_card["splitRoomNight"] = args.split_room_night

    gift_use = gift_card.setdefault("superDealGiftUseModel", {})
    checkin_start = args.checkin_start or (
        datetime.now(CHINA_TZ) + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    checkin_end = args.checkin_end or (
        datetime.now(CHINA_TZ) + timedelta(days=31)
    ).strftime("%Y-%m-%d")
    checkin_start_ms = _parse_date(checkin_start)
    checkin_end_ms = _parse_date(checkin_end, end_of_day=True)
    gift_use["startTime"] = checkin_start_ms
    gift_use["endTime"] = checkin_end_ms
    gift_use["periodDays"] = args.period_days
    gift_use["availableCheckInDateList"] = [{
        "startDate": checkin_start_ms,
        "endDate": checkin_end_ms,
    }]

    # 超团加价金额（superDealModel.spuBaseAddPriceModelList）
    # 校验加价日期必须在入住日期范围内
    if args.base_add_price:
        checkin_start_str = datetime.fromtimestamp(
            checkin_start_ms / 1000, tz=CHINA_TZ
        ).strftime("%Y%m%d")
        checkin_end_str = datetime.fromtimestamp(
            checkin_end_ms / 1000, tz=CHINA_TZ
        ).strftime("%Y%m%d")
        for idx, entry in enumerate(args.base_add_price):
            ap_start = str(entry["startDate"])
            ap_end = str(entry["endDate"])
            if ap_start < checkin_start_str or ap_end > checkin_end_str:
                raise ValueError(
                    f"--base-add-price[{idx}] 日期范围 {ap_start}~{ap_end} "
                    f"超出入住日期范围 {checkin_start_str}~{checkin_end_str}；"
                    f"请用 --checkin-start/--checkin-end 调整入住范围，"
                    f"或修改加价日期"
                )
    super_deal["spuBaseAddPriceModelList"] = args.base_add_price or None

    # 确保 spuImageInfoModel 存在
    model.setdefault("spuImageInfoModel", copy.deepcopy(_default_spu_template()["spuImageInfoModel"]))

    return model


# ════════════════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════════════════


def main() -> None:
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    parser = argparse.ArgumentParser(description="创建非通兑超团（MeResourceFacade#submitSpu RPC）")
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--payload-file", help="ME 成功抓包的完整 SpuModel JSON 文件")
    source.add_argument("--payload-json", help="ME 成功抓包的完整 SpuModel JSON 字符串")
    parser.add_argument(
        "--calc-fullday-price", action="store_true",
        help=(
            "仅打印专属全日房价格换算结果和 create-fullday.py 的 --set 片段，不创建超团；"
            "配合 --sale-price/--room-nights/--overseas/--max-adult 使用"
        ),
    )
    parser.add_argument("--partner-id", required=True, help="供应商ID")
    parser.add_argument("--poi-id", required=True, help="单门店ID")
    parser.add_argument(
        "--goods-id", type=int, default=None,
        help=(
            "已创建好的关联商品 goodsId（必填，--calc-fullday-price 模式除外）。"
            "非直连场景：先按 W1 流程（factory/fullday/create-fullday.py）创建专属全日房，"
            "全日房卖价须满足「超团价格÷间夜」公式，可先用 --calc-fullday-price 换算；"
            "直连场景：先用 zl-hotel-testdata skill 创建直连商品（isSuperDeal=true），"
            "并额外加 --direct-goods"
        ),
    )
    parser.add_argument(
        "--direct-goods", action="store_true",
        help="--goods-id 为直连商品（而非专属全日房）时需加此参数，脚本会移除 spuActivityStockModel",
    )
    parser.add_argument("--product-name", default="", help="超团标题，不传则自动生成")
    parser.add_argument("--sale-price", type=int, default=20000, help="售价 mtPrice，单位分")
    parser.add_argument("--line-price", type=int, default=30000, help="划线价 linePrice，单位分")
    parser.add_argument("--inventory", type=int, default=1000, help="券库存")
    parser.add_argument("--person-bind-limit", type=int, default=5, help="每人绑定上限")
    parser.add_argument("--room-nights", type=int, default=1, help="间夜数")
    parser.add_argument("--split-room-night", type=int, default=None, help="拆分间夜数，默认等于 room-nights")
    parser.add_argument("--period-days", type=int, default=30, help="券有效天数，默认30天")
    parser.add_argument("--total-count", type=int, default=300, help="活动库存总量，默认300（后端约束: >0且<=300）")
    parser.add_argument(
        "--base-add-price",
        default=None,
        help=(
            "超团加价金额 JSON 数组（嵌套结构），例如："
            "--base-add-price '[{\"startDate\":\"20260714\",\"endDate\":\"20260802\","
            "\"weekPrices\":[{\"inWeek\":[6,7],\"addPrice\":1000}]}]'；"
            "不传时 spuBaseAddPriceModelList 为 null"
        ),
    )
    parser.add_argument("--sell-end", help="售卖截止日期，格式 YYYY-MM-DD")
    parser.add_argument("--checkin-start", help="可入住开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--checkin-end", help="可入住结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--overseas", action="store_true", help="境外超团（专属全日房使用多人同价模式）")
    parser.add_argument("--max-adult", type=int, default=None, help="境外最大可住成人人数（1~6，默认2）；仅 --overseas 时生效")
    parser.add_argument("--with-xgoods", action="store_true", help="（已废弃）默认行为已改为自动新建+审核+绑定非房，保留此参数仅为向后兼容")
    parser.add_argument("--skip-xgoods", action="store_true", help="跳过默认的非房产品新建与绑定")
    parser.add_argument("--xgoods-id", type=int, default=None, help="指定要绑定的已有非房产品 xgoodsId；指定时跳过新建，直接查询并绑定该非房")
    parser.add_argument("--swimlane", default="", help="泳道名，空表示主干")
    parser.add_argument("--dry-run", action="store_true", help="打印 RPC 参数但不执行")
    parser.add_argument(
        "--skip-refresh-spu-cache", action="store_true",
        help="跳过上线后的 SPU 缓存刷新（SPU 套餐产品缓存 + POI-SPU 映射缓存）；默认上线后自动刷新",
    )
    parser.add_argument(
        "--cache-env", choices=["test", "prod"], default="test",
        help="goodsoperator-cli 缓存刷新环境（默认 test，与本 skill 创建商品所用环境一致）",
    )
    args = parser.parse_args()

    if args.calc_fullday_price:
        contract_no = None
        try:
            contract_no = _query_contract_no(args.partner_id)
        except ValueError as error:
            print(f"  ⚠️ {error}", file=sys.stderr)
        _print_calc_fullday_price(
            sale_price=args.sale_price,
            room_nights=args.room_nights,
            overseas=args.overseas,
            max_adult=args.max_adult,
            contract_no=contract_no,
        )
        return

    if not args.goods_id:
        parser.error(
            "--goods-id 为必填参数：请先按 W1 流程创建专属全日房（或直连商品），"
            "拿到 goodsId 后再传入；可先用 --calc-fullday-price 打印价格换算辅助信息"
        )
    if bool(args.checkin_start) != bool(args.checkin_end):
        parser.error("--checkin-start 与 --checkin-end 必须同时提供")
    if args.checkin_start and args.checkin_end and args.checkin_start > args.checkin_end:
        parser.error("--checkin-start 不能晚于 --checkin-end")
    if args.line_price < args.sale_price:
        parser.error("--line-price 不能小于 --sale-price")
    if args.inventory <= 0 or args.person_bind_limit <= 0 or args.room_nights <= 0:
        parser.error("库存、每人绑定上限和间夜数必须大于 0")

    # 解析加价金额 JSON（嵌套结构：[{startDate, endDate, weekPrices: [{inWeek, addPrice}]}]）
    if args.base_add_price:
        try:
            parsed = json.loads(args.base_add_price)
        except json.JSONDecodeError as exc:
            parser.error(f"--base-add-price 不是合法 JSON: {exc}")
        if not isinstance(parsed, list):
            parser.error("--base-add-price 必须是 JSON 数组")
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                parser.error(f"--base-add-price[{idx}] 必须是 JSON 对象")
            for key in ("startDate", "endDate", "weekPrices"):
                if key not in item:
                    parser.error(f"--base-add-price[{idx}] 缺少必填字段 {key}")
            try:
                datetime.strptime(str(item["startDate"]), "%Y%m%d")
                datetime.strptime(str(item["endDate"]), "%Y%m%d")
            except ValueError:
                parser.error(
                    f"--base-add-price[{idx}] 日期格式错误，要求 YYYYMMDD"
                )
            if not isinstance(item["weekPrices"], list) or not item["weekPrices"]:
                parser.error(f"--base-add-price[{idx}].weekPrices 必须是非空数组")
            for wp_idx, wp in enumerate(item["weekPrices"]):
                if not isinstance(wp, dict) or "addPrice" not in wp:
                    parser.error(
                        f"--base-add-price[{idx}].weekPrices[{wp_idx}] 缺少 addPrice"
                    )
        args.base_add_price = parsed

    # 派生默认值：未显式传参时由其他参数推导
    if args.split_room_night is None:
        args.split_room_night = args.room_nights
    if args.total_count is None:
        args.total_count = 300
    if args.total_count <= 0 or args.total_count > 300:
        parser.error(f"--total-count 必须 >0 且 <=300（后端约束），当前值: {args.total_count}")
    if args.period_days <= 0:
        parser.error("--period-days 必须大于 0")

    try:
        template = _load_payload(args.payload_file, args.payload_json)
        spu_model = build_spu_model(template, args)
        _build_related_goods(spu_model, [args.goods_id], args)
        if not args.dry_run and args.xgoods_id:
            # 用户指定已有非房 xgoodsId，直接查询并绑定
            _refresh_xgoods_snapshot(spu_model, args)
        elif not args.dry_run and not args.skip_xgoods:
            # 默认：新建非房 + 审核 + 绑定
            args.xgoods_id = _create_and_audit_xgoods(args)
            _refresh_xgoods_snapshot(spu_model, args)
        elif not args.dry_run:
            spu_model["relateXgoodsInfoModels"] = []
            print("  --skip-xgoods 已跳过非房创建与绑定")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    print("\n=== 创建非通兑超团（MeResourceFacade#submitSpu）===")
    print(f"  partnerId : {args.partner_id}")
    print(f"  poiId     : {args.poi_id}")
    print(f"  title     : {spu_model.get('spuBaseModel',{}).get('title','')}")
    print(f"  salePrice : {args.sale_price}分")
    print(f"  linePrice : {args.line_price}分")
    print(f"  addPrice  : {args.base_add_price or '无'}")
    print(f"  swimlane  : {args.swimlane or '主干'}")

    if args.dry_run:
        print("\n  [dry-run] 以下为将提交的 SpuModel：")
        print(json.dumps(spu_model, ensure_ascii=False, indent=2))
        return

    # ⏳ 等待专属全日房型信息在后端传播完成
    # 专属全日房上线后，后端房型信息（TDC→商品中心）异步传播，立即调用 submitSpu
    # 会报 200013028「查询套餐关联房型信息失败」。实测等待 60s 可稳定通过。
    print("\n⏳ 等待 60s，确保专属全日房型信息在后端传播完成...")
    time.sleep(60)
    response = _iface.call_raw(
        partner_id=args.partner_id,
        spu_model=spu_model,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        return

    spu_id = _extract_spu_id(response)

    print("\n" + "=" * 56)
    print("  非通兑超团创建完成")
    print(f"  spuId     : {spu_id or '响应未直接返回，需通过商品查询接口回查'}")
    print(f"  partnerId : {args.partner_id}")
    print(f"  poiId     : {args.poi_id}")
    print(f"  原始响应  : {json.dumps(response, ensure_ascii=False)}")
    print("=" * 56)
    if spu_id:
        print(
            f"\n  📋 验证入库/在线状态："
            f"python3 factory/super-deal/query-spu.py --partner-id {args.partner_id} --spu-id {spu_id} --wait"
        )
        print("     （不要用 querySpuListPage，该接口对超团查询不可靠恒返回空列表）")

    # ── submitSpu 创建完成，后续审核/上线走原流程（HTTP 网关 + auditProduct）──
    # autoPublish=true 在 spuBaseModel 内，submitSpu 会创建 SPU + 红包 + 图文。
    # 后续审核/上线不在本脚本处理，回到原有流程（通兑超团 factory/audit/super-deal-unified/audit.py）。
    if spu_id:
        # ── 刷新 SPU 缓存（SPU 套餐产品缓存 + POI-SPU 映射缓存）──
        # best-effort，失败不中断主流程。
        if args.skip_refresh_spu_cache:
            print("\n  --skip-refresh-spu-cache 已跳过 SPU 缓存刷新")
        else:
            print("\n  ⏳ 开始刷新 SPU 缓存（goodsoperator-cli）...")
            refresh_spu_cache(
                spu_id=spu_id,
                poi_ids=[args.poi_id],
                env=args.cache_env,
            )


if __name__ == "__main__":
    main()

