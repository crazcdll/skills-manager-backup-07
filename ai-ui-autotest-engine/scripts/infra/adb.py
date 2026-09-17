#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android adb 环境准备。

确保 adb 二进制可用（版本 >= 1.0.40），供 imeituan CLI 内部 AdbAdapter 使用。
设备连接和交互由 imeituan CLI 通过 Session 机制管理。

本模块是 adb 获取的唯一入口，check_deps 和 device_lifecycle 都通过 ensure_adb() 获取 adb。

查找链（优先级从高到低）：
  1. 当前进程 PATH 直接可用（which adb 版本合规）
  2. env_patch.json 持久化路径（跨会话记忆）
  3. imeituan device environment status 查询受管路径
  4. ~/.imeituan/bin/ 等固定目录
  5. adbutils 内置 ADB（仅 Linux 沙箱，自动 pip 安装）
  6. （最后一步）自下载到持久化目录 ~/.local/share/ai-ui-autotest-engine/adb/

非交互 Shell 不加载 ~/.zshrc，找到后通过 _prepend_path 显式注入当前进程 PATH，
不依赖 shell 配置文件是否被加载。

Linux 沙箱无法从 dl.google.com 下载 platform-tools（返回 502），
改用 adbutils 包内置的 ADB 可执行文件，通过 PyPI 镜像安装。失败时仅给出提示，
不做复杂的多源回退。
"""
import json
import os
import re
import subprocess
import sys
import zipfile

from core.util.paths import CONFIG_DIR, ENV_PATCH_JSON
from core.util.json_utils import write_json_atomic, read_json

ADB_MIN_VERSION = 40  # adb 1.0.40+ 才能连接新设备
_DOWNLOAD_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-"
    f"{'darwin' if sys.platform == 'darwin' else 'linux'}.zip"
)

# imeituan 受管 ADB 目录（imeituan device environment install adb 的安装目标）
_IMEITUAN_BIN_DIR = os.path.expanduser("~/.imeituan/bin")

# 自下载持久化目录（非临时目录，跨任务保留，不会被 preflight-clean 清理）
_ADB_PERSISTENT_BASE = os.path.join(
    os.path.expanduser("~/.local/share/ai-ui-autotest-engine"), "adb"
)


def _pip_install_adbutils():
    """自动 pip 安装 adbutils 包（Linux 沙箱，内置 ADB 二进制）。"""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "adbutils"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=180, check=True,
        )
        return True
    except Exception as e:
        sys.stderr.write(f"[device:adb] pip install adbutils 失败: {e}\n")
        return False


def _get_adbutils_adb():
    """获取 adbutils 内置的 ADB 可执行文件路径，未安装时自动 pip 安装。

    adbutils 内置 ADB 仅在 Linux 环境中有效（PyPI 打包了二进制），
    macOS/Windows 的 binaries/ 目录为空。

    Returns:
        (path, installed): path 为可执行文件路径，installed 表示是否本次新安装的
    """
    if sys.platform != "linux":
        return None, False

    installed = False
    try:
        import adbutils
    except ImportError:
        if not _pip_install_adbutils():
            return None, False
        installed = True
        import adbutils

    adb_path = os.path.join(os.path.dirname(adbutils.__file__), "binaries", "adb")
    if os.path.isfile(adb_path) and os.access(adb_path, os.X_OK):
        return adb_path, installed
    return None, False


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(
            cmd, shell=isinstance(cmd, str), capture_output=True,
            text=True, timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def _version_ok(adb_path):
    try:
        out = subprocess.run(
            [adb_path, "version"], capture_output=True, text=True, timeout=5
        ).stdout
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
        return bool(m and int(m.group(3)) >= ADB_MIN_VERSION)
    except Exception:
        return False


def _verify_adb(adb_path):
    """三重验证：二进制存在性 → 版本合规 → 设备命令可用性。

    Returns:
        (ok, checks): ok=True 表示全部通过，checks 为各维度检查结果 dict
    """
    checks = {}
    checks["exists"] = os.path.isfile(adb_path) and os.access(adb_path, os.X_OK)
    if checks["exists"]:
        checks["version"] = _version_ok(adb_path)
        if checks["version"]:
            rc, _ = _run([adb_path, "devices"], timeout=10)
            checks["device_cmd"] = (rc == 0)
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


def _imeituan_managed_adb():
    """查询 imeituan 受管的 ADB 可执行文件路径。

    通过 `imeituan device environment status` 获取当前受管环境的工具列表，
    从中提取 adb 的完整路径。兼容 JSON envelope 和裸 JSON 两种输出格式。
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
        # 兼容 {code, data: {tools: {adb: {path: ...}}}} 和 {tools: {adb: {path: ...}}}
        data = status.get("data", status)
        if not isinstance(data, dict):
            return None
        tools = data.get("tools", {})
        if not isinstance(tools, dict):
            return None
        adb_info = tools.get("adb", {})
        if isinstance(adb_info, dict):
            path = adb_info.get("path")
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        elif isinstance(adb_info, str):
            if os.path.isfile(adb_info) and os.access(adb_info, os.X_OK):
                return adb_info
        return None
    except Exception:
        return None


