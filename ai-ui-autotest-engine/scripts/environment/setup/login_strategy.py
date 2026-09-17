#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录策略模式 — 按 App 分派的统一登录接口。

策略构建按 App 注册（APP_LOGIN_STRATEGY_BUILDERS），不同 App 的登录页交互、可测性通道
均可能不同，禁止跨 App 复用同一套策略实现。

美团（meituan）环境类型 → 策略映射：
  A (online)   → PasswordLoginStrategy
  B (swimline) → QahomeLoginStrategy (with swimline setup)
  C (alpha)    → QahomeLoginStrategy (with alpha env setup)
  D (已登录)    → NoopLoginStrategy（仅做登录态校验；device_type=local 会被
                env_validator 反向约束为只能选 D）

未在 APP_LOGIN_STRATEGY_BUILDERS 中注册的 App，构建时直接报错。
"""
import re
import json
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional

from environment.setup.login_password import password_login
from environment.setup.login_qahome import qahome_login
from environment.setup.login_state import check_login_state
from environment.setup.location import normalize_location
from environment.setup.app_lifecycle import restart_app_after_env_switch
from mock.appmock_device import appmock_enable
from mock.appmock_swimlane import (
    appmock_env_set, appmock_swimline_list, appmock_swimline_add,
    appmock_swimline_switch, appmock_ensure_url_mappings,
)

class LoginStrategy(ABC):
    """登录策略抽象基类。

    三阶段契约：
      1. validate()  — 前置条件校验
      2. execute()   — 执行登录流程
      3. verify()    — 验证登录状态
    """

    def __init__(self, account: str, password: Optional[str] = None,
                 location: Optional[str] = None, **kwargs):
        self.account = account
        self.password = password
        self.location = location
        self.extra = kwargs

    @abstractmethod
    def validate(self) -> Tuple[bool, str]:
        """前置条件校验。"""
        pass

    @abstractmethod
    def execute(self, mis: str) -> Tuple[bool, Optional[str], List[dict]]:
        """执行登录流程。

        Args:
            mis: 用户 MIS 号

        Returns:
            (ok, screenshot_path, extra_configs)
        """
        pass

    @abstractmethod
    def verify(self) -> Tuple[bool, str]:
        """验证登录状态。"""
        pass

    def get_auth_method(self) -> str:
        return "unknown"

class PasswordLoginStrategy(LoginStrategy):
    """凭证登录策略（A: online）。"""

    def __init__(self, account: str, password: Optional[str] = None,
                 location: Optional[str] = None, **kwargs):
        super().__init__(account, password, location, **kwargs)

    def validate(self) -> Tuple[bool, str]:
        if not self.account:
            return False, "线上环境必须提供 account"
        if not self.password:
            return False, "线上环境凭证登录必须提供 password"
        if "{" in self.account or "{" in (self.password or ""):
            return False, "account/password 包含 {占位符}，请使用 Flow 测试数据参考中的真实值"
        return True, ""

    def execute(self, mis: str) -> Tuple[bool, Optional[str], List[dict]]:
        loc = normalize_location(self.location)
        ok, shot = password_login(
            self.account, self.password,
            location=loc, signin_env="online",
        )

        if not ok:
            print("[login-online] ❌ 凭证登录执行失败")
            return False, None, []

        print("[login-online] ✅ 凭证登录 scheme 推送完成")
        return True, shot, []

    def verify(self) -> Tuple[bool, str]:
        """凭证登录验证：截图已在 execute 中完成，由外部 AI 读图确认。"""
        return True, "[NEEDS_VISUAL_CHECK]"

    def get_auth_method(self) -> str:
        return "password"

class QahomeLoginStrategy(LoginStrategy):
    """QAHome 验证码登录策略（B: swimline, C: alpha）。"""

    def __init__(self, account: Optional[str] = None,
                 env_type: str = "alpha",
                 lane_name: Optional[str] = None,
                 url_pattern: Optional[str] = None,
                 url_mapping: Optional[str] = None,
                 **kwargs):
        super().__init__(account, None, None, **kwargs)
        self.env_type = env_type
        self.lane_name = lane_name
        self.url_pattern = url_pattern
        self.url_mapping = url_mapping

    def validate(self) -> Tuple[bool, str]:
        """校验 account 是否合法且不含占位符。"""
        if not self.account:
            return False, "QAHome 登录必须提供 account"
        if "{" in self.account:
            return False, f"account 含占位符 {self.account!r}，请用 Flow 测试数据参考中的真实值 save-answers 后重试"
        if not re.match(r'^1[3-9]\d{9}$', self.account):
            return False, f"account 不是有效手机号: {self.account!r}"
        return True, ""

    def execute(self, mis: str) -> Tuple[bool, Optional[str], List[dict]]:
        if self.env_type == "alpha":
            appmock_env_set("alpha", mis=mis)
            print("[login-alpha] ✅ alpha 环境已切换")
            restart_app_after_env_switch(label="alpha")
            # 冷重启后 AppMock 代理可能丢失，重新启用
            appmock_enable(mis)

        elif self.env_type == "swimline":
            if not self._setup_swimline(mis):
                return False, None, []

        ok = qahome_login(self.account, mock_enabled=True)
        if not ok:
            # 验证码获取失败：前置条件（AppMock 启用/环境切换）可能未生效，
            # 完整重试一次：重新启用 SDK + 切环境 + 冷重启后重新登录
            print(f"[login-{self.env_type}] 🔄 登录失败，执行完整恢复后重试...")
            ok = self._retry_with_full_recovery(mis)
            if not ok:
                print(f"[login-{self.env_type}] ❌ 重试后仍失败，判定登录失败")
                return False, None, []

        if self.env_type == "swimline" and not self.lane_name and self.url_mapping:
            if not self._setup_url_mappings(mis):
                return False, None, []

        print(f"[login-{self.env_type}] ✅ 环境登录完成")
        return True, None, []

    def _retry_with_full_recovery(self, mis: str) -> bool:
        """登录失败后的分层重试。

        分两层，每层失败才进入下一层：
          1. 轻量重试：不重启 App，直接重新导航登录页重试（解决偶发 UI 定位/点击失败）
          2. 完整恢复：冷重启一次 + 环境恢复后重试（解决 AppMock/网络栈未生效）

        ⚠️ 两个问题点（已修复）：
          - 旧版 _setup_swimline 内含 restart_app_after_env_switch，重试中调用
            会导致级联冷重启（sdk_enable_and_restart 重启一次 + _setup_swimline 再重启一次）
          - 完整恢复时只做一次冷重启，不再重复切环境（泳道/域名映射在上一次 execute 已配置好）
        """
        from environment.setup.sdk_enable import sdk_enable_and_restart

        # 尝试 1：轻量重试 —— 不重启，直接重新导航登录页
        print(f"[login-{self.env_type}] 🔄 轻量重试：直接重新导航登录页...")
        ok = qahome_login(self.account, mock_enabled=True)
        if ok:
            print(f"[login-{self.env_type}] ✅ 轻量重试登录成功")
            return True

        # 尝试 2：完整恢复 —— 一次冷重启 + 环境恢复
        print(f"[login-{self.env_type}] 🔄 轻量重试失败，执行完整恢复（冷重启 + 环境恢复）...")

        # 2a. 重新启用 AppMock SDK（含一次冷重启）
        if not sdk_enable_and_restart(mis):
            print(f"[login-{self.env_type}] ❌ 完整恢复时 AppMock SDK 启用失败")
            return False

        # 2b. 泳道环境需重新激活域名映射（不重复 _setup_swimline，
        #     因为泳道规则和域名映射在首次 execute 已配置，只需重启后重新激活）
        if self.env_type == "swimline" and self.url_mapping:
            print(f"[login-{self.env_type}] 🔄 恢复步骤: 重新激活域名映射...")
            mappings = (json.loads(self.url_mapping) if isinstance(self.url_mapping, str)
                        else self.url_mapping)
            appmock_ensure_url_mappings(mappings, mis=mis)
            restart_app_after_env_switch(label="url-mapping-recovery")

        # 2c. 重新登录
        print(f"[login-{self.env_type}] 🔄 恢复步骤: 重新登录...")
        ok = qahome_login(self.account, mock_enabled=True)
        if ok:
            print(f"[login-{self.env_type}] ✅ 完整恢复后登录成功")
        return ok

    def _setup_swimline(self, mis: str) -> bool:
        """泳道环境配置（登录前）。"""
        if not self.lane_name:
            appmock_env_set("alpha", mis=mis)
            print("[login-swimline] 纯域名映射模式：已切换 alpha 测试环境")
            restart_app_after_env_switch(label="swimline")
        else:
            url_pat = self.url_pattern or "/*"
            rule_id = None

            raw = appmock_swimline_list(mis=mis)
            items = raw.get("items", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_url = item.get("url", "") or item.get("urlPattern", "")
                if item_url == url_pat:
                    rule_id = str(item.get("id") or item.get("ruleId"))
                    print(f"[login-swimline] 复用已有泳道规则 ruleId={rule_id}")
                    break

            if not rule_id:
                result = appmock_swimline_add(url_pat, self.lane_name, mis=mis)
                rule_id = str(result.get("id") or result.get("ruleId") or "")
                if not rule_id and result.get("raw"):
                    m = re.search(r'id[=:]\s*(\d+)', result["raw"])
                    if m:
                        rule_id = m.group(1)
                if rule_id:
                    print(f"[login-swimline] 泳道已创建 ruleId={rule_id}")
                else:
                    print(f"[login-swimline] ⚠️ 泳道创建失败: {result}")
                    return False

            switch_ok = appmock_swimline_switch(rule_id, mis=mis)
            if not switch_ok:
                print(f"[login-swimline] ⚠️ 泳道切换失败 ruleId={rule_id}")
                return False
            print(f"[login-swimline] 泳道已切换 ruleId={rule_id}")

            if self.url_mapping:
                mappings = json.loads(self.url_mapping) if isinstance(self.url_mapping, str) else self.url_mapping
                results = appmock_ensure_url_mappings(mappings, mis=mis)
                print(f"[login-swimline] 域名映射已配置 ({len(results)} 条)")

            restart_app_after_env_switch(label="swimline")
        return True

    def _setup_url_mappings(self, mis: str) -> bool:
        """登录后激活域名映射 + 冷重启。"""
        if self.url_mapping:
            mappings = json.loads(self.url_mapping) if isinstance(self.url_mapping, str) else self.url_mapping
            results = appmock_ensure_url_mappings(mappings, mis=mis)
            print(f"[login-swimline] 域名映射已配置 ({len(results)} 条)")
        restart_app_after_env_switch(label="url-mapping")
        return True

    def verify(self) -> Tuple[bool, str]:
        ok, detail = check_login_state()
        return ok, detail

    def get_auth_method(self) -> str:
        return "qahome"

class NoopLoginStrategy(LoginStrategy):
    """默认已登录策略（env.type == D）：假定用户已自行登录，不执行任何登录动作，
    仅做轻量登录态校验（快速失败，避免几十步之后才暴露环境问题）。
    device_type=local 会被 env_validator 反向约束为只能选 D（详见 env_validator.py）。
    """

    def __init__(self, **kwargs):
        super().__init__(account=None, password=None, location=None, **kwargs)

    def validate(self) -> Tuple[bool, str]:
        return True, ""

    def execute(self, mis: str) -> Tuple[bool, Optional[str], List[dict]]:
        # 不推送任何 scheme，不重启 App —— 尊重用户当前真实状态
        return True, None, []

    def verify(self) -> Tuple[bool, str]:
        ok, detail = check_login_state()
        if not ok:
            return False, f"{detail}（env.type=D 需要用户预先手动登录线上账号）"
        return True, detail

    def get_auth_method(self) -> str:
        return "noop_assume_logged_in"

def _build_meituan_strategy(env_config: dict, env_type: str) -> LoginStrategy:
    """美团 App 的登录策略构建。

    根据 auth_method 字段选择策略实现，env_type 用于确定环境切换目标。
    auth_method 取值: password / qahome / noop
    env_type 取值: A(online) / B(swimline) / C(alpha) / D(noop)
    """
    account = env_config.get("account")
    password = env_config.get("_password_raw")
    location = env_config.get("location")
    auth_method = env_config.get("auth_method")

    if auth_method == "noop" or env_type == "D":
        return NoopLoginStrategy()

    if auth_method == "password":
        return PasswordLoginStrategy(
            account=account, password=password,
            location=location,
        )
    elif auth_method == "qahome":
        if env_type == "B":
            swimline = env_config.get("swimline") or {}
            lane_name = swimline.get("lane_name") if isinstance(swimline, dict) else None
            url_pattern = swimline.get("url_pattern") if isinstance(swimline, dict) else None
            url_mappings = env_config.get("url_mappings") or []

            # 泳道和域名映射都为空 → 跳过泳道配置，按 alpha 环境处理
            has_swim_config = bool(lane_name and lane_name.strip()) or bool(url_mappings)
            if not has_swim_config:
                return QahomeLoginStrategy(
                    account=account, env_type="alpha"
                )
            return QahomeLoginStrategy(
                account=account, env_type="swimline",
                lane_name=lane_name,
                url_pattern=url_pattern,
                url_mapping=url_mappings,
            )
        elif env_type == "C":
            return QahomeLoginStrategy(
                account=account, env_type="alpha"
            )
        else:
            # 默认使用 alpha 环境
            return QahomeLoginStrategy(
                account=account, env_type="alpha"
            )
    else:
        raise ValueError(f"未知认证方式: {auth_method}，环境类型: {env_type}")

# App → 策略构建函数注册表。唯一事实来源，新增 App 支持时在此注册一个完整的
# 构建函数（签名: (env_config, env_type) -> LoginStrategy），不得复用其他 App 的实现。
APP_LOGIN_STRATEGY_BUILDERS = {
    "meituan": _build_meituan_strategy,
    # "dianping": _build_dianping_strategy,  # 登录页交互/可测性通道待调研，未注册前禁止使用
}

def build_login_strategy(env_config: dict, app: str = "meituan") -> LoginStrategy:
    """根据 App + 环境配置构建登录策略。

    env.type 枚举 A/B/C/D 由用户在 steps-input 中显式选择，与 device_type
    完全解耦（任何设备类型都可使用）；具体策略实现按 app 分派，不同 App 的
    登录页交互、可测性通道、认证方式集合均可能不同，不跨 App 复用实现。
    """
    builder = APP_LOGIN_STRATEGY_BUILDERS.get(app)
    if builder is None:
        supported = "、".join(APP_LOGIN_STRATEGY_BUILDERS.keys())
        raise ValueError(
            f"App「{app}」尚未注册登录策略（APP_LOGIN_STRATEGY_BUILDERS 中无对应条目）。"
            f"当前仅支持: {supported}。"
            f"如需支持新 App，需先调研其登录页交互/可测性通道，实现对应的构建函数并注册。"
        )
    env_type = env_config.get("type", "").upper()
    return builder(env_config, env_type)
