#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证方式规则 + 凭证校验。

职责边界（与 `provisioning/credentials.py` 分工）：
  · 本模块只回答「这种登录方式需要什么」——要不要密码、要不要账号；
  · 「账号从哪来」由 credentials 的 provider 决定，本模块不关心来源。

认证规则：
  password → 凭证登录，需要 account + password
  qahome   → QAHome 验证码登录，只需要 account（号池生成）
  noop     → 免登录，不需要账号

设备类型约束（DEVICE_TYPE_ALLOWED_AUTH_METHODS）：
  local（本地真机）→ 只允许 noop（不自动登录，避免污染真机数据）
"""
import re

from aitest.shared.errors import ConfigError

# 认证方式 → 认证约束。唯一事实来源，新增认证方式时在此追加。
AUTH_METHOD_RULES = {
    "password": {
        "desc": "凭证登录",
        "requires_password": True,
        "requires_account": True,
    },
    "qahome": {
        "desc": "QAHome 验证码登录",
        "requires_password": False,
        "requires_account": True,
    },
    "noop": {
        "desc": "默认已登录（跳过登录）",
        "requires_password": False,
        "requires_account": False,
    },
}

# 认证方式 → 中文描述
AUTH_METHOD_DESC = {
    "password": "凭证登录",
    "qahome": "QAHome 验证码登录",
    "noop": "默认已登录（跳过登录）",
}

# device_type → 允许的 auth_method 集合。
# 与 APP_ENV_TYPE_RULES 正交：这是"设备维度"对登录方式的约束，不区分环境。
# 不在白名单中的 device_type 视为不限制。
DEVICE_TYPE_ALLOWED_AUTH_METHODS = {
    "local": {"noop"},
}

_MIN_PASSWORD_LENGTH = 6
_PLACEHOLDER_RE = re.compile(
    r'^([\*\.\_\-]+|placeholder|REPLACE_WITH_\w+|todo|fixme|changeme|password|test1*|dummy|none|null|undefined|N/?A)$',
    re.IGNORECASE,
)
_MASKED_RE = re.compile(r'^.{1,4}\*{2,}.{0,4}$')


class AuthValidationError(ConfigError):
    """认证方式/凭证校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "AUTH_CONFIG_INVALID"


def _is_real_password(password):
    """判断凭证是否为真实可用凭证（非占位符/脱敏/过短）。"""
    if not password or not isinstance(password, str):
        return False
    password = password.strip()
    if len(password) < _MIN_PASSWORD_LENGTH:
        return False
    if _PLACEHOLDER_RE.match(password):
        return False
    if _MASKED_RE.match(password):
        return False
    if len(set(password)) == 1:
        return False
    return True


def get_allowed_auth_methods(device_type: str):
    """返回指定 device_type 下允许的 auth_method 集合；None 表示不限制。"""
    return DEVICE_TYPE_ALLOWED_AUTH_METHODS.get(device_type)


def get_auth_method_rules() -> dict:
    """获取认证方式规则表（深拷贝，防止调用方意外修改）。"""
    return {k: dict(v) for k, v in AUTH_METHOD_RULES.items()}


def validate_credential(auth_method, credential):
    """校验一份已解析的凭证是否满足该认证方式的要求。

    凭证的**来源**不在本函数关心范围内（平台下发 / 用户提供 / 号池一视同仁），
    只看「够不够用」。通过时返回凭证本身，便于链式使用。

    Raises:
        AuthValidationError
    """
    method = str(auth_method or "").lower()
    rule = AUTH_METHOD_RULES.get(method)
    if rule is None:
        raise AuthValidationError(
            f"不支持的认证方式: {method}，支持: {'/'.join(AUTH_METHOD_RULES)}"
        )

    if not rule["requires_account"]:
        return credential

    if credential is None or not getattr(credential, "account", ""):
        raise AuthValidationError(
            f"认证方式 {method}（{rule['desc']}）缺少登录账号。\n"
            "  线上账号由平台下发（ provisioning/credentials.py::fixed_credential ）；"
            "如需临时替换，传 credential={account, password, country_code}。"
        )

    if rule["requires_password"] and not _is_real_password(credential.password):
        got = "未提供" if not credential.password else "不是有效凭证（占位符/脱敏/过短）"
        raise AuthValidationError(
            f"认证方式 {method}（{rule['desc']}）的密码{got}。\n"
            "  线上账号由平台下发（ provisioning/credentials.py::fixed_credential ）；"
            "如需临时替换，同时传 credential.account 与 credential.password（必须成对）。"
        )

    # 国家码必须显式给出：平台下发一定会带；手动覆盖时漏传会静默落到登录动作的
    # 默认国家码，表现为「账号密码都对但登录失败」，很难排查。
    if rule["requires_password"] and not str(getattr(credential, "country_code", "") or "").strip():
        raise AuthValidationError(
            f"认证方式 {method}（{rule['desc']}）缺少国家码 country_code。\n"
            "  平台下发应同时返回 country_code；"
            "如需手动指定，传 credential={account, password, country_code}。"
        )

    return credential
