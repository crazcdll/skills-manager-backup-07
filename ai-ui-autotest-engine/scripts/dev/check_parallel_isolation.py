#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并行隔离守卫 —— 固化「租约归属 / 会话隔离 / 收尾顺序」三条不变量。

用法：
    python3 scripts/dev/check_parallel_isolation.py

覆盖不变量（全部注入临时目录，不碰真机 / 平台 / 真实 imeituan 会话）：

  A. 心跳口径  renew 必须用 `lease_owner()`（run#workspace），纯 run 名不得命中
  B. 认领围栏  空闲可认领、同 owner 刷新、他人有效租约拒绝、过期租约可接管
  C. 会话隔离  只隔离「同 serial + legacy」会话，新格式与其他设备一律不动
  D. 错误分类  legacy / 端口冲突 → 不重试；超时 / 设备不可达 → 可重试
  E. 收尾顺序  device disconnect 必须早于 device release（同一序列内）
  F. 静态守卫  注册链路不得再出现全局 `adb kill-server`；心跳不得再用纯 run 名
  G. 依赖版本  imeituan 使用前必须比对 latest：旧版升级、新版不降级、离线不阻断；
               可执行文件解析只能收敛在 shared/imeituan.py

  H. 设备池  租约必须是用户级单一事实源；release 后进入隔离期，隔离期内不得复用；
               设备复用阻塞（ADB_COORDINATION_* / SESSION_CLEANUP_PENDING）不盲重试

  I. 报告目录 并发/重试必须落到不同目录（`<batch>/<run>[-rN]`）；归档保留过程信息
               但必须脱敏（intake / flow-context / steps / 遥测）；控制台按 case_tag
               映射 case_id（不能用目录顺序猜）

退出码：0 全部通过 / 1 有失败。

【为什么需要它】这三类问题都属于「平时看不出、并发时集中爆」的口径：
租约 owner 拼错 → 15 分钟后设备被二次分配；legacy 会话不隔离 → 每次注册都撞同一堵墙；
disconnect 漏掉 → 会话无限累积。用一条命令把它们固化，改坏立刻可见。
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import traceback

# 源树零字节码：本文件是进程入口，开关必须在引擎包导入之前生效。
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)

from devices.toolchain import session_store
from devices.toolchain.imeituan_cli import classify_error
from execution.engine.sop.constants import CLEANUP_CMDS

import shared.imeituan as imeituan_mod


# ═══════════════════════════════════════════════════════════════════
# 夹具
# ═══════════════════════════════════════════════════════════════════

