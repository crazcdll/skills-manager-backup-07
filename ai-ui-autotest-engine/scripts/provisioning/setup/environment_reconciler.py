#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境澄清唯一入口（EnvironmentReconciler）：前台就绪 + 遮挡弹窗消除，一处编排。

【为什么需要唯一入口】澄清是"让后续判定与取证落在干净页面上"的前置条件。历史上它被写在
三个地方（冷重启内部、L2 前置步骤、L3 认证动作自清），于是出现两类回退：

  1. **时机错位**：L2 的澄清排在最后一次冷重启**之前**。系统弹窗（通知/定位引导）是在
     App 启动**之后**才出现的，最后一次重启后新起的那批没人管 —— 结果"澄清过了"仍被
     挡住（实测：登录页被「定位服务引导」覆盖，元素定位与登录态判定双失败）。
  2. **语义分叉**：各处各写一份等待窗口与返回语义（有的返回 bool、有的返回 None），
     失败处理与日志口径不一致，排查时无法按阶段过滤。

因此固化两条契约（由 `dev/check_architecture.py` 规则 21/22/23 守卫）：

  · **唯一入口**：业务层要澄清环境只能调 `reconcile_environment()`；执行器
    `devices.popup.dismiss_popups` 是实现细节，只允许本模块与 `devices` 层自身引用
    （词表在 `platform/popup/patterns.py`，平台无关）。
  · **时机**：L2 前置管线里，澄清必须是**所有重启类步骤之后**的最后一步
    （见 `provisioning/setup/login/registry.py`），即"最后一次设备态变更"之后再澄清。
L3 认证动作可在动作期间**复核**同一入口（弹窗可能到动作期间才出现），但必须复用
本入口，不得自建第二套实现。

另一个入口：`reconcile_system_onboarding()` —— **场景限定**版，只收敛系统层引导
（典型：系统输入法首启向导）。它在"动作期间系统引导抢走前台导致控件定位失败"的
场景里使用：不等待弹窗出现（它已在屏上）、不启用通用关闭兜底（背景是业务正常页面）。


【分层】本模块属 `provisioning`：只向下依赖 `devices`（执行器）与同层生命周期原语。
"""
from shared.context import get_app_descriptor


class ReconcileResult:
    """澄清结果（终态三态与执行器 `DismissResult.final_state` 对齐）。

    foreground_ok  False 表示"前台就绪等待/拉回未成功"——不阻断澄清，但调用方据此
                  决定是否需要额外的等待（历史上这类信息被各处各自 print 后丢弃）。
    """

    __slots__ = ("label", "foreground_ok", "dismissed", "final_state")

    def __init__(self, *, label, foreground_ok=True, dismissed=(), final_state="none-found"):
        self.label = label
        self.foreground_ok = foreground_ok
        self.dismissed = list(dismissed)
        self.final_state = final_state

    @property
    def any_dismissed(self) -> bool:
        """本轮是否真的消除了弹窗（调用方据此决定是否复核判定）。"""
        return bool(self.dismissed)

    def __repr__(self):
        return (f"ReconcileResult(label={self.label!r}, foreground_ok={self.foreground_ok}, "
                f"dismissed={len(self.dismissed)}, final_state={self.final_state!r})")


def _ensure_foreground(timeout):
    """确保目标 App 在前台（委托生命周期原语，不重复实现前台判定语义）。"""
    from provisioning.setup.app_lifecycle import wait_app_foreground

    return wait_app_foreground(timeout=timeout)


def _dismiss_popups(wait_for_popup_ms, prefer_texts):
    """调唯一执行器消除弹窗，返回 (dismissed, final_state)。"""
    from devices.popup import dismiss_popups

    vr = dismiss_popups(prefer_texts=tuple(prefer_texts),
                        wait_for_popup_ms=wait_for_popup_ms)
    return list(vr.dismissed or ()), vr.final_state


def reconcile_environment(*, label="env", wait_for_popup_ms=0, prefer_texts=("同意",),
                          ensure_foreground=False, foreground_timeout=10):
    """**环境澄清唯一入口**：可选的前台就绪 + 消除遮挡弹窗（不重启）。

    Args:
        label: 日志前缀（`[<label>]`，便于按阶段排查）
        wait_for_popup_ms: 刚冷重启/首启场景下等待弹窗渲染出现的最长毫秒数（0=不等待）
        prefer_texts: 优先点击的文案（默认「同意」）
        ensure_foreground: 是否先确保 App 在前台（冷重启后 / 长等待后建议 True）
        foreground_timeout: 前台就绪等待上限（秒）

    Returns:
        ReconcileResult；**采集/点击过程中抛异常时返回 None**（沿用历史契约形状：
        调用方按"None = 未能澄清"处理，例如 `_cold_restart_app` 据此决定是否再冷启一次）。
    """
    app = get_app_descriptor()
    foreground_ok = True
    if ensure_foreground:
        try:
            foreground_ok = _ensure_foreground(foreground_timeout)
        except Exception as e:  # noqa: BLE001 —— 前台等待失败不阻断澄清
            foreground_ok = False
            print(f"[{label}] ⚠️ 前台就绪等待异常（{app.package_name}）: {e}")

    try:
        dismissed, final_state = _dismiss_popups(wait_for_popup_ms, prefer_texts)
    except Exception as e:  # noqa: BLE001 —— 澄清失败不阻断主流程（逐条判定仍会给出结论）
        print(f"[{label}] ⚠️ 弹窗澄清异常: {e}")
        return None

    if dismissed:
        names = "、".join(str(d.get("name") or d.get("kind")) for d in dismissed)
        print(f"[{label}] 环境澄清：已消除 {len(dismissed)} 个遮挡弹窗（{names}）")
    else:
        print(f"[{label}] 环境澄清：无遮挡弹窗（{final_state}）")
    return ReconcileResult(label=label, foreground_ok=foreground_ok,
                           dismissed=dismissed, final_state=final_state)


def reconcile_system_onboarding(*, label="onboarding", max_rounds=6):
    """收敛**系统层引导**（典型：系统输入法首启向导）—— 场景限定的唯一入口。

    与 `reconcile_environment` 的差异：不做前台就绪、不启用通用关闭兜底，只按
    `platform/popup/patterns.py` 的场景词表精确消除。用于"**动作期间**系统引导抢走
    前台、导致控件定位失败"的自愈（L3 认证动作复用本入口，不自建实现、也不写平台
    字面量——架构守卫规则 21/22）。

    Returns:
        ReconcileResult（`foreground_ok` 恒 True：本入口不做前台等待）；
        采集/点击异常时返回 None（与 `reconcile_environment` 契约一致）。
    """
    from devices.popup import resolve_system_onboarding

    try:
        vr = resolve_system_onboarding(max_rounds=max_rounds)
    except Exception as e:  # noqa: BLE001 —— 自愈失败不阻断主流程（仍交回原判定）
        print(f"[{label}] ⚠️ 系统引导收敛异常: {e}")
        return None

    dismissed = list(vr.dismissed or ())
    if dismissed:
        names = "、".join(str(d.get("name") or d.get("kind")) for d in dismissed)
        print(f"[{label}] 系统引导已收敛：{len(dismissed)} 步（{names}）")
    return ReconcileResult(label=label, foreground_ok=True,
                           dismissed=dismissed, final_state=vr.final_state)


__all__ = ["ReconcileResult", "reconcile_environment", "reconcile_system_onboarding"]
