#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HarmonyOS 能力实测（`device setup` 跑一次）。

四条实测结论都来自真实故障：
  · `atm perm` **子命令不存在** → 预授权不可用（历史：每轮 stderr 噪音 + "✅ 已预授予"假成功）；
  · `uitest dumpLayout` 可能结构异常 / 被系统弹窗或 IME 抢占窗口 → 采集间歇不可用；
  · 登录页**几乎不暴露 resource-id**（实测仅 normalTextInput/navRoot/ffpRoot）→ 定位须走角色/文案；
  · AppMock enable 是**单向 scheme**、无状态查询通道 → 只能"已下发不可确认"（有降级路径）。
"""
from shared.capabilities import (
    CAP_APP_MOCK_STATE, CAP_FOREGROUND_QUERY, CAP_IME_CONTROL, CAP_RESOURCE_ID,
    CAP_RUNTIME_GRANT, CAP_VIEW_TREE_DUMP,
    CapabilityReport, CapabilityState,
)

from devices.capabilities import CapabilityProber, probe_view_tree


class PlatformCapabilityProber(CapabilityProber):
    platform = "harmony"

    def probe(self, ops, package: str) -> CapabilityReport:
        report = CapabilityReport(platform=self.platform)
        self._probe_view_tree(ops, report)
        self._probe_runtime_grant(ops, report)
        self._probe_foreground(ops, report)
        self._probe_ime(ops, report)
        # 结构性不可确认：不是"坏"，而是"没有查询通道"，上层走"已下发 + 清数据/预授权"降级
        report.set(CAP_APP_MOCK_STATE, CapabilityState.DEGRADED,
                   "无 AppMock 状态查询通道（EnableAppMock 走已下发 + 清数据/预授权降级）")
        return report

    # ── 各能力探测 ────────────────────────────────────────────────

    def _probe_view_tree(self, ops, report):
        ok, has_id, evidence = probe_view_tree(ops)
        report.set(CAP_VIEW_TREE_DUMP,
                   CapabilityState.AVAILABLE if ok else CapabilityState.DEGRADED, evidence)
        report.set(CAP_RESOURCE_ID,
                   CapabilityState.AVAILABLE if has_id else CapabilityState.DEGRADED,
                   evidence if has_id else "无 resource-id（定位须走角色/文案，见 PageSpec）")

    def _probe_runtime_grant(self, ops, report):
        """`atm` 是否支持 `perm` 子命令（鸿蒙预授权的唯一通道）。"""
        try:
            r = ops.shell("atm", "help")
        except Exception as e:                           # noqa: BLE001 - 探测失败即结论
            report.set(CAP_RUNTIME_GRANT, CapabilityState.DEGRADED, f"atm help 异常: {str(e)[:100]}")
            return
        out = f"{getattr(r, 'stdout', '') or ''}{getattr(r, 'stderr', '') or ''}"
        if "perm" in out:
            report.set(CAP_RUNTIME_GRANT, CapabilityState.AVAILABLE, "atm 支持 perm 子命令")
        else:
            report.set(CAP_RUNTIME_GRANT, CapabilityState.DEGRADED,
                       "atm 无 perm 子命令（预授权不可用 → 由弹窗澄清降级）")

    def _probe_foreground(self, ops, report):
        try:
            line = ops.check_foreground() or ""
        except Exception as e:                           # noqa: BLE001
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.DEGRADED, f"焦点查询异常: {str(e)[:100]}")
            return
        if line:
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.AVAILABLE, f"焦点串: {line[:80]}")
        else:
            report.set(CAP_FOREGROUND_QUERY, CapabilityState.DEGRADED,
                       "焦点串为空（无法判定前台，须按内容判定）")

    def _probe_ime(self, ops, report):
        """`uitest uiInput` 是否提供 keyEvent（收起输入法的唯一手段）。"""
        try:
            r = ops.shell("uitest", "uiInput", "help")
        except Exception as e:                           # noqa: BLE001
            report.set(CAP_IME_CONTROL, CapabilityState.DEGRADED, f"uitest help 异常: {str(e)[:100]}")
            return
        out = f"{getattr(r, 'stdout', '') or ''}{getattr(r, 'stderr', '') or ''}"
        if "keyEvent" in out:
            report.set(CAP_IME_CONTROL, CapabilityState.AVAILABLE, "uitest uiInput 支持 keyEvent（可收 IME）")
        else:
            report.set(CAP_IME_CONTROL, CapabilityState.DEGRADED, "未见 keyEvent（IME 不可编程收起）")
