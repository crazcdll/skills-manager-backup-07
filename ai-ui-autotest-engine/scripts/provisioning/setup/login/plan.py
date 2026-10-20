#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1 登录计划：把 env 配置块派生为**可执行、已校验**的登录意图。

本层是"要登到哪、用什么认证、带什么配置"的**唯一表达**，纯数据 + 纯函数，
不接触设备、不拼 scheme。

派生规则**全部复用既有校验器**，不在此处重复维护：
  - 环境类型合法性     → provisioning.validators.env_validator
  - 认证方式与凭证要求 → provisioning.validators.auth_validator
  - 可选配置           → provisioning.validators.config_validator
  - env.type → auth_method 默认值 → env_validator.infer_auth_method
    （device_type=local 会被强制为 noop，该约束同样来自 auth_validator）

组合规则（`env_type(A/B/C/D) × auth_method × 泳道配置`）集中在 `LoginPlan.derive()` 一处表达，
规则本体仍由校验器承载。
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from provisioning.setup.location import DEFAULT_LOCATION, normalize_location
from provisioning.validators.env_validator import (
    ENV_TYPE_MAP, infer_auth_method, validate_env_config,
)
from provisioning.validators.auth_validator import get_allowed_auth_methods


# 目标环境：与 Pillow/AppMock 的"环境切换"语义对齐
TARGET_ENV_ONLINE = "online"
TARGET_ENV_ALPHA = "alpha"
TARGET_ENV_SWIMLINE = "swimline"
TARGET_ENV_NONE = "none"

DEFAULT_COUNTRY_CODE = "86"
DEFAULT_LOGIN_ENV = "prod"  # pillow signin 的 env 取值；prod=线上（test/staging 见 CLI）


@dataclass(frozen=True)
class SwimlineConfig:
    lane_name: str
    url_pattern: str = "/*"


@dataclass(frozen=True)
class LoginPlan:
    """已校验的登录意图。"""

    app: str
    device_type: str
    auth: str                      # password | qahome | noop
    env_type: str                  # A | B | C | D
    target_env: str                # online | alpha | swimline | none
    account: Optional[str] = None
    password: Optional[str] = None
    country_code: str = DEFAULT_COUNTRY_CODE
    login_env: str = DEFAULT_LOGIN_ENV
    location: Optional[str] = None
    swimline: Optional[SwimlineConfig] = None
    url_mappings: Tuple[dict, ...] = ()
    bundles: Tuple[dict, ...] = ()
    ptest: bool = False

    # ── 派生入口 ──────────────────────────────────────────────
    @staticmethod
    def derive(env_config: dict, app: str = "meituan",
               device_type: str = "sandbox") -> "LoginPlan":
        """从 env 配置块派生登录计划（含全部既有校验）。

        Raises:
            EnvValidationError / AuthValidationError / ConfigValidationError
            —— 均继承 ConfigError。
        """
        env_config = dict(env_config or {})
        env_config["app"] = app
        normalized = validate_env_config(env_config, app=app, device_type=device_type)

        env_type = str(normalized.get("type", "")).upper()
        auth = normalized.get("auth_method") or infer_auth_method(env_type, device_type)

        # device_type 约束优先于 env.type 推断（如 local → 强制 noop）
        allowed = get_allowed_auth_methods(device_type)
        if allowed is not None and len(allowed) == 1:
            auth = next(iter(allowed))

        swimline_cfg = normalized.get("swimline") or None
        url_mappings = tuple(normalized.get("url_mappings") or ())

        return LoginPlan(
            app=app,
            device_type=device_type,
            auth=auth,
            env_type=env_type,
            target_env=_resolve_target_env(env_type, swimline_cfg, url_mappings),
            account=normalized.get("account"),
            password=normalized.get("_password_raw"),
            country_code=str(normalized.get("country_code") or DEFAULT_COUNTRY_CODE),
            login_env=str(normalized.get("login_env") or DEFAULT_LOGIN_ENV),
            # 定位预设名归一化（支持中文别名「北京」→ beijing）；未配置时用兜底城市。
            # 登录必须有定位：App 无定位会卡「定位中」，首页渲染不出「去登录」入口。
            location=normalize_location(normalized.get("location")) or DEFAULT_LOCATION,
            swimline=(SwimlineConfig(lane_name=swimline_cfg["lane_name"],
                                     url_pattern=swimline_cfg.get("url_pattern", "/*"))
                      if isinstance(swimline_cfg, dict) and swimline_cfg.get("lane_name") else None),
            url_mappings=url_mappings,
            bundles=tuple(normalized.get("bundle_lock") or ()),
            ptest=bool(normalized.get("ptest")),
        )

    @property
    def env_name(self) -> str:
        """env.type 对应的环境名（取 ENV_TYPE_MAP）。"""
        return ENV_TYPE_MAP.get(self.env_type, "")


def _resolve_target_env(env_type: str, swimline_cfg, url_mappings) -> str:
    """env.type + 泳道配置 → 目标环境。

    组合规则：
      D                → none（不自动登录）
      B + 有泳道/映射  → swimline
      B + 两者都空     → 降级 alpha（跳过泳道配置，按 alpha 处理）
      A                → online
      C                → alpha
    """
    if env_type == "D":
        return TARGET_ENV_NONE
    if env_type == "B":
        has_swim = bool(isinstance(swimline_cfg, dict) and (swimline_cfg.get("lane_name") or "").strip()) \
            or bool(url_mappings)
        return TARGET_ENV_SWIMLINE if has_swim else TARGET_ENV_ALPHA
    if env_type == "A":
        return TARGET_ENV_ONLINE
    if env_type == "C":
        return TARGET_ENV_ALPHA
    return TARGET_ENV_NONE
