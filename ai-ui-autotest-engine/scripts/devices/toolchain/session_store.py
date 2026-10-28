#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan 会话存储层（纯文件系统，不调用 CLI）。

imeituan 的会话是 `~/.imeituan/sessions/sess-*.json` 下的独立文件；CLI 只看这一层
的 `*.json`。不同大版本的会话结构不兼容：

    · 0.6.3+（独立 ADB Server 模型）——`lease.adbServerSocket` 必填，
      cleanupStack 里的 adb 条目也带 `meta.adbServerSocket`；
    · 0.6.1 及更早（共享 Server 模型）——没有 server socket 字段。

旧结构会话在 0.6.3 上是**确定性不可用**：任何清理/复用都会抛
`ADB_SERVER_LEGACY_IDENTITY_UNKNOWN`，且 `failurePolicy=retain-session` 会把记录
原样保留，于是下一次注册继续撞同一堵墙。

本模块提供唯一的"隔离"入口：把这类会话**移动**到 `sessions/.stale/`（不删除），
让 CLI 不再扫描到它，同时保留现场供回滚/取证。隔离条件严格限定：

    1. `lease.serial` 必须等于本次要注册的设备串（绝不碰其他设备的会话）；
    2. 必须是 legacy 形态（缺少 server socket 身份）；
    3. 同盘原子 `os.replace`，命名携带时间戳，可人工 `mv` 回滚。

`pid` 不能用于判活：imeituan 每次 CLI 调用都是一个短命进程，正常会话也常是 `pid=0`。
"""
import glob
import json
import os
import sys
from datetime import datetime

from shared.errors import soft_fail

# imeituan 默认把会话写在 ~/.imeituan。
# 覆盖入口只给**本引擎的测试**用（AI_UITEST_IMEITUAN_HOME）：不要复用 imeituan 自己的
# 环境变量——CLI 并不认识 IMEITUAN_HOME，生产环境若误设会让引擎和 CLI 看不同的目录。
_DEFAULT_HOME = "~/.imeituan"
_HOME_ENV = "AI_UITEST_IMEITUAN_HOME"
STALE_DIRNAME = ".stale"


def imeituan_home() -> str:
    return os.path.expanduser(os.environ.get(_HOME_ENV) or _DEFAULT_HOME)


def sessions_root() -> str:
    return os.path.join(imeituan_home(), "sessions")


def stale_root() -> str:
    return os.path.join(sessions_root(), STALE_DIRNAME)


def _is_adb_entry(entry: dict) -> bool:
    argv = entry.get("argv") or []
    if not argv:
        return False
    return os.path.basename(str(argv[0])).lower() in ("adb", "adb.exe")


def legacy_reason(session: dict) -> str:
    """判断会话是否为 legacy 形态；是则返回原因，否则返回空串。

    判据与 imeituan 0.6.3 的清理校验保持一致：adb 清理条目必须能证明
    "创建时的 ADB Server 身份"，否则清理必失败并保留记录。
    """
    lease = session.get("lease") or {}
    if not str(lease.get("adbServerSocket") or "").strip():
        return "lease.adbServerSocket 缺失（旧版共享 Server 会话）"
    for entry in session.get("cleanupStack") or []:
        if not isinstance(entry, dict) or not _is_adb_entry(entry):
            continue
        meta = entry.get("meta") or {}
        if not str(meta.get("adbServerSocket") or "").strip():
            return f"cleanup 条目 {entry.get('id') or '?'} 缺少 adbServerSocket"
    return ""


def read_session(path: str):
    """读取会话文件；损坏/不可读返回 None（不抛）。"""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def iter_sessions(serial: str = None):
    """遍历会话文件，产出 `(path, session)`；可按 `lease.serial` 过滤。

    只扫描 `sessions/*.json` 顶层（与 CLI 一致），不会递归进入 `.stale/`。
    """
    root = sessions_root()
    if not os.path.isdir(root):
        return
    for path in sorted(glob.glob(os.path.join(root, "*.json"))):
        session = read_session(path)
        if not session:
            continue
        if serial is not None:
            lease = session.get("lease") or {}
            if str(lease.get("serial") or "") != str(serial):
                continue
        yield path, session


def _move_to_stale(path: str, session_id: str, reason: str) -> dict:
    """把会话文件原子移动到 `.stale/`，返回移动记录。"""
    stale = stale_root()
    os.makedirs(stale, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    base = session_id or os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(stale, f"{stamp}-{base}.json")
    suffix = 1
    while os.path.exists(dst):
        dst = os.path.join(stale, f"{stamp}-{suffix}-{base}.json")
        suffix += 1
    os.replace(path, dst)
    return {"session_id": session_id, "from": path, "to": dst, "reason": reason}


def quarantine_legacy(serial: str) -> list:
    """隔离**指定设备串**上的 legacy 会话（移入 `sessions/.stale/`，不删除）。

    Returns:
        list[dict]: 每条为 `{session_id, from, to, reason}`；无命中返回 []。
    """
    moved = []
    if not str(serial or "").strip():
        return moved
    for path, session in list(iter_sessions(serial=serial)):
        reason = legacy_reason(session)
        if not reason:
            continue
        try:
            record = _move_to_stale(path, session.get("sessionId", ""), reason)
        except OSError as e:                       # 移动失败不阻断注册，留痕即可
            soft_fail("infra", "SESSION_QUARANTINE_FAILED", f"{path}: {e}")
            sys.stderr.write(f"[device:session] ⚠️ 隔离 legacy 会话失败（忽略）: {path}: {e}\n")
            continue
        moved.append(record)
        sys.stderr.write(
            f"[device:session] 🧹 已隔离 legacy 会话 {record['session_id'] or path}"
            f" → {os.path.join(STALE_DIRNAME, os.path.basename(record['to']))}"
            f"（{reason}）\n")
    return moved


def quarantine_session(session_id: str, reason: str = "会话不可用") -> dict:
    """按 session_id 隔离单个会话（断开失败时的兜底）；返回移动记录或 None。"""
    sid = str(session_id or "").strip()
    if not sid:
        return None
    for path, session in list(iter_sessions()):
        if str(session.get("sessionId") or "") != sid:
            continue
        try:
            record = _move_to_stale(path, sid, reason)
        except OSError as e:
            soft_fail("infra", "SESSION_QUARANTINE_FAILED", f"{path}: {e}")
            return None
        sys.stderr.write(f"[device:session] 🧹 已隔离会话 {sid}（{reason}）\n")
        return record
    return None
