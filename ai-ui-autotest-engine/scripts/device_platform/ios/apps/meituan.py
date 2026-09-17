#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MeituanIOSAppDescriptor — 美团 iOS App 描述符。"""
from device_platform.base import AppDescriptor


class MeituanIOSAppDescriptor(AppDescriptor):
    """美团 iOS 模拟器/设备 App 描述符。"""

    @property
    def platform(self) -> str:
        return "ios"

    @property
    def package_name(self) -> str:
        """App bundle ID。本地模拟器默认使用 com.meituan.imeituan。"""
        return "com.meituan.imeituan"

    @property
    def main_activity_class(self) -> str:
        """iOS 无 Activity 概念，返回空字符串。"""
        return ""

    @property
    def main_activity(self) -> str:
        return self.package_name

    @property
    def appmock_content_uri(self) -> str:
        return ""

    @property
    def debug_overlay_prefixes(self) -> tuple:
        """调试浮层/按钮类名前缀。"""
        return ("mrn_dev_kit", "NVDebug")

    @property
    def scheme_prefix(self) -> str:
        return "imeituan://www.meituan.com"

    def is_foreground(self, focus: str) -> bool:
        """iOS 判定当前 App 是否在前台（通过 bundleId 匹配）。"""
        return self.package_name in focus.lower() or "imeituan" in focus.lower()
