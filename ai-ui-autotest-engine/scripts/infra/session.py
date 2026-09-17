#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI session 注册与生命周期管理。

在 platform/<platform>/ops.py::register_device() 基础上增加重试逻辑、
日志输出和 session_id 持久化，供 device_lifecycle.py 调用。
"""
import sys

from infra.imeituan_cli import imeituan_disconnect_device, imeituan_location
from device_platform.base import get_platform_module


def imeituan_register(adb_address: str, platform: str = "android", device_type: str = "sandbox") -> dict:
    """注册外部设备到 imeituan CLI session，返回包含 session_id 的结果。

    先断开所有残留 session（防止设备切换时旧 session 干扰），再注册当前设备。
    非致命：失败时返回 {"ok": False, ...}，不应阻断 setup 整体流程。

    具体走云真机注册入口还是本地直连入口，由 get_platform_module(platform)
    .register_device(serial, device_type) 决定——device_type 告知平台模块
    当前设备是 sandbox（云模拟器，需远程连接）还是 local（本地真机，直连），
    各平台按 device_type 选择正确的 imeituan CLI 入口。
    """
    # 1) 断开所有残留 session（静默忽略失败）
    sys.stderr.write("[device:session] 断开残留 session...\n")
    sys.stderr.flush()
    imeituan_disconnect_device(all_sessions=True)

    # 2) 注册当前设备
    sys.stderr.write(f"[device:session] 注册设备 {adb_address} (platform={platform}, timeout=30s)...\n")
    sys.stderr.flush()
    result = get_platform_module(platform).register_device(adb_address, device_type)
    if result["ok"] and result.get("session_id"):
        sys.stderr.write(f"[device:session] ✅ session 创建成功: {result['session_id']}\n")
    elif result["ok"]:
        sys.stderr.write("[device:session] ⚠️ register 成功但未返回 session_id，CLI 契约异常\n")
        result["ok"] = False
        result["detail"] = "register 成功但未返回 session_id"
    else:
        sys.stderr.write(f"[device:session] ⚠️ session 创建失败: {result['detail']}\n")
    return result


def imeituan_disconnect(session_id: str = None) -> dict:
    """断开 imeituan CLI session，触发 LIFO 清理栈。

    优先使用 session_id 精确断开；未提供时用 --all 断开所有 session。
    非致命：失败时返回 {"ok": False, ...}，不应阻断 destroy/cleanup 流程。
    """
    if session_id:
        sys.stderr.write(f"[device:session] 断开 session {session_id}...\n")
        return imeituan_disconnect_device(session_id=session_id)
    else:
        sys.stderr.write("[device:session] 断开所有 session...\n")
        return imeituan_disconnect_device(all_sessions=True)


def imeituan_location_off() -> dict:
    """关闭模拟定位（GPS mock 是系统级设置，pm clear 不会清除）。

    异常恢复场景专用：设备即将 destroy 前，如果之前 set-location 开启过
    模拟定位，理论上会随实例销毁一起清除；但如果异常恢复流程选择保留实例
    仅重置环境（不销毁），就需要主动关闭，避免定位状态残留到下次复用。

    非致命：失败时返回 {"ok": False, ...}，不应阻断整体清理流程。
    """
    try:
        r = imeituan_location(clear=True)
        ok = r.returncode == 0
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return {"ok": ok, "detail": out[:200]}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:200]}
