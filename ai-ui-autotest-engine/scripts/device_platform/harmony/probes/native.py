#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NativeProbe — HarmonyOS ArkUI 视图树渲染层探针。

包装 screen_state.inspect_tree 的采集与匹配逻辑，覆盖鸿蒙原生 ArkUI 控件、
MRN(React Native)容器渲染的内容。`uitest dumpLayout` 能穿透 ArkWeb 拿到
内部 DOM（`Web` 节点下直接挂着 `rootWebArea` 及 W3C accessibility role
节点），可直接复用本探针的 text 匹配与坐标定位逻辑，无需单独探针。

与 device_platform.android.probes.native.NativeProbe 实现完全对称：匹配算法本身
平台无关，screen_state.inspect_tree 内部已按 platform 分派到对应 node_adapter。
"""
from device_platform.base import RendererProbe


class NativeProbe(RendererProbe):
    """基于 uitest dumpLayout 视图树的 native 探针（HarmonyOS）。"""

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
