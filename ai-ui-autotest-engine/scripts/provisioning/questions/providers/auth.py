#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证维度 provider —— 登录方式（派生）+ 凭证收集。

规则表以 `provisioning/validators/auth_validator.py` 为唯一事实来源；
登录方式由 `env_type` + `device_type` **派生**（`infer_auth_method`），不向用户提问。

账号（account）按登录方式取不同来源，由**两个互斥的题**承担（门控来自
`auth_validator.account_depends_on`，不硬编码 auth_method 字面量）：

  · `account`      —— 手填真实账号，仅凭证登录（线上 A）；
  · `test_account` —— 引擎按 workspace 确定性生成的测试手机号，仅验证码登录
                      （alpha/泳道 B/C）；`overridable` 允许 input-seed 指定号码。

env.account 由 `build_env_from_intake` 从二者二选一合成（互斥门控保证此刻只有一个有值）。
"""
from provisioning.questions.registry import QuestionProvider, register_provider
from provisioning.validators.auth_validator import (
    account_depends_on, generate_test_account,
)
from provisioning.validators.env_validator import infer_auth_method


@register_provider
class AuthQuestionProvider(QuestionProvider):
    name = "auth"

    def questions(self, ctx) -> list:
        return [
            {
                # 登录方式：派生（`env_type` + `device_type`）—— 等两者就绪后才求值
                "id": "auth_method", "group": "env", "order": 20,
                "prompt": "登录方式（自动推断）", "source": "derived",
                "depends_on": ["env_type", "device_type"],
                "resolve": lambda c: infer_auth_method(c.get("env_type"),
                                                       device_type=c.get("device_type")),
            },
            {
                # 手填账号：仅凭证登录（线上 A）需要用户提供真实账号
                "id": "account", "group": "identity", "order": 40,
                "prompt": "登录账号（凭证登录）",
                "input_type": "text", "required": True,
                "depends_on": account_depends_on("manual"),
            },
            {
                # 自动测试号：仅验证码登录（alpha/泳道）适用；按 workspace 确定性生成
                "id": "test_account", "group": "identity", "order": 41,
                "prompt": "测试手机号（自动生成）",
                "input_type": "text", "required": False,
                "source": "derived", "overridable": True,
                "depends_on": account_depends_on("generated"),
                "resolve": lambda c: generate_test_account(c.task_id),
                "note": "按 workspace 确定性生成；如需指定号码，可用 input-seed 覆盖 test_account",
            },
            {
                "id": "password", "group": "identity", "order": 42,
                "prompt": "该账号的登录凭证",
                "input_type": "text", "required": True, "sensitive": True,
                "depends_on": ["auth_method", "auth_method == 'password'"],
            },
        ]
