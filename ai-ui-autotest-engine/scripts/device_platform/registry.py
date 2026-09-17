"""设备平台注册表：三张表（platform / device_type / app）+ 契约校验 + 查表分发。"""
import importlib
import inspect
from device_platform.errors import PlatformModuleContractError
from device_platform.interfaces.platform_ops import PlatformOps


# ═══════════════════════════════════════════════════════════════════
# 平台模块注册表 —— platform → ops 模块路径，全仓库唯一事实来源
# ═══════════════════════════════════════════════════════════════════
# 新增平台：新建 device_platform/<platform>/ops.py 实现 _REQUIRED_MODULE_ATTRS
# 全部成员，并在下方追加一行即可。
_PLATFORM_MODULES = {
    "android": "device_platform.android.ops",
    "harmony": "device_platform.harmony.ops",
    # ios 模块已注册但未完全就绪：ops.py 有骨架实现（WDA 模式），
    # 但 probes/ 下缺少 native.py 探针、lifecycle 未接入。
    # 实际使用会在缺少的模块处因 ImportError 报错，不会静默失败。
    "ios": "device_platform.ios.ops",
}
# 契约成员清单：(名称, 期望类型, 说明)。callable 校验签名参数个数，None 豁免类型校验
_REQUIRED_MODULE_ATTRS = [
    ("PlatformOpsClass", "subclass",
     "该平台的 PlatformOps 具体实现类（如 AndroidOps/HarmonyOps），"
     "供 context.create_platform_ops 统一按 (serial, app_descriptor) 构造，"
     "不再需要在调用方手写 if/elif platform 分支"),
    ("probe_local_devices", "callable", 0,
     "探测唯一在线的本地设备，失败抛 LocalDeviceProbeError"),
    ("ensure_toolchain", "callable", 0,
     "确保连接工具链（adb/hdc/...）就绪"),
    ("register_device", "callable", 2,
     "注册设备到 imeituan CLI session，返回 {ok, session_id, detail}。"
     "接收 (serial, device_type) 两个参数，按 device_type 选择连接入口"),
    ("build_probes", "callable", 2,
     "构建该平台的渲染层探针链（native 探针）"),
    ("reset_probe_state", "callable", 0,
     "重置本平台探针的进程级状态（页面切换时由 context.invalidate_probes 调用）；"
     "无跨页面状态的平台实现为空函数。使工厂层无需反向依赖具体平台实现"),
    ("parse_tree", "callable", 1,
     "原始视图树 JSON → screen_state.node_model 统一 UiNode 字典列表"),
    ("FRESH_INSTALL_GUIDANCE_ID", (str, type(None)),
     "全新安装后是否存在系统级强制拦截需要展示引导，None 表示无此问题"),
    ("INSTALL_VERIFY_RETRIES", int,
     "安装后版本校验轮询重试上限（各平台安装耗时差异较大）"),
]
_contract_verified = set()  # 已校验通过的 platform 名称，避免重复校验开销
def _verify_module_contract(platform: str, module) -> None:
    """校验平台模块是否完整实现 _REQUIRED_MODULE_ATTRS 声明的全部成员。
    一次性报出全部问题，减少排查往返。
    """
    if platform in _contract_verified:
        return

    problems = []
    for entry in _REQUIRED_MODULE_ATTRS:
        name, kind = entry[0], entry[1]
        if not hasattr(module, name):
            problems.append(f"缺少成员 `{name}`（{entry[-1]}）")
            continue
        value = getattr(module, name)
        if kind == "callable":
            expected_argc = entry[2]
            if not callable(value):
                problems.append(f"`{name}` 应为可调用对象，实际为 {type(value).__name__}")
                continue
            try:
                argc = len(inspect.signature(value).parameters)
            except (TypeError, ValueError):
                argc = expected_argc  # 内建/C 扩展函数拿不到签名时不误报
            if argc != expected_argc:
                problems.append(
                    f"`{name}` 期望 {expected_argc} 个参数，实际签名有 {argc} 个"
                )
        elif kind == "subclass":
            if not (isinstance(value, type) and issubclass(value, PlatformOps)):
                problems.append(f"`{name}` 应为 PlatformOps 的子类，实际为 {value!r}")
        else:
            if value is not None and not isinstance(value, kind):
                problems.append(
                    f"`{name}` 期望类型 {kind}，实际为 {type(value).__name__}"
                )

    if problems:
        detail = "\n  - ".join(problems)
        raise PlatformModuleContractError(
            f"平台模块 {module.__name__}（platform={platform}）未完整实现契约：\n  - {detail}"
        )
    _contract_verified.add(platform)
