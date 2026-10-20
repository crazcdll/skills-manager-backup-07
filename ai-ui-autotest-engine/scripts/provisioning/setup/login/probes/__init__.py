#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L4 登录态探针：按 platform 判定"登录是否真的成功"。

【为什么按平台注册】不同平台的"登录态"可信来源不同：
  · 前台判定型（android / ios / 未注册平台共用）：App 在前台即视为登录成功
    （环境每次重建，凭证登录另由「读图确认」兜底）→ `ForegroundProbe`
  · HarmonyOS：同一 Ability 内路由切换不改窗口标识，"前台"与"已登录"脱钩，
    需要真登录态 → `HarmonyMpiumProbe`（`imeituan control auth status`）

【契约】`authoritative_for_password` 决定是否对凭证登录做程序化判定：
  · False（Android）：凭证登录以「读图确认」为判据，不做程序化探测（也不引入额外副作用）
  · True （Harmony）：凭证登录同样需要真登录态，否则失败会被静默放过

`dev/check_architecture.py::check_login_android_probe_frozen`（规则 16）
锁定 Android 探针的判定语义（仍走前台判定，不得换成真登录态探针）。
"""
from abc import ABC, abstractmethod
from typing import Dict

from provisioning.setup.login.policy import ProbeResult


class LoginStateProbe(ABC):
    """登录态判定契约。"""

    #: 是否对「凭证登录(password)」也做程序化判定。
    #:
    #: 契约（由规则 16 锁定 Android 侧）：
    #:   · False（Android 探针）：凭证登录的判据是「读图确认」
    #:     （`[NEEDS_VISUAL_CHECK]`）—— 因此不对凭证登录做程序化判定，
    #:     也不为此引入额外副作用（如自动拉起 App）。
    #:   · 鸿蒙没有「前台≈已登录」的代理关系，凭证登录**需要**真登录态判定，
    #:     否则登录失败会被静默放过 —— 因此鸿蒙探针对凭证登录是权威的。
    authoritative_for_password: bool = True

    @abstractmethod
    def probe(self) -> ProbeResult:
        """返回登录态判定结果（不发起登录）。"""

    @property
    def name(self) -> str:
        return type(self).__name__


class ForegroundProbe(LoginStateProbe):
    """前台判定型探针（android / ios / 未注册平台共用）：前台判定 + 读图证据。

    `check_login_state` / `login_go_home`（`probes/android.py`）本身就是**平台无关**的
    （只经 `AppDescriptor.describe_foreground_state` + `PlatformOps`），因此 iOS 等
    "无真登录态通道"的平台直接复用本探针，无需另写一份。

      · qahome / noop → 调 `check_login_state()`（不就判失败）
      · password      → 不调用（`authoritative_for_password=False`）
    """

    authoritative_for_password = False

    def probe(self) -> ProbeResult:
        from provisioning.setup.login.probes.android import check_login_state

        ok, detail = check_login_state()
        return ProbeResult(
            logged_in=bool(ok),
            detail=detail,
            # 结论来自"是否在前台"，不等于真登录态
            # （凭证登录另由读图确认兜底，故标记为不可完全确认）
            reliable=False,
        )


class HarmonyMpiumProbe(LoginStateProbe):
    """HarmonyOS：真登录态 —— `imeituan control auth status`（Mpium AppInfo.get）。

    该通道三端统一（Android 也可用），但本探针只在鸿蒙注册，
    以保证 Android 侧行为不变（F-1）。
    鸿蒙没有「前台≈已登录」的代理关系，故对凭证登录也是权威判据。
    """

    authoritative_for_password = True

    def probe(self) -> ProbeResult:
        import json

        from devices.toolchain.imeituan_cli import imeituan_exec

        try:
            r = imeituan_exec(["control", "auth", "status", "--format", "json"], timeout=60)
            payload = json.loads((r.stdout or "").strip() or "{}")
        except Exception as e:  # noqa: BLE001 — 探针失败不得打断主流程
            return ProbeResult(logged_in=False, detail=f"auth status 查询异常: {e}", reliable=False)

        if payload.get("code") != 0:
            msg = (payload.get("error") or {}).get("message", "")
            return ProbeResult(logged_in=False,
                               detail=f"auth status 无响应: {msg[:160]}",
                               reliable=False)

        data = payload.get("data") or {}
        logged_in = bool(data.get("loggedIn"))
        user_id = str(data.get("userId") or "")
        return ProbeResult(
            logged_in=logged_in,
            detail=f"channel={data.get('channel', '')} status={data.get('status', '')}",
            user_id=user_id,
            reliable=True,
        )


# platform → 探针实例。唯一事实来源，新增平台在此登记一行。
# 未在此登记的平台会回落到前台探针（见 get_login_state_probe）——不静默借用他平台语义；
# 规则 28 会要求 SUPPORTED_DEVICE_COMBINATIONS 里的 platform 必须在此显式登记。
LOGIN_STATE_PROBES: Dict[str, LoginStateProbe] = {
    "android": ForegroundProbe(),
    "harmony": HarmonyMpiumProbe(),
    # iOS：与 android 同为「无真登录态通道」—— 先以前台判定（bundleId）为准；
    # iOS 云模拟器接入后若提供真登录态通道，再换专用探针。
    "ios": ForegroundProbe(),
}


def get_login_state_probe(platform: str) -> LoginStateProbe:
    """按 platform 取登录态探针；未注册平台回退到前台探针（保守，不误判成功）。"""
    return LOGIN_STATE_PROBES.get(platform) or ForegroundProbe()


__all__ = [
    "LoginStateProbe",
    "ForegroundProbe",
    "HarmonyMpiumProbe",
    "LOGIN_STATE_PROBES",
    "get_login_state_probe",
]
