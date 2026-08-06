#!/usr/bin/env python3
"""通过 MeResourceFacade#submitSpu RPC 创建通兑超团。

直接调用研发 Thrift RPC（与套餐/非通兑超团共用同一已注册 OCTO 接口）：
  appkey  : com.sankuai.hotel.biz.platform
  service : com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method  : submitSpu(Long userId, SpuModel spuModel)

核心流程：
  1. 为每个门店（至少2个）先按 W1 流程（factory/fullday/create-fullday.py）
     单独创建好一条专属全日房（本脚本不再自动创建）
  2. 通过 --goods-ids 传入各门店对应的 goodsId（数量需与 --shop-ids 一致）
  3. 使用传入的 goodsId 组装 relatedGoodsList
  4. 构建 SpuModel 并通过 RPC 提交
  5. 响应同步返回 spuId

与非通兑超团的关键差异：
  - spuExchangeType=0（非通兑为 1）
  - poiId=null（非通兑为真实单门店）
  - relatedGoodsList 包含至少2个不同门店的商品
  - autoPublish=false（需调用 auditProduct 审核，不需要 BPM；非通兑为 true 自动上线）
  - 响应同步返回 spuId
  - 价格单位为分（mtPrice + linePrice）

====================================================================
【前置说明：专属全日房需先单独创建，与套餐（W4）编排方式一致】

  本脚本不再自动为每个门店创建专属全日房，需先对每个门店单独执行
  W1 流程（factory/fullday/create-fullday.py），全部完成后把 goodsId
  按 --shop-ids 的顺序拼成 --goods-ids 传入本脚本。

  每个门店的全日房售价都必须满足超团公式：
    全日房基础卖价 = 超团价格(mtPrice) ÷ 间夜(roomNights)

  可先用 --calc-fullday-price 打印出这个价格以及可直接粘贴给
  create-fullday.py 的 --set 参数，减少手工换算 JSON 出错的概率。
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

DEFAULT_SALE_STRATEGIES = [
    {"saleChannel": 1, "saleTerminal": terminal, "saleStrategy": [1, 2, 3], "blackWhiteStatus": 1}
    for terminal in (1, 2, 3)
] + [
    {"saleChannel": 2, "saleTerminal": terminal, "saleStrategy": [0, 1], "blackWhiteStatus": 1}
    for terminal in (1, 2)
]

# 图文详情默认素材（境外通兑超团 submitSpu 时携带，绕过 approvedSpuAndAddGraphicDetails 默认模板不匹配 sellChannel=11 的问题）
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

DEFAULT_PURCHASE_NOTE = (
    "重点说明：超级团购能否成功兑换酒店房间，取决于兑换日期的剩余可兑换房间数量，"
    "显示\u201c今日已兑完\u201d的日期将无法继续用券兑换\n"
    "预约方式：选择对应酒店→选择产品预约下单→到店入住，实际可用以酒店产品展示为准"
)


def _load_module(module_name: str, relative_path: str):
    spec = ilu.spec_from_file_location(module_name, os.path.join(ROOT, relative_path))
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_module("super_deal_unified_interface", "interface/super-deal-unified/interface.py")
_infra_iface = _load_module("infra_interface", "interface/infra/interface.py")
_query_contract = _load_module("query_contract", "factory/infra/query-contract.py")

# 上线后刷新 SPU 缓存（best-effort，失败不中断主流程）
from scripts.refresh_spu_cache import refresh_spu_cache  # noqa: E402


def _show_schema() -> None:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        print(file.read())


# ════════════════════════════════════════════════════════════════════════════
# SpuModel 默认模板
# ════════════════════════════════════════════════════════════════════════════

def _default_spu_template() -> dict:
    """返回通兑超团默认 SpuModel 模板（标准嵌套结构）。

    模板遵循标准 SpuModel 嵌套结构（MeResourceFacade#submitSpu 接口）：
      顶层 7 字段：spuBaseModel / spuImageInfoModel / spuAuditModel /
                   relatedGoodsList / relateXgoodsInfoModels / dayTripModel / superDealModel
      超团业务字段全部在 superDealModel 内
    """
    return {
        # ── 1. spuBaseModel: SPU 通用基础信息 ────────────────────────
        "spuBaseModel": {
            "spuType": 1,                      # 1=超级团购
            "spuSecondType": 0,
            "status": 0,                       # 0=下架
            "title": None,                     # build_spu_model 填充
            "shortTitle": None,
            "partnerId": None,                 # build_spu_model 填充
            "poiId": None,                     # 通兑=null（不绑定单门店）
            "autoPublish": False,              # 通兑=需审核后上线
            "relatedPoiNum": 0,               # build_spu_model 填充
            "relatedGoodsNum": 0,              # build_spu_model 填充
            "giftsName": "",
            "serviceTel": "",
            "customerName": "",
            "nameCustomerType": 0,
            "spuRelatedGoodsType": 1,
        },
        # ── 2. spuImageInfoModel: 图片信息（境外通兑时 build_spu_model 填充）──
        "spuImageInfoModel": None,
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
                "spuExchangeType": 0,          # 0=通兑
                "spuServiceType": 2,
                "marketingLabels": [],
                "recommendations": [],
                "spuSaleStrategyList": copy.deepcopy(DEFAULT_SALE_STRATEGIES),
            },
            # 7.2 superDealRelatedModel: 超团关联信息
            "superDealRelatedModel": {
                "spuRelatedGoodsType": 1,
                "relatedGoodsByFile": False,
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
                        "availableCheckInDateList": [],  # build_spu_model 填充
                        "autoExpiredRefund": True,
                        "purchaseNote": DEFAULT_PURCHASE_NOTE,
                        "briefDesc": "部分日期不可订，请以实际可兑换日期为准",
                    },
                },
                "superDealSieveModel": {
                    "sieveModelList": None,
                    "topPoiList": [],          # build_spu_model 填充
                },
                "purchaseRestrictionRule": {
                    "period": None,
                    "periodUnit": None,
                    "quantity": None,
                },
            },
            # 7.7 spuModuleAuditMap: 模块审核状态
            "spuModuleAuditMap": None,
            # 7.8 spuActivityStockModel: 团购库存
            "spuActivityStockModel": None,
            # 7.9 spuTagModelList: 团购标签
            "spuTagModelList": None,
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# 日期工具
# ════════════════════════════════════════════════════════════════════════════

def _parse_date(value: str, end_of_day: bool = False) -> int:
    date_value = datetime.strptime(value, "%Y-%m-%d").date()
    clock = datetime_time(23, 59, 59) if end_of_day else datetime_time.min
    return int(datetime.combine(date_value, clock, tzinfo=CHINA_TZ).timestamp() * 1000)


# ════════════════════════════════════════════════════════════════════════════
# 价格公式计算（--calc-fullday-price 辅助命令用，本脚本不再自动创建全日房）
# ════════════════════════════════════════════════════════════════════════════

def _query_contract_no(partner_id: str) -> str:
    """按 partnerId 查询生效合同编号，供 --calc-fullday-price 打印提示使用。

    专属全日房本身的合同编号由用户在执行 W1 create-fullday.py 时通过
    --set contractNo=... 自行传入/查询（供应商维度，所有门店共用同一个）。
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

    ⚠️ 通兑超团的所有门店专属全日房都共用同一个超团价格(mtPrice)和间夜数，
    因此每个门店的基础卖价换算结果完全相同，只需算一次即可套用到所有门店。
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

    通兑超团每个门店都要单独跑一次 create-fullday.py，但因为共用同一个
    mtPrice/roomNights，换算结果对所有门店都一样，只需打印一次即可。
    """
    price_info = calculate_fullday_price(sale_price, room_nights, overseas, max_adult)
    base_price = price_info["base_price"]
    max_adult = max_adult or 2

    print("📐 通兑超团专属全日房价格换算（所有门店共用同一份换算结果）")
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
    print("\n可直接粘贴给 create-fullday.py 的 --set 参数（对每个门店都用同一份）：")
    print(f"  --set 'goodsDetailList.0.priceInfo.unifiedDatePriceInfos.weekPriceInfos={week_price_json}'")
    if contract_no:
        print(f"  --set goodsDetailList.0.goodsBaseInfo.contractNo={contract_no}")
    for key, value in price_info["extra_overrides"].items():
        print(f"  --set {key}={value}")
    print(
        "\n⚠️ 每个门店都要单独执行一次 create-fullday.py（--poi-id 不同），"
        "全日房 goodsName 建议包含“超级团购”字样。全部门店创建完成并确认\n"
        "[Step 6] 上线成功后，把 goodsId 按 --shop-ids 的顺序拼成 --goods-ids 传给本脚本。"
    )


def _build_related_goods_from_ids(shop_ids: list[str], goods_ids: list[str]) -> list[dict]:
    """用已创建好的各门店 goodsId 组装 relatedGoodsList（{poiIdStr, goodsId}）。"""
    return [
        {"poiIdStr": poi, "goodsId": int(gid)}
        for poi, gid in zip(shop_ids, goods_ids)
    ]


# ════════════════════════════════════════════════════════════════════════════
# SpuModel 构建
# ════════════════════════════════════════════════════════════════════════════

def build_spu_model(args: argparse.Namespace, related_goods: list[dict]) -> dict:
    """构建通兑超团 SpuModel（标准嵌套结构）。"""
    model = _default_spu_template()
    title = args.product_name or f"{args.partner_id}通兑超团_{int(time.time())}"

    # ── spuBaseModel: 通用基础信息 ──────────────────────────────
    base = model["spuBaseModel"]
    base["title"] = title
    base["partnerId"] = int(args.partner_id)
    base["poiId"] = None  # 通兑不绑定单门店
    base["relatedGoodsNum"] = 0  # 后端自行从 relatedGoodsList 计算
    base["relatedPoiNum"] = 0

    # ── superDealModel: 超团专属业务字段 ────────────────────────
    super_deal = model["superDealModel"]

    # superDealBaseModel
    sd_base = super_deal["superDealBaseModel"]
    sd_base["linePrice"] = args.line_price

    # superDealCouponModel
    coupon = super_deal["superDealCouponModel"]
    coupon["subTitle"] = title[:20]
    coupon["couponTitle"] = title[:20]
    coupon["personBindLimit"] = args.person_bind_limit

    # 券售卖时间
    now_ms = int(datetime.now(CHINA_TZ).timestamp() * 1000)
    sell_end = args.sell_end or (
        datetime.now(CHINA_TZ) + timedelta(days=30)
    ).strftime("%Y-%m-%d")
    sell_end_ms = _parse_date(sell_end, end_of_day=True)
    coupon["startDate"] = now_ms
    coupon["endDate"] = sell_end_ms

    inventory = coupon["couponInventoryModel"]
    inventory["inventoryAmount"] = args.inventory
    inventory["startDateTime"] = now_ms
    inventory["endDateTime"] = sell_end_ms

    # 礼包卡
    gift_card = coupon["superDealGiftCardModel"]
    gift_card["mtPrice"] = args.sale_price
    gift_card["roomNights"] = args.room_nights
    gift_card["splitRoomNight"] = args.split_room_night

    # 入住时间
    gift_use = gift_card["superDealGiftUseModel"]
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

    # ── relatedGoodsList: 关联产品（顶层字段，submitSpu 必填）────────
    # 通兑超团 relatedGoodsList 至少需 2 个不同门店的商品，每项结构 {poiIdStr, goodsId}
    model["relatedGoodsList"] = list(related_goods)
    base["relatedGoodsNum"] = len(related_goods)
    base["relatedPoiNum"] = len({item.get("poiIdStr") for item in related_goods if item.get("poiIdStr")})

    # topPoiList
    coupon["superDealSieveModel"]["topPoiList"] = [
        item["poiIdStr"] for item in related_goods if item.get("poiIdStr")
    ]

    # 加价金额校验
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
                    f"超出入住日期范围 {checkin_start_str}~{checkin_end_str}"
                )
    super_deal["spuBaseAddPriceModelList"] = args.base_add_price or None

    # 境外通兑超团：submitSpu 时携带 spuImageInfoModel
    # 根因：auditProduct 的 approvedSpuAndAddGraphicDetails(spuId, spuType) 不接收渠道参数，
    # 默认图文模板匹配 sellChannel=3（境内），对 sellChannel=11（境外）静默丢弃 → 上线报"套餐缺少图文详情"
    # 解决方案：境外创建时直接携带图文，auditProduct 审批已有图文而非添加默认模板
    if getattr(args, "overseas", False):
        model["spuImageInfoModel"] = {
            "spuBannerImages": copy.deepcopy(DEFAULT_BANNER_IMAGES),
            "imageTextModules": copy.deepcopy(DEFAULT_IMAGE_TEXT_MODULES),
            "imageTextType": 2,
        }

    return model


# ════════════════════════════════════════════════════════════════════════════
# 创建后自动审核
# ════════════════════════════════════════════════════════════════════════════

def _run_auto_audit(spu_id: str, partner_id: str) -> None:
    """创建成功后自动串联审核流程（仅 auditProduct 图文信息审核，无需 BPM）。

    通过 subprocess 调用 factory/audit/super-deal-unified/audit.py --graphic-only，
    直接调 auditProduct RPC 即可完成图文+优惠券+选单侧审核全部通过
    （superDealCouponModel.couponAuditStatus / giftCardAuditStatus / sieveAuditStatus 均变为 4）。

    ✅ 已实测验证（2026-07-22，spuId=2257204683）：通兑超团审核不需要先走 BPM
       基础信息审核，单独调用 auditProduct 即可，随后上线成功。跳过 BPM 还能规避
       BPM 687 候选组委托权限问题（委托 API 只改 assignee，不改变发起 complete
       请求的登录身份，容易因默认委托目标不在候选组而报"你无权操作"）。
       残留现象：spuAuditModel.auditStatus 会停留在 8（不会变成 4），不影响上线。

    ⚠️ auditProduct 短间隔内重复调用同一 spuId 可能返回不稳定结果（一次成功一次
       报 "SPU基础信息审核失败"），若已确认成功不要重复调用，否则可能把状态打回
       卡死态（couponAuditStatus 卡在非4的中间态且无法自愈）。
    """
    import subprocess

    audit_script = os.path.join(_SCRIPT_DIR, "..", "audit", "super-deal-unified", "audit.py")
    cmd = [
        sys.executable, audit_script,
        "--spu-id", str(spu_id),
        "--partner-id", str(partner_id),
        "--graphic-only",
        "--auto-online",
    ]

    print("\n" + "=" * 56)
    print("  自动串联审核流程（auditProduct 图文信息审核，无需 BPM）")
    print(f"  spuId     : {spu_id}")
    print(f"  partnerId : {partner_id}")
    print(f"  命令      : {' '.join(cmd)}")
    print("=" * 56)

    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
    except Exception as e:
        print(f"\n  ⚠️ 自动审核调用异常: {e}", file=sys.stderr)
        print(f"  请手动执行: {' '.join(cmd)}", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(f"\n  ⚠️ 自动审核返回非零退出码({result.returncode})", file=sys.stderr)
        print(f"  请检查上方日志或手动执行: {' '.join(cmd)}", file=sys.stderr)
        return False
    else:
        print(f"\n  ✅ 自动审核流程完成", file=sys.stderr)
        return True


# ════════════════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    parser = argparse.ArgumentParser(
        description="创建通兑超团（MeResourceFacade#submitSpu RPC）"
    )
    parser.add_argument(
        "--calc-fullday-price", action="store_true",
        help=(
            "仅打印专属全日房价格换算结果和 create-fullday.py 的 --set 片段，不创建超团；"
            "配合 --sale-price/--room-nights/--overseas/--max-adult 使用，"
            "--partner-id 用于附带查询合同编号（可选）"
        ),
    )
    parser.add_argument("--partner-id", required=True, help="供应商ID")
    parser.add_argument(
        "--shop-ids", default=None,
        help="通兑门店ID列表，英文逗号分隔（至少2个）；必填，--calc-fullday-price 模式除外",
    )
    parser.add_argument(
        "--goods-ids", default=None,
        help=(
            "已创建好的各门店关联商品 goodsId，英文逗号分隔，顺序须与 --shop-ids 一致（必填，"
            "--calc-fullday-price 模式除外）。需先对每个门店单独执行 W1 流程"
            "（factory/fullday/create-fullday.py）创建专属全日房，全日房卖价须满足"
            "「超团价格÷间夜」公式，可先用 --calc-fullday-price 换算"
        ),
    )
    parser.add_argument("--product-name", default="", help="超团标题，不传则自动生成")
    parser.add_argument("--sale-price", type=int, default=20000, help="售价 mtPrice，单位分")
    parser.add_argument("--line-price", type=int, default=30000, help="划线价 linePrice，单位分")
    parser.add_argument("--inventory", type=int, default=1000, help="券库存")
    parser.add_argument("--person-bind-limit", type=int, default=5, help="每人绑定上限")
    parser.add_argument("--room-nights", type=int, default=1, help="间夜数")
    parser.add_argument(
        "--split-room-night", type=int, default=None,
        help="拆分间夜数，默认等于 room-nights",
    )
    parser.add_argument(
        "--period-days", type=int, default=None,
        help="券有效天数，默认 null（由 availableCheckInDateList 决定）",
    )
    parser.add_argument(
        "--base-add-price",
        default=None,
        help=(
            "超团加价金额 JSON 数组，例如："
            "--base-add-price '[{\"startDate\":\"20260714\",\"endDate\":\"20260802\","
            "\"weekPrices\":[{\"inWeek\":[6,7],\"addPrice\":1000}]}]'"
        ),
    )
    parser.add_argument("--sell-end", help="售卖截止日期，格式 YYYY-MM-DD")
    parser.add_argument("--checkin-start", help="可入住开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--checkin-end", help="可入住结束日期，格式 YYYY-MM-DD")
    parser.add_argument("--overseas", action="store_true", help="境外通兑超团（专属全日房使用多人同价模式）")
    parser.add_argument("--max-adult", type=int, default=None, help="境外最大可住成人人数（1~6，默认2）；仅 --overseas 时生效")
    parser.add_argument("--swimlane", default="", help="泳道名，空表示主干")
    parser.add_argument("--dry-run", action="store_true", help="打印 RPC 参数但不执行")
    parser.add_argument(
"--skip-audit", action="store_true",
help="跳过创建后的自动审核（auditProduct 图文信息审核）；默认创建后自动审核",
    )
    parser.add_argument(
        "--skip-refresh-spu-cache", action="store_true",
        help="跳过上线后的 SPU 缓存刷新（SPU 套餐产品缓存 + POI-SPU 映射缓存）；默认审核上线后自动刷新",
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

    # 解析门店列表
    args.shop_ids = [s.strip() for s in args.shop_ids.split(",") if s.strip()]
    if len(args.shop_ids) < 2:
        parser.error("通兑超团 --shop-ids 至少需要 2 个门店ID，格式：id1,id2")

    if not args.goods_ids:
        parser.error(
            "--goods-ids 为必填参数：请先对每个门店按 W1 流程创建专属全日房，"
            "拿到 goodsId 后按 --shop-ids 顺序拼接传入；可先用 --calc-fullday-price 打印价格换算辅助信息"
        )

    # 日期校验
    if bool(args.checkin_start) != bool(args.checkin_end):
        parser.error("--checkin-start 与 --checkin-end 必须同时提供")
    if args.checkin_start and args.checkin_end and args.checkin_start > args.checkin_end:
        parser.error("--checkin-start 不能晚于 --checkin-end")

    # 价格校验
    if args.line_price < args.sale_price:
        parser.error("--line-price 不能小于 --sale-price")
    if args.inventory <= 0 or args.person_bind_limit <= 0 or args.room_nights <= 0:
        parser.error("库存、每人绑定上限和间夜数必须大于 0")

    # 解析加价金额 JSON
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
                parser.error(f"--base-add-price[{idx}] 日期格式错误，要求 YYYYMMDD")
            if not isinstance(item["weekPrices"], list) or not item["weekPrices"]:
                parser.error(f"--base-add-price[{idx}].weekPrices 必须是非空数组")
            for wp_idx, wp in enumerate(item["weekPrices"]):
                if not isinstance(wp, dict) or "addPrice" not in wp:
                    parser.error(
                        f"--base-add-price[{idx}].weekPrices[{wp_idx}] 缺少 addPrice"
                    )
        args.base_add_price = parsed

    # 派生默认值
    if args.split_room_night is None:
        args.split_room_night = args.room_nights

    # 解析 --goods-ids（数量须与 --shop-ids 一致）
    goods_id_list = [s.strip() for s in args.goods_ids.split(",") if s.strip()]
    if len(goods_id_list) != len(args.shop_ids):
        parser.error(f"--goods-ids 数量({len(goods_id_list)})必须与 --shop-ids 数量({len(args.shop_ids)})一致")
    related_goods = _build_related_goods_from_ids(args.shop_ids, goods_id_list)
    print(f"  ✅ 使用已创建好的 goodsId 组装 relatedGoodsList: {goods_id_list}")

    try:
        spu_model = build_spu_model(args, related_goods)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    print("\n=== 创建通兑超团（MeResourceFacade#submitSpu）===")
    print(f"  partnerId : {args.partner_id}")
    print(f"  shopIds   : {','.join(args.shop_ids)}")
    print(f"  title     : {spu_model.get('spuBaseModel',{}).get('title','')}")
    print(f"  salePrice : {args.sale_price}分")
    print(f"  linePrice : {args.line_price}分")
    print(f"  addPrice  : {args.base_add_price or '无'}")
    print(f"  swimlane  : {args.swimlane or '主干'}")

    if args.dry_run:
        print("\n  [dry-run] 以下为将提交的 SpuModel：")
        print(json.dumps(spu_model, ensure_ascii=False, indent=2))
        return

    response = _iface.call_raw(
        partner_id=args.partner_id,
        spu_model=spu_model,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    spu_id = _iface.extract_spu_id(response)

    print("\n" + "=" * 56)
    print("  通兑超团创建完成")
    print(f"  spuId     : {spu_id or '响应未直接返回，需通过商品查询接口回查'}")
    print(f"  partnerId : {args.partner_id}")
    print(f"  shopIds   : {','.join(args.shop_ids)}")
    print(f"  原始响应  : {json.dumps(response, ensure_ascii=False)}")
    print("=" * 56)
    if spu_id:
        print(
            f"\n  📋 验证入库/审核/在线状态："
            f"python3 factory/super-deal/query-spu.py --partner-id {args.partner_id} --spu-id {spu_id} --wait"
        )
        print("     （不要用 querySpuListPage，该接口对超团查询不可靠恒返回空列表；通兑超团需等审核完成后 status 才会变为 1）")

    # ── 自动串联审核流程（auditProduct 图文信息审核，无需 BPM）──
    if not spu_id:
        print("\n  ⚠️ 未获取到 spuId，无法自动审核，请手动执行审核脚本")
        return

    if args.skip_audit:
        print("\n  --skip-audit 已跳过自动审核，请手动执行：")
        print(f"  python3 factory/audit/super-deal-unified/audit.py --spu-id {spu_id} --partner-id {args.partner_id} --graphic-only --auto-online")
        return

    audit_ok = _run_auto_audit(spu_id, args.partner_id)

    # ── 上线后刷新 SPU 缓存（SPU 套餐产品缓存 + POI-SPU 映射缓存）──
    # 超团审核上线后报价服务依赖 SPU 缓存与 POI-SPU 映射缓存，若不刷新会出现
    # C 端查不到产品/房型售罰等问题。best-effort，失败不中断主流程。
    # 仅在自动审核+上线成功时刷新；--skip-audit / 审核失败时不刷新（需用户手动上线后自行刷新）。
    if not audit_ok:
        print("\n  ⚠️ 自动审核/上线未完全成功，跳过 SPU 缓存刷新", file=sys.stderr)
        print("  请手动审核上线后执行：", file=sys.stderr)
        print(
            f"  hthotel-ops-product --env {args.cache_env} goodsquery query-spu "
            f"--spu-id {spu_id} --sync",
            file=sys.stderr,
        )
        return

    if args.skip_refresh_spu_cache:
        print("\n  --skip-refresh-spu-cache 已跳过 SPU 缓存刷新")
        return

    print("\n  ⏳ 开始刷新 SPU 缓存（goodsoperator-cli）...")
    refresh_spu_cache(
        spu_id=spu_id,
        poi_ids=args.shop_ids,
        env=args.cache_env,
    )


if __name__ == "__main__":
    main()

