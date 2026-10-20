#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内置 QuestionProvider —— 导入即注册（`@register_provider`）。

一个信息域一个 provider：device / env / auth / config / placeholder。
新增信息域 = 新增本目录下的一个模块并在此 import；驱动层零改动。
"""
from provisioning.questions.providers import (  # noqa: F401
    auth,
    config,
    device,
    env,
    placeholder,
)