def get_platform_module(platform: str):
    """按 platform 惰性加载对应 ops 模块，供跨平台统一分发调用。

    首次加载后立即校验模块是否完整实现 _REQUIRED_MODULE_ATTRS 声明的契约，
    校验结果按 platform 缓存，同一平台只在进程内校验一次。

    Raises:
        RuntimeError: platform 未在 _PLATFORM_MODULES 注册
        PlatformModuleContractError: 模块未完整实现契约（早失败，见该异常说明）
    """
    module_path = _PLATFORM_MODULES.get(platform)
    if module_path is None:
        raise RuntimeError(
            f"不支持的 platform: {platform}（当前仅支持: {', '.join(_PLATFORM_MODULES)}）"
        )
    module = importlib.import_module(module_path)
    _verify_module_contract(platform, module)
    return module
def all_platforms() -> tuple:
    """返回全部已注册的 platform 名称（用于文档/校验场景遍历，不建议业务分支用它做 if）。"""
    return tuple(_PLATFORM_MODULES)
# ═══════════════════════════════════════════════════════════════════
# 设备类型注册表 —— device_type → (DeviceLifecycle 实现类路径, 支持的 platform 集合)
# 全仓库关于「这种设备获取方式支持哪些操作系统平台」的唯一事实来源
# ═══════════════════════════════════════════════════════════════════
# 三种设备获取方式与 platform 的支持广度天生不对称，不是靠三元组穷举能长期
# 维护的关系，必须显式声明，而不是散落在 device_validator 的组合清单里
# 靠人工保持一致：
#   - local（本地真机）：设备已物理连接，跨平台通用（一套 LocalDeviceLifecycle
#     内部按 get_platform_module(platform) 分发），新增平台只需 platform/<x>/ops.py
#     实现 probe_local_devices，不需要改 lifecycle 层。
#   - sandbox（云模拟器）：依赖 yooz-server API，目前后端只提供 Android 镜像，
#     "只支持一端"是当前后端能力的限制而非架构限制——SandboxDeviceLifecycle
#     本身不含任何 Android 专属代码（纯 HTTP API 调用），未来 yooz 侧新增
#     鸿蒙镜像时，只需在此扩展 platforms 元组，不需要动 SandboxDeviceLifecycle。
#   - cloud_device（云真机）：依赖 Conan 平台 occupy/release API，规划中支持
#     Android/iOS/Harmony 三端，platforms 预留声明但 lifecycle 模块待接入
#     （对应 CloudDeviceOnboardingProfile 现状，接入前调用会在模块导入时报错，
#     不会拖到运行时）。
#
# 新增/扩展设备获取方式时只需：
#   1. 新建（或扩展）DeviceLifecycle 实现，放在 platform/lifecycle/（跨平台通用）
#      或 platform/<platform>/lifecycle/（确有平台专属逻辑，如未来鸿蒙云真机
#      有独立的 Ability 拉起方式）
#   2. 在 _DEVICE_TYPE_REGISTRY 追加/修改一行
# device_validator.SUPPORTED_DEVICE_COMBINATIONS 的（device_type, platform）
# 二元合法性由本注册表派生，不再单独维护一份平行清单；
# context.create_device_lifecycle 通过 get_device_lifecycle_class() 分发，
# 不再手写 if/elif device_type 分支。
_DEVICE_TYPE_REGISTRY = {
    "sandbox": {
        "module": "device_platform.lifecycle.sandbox",
        "class_name": "SandboxDeviceLifecycle",
        "platforms": ("android",),
        "category": "cloud",
    },
    "local": {
        "module": "device_platform.lifecycle.local",
        "class_name": "LocalDeviceLifecycle",
        "platforms": ("android", "harmony"),
        "category": "local",
    },
    "cloud_device": {
        "module": "device_platform.lifecycle.cloud_device",
        "class_name": "CloudDeviceLifecycle",
        "platforms": ("android", "ios", "harmony"),
        "category": "cloud",
    },
    "local-emulator": {
        "module": "device_platform.lifecycle.local_emulator",
        "class_name": "LocalEmulatorDeviceLifecycle",
        "platforms": ("ios",),
        "category": "local",
    },
}
def all_device_types() -> tuple:
    """返回全部已注册的 device_type 名称（用于文档/问题清单遍历）。"""
    return tuple(_DEVICE_TYPE_REGISTRY)
