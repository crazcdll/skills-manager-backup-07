#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池 API 客户端 —— 服务端租约（`device_registry` 单表）的唯一出口。

为什么需要这一层（而不是本地记账）：

  · **租约真相只在服务端**。本地文件锁只能串行化同一台机器上的进程；跨机器 /
    跨 workspace 的并发（真实场景：多个 AICoding 会话同时跑）完全看不见对方，
    于是同一台设备会被两个 run 同时驱动。服务端单行 CAS 才能给出全局排他。

  · **provider 决定占用通道**：
      sandbox —— 实例常驻、我方拥有，服务端直接从库存分配（本层只调 claim）
      conan   —— 平台共享池、需要用户 SSO，服务端不能代为 occupy/release；
                 客户端先 `conan-cli device occupy`，再调本层 bind 绑定租约
    本地真机 / 本地模拟器**不进设备池**，不经过本层。

  · **错误必须带 code**。池满（NO_CAPACITY）不该“立即”重试（命令层有界等待），租约丢失（LEASE_LOST）
    必须立刻停手，传输失败可以重试——三者不能糊成一句文案。

接口与 `yooz-server` 路由一一对应（`/node/api/data/monitor/device/*`）。
"""
from platform.sandbox_api import SandboxApiError, api_get, api_post

_BASE = "/node/api/data/monitor/device"

PROVIDER_SANDBOX = "sandbox"
PROVIDER_CONAN = "conan"


class DevicePoolError(Exception):
    """设备池业务失败。

    code 取值（与服务端一致）：
        INVALID_INPUT / NO_CAPACITY / LEASE_LOST / CONFLICT / NOT_FOUND /
        PROVIDER_ERROR / TRANSPORT（传输层失败，可重试）
    """

    def __init__(self, message, code="PROVIDER_ERROR"):
        super().__init__(message)
        self.code = code


def _call(fn, path, payload, timeout=20):
    try:
        return fn(path, payload, timeout=timeout) or {}
    except SandboxApiError as e:
        raise DevicePoolError(
            str(e), code=getattr(e, "code", None) or "TRANSPORT"
        ) from e


def _compact(body: dict) -> dict:
    """去掉 None，避免把空值当成"显式清空"传给服务端。"""
    return {k: v for k, v in body.items() if v is not None}


# ─── 领取 ────────────────────────────────────────────────────────────────

def claim_sandbox(owner, platform, *, form=None, app=None, run_id=None, task=None,
                  ttl_seconds=None, cooldown_seconds=None) -> dict:
    """从 sandbox 库存领一台（服务端 CAS 分配，池满抛 NO_CAPACITY）。"""
    return _call(api_post, f"{_BASE}/claim", _compact({
        "provider": PROVIDER_SANDBOX,
        "platform": platform,
        "owner": owner,
        "form": form,
        "app": app,
        "run_id": run_id,
        "task": task,
        "ttl_seconds": ttl_seconds,
        "cooldown_seconds": cooldown_seconds,
    }), timeout=30)


def bind_conan(owner, platform, device_id, *, connect_address=None,
               provider_lease_id=None, form=None, app=None, run_id=None,
               task=None, ttl_seconds=None) -> dict:
    """把客户端已 occupy 的 Conan 设备绑定成本 run 的租约。

    排他性由 Conan 保证；服务端只拒绝"已被别人绑定"的冲突（CONFLICT）。
    """
    return _call(api_post, f"{_BASE}/claim", _compact({
        "provider": PROVIDER_CONAN,
        "platform": platform,
        "owner": owner,
        "device_id": device_id,
        "connect_address": connect_address,
        "provider_lease_id": provider_lease_id,
        "form": form,
        "app": app,
        "run_id": run_id,
        "task": task,
        "ttl_seconds": ttl_seconds,
    }), timeout=30)


# ─── 续租 / 归还 ──────────────────────────────────────────────────────────

def renew(device_id, owner, *, fence=None, ttl_seconds=None) -> dict:
    """续租。返回 LEASE_LOST 表示这台已被别人接管，调用方必须立刻停手。"""
    return _call(api_post, f"{_BASE}/renew", _compact({
        "device_id": device_id,
        "owner": owner,
        "fence": fence,
        "ttl_seconds": ttl_seconds,
    }), timeout=15)


def release(device_id, owner, *, fence=None, provider_released=None, error=None) -> dict:
    """归还租约。

    provider_released 只对 conan 有意义：
      True  —— 客户端已成功 `conan-cli release`，行回到候选态 external
      False —— 平台侧还没还，行落 draining/pending，等待 sweeper 补偿
      省略  —— 等价于 False（宁可留 pending，也不能谎报已归还）
    """
    return _call(api_post, f"{_BASE}/release", _compact({
        "device_id": device_id,
        "owner": owner,
        "fence": fence,
        "provider_released": provider_released,
        "error": error,
    }), timeout=15)


# ─── 健康 / 查询 ──────────────────────────────────────────────────────────

def report(device_id, outcome, *, owner=None, error=None, quarantine_seconds=None) -> dict:
    """健康上报：healthy / broken / quarantined（隔离期从服务端全局生效）。"""
    return _call(api_post, f"{_BASE}/report", _compact({
        "device_id": device_id,
        "owner": owner,
        "outcome": outcome,
        "error": error,
        "quarantine_seconds": quarantine_seconds,
    }), timeout=15)


def get(device_id) -> dict:
    """单设备查询（围栏校验：确认这台仍归本 run）。"""
    return _call(api_get, f"{_BASE}/get", {"device_id": device_id}, timeout=15)


def list_devices(*, provider=None, platform=None, state=None, owner=None,
                 keyword=None, page=1, page_size=200) -> dict:
    """查询设备（返回 {rows, total, summary}）。"""
    return _call(api_get, f"{_BASE}/list", _compact({
        "provider": provider,
        "platform": platform,
        "state": state,
        "owner": owner,
        "keyword": keyword,
        "page": page,
        "pageSize": page_size,
    }), timeout=25)


def pending_releases(owner=None) -> dict:
    """平台侧尚未归还的 conan 设备（供客户端启动时补偿）。"""
    params = {"owner": owner} if owner else {}
    return _call(api_get, f"{_BASE}/pending-release", params, timeout=20)
