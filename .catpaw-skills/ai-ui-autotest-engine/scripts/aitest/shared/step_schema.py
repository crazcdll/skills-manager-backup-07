#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤模型的共享语义字段 —— 跨「编译层」与「执行层」的唯一定义。

为什么要独立成模块
──────────────────
步骤模型里有少量字段不属于某个引擎内部约定，而是**业务语义**，需要在三处保持一致：

  ① 编译层（flow_json：业务 steps.json → CASES）—— 生成/规范化该字段；
  ② 装载层（steps_builder：CASES → steps_json → flow-context）—— 校验并落盘；
  ③ 执行层（steps/pipeline：跑步骤、给结论）—— 读到它就要改变收口语义。

若三处各写一份字面量（"landing"）和判断，改一处漏一处就会出现
「编译期认为是落地步骤、运行期不认」的静默不一致。因此常量 + 判定 + 校验
集中在这里，两侧只调用，不重复实现。

当前唯一的语义角色
──────────────────
`landing` —— 落地入口步骤（首步 open-url）。它失败代表「用例前置不成立」
（商品下架 / 环境 URL 失效 / 登录态失效），不是用例本身的业务缺陷。

本模块只负责**模型字段的合法性**（role 取值、位置约束）；落地角色的
归一化形状、必填 hook、收口策略与提示文案统一在 `shared/landing.py`，
避免同一语义散落到多层。
"""

from __future__ import annotations

# 落地入口步骤的角色标记。只在首步、且 action=open-url 时合法。
LANDING_ROLE = "landing"

# 允许出现在步骤模型里的 role 取值（None 表示无角色）。
VALID_ROLES = frozenset({LANDING_ROLE})


def normalize_role(value) -> str | None:
    """把 role 规范化为「去空白的字符串或 None」。"""
    if value is None:
        return None
    role = str(value).strip()
    return role or None


def role_error(role, *, index: int, kind: str, action) -> str | None:
    """校验 role 与步骤位置的组合是否合法，返回错误文案（合法返回 None）。

    调用方决定错误的表达方式：编译层直接 raise，装载层收集进 errors 列表，
    但**判定规则只有这一份**。
    """
    normalized = normalize_role(role)
    if normalized is None:
        return None
    if normalized not in VALID_ROLES:
        return f"role 非法: {normalized!r}（仅支持 {', '.join(sorted(VALID_ROLES))}）"
    if kind != "ui" or str(action or "").strip() != "open-url":
        return f"role={normalized} 只能用于 action=open-url 的 UI 步骤"
    if index != 0:
        return f"role={normalized} 只能用于首步（index=0），当前 index={index}"
    return None

