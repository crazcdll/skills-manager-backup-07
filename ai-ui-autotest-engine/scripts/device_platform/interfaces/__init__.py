"""设备平台契约 ABC 汇总导出。"""
from device_platform.interfaces.app_descriptor import AppDescriptor
from device_platform.interfaces.lifecycle import DeviceLifecycle
from device_platform.interfaces.platform_ops import PlatformOps
from device_platform.interfaces.renderer_probe import RendererProbe

__all__ = ["PlatformOps", "AppDescriptor", "DeviceLifecycle", "RendererProbe"]