def get_supported_platforms(device_type: str) -> tuple:
    """返回指定 device_type 支持的 platform 集合，供 device_validator 派生
    SUPPORTED_DEVICE_COMBINATIONS、cli.py device-required 生成选项禁用态使用。

    Raises:
        RuntimeError: device_type 未在 _DEVICE_TYPE_REGISTRY 注册
    """
    entry = _DEVICE_TYPE_REGISTRY.get(device_type)
    if entry is None:
        raise RuntimeError(
            f"不支持的 device_type: {device_type}（当前仅支持: {', '.join(_DEVICE_TYPE_REGISTRY)}）"
        )
    return entry["platforms"]
def get_device_category(device_type: str) -> str:
    """返回 device_type 的类别（cloud / local）。

    cloud 类别：云端设备，需要 sandbox_id 标识，可能涉及 ADB Server 修复。
    local 类别：本地设备（真机或模拟器），不需要 sandbox_id。

    Raises:
        RuntimeError: device_type 未在 _DEVICE_TYPE_REGISTRY 注册
    """
    entry = _DEVICE_TYPE_REGISTRY.get(device_type)
    if entry is None:
        raise RuntimeError(
            f"不支持的 device_type: {device_type}（当前仅支持: {', '.join(_DEVICE_TYPE_REGISTRY)}）"
        )
    return entry.get("category", "unknown")
def is_device_platform_supported(device_type: str, platform: str) -> bool:
    """判断 (device_type, platform) 组合是否受支持，未注册的 device_type 视为不支持。"""
    entry = _DEVICE_TYPE_REGISTRY.get(device_type)
    return bool(entry) and platform in entry["platforms"]
def get_device_lifecycle_class(device_type: str):
    """按 device_type 惰性加载对应 DeviceLifecycle 实现类。

    只做「拿到类」这一步，不负责实例化（sandbox 无参构造，local 需要
    platform 参数，未来 cloud_device 可能还需要 user_mis），实例化参数
    差异由调用方（context.create_device_lifecycle）处理，本函数只保证
    「device_type → 类」这一映射关系不再散落。

    Raises:
        RuntimeError: device_type 未注册，或已注册但模块/类尚未实现
            （如 cloud_device 当前仅有 platforms 声明，lifecycle 模块待接入）
    """
    entry = _DEVICE_TYPE_REGISTRY.get(device_type)
    if entry is None:
        raise RuntimeError(
            f"不支持的 device_type: {device_type}（当前仅支持: {', '.join(_DEVICE_TYPE_REGISTRY)}）"
        )
    try:
        module = importlib.import_module(entry["module"])
    except ImportError as e:
        raise RuntimeError(
            f"device_type={device_type} 已注册但实现模块 {entry['module']} 尚未接入: {e}"
        ) from e
    return getattr(module, entry["class_name"])
