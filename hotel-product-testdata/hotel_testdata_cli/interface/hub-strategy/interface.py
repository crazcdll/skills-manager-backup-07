#!/usr/bin/env python3
"""
接口层：货盘规则（HubStrategy）管理

Thrift RPC
  appKey : com.sankuai.hotelcrs.supply.hub
  service: com.sankuai.hotelcrs.supply.hub.api.facade.HubStrategyFacade

支持三个方法：
  - createStrategy           创建货盘规则，返回 strategyId
  - updateStrategyStatus     更新货盘规则状态（发布上线 strategyStatus=1 / 下线 strategyStatus=0）
  - query_goods2spu          查询货盘规则生成的套餐记录，返回 spuId 列表
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.runner import invoke as rpc_invoke  # noqa

# ── 接口配置 ──────────────────────────────────────────────────────────────────
APPKEY  = "com.sankuai.hotelcrs.supply.hub"
SERVICE = "com.sankuai.hotelcrs.supply.hub.api.facade.HubStrategyFacade"

METHOD_CREATE  = "createStrategy"
METHOD_UPDATE  = "updateStrategyStatus"
METHOD_QUERY   = "queryGoods2SpuRecordByPage"

# ── 可选渠道枚举（供 factory 层参考）────────────────────────────────────────
CHANNELS = {
    "2783_2_1003_1007_4006":    "酒店搜索主流程/美团App/酒店民宿/POI详情页/酒店套餐",
    "2783_2_63_163_4605":       "酒店搜索主流程/美团App/门票/POI详情页/门票+酒店",
    "2783_1010_1011_1015_4606": "酒店搜索主流程/美团团购小程序/酒店民宿/POI详情页/景点游玩门票酒店套餐",
    "2783_16_1016_1019_4024":   "酒店搜索主流程/点评App/酒店民宿/POI详情页/酒店套餐",
    "2783_16_64_165_4607":      "酒店搜索主流程/点评App/门票/POI详情页/景点游玩酒店套餐",
    "2783_1021_1630_1631_4646": "酒店搜索主流程/点评小程序/景点游玩/POI详情页/景酒套餐",
}


# ════════════════════════════════════════════════════════════════════════════
# 创建货盘规则
# ════════════════════════════════════════════════════════════════════════════

def create_strategy(
    strategy_name: str,
    file_url: str,
    strategy_desc: str = "",
    strategy_type: int = 1,
    strategy_status: int = 0,
    relation_item_type: int = 3,
    break_strategy_type: int = 3,
    form_trans_type: int = 3,
    channel_break_type: int = 2,
    channels: list = None,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    创建货盘规则（HubStrategyFacade#createStrategy）。

    参数：
        strategy_name       - 规则名称（如"测试货盘规则"）
        file_url            - S3 文件下载链接（https://msstest.sankuai.com/...）
        strategy_desc       - 规则描述（可为空）
        strategy_type       - 规则类型（默认 1）
        strategy_status     - 初始状态（0=草稿，默认0；发布前先创建再调 updateStrategyStatus）
        relation_item_type  - 关联对象类型（默认 3=文件类型）
        break_strategy_type - 拆分策略类型（默认 3）
        form_trans_type     - 表单传输类型（默认 3）
        channel_break_type  - 渠道拆分类型（2=突破全渠道；5=删除部分渠道）；传入 channels 时自动切换为 5
        channels            - 要删除的渠道列表（channel_break_type=5 时使用），示例：
                              ["2783_2_1003_1007_4006", "2783_16_1016_1019_4024"]
                              为 None 时走突破全渠道（channelBreakType=2）
        swimlane            - 泳道（空=主干）
        dry_run             - True 时只打印不执行

    返回：接口响应 dict（含 strategyId）
    """
    # 有 channels 时自动切换为指定渠道模式
    if channels:
        channel_break_type = 5

    channel_break_rule: dict = {"channelBreakType": channel_break_type}
    if channels:
        channel_break_rule["channels"] = channels

    params = {
        "strategyName":   strategy_name,
        "strategyDesc":   strategy_desc,
        "strategyType":   strategy_type,
        "strategyStatus": strategy_status,
        "strategyItemModel": {
            "controlObject": {
                "relationItemType": relation_item_type,
                "fileUrl":          file_url,
            },
            "breakStrategyModel": {
                "breakStrategyType": break_strategy_type,
                "breakRule": {
                    "formTransBreakRuleModel": {
                        "formTransType":    form_trans_type,
                        "channelBreakRule": channel_break_rule,
                    }
                },
                "protectRule": None,
            },
        },
    }

    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD_CREATE,
        params=params,
        swimlane=swimlane,
        timeout_ms=10000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"创建货盘规则（{strategy_name}）...",
    )


# ════════════════════════════════════════════════════════════════════════════
# 更新货盘规则状态（发布上线 / 下线）
# ════════════════════════════════════════════════════════════════════════════

def update_strategy_status(
    strategy_id: int,
    strategy_status: int = 1,
    swimlane: str = "",
    dry_run: bool = False,
) -> dict:
    """
    更新货盘规则状态（HubStrategyFacade#updateStrategyStatus）。

    参数：
        strategy_id     - 货盘规则 ID（createStrategy 返回）
        strategy_status - 目标状态（1=发布上线，0=下线）
        swimlane        - 泳道（空=主干）
        dry_run         - True 时只打印不执行

    返回：接口响应 dict
    """
    params = {
        "strategyId":     strategy_id,
        "strategyStatus": strategy_status,
    }

    status_label = "发布上线" if strategy_status == 1 else "下线"
    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD_UPDATE,
        params=params,
        swimlane=swimlane,
        timeout_ms=20000,
        dry_run=dry_run,
        raise_on_biz_error=True,
        progress_hint=f"货盘规则 {strategy_id} {status_label}...",
    )


# ════════════════════════════════════════════════════════════════════════════
# 查询货盘规则生成的套餐记录
# ════════════════════════════════════════════════════════════════════════════

def query_goods2spu(
    strategy_id: int,
    page: int = 1,
    page_size: int = 10,
    swimlane: str = "",
) -> dict:
    """
    查询货盘规则生成的套餐记录（HubStrategyFacade#queryGoods2SpuRecordByPage）。

    参数：
        strategy_id - 货盘规则 ID（createStrategy 返回）
        page        - 页码（默认 1）
        page_size   - 每页条数（默认 10）
        swimlane    - 泳道（空=主干）

    返回：接口响应 dict；有效套餐：spuId 非 0 非 null 且 status=1
    """
    params = {
        "strategyId": strategy_id,
        "page":       page,
        "pageSize":   page_size,
    }
    return rpc_invoke(
        appkey=APPKEY,
        service=SERVICE,
        method=METHOD_QUERY,
        params=params,
        swimlane=swimlane,
        timeout_ms=10000,
        raise_on_biz_error=True,
        progress_hint=f"查询货盘规则 {strategy_id} 生成的套餐...",
    )

