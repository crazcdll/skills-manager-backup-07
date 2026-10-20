#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置校验器 — 独立的可选配置项收集（ptest、bundle_lock 等）。

bundle_lock 是 MRN 锁包配置，与环境/认证方式正交。
场景 AppMock 不作为可选配置采集：它是 case 级配置（每个 Flow 的「可测性环境」
AppMock 行 → 对应 case 的 `mock_ids`，由 flow-init 解析）。
提取入口 `extract_flow_appmock_ids` 与 `extract_flow_bundle_names` 仍共用同一张表，
保证「Flow 声明的配置」在解析层口径一致。

ptest **不是**环境无关的通用开关：它是「线上环境(A) + partMock 注入」，
仅线上环境可选（适用关系以 `env_validator.ENV_CAPABILITIES` 为唯一事实来源）。
本模块负责在合成 env 时代入 env_type 做**组合校验**，与环境不匹配的 ptest
直接报错（早失败），而非放行到执行层才由 Mock 遮蔽暴露。

本模块不包含任何必填项，所有字段均为 required=False。
"""

import re

from shared.errors import ConfigError
from provisioning.validators.env_validator import field_applicable


class ConfigValidationError(ConfigError):
    """可选配置（ptest/锁包）校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "OPTIONAL_CONFIG_INVALID"


def extract_flow_bundle_names(flow_path):
    """从 Flow「可测性环境」表提取目标锁包包名列表（仅包名）。
    与 env_validator 中的 extract_flow_bundle_names 逻辑一致。
    """
    _FLOW_BUNDLE_ROW_RE = re.compile(r'\|\s*(?:目标锁包|MRN锁包|锁包)\s*\|\s*(.+?)\s*\|')
    try:
        with open(flow_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []
    names = []
    for m in _FLOW_BUNDLE_ROW_RE.findall(content):
        raw = m.strip().replace("`", "")
        raw = re.sub(r'（.*?）|\(.*?\)', '', raw).strip()
        for part in raw.split(","):
            part = part.strip()
            if ":" in part:
                part = part.split(":")[0].strip()
            if part and part not in names:
                names.append(part)
    return names


_APPMOCK_ROW_RE = re.compile(r'\|\s*AppMock\s*\|\s*(.+?)\s*\|', re.IGNORECASE)
_FLOW_BACKTICK_RE = re.compile(r'`([^`]+)`')
_APPMOCK_ID_RE = re.compile(r'^[A-Za-z0-9_.\-]+$')


def extract_flow_appmock_ids(flow_path):
    """从 Flow「可测性环境」表提取 AppMock 规则 ID 列表。

    该表是「测试环境配置的唯一落点」，AppMock 行形如：
        | AppMock | `16305525`（自动化测试：preview 接口 Mock，测试环境下提单页必需） |

    规则：
      · 只取反引号内的 token（无反引号时整格回退），去掉括号注释后按逗号拆分；
      · 仅保留形如 ID 的 token（字母/数字/._-），避免把中文说明误当 ID。
    与 `extract_flow_bundle_names` 是同一张表的兄弟行提取器，二者保持同构。
    """
    try:
        with open(flow_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return []
    ids = []
    for cell in _APPMOCK_ROW_RE.findall(content):
        tokens = _FLOW_BACKTICK_RE.findall(cell) or [cell]
        for token in tokens:
            token = re.sub(r'（.*?）|\(.*?\)', '', str(token)).strip()
            for part in token.split(","):
                part = part.strip().strip("`").strip()
                if part and _APPMOCK_ID_RE.match(part) and part not in ids:
                    ids.append(part)
    return ids


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

