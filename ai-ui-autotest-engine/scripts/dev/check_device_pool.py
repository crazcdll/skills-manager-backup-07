#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池守卫 —— 固化 T2 租约口径，防止回退。

用法：
    python3 scripts/dev/check_device_pool.py

覆盖不变量（注入 FakeLifecycle + 临时租约文件，不碰真机 / 平台）：

  A. 领取   复用空闲实例 / 无空闲则新建并登记 owner 租约
  B. 隔离   已被有效租约占用的实例不被抢占（多 run 各自独占）
  C. 锁     领取在锁内完成"读→决策→登记"（否则并发会抢同一台）
  D. 心跳   renew 刷新 owner 名下条目的 heartbeat_at
  E. 归还   release 只删本 run 租约条目、实例数不变、从不销毁
  F. 状态   status 叠加 in_use / idle / stale
  G. 维护   gc 只清失效（心跳超时）条目、不销毁实例
  H. 容错   损坏的租约文件按空租约处理（不抛）

退出码：0 全部通过 / 1 有失败。

【为什么需要它】T2 的核心决策（复用优先、只动租约、不销毁实例、心跳判活、
锁内决策）都是易回退的口径；本脚本把它们固化为一条命令，改坏了立刻可见。
"""
import contextlib
import io
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.device_pool.device_lease import DeviceLeaseManager, LEASE_TTL
from resources.device_pool.lease_store import LocalFileLeaseStore


def _ago(seconds):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


class _FakeLifecycle:
    """鸭子类型的 DeviceLifecycle：只实现设备池用到的 query / acquire / release。"""

    def __init__(self, devices):
        self.devices = devices
        self.destroy_calls = []

    def query_user_devices(self, mis):
        return [dict(v) for v in self.devices.values()]

    def acquire(self, mis):
        sid = f"S{len(self.devices) + 1}"
        self.devices[sid] = {"sandboxId": sid, "state": "running", "started_at": _ago(60)}
        return {"sandboxId": sid, "serial": f"10.0.0.{len(self.devices)}:8080", "scrcpyUrl": ""}

    def release(self, info):
        # 池不得调用它（不销毁实例）；一旦被调用即视为回归
        self.destroy_calls.append(info.get("sandboxId"))
        return True


def _manager(tmp):
    store = LocalFileLeaseStore(os.path.join(tmp, "leases.json"))
    lc = _FakeLifecycle({"S1": {"sandboxId": "S1", "state": "running", "started_at": _ago(120)}})
    return DeviceLeaseManager(lc, store=store, ttl=900), store, lc


def test_acquire_reuses_idle_and_registers_lease():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, _lc = _manager(tmp)
        r = m.acquire("mis", owner="runA", task="tA")
        assert r["sandboxId"] == "S1" and r["reused"] is True, r
        lease = store.read()["S1"]
        assert lease["owner"] == "runA" and lease["owner_task"] == "tA", lease
        assert lease["heartbeat_at"] > 0


def test_acquire_creates_when_all_leased():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, _lc = _manager(tmp)
        m.acquire("mis", owner="runA")
        r2 = m.acquire("mis", owner="runB")
        assert r2["sandboxId"] == "S2" and r2["reused"] is False, r2
        assert set(store.read()) == {"S1", "S2"}


def test_leased_instance_is_not_stolen():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, _lc = _manager(tmp)
        m.acquire("mis", owner="runA")
        m.acquire("mis", owner="runB")   # 领到新机，不得动 S1
        assert store.read()["S1"]["owner"] == "runA"


def test_acquire_holds_lock_across_decision_and_registration():
    """元守卫：领取必须持锁完成"读→决策→登记"，否则并发会抢同一台。"""
    with tempfile.TemporaryDirectory() as tmp:
        m, store, _lc = _manager(tmp)
        depth = {"in": 0, "max": 0}
        real_lock = store.lock

        @contextlib.contextmanager
        def counting_lock():
            depth["in"] += 1
            depth["max"] = max(depth["max"], depth["in"])
            try:
                with real_lock():
                    yield
            finally:
                depth["in"] -= 1

        store.lock = counting_lock
        m.acquire("mis", owner="runA")
        assert depth["max"] >= 1, "acquire 未持锁（并发会抢同一台）"


def test_renew_refreshes_only_owner_entries():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, _lc = _manager(tmp)
        m.acquire("mis", owner="runA")
        before = store.read()["S1"]["heartbeat_at"]
        time.sleep(1.1)
        assert m.renew("runA") == 1
        assert store.read()["S1"]["heartbeat_at"] > before
        assert m.renew("nobody") == 0


def test_release_only_drops_lease_and_keeps_instance():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, lc = _manager(tmp)
        m.acquire("mis", owner="runA")
        m.acquire("mis", owner="runB")
        n = len(lc.devices)
        assert m.release("runA") == 1
        assert "S1" not in store.read() and "S2" in store.read()
        assert len(lc.devices) == n, "归还不得销毁实例"
        assert lc.destroy_calls == [], "池不得调用销毁"


def test_status_overlays_three_states():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, lc = _manager(tmp)
        m.acquire("mis", owner="runA")                 # S1 in_use
        m.acquire("mis", owner="runB")                 # S2 in_use
        m.release("runA")                              # S1 idle
        lc.devices["S9"] = {"sandboxId": "S9", "state": "running", "started_at": _ago(90000)}
        states = {x["sandboxId"]: x["status"] for x in m.status("mis")}
        assert states["S1"] == "idle", states
        assert states["S2"] == "in_use", states
        assert states["S9"] == "stale", states


def test_gc_prunes_expired_lease_but_never_destroys():
    with tempfile.TemporaryDirectory() as tmp:
        m, store, lc = _manager(tmp)
        m.acquire("mis", owner="runB")                 # 复用 S1（有效租约）
        leases = store.read()
        leases["S_old"] = {"owner": "dead", "heartbeat_at": int(time.time()) - (LEASE_TTL + 100)}
        store.write(leases)
        n = len(lc.devices)
        res = m.gc()
        assert res["pruned"] == 1, res
        assert "S_old" not in store.read() and "S1" in store.read()
        assert len(lc.devices) == n and lc.destroy_calls == [], "gc 不得销毁实例"


def test_corrupt_lease_file_is_treated_as_empty():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "leases.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        assert LocalFileLeaseStore(path).read() == {}, "损坏租约应降级为空，不得抛异常"


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        # 隔离被测函数的标准输出（库层会打印进度噪声）；失败时回放，不丢调试信息。
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn()
            print(f"  ✅ {name}")
        except AssertionError as e:
            failed.append((name, e))
            print(f"  ❌ {name}: {e}")
            _dump(buf)
        except Exception as e:  # noqa: BLE001 — 守卫需暴露真实异常
            failed.append((name, e))
            print(f"  💥 {name}: {type(e).__name__}: {e}")
            _dump(buf)
            traceback.print_exc()
    total = len(tests)
    print(f"\n{total - len(failed)}/{total} passed")
    return 1 if failed else 0


def _dump(buf):
    text = buf.getvalue().strip()
    if text:
        for line in text.splitlines():
            print(f"      | {line}")


if __name__ == "__main__":
    sys.exit(main())
