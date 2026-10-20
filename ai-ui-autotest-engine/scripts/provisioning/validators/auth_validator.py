#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证方式校验器 — 独立的登录方式选择 + 凭证收集。

与 env_validator 解耦：env_validator 只负责「在什么环境测」，
auth_validator 只负责「怎么登录」，两者独立选择、正交组合。

认证规则：
  password → 凭证登录，account + password 必填
  qahome   → QAHome 验证码登录，account 必填
  noop     → 免登录，不需要 account/password

设备类型约束（DEVICE_TYPE_ALLOWED_AUTH_METHODS）：
  local（本地真机）→ 只允许 noop（不自动登录，避免污染真机数据）
"""

import hashlib
import re

from shared.errors import ConfigError

# 认证方式 → 认证约束。唯一事实来源，新增认证方式时在此追加。
#   account_generatable —— 账号是否可由引擎自动生成（测试手机号）：
#     · 验证码登录(qahome)：账号是「任意格式合法的测试号」，可自动生成；
#     · 凭证登录(password)：账号是用户真实账号，必须手填。
AUTH_METHOD_RULES = {
    "password": {
        "desc": "凭证登录",
        "password_required": True,
        "account_required": True,
        "account_generatable": False,
    },
    "qahome": {
        "desc": "QAHome 验证码登录",
        "password_required": False,
        "account_required": True,
        "account_generatable": True,
    },
    "noop": {
        "desc": "默认已登录（跳过登录）",
        "password_required": False,
        "account_required": False,
        "account_generatable": False,
    },
}

# device_type → 允许的 auth_method 集合。
# 与 APP_ENV_TYPE_RULES 正交：这是"设备维度"对登录方式的约束，不区分环境。
# 不在白名单中的 device_type 视为不限制。
DEVICE_TYPE_ALLOWED_AUTH_METHODS = {
    "local": {"noop"},
}

# 认证方式 → 中文描述
AUTH_METHOD_DESC = {
    "password": "凭证登录",
    "qahome": "QAHome 验证码登录",
    "noop": "默认已登录（跳过登录）",
}

_MIN_PASSWORD_LENGTH = 6
_PLACEHOLDER_RE = re.compile(
    r'^([\*\.\_\-]+|placeholder|REPLACE_WITH_\w+|todo|fixme|changeme|password|test1*|dummy|none|null|undefined|N/?A)$',
    re.IGNORECASE,
)
_MASKED_RE = re.compile(r'^.{1,4}\*{2,}.{0,4}$')


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


class AuthValidationError(ConfigError):
    """认证方式/凭证校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "AUTH_CONFIG_INVALID"


def get_allowed_auth_methods(device_type: str):
    """返回指定 device_type 下允许的 auth_method 集合；None 表示不限制。"""
    return DEVICE_TYPE_ALLOWED_AUTH_METHODS.get(device_type)


def get_auth_method_rules() -> dict:
    """获取认证方式规则表（深拷贝，防止调用方意外修改）。"""
    return dict(AUTH_METHOD_RULES)


# ═══════════════════════════════════════════════════════════════════
# 账号来源：手填 vs 引擎生成（唯一事实来源：AUTH_METHOD_RULES）
# ═══════════════════════════════════════════════════════════════════

def account_source(auth_method) -> str:
    """认证方式 → 账号来源：'manual'（用户手填）| 'generated'（引擎生成）| 'none'。"""
    rule = AUTH_METHOD_RULES.get(str(auth_method or "").lower())
    if not rule or not rule.get("account_required", True):
        return "none"
    return "generated" if rule.get("account_generatable") else "manual"


def account_auth_methods(source: str) -> tuple:
    """账号来源为 source 的认证方式集合（供声明层构造互斥门控）。"""
    return tuple(m for m in AUTH_METHOD_RULES if account_source(m) == source)


def account_depends_on(source: str) -> list:
    """账号题的 depends_on 表达式列表（单一来源：AUTH_METHOD_RULES）。

    账号在不同认证方式下由**两个互斥的题**承担（手填 / 自动生成），本函数给出
    其中一题应有的门控，声明层据此声明，不硬编码 auth_method 字面量。
    """
    methods = account_auth_methods(source)
    if not methods:
        raise ConfigError(f"没有认证方式的账号来源为 {source!r}（AUTH_METHOD_RULES 配置错误）")
    if len(methods) == 1:
        return ["auth_method", f"auth_method == '{methods[0]}'"]
    return ["auth_method", f"auth_method in ({', '.join(repr(m) for m in methods)})"]


# ── 测试手机号：格式（唯一事实来源）+ 确定性生成 ────────────────────
# 中国大陆手机号：1 开头、第二位 3-9、共 11 位。
TEST_ACCOUNT_RE = re.compile(r"^1[3-9]\d{9}$")


def is_valid_test_account(value) -> bool:
    """是否为格式合法的测试手机号。"""
    return isinstance(value, str) and bool(TEST_ACCOUNT_RE.match(value))


def generate_test_account(seed: str) -> str:
    """由 workspace 标识**确定性**生成一个格式合法的测试手机号。

    确定性：同一 seed 恒得同一号码 —— 派生值每轮重算也不改号（否则登录会因号码
      漂移而查不到本次下发的验证码）；
    隔离性：不同 workspace 的 seed 不同 → 号码不同，避免并行会话在共享短信池里串号。
    """
    digest = hashlib.sha256(str(seed).encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big")
    return f"1{3 + n % 7}{(n // 7) % 10**9:09d}"


def validate_auth_config(auth_dict):
    """校验认证配置块，通过时返回标准化后的 auth 配置。

    auth_dict 应包含: auth_method, account, password（可选）
    校验失败时抛出 AuthValidationError。
    """
    if not isinstance(auth_dict, dict):
        raise AuthValidationError("auth 配置必须是字典")

    auth_method = auth_dict.get("auth_method")
    if not auth_method:
        raise AuthValidationError("auth_method 不能为空（password/qahome/noop）")

    auth_method = str(auth_method).lower()
    if auth_method not in AUTH_METHOD_RULES:
        raise AuthValidationError(
            f"不支持的认证方式: {auth_method}，支持: {'/'.join(AUTH_METHOD_RULES.keys())}"
        )

    rule = AUTH_METHOD_RULES[auth_method]
    account = auth_dict.get("account")
    password = auth_dict.get("password")

    if rule.get("account_required", True) and not account:
        raise AuthValidationError(
            f"认证方式 {auth_method} ({rule['desc']}) 必须提供 account（测试手机号）"
        )

    if rule["password_required"]:
        if not _is_real_password(password):
            hint = "未填写 password" if not password else (
                f"password 值 \"{password}\" 不是有效凭证（占位符/脱敏/过短）"
            )
            raise AuthValidationError(
                f"认证方式 {auth_method} ({rule['desc']}) 凭证登录必须提供真实凭证。\n"
                f"  当前问题: {hint}\n"
                f"  解决方法: 用 AskQuestion 向用户询问真实凭证"
            )
        normalized_password = password

    # 构建标准化结果
    normalized = dict(auth_dict)
    normalized.update({
        "auth_method": auth_method,
        "account": account,
        "_password_raw": normalized_password if rule["password_required"] else password,
    })
    normalized.pop("password", None)

    return normalized