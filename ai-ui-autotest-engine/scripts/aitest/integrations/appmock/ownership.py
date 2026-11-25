#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行期规则归属闸门。

可写集合 = 运行域里实际存在的规则（以域查询为唯一事实源，不看本地清单）：
母本 id 不在运行域列表里 → 写命令一律被拒；执行期自建规则（如归档）也在运行域，天然可写。
mock-map.json 仅服务读侧视图（规则库 id → 运行副本 id）。
"""
import os

from aitest.shared.case_utils import resolve_runtime_domain
from aitest.shared.errors import MockError
from aitest.shared.json_utils import read_json
from aitest.shared.paths import mock_state_dir
from aitest.integrations.appmock.rules import appmock_list, extract_mock_id

# 物化状态文件名（mock_lifecycle 写、本模块读）
MOCK_MAP_FILENAME = "mock-map.json"

# {domain: {mockId: rule}} —— 单次 CLI 进程内缓存，避免每个写命令多一次 list
_INDEX_CACHE = {}

_REJECT_HINT = (
    "执行期只允许写**运行域副本**：请改用 mock-map 里的运行域 mockId，"
    "或改规则库里的原始规则后重跑 `mock-preflight` 生效"
)


def runtime_rule_index(refresh: bool = False) -> dict:
    """{运行域 mockId: rule} —— 查询失败返回空 dict（调用方一律 fail-closed）。"""
    domain = resolve_runtime_domain()
    if refresh or domain not in _INDEX_CACHE:
        index = {}
        for item in appmock_list(mis=domain):
            mock_id = extract_mock_id(item)
            if mock_id:
                index[mock_id] = str(item.get("rule") or "").strip()
        _INDEX_CACHE[domain] = index
    return _INDEX_CACHE[domain]


def runtime_rule_by_rule() -> dict:
    """{rule: 运行域 mockId}（同 rule 取首条）。"""
    return {rule: mid for mid, rule in runtime_rule_index().items() if rule}


def require_runtime_rule(mock_id) -> str:
    """断言 mockId 属于本次运行域，返回其 rule；否则 fail-fast。"""
    target = str(mock_id or "").strip()
    if not target:
        raise MockError(f"缺少 mockId。{_REJECT_HINT}")
    rule = runtime_rule_index().get(target)
    if rule is None:
        raise MockError(f"mockId={target} 不在本次运行域内（属于规则库母本或已失效）。{_REJECT_HINT}")
    return rule


def find_runtime_rule(rule) -> str:
    """按 rule 查运行域已有规则 id（不存在返回空串）。"""
    return runtime_rule_by_rule().get(str(rule or "").strip(), "")


def mock_state() -> dict:
    """读取本次 run 的物化状态（mock-map.json）；无 run/无文件返回空 dict。"""
    try:
        path = os.path.join(mock_state_dir(), MOCK_MAP_FILENAME)
    except (RuntimeError, OSError):
        return {}
    data = read_json(path, default={})
    return data if isinstance(data, dict) else {}
