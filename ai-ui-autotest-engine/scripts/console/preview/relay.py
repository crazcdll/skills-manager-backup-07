#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relay 预览：调用 imeituan 的投屏中继（serve 模式），把帧中继为 MJPEG。

默认**不启用**（截图轮询已满足鸿蒙模拟器；relay 依赖 imeituan 版本/会话，属增强项）。
通过环境变量 `AI_UITEST_CONSOLE_PREVIEW=relay` 打开；启动失败时由 manager 回退截图。
"""
import base64
import json
import re
import subprocess
import threading
import time

from console.preview.base import PreviewAdapter

_READY_RE = re.compile(r"MIRROR_SERVER_READY\s+(\S+)")
_FRAME_HEADER = 13   # 1B type + 4B seq + 8B timestamp


def _resolve_imeituan():
    """投屏中继与设备命令使用**同一份**受管安装（并已确保最新）。"""
    from shared.imeituan import ensure_bin
    return ensure_bin()


class RelayPreview(PreviewAdapter):
    kind = "relay"

    def __init__(self, device):
        super().__init__(device)
        self._proc = None
        self._ws = None
        self._media = {}
        self._lock = threading.Lock()

    # ── 内部：启动中继进程 ────────────────────────────────
    def _start_relay(self, timeout=15):
        imeituan = _resolve_imeituan()
        if not imeituan:
            raise RuntimeError("imeituan not found")
        platform = self.device.get("platform") or "harmony"
        args = [imeituan, "device", "remote-desktop", "--mode", "serve",
                "--protocol", "cast-stream-v2", "-p", platform,
                "--device-id", self.serial]
        session = self.device.get("session_id")
        if session:
            extra = {"IMEITUAN_SESSION": session}
        else:
            extra = None
        # 与命令行使用方一致：无论当前 shell 的 Node 是哪个版本，都在 Node>=18 下运行
        from provisioning.prereq.node_env import node_process_env
        env = node_process_env(extra)
        if env is None:
            raise RuntimeError("Node>=18 不可用，relay 无法启动")
        self._proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, bufsize=1,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError("relay exited early")
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            m = _READY_RE.search(line)
            if m:
                info = json.loads(base64.urlsafe_b64decode(m.group(1) + "=="))
                return info
        raise RuntimeError("relay not ready in time")

    def _connect(self, endpoint):
        import websocket  # websocket-client（已是硬依赖）
        return websocket.create_connection(endpoint, timeout=8,
                                           subprotocols=["cast-stream-v2"])

    # ── 帧流 ─────────────────────────────────────────────
    def frames(self):
        try:
            info = self._start_relay()
        except Exception:
            return
        endpoint = info.get("endpoint")
        self._media = info.get("media") or {}
        if not endpoint:
            self.stop()
            return
        try:
            self._ws = self._connect(endpoint)
        except Exception:
            self.stop()
            return
        try:
            while not self._stopped:
                try:
                    msg = self._ws.recv()
                except Exception:
                    break
                if not msg:
                    break
                if isinstance(msg, str):
                    continue  # hello / metrics 等 JSON 文本
                payload = msg[_FRAME_HEADER:]
                if not payload:
                    continue
                mime = self._media.get("mime") or "image/jpeg"
                if self._media.get("codec") not in (None, "jpeg"):
                    # H.264 无法直接转 MJPEG（真机场景）；本迭代不处理
                    continue
                yield (mime if mime.startswith("image/") else "image/jpeg"), payload
        finally:
            self.stop()

    def stop(self):
        self._stopped = True
        with self._lock:
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            if self._proc is not None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None
