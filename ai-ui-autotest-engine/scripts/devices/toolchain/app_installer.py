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

from shared.json_utils import read_json
from shared.paths import SKILL_DIR, REFERENCES_DIR
from devices.base import PlatformOps, DeviceLifecycle
from devices.interfaces.artifact_spec import (
    ArtifactSpec, BuildKind, decide_app_action,
)
from shared.context import get_app_descriptor

_APK_SOURCES_PATH = os.path.join(REFERENCES_DIR, "apk_sources.json")
_FALLBACK_TESTABILITY_APK_URL = (
    "https://hyperloop-s3.sankuai.com/hpx-artifacts/"
    "5440930-973-1781175373969276/aimeituan-release_12.59.200-545701-aarch64.apk"
)

# 各平台安装耗时预估（真机验证经验值），用于生成用户可读的耗时提示。
# HarmonyOS 走「打开企业安装页 + 点击下载 + 点击系统安装确认」的 UI
# 自动化流程（见 devices/harmony/ops.py::HarmonyOps.install_app），安装包
# 由系统在后台下载，功能测试包体积明显大于 Android APK，全流程比 Android
# 明显更长。
_INSTALL_ETA_HINT = {
    "android": "预计约 1-2 分钟",
    "harmony": "预计约 2-3 分钟（HarmonyOS 功能测试包体积较大，系统会在后台自动下载，请耐心等待，安装过程中请勿拔断设备连接）",
}

def load_apk_config(platform: str = "android", form: str = "real") -> dict:
    """读取 references/apk_sources.json 中 meituan → platform → form 的目标条目。

    统一结构（所有平台一致）：`meituan[platform][form]`，form ∈ {real, emulator}
    （真机/云真机 vs 模拟器）。同一平台的真机与模拟器可能是不同制品/包名
    （如鸿蒙真机企业包 com.sankuai.hmeituan.beta vs 模拟器正式包 com.sankuai.hmeituan）。
    form 由调用方从 AppDescriptor.form 传入，本函数只按 (platform, form) 查表，
    **不做任何平台分支**——平台差异全部落在 apk_sources.json 的条目字段里
    （`version` / `version_code` / `requires_testability_build`）。

    读取失败 / 节点缺失时返回内置兜底配置：`version` 置空（调用方据
    `ArtifactSpec.version_key()` 判为无法比对而重装），仍带内置
    `testability_apk_url`，保证安装链路有制品地址可用。
    """
    try:
        cfg = read_json(_APK_SOURCES_PATH, default={})
        platform_cfg = (cfg.get("meituan") or {}).get(platform) or {}
        entry = platform_cfg.get(form) if isinstance(platform_cfg, dict) else None
        if isinstance(entry, dict) and entry.get("testability_apk_url"):
            sys.stderr.write(
                f"[device:install] 目标可测性安装包（{platform}/{form}）: {entry.get('version', '未知')}"
                f"（来源: apk_sources.json，更新于 {entry.get('updated', '未知')}）\n"
            )
            return entry
    except Exception as e:
        sys.stderr.write(f"[device:install] 读取 apk_sources.json 失败（{e}），回退到内置固定版本\n")
    return {"version": None, "testability_apk_url": _FALLBACK_TESTABILITY_APK_URL}

