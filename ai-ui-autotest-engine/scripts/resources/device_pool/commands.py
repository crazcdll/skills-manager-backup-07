#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池命令入口：create / query / release。

池化命令（依赖设备池）居于 `resources` 层；设备级命令（setup / register /
check-version）留在 `devices` 层，由 `cli.py` 按子命令路由——依赖方向
`resources → devices`（合法），`devices` 不反向依赖 `resources`。

输出/参数解析辅助（`_emit*` / `_resolve_flow_context` / `_write_sandbox_state`）
保留在 `devices.device_commands`，本模块复用，不重复实现。
"""
import json
import os
import sys
import time

from shared.context import create_device_lifecycle
from shared.errors import DeviceError, soft_fail
from shared.workspace import render_cmd
from shared.case_utils import resolve_mis
from shared.paths import require_active_task
from devices.device_commands import (
    _clear_lease_meta,
    _emit,
    _emit_err,
    _emit_guidance,
    _ensure_toolchain,
    _resolve_flow_context,
    _write_sandbox_state,
)

from resources.device_pool.device_lease import (
    PROVIDER_CONAN, PROVIDER_SANDBOX, REUSE_QUARANTINE_TTL, DevicePool, lease_owner,
)
from resources.device_pool.pool_api import DevicePoolError

# cli.py 依此路由"池化命令 → resources；其余 → devices"（单一事实来源）
POOLED_SUBCMDS = ("create", "query", "release")

# 只有这两类设备进池。本地真机 / 本地模拟器不跨机共享、无需排队，不参与租约。
_PROVIDER_BY_DEVICE_TYPE = {
    "sandbox": PROVIDER_SANDBOX,
    "cloud-emulator": PROVIDER_CONAN,
}


def _provider_of(device_type: str) -> str:
    provider = _PROVIDER_BY_DEVICE_TYPE.get(device_type)
    if not provider:
        _emit_err(f"设备类型 {device_type} 不进设备池（仅 sandbox / cloud-emulator）")
    return provider


def _pool(device_type: str, platform: str) -> DevicePool:
    """按 device_type 构造服务端设备池客户端。"""
    return DevicePool(provider=_provider_of(device_type), platform=platform)


def _require_platform(meta: dict) -> str:
    """从 flow-context.meta 取运行平台（flow-init 保证已写入），缺失则显式失败。

    禁止在这里给平台默认值：默认值会让"漏传/漏配"静默按某个平台处理
    （实测踩过：`create_device_lifecycle(device_type)` 用默认 android 处理鸿蒙云模拟器）。
    """
    platform = str((meta or {}).get("platform") or "").strip()
    if not platform:
        _emit_err("flow-context.json 缺少 meta.platform（flow-init 应已写入；请检查 device.platform）")
    return platform


def _row_view(row: dict) -> dict:
    """把服务端行映射成旧的 status 视图（保持 `device query` 输出兼容）。"""
    return {
        "sandboxId": row.get("device_id"),
        "serial": row.get("device_id"),
        "remoteAddress": row.get("connect_address") or "",
        "state": row.get("state"),
        "status": row.get("state"),
        "owner": row.get("lease_owner") or "",
        "leaseExpiresAt": row.get("lease_expires_at"),
        "useCount": row.get("use_count", 0),
    }


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


# 池满后的有界等待：并发滑动窗口下，别的分片释放（含 120s 复用冷却）后本分片
# 仍有机会拿到设备，而不是直接判死。0 = 不等待（旧行为）。
CLAIM_WAIT_SECONDS = int(os.environ.get("AI_UITEST_CLAIM_WAIT_SECONDS", "120"))
CLAIM_POLL_SECONDS = int(os.environ.get("AI_UITEST_CLAIM_POLL_SECONDS", "15"))


def _claim_with_wait(pool, owner):
    """领取 sandbox；仅对 NO_CAPACITY 做有界轮询等待，其余错误立即抛出。

    为什么不无限等：池子可能被别的团队 / 别的机器占满，无限等会让分片卡死；
    为什么不再立即失败：CLI 是滑动窗口（完成一个补一个），刚释放的设备过 120s
    冷却就能再分，直接判死会造成“明明有 50 台却跑不满并发”。
    """
    deadline = time.time() + max(0, CLAIM_WAIT_SECONDS)
    while True:
        try:
            return pool.claim(owner)
        except DevicePoolError as e:
            if e.code != "NO_CAPACITY" or time.time() >= deadline:
                raise
            wait = max(1, min(CLAIM_POLL_SECONDS, int(deadline - time.time())))
            sys.stderr.write(
                f"[device:create] 暂无空闲设备，{wait}s 后重试"
                f"（最多等 {CLAIM_WAIT_SECONDS}s，可调 AI_UITEST_CLAIM_WAIT_SECONDS）\n")
            sys.stderr.flush()
            time.sleep(wait)


def _release_previous_lease(meta, owner: str) -> None:
    """换机前先归还本 run 对旧设备的租约。

    重领/换设备时若直接 claim，会同时持有「旧设备 + 新设备」两条租约（同一个 owner），
    旧设备因此被白白占用到本轮收尾。这里在领取前先还旧的；服务端只接受 owner 本人
    的 release，所以不会误伤其他 workspace。
    """
    prev = str((meta or {}).get("sandbox_id") or "").strip()
    prev_type = str((meta or {}).get("device_type") or "sandbox")
    if not prev or prev_type not in _PROVIDER_BY_DEVICE_TYPE:
        return
    try:
        pool = _pool(prev_type, _require_platform(meta))
        pool.release(prev, owner, fence=meta.get("lease_fence"))
        sys.stderr.write(f"[device:create] 已归还旧设备租约: {prev[:8]}\n")
    except DevicePoolError as e:
        sys.stderr.write(f"[device:create] 旧设备租约已失效（{e.code}），继续领取: {e}\n")


def quarantine_current_device(args, reason: str, ttl: int = None) -> bool:
    """把 flow-context 当前 sandbox 置为复用隔离（setup 自动换机路径的唯一入口）。

    只对 cloud sandbox 生效；本地真机/模拟器不参与设备池。
    """
    try:
        meta = _resolve_flow_context(args)
    except Exception as e:  # noqa: BLE001 —— 隔离失败不能反向阻断主流程
        sys.stderr.write(f"[device] 读取 flow-context 失败，跳过设备隔离: {e}\n")
        return False
    device_id = str(meta.get("sandbox_id") or "").strip()
    device_type = str(meta.get("device_type") or "sandbox")
    if not device_id or device_type not in _PROVIDER_BY_DEVICE_TYPE:
        return False
    entry_ttl = REUSE_QUARANTINE_TTL if ttl is None else int(ttl)
    try:
        pool = _pool(device_type, _require_platform(meta))
        # quarantined 会自动摘掉租约（服务端把 conan 的占用留给 pending sweeper 补还）。
        pool.report(device_id, "quarantined", error=reason,
                    quarantine_seconds=entry_ttl)
    except DevicePoolError as e:
        sys.stderr.write(f"[device] 设备隔离失败（{e.code}，不影响主流程）: {e}\n")
        return False
    # 服务端已把 fence +1 并摘掉租约：本地旧的 fence 立刻作废，必须同步清掉，
    # 否则后续心跳会一直拿旧 fence 续租（LEASE_LOST 噪音/围栏误失败）。
    _clear_lease_meta(args.state_file)
    sys.stderr.write(
        f"[device] 已将 {device_id[:8]} 置为复用隔离（{entry_ttl}s，{reason}）\n")
    return True


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

    lifecycle = create_device_lifecycle("cloud-emulator", platform=platform)
    pool = _pool("cloud-emulator", platform)
    # 上一轮崩溃留下的 pending 归还先补掉，避免 Conan 配额慢性泄漏。
    pool.sweep_pending(owner)
    _release_previous_lease(meta, owner)

    try:
        info = lifecycle.acquire(resolve_mis())
    except ConanApiError as e:
        _emit_err(f"占用云模拟器失败: {e}", event="device_create_failed",
                  code="DEVICE_CREATE_FAILED", raw=getattr(e, "raw", "") or str(e))

    serial = info.get("sandboxId") or info.get("serial")
    remote = info.get("remoteAddress", "")
    sys.stderr.write(
        f"[device:create] Conan 云模拟器已占用: serial={serial} remote={remote}"
        f"（occupationId={info.get('occupationId')}）\n"
    )

    # Conan 侧的排他性由平台 occupy 保证；这里补一条服务端租约，让「谁在用」对全队可见，
    # 同时让过期回收 / 心跳 / 围栏对两类设备统一口径。绑定失败必须回滚平台占用，
    # 否则本 run 会白占一枚配额（发布后由 sweeper 兜，但能当场回滚就不要留给它）。
    try:
        lease = pool.bind(
            owner, serial,
            connect_address=remote,
            provider_lease_id=info.get("occupationId"),
            form="emulator",
        )
    except DevicePoolError as e:
        from platform import conan_api
        conan_api.release(serial)
        _emit_err(f"绑定 Conan 设备租约失败（已回滚平台占用）: {e}",
                  event="device_create_failed", code="DEVICE_BIND_FAILED")

    _write_sandbox_state({
        "sandboxId": serial, "adbAddress": serial, "user": resolve_mis(),
        "remoteAddress": remote, "scrcpyUrl": "", "device_type": "cloud-emulator",
        "lease_fence": lease.get("fence"),
        "lease_expires_at": lease.get("lease_expires_at"),
    }, args.state_file)
    _emit({
        "ok": True, "reused": int(lease.get("use_count") or 1) > 1, "leaseOwner": owner,
        "sandboxId": serial, "serialNumber": serial, "remoteConnectAddress": remote,
        "occupationId": info.get("occupationId"), "model": info.get("model", ""),
        "version": info.get("version", ""), "device_type": "cloud-emulator",
        "leaseFence": lease.get("fence"),
        "leaseExpiresAt": lease.get("lease_expires_at"),
    })


def _create_sandbox(args, meta):
    """云模拟器：从设备池领取空闲实例并登记 owner 租约（**不再新建实例**）。"""
    platform = _require_platform(meta)
    _ensure_toolchain(platform)
    owner = lease_owner()
    if not owner:
        _emit_err(f"未设置 active_run，请先执行 {render_cmd('flow-init')}")

    pool = _pool("sandbox", platform)
    _release_previous_lease(meta, owner)
    try:
        lease = _claim_with_wait(pool, owner)
    except DevicePoolError as e:
        if e.code == "NO_CAPACITY":
            summary = pool.summary()
            waited = f"；已等待 {CLAIM_WAIT_SECONDS}s" if CLAIM_WAIT_SECONDS > 0 else ""
            _emit_err(
                f"设备池已满：sandbox/{platform} 没有空闲设备"
                f"（总量 {summary.get('total', 0)}，空闲 {summary.get('idle', 0)}{waited}）。"
                f"不要立即重试——等待他人归还，或联系设备池维护者扩容。",
                event="device_create_failed", code="POOL_EXHAUSTED",
                raw=getattr(e, "raw", "") or str(e))
        _emit_err(f"领取设备失败（{e.code}）: {e}", event="device_create_failed",
                  code="DEVICE_CREATE_FAILED", raw=getattr(e, "raw", "") or str(e))

    sid = lease["device_id"]
    addr = lease.get("connect_address") or ""
    if not addr:
        # 库存行缺连接地址（对账没拿到详情 / 人工插行）：当场标 broken 并在服务端
        # 摘掉租约，否则本 run 会带着空 adb 地址跑到 setup 才失败，还白占一台。
        try:
            pool.report(sid, "broken", error="missing_connect_address")
        except DevicePoolError as e:
            sys.stderr.write(f"[device] 标记异常库存失败（{e.code}）: {e}\n")
        _emit_err(f"领取到的 sandbox {sid} 缺少 connect_address（已标记 broken）",
                  event="device_create_failed", code="DEVICE_INVALID_INVENTORY")
    ip, _, port = addr.partition(":")
    reused = int(lease.get("use_count") or 1) > 1
    sys.stderr.write(
        f"[device] 已领取 sandbox {sid} @ {addr}"
        f"（第 {lease.get('use_count')} 次使用，租约至 {lease.get('lease_expires_at')}）\n")

    output = {
        "ok": True, "reused": reused, "leaseOwner": owner,
        "sandboxId": sid, "serialNumber": addr, "remoteConnectAddress": addr,
        "ip": ip, "adbPort": int(port) if port.isdigit() else 8080,
        "scrcpyUrl": lease.get("view_url") or "", "device_type": "sandbox",
        "leaseFence": lease.get("fence"),
        "leaseExpiresAt": lease.get("lease_expires_at"),
    }
    _write_sandbox_state({
        "sandboxId": sid, "adbAddress": addr, "user": resolve_mis(),
        "scrcpyUrl": output["scrcpyUrl"], "device_type": "sandbox",
        "lease_fence": lease.get("fence"),
        "lease_expires_at": lease.get("lease_expires_at"),
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
    """查询池内设备与占用态（idle / in_use / draining / quarantined / broken）。

    口径：读服务端单表，**不读本地文件**——本地只记本 run 自己的租约，
    看不到别人占了什么，用它判断"有没有空闲"必然误判。
    """
    meta = _resolve_flow_context(args)
    platform = _require_platform(meta)
    device_type = meta.get("device_type", "sandbox")
    if device_type not in _PROVIDER_BY_DEVICE_TYPE:
        _emit_err(f"{device_type} 不进设备池；本地设备请用 `device setup` 探测")
    pool = _pool(device_type, platform)
    try:
        rows = pool.list()
        summary = pool.summary()
    except DevicePoolError as e:
        raise DeviceError(f"查询设备池失败（{e.code}）: {e}") from e

    instances = [_row_view(r) for r in rows]
    print(json.dumps({"ok": True, "count": len(instances), "summary": summary,
                      "sandboxes": instances}, ensure_ascii=False, indent=2))


# ─── release ────────────────────────────────────────────────────
def cmd_release(args):
    """归还本 run 名下全部租约（**只还租约，不销毁实例**）。

    Conan 的"还平台占用"在 `DevicePool.release_owner` 内完成（先 conan-cli release
    成功再改服务端状态），这里不再单独处理，避免两处顺序不一致造成配额泄漏。
    """
    owner = lease_owner()
    released = 0
    if owner:
        try:
            meta = _resolve_flow_context(args)
        except Exception as e:  # noqa: BLE001 —— 收尾不能因读上下文失败而中断
            sys.stderr.write(f"[device:release] 读取 flow-context 失败（按默认处理）: {e}\n")
            meta = {}
        device_type = meta.get("device_type", "sandbox")
        if device_type in _PROVIDER_BY_DEVICE_TYPE:
            # 收尾不因缺 platform 而失败：platform 只用于筛选，缺了也能按 owner 归还。
            platform = str(meta.get("platform") or "").strip() or None
            try:
                released = _pool(device_type, platform).release_owner(owner)
            except DevicePoolError as e:
                sys.stderr.write(f"[device:release] 归还租约失败（{e.code}）: {e}\n")
            # 服务端 fence 已前进、租约已作废：本地同步清掉，避免心跳继续拿旧 fence 续租。
            _clear_lease_meta(args.state_file)
        else:
            sys.stderr.write(
                f"[device:release] {device_type} 不进设备池，无需归还租约\n")

    _emit({"ok": True, "owner": owner, "released": released})


# ─── 分发 ───────────────────────────────────────────────────────
def cmd_device(args):
    """resources 层设备池命令分发（create / query / release）。"""
    subcmd = args.device_subcmd
    args.command = subcmd
    handlers = {
        "create": cmd_create,
        "query": cmd_query,
        "release": cmd_release,
    }
    handlers[subcmd](args)
