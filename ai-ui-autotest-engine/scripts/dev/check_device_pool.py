#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备池守卫 —— 固化服务端租约口径，防止回退。

用法：
    python3 scripts/dev/check_device_pool.py

不碰真机、不碰网络：把 `pool_api` 的五个出口替换成假实现，验证**编排层语义**。

覆盖不变量：

  A. owner 口径   `<run>#<task>`；run 缺失时退化为 task；不允许纯 run 名做设备归属
  B. 过期判断     `remaining_seconds` 兼容 `Z` / `+00:00` / 非法串（非法必须触发续期）
  C. 领取口径     sandbox 必须带 owner + platform + run/task；NO_CAPACITY 码必须透出
  D. 归还顺序     conan 先还平台占用、再改服务端状态；平台失败也必须落库（pending 待补偿）
  E. 隔离口径     report 必须带 quarantine_seconds（长隔离不能被短冷却覆盖）
  F. 容量/补偿     summary 必须展平服务端嵌套结构；sweep_pending 必须全局扫（只跳他人持有）
  G. 不再本地记账 源码里不得出现本地租约存储（leases.json / LeaseStore）

退出码：0 全部通过 / 1 有失败。

【为什么需要它】"设备池"曾经用本地文件 + flock 记账，在单机串行场景看似正确，但在
多机 / 多会话并发下会让同一台设备被两次发放（实测同 sandbox 被两个分片同时占用
12–36 分钟）。现在权威在服务端单行 CAS，本脚本把新口径固化下来，改坏了立刻可见。
"""
import inspect
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)

import resources.device_pool.device_lease as dl
import resources.device_pool.pool_api as api


# ═══════════════════════════════════════════════════════════════════
# 夹具：把 pool_api 出口换成记录型假实现
# ═══════════════════════════════════════════════════════════════════

class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, name, result):
        def fn(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if isinstance(result, Exception):
                raise result
            return result
        return fn


class _Patched:
    """临时替换 pool_api / conan_api 的出口。"""

    def __init__(self, **replacements):
        self.replacements = replacements
        self.saved = {}

    def __enter__(self):
        for dotted, fn in self.replacements.items():
            mod_name, attr = dotted.rsplit(".", 1)
            mod = dl if mod_name == "dl" else api
            if mod_name == "conan":
                from platform import conan_api as mod  # noqa: PLC0415
            self.saved[dotted] = (mod, attr, getattr(mod, attr, None))
            setattr(mod, attr, fn)
        return self

    def __exit__(self, *exc):
        for dotted, (mod, attr, old) in self.saved.items():
            if old is None:
                delattr(mod, attr)
            else:
                setattr(mod, attr, old)
        return False


# ═══════════════════════════════════════════════════════════════════
# A. owner 口径
# ═══════════════════════════════════════════════════════════════════

def test_lease_owner_is_run_scoped():
    """owner 必须 `<run>#<task>`：纯 run 名不唯一（同机多 workspace 会撞）。"""
    with _Patched(**{"dl.get_active_run": lambda: "flow04-alpha",
                     "dl.get_active_task": lambda: "ws-home"}):
        assert dl.lease_owner() == "flow04-alpha#ws-home"


def test_lease_owner_falls_back_to_task():
    with _Patched(**{"dl.get_active_run": lambda: "",
                     "dl.get_active_task": lambda: "ws-home"}):
        assert dl.lease_owner() == "ws-home"


def test_lease_owner_empty_when_no_scope():
    with _Patched(**{"dl.get_active_run": lambda: "",
                     "dl.get_active_task": lambda: ""}):
        assert dl.lease_owner() == ""


# ═══════════════════════════════════════════════════════════════════
# B. 过期判断
# ═══════════════════════════════════════════════════════════════════

def test_remaining_seconds_parses_iso():
    assert dl.remaining_seconds("2099-01-01T00:00:00Z") > 0
    assert dl.remaining_seconds("2099-01-01T00:00:00+00:00") > 0
    assert dl.remaining_seconds("2020-01-01T00:00:00Z") < 0


def test_remaining_seconds_invalid_forces_renew():
    """无法解析（空 / 脏数据）必须返回 -1，从而触发一次续期。"""
    for bad in (None, "", "not-a-time", 123):
        assert dl.remaining_seconds(bad) == -1, bad


# ═══════════════════════════════════════════════════════════════════
# C. 领取口径
# ═══════════════════════════════════════════════════════════════════

def test_claim_passes_scope_to_server():
    rec = _Recorder()
    row = {"device_id": "S1", "connect_address": "10.0.0.1:8080", "fence": 7,
           "lease_expires_at": "2099-01-01T00:00:00Z", "use_count": 2}
    with _Patched(**{"api.claim_sandbox": rec("claim", row),
                     "dl.get_active_run": lambda: "run-a",
                     "dl.get_active_task": lambda: "ws-a"}):
        got = dl.DevicePool("sandbox", "android").claim("run-a#ws-a")
    assert got["device_id"] == "S1"
    name, args, kwargs = rec.calls[0]
    assert name == "claim"
    assert args[:2] == ("run-a#ws-a", "android"), args
    assert kwargs.get("run_id") == "run-a" and kwargs.get("task") == "ws-a", kwargs


def test_no_capacity_error_code_survives():
    """池满必须是可判别的 code，不能被包装成普通异常文本。"""
    err = api.DevicePoolError("no idle sandbox/android device", code="NO_CAPACITY")
    with _Patched(**{"api.claim_sandbox": _Recorder()("claim", err)}):
        try:
            dl.DevicePool("sandbox", "android").claim("r#w")
        except api.DevicePoolError as e:
            assert e.code == "NO_CAPACITY", e.code
        else:
            raise AssertionError("池满必须抛错（旧实现会静默新建，掩盖容量问题）")


# ═══════════════════════════════════════════════════════════════════
# D. 归还顺序
# ═══════════════════════════════════════════════════════════════════

def _conan_row(serial="10.0.0.9:5555"):
    return {"device_id": serial, "provider": "conan", "state": "in_use",
            "lease_owner": "r#w", "fence": 2}


def test_release_owner_releases_platform_before_state():
    """conan 必须先把平台占用还掉，再告诉服务端"已归还"。"""
    seq = []
    with _Patched(**{
        "api.list_devices": lambda **kw: {"rows": [_conan_row()]},
        "api.release": lambda *a, **kw: seq.append(("server", kw)) or {"device_id": "x"},
        "conan.release": lambda serial: seq.append(("conan", serial)) or True,
    }):
        assert dl.DevicePool("conan", "harmony").release_owner("r#w") == 1
    assert [s[0] for s in seq] == ["conan", "server"], seq
    assert seq[1][1].get("provider_released") is True, seq


def test_release_owner_marks_pending_when_platform_fails():
    """平台归还失败也必须落库（provider_released=False → pending 待补偿），
    否则服务端以为配额已释放，而 Conan 侧还占着（配额泄漏）。"""
    seq = []
    with _Patched(**{
        "api.list_devices": lambda **kw: {"rows": [_conan_row()]},
        "api.release": lambda *a, **kw: seq.append(("server", kw)) or {"device_id": "x"},
        "conan.release": lambda serial: (_ for _ in ()).throw(RuntimeError("boom")),
    }):
        assert dl.DevicePool("conan", "harmony").release_owner("r#w") == 1
    assert seq and seq[0][1].get("provider_released") is False, seq


def test_release_owner_skips_unowned_rows():
    with _Patched(**{"api.list_devices": lambda **kw: {"rows": [
            {"device_id": "S1", "provider": "sandbox", "lease_owner": ""}]},
            "api.release": _Recorder()("release", {"device_id": "S1"})}):
        assert dl.DevicePool("sandbox", "android").release_owner("r#w") == 0


# ═══════════════════════════════════════════════════════════════════
# E. 隔离口径
# ═══════════════════════════════════════════════════════════════════

def test_report_forwards_quarantine_ttl():
    rec = _Recorder()
    with _Patched(**{"api.report": rec("report", {"device_id": "S1"}),
                     "dl.get_active_run": lambda: "r",
                     "dl.get_active_task": lambda: "w"}):
        dl.DevicePool("sandbox", "android").report(
            "S1", "quarantined", error="ADB_SERVER_COORDINATION", quarantine_seconds=300)
    _name, _args, kwargs = rec.calls[0]
    assert kwargs.get("quarantine_seconds") == 300, kwargs
    assert _args[1] == "quarantined", _args


# ═══════════════════════════════════════════════════════════════════
# F. 容量快照与补偿归还口径
# ═══════════════════════════════════════════════════════════════════

def test_summary_flattens_provider_states():
    """池满提示读的是 `summary['idle'] / ['total']`，服务端返回的是按 provider 嵌套的结构。"""
    with _Patched(**{"api.list_devices": lambda **kw: {
            "rows": [], "total": 3,
            "summary": {"sandbox": {"idle": 1, "in_use": 2}}}}):
        s = dl.DevicePool("sandbox", "android").summary()
    assert (s.get("idle"), s.get("in_use"), s.get("total")) == (1, 2, 3), s


def test_sweep_pending_scans_globally_but_skips_foreign_owner():
    """过期回收会把 owner 清空：只按本 owner 扫会永久漏掉这些 conan 配额。"""
    rows = [
        {"device_id": "C-orphan", "provider": "conan", "lease_owner": None, "fence": 3},
        {"device_id": "C-mine", "provider": "conan", "lease_owner": "r#w", "fence": 1},
        {"device_id": "C-other", "provider": "conan", "lease_owner": "x#y", "fence": 2},
    ]
    rec = _Recorder()
    with _Patched(**{
        "api.pending_releases": rec("pending", {"rows": rows}),
        "api.release": rec("release", {"device_id": "x"}),
        "conan.release": lambda serial: True,
    }):
        dl.DevicePool("conan", "harmony").sweep_pending("r#w")
    ids = [args[0] for name, args, _kw in rec.calls if name == "release"]
    assert ids == ["C-orphan", "C-mine"], ids


# ═══════════════════════════════════════════════════════════════════
# G. 静态守卫：不得回退到本地记账
# ═══════════════════════════════════════════════════════════════════

def test_no_local_lease_store_in_source():
    offenders = []
    for root, dirs, files in os.walk(_SCRIPTS_DIR):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "dev")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            if "lease_store" in text or "leases.json" in text:
                offenders.append(os.path.relpath(path, _SCRIPTS_DIR))
    assert not offenders, f"设备归属不得再落本地文件：{offenders}"


def test_pool_api_has_no_local_fallback():
    """pool_api 不得提供"服务端不可达就写本地"的降级路径（会静默串台）。"""
    src = inspect.getsource(api)
    for banned in ("leases.json", "LocalFileLeaseStore"):
        assert banned not in src, banned


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ✅ {name}")
        except AssertionError as e:
            failed.append((name, e))
            print(f"  ❌ {name}: {e}")
        except Exception as e:  # noqa: BLE001 — 守卫需暴露真实异常
            failed.append((name, e))
            print(f"  💥 {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
