#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池编排 —— 服务端租约（`device_registry` 单表）的薄封装。

**为什么不在这里维护本地租约了**

旧实现用本地 JSON 租约表 + `flock` 记账，只能串行化**同一台机器**
上的进程。真实场景是多台机器 / 多个 AICoding 会话并发跑同一条测试，本地文件彼此
不可见，于是同一台设备会被两个 run 同时驱动（历史事故：同一 sandbox 被两个分片
同时占用 12–36 分钟）。现在租约唯一权威在服务端单行 CAS，本模块只做协议编排：

    acquire → POST /device/claim          （sandbox：服务端从库存分配）
    occupy  → 客户端 conan-cli occupy + POST /device/claim（conan：绑定租约）
    renew   → POST /device/renew          （fence 不匹配即 LEASE_LOST，必须停手）
    release → POST /device/release        （conan 需先 conan-cli release）
    report  → POST /device/report         （broken / quarantined）
    status  → GET  /device/list

不变量：

1. **owner 唯一口径**：所有写操作都用 `lease_owner()`（`<run>#<workspace>`）。
   run 名不唯一，纯 run 名做 owner 会让两个并发 run 互相续/还对方的租约。
2. **本地不缓存占用态**：`flow-context` 只存本 run 自己的 lease_id / fence /
   expires_at（用于心跳节流与围栏），不存"池子里谁空闲"。
3. **失败必须带 code**：`NO_CAPACITY` 不可立即重试（命令层有界等待）、`LEASE_LOST` 立刻停手、
   `TRANSPORT` 可重试——三者不能糊成一句话。

