#!/usr/bin/env python3
"""
接口层：缓存刷新 / 改价审核
工具：工具1031（HotelCacheUpdateOrPriceAuditService.cacheUpdateOrPriceAudit）
协议：Thrift via DataUnity

operationType 枚举：
  1 - 缓存刷新（商品/SPU/门店/货盘级别，四选一）
  2 - BD改价审核（通过/驳回）
  3 - 商家改价审核（通过/驳回）

auditStatus（operationType=2/3 时必填）：
  2 - 驳回
  3 - 通过（默认）

目标ID（四选一）：productId / spuId / poiId / rpId
"""

import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.du_runner import run_tool, DuError  # noqa


TOOL_ID = 1031

OP_DESC = {
    1: "缓存刷新",
    2: "BD改价审核",
    3: "商家改价审核",
}

AUDIT_STATUS_DESC = {
    2: "驳回",
    3: "通过",
}


# ════════════════════════════════════════════════════════════════════════════
# 参数校验
# ════════════════════════════════════════════════════════════════════════════

def validate(params: dict) -> None:
    """
    参数联动强校验，失败时抛出 ValueError。

    V1  operationType 必须是 1/2/3
    V2  至少传一个目标ID（productId/spuId/poiId/rpId）
    V3  operationType=2/3 时 auditStatus 必须是 2 或 3
    """
    errors = []
    op = params.get("operationType")
    if op not in (1, 2, 3):
        errors.append(f"V1: operationType={op} 非法，合法值：1=缓存刷新, 2=BD改价审核, 3=商家改价审核")
    ids_present = any(params.get(k) for k in ("productId", "spuId", "poiId", "rpId"))
    if not ids_present:
        errors.append("V2: 至少传一个目标ID（productId / spuId / poiId / rpId）")
    if op in (2, 3):
        audit_status = params.get("auditStatus")
        if audit_status not in (2, 3):
            errors.append(f"V3: operationType={op} 时 auditStatus 必须是 2（驳回）或 3（通过），"
                          f"当前值={audit_status}")
    if errors:
        raise ValueError(f"参数校验失败（共 {len(errors)} 项）：\n" +
                         "\n".join(f"  {e}" for e in errors))


# ════════════════════════════════════════════════════════════════════════════
# 主调用函数
# ════════════════════════════════════════════════════════════════════════════

def call(
    operation_type: int,
    product_id: Optional[int] = None,
    spu_id: Optional[int] = None,
    poi_id: Optional[int] = None,
    rp_id: Optional[int] = None,
    audit_status: int = 3,
    is_oversea: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    缓存刷新 / 改价审核，直调 DataUnity 工具1031。

    参数：
        operation_type - 操作类型：1=缓存刷新, 2=BD改价审核, 3=商家改价审核
        product_id     - 商品ID（四选一）
        spu_id         - SPU ID（套餐/超团）（四选一）
        poi_id         - 门店ID（四选一）
        rp_id          - 货盘RPID（四选一）
        audit_status   - 审核状态（op=2/3时必填）：2=驳回, 3=通过（默认3）
        is_oversea     - 是否境外（缓存刷新时生效，默认False）
        dry_run        - True 时只打印不执行

    返回：DataUnity 原始响应 dict
    异常：ValueError（参数校验失败），DuError（工具调用失败）
    """
    params = {
        "operationType": operation_type,
        "auditStatus":   audit_status,
        "isOversea":     is_oversea,
    }
    if product_id is not None:
        params["productId"] = product_id
    if spu_id is not None:
        params["spuId"] = spu_id
    if poi_id is not None:
        params["poiId"] = poi_id
    if rp_id is not None:
        params["rpId"] = rp_id

    validate(params)
    return run_tool(TOOL_ID, params, dry_run=dry_run)


# ════════════════════════════════════════════════════════════════════════════
# batchOnlineSwitch - 批量上线/下线商品
# ════════════════════════════════════════════════════════════════════════════

SWITCH_STATUS_DESC = {
    2: "上线",
    3: "下线",
}

SWITCH_APPKEY  = "com.sankuai.hotel.biz.platform"
SWITCH_SERVICE = "com.meituan.hotel.biz.platform.goods.facade.standard.MeGoodsFacade"
SWITCH_METHOD  = "batchOnlineSwitch"


def call_online_switch(
    partner_id: int,
    poi_id: str,
    goods_ids: list,
    status: int,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    批量上线 / 下线商品，直调 MeGoodsFacade#batchOnlineSwitch。

    对应前端请求：
      POST /api/gw/v1/product/goods/batchOnlineSwitch
      body: {"partnerId":4550589,"poiId":"1085927256096396","goodsIds":[600000632131],"status":2}

    参数：
        partner_id - 供应商ID
        poi_id     - 门店ID（字符串）
        goods_ids  - 商品ID列表，如 [600000632131]
        status     - 2=上线，3=下线
        swimlane   - 泳道（空字符串=主干）
        dry_run    - True 时只打印不执行

    返回：RPC 原始响应 dict
    异常：ValueError（参数校验失败），InvokeError（调用失败）
    """
    if status not in (2, 3):
        raise ValueError(f"status={status} 非法，合法值：2=上线, 3=下线")
    if not goods_ids:
        raise ValueError("goods_ids 不能为空")

    params = {
        "partnerId": int(partner_id),
        "poiId": str(poi_id),
        "goodsIds": [int(g) for g in goods_ids],
        "status": int(status),
    }

    # 复用 runner.invoke（与 batchCreateGoods 同一链路）
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    from scripts.runner import invoke, InvokeError  # noqa

    label = SWITCH_STATUS_DESC.get(status, str(status))
    if dry_run:
        import json
        print(f"[dry-run] batchOnlineSwitch 参数：\n{json.dumps(params, ensure_ascii=False, indent=2)}")
        return {}

    print(f"正在批量{label}商品（{goods_ids}）...")
    return invoke(
        appkey=SWITCH_APPKEY,
        service=SWITCH_SERVICE,
        method=SWITCH_METHOD,
        params=params,
        swimlane=swimlane,
        timeout_ms=30000,
        raise_on_biz_error=True,
        progress_hint=f"批量{label}商品中...",
    )

