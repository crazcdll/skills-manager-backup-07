#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认证维度 provider —— 登录方式（派生）+ 凭证（派生）。

登录方式由 `env_type` + `device_type` **派生**（`infer_auth_method`），不向用户提问。

凭证只有**一个问题**：`credential`。
  · `source: derived` —— 默认不问，由 `provisioning/credentials.py` 按认证方式
    解析（线上 → 内置固定账号；测试 → 号池确定性生成）；
  · `overridable: True` —— 用户想用别的号时，用 input-seed 覆盖即可；
  · 只给账号不给密码视为无效输入，回落默认来源（不会拼凑内置密码）。

凭证以结构化对象流转（account / password / country_code / source），
env 里只保留 `credential` 一个字段。
"""
from aitest.provisioning.credentials import resolve
from aitest.provisioning.questions.registry import QuestionProvider, register_provider
from aitest.provisioning.validators.env_validator import infer_auth_method


def _resolve_credential(ctx):
    """解析当前认证方式下的凭证；无身份需求（noop）时返回 None。"""
    cred = resolve(ctx.get("auth_method"), ctx)
    return cred.to_dict() if cred else None


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
                # 凭证：默认不问；线上由平台下发，测试环境用号池
                "id": "credential", "group": "identity", "order": 40,
                "prompt": "登录凭证（默认使用平台下发账号 / 测试号池）",
                "source": "derived", "overridable": True,
                "required": False,
                "depends_on": ["auth_method", "auth_method != 'noop'"],
                "resolve": _resolve_credential,
                "note": "默认不问；如需指定账号，用 input-seed 覆盖 credential "
                        "（凭证登录需同时给 account / password / country_code）",
            },
        ]