def _write_session(root, sid, serial, socket="127.0.0.1:15037",
                   adb_entry_socket="127.0.0.1:15037"):
    """在临时 IMEITUAN_HOME 下写一条会话文件，返回路径。"""
    path = os.path.join(root, "sessions", f"{sid}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    meta = {"transport": "adb", "failurePolicy": "retain-session"}
    if adb_entry_socket is not None:
        meta["adbServerSocket"] = adb_entry_socket
    lease = {"serial": serial, "platform": "android"}
    if socket is not None:
        lease["adbServerSocket"] = socket
    data = {
        "sessionId": sid,
        "lease": lease,
        "cleanupStack": [{
            "id": f"transport-disconnect-{serial}",
            "argv": ["adb", "disconnect", serial],
            "meta": meta,
        }],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


@contextlib.contextmanager
def _imeituan_home(tmp):
    """把 session_store 的会话根指向临时目录（仅引擎测试专用变量）。"""
    env = session_store._HOME_ENV
    old = os.environ.get(env)
    os.environ[env] = tmp
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = old


# ═══════════════════════════════════════════════════════════════════
# C. 会话隔离
# ═══════════════════════════════════════════════════════════════════

def test_quarantine_only_legacy_same_serial():
    with tempfile.TemporaryDirectory() as tmp, _imeituan_home(tmp):
        legacy = _write_session(tmp, "sess-legacy", "1.1.1.1:8080",
                                socket=None, adb_entry_socket=None)
        modern = _write_session(tmp, "sess-modern", "1.1.1.1:8080")
        other = _write_session(tmp, "sess-other", "2.2.2.2:8080",
                                socket=None, adb_entry_socket=None)

        moved = session_store.quarantine_legacy("1.1.1.1:8080")

        assert [m["session_id"] for m in moved] == ["sess-legacy"], moved
        assert not os.path.exists(legacy), "legacy 会话必须从 sessions/ 移走"
        assert os.path.exists(moved[0]["to"]), "隔离目标是可回溯的真实文件"
        assert os.path.dirname(moved[0]["to"]) == session_store.stale_root()
        assert os.path.exists(modern), "新格式会话不得被隔离"
        assert os.path.exists(other), "其他设备串的会话不得被隔离"


def test_quarantine_cleanup_entry_missing_socket():
    """lease 有 socket、但 adb 清理条目缺 socket → 同样会在清理时炸，应隔离。"""
    with tempfile.TemporaryDirectory() as tmp, _imeituan_home(tmp):
        path = _write_session(tmp, "sess-half", "1.1.1.1:8080", socket="127.0.0.1:15037")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["cleanupStack"][0]["meta"].pop("adbServerSocket", None)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        moved = session_store.quarantine_legacy("1.1.1.1:8080")
        assert [m["session_id"] for m in moved] == ["sess-half"], moved


def test_quarantine_noop_when_root_missing():
    with tempfile.TemporaryDirectory() as tmp, _imeituan_home(tmp):
        assert session_store.quarantine_legacy("1.1.1.1:8080") == []


# ═══════════════════════════════════════════════════════════════════
# D. 错误分类
# ═══════════════════════════════════════════════════════════════════

def test_classify_deterministic_errors():
    for text in (
        "ADB_SERVER_LEGACY_IDENTITY_UNKNOWN: 缺少创建时的 ADB Server 身份",
        "ADB_PORT_OWNERSHIP_CONFLICT: 当前监听 Server 没有可验证的网络隔离启动记录",
        "ADB_RUNTIME_MIGRATION_REQUIRED",
    ):
        got = classify_error(text)
        assert got["retryable"] is False, (text, got)


def test_classify_device_reuse_errors():
    """单设备会话未清理：不盲重试，且不能被 transport-disconnect 降级成 DEVICE_UNREACHABLE。"""
    for code in ("SESSION_CLEANUP_PENDING", "SESSION_RESOURCES_ACTIVE", "SESSION_CLOSING"):
        got = classify_error(
            f"transport-disconnect-33.195.3.15:8080: {code}: 旧设备操作尚未安全退出")
        assert got["code"] == code, (code, got)
        assert got["retryable"] is False and got.get("device_reuse") is True, (code, got)


def test_classify_adb_coordination_errors():
    """ADB 协调台账错误不能触发换 sandbox。"""
    for code in ("ADB_SERVER_COORDINATION_QUARANTINED",
                 "ADB_SERVER_COORDINATION_UNAVAILABLE",
                 "ADB_SERVER_COORDINATION_CORRUPT"):
        got = classify_error(f"{code}: 旧设备操作尚未安全退出")
        assert got["code"] == code, (code, got)
        assert got["retryable"] is False and got.get("coordination") is True, (code, got)
        assert not got.get("device_reuse"), (code, got)
    got = classify_error("APPMOCK ENABLE FAIL: 旧设备操作尚未安全退出，请稍后重试连接")
    assert got.get("coordination") is True, got


def test_transport_port_picker_skips_used_and_busy():
    """每个 workspace 必须拿到唯一本地端口，且跳过已占用端口。"""
    from shared.transport_port import PORT_START, pick_port

    assert pick_port(set(), lambda p: True) == PORT_START
    assert pick_port({PORT_START, PORT_START + 1}, lambda p: True) == PORT_START + 2
    busy = {PORT_START}
    assert pick_port(set(), lambda p: p not in busy) == PORT_START + 1


def test_transport_port_maps_to_adb_only_for_android():
    """通用 transport port 只在 Android 适配层映射给 imeituan ADB。"""
    from provisioning.prereq.node_env import _imeituan_env
    from shared.paths import ENV_TRANSPORT_PORT

    old = os.environ.get(ENV_TRANSPORT_PORT)
    os.environ[ENV_TRANSPORT_PORT] = "16000"
    try:
        android_env = _imeituan_env({"KEEP": "1"}, "android")
        harmony_env = _imeituan_env({"KEEP": "1"}, "harmony")
    finally:
        if old is None:
            os.environ.pop(ENV_TRANSPORT_PORT, None)
        else:
            os.environ[ENV_TRANSPORT_PORT] = old
    assert android_env["IMEITUAN_CLOUD_ADB_PORT"] == "16000"
    assert android_env["KEEP"] == "1"
    assert "IMEITUAN_CLOUD_ADB_PORT" not in harmony_env


def test_imeituan_run_forwards_generic_port_to_android_cli():
    """Android 适配层必须把通用端口注入 imeituan CLI 的 ADB 环境变量。"""
    import subprocess
    from provisioning.prereq import node_env
    from shared.paths import ENV_PLATFORM, ENV_TRANSPORT_PORT
    import shared.imeituan as imeituan

    seen = []
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")
    old_platform = os.environ.get(ENV_PLATFORM)
    old_port = os.environ.get(ENV_TRANSPORT_PORT)
    orig_run, orig_bin = node_env.run_cli, imeituan.ensure_bin
    os.environ[ENV_PLATFORM] = "android"
    os.environ[ENV_TRANSPORT_PORT] = "16000"
    node_env.run_cli = lambda cmd, **kw: seen.append(kw.get("env_extra")) or ok
    imeituan.ensure_bin = lambda: "/tmp/imeituan"
    try:
        node_env.imeituan_run(["device", "verify"])
    finally:
        node_env.run_cli, imeituan.ensure_bin = orig_run, orig_bin
        for key, value in ((ENV_PLATFORM, old_platform), (ENV_TRANSPORT_PORT, old_port)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    assert seen[0]["IMEITUAN_CLOUD_ADB_PORT"] == "16000", seen


def test_imeituan_run_repairs_then_retries_once():
    """ADB 协调错误必须 repair 后重试一次；非 Android 不得触发修复。"""
    import subprocess
    from provisioning.prereq import node_env
    import shared.imeituan as imeituan

    calls = []
    repaired = []
    fail = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="",
        stderr="ADB_SERVER_COORDINATION_QUARANTINED: 旧设备操作尚未安全退出")
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="{}", stderr="")
    orig_run, orig_repair, orig_bin = (
        node_env.run_cli, node_env._repair_adb_coordination, imeituan.ensure_bin)
    node_env.run_cli = lambda cmd, **kw: calls.append(cmd) or (fail if len(calls) == 1 else ok)
    node_env._repair_adb_coordination = lambda: repaired.append(True) or True
    imeituan.ensure_bin = lambda: "/tmp/imeituan"
    try:
        cp = node_env.imeituan_run(["device", "verify"], adb_recovery=True)
    finally:
        node_env.run_cli, node_env._repair_adb_coordination, imeituan.ensure_bin = (
            orig_run, orig_repair, orig_bin)
    assert cp.returncode == 0
    assert repaired == [True] and len(calls) == 2, (calls, repaired)


def test_imeituan_run_skips_adb_repair_when_recovery_disabled():
    """Harmony/iOS 适配层显式关闭 ADB 修复后，不得执行 Android repair。"""
    import subprocess
    from provisioning.prereq import node_env
    import shared.imeituan as imeituan

    calls = []
    repaired = []
    fail = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="设备连接状态无法读取")
    orig_run, orig_repair, orig_bin = (
        node_env.run_cli, node_env._repair_adb_coordination, imeituan.ensure_bin)
    node_env.run_cli = lambda cmd, **kw: calls.append(cmd) or fail
    node_env._repair_adb_coordination = lambda: repaired.append(True) or True
    imeituan.ensure_bin = lambda: "/tmp/imeituan"
    try:
        cp = node_env.imeituan_run(["device", "verify"], adb_recovery=False)
    finally:
        node_env.run_cli, node_env._repair_adb_coordination, imeituan.ensure_bin = (
            orig_run, orig_repair, orig_bin)
    assert cp.returncode == 1
    assert repaired == [] and len(calls) == 1, (calls, repaired)


