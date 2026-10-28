#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装制品缓存（Skill 级，跨 workspace / 跨子 Agent 共享）—— **唯一入口**。

【为什么需要它】
每个 run 都要"拿到可测性安装包再装到设备"。制品（鸿蒙 HAP 1.4G、Android APK
数百 MB）如果每次重下，代价是：① 每个 run 白等几分钟；② 多个子 Agent 并行时会
同时对源站发起同样的大包下载（带宽互相挤占，最坏情况 N 倍重复流量）。
所以制品必须有**一份**跨 run 的本地缓存，且安装前必须**先看缓存**。

【分层模型】
  L1 制品缓存（本模块，host 侧）：`~/.local/share/ai-ui-autotest-engine/cache/artifacts/<platform>/<form>/<pkg>/<文件名>`
      · 所有"需要本地制品"的通道（鸿蒙 HAP、Android APK、iOS 制品）共用这一份；
      · **机器级**（跨安装 / 跨 workspace / 跨子 Agent 共享），不能落在 Skill 目录：
        Skill 会被多份安装/镜像，落在里面会各下一份，且 Skill 更新时整目录被替换；
      · **引擎永不自动清理**：只有用户手动清理该目录才会消失；
        post-clean / preflight-clean 只作用于 `$STATE/run/tasks/<ws>/`，不触碰本目录。
  L2 设备侧缓存（device 侧，各 PlatformOps 自持，如鸿蒙 `DEVICE_APK_CACHE_DIR`）：
      · 解决"同一台设备被多次占用时重复 host→device 传输"；
      · 命中判定用 L1 本地文件的**确切大小**（无需再探测远端）。

【并发安全（多子 Agent 同时安装同一制品）】
  1. 读路径无锁：命中即返回，不产生任何写操作；
  2. 未命中才进入**按制品加锁**（`<file>.lock` 的 flock）：等待者的进程崩溃/退出时
     内核自动释放锁，不会留下死锁；
  3. 拿到锁后**二次判定**：等锁期间别的 Agent 可能已经下完 → 直接复用，不重复下载；
  4. 落盘原子：先写 `<file>.part.<pid>` 再 `os.replace`，读者永远看不到半截文件；
  5. 崩溃残留：只在持有锁时清理超龄 `.part.*`（不影响他人正在写的 part）。

【命中判定（为什么不做全量哈希）】
  命中 = 文件存在 + 大小 > 0 + sidecar 记录的大小与磁盘实际大小一致（防截断）+
  （可选）远端大小一致（HEAD，用于"同名文件被换内容"的情况；探测失败不否决缓存）。
  1.4G 的制品每次安装都算哈希是纯浪费——原子落盘 + 大小校验已能覆盖真实故障
  （截断、半包、并发写坏）；防篡改不在本模块职责内。
