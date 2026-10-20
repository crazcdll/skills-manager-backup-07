#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备管理命令 — 安装/启动/停止/定位/断开/Shell。

从 locators.py 中拆分出来，对应 CLI 中的 install-app / force-stop / launch / set-location / disconnect / shell 命令。
"""
import time

from shared.errors import DeviceError, UsageError
from shared.case_utils import encode_scheme_payload
from shared.context import get_platform_ops, get_app_descriptor
from devices.toolchain.app_installer import load_apk_config
from provisioning.setup.location import (
    LOCATION_PRESETS as _LOCATION_PRESETS, build_location_action,
    build_location_clear_action,
)


def _cmd_install_app(args):
    """通过 PlatformOps 向设备安装可测性 App。"""
    app = get_app_descriptor()
    apk_url = args.url
    if not apk_url:
        apk_url = load_apk_config(platform=app.platform, form=app.form).get("testability_apk_url")

    if not apk_url:
        raise UsageError("未指定 --url 且 apk_sources.json 中该平台/形态（platform/form）无配置")

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


def _push_location_action(action, ops) -> bool:
    """经**通用可测性 scheme** 推送定位 action。

    与登录前置（`provisioning/setup/login/steps.py::PushLocation`）**同一通道**：
    承载页为 MRN，内容进原生视图树，**不走 Pillow-H5**；两条入口共用
    `provisioning/setup/location` 的 action 构造器，避免通道/格式漂移。
    """
    scheme = get_app_descriptor().testability_scheme_prefix + encode_scheme_payload(action)
    return bool(ops.open_url(scheme))


def _cmd_set_location(args):
    """预设设备 GPS 模拟定位（off = 清除）。"""
    ops = get_platform_ops()
    preset = args.preset
    if preset == "off":
        if _push_location_action(build_location_clear_action(), ops):
            print("SET-LOCATION: ✅ 已关闭模拟定位")
        else:
            print("SET-LOCATION: ⚠️ 关闭模拟定位失败（scheme 推送被拒）")
        return

    if preset not in _LOCATION_PRESETS:
        raise UsageError(f"SET-LOCATION FAIL: 未知预设 '{preset}'，可选: {', '.join(_LOCATION_PRESETS.keys())}, off")

    loc = _LOCATION_PRESETS[preset]
    if not _push_location_action(build_location_action(loc), ops):
        raise DeviceError("SET-LOCATION FAIL: 定位 scheme 推送失败")
    print(f"SET-LOCATION: ✅ 模拟定位已设为{loc['label']} ({loc['lat']}, {loc['lng']})")

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