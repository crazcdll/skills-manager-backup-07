#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截图轮询预览：通用兜底（Android/鸿蒙 皆可），约 1 帧/秒。

对**鸿蒙云模拟器**尤其契合：其 relay 本身也是 JPEG 截图流；直接轮询
`imeituan device screenshot` 无需任何转码即可作为 MJPEG 输出。
"""
import time

from console import config
from console.preview.base import PreviewAdapter, grab_screenshot


class ScreenshotPreview(PreviewAdapter):
    kind = "screenshot"

    def __init__(self, device, interval=config.PREVIEW_INTERVAL_SEC):
        super().__init__(device)
        self.interval = max(interval, 1.0 / config.PREVIEW_MAX_FPS)

    def frames(self):
        session_id = self.device.get("session_id", "")
        while not self._stopped:
            t0 = time.time()
            shot = grab_screenshot(session_id, timeout=18)
            if shot:
                yield shot
            if self._stopped:
                break
            dt = time.time() - t0
            if dt < self.interval:
                time.sleep(self.interval - dt)
