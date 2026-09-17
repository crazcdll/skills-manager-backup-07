#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可测性 App 版本探测 + 按需安装/升级（编排层）。

设备操作已收敛到 PlatformOps，安装机制已收敛到 DeviceLifecycle，
本模块仅负责编排逻辑：版本比对、安装策略、重试验证。

核心能力：
    load_apk_config(platform)        — 读取 references/apk_sources.json 对应平台的目标版本
    check_version(ops)               — 通过 PlatformOps 探测设备当前安装的版本
    ensure_app_installed()           — 探测 + 按需安装/升级（版本不符即卸载重装），
                                        供 sandbox 云模拟器（一次性环境）使用
    ensure_app_installed_if_missing() — 仅在完全未安装时才安装，已安装（任意版本）
                                        直接复用，供本地真机（不允许自动卸载/升级）使用

包名统一以 AppDescriptor.package_name 为准，apk_sources.json 中的 package
字段仅作交叉展示，避免包名硬编码在两处导致探测串包。

安装耗时按平台差异较大，通过返回结构体的 notice 字段传递耗时提示（而非只依赖
可能被忽略的 stderr 日志），调用方必须将 notice 转述给用户，不能静默等待。
"""
import json
import os
import sys
import time

from core.util.json_utils import read_json
from core.util.paths import SKILL_DIR, REFERENCES_DIR
from device_platform.base import PlatformOps, DeviceLifecycle
from context import get_app_descriptor

_APK_SOURCES_PATH = os.path.join(REFERENCES_DIR, "apk_sources.json")
_FALLBACK_TESTABILITY_APK_URL = (
    "https://hyperloop-s3.sankuai.com/hpx-artifacts/"
    "5440930-973-1781175373969276/aimeituan-release_12.59.200-545701-aarch64.apk"
)

# 各平台安装耗时预估（真机验证经验值），用于生成用户可读的耗时提示。
# HarmonyOS 走「打开企业安装页 + 点击下载 + 点击系统安装确认」的 UI
# 自动化流程（见 platform/harmony/ops.py::HarmonyOps.install_app），安装包
# 由系统在后台下载，功能测试包体积明显大于 Android APK，全流程比 Android
# 明显更长。
_INSTALL_ETA_HINT = {
    "android": "预计约 1-2 分钟",
    "harmony": "预计约 2-3 分钟（HarmonyOS 功能测试包体积较大，系统会在后台自动下载，请耐心等待，安装过程中请勿拔断设备连接）",
}

def load_apk_config(platform: str = "android") -> dict:
    """读取 references/apk_sources.json 中 meituan 对应 platform 分支的目标版本配置。

    Android/Harmony 是完全独立发布的安装包（不同格式、不同版本号节奏），
    因此按 platform 分层存储；旧版本扁平结构（meituan 直接是配置对象，无
    android/harmony 子节点）在 android 分支下兼容读取，避免破坏现有配置。

    读取失败或目标平台节点缺失时返回内置的兜底配置（version 置空，调用方据此
    判断无法比对版本，只能强制重装；harmony 目前无内置兜底安装包地址）。
    """
    try:
        cfg = read_json(_APK_SOURCES_PATH, default={})
        meituan = cfg.get("meituan") or {}
        platform_cfg = meituan.get(platform)
        if not isinstance(platform_cfg, dict) and platform == "android":
            platform_cfg = meituan  # 兼容旧版本扁平结构
        if isinstance(platform_cfg, dict) and platform_cfg.get("testability_apk_url"):
            sys.stderr.write(
                f"[device:install] 目标可测性安装包版本（{platform}）: {platform_cfg.get('version', '未知')}"
                f"（来源: apk_sources.json，更新于 {platform_cfg.get('updated', '未知')}）\n"
            )
            return platform_cfg
    except Exception as e:
        sys.stderr.write(f"[device:install] 读取 apk_sources.json 失败（{e}），回退到内置固定版本\n")
    fallback = {"version": None}
    if platform == "android":
        fallback["testability_apk_url"] = _FALLBACK_TESTABILITY_APK_URL
    return fallback

def check_version(ops: PlatformOps) -> dict:
    """独立的版本探测接口，返回结构化结果，供 CLI check-version 子命令使用。

    包名取自 get_app_descriptor()（已按 flow-context.json 的 meta.platform
    分派到正确的 AppDescriptor 子类），apk_sources.json 只提供目标版本/安装包
    地址，按同一 platform 读取对应分支。
    """
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    apk_cfg = load_apk_config(platform=app_desc.platform)
    ver = ops.get_installed_version(package)
    target_version = apk_cfg.get("version")

    if not ver["installed"]:
        needs_update = True
        reason = "未安装"
    elif target_version is None:
        needs_update = True
        reason = "无法读取目标版本配置，无法比对，建议重装"
    elif ver["versionName"] != target_version:
        needs_update = True
        reason = f"版本不一致（当前 {ver['versionName']} vs 目标 {target_version}）"
    else:
        needs_update = False
        reason = "已是目标版本"

    return {
        "installed": ver["installed"],
        "currentVersion": ver["versionName"],
        "currentVersionCode": ver["versionCode"],
        "targetVersion": target_version,
        "needsUpdate": needs_update,
        "reason": reason,
    }

def verify_install(ops: PlatformOps, package: str = None, retries: int = 24, interval: float = 3.0) -> bool:
    if package is None:
        package = get_app_descriptor().package_name
    sys.stderr.write(f"[device:install] 开始验证安装（每 {interval:.0f}s 检查，最多 {retries} 次）...\n")
    sys.stderr.flush()
    for i in range(retries):
        sys.stderr.write(f"[device:install] 等待安装 {i + 1}/{retries}...\n")
        sys.stderr.flush()
        time.sleep(interval)
        if ops.is_package_installed(package):
            sys.stderr.write(f"[device:install] ✅ APK 安装确认完成（第 {i + 1} 次检查）\n")
            return True
    return False

def ensure_app_installed(ops: PlatformOps, device_lifecycle: DeviceLifecycle,
                         device_id: str = None, force: bool = False) -> dict:
    """探测当前版本，仅在未安装或版本不一致时才执行 卸载+安装，否则跳过。

    Args:
        ops: PlatformOps 实例（设备操作通过 ops 委托）
        device_lifecycle: DeviceLifecycle 实例（安装机制通过 lifecycle 委托）
        device_id: 设备特定标识（sandbox: sandbox_id，local: 忽略）
        force: 强制重装，忽略版本比对结果

    Returns:
        { skipped: bool, versionCheck: {...}, steps: [...] }
    """
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    apk_cfg = load_apk_config(platform=app_desc.platform)
    version_check = check_version(ops)
    steps = []

    if not force and not version_check["needsUpdate"]:
        sys.stderr.write(
            f"[device:install] 已是目标版本 {version_check['currentVersion']}，跳过卸载重装\n"
        )
        return {"skipped": True, "versionCheck": version_check, "steps": steps}

    # 需要安装/升级：卸载旧包（未安装时该步骤是空操作，不影响后续）
    sys.stderr.write(f"[device:install] 卸载旧版本 {package}...\n")
    uninstalled = ops.uninstall_app(package)
    steps.append({"step": "uninstall_official", "ok": uninstalled})

    apk_url = apk_cfg.get("testability_apk_url", _FALLBACK_TESTABILITY_APK_URL)
    sys.stderr.write("[device:install] 安装可测性 APK（约 60-120s）...\n")
    install_ok = False
    install_err = None
    for install_attempt in range(2):  # 最多尝试 2 次
        try:
            if install_attempt > 0:
                sys.stderr.write(f"[device:install] 第 {install_attempt + 1} 次尝试安装...\n")
                time.sleep(3)
            device_lifecycle.install_app(ops, apk_url, device_id)
            install_ok = True
            break
        except Exception as e:
            install_err = str(e)
            sys.stderr.write(f"[device:install] 安装失败（第 {install_attempt + 1} 次）: {e}\n")

    steps.append({"step": "install_testability_apk", "ok": install_ok})
    if not install_ok:
        return {"skipped": False, "versionCheck": version_check, "steps": steps, "error": f"安装 APK 失败（重试后仍失败）: {install_err}"}

    installed_ok = verify_install(ops, package)
    if not installed_ok:
        # verify_install 失败时重试一次安装
        sys.stderr.write("[device:install] 安装后未检测到包，重试一次安装...\n")
        try:
            device_lifecycle.install_app(ops, apk_url, device_id)
        except Exception:
            pass
        installed_ok = verify_install(ops, package)
    steps.append({"step": "verify_install", "ok": installed_ok})
    if not installed_ok:
        return {"skipped": False, "versionCheck": version_check, "steps": steps, "error": "APK 安装后未检测到包（重试后仍失败）"}

    return {"skipped": False, "versionCheck": version_check, "steps": steps}


def ensure_app_installed_if_missing(ops: PlatformOps, device_lifecycle: DeviceLifecycle,
                                    device_id: str = None) -> dict:
    """本地真机专用：仅在完全未安装目标 App 时才执行安装，已安装（任意版本）
    一律直接复用，不做任何卸载/升级动作。

    与 ensure_app_installed() 的核心差异——不比对版本、不卸载：
    本地真机是用户自己的手机，已安装的正式包/测试包可能承载着用户的真实
    使用数据（登录态、缓存等），版本落后也不应该被自动覆盖；只有"设备上
    压根没有这个包"这种确定性场景才自动补装，避免流程因为环境缺失直接卡死。

    Args:
        ops: PlatformOps 实例
        device_lifecycle: DeviceLifecycle 实例（安装机制通过 lifecycle 委托）
        device_id: 设备特定标识（本地真机场景恒为 None，占位保持接口一致）

    Returns:
        { skipped: bool, alreadyInstalled: bool, versionCheck: {...},
          steps: [...], notice: str|None, error: str（仅失败时） }
        notice 字段是给用户看的强提示文案（如预计安装耗时），调用方必须
        转述给用户，不能只当作可忽略的日志。
    """
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    platform = app_desc.platform
    apk_cfg = load_apk_config(platform=platform)
    version_check = check_version(ops)
    steps = []

    if version_check["installed"]:
        sys.stderr.write(
            f"[device:install] ✅ 设备已安装 {package}（当前版本 {version_check['currentVersion']}），"
            f"本地真机场景直接复用现有安装，不做卸载/升级\n"
        )
        return {
            "skipped": True, "alreadyInstalled": True,
            "versionCheck": version_check, "steps": steps, "notice": None,
        }

    apk_url = apk_cfg.get("testability_apk_url")
    if not apk_url:
        return {
            "skipped": False, "alreadyInstalled": False, "versionCheck": version_check,
            "steps": steps,
            "error": f"设备未安装 {package}，且 apk_sources.json 中 {platform} 平台缺少 testability_apk_url 配置，无法自动安装",
        }

    eta_hint = _INSTALL_ETA_HINT.get(platform, "预计约 1-2 分钟")
    notice = (
        f"⚠️ 重要提示：设备未安装可测性测试包（{package}），即将自动安装 {eta_hint}。"
        f"请保持设备与电脑的连接稳定，不要在安装过程中拔断数据线或锁屏。"
        f"安装完成后首次启动可能出现系统级信任/权限弹窗，需要用户手动确认后才能继续。"
    )
    sys.stderr.write(f"\n{'='*70}\n[device:install] {notice}\n{'='*70}\n")
    sys.stderr.flush()

    install_ok = False
    install_err = None
    for install_attempt in range(2):  # 最多尝试 2 次
        try:
            if install_attempt > 0:
                sys.stderr.write(f"[device:install] 第 {install_attempt + 1} 次尝试安装...\n")
                time.sleep(3)
            device_lifecycle.install_app(ops, apk_url, device_id)
            install_ok = True
            break
        except Exception as e:
            install_err = str(e)
            sys.stderr.write(f"[device:install] 安装失败（第 {install_attempt + 1} 次）: {e}\n")

    steps.append({"step": "install_testability_apk", "ok": install_ok})
    if not install_ok:
        return {
            "skipped": False, "alreadyInstalled": False, "versionCheck": version_check,
            "steps": steps, "notice": notice,
            "error": f"安装 APK 失败（重试后仍失败）: {install_err}",
        }

    # device_lifecycle.install_app() 是同步阻塞调用（Android: adb/imeituan install；
    # HarmonyOS: 打开企业安装页 + 点击下载 + 点击系统安装确认，触发动作已在其内部
    # 完成），verify_install 只是确认设备端状态已生效。重试上限由各平台模块自行
    # 声明（见 platform/<platform>/ops.py::INSTALL_VERIFY_RETRIES），本函数
    # 不感知具体平台差异。
    from device_platform.base import get_platform_module
    verify_retries = get_platform_module(platform).INSTALL_VERIFY_RETRIES
    installed_ok = verify_install(ops, package, retries=verify_retries)
    if not installed_ok:
        sys.stderr.write("[device:install] 安装后未检测到包，重试一次安装...\n")
        try:
            device_lifecycle.install_app(ops, apk_url, device_id)
        except Exception:
            pass
        installed_ok = verify_install(ops, package, retries=verify_retries)
    steps.append({"step": "verify_install", "ok": installed_ok})
    if not installed_ok:
        return {
            "skipped": False, "alreadyInstalled": False, "versionCheck": version_check,
            "steps": steps, "notice": notice,
            "error": "APK 安装后未检测到包（重试后仍失败）",
        }

    return {
        "skipped": False, "alreadyInstalled": False, "freshInstall": True,
        "versionCheck": version_check, "steps": steps, "notice": notice,
    }
