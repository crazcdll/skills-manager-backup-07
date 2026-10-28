#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android adb 环境准备。

`ensure_adb()` 是本模块唯一入口：check-deps、设备命令、WebView 端口转发
都通过它拿 adb。

查找链（从高到低，全部是确定性来源）：
  1. 当前进程 PATH（`adb version` 通过且版本 >= 1.0.40）
  2. 用户级工具链缓存（`$STATE/toolchain/toolchain.json`，跨会话记忆）
  3. `imeituan device environment status` 查询受管路径
  4. Skill 内置包的已安装副本（`$STATE/toolchain/adb/<ver>-<platform>/`）
  5. 安装：解压 Skill 内置离线包（`references/toolchain/*.zip`）并验证 `adb version`

刻意不做的事：
  · 不访问 dl.google.com —— 内网/沙箱对该域名返回 502，这条路在本流程真正
    需要它的机器上必然失败；
  · 不 `pip install adbutils` —— 污染用户 Python 环境，且只是把「拿一个 adb」
    拆成第二套互不相干的逻辑。
  固定版本 + 校验和的离线包同时解决了可用性与版本漂移（不同机器 adb 行为不一致）。

非交互 Shell 不加载 ~/.zshrc，因此找到后显式 prepend 当前进程 PATH 并持久化。

统一返回 `(path, status)`：
  · "session_available" — 当前会话 PATH 直接可用
  · "installed"         — 使用 Skill 内置包的已安装副本（绝对路径）
  · None                — 不可用
