#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI session 注册与生命周期管理。

在 devices/<platform>/ops.py::register_device() 基础上增加：

  · **注册前隔离**：把本设备串上的 legacy 会话移入 `sessions/.stale/`（见 session_store）；
  · 重试策略数据化：结果携带 `code` / `retryable`，由调用方决定是否重试；
  · 会话收尾：`disconnect_session()` 断开本 run 的会话，legacy 则隔离后视为已收尾；
  · session_id 持久化与失效重建（reestablisher）。

设计约束：本模块只做**会话生命周期**，不判断"要不要重试几次"（那属于设备编排层）。
"""
import re
import sys

from devices.toolchain.imeituan_cli import (
    bind_session, imeituan_disconnect_device, imeituan_set_package,
    set_session_reestablisher,
)
from devices.toolchain.session_store import quarantine_legacy, quarantine_session
from devices.base import get_platform_module
from shared.errors import soft_fail

_SESSION_ID_RE = re.compile(r"(sess-[0-9a-fA-F]{4,})")


def imeituan_register(adb_address: str, platform: str = "android", device_type: str = "sandbox",
                      remote_address: str = None) -> dict:
    """注册外部设备到 imeituan CLI session，返回结构化结果。

    【会话可用性契约】注册成功后本函数负责把新会话置为"立即可用"，包括两件事：
      1. `bind_session` —— 本进程后续设备命令路由到本 run 的设备；
      2. `_select_session_package` —— 选中目标 App 包。
    第 2 件事不能留给调用方：imeituan 的 App 层命令（`control auth status`、
    `device open-url` …）都按 session 里选中的包路由，而**任何一次重新注册都会清空
    该选择**（表现为 `尚未选择 package-id`）。因此凡走本入口重建会话，绑定必须随之重建，
    否则会出现"设备已注册、App 层命令全部失效"的隐形断链。

    【注册前隔离】同一设备串上的 legacy 会话在 0.6.3 上是确定性不可用（清理必失败且
    retain-session），注册前统一移入 `.stale/`，避免"3 次盲重试撞同一堵墙"。

    **不做全量断会话**：`disconnect --all` 会把并发 run 的会话一并踢掉（并发串台根源），已移除。

    失败时返回 `{ok: False, code, retryable, detail}`，由编排层决定重试/终止。
    """
    moved = quarantine_legacy(adb_address)
    if moved:
        sys.stderr.write(
            f"[device:session] 注册前已隔离 {len(moved)} 个 legacy 会话（本设备串）\n")

    sys.stderr.write(f"[device:session] 注册设备 {adb_address} (platform={platform}, timeout=30s)...\n")
    sys.stderr.flush()
    result = get_platform_module(platform).register_device(adb_address, device_type, remote_address)
    if result.get("ok") and result.get("session_id"):
        bind_session(result["session_id"])
        _select_session_package()
        _arm_reestablisher(adb_address, platform, device_type, remote_address)
        sys.stderr.write(f"[device:session] ✅ session 创建成功: {result['session_id']}"
                         f"（已绑定本 run，后续设备命令路由到该会话）\n")
    elif result.get("ok"):
        sys.stderr.write("[device:session] ⚠️ register 成功但未返回 session_id，CLI 契约异常\n")
        result.update({"ok": False, "code": "SESSION_ID_MISSING",
                       "retryable": True, "detail": "register 成功但未返回 session_id"})
    else:
        sys.stderr.write(f"[device:session] ⚠️ session 创建失败[{result.get('code') or '?'}]: "
                         f"{result.get('detail') or '未知错误'}\n")
    return result


def remediate_failed_session(detail: str) -> dict:
    """隔离"注册失败信息里点名的那个会话"（legacy 清理卡死时的定向修复）。

    imeituan 在清理失败时会把 sessionId 放在错误首行（`sess-xxxx\\ntransport-disconnect…`）。
    这里只按 id 精确隔离，不猜测、不批量删除；返回 `{quarantined, session_id}`。
    """
    m = _SESSION_ID_RE.search(str(detail or ""))
    session_id = m.group(1) if m else ""
    record = quarantine_session(session_id, "注册失败：legacy 会话清理卡死") if session_id else None
    return {"session_id": session_id, "quarantined": record}


def disconnect_session(session_id: str) -> dict:
    """收尾断开本 run 的会话；legacy/迁移类确定性失败视为"已收尾"（隔离后返回 ok）。

    返回 `{ok, code, detail, quarantined}`：
      · ok=True  → 会话已断开，或已隔离（不再占用 CLI 的会话表）；
      · ok=False → 瞬态失败（可留待下次收尾重试）。
    """
    sid = str(session_id or "").strip()
    if not sid:
        return {"ok": True, "code": "", "detail": "无会话可断开", "quarantined": None}

    result = imeituan_disconnect_device(sid)
    if result.get("ok"):
        return {**result, "quarantined": None}

    # 会话已不存在 = 已经收尾（幂等）：不要让收尾序列报失败。
    if result.get("code") == "SESSION_NOT_FOUND":
        return {"ok": True, "code": "SESSION_NOT_FOUND",
                "detail": result.get("detail"), "quarantined": None}

    if not result.get("retryable"):
        # 确定性失败：该会话在 CLI 侧已经不可用，隔离后等价于"已断开"。
        record = quarantine_session(sid, f"断开失败[{result.get('code')}]，会话已不可用")
        return {"ok": True, "code": result.get("code"),
                "detail": result.get("detail"), "quarantined": record}
    return {**result, "quarantined": None}


def _arm_reestablisher(adb_address: str, platform: str, device_type: str,
                       remote_address: str = None) -> None:
    """把「用同一设备信息重建会话」的能力交给 imeituan_cli。

    会话是进程外的跨命令资源，长流程（device setup / 登录）中途可能失效；失效时
    `imeituan_cli._run` 会回调本函数重建（含 bind_session + set-package，与首次注册
    同一路径，保证 App 层命令路由不丢）并重试一次。注入设备信息是因为只有本入口知道
    serial/platform/device_type/remote。
    """

    def _reestablish() -> bool:
        res = imeituan_register(adb_address, platform=platform,
                               device_type=device_type, remote_address=remote_address)
        return bool(res.get("ok"))

    set_session_reestablisher(_reestablish)


def _select_session_package(package: str = None) -> bool:
    """为新会话选中目标 App 包（包名来自 AppDescriptor，按 meta.platform 已解析）。

    失败不抛出：会话本身已可用，仅 App 层命令会报未选中包并给出明确指引，
    因此记录 soft_fail 后继续（与"注册失败不阻断 setup"的容错策略一致）。
    """
    try:
        from shared.context import get_app_descriptor

        pkg = package or get_app_descriptor().package_name
        sys.stderr.write(f"[device:session] 选中 session 目标包: {pkg}...\n")
        imeituan_set_package(pkg)
        return True
    except Exception as e:  # noqa: BLE001 —— 不阻断注册，只影响 App 层命令
        soft_fail("infra", "SESSION_SELECT_PACKAGE_FAILED", e)
        sys.stderr.write(f"[device:session] ⚠️ 选中目标包失败（App 层命令会报未选择 package-id）: {e}\n")
        return False
