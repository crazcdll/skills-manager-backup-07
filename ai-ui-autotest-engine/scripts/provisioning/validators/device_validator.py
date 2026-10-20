#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备配置校验器 — device_type × platform × app 支持矩阵，唯一事实来源。

与 env_validator.py 职责对称、正交：
  env_validator    → 认证维度（环境类型 A-D、账号密码、MIS）
  device_validator → 设备维度（云模拟器/本地真机、Android/鸿蒙、美团/点评）

两者都在 flow-init 阶段完成硬校验，报错时机提前到设备创建之前，
避免非法组合跑到 device create / get_app_descriptor 才失败、浪费设备资源。

本模块的 SUPPORTED_DEVICE_COMBINATIONS 与 devices/registry.py 的三张底层
注册表是"业务白名单"与"能力声明"的关系，不是同一份数据的重复拷贝：
  devices/registry.py::_DEVICE_TYPE_REGISTRY  — device_type 理论支持哪些 platform
                                              （能力/接口层面已实现）
  devices/registry.py::_APP_REGISTRY          — (app, platform) 是否已有
                                              AppDescriptor 实现（App 层面已接入）
  本模块::SUPPORTED_DEVICE_COMBINATIONS    — 三者组合是否已经过业务验证、
                                              允许用户在 flow-init 时选择
                                              （如"云模拟器+鸿蒙+美团"即使
                                              两个底层能力都具备，只要没有
                                              实际验证过，也不出现在此白名单）
