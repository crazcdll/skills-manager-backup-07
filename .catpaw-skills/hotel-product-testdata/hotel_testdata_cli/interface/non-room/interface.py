#!/usr/bin/env python3
"""
接口层：非房商品创建（xGoods）

直接 Thrift RPC 调用
  appKey : com.sankuai.hotel.biz.platform
  service: com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade
  method : submitXgoods
  同步接口，直接返回 xGoodsId；创建成功后仍需走审核流程才可上线。
"""

import sys
import os
import json
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ── 直接 RPC 接口配置 ────────────────────────────────────────────────────────
APPKEY  = "com.sankuai.hotel.biz.platform"
SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeResourceFacade"
METHOD  = "submitXgoods"
# submitXgoods(XgoodsInfoModifyParam param) —— 单参数复杂结构体
# body 模式下 DataUnity 无法自动推断该结构体参数类型，须走显式 parameterTypes 模式
XGOODS_INFO_MODIFY_PARAM_TYPE = (
    "com.meituan.hotel.biz.platform.goods.model.xgoods.XgoodsInfoModifyParam"
)

# ── 从 schema.json 加载模板（单一数据源，避免硬编码与 schema 不同步）────────
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "../../factory/non-room/schema.json")

def _load_templates() -> dict:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    raw = schema.get("templates", {})
    # 过滤掉 _desc 等注释字段，只保留正式模板
    return {k: {fk: fv for fk, fv in v.items() if not fk.startswith("_")}
            for k, v in raw.items()}

_TEMPLATES = _load_templates()


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数（直接 Thrift RPC）
# ════════════════════════════════════════════════════════════════════════════

# ── 独立售卖（加购）sellStatus=1 时必填的 8 个扩展字段 ─────────────────────────
# CRS-60（PR hotel/hotel-biz-platform#3281）。字段归属唯一依据：
# 学城《1.前后端交互接口》contentId=2769956950。
SELL_ALONE_REQUIRED_FIELDS = (
    "promotion_text", "display_order", "contract_no", "total_stock",
    "market_price", "sale_price", "commission_rate", "max_num_per_order",
)


