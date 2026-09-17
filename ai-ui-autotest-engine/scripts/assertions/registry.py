#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言策略注册表。"""

from __future__ import annotations
from typing import Dict, Optional
from assertions.engine import BaseAssertionStrategy
from assertions.ui.strategies.present import TextPresentStrategy
from assertions.ui.strategies.gone import TextGoneStrategy
from assertions.ui.strategies.visual import VisualAIStrategy

class StrategyRegistry:
    """策略注册表"""

    def __init__(self):
        self._strategies: Dict[str, BaseAssertionStrategy] = {}

    def register(self, type_name: str, strategy: BaseAssertionStrategy):
        self._strategies[type_name] = strategy

    def get(self, type_name: str) -> Optional[BaseAssertionStrategy]:
        return self._strategies.get(type_name)

    def types(self) -> list:
        return list(self._strategies.keys())


# 全局注册表实例
REGISTRY = StrategyRegistry()

# 注册 UI 断言策略
REGISTRY.register("present", TextPresentStrategy())
REGISTRY.register("gone", TextGoneStrategy())
REGISTRY.register("visual", VisualAIStrategy())
# 数据断言策略（api / track）由 api_step_executor / track_step_executor 独立处理
# 在引擎层只做协议解析，不注册执行策略