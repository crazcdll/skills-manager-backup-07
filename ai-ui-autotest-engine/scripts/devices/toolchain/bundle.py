#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 内置 adb 离线包：清单驱动的解压安装。

adb 只需要「一个版本、一个位置」，因此这里不提供版本枚举 / 多版本回退 / 清理子命令：

  · 清单 `references/toolchain/manifest.json` 声明版本、各平台包名、大小
    与解压成员白名单 —— 代码里没有第二个「版本号 / 文件名」来源；
  · 安装前校验存在性与大小（不算哈希），解压后跑 `adb version` 验证产物可用；
  · 解压到同盘临时目录后 **原子 rename** 到 `$STATE/toolchain/adb/<ver>-<plat>/`，
    中断或并发都不会留下半个副本；
  · 全程持有 `$STATE/toolchain/.install.lock` 文件锁：多进程同时冷启动，
    只有一个真正解压，其余等锁后命中已安装副本。

为什么不用官方在线下载：内网/沙箱对 dl.google.com 返回 502，而固定版本 +
随包分发的离线包同时解决了可用性与版本漂移（不同机器 adb 行为不一致）。
"""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from shared import paths

REFS_DIR = os.path.join(paths.REFERENCES_DIR, "toolchain")
MANIFEST_PATH = os.path.join(REFS_DIR, "manifest.json")
INSTALL_ROOT = os.path.join(paths.TOOLCHAIN_DIR, "adb")
LOCK_PATH = os.path.join(paths.TOOLCHAIN_DIR, ".install.lock")

_CHUNK = 1 << 20


def manifest_platform():
    """当前进程所在平台在清单中的键（darwin / linux）。"""
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def read_manifest():
    """读取清单；缺失或损坏时抛 RuntimeError（调用方决定如何降级）。"""
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise RuntimeError(f"清单不存在: {MANIFEST_PATH}（{e.strerror}）")
    except ValueError as e:
        raise RuntimeError(f"清单不是合法 JSON: {MANIFEST_PATH}（{e}）")
    if not isinstance(data, dict) or not data.get("platforms"):
        raise RuntimeError(f"清单缺少 platforms 段: {MANIFEST_PATH}")
    return data


def _entry(man, plat):
    entry = (man.get("platforms") or {}).get(plat)
    if not isinstance(entry, dict) or not entry.get("bundle"):
        raise RuntimeError(f"清单未声明平台 {plat} 的离线包（当前 Skill 只随包分发 darwin/linux）")
    return entry


def bundle_path(entry):
    return os.path.join(REFS_DIR, entry["bundle"])


def verify(plat=None):
    """校验离线包本体（只读）：存在性 → 大小（不算哈希）。

    为什么不算哈希：包随 Skill 分发，清单版本变了就解压到新目录
    `<version>-<platform>`，天然不会复用旧包；哈希只会让每次体检多读几十 MB。

    Returns:
        dict: {ok, platform, bundle, path, size, expected_size, error, version}
    """
    plat = plat or manifest_platform()
    res = {"ok": False, "platform": plat, "bundle": None, "path": None,
           "size": None, "expected_size": None, "error": None, "version": None}
    try:
        man = read_manifest()
        entry = _entry(man, plat)
    except RuntimeError as e:
        res["error"] = str(e)
        return res

    path = bundle_path(entry)
    res.update(bundle=entry["bundle"], path=path, version=man.get("version"),
               expected_size=entry.get("size"))

    if not os.path.isfile(path):
        res["error"] = "离线包未随 Skill 分发（文件缺失）"
        return res

    res["size"] = os.path.getsize(path)
    if res["expected_size"] and res["size"] != res["expected_size"]:
        res["error"] = f"离线包大小不符（期望 {res['expected_size']}，实际 {res['size']}）"
        return res

    res["ok"] = True
    return res


def install_dir(plat=None, man=None):
    """安装目录：`$STATE/toolchain/adb/<version>-<platform>/`。"""
    man = man or read_manifest()
    return os.path.join(INSTALL_ROOT, f"{man.get('version')}-{plat or manifest_platform()}")


def installed(plat=None):
    """已安装副本（只读，不做任何安装动作）。

    Returns:
        dict | None: {dir, bin, version}；未安装或不可执行时 None。
    """
    plat = plat or manifest_platform()
    try:
        dest = install_dir(plat)
        version = read_manifest().get("version")
    except RuntimeError:
        return None
    binary = os.path.join(dest, "adb")
    if os.path.isfile(binary) and os.access(binary, os.X_OK):
        return {"dir": dest, "bin": binary, "version": version}
    return None


def _member_allowed(rel, members):
    """白名单判定：`adb` 精确匹配；以 `/` 结尾的条目按目录前缀匹配。"""
    for m in members:
        if m.endswith("/"):
            if rel.startswith(m):
                return True
        elif rel == m:
            return True
    return False


def _extract(bundle, dest_tmp, members):
    """解压白名单成员并剥离压缩包首层目录（`platform-tools/`）。"""
    picked = 0
    with zipfile.ZipFile(bundle) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/", 1)
            if len(parts) != 2:
                continue
            rel = parts[1]
            if not _member_allowed(rel, members):
                continue
            target = os.path.join(dest_tmp, rel)
            os.makedirs(os.path.dirname(target) or dest_tmp, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, _CHUNK)
            # 压缩包不携带可信权限位：可执行文件统一 0755，其余只读
            mode = 0o755 if (rel == "adb" or rel.endswith((".so", ".dylib"))) else 0o644
            os.chmod(target, mode)
            picked += 1
    if not os.path.isfile(os.path.join(dest_tmp, "adb")):
        raise RuntimeError(f"离线包内未找到 adb（已解压 {picked} 个成员）")
    return picked


def _clear_quarantine(binary):
    """macOS：去掉下载隔离属性，否则首次执行可能被 Gatekeeper 拦下。"""
    if sys.platform != "darwin":
        return
    try:
        subprocess.run(["xattr", "-c", binary], capture_output=True, timeout=10)
    except Exception:  # noqa: BLE001 —— 清属性失败不影响二进制可用性
        pass


def _cleanup_stale(dest):
    """锁内清理：历史临时目录 + 其它版本/平台的残留安装目录。"""
    if not os.path.isdir(INSTALL_ROOT):
        return
    keep = os.path.basename(dest)
    for name in os.listdir(INSTALL_ROOT):
        path = os.path.join(INSTALL_ROOT, name)
        if name == keep:
            continue
        try:
            if os.path.isdir(path) and name.startswith(".tmp-"):
                shutil.rmtree(path)
            elif os.path.isdir(path) and os.path.isfile(os.path.join(path, "adb")):
                shutil.rmtree(path)
        except OSError:
            pass  # 并发进程正在用另一个目录，交给下次清理


def install(force=False, log=None):
    """安装内置离线包（幂等）。

    Args:
        force: 已安装也强制重解（用于副本损坏后的自愈）。
        log:   可选 `log(msg)`，安装进度回调。

    Returns:
        dict: {ok, action, bin, dir, version, error}
              action ∈ already-installed | installed | failed
    """
    say = log or (lambda _m: None)
    plat = manifest_platform()
    res = {"ok": False, "action": "failed", "bin": None, "dir": None,
           "version": None, "error": None}

    if not force:
        meta = installed(plat)
        if meta:
            return {"ok": True, "action": "already-installed", "bin": meta["bin"],
                    "dir": meta["dir"], "version": meta["version"], "error": None}

    check = verify(plat)
    if not check["ok"]:
        res["error"] = check["error"]
        return res
    res["version"] = check["version"]
    members = read_manifest().get("members") or ["adb"]

    try:
        dest = install_dir(plat)
    except RuntimeError as e:
        res["error"] = str(e)
        return res

    os.makedirs(INSTALL_ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            # 等锁期间别的进程可能已经装好：命中即复用（force 例外）
            if not force:
                meta = installed(plat)
                if meta:
                    return {"ok": True, "action": "already-installed", "bin": meta["bin"],
                            "dir": meta["dir"], "version": meta["version"], "error": None}

            say(f"解压内置离线包 {check['bundle']} → {dest}")
            # 先清残留（历史 .tmp-* 与旧版本目录），再建本次临时目录：
            # 反过来的话清理会把本次的临时目录当成残留删掉。
            _cleanup_stale(dest)
            tmp = tempfile.mkdtemp(prefix=".tmp-", dir=INSTALL_ROOT)
            try:
                picked = _extract(check["path"], tmp, members)
                binary = os.path.join(tmp, "adb")
                _clear_quarantine(binary)
                probe = subprocess.run([binary, "version"], capture_output=True, timeout=30)
                if probe.returncode != 0:
                    raise RuntimeError("解压出的 adb 无法执行（与当前平台不匹配？）")
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                os.replace(tmp, dest)
                os.chmod(dest, 0o755)  # mkdtemp 创建的是 0700，目录本身放开为 0755
                say(f"内置包安装完成：{picked} 个成员 → {dest}")
            finally:
                if os.path.isdir(tmp):
                    shutil.rmtree(tmp, ignore_errors=True)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

    return {"ok": True, "action": "installed", "bin": os.path.join(dest, "adb"),
            "dir": dest, "version": res["version"], "error": None}


def info(plat=None):
    """只读摘要（`toolchain` 体检用）：清单 / 包体校验 / 安装状态。"""
    plat = plat or manifest_platform()
    check = verify(plat)
    return {"platform": plat, "version": check.get("version"),
            "bundle": check.get("bundle"), "path": check.get("path"),
            "size": check.get("size"),
            "bundle_ok": check["ok"], "bundle_error": check.get("error"),
            "installed": installed(plat)}
