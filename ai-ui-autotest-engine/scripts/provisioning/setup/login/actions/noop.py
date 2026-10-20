#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""免登录认证动作（env.type=D，或 device_type=local 被强制）。

语义：**不推送任何 scheme、不重启 App**，
尊重设备当前真实状态；登录态校验交给 L4 探针（编排层负责）。
"""
from provisioning.setup.login.actions import AuthAction
from provisioning.setup.login.policy import AuthOutcome


class NoopAuthAction(AuthAction):
    method = "noop"

    def perform(self, plan, ctx) -> AuthOutcome:
        return AuthOutcome(
            ok=True,
            detail="noop：不推送 scheme、不重启 App（假定设备已登录）",
        )


__all__ = ["NoopAuthAction"]
