#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""信息收集框架（Question Framework）。

声明式问题（Question Schema）+ Provider 注册表 + 统一驱动
（`input-next` / `input-answer` / `input-status`）。

定位：**收集由子 Agent 自己完成**（单 Agent 与多子 Agent 同构）；
Agent 层只提供原始数据。结果落 **workspace 级** `intake.json`（子 Agent 私有）。
"""
from provisioning.questions.driver import answer, next_question, schema_view, seed, status
from provisioning.questions.registry import (
    QuestionProvider, all_providers, all_questions, register_provider,
)
from provisioning.questions.schema import (
    normalize_question, public_view, validate_questions,
)
from shared.intake import IntakeContext

__all__ = [
    "IntakeContext",
    "QuestionProvider", "register_provider", "all_providers", "all_questions",
    "next_question", "answer", "status", "seed", "schema_view",
    "normalize_question", "public_view", "validate_questions",
]
