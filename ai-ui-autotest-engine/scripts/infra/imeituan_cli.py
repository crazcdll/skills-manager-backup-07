#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI 设备交互层。

通过 imeituan CLI 执行设备操作，CLI 内部通过 Session 机制路由到
AdbAdapter（Android）/ XcrunAdapter（iOS）/ HdcAdapter（Harmony）。

Session 在 setup 阶段由 device register 创建并持久化到 flow-context.json，
后续所有 device shell / device input 等命令自动路由到活跃 session 对应的 Adapter。
"""
import json
import os
import re
import subprocess

from core.errors import soft_fail
from infra.node_env import imeituan_run


def _run(args, timeout=30):
    """执行 imeituan CLI 命令，返回原始 CompletedProcess。"""
    try:
        return imeituan_run(list(args), capture=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=list(args), returncode=1, stdout="",
            stderr=f"TIMEOUT after {e.timeout}s")


def _parse_json(r):
    """解析 CLI 输出的 JSON，返回 payload 或 None。"""
    raw = (r.stdout or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _unwrap(r):
    """解析 JSON envelope，提取 stdout/stderr/returncode。

    成功时 data 中的 stdout/stderr/exitCode 覆盖原始值；
    失败时 returncode=1、stderr=error.message；
    非 envelope 格式原样返回。
    """
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return r
    if payload.get("code") == 0:
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return r
        return subprocess.CompletedProcess(
            args=r.args,
            returncode=data.get("exitCode", 0),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
        )
    return subprocess.CompletedProcess(
        args=r.args,
        returncode=1,
        stdout="",
        stderr=payload.get("error", {}).get("message", ""),
    )


def _success(r):
    """判断 CLI 命令是否成功（envelope code == 0 或非 JSON 时 subprocess returncode == 0）。"""
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return r.returncode == 0
    return payload.get("code") == 0


# ═══════════════════════════════════════════════════════════
# 设备操作（依赖活跃 session）
# ═══════════════════════════════════════════════════════════

def imeituan_shell(*shell_args, timeout=30):
    """在设备上执行 shell 命令，返回 CompletedProcess。"""
    args = ["device", "shell", "--", *shell_args]
    return _unwrap(_run(args, timeout=timeout))


def imeituan_input(action, timeout=30, **kwargs):
    """设备输入操作（tap/swipe/text）。"""
    cmd = ["device", "input", action]
    for k, v in kwargs.items():
        cmd += ["--" + k.replace("_", "-"), str(v)]
    return _unwrap(_run(cmd, timeout=timeout))


def imeituan_open_url(url, timeout=15):
    """在设备上打开 URL/scheme。

    package 已在 device setup 阶段通过 `imeituan device set-package <package-id>` 设置，
    open-url 不再需要 --package-id 参数。
    """
    return _unwrap(_run(["device", "open-url", url], timeout=timeout))


def imeituan_install(apk_path, timeout=300):
    """向设备安装 APK。"""
    return _unwrap(_run(["device", "install", apk_path, "--timeout", str(timeout)],
                        timeout=timeout + 30))


def imeituan_screenshot(output_path, timeout=30):
    """截图保存到指定路径，返回是否成功。"""
    r = _run(["device", "screenshot", "-o", output_path], timeout=timeout)
    return _success(r) and os.path.isfile(output_path)


def imeituan_screen_size(default=(1080, 2340), timeout=10):
    """获取设备屏幕分辨率 (width, height)。"""
    try:
        r = imeituan_shell("wm", "size", timeout=timeout)
        m = re.search(r'(\d+)x(\d+)', r.stdout or "")
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception as e:
        soft_fail("device", "SCREEN_SIZE_PROBE_FAILED", e)
    return default


def imeituan_alive(timeout=10):
    """轻量级设备连通性检查。"""
    try:
        r = imeituan_shell("echo", "alive", timeout=timeout)
        return r.returncode == 0 and "alive" in ((r.stdout or "") + (r.stderr or ""))
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# Control 命令（感知 & 定位）
# ═══════════════════════════════════════════════════════════

def imeituan_inspect_tree(output_path, cli_timeout=30, subprocess_timeout=None):
    """获取设备视图树 JSON，输出到指定文件路径。"""
    timeout = subprocess_timeout or (cli_timeout + 15)
    r = _run(["control", "inspect-tree", "--timeout", str(cli_timeout),
              "-o", output_path], timeout=timeout)
    ok = _success(r)
    return subprocess.CompletedProcess(args=r.args, returncode=0 if ok else 1,
                                       stdout=r.stdout, stderr=r.stderr)


def imeituan_location(*, clear=False, lat=None, lng=None, timeout=15):
    """设置或清除设备模拟定位。"""
    args = ["control", "location"]
    if clear:
        args.append("--clear")
    elif lat is not None and lng is not None:
        args += ["--lat", str(lat), "--lng", str(lng)]
    else:
        raise ValueError("Either clear=True or both lat and lng must be provided")
    return _unwrap(_run(args, timeout=timeout))


# ═══════════════════════════════════════════════════════════
# 通用 CLI 执行（供 appmock 等模块使用）
# ═══════════════════════════════════════════════════════════

def imeituan_exec(args, timeout=30):
    """执行 imeituan CLI 命令，返回原始 CompletedProcess。"""
    return _run(args, timeout=timeout)


# ═══════════════════════════════════════════════════════════
# Session 管理命令
# ═══════════════════════════════════════════════════════════

def imeituan_register_device(serial, platform="android"):
    """注册外部设备到 CLI session，返回 {ok, session_id, detail}。

    仅适用于云真机场景：`device register` 会把 --remote-address 当网络
    地址发起连接探测，本地 USB 直连设备的 serial 不是 ip:port 网络地址，
    会导致 Harmony 分支报错。本地真机请改用 imeituan_connect_local_device()。
    """
    r = _run(["device", "register", "-p", platform,
              "--serial", serial, "--remote-address", serial,
              "--force"], timeout=30)
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return {"ok": False, "detail": (r.stderr or "未知错误")[:200]}

    if payload.get("code") != 0:
        return {"ok": False, "detail": payload.get("error", {}).get("message", "")[:200]}

    sid = payload.get("data", {}).get("sessionId", "")
    if sid:
        return {"ok": True, "session_id": sid, "detail": ""}
    return {"ok": False, "detail": "register 成功但未返回 session_id"}


def imeituan_connect_local_emulator(serial, platform="ios"):
    """连接本地模拟器并创建 CLI session，返回 {ok, session_id, detail}。

    对应 `imeituan device connect --target local-emulator`，适用于本地启动的 iOS / Android 模拟器。
    """
    r = _run(["device", "connect", "--target", "local-emulator", "-p", platform,
              "--serial", serial, "--force"], timeout=30)
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return {"ok": False, "detail": (r.stderr or "未知错误")[:200]}

    if payload.get("code") != 0:
        return {"ok": False, "detail": payload.get("error", {}).get("message", "")[:200]}

    sid = payload.get("data", {}).get("sessionId", "")
    if sid:
        return {"ok": True, "session_id": sid, "detail": ""}
    return {"ok": False, "detail": "connect 成功但未返回 session_id"}


def imeituan_connect_local_device(serial, platform="harmony"):
    """连接本地已物理连接的真机并创建 CLI session，返回 {ok, session_id, detail}。

    对应 `imeituan device connect --target local-device`，会跳过网络连接
    探测，是本地 USB/HDC 直连设备的正确入口（区别于面向云真机的 device register）。
    """
    r = _run(["device", "connect", "--target", "local-device", "-p", platform,
              "--serial", serial, "--force"], timeout=30)
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return {"ok": False, "detail": (r.stderr or "未知错误")[:200]}

    if payload.get("code") != 0:
        return {"ok": False, "detail": payload.get("error", {}).get("message", "")[:200]}

    sid = payload.get("data", {}).get("sessionId", "")
    if sid:
        return {"ok": True, "session_id": sid, "detail": ""}
    return {"ok": False, "detail": "connect 成功但未返回 session_id"}




def imeituan_disconnect_device(session_id=None, all_sessions=False):
    """断开 CLI session，返回 {ok, detail}。"""
    args = ["device", "disconnect"]
    if all_sessions:
        args.append("--all")
    elif session_id:
        args += ["--session", session_id]

    r = _run(args, timeout=15)
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return {"ok": r.returncode == 0, "detail": (r.stderr or "")[:200]}

    if payload.get("code") == 0:
        return {"ok": True, "detail": ""}
    return {"ok": False, "detail": payload.get("error", {}).get("message", "")[:200]}
