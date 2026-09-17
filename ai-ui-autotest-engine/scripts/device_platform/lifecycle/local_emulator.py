#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LocalEmulatorDeviceLifecycle — 本地模拟器设备生命周期实现（覆盖 iOS / Android 模拟器）。

负责本地已安装模拟器的发现、启动校验与静默准备（如启动 WDA 服务），
无需走云端沙箱 API 创建或销毁。
"""
import subprocess
import sys
from device_platform.base import DeviceLifecycle, PlatformOps, get_platform_module
from infra.node_env import imeituan_run


class LocalEmulatorDeviceLifecycle(DeviceLifecycle):
    """本地模拟器生命周期实现。"""

    def __init__(self, platform: str = "ios"):
        self._platform = platform

    @property
    def device_type(self) -> str:
        return "local-emulator"

    def acquire(self, user_mis: str) -> dict:
        """探测或启动本地模拟器实例，并在后台静默拉起 WDA 服务（使用 --mode serve，不弹浏览器窗口）。"""
        module = get_platform_module(self._platform)
        serial = module.probe_local_devices()

        # 如果是 iOS 模拟器，静默启动 WDA serve 通道（--mode serve，不弹网页）
        if self._platform == "ios":
            try:
                sys.stderr.write(f"[device:lifecycle] 静默就绪 iOS 模拟器 WDA 服务 (serial={serial})...\n")
                imeituan_run([
                    "device", "remote-desktop",
                    "-p", "ios",
                    "--target", "local-emulator",
                    "--device-id", serial,
                    "--auto-install",
                    "--mode", "serve",
                    "--format", "json"
                ], timeout=45)
            except Exception as e:
                sys.stderr.write(f"[device:lifecycle] ⚠️ WDA 静默准备跳过/异常: {e}\n")

        return {"serial": serial, "sandboxId": None}

    def install_app(self, ops: PlatformOps, artifact_url: str, device_id: str = None) -> bool:
        """安装应用包到模拟器。"""
        # 如果是 preset 或 URL 安装，直接通过 imeituan device install
        if artifact_url in ("meituan", "dianping") or not artifact_url:
            r = imeituan_run(["device", "install", "--preset", artifact_url or "meituan", "--format", "json"], timeout=300)
            return r.returncode == 0
        return ops.install_app(artifact_url)

    def release(self, device_info: dict) -> bool:
        """本地模拟器保持复用，不执行销毁操作。"""
        return True

    def query_user_devices(self, user_mis: str) -> list:
        return []

    def cleanup_user_devices(self, user_mis: str) -> dict:
        return {"released": [], "errors": []}
