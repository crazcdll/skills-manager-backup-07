#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务生命周期：单例锁 + 端口探测 + 后台启动 + 健康探测。

`ensure()` 是唯一入口，幂等：
  · 服务已存活 → 直接返回其地址（★ 其他会话在此跳过，绝不重启）；
  · 未存活 → flock 串行化，启动一个脱离父会话的常驻服务进程。
"""
import errno
import json
import os
import secrets
import socket
import subprocess
import sys
import time

from console import config
from shared.json_utils import read_json, write_json_atomic
from shared.paths import (
    SKILL_DIR,
    console_dir,
    console_lock_path,
    console_server_json,
    console_server_log,
    console_token_path,
    ensure_dirs,
)


def _server_entry() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


def read_info():
    try:
        info = read_json(console_server_json(), None)
        return info if isinstance(info, dict) else None
    except Exception:
        return None


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM
    return True


def is_alive(info) -> bool:
    if not info or not _pid_alive(info.get("pid")):
        return False
    return _healthz(info.get("port"), info.get("token"))


def alive_cheap(info=None) -> bool:
    """轻量存活判断（仅 pid，不做网络探测）——供 CLI 遥测热路径使用，微秒级开销。"""
    info = info if info is not None else read_info()
    return bool(info and _pid_alive(info.get("pid")))


def _healthz(port, token, timeout=config.HEALTH_TIMEOUT) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout) as s:
            req = (f"GET /healthz HTTP/1.0\r\nHost: 127.0.0.1\r\n"
                   f"X-Console-Token: {token or ''}\r\n\r\n").encode()
            s.sendall(req)
            s.settimeout(timeout)
            data = s.recv(256)
            return b"200" in data.split(b"\r\n", 1)[0]
    except OSError:
        return False


def _probe_port(port, timeout=config.HEALTH_TIMEOUT):
    """探测某端口是否是在跑的 catpaw-console（token-free `/healthz`）。

    返回 `{"pid": int, "port": int}` 或 None。**这是单例判据的“现实来源”**——
    不依赖 `server.json`，因此名片缺失/陈旧也不会误判。
    """
    if not port:
        return None
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout) as s:
            s.sendall(b"GET /healthz HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            s.settimeout(timeout)
            data = s.recv(512)
    except OSError:
        return None
    head, _, body = data.partition(b"\r\n\r\n")
    if b"200" not in head.split(b"\r\n", 1)[0]:
        return None
    try:
        obj = json.loads(body.decode("utf-8", "replace") or "{}")
    except ValueError:
        return None
    if not isinstance(obj, dict) or obj.get("service") != "catpaw-console":
        return None
    return {"pid": int(obj.get("pid") or 0), "port": int(port)}


def _candidate_ports():
    """候选端口：名片已知端口优先，其后是配置的扫描范围。"""
    ports = list(range(config.DEFAULT_PORT, config.DEFAULT_PORT + config.PORT_SCAN_RANGE))
    known = (read_info() or {}).get("port")
    try:
        kp = int(known)
    except (TypeError, ValueError):
        return ports
    return [kp] + [p for p in ports if p != kp]


def discover_running():
    """探测**现实**中正在运行的控制台实例；返回其 info 或 None。

    判据：端口范围内有 `catpaw-console` 在响应 `/healthz`。命中即用探测结果
    **刷新名片**（server.json 退化为缓存/展示），保证名片始终指向真实实例。
    """
    for p in _candidate_ports():
        hit = _probe_port(p)
        if not hit:
            continue
        info = {
            "version": config.CONSOLE_VERSION,
            "pid": hit["pid"], "host": config.BIND_HOST, "port": hit["port"],
            "url": f"http://127.0.0.1:{hit['port']}",
            "token": _load_or_create_token(),
        }
        try:
            write_json_atomic(console_server_json(), info)
        except Exception:
            pass
        return info
    return None


class _FileLock:
    """flock 单例锁（跟 lease_store 同款用法）。"""

    def __init__(self, path):
        self._path = path
        self._fh = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        import fcntl
        self._fh = open(self._path, "w")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        try:
            import fcntl
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            if self._fh:
                self._fh.close()
        return False


def _spawn(token):
    """后台启动服务进程（脱离父会话，输出落 server.log）。"""
    log = open(console_server_log(), "a", encoding="utf-8")
    env = dict(os.environ)
    env.pop("AI_UITEST_TASK", None)      # 服务与任何 workspace 无关
    proc = subprocess.Popen(
        [sys.executable, _server_entry(), "--token", token,
         "--port", str(config.DEFAULT_PORT),
         "--port-range", str(config.PORT_SCAN_RANGE),
         "--host", config.BIND_HOST],
        cwd=SKILL_DIR, stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True, env=env,
    )
    return proc


def _wait_ready(old_pid, timeout=config.STARTUP_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = read_info()
        if info and info.get("pid") != old_pid and is_alive(info):
            return info
        time.sleep(0.2)
    return read_info() if is_alive(read_info()) else None


_TOKEN_FILE_MIN_LEN = 22


def _persist_token(tok) -> None:
    """把 token 落盘（幂等）；空 / 过短则忽略。"""
    tok = str(tok or "").strip()
    if len(tok) < _TOKEN_FILE_MIN_LEN:
        return
    try:
        ensure_dirs()
        path = console_token_path()
        try:
            with open(path, encoding="utf-8") as f:
                if (f.read() or "").strip() == tok:
                    return
        except OSError:
            pass
        with open(path, "w", encoding="utf-8") as f:
            f.write(tok)
    except OSError:
        pass


def _load_or_create_token(existing_token="") -> str:
    """取得**稳定**的访问令牌（保证控制台链接长期不变）。

    优先级：`.console/token`（持久化文件） → 调用方传入的现有 token → 新生成；
    无论哪条来源都回写 `.console/token`，使后续任何重启都复用同一 token。
    """
    ensure_dirs()
    tok = ""
    try:
        with open(console_token_path(), encoding="utf-8") as f:
            tok = (f.read() or "").strip()
    except OSError:
        tok = ""
    if len(tok) < _TOKEN_FILE_MIN_LEN:
        candidate = str(existing_token or "").strip()
        tok = candidate if len(candidate) >= _TOKEN_FILE_MIN_LEN else secrets.token_urlsafe(config.TOKEN_BYTES)
    _persist_token(tok)
    return tok


def ensure():
    """幂等启动并返回 {ok, started, url, port, token, pid}。

    存活判据 = **探测现实**（端口范围内是否有 catpaw-console 在响应），而非
    `server.json`——名片缺失/陈旧也不会拉起第二个实例；`server.json` 只是缓存。
    """
    ensure_dirs()
    found = discover_running()
    if found:
        return {"ok": True, "started": False, **found}
    with _FileLock(console_lock_path()):
        found = discover_running()
        if found:
            return {"ok": True, "started": False, **found}
        existing = read_info() or {}
        old_pid = existing.get("pid")
        token = _load_or_create_token(existing.get("token"))
        _spawn(token)
        info = _wait_ready(old_pid)
        if not info:
            return {"ok": False, "error": "服务启动超时，请查看 .console/server.log"}
        return {"ok": True, "started": True, **info}


def stop():
    """停止**所有**运行中的控制台实例（按探测现实，不依赖名片）。"""
    info = read_info() or {}
    _persist_token(info.get("token"))      # 停止也保住 token，重启后链接不变
    killed = []
    for p in _candidate_ports():
        hit = _probe_port(p)
        if hit and _pid_alive(hit["pid"]) and hit["pid"] not in killed:
            killed.append(hit["pid"])
    if _pid_alive(info.get("pid")) and info.get("pid") not in killed:   # 兜底：名片里的 pid
        killed.append(info.get("pid"))
    for pid in killed:
        try:
            os.kill(int(pid), 15)
        except OSError:
            pass
    for _ in range(20):
        if not any(_pid_alive(x) for x in killed):
            break
        time.sleep(0.1)
    try:
        os.remove(console_server_json())
    except OSError:
        pass
    return {"ok": True, "stopped": bool(killed), "pids": killed}


def status():
    """报告**真实**运行实例（探测现实）；无实例时退回名片展示。"""
    found = discover_running()
    if found:
        return {"ok": True, "running": True, **found}
    return {"ok": True, "running": False, **(read_info() or {})}
