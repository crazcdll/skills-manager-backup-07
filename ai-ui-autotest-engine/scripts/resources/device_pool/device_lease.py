#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池编排 —— 领取 / 续约 / 归还 / 状态 / 维护。

`DeviceLeaseManager` 只依赖两个**注入的契约**，因此与具体设备类型、存储后端解耦：

    lifecycle  DeviceLifecycle：query_user_devices / acquire（鸭子类型）
    store      LeaseStore：lock / read / write

租约语义：
    acquire  复用池中空闲实例，否则新建，并登记 owner 租约
    renew    刷新 owner 的 heartbeat_at（命令级心跳，长用例不被误判为"已死"）
    release  删 owner 的全部条目（**只归还租约，不销毁实例**）
    status   叠加 in_use / idle / stale + lease.owner（观测）
    gc       清失效条目（**不销毁任何实例**）

失效判定：`heartbeat_at` 超过 `LEASE_TTL` 未刷新 → 条目失效（占用者可能已崩溃）。
实例回收交由人工 / 平台侧，本层不做。
"""
import os
import time
from datetime import datetime

from shared.paths import get_active_run, get_active_task

from resources.device_pool.lease_store import LocalFileLeaseStore


def lease_owner() -> str:
    """本进程对应的租约 owner：`<run>#<workspace>`。

    为什么必须带 workspace：run 名（如 `flow04-alpha-login`）**不唯一**——同一台机器上
    两个 workspace 完全可能跑同一条 Flow。只用 run 名作 owner 时，两个并发 run 会互相
    `release`/`renew` 对方的租约（实测：`leases.json` 里本 run 的租约被同名 run 清掉）。
    带上 workspace 后，租约归属精确到"哪个工作区"，互不干扰；人为排查时也一目了然。
    """
    run = (get_active_run() or "").strip()
    task = (get_active_task() or "").strip()
    if not run:
        return task
    return f"{run}#{task}" if task else run

# 心跳超时：条目失效（判"占用者已死"）
LEASE_TTL = int(os.environ.get("AI_UITEST_LEASE_TTL", "900"))
# 仅用于 `stale` 展示（实例年龄超此且无租约），不触发任何动作
STALE_TTL = int(os.environ.get("AI_UITEST_STALE_TTL", "86400"))

IN_USE = "in_use"
IDLE = "idle"
STALE = "stale"


def _now() -> int:
    return int(time.time())


def _parse_epoch(value) -> int:
    """把实例的启动时间归一成 epoch 秒。

    平台可能返回 epoch（int/数字串）或 ISO 字符串（`2026-09-19T00:00:00Z`）；
    无法解析一律返回 0（→ 年龄按 0 计，不会误判 stale，安全兜底）。
    """
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except (ValueError, OSError, OverflowError):
        return 0


class DeviceLeaseManager:
    """设备池：在 DeviceLifecycle 之上做"取池 → 复用/新建 → 登记"的编排。"""

    def __init__(self, lifecycle=None, store=None, device_type="sandbox",
                 ttl=None, stale_ttl=None):
        self._lc = lifecycle
        self._store = store or LocalFileLeaseStore()
        self._device_type = device_type
        self.ttl = ttl if ttl is not None else LEASE_TTL
        self.stale_ttl = stale_ttl if stale_ttl is not None else STALE_TTL

    # ── 内部 ─────────────────────────────────────────────────────
    def _new_lease(self, owner: str, owner_mis: str, task: str = None) -> dict:
        now = _now()
        return {
            "owner": owner,
            "owner_task": task or "",
            "owner_mis": owner_mis,
            "device_type": self._device_type,
            "started_at": now,
            "heartbeat_at": now,
        }

    def _living(self, lease) -> bool:
        return bool(lease) and (_now() - int(lease.get("heartbeat_at", 0))) < self.ttl

    def _prune(self, leases: dict) -> int:
        """删除失效条目（心跳超时），返回删除数量。"""
        dead = [k for k, v in leases.items() if not self._living(v)]
        for key in dead:
            leases.pop(key, None)
        return len(dead)

    def _running(self, user_mis: str) -> list:
        return [i for i in (self._lc.query_user_devices(user_mis) or [])
                if i.get("state") == "running"]

    # ── 对外 ─────────────────────────────────────────────────────
    def acquire(self, user_mis: str, owner: str, task: str = None) -> dict:
        """领取设备：复用池中空闲实例，否则新建并登记租约。

        查平台在锁外；"决策 + 登记"在锁内（flock 串行化，避免并发抢同一台）。
        Returns:
            dict: 设备信息 + `reused`(bool) + `leaseOwner`
        """
        running = self._running(user_mis)
        with self._store.lock():
            leases = self._store.read()
            self._prune(leases)
            idle = [i for i in running if i.get("sandboxId") not in leases]
            if idle:
                # 确定性选机：先用启动更早的实例，避免老实例永不被复用
                target = min(idle, key=lambda i: _parse_epoch(i.get("started_at")))
                leases[target["sandboxId"]] = self._new_lease(owner, user_mis, task)
                self._store.write(leases)
                return {**target, "reused": True, "leaseOwner": owner}

        # 无空闲 → 新建（耗时数十秒，放锁外，避免长持锁）
        info = self._lc.acquire(user_mis)
        with self._store.lock():
            leases = self._store.read()
            self._prune(leases)
            leases[info["sandboxId"]] = self._new_lease(owner, user_mis, task)
            self._store.write(leases)
        return {**info, "reused": False, "leaseOwner": owner}

    def renew(self, owner: str) -> int:
        """刷新 owner 名下所有租约的心跳；返回刷新条目数。"""
        with self._store.lock():
            leases = self._store.read()
            touched = 0
            for lease in leases.values():
                if lease.get("owner") == owner:
                    lease["heartbeat_at"] = _now()
                    touched += 1
            if touched:
                self._store.write(leases)
            return touched

    def release(self, owner: str) -> int:
        """归还 owner 名下所有租约（**实例保留**）；返回删除条目数。"""
        with self._store.lock():
            leases = self._store.read()
            keys = [k for k, v in leases.items() if v.get("owner") == owner]
            if keys:
                for key in keys:
                    leases.pop(key, None)
                self._store.write(leases)
            return len(keys)

    def status(self, user_mis: str) -> list:
        """叠加占用态：`in_use`（有效租约）/ `idle`（无租约）/ `stale`（无租约且年龄超窗）。"""
        with self._store.lock():
            leases = self._store.read()
            self._prune(leases)
        result = []
        for inst in (self._lc.query_user_devices(user_mis) or []):
            lease = leases.get(inst.get("sandboxId"))
            age = _now() - _parse_epoch(inst.get("started_at"))
            if self._living(lease):
                state = IN_USE
            elif inst.get("state") == "running" and inst.get("started_at") and age > self.stale_ttl:
                state = STALE
            else:
                state = IDLE
            result.append({
                **inst,
                "status": state,
                "lease": ({"owner": lease.get("owner"),
                           "heartbeatAge": _now() - int(lease.get("heartbeat_at", 0))}
                          if self._living(lease) else None),
            })
        return result

    def gc(self) -> dict:
        """池维护：清失效租约条目（**不销毁任何实例**）。"""
        with self._store.lock():
            leases = self._store.read()
            pruned = self._prune(leases)
            self._store.write(leases)
        return {"pruned": pruned}
