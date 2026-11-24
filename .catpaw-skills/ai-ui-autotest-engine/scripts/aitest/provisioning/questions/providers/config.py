#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置 provider —— MRN 锁包 / 场景 AppMock。

ptest **不是可选配置**：它是环境类型 P（线上泳道）的派生事实，由环境选择
一次性决定（选「线上泳道环境（ptest）」即 type=P），本 provider 不再有任何
ptest 问题（含 derived）。

MRN 锁包为 `required=False` 的提问：用户可选「跳过」
（input-answer --value __skip__），跳过时按该题 `default` 落值。`default`
会随 render 下发给 AI（不静默生效，仍会逐题提问），确保"一步一步、每题可见"。

锁包目标由用户在提问时直接给出（不提供则只声明包名、不锁版本）。

场景 AppMock **不在本 provider 采集**：它是 **case 级**配置（`cases[].mock_ids` /
`env.mock_ids`，由 `flow-init` 原样透传），与批级的锁包正交，因此不在此声明问题。
"""
from aitest.provisioning.questions.registry import QuestionProvider, register_provider


@register_provider
class ConfigQuestionProvider(QuestionProvider):
    name = "config"

    def questions(self, ctx) -> list:
        prompt = (
            "锁定 MRN bundle JSON 数组（如 "
            "[{\"name\":\"@meishi/xxx\",\"version\":\"1.0.0\"}]；"
            "version 可省略=仅声明目标不锁包；无需请跳过）"
        )
        return [
            {
                "id": "bundle_lock", "group": "config", "order": 51,
                "prompt": prompt,
                "input_type": "text", "required": False, "default": [],
            },
        ]
