"""设备平台契约 ABC 汇总导出。"""
from aitest.devices.interfaces.app_descriptor import AppDescriptor
from aitest.devices.interfaces.lifecycle import DeviceLifecycle
from aitest.devices.interfaces.platform_ops import PlatformOps
from aitest.devices.interfaces.renderer_probe import RendererProbe

__all__ = ["PlatformOps", "AppDescriptor", "DeviceLifecycle", "RendererProbe"]