def test_node_env_late_transport_port_propagates():
    """Node18 env 缓存不能丢掉 workspace 首次命令才注入的传输端口。"""
    from provisioning.prereq.node_env import _with_live_env
    from shared.paths import ENV_TRANSPORT_PORT

    old = os.environ.get(ENV_TRANSPORT_PORT)
    os.environ[ENV_TRANSPORT_PORT] = "16000"
    try:
        merged = _with_live_env({"PATH": "/node18/bin"})
    finally:
        if old is None:
            os.environ.pop(ENV_TRANSPORT_PORT, None)
        else:
            os.environ[ENV_TRANSPORT_PORT] = old
    assert merged["PATH"] == "/node18/bin"
    assert merged[ENV_TRANSPORT_PORT] == "16000"


def test_classify_transient_errors():
    for text, code in (
        ("TIMEOUT after 30s", "TIMEOUT"),
        ("transport-disconnect-1.1.1.1:8080", "DEVICE_UNREACHABLE"),
        ("ADB_SHARED_SERVER_UNRESPONSIVE", "ADB_SHARED_SERVER_UNRESPONSIVE"),
    ):
        got = classify_error(text)
        assert got["retryable"] is True and got["code"] == code, (text, got)


def test_classify_session_not_found():
    for text in (
        'NOT_FOUND: session sess-abc does not exist',
        '{"error":{"code":"NOT_FOUND","message":"session sess-abc does not exist"}}',
    ):
        got = classify_error(text)
        assert got["code"] == "SESSION_NOT_FOUND" and got["retryable"] is False, (text, got)


def test_disconnect_missing_session_is_idempotent():
    """会话本来就没了 → 收尾必须成功，不能把 cleanup 报成失败。"""
    from devices.toolchain import session as session_mod

    original = session_mod.imeituan_disconnect_device
    session_mod.imeituan_disconnect_device = lambda sid=None: {
        "ok": False, "code": "SESSION_NOT_FOUND", "retryable": False,
        "detail": f"session {sid} does not exist",
    }
    try:
        res = session_mod.disconnect_session("sess-gone")
    finally:
        session_mod.imeituan_disconnect_device = original
    assert res["ok"] is True and res["code"] == "SESSION_NOT_FOUND", res


def test_register_retries_once_when_record_already_gone():
    """legacy 错误点名的会话已被 CLI 清掉时，仍应定向重试一次并成功。"""
    import devices.device_commands as dc
    from devices.toolchain import session as session_mod

    calls = {"n": 0}

    def fake_register(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "code": "ADB_SERVER_LEGACY_IDENTITY_UNKNOWN",
                    "retryable": False, "session_id": "",
                    "detail": "sess-dead\ntransport-disconnect-1.1.1.1:8080: 身份缺失"}
        return {"ok": True, "code": "", "retryable": False,
                "session_id": "sess-new", "detail": ""}

    original_reg = dc.imeituan_register
    original_fix = session_mod.remediate_failed_session
    dc.imeituan_register = fake_register
    # 记录已不存在：隔离不到任何文件，但 session_id 能解析出来
    session_mod.remediate_failed_session = lambda detail: {
        "session_id": "sess-dead", "quarantined": None}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "flow-context.json")
            with open(state, "w", encoding="utf-8") as fh:
                json.dump({"meta": {}}, fh)
            res = dc._register_with_retry("1.1.1.1:8080", "android", state)
    finally:
        dc.imeituan_register = original_reg
        session_mod.remediate_failed_session = original_fix
    assert calls["n"] == 2, calls
    assert res["ok"] and res["session_id"] == "sess-new", res


