#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MeituanAppDescriptor — 美团 Android App 描述符实现。

封装美团 App 的包名、首页 Activity、AppMock URI、调试控件类名、Scheme 前缀等常量。

新增其他 App（如点评）时，在同目录下新建一个文件（如 dianping.py）实现同样的
AppDescriptor 接口，并在 platform/registry.py::_APP_REGISTRY 追加一行注册，
不需要改动本文件或 context/__init__.py。
"""
from device_platform.base import AppDescriptor


class MeituanAppDescriptor(AppDescriptor):
    """美团 App 描述符。"""

    _PACKAGE = "com.sankuai.meituan"
    _MAIN_ACTIVITY_CLASS = "com.meituan.android.pt.homepage.activity.MainActivity"

    @property
    def package_name(self) -> str:
        return self._PACKAGE

    @property
    def main_activity_class(self) -> str:
        return self._MAIN_ACTIVITY_CLASS

    @property
    def appmock_content_uri(self) -> str:
        return f"content://{self._PACKAGE}.appmock/mock"

    @property
    def debug_overlay_prefixes(self) -> tuple:
        return (
            "com.meituan.android.mrn.debug.n$c",
            f"{self._PACKAGE}.kernel.net.utils.b$a",
            "com.meituan.android.recce.debug.widget",
        )

    @property
    def scheme_prefix(self) -> str:
        return "imeituan://www.meituan.com"

    @property
    def uninspectable_activities(self) -> tuple:
        """不支持 imeituan inspect-tree 的 Activity 标识列表（小写），降级走 uiautomator。
        
        包括：首页 MainActivity（未集成 dump 能力）、升级弹窗 UpgradeDialogActivity（短期弹窗，无 dump 能力）。
        """
        return ("mainactivity", "upgradedialogactivity")
