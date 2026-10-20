#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QuestionProvider 注册表 —— 信息收集的唯一扩展点。

每个 provider 只声明本域问题（`questions`）+ 派生值（`derive`）；
驱动层（driver）零改动。

  · 新增一个问题 = provider 加一条声明
  · 新增一个信息域 = 注册一个 provider
"""
import importlib
import importlib.util

from abc import ABC

from shared.errors import ContractError


class QuestionProvider(ABC):
    """一个信息域的声明式问题集 + 派生值计算。"""

    name: str = ""
    # 静态声明本 provider 可能产出的派生键（如 "device_type"）。
    # 供 depends_on 引用校验使用：派生键是动态的（输入未就绪时为空），
    # 必须静态声明才能稳定校验引用完整性。
    derived_keys: tuple = ()

    def questions(self, ctx) -> list:
        """声明本域问题（list[dict]，见 schema）。"""
        return []

    def derive(self, ctx) -> dict:
        """计算派生/提取值（{question_id: value}），供驱动回填。"""
        return {}


_REGISTRY = {}
_LOADED = False


def register_provider(cls):
    """类装饰器：注册 provider（name 必须非空且唯一）。"""
    inst = cls()
    if not getattr(inst, "name", ""):
        raise ContractError(f"provider {cls.__name__} 缺少 name")
    if inst.name in _REGISTRY:
        raise ContractError(f"provider 名称重复：{inst.name}")
    _REGISTRY[inst.name] = inst
    return cls


def ensure_providers_loaded():
    """加载内置 provider 包（Q1 迁移前允许缺席，框架照常可用）。"""
    global _LOADED
    if _LOADED:
        return
    if importlib.util.find_spec("provisioning.questions.providers") is not None:
        importlib.import_module("provisioning.questions.providers")
    _LOADED = True


def all_providers() -> list:
    ensure_providers_loaded()
    return list(_REGISTRY.values())


def all_questions(ctx) -> list:
    questions = []
    for provider in all_providers():
        questions.extend(provider.questions(ctx) or [])
    return questions


def all_derived_keys() -> set:
    """所有 provider 静态声明的派生键（供 depends_on 引用校验）。"""
    keys = set()
    for provider in all_providers():
        keys.update(getattr(provider, "derived_keys", ()) or ())
    return keys
