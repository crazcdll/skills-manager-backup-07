#!/usr/bin/env python3
"""
接口层：生意助手/全域通报名
工具：工具1037（ProductMakeService.createProductAsync）
协议：Thrift via DataUnity（异步）

configKey 枚举：
  notUpscale                  生意助手（仅生意助手，不上全域通）
  upscaleFixed                全域通一口价（最常用）
  upscaleDiscount             全域通折扣
  upscaleFixedDiscountMixed   全域通一口价折扣混合

两种报名方式（互斥）：
  方式一：供应商+门店报名（新建Goods报名）→ 传 partner_id + poi_id
  方式二：指定产品ID报名（对已有产品报名）→ 传 product_id

⚠️ 异步接口，报名结果由【供应链商品测试数据助手】通过大象推送。
"""

import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.du_runner import run_tool, DuError  # noqa


TOOL_ID = 1037

VALID_CONFIG_KEYS = {
    "notUpscale",
    "upscaleFixed",
    "upscaleDiscount",
    "upscaleFixedDiscountMixed",
}

CONFIG_KEY_DESC = {
    "notUpscale":               "生意助手",
    "upscaleFixed":             "全域通一口价",
    "upscaleDiscount":          "全域通折扣",
    "upscaleFixedDiscountMixed":"全域通一口价折扣混合",
}


# ════════════════════════════════════════════════════════════════════════════
# 参数校验
# ════════════════════════════════════════════════════════════════════════════

def validate(mode: int, params: dict) -> None:
    """
    参数联动强校验，失败时抛出 ValueError。

    V1  configKey 必须在合法枚举中
    V2  方式一：partnerId + poiId 必填
    V3  方式二：productId 必填
    V4  mode 只能是 1 或 2
    """
    errors = []
    if mode not in (1, 2):
        errors.append(f"V4: mode={mode} 非法，只能是 1（供应商+门店）或 2（产品ID）")
    config_key = params.get("configKey", "")
    if config_key not in VALID_CONFIG_KEYS:
        errors.append(f"V1: configKey={config_key!r} 非法，"
                      f"合法值: {sorted(VALID_CONFIG_KEYS)}")
    if mode == 1:
        if not params.get("partnerId"):
            errors.append("V2: 方式一必须传 partnerId")
        if not params.get("poiId"):
            errors.append("V2: 方式一必须传 poiId")
    elif mode == 2:
        if not params.get("productId"):
            errors.append("V3: 方式二必须传 productId")
    if errors:
        raise ValueError(f"参数校验失败（共 {len(errors)} 项）：\n" +
                         "\n".join(f"  {e}" for e in errors))


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数
# ════════════════════════════════════════════════════════════════════════════

def call(
    mode: int,
    config_key: str = "upscaleFixed",
    partner_id: Optional[str] = None,
    poi_id: Optional[str] = None,
    product_id: Optional[str] = None,
    mis: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """
    生意助手/全域通报名，直调 DataUnity 工具1037。

    参数：
        mode        - 报名方式：1=供应商+门店（新建Goods），2=指定产品ID
        config_key  - 报名类型（默认 "upscaleFixed"=全域通一口价）
        partner_id  - [方式一] 供应商ID
        poi_id      - [方式一] 门店ID
        product_id  - [方式二] 产品ID
        mis         - 操作人MIS
        dry_run     - True 时只打印不执行

    返回：DataUnity 原始响应 dict
    异常：ValueError（参数校验失败），DuError（工具调用失败）
    """
    if mode == 1:
        params = {
            "partnerId": partner_id,
            "poiId":     poi_id,
            "configKey": config_key,
        }
    else:
        params = {
            "productId": product_id,
            "configKey": config_key,
        }
    if mis:
        params["mis"] = mis

    validate(mode, params)
    return run_tool(TOOL_ID, params, dry_run=dry_run)

