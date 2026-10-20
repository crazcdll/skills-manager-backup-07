#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 设备端开关 —— enable / disable / SDK 状态检查。

Android 和 HarmonyOS 走完全独立的两套实现（非简单的参数/文案差异，而是
整条下发链路不同），因此不用内联 if/else 分叉，而是各自实现一个完整的
_AppmockDeviceStrategy 并按 platform 注册分发（_STRATEGIES），新增平台
支持时只需实现并注册一个新策略，不需要改动本文件其余逻辑或调用方
（appmock_enable/appmock_disable/check_appmock_sdk_enabled/appmock_ready
四个对外接口签名不变）。

Android: 仅走 ContentProvider 直连（adb content call），不再经过 imeituan CLI。

HarmonyOS: `imeituan-cli` 的 `inject mock enable/disable` 底层与 `device
open-url` 复用同一套 scheme 分发机制（pillow-schema），在 HarmonyOS 分支未
实现"显式指定目标包"能力（--package-id 被静默忽略），裸拼
`hdc shell aa start -U <scheme>` 缺少 `-b <bundle>`，必然触发系统多包消歧
弹窗（设备上通常同时装有正式版 + beta 版）。实测已验证 AppMock 开关本质是
`imeituan://www.meituan.com/appmock/enable?misId=<mis>` /
`imeituan://www.meituan.com/appmock/disable` 两个 scheme 跳链，因此鸿蒙场景
完全绕开 imeituan-cli 的 inject 封装，直接走 PlatformOps.launch_scheme()
（HarmonyOps 内部用 `-b <bundle> -A action.system.home -U <scheme>` 组合，
已验证静默生效、无消歧弹窗），与 HarmonyOps.open_url() 走同一条已验证通道。
HarmonyOS 无 ContentProvider 机制，且 AppMock enable/disable 是单向 scheme
跳链（无对应的状态查询 scheme），无法做强验证，check_sdk_enabled 恒返回
False，由 appmock_enable 走"已下发但无法确认"的降级提示分支。