def _download_platform_tools(dest_dir):
    """从 Google 官方下载 platform-tools，解压到 dest_dir/platform-tools/。

    dest_dir 是父目录（与 zip 内 platform-tools/ 平级），
    返回 adb 可执行文件路径。
    """
    zip_path = os.path.join(dest_dir, "platform-tools.zip")
    os.makedirs(dest_dir, exist_ok=True)
    rc, out = _run(["curl", "-sL", "-o", zip_path, _DOWNLOAD_URL], timeout=120)
    if rc != 0:
        raise RuntimeError(f"curl 失败: {out}")
    with zipfile.ZipFile(zip_path) as zf:
        members = [
            m for m in zf.namelist()
            if m.startswith("platform-tools/adb") or m.startswith("platform-tools/lib64/")
        ]
        zf.extractall(dest_dir, members=members)
    adb_path = os.path.join(dest_dir, "platform-tools", "adb")
    os.chmod(adb_path, 0o755)
    return adb_path


def _is_path_in_current_session():
    """检查 adb 是否在当前会话 PATH 中可见（非交互 Shell 检测）。"""
    rc, _ = _run(["adb", "version"], timeout=5)
    return rc == 0


def ensure_adb(install=True):
    """确保存在可用的 adb，返回 (path, status)。

    Args:
        install: 未找到时是否自动下载安装

    Returns:
        (path, status):
            path  — 可执行文件路径，不可用时为 None
            status — 三态字符串或 None：
                "session_available" — 当前会话 PATH 中直接可用
                "path_not_loaded"   — 已由 imeituan 管理，但非交互会话未加载 PATH，
                                      已使用绝对路径继续
                "temp_available"    — 自下载的持久化副本，非受管环境
                None                — 不可用

    查找链：PATH → env_patch.json → imeituan status → ~/.imeituan/bin → 固定目录 → adbutils(Linux) → 自下载。
    找到后自动 prepend PATH 并持久化到 env_patch.json。
    """
    # ── ① 当前进程 PATH 直接可用 ──
    rc, out = _run(["adb", "version"], timeout=5)
    if rc == 0:
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
        if m and int(m.group(3)) >= ADB_MIN_VERSION:
            return "adb", "session_available"
        sys.stderr.write(f"[device:adb] adb 版本过旧 ({out.splitlines()[0]})，查找新版...\n")
    else:
        sys.stderr.write("[device:adb] adb 未在 PATH 中找到，继续查找...\n")

    env_patch = _read_env_patch()

    # ── ② env_patch.json 持久化路径 ──
    if env_patch.get("adb_dir") and os.path.isdir(env_patch["adb_dir"]):
        adb_path = os.path.join(env_patch["adb_dir"], "adb")
        ok, _ = _verify_adb(adb_path)
        if ok:
            _prepend_path(env_patch["adb_dir"])
            return adb_path, "session_available"

    # ── ③ imeituan device environment status 查询受管路径 ──
    imeituan_adb = _imeituan_managed_adb()
    if imeituan_adb:
        adb_dir = os.path.dirname(imeituan_adb)
        ok, _ = _verify_adb(imeituan_adb)
        if ok:
            _prepend_path(adb_dir)
            env_patch["adb_dir"] = adb_dir
            _write_env_patch(env_patch)
            status = "session_available" if _is_path_in_current_session() else "path_not_loaded"
            if status == "path_not_loaded":
                sys.stderr.write(
                    f"[device:adb] ADB 已由 imeituan 管理 ({imeituan_adb})，"
                    f"但当前非交互会话未加载 PATH，已使用绝对路径继续\n"
                )
            return imeituan_adb, status

    # ── ④ 固定目录 ──
    _candidate_dirs = [
        _IMEITUAN_BIN_DIR,
        "/tmp/platform-tools",
        "/tmp/adb-tools/platform-tools",
        "/usr/local/lib/android/platform-tools",
        os.path.expanduser("~/.local/lib/android/platform-tools"),
        os.path.expanduser("~/platform-tools"),
        "/opt/homebrew/lib/android/platform-tools",
    ]

    for d in _candidate_dirs:
        if not os.path.isdir(d):
            continue
        adb_path = os.path.join(d, "adb")
        ok, _ = _verify_adb(adb_path)
        if ok:
            _prepend_path(d)
            env_patch["adb_dir"] = d
            _write_env_patch(env_patch)
            status = "session_available" if _is_path_in_current_session() else "path_not_loaded"
            return adb_path, status

    if not install:
        return None, None

    # ── ⑤ adbutils 内置 ADB（仅 Linux 沙箱有效） ──
    if sys.platform == "linux":
        adbutils_adb, newly_installed = _get_adbutils_adb()
        if adbutils_adb:
            adb_dir = os.path.dirname(adbutils_adb)
            ok, checks = _verify_adb(adbutils_adb)
            if ok:
                _prepend_path(adb_dir)
                env_patch["adb_dir"] = adb_dir
                _write_env_patch(env_patch)
                tag = "（来自 adbutils 包，本次新安装）" if newly_installed else "（来自 adbutils 包）"
                sys.stderr.write(f"[device:adb] adb 已就绪: {adbutils_adb}{tag}\n")
                return adbutils_adb, "temp_available"
        sys.stderr.write("[device:adb] Linux 沙箱未能通过 adbutils 获取 adb，请检查 PyPI 镜像配置\n")
        return None, None

    # ── ⑥ 非 Linux 环境：自下载到持久化目录 ──
    sys.stderr.write("[device:adb] 未找到可用 adb，自动下载 platform-tools...\n")
    try:
        adb_path = _download_platform_tools(_ADB_PERSISTENT_BASE)
        adb_dir = os.path.join(_ADB_PERSISTENT_BASE, "platform-tools")
        _prepend_path(adb_dir)
        env_patch["adb_dir"] = adb_dir
        _write_env_patch(env_patch)
        # 三重验证
        ok, checks = _verify_adb(adb_path)
        if not ok:
            sys.stderr.write(f"[device:adb] 下载后验证失败: {checks}\n")
            return None, None
        sys.stderr.write(f"[device:adb] adb 已就绪: {adb_path}（持久化目录，非受管环境）\n")
        return adb_path, "temp_available"
    except Exception as e:
        sys.stderr.write(f"[device:adb] adb 下载失败: {e}\n")
        return None, None


def list_devices(adb_bin="adb"):
    """列出当前通过 adb 连接的设备序列号（仅 state=device 的在线设备）。

    用于本地真机场景（device_type=local）自动探测已连接设备，
    不包括 offline/unauthorized 状态的条目。
    """
    rc, out = _run([adb_bin, "devices"], timeout=10)
    if rc != 0:
        return []
    serials = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or "\t" not in line:
            continue
        serial, state = line.split("\t", 1)
        if state.strip() == "device":
            serials.append(serial)
    return serials