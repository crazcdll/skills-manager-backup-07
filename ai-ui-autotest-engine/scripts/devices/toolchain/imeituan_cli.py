#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""imeituan CLI 设备交互层。

通过 imeituan CLI 执行设备操作，CLI 内部通过 Session 机制路由到
AdbAdapter（Android）/ XcrunAdapter（iOS）/ HdcAdapter（Harmony）。

Session 在 setup 阶段由 device register 创建并持久化到 flow-context.json，
后续所有 device shell / device input 等命令自动路由到活跃 session 对应的 Adapter。
"""
import json
import os
import re
import shutil
import subprocess
import sys

from shared.errors import DeviceError, soft_fail
from provisioning.prereq.node_env import imeituan_run


# ═══════════════════════════════════════════════════════════
# 会话绑定 —— 设备命令一律路由到「本 run 的会话」
# ═══════════════════════════════════════════════════════════
# imeituan CLI 的「活跃 session」是 ~/.imeituan 下的全局单例：并发 run 时
# 谁后注册谁抢走它，前者的设备命令会被静默路由到别人的设备。因此引擎不再依赖
# 全局活跃会话，而是把「本 run 的 session_id」显式注入每个子进程（IMEITUAN_SESSION），
# 达成 run 级隔离（session_id 持久化于 flow-context.json meta.session_id）。
SESSION_ENV = "IMEITUAN_SESSION"

# ═══════════════════════════════════════════════════════════
# 错误分类 —— 「确定性错误不重试」的唯一事实来源
# ═══════════════════════════════════════════════════════════
# 会话层的错误分两类：
#   · 确定性（deterministic）：同一磁盘状态下重试必然复现，只能通过隔离/修环境解决。
#     典型是 legacy 会话缺少 ADB Server 身份（CLI 会 retain-session，越重试越卡）。
#   · 瞬态（transient）：网络/云 Server 排队/设备刚启动，退避后重试有意义。
# 由 CLI 输出（error.message / stderr）解析错误码；解析不出按瞬态处理（保守）。
# 设备复用阻塞：同一台 sandbox 的上一个 session/ADB 操作尚未退出。
# 重试同一台无意义，正确处理是「隔离该设备 + 换一台」，不能判成 case 失败。
DEVICE_REUSE_ERRORS = (
    "SESSION_CLEANUP_PENDING",
    "SESSION_RESOURCES_ACTIVE",
    "SESSION_CLOSING",
)

# Cloud ADB Server 协调台账错误：这是 Android ADB 传输的全局台账状态，不是单台
# 设备问题。命中时 repair 该端口的调度台账并退避重试，禁止通过换 sandbox 解决。
ADB_COORDINATION_ERRORS = (
    "ADB_SERVER_COORDINATION_QUARANTINED",
    "ADB_SERVER_COORDINATION_UNAVAILABLE",
    "ADB_SERVER_COORDINATION_CORRUPT",
)

_DETERMINISTIC_ERRORS = (
    "ADB_SERVER_LEGACY_IDENTITY_UNKNOWN",
    "ADB_RUNTIME_MIGRATION_REQUIRED",
    "ADB_PORT_OWNERSHIP_CONFLICT",
    "ADB_SDK_UPGRADE_REQUIRED",
    "ADB_SERVER_PROFILE_UNSUPPORTED",
    "SESSION_CLEANUP_PENDING",
    "SESSION_RESOURCES_ACTIVE",
    "SESSION_CLOSING",
)
_TRANSIENT_ERRORS = (
    "ADB_SHARED_SERVER_UNRESPONSIVE",
    "ADB_QUEUE_TIMEOUT",
    "ADB_SERVER_RECOVERY_FAILED",
    "SESSION_TIMEOUT",
    "TIMEOUT",
)
# 设备侧连接失败：多数是实例刚创建/端口未就绪，可退避重试一次。
_DEVICE_UNREACHABLE_MARKERS = ("transport-disconnect", "ECONNREFUSED", "connection refused",
                               "device offline", "cannot connect")


def classify_error(text: str) -> dict:
    """从 CLI 输出中提取错误码与可重试性，返回 `{code, retryable}`。

    只做**字符串分类**，不改变调用结果；供注册重试与收尾逻辑分支使用。
    """
    raw = str(text or "")
    upper = raw.upper()
    # 会话已经不存在：断开操作应视为“已收尾”（幂等）；注册侧由 reestablisher 处理。
    if "NOT_FOUND" in upper or ("SESSION" in upper and "DOES NOT EXIST" in upper):
        return {"code": "SESSION_NOT_FOUND", "retryable": False}
    # Cloud ADB 协调台账：交给 imeituan_run 的 repair + 退避，不能换 sandbox。
    for code in ADB_COORDINATION_ERRORS:
        if code in upper:
            return {"code": code, "retryable": False, "coordination": True}
    # 设备复用阻塞优先分类：这些错误重试同一台设备必然复现，但可以换设备恢复。
    for code in DEVICE_REUSE_ERRORS:
        if code in upper:
            return {"code": code, "retryable": False, "device_reuse": True}
    for code in _DETERMINISTIC_ERRORS:
        if code in upper:
            return {"code": code, "retryable": False}
    # 有些 AppMock/设备命令只透出中文文案，不带 errorCode；同样按协调台账处理。
    if "旧设备操作尚未安全退出" in raw:
        return {"code": "ADB_SERVER_COORDINATION_QUARANTINED",
                "retryable": False, "coordination": True}
    if "设备连接状态无法读取" in raw or "ADB 调度记录损坏" in raw:
        return {"code": "ADB_SERVER_COORDINATION_CORRUPT",
                "retryable": False, "coordination": True}
    for code in _TRANSIENT_ERRORS:
        if code in upper:
            return {"code": code, "retryable": True}
    if any(marker.lower() in raw.lower() for marker in _DEVICE_UNREACHABLE_MARKERS):
        return {"code": "DEVICE_UNREACHABLE", "retryable": True}
    return {"code": "SESSION_REGISTER_FAILED", "retryable": True}


def is_deterministic(text: str) -> bool:
    return not classify_error(text)["retryable"]


def _error_fields(payload) -> dict:
    """从 CLI JSON envelope 提取 `{code, detail}`（解析不出时回退空值）。"""
    if not isinstance(payload, dict):
        return {"code": "", "detail": ""}
    err = payload.get("error") or {}
    if isinstance(err, dict):
        return {"code": str(err.get("code") or ""),
                "detail": str(err.get("message") or "")}
    return {"code": "", "detail": str(err)}

# 不需会话的命令前缀（注册/连接/销毁会话本身、工具链环境、纯本地子命令）。
_SESSION_FREE_PREFIXES = (
    ("device", "register"), ("device", "connect"), ("device", "disconnect"),
    ("device", "environment"),
    ("session",), ("contract",), ("plugin",), ("help",), ("bridge",),
)
# 需要设备会话的命令前缀（会真实路由到某台设备）。
_DEVICE_SCOPED_PREFIXES = (
    ("device",), ("control",), ("inject",), ("observe",),
)


def bind_session(session_id: str) -> str:
    """把本进程的设备命令绑定到指定 imeituan session（返回生效的 session_id）。"""
    sid = str(session_id or "").strip()
    if sid:
        os.environ[SESSION_ENV] = sid
    return sid


def unbind_session() -> None:
    """清除本进程的会话绑定。"""
    os.environ.pop(SESSION_ENV, None)


def current_session():
    """读取本进程当前绑定的 session_id（未绑定返回 None）。"""
    return os.environ.get(SESSION_ENV) or None


def needs_session(args) -> bool:
    """该命令是否必须绑定设备会话（未绑定则应显式失败而非静默路由）。"""
    tokens = tuple(str(a) for a in args)
    for pref in _SESSION_FREE_PREFIXES:
        if tokens[:len(pref)] == pref:
            return False
    return tokens[:1] in _DEVICE_SCOPED_PREFIXES


# ═══════════════════════════════════════════════════════════
# 会话自愈 —— 会话是进程外的跨命令资源，长流程中途可能失效
# ═══════════════════════════════════════════════════════════
# imeituan 的 session 由 CLI 进程之外的服务持有，会在 device setup / 登录等长流程中途
# 被回收（实测 `session <sid> does not exist`，随后 force-stop/launch/inspect-tree 全挂）。
# 重建会话需要 serial/platform/device_type/remote 等设备信息，只有注册入口
# （`devices/toolchain/session.py::imeituan_register`）掌握，故以**回调注入**：本层不反向
# import session.py（否则 session → imeituan_cli → session 成环）。
_SESSION_REESTABLISHER = None
_SESSION_MISSING_RE = re.compile(r"session\s+\S+\s+does not exist", re.IGNORECASE)


def set_session_reestablisher(fn) -> None:
    """注册「会话失效时重建会话」的回调（由 session.py::imeituan_register 注入）。"""
    global _SESSION_REESTABLISHER
    _SESSION_REESTABLISHER = fn


def _is_session_missing(r) -> bool:
    """命令是否因「会话不存在」失败（imeituan 在 error.message / stderr 给出）。"""
    text = f"{getattr(r, 'stdout', '') or ''}\n{getattr(r, 'stderr', '') or ''}"
    if _SESSION_MISSING_RE.search(text):
        return True
    low = text.lower()
    return "session" in low and "does not exist" in low


def _run(args, timeout=30, _allow_reestablish=True):
    """执行 imeituan CLI 命令，返回原始 CompletedProcess。

    会话绑定：若本进程已绑定 session，则注入 IMEITUAN_SESSION，使命令路由到
    本 run 的设备；若命令需要会话却未绑定，直接抛 DeviceError（避免静默落到
    并发 run 的设备上），把「串台」从静默错误变成显式失败。

    会话自愈：已绑定会话但命令反馈「会话不存在」时，透明重建一次并重试
    （仅重试一次，避免不可恢复错误下无限循环）。
    """
    args = [str(a) for a in args]
    sid = current_session()
    if sid is None and needs_session(args):
        raise DeviceError(
            f"设备命令未绑定会话: imeituan {' '.join(args[:3])} ...\n"
            "  请先完成 device setup；或在 workspace 内执行（自动从 "
            "flow-context.json meta.session_id 绑定本 run 的会话）"
        )
    env_extra = {SESSION_ENV: sid} if sid else None
    try:
        r = imeituan_run(args, capture=True, timeout=timeout, env_extra=env_extra)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args=args, returncode=1, stdout="",
            stderr=f"TIMEOUT after {e.timeout}s")

    if (_allow_reestablish and sid and _SESSION_REESTABLISHER
            and _is_session_missing(r)):
        sys.stderr.write("[session] 检测到会话失效，正在重建会话并重试...\n")
        sys.stderr.flush()
        try:
            if _SESSION_REESTABLISHER():
                return _run(args, timeout=timeout, _allow_reestablish=False)
        except Exception as e:  # noqa: BLE001 —— 重建失败则按原错误返回
            soft_fail("infra", "SESSION_REESTABLISH_FAILED", e)
    return r


def _parse_json(r):
    """解析 CLI 输出的 JSON，返回 payload 或 None。"""
    raw = (r.stdout or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _unwrap(r):
    """解析 JSON envelope，提取 stdout/stderr/returncode。

    成功时 data 中的 stdout/stderr/exitCode 覆盖原始值；
    失败时 returncode=1、stderr=error.message；
    非 envelope 格式原样返回。
    """
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return r
    if payload.get("code") == 0:
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return r
        return subprocess.CompletedProcess(
            args=r.args,
            returncode=data.get("exitCode", 0),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
        )
    return subprocess.CompletedProcess(
        args=r.args,
        returncode=1,
        stdout="",
        stderr=payload.get("error", {}).get("message", ""),
    )


def _success(r):
    """判断 CLI 命令是否成功（envelope code == 0 或非 JSON 时 subprocess returncode == 0）。"""
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        return r.returncode == 0
    return payload.get("code") == 0


# ═══════════════════════════════════════════════════════════
# 设备操作（依赖活跃 session）
# ═══════════════════════════════════════════════════════════

def imeituan_shell(*shell_args, timeout=30):
    """在设备上执行 shell 命令，返回 CompletedProcess。"""
    args = ["device", "shell", "--", *shell_args]
    return _unwrap(_run(args, timeout=timeout))


def imeituan_input(action, timeout=30, **kwargs):
    """设备输入操作（tap/swipe/text）。"""
    cmd = ["device", "input", action]
    for k, v in kwargs.items():
        cmd += ["--" + k.replace("_", "-"), str(v)]
    return _unwrap(_run(cmd, timeout=timeout))


def imeituan_set_package(package, timeout=15):
    """把目标 App 包写入当前 session（imeituan 的 App 层命令按它路由）。

    “session = 设备 + 目标包”是 imeituan CLI 的固有模型：未选中包时，所有 App 层
    命令（`control auth status`、`device open-url` …）都会报“尚未选择 package-id”。
    会话创建入口（devices/toolchain/session.py::imeituan_register）在用完本函数完成绑定。
    """
    return _unwrap(_run(["device", "set-package", package], timeout=timeout))


def imeituan_open_url(url, timeout=15):
    """在设备上打开 URL/scheme。

    目标包已由 session 创建入口（imeituan_register）绑定，open-url 不需 --package-id。
    """
    return _unwrap(_run(["device", "open-url", url], timeout=timeout))


def imeituan_install(apk_path, timeout=300):
    """向设备安装 APK。"""
    return _unwrap(_run(["device", "install", apk_path, "--timeout", str(timeout)],
                        timeout=timeout + 30))


def imeituan_screenshot(output_path, timeout=30):
    """截图保存到指定路径，返回是否成功。"""
    r = _run(["device", "screenshot", "-o", output_path], timeout=timeout)
    return _success(r) and os.path.isfile(output_path)


def imeituan_screen_size(default=(1080, 2340), timeout=10):
    """获取设备屏幕分辨率 (width, height)。"""
    try:
        r = imeituan_shell("wm", "size", timeout=timeout)
        m = re.search(r'(\d+)x(\d+)', r.stdout or "")
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception as e:
        soft_fail("device", "SCREEN_SIZE_PROBE_FAILED", e)
    return default


def imeituan_alive(timeout=10):
    """轻量级设备连通性检查。"""
    try:
        r = imeituan_shell("echo", "alive", timeout=timeout)
        return r.returncode == 0 and "alive" in ((r.stdout or "") + (r.stderr or ""))
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# Control 命令（感知 & 定位）
# ═══════════════════════════════════════════════════════════

def imeituan_inspect_tree(output_path, cli_timeout=30, subprocess_timeout=None):
    """获取设备视图树 JSON，输出到指定文件路径。"""
    timeout = subprocess_timeout or (cli_timeout + 15)
    r = _run(["control", "inspect-tree", "--timeout", str(cli_timeout),
              "-o", output_path], timeout=timeout)
    ok = _success(r)
    return subprocess.CompletedProcess(args=r.args, returncode=0 if ok else 1,
                                       stdout=r.stdout, stderr=r.stderr)


# 说明：官方 `imeituan control location`（Pillow-H5 通道）的封装已移除 ——
# 定位统一改经**通用可测性 scheme**（`provisioning/setup/location.build_location_action` /
# `build_location_clear_action`，承载页为 MRN、内容进原生视图树），
# 引擎内已无 H5 定位通道的调用方。


# ═══════════════════════════════════════════════════════════
# 通用 CLI 执行（供 appmock 等模块使用）
# ═══════════════════════════════════════════════════════════

def imeituan_exec(args, timeout=30):
    """执行 imeituan CLI 命令，返回原始 CompletedProcess。"""
    return _run(args, timeout=timeout)


def stop_adb_server(port: int) -> None:
    """停止指定端口的 ADB Server；供 Android workspace 端口收尾使用。"""
    adb = shutil.which("adb")
    if not adb:
        return
    try:
        subprocess.run(
            [adb, "-P", str(port), "kill-server"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return


# ═══════════════════════════════════════════════════════════
# Session 管理命令
# ═══════════════════════════════════════════════════════════

def _session_result(r, missing_sid_detail: str) -> dict:
    """把「创建会话」类命令的返回统一成结构化结果。

    返回字段固定为 `{ok, code, retryable, session_id, detail}`：
      · code/retryable 由 `classify_error` 解析 CLI 输出得到，调用方据此决定是否重试；
      · 不再只返回一句字符串 detail —— 重试策略需要机器可判定的身份。
    """
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        detail = (r.stderr or "未知错误")[:300]
        cls = classify_error(detail)
        return {"ok": False, "code": cls["code"], "retryable": cls["retryable"],
                "device_reuse": bool(cls.get("device_reuse")),
                "coordination": bool(cls.get("coordination")),
                "session_id": "", "detail": detail}

    if payload.get("code") != 0:
        fields = _error_fields(payload)
        text = (fields["detail"] or r.stderr or fields["code"] or "未知错误").strip()
        cls = classify_error(text or fields["code"])
        return {"ok": False, "code": cls["code"], "retryable": cls["retryable"],
                "device_reuse": bool(cls.get("device_reuse")),
                "coordination": bool(cls.get("coordination")),
                "session_id": "", "detail": text[:300]}

    sid = (payload.get("data") or {}).get("sessionId", "")
    if sid:
        return {"ok": True, "code": "", "retryable": False,
                "session_id": sid, "detail": ""}
    return {"ok": False, "code": "SESSION_ID_MISSING", "retryable": True,
            "session_id": "", "detail": missing_sid_detail}


def imeituan_register_device(serial, platform, remote_address=None):
    """注册外部设备到 CLI session，返回结构化结果。

    适用于"设备在远程 server 上"的场景（云真机 / 云模拟器 / Android sandbox）：
    `device register --remote-address <RA>`，RA 缺省回退为 serial（Android sandbox
    的 serial 本身即 ip:port 网络地址）。本地 USB 直连设备请改用
    imeituan_connect_local_device()。
    """
    r = _run(["device", "register", "-p", platform,
              "--serial", serial, "--remote-address", remote_address or serial,
              "--force"], timeout=30)
    return _session_result(r, "register 成功但未返回 session_id")


def imeituan_connect_local_emulator(serial, platform):
    """连接本地模拟器并创建 CLI session，返回结构化结果。

    对应 `imeituan device connect --target local-emulator`，适用于本地启动的 iOS / Android 模拟器。
    """
    r = _run(["device", "connect", "--target", "local-emulator", "-p", platform,
              "--serial", serial, "--force"], timeout=30)
    return _session_result(r, "connect 成功但未返回 session_id")


def imeituan_connect_local_device(serial, platform):
    """连接本地已物理连接的真机并创建 CLI session，返回结构化结果。

    对应 `imeituan device connect --target local-device`，会跳过网络连接
    探测，是本地 USB/HDC 直连设备的正确入口（区别于面向云真机的 device register）。
    """
    r = _run(["device", "connect", "--target", "local-device", "-p", platform,
              "--serial", serial, "--force"], timeout=30)
    return _session_result(r, "connect 成功但未返回 session_id")




def imeituan_disconnect_device(session_id=None) -> dict:
    """断开会话，返回结构化结果 `{ok, code, retryable, detail}`。

    只断开**指定或当前绑定**的会话，**绝不做全量断开**——`disconnect --all`
    会把并发 run 的会话一并踢掉，是并发串台的根源之一。

    注意：legacy 会话的断开本身就会抛 `ADB_SERVER_LEGACY_IDENTITY_UNKNOWN`
    （CLI 拒绝执行无身份的 adb 清理）。调用方（session.py）应把这类确定性错误
    当作"会话已不可用"，走隔离而不是重试。
    """
    target = str(session_id or "").strip() or current_session()
    args = ["device", "disconnect"]
    if target:
        args += ["--session", target]

    r = _run(args, timeout=15)
    payload = _parse_json(r)
    if not isinstance(payload, dict):
        text = (r.stderr or "")[:300]
        cls = classify_error(text)
        return {"ok": r.returncode == 0, "code": cls["code"],
                "retryable": cls["retryable"],
                "device_reuse": bool(cls.get("device_reuse")),
                "coordination": bool(cls.get("coordination")), "detail": text}

    if payload.get("code") == 0:
        return {"ok": True, "code": "", "retryable": False, "detail": ""}
    fields = _error_fields(payload)
    text = (fields["detail"] or fields["code"] or "未知错误").strip()
    cls = classify_error(text)
    return {"ok": False, "code": cls["code"], "retryable": cls["retryable"],
            "device_reuse": bool(cls.get("device_reuse")),
            "coordination": bool(cls.get("coordination")), "detail": text[:300]}
