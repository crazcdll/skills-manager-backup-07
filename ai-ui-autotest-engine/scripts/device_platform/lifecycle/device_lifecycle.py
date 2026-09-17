#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备生命周期管理 CLI（Python 版）。

通过 DeviceLifecycle 接口统一抽象 sandbox/local 两种设备类型，
工具链按 meta.platform 分发（android: adb, harmony: hdc）。
标准流程：create → setup。
"""
import argparse
import json
import os
import sys
import time

from infra.sandbox_api import SandboxApiError
from core.errors import DeviceError, UsageError, soft_fail
from infra.app_installer import (
    check_version, ensure_app_installed, ensure_app_installed_if_missing,
)
from infra.session import imeituan_register, imeituan_disconnect
from infra.imeituan_cli import imeituan_exec
from context import create_platform_ops, create_device_lifecycle, get_app_descriptor, get_onboarding_profile
from core.flow.flow_context import update_meta_fields, read_meta_fields
from core.sop.constants import FLOW_CONTEXT_FILENAME
from core.util.case_utils import resolve_mis, resolve_case_path
from core.util.paths import get_active_case
from device_platform.base import get_device_category, is_device_platform_supported

_REGISTER_MAX_RETRIES = 3
_REGISTER_RETRY_INTERVAL = 5


def _ensure_toolchain(platform: str):
    """确保指定 platform 的连接工具链（adb/hdc/...）就绪，不可用时直接报错退出。"""
    from device_platform.base import get_platform_module
    if not get_platform_module(platform).ensure_toolchain():
        _emit_err(f"{platform} 连接工具链不可用（请检查 check-deps 输出）")


def _register_with_retry(adb_address, platform, state_file, log=None, device_type="sandbox"):
    """注册设备到 imeituan session（带重试 + session_id 持久化）。
    重试前自动修复 ADB Server 陈旧状态。
    """
    reg_result = None
    for attempt in range(_REGISTER_MAX_RETRIES):
        reg_result = imeituan_register(adb_address, platform=platform, device_type=device_type)
        if reg_result["ok"]:
            break
        if attempt < _REGISTER_MAX_RETRIES - 1:
            sys.stderr.write(f"注册失败，等待 {_REGISTER_RETRY_INTERVAL}s 后重试（{attempt + 1}/{_REGISTER_MAX_RETRIES}）...\n")
            time.sleep(_REGISTER_RETRY_INTERVAL)
            # 修复措施：ADB Server 陈旧状态导致连接失败，重启 ADB Server
            if is_device_platform_supported(device_type, "android"):
                try:
                    import subprocess
                    r = subprocess.run(["adb", "kill-server"], capture_output=True, timeout=15)
                    if r.returncode == 0:
                        sys.stderr.write("[device:session] 已重启 ADB Server（修复陈旧连接状态），准备重试注册...\n")
                    else:
                        sys.stderr.write(f"[device:session] adb kill-server 执行异常: {r.stderr.decode()[:200]}\n")
                except Exception as e:
                    sys.stderr.write(f"[device:session] adb kill-server 失败: {e}\n")
    if log:
        log("imeituan_register", reg_result["ok"], reg_result["detail"])
    if reg_result["ok"] and reg_result.get("session_id"):
        update_meta_fields(state_file, {"session_id": reg_result["session_id"]})
        sys.stderr.write(f"session_id 已写入 flow-context.json: {reg_result['session_id']}\n")
    return reg_result

def _write_sandbox_state(state: dict, path: str):
    """create 成功后将设备信息写入 flow-context.json 的 meta 字段。"""
    update_meta_fields(path, {
        "sandbox_id": state.get("sandboxId", ""),
        "device_serial": state.get("adbAddress", ""),
        "sandbox_user": state.get("user", ""),
        "scrcpyUrl": state.get("scrcpyUrl", ""),
        "device_type": state.get("device_type", "sandbox"),
    })

def _emit(obj, ok_exit=True):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    if not ok_exit:
        raise DeviceError(str(obj.get("error", "设备命令失败")))

def _emit_err(msg, event="device_command_failed", code="DEVICE_CMD_FAILED", raw=""):
    # 设备命令失败统一出口：记录 audit 事件到时间线，然后打印错误退出
    # 异常上报由 AI 在终止时统一调用 report-error 完成
    try:
        from core.audit.runtime_audit import append_event
        from core.util.paths import get_active_case
        _case_name = get_active_case()
        if _case_name:
            from core.util.case_utils import resolve_case_path
            append_event(resolve_case_path(_case_name), "device.failed",
                         {"event": event, "message": msg, "code": code})
    except Exception as e:
        soft_fail("infra", "DEVICE_FAILED_AUDIT_WRITE", e)
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    raise DeviceError(msg)


def _emit_guidance(guidance_id, fallback_msg, **detail):
    """输出结构化设备连接引导（见 environment/device_guidance.py），退出码与
    _emit_err 一致（约定失败语义不变），但 stdout 携带可展示给用户的分步指引，
    而非一句话文本报错。guidance_id 未注册时透明回退到 _emit_err，不静默吞错。
    """
    from environment.helpers.device_guidance import build_guidance_payload
    payload = build_guidance_payload(guidance_id, detail=detail or None)
    if payload is None:
        _emit_err(fallback_msg)
    print(json.dumps({"error": fallback_msg, **payload}, ensure_ascii=False, indent=2))
    raise DeviceError(fallback_msg)


# ─── 子命令：create ─────────────────────────────────────────
def _create_local(args, meta):
    """本地真机：自动探测已连接设备（不走云端创建），写入 flow-context.json。

    探测逻辑完全委托给 LocalDeviceLifecycle.acquire()（按 meta.platform 内部
    分发到对应平台的 probe_local_devices() 实现），本函数只负责：
    - 把 LocalDeviceProbeError 转成结构化 guidance 输出（未注册 guidance_id
      透明回退到纯文本报错，行为与 acquire() 直接抛错时一致）
    - 落盘 flow-context.json / sandbox_state

    新增平台支持时不需要改动本函数，只需按 platform/lifecycle/local.py 顶部
    的"平台模块契约"在对应 platform/<platform>/ops.py 中实现并注册。
    """
    from device_platform.base import LocalDeviceProbeError

    platform = meta.get("platform", "android")
    lifecycle = create_device_lifecycle("local", platform=platform)
    try:
        device_info = lifecycle.acquire(resolve_mis())
    except LocalDeviceProbeError as e:
        if e.guidance_id:
            _emit_guidance(e.guidance_id, str(e), **e.detail)
        _emit_err(str(e))

    serial = device_info["serial"]
    sys.stderr.write(f"[device:create] 本地真机已探测: {serial}（platform={platform}）\n")

    output = {
        "ok": True,
        "sandboxId": "",
        "serialNumber": serial,
        "remoteConnectAddress": serial,
        "device_type": "local",
    }
    _write_sandbox_state({
        "sandboxId": "",
        "adbAddress": serial,
        "user": resolve_mis(),
        "scrcpyUrl": "",
        "device_type": "local",
    }, args.state_file)
    _emit(output)


def _create_local_emulator(args, meta):
    """本地模拟器：自动探测/启动已安装模拟器，写入 flow-context.json。"""
    from device_platform.base import LocalDeviceProbeError

    platform = meta.get("platform", "ios")
    lifecycle = create_device_lifecycle("local-emulator", platform=platform)
    try:
        device_info = lifecycle.acquire(resolve_mis())
    except LocalDeviceProbeError as e:
        if e.guidance_id:
            _emit_guidance(e.guidance_id, str(e), **e.detail)
        _emit_err(str(e))

    serial = device_info["serial"]
    sys.stderr.write(f"[device:create] 本地模拟器已就绪: {serial}（platform={platform}）\n")

    output = {
        "ok": True,
        "sandboxId": "",
        "serialNumber": serial,
        "remoteConnectAddress": serial,
        "device_type": "local-emulator",
    }
    _write_sandbox_state({
        "sandboxId": "",
        "adbAddress": serial,
        "user": resolve_mis(),
        "scrcpyUrl": "",
        "device_type": "local-emulator",
    }, args.state_file)
    _emit(output)


def cmd_create(args):
    """创建设备实例。

    sandbox：优先复用已有 running 实例，无可用实例时创建新设备。
    local：跳过创建，自动探测已连接的本地真机（按 meta.platform 选择 adb/hdc）。
    local-emulator：本地模拟器实例自动发现与就绪。
    """
    if not resolve_mis():
        _emit_err("无法获取 user_mis（flow-context.json meta.user_mis 为空且 resolve_mis 失败）")

    meta = read_meta_fields(args.state_file)
    device_type = meta.get("device_type", "sandbox")

    # 按 device_type 分发到对应的创建实现
    _CREATE_HANDLERS = {
        "local": _create_local,
        "local-emulator": _create_local_emulator,
    }
    handler = _CREATE_HANDLERS.get(device_type)
    if handler:
        handler(args, meta)
        return

    # sandbox 恒为 Android（device_platform.registry._DEVICE_TYPE_REGISTRY 声明），
    # 直接按 "android" 分发工具链检查，不依赖 meta.platform。
    _ensure_toolchain("android")

    lifecycle = create_device_lifecycle("sandbox")

    # ── 先查已有 running 实例，有则复用 ──
    try:
        instances = lifecycle.query_user_devices(resolve_mis())
        running = [i for i in instances if i.get("state") == "running"]
    except Exception as e:
        running = []
        sys.stderr.write(f"[device] 查询已有实例失败，将创建新设备: {e}\n")

    if running:
        reuse = running[0]
        sid = reuse["sandboxId"]
        addr = reuse["adbAddress"]
        sys.stderr.write(f"[device] 复用已有模拟器 ({sid} @ {addr})\n")
        _write_sandbox_state({
            "sandboxId": sid,
            "adbAddress": addr,
            "user": resolve_mis(),
            "scrcpyUrl": reuse.get("scrcpyUrl", ""),
            "device_type": "sandbox",
        }, args.state_file)
        _emit({
            "ok": True, "reused": True,
            "sandboxId": sid,
            "serialNumber": addr,
            "remoteConnectAddress": addr,
            "scrcpyUrl": reuse.get("scrcpyUrl", ""),
            "device_type": "sandbox",
        })
        return

    # ── 创建新设备 ──
    sys.stderr.write(f"[device] 创建新模拟器 (user: {resolve_mis()})...\n")
    try:
        device_info = lifecycle.acquire(resolve_mis())
    except Exception as e:
        _emit_err(f"创建设备失败: {e}", event="device_create_failed",
                  code="DEVICE_CREATE_FAILED", raw=getattr(e, "raw", "") or str(e))

    if not device_info or not device_info.get("sandboxId"):
        raise DeviceError("创建模拟器失败")

    adb_address = device_info["serial"]
    sys.stderr.write(f"[device] 模拟器创建成功 ({device_info['sandboxId']})\n")

    # 记录设备创建成功事件（fire-and-forget）
    try:
        from core.audit.runtime_audit import append_event
        _run_dir = os.path.dirname(args.state_file)
        append_event(_run_dir, "device.created",
                     {"sandbox_id": device_info["sandboxId"], "serial": adb_address,
                      "device_type": "sandbox"})
    except Exception as e:
        soft_fail("infra", "DEVICE_CREATED_AUDIT_WRITE_FAILED", e)

    output = {
        "ok": True,
        "sandboxId": device_info["sandboxId"],
        "serialNumber": adb_address,
        "remoteConnectAddress": adb_address,
        "ip": device_info.get("ip", ""),
        "adbPort": device_info.get("adbPort", 8080),
        "scrcpyUrl": device_info.get("scrcpyUrl", ""),
        "device_type": "sandbox",
    }
    _write_sandbox_state({
        "sandboxId": output["sandboxId"],
        "adbAddress": adb_address,
        "user": resolve_mis(),
        "scrcpyUrl": output["scrcpyUrl"],
        "device_type": "sandbox",
    }, args.state_file)
    _emit(output)

# ─── 子命令：check-version ──────────────────────────────────
def cmd_check_version(args):
    if not args.adb_address:
        _emit_err("缺少 adb_address（flow-context.json 无 device_serial 记录，请先执行 create）")

    # check_version 内部使用 imeituan_shell，需要 session 存在
    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    device_type = meta.get("device_type", "sandbox")
    _ensure_toolchain(platform)
    reg_result = _register_with_retry(args.adb_address, platform, args.state_file, device_type=device_type)
    if not reg_result["ok"]:
        _emit_err(f"设备注册失败，无法探测版本: {reg_result['detail']}")

    ops = create_platform_ops(args.adb_address, platform=platform)
    result = check_version(ops)
    _emit({"ok": True, "adbAddress": args.adb_address, **result})

# ─── setup 子段：按 OnboardingProfile 能力位独立执行/跳过 ─────
def _register_session(args, steps, log_step):
    """注册设备到 imeituan session（必须在所有 imeituan_shell 调用之前，所有设备类型均需要）。

    返回 (ops, package, main_activity) 供后续段使用，失败直接抛 core.errors 错误。
    """
    sys.stderr.write("[device:setup] 注册设备到 imeituan session...\n")
    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    device_type = meta.get("device_type", "sandbox")
    reg_result = _register_with_retry(args.adb_address, platform, args.state_file, log=log_step, device_type=device_type)
    if not reg_result["ok"]:
        print(json.dumps({
            "ok": False, "steps": steps,
            "error": f"imeituan 注册失败（{_REGISTER_MAX_RETRIES} 次重试后仍失败），无法继续 setup: {reg_result['detail']}",
        }, ensure_ascii=False, indent=2))
        raise DeviceError(f"imeituan 注册失败（{_REGISTER_MAX_RETRIES} 次重试后仍失败），无法继续 setup: {reg_result['detail']}")

    ops = create_platform_ops(args.adb_address, platform=platform)
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    main_activity = f"{package}/{app_desc.main_activity_class}"

    # session 初始化时自动设置目标包，确保后续 inject mock 等命令有路由目标
    # 不阻断：set-package 失败时后续命令会报 PACKAGE_NOT_SELECTED 并显示明确指引
    sys.stderr.write(f"[device:setup] 设置 session 目标包: {package}...\n")
    imeituan_exec(["device", "set-package", package])

    return ops, package, main_activity


def _check_version_step(ops, log_step, allow_install=True):
    """探测已装版本 vs 目标版本（只读，不执行安装动作）。

    allow_install=False 且探测到版本落后时（如本地真机默认关闭自动装卸），
    额外记录一条非阻断 WARNING，避免用户在不知情的情况下用旧版本跑用例。
    """
    version_check = check_version(ops)
    log_step(
        "version_check",
        True,
        f"installed={version_check['installed']} current={version_check['currentVersion']} "
        f"target={version_check['targetVersion']} reason={version_check['reason']}",
    )
    if not allow_install and version_check.get("needsUpdate"):
        log_step(
            "version_outdated_warning", True,
            f"本地包版本落后于目标版本（{version_check['reason']}），未自动升级，"
            f"如用例依赖新功能可能失败",
        )
    return version_check


def _install_or_upgrade(args, ops, lifecycle, steps, log_step):
    """按需卸载重装以对齐目标版本（跳过已是目标版本的场景）。

    Returns:
        bool: 本次是否发生了全新安装（True=卸载重装过，需首次启动引导；
              False=复用现有安装）。
    """
    force_reinstall = getattr(args, "force_reinstall", False)
    install_result = ensure_app_installed(
        ops, lifecycle, args.sandbox_id, force=force_reinstall,
    )
    if install_result["skipped"]:
        log_step("install_or_upgrade", True, "已是目标版本，跳过卸载重装")
        return False
    for s in install_result["steps"]:
        log_step(s["step"], s["ok"], s.get("detail", ""))
    if install_result.get("error"):
        raise DeviceError(install_result["error"])
    return True


def _install_if_missing_step(ops, lifecycle, steps, log_step, notices):
    """本地真机专用：仅在完全未安装时自动补装，已安装（任意版本）直接复用。

    与 _install_or_upgrade 的关键差异——不比对版本、不卸载：本地真机是
    用户自己的手机，不允许自动卸载/升级已有安装，只在压根没有目标 App
    时才自动装一个。

    Returns:
        bool: 本次是否发生了全新安装（freshInstall=True），供调用方判断是否
              需要展示企业应用信任弹窗引导。
    """
    install_result = ensure_app_installed_if_missing(ops, lifecycle)
    if install_result.get("notice"):
        notices.append(install_result["notice"])
    if install_result["skipped"]:
        log_step("install_if_missing", True, "设备已安装目标 App，直接复用现有安装")
        return False
    for s in install_result["steps"]:
        log_step(s["step"], s["ok"], s.get("detail", ""))
    if install_result.get("error"):
        print(json.dumps({
            "ok": False, "steps": steps, "important_notices": notices,
            "error": install_result["error"],
        }, ensure_ascii=False, indent=2))
        raise DeviceError(install_result["error"])
    return bool(install_result.get("freshInstall"))


def _first_run_onboarding(ops, package, main_activity, log_step, fresh_install):
    """首次启动引导，按是否全新安装分两条路径。

    fresh_install=True（全新安装）：启动 App → 检测隐私弹窗「同意」→ 点击 →
    冷重启（让同意状态生效并初始化 AppMock）。
    fresh_install=False（复用现有安装）：直接冷重启（确保 AppMock 初始化），
    跳过隐私弹窗检测——复用 App 早已同意过隐私协议不会再弹窗，检测反而可能
    误命中页面其它含「同意」字样的文案。
    """
    from screen_state.inspect_tree import inspect_tree_find_center

    if fresh_install:
        sys.stderr.write("[device:setup] 启动 App 并处理隐私弹窗...\n")
        launch_ok = ops.launch_app(main_activity)
        log_step("launch_app", launch_ok, "全新安装后首次启动" if launch_ok else "am start 失败")
        sys.stderr.write("[device:setup] 等待隐私弹窗渲染（12s）...\n")
        time.sleep(12)

        # 检测隐私弹窗"同意"按钮。detail=True 返回 dict 或 None，dict 的
        # center 可能为 None（unresolved：命中「同意」文案但不可点击），
        # 只有拿到有效可点击坐标才视为真正命中弹窗按钮。
        agree_btn = inspect_tree_find_center("同意", detail=True)
        agree_center = agree_btn.get("center") if isinstance(agree_btn, dict) else None
        if agree_center:
            sys.stderr.write(f"[device:setup] 检测到隐私协议弹窗，点击同意 @ {agree_center}\n")
            tap_ok = ops.tap(*agree_center)
            log_step("tap_privacy_agree", tap_ok, f"tap{agree_center}")
            time.sleep(3)
        else:
            sys.stderr.write("[device:setup] 无隐私协议弹窗，跳过\n")
            log_step("tap_privacy_agree", True, "无隐私弹窗，跳过")
    else:
        log_step("tap_privacy_agree", True, "复用现有安装，跳过隐私弹窗检测")

    sys.stderr.write("[device:setup] 冷重启 App（确保 AppMock 初始化）...\n")
    stop_ok = ops.force_stop(package)
    time.sleep(2)
    relaunch_ok = ops.launch_app(main_activity)
    time.sleep(3)
    cold_ok = stop_ok and relaunch_ok
    log_step("cold_restart", cold_ok,
             "冷重启完成" if cold_ok else f"force_stop={stop_ok} relaunch={relaunch_ok}")

    ps_out = ops.pidof(package)
    app_running = bool(ps_out) and ps_out.isdigit()
    log_step("verify_running", app_running, f"pid={ps_out}" if app_running else "App 未运行")


def _setup_keyboard_if_needed(ops, log_step):
    """ADBKeyboard 安装 + 设为默认输入法（仅云模拟器使用，非关键步骤）。"""
    adb_kb_ok = ops.setup_keyboard()
    log_step("adb_keyboard", adb_kb_ok, "已安装并设为默认输入法" if adb_kb_ok else "安装或激活失败（不影响主流程）")
    if not adb_kb_ok:
        sys.stderr.write(
            "[device:setup] 警告：ADBKeyboard 安装失败，中文输入可能不可用\n"
            "   可手动安装: imeituan device install references/ADBKeyboard.apk\n"
        )


# ─── 子命令：setup ──────────────────────────────────────────
def cmd_setup(args):
    """设备环境初始化，按 OnboardingProfile 能力位逐段判断执行：
    session 注册（总是执行）→ 版本探测 → 仅缺失安装 → 卸载重装 →
    首次启动引导 → 输入法配置 → 前台校验（鸿蒙全新安装场景除外）。
    sandbox 全部能力位为 True；local/cloud_device 无 sandboxId，仅要求
    adb_address（device_serial）非空。

    鸿蒙 + 本地真机 + 全新安装时，HarmonyOS 企业签名信任机制会在首次点击
    图标时弹出系统级拦截弹窗，无法通过 hdc 程序化绕过，也不应沿用 Android
    的隐私协议自动点击逻辑——直接跳过首次启动引导和前台自动校验，改为输出
    结构化 guidance（harmony_local_untrusted_app）指引用户手动处理。
    """
    if not args.adb_address:
        _emit_err("缺少 adb_address（flow-context.json 无 device_serial 记录，请先执行 create）")

    meta = read_meta_fields(args.state_file)
    device_type = meta.get("device_type", "sandbox")
    platform = meta.get("platform", "android")
    if get_device_category(device_type) == "cloud" and not args.sandbox_id:
        _emit_err("缺少 sandbox_id（flow-context.json 无记录，请先执行 create）")

    # 统一按 platform 分发工具链检查（Android→adb，Harmony→hdc，详见
    # platform/lifecycle/local.py 顶部的平台模块契约说明）；sandbox 的
    # meta.platform 恒为 android（_DEVICE_TYPE_REGISTRY 声明），走同一
    # 分发路径不需要单独分支。
    _ensure_toolchain(platform)

    steps = []
    notices = []

    def log_step(name, ok, detail=""):
        steps.append({"step": name, "ok": ok, "detail": detail})
        mark = "✓" if ok else "✗"
        sys.stderr.write(f"[device:setup] {mark} {name}" + (f" — {detail}" if detail else "") + "\n")

    profile = get_onboarding_profile()
    lifecycle = create_device_lifecycle(device_type)

    ops, package, main_activity = _register_session(args, steps, log_step)

    if profile.needs_version_check():
        sys.stderr.write("[device:setup] 检测 App 版本...\n")
        _check_version_step(ops, log_step, allow_install=profile.needs_app_install())

    fresh_install = False
    if profile.needs_install_if_missing():
        fresh_install = _install_if_missing_step(ops, lifecycle, steps, log_step, notices)

    if profile.needs_app_install():
        sys.stderr.write("[device:setup] 按需安装/升级（可能需要 30-60s）...\n")
        fresh_install = _install_or_upgrade(args, ops, lifecycle, steps, log_step)

    # 全新安装 + 该平台存在系统级强制信任拦截（如 HarmonyOS 企业应用信任
    # 校验）：直接展示引导并提前终止，不再尝试 Android 式隐私协议点击或
    # 前台自动校验（必然因弹窗拦截而失败，白白多等 3 次重试）。
    # FRESH_INSTALL_GUIDANCE_ID 是否为 None 由各平台模块自行声明（详见
    # platform/lifecycle/local.py 顶部的平台模块契约说明），本函数不感知
    # 具体是哪个平台——sandbox 目前恒为 Android，该平台此值恒为 None，
    # 与 device_type 无关，因此不需要额外按 device_type 分支短路。
    from device_platform.base import get_platform_module
    fresh_install_guidance_id = get_platform_module(platform).FRESH_INSTALL_GUIDANCE_ID

    if fresh_install and fresh_install_guidance_id:
        sys.stderr.write(
            "\n" + "=" * 70 +
            f"\n[device:setup] ⚠️ 全新安装完成，{platform} 平台信任校验将拦截首次启动，"
            "\n需要用户在设备上手动处理，详见 guidance 字段\n" + "=" * 70 + "\n"
        )
        from environment.helpers.device_guidance import build_guidance_payload
        payload = build_guidance_payload(
            fresh_install_guidance_id,
            detail={"package": package, "adbAddress": args.adb_address},
        )
        print(json.dumps({
            "ok": False, "steps": steps, "important_notices": notices,
            **(payload or {"error": "全新安装完成，需用户手动处理系统信任弹窗后重新登录"}),
        }, ensure_ascii=False, indent=2))
        raise DeviceError("全新安装完成，需用户手动处理系统信任弹窗后重新登录")

    if profile.needs_first_run_onboarding():
        _first_run_onboarding(ops, package, main_activity, log_step, fresh_install)
    else:
        launch_ok = ops.launch_app(main_activity)
        log_step("launch_app", launch_ok, "拉起 App" if launch_ok else "启动失败")

    if profile.needs_keyboard_setup():
        _setup_keyboard_if_needed(ops, log_step)

    # ── 最终前台校验：确保 setup 结束时 App 在前台（所有设备类型均需要） ──
    fg_ok = False
    for _attempt in range(3):
        fg_line = ops.check_foreground()
        fg_ok = bool(fg_line) and package in fg_line
        if fg_ok:
            break
        sys.stderr.write(f"[device:setup] App 不在前台，重新拉起（尝试 {_attempt + 1}/3）...\n")
        ops.launch_app(main_activity)
        time.sleep(3)
    log_step("ensure_foreground", fg_ok, "App 在前台" if fg_ok else "App 仍不在前台（不阻断，后续操作会拉起）")

    # 注：不基于"多次拉起仍不在前台"推断信任拦截——探测不到前台的成因还
    # 包括启动慢、闪退等，不是信任拦截的唯一可能。只有"全新安装"这一信号
    # 足够可靠（见上方 fresh_install 分支），此处保留不阻断的警告日志即可。

    # ── 防熄屏：本地真机场景避免测试过程中自动熄屏 ──
    if profile.needs_screen_check():
        sys.stderr.write("[device:setup] 开启防熄屏（保持屏幕常亮）...\n")
        imeituan_exec(["device", "keep-awake", "--on"])

    # adb_keyboard / ensure_foreground 失败、version_outdated_warning 均不阻断 setup
    non_critical = {"adb_keyboard", "ensure_foreground", "version_outdated_warning"}
    critical_steps = [s for s in steps if s["step"] not in non_critical]
    all_ok = all(s["ok"] for s in critical_steps)
    output = {
        "ok": all_ok, "steps": steps,
        "adbAddress": args.adb_address, "sandboxId": args.sandbox_id,
    }
    if notices:
        output["important_notices"] = notices
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not all_ok:
        raise DeviceError("cmd-setup 部分步骤失败")

# ─── 子命令：register ──────────────────────────────────────
def cmd_register(args):
    if not args.adb_address:
        _emit_err("缺少 adb_address（flow-context.json 无 device_serial 记录，请先执行 create）")

    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    device_type = meta.get("device_type", "sandbox")
    _ensure_toolchain(platform)
    result = _register_with_retry(args.adb_address, platform, args.state_file, device_type=device_type)
    print(json.dumps({
        "ok": result["ok"], "adbAddress": args.adb_address, "detail": result["detail"],
    }, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise DeviceError("查询设备失败")

# ─── 子命令：query ──────────────────────────────────────────
def cmd_query(args):
    mis = resolve_mis()
    if not mis:
        _emit_err("无法获取 user_mis")

    lifecycle = create_device_lifecycle("sandbox")
    try:
        instances = lifecycle.query_user_devices(mis)
    except SandboxApiError as e:
        raise DeviceError(str(e)) from e

    print(json.dumps({"ok": True, "count": len(instances), "sandboxes": instances}, ensure_ascii=False, indent=2))

def cmd_device(args):
    """device 子命令分发到 cmd_create / cmd_setup / cmd_query / check-version / register 等处理函数。"""
    subcmd = args.device_subcmd
    _LEVEL2 = {"setup", "check-version", "register"}
    if subcmd in _LEVEL2:
        _resolve_device_state(args)
        args.command = subcmd
    else:
        _resolve_flow_context(args)
        args.command = subcmd
    handlers = {
        "create": cmd_create, "setup": cmd_setup,
        "query": cmd_query,
        "check-version": cmd_check_version, "register": cmd_register,
    }
    handlers[subcmd](args)


# ─── 参数解析 ───────────────────────────────────────────────
# 命令分两级：
#   Level 1（create）：需 active_case + flow-context.json
#   Level 2（setup/check-version/register）：需 flow-context.json + 已有设备信息
# --force-reinstall / --force 是行为开关，不是状态参数。

def _resolve_flow_context(args):
    """Level 1: 从 active_case 解析 flow-context.json 路径。

    用于 create 命令——需要写 state_file 但不需要已有设备信息。
    返回 meta dict 供 Level 2 复用，避免重复读取。
    """
    case_name = get_active_case()
    if not case_name:
        raise UsageError("未设置 active_case，请先执行 flow-init")

    run_dir = resolve_case_path(case_name)
    fc_path = os.path.join(run_dir, FLOW_CONTEXT_FILENAME)
    meta = read_meta_fields(fc_path)

    args.state_file = fc_path
    return meta


def _resolve_device_state(args):
    """Level 2: 在 flow_context 基础上，解析已有的 sandbox_id 和 adb_address。

    用于 setup/check-version/register——依赖 create 已写入的设备信息。
    """
    meta = _resolve_flow_context(args)
    args.sandbox_id = meta.get("sandbox_id", "") or None
    args.adb_address = meta.get("device_serial", "") or None
