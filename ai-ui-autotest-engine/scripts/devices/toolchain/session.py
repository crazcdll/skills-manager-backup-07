#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI session 注册与生命周期管理。

在 devices/<platform>/ops.py::register_device() 基础上增加重试逻辑、
日志输出和 session_id 持久化，供 device_commands.py 调用。
"""
import sys

from devices.toolchain.imeituan_cli import (
    bind_session, imeituan_set_package, set_session_reestablisher,
)
from devices.base import get_platform_module
from shared.errors import soft_fail


def imeituan_register(adb_address: str, platform: str = "android", device_type: str = "sandbox",
                      remote_address: str = None) -> dict:
    """注册外部设备到 imeituan CLI session，返回包含 session_id 的结果。

    【会话可用性契约】注册成功后本函数负责把新会话置为"立即可用"，包括两件事：
      1. `bind_session` —— 本进程后续设备命令路由到本 run 的设备；
      2. `_select_session_package` —— 选中目标 App 包。
    第 2 件事不能留给调用方：imeituan 的 App 层命令（`control auth status`、
    `device open-url` …）都按 session 里选中的包路由，而**任何一次重新注册都会清空
    该选择**（表现为 `尚未选择 package-id`）。因此凡走本入口重建会话，绑定必须随之重建，
    否则会出现"设备已注册、App 层命令全部失效"的隐形断链。

    **不做全量断会话**：`disconnect --all` 会把并发 run 的会话一并踢掉（并发串台根源），已移除。

    非致命：失败时返回 {"ok": False, ...}，不应阻断 setup 整体流程。

    具体走哪个连接入口，由 get_platform_module(platform).register_device(
    serial, device_type, remote_address) 决定。
    """
    sys.stderr.write(f"[device:session] 注册设备 {adb_address} (platform={platform}, timeout=30s)...\n")
    sys.stderr.flush()
    result = get_platform_module(platform).register_device(adb_address, device_type, remote_address)
    if result["ok"] and result.get("session_id"):
        bind_session(result["session_id"])
        _select_session_package()
        _arm_reestablisher(adb_address, platform, device_type, remote_address)
        sys.stderr.write(f"[device:session] ✅ session 创建成功: {result['session_id']}"
                         f"（已绑定本 run，后续设备命令路由到该会话）\n")
    elif result["ok"]:
        sys.stderr.write("[device:session] ⚠️ register 成功但未返回 session_id，CLI 契约异常\n")
        result["ok"] = False
        result["detail"] = "register 成功但未返回 session_id"
    else:
        sys.stderr.write(f"[device:session] ⚠️ session 创建失败: {result['detail']}\n")
    return result


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
