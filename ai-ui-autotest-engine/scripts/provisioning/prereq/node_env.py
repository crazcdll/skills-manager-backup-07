#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Node 版本管理 & imeituan CLI 执行器（共享模块）。

imeituan CLI 要求 Node >= 18，但用户 PATH 中可能默认 Node 16（nvm 场景）。
本模块提供：
  - current_node_major()      : 获取当前 Node 主版本号
  - node_manager_prefix()     : 探测 nvm/fnm/volta，返回切到目标版本的 shell 前缀
  - node18_env()              : 返回 PATH 前置 Node18 bin 的 env（零 nvm 开销）
  - node_process_env(extra)   : 返回 Node>=18 的进程环境（供 Popen 直接用）
  - run_with_node(cmd, ...)   : 在 Node>=18 环境下执行 shell 命令（字符串形式）
  - run_cli(cmd_list, ...)    : 在 Node>=18 环境下执行命令行（list 形式，执行内核）
  - imeituan_run(args, ...)   : 执行受管 imeituan CLI（使用前已确保最新）

供 devices/toolchain/imeituan_cli.py（统一 CLI 入口，跨 android/ios/harmony 平台通用）、
shared/imeituan.py（依赖安装/版本探测）和 provisioning/prereq/check_deps.py 复用。

设计要点：优先探测 nvm 管理的 Node 18+ bin 目录并 prepend 到 PATH，
避免每次 subprocess 都 source nvm.sh。找不到时 fallback 到 nvm source 方式。
"""
import os
import subprocess
import threading
import time
from shutil import which

from shared.paths import ENV_PLATFORM, ENV_TRANSPORT_PORT

REQUIRED_NODE_MAJOR = 18   # imeituan CLI 最低要求
NPM_REGISTRY = "http://r.npm.sankuai.com"

# ─── 缓存：避免每次调用都探测 Node 版本 ──────────────────────
_cached_node_major = None
_cached_prefix = ...       # 用 ... 表示未探测，None 表示探测后无可用管理器
_cached_node18_env = ...   # 用 ... 表示未探测，None 表示无法解析 Node 18 路径

def current_node_major():
    """返回当前 PATH 中 node 的主版本号；无 node 或解析失败返回 None。"""
    global _cached_node_major
    if _cached_node_major is not None:
        return _cached_node_major
    try:
        r = subprocess.run(["node", "-v"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=15)
        ver = (r.stdout or "").strip().lstrip("v")
        _cached_node_major = int(ver.split(".")[0]) if ver else None
    except Exception:
        _cached_node_major = None
    return _cached_node_major

def _find_node18_bin_dir():
    """探测 nvm 管理的 Node 18+ bin 目录（含 v20/v22 等更高版本）。

    优先选最高版本号。返回 bin 目录绝对路径，或 None（未找到）。
    """
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    nvm_dir = os.environ.get("NVM_DIR") or os.path.join(home, ".nvm")
    versions_dir = os.path.join(nvm_dir, "versions", "node")
    if not os.path.isdir(versions_dir):
        return None
    try:
        versions = [
            d for d in os.listdir(versions_dir)
            if d.startswith("v") and d[1:].split(".")[0].isdigit()
            and int(d[1:].split(".")[0]) >= REQUIRED_NODE_MAJOR
        ]
        versions.sort(key=lambda d: int(d[1:].split(".")[0]), reverse=True)
        for d in versions:
            bin_dir = os.path.join(versions_dir, d, "bin")
            node_bin = os.path.join(bin_dir, "node")
            if os.path.isfile(node_bin):
                return bin_dir
    except OSError:
        pass
    return None

def node18_env():
    """返回 PATH 前置 Node18 bin 的 os.environ 副本（零 nvm 开销）。

    首次调用时探测 Node 18 bin 路径并缓存。后续直接返回缓存。
    如果当前 Node 已 >= 18，直接返回当前 env 不做修改。
    如果找不到 Node 18，返回 None。
    """
    global _cached_node18_env
    if _cached_node18_env is not ...:
        return _cached_node18_env

    if not _need_node_switch():
        # 当前 Node 已够用，直接用当前 env
        _cached_node18_env = os.environ.copy()
        return _cached_node18_env

    bin_dir = _find_node18_bin_dir()
    if not bin_dir:
        _cached_node18_env = None
        return None

    env = os.environ.copy()
    env["PATH"] = bin_dir + ":" + env.get("PATH", "")
    _cached_node18_env = env
    return _cached_node18_env

def node_manager_prefix(target_major=None):
    """探测 nvm/fnm/volta，返回切到目标 Node 版本的 shell 前缀字符串；无则 None。

    这是 fallback 路径——仅当 node18_env() 不可用时才走这里。
    """
    global _cached_prefix
    if _cached_prefix is not ...:
        return _cached_prefix
    target = target_major or REQUIRED_NODE_MAJOR
    nvm_sh = os.path.expanduser("~/.nvm/nvm.sh")
    if os.path.isfile(nvm_sh):
        _cached_prefix = (f'source "{nvm_sh}" && nvm install {target} >/dev/null 2>&1 '
                          f'&& nvm use {target} >/dev/null 2>&1')
        return _cached_prefix
    if which("fnm"):
        _cached_prefix = (f'eval "$(fnm env)" && fnm install {target} >/dev/null 2>&1 '
                          f'&& fnm use {target} >/dev/null 2>&1')
        return _cached_prefix
    if which("volta"):
        _cached_prefix = f'volta install node@{target} >/dev/null 2>&1'
        return _cached_prefix
    _cached_prefix = None
    return None

def _need_node_switch():
    """判断当前 Node 版本是否低于要求，需要通过版本管理器切换。"""
    major = current_node_major()
    return major is None or major < REQUIRED_NODE_MAJOR

def run_with_node(cmd, timeout=300):
    """在 Node>=18 环境下执行 shell 命令（字符串形式）。

    返回 (ok: bool, output: str)。

    优先走 PATH 前置方案（零 nvm 开销），fallback 到 bash -lc + nvm source。
    """
    if not _need_node_switch():
        try:
            r = subprocess.run(["/bin/bash", "-lc", cmd],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=timeout)
            return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return False, str(e)

    # 优先：PATH 前置 Node 18 bin（直接 subprocess，省 nvm source ~0.8s/次）
    env = node18_env()
    if env is not None:
        try:
            r = subprocess.run(["/bin/bash", "-c", cmd],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=timeout, env=env)
            return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return False, str(e)

    # Fallback：nvm source 方式
    prefix = node_manager_prefix()
    if not prefix:
        major = current_node_major()
        return False, (f"Node {major or '未安装'} < {REQUIRED_NODE_MAJOR}，"
                       "且未检测到 nvm/fnm/volta")
    try:
        full = f"{prefix} && {cmd}"
        r = subprocess.run(["/bin/bash", "-lc", full],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)

def _with_live_env(base, extra=None):
    """在缓存的 Node18 env 上补齐**之后才设置**的 os.environ 变量。

    `node18_env()` 会缓存首次 os.environ 副本；`IMEITUAN_CLOUD_ADB_PORT` /
    `AI_UITEST_PLATFORM` 由 active context 在首次设备命令前注入，可能晚于缓存。
    这里只补缺失键，不覆盖 Node18 的 PATH 等既有配置。
    """
    merged = dict(base or {})
    for key, value in os.environ.items():
        merged.setdefault(key, value)
    if extra:
        merged.update({k: str(v) for k, v in extra.items() if v is not None})
    return merged


def node_process_env(env_extra=None):
    """返回 Node>=18 的进程环境（供 Popen / subprocess 直接用）。

    当前 Node 已满足要求时基于 `os.environ`；否则基于前置的 Node18 PATH。
    完全找不到 Node>=18 且版本管理器也无法切换时返回 None —— 调用方应视为不可用。
    env_extra 必须在这里显式 merge：`node18_env()` 会缓存首次 os.environ 副本，
    晚于该缓存设置的变量不会自动透传。
    """
    extra = {k: str(v) for k, v in (env_extra or {}).items() if v is not None}
    if _need_node_switch():
        base = node18_env()
        if base is None:
            return None
    else:
        base = os.environ
    return _with_live_env(base, extra)


def run_cli(cmd_list, capture=True, timeout=30, env_extra=None):
    """在 Node>=18 环境下执行任意命令行（list 形式；不做可执行文件解析）。

    这是引擎所有 Node CLI 的**唯一执行内核**：设备命令入口 imeituan_run 与
    依赖安装/版本探测（shared/imeituan.py）都走这里，保证“无论当前 shell 的
    Node 是哪个版本，命令都在 Node>=18 下执行”。

    返回 subprocess.CompletedProcess。
    优先走 PATH 前置方案（~0.3s/次），fallback 到 nvm source（~2.3s/次）。
    """
    cmd_list = [str(c) for c in cmd_list]
    extra = {k: str(v) for k, v in (env_extra or {}).items() if v is not None}

    if not _need_node_switch():
        # Node 版本足够，直接 subprocess
        kw = {"universal_newlines": True, "timeout": timeout}
        if extra:
            kw["env"] = _with_live_env(os.environ, extra)
        if capture:
            kw["stdout"] = subprocess.PIPE
            kw["stderr"] = subprocess.PIPE
        return subprocess.run(cmd_list, **kw)

    # 优先：PATH 前置 Node 18 bin（零 nvm 开销）
    env = node18_env()
    if env is not None:
        kw = {"universal_newlines": True, "timeout": timeout,
              "env": _with_live_env(env, extra)}
        if capture:
            kw["stdout"] = subprocess.PIPE
            kw["stderr"] = subprocess.PIPE
        return subprocess.run(cmd_list, **kw)

    # Fallback：通过版本管理器切换
    prefix = node_manager_prefix()
    if not prefix:
        return subprocess.CompletedProcess(
            cmd_list, returncode=1,
            stdout="", stderr=f"Node < {REQUIRED_NODE_MAJOR}，无 nvm/fnm/volta")

    import shlex
    export = " ".join(f"{k}={shlex.quote(v)}" for k, v in extra.items())
    shell_cmd = (f"{export} && " if export else "") + f"{prefix} && {shlex.join(cmd_list)}"
    kw = {"universal_newlines": True, "timeout": timeout}
    if capture:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
    return subprocess.run(["/bin/bash", "-lc", shell_cmd], **kw)


def _imeituan_env(env_extra, platform: str):
    """把通用 transport port 适配成 imeituan CLI 的 ADB 环境变量。

    通用端口由 engine 统一分配；只有 Android/ADB 传输需要把它映射为 CLI 认识
    的 `IMEITUAN_CLOUD_ADB_PORT`。HarmonyOS/iOS 不注入该变量。
    """
    extra = dict(env_extra or {})
    if platform == "android":
        port = os.environ.get(ENV_TRANSPORT_PORT, "").strip()
        if port:
            extra.setdefault("IMEITUAN_CLOUD_ADB_PORT", port)
    return extra


def imeituan_run(args, capture=True, timeout=30, env_extra=None, adb_recovery=None):
    """在 Node>=18 环境下执行 imeituan CLI 命令。

    args: list[str]，如 ["device", "connect", "-p", "android", ...]
    env_extra: 额外注入子进程的环境变量（如 IMEITUAN_SESSION 设备会话绑定）。
    adb_recovery: 是否允许执行 Android/ADB 专属的 Cloud ADB 台账修复。
        默认按 `AI_UITEST_PLATFORM` 判定：只有 android 才启用；HarmonyOS 走
        hdc、iOS 走 WDA，均不应触发 `device contract --repair-android-runtime`。

    可执行文件走 `shared.imeituan.ensure_bin()`：固定受管路径，且**使用前已确保
    是最新版本**；不随调用方 PATH 漂移，也不受当前 Node 版本影响。

    命中 `ADB_SERVER_COORDINATION_*` 时先调用平台官方修复命令，成功后对原命令
    重试一次；修复命令自身必须 `adb_recovery=False` 防止递归。
    """
    platform = os.environ.get(ENV_PLATFORM, "").strip().lower()
    if adb_recovery is None:
        adb_recovery = platform == "android"
    cmd_env = _imeituan_env(env_extra, platform)
    from shared.imeituan import ensure_bin
    cmd = [ensure_bin()] + list(args)
    cp = run_cli(cmd, capture=capture, timeout=timeout, env_extra=cmd_env)
    if adb_recovery and cp.returncode != 0 and _is_coordination_error(cp):
        if _repair_adb_coordination():
            cp = run_cli(cmd, capture=capture, timeout=timeout, env_extra=cmd_env)
    return cp


# ─── Cloud ADB 协调修复（仅 Android/ADB 路径） ───────────────
# 这些错误不是单台设备问题，而是本机 Cloud ADB Server 的调度台账异常。
# 修复会中断该端口上的 ADB 命令并重建 Server，因此同一 workspace 内串行执行。
_COORDINATION_MARKERS = (
    "ADB_SERVER_COORDINATION_",
    "旧设备操作尚未安全退出",
    "设备连接状态无法读取",
    "ADB 调度记录损坏",
)
_SESSION_REUSE_MARKERS = (
    "SESSION_CLEANUP_PENDING",
    "SESSION_RESOURCES_ACTIVE",
    "SESSION_CLOSING",
)
_repair_lock = threading.Lock()
_last_repair_at = 0.0
_REPAIR_COOLDOWN_SEC = 5.0


def _is_coordination_error(cp) -> bool:
    text = f"{cp.stdout or ''}\n{cp.stderr or ''}".upper()
    # 显式协调错误优先；显式单设备会话错误交给设备池换机，不做 ADB 修复。
    if "ADB_SERVER_COORDINATION_" in text:
        return True
    if any(marker in text for marker in _SESSION_REUSE_MARKERS):
        return False
    return any(marker.upper() in text for marker in _COORDINATION_MARKERS)


def _repair_adb_coordination() -> bool:
    """修复本 workspace 独立 Cloud ADB Server 的调度台账；失败返回 False。"""
    global _last_repair_at
    with _repair_lock:
        now = time.monotonic()
        if now - _last_repair_at < _REPAIR_COOLDOWN_SEC:
            return True
        _last_repair_at = now
        try:
            cp = imeituan_run(
                ["device", "contract", "--repair-android-runtime"],
                capture=True, timeout=120, env_extra=None, adb_recovery=False,
            )
            return cp.returncode == 0
        except Exception:
            return False