三者天然可能不同步（能力已具备但业务未验证 ≠ 不合法组合），因此不做
"从底层矩阵自动生成"，而是在模块导入时对 SUPPORTED_DEVICE_COMBINATIONS
做一次性一致性自检（_assert_combinations_backed_by_registries）——
每条白名单组合的 (device_type, platform) 和 (app, platform) 二元组必须先
在底层注册表存在，否则说明白名单本身写错了（如手滑拼错 platform 名称），
在导入阶段直接报错，不拖到用户实际选择该组合时才发现。
"""
from shared.errors import ConfigError


class DeviceValidationError(ConfigError):
    """设备组合校验失败。身份由 ConfigError 基类提供（category=env）。"""
    code = "DEVICE_COMBINATION_INVALID"

# 唯一支持矩阵声明（业务白名单，见上方模块文档字符串）。新增支持组合时：
#   1. 确认 devices/registry.py 的 _DEVICE_TYPE_REGISTRY / _APP_REGISTRY
#      已具备对应能力（若无需先完成平台/App 接入）
#   2. 在此追加一条
# 不需要改动 context.py 的分发逻辑——分发已通过注册表查表完成。
SUPPORTED_DEVICE_COMBINATIONS = [
    {"device_type": "sandbox", "platform": "android", "app": "meituan"},
    {"device_type": "local", "platform": "harmony", "app": "meituan"},
    {"device_type": "local", "platform": "android", "app": "meituan"},
    {"device_type": "cloud-emulator", "platform": "harmony", "app": "meituan"},
    {"device_type": "local-emulator", "platform": "ios", "app": "meituan"},
]


def _assert_combinations_backed_by_registries():
    """校验 SUPPORTED_DEVICE_COMBINATIONS 每条组合的能力底座均已注册。

    只做"白名单是否有能力支撑"的一致性检查，不反向要求底层注册表的
    每个组合都出现在白名单里（能力具备 ≠ 已业务验证，见模块文档）。
    """
    from devices.base import is_device_platform_supported, is_app_platform_supported

    problems = []
    for combo in SUPPORTED_DEVICE_COMBINATIONS:
        dt, pf, app = combo["device_type"], combo["platform"], combo["app"]
        if not is_device_platform_supported(dt, pf):
            problems.append(
                f"{_device_combo_label(dt, pf, app)}: device_type={dt} 未在 "
                f"devices.registry._DEVICE_TYPE_REGISTRY 声明支持 platform={pf}"
            )
        if not is_app_platform_supported(app, pf):
            problems.append(
                f"{_device_combo_label(dt, pf, app)}: app={app} 未在 "
                f"devices.registry._APP_REGISTRY 注册 platform={pf} 的 AppDescriptor 实现"
            )
    if problems:
        detail = "\n  - ".join(problems)
        raise DeviceValidationError(
            f"SUPPORTED_DEVICE_COMBINATIONS 存在缺少能力底座支撑的组合：\n  - {detail}"
        )

DEVICE_TYPE_LABELS = {
    "sandbox": "云模拟器",
    "local": "本地真机",
    "local-emulator": "本地模拟器",
    "cloud-emulator": "云模拟器（Conan）",
    "cloud_device": "云真机（暂不支持）",
}
PLATFORM_LABELS = {
    "android": "Android",
    "harmony": "鸿蒙",
    "ios": "iOS",
}
APP_LABELS = {
    "meituan": "美团",
    "dianping": "点评（暂不支持）",
}

def _device_combo_label(device_type, platform, app):
    dt = DEVICE_TYPE_LABELS.get(device_type, device_type)
    pf = PLATFORM_LABELS.get(platform, platform)
    ap = APP_LABELS.get(app, app)
    return f"{dt} - {pf} - {ap}"

def validate_device_combination(device_type, platform, app):
    """校验 device_type/platform/app 三维组合是否受支持。

    唯一硬校验入口，供 flow_init 在写入 flow-context.json 之前调用。
    不支持时抛出 DeviceValidationError。
    """
    combo = {"device_type": device_type, "platform": platform, "app": app}
    if combo in SUPPORTED_DEVICE_COMBINATIONS:
        return

    supported = "\n".join(
        f"  - {_device_combo_label(c['device_type'], c['platform'], c['app'])}"
        for c in SUPPORTED_DEVICE_COMBINATIONS
    )
    raise DeviceValidationError(
        f"不支持的设备组合：{_device_combo_label(device_type, platform, app)}\n"
        f"当前仅支持以下组合：\n{supported}\n"
        f"请重新选择设备组合。"
    )

def _combo_value(device_type, platform, app):
    """组合唯一编码：device_type-platform-app（如 sandbox-android-meituan）。"""
    return f"{device_type}-{platform}-{app}"


def _device_combo_map():
    """SUPPORTED_DEVICE_COMBINATIONS → {combo: {device_type, platform, app}}。

    交互层只展示 combo 选项（用户选择），内部三维组合保持独立可扩展：
    新增支持组合只需在 SUPPORTED_DEVICE_COMBINATIONS 追加一条，选项与映射自动生成。
    """
    return {
        _combo_value(c["device_type"], c["platform"], c["app"]): {
            "device_type": c["device_type"],
            "platform": c["platform"],
            "app": c["app"],
        }
        for c in SUPPORTED_DEVICE_COMBINATIONS
    }


def device_combo_options() -> list:
    """设备组合选择题选项（value=combo 编码，label=中文）。选项自动随矩阵扩展。"""
    return [
        {
            "value": _combo_value(c["device_type"], c["platform"], c["app"]),
            "label": _device_combo_label(c["device_type"], c["platform"], c["app"]),
        }
        for c in SUPPORTED_DEVICE_COMBINATIONS
    ]


def split_device_combo(combo: str) -> dict:
    """combo 编码 → {device_type, platform, app}；非法 → DeviceValidationError。"""
    meta = _device_combo_map().get(str(combo))
    if not meta:
        raise DeviceValidationError(
            f"device_combo 非法: {combo!r}（可选: {', '.join(_device_combo_map())}）"
        )
    return dict(meta)


# 模块导入时立即自检（早失败）：SUPPORTED_DEVICE_COMBINATIONS 任何一条组合
# 缺少 devices/registry.py 的能力底座支撑，直接在导入阶段报错，不拖到用户
# 实际触发 flow-init 选择该组合时才发现白名单本身写错了。
_assert_combinations_backed_by_registries()
