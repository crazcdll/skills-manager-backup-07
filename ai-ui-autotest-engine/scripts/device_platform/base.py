"""设备平台契约与注册表的统一导入入口（facade）。

职责边界（原 base.py 已按职责拆分为同层模块）：
    errors.py        平台相关异常类
    interfaces/      4 个契约 ABC
                     platform_ops / app_descriptor / lifecycle / renderer_probe
    registry.py      3 张注册表（platform / device_type / app）+ 契约校验 + 查表分发

本模块保留为**统一入口**，对外 API 不变——调用方
`from device_platform.base import PlatformOps, get_platform_module, ...` 零改动。
新增平台 / 设备类型 / App 时只需改 registry.py 的注册表，本文件不需要改动。

注：`PlatformOps` 目前仍是较宽的接口（含部分平台专属能力），
后续可按 ISP 在 interfaces/ 下进一步拆分；本文件作为入口无需随之改动。
"""
from device_platform.errors import PlatformModuleContractError, LocalDeviceProbeError
from device_platform.interfaces.app_descriptor import AppDescriptor
from device_platform.interfaces.lifecycle import DeviceLifecycle
from device_platform.interfaces.platform_ops import PlatformOps
from device_platform.interfaces.renderer_probe import RendererProbe
from device_platform.registry import (
    all_apps,
    all_device_types,
    all_platforms,
    get_app_descriptor_class,
    get_device_category,
    get_device_lifecycle_class,
    get_platform_module,
    get_supported_platforms,
    get_supported_platforms_for_app,
    is_app_platform_supported,
    is_device_platform_supported,
)

__all__ = [
    # 异常
    "PlatformModuleContractError", "LocalDeviceProbeError",
    # 契约 ABC
    "PlatformOps", "AppDescriptor", "DeviceLifecycle", "RendererProbe",
    # 注册表查询 / 契约校验
    "get_platform_module", "all_platforms",
    "all_device_types", "get_supported_platforms", "get_device_category",
    "is_device_platform_supported", "get_device_lifecycle_class",
    "all_apps", "get_supported_platforms_for_app", "is_app_platform_supported",
    "get_app_descriptor_class",
]
