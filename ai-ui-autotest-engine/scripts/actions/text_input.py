#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文本输入与清除 —— 平台无关的编排层，具体输入机制委托给 PlatformOps。

职责分工：
  - text_input.py：纯编排，不包含任何平台特定的 keycode/ADBKeyboard 字面量
  - PlatformOps.clear_text()：各平台自行实现清空输入框的按键序列
  - PlatformOps.supports_cjk_input()：声明平台是否原生支持 CJK 输入
"""
import sys
import time

from core.errors import soft_fail
from context import get_platform_ops
from screen_state.inspect_tree import inspect_tree_has_text, invalidate_cache


def _has_cjk(text: str) -> bool:
    """检查文本是否含 CJK 字符。"""
    return any('\u4e00' <= c <= '\u9fff' for c in text)


def _is_adb_keyboard_active():
    """检测 ADB Keyboard 是否为当前活跃输入法（仅 Android，不缓存）。"""
    ops = get_platform_ops()
    if ops.supports_cjk_input():
        return False  # 鸿蒙不需要 ADBKeyboard
    try:
        val = ops.get_setting("secure", "default_input_method")
        return "ADBKeyboard" in val or "adbkeyboard" in val.lower()
    except Exception as e:
        soft_fail("device", "INPUT_METHOD_PROBE_FAILED", e)
        return False


def _broadcast_text(text: str) -> bool:
    """通过 ADBKeyboard 广播输入文本（仅 Android）。"""
    ops = get_platform_ops()
    if not ops.broadcast("ADB_INPUT_TEXT", msg=text):
        sys.stderr.write(f"⚠️  ADBKeyboard broadcast 发送失败: '{text}'\n")
        return False
    time.sleep(0.5)
    # 写入前必须作废缓存，否则会命中旧快照导致校验永远不通过
    invalidate_cache()
    try:
        if inspect_tree_has_text(text):
            return True
    except Exception as e:
        soft_fail("device", "TEXT_INPUT_VERIFY_FAILED", e)
    return False


def input_text(text: str):
    """输入文本。

    平台无关的编排：
      - 平台原生支持 CJK 或纯 ASCII → 直接 ops.input_text()
      - 平台不支持 CJK（Android）且有 ADBKeyboard → broadcast
      - 降级：ops.input_text() + inspect-tree 校验
    """
    ops = get_platform_ops()

    # 平台原生支持 CJK 或纯 ASCII：直接走 input_text
    if ops.supports_cjk_input() or not _has_cjk(text):
        if not ops.input_text(text):
            sys.stderr.write(f"⚠️  input_text 失败: '{text}'\n")
            return False
        time.sleep(0.3)
        invalidate_cache()
        try:
            if inspect_tree_has_text(text):
                return True
        except Exception as e:
            soft_fail("device", "TEXT_INPUT_VERIFY_FAILED", e)
        sys.stderr.write(f"⚠️  文本输入未生效: '{text}'\n")
        return False

    # 含 CJK 且平台不支持原生输入（Android）：优先 ADBKeyboard broadcast
    ok = False
    if _is_adb_keyboard_active():
        if _broadcast_text(text):
            ok = True
        else:
            sys.stderr.write(f"⚠️  ADBKeyboard broadcast 未生效: '{text}'\n")

    if not ok:
        # 降级：imeituan CLI 原生输入（部分版本支持中文）
        if not ops.input_text(text):
            sys.stderr.write(f"⚠️  input_text 命令执行失败: '{text}'\n")
        time.sleep(0.3)
        invalidate_cache()
        try:
            if inspect_tree_has_text(text):
                ok = True
        except Exception as e:
            soft_fail("device", "TEXT_INPUT_VERIFY_FAILED", e)
        if not ok:
            sys.stderr.write(f"⚠️  文本输入未生效: '{text}'\n")
            return False

    return ok


def edittext_clear(node, max_del=20):
    """清空 EditText：委托给 PlatformOps.clear_text()。

    各平台自行实现聚焦 → 移到末尾 → 批量删除的按键序列，
    本函数不包含任何平台特定的 keycode 字面量。
    """
    ops = get_platform_ops()
    ops.clear_text(node["_cx"], node["_cy"], max_del)