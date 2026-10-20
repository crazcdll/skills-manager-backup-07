#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""租约存储 —— 契约 + 本地文件后端。

`LeaseStore` 是**存储后端契约**，编排层（`DeviceLeaseManager`）只依赖它，
因此"本地文件 → 平台资源池"的演进只需替换实现，编排零改动。

契约语义：
    lock()         上下文管理器，锁内串行化"读 → 决策 → 写"
    read()         读全量租约：{resource_id: lease_dict}
    write(leases)  全量写回

当前实现 `LocalFileLeaseStore`：`SKILL_DIR/.device-pool/leases.json`，
原子写（`write_json_atomic`）+ `flock` 互斥（同机多进程并发 acquire 不抢同一台）。
"""
import fcntl
import os
from contextlib import contextmanager

from shared.json_utils import read_json, write_json_atomic
from shared.paths import device_pool_leases_path, ensure_dirs


class LeaseStore:
    """租约存储后端契约。"""

    def lock(self):
        """返回上下文管理器：进入时独占、退出时释放。"""
        raise NotImplementedError

    def read(self) -> dict:
        """读全量租约（`{resource_id: lease}`），无文件时返回空 dict。"""
        raise NotImplementedError

    def write(self, leases: dict):
        """全量写回租约表（原子替换）。"""
        raise NotImplementedError


class LocalFileLeaseStore(LeaseStore):
    """本地文件后端：`.device-pool/leases.json`（原子写 + flock）。"""

    def __init__(self, path: str = None):
        # path=None → 默认路径（惰性解析，便于测试注入临时目录）
        self._path = path

    def path(self) -> str:
        return self._path or device_pool_leases_path()

    @contextmanager
    def lock(self):
        self_dir = os.path.dirname(self.path())
        os.makedirs(self_dir, exist_ok=True)
        with open(self.path() + ".lock", "w") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def read(self) -> dict:
        data = read_json(self.path(), default={}) or {}
        leases = data.get("leases")
        return leases if isinstance(leases, dict) else {}

    def write(self, leases: dict):
        ensure_dirs()
        write_json_atomic(self.path(), {"version": 1, "leases": dict(leases or {})})


def read_leases() -> dict:
    """只读全量租约（`{serial: lease}`）——供**只读消费方**（如控制台发现层）使用。

    租约文件只允许经租约层访问（禁止外部直读 `device_pool_leases_path()` 绕过 LeaseStore）。
    """
    return LocalFileLeaseStore().read()
