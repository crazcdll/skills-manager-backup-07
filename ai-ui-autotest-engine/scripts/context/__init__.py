#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行上下文 — PlatformOps + DeviceLifecycle + AppDescriptor 延迟初始化与缓存。

Skill 是 CLI 模式（每次命令都是独立进程），不能做常驻依赖注入容器。
用模块级延迟初始化解决：首次调用时读 flow-context.json 的 meta 字段
实例化对应实现并缓存，后续调用返回同一实例。

使用方式：
    from context import get_platform_ops, get_device_lifecycle, get_app_descriptor
    ops = get_platform_ops()
    ops.tap(450, 426)
    lifecycle = get_device_lifecycle()
    lifecycle.acquire(user_mis)
    app = get_app_descriptor()
    app.package_name

首次调用前必须已完成 flow-init（flow-context.json 存在且 meta.device_serial 非空）。
Level 0 命令（device query/release/cleanup）不需要 PlatformOps，不触发初始化。

meta 字段：
    device_serial — adb 设备地址 (ip:port)，必需
    platform      — android/harmony，默认 android（ios 待接入）
    device_type   — sandbox/local/cloud_device，默认 sandbox（cloud_device 待接入）
    app           — meituan/dianping，默认 meituan（dianping 尚未调研，不可用）

    device_type/platform/app 三维组合的合法性由
    environment.device_validator.SUPPORTED_DEVICE_COMBINATIONS 唯一声明，
    flow-init 阶段已做硬校验。

本模块不维护任何 if/elif platform 或 if/elif device_type 分支——全部通过
platform/registry.py 声明的三张注册表查表分发：
    _PLATFORM_MODULES      — platform → ops 模块（PlatformOps 实现 + 契约函数）
    _DEVICE_TYPE_REGISTRY  — device_type → (DeviceLifecycle 实现, 支持的 platform 集合)
    _APP_REGISTRY          — (app, platform) → AppDescriptor 实现
