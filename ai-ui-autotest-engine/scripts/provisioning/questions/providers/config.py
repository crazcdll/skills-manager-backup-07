#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可选配置 provider —— ptest / MRN 锁包 / 场景 AppMock。

ptest / MRN 锁包为 `required=False` 的提问：用户可选「跳过」
（input-answer --value __skip__），跳过时按该题 `default` 落值。`default`
会随 render 下发给 AI（不静默生效，仍会逐题提问），确保"一步一步、每题可见"。

ptest 的适用环境由 `validators/env_validator.ENV_CAPABILITIES` 派生（仅线上 A），
采集层不再硬编码条件，与校验层共用同一张矩阵。

锁包目标从本 workspace 的 Flow .md 提取并**前置到提问**（解析以 config_validator
为唯一事实来源）：Flow 「可测性环境」表声明了什么，就在题面里原样露出。

场景 AppMock **不在本 provider 采集**：它是 **case 级**配置（每个 Flow 的「可测性环境」
AppMock 行 → 对应 case 的 `mock_ids`，由 flow-init 解析），与批级的 ptest / 锁包
正交，因此不在此声明问题。
"""
import os

from provisioning.questions.registry import QuestionProvider, register_provider
from provisioning.validators.config_validator import extract_flow_bundle_names
from provisioning.validators.env_validator import capability_depends_on
from shared.paths import flows_dir


def _flow_bundle_names() -> list:
    names = []
    directory = flows_dir()
    if os.path.isdir(directory):
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".md"):
                continue
            for name in extract_flow_bundle_names(os.path.join(directory, fname)):
                if name not in names:
                    names.append(name)
    return names


@register_provider
class ConfigQuestionProvider(QuestionProvider):
    name = "config"

    def questions(self, ctx) -> list:
        names = _flow_bundle_names()
        prompt = "是否需要锁定 MRN bundle？（仅声明包名不锁包；提供版本才会锁包；无需请跳过）"
        if names:
            prompt = (
                f"是否需要锁定 MRN bundle？Flow 声明的目标包: {', '.join(names)}"
                "（仅声明包名不锁包；提供版本才会锁包；无需请跳过）"
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
                "note": f"Flow 声明的目标锁包: {', '.join(names)}" if names else None,
            },
        ]
