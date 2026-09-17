#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备管理命令 — 安装/启动/停止/定位/断开/Shell。

从 locators.py 中拆分出来，对应 CLI 中的 install-app / force-stop / launch / set-location / disconnect / shell 命令。
"""
import json
import os
import time

from core.errors import DeviceError, UsageError, soft_fail
from context import get_platform_ops, get_app_descriptor
from infra.imeituan_cli import imeituan_location
from environment.setup.location import LOCATION_PRESETS as _LOCATION_PRESETS
from core.util.paths import REFERENCES_DIR


def _load_apk_sources():
    """读取 references/apk_sources.json 返回 dict。"""
    apk_json = os.path.join(REFERENCES_DIR, "apk_sources.json")
    if os.path.isfile(apk_json):
        try:
            with open(apk_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            soft_fail("infra", "APK_SOURCES_UNREADABLE", e)
    return {}


def _cmd_install_app(args):
    """通过 PlatformOps 向设备安装可测性 App。"""
    apk_url = args.url
    if not apk_url:
        apk_config = _load_apk_sources()
        apk_url = apk_config.get("meituan", {}).get("testability_apk_url")

    if not apk_url:
        raise UsageError("未指定 --url 且 references/apk_sources.json 中无配置")

    app = get_app_descriptor()
    pkg = app.package_name
    print(f"INSTALL-APP: 开始安装 {apk_url}")
    ops = get_platform_ops()

    ops.uninstall_app(pkg)
    try:
        install_ok = ops.install_app(apk_url, timeout=args.timeout)
    except Exception as e:
        raise DeviceError(f"INSTALL-APP FAIL: {e}") from e
    if not install_ok:
        raise DeviceError("INSTALL-APP FAIL: 安装命令执行失败")

    print(f"INSTALL-APP OK")
    time.sleep(2)

    if not ops.is_package_installed(pkg):
        raise DeviceError("INSTALL-APP VERIFY FAIL: 包未检测到")

    print(f"INSTALL-APP VERIFY OK: package:{pkg}")

    ver_info = ops.get_installed_version(pkg)
    ver = ver_info.get("versionName") or "unknown"
    print(f"INSTALL-APP VERSION: {ver}")


def _cmd_force_stop(args):
    """强制关闭 App（am force-stop）。"""
    ops = get_platform_ops()
    pkg = args.package or get_app_descriptor().package_name
    ok = ops.force_stop(pkg)
    if ok:
        ops.press_home()
        print(f"FORCE-STOP OK: {pkg} (已回到桌面)")
    else:
        raise DeviceError(f"FORCE-STOP FAIL: {pkg}")


def _cmd_launch(args):
    """启动 App 到首页。"""
    ops = get_platform_ops()
    app = get_app_descriptor()
    pkg = args.package or app.package_name
    wait_sec = args.wait
    activity = args.activity or app.main_activity_class

    ok = ops.launch_app(f"{pkg}/{activity}")
    if not ok:
        raise DeviceError(f"LAUNCH FAIL: {pkg}/{activity}")

    print(f"LAUNCH OK: {pkg}/{activity}")

    if wait_sec > 0:
        time.sleep(wait_sec)

    focus = ops.check_foreground()
    if pkg in focus:
        print(f"LAUNCH VERIFY: {pkg} 已在前台")
    else:
        print(f"LAUNCH WARN: {pkg} 可能不在前台（焦点窗口: {focus}），请截图确认")


def _cmd_set_location(args):
    """预设设备 GPS 模拟定位。"""
    ops = get_platform_ops()
    preset = args.preset
    if preset == "off":
        r = imeituan_location(clear=True)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode == 0:
            print(f"SET-LOCATION: ✅ 已关闭模拟定位")
        else:
            print(f"SET-LOCATION: ⚠️ 关闭模拟定位失败: {out[:200]}")
        return

    if preset not in _LOCATION_PRESETS:
        raise UsageError(f"SET-LOCATION FAIL: 未知预设 '{preset}'，可选: {', '.join(_LOCATION_PRESETS.keys())}, off")

    loc = _LOCATION_PRESETS[preset]
    r = imeituan_location(lat=loc["lat"], lng=loc["lng"])
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode == 0:
        print(f"SET-LOCATION: ✅ 模拟定位已设为{loc['label']} ({loc['lat']}, {loc['lng']})")
    else:
        raise DeviceError(f"SET-LOCATION FAIL: 设置模拟定位失败: {out[:200]}")

    time.sleep(2)
    app = get_app_descriptor()
    if not ops.launch_app(app.main_activity, launcher_intent=True):
        print("SET-LOCATION: ⚠️ 跳回主页失败")
    else:
        time.sleep(1)
        print("SET-LOCATION: 已跳回主页")


def _cmd_disconnect(args):
    """断开设备连接。"""
    ops = get_platform_ops()
    ok = ops.disconnect()
    if ok:
        print(f"DISCONNECT OK: {ops.serial}")
    else:
        raise DeviceError(f"DISCONNECT FAIL: {ops.serial}")


def _cmd_shell(args):
    """执行设备 Shell 命令。"""
    ops = get_platform_ops()
    r = ops.shell(*args.shell_cmd)
    out = ((r.stdout or "") + (r.stderr or ""))
    print(out.rstrip())
    return r.returncode