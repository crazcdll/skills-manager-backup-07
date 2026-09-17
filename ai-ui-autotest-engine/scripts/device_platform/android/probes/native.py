#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NativeProbe — Android View 树渲染层探针。

包装 screen_state.inspect_tree 的采集与匹配逻辑，覆盖 Android 原生控件、
MRN(React Native)、Recce 渲染的内容。WebView 内部 DOM 不在本探针覆盖范围。
"""
from device_platform.base import RendererProbe


class NativeProbe(RendererProbe):
    """基于 imeituan inspect-tree 的 native 视图树探针。"""

    @property
    def probe_name(self) -> str:
        return "native"

    def available(self) -> bool:
        return True

    def find_text(self, text: str) -> bool:
        from screen_state.inspect_tree import native_has_text
        return native_has_text(text)

    def find_center(self, text: str) -> tuple:
        from screen_state.inspect_tree import native_find_center
        return native_find_center(text)

    def list_texts(self) -> list:
        from screen_state.inspect_tree import native_list_texts
        return native_list_texts()