"""
import json
import os
import re
import shutil
import subprocess
import sys

from devices.toolchain import bundle
from shared.toolchain_env import read_env, update_env

ADB_MIN_VERSION = 40  # adb 1.0.40+ 才能连接新设备
_IMEITUAN_BIN_DIR = os.path.expanduser("~/.imeituan/bin")
_VERSION_RE = re.compile(r"Android Debug Bridge version (\d+)\.(\d+)\.(\d+)")


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:  # noqa: BLE001 —— 探测失败等价于「这条路径不可用」
        return -1, str(e)


def _verify_adb(adb_path):
    """存在性 → 版本合规。

    **刻意不跑 `adb devices`**：它会隐式拉起 5037 上的共享 ADB Server，而
    imeituan 对 Server 有启动身份校验——被引擎随手拉起、没有身份记录的 Server
    会让并发中的会话清理报
    `ADB_PORT_OWNERSHIP_CONFLICT: 当前监听 Server 没有可验证的网络隔离启动记录`。
    真正的设备探测只发生在本地真机路径（`list_devices`），云设备交给 imeituan。

    Returns:
        (ok, checks): checks 形如 {"exists": bool, "version": bool}
    """
    exists = os.path.isfile(adb_path) and os.access(adb_path, os.X_OK)
    if not exists:
        return False, {"exists": False, "version": False}
    rc, out = _run([adb_path, "version"], timeout=5)
    m = _VERSION_RE.search(out or "")
    version_ok = rc == 0 and bool(m) and int(m.group(3)) >= ADB_MIN_VERSION
    return version_ok, {"exists": True, "version": version_ok}


def _prepend_path(directory):
    current = os.environ.get("PATH", "")
    if directory and directory not in current.split(":"):
        os.environ["PATH"] = directory + ":" + current


def _imeituan_managed_adb():
    """查询 imeituan 受管的 adb 路径（`imeituan device environment status`）。

    兼容 JSON envelope 与裸 JSON 两种输出。受管 CLI 不存在时直接返回：
    探测不得触发 npm 安装，否则「只读体检」就不再无副作用。
    """
    try:
        from shared.imeituan import managed_bin, run as run_imeituan
        if not managed_bin():
            return None
        r = run_imeituan(["device", "environment", "status"], timeout=15)
        if r.returncode != 0:
            return None
        status = json.loads(r.stdout)
    except Exception:  # noqa: BLE001 —— 查不到就当没有受管副本
        return None
    data = status.get("data", status) if isinstance(status, dict) else None
    tools = data.get("tools") if isinstance(data, dict) else None
    adb_info = (tools or {}).get("adb") if isinstance(tools, dict) else None
    path = adb_info.get("path") if isinstance(adb_info, dict) else adb_info
    if isinstance(path, str) and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    return None


def source_of(adb_path):
    """按路径推断来源：system / imeituan / bundled / none（仅用于诊断展示）。"""
    if not adb_path:
        return "none"
    if adb_path == "adb":
        return "system"
    real = os.path.realpath(adb_path)
    roots = (("bundled", bundle.INSTALL_ROOT), ("imeituan", _IMEITUAN_BIN_DIR))
    for name, root in roots:
        root_real = os.path.realpath(root)
        if real == root_real or real.startswith(root_real + os.sep):
            return name
    return "system"


def version_of(adb_path):
    """`adb version` 的版本号（如 "1.0.41"）；读不到返回 None。"""
    if not adb_path:
        return None
    rc, out = _run([adb_path, "version"], timeout=5)
    m = _VERSION_RE.search(out or "")
    return ".".join(m.groups()) if rc == 0 and m else None


def _reuse(path, status):
    """命中即 prepend PATH + 持久化缓存目录。"""
    _prepend_path(os.path.dirname(path))
    update_env({"adb_dir": os.path.dirname(path)})
    return path, status


def ensure_adb(install=True):
    """确保存在可用的 adb，返回 `(path, status)`（不可用时 `(None, None)`）。

    Args:
        install: 未找到时是否解压内置离线包。False = 纯探测：不解压、不触发
                 imeituan 安装（只读体检用）。
    """
    # PATH 上的 adb 必须先解析成绝对路径再校验：`_verify_adb("adb")` 里的
    # `os.path.isfile("adb")` 对裸命令名恒为 False，会让本分支形同废码，
    # 进而把「系统已装 adb」的机器误判为缺失、白解压 24MB 内置包。
    found = shutil.which("adb")
    if found and _verify_adb(found)[0]:
        return "adb", "session_available"

    cached_dir = read_env().get("adb_dir") or ""
    if cached_dir and _verify_adb(os.path.join(cached_dir, "adb"))[0]:
        return _reuse(os.path.join(cached_dir, "adb"), "session_available")

    managed = _imeituan_managed_adb()
    if managed and _verify_adb(managed)[0]:
        # `_reuse` 会把所在目录 prepend 进 PATH，本进程内即刻可用，无需再区分
        # 「PATH 未加载」这种中间态（历史上那套判断在 prepend 之后恒为假）
        return _reuse(managed, "session_available")

    meta = bundle.installed()
    if meta and _verify_adb(meta["bin"])[0]:
        return _reuse(meta["bin"], "installed")

    if not install:
        return None, None

    log = lambda m: sys.stderr.write(f"[device:adb] {m}\n")  # noqa: E731
    try:
        res = bundle.install(log=log)
        if res["ok"] and not _verify_adb(res["bin"])[0]:
            # 已装副本损坏（解压中断 / 被外部改动）：强制重解一次内置包
            sys.stderr.write("[device:adb] 已安装副本不可用，重新解压内置包\n")
            res = bundle.install(force=True, log=log)
    except Exception as e:  # noqa: BLE001 —— 坏包/超时统一降级为「adb 不可用」
        sys.stderr.write(f"[device:adb] 解压内置包异常：{type(e).__name__}: {e}\n")
        return None, None
    if not res["ok"]:
        sys.stderr.write(f"[device:adb] 内置离线包不可用（{res['action']}）：{res['error']}\n")
        return None, None

    action = "复用已有副本" if res["action"] == "already-installed" else "本次解压"
    sys.stderr.write(f"[device:adb] adb 已就绪: {res['bin']}"
                     f"（内置包 {res['version']}，{action}）\n")
    return _reuse(res["bin"], "installed")


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
