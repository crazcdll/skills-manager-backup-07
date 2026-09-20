#!/usr/bin/env python3
"""通过 MeResourceFacade#submitSpu RPC 创建商促通兑超团。

直接调用研发 Thrift RPC（与非通兑/普通通兑超团共用同一已注册 OCTO 接口）：
  appkey  : com.sankuai.hotel.biz.platform
  service : com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method  : submitSpu(Long userId, SpuModel spuModel)

商促通兑超团（spuExchangeType=2）核心特点：
  - 不需要关联固定门店和产品：poiId=null、relatedGoodsList=[]
    （无需走全日房 W1 / 非房 W3 / 直连商品等任何前置流程）
  - 必须由用户提供关联商促活动 ID（--promo-activity-id）和
    选择选单 ID（--sieve-goods-id），写入
    superDealModel.superDealRelatedModel.spuPromoActivityModel
  - 选单覆盖门店由后端按商促活动动态解析（topPoiList=[]）
  - autoPublish=false，创建后自动串联审核上线流程
    （复用 factory/audit/super-deal-unified/audit.py --graphic-only --auto-online，
    与普通通兑超团一致）

模板来源：线上成功抓包（traceId=0a15e4e7844b1789030427605，spuId=2257594710，
partnerId=4570390，MTA 网关 /api/v1/mta/prepay/partner/{partnerId}/spu/submit
的扁平请求 → 映射为标准嵌套 SpuModel，后端最终调的就是同一个 submitSpu RPC）。

与其他超团的关键差异：
  - vs 非通兑（spuExchangeType=1）：不需要专属全日房/非房，必须传商促活动+选单
  - vs 普通达兑（spuExchangeType=0）：不需要 ≥2 门店全日房，必须传商促活动+选单
  - 价格默认值贴近商促场景：mtPrice=7000分(70元)、linePrice=8000分(80元)
  - 有效期默认贴近线上商促形态：入住/售卖约一年（362 天，后端约束最长 363 天），
    而非普通超团的 30 天

⚠️ --promo-activity-id / --sieve-goods-id 必须是测试环境真实存在的商促活动
   和选单 ID（线上抓包值 100100422 / 1671782299 不能直接在测试环境使用）。

使用示例：
  # dry-run 查看将提交的 SpuModel
  python3 factory/super-deal-promo/create-super-deal-promo.py \
    --partner-id 4570390 \
    --promo-activity-id <商促活动ID> \
    --sieve-goods-id <选择选单ID> \
    --dry-run

  # 正式创建（创建后自动串联 auditProduct 审核 + 上线 + SPU 缓存刷新）
  python3 factory/super-deal-promo/create-super-deal-promo.py \
    --partner-id 4570390 \
    --promo-activity-id <商促活动ID> \
    --sieve-goods-id <选择选单ID> \
    --product-name "商促通兑超团-测试"
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

DEFAULT_PURCHASE_NOTE = (
    "重点说明：超级团购能否成功兑换酒店房间，取决于兑换日期的剩余可兑换房间数量，"
    "显示\u201c今日已兑完\u201d的日期将无法继续用券兑换\n"
    "预约方式：选择对应酒店→选择产品预约下单→到店入住，实际可用以酒店产品展示为准"
)

# 默认有效期（天）：贴近线上商促通兑超团真实形态（约一年）
# ⚠️ 后端硬约束（实测 2026-09-10）：售卖结束时间最长只能设置从今天算起 363 天内，
#    取 362 留余量；线上抓包时创建日距今 365 天能过，推测网关/线上与测试校验不一致，
#    以测试环境实测为准。
DEFAULT_VALID_DAYS = 362


def _load_module(module_name: str, relative_path: str):
    spec = ilu.spec_from_file_location(module_name, os.path.join(ROOT, relative_path))
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_iface = _load_module("super_deal_promo_interface", "interface/super-deal-promo/interface.py")

# 上线后刷新 SPU 缓存（best-effort，失败不中断主流程）
from scripts.refresh_spu_cache import refresh_spu_cache  # noqa: E402


def _show_schema() -> None:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        print(file.read())


# ════════════════════════════════════════════════════════════════════════════
# SpuModel 默认模板
# ════════════════════════════════════════════════════════════════════════════

def _default_spu_template() -> dict:
    """返回商促通兑超团默认 SpuModel 模板（标准嵌套结构，忠实线上成功抓包）。

    模板遵循标准 SpuModel 嵌套结构（MeResourceFacade#submitSpu 接口）：
      顶层 7 字段：spuBaseModel / spuImageInfoModel / spuAuditModel /
                   relatedGoodsList / relateXgoodsInfoModels / dayTripModel / superDealModel
      商促核心字段在 superDealModel.superDealRelatedModel.spuPromoActivityModel

    与线上抓包（网关扁平结构）的字段对应关系见 interface/super-deal-promo/interface.py
    文件头注释。以下抓包值保持原样：couponTitle=null（subTitle 有值）、
    coupon.startDate/endDate=null、couponInventoryModel.startDateTime=null、
    giftUse.startTime=null、periodDays=null、splitRoomNight=null、
    purchaseRestrictionRule.periodUnit=2。
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
            "poiId": None,                     # 商促通兑=null（不绑定单门店）
            "autoPublish": False,              # 需审核后上线（与普通通兑一致）
            "relatedPoiNum": 0,
            "relatedGoodsNum": 0,
            "giftsName": "",
            "serviceTel": "",
            "customerName": "",
            "nameCustomerType": 0,
            "spuRelatedGoodsType": 1,
        },
        # ── 2. spuImageInfoModel: 图片信息（审核时由 auditProduct 添加默认图文）──
        "spuImageInfoModel": None,
        # ── 3. spuAuditModel: 审核信息 ────────────────────────────────
        "spuAuditModel": None,
        # ── 4. relatedGoodsList: 关联产品（商促必须为空）──────────────
        "relatedGoodsList": [],
        # ── 5. relateXgoodsInfoModels: 关联非房（商促不关联）──────────
        "relateXgoodsInfoModels": [],
        # ── 6. dayTripModel: 套餐信息（超团不用）──────────────────────
        "dayTripModel": None,
        # ── 7. superDealModel: 超团专属业务字段 ────────────────────────
        "superDealModel": {
            # 7.1 superDealBaseModel: 超团基础信息
            "superDealBaseModel": {
                "preCheckDays": 0,
                "linePrice": None,              # build_spu_model 填充
                "spuExchangeType": 2,          # 2=商促通兑
                "spuServiceType": 2,
                "marketingLabels": [],
                "recommendations": [],
                "spuSaleStrategyList": copy.deepcopy(DEFAULT_SALE_STRATEGIES),
            },
            # 7.2 superDealRelatedModel: 超团关联信息（商促核心）──────
            "superDealRelatedModel": {
                "spuRelatedGoodsType": 1,
                "relatedGoodsByFile": False,
                "spuPromoActivityModel": {
                    "promoActivityId": None,    # build_spu_model 填充（必填）
                    "promoActivityName": None,  # 可选
                    "sieveGoodsId": None,       # build_spu_model 填充（必填）
                },
            },
            # 7.3 distinctionAddPrice: 是否分门店加价
            "distinctionAddPrice": False,
            # 7.4 spuDistinctAddPriceModelList: 分门店加价
            "spuDistinctAddPriceModelList": None,
            # 7.5 spuBaseAddPriceModelList: 统一加价（商促抓包为 null）
            "spuBaseAddPriceModelList": None,
            # 7.6 superDealCouponModel: 营销/券信息
            "superDealCouponModel": {
                "mBoxId": None,                 # 后端自动创建（响应返回 bizacctid）
                "couponAuditStatus": None,
                "auditMsg": None,
                "couponTitle": None,            # 抓包为 null
                "subTitle": None,               # build_spu_model 填充
                "startDate": None,              # 抓包为 null（售卖时间在 couponInventoryModel）
                "endDate": None,                # 抓包为 null
                "marketVisible": False,
                "topAppType": [0, 1, 3, 4, 100],
                "personBindLimit": None,         # build_spu_model 填充
                "needGuestFlag": 0,
                "needGuestInfo": [],
                "payLimitTime": 30,
                "couponInventoryModel": {
                    "startDateTime": None,      # 抓包为 null
                    "spuSellTimeType": 1,
                    "inventoryAmount": None,    # build_spu_model 填充
                    "endDateTime": None,        # build_spu_model 填充
                },
                "superDealGiftCardModel": {
                    "giftCardId": None,
                    "mtPrice": None,             # build_spu_model 填充
                    "roomNights": None,          # build_spu_model 填充
                    "splitRoomNight": None,      # 抓包为 null
                    "checkInScenes": None,
                    "superDealGiftUseModel": {
                        "startTime": None,       # 抓包为 null
                        "endTime": None,         # build_spu_model 填充
                        "periodDays": None,      # 抓包为 null
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
                    "topPoiList": [],           # 商促：选单门店由后端按活动动态解析
                },
                "purchaseRestrictionRule": {
                    "period": None,
                    "periodUnit": 2,             # 抓包为 2
                    "quantity": None,
                },
            },
            # 7.7 spuModuleAuditMap: 模块审核状态
            "spuModuleAuditMap": None,
            # 7.8 spuActivityStockModel: 团购库存（商促抓包无此字段）
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
# SpuModel 构建
# ════════════════════════════════════════════════════════════════════════════

def build_spu_model(template: dict, args: argparse.Namespace) -> dict:
    """以模板为基底（默认模板或用户自定义模板），仅覆盖本次构造的动态字段。

    与 create-super-deal.py（非通兑）模式一致：用户自定义模板（--payload-file/
    --payload-json）的其余字段原样保留，动态字段一律由 CLI 参数覆盖。
    """
    model = copy.deepcopy(template)

    # 自定义模板时确保商促核心嵌套结构存在（缺失则注入默认骨架，供下方覆盖）
    super_deal = model.setdefault("superDealModel", {})
    sd_related = super_deal.setdefault("superDealRelatedModel", {})
    sd_related.setdefault(
        "spuPromoActivityModel",
        {"promoActivityId": None, "promoActivityName": None, "sieveGoodsId": None},
    )

    title = args.product_name or f"{args.partner_id}商促通兑超团_{int(time.time())}"

    # ── spuBaseModel: 通用基础信息 ──────────────────────────────
    base = model.setdefault("spuBaseModel", {})
    # 新建不传 spuId（让后端自动生成，避免被误判为更新）
    base.pop("spuId", None)
    base["title"] = title
    base["partnerId"] = int(args.partner_id)
    base["poiId"] = None              # 商促通兑不绑定单门店
    base["relatedGoodsNum"] = 0       # 不关联产品
    base["relatedPoiNum"] = 0
    base["spuType"] = 1
    base["autoPublish"] = False       # 需审核后上线

    # ── superDealModel: 超团专属业务字段 ────────────────────────
    # superDealBaseModel
    sd_base = super_deal.setdefault("superDealBaseModel", {})
    sd_base["linePrice"] = args.line_price
    sd_base["spuExchangeType"] = 2    # 商促通兑
    sd_base.setdefault("spuServiceType", 2)

    # superDealRelatedModel.spuPromoActivityModel（商促核心字段）
    promo = sd_related["spuPromoActivityModel"]
    promo["promoActivityId"] = int(args.promo_activity_id)
    promo["promoActivityName"] = args.promo_activity_name
    promo["sieveGoodsId"] = int(args.sieve_goods_id)

    # superDealCouponModel
    coupon = super_deal.setdefault("superDealCouponModel", {})
    coupon["subTitle"] = f"{title}红包"[:20]
    coupon["personBindLimit"] = args.person_bind_limit

    # 券售卖截止时间（couponInventoryModel；抓包 startDateTime=null）
    inventory = coupon.setdefault("couponInventoryModel", {})
    inventory["inventoryAmount"] = args.inventory
    inventory["endDateTime"] = _parse_date(args.sell_end)  # 当天 00:00（忠实抓包）

    # 礼包卡
    gift_card = coupon.setdefault("superDealGiftCardModel", {})
    gift_card["mtPrice"] = args.sale_price
    gift_card["roomNights"] = args.room_nights

    # 入住时间（availableCheckInDateList；抓包 startTime=null）
    gift_use = gift_card.setdefault("superDealGiftUseModel", {})
    checkin_start_ms = _parse_date(args.checkin_start)
    checkin_end_ms = _parse_date(args.checkin_end, end_of_day=True)
    gift_use["endTime"] = checkin_end_ms
    gift_use["availableCheckInDateList"] = [{
        "startDate": checkin_start_ms,
        "endDate": checkin_end_ms,
    }]

    # ── relatedGoodsList（顶层）：商促必须为空 ──────────────────
    model["relatedGoodsList"] = []
    # spuImageInfoModel：默认 None（审核时 auditProduct 添加默认图文，
    # 与普通通兑"submitSpu 不能带 spuImageInfoModel"的约束一致）
    model.setdefault("spuImageInfoModel", None)

    return model


# ════════════════════════════════════════════════════════════════════════════
# 创建后自动审核（复用通兑超团审核脚本，审核上线流程一致）
# ════════════════════════════════════════════════════════════════════════════

def _run_auto_audit(spu_id: str, partner_id: str) -> bool:
    """创建成功后自动串联审核流程（auditProduct 图文信息审核 + 自动上线）。

    与普通通兑超团完全一致：商促通兑 autoPublish=false，创建后需
    auditProduct（configKey=spuDeal）完成图文+优惠券+选单侧审核，再
    updateSpuStatus 上线。直接 subprocess 调用
    factory/audit/super-deal-unified/audit.py --graphic-only --auto-online。
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
    print("  自动串联审核流程（auditProduct 图文信息审核 + 自动上线，与普通通兑一致）")
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
    print("\n  ✅ 自动审核流程完成", file=sys.stderr)
    return True


# ════════════════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════════════════

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


def main() -> None:
    if "--show-schema" in sys.argv:
        _show_schema()
        return

    parser = argparse.ArgumentParser(
        description="创建商促通兑超团（MeResourceFacade#submitSpu RPC，spuExchangeType=2）"
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--payload-file", help="自定义完整 SpuModel JSON 文件（覆盖默认模板，动态字段仍由参数覆盖）")
    source.add_argument("--payload-json", help="自定义完整 SpuModel JSON 字符串")
    parser.add_argument("--partner-id", required=True, help="供应商ID")
    parser.add_argument(
        "--promo-activity-id", required=True,
        help=(
            "关联商促活动 ID（必填，须由用户提供，且必须是测试环境真实存在的活动；"
            "映射 superDealRelatedModel.spuPromoActivityModel.promoActivityId）"
        ),
    )
    parser.add_argument(
        "--sieve-goods-id", type=int, required=True,
        help=(
            "选择选单 ID（必填，须由用户提供，且必须是测试环境真实存在的选单；"
            "映射 superDealRelatedModel.spuPromoActivityModel.sieveGoodsId）"
        ),
    )
    parser.add_argument(
        "--promo-activity-name", default=None,
        help="商促活动名称（可选，默认不传；映射 spuPromoActivityModel.promoActivityName）",
    )
    parser.add_argument("--product-name", default="", help="超团标题，不传则自动生成")
    parser.add_argument(
        "--sale-price", type=int, default=7000,
        help="售价 mtPrice，单位分（默认 7000 分=70 元，贴近线上商促形态）",
    )
    parser.add_argument(
        "--line-price", type=int, default=8000,
        help="划线价 linePrice，单位分（默认 8000 分=80 元）",
    )
    parser.add_argument("--inventory", type=int, default=1000, help="券库存")
    parser.add_argument("--person-bind-limit", type=int, default=5, help="每人绑定上限")
    parser.add_argument("--room-nights", type=int, default=1, help="间夜数")
    parser.add_argument(
        "--sell-end",
        help=f"售卖截止日期，格式 YYYY-MM-DD（默认今天+{DEFAULT_VALID_DAYS}天；⚠️ 后端约束最长 363 天）",
    )
    parser.add_argument(
        "--checkin-start",
        help="可入住开始日期，格式 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument(
        "--checkin-end",
        help=f"可入住结束日期，格式 YYYY-MM-DD（默认今天+{DEFAULT_VALID_DAYS}天）",
    )
    parser.add_argument("--swimlane", default="", help="泳道名，空表示主干")
    parser.add_argument("--dry-run", action="store_true", help="打印 RPC 参数但不执行")
    parser.add_argument(
        "--skip-audit", action="store_true",
        help="跳过创建后的自动审核（auditProduct 图文信息审核 + 自动上线）；默认创建后自动审核",
    )
    parser.add_argument(
        "--skip-refresh-spu-cache", action="store_true",
        help="跳过上线后的 SPU 缓存刷新；默认审核上线后自动刷新",
    )
    parser.add_argument(
        "--cache-env", choices=["test", "prod"], default="test",
        help="goodsoperator-cli 缓存刷新环境（默认 test，与本 skill 创建商品所用环境一致）",
    )
    args = parser.parse_args()

    # ── 参数校验 ────────────────────────────────────────────────────────
    try:
        int(args.promo_activity_id)
    except (TypeError, ValueError):
        parser.error(f"--promo-activity-id 必须为整数: {args.promo_activity_id!r}")

    if bool(args.checkin_start) != bool(args.checkin_end):
        parser.error("--checkin-start 与 --checkin-end 必须同时提供")
    if args.checkin_start and args.checkin_end and args.checkin_start > args.checkin_end:
        parser.error("--checkin-start 不能晚于 --checkin-end")
    if args.line_price < args.sale_price:
        parser.error("--line-price 不能小于 --sale-price")
    if args.inventory <= 0 or args.person_bind_limit <= 0 or args.room_nights <= 0:
        parser.error("库存、每人绑定上限和间夜数必须大于 0")

    # ── 派生默认日期（贴近线上商促形态：今天起约一年）──────────────────
    today = datetime.now(CHINA_TZ)
    if not args.checkin_start:
        args.checkin_start = today.strftime("%Y-%m-%d")
    if not args.checkin_end:
        args.checkin_end = (today + timedelta(days=DEFAULT_VALID_DAYS)).strftime("%Y-%m-%d")
    if not args.sell_end:
        args.sell_end = (today + timedelta(days=DEFAULT_VALID_DAYS)).strftime("%Y-%m-%d")

    # ── 构建 SpuModel 并校验 ───────────────────────────────────────────
    try:
        template = _load_payload(args.payload_file, args.payload_json)
        model = build_spu_model(template, args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))

    try:
        _iface.validate(args.partner_id, model)
    except ValueError as error:
        parser.error(str(error))

    print("\n=== 创建商促通兑超团（MeResourceFacade#submitSpu）===")
    print(f"  partnerId       : {args.partner_id}")
    print(f"  promoActivityId : {args.promo_activity_id}")
    print(f"  sieveGoodsId    : {args.sieve_goods_id}")
    print(f"  title           : {model.get('spuBaseModel', {}).get('title', '')}")
    print(f"  salePrice       : {args.sale_price}分")
    print(f"  linePrice       : {args.line_price}分")
    print(f"  入住范围        : {args.checkin_start} ~ {args.checkin_end}")
    print(f"  售卖截止        : {args.sell_end}")
    print(f"  swimlane        : {args.swimlane or '主干'}")

    if args.dry_run:
        print("\n  [dry-run] 以下为将提交的 SpuModel：")
        print(json.dumps(model, ensure_ascii=False, indent=2))
        return

    response = _iface.call_raw(
        partner_id=args.partner_id,
        spu_model=model,
        swimlane=args.swimlane,
        dry_run=args.dry_run,
    )

    spu_id = _iface.extract_spu_id(response)

    print("\n" + "=" * 56)
    print("  商促通兑超团创建完成")
    print(f"  spuId     : {spu_id or '响应未直接返回，需通过商品查询接口回查'}")
    print(f"  partnerId : {args.partner_id}")
    print(f"  原始响应  : {json.dumps(response, ensure_ascii=False)}")
    print("=" * 56)
    if spu_id:
        print(
            f"\n  📋 验证入库/审核/在线状态："
            f"python3 factory/super-deal/query-spu.py --partner-id {args.partner_id} --spu-id {spu_id} --wait"
        )

    # ── 自动串联审核流程（auditProduct 图文审核 + 自动上线，与普通通兑一致）──
    if not spu_id:
        print("\n  ⚠️ 未获取到 spuId，无法自动审核，请手动执行审核脚本")
        return

    if args.skip_audit:
        print("\n  --skip-audit 已跳过自动审核，请手动执行：")
        print(f"  python3 factory/audit/super-deal-unified/audit.py --spu-id {spu_id} --partner-id {args.partner_id} --graphic-only --auto-online")
        return

    audit_ok = _run_auto_audit(spu_id, args.partner_id)

    # ── 上线后刷新 SPU 缓存 ────────────────────────────────────────────
    # 商促通兑不绑定固定门店（选单门店由后端按商促活动动态解析），
    # 因此只刷新 SPU 套餐产品缓存，不刷新 POI-SPU 映射缓存。
    # best-effort，失败不中断主流程。
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
        poi_ids=None,  # 商促不绑定门店，仅刷新 SPU 缓存
        env=args.cache_env,
    )


if __name__ == "__main__":
    main()

