#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Node 版本管理 & imeituan CLI 执行器（共享模块）。

imeituan CLI 要求 Node >= 18，但用户 PATH 中可能默认 Node 16（nvm 场景）。
本模块提供：
  - current_node_major()      : 获取当前 Node 主版本号
  - node_manager_prefix()     : 探测 nvm/fnm/volta，返回切到目标版本的 shell 前缀
  - node18_env()              : 返回 PATH 前置 Node18 bin 的 env（零 nvm 开销）
  - run_with_node(cmd, ...)   : 在 Node>=18 环境下执行 shell 命令（字符串形式）
  - imeituan_run(args, ...)   : 在 Node>=18 环境下执行 imeituan CLI 命令（列表形式）

供 infra/imeituan_cli.py（统一 CLI 入口，跨 android/ios/harmony 平台通用）和 infra/check_deps.py 复用。

设计要点：优先探测 nvm 管理的 Node 18+ bin 目录并 prepend 到 PATH，
避免每次 subprocess 都 source nvm.sh。找不到时 fallback 到 nvm source 方式。
"""
import os
import subprocess
from shutil import which

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

def imeituan_run(args, capture=True, timeout=30):
    """在 Node>=18 环境下执行 imeituan CLI 命令。

    args: list[str]，如 ["device", "connect", "-p", "android", ...]
    capture: 是否捕获 stdout/stderr
    timeout: 超时秒数

    返回 subprocess.CompletedProcess。

    优先走 PATH 前置方案（~0.3s/次），fallback 到 nvm source（~2.3s/次）。
    """
    cmd_list = ["imeituan"] + list(args)

    if not _need_node_switch():
        # Node 版本足够，直接 subprocess
        kw = {"universal_newlines": True, "timeout": timeout}
        if capture:
            kw["stdout"] = subprocess.PIPE
            kw["stderr"] = subprocess.PIPE
        return subprocess.run(cmd_list, **kw)

    # 优先：PATH 前置 Node 18 bin（零 nvm 开销）
    env = node18_env()
    if env is not None:
        kw = {"universal_newlines": True, "timeout": timeout, "env": env}
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
    shell_cmd = f"{prefix} && {shlex.join(cmd_list)}"
    kw = {"universal_newlines": True, "timeout": timeout}
    if capture:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE
    return subprocess.run(["/bin/bash", "-lc", shell_cmd], **kw)
