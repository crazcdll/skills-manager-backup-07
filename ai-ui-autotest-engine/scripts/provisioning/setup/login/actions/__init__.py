#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L3 认证动作层：按 `auth_method` 注册的"怎么登录"实现。

职责边界（禁止越界）：
  ✅ 构造并下发认证动作（scheme / UI 交互）、等待、产出 AuthOutcome
  ❌ 不做环境前置副作用（属 L2 steps）、不直接拼平台 shell（须经 PlatformOps）

平台差异**不进本层**：pillow action 规范跨端统一（同一个 signin action 在
Android 与 Harmony 内容一致），端差异体现在下发通道（PlatformOps.launch_scheme）
与登录态判定（L4 probes）。

注册表是本层唯一扩展点：新增认证方式 = 新增一个模块 + 在 `_AUTH_ACTIONS` 登记一行。
"""
from abc import ABC, abstractmethod
from typing import Dict, Tuple

from provisioning.setup.login.policy import AuthOutcome


class AuthAction(ABC):
    """认证动作契约。"""

    #: 认证方式标识，与 validators.auth_validator.AUTH_METHOD_RULES 的键一致
    method: str = ""

    @abstractmethod
    def perform(self, plan, ctx) -> AuthOutcome:
        """执行认证动作并返回结果。"""


# auth_method → (模块路径, 类名)。惰性导入，避免无关依赖在 import 期被拉起。
_AUTH_ACTIONS: Dict[str, Tuple[str, str]] = {
    "password": ("provisioning.setup.login.actions.password", "PasswordAuthAction"),
    "qahome": ("provisioning.setup.login.actions.qahome", "QahomeAuthAction"),
    "noop": ("provisioning.setup.login.actions.noop", "NoopAuthAction"),
}


def registered_auth_methods() -> Tuple[str, ...]:
    return tuple(_AUTH_ACTIONS)


def create_auth_action(auth_method: str) -> AuthAction:
    """按 auth_method 构造认证动作。

    Raises:
        ValueError: 未注册的认证方式（"未注册即不可用"，与三张校验表的约定一致）
    """
    import importlib

    entry = _AUTH_ACTIONS.get(auth_method)
    if entry is None:
        raise ValueError(
            f"未注册的认证方式: {auth_method!r}（已注册: {', '.join(_AUTH_ACTIONS)}）"
        )
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


__all__ = ["AuthAction", "create_auth_action", "registered_auth_methods", "AuthOutcome"]
