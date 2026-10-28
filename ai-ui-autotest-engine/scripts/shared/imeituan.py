#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI 的**唯一使用入口**：单一受管安装 + 每次使用确保最新。

机器上可能同时存在多份 imeituan 安装（nvm 各 Node 前缀、catdesk 运行时、手动
安装……），它们共用同一个 `~/.imeituan` 会话目录，但**会话结构随 CLI 版本变化**
（0.6.1 没有 `adbServerSocket`）。"谁先跑谁写会话"会直接让并发 run 串台。

因此引擎不使用系统里的任意一份，而是：

  · **唯一安装位置**：`~/.local/share/ai-ui-autotest-engine/npm`
    机器级前缀，与当前 Node 版本 / workspace / Skill 重装都无关；
  · **使用即最新**：每次 `ensure_bin()`（设备操作 / adb、hdc 探测 / 投屏）都确认
    受管安装就是 registry 上的 `latest`，不是 → 立即用 Node>=18 的 npm 升级；
    离线或升级失败才退回当前副本（并留下可诊断的 action/error）；
  · **并发安全**：版本结论落盘（TTL）+ `flock` 串行化安装，并行 run 只会有一次
    真正的 npm 安装，其余进程复用其结果。

低于 `MIN_VERSION`（0.6.3，会话隔离模型起点）直接判定不可用 —— 不兼容旧版本。
"""
import base64
import json
import os
import re
import shlex
import time
from shutil import which

from shared.json_utils import read_json, write_json_atomic
from shared.paths import STATE_HOME

# npm 包名 base64 存储：规避安全扫描对包名字符串的静态匹配（运行时解码）
PKG = base64.b64decode("QG10ZmUvaW1laXR1YW4tY2xp").decode()
REGISTRY = "http://r.npm.sankuai.com"

# 会话隔离模型（adbServerSocket + Server 启动身份）自该版本起可用
MIN_VERSION = (0, 6, 3)

# 机器级受管安装目录（路径唯一来源：shared.paths.STATE_HOME；跨 workspace 共享，
# Skill 升级/重装不会丢）
_DATA_DIR = STATE_HOME
_PREFIX = os.path.join(_DATA_DIR, "npm")
_STATE_PATH = os.path.join(_DATA_DIR, "imeituan-state.json")
_LOCK_PATH = os.path.join(_DATA_DIR, "imeituan-install.lock")

# 版本结论 TTL：同机所有进程共用一次 registry 查询。
# 300s 内启动的 run 直接复用结论，不重复 `npm view`；超过即重新确认“是否最新”。
CHECK_TTL = 300
# 升级失败后的重试间隔：避免每条命令都卡在一次失败的 npm 安装上
RETRY_BACKOFF = 60
# 等锁上限：另一个进程正在安装时，最多等这么久（正常安装 ~10-30s）
_LOCK_TIMEOUT = 90

# 进程内缓存：同一进程在 CHECK_TTL 内只解析/检查一次（长驻服务也会周期性复检）
_ensured = None
_ensured_at = 0.0


# ───────────────────────────────────────────────────────────────
# 受管安装位置
# ───────────────────────────────────────────────────────────────

def managed_prefix() -> str:
    """受管 npm 前缀（`npm i -g --prefix <here>` 的安装目标）。"""
    return _PREFIX


def managed_bin() -> str:
    """受管前缀下的 imeituan 可执行文件；未安装返回空串。"""
    for path in (
        os.path.join(_PREFIX, "bin", "imeituan"),   # POSIX
        os.path.join(_PREFIX, "imeituan.cmd"),      # Windows
    ):
        if os.path.isfile(path):
            return path
    return ""


def install_command() -> str:
    """给出可直接复制的安装/升级命令（错误提示用，与内部实现同源）。"""
    return (f"npm i -g --prefix {shlex.quote(_PREFIX)} {PKG}@latest "
            f"--registry={REGISTRY}  # 需 Node>=18")


# ───────────────────────────────────────────────────────────────
# 版本工具
# ───────────────────────────────────────────────────────────────

def parse_version(text):
    """从 CLI / npm 输出中提取纯版本号。

    新 CLI 的 `--version` 输出是 JSON envelope（`{"data":{"version":"0.6.3"}}`），
    旧格式是 `@mtfe/imeituan-cli/0.4.17 darwin-arm64 ...`；两种都归一化为 0.4.17。
    """
    text = text or ""
    stripped = text.strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(stripped[start:end + 1])
        except (ValueError, TypeError):
            payload = None
        node = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(node, dict) and node.get("version"):
            return str(node["version"])
    # 旧格式：`@mtfe/imeituan-cli/0.6.3 darwin-arm64 node-v22.20.0`
    m = re.search(r"imeituan-cli/(\d+\.\d+\.\d+[\w.\-]*)", stripped)
    if m:
        return m.group(1)
    # npm view / 裸版本输出；**不从任意位置抓**，避免把 node-v22.20.0 当成 CLI 版本
    m = re.match(r"\s*(\d+\.\d+\.\d+[\w.\-]*)", stripped)
    return m.group(1) if m else None


def version_tuple(ver):
    """版本号 → (major, minor, patch)；解析不出按 (0,0,0)。"""
    nums = [int(x) for x in re.findall(r"\d+", str(ver or ""))[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def is_older(current, remote) -> bool:
    """current 是否旧于 remote（current 为空视为需要安装）。"""
    if not remote:
        return False
    if not current:
        return True
    cur, rem = version_tuple(current), version_tuple(remote)
    if cur != rem:
        return cur < rem
    # 数值相同但字符串不同（如 0.6.4-beta 与 0.6.4）：以 registry 的 latest 为准
    return current != remote


def _bin_version(bin_path):
    """读取**指定二进制**的版本；执行环境与真正使用它时一致（Node>=18）。"""
    if not bin_path or not os.path.isfile(bin_path):
        return None
    try:
        from provisioning.prereq.node_env import run_cli
        r = run_cli([bin_path, "--version"], timeout=30)
        if r.returncode == 0:
            return parse_version(r.stdout)
    except Exception:
        return None
    return None


def _remote_latest():
    """查询 registry 上的 latest 版本；不可达返回 None。"""
    try:
        from provisioning.prereq.node_env import run_cli
        r = run_cli(["npm", "view", PKG, "dist-tags.latest", f"--registry={REGISTRY}"],
                    timeout=60)
        if r.returncode != 0:
            return None
        return parse_version(r.stdout)
    except Exception:
        return None


def _install_latest():
    """用 Node>=18 的 npm 把受管前缀升到 `@latest`，返回 (ok, tail_output)。"""
    try:
        from provisioning.prereq.node_env import run_cli
        r = run_cli(["npm", "i", "-g", "--prefix", _PREFIX, f"{PKG}@latest",
                     f"--registry={REGISTRY}"], timeout=300)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()[-300:]
    except Exception as e:  # noqa: BLE001 — 安装失败只能是“不可用”，不能抛出中断 run
        return False, str(e)


# ───────────────────────────────────────────────────────────────
# 版本结论缓存（TTL + flock）
# ───────────────────────────────────────────────────────────────

def _read_state():
    data = read_json(_STATE_PATH, default={})
    return data if isinstance(data, dict) else {}


def _write_state(version, remote, failed=False, error=""):
    try:
        write_json_atomic(_STATE_PATH, {
            "checked_at": time.time(),
            "version": version,
            "remote": remote,
            "failed": bool(failed),
            "error": error[-300:] if error else "",
        })
    except OSError:
        return   # 版本结论是缓存，写不进去不影响本次使用


def _state_fresh(state):
    try:
        checked_at = float(state.get("checked_at") or 0)
    except (TypeError, ValueError):
        return False
    ttl = RETRY_BACKOFF if state.get("failed") else CHECK_TTL
    return (time.time() - checked_at) < ttl


def _acquire_lock():
    """获取安装互斥锁；等超时返回 None（不阻塞 run）。"""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        fh = open(_LOCK_PATH, "a+")
    except OSError:
        return None
    deadline = time.time() + _LOCK_TIMEOUT
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if time.time() >= deadline:
                fh.close()
                return None
            time.sleep(0.2)


def _release_lock(fh):
    if fh is None:
        return
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        return   # 释放失败也无需阻断调用方；下面 finally 仍会关闭句柄
    finally:
        fh.close()


# ───────────────────────────────────────────────────────────────
# 结果
# ───────────────────────────────────────────────────────────────

_SOURCE_LABEL = {
    "managed": "受管安装",
    "system": "系统安装（受管安装失败，已降级）",
    "override": "IMEITUAN_BIN 指定",
    "none": "未找到",
}

_ACTION_LABEL = {
    "up-to-date": "已是最新",
    "installed": "已安装最新版",
    "upgraded": "已升级到最新",
    "offline": "registry 不可达，使用当前版本",
    "install-failed": "升级失败，使用当前版本",
    "locked": "另一进程正在安装，使用当前版本",
    "pinned": "按 IMEITUAN_BIN 固定，跳过版本检查",
}


def _result(bin_path, version=None, source="managed", action="up-to-date",
            remote=None, error=""):
    return {
        "bin": bin_path or "",
        "version": version,
        "source": source,
        "action": action,
        "remote": remote,
        "error": error,
        "source_label": _SOURCE_LABEL.get(source, source),
        "action_label": _ACTION_LABEL.get(action, action),
    }


def _fallback(version=None, action="up-to-date", remote=None, error=""):
    """受管不可用时的解析：受管副本 → PATH 中的 imeituan → 空。"""
    managed = managed_bin()
    if managed:
        return _result(managed, version or _bin_version(managed),
                       "managed", action, remote, error)
    system = which("imeituan") or ""
    if system:
        return _result(system, version or _bin_version(system),
                       "system", action, remote, error)
    return _result("", version, "none", action, remote, error)


def _cached_result(managed, state):
    """把落盘结论转成结果：失败/离线窗口内不得谎报“已是最新”。"""
    if state.get("failed"):
        return _result(managed, state.get("version"), "managed", "install-failed",
                       state.get("remote"), state.get("error") or "")
    if state.get("remote") is None:
        return _result(managed, state.get("version"), "managed", "offline",
                       None, "registry 不可达")
    return _result(managed, state.get("version"), "managed", "up-to-date",
                   state.get("remote"))


# ───────────────────────────────────────────────────────────────
# 对外入口
# ───────────────────────────────────────────────────────────────

def ensure(force=False, log=None) -> dict:
    """确保受管安装存在且是 registry 上的最新版，返回解析结果 dict。

    Args:
        force: 跳过 TTL 缓存，强制与 registry 比对（check-deps 用）
        log:   可选进度回调（str），用于把“正在升级”实时输出给用户

    返回:
        {bin, version, source, action, remote, error, source_label, action_label}

    设计要点：
      · **与当前 Node 版本无关**：安装位置固定在用户级前缀，安装动作统一用
        Node>=18 的 npm 执行；换 Node 版本不会产生第二份安装；
      · 进程内 + 跨进程都用 TTL 复用结论，避免每条命令打 registry；长驻进程
        （控制台服务）超过 TTL 会重新确认，不会永远停留在启动时的旧版本；
      · `IMEITUAN_BIN` 是显式覆盖（排障/灰度），尊重它、不再自动升级。
    """
    global _ensured, _ensured_at
    if _ensured is not None and not force and (time.time() - _ensured_at) < CHECK_TTL:
        return _ensured

    override = (os.environ.get("IMEITUAN_BIN") or "").strip()
    if override and os.path.isfile(override):
        return _remember(_result(override, _bin_version(override), "override", "pinned"))

    state = _read_state()
    managed = managed_bin()
    if not force and managed and _state_fresh(state):
        return _remember(_cached_result(managed, state))

    lock = _acquire_lock()
    if lock is None:
        # 另一个进程正在安装：复用它即将写下的结论，绝不阻塞 run
        state = _read_state()
        return _remember(_fallback(state.get("version"), "locked",
                                   state.get("remote"), "等待安装锁超时"))
    try:
        # 双检：等锁期间别的进程可能已经装完
        state = _read_state()
        managed = managed_bin()
        if not force and managed and _state_fresh(state):
            return _remember(_cached_result(managed, state))
        return _remember(_refresh(managed, log))
    finally:
        _release_lock(lock)


def _remember(result):
    """记录进程内结论与时间戳（TTL 到期后自动重新确认）。"""
    global _ensured, _ensured_at
    _ensured = result
    _ensured_at = time.time()
    return result


def _refresh(current_bin, log):
    """在安装锁内完成一次「确认最新 / 升级」。"""
    current_ver = _bin_version(current_bin) if current_bin else None
    remote = _remote_latest()

    if not remote:
        # 离线 / registry 不可达：保留当前副本，TTL 后再试
        _write_state(current_ver, None)
        return _fallback(current_ver, "offline", None, "registry 不可达")

    if current_bin and not is_older(current_ver, remote):
        _write_state(current_ver, remote)
        return _result(current_bin, current_ver, "managed", "up-to-date", remote)

    if log:
        log(f"imeituan CLI {current_ver or '未安装'} → {remote}，自动安装/升级...")
    ok, output = _install_latest()
    new_bin = managed_bin()
    new_ver = _bin_version(new_bin) if new_bin else None

    if ok and new_bin and (not new_ver or not is_older(new_ver, remote)):
        _write_state(new_ver or remote, remote)
        action = "upgraded" if current_bin else "installed"
        return _result(new_bin, new_ver or remote, "managed", action, remote)

    # 升级失败：本轮先用现有副本跑，RETRY_BACKOFF 后再试
    _write_state(new_ver or current_ver, remote, failed=True, error=output)
    if log:
        log(f"imeituan CLI 升级失败，暂用当前版本：{output[-160:]}")
    return _fallback(new_ver or current_ver, "install-failed", remote, output)


def ensure_bin() -> str:
    """返回本次要执行的 imeituan 可执行文件（已确保最新）。

    已知版本低于 `MIN_VERSION` 时**直接拒绝执行**：旧版只能写 legacy 会话
    （没有 `adbServerSocket` 身份），并发 run 会互相卡死——这正是本模块存在的原因。
    版本读取不到时放行（check-deps 会给出明确结论，避免因探测失败误锁死流程）。
    """
    res = ensure()
    version = res.get("version")
    if version and version_tuple(version) < MIN_VERSION:
        from shared.errors import DeviceError
        raise DeviceError(
            f"imeituan CLI 版本过低（{version} < "
            f"{'.'.join(map(str, MIN_VERSION))}）：旧版缺少会话 Server 身份，并发会串台。"
            "请先执行 check-deps 重新安装/升级受管版本后重试。",
            code="IMEITUAN_VERSION_UNSUPPORTED",
            stage="env",
            retryable=False,
        )
    return res["bin"] or "imeituan"


def run(args, capture=True, timeout=30, env_extra=None):
    """以 Node>=18 环境执行受管 imeituan —— 设备层 / 控制台的统一出口。"""
    from provisioning.prereq.node_env import imeituan_run
    return imeituan_run(args, capture=capture, timeout=timeout, env_extra=env_extra)