业务层（登录动作等）请用 `appmock_ready()`：它按 `PlatformOps.can_verify_appmock_state`
能力位回答"能不能用"，从而避免把"平台是否可确认"这条平台差异以**隐式分支**的
形式带进业务层（鸿蒙恒 False ⇒ 恒失败）。`check_appmock_sdk_enabled` 表示的是
"设备端真实状态"，只有必须知道真实状态才能决策的地方才可用（架构守卫规则 20）。
"""
from abc import ABC, abstractmethod

from shared.case_utils import set_mock_domain, resolve_mock_domain
from shared.context import get_app_descriptor, get_platform_ops
from platform.appmock.client import _device_content_call


class _AppmockDeviceStrategy(ABC):
    """单平台 AppMock 设备端开关的完整实现契约。"""

    @abstractmethod
    def check_sdk_enabled(self) -> bool:
        ...

    @abstractmethod
    def enable(self, mis: str, verify: bool) -> bool:
        ...

    @abstractmethod
    def disable(self) -> bool:
        ...


class _AndroidAppmockStrategy(_AppmockDeviceStrategy):
    """Android：ContentProvider 直连（adb content call），不再兜底 imeituan CLI。

    ContentProvider 直连通过 `adb shell content call` 直接调用 App 内
    AppMock ContentProvider，不依赖 Mpium WebSocket 云通道，在 force-stop
    冷重启后依然可靠。
    """

    def check_sdk_enabled(self) -> bool:
        ok, out = _device_content_call("getStatus")
        if ok:
            out_lower = out.strip().lower()
            return "enabled=true" in out_lower or "true" in out_lower
        return False

    def enable(self, mis: str, verify: bool) -> bool:
        # ContentProvider 直连（adb content call）—— 设备端唯一开关通道
        print(f"APPMOCK ENABLE: 通过 ContentProvider 直连启用 AppMock (user={mis})...")
        ok, out = _device_content_call("enable", mis)
        if not ok:
            print(f"APPMOCK ENABLE FAIL (content call): {out}")
            return False
        print(f"APPMOCK ENABLE OK (content call): user={mis}")
        set_mock_domain(mis)

        if not verify:
            return True

        if self.check_sdk_enabled():
            print(f"APPMOCK ENABLE VERIFIED: 设备端 SDK 已确认启用")
            return True

        print("APPMOCK ENABLE: 设备端状态查询显示未启用，重试一次...")
        ok, out = _device_content_call("enable", mis)
        if ok and self.check_sdk_enabled():
            print(f"APPMOCK ENABLE VERIFIED (重试后): 设备端 SDK 已确认启用")
            return True

        print("APPMOCK ENABLE WARN: 指令已下发但设备端状态查询仍未确认启用，"
              "请读图确认 MOCK 标签或用 record-data 核实。")
        return True

    def disable(self) -> bool:
        # ContentProvider 直连（设备端唯一开关通道）
        ok, out = _device_content_call("disable")
        if ok:
            print("APPMOCK DISABLE OK (content call)")
            return True
        print(f"APPMOCK DISABLE FAIL (content call): {out}")
        return False


class _HarmonyAppmockStrategy(_AppmockDeviceStrategy):
    """HarmonyOS：绕开 imeituan-cli inject 封装，直接走 PlatformOps.launch_scheme()。"""

    def _scheme(self, action: str, mis: str = None) -> str:
        prefix = get_app_descriptor().scheme_prefix
        if action == "enable":
            return f"{prefix}/appmock/enable?misId={mis}"
        return f"{prefix}/appmock/disable"

    def check_sdk_enabled(self) -> bool:
        return False

    def enable(self, mis: str, verify: bool) -> bool:
        ops = get_platform_ops()
        scheme = self._scheme("enable", mis)
        if not ops.launch_scheme(scheme):
            print(f"APPMOCK ENABLE FAIL (harmony scheme): {scheme}")
            return False
        print(f"APPMOCK ENABLE OK (harmony scheme): user={mis}")
        set_mock_domain(mis)
        print("APPMOCK ENABLE WARN: HarmonyOS 无状态查询通道，指令已下发，"
              "请读图确认 MOCK 标签或用 record-data 核实。")
        return True

    def disable(self) -> bool:
        ops = get_platform_ops()
        scheme = self._scheme("disable")
        if ops.launch_scheme(scheme):
            print(f"APPMOCK DISABLE OK (harmony scheme)")
            return True
        print(f"APPMOCK DISABLE FAIL (harmony scheme): {scheme}")
        return False


# platform → 策略实例，唯一事实来源。新增平台支持时在此注册一个完整实现。
_STRATEGIES = {
    "android": _AndroidAppmockStrategy(),
    "harmony": _HarmonyAppmockStrategy(),
}


def _current_strategy() -> _AppmockDeviceStrategy:
    platform = get_app_descriptor().platform
    strategy = _STRATEGIES.get(platform)
    if strategy is None:
        raise RuntimeError(f"AppMock 设备端开关不支持平台: {platform}")
    return strategy


def check_appmock_sdk_enabled() -> bool:
    """查询设备端 AppMock SDK 是否已启用（读设备本地真实状态）。

    语义是"**设备端真实开关状态**"，不是"能不能用"：不可确认平台
    （`can_verify_appmock_state=False`，如鸿蒙）恒返回 False，表达的是"查不到"
    而非"没开"。只有必须知道真实状态才能决策的地方才可用它——目前唯一合法
    消费者是 `login/steps.py::EnableAppMock`（据此选择「清数据 + 预授权」分支）。
    业务层的前置判定请改用 `appmock_ready()`（架构守卫规则 20 强制）。
    """
    return _current_strategy().check_sdk_enabled()


def appmock_ready() -> bool:
    """业务层语义入口：本次运行可否把 AppMock 视为"已就绪"。

    它回答的是业务层（登录动作等）真正关心的问题——"能不能用"，与
    `check_appmock_sdk_enabled`（设备端真实状态、不可确认平台恒 False）是
    **两个不同的问题**，不可混用：

      · 平台差异的唯一声明点是 `PlatformOps.can_verify_appmock_state`；
      · 不可确认平台：`EnableAppMock` 已负责下发（并在该分支内完成清数据 +
        预授权），**已下发即视为就绪**；
      · 可确认平台：以设备端真实状态为准。

    在业务层直接消费 `check_appmock_sdk_enabled`，等于把"平台是否可确认"这条
    平台差异以隐式分支的形式带进业务层（鸿蒙必然恒失败），故由架构守卫规则 20
    禁止。
    """
    from shared.capabilities import CAP_APP_MOCK_STATE, CapabilityState, state_of

    declared = getattr(get_platform_ops(), "can_verify_appmock_state", True)
    # 能力闸：实测 unavailable（无降级路径）→ 直接判定未就绪；
    # 其余情况按"声明"决定是否需要真查询（探针未跑时 state_of 回落声明值）。
    if state_of(CAP_APP_MOCK_STATE, declared=declared) is CapabilityState.UNAVAILABLE:
        return False
    if not declared:
        return True
    return check_appmock_sdk_enabled()


def appmock_enable(mis: str = None, verify: bool = True) -> bool:
    """开启设备端 AppMock 总开关。

    MIS 自动从 intake（信息收集结果）/ 环境变量 / flow-context 解析，
    调用方无需传参。

    verify=True 时在下发成功后查询设备端真实状态做二次确认（HarmonyOS 无法
    确认，见 _HarmonyAppmockStrategy.check_sdk_enabled）。
    """
    mis = resolve_mock_domain(mis)
    if not mis:
        print("APPMOCK ENABLE: 无法确定当前用户 MIS 号")
        return False
    return _current_strategy().enable(mis, verify)


def appmock_disable() -> bool:
    """关闭设备端 AppMock 总开关。"""
    return _current_strategy().disable()