# ═══════════════════════════════════════════════════════════════════
# E. 收尾顺序
# ═══════════════════════════════════════════════════════════════════

def test_fence_defaults_cover_device_commands():
    """默认围栏：设备/截图/恢复类命令必须校验归属；纯数据与恢复入口豁免。"""
    import argparse

    import cli

    def fence(cmd, sub=""):
        return cli._should_fence(cmd, argparse.Namespace(device_subcmd=sub))

    for cmd in ("mock", "log-record", "override-step-result", "step", "open-url",
                "screenshot", "env-prepare", "flow-next", "flow-advance"):
        assert fence(cmd) is True, f"{cmd} 必须受围栏保护"
    for cmd in ("flow-fail", "mis", "cleanup", "flow-status", "gen-report",
                "report-error", "flow-finalize", "ack", "skip-case"):
        assert fence(cmd) is False, f"{cmd} 属恢复/只读命令，必须豁免"
    assert fence("device", "setup") is True
    assert fence("device", "register") is True
    assert fence("device", "clean-tmp") is True
    for sub in ("create", "query", "release", "disconnect"):
        assert fence("device", sub) is False, f"device {sub} 豁免"


def test_cleanup_disconnects_before_release():
    cmds = list(CLEANUP_CMDS)
    assert any("device disconnect" in c for c in cmds), cmds
    assert any("device release" in c for c in cmds), cmds
    di = next(i for i, c in enumerate(cmds) if "device disconnect" in c)
    ri = next(i for i, c in enumerate(cmds) if "device release" in c)
    assert di < ri, f"disconnect 必须先于 release：{cmds}"


# ═══════════════════════════════════════════════════════════════════
# F. 静态守卫
# ═══════════════════════════════════════════════════════════════════

