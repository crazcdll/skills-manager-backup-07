#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""控制台共享状态：事件环形缓冲 + 订阅者 fanout + 运行/设备快照。

服务进程内单例（HUB）；后台线程（discovery/tailer）向它 publish / set_*，
HTTP 层（/api、/events、/device/*）从它读取。线程安全。

统一「设备归属」模型：
    每条 UI 事件尽量带 device（serial）。结构化事件（stage/step/audit）在写入端
    即带上；CLI 遥测（raw）只带 task，需经 `device_of_session()` 按会话反查补齐。
"""
import queue
import threading
import time
from collections import deque

from console import config


class Hub:
    """线程安全的事件总线与状态快照。"""

    def __init__(self, maxlen=config.EVENT_RING_MAX):
        self._lock = threading.Lock()
        self._events = deque(maxlen=maxlen)
        self._subs = set()
        self._seq = 0
        self.started_at = time.time()
        self.runs = []                 # list[dict]
        self.devices = []              # list[dict]
        self.sessions = []             # list[dict]（session = workspace/task）
        self._session_device = {}      # task -> serial
        self.stats = {"events": 0}

    # ── 事件 ──────────────────────────────────────────────
    def publish(self, event: dict) -> dict:
        event = dict(event)
        with self._lock:
            self._seq += 1
            event["_seq"] = self._seq
            self._events.append(event)
            self.stats["events"] += 1
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
        return event

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=4000)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def snapshot(self, since: int = 0, limit: int = 1000) -> list:
        with self._lock:
            items = [e for e in self._events if e.get("_seq", 0) > since]
        return items[-limit:]

    def latest_seq(self) -> int:
        with self._lock:
            return self._seq

    # ── 状态快照 ──────────────────────────────────────────
    def set_snapshot(self, runs: list, devices: list, sessions: list) -> None:
        """原子更新 run / device / session 快照与「会话(task)→设备」索引。"""
        index = {}
        for s in sessions:                      # 会话自带 device_serial（可早于设备租约存在）
            if s.get("task"):
                index[s["task"]] = s.get("device_serial", "")
        for d in devices:                       # 设备租约为准（覆盖会话里的 serial）
            if d.get("task"):
                index[d["task"]] = d.get("serial", "")
        with self._lock:
            self.runs = list(runs)
            self.devices = list(devices)
            self.sessions = list(sessions)
            self._session_device = index

    def get_runs(self) -> list:
        with self._lock:
            return list(self.runs)

    def get_devices(self) -> list:
        with self._lock:
            return list(self.devices)

    def get_sessions(self) -> list:
        with self._lock:
            return list(self.sessions)

    def device_of_session(self, task: str) -> str:
        """会话(task) → 设备 serial；统一设备归属（设备租约键 sandboxId）。"""
        with self._lock:
            return self._session_device.get(task or "", "")


HUB = Hub()
