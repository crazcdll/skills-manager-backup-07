#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AppMock 设备端开关 —— enable / disable / SDK 状态检查。

Android 和 HarmonyOS 走完全独立的两套实现（非简单的参数/文案差异，而是
整条下发链路不同），因此不用内联 if/else 分叉，而是各自实现一个完整的
_AppmockDeviceStrategy 并按 platform 注册分发（_STRATEGIES），新增平台
支持时只需实现并注册一个新策略，不需要改动本文件其余逻辑或调用方
（appmock_enable/appmock_disable/check_appmock_sdk_enabled 三个对外接口
签名不变）。

Android: 优先 imeituan CLI inject 命令，SSO 失败时 fallback 到 ops.content_call。

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
"""
from abc import ABC, abstractmethod

from infra.imeituan_cli import imeituan_exec
from core.util.case_utils import set_current_user_mis, resolve_mis
from context import get_app_descriptor, get_platform_ops
from mock.appmock_core import _cli_out, _is_sso_failure, _device_content_call
from core.errors import AutotestError, soft_fail


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
    """Android：ContentProvider 直连（adb content call）优先，imeituan CLI 作为备选。

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
        # 优先走 ContentProvider 直连（adb content call），不依赖 Mpium WebSocket
        # 在 force-stop 冷重启后依然可靠，是 Android 场景下的最佳方案
        print(f"APPMOCK ENABLE: 通过 ContentProvider 直连启用 AppMock (user={mis})...")
        try:
            ok, out = _device_content_call("enable", mis)
            if ok:
                print(f"APPMOCK ENABLE OK (content call): user={mis}")
                set_current_user_mis(mis)
            else:
                print(f"APPMOCK ENABLE content call FAIL: {out}")
                # ContentProvider 直连失败时，兜底走 imeituan CLI
                print("APPMOCK ENABLE: 兜底走 imeituan CLI inject...")
                r = imeituan_exec(["inject", "mock", "enable", "--user", mis])
                out = _cli_out(r)
                if r.returncode != 0:
                    print(f"APPMOCK ENABLE FAIL: {out}")
                    return False
                set_current_user_mis(mis)
        except Exception as e:
            print(f"APPMOCK ENABLE content call 异常: {e}")
            return False

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
        # 优先走 ContentProvider 直连
        try:
            ok, fb_out = _device_content_call("disable")
            if ok:
                print(f"APPMOCK DISABLE OK (content call)")
                return True
            print(f"APPMOCK DISABLE content call FAIL: {fb_out}")
        except AutotestError as e:
            # 直连不可用时降级走 CLI，属可容忍失败，但需留痕
            soft_fail("device", "APPMOCK_CONTENT_DISABLE_FAILED", e)
        # 兜底走 imeituan CLI
        r = imeituan_exec(["inject", "mock", "disable"])
        out = _cli_out(r)
        if r.returncode == 0:
            print(f"APPMOCK DISABLE OK")
            return True
        print(f"APPMOCK DISABLE FAIL: {out}")
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
        set_current_user_mis(mis)
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
    """查询设备端 AppMock SDK 是否已启用（读设备本地真实状态）。"""
    return _current_strategy().check_sdk_enabled()


def appmock_enable(mis: str = None, verify: bool = True) -> bool:
    """开启设备端 AppMock 总开关。

    MIS 自动从 env_answers.json / 环境变量 / flow-context 解析，
    调用方无需传参。

    verify=True 时在下发成功后查询设备端真实状态做二次确认（HarmonyOS 无法
    确认，见 _HarmonyAppmockStrategy.check_sdk_enabled）。
    """
    mis = resolve_mis(mis)
    if not mis:
        print("APPMOCK ENABLE: 无法确定当前用户 MIS 号")
        return False
    return _current_strategy().enable(mis, verify)


def appmock_disable() -> bool:
    """关闭设备端 AppMock 总开关。"""
    return _current_strategy().disable()
