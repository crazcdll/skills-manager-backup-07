#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""凭证（登录身份）—— 独立领域，唯一事实来源。

设计分工（两层，互不越界）：
  · `auth_validator.AUTH_METHOD_RULES` 只回答「要不要密码」；
  · 本模块回答「账号从哪来」。

来源由 **provider 函数** 承担，而不是由「激活哪个问题」承担：

  password（线上）→ fixed_credential    用户显式提供优先，否则平台下发（不内置、不降级）
  qahome  （测试）→ synthetic_phone     按 workspace 确定性生成（号池）
  noop            → None                不需要身份

新增来源（例如平台下发）只需在 `PROVIDERS` 里加一个函数，
问题声明与 env 合成都不必改动。

凭证以结构化对象在 env 里流转（`env.credential`），不再拆成
`account` / `password` / `test_account` 等多个平铺键。
"""
import hashlib
import re
from dataclasses import dataclass
from typing import Optional

from aitest.shared.errors import ConfigError

# ── 线上账号 ────────────────────────────────────────────────────────
# 权威来源是 yooz-server 下发（`platform/credential_api.py`）：Skill 内**不内置**
# 线上账号 —— 账号密码不随仓库扩散，轮换只改服务端；接口不可用即失败（不降级）。
# 该账号无实名认证、未绑银行卡：可走完下单流程，支付必然失败（见执行原则）。

SOURCE_PLATFORM = "platform"
SOURCE_EXPLICIT = "explicit"
SOURCE_SYNTHETIC = "synthetic"

# 来源 → 报告里显示的中文标签（便于排查「为什么这个用例用了另一个号」）
SOURCE_LABEL = {
    SOURCE_PLATFORM: "平台下发",
    SOURCE_EXPLICIT: "用户提供",
    SOURCE_SYNTHETIC: "测试号池",
}


class CredentialUnavailableError(ConfigError):
    """线上账号不可用：平台接口失败或未配置账号。

    Skill 内不再内置线上账号，所以这里**只能失败**，不能静默降级到一份
    可能已过期的硬编码密码。
    """

    code = "CREDENTIAL_UNAVAILABLE"


@dataclass(frozen=True)
class Credential:
    """登录身份。密码可缺省（验证码登录）。"""

    account: str
    password: Optional[str] = None
    country_code: Optional[str] = None
    source: str = SOURCE_EXPLICIT

    def satisfies(self, auth_method) -> bool:
        """是否满足该认证方式的最小要求（不满足则回落到 provider 默认）。"""
        if not self.account:
            return False
        return bool(self.password) if requires_password(auth_method) else True

    def to_dict(self) -> dict:
        out = {"account": self.account, "source": self.source}
        if self.password:
            out["password"] = self.password
        if self.country_code:
            out["country_code"] = self.country_code
        return out

    @classmethod
    def from_dict(cls, raw) -> Optional["Credential"]:
        """宽容解析：接受 dict / Credential / None，缺字段不报错。

        由用户或上游直接给出的 dict 没有 `source`，按「用户提供」处理；
        由 provider 生成的 dict 自带 `source`，原样保留。
        """
        if raw is None:
            return None
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, dict):
            return None
        account = str(raw.get("account") or "").strip()
        password = raw.get("password")
        country_code = raw.get("country_code")
        if not account and not password:
            return None
        return cls(
            account=account,
            password=str(password) if password else None,
            country_code=str(country_code) if country_code else None,
            source=str(raw.get("source") or SOURCE_EXPLICIT),
        )


# ═══════════════════════════════════════════════════════════════════
# 认证方式 → 是否要密码（规则表在 auth_validator，此处只读）
# ═══════════════════════════════════════════════════════════════════

def requires_password(auth_method) -> bool:
    """该认证方式是否依赖密码。未知方式按「需要密码」从严处理。"""
    from aitest.provisioning.validators.auth_validator import AUTH_METHOD_RULES
    rule = AUTH_METHOD_RULES.get(str(auth_method or "").lower())
    return True if rule is None else bool(rule["requires_password"])


# ═══════════════════════════════════════════════════════════════════
# 测试号生成（号池）：按 workspace 确定性生成
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# providers：认证方式 → 凭证来源
# ═══════════════════════════════════════════════════════════════════

def ctx_get(ctx, key, default=None):
    """兼容 dict 与 IntakeContext（后者把答案与 task_id 分开放）。"""
    if isinstance(ctx, dict):
        return ctx.get(key, default)
    getter = getattr(ctx, "get", None)
    if callable(getter):
        try:
            value = getter(key)
        except Exception:  # noqa: BLE001 — 取值失败一律回落属性访问
            value = None
        if value is not None:
            return value
    return getattr(ctx, key, default)


def _fetch_platform_credential() -> dict:
    """查询平台下发的线上账号（每次实时查，不缓存）。

    Raises:
        CredentialUnavailableError: 接口不可用 / 未返回完整账号。
    """
    from aitest.integrations.credential_api import fetch_online_credential

    try:
        remote = fetch_online_credential()
    except Exception as exc:  # noqa: BLE001 — 统一转为领域错误，便于上层提示
        raise CredentialUnavailableError(
            f"线上账号下发失败：平台接口不可用（{exc}）。\n"
            "  排查：确认可访问 YOOZ_SERVER_URL 下的 "
            "/node/api/data/monitor/test-identity/query；"
            "Skill 内不再内置线上账号，接口不可用无法降级。"
        ) from exc
    if not remote:
        raise CredentialUnavailableError(
            "线上账号下发失败：平台未返回完整身份（uid / secret / region 任一为空）。\n"
            "  修复：在 yooz-server 的 ONLINE_IDENTITY 中配置后重试。"
        )
    return remote


def fixed_credential(ctx) -> Credential:
    """线上账号：由平台下发（每次实时查，不缓存）。"""
    remote = _fetch_platform_credential()
    return Credential(
        account=remote["account"],
        password=remote["password"],
        country_code=remote["country_code"],
        source=SOURCE_PLATFORM,
    )


def synthetic_phone(ctx) -> Credential:
    """测试环境号池：按 workspace 确定性生成。"""
    return Credential(
        account=generate_test_account(ctx_get(ctx, "task_id") or ""),
        source=SOURCE_SYNTHETIC,
    )


def _no_identity(ctx) -> Optional[Credential]:
    return None


PROVIDERS = {
    "password": fixed_credential,
    "qahome": synthetic_phone,
    "noop": _no_identity,
}


# ═══════════════════════════════════════════════════════════════════
# 解析入口（全局唯一决策点）
# ═══════════════════════════════════════════════════════════════════

def resolve(auth_method, ctx=None) -> Optional[Credential]:
    """按认证方式解析凭证：显式提供优先，否则用该方式的默认 provider。

    显式要求**账号与密码成对**（凭证登录下）：只给账号不给密码的输入会被忽略并
    回落默认，绝不用内置密码去配用户的账号——那种错配只会表现为「登录失败」。
    """
    ctx = ctx if ctx is not None else {}
    method = str(auth_method or "").lower()

    provided = Credential.from_dict(ctx_get(ctx, "credential"))
    if provided is not None:
        if provided.satisfies(method):
            return provided
        if provided.account:
            print(
                "CREDENTIAL: 账号/密码未成对提供，已忽略（"
                f"auth_method={method}，使用默认来源）"
            )

    provider = PROVIDERS.get(method, fixed_credential)
    return provider(ctx)


def describe(credential) -> str:
    """人类可读的凭证摘要（账号脱敏，密码永不出现在文本里）。"""
    cred = Credential.from_dict(credential)
    if cred is None:
        return "无（免登录）"
    account = cred.account
    masked = f"{account[:4]}***{account[-3:]}" if len(account) >= 8 else "***"
    label = SOURCE_LABEL.get(cred.source, cred.source)
    extra = "，含密码" if cred.password else ""
    return f"{masked}（{label}{extra}）"