def _read(*parts):
    with open(os.path.join(_SCRIPTS_DIR, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_no_global_adb_kill_server():
    """守卫的是**可执行代码**：`subprocess.run(["adb", "kill-server"])` 这类调用。

    文档/注释里出现 `adb kill-server` 是允许的（用于解释为什么不能这么做）。
    """
    src = _read("devices", "device_commands.py")
    assert '"adb", "kill-server"' not in src and "'adb', 'kill-server'" not in src, \
        "注册链路不得再执行全局 adb kill-server（打断并发 run）"


def test_heartbeat_uses_lease_owner():
    src = _read("cli.py")
    assert "owner = _lease_owner()" in src, "命令级心跳必须使用 lease_owner()"
    assert "owner = get_active_run()" not in src, "心跳不得再使用纯 run 名续约"


def test_register_uses_classified_retry():
    src = _read("devices", "device_commands.py")
    assert "_REGISTER_ATTEMPTS" in src and "retryable" in src, "注册必须按错误分类重试"
    assert "remediate_failed_session" in src, "legacy 会话失败必须定向隔离后重试"


# ═════════════════════════════════════════════════════════════════
# G. 依赖版本（imeituan 使用即最新）
# ═══════════════════════════════════════════════════════════════

@contextlib.contextmanager
def _patched_imeituan(tmp, *, remote, versions, install_ok=True):
    """把受管安装 / registry 查询注入临时目录（离线，不碰真实 npm 与用户安装）。"""
    prefix = os.path.join(tmp, "npm")
    bin_path = os.path.join(prefix, "bin", "imeituan")
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)
    with open(bin_path, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\n")

    names = ("_DATA_DIR", "_PREFIX", "_STATE_PATH", "_LOCK_PATH", "_ensured",
             "_ensured_at", "_bin_version", "_remote_latest", "_install_latest")
    original = {n: getattr(imeituan_mod, n) for n in names}
    calls = {"install": 0}
    current = {"version": versions[0]}

    imeituan_mod._DATA_DIR = tmp
    imeituan_mod._PREFIX = prefix
    imeituan_mod._STATE_PATH = os.path.join(tmp, "state.json")
    imeituan_mod._LOCK_PATH = os.path.join(tmp, "install.lock")
    imeituan_mod._ensured = None
    imeituan_mod._bin_version = lambda path: current["version"] if path else None
    imeituan_mod._remote_latest = lambda: remote

    def fake_install():
        calls["install"] += 1
        if install_ok:
            current["version"] = versions[-1]
        return install_ok, ("" if install_ok else "npm ERR! EACCES")

    imeituan_mod._install_latest = fake_install
    try:
        yield calls, current
    finally:
        for name, value in original.items():
            setattr(imeituan_mod, name, value)


def test_imeituan_version_compare():
    """最新判定：空版本要装、旧版要升、新版不得降级、预发布以 latest 为准。"""
    assert imeituan_mod.is_older(None, "0.6.4")
    assert imeituan_mod.is_older("0.6.2", "0.6.3")
    assert imeituan_mod.is_older("0.6.4-beta", "0.6.4")
    assert not imeituan_mod.is_older("0.6.4", "0.6.4")
    assert not imeituan_mod.is_older("0.6.5", "0.6.4")
    assert not imeituan_mod.is_older("0.6.4", None), "registry 不可达时不得判为需要升级"


def test_placeholder_answer_expands_date_expression():
    """答案本身是 {T+N} 时也必须展开（批量任务实际踩到的根因）。"""
    from datetime import datetime, timedelta
    from shared.placeholders import substitute

    expected = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    out = substitute(
        "checkinDate={checkinDate}&checkoutDate={checkoutDate}",
        {"checkinDate": "{T+10:%Y-%m-%d}", "checkoutDate": "{T+11:%Y-%m-%d}"},
    )
    assert f"checkinDate={expected}" in out, out
    assert "{T+" not in out, out


def test_placeholder_answer_expands_nested_names():
    """答案可继续引用其他命名占位符；自引用必须终止。"""
    from shared.placeholders import substitute

    assert substitute("x={a}", {"a": "{b}", "b": "v"}) == "x=v"
    assert substitute("x={a}", {"a": "{a}"}) == "x={a}"


def test_placeholder_date_base_is_shared_and_env_overridable():
    """同一批日期必须用同一个基线；支持 T-N 与 {{T+N}}。"""
    from shared.placeholders import substitute

    old = os.environ.get("AI_UITEST_DATE_BASE")
    os.environ["AI_UITEST_DATE_BASE"] = "2026-01-01"
    try:
        out = substitute("a={T+10}&b={T-1}&c={{T+2:%Y-%m-%d}}", {})
    finally:
        if old is None:
            os.environ.pop("AI_UITEST_DATE_BASE", None)
        else:
            os.environ["AI_UITEST_DATE_BASE"] = old
    assert out == "a=2026-01-11&b=2025-12-31&c=2026-01-03", out


def test_find_unresolved_placeholders_covers_dates_and_names():
    """执行前守卫必须同时识别日期与普通占位符。"""
    from shared.placeholders import find_unresolved_placeholders

    got = find_unresolved_placeholders("x={T+10:%Y-%m-%d}&y={checkinDate}")
    assert got == ["{T+10:%Y-%m-%d}", "{checkinDate}"], got


def test_imeituan_version_parsing():
    """新旧两种 --version 输出都要能解析（新 CLI 是 JSON envelope）。"""
    assert imeituan_mod.parse_version(
        '{"schemaVersion":"terminal-cli/v1","success":true,'
        '"data":{"version":"0.6.3"},"error":null}') == "0.6.3"
    # 前面有告警行时也必须优先取 JSON 里的 CLI 版本，而不是 node 版本
    assert imeituan_mod.parse_version(
        'warn: node v18.20.4\n{"data":{"version":"0.6.3"}}') == "0.6.3"
    assert imeituan_mod.parse_version(
        "@mtfe/imeituan-cli/0.6.3 darwin-arm64 node-v22.20.0") == "0.6.3"
    assert imeituan_mod.parse_version("  0.6.10\n") == "0.6.10"
    assert imeituan_mod.parse_version("") is None
    # 解析不出 CLI 版本时返回 None（宁可重新安装，也不能把 node 版本当 CLI 版本）
    assert imeituan_mod.parse_version("warn: node v18.20.4") is None


def test_imeituan_upgrade_when_not_latest():
    """使用依赖时发现旧版 → 自动升级；TTL 内不重复安装。"""
    with tempfile.TemporaryDirectory() as tmp:
        with _patched_imeituan(tmp, remote="0.6.9", versions=["0.6.3", "0.6.9"]) as (calls, _v):
            res = imeituan_mod.ensure(force=True)
            assert res["action"] == "upgraded", res
            assert res["version"] == "0.6.9", res
            assert calls["install"] == 1, "旧版必须触发一次升级"

            # 模拟新进程（清空进程内缓存）：TTL 内直接复用落盘结论，不重复安装
            imeituan_mod._ensured = None
            again = imeituan_mod.ensure()
            assert again["action"] == "up-to-date", again
            assert again["version"] == "0.6.9", again
            assert calls["install"] == 1, "TTL 内必须复用结论，不得重复安装"


def test_imeituan_never_downgrades():
    """本地版本高于 registry latest（内部预发/灰度）时保持不动。"""
    with tempfile.TemporaryDirectory() as tmp:
        with _patched_imeituan(tmp, remote="0.6.4", versions=["0.7.0"]) as (calls, _v):
            res = imeituan_mod.ensure(force=True)
            assert res["action"] == "up-to-date" and calls["install"] == 0, res


def test_imeituan_offline_keeps_current():
    """registry 不可达时不阻断 run：保留当前副本，标记 offline。"""
    with tempfile.TemporaryDirectory() as tmp:
        with _patched_imeituan(tmp, remote=None, versions=["0.6.3"]) as (calls, _v):
            res = imeituan_mod.ensure(force=True)
            assert res["action"] == "offline", res
            assert res["bin"].endswith(os.path.join("bin", "imeituan")), res
            assert calls["install"] == 0

            # 模拟新进程：离线结论在 TTL 内仍为 offline（不得谎报已是最新）
            imeituan_mod._ensured = None
            again = imeituan_mod.ensure()
            assert again["action"] == "offline", again


def test_imeituan_install_failure_backoff():
    """升级失败：不得谎报“已是最新”，且在退避窗口内不得反复重装。"""
    with tempfile.TemporaryDirectory() as tmp:
        with _patched_imeituan(tmp, remote="0.6.9", versions=["0.6.3"],
                              install_ok=False) as (calls, _v):
            res = imeituan_mod.ensure(force=True)
            assert res["action"] == "install-failed", res
            assert res["version"] == "0.6.3" and "EACCES" in res["error"], res
            assert calls["install"] == 1

            # 模拟新进程：失败结论在退避窗口内仍为 install-failed，且不重装
            imeituan_mod._ensured = None
            again = imeituan_mod.ensure()
            assert again["action"] == "install-failed", again
            assert calls["install"] == 1, "退避窗口内不得重复安装"


def test_imeituan_old_version_is_refused():
    """低于 MIN_VERSION 必须在**使用出口**就失败，而不是写入 legacy 会话。"""
    from shared.errors import AutotestError

    with tempfile.TemporaryDirectory() as tmp:
        with _patched_imeituan(tmp, remote="0.6.3", versions=["0.5.0"],
                              install_ok=False):
            try:
                imeituan_mod.ensure_bin()
            except AutotestError as e:
                assert e.code == "IMEITUAN_VERSION_UNSUPPORTED", e.code
            else:
                raise AssertionError("0.5.0 低于最低版本，必须拒绝执行")


# ═════════════════════════════════════════════════════════════════
# H. 设备池：用户级共享 + release 后复用隔离
# ═══════════════════════════════════════════════════════════════

def test_device_pool_is_user_level():
    """租约必须是机器级单一事实源，不能落在单个 Skill 安装目录下。"""
    from shared.paths import DEVICE_POOL_DIR, SKILL_DIR, STATE_HOME

    assert DEVICE_POOL_DIR == os.path.join(STATE_HOME, "device-pool"), DEVICE_POOL_DIR
    assert not DEVICE_POOL_DIR.startswith(SKILL_DIR), DEVICE_POOL_DIR


def test_machine_level_state_outside_skill():
    """机器级状态必须落在 Skill 目录之外（跨安装共享 + 不随 Skill 更新丢失）。

    覆盖：控制台服务、凭据、工具链缓存、制品缓存、运行态与报告归档。
    为什么固化：Skill 会被多份安装/镜像（`~/.catpaw/skills`、各项目的
    `.claude/skills`、`.catpaw/skills/skills-market`），落在 SKILL_DIR 内的状态
    会各存一份；常驻服务的心跳还会把删掉的目录重建回来（幽灵目录），
    而 Skill 自动更新会整目录替换 —— 在跑的 workspace 与历史报告会直接丢。
    """
    from shared import artifact_cache
    from shared.paths import (
        CONSOLE_DIR, CREDENTIALS_DIR, OUTPUT_DIR, RUN_DIR, SKILL_DIR, STATE_HOME,
        TOOLCHAIN_DIR,
    )

    expected_root = os.path.abspath(STATE_HOME) + os.sep
    skill_prefix = os.path.abspath(SKILL_DIR) + os.sep
    for name, path in (("console", CONSOLE_DIR), ("credentials", CREDENTIALS_DIR),
                       ("toolchain", TOOLCHAIN_DIR), ("run", RUN_DIR),
                       ("reports", OUTPUT_DIR),
                       ("artifacts", artifact_cache.ARTIFACTS_DIR)):
        real = os.path.abspath(path)
        assert not real.startswith(skill_prefix), f"{name} 落在 Skill 目录内: {real}"
        assert real.startswith(expected_root), \
            f"{name} 未落在机器级目录: {real}"


def test_device_reuse_recovery_switches_sandbox():
    """setup 的组合根恢复：隔离 → release → create，并把新设备写回 args。"""
    import argparse
    import cli

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "flow-context.json")
        with open(state, "w", encoding="utf-8") as fh:
            json.dump({"meta": {
                "device_type": "sandbox", "platform": "android",
                "sandbox_id": "S1", "device_serial": "1.1.1.1:8080",
                "user_mis": "mis",
            }}, fh)

        calls = []
        originals = (cli._quarantine_current_device, cli._pool_release, cli._pool_create)
        cli._quarantine_current_device = lambda a, code: calls.append(("quarantine", code)) or True
        cli._pool_release = lambda a: calls.append(("release",))

        def fake_create(a):
            calls.append(("create",))
            with open(state, encoding="utf-8") as fh:
                data = json.load(fh)
            data["meta"].update({"sandbox_id": "S2", "device_serial": "2.2.2.2:8080"})
            with open(state, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

        cli._pool_create = fake_create
        try:
            args = argparse.Namespace(state_file=state)
            ok = cli._recover_device_reuse(
                args, {"code": "SESSION_CLEANUP_PENDING"})
        finally:
            (cli._quarantine_current_device, cli._pool_release, cli._pool_create) = originals

        assert ok is True
        assert args.sandbox_id == "S2" and args.adb_address == "2.2.2.2:8080"
        assert [c[0] for c in calls] == ["quarantine", "release", "create"], calls


def test_imeituan_resolution_single_entry():
    """静态守卫：imeituan 可执行文件/版本解析不得散落在调用方。"""
    # 动态拼接，避免守卫脚本自身命中字面量
    needles = ('which(' + '"imeituan")', 'which(' + "'imeituan')")
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(_SCRIPTS_DIR):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, _SCRIPTS_DIR)
            if rel == os.path.join("shared", "imeituan.py"):
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if any(n in text for n in needles):
                offenders.append(rel)
    assert not offenders, f"imeituan 解析必须唯一收敛在 shared/imeituan.py：{offenders}"


def test_redaction_handles_escaped_json_and_short_secrets():
    """note 内嵌 JSON（quote 被转义）也要脱敏；短值不得误伤时间戳等普通文本。"""
    from shared.output_guard import redact_text

    note = json.dumps({"password": "1234"}, ensure_ascii=False)
    wrapped = json.dumps({"note": note}, ensure_ascii=False)
    out = redact_text(wrapped)
    assert "1234" not in out, out
    assert "***" in out, out
    # 4 位短值不做精确替换，避免把时间戳/计数打花
    assert redact_text("ts=1234 count=1234", ["1234"]) == "ts=1234 count=1234"
    # >=6 位的 secret 仍做精确替换（覆盖拼进任意字符串的场景）
    assert "SecretPass" not in redact_text("landing=x&pwd=SecretPass", ["SecretPass"])


def test_report_output_dir_is_unique_per_run():
    """同一 batch 的同一 run 重试必须落新目录，不能覆盖上一轮证据。"""
    import shared.paths as paths

    old_output = paths.OUTPUT_DIR
    old_task = os.environ.pop(paths.ENV_WORKSPACE, None)
    with tempfile.TemporaryDirectory() as tmp:
        paths.OUTPUT_DIR = os.path.join(tmp, "reports")
        try:
            first = paths.allocate_run_output_dir("batch-A", "shard-01")
            second = paths.allocate_run_output_dir("batch-A", "shard-01")
            assert os.path.basename(first) == "shard-01", first
            assert os.path.basename(second) == "shard-01-r2", second
            assert os.path.dirname(first) == os.path.join(paths.OUTPUT_DIR, "batch-A")
            assert os.path.isdir(os.path.dirname(first))
        finally:
            paths.OUTPUT_DIR = old_output
            if old_task is None:
                os.environ.pop(paths.ENV_WORKSPACE, None)
            else:
                os.environ[paths.ENV_WORKSPACE] = old_task


def test_archive_keeps_process_info_but_redacts_secrets():
    """归档保留 inspect_tree / dumps 等过程信息；intake / flow-context / 日志必须脱敏。"""
    import shared.paths as paths
    from shared.observability.runtime_audit import archive_run

    secret = "SecretPass123"
    old_tasks = paths.TASKS_DIR
    old_task_env = os.environ.get(paths.ENV_WORKSPACE)
    with tempfile.TemporaryDirectory() as tmp:
        paths.TASKS_DIR = os.path.join(tmp, "tasks")
        os.environ[paths.ENV_WORKSPACE] = "task-x"
        task = os.path.join(paths.TASKS_DIR, "task-x")
        run_dir = os.path.join(task, "runs", "run-1")
        case_dir = os.path.join(run_dir, "cases", "case_01")
        os.makedirs(case_dir, exist_ok=True)
        os.makedirs(os.path.join(run_dir, "dumps"), exist_ok=True)
        os.makedirs(os.path.join(task, "audit"), exist_ok=True)

        def _dump(path, data):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

        _dump(os.path.join(task, "intake.json"),
              {"answers": {"password": secret, "account": "13800000000"}})
        _dump(os.path.join(run_dir, "flow-context.json"),
              {"meta": {"batch_id": "batch-A"}, "env": {"_password_raw": secret}})
        with open(os.path.join(case_dir, "steps.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"sid": "S1", "status": "note",
                                 "note": json.dumps({"password": secret})}) + "\n")
        with open(os.path.join(run_dir, "inspect_tree.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"password": secret, "nodes": [1, 2, 3]}))
        with open(os.path.join(task, "console-ingest.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"line": f"--password {secret}"}) + "\n")
        plain = os.path.join(run_dir, "dumps", "plain.txt")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write("process info\n")
        src_ino = os.stat(plain).st_ino
        frames_dir = os.path.join(case_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        shot = os.path.join(frames_dir, "step1.png")
        with open(shot, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        shot_ino = os.stat(shot).st_ino

        try:
            archive = archive_run(run_dir, os.path.join(tmp, "reports", "batch-A", "run-1"))

            # 过程信息保留（归档的是整个 workspace，run 内容在 runs/run-1 下）
            assert os.path.isfile(os.path.join(archive, "runs", "run-1", "inspect_tree.json"))
            assert os.path.isfile(os.path.join(archive, "runs", "run-1", "dumps", "plain.txt"))
            # 媒体零拷贝（硬链）；文本必须复制 —— 否则后续 run 追加日志会污染归档快照
            assert os.stat(os.path.join(
                archive, "runs", "run-1", "cases", "case_01", "frames", "step1.png"
            )).st_ino == shot_ino
            assert os.stat(os.path.join(
                archive, "runs", "run-1", "dumps", "plain.txt")).st_ino != src_ino
            # 后续向源文件追加（console-ingest.jsonl 就是 append-only）不得影响归档
            with open(plain, "a", encoding="utf-8") as fh:
                fh.write("later run appended\n")
            with open(os.path.join(
                    archive, "runs", "run-1", "dumps", "plain.txt"), encoding="utf-8") as fh:
                assert "later run appended" not in fh.read()
            # 所有文件都不含明文（按字节断言，二进制文件也覆盖）
            for root, _dirs, files in os.walk(archive):
                for name in files:
                    path = os.path.join(root, name)
                    with open(path, "rb") as fh:
                        assert secret.encode() not in fh.read(), path
            # 运行态源文件不被就地改写（归档脱敏是原子替换）
            with open(os.path.join(case_dir, "steps.jsonl"), encoding="utf-8") as fh:
                assert secret in fh.read()
        finally:
            paths.TASKS_DIR = old_tasks
            if old_task_env is None:
                os.environ.pop(paths.ENV_WORKSPACE, None)
            else:
                os.environ[paths.ENV_WORKSPACE] = old_task_env


def test_console_reads_batch_layout_and_maps_case_tag():
    """历史报告读两级目录；case 目录名（case_01）必须按 case_tag 映射业务 case_id。"""
    import console.discovery as discovery

    old_output = discovery.OUTPUT_DIR
    with tempfile.TemporaryDirectory() as tmp:
        discovery.OUTPUT_DIR = tmp
        run_dir = os.path.join(tmp, "batch-A", "shard-01")
        case_dir = os.path.join(run_dir, "cases", "case_01")
        os.makedirs(case_dir, exist_ok=True)
        with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"batch_id": "batch-A", "run_id": "shard-01", "run_name": "shard-01",
                       "report_id": "batch-A--shard-01", "title": "酒店下单",
                       "run_status": "completed"}, fh)
        with open(os.path.join(case_dir, "steps.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"sid": "S1", "ok": 1}) + "\n")

        try:
            items = discovery.history()
            assert items and items[0]["batch_id"] == "batch-A", items
            assert items[0]["run_name"] == "shard-01", items
            assert items[0]["dir"] == os.path.join("batch-A", "shard-01"), items

            manifest = {"cases": [{"case_id": "酒店-下单", "case_name": "酒店下单"}]}
            fc = {"cases_manifest": [{"case_tag": "case_01",
                                      "case_id": "酒店-下单", "case_name": "酒店下单"}]}
            cases = discovery._cases(run_dir, manifest, fc)
            assert cases[0]["case_id"] == "酒店-下单", cases
            assert cases[0]["steps_pass"] == 1, cases
        finally:
            discovery.OUTPUT_DIR = old_output


def test_report_output_dir_reuses_only_unfinalized():
    """同 workspace 重跑 flow-init：未落盘复用空壳，已落盘必须新开 -rN（不覆盖证据）。"""
    import shared.paths as paths

    old_output, old_tasks = paths.OUTPUT_DIR, paths.TASKS_DIR
    old_task = os.environ.get(paths.ENV_WORKSPACE)
    with tempfile.TemporaryDirectory() as tmp:
        paths.OUTPUT_DIR = os.path.join(tmp, "reports")
        paths.TASKS_DIR = os.path.join(tmp, "tasks")
        os.environ[paths.ENV_WORKSPACE] = "task-x"
        try:
            first = paths.allocate_run_output_dir("batch-A", "shard-01")
            os.makedirs(paths.run_dir("shard-01"), exist_ok=True)
            paths.set_active_run("shard-01")
            with open(paths.run_file("flow-context.json", "shard-01"),
                      "w", encoding="utf-8") as fh:
                json.dump({"meta": {"batch_id": "batch-A",
                                    "batch_output_dir": first}}, fh)

            # 尚未落盘：复用同一目录（不产生空壳）
            assert paths.allocate_run_output_dir("batch-A", "shard-01") == first

            # 已落盘：重跑必须顺延，不能覆盖上一轮 report.json / run 归档
            with open(os.path.join(first, "meta.json"), "w", encoding="utf-8") as fh:
                fh.write("{}")
            second = paths.allocate_run_output_dir("batch-A", "shard-01")
            assert os.path.basename(second) == "shard-01-r2", second
            third = paths.allocate_run_output_dir("batch-A", "shard-01")
            assert os.path.basename(third) == "shard-01-r3", third
        finally:
            paths.OUTPUT_DIR, paths.TASKS_DIR = old_output, old_tasks
            if old_task is None:
                os.environ.pop(paths.ENV_WORKSPACE, None)
            else:
                os.environ[paths.ENV_WORKSPACE] = old_task


def test_redaction_covers_key_value_headers_and_binary():
    """短值走 key 形态兜住；认证头整行掩码；bool 不掩码；二进制不参与文本脱敏。"""
    from shared.output_guard import redact_obj, redact_text, redact_tree

    assert "1234" not in redact_text("pwd=1234&next=1")
    assert "abc" not in redact_text("password: abc")
    assert "eyJhbGci" not in redact_text("authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
    assert "sid-1" not in redact_text("cookie: sid=sid-1; theme=dark")
    # bool 不是凭证，不能被改成字符串 "***"（会让平台字段类型漂移）
    assert redact_obj({"is_password_reset": True}) == {"is_password_reset": True}
    assert redact_obj({"password": "abc"}) == {"password": "***"}

    with tempfile.TemporaryDirectory() as tmp:
        blob = os.path.join(tmp, "state.db")
        raw = b"\x00\x01password=SecretPass123"
        with open(blob, "wb") as fh:
            fh.write(raw)
        assert redact_tree(tmp) == []
        with open(blob, "rb") as fh:
            assert fh.read() == raw


def test_report_modules_bind_their_redactors():
    """回归：报告模块调用脱敏必须真的导入符号（漏导入会在运行期才 NameError）。"""
    import reporting.finalizer as finalizer
    import reporting.gen_report as gen_report

    for mod in (gen_report, finalizer):
        assert callable(getattr(mod, "redact_obj", None)), mod.__name__
        assert callable(getattr(mod, "secrets_from", None)), mod.__name__


def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
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
