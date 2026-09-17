#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MeituanHarmonyAppDescriptor — 美团 HarmonyOS App 描述符实现。

封装美团鸿蒙版 App 的 bundleName、EntryAbility、AppMock URI、Scheme 前缀等常量。

与 Android 版本的关键差异：
  - main_activity_class 语义变为 abilityName（如 "EntryAbility"），
    main_activity 返回 "bundleName/abilityName" 形式，供 HarmonyOps.launch_app 使用。
  - debug_overlay_prefixes 为 ArkWeb/ArkUI 组件类名，
    与 Android 视图体系类名完全不同，已按真机实测结果校准。

新增其他 App（如点评鸿蒙版）时，在同目录下新建一个文件（如 dianping.py），
并在 platform/registry.py::_APP_REGISTRY 追加一行注册，不需要改动本文件。
"""
from device_platform.base import AppDescriptor


class MeituanHarmonyAppDescriptor(AppDescriptor):
    """美团 HarmonyOS App 描述符。

    默认对接 beta 包（com.sankuai.hmeituan.beta）。若需要切换到正式包
    （com.sankuai.hmeituan），可通过子类覆盖 _PACKAGE 或后续接入
    flow-context.json 的 meta.app 变体机制。
    """

    _PACKAGE = "com.sankuai.hmeituan.beta"
    _ABILITY_NAME = "EntryAbility"

    @property
    def platform(self) -> str:
        return "harmony"

    @property
    def package_name(self) -> str:
        return self._PACKAGE

    @property
    def main_activity_class(self) -> str:
        """鸿蒙下语义为 abilityName（不含包名前缀）。"""
        return self._ABILITY_NAME

    @property
    def appmock_content_uri(self) -> str:
        """鸿蒙无 ContentProvider 体系，AppMock 走 scheme 通道，此字段保留占位。"""
        return f"content://{self._PACKAGE}.appmock/mock"

    @property
    def debug_overlay_prefixes(self) -> tuple:
        # TODO(harmony): 待开启调试面板/MRN 调试浮层后用 uitest dumpLayout
        # 实测真实 type 值后补齐，暂无可用样本。
        return ()

    @property
    def scheme_prefix(self) -> str:
        return "imeituan://www.meituan.com"

    def is_foreground(self, focus: str) -> bool:
        """鸿蒙同一 Ability 内路由切换不产生新的窗口标识，无法像 Android
        MainActivity 那样精确到具体页面，退化为"App 包名在前台即视为命中"。
        """
        return self.package_name in focus

    def foreground_confirmed_hint(self) -> str:
        return "鸿蒙无法区分具体页面，按 App 前台判定"