本地真机 / 本地模拟器不进设备池，也不经过本模块。
"""
import os
import sys
from datetime import datetime, timezone

from shared.paths import get_active_run, get_active_task

from resources.device_pool import pool_api
from resources.device_pool.pool_api import DevicePoolError

PROVIDER_SANDBOX = pool_api.PROVIDER_SANDBOX
PROVIDER_CONAN = pool_api.PROVIDER_CONAN

# 租约 TTL 的本地口径：仅用于"是否该提前续期"的判断，真正过期以服务端为准。
LEASE_TTL = int(os.environ.get("AI_UITEST_LEASE_TTL", "900"))
# 提前续期阈值：剩余不足该秒数才真正打网络（避免每条 CLI 命令多两次 HTTP）。
RENEW_AHEAD = int(os.environ.get("AI_UITEST_LEASE_RENEW_AHEAD", "300"))
# 归还后的复用冷却（服务端默认 120s，这里只用于本地提示文案）。
QUARANTINE_TTL = int(os.environ.get("AI_UITEST_DEVICE_QUARANTINE_TTL", "120"))
# 明确命中设备复用错误时使用更长的隔离期（setup 自动换机路径使用）。
REUSE_QUARANTINE_TTL = int(os.environ.get("AI_UITEST_DEVICE_REUSE_QUARANTINE_TTL", "300"))


def lease_owner() -> str:
    """本进程对应的租约 owner：`<run>#<workspace>`。

    为什么必须带 workspace：run 名（如 `flow04-alpha-login`）**不唯一**——同一台机器上
    两个 workspace 完全可能跑同一条 Flow。只用 run 名作 owner 时，两个并发 run 会互相
    `release`/`renew` 对方的租约（实测：本地租约表里本 run 的租约被同名 run 清掉）。

    ⚠️ **本函数是 owner 的唯一来源**：心跳、围栏、认领、归还都必须调用它，
    不允许各自拼 `get_active_run()`（否则会出现「写的是 a#b、续的是 a」的隐形断链）。
    """
    run = (get_active_run() or "").strip()
    task = (get_active_task() or "").strip()
    if not run:
        return task
    return f"{run}#{task}" if task else run


def remaining_seconds(expires_at) -> int:
    """距 `lease_expires_at`（ISO 串）还有多少秒；无法解析返回 -1（→ 触发续期）。"""
    text = str(expires_at or "").strip()
    if not text:
        return -1
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int((dt - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, OSError, OverflowError):
        return -1


class DevicePool:
    """按 provider 绑定的一层协议封装（无状态，可随时新建）。"""

    def __init__(self, provider: str = PROVIDER_SANDBOX, platform: str = None):
        self.provider = provider
        self.platform = platform

    # ── 领取 ─────────────────────────────────────────────────────
    def claim(self, owner: str, *, run_id: str = None, task: str = None,
              ttl_seconds: int = None) -> dict:
        """sandbox：服务端从库存 CAS 分配一台。

        Raises:
            DevicePoolError: code=NO_CAPACITY 表示池已满（不可重试）。
        """
        return pool_api.claim_sandbox(
            owner, self.platform,
            run_id=run_id or get_active_run(),
            task=task or get_active_task(),
            ttl_seconds=ttl_seconds,
        )

    def bind(self, owner: str, device_id: str, *, connect_address: str = None,
             provider_lease_id: str = None, form: str = None,
             ttl_seconds: int = None) -> dict:
        """conan：把已经 occupy 到的设备绑定成本 run 的租约。"""
        return pool_api.bind_conan(
            owner, self.platform, device_id,
            connect_address=connect_address,
            provider_lease_id=provider_lease_id,
            form=form,
            run_id=get_active_run(),
            task=get_active_task(),
            ttl_seconds=ttl_seconds,
        )

    # ── 续租 ─────────────────────────────────────────────────────
    def renew(self, device_id: str, owner: str, *, fence=None,
              ttl_seconds: int = None) -> dict:
        """续租；LEASE_LOST 表示设备已被接管，调用方必须立刻停手。"""
        return pool_api.renew(device_id, owner, fence=fence, ttl_seconds=ttl_seconds)

    def renew_owner(self, owner: str, *, ttl_seconds: int = None) -> list:
        """续租 owner 名下所有设备（数量通常为 1）。"""
        renewed = []
        for row in self.list(owner=owner):
            if not row.get("lease_owner"):
                continue
            renewed.append(pool_api.renew(
                row["device_id"], owner,
                fence=row.get("fence"),
                ttl_seconds=ttl_seconds,
            ))
        return renewed

    # ── 归还 ─────────────────────────────────────────────────────
    def release(self, device_id: str, owner: str, *, fence=None,
                provider_released=None) -> dict:
        return pool_api.release(
            device_id, owner, fence=fence, provider_released=provider_released)

    def release_owner(self, owner: str) -> int:
        """归还 owner 名下全部设备；conan 先还平台占用，再改服务端状态。

        顺序不能反：先 `conan-cli release` 成功，才允许告诉服务端"已归还"，
        否则服务端会把配额记成已释放，而平台侧还占着（配额泄漏）。
        """
        released = 0
        for row in self.list(owner=owner):
            if not row.get("lease_owner"):
                continue
            provider_released = None
            if row.get("provider") == PROVIDER_CONAN:
                provider_released = self._release_conan(row["device_id"])
            try:
                pool_api.release(
                    row["device_id"], owner,
                    fence=row.get("fence"),
                    provider_released=provider_released,
                )
                released += 1
            except DevicePoolError as e:
                sys.stderr.write(
                    f"[device:release] 归还 {row.get('device_id', '')[:8]} 失败"
                    f"（{e.code}）: {e}\n")
        return released

    def _release_conan(self, serial: str) -> bool:
        """归还 Conan 占用；失败返回 False（服务端会落 pending 等 sweeper 补偿）。"""
        from platform import conan_api
        try:
            return bool(conan_api.release(serial))
        except Exception as e:  # noqa: BLE001 —— 失败不能阻断收尾
            sys.stderr.write(
                f"[device:release] Conan 归还失败（保留 pending 待补偿）: {e}\n")
            return False

    def sweep_pending(self, owner: str) -> int:
        """补偿归还：把"平台侧还没还"的 conan 设备补还掉。

        崩溃 / 断网时 `release_owner` 会把这些行留在 draining+pending；
        下一轮 `device create` 开头扫一次，配额不会长期泄漏。

        **必须全局扫**：过期回收（`reclaimExpired`）会把 owner 清空，只按本 run 的
        owner 去查永远查不到这些行 —— 一旦 owner 不再回来，配额就永久泄漏。
        仍被别人持有（owner 非空且不是自己）的 pending 行不动，那是人家正常的
        两阶段归还中途状态。
        """
        try:
            rows = pool_api.pending_releases().get("rows") or []
        except DevicePoolError as e:
            sys.stderr.write(f"[device:create] 读取待归还清单失败（忽略）: {e}\n")
            return 0
        done = 0
        for row in rows:
            if row.get("provider") != PROVIDER_CONAN:
                continue
            holder = str(row.get("lease_owner") or "")
            if holder and holder != owner:
                continue
            ok = self._release_conan(row["device_id"])
            try:
                pool_api.release(
                    row["device_id"], holder or owner,
                    fence=row.get("fence"),
                    provider_released=ok,
                )
                done += 1 if ok else 0
            except DevicePoolError as e:
                sys.stderr.write(
                    f"[device:create] 补偿归还 {row.get('device_id', '')[:8]} 失败: {e}\n")
        return done

    # ── 健康 ─────────────────────────────────────────────────────
    def report(self, device_id: str, outcome: str, *, owner: str = None,
               error: str = None, quarantine_seconds: int = None) -> dict:
        return pool_api.report(
            device_id, outcome,
            owner=owner or lease_owner(),
            error=error,
            quarantine_seconds=quarantine_seconds,
        )

    # ── 查询 ─────────────────────────────────────────────────────
    def list(self, *, owner: str = None, state: str = None, keyword: str = None,
             provider: str = None, page_size: int = 200) -> list:
        data = pool_api.list_devices(
            provider=provider or self.provider,
            platform=self.platform,
            state=state,
            owner=owner,
            keyword=keyword,
            page_size=page_size,
        )
        return data.get("rows") or []

    def summary(self, provider: str = None) -> dict:
        """池容量快照：`{total, idle, in_use, ...}`。

        服务端返回的是嵌套结构 `{provider: {state: count}}`（list 接口按 provider
        分组），这里必须展平 —— 调用方（池满提示）用的是 `summary["idle"]`。
        """
        data = pool_api.list_devices(
            provider=provider or self.provider,
            page_size=1,
        )
        raw = data.get("summary") or {}
        flat: dict = {}
        for states in raw.values():
            for state, count in (states or {}).items():
                flat[state] = flat.get(state, 0) + int(count or 0)
        flat["total"] = sum(
            flat.get(s, 0) for s in ("idle", "in_use", "draining", "quarantined", "broken", "external"))
        if not flat["total"]:
            flat["total"] = sum(v for k, v in flat.items() if k != "total")
        return flat

    def get(self, device_id: str) -> dict:
        """单设备查询；不存在返回 None。"""
        try:
            return pool_api.get(device_id)
        except DevicePoolError as e:
            if e.code == "NOT_FOUND":
                return None
            raise

    def owner_of(self, device_id: str) -> str:
        return (self.get(device_id) or {}).get("lease_owner") or ""
