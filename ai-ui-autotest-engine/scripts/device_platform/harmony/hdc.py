#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOS hdc 环境准备。

确保 hdc 二进制可用，供 platform/harmony/ops.py 直拼命令使用。

hdc 由 `imeituan device environment install hdc` 安装到 ~/.imeituan/bin/hdc，
安装脚本会把该目录写入 ~/.zshrc 的 PATH，但这仅在交互式 shell 生效——
非交互式子进程（本 Python 脚本的运行环境）不会自动加载 .zshrc，因此
即使命令行验证通过，脚本内 subprocess 调用仍可能因 PATH 缺失该目录而失败。

本模块是 hdc 获取的唯一入口，check_deps 和 platform/harmony 相关模块都
通过 ensure_hdc() 获取 hdc，找到后显式 prepend 当前进程 PATH 并持久化，
不依赖 shell 配置文件是否被加载。

查找链（优先级从高到低）：
  1. 当前进程 PATH 直接可用（hdc -v 成功）
  2. env_patch.json 持久化路径（跨会话记忆）
  3. imeituan device environment status 查询受管路径
  4. ~/.imeituan/bin/ 固定目录
  5. install=True 时：imeituan device environment install hdc 自动安装
"""
import json
import os
import re
import subprocess
import sys

from core.util.json_utils import write_json_atomic, read_json
from core.util.paths import CONFIG_DIR, ENV_PATCH_JSON

_IMEITUAN_BIN_DIR = os.path.expanduser("~/.imeituan/bin")
_INSTALL_CMD = "imeituan device environment install hdc"


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return -1, str(e)


def _verify_hdc(hdc_path):
    """三重验证：二进制存在性 → 版本可读 → 设备命令可用性。

    hdc 没有设备时 `hdc list targets` 返回 "[Empty]"（exit code=0），
    因此设备命令检查放宽为：exit code == 0 且输出非空即为可用。
    注：hdc 的版本输出格式为 "HDC-<version>"，正则提取版本号。
    """
    checks = {}
    checks["exists"] = os.path.isfile(hdc_path) and os.access(hdc_path, os.X_OK)
    if checks["exists"]:
        rc, out = _run([hdc_path, "-v"])
        checks["version"] = (rc == 0) and bool(out.strip())
        if checks["version"]:
            rc2, out2 = _run([hdc_path, "list", "targets"])
            # list targets 成功即表明 hdc 可执行（即使无设备也返回 0）
            checks["device_cmd"] = (rc2 == 0)
        else:
            checks["device_cmd"] = False
    else:
        checks["version"] = False
        checks["device_cmd"] = False
    return all(checks.values()), checks


def _prepend_path(directory):
    current = os.environ.get("PATH", "")
    if directory not in current.split(":"):
        os.environ["PATH"] = directory + ":" + current


def _read_env_patch():
    if not os.path.isfile(ENV_PATCH_JSON):
        return {}
    return read_json(ENV_PATCH_JSON, default={})


def _write_env_patch(patch):
    write_json_atomic(ENV_PATCH_JSON, patch)


def _imeituan_managed_hdc():
    """查询 imeituan 受管的 HDC 可执行文件路径。

    通过 `imeituan device environment status` 获取当前受管环境的工具列表，
    从中提取 hdc 的完整路径。兼容 JSON envelope 和裸 JSON 两种输出格式。
    """
    try:
        r = subprocess.run(
            ["imeituan", "device", "environment", "status"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None
        try:
            status = json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(status, dict):
            return None
        data = status.get("data", status)
        if not isinstance(data, dict):
            return None
        tools = data.get("tools", {})
        if not isinstance(tools, dict):
            return None
        hdc_info = tools.get("hdc", {})
        if isinstance(hdc_info, dict):
            path = hdc_info.get("path")
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        elif isinstance(hdc_info, str):
            if os.path.isfile(hdc_info) and os.access(hdc_info, os.X_OK):
                return hdc_info
        return None
    except Exception:
        return None


def _is_path_in_current_session():
    """检查 hdc 是否在当前会话 PATH 中可见（非交互 Shell 检测）。"""
    rc, _ = _run(["hdc", "-v"])
    return rc == 0


def ensure_hdc(install=True):
    """确保存在可用的 hdc，返回 (path, status)。

    Args:
        install: 未找到时是否自动安装

    Returns:
        (path, status):
            path  — 可执行文件路径，不可用时为 None
            status — 三态字符串或 None：
                "session_available" — 当前会话 PATH 中直接可用
                "path_not_loaded"   — 已由 imeituan 管理，但非交互会话未加载 PATH，
                                      已使用绝对路径继续
                "temp_available"    — 通过 imeituan 安装后可用（非 PATH 原生可见）
                None                — 不可用

    查找链：PATH → env_patch.json → imeituan status → ~/.imeituan/bin → 自动安装。
    找到后显式 prepend 当前进程 PATH 并持久化到 env_patch.json，
    使子进程环境无需依赖 .zshrc 即可解析到 hdc。
    """
    # ── ① 当前进程 PATH 直接可用 ──
    rc, _ = _run(["hdc", "-v"])
    if rc == 0:
        return "hdc", "session_available"

    env_patch = _read_env_patch()

    # ── ② env_patch.json 持久化路径 ──
    if env_patch.get("hdc_dir") and os.path.isdir(env_patch["hdc_dir"]):
        hdc_path = os.path.join(env_patch["hdc_dir"], "hdc")
        ok, _ = _verify_hdc(hdc_path)
        if ok:
            _prepend_path(env_patch["hdc_dir"])
            return hdc_path, "session_available"

    # ── ③ imeituan device environment status 查询受管路径 ──
    imeituan_hdc = _imeituan_managed_hdc()
    if imeituan_hdc:
        hdc_dir = os.path.dirname(imeituan_hdc)
        ok, _ = _verify_hdc(imeituan_hdc)
        if ok:
            _prepend_path(hdc_dir)
            env_patch["hdc_dir"] = hdc_dir
            _write_env_patch(env_patch)
            status = "session_available" if _is_path_in_current_session() else "path_not_loaded"
            if status == "path_not_loaded":
                sys.stderr.write(
                    f"[device:hdc] HDC 已由 imeituan 管理 ({imeituan_hdc})，"
                    f"但当前非交互会话未加载 PATH，已使用绝对路径继续\n"
                )
            return imeituan_hdc, status

    # ── ④ ~/.imeituan/bin/ 固定目录 ──
    if os.path.isdir(_IMEITUAN_BIN_DIR):
        hdc_path = os.path.join(_IMEITUAN_BIN_DIR, "hdc")
        ok, _ = _verify_hdc(hdc_path)
        if ok:
            _prepend_path(_IMEITUAN_BIN_DIR)
            env_patch["hdc_dir"] = _IMEITUAN_BIN_DIR
            _write_env_patch(env_patch)
            status = "session_available" if _is_path_in_current_session() else "path_not_loaded"
            return hdc_path, status

    if not install:
        return None, None

    # ── ⑤ 自动安装（imeituan 是 HDC 的唯一官方分发渠道） ──
    sys.stderr.write(f"[device:hdc] 未找到可用 hdc，自动执行: {_INSTALL_CMD}\n")
    rc, out = _run(["imeituan", "device", "environment", "install", "hdc"], timeout=180)
    if rc != 0:
        sys.stderr.write(f"[device:hdc] 安装失败: {out[:300]}\n")
        return None, None

    hdc_path = os.path.join(_IMEITUAN_BIN_DIR, "hdc")
    ok, checks = _verify_hdc(hdc_path)
    if ok:
        _prepend_path(_IMEITUAN_BIN_DIR)
        env_patch["hdc_dir"] = _IMEITUAN_BIN_DIR
        _write_env_patch(env_patch)
        sys.stderr.write(f"[device:hdc] hdc 已安装: {hdc_path}\n")
        return hdc_path, "temp_available"

    sys.stderr.write(f"[device:hdc] 安装命令执行成功但验证失败: {checks}\n")
    return None, None


def hdc_version(hdc_path="hdc"):
    rc, out = _run([hdc_path, "-v"])
    if rc != 0:
        return None
    m = re.search(r"(\d+\.\d+\.\d+\w*)", out)
    return m.group(1) if m else out.splitlines()[0] if out else None


def list_targets(hdc_bin="hdc"):
    """列出当前通过 hdc 连接的鸿蒙设备序列号。

    用于本地真机场景（device_type=local）自动探测已连接设备。
    `hdc list targets` 无设备时输出 "[Empty]"，需过滤。
    """
    rc, out = _run([hdc_bin, "list", "targets"], timeout=10)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip() and line.strip() != "[Empty]"]

