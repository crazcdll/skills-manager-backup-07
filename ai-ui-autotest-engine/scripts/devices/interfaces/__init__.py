"""设备平台契约 ABC 汇总导出。"""
from devices.interfaces.app_descriptor import AppDescriptor
from devices.interfaces.lifecycle import DeviceLifecycle
from devices.interfaces.platform_ops import PlatformOps
from devices.interfaces.renderer_probe import RendererProbe

__all__ = ["PlatformOps", "AppDescriptor", "DeviceLifecycle", "RendererProbe"]
