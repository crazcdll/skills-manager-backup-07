#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备接入策略 —— OnboardingProfile，按 device_type 分发。

OnboardingProfile 管设备生命周期粒度的准备/收尾（能力位组合，非单一开关）。

登录流程（`provisioning/setup/login/registry.py::ENV_STEPS` + `login/plan.py`）同样遵循策略
模式，但分发键为 `env_type`，与 device_type 完全解耦（本地真机也需显式声明真实 env_type）。
"""
from abc import ABC, abstractmethod


class OnboardingProfile(ABC):
    """设备类型 → 环境准备策略。回答"这类设备接入生命周期要做哪些事"。"""

    @property
    @abstractmethod
    def device_type(self) -> str:
        """设备类型标识：sandbox / local / cloud_device。"""

    @abstractmethod
    def needs_device_acquire(self) -> bool:
        """是否需要走 DeviceLifecycle.acquire()。"""

    @abstractmethod
    def needs_version_check(self) -> bool:
        """是否需要探测已装版本 vs 目标版本（只读探测，不代表会执行安装）。"""

    @abstractmethod
    def needs_app_install(self) -> bool:
        """版本不符时是否允许自动卸载重装（激进动作，会清空已安装 App 的本地数据）。"""

    @abstractmethod
    def needs_install_if_missing(self) -> bool:
        """完全未安装时是否允许自动补装（保守动作，不触碰任何已有安装）。

        与 needs_app_install() 正交：后者管"版本不符要不要卸载重装"的激进操作，
        本方法只管"完全未安装时要不要装"的保守操作，因此本地真机可默认开启。
        """

    @abstractmethod
    def needs_first_run_onboarding(self) -> bool:
        """是否需要隐私协议弹窗引导 + 冷重启（仅"全新安装"场景需要）。"""

    @abstractmethod
    def needs_keyboard_setup(self) -> bool:
        """是否需要安装 ADBKeyboard 并设为默认输入法（仅云模拟器使用）。"""

    @abstractmethod
    def needs_screen_check(self) -> bool:
        """每个 UI 步骤执行前是否需要做熄屏/锁屏检查（仅本地真机存在物理熄屏问题）。"""

    def required_capabilities(self) -> tuple:
        """**硬依赖**能力声明（`shared.capabilities.CAP_*`）。

        默认空 = 不设硬依赖（探测结果只做记录与降级）。声明后：`device setup`
        实测到这些能力 `unavailable` 时会**立即失败**（而不是跑到登录/断言中途才炸）。

        政策刻意保守：只有"缺了它，本次用例必然无法完成且无降级路径"的能力才应声明。
        例：视图树采集在**首页**本就不支持（未注入 dump），故不声明为硬依赖。
        """
        return ()


class SandboxOnboardingProfile(OnboardingProfile):
    """云模拟器：全套流程（按 needs_app_install 卸载重装，不走 install_if_missing）。

    sandbox 每次都是全新实例，不需要区分"保守补装"和"激进重装"，两者都开会导致
    install_if_missing 分支因未传 sandbox_id 而报错，因此只走 needs_app_install。
    """

    @property
    def device_type(self) -> str:
        return "sandbox"

    def needs_device_acquire(self) -> bool:
        return True

    def needs_version_check(self) -> bool:
        return True

    def needs_app_install(self) -> bool:
        return True

    def needs_install_if_missing(self) -> bool:
        return False

    def needs_first_run_onboarding(self) -> bool:
        return True

    def needs_keyboard_setup(self) -> bool:
        return True

    def needs_screen_check(self) -> bool:
        return False


class LocalOnboardingProfile(OnboardingProfile):
    """本地真机（Android/Harmony 通用，平台差异交给 PlatformOps）。

    不获取/不装机引导/不销毁，只做 session 注册 + AppMock 环境重置。app_install
    （版本不符即卸载重装）默认关闭需用户显式打开，避免误卸装正式包；
    install_if_missing（完全未安装时补装）恒为 True，属保守动作。
    """

    def __init__(self, auto_install: bool = False):
        self._auto_install = auto_install

    @property
    def device_type(self) -> str:
        return "local"

    def needs_device_acquire(self) -> bool:
        return False

    def needs_version_check(self) -> bool:
        return True

    def needs_app_install(self) -> bool:
        return self._auto_install

    def needs_install_if_missing(self) -> bool:
        return True

    def needs_first_run_onboarding(self) -> bool:
        return False

    def needs_keyboard_setup(self) -> bool:
        return False

    def needs_screen_check(self) -> bool:
        return True


class CloudDeviceOnboardingProfile(OnboardingProfile):
    """云真机（Conan 平台）：接入细节待定，先占位骨架。
    
    注：当前所有方法均抛出 NotImplementedError，仅做协议占位。
    计划在 Conan 设备接入调研完成后（预计 2026 Q3）补充实现。
    入口已在 SUPPORTED_DEVICE_COMBINATIONS 中设为不可选，
    flow-init 阶段会提前拦截，正常流程不会走到这里。
    """

    @property
    def device_type(self) -> str:
        return "cloud_device"

    def needs_device_acquire(self) -> bool:
        raise NotImplementedError("Conan occupy 流程待接入")

    def needs_version_check(self) -> bool:
        raise NotImplementedError("镜像预装 App 情况待确认")

    def needs_app_install(self) -> bool:
        raise NotImplementedError("镜像预装 App 情况待确认")

    def needs_install_if_missing(self) -> bool:
        raise NotImplementedError("接入时应比照 SandboxOnboardingProfile 恒为 True")

    def needs_first_run_onboarding(self) -> bool:
        raise NotImplementedError("待接入")

    def needs_keyboard_setup(self) -> bool:
        raise NotImplementedError("待接入")

    def needs_screen_check(self) -> bool:
        raise NotImplementedError("物理熄屏问题待确认")


class LocalEmulatorOnboardingProfile(OnboardingProfile):
    """本地模拟器（iOS/Android 模拟器通用）。

    不销毁实例，只做 session 注册 + 版本探测 + 首次启动抑制断言。
    """

    def __init__(self, auto_install: bool = True):
        self._auto_install = auto_install

    @property
    def device_type(self) -> str:
        return "local-emulator"

    def needs_device_acquire(self) -> bool:
        return True

    def needs_version_check(self) -> bool:
        return True

    def needs_app_install(self) -> bool:
        return self._auto_install

    def needs_install_if_missing(self) -> bool:
        return True

    def needs_first_run_onboarding(self) -> bool:
        return False

    def needs_keyboard_setup(self) -> bool:
        return False

    def needs_screen_check(self) -> bool:
        return False


class CloudEmulatorOnboardingProfile(OnboardingProfile):
    """Conan 云模拟器（form=emulator，消耗型资源；当前仅注册了 harmony，见 registry）。

    与 sandbox（yooz，一次性实例、卸载重装）不同：Conan 模拟器镜像可能已预装包
    （com.sankuai.hmeituan，非 enterprise），因此基础语义是**只在缺失时补装**；
    无输入法配置、无物理熄屏问题。

    `align_testability_build`（调用方按 meta.platform 注入，见 shared.context 的
    `_ONBOARDING_CTOR_KWARGS_EXTRACTORS`）：鸿蒙镜像预装的是**正式包**，而登录
    signin 依赖可测性(debug)包的 MSI 能力——正式包会静默卡 Loading 且页面不报错，
    因此鸿蒙**必须**在版本不一致时卸载重装到配置的可测性包。
    默认取 False（保守：镜像预装即复用，缺失才补装）——"必须对齐可测性构建"是
    平台专属要求，必须由提取器显式声明（鸿蒙由
    `shared/context.py::_ONBOARDING_CTOR_KWARGS_EXTRACTORS` 按 meta.platform 注入 True）。
    这样将来新增 iOS 等平台时，漏配提取器会退化为保守行为，而不会默认触发卸载重装。

    首启处理（`needs_first_run_onboarding=True`）：全新安装后的首启弹窗链必须收敛
    （见该类下方方法注释），否则系统弹窗会挡住登录页。
    """

    def __init__(self, align_testability_build: bool = False):
        self._align_testability_build = align_testability_build

    @property
    def device_type(self) -> str:
        return "cloud-emulator"

    def needs_device_acquire(self) -> bool:
        return True

    def needs_version_check(self) -> bool:
        return True

    def needs_app_install(self) -> bool:
        return self._align_testability_build

    def needs_install_if_missing(self) -> bool:
        return True

    def needs_first_run_onboarding(self) -> bool:
        # 该位的契约就是"全新安装场景需要"：Conan 模拟器可能全新安装（镜像预装的正式包
        # 与目标版本不一致时会对齐重装），而首装后的首启弹窗链（隐私协议 → 系统通知权限
        # → 定位引导/权限）必须收敛，否则会直接挡住登录页导致登录判定失败。
        # 具体动作由 `device_commands._first_run_onboarding` 按 fresh_install 决定：
        # 复用现有安装时只拉起前台，不重复冷重启。
        return True

    def needs_keyboard_setup(self) -> bool:
        return False

    def needs_screen_check(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════
# device_type → OnboardingProfile 类 注册表
# 全仓库关于「这类设备的接入策略由哪个类负责」的唯一事实来源
# ═══════════════════════════════════════════════════════════════════
_DEVICE_TYPE_PROFILE_REGISTRY = {
    "sandbox": SandboxOnboardingProfile,
    "local": LocalOnboardingProfile,
    "cloud_device": CloudDeviceOnboardingProfile,
    "cloud-emulator": CloudEmulatorOnboardingProfile,
    "local-emulator": LocalEmulatorOnboardingProfile,
}


def create_onboarding_profile(device_type: str, **kwargs) -> OnboardingProfile:
    """按 device_type 查表构造 OnboardingProfile 实例。

    Args:
        device_type: 设备类型（sandbox/local/cloud_device）
        **kwargs: 透传给具体实现的构造参数（如 LocalOnboardingProfile 的
            auto_install），非该实现所需的参数会在构造时报 TypeError，
            调用方需按 device_type 自行判断是否传入。
    Raises:
        RuntimeError: device_type 未注册
    """
    profile_cls = _DEVICE_TYPE_PROFILE_REGISTRY.get(device_type)
    if profile_cls is None:
        raise RuntimeError(
            f"不支持的设备类型: {device_type}"
            f"（当前仅支持: {', '.join(_DEVICE_TYPE_PROFILE_REGISTRY)}）"
        )
    return profile_cls(**kwargs)