# ═══════════════════════════════════════════════════════════════════
# App 注册表 —— (app, platform) → AppDescriptor 实现类路径
# 全仓库关于「目标 App 在某平台上具体是什么」的唯一事实来源
# ═══════════════════════════════════════════════════════════════════
# App 维度与 Platform 维度不正交：同一个 App 在不同 OS 上是完全独立的安装包
# （包名、Activity/Ability、调试控件类名均不同），因此分派键必须是二元组
# (app, platform)，与 PlatformOps/DeviceLifecycle 的单维度分派不同。
#
# 只有 (app, platform) 二元组同时出现在本表中，该组合才「可用」；
# 只声明了 app 名称、没有对应 platform 条目的场景（如 dianping 登录方式/
# 可测性通道尚未调研）视为未支持，get_app_descriptor_class() 直接报错，
# 不会静默回退到美团实现或返回残缺对象——与 login_strategy.py 的
# APP_LOGIN_STRATEGY_BUILDERS、env_validator.py 的 APP_ENV_TYPE_RULES
# 遵循同一约定："未注册即不可用"，三张表各自独立维护但语义对齐，
# 同一个 App 要完整可用必须三表同时补齐。
#
# 新增 App 支持时只需：
#   1. 在 device_platform/<platform>/apps/ 下新增 <app>.py 实现 AppDescriptor
#   2. 在 _APP_REGISTRY 追加一行注册
#   3. 同步补齐 login_strategy.py / env_validator.py / auth_validator.py / device_validator.py 四处
#      各命令内置的 AI 引导提示已涵盖规则，无需再查阅独立文档
# 不需要改动 context/__init__.py——create_app_descriptor 通过
# get_app_descriptor_class() 统一分发，不会新增 if/elif app 分支。
_APP_REGISTRY = {
    ("meituan", "android"): "device_platform.android.apps.meituan.MeituanAppDescriptor",
    ("meituan", "harmony"): "device_platform.harmony.apps.meituan.MeituanHarmonyAppDescriptor",
    ("meituan", "ios"): "device_platform.ios.apps.meituan.MeituanIOSAppDescriptor",
    # ("dianping", "android"): 登录方式/可测性通道尚未调研，未注册前禁止使用。
    # 新增 App 时同步补齐 login_strategy.py / env_validator.py / auth_validator.py / device_validator.py 四处。
}
def all_apps() -> tuple:
    """返回全部已注册 (app, platform) 组合中的 app 名称去重集合。"""
    seen = []
    for app_name, _ in _APP_REGISTRY:
        if app_name not in seen:
            seen.append(app_name)
    return tuple(seen)
def get_supported_platforms_for_app(app_name: str) -> tuple:
    """返回指定 app 已注册可用的 platform 集合，未注册任何组合时返回空元组。"""
    return tuple(p for a, p in _APP_REGISTRY if a == app_name)
def is_app_platform_supported(app_name: str, platform: str) -> bool:
    """判断 (app, platform) 组合是否已注册可用。"""
    return (app_name, platform) in _APP_REGISTRY
def get_app_descriptor_class(app_name: str, platform: str):
    """按 (app, platform) 惰性加载对应 AppDescriptor 实现类。

    Raises:
        RuntimeError: 组合未在 _APP_REGISTRY 注册（含"App 存在但该平台未调研"
            的场景，如 dianping 尚未在任何 platform 下注册）
    """
    dotted_path = _APP_REGISTRY.get((app_name, platform))
    if dotted_path is None:
        registered = "、".join(f"{a}@{p}" for a, p in _APP_REGISTRY) or "（无）"
        raise RuntimeError(
            f"不支持的 App 组合: app={app_name} platform={platform}"
            f"（当前已注册: {registered}）"
        )
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
