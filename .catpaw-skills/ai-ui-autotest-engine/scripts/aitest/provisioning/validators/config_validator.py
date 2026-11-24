#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置校验器 — 独立的可选配置项收集（bundle_lock）。

bundle_lock 是 MRN 锁包配置，与环境/认证方式正交。
场景 AppMock 不作为可选配置采集：它是 case 级声明，由 `steps.json` 的
`env.mock_ids` 提供，`flow-init` 原样透传。
本模块**不读取任何文档文件**（没有 md 解析入口）：所有配置只有 `steps.json`
与 intake 两个来源，避免出现第二份事实。

ptest **不是**可选配置：它是环境类型 P（线上泳道）的派生事实，由
`env_validator` 按 `type=P` 物化，本模块不再接受 ptest 字段。

本模块不包含任何必填项，所有字段均为 required=False。
"""

from aitest.shared.errors import ConfigError


class ConfigValidationError(ConfigError):
    """可选配置（锁包）校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "OPTIONAL_CONFIG_INVALID"


def validate_config(config_dict, env_type):
    """校验可选配置块，通过时返回标准化后的 config 配置。

    Args:
        config_dict: 含 bundle_lock（可选）
        env_type:    当前环境类型（A/P/B/C/D/E），保留入参用于统一调用签名；
                     可选能力的适用性仍由 `env_validator.ENV_CAPABILITIES` 判定。
    校验失败时抛出 ConfigValidationError。
    """
    if not isinstance(config_dict, dict):
        raise ConfigValidationError("config 配置必须是字典")

    normalized = dict(config_dict)

    # bundle_lock 校验
    bundle_lock = normalized.get("bundle_lock", [])
    if not isinstance(bundle_lock, list):
        raise ConfigValidationError("bundle_lock 必须是数组（每项 {name, version} 对象）；无锁包请传 []")
    normalized_bundle_lock = []
    for item in bundle_lock:
        if not isinstance(item, dict):
            raise ConfigValidationError(
                f"bundle_lock 每项必须是对象 {{name, version}}: {item!r}"
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigValidationError(
                f"bundle_lock 每项必须提供非空 name（包名）: {item!r}"
            )
        version = item.get("version")
        if version not in (None, ""):
            if not isinstance(version, str) or not version.strip():
                raise ConfigValidationError(
                    f"bundle_lock 每项 version 必须是非空字符串或省略（省略=仅声明目标不锁包）: {item!r}"
                )
        entry = {"name": name.strip()}
        if version:
            entry["version"] = version.strip()
        normalized_bundle_lock.append(entry)
    normalized["bundle_lock"] = normalized_bundle_lock

    return normalized
