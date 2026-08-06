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

def call(
    partner_id: str,
    poi_id: str,
    product_name: str,
    xgoods_type: str = "catering",
    swimlane: str = "",
    dry_run: bool = False,
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
        params=params,
        swimlane=swimlane,
        timeout_ms=30000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"直调 MeResourceFacade#submitXgoods（partnerId={partner_id}, poiId={poi_id}）...",
    )

