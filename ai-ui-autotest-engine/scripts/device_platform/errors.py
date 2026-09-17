"""设备平台异常：平台模块契约违反、本地真机探测失败。"""
from core.errors import ContractError, DeviceError


class PlatformModuleContractError(ContractError):
    """平台 ops 模块未完整实现 _REQUIRED_MODULE_ATTRS 声明的契约。

    在 get_platform_module() 首次加载该模块时立即抛出（"早失败"），而不是
    等到某个调用方在深层调用栈里踩到 AttributeError 才暴露（"晚失败"）。
    """
class LocalDeviceProbeError(DeviceError):
    """本地真机探测失败（未连接/多设备/屏幕不可交互等可现场修复的状态）。

    guidance_id 命中 environment.device_guidance.GUIDANCE_REGISTRY 时，
    调用方（device_lifecycle.py）据此输出结构化分步引导；未命中时退化为
    纯文本报错，行为与直接抛 RuntimeError 一致。
    """

    def __init__(self, message: str, guidance_id: str = None, **detail):
        super().__init__(message)
        self.guidance_id = guidance_id
        self.detail = detail
