#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android 能力实测（`device setup` 跑一次）。

与 Harmony 的对照（这份差异正是"能力闸"要显式化的东西）：
  · AppMock 状态：`content call getStatus` **可确认**（鸿蒙无查询通道）；
  · 预授权：`pm grant` 可用（鸿蒙 `atm perm` 不存在）；
  · resource-id：视图树**暴露** m_id（鸿蒙几乎不暴露）；
  · IME：ADBKeyboard 广播输入（无可见键盘，不抢窗口）。
"""
from shared.capabilities import (
    CAP_APP_MOCK_STATE, CAP_FOREGROUND_QUERY, CAP_IME_CONTROL, CAP_RESOURCE_ID,
    CAP_RUNTIME_GRANT, CAP_VIEW_TREE_DUMP,
    CapabilityReport, CapabilityState,
)

from devices.capabilities import CapabilityProber, probe_view_tree


class PlatformCapabilityProber(CapabilityProber):
    platform = "android"

    def probe(self, ops, package: str) -> CapabilityReport:
        report = CapabilityReport(platform=self.platform)
        self._probe_view_tree(ops, report)
        self._probe_appmock_state(ops, report)
        self._probe_runtime_grant(ops, report)
        self._probe_foreground(ops, report)
        self._probe_ime(ops, report)
        return report

    # ── 各能力探测 ────────────────────────────────────────────────

    def _probe_view_tree(self, ops, report):
        ok, has_id, evidence = probe_view_tree(ops)
        report.set(CAP_VIEW_TREE_DUMP,
                   CapabilityState.AVAILABLE if ok else CapabilityState.DEGRADED, evidence)
        report.set(CAP_RESOURCE_ID,
                   CapabilityState.AVAILABLE if has_id else CapabilityState.DEGRADED, evidence)

    def _probe_appmock_state(self, ops, report):
        """AppMock 真实状态可确认性（Android 走 ContentProvider）。"""
        try:
            from platform.appmock.client import _device_content_call
            ok, out = _device_content_call("getStatus")
        except Exception as e:                           # noqa: BLE001 - 探测失败即结论
            report.set(CAP_APP_MOCK_STATE, CapabilityState.DEGRADED, f"getStatus 异常: {str(e)[:100]}")
            return
        if ok:
            report.set(CAP_APP_MOCK_STATE, CapabilityState.AVAILABLE,
                       f"ContentProvider getStatus 可用（{str(out)[:60]}）")
        else:
            report.set(CAP_APP_MOCK_STATE, CapabilityState.DEGRADED,
                       "getStatus 无响应（按「已下发不可确认」降级）")

    def _probe_runtime_grant(self, ops, report):
        """`pm` 是否提供 `grant`（Android 预授权通道）。"""
        try:
            r = ops.shell("pm")
        except Exception as e:                           # noqa: BLE001
            report.set(CAP_RUNTIME_GRANT, CapabilityState.DEGRADED, f"pm 探测异常: {str(e)[:100]}")
            return
        out = f"{getattr(r, 'stdout', '') or ''}{getattr(r, 'stderr', '') or ''}"
        if "grant" in out:
            report.set(CAP_RUNTIME_GRANT, CapabilityState.AVAILABLE, "pm 支持 grant")
        else:
            report.set(CAP_RUNTIME_GRANT, CapabilityState.DEGRADED, "pm 未见 grant（预授权不可用）")

    def _probe_foreground(self, ops, report):
        try:
            line = ops.check_foreground() or ""
        except Exception as e:                           # noqa: BLE001
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.DEGRADED, f"焦点查询异常: {str(e)[:100]}")
            return
        if line:
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.AVAILABLE, f"焦点串: {line[:80]}")
        else:
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.DEGRADED, "焦点串为空")

    def _probe_ime(self, ops, report):
        """ADBKeyboard 无界面输入法：CJK 输入依赖它（`supports_cjk_input` 声明）。"""
        if getattr(ops, "supports_cjk_input", False):
            report.set(CAP_IME_CONTROL, CapabilityState.AVAILABLE, "ADBKeyboard 广播输入（无可见键盘）")
        else:
            report.set(CAP_IME_CONTROL, CapabilityState.DEGRADED, "无无界面输入法（可能弹系统键盘）")
