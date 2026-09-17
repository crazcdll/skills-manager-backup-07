#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOS 视图树采集 — 基于 uitest dumpLayout。

选型说明：官方 imeituan-cli 的 `control inspect-tree` 在鸿蒙上依赖的正则
与真机实际输出格式不兼容；`uitest dumpLayout` 是 HarmonyOS 自带的 UI
测试工具命令，直接提供 clickable/text/bounds/enabled 等标准无障碍属性，
且与 HarmonyOps.tap/swipe 已在用的 uitest 工具链一致，不引入额外依赖。

工作原理：
  1. hdc shell uitest dumpLayout -p <设备侧路径>，落盘为 JSON
  2. hdc file recv 拉取到本机
  3. 直接返回原始 JSON dict，不做结构改写，由上层按 platform 分派到
     device_platform.harmony.probes.node_adapter.parse_tree() 解析。

用法（独立验证，也是 HarmonyOps.inspect_tree 的实现依赖）：
    python3 inspect_tree.py --serial <serial> [-o out.json]
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
import uuid

from core.util.json_utils import read_json
from device_platform.harmony.hdc import ensure_hdc

_DEVICE_TMP_DIR = "/data/local/tmp"
_hdc_bin_cache = None


def _hdc_bin() -> str:
    """惰性解析 hdc 可执行文件路径（与 platform/harmony/ops.py::_hdc_bin 同一手法）。

    非交互式子进程不会加载 ~/.zshrc，不能假设 PATH 已包含 hdc 所在目录，
    必须显式经 ensure_hdc() 探测并 prepend 当前进程 PATH。
    """
    global _hdc_bin_cache
    if _hdc_bin_cache is None:
        hdc_path, _ = ensure_hdc(install=False) or (None, None)
        _hdc_bin_cache = hdc_path or "hdc"
    return _hdc_bin_cache


def _hdc_shell(serial: str, *args: str, timeout: int = 30) -> str:
    """执行 hdc -t <serial> shell <args...>，返回 stdout 文本。"""
    cmd = [_hdc_bin(), "-t", serial, "shell", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout or ""


def _hdc_file_recv(serial: str, device_path: str, local_path: str, timeout: int = 30) -> bool:
    cmd = [_hdc_bin(), "-t", serial, "file", "recv", device_path, local_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0


def _hdc_shell_rm(serial: str, device_path: str) -> None:
    try:
        _hdc_shell(serial, "rm", "-f", device_path, timeout=10)
    except Exception:
        pass  # 清理失败不影响主流程，设备临时目录残留文件无害


def inspect_tree(serial: str, *, bundle_name: str = None, timeout: int = 30) -> dict:
    """采集鸿蒙设备当前前台内容的视图树（uitest dumpLayout 原始 JSON）。

    Args:
        serial: hdc 设备序列号。
        bundle_name: 可选，指定包名过滤（对应 dumpLayout -b 参数），可减少
            体积（排除状态栏等系统窗口）；默认 None 使用合并窗口模式。
        timeout: hdc 命令超时秒数。

    Returns:
        dict: uitest dumpLayout 输出的原始树（{"attributes": {...},
            "children": [...]}）,供上层 node_adapter.parse_tree() 解析。

    Raises:
        RuntimeError: 采集或拉取失败。
    """
    device_path = f"{_DEVICE_TMP_DIR}/ai_ui_autotest_engine_layout_{uuid.uuid4().hex[:8]}.json"

    cmd_args = ["uitest", "dumpLayout"]
    if bundle_name:
        cmd_args += ["-b", bundle_name]
    cmd_args += ["-p", device_path]

    out = _hdc_shell(serial, *cmd_args, timeout=timeout)
    if "DumpLayout saved to" not in out:
        raise RuntimeError(
            f"INSPECT_TREE_FAILED: uitest dumpLayout 执行失败或输出格式异常: {out.strip()!r}"
        )

    with tempfile.NamedTemporaryFile(prefix="harmony_layout_", suffix=".json", delete=False) as tf:
        local_tmp_path = tf.name

    try:
        if not _hdc_file_recv(serial, device_path, local_tmp_path, timeout=timeout):
            raise RuntimeError(f"INSPECT_TREE_FAILED: 无法拉取设备侧文件 {device_path}")
        with open(local_tmp_path, "r", encoding="utf-8") as f:
            tree = read_json(local_tmp_path, default={})
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"INSPECT_TREE_FAILED: 布局文件解析失败: {e}") from e
    finally:
        import os
        try:
            os.remove(local_tmp_path)
        except OSError:
            pass
        _hdc_shell_rm(serial, device_path)

    if not isinstance(tree, dict) or "attributes" not in tree:
        raise RuntimeError(
            "INSPECT_TREE_FAILED: uitest dumpLayout 输出结构异常"
            "（缺少顶层 attributes 字段，可能是设备端版本差异）"
        )
    return tree



