#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LocalDeviceLifecycle — 本地真机设备生命周期实现（跨平台，非 Android 专属）。

本地真机不需要获取和释放（设备已物理连接），但"获取"仍需完成设备发现
（探测唯一在线设备 + 前置可用性校验），只是不经过云端 API。

探测逻辑分发到 device_platform.base.get_platform_module(platform) 返回的平台
ops 模块（该模块必须实现的契约成员清单见 device_platform/registry.py 顶部注释），
本文件不感知任何平台细节，新增平台支持无需改动本文件。

安装统一透传给 PlatformOps.install_app()，由各平台实现自行处理安装细节。

按 platform 动态分派，同时服务多平台，因此放在 device_platform/ 顶层而非
device_platform/android/ 下（区别于 SandboxDeviceLifecycle——后者依赖
yooz-server API，是 Android/云模拟器专属）。
"""
from device_platform.base import DeviceLifecycle, PlatformOps, get_platform_module


class LocalDeviceLifecycle(DeviceLifecycle):
    """本地真机设备生命周期实现（跨平台：Android + HarmonyOS 均适用）。"""

    def __init__(self, platform: str = "android"):
        self._platform = platform

    @property
    def device_type(self) -> str:
        return "local"

    def acquire(self, user_mis: str) -> dict:
        """探测唯一在线的本地设备并校验前置可用性，返回其 serial。

        探测逻辑分发到 get_platform_module(self._platform).probe_local_devices()，
        本方法不感知任何平台细节。

        Raises:
            LocalDeviceProbeError: 平台专属探测失败（见各 probe_local_devices）
            RuntimeError: platform 未在 device_platform.registry._PLATFORM_MODULES 注册
        """
        module = get_platform_module(self._platform)
        return {"serial": module.probe_local_devices(), "sandboxId": None}

    def install_app(self, ops: PlatformOps, artifact_url: str,
                    device_id: str = None) -> bool:
        """透传给 PlatformOps.install_app() 直接安装应用到设备。"""
        return ops.install_app(artifact_url)

    def release(self, device_info: dict) -> bool:
        """本地真机不需要释放。"""
        return True

    def query_user_devices(self, user_mis: str) -> list:
        """本地真机不涉及用户设备查询。"""
        return []

    def cleanup_user_devices(self, user_mis: str) -> dict:
        """本地真机不涉及用户设备清理。"""
        return {"released": [], "errors": []}
