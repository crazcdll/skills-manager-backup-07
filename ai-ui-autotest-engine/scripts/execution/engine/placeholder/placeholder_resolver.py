#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""占位符提取与替换（steps-input.json 边界层）。

职责收敛（唯一实现，禁止再各自解析）：
  · 提取：`extract_placeholders_from_steps` —— 供 flow-init 做占位符门禁
  · 替换：`resolve_placeholders` —— flow-init 的唯一替换入口，委托
          `shared.placeholders.substitute`（`{T+N}` → 日期，`{xxx}` → intake 值）

文法与替换实现统一于 `shared.placeholders`（全仓库唯一事实来源）。
"""
from shared.placeholders import (
    collect_case_placeholder_text,
    extract_placeholders,
    substitute,
)


def extract_placeholders_from_steps(steps_input: dict) -> dict:
    """从 steps-input.json 提取所有 {xxx} 占位符。

    返回: {case_id: [placeholder_name, ...]}
    """
    result = {}
    for i, case in enumerate(steps_input.get("cases", []) or []):
        case_id = case.get("case_id", f"case-{i+1:02d}")
        placeholders = extract_placeholders(collect_case_placeholder_text(case))
        if placeholders:
            result[case_id] = placeholders
    return result


def resolve_placeholders(obj, answers: dict):
    """统一替换占位符（flow-init 唯一替换入口）。

    `{T+N}` / `{T+N:format}` → 自动计算日期；`{xxx}` → intake 中的值。
    """
    return substitute(obj, answers, with_dates=True)
