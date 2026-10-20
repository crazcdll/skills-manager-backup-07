#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预览适配器基类 + 公共工具。"""
import os
import subprocess
import tempfile


def detect_mime(data: bytes) -> str:
    """按魔数判定图片类型（避免引入 PIL 依赖）。"""
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"GIF8":
        return "image/gif"
    return "application/octet-stream"


class PreviewAdapter:
    """一个设备一种预览策略。frames() 生成 (mime, bytes)。"""

    kind = "none"

    def __init__(self, device: dict):
        self.device = device or {}
        self._stopped = False

    @property
    def serial(self) -> str:
        return self.device.get("serial", "")

    def frames(self):
        return iter(())

    def stop(self):
        self._stopped = True


def run_imeituan(args, timeout=20, session_id=None):
    """执行 imeituan CLI（复用引擎封装；失败返回 None）。"""
    try:
        from provisioning.prereq.node_env import imeituan_run
    except Exception:
        return None
    env_extra = {"IMEITUAN_SESSION": session_id} if session_id else None
    try:
        return imeituan_run([str(a) for a in args], capture=True,
                            timeout=timeout, env_extra=env_extra)
    except Exception:
        return None


def grab_screenshot(session_id, timeout=20):
    """抓一张设备截图（返回 (mime, bytes) 或 None）。走 imeituan device screenshot。"""
    if not session_id:
        return None
    fd, path = tempfile.mkstemp(suffix=".img")
    os.close(fd)
    try:
        r = run_imeituan(["device", "screenshot", "-o", path],
                         timeout=timeout, session_id=session_id)
        if r is None:
            return None
        if getattr(r, "returncode", 1) != 0 and not os.path.getsize(path):
            return None
        if not os.path.getsize(path):
            return None
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            return None
        return detect_mime(data), data
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