以及 core/onboarding.py 的 _DEVICE_TYPE_PROFILE_REGISTRY（device_type →
OnboardingProfile/MockLifecyclePolicy 实现）。新增平台/设备类型/App 支持时，
只需在对应注册表追加一行，本模块的 create_*/get_* 函数不需要改动。
"""
from core.util.paths import active_case_context_path
from device_platform.base import PlatformOps, DeviceLifecycle, AppDescriptor, RendererProbe

_ops_cache = None
_lifecycle_cache = None
_app_cache = None
_probes_cache = None
_onboarding_cache = None
_mock_policy_cache = None


def _read_meta() -> dict:
    """从 flow-context.json 读取 meta 字段，委托 flow_context.read_meta_fields 完成。"""
    fc_path = active_case_context_path()
    if not fc_path:
        return {}
    from core.flow.flow_context import read_meta_fields
    return read_meta_fields(fc_path)


def get_app_descriptor():
    """获取 AppDescriptor 实例（延迟初始化 + 模块级缓存）。

    首次调用时读 flow-context.json 的 meta.app（默认 "meituan"）和
    meta.platform（默认 "android"），实例化对应实现并缓存。

    同一个 App 在不同 OS 平台上是完全不同的安装包（包名、Activity/Ability、
    调试控件类名均不同），因此 App 维度和 Platform 维度
    在 AppDescriptor 分派上不正交——必须联合 app_name + platform 才能定位
    到具体实现，与 OnboardingProfile/MockLifecyclePolicy 按 device_type
    单维度分派的情况不同。

    Returns:
        AppDescriptor 实例
    """
    global _app_cache
    if _app_cache is not None:
        return _app_cache

    meta = _read_meta()
    app_name = meta.get("app", "meituan")
    platform = meta.get("platform", "android")

    _app_cache = create_app_descriptor(app_name, platform=platform)
    return _app_cache


def create_app_descriptor(app_name: str = "meituan", platform: str = "android") -> AppDescriptor:
    """创建 AppDescriptor 实例（无缓存，每次创建新实例）。

    通过 device_platform.base.get_app_descriptor_class() 按 (app, platform) 二元组
    查表分发，不在本函数内维护 if/elif 分支——新增 App（如点评调研完成后）
    或新增平台时，只需在 device_platform/registry.py::_APP_REGISTRY 追加注册，本函数
    不需要改动。

    Args:
        app_name: App 名称（meituan，dianping 尚未调研，见 _APP_REGISTRY 注释）
        platform: 操作系统平台（android/harmony），决定具体包名/Activity实现
    Returns:
        AppDescriptor 实例
    Raises:
        RuntimeError: (app_name, platform) 组合未注册
    """
    from device_platform.base import get_app_descriptor_class
    cls = get_app_descriptor_class(app_name, platform)
    return cls()


def get_platform_ops():
    """获取 PlatformOps 实例（延迟初始化 + 模块级缓存）。

    首次调用时读 flow-context.json 的 meta.platform（默认 "android"）
    和 meta.device_serial，实例化对应实现并缓存。
    AndroidOps 同时接收 AppDescriptor 实例，用于 open_url 等 App 维度参数。

    Returns:
        PlatformOps 实例

    Raises:
        RuntimeError: flow-context.json 不存在或 meta.device_serial 为空
    """
    global _ops_cache
    if _ops_cache is not None:
        return _ops_cache

    meta = _read_meta()
    serial = meta.get("device_serial", "")
    if not serial:
        raise RuntimeError(
            "无法获取 device_serial：flow-context.json 不存在或 meta.device_serial 为空。"
            "请先执行 device create 创建设备。"
        )

    platform = meta.get("platform", "android")
    _ops_cache = create_platform_ops(serial, platform=platform)
    return _ops_cache


def create_platform_ops(serial: str, platform: str = "android") -> PlatformOps:
    """创建 PlatformOps 实例（无缓存，每次创建新实例）。

    用于 CLI 子进程（如 cmd_setup / cmd_check_version）中需要显式指定
    serial 和 platform 的场景，不走模块级缓存。
    自动注入 AppDescriptor 实例。

    通过 device_platform.base.get_platform_module(platform).PlatformOpsClass 分发，
    不在本函数内维护 if/elif 分支——新增平台时只需在对应 device_platform/<x>/ops.py
    暴露 PlatformOpsClass 契约成员并在 _PLATFORM_MODULES 注册，本函数不需要改动。

    Args:
        serial: 设备标识
        platform: 平台名称（android/harmony，ios 待接入）
    Returns:
        PlatformOps 实例
    Raises:
        RuntimeError: platform 未注册
        PlatformModuleContractError: 模块未完整实现契约
    """
    from device_platform.base import get_platform_module
    app_desc = get_app_descriptor()
    ops_cls = get_platform_module(platform).PlatformOpsClass
    return ops_cls(serial, app_desc)


def get_device_lifecycle():
    """获取 DeviceLifecycle 实例（延迟初始化 + 模块级缓存）。

    首次调用时读 flow-context.json 的 meta.device_type（默认 "sandbox"），
    实例化对应实现并缓存。

    Returns:
        DeviceLifecycle 实例
    """
    global _lifecycle_cache
    if _lifecycle_cache is not None:
        return _lifecycle_cache

    meta = _read_meta()
    device_type = meta.get("device_type", "sandbox")
    platform = meta.get("platform", "android")
    _lifecycle_cache = create_device_lifecycle(device_type, platform=platform)
    return _lifecycle_cache


# device_type → 实例化时需要透传的额外构造参数名集合。sandbox 是无参构造
# （yooz-server 目前只有 Android 镜像，构造函数不感知 platform），
# local/cloud_device 需要 platform 决定探测/交互分发到哪个平台实现。
# 与 device_platform.registry._DEVICE_TYPE_REGISTRY.platforms（回答"这个 device_type
# 支持哪些 platform"）是两件不同的事——本表回答"构造该 DeviceLifecycle
# 实例需要传哪些参数"，二者都由 device_platform/registry.py 统一声明该 device_type
# 存在，本表只管构造签名差异，避免 create_device_lifecycle 里出现
# if device_type == "sandbox": Cls() else: Cls(platform=platform) 分支。
_DEVICE_TYPE_CTOR_KWARGS = {
    "sandbox": (),
    "local": ("platform",),
    "cloud_device": ("platform",),
    "local-emulator": ("platform",),
}


def create_device_lifecycle(device_type: str = "sandbox", platform: str = "android") -> DeviceLifecycle:
    """创建 DeviceLifecycle 实例（无缓存，每次创建新实例）。

    用于 CLI 子进程中需要显式指定 device_type 的场景，不走模块级缓存。

    通过 device_platform.base.get_device_lifecycle_class() 查表拿到实现类，
    再按 _DEVICE_TYPE_CTOR_KWARGS 声明决定是否透传 platform 构造参数，
    不在本函数内维护 if/elif device_type 分支——新增设备获取方式时只需在
    device_platform/registry.py::_DEVICE_TYPE_REGISTRY 注册实现位置，若构造签名需要
    额外参数，同步在 _DEVICE_TYPE_CTOR_KWARGS 声明。

    cloud_device 已声明 platforms 但 lifecycle 模块待接入，调用会在
    get_device_lifecycle_class() 内部因 ImportError 转成清晰的 RuntimeError
    （早失败），且 SUPPORTED_DEVICE_COMBINATIONS 未登记该组合，flow-init
    阶段已提前拦截，正常流程不会走到这里。

    Args:
        device_type: 设备类型（sandbox/local，cloud_device 待接入）
        platform: 操作系统平台（android/harmony），仅构造参数包含 "platform"
            的 device_type 会用到，决定探测/交互分发到哪个平台实现
    Returns:
        DeviceLifecycle 实例
    Raises:
        RuntimeError: device_type 未注册，或已注册但实现模块尚未接入
    """
    from device_platform.base import get_device_lifecycle_class
    cls = get_device_lifecycle_class(device_type)
    ctor_kwargs = _DEVICE_TYPE_CTOR_KWARGS.get(device_type, ())
    kwargs = {"platform": platform} if "platform" in ctor_kwargs else {}
    return cls(**kwargs)


# device_type → 构造 OnboardingProfile 时需要额外透传的 kwargs 提取规则。
# 目前只有 local 的 auto_install 一个特例（来自 meta.device_auto_install），
# 新增此类特例时在此追加一行，get_onboarding_profile 本身不需要改动。
_ONBOARDING_CTOR_KWARGS_EXTRACTORS = {
    "local": lambda meta: {"auto_install": bool(meta.get("device_auto_install"))},
}


def get_onboarding_profile():
    """获取 OnboardingProfile 实例（延迟初始化 + 模块级缓存）。

    首次调用时读 flow-context.json 的 meta.device_type（默认 "sandbox"）和
    meta.device_auto_install，实例化对应实现并缓存。

    通过 core.onboarding.create_onboarding_profile() 查表分发，不在本函数内
    维护 if/elif device_type 分支——新增设备类型时只需在
    core/onboarding.py::_DEVICE_TYPE_PROFILE_REGISTRY 注册。

    Returns:
        OnboardingProfile 实例
    Raises:
        RuntimeError: device_type 未注册
    """
    global _onboarding_cache
    if _onboarding_cache is not None:
        return _onboarding_cache

    from core.profile.onboarding import create_onboarding_profile

    meta = _read_meta()
    device_type = meta.get("device_type", "sandbox")
    extractor = _ONBOARDING_CTOR_KWARGS_EXTRACTORS.get(device_type)
    kwargs = extractor(meta) if extractor else {}
    _onboarding_cache = create_onboarding_profile(device_type, **kwargs)
    return _onboarding_cache


def get_mock_lifecycle_policy():
    """获取 MockLifecyclePolicy 实例（延迟初始化 + 模块级缓存）。

    首次调用时读 flow-context.json 的 meta.device_type（默认 "sandbox"），
    实例化对应实现并缓存。

    通过 core.onboarding.create_mock_lifecycle_policy() 查表分发，不在本
    函数内维护 if/elif device_type 分支。

    Returns:
        MockLifecyclePolicy 实例
    Raises:
        RuntimeError: device_type 未注册
    """
    global _mock_policy_cache
    if _mock_policy_cache is not None:
        return _mock_policy_cache

    from core.profile.onboarding import create_mock_lifecycle_policy

    meta = _read_meta()
    device_type = meta.get("device_type", "sandbox")
    _mock_policy_cache = create_mock_lifecycle_policy(device_type)
    return _mock_policy_cache


def get_probes():
    """获取渲染层探针链（延迟初始化 + 模块级缓存）。

    探针链的组成规则完全由平台决定。
    get_platform_module(platform).build_probes() 决定，本函数只负责
    分发与缓存，不感知任何平台差异（各平台差异原因见对应
    platform/<platform>/ops.py::build_probes 文档字符串）。

    Returns:
        list[RendererProbe]
    """
    global _probes_cache
    if _probes_cache is not None:
        return _probes_cache

    from device_platform.base import get_platform_module
    platform = get_app_descriptor().platform
    module = get_platform_module(platform)
    _probes_cache = module.build_probes(get_platform_ops(), get_app_descriptor())
    return _probes_cache


def invalidate_probes():
    """作废探针链缓存。

    页面切换后渲染容器的存在性会变化，需重新探测。
    与 screen_state.inspect_tree.invalidate_cache 同时调用。

    同时让平台模块重置探针的进程级状态——页面切换后 WebView 可能重新出现，
    重置后探针链在下次 build_probes() 时能重新发现 CDP 调试能力。
    """
    global _probes_cache
    if _probes_cache:
        for p in _probes_cache:
            p.close()
    _probes_cache = None
    # 通过平台注册表分发（与 get_probes / build_probes 同一机制），
    # context 不感知任何具体平台实现
    _reset_platform_probe_state()


def _reset_platform_probe_state():
    """调用当前平台模块的 reset_probe_state()，重置探针的进程级状态。

    探针的进程级状态（如 Android 的 CDP 不可达标记 + WebView 屏幕偏移缓存）
    由各平台模块自行持有，本函数只负责在页面切换时触发重置。历史上此处
    硬编码 `from device_platform.android.probes.webview import reset_cdp_dead_reason`，
    形成 context → android.probes → screen_state.inspect_tree → context 的跨包循环；
    改为平台契约分发后该环被消除。

    平台解析失败时静默跳过（与原实现的 ImportError 兜底等价）。
    """
    try:
        from device_platform.base import get_platform_module
        platform = get_app_descriptor().platform
        get_platform_module(platform).reset_probe_state()
    except Exception:
        pass


def reset_cache():
    """重置缓存（主要用于测试场景）。"""
    global _ops_cache, _lifecycle_cache, _app_cache, _onboarding_cache, _mock_policy_cache
    invalidate_probes()
    _ops_cache = None
    _lifecycle_cache = None
    _app_cache = None
    _onboarding_cache = None
    _mock_policy_cache = None
