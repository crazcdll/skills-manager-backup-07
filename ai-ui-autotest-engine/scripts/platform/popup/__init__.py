#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平台弹窗策略包：词表（纯数据/纯函数）+ 消除契约。

本包只放**平台无关**的语义与数据；真正的"采集 + 点击"动作在
`devices/popup.py`（devices 层）里执行，避免 platform 层反向依赖 devices/execution。
"""
from platform.popup.patterns import (
    DEFAULT_CLOSE_TEXTS, POPUP_PATTERNS, match_generic_close, match_popup,
    match_preferred, node_center, node_text,
)

__all__ = [
    "POPUP_PATTERNS", "DEFAULT_CLOSE_TEXTS",
    "node_text", "node_center", "match_popup", "match_preferred", "match_generic_close",
]
