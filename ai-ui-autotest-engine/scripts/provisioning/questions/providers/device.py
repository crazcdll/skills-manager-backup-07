#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备维度 provider —— 设备组合（device_type × platform × app）选择。

规则表仍以 `provisioning/validators/device_validator.py` 为唯一事实来源；
本 provider 只负责"声明问题 + 派生三维值"。
"""
from provisioning.questions.registry import QuestionProvider, register_provider
from provisioning.validators.device_validator import (
    device_combo_options, split_device_combo,
)


@register_provider
class DeviceQuestionProvider(QuestionProvider):
    name = "device"
    derived_keys = ("device_type", "platform", "app")

    def questions(self, ctx) -> list:
        options = device_combo_options()
        return [{
            "id": "device_combo",
            "group": "device",
            "order": 10,
            "prompt": "选择设备组合（设备接入方式 × 平台 × App）",
            "input_type": "single",
            "required": True,
            "options": options,
            "default": options[0]["value"] if options else None,
        }]

    def derive(self, ctx) -> dict:
        combo = ctx.get("device_combo")
        if not combo:
            return {}
        return split_device_combo(combo)