"""
import fcntl
import os
import shutil
import sys
import time
from contextlib import contextmanager
from urllib.parse import urlparse

from shared.json_utils import read_json, write_json_atomic
from shared.paths import STATE_HOME

# ── 缓存根（机器级，永不自动清理；见模块 docstring 的分层模型）──────────
CACHE_ROOT = os.path.join(STATE_HOME, "cache")
ARTIFACTS_DIR = os.path.join(CACHE_ROOT, "artifacts")

# 崩溃残留的 part 文件超过该秒数才清理（远大于正常下载耗时，避免误删活跃下载）
_STALE_PART_SEC = 6 * 3600
# socket 级超时（不是总时长）：大包下载期间只要持续有数据就不会触发
_SOCKET_TIMEOUT = 300


def cache_root() -> str:
    """L1 制品缓存的根目录（`~/.local/share/ai-ui-autotest-engine/cache`）。"""
    return CACHE_ROOT


def is_cache_path(path: str) -> bool:
    """判断路径是否位于 L1 缓存内（供"哪些目录必须保留"的判定复用）。"""
    try:
        return os.path.abspath(path).startswith(os.path.abspath(CACHE_ROOT) + os.sep)
    except (TypeError, ValueError):
        return False


def scope_of(app_desc) -> str:
    """由 AppDescriptor 派生缓存命名空间：`<platform>/<form>/<package>`。

    以包名为最后一级：同一平台/形态下不同 App（含鸿蒙真机 beta 包与模拟器正式包）
    天然分目录，文件名重复也不会互相覆盖。只在 attributes 上取值，不 import
    devices 层（保持 shared 层零跨包依赖）。
    """
    platform = getattr(app_desc, "platform", None) or "android"
    form = getattr(app_desc, "form", None) or "real"
    package = getattr(app_desc, "package_name", None) or "unknown"
    return f"{platform}/{form}/{package}"


def is_remote(url) -> bool:
    """是否为需要先落缓存的远程制品 URL（http/https）。"""
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def resolve(artifact: str, scope: str, *, timeout: int = _SOCKET_TIMEOUT,
            label: str = "") -> str:
    """制品定位符 → **本地文件路径**（所有安装通道的唯一入口）。

    远程 URL → 经 L1 缓存（命中即免下载，并发只下一次）；本地路径 / 预设名 →
    原样返回（随仓制品如 ADBKeyboard.apk 本身就是本地文件，不做也无需副本）。
    因此调用方不需要自己判 URL，也不会各写一份“先看缓存”的逻辑。
    """
    if is_remote(artifact):
        return ensure(artifact, scope, timeout=timeout, label=label)
    return artifact


def artifact_path(url: str, scope: str) -> str:
    """制品在 L1 缓存中的确定路径（纯函数，便于运维/自检直接推算）。"""
    name = os.path.basename(urlparse(url).path) or "artifact.bin"
    return os.path.join(ARTIFACTS_DIR, *scope.split("/"), name)


def _meta_path(path: str) -> str:
    return path + ".meta.json"


def remote_size(url: str, timeout: int = 60):
    """远端制品大小（HEAD Content-Length）；探测失败返回 None（调用方按"不校验"处理）。"""
    from urllib.request import Request, urlopen
    try:
        with urlopen(Request(url, method="HEAD"), timeout=timeout) as resp:
            return int(resp.headers.get("Content-Length") or 0) or None
    except Exception as e:  # noqa: BLE001 —— 探测失败不阻断安装，退化为不校验大小
        sys.stderr.write(f"[artifact_cache] 远端大小探测失败（按不校验处理）: {e}\n")
        return None


def lookup(url: str, scope: str, *, verify_remote: bool = False) -> dict:
    """只看缓存（不下载），返回 `{"hit": bool, path, size, reason, ...}`。"""
    path = artifact_path(url, scope)
    result = {"hit": False, "path": path, "size": None, "url": url, "reason": ""}
    if not os.path.isfile(path):
        result["reason"] = "缓存无此制品"
        return result
    size = os.path.getsize(path)
    if size <= 0:
        result["reason"] = "缓存文件为空（视为未命中）"
        return result
    meta = read_json(_meta_path(path), default={}) or {}
    if not meta:
        result["reason"] = "缺少 sidecar 元数据（视为未命中，避免复用来历不明的文件）"
        return result
    if meta.get("size") != size:
        result["reason"] = f"缓存大小与元数据不一致（磁盘 {size} vs 记录 {meta.get('size')}）"
        return result
    if verify_remote:
        remote = remote_size(url)
        if remote is not None and remote != size:
            result["reason"] = f"远端制品已变化（远端 {remote} vs 缓存 {size}）"
            return result
    result.update({"hit": True, "size": size, "reason": "命中缓存",
                   "downloadedAt": meta.get("downloadedAt"), "url": meta.get("url")})
    return result


def describe(url: str, scope: str) -> dict:
    """不下载、不发起网络请求的缓存摘要，供安装报告 / check-version 展示。"""
    info = lookup(url, scope)
    return {
        "hit": info["hit"], "path": info["path"], "size": info["size"],
        "cacheRoot": CACHE_ROOT, "reason": info["reason"],
    }


@contextmanager
def _download_lock(path: str, label: str = ""):
    """按制品加排他锁（flock）：等锁期间不打日志噪音，只在需要等待时提示一次。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_fh = open(path + ".lock", "w", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.stderr.write(
                f"[artifact_cache] 另一进程正在下载同一制品，等待其完成{label}: "
                f"{os.path.basename(path)}\n")
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        finally:
            lock_fh.close()


def _clean_stale_parts(path: str):
    """清理本制品目录下超龄的 `.part.*`（崩溃残留），不动他人正在写的 part。"""
    directory = os.path.dirname(path)
    prefix = os.path.basename(path) + ".part."
    now = time.time()
    try:
        names = os.listdir(directory)
    except OSError as e:
        sys.stderr.write(f"[artifact_cache] 列目录清理残留失败（忽略）: {e}\n")
        return
    for name in names:
        if not name.startswith(prefix):
            continue
        target = os.path.join(directory, name)
        try:
            if now - os.path.getmtime(target) > _STALE_PART_SEC:
                os.remove(target)
                sys.stderr.write(f"[artifact_cache] 清理超龄下载残留: {target}\n")
        except OSError as e:
            sys.stderr.write(f"[artifact_cache] 清理残留失败（忽略）: {e}\n")


def _download(url: str, part_path: str, timeout: int) -> int:
    """流式下载到 `part_path`（不落最终路径），返回字节数。"""
    from urllib.request import urlopen
    with urlopen(url, timeout=timeout) as resp, open(part_path, "wb") as fh:
        shutil.copyfileobj(resp, fh, length=1024 * 1024)
    return os.path.getsize(part_path)


def ensure(url: str, scope: str, *, timeout: int = _SOCKET_TIMEOUT, label: str = "") -> str:
    """取制品本地路径：命中缓存直接返回，未命中才加锁下载（并发下只下载一次）。

    Args:
        url: 制品 URL（http/https）
        scope: 命名空间（用 `scope_of(app_desc)` 派生，见该函数）
        timeout: socket 级超时
        label: 日志用标签（如 "harmony/emulator"）

    Returns:
        str: L1 缓存中的本地文件路径（保证存在、非空、大小与元数据一致）
    """
    if not is_remote(url):
        raise ValueError(f"artifact_cache 只接受 http/https 制品 URL，收到: {url!r}")
    path = artifact_path(url, scope)
    info = lookup(url, scope, verify_remote=True)
    if info["hit"]:
        sys.stderr.write(
            f"[artifact_cache] ✅ 命中制品缓存{'（' + label + '）' if label else ''}: "
            f"{path}（{info['size'] // 1024 // 1024}MB）\n")
        return path
    sys.stderr.write(
        f"[artifact_cache] 未命中缓存{'（' + label + '）' if label else ''}"
        f"（{info['reason']}）→ 准备下载: {url}\n")

    with _download_lock(path, label=f"（{label}）" if label else ""):
        info = lookup(url, scope, verify_remote=True)  # 二次判定：等锁期间可能已下完
        if info["hit"]:
            sys.stderr.write(
                f"[artifact_cache] ✅ 命中制品缓存（等锁期间已就绪）: {path}\n")
            return path
        _clean_stale_parts(path)
        part_path = f"{path}.part.{os.getpid()}"
        started = time.time()
        try:
            size = _download(url, part_path, timeout)
        except Exception:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError as e:
                    sys.stderr.write(f"[artifact_cache] 清理失败下载残留（忽略）: {e}\n")
            raise
        if size <= 0:
            raise RuntimeError(f"制品下载为空: {url}")
        os.replace(part_path, path)  # 原子落盘：读者看不到半截文件
        write_json_atomic(_meta_path(path), {
            "url": url, "scope": scope, "size": size,
            "downloadedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        sys.stderr.write(
            f"[artifact_cache] ⬇️ 下载完成: {path}（{size // 1024 // 1024}MB，"
            f"耗时 {time.time() - started:.0f}s；后续 run / 子 Agent 将直接复用）\n")
    return path


__all__ = [
    "ARTIFACTS_DIR", "CACHE_ROOT",
    "artifact_path", "cache_root", "describe", "ensure", "is_cache_path",
    "is_remote", "lookup", "remote_size", "resolve", "scope_of",
]
