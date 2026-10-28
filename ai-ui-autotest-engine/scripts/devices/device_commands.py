#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备级命令实现：setup / check-version / register（含设备状态与输出的公共底座）。

命名澄清：本模块**不是** DeviceLifecycle 抽象类，也不是它的实现——
    - 抽象契约：`devices/interfaces/lifecycle.py::DeviceLifecycle`
    - 具体实现：`devices/lifecycle/{sandbox,local,cloud_emulator,local_emulator}.py`
本模块是 `devices` 层的**命令处理器**：把"拿到设备之后"的环境准备（注册会话、探测/
安装 App、首次启动引导、前台校验）跑完，并把设备身份写进 flow-context.json。
其中 `_emit*` / `_write_sandbox_state` / `_register_with_retry` / `_resolve_*` 是设备
状态与输出的公共底座，被 `resources/device_pool/commands.py` 复用（池化命令
create/query/release 在那边）。

工具链按 meta.platform 分发（android: adb, harmony: hdc）；标准流程：create → setup。
"""
import json
import os
import sys
import time

from shared.errors import DeviceError, UsageError, soft_fail
from devices.toolchain.app_installer import (
    check_version, ensure_app_installed, ensure_app_installed_if_missing,
)
from devices.toolchain.session import imeituan_register
from devices.toolchain.imeituan_cli import DEVICE_REUSE_ERRORS, imeituan_exec
from shared.context import create_platform_ops, create_device_lifecycle, get_app_descriptor, get_onboarding_profile
from execution.engine.flow.flow_context import update_meta_fields, read_meta_fields
from execution.engine.sop.constants import FLOW_CONTEXT_FILENAME
from shared.case_utils import resolve_case_path
from shared.paths import get_active_run
from shared.workspace import render_text
from devices.base import get_device_category, get_device_form

# 注册尝试次数：只对**瞬态错误**生效；确定性错误（legacy 会话、端口归属冲突等）
# 立即终止，不做无意义的重复（详见 imeituan_cli.classify_error）。
_REGISTER_ATTEMPTS = 3
_REGISTER_BACKOFF = (3, 8)          # 第 1/2 次失败后的退避秒数

# 这些确定性错误可以通过"隔离出问题的会话"自愈一次，其余确定性错误直接终止。
_SESSION_SELF_HEAL_CODES = (
    "ADB_SERVER_LEGACY_IDENTITY_UNKNOWN",
    "ADB_RUNTIME_MIGRATION_REQUIRED",
    "SESSION_CLEANUP_PENDING",
)


def _ensure_toolchain(platform: str):
    """确保指定 platform 的连接工具链（adb/hdc/...）就绪，不可用时直接报错退出。

    排查提示由各平台模块以 `TOOLCHAIN_HINT` 声明（数据驱动，避免在编排层写
    `if platform == ...` 分支），未声明时回退到通用提示。注意：check-deps 只覆盖
    android/harmony 的依赖安装，iOS 的前置（Xcode / xcrun）不在其覆盖范围内，
    因此 iOS 模块必须自带提示，否则报错会把用户误导到 check-deps。
    """
    from devices.base import get_platform_module

    mod = get_platform_module(platform)
    if not mod.ensure_toolchain():
        hint = getattr(mod, "TOOLCHAIN_HINT", "请检查 check-deps 输出")
        _emit_err(f"{platform} 连接工具链不可用（{hint}）")


def _register_with_retry(adb_address, platform, state_file, log=None, device_type="sandbox",
                         remote_address=None):
    """注册设备到 imeituan session（按错误类型重试 + session_id 持久化）。

    重试策略（唯一实现，调用方不再自己加循环）：
      · 瞬态错误（超时 / 云 Server 排队 / 设备刚启动）→ 退避后重试，最多 `_REGISTER_ATTEMPTS` 次；
      · 确定性错误（legacy 会话、端口归属冲突、SDK 版本不达标）→ **不重试**；
        其中"会话记录卡死"类错误先做一次定向隔离（把点名会话移入 `.stale/`）再试一次；
      · 任何情况下都**不再执行 `adb kill-server`**：那是全局副作用，会打断同机其他
        并发 run 的 adb 连接，并制造"无启动身份"的共享 Server（ADB_PORT_OWNERSHIP_CONFLICT）。

    并发隔离：只断开「本 run 已有的旧会话」（若有），绝不做全量断开——全量会把
    并发 run 的会话一并踢掉。注册成功后由 imeituan_register 绑定本 run 会话。
    云设备需传 remote_address（远程 server 地址）。
    """
    from devices.toolchain.session import disconnect_session, remediate_failed_session

    prev_sid = (read_meta_fields(state_file) or {}).get("session_id", "")
    if prev_sid:
        closed = disconnect_session(prev_sid)
        if closed.get("ok"):
            update_meta_fields(state_file, {"session_id": ""})
        else:
            # 瞬态断开失败不阻断注册：新会话会覆盖 flow-context 的 session_id。
            sys.stderr.write(f"[device:session] 旧会话断开暂未完成（{closed.get('code') or '?'}），继续注册\n")

    reg_result = None
    healed = False
    for attempt in range(_REGISTER_ATTEMPTS):
        reg_result = imeituan_register(adb_address, platform=platform, device_type=device_type,
                                       remote_address=remote_address)
        if reg_result["ok"]:
            break

        code = reg_result.get("code") or ""
        retryable = bool(reg_result.get("retryable"))

        # 确定性 + 可自愈：只隔离"错误信息里点名的那个会话"，然后重试一次（不是盲重试）。
        if not retryable and not healed and code in _SESSION_SELF_HEAL_CODES:
            healed = True
            fix = remediate_failed_session(reg_result.get("detail", ""))
            # 错误里点名了会话就再试一次：
            #   · 隔离成功 → 坏记录已移走；
            #   · 文件已不存在（被 CLI 自己清掉）→ 状态已变化，同样值得再试一次。
            # 都不是“盲重试”，而是针对已知状态的定向重试。
            if fix.get("session_id"):
                sys.stderr.write(
                    f"[device:session] 故障会话 {fix['session_id']} 已处理"
                    f"（{'已隔离' if fix.get('quarantined') else '记录已不存在'}），重新注册一次\n")
                continue

        if not retryable:
            sys.stderr.write(f"[device:session] 确定性失败[{code}]，不再重试："
                             f"{reg_result.get('detail', '')[:200]}\n")
            break

        if attempt < _REGISTER_ATTEMPTS - 1:
            wait = _REGISTER_BACKOFF[min(attempt, len(_REGISTER_BACKOFF) - 1)]
            sys.stderr.write(f"[device:session] 瞬态失败[{code}]，{wait}s 后重试"
                             f"（{attempt + 1}/{_REGISTER_ATTEMPTS}）...\n")
            time.sleep(wait)

    if log:
        log("imeituan_register", reg_result["ok"], reg_result.get("detail", ""))
    if reg_result["ok"] and reg_result.get("session_id"):
        update_meta_fields(state_file, {"session_id": reg_result["session_id"]})
        sys.stderr.write(f"session_id 已写入 flow-context.json: {reg_result['session_id']}\n")
    return reg_result

def _write_sandbox_state(state: dict, path: str):
    """create 成功后将设备信息写入 flow-context.json 的 meta 字段。

    额外落 `lease_fence` / `lease_expires_at`：服务端租约用 fence 做乐观锁，
    后续 renew/release 必须带同一个 fence；到期时间用于心跳节流
    （剩余充足就不打网络，避免每条 CLI 命令多 1–2 次 HTTP）。
    本地真机 / 本地模拟器不产生这两个字段（为 None，心跳按 device_type 跳过）。
    """
    update_meta_fields(path, {
        "sandbox_id": state.get("sandboxId", ""),
        "device_serial": state.get("adbAddress", ""),
        "device_remote_address": state.get("remoteAddress", ""),
        "sandbox_user": state.get("user", ""),
        "scrcpyUrl": state.get("scrcpyUrl", ""),
        "device_type": state.get("device_type", "sandbox"),
        "lease_fence": state.get("lease_fence"),
        "lease_expires_at": state.get("lease_expires_at"),
    })

def _clear_lease_meta(path: str):
    """清掉本 run 的租约 fence / 到期时间（设备被隔离或已归还后调用）。

    为什么要清：`report`/`release` 都会让服务端 fence +1、租约失效。
    本地若继续留着旧 fence，之后每条命令的心跳都会拿它去 renew，稳定报
    LEASE_LOST（噪音），围栏开启时甚至直接失败。
    """
    update_meta_fields(path, {"lease_fence": None, "lease_expires_at": None})


def _emit(obj, ok_exit=True):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    if not ok_exit:
        raise DeviceError(str(obj.get("error", "设备命令失败")))

def _emit_err(msg, event="device_command_failed", code="DEVICE_CMD_FAILED", raw=""):
    # 设备命令失败统一出口：记录 audit 事件到时间线，然后打印错误退出
    # 异常上报由 AI 在终止时统一调用 report-error 完成
    try:
        from shared.observability.runtime_audit import append_event
        _case_name = get_active_run()
        if _case_name:
            append_event(resolve_case_path(_case_name), "device.failed",
                         {"event": event, "message": msg, "code": code})
    except Exception as e:
        soft_fail("infra", "DEVICE_FAILED_AUDIT_WRITE", e)
    print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    raise DeviceError(msg)


def _emit_guidance(guidance_id, fallback_msg, **detail):
    """输出结构化设备连接引导（见 provisioning/helpers/device_guidance.py），退出码与
    _emit_err 一致（约定失败语义不变），但 stdout 携带可展示给用户的分步指引，
    而非一句话文本报错。guidance_id 未注册时透明回退到 _emit_err，不静默吞错。
    """
    from provisioning.helpers.device_guidance import build_guidance_payload
    payload = build_guidance_payload(guidance_id, detail=detail or None)
    if payload is None:
        _emit_err(fallback_msg)
    # guidance.steps 里的 retry_cmd 是 AI 直接执行的命令 → 渲染为 workspace 入口
    print(render_text(json.dumps({"error": fallback_msg, **payload}, ensure_ascii=False, indent=2)))
    raise DeviceError(fallback_msg)


# ─── 子命令：check-version ──────────────────────────────────
def cmd_check_version(args):
    if not args.adb_address:
        _emit_err("缺少 adb_address（flow-context.json 无 device_serial 记录，请先执行 create）")

    # check_version 内部使用 imeituan_shell，需要 session 存在
    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    device_type = meta.get("device_type", "sandbox")
    _ensure_toolchain(platform)
    reg_result = _register_with_retry(args.adb_address, platform, args.state_file, device_type=device_type,
                                      remote_address=meta.get("device_remote_address") or None)
    if not reg_result["ok"]:
        _emit_err(f"设备注册失败，无法探测版本: {reg_result['detail']}")

    ops = create_platform_ops(args.adb_address, platform=platform,
                              remote_address=meta.get("device_remote_address") or None)
    result = check_version(ops)
    _emit({"ok": True, "adbAddress": args.adb_address, **result})


def clean_device_best_effort(platform: str, serial: str, remote: str = None,
                             extra_packages: tuple = (),
                             prefix: str = "device:setup") -> dict:
    """占用后、使用前清理共享设备：残留运行 App + 临时遗留 + 非可测性的大 App。

    让"清理"成为设备生命周期的一部分：云模拟器/云手机是**共享设备**，实例归还后
    `/data/local/tmp` 的传输/安装产物与日志目录、以及别的用例装的大 App 都留在实例上，
    越积越多甚至撑满设备——"用前清一次"比"装不下再补救"可靠得多。

    步骤与保留边界：
      · ① 停止残留运行中的被测 App（`PlatformOps.stop_running_apps`，含 `extra_packages`
        里的当前目标包）：让设备回到「App 未运行」的起点；
      · ② 临时目录遗留：始终保留本 Skill 的设备侧安装包缓存（`device_temp_keep_paths`，
        即预热资产）；
      · ③ App 清理：只卸载被测 App 前缀里**非可测性**的包，可测性(debug/test)构建
        一律保留（含目标包：目标包为正式构建会被卸载，随后由安装链路按需重装），
        系统包不碰（见 `PlatformOps.clean_device_unused_apps`）。
    返回 `{"stop": {...}, "temp": {...}, "apps": {...}}`，三个子步骤均失败不阻断。
    """
    if not serial:
        return {}
    try:
        ops = create_platform_ops(serial, platform=platform, remote_address=remote or None)
    except Exception as e:  # noqa: BLE001 —— 连不上就跳过清理，不影响主流程
        sys.stderr.write(f"[{prefix}] ⚠️ 清理跳过（无法创建设备句柄）: {e}\n")
        return {}

    result = {}

    # ① 残留运行中的被测 App：先归零，让本次流程从「App 未运行」开始
    try:
        stop = ops.stop_running_apps(extra_packages=extra_packages)
        result["stop"] = stop
        stopped = stop.get("stopped") or []
        if stopped:
            sys.stderr.write(
                f"[{prefix}] 🧹 停止残留运行 App {len(stopped)} 个: {', '.join(stopped)}\n")
        else:
            sys.stderr.write(f"[{prefix}] 🧹 无残留运行 App\n")
    except Exception as e:  # noqa: BLE001 —— 清理失败绝不影响占用/使用主流程
        sys.stderr.write(f"[{prefix}] ⚠️ 停止残留运行 App 失败（忽略）: {e}\n")

    # ② 临时目录遗留（文件 + 目录），保留设备侧安装包缓存
    try:
        res = ops.clean_device_temp_artifacts()
        result["temp"] = res
        n = len(res.get("deleted") or [])
        nd = len(res.get("deletedDirs") or [])
        mb = (res.get("bytes") or 0) / 1024 / 1024
        if n or nd:
            sys.stderr.write(
                f"[{prefix}] 🧹 清理临时遗留 {n} 文件 / {nd} 目录，释放约 {mb:.0f}MB\n")
        else:
            sys.stderr.write(f"[{prefix}] 🧹 无临时遗留\n")
    except Exception as e:  # noqa: BLE001 —— 清理失败绝不影响占用/使用主流程
        sys.stderr.write(f"[{prefix}] ⚠️ 清理临时遗留失败（忽略）: {e}\n")

    # ③ 其它用例遗留的大 App（非可测性才卸，系统包不碰）
    # 目标包显式排除：其去留由安装链路（decide_app_action）决定，清理不得误卸目标包
    try:
        apps = ops.clean_device_unused_apps(exclude_packages=tuple(extra_packages))
        result["apps"] = apps
        gone = apps.get("uninstalled") or []
        if gone:
            sys.stderr.write(
                f"[{prefix}] 🧹 卸载无用 App {len(gone)} 个: {', '.join(gone)}\n")
        else:
            sys.stderr.write(f"[{prefix}] 🧹 无需卸载的无用 App\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[{prefix}] ⚠️ 卸载无用 App 失败（忽略）: {e}\n")

    return result


def cmd_clean_tmp(args):
    """清理设备临时目录里历次占用遗留的安装/传输产物（直接删除，保留本 Skill 缓存）。

    设备端 App 的安装路径由系统决定（hdc/bm 均不能指定安装目录），所以"独立目录"
    只能用于**缓存安装包**，不能用来判断"是否已安装"——版本判定仍走 bm dump。
    本命令默认清理白名单文件 + 非保留子目录，并且**保留本 Skill 自己的设备侧缓存
    目录**（ops.device_temp_keep_paths，如鸿蒙 hap 缓存）与自己的临时文件。
    """
    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    ops = create_platform_ops(args.adb_address, platform=platform,
                              remote_address=meta.get("device_remote_address") or None)
    result = ops.clean_device_temp_artifacts()
    freed_mb = (result.get("bytes") or 0) / 1024 / 1024
    sys.stderr.write(
        f"[device:clean-tmp] 删除 {len(result.get('deleted') or [])} 文件 / "
        f"{len(result.get('deletedDirs') or [])} 目录，释放 {freed_mb:.1f}MB；"
        f"保留 {len(result.get('keptPaths') or [])} 项本 Skill 缓存\n")
    _emit({"ok": True, **result})


# ─── setup 子段：按 OnboardingProfile 能力位独立执行/跳过 ─────
def _register_session(args, steps, log_step):
    """注册设备到 imeituan session（必须在所有 imeituan_shell 调用之前，所有设备类型均需要）。

    “注册即可用”包含两件事，且都归本链路负责（第 2 件实现在
    `devices/toolchain/session.py::imeituan_register`）：
      1. 建会话并绑定本进程（bind_session）；
      2. 为会话选中目标 App 包（set-package）—— App 层命令（`control auth status`、
         `device open-url` …）都按它路由，且**任何一次重新注册都会清空该选择**，
         所以不能留给调用方，否则会出现“设备已注册、App 层命令全失效”的隐形断链。

    返回 (ops, package, main_activity) 供后续段使用，失败直接抛 shared.errors 错误。
    """
    sys.stderr.write("[device:setup] 注册设备到 imeituan session...\n")
    meta = read_meta_fields(args.state_file)
    platform = meta.get("platform", "android")
    device_type = meta.get("device_type", "sandbox")
    reg_result = _register_with_retry(args.adb_address, platform, args.state_file, log=log_step, device_type=device_type,
                                      remote_address=meta.get("device_remote_address") or None)

    # 设备复用阻塞（上一轮 session/ADB 尚未退出）：不判失败、不盲重试同一台；
    # 交由 CLI 组合根执行「隔离旧 sandbox → 换一台 → 再注册一次」。
    if not reg_result["ok"] and reg_result.get("code") in DEVICE_REUSE_ERRORS:
        recover = getattr(args, "device_reuse_recover", None)
        if recover is not None:
            try:
                switched = bool(recover(reg_result))
            except Exception as e:  # noqa: BLE001 —— 换机失败则按原错误上报
                sys.stderr.write(f"[device:setup] 设备复用恢复失败: {e}\n")
                switched = False
            if switched:
                meta = read_meta_fields(args.state_file)
                platform = meta.get("platform", platform)
                device_type = meta.get("device_type", device_type)
                reg_result = _register_with_retry(
                    args.adb_address, platform, args.state_file, log=log_step,
                    device_type=device_type,
                    remote_address=meta.get("device_remote_address") or None)

    if not reg_result["ok"]:
        code = reg_result.get("code") or "SESSION_REGISTER_FAILED"
        detail = reg_result.get("detail") or "未知错误"
        print(json.dumps({
            "ok": False, "steps": steps, "errorCode": code,
            "error": f"imeituan 会话注册失败[{code}]，无法继续 setup: {detail}",
        }, ensure_ascii=False, indent=2))
        raise DeviceError(f"imeituan 会话注册失败[{code}]，无法继续 setup: {detail}",
                          code=code, stage="B1_device")

    ops = create_platform_ops(args.adb_address, platform=platform,
                              remote_address=meta.get("device_remote_address") or None)
    app_desc = get_app_descriptor()
    package = app_desc.package_name
    main_activity = f"{package}/{app_desc.main_activity_class}"
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


def _log_artifact_cache_step(install_result, log_step):
    """把“安装前先看制品缓存”的结果记成一条 step（命中则本轮零下载）。

    制品缓存是 Skill 级共享资源（`shared/artifact_cache.py`）：命中表示本次安装不会
    产生下载，未命中则表示安装时会下载一次并沉淀下来供后续 run / 子 Agent 复用。
    这条 step 让 `device setup` 的结构化输出能区分这两种情况（无需翻 stderr 日志）。
    """
    cache = (install_result.get("versionCheck") or {}).get("artifactCache") or {}
    if cache.get("applicable") is False:
        log_step("artifact_cache", True, f"不适用：{cache.get('reason')}")
        return
    if not cache.get("path"):
        log_step("artifact_cache", True, "无本地制品（平台侧制品通道或无需安装）")
        return
    detail = (f"命中缓存：{cache.get('path')}" if cache.get("hit")
              else f"未命中（{cache.get('reason')}），安装时下载一次")
    log_step("artifact_cache", True, detail)


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
    _log_artifact_cache_step(install_result, log_step)
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
    _log_artifact_cache_step(install_result, log_step)
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
    """全新安装后的**首启收敛**（启动 → 消除首启弹窗链 → 冷重启生效）。

    `needs_first_run_onboarding()` 声明"该设备类型需要这套首启处理"（语义就是"全新安装
    场景需要"），本函数按本次运行的实际情况决定动作：

      · fresh_install=True（本次刚装上 App）：启动 → 用引擎唯一的弹窗执行器收敛
        **首启弹窗链**（隐私协议 → 系统通知权限 → 定位引导/定位权限）→ 冷重启，
        让首次授权状态生效并初始化 AppMock。
      · fresh_install=False（复用现有安装）：只把 App 拉到前台。App 早已同意过隐私协议，
        AppMock 初始化由登录管线的 EnableAppMock 负责，此处不再重复冷重启。

    为什么必须收敛整条链而不是只点「同意」：系统级弹窗（通知/定位权限）是在**App 启动
    之后**才弹出的，漏掉会直接压在登录页（pillow 扫码配置页）上，导致 signin 行文案断言
    与登录态判定双双失败。
    """
    from devices.popup import dismiss_popups

    if not fresh_install:
        launch_ok = ops.launch_app(main_activity)
        log_step("launch_app", launch_ok, "复用现有安装，拉起 App" if launch_ok else "启动失败")
        log_step("settle_first_run_popups", True, "复用现有安装，跳过首启弹窗收敛")
        return

    sys.stderr.write("[device:setup] 启动 App 并收敛首启弹窗链...\n")
    launch_ok = ops.launch_app(main_activity)
    log_step("launch_app", launch_ok, "全新安装后首次启动" if launch_ok else "am start 失败")

    sys.stderr.write("[device:setup] 等待首启弹窗渲染并收敛（隐私协议 → 通知/定位权限）...\n")
    vr = dismiss_popups(prefer_texts=("同意",), wait_for_popup_ms=12000)
    names = "、".join(str(d.get("name") or d.get("kind")) for d in vr.dismissed)
    log_step(
        "settle_first_run_popups", True,
        f"已消除 {len(vr.dismissed)} 个首启弹窗（{names}）" if vr.any_dismissed
        else f"无需消除（{vr.final_state}）",
    )

    sys.stderr.write("[device:setup] 冷重启 App（使首启授权生效并初始化 AppMock）...\n")
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
    首启处理（首启弹窗链收敛）→ 输入法配置 → 前台校验。
    sandbox 全部能力位为 True；local/cloud_device 无 sandboxId，仅要求
    adb_address（device_serial）非空。

    `form=real` 且全新安装时，HarmonyOS 企业签名信任机制会在首次启动时弹出
    系统级拦截弹窗，无法通过 hdc 程序化绕过，也不应沿用 Android 的隐私协议
    自动点击逻辑——直接输出结构化 guidance（harmony_local_untrusted_app）
    并终止 setup，指引用户手动处理（云模拟器 form=emulator 不触发该分支）。
    """
    if not args.adb_address:
        _emit_err("缺少 adb_address（flow-context.json 无 device_serial 记录，请先执行 create）")

    meta = read_meta_fields(args.state_file)
    device_type = meta.get("device_type", "sandbox")
    platform = meta.get("platform", "android")
    if get_device_category(device_type) == "cloud" and not args.sandbox_id:
        _emit_err("缺少 sandbox_id（flow-context.json 无记录，请先执行 create）")

    # 统一按 platform 分发工具链检查（Android→adb，Harmony→hdc，详见
    # devices/lifecycle/local.py 顶部的平台模块契约说明）；sandbox 的
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
    lifecycle = create_device_lifecycle(device_type, platform=platform)

    ops, package, main_activity = _register_session(args, steps, log_step)

    # 设备复用恢复可能已换机：后续步骤一律以最新的 flow-context 为准
    meta = read_meta_fields(args.state_file)

    # 用前自动清理 —— 必须在 session 就绪**之后**：清理走设备 shell 命令，session 未注册
    # 时必然失败（历史上放在 device create 里，冷启动会稳定报一条 warning）。仅云设备需要
    # （共享设备历次占用会在 /data/local/tmp 堆积安装/传输产物）；本地真机是用户自己的手机，
    # 不做侵入式清理。best-effort，失败不影响 setup。
    if get_device_category(device_type) == "cloud":
        clean_res = clean_device_best_effort(
            platform, args.adb_address,
            remote=meta.get("device_remote_address") or None,
            extra_packages=(package,),
            prefix="device:setup",
        )
        # 与其它子步骤一致地记入结构化 steps：否则清理只出现在 stderr，调用方一旦
        # 过滤 / 截断输出（如 `| tail -N`）就无从判断它到底执行没有（实测踩到过一次）。
        stop_res = clean_res.get("stop") or {}
        stopped = stop_res.get("stopped") or []
        log_step(
            "stop_stale_apps", True,
            f"停止残留运行 App {len(stopped)} 个（{', '.join(stopped) if stopped else '无'}）",
        )
        temp_res = clean_res.get("temp") or {}
        if temp_res:
            log_step(
                "clean_device_temp", True,
                f"清理 {len(temp_res.get('deleted') or [])} 文件 / "
                f"{len(temp_res.get('deletedDirs') or [])} 目录，"
                f"释放 {(temp_res.get('bytes') or 0) / 1024 / 1024:.1f}MB，"
                f"保留 {len(temp_res.get('keptPaths') or [])} 项本 Skill 缓存",
            )
        else:
            log_step("clean_device_temp", True, "未执行或失败（best-effort，不影响 setup）")
        apps_res = clean_res.get("apps") or {}
        gone = apps_res.get("uninstalled") or []
        kept_t = apps_res.get("keptTestability") or []
        log_step(
            "clean_device_apps", True,
            f"卸载无用 App {len(gone)} 个（{', '.join(gone) if gone else '无'}）；"
            f"保留可测性 App {len(kept_t)} 个（{', '.join(kept_t) if kept_t else '无'}）",
        )

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
    # devices/lifecycle/local.py 顶部的平台模块契约说明），本函数不感知
    # 具体是哪个平台——sandbox 目前恒为 Android，该平台此值恒为 None，
    # 与 device_type 无关，因此不需要额外按 device_type 分支短路。
    from devices.base import get_platform_module
    fresh_install_guidance_id = get_platform_module(platform).FRESH_INSTALL_GUIDANCE_ID

    # 企业签名信任拦截只发生在**真机**（模拟器忽略签名校验，安装后可正常启动），
    # 故仅 form=real 才需要指引用户手动信任；避免云模拟器（form=emulator）被误暂停。
    if fresh_install and fresh_install_guidance_id and get_device_form(device_type) == "real":
        sys.stderr.write(
            "\n" + "=" * 70 +
            f"\n[device:setup] ⚠️ 全新安装完成，{platform} 平台信任校验将拦截首次启动，"
            "\n需要用户在设备上手动处理，详见 guidance 字段\n" + "=" * 70 + "\n"
        )
        from provisioning.helpers.device_guidance import build_guidance_payload
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

    # ── 能力实测：声明 × 实测 × 闸门（落 workspace/capabilities.json）──
    # 目的：把"平台能否做/能否观测"从"各处 try/except 试错 + 日志降级"收敛为**一次探测结论**
    # （典型：鸿蒙 atm 无 perm 子命令 → 预授权不可用；dumpLayout 间歇异常 → 采集降级）。
    # 探测只读、幂等、best-effort；失败不阻断 setup（上层按"声明值"回落）。
    capability_report = None
    try:
        from devices.capabilities import probe_and_persist
        capability_report = probe_and_persist(platform, ops, package)
        log_step("capability_probe", True, "；".join(capability_report.summary_lines())[:400])
        for line in capability_report.summary_lines():
            sys.stderr.write(f"[device:setup] 能力: {line}\n")
    except Exception as e:                               # noqa: BLE001 - 探测不得阻断 setup
        log_step("capability_probe", True, f"探测跳过（best-effort）: {str(e)[:120]}")

    # 硬依赖闸门：profile 声明的必需能力若实测 unavailable → 立即失败并给建议，
    # 不再拖到登录/断言中途才炸。
    _required = tuple(getattr(profile, "required_capabilities", lambda: ())() or ())
    if _required and capability_report is not None:
        from shared.capabilities import CapabilityState
        _bad = [c for c in _required
                if capability_report.state(c) is CapabilityState.UNAVAILABLE]
        if _bad:
            print(json.dumps({
                "ok": False, "steps": steps, "important_notices": notices,
                "capabilities": capability_report.to_dict(),
                "missing_capabilities": _bad,
            }, ensure_ascii=False, indent=2))
            raise DeviceError(
                f"必需能力实测不可用: {', '.join(_bad)}"
                "（可改用 Android 云模拟器 / 本地真机，或先在设备上人工预置后重试）"
            )

    # 注：不基于"多次拉起仍不在前台"推断信任拦截——探测不到前台的成因还
    # 包括启动慢、闪退等，不是信任拦截的唯一可能。只有"全新安装"这一信号
    # 足够可靠（见上方 fresh_install 分支），此处保留不阻断的警告日志即可。

    # ── 防熄屏：本地真机场景避免测试过程中自动熄屏 ──
    if profile.needs_screen_check():
        sys.stderr.write("[device:setup] 开启防熄屏（保持屏幕常亮）...\n")
        imeituan_exec(["device", "keep-awake", "--on"])

    # adb_keyboard / ensure_foreground / capability_probe 失败、version_outdated_warning 均不阻断 setup
    non_critical = {"adb_keyboard", "ensure_foreground", "version_outdated_warning", "capability_probe"}
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
    result = _register_with_retry(args.adb_address, platform, args.state_file, device_type=device_type,
                                  remote_address=meta.get("device_remote_address") or None)
    print(json.dumps({
        "ok": result["ok"], "adbAddress": args.adb_address,
        "errorCode": result.get("code") or "", "detail": result.get("detail") or "",
    }, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise DeviceError(f"会话注册失败[{result.get('code') or '?'}]: {result.get('detail') or '未知错误'}",
                          code=result.get("code") or "SESSION_REGISTER_FAILED")

# ─── 子命令：disconnect ────────────────────────────────────
def cmd_disconnect(args):
    """收尾断开本 run 的 imeituan 会话（并清空 flow-context 的 session_id）。

    与 `device release`（归还**租约**）职责分离：
      · release  → 设备池层面「这台机器我不用了」，实例保留；
      · disconnect → CLI 会话层面「这个会话可以回收」，避免 `~/.imeituan/sessions`
        无限累积、污染后续注册。

    legacy / 迁移类确定性失败由 `disconnect_session()` 隔离后视为已收尾（返回 ok），
    瞬态失败返回非 0 让清理序列留痕（不阻断后续步骤）。
    """
    from devices.toolchain.session import disconnect_session

    meta = read_meta_fields(args.state_file)
    sid = (meta.get("session_id") or "").strip()
    result = disconnect_session(sid)
    if result.get("ok") and sid:
        update_meta_fields(args.state_file, {"session_id": ""})

    payload = {
        "ok": bool(result.get("ok")),
        "sessionId": sid,
        "code": result.get("code") or "",
        "quarantined": bool(result.get("quarantined")),
        "detail": result.get("detail") or "",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise DeviceError(f"断开 imeituan 会话失败[{payload['code'] or '?'}]: "
                          f"{payload['detail'] or '未知错误'}",
                          code=payload["code"] or "SESSION_DISCONNECT_FAILED")


# ─── 子命令分发（池化命令在 resources/device_pool/commands.py）────
def cmd_device(args):
    """devices 层设备子命令分发：setup / check-version / register / disconnect。

    池化命令（create / query / release）由 `cli.py` 路由到
    `resources.device_pool.commands`，不在本层处理——避免 devices 反向依赖 resources。
    """
    subcmd = args.device_subcmd
    _resolve_device_state(args)
    args.command = subcmd
    handlers = {
        "setup": cmd_setup,
        "check-version": cmd_check_version,
        "register": cmd_register,
        "disconnect": cmd_disconnect,
        "clean-tmp": cmd_clean_tmp,
    }
    handlers[subcmd](args)


# ─── 参数解析 ───────────────────────────────────────────────
# 命令分两级：
#   Level 1（create）：需 active_run + flow-context.json
#   Level 2（setup/check-version/register）：需 flow-context.json + 已有设备信息
# --force-reinstall / --force 是行为开关，不是状态参数。

def _resolve_flow_context(args):
    """Level 1: 从 active_run 解析 flow-context.json 路径。

    用于 create 命令——需要写 state_file 但不需要已有设备信息。
    返回 meta dict 供 Level 2 复用，避免重复读取。
    """
    case_name = get_active_run()
    if not case_name:
        raise UsageError("未设置 active_run，请先执行 flow-init")

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
