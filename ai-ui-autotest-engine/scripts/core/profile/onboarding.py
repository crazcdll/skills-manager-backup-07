#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备接入策略 —— OnboardingProfile + MockLifecyclePolicy，均由 device_type 分发。

OnboardingProfile 管设备生命周期粒度的准备/收尾（能力位组合，非单一开关）；
MockLifecyclePolicy 管 mis 账号级 AppMock 状态，两者接口互不依赖。

LoginStrategy（environment/login_strategy.py）同样遵循策略模式，但分发键为
env.type，与 device_type 完全解耦（本地真机也需显式声明真实 env.type）。
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
    def needs_device_release(self) -> bool:
        """收尾是否需要 destroy/cleanup。"""

    @abstractmethod
    def needs_screen_check(self) -> bool:
        """每个 UI 步骤执行前是否需要做熄屏/锁屏检查（仅本地真机存在物理熄屏问题）。"""


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

    def needs_device_release(self) -> bool:
        return False  # 复用模拟器，不自动销毁

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

    def needs_device_release(self) -> bool:
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

    def needs_device_release(self) -> bool:
        raise NotImplementedError("Conan release 流程待接入")

    def needs_screen_check(self) -> bool:
        raise NotImplementedError("物理熄屏问题待确认")


class MockLifecyclePolicy(ABC):
    """设备类型 → Mock/AppMock 账号级状态管理策略。"""

    @abstractmethod
    def needs_mock_baseline_snapshot(self) -> bool:
        """B0 阶段是否需要对 mock_ids 做基线快照。"""


class SandboxMockLifecyclePolicy(MockLifecyclePolicy):
    def needs_mock_baseline_snapshot(self) -> bool:
        return True


class LocalMockLifecyclePolicy(MockLifecyclePolicy):
    """本地真机：不做基线快照。"""

    def needs_mock_baseline_snapshot(self) -> bool:
        return False


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

    def needs_device_release(self) -> bool:
        return False

    def needs_screen_check(self) -> bool:
        return False


class LocalEmulatorMockLifecyclePolicy(MockLifecyclePolicy):
    def needs_mock_baseline_snapshot(self) -> bool:
        return False


class CloudDeviceMockLifecyclePolicy(MockLifecyclePolicy):
    """云真机：接入细节待定，先占位骨架。"""

    def needs_mock_baseline_snapshot(self) -> bool:
        raise NotImplementedError("云真机接入待细化")


# ═══════════════════════════════════════════════════════════════════
# device_type → (OnboardingProfile 类, MockLifecyclePolicy 类) 注册表
# 全仓库关于「这类设备的接入策略由哪个类负责」的唯一事实来源
# ═══════════════════════════════════════════════════════════════════
_DEVICE_TYPE_PROFILE_REGISTRY = {
    "sandbox": (SandboxOnboardingProfile, SandboxMockLifecyclePolicy),
    "local": (LocalOnboardingProfile, LocalMockLifecyclePolicy),
    "cloud_device": (CloudDeviceOnboardingProfile, CloudDeviceMockLifecyclePolicy),
    "local-emulator": (LocalEmulatorOnboardingProfile, LocalEmulatorMockLifecyclePolicy),
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
    entry = _DEVICE_TYPE_PROFILE_REGISTRY.get(device_type)
    if entry is None:
        raise RuntimeError(
            f"不支持的设备类型: {device_type}"
            f"（当前仅支持: {', '.join(_DEVICE_TYPE_PROFILE_REGISTRY)}）"
        )
    profile_cls, _ = entry
    return profile_cls(**kwargs)


def create_mock_lifecycle_policy(device_type: str) -> MockLifecyclePolicy:
    """按 device_type 查表构造 MockLifecyclePolicy 实例（无额外构造参数）。

    Raises:
        RuntimeError: device_type 未注册
    """
    entry = _DEVICE_TYPE_PROFILE_REGISTRY.get(device_type)
    if entry is None:
        raise RuntimeError(
            f"不支持的设备类型: {device_type}"
            f"（当前仅支持: {', '.join(_DEVICE_TYPE_PROFILE_REGISTRY)}）"
        )
    _, policy_cls = entry
    return policy_cls()