def call(
    partner_id: str,
    poi_id: str,
    product_name: str,
    xgoods_type: str = "catering",
    swimlane: str = "",
    dry_run: bool = False,
    sell_status: int = 0,
    promotion_text: Optional[str] = None,
    display_order: Optional[int] = None,
    contract_no: Optional[str] = None,
    total_stock: Optional[int] = None,
    market_price: Optional[str] = None,
    sale_price: Optional[str] = None,
    commission_rate: Optional[int] = None,
    max_num_per_order: Optional[int] = None,
) -> dict:
    """
    直接 Thrift RPC 调用 MeResourceFacade#submitXgoods 创建非房。

    同步接口，成功时直接返回 xGoodsId（无需等待大象推送）。
    创建成功后仍需走审核流程才可上线。

    参数：
        partner_id   - 供应商ID（partnerId）
        poi_id       - 门店ID（poiId）
        product_name - 商品名称（name 字段；⚠️ 不能超过 20 字符）
        xgoods_type  - 模板类型：catering（餐饮，默认）| scenic（景点/门票）
        swimlane     - 泳道（空字符串=主干）
        dry_run      - True 时只打印不执行

        独立售卖（加购）扩展 —— sellStatus=1 时下列 8 个参数全部必填：
        sell_status        - 0=非加购（默认，不影响原逻辑）| 1=普通加购（独立售卖）
        promotion_text     - 促销文案（basicInfoModel.promotionText）
        display_order      - 展示顺序 1-20（basicInfoModel.displayOrder）
        contract_no        - 合同编号字符串（basicInfoModel.contractNo）；仅支持合同类型
                              ∈ {预付合同=2, 团购合同=0}，禁止包销合同(=5)
        total_stock        - 总库存（⚠️ stockModel.totalStock，顶层新模型，非 basicInfoModel 字段）
        market_price       - 门市价，单位分（priceModel.marketPrice）
        sale_price         - 卖价，单位分（priceModel.salePrice）
        commission_rate    - 佣金率，万分位整数如 1250=12.50%（priceModel.commissionRate）
        max_num_per_order  - 每单限购份数 1-10（ruleModel.useRuleModel.maxNumPerOrder）

    返回：接口原始响应 dict
    """
    import copy
    from scripts.runner import invoke as rpc_invoke  # noqa

    # 选择模板
    template = _TEMPLATES.get(xgoods_type)
    if template is None:
        raise ValueError(f"未知 xgoods_type={xgoods_type!r}，合法值：{list(_TEMPLATES.keys())}")

    # 深拷贝模板，填入动态字段
    # ⚠️ name 不能超过 20 字符（接口硬限制）
    if len(product_name) > 20:
        import sys as _sys
        print(f"[WARN] 商品名称超过20字符（{len(product_name)}），已自动截断至20字符", file=_sys.stderr)
        product_name = product_name[:20]

    xgoods_model = copy.deepcopy(template)
    xgoods_model["basicInfoModel"]["partnerId"] = partner_id
    xgoods_model["basicInfoModel"]["poiId"] = poi_id
    xgoods_model["basicInfoModel"]["name"] = product_name

    # ── 独立售卖（加购）扩展字段组装 ─────────────────────────────────────────
    if sell_status:
        _local_vars = {
            "promotion_text": promotion_text, "display_order": display_order,
            "contract_no": contract_no, "total_stock": total_stock,
            "market_price": market_price, "sale_price": sale_price,
            "commission_rate": commission_rate, "max_num_per_order": max_num_per_order,
        }
        missing = [f for f in SELL_ALONE_REQUIRED_FIELDS if _local_vars.get(f) in (None, "")]
        if missing:
            raise ValueError(
                f"sellStatus=1（独立售卖/加购）时以下字段全部必填，缺失：{missing}；"
                f"对应 CLI 参数：--promotion-text/--display-order/--contract-no/--total-stock/"
                f"--market-price/--sale-price/--commission-rate/--max-num-per-order"
            )
        xgoods_model["basicInfoModel"]["sellStatus"] = sell_status
        xgoods_model["basicInfoModel"]["promotionText"] = promotion_text
        xgoods_model["basicInfoModel"]["displayOrder"] = display_order
        xgoods_model["basicInfoModel"]["contractNo"] = contract_no
        # ⚠️ stockModel 是与 basicInfoModel/priceModel 同级的顶层新模型，不要塞进 basicInfoModel
        xgoods_model["stockModel"] = {"totalStock": total_stock}
        xgoods_model.setdefault("priceModel", {})
        xgoods_model["priceModel"]["marketPrice"] = market_price
        xgoods_model["priceModel"]["salePrice"] = sale_price
        xgoods_model["priceModel"]["commissionRate"] = commission_rate
        # ⚠️ 实测发现：sellStatus=1 时 marketPrice/salePrice 从可空变必填，会联动触发
        # "请上传价值凭证"校验（普通非房因 marketPrice 为空不触发）。补齐门市价价值凭证
        # （priceProofType=0 + priceProofUrls，复用模板已有的测试图床地址），否则报 200002000。
        if not xgoods_model["priceModel"].get("priceProofUrls"):
            _test_proof_url = (
                xgoods_model.get("basicInfoModel", {}).get("images", [{}])[0]
                .get("imageModels", [{}])[0].get("url")
                or "http://p0.inf.test.sankuai.com/testhubble/b44e5f8e32047452045e051bfd08553537344.webp"
            )
            xgoods_model["priceModel"]["priceProofType"] = 0
            xgoods_model["priceModel"]["priceProofUrls"] = [_test_proof_url]
        xgoods_model.setdefault("ruleModel", {}).setdefault("useRuleModel", {})
        xgoods_model["ruleModel"]["useRuleModel"]["maxNumPerOrder"] = max_num_per_order
    else:
        # sellStatus=0（默认）：显式写入 0，行为与原非房上单逻辑完全一致
        xgoods_model["basicInfoModel"]["sellStatus"] = 0

    params = {
        "partnerId":      partner_id,
        "poiId":          poi_id,
        "submitType":     1,
        "xgoodsInfoModel": xgoods_model,
    }

    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD,
        params=None,
        parameter_values=[
            json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        ],
        parameter_types=[XGOODS_INFO_MODIFY_PARAM_TYPE],
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"直调 MeResourceFacade#submitXgoods（partnerId={partner_id}, poiId={poi_id}）...",
    )

