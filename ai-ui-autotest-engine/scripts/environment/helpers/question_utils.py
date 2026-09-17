#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AskQuestion 契约构造的共享工具。

env_validator.py（阶段③认证维度）与 device_validator.py（阶段①设备维度）
的 get_required_fields()/get_device_required_fields() 共用同一套
known_values 预填规则，抽到本模块避免两处重复实现。
"""


def _coerce_value(value, valid_values):
    """尝试将 value 类型转换为与 valid_values 中的类型匹配。

    主要解决 --answers 中的 JSON 基本类型与 options 声明类型不一致的问题，
    例如 JSON 字符串 "true" 与 Python 布尔值 True 不匹配。
    """
    if not valid_values:
        return value
    sample = next(iter(valid_values))
    target_type = type(sample)

    if target_type is bool:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "1", "yes"):
                return True
            if lowered in ("false", "0", "no"):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
    elif target_type is int:
        if isinstance(value, str):
            try:
                return int(value.strip())
            except (ValueError, TypeError):
                pass
        if isinstance(value, float):
            return int(value) if value == int(value) else value
    elif target_type is float:
        if isinstance(value, str):
            try:
                return float(value.strip())
            except (ValueError, TypeError):
                pass
        if isinstance(value, int):
            return float(value)

    return value


# 手动输入信号值：__manual_input__ 表示用户选择手动输入，__skip__ 表示跳过此字段。
# 与 allow_manual_input=True 配合使用，不被视为"已解析"。
_MANUAL_INPUT_SIGNALS = {"__manual_input__", "__skip__"}


def apply_known_value(question, known_values, allow_manual_input=False):
    """若调用方已从用户原始提示词中识别出该字段的值，则回填为 default 并标记 resolved。

    只回填 default/resolved/skip_reason，不改变 options（可选值集合仍由脚本固定声明，
    调用方无法通过 known_values 绕过白名单）。未命中或值非法时原样返回。
    自动做类型容错，例如 JSON 字符串 "true" → Python 布尔值 True。

    allow_manual_input=True 时，__manual_input__ 和 __skip__ 不被视为
    已解析的值——即使 known_values 中包含它们，也不会标记 resolved。
    这允许 AI 将手动输入字段作为 AskQuestion 选择题展示，用户选择
    "手动输入"后，AI 再在聊天中询问具体值，然后通过 save-answers 保存真实值。
    """
    if not known_values or question["id"] not in known_values:
        return question
    value = known_values[question["id"]]

    # allow_manual_input=True 时，__manual_input__/__skip__ 不视为已解析
    if allow_manual_input and value in _MANUAL_INPUT_SIGNALS:
        return question

    # allow_manual_input=True 且为真实值（非信号值）时，跳过 options 白名单校验。
    # 因为 mixed 类型 input 的 options 只是 UI 导航选项（手动输入/跳过），
    # 不是合法的值范围约束，真实值不在白名单中不应阻塞 resolve。
    if allow_manual_input:
        pass  # 跳过 options 校验，直接标记 resolved
    else:
        options = question.get("options")
        if options is not None:
            try:
                valid_values = {o["value"] for o in options if not o.get("disabled")}
            except TypeError:
                # options 包含不可哈希值（如 list），无法构建 set，跳过校验
                return question
            try:
                if value not in valid_values:
                    coerced = _coerce_value(value, valid_values)
                    try:
                        if coerced not in valid_values:
                            return question
                    except TypeError:
                        return question
                    value = coerced
            except TypeError:
                # value 是不可哈希类型（如 list），无法与 options set 比较
                # 保持 question 原样 unresolved，由 AI 后续通过 AskQuestion 处理
                return question
    question = dict(question)
    question["default"] = value
    question["resolved"] = True
    question["skip_reason"] = f"已从用户提示词中识别: {value}"
    return question