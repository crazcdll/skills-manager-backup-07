#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Workspace 级本地传输端口分配。

每个 workspace（Android / HarmonyOS / iOS）都在首次需要设备上下文时分配一个
**唯一本地端口**，用于隔离本机的设备传输服务。当前只有 Android ADB 适配器会
把这个端口映射到 `IMEITUAN_CLOUD_ADB_PORT`；HarmonyOS 走 `hdc`、iOS 走 WDA，
暂时不使用该端口，但保留统一的 workspace 级端口状态，后续传输层需要本地端口
时可直接复用，不需要再引入第二套分配器。

端口持久化到 `$STATE/run/tasks/<ws>/transport-port.json`，后续命令只读复用。
端口范围固定 `16000–19999`，避开本地共享 ADB 5037 与默认 cloud 15037。
"""
import fcntl
import os
import socket
import time

from shared.json_utils import read_json, write_json_atomic
from shared.paths import ENV_TRANSPORT_PORT, RUN_DIR, get_active_task, task_dir

PORT_START = 16000
PORT_END = 19999
PORT_FILE = "transport-port.json"
LOCK_FILE = "transport-ports.lock"


def _port_is_free(port: int) -> bool:
    """本机 127.0.0.1:port 是否可绑定（本地传输服务只监听回环）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _used_ports() -> set:
    """扫描所有 workspace 已登记的端口（task 目录删除后自动消失）。"""
    used = set()
    tasks_root = os.path.join(RUN_DIR, "tasks")
    if not os.path.isdir(tasks_root):
        return used
    for name in os.listdir(tasks_root):
        data = read_json(os.path.join(tasks_root, name, PORT_FILE), default={}) or {}
        try:
            port = int(data.get("port"))
        except (TypeError, ValueError):
            continue
        if PORT_START <= port <= PORT_END:
            used.add(port)
    return used


def pick_port(used: set, is_free=None) -> int:
    """从固定范围选出第一个未登记且本机可绑定的端口。"""
    check = is_free or _port_is_free
    for port in range(PORT_START, PORT_END + 1):
        if port in used:
            continue
        if check(port):
            return port
    raise RuntimeError(
        f"本地传输端口耗尽：{PORT_START}-{PORT_END} 内没有可用端口；"
        f"请清理 $STATE/run/tasks 下已结束的 workspace"
    )


def ensure_transport_port() -> int:
    """确保当前 workspace 已绑定唯一本地传输端口，并写入进程环境。

    无 workspace（ws-init / console 等）时直接返回 0；调用方无需分支。
    """
    current = os.environ.get(ENV_TRANSPORT_PORT, "").strip()
    if current:
        try:
            return int(current)
        except ValueError:
            os.environ.pop(ENV_TRANSPORT_PORT, None)

    task = get_active_task()
    if not task:
        return 0

    port_file = os.path.join(task_dir(task), PORT_FILE)
    data = read_json(port_file, default={}) or {}
    try:
        port = int(data.get("port"))
    except (TypeError, ValueError):
        port = 0
    if PORT_START <= port <= PORT_END:
        os.environ[ENV_TRANSPORT_PORT] = str(port)
        return port

    os.makedirs(RUN_DIR, exist_ok=True)
    lock_path = os.path.join(RUN_DIR, LOCK_FILE)
    with open(lock_path, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            # 双检：同一 workspace 的并发命令可能已先写入
            data = read_json(port_file, default={}) or {}
            try:
                port = int(data.get("port"))
            except (TypeError, ValueError):
                port = 0
            if not (PORT_START <= port <= PORT_END):
                port = pick_port(_used_ports())
                write_json_atomic(port_file, {
                    "port": port,
                    "workspace": task,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
            os.environ[ENV_TRANSPORT_PORT] = str(port)
            return port
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def release_transport_port(task: str = None, cleanup=None) -> None:
    """回收 workspace 的传输端口；可选执行传输层清理回调。

    必须在删除 task 目录**之前**调用（端口文件位于 task 目录内）。清理回调
    接收端口号，由具体传输层负责，例如 Android 的 `adb -P <port> kill-server`。
    """
    task = (task or get_active_task()).strip()
    if not task:
        return
    port_file = os.path.join(task_dir(task), PORT_FILE)
    data = read_json(port_file, default={}) or {}
    try:
        port = int(data.get("port"))
    except (TypeError, ValueError):
        return
    try:
        os.remove(port_file)
    except OSError:
        pass
    if cleanup:
        cleanup(port)
