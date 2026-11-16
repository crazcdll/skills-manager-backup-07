#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置校验器 — 独立的可选配置项收集（ptest、bundle_lock 等）。

bundle_lock 是 MRN 锁包配置，与环境/认证方式正交。
场景 AppMock 不作为可选配置采集：它是 case 级声明，由 `steps.json` 的
`env.mock_ids` 提供，`flow-init` 原样透传。
本模块**不读取任何文档文件**（没有 md 解析入口）：所有配置只有 `steps.json`
与 intake 两个来源，避免出现第二份事实。

ptest **不是**环境无关的通用开关：它是「线上环境(A) + partMock 注入」，
仅线上环境可选（适用关系以 `env_validator.ENV_CAPABILITIES` 为唯一事实来源）。
本模块负责在合成 env 时代入 env_type 做**组合校验**，与环境不匹配的 ptest
直接报错（早失败），而非放行到执行层才由 Mock 遮蔽暴露。

本模块不包含任何必填项，所有字段均为 required=False。
"""

from aitest.shared.errors import ConfigError
from aitest.provisioning.validators.env_validator import field_applicable


class ConfigValidationError(ConfigError):
    """可选配置（ptest/锁包）校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "OPTIONAL_CONFIG_INVALID"


def validate_config(config_dict, env_type):
    """校验可选配置块，通过时返回标准化后的 config 配置。

    Args:
        config_dict: 含 ptest（可选）、bundle_lock（可选）
        env_type:    当前环境类型（A/B/C/D，**必填**）——可选能力必须与环境
                     匹配，依据 `env_validator.ENV_CAPABILITIES`（唯一事实来源）；
                     不提供 env_type 就无法判定适用性，故不设默认值。
    校验失败时抛出 ConfigValidationError。
    """
    if not isinstance(config_dict, dict):
        raise ConfigValidationError("config 配置必须是字典")

    normalized = dict(config_dict)

    # ptest：布尔 + 环境适用性（仅线上 A 适用；矩阵见 env_validator.ENV_CAPABILITIES）
    ptest = normalized.get("ptest", False)
    if not isinstance(ptest, bool):
        raise ConfigValidationError("ptest 必须是布尔值 true/false")
    if ptest and not field_applicable("ptest", env_type):
        raise ConfigValidationError(
            f"ptest 仅适用于线上环境（env.type=A），当前 env.type={str(env_type).upper()} 不支持；"
            "请关闭 ptest 或选择线上环境（A）"
        )
    normalized["ptest"] = ptest

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

