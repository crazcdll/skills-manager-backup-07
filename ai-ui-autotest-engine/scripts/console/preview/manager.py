#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预览管理器：按设备选择/缓存预览策略，向 HTTP 层提供 (mime, bytes) 帧流。

选择规则：
  · Android sandbox 且有 scrcpyUrl → scrcpy（前端 iframe，服务端零成本）
  · 其他（含鸿蒙云模拟器）→ 截图轮询 MJPEG（默认）
  · 设 AI_UITEST_CONSOLE_PREVIEW=relay → 鸿蒙走 imeituan relay（失败自动回退截图）
"""
import base64
import json
import os
import socket
import ssl
import threading
import time
import urllib.parse

from console.preview.screenshot import ScreenshotPreview
from console.preview.relay import RelayPreview


class PreviewManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}   # serial -> {"key":..., "adapter": PreviewAdapter}

    @staticmethod
    def _key(device):
        return (device.get("serial"), device.get("session_id"),
                device.get("platform"), device.get("preview_kind"))

    def _build(self, device):
        # 服务端帧流（MJPEG 端点）统一走截图；scrcpy 画面由前端 iframe 经本服务**反代**内嵌
        # （反代只透传 body、剥掉上游 CSP，所以能嵌）。设 relay 时鸿蒙走 imeituan relay。
        if os.environ.get("AI_UITEST_CONSOLE_PREVIEW", "").lower() == "relay" \
                and device.get("session_id"):
            return RelayPreview(device)
        return ScreenshotPreview(device)

    def get(self, device):
        serial = device.get("serial", "")
        key = self._key(device)
        with self._lock:
            entry = self._cache.get(serial)
            if entry and entry["key"] == key:
                return entry["adapter"]
            if entry:
                try:
                    entry["adapter"].stop()
                except Exception:
                    pass
            adapter = self._build(device)
            self._cache[serial] = {"key": key, "adapter": adapter}
            return adapter

    def stream(self, device):
        """返回 (mime, bytes) 生成器；无 session（拿不到截图）时不建流。"""
        if not device.get("session_id"):
            return None
        return self.get(device).frames()

    def stop_all(self):
        with self._lock:
            for entry in self._cache.values():
                try:
                    entry["adapter"].stop()
                except Exception:
                    pass
            self._cache.clear()


_UDID_TTL = 90.0
_udid_cache = {}          # scrcpy_url -> (ts, udid)
_udid_lock = threading.Lock()


def _ws_text_once(url, timeout=3.0):
    """极简 WebSocket 客户端：握手后读第一帧文本（仅用于查设备列表，零第三方依赖）。"""
    u = urllib.parse.urlparse(url)
    secure = u.scheme == "wss"
    host, port = u.hostname or "", u.port or (443 if secure else 80)
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        if secure:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                      f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return ""
            buf += chunk
        head, _, data = buf.partition(b"\r\n\r\n")
        if b" 101" not in head.split(b"\r\n", 1)[0]:
            return ""
        while len(data) < 2:
            data += sock.recv(4096)
        length, idx = data[1] & 0x7F, 2
        if length == 126:
            while len(data) < 4:
                data += sock.recv(4096)
            length, idx = int.from_bytes(data[2:4], "big"), 4
        elif length == 127:
            while len(data) < 10:
                data += sock.recv(4096)
            length, idx = int.from_bytes(data[2:10], "big"), 10
        while len(data) < idx + length:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data[idx:idx + length].decode("utf-8", "replace")
    finally:
        try:
            sock.close()
        except OSError:
            pass


def resolve_udid(scrcpy_url, fallback="", ttl=_UDID_TTL):
    """scrcpy 服务认可的设备 udid（TTL 缓存）。

    传错 udid 时 scrcpy 会在 WS 建立后立刻关流（`Failed to start service`）→ 黑屏；
    这里查 `goog-device-list` 取 state=device 的真实序列号，查不到则回退 fallback。
    """
    if not scrcpy_url:
        return fallback
    now = time.time()
    with _udid_lock:
        hit = _udid_cache.get(scrcpy_url)
        if hit and now - hit[0] < ttl:
            return hit[1] or fallback
    udid = ""
    try:
        raw = _ws_text_once(scrcpy_url.rstrip("/") + "/?action=goog-device-list")
        devs = (json.loads(raw).get("data") or {}).get("list") or []
        udid = next((d.get("udid", "") for d in devs if d.get("state") == "device"), "")
    except Exception:  # noqa: BLE001
        udid = ""
    with _udid_lock:
        _udid_cache[scrcpy_url] = (now, udid)
    return udid or fallback


MANAGER = PreviewManager()