def _as_int(value) -> int:
    """宽松转 int：解析不出（None/非数字）时返回 None，供调用方决定回退策略。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def check_version(ops: PlatformOps) -> dict:
    """独立的版本探测接口，返回结构化结果，供 CLI check-version 子命令使用。

    决策全部收敛到 `devices/interfaces/artifact_spec.py::decide_app_action`：
      · 目标包名取自 get_app_descriptor()（已按 flow-context.json 的 meta.platform
        分派到正确的 AppDescriptor 子类）；apk_sources.json 的 `package` 仅作交叉展示；
      · 目标版本/构建要求按 (platform, form) 从 apk_sources.json 读取，构造 ArtifactSpec；
      · 已装包版本与构建类型由 PlatformOps 探测（get_installed_version /
        installed_build_kind）；
      · 返回结构保持向后兼容的键，供 device_commands/reporting 消费。
    """
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    apk_cfg = load_apk_config(platform=app_desc.platform, form=app_desc.form)

    spec = ArtifactSpec(
        package=package,
        url=apk_cfg.get("testability_apk_url"),
        version_code=_as_int(apk_cfg.get("version_code")),
        version_name=apk_cfg.get("version"),
        requires_testability_build=bool(apk_cfg.get("requires_testability_build")),
    )
    installed = ops.get_installed_version(package)
    build_kind = ops.installed_build_kind(package)
    decision = decide_app_action(spec, installed, build_kind)

    return {
        "installed": bool(installed.get("installed")),
        "currentVersion": installed.get("versionName"),
        "currentVersionCode": installed.get("versionCode"),
        "targetVersion": apk_cfg.get("version"),
        "targetVersionCode": apk_cfg.get("version_code"),
        "requiresDebugBuild": spec.requires_testability_build,
        "currentDebugBuild": (True if build_kind is BuildKind.TESTABILITY
                              else False if build_kind is BuildKind.RELEASE else None),
        "needsUpdate": decision.action != "reuse",
        "reason": decision.reason,
        "action": decision.action,
        "artifactCache": _artifact_cache_info(app_desc, apk_cfg),
    }


def _artifact_cache_info(app_desc, apk_cfg: dict) -> dict:
    """制品缓存摘要（不下载、不联网）：安装前“先看缓存”的可观测出口。

    L1 缓存与其并发约定见 `shared/artifact_cache.py`（跨 run / 跨子 Agent 共享，
    引擎永不自动清理）；这里只做只读探测，结果随 check-version 一并输出，
    使运维/报告能区分“本次需下载”与“直接复用缓存”。
    """
    target_url = apk_cfg.get("testability_apk_url")
    if not target_url:
        return {"hit": False, "reason": "未配置制品 URL（平台侧制品通道或无需安装）"}
    from shared import artifact_cache

    return artifact_cache.describe(target_url, artifact_cache.scope_of(app_desc))


def _log_artifact_cache(cache_info: dict):
    """把制品缓存命中情况打到安装日志（命中则本轮不会发生下载）。"""
    cache_info = cache_info or {}
    if cache_info.get("applicable") is False:
        sys.stderr.write(
            f"[device:install] 制品缓存不适用: {cache_info.get('reason', '-')}\n")
        return
    state = "✅ 命中" if cache_info.get("hit") else "未命中（安装前将下载一次）"
    sys.stderr.write(
        f"[device:install] 制品缓存{state}: "
        f"{cache_info.get('reason', '-')}"
        f"{(' — ' + str(cache_info.get('path'))) if cache_info.get('path') else ''}\n")


def _apply_artifact_channel(version_check: dict, device_lifecycle, ops) -> None:
    """按设备与平台**两层声明**修正 `artifactCache` 的适用性（就地修改）。

    任一为 False 即“制品不经本地”，此时 L1 缓存不适用：
      · `DeviceLifecycle.uses_local_artifact`：设备获取方式层面（sandbox = 平台侧下载并投递）；
      · `PlatformOps.uses_local_artifact`：平台形态层面（HarmonyOS form=real = 企业安装页）。
    标成 `applicable=False` 后，安装日志/报告不会给出“未命中，安装时下载一次”
    这种与实际不符的描述。
    """
    local_channel = (getattr(device_lifecycle, "uses_local_artifact", True)
                     and getattr(ops, "uses_local_artifact", True))
    if local_channel:
        return
    version_check["artifactCache"] = {
        "applicable": False,
        "reason": "平台侧制品通道（制品不经本地，L1 制品缓存不适用）",
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
    apk_cfg = load_apk_config(platform=app_desc.platform, form=app_desc.form)
    version_check = check_version(ops)
    _apply_artifact_channel(version_check, device_lifecycle, ops)
    steps = []

    if not force and not version_check["needsUpdate"]:
        sys.stderr.write(
            f"[device:install] 已是目标版本 {version_check['currentVersion']}，跳过卸载重装\n"
        )
        return {"skipped": True, "versionCheck": version_check, "steps": steps}

    _log_artifact_cache(version_check.get("artifactCache") or {})

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
    apk_cfg = load_apk_config(platform=platform, form=app_desc.form)
    version_check = check_version(ops)
    _apply_artifact_channel(version_check, device_lifecycle, ops)
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
    _log_artifact_cache(version_check.get("artifactCache") or {})
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
    # 声明（见 devices/<platform>/ops.py::INSTALL_VERIFY_RETRIES），本函数
    # 不感知具体平台差异。
    from devices.base import get_platform_module
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
