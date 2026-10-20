#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI 遥测 tee —— 把本次命令的 stdout/stderr 镜像到控制台服务。

**性能优先（对测试主流程零干扰）**：
  · 服务未启动 → `maybe_install_tee()` 直接返回，**零开销、不包裹任何流**；
  · 服务在线 → 原 stdout/stderr **原样透传**（AI 照旧解析 JSON），仅把文本
    非阻塞地放入内存队列；由后台守护线程批量追加到**本 workspace** 的
    `console-ingest.jsonl`（随 post-clean 回收，不进常驻 .console/）。
    **不做任何网络调用**（服务端 tail 该文件即可），也不阻塞主线程。
  · 进程退出（含短命令）→ atexit 兜底 flush，保证日志不丢。
"""
import atexit
import json
import os
import queue
import sys
import threading
import time

from shared.paths import console_ingest_path

_ENABLED = None
_INSTALLED = False
_QUEUE = queue.Queue(maxsize=4000)
_CTX = {"task": "", "run": "", "cmd": ""}
_WORKER = None


def _console_alive():
    try:
        from console.service import read_info, alive_cheap
        return alive_cheap(read_info())
    except Exception:
        return False


def enabled():
    global _ENABLED
    if _ENABLED is None:
        if os.environ.get("AI_UITEST_CONSOLE", "1") == "0":
            _ENABLED = False
        else:
            _ENABLED = _console_alive()
    return _ENABLED


def _drain():
    """后台线程：批量把队列里的行追加到本 workspace 的 ingest（append-only JSONL）。"""
    path = console_ingest_path(_CTX["task"])
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = []
    last = time.time()
    while True:
        try:
            item = _QUEUE.get(timeout=0.2)
            buf.append(item)
        except queue.Empty:
            pass
        now = time.time()
        if buf and (len(buf) >= 40 or now - last >= 0.25):
            try:
                with open(path, "a", encoding="utf-8") as f:
                    for rec in buf:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except OSError:
                pass
            buf = []
            last = now


def _ensure_worker():
    global _WORKER
    if _WORKER is None:
        _WORKER = threading.Thread(target=_drain, name="console-telemetry",
                                   daemon=True)
        _WORKER.start()


def _enqueue(stream_name, text):
    if not text:
        return
    ctx = _CTX
    for line in text.splitlines():
        if not line:
            continue
        try:
            _QUEUE.put_nowait({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "task": ctx["task"], "run": ctx["run"], "cmd": ctx["cmd"],
                "stream": stream_name, "line": line,
            })
        except queue.Full:
            return


class _Tee:
    """透明包装：先写原始流，再非阻塞入队。"""

    def __init__(self, original, stream_name):
        self._original = original
        self._stream_name = stream_name

    def write(self, text):
        try:
            n = self._original.write(text)
        except Exception:
            n = 0
        _enqueue(self._stream_name, text if isinstance(text, str) else "")
        return n

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)


def _flush_now():
    """atexit：把队列剩余行立即落盘（短命令也能保住日志）。"""
    if not _INSTALLED:
        return
    path = console_ingest_path(_CTX["task"])
    if not path:
        return
    pending = []
    while True:
        try:
            pending.append(_QUEUE.get_nowait())
        except queue.Empty:
            break
    if not pending:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            for rec in pending:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def set_context(task="", run="", cmd=""):
    _CTX["task"] = task or ""
    _CTX["run"] = run or ""
    _CTX["cmd"] = cmd or ""


def maybe_install_tee(task="", run="", cmd=""):
    """仅当「服务在线 + 处于 workspace 内」时安装 tee；否则完全不动 stdout/stderr。

    无 task（ws-init / console 等 workspace 之外的命令）→ 不装 tee：遥测必须落到
    某个 workspace，不存在「无归属」的共享遥测。
    """
    global _INSTALLED
    if _INSTALLED or not task or not enabled():
        return False
    set_context(task, run, cmd)
    _ensure_worker()
    sys.stdout = _Tee(sys.stdout, "stdout")
    sys.stderr = _Tee(sys.stderr, "stderr")
    atexit.register(_flush_now)
    _INSTALLED = True
    return True
