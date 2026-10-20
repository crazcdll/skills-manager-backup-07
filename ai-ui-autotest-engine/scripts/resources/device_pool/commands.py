#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池命令入口：create / query / release / pool-gc。

池化命令（依赖设备池）居于 `resources` 层；设备级命令（setup / register /
check-version）留在 `devices` 层，由 `cli.py` 按子命令路由——依赖方向
`resources → devices`（合法），`devices` 不反向依赖 `resources`。

输出/参数解析辅助（`_emit*` / `_resolve_flow_context` / `_write_sandbox_state`）
保留在 `devices.device_commands`，本模块复用，不重复实现。
"""
import json
import os
import sys

from platform.sandbox_api import SandboxApiError, api_post
from shared.context import create_device_lifecycle
from shared.errors import DeviceError, soft_fail
from shared.workspace import render_cmd
from shared.case_utils import resolve_mis
from shared.paths import get_active_task, require_active_task
from devices.device_commands import (
    _emit,
    _emit_err,
    _emit_guidance,
    _ensure_toolchain,
    _resolve_flow_context,
    _write_sandbox_state,
)

from resources.device_pool.device_lease import DeviceLeaseManager, lease_owner
from resources.device_pool.lease_store import LocalFileLeaseStore

# cli.py 依此路由"池化命令 → resources；其余 → devices"（单一事实来源）
POOLED_SUBCMDS = ("create", "query", "release", "pool-gc")


def _manager(lifecycle=None, device_type="sandbox") -> DeviceLeaseManager:
    """构造绑定本地租约后端的设备池管理器（租约登记 device_type，便于观测/筛选）。"""
    return DeviceLeaseManager(lifecycle, store=LocalFileLeaseStore(), device_type=device_type)


def _require_platform(meta: dict) -> str:
    """从 flow-context.meta 取运行平台（flow-init 保证已写入），缺失则显式失败。

    禁止在这里给平台默认值：默认值会让"漏传/漏配"静默按某个平台处理
    （实测踩过：`create_device_lifecycle(device_type)` 用默认 android 处理鸿蒙云模拟器）。
    """
    platform = str((meta or {}).get("platform") or "").strip()
    if not platform:
        _emit_err("flow-context.json 缺少 meta.platform（flow-init 应已写入；请检查 device.platform）")
    return platform


def _record_device_occupy(device_id, user_mis, *, device_type, platform, app,
                          platform_state, connect_address, view_url, owner, action):
    """best-effort 登记一次设备占用（写平台设备登记表 device_registry）。

    通用登记（不限于 sandbox）：device_type × platform 区分设备类型；
    仅为管理侧记录「谁在何时占用了哪台设备」，**绝不阻塞占用主流程**：
    任何异常（网络/接口不存在/返回码非 0）都只记 soft_fail，不向上抛。
    """
    try:
        if not device_id or not user_mis:
            return
        api_post("/node/api/data/monitor/device/occupy", {
            "device_id": device_id,
            "owner_mis": user_mis,
            "device_type": device_type,
            "platform": platform,
            "app": app,
            "platform_state": platform_state,
            "connect_address": connect_address,
            "view_url": view_url,
            "owner_run": owner,
            "owner_task": get_active_task(),
            "action": action,
        }, timeout=8)
    except Exception as e:  # noqa: BLE001 —— 记录失败不影响占用
        soft_fail("infra", "DEVICE_OCCUPY_RECORD_FAILED", e)
        sys.stderr.write(f"[device] 占用登记失败（已忽略，不影响占用）: {e}\n")


def _record_device_release(device_id, owner):
    """best-effort 登记一次设备归还（写平台设备登记表 device_registry）。

    与 `_record_device_occupy` 对称：只把设备行的 `last_action` 置 `release`、
    刷新 `last_released_at`，**不销毁实例**。设备管理页据此把该设备判为「空闲」
    （页面按 `last_action === 'release'` 派生占用态，不新增 DB 字段）。

    仅为管理侧记录，**绝不阻塞收尾流程**：任何异常都只记 soft_fail，不向上抛。
    """
    try:
        if not device_id:
            return
        api_post("/node/api/data/monitor/device/release", {
            "device_id": device_id,
            "owner_run": owner,
        }, timeout=8)
    except Exception as e:  # noqa: BLE001 —— 记录失败不影响收尾
        soft_fail("infra", "DEVICE_RELEASE_RECORD_FAILED", e)
        sys.stderr.write(f"[device] 归还登记失败（已忽略，不影响收尾）: {e}\n")


# ─── create ─────────────────────────────────────────────────────
def _create_local(args, meta):
    """本地真机：自动探测已连接设备（不走云端创建），写入 flow-context.json。"""
    from devices.base import LocalDeviceProbeError

    platform = _require_platform(meta)
    lifecycle = create_device_lifecycle("local", platform=platform)
    try:
        device_info = lifecycle.acquire(resolve_mis())
    except LocalDeviceProbeError as e:
        if e.guidance_id:
            _emit_guidance(e.guidance_id, str(e), **e.detail)
        _emit_err(str(e))

    serial = device_info["serial"]
    sys.stderr.write(f"[device:create] 本地真机已探测: {serial}（platform={platform}）\n")
    _write_sandbox_state({
        "sandboxId": "", "adbAddress": serial, "user": resolve_mis(),
        "scrcpyUrl": "", "device_type": "local",
    }, args.state_file)
    _emit({
        "ok": True, "sandboxId": "", "serialNumber": serial,
        "remoteConnectAddress": serial, "device_type": "local",
    })


def _create_local_emulator(args, meta):
    """本地模拟器：自动探测/启动已安装模拟器，写入 flow-context.json。"""
    from devices.base import LocalDeviceProbeError

    platform = _require_platform(meta)
    lifecycle = create_device_lifecycle("local-emulator", platform=platform)
    try:
        device_info = lifecycle.acquire(resolve_mis())
    except LocalDeviceProbeError as e:
        if e.guidance_id:
            _emit_guidance(e.guidance_id, str(e), **e.detail)
        _emit_err(str(e))

    serial = device_info["serial"]
    sys.stderr.write(f"[device:create] 本地模拟器已就绪: {serial}（platform={platform}）\n")
    _write_sandbox_state({
        "sandboxId": "", "adbAddress": serial, "user": resolve_mis(),
        "scrcpyUrl": "", "device_type": "local-emulator",
    }, args.state_file)
    _emit({
        "ok": True, "sandboxId": "", "serialNumber": serial,
        "remoteConnectAddress": serial, "device_type": "local-emulator",
    })


def _create_cloud_emulator(args, meta):
    """Conan 云模拟器：从设备池领取（复用已占用的空闲 Conan 设备 / 占用新建）并登记 owner 租约。

    与 sandbox 同构——都走设备池（并发不抢机 + 空闲复用）；差异仅在生命周期实现
    （occupy/release）与消耗型资源的显式归还（见 cmd_release）。
    """
    from platform.conan_api import ConanApiError

    platform = _require_platform(meta)
    _ensure_toolchain(platform)
    owner = lease_owner()
    if not owner:
        _emit_err(f"未设置 active_run，请先执行 {render_cmd('flow-init')}")

    manager = _manager(create_device_lifecycle("cloud-emulator", platform=platform),
                       device_type="cloud-emulator")
    try:
        info = manager.acquire(resolve_mis(), owner=owner, task=get_active_task())
    except ConanApiError as e:
        _emit_err(f"占用云模拟器失败: {e}", event="device_create_failed",
                  code="DEVICE_CREATE_FAILED", raw=getattr(e, "raw", "") or str(e))

    serial = info.get("sandboxId") or info.get("serial")
    remote = info.get("remoteAddress", "")
    reused = bool(info.get("reused"))
    sys.stderr.write(
        f"[device:create] Conan 云模拟器{'（复用池中空闲）' if reused else '已占用'}: "
        f"serial={serial} remote={remote}（occupationId={info.get('occupationId')}）\n"
    )
    # 占用登记（best-effort）：记录到 device_registry（device_type=cloud-emulator），
    # 沉淀为后续「鸿蒙候选」来源。仅为记录，不维护占用状态，失败不影响占用。
    _record_device_occupy(
        # 占用人 = 实际占用者 mis（云模拟器的“共享池”语义由 device_type=cloud-emulator 表达）
        serial, resolve_mis(),
        device_type="cloud-emulator", platform=platform, app=meta.get("app", "meituan"),
        platform_state="running",
        connect_address=remote,
        view_url="",
        owner=owner, action="reuse" if reused else "create",
    )
    _write_sandbox_state({
        "sandboxId": serial, "adbAddress": serial, "user": resolve_mis(),
        "remoteAddress": remote, "scrcpyUrl": "", "device_type": "cloud-emulator",
    }, args.state_file)
    _emit({
        "ok": True, "reused": reused, "leaseOwner": owner,
        "sandboxId": serial, "serialNumber": serial, "remoteConnectAddress": remote,
        "occupationId": info.get("occupationId"), "model": info.get("model", ""),
        "version": info.get("version", ""), "device_type": "cloud-emulator",
    })


def _create_sandbox(args, meta):
    """云模拟器：从设备池领取（复用空闲 / 新建）并登记 owner 租约。"""
    platform = _require_platform(meta)
    _ensure_toolchain(platform)
    owner = lease_owner()
    if not owner:
        _emit_err(f"未设置 active_run，请先执行 {render_cmd('flow-init')}")

    manager = _manager(create_device_lifecycle("sandbox", platform=platform))
    try:
        info = manager.acquire(resolve_mis(), owner=owner, task=get_active_task())
    except SandboxApiError as e:
        _emit_err(f"创建设备失败: {e}", event="device_create_failed",
                  code="DEVICE_CREATE_FAILED", raw=getattr(e, "raw", "") or str(e))

    if not info or not info.get("sandboxId"):
        raise DeviceError("创建模拟器失败")

    sid = info["sandboxId"]
    addr = info.get("serial") or info.get("adbAddress") or ""
    reused = bool(info.get("reused"))
    sys.stderr.write(
        f"[device] {'复用池中空闲' if reused else '新建'}模拟器 ({sid} @ {addr})\n")

    # 占用登记（best-effort，失败不影响占用）
    _record_device_occupy(
        sid, resolve_mis(),
        device_type="sandbox", platform=platform, app=meta.get("app", "meituan"),
        platform_state=info.get("state") or "running",
        connect_address=addr,
        view_url=info.get("scrcpyUrl") or "",
        owner=owner, action="reuse" if reused else "create",
    )

    output = {
        "ok": True, "reused": reused, "leaseOwner": owner,
        "sandboxId": sid, "serialNumber": addr, "remoteConnectAddress": addr,
        "ip": info.get("ip", ""), "adbPort": info.get("adbPort", 8080),
        "scrcpyUrl": info.get("scrcpyUrl", ""), "device_type": "sandbox",
    }
    _write_sandbox_state({
        "sandboxId": sid, "adbAddress": addr, "user": resolve_mis(),
        "scrcpyUrl": output["scrcpyUrl"], "device_type": "sandbox",
    }, args.state_file)

    if not reused:
        try:
            from shared.observability.runtime_audit import append_event
            append_event(os.path.dirname(args.state_file), "device.created",
                         {"sandbox_id": sid, "serial": addr, "device_type": "sandbox"})
        except Exception as e:
            soft_fail("infra", "DEVICE_CREATED_AUDIT_WRITE_FAILED", e)

    _emit(output)


# device_type → create 处理器。未登记即显式报错（不再静默落到 sandbox 分支）。
_CREATE_HANDLERS = {
    "sandbox": _create_sandbox,
    "local": _create_local,
    "local-emulator": _create_local_emulator,
    "cloud-emulator": _create_cloud_emulator,
}


def cmd_create(args):
    """创建设备实例：按 meta.device_type 分派（sandbox/cloud-emulator 走设备池；local/local-emulator 自动探测）。"""
    require_active_task()   # 无 workspace → 先报根因（请先 ws-init）
    if not resolve_mis():
        _emit_err("无法获取 user_mis（flow-context.json meta.user_mis 为空且 resolve_mis 失败）")

    meta = _resolve_flow_context(args)
    device_type = meta.get("device_type", "sandbox")
    handler = _CREATE_HANDLERS.get(device_type)
    if handler is None:
        _emit_err(f"不支持的 device_type: {device_type}")
        return
    handler(args, meta)


# ─── query ──────────────────────────────────────────────────────
def cmd_query(args):
    """查询用户名下设备，叠加占用态（in_use / idle / stale）。按 meta.device_type 取设备源。"""
    meta = _resolve_flow_context(args)
    mis = resolve_mis()
    if not mis:
        _emit_err("无法获取 user_mis")

    from platform.conan_api import ConanApiError
    device_type = meta.get("device_type", "sandbox")
    platform = _require_platform(meta)
    manager = _manager(create_device_lifecycle(device_type, platform=platform),
                       device_type=device_type)
    try:
        instances = manager.status(mis)
    except (SandboxApiError, ConanApiError) as e:
        raise DeviceError(str(e)) from e

    print(json.dumps({"ok": True, "count": len(instances), "sandboxes": instances},
                     ensure_ascii=False, indent=2))


# ─── release ────────────────────────────────────────────────────
def cmd_release(args):
    """归还本 run 名下的租约（**只还租约，不销毁实例**）；云模拟器额外显式归还 Conan 占用。"""
    owner = lease_owner()
    released = _manager().release(owner) if owner else 0

    # 云模拟器（Conan）是消耗型资源（配额有限、占用会到期）：租约之外还需归还
    # Conan 占用，避免设备泄漏。归还走平台唯一出口 platform.conan_api（属"归还
    # 借用的设备"而非"销毁复用型实例"，不违反 DeviceLifecycle 不提供销毁能力的约定）。
    cloud_released = False
    try:
        meta = _resolve_flow_context(args)
    except Exception as e:
        sys.stderr.write(f"[device:release] 读取 flow-context 失败（忽略）: {e}\n")
        meta = {}
    # 云模拟器（sandbox）归还登记：写平台设备管理表（last_action=release /
    # last_released_at），供设备管理页把该设备展示为「空闲」。best-effort，不阻断。
    if meta.get("device_type") == "sandbox":
        _record_device_release(meta.get("sandbox_id"), owner)

    if meta.get("device_type") == "cloud-emulator" and meta.get("device_serial"):
        # 归还登记（best-effort）：只把 device_registry 行的 last_action 置 release。
        _record_device_release(meta.get("device_serial"), owner)
        from platform import conan_api
        try:
            cloud_released = conan_api.release(meta["device_serial"])
        except Exception as e:
            sys.stderr.write(f"[device:release] 归还 Conan 占用失败（忽略，不阻断收尾）: {e}\n")

    _emit({"ok": True, "owner": owner, "released": released, "cloudReleased": cloud_released})


# ─── pool-gc ────────────────────────────────────────────────────
def cmd_pool_gc(args):
    """池维护：清理失效租约条目（**不销毁任何实例**）。"""
    _emit({"ok": True, **_manager().gc()})


# ─── 分发 ───────────────────────────────────────────────────────
def cmd_device(args):
    """resources 层设备池命令分发（create / query / release / pool-gc）。"""
    subcmd = args.device_subcmd
    args.command = subcmd
    handlers = {
        "create": cmd_create,
        "query": cmd_query,
        "release": cmd_release,
        "pool-gc": cmd_pool_gc,
    }
    handlers[subcmd](args)
