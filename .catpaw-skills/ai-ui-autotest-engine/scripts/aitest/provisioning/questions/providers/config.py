#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置 provider —— ptest / MRN 锁包 / 场景 AppMock。

ptest / MRN 锁包为 `required=False` 的提问：用户可选「跳过」
（input-answer --value __skip__），跳过时按该题 `default` 落值。`default`
会随 render 下发给 AI（不静默生效，仍会逐题提问），确保"一步一步、每题可见"。

ptest 的适用环境由 `validators/env_validator.ENV_CAPABILITIES` 派生（仅线上 A），
采集层不再硬编码条件，与校验层共用同一张矩阵。

锁包目标由用户在提问时直接给出（不提供则只声明包名、不锁版本）。

场景 AppMock **不在本 provider 采集**：它是 **case 级**配置（`cases[].mock_ids` /
`env.mock_ids`，由 `flow-init` 原样透传），与批级的 ptest / 锁包正交，因此不在此声明问题。
"""
from aitest.provisioning.questions.registry import QuestionProvider, register_provider
from aitest.provisioning.validators.env_validator import capability_depends_on


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
                "id": "ptest", "group": "config", "order": 50,
                "prompt": "是否开启 ptest（注入 isPtest/isGreyTest/isDevBundle 参数）？",
                "input_type": "single", "required": False, "default": False,
                # 仅线上(A)适用：条件由环境能力矩阵派生，不手写
                "depends_on": capability_depends_on("ptest"),
                "options": [
                    {"value": True, "label": "开启 ptest（线上环境 + partMock 注入）"},
                    {"value": False, "label": "不开（纯线上）"},
                ],
            },
            {
                "id": "bundle_lock", "group": "config", "order": 51,
                "prompt": prompt,
                "input_type": "text", "required": False, "default": [],
            },
        ]
