#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备能力探测（策略注册表 + 落盘编排）—— `device setup` 阶段跑一次。

【分工】三层，各自单一职责：
  · `shared/capabilities.py`  数据模型（CapabilityState / CapabilityReport）+ 落盘 + **消费入口**
  · 本模块                     `CapabilityProber` 契约 + **按 platform 的策略注册表** + `probe_and_persist()`
  · `devices/<platform>/capabilities.py`  各平台**实测**实现（下发设备命令，属平台专属能力）

【为什么探测放平台层】实测要下发设备命令（`atm help` / `uitest dumpLayout` / `content call`），
天然是平台专属逻辑；框架层只做"分发 + 落盘 + 消费"，新增平台 = 写一个 Prober 并在
`_PROBER_MODULES` 加一行。

【分层】本模块属 `devices`，只依赖 `shared` 与 `devices`（平台实现在 devices 内）。
"""
import importlib

from shared.capabilities import (
    ALL_CAPABILITIES, CapabilityReport, CapabilityState, save_report,
)


class CapabilityProber:
    """能力探测器契约：一次探测产出一份 `CapabilityReport`。

    约定（重要）：**探测必须只读、幂等、可重入** —— 它跑在 `device setup` 里，
    失败不得中断 setup（未探测到的能力会被消费入口按"声明值"回落）。
    """

    platform = ""

    def probe(self, ops, package: str) -> CapabilityReport:  # pragma: no cover - 契约
        raise NotImplementedError


class UnregisteredProber(CapabilityProber):
    """未注册平台的保守兜底：全部 `degraded`（不阻断，也不假装可用）。"""

    platform = "unknown"

    def probe(self, ops, package: str) -> CapabilityReport:
        report = CapabilityReport(platform=self.platform)
        for cap in ALL_CAPABILITIES:
            report.set(cap, CapabilityState.DEGRADED, "未注册平台探测实现")
        return report


# platform → 探测实现模块（唯一事实来源；新增平台加一行）
_PROBER_MODULES = {
    "android": "devices.android.capabilities",
    "harmony": "devices.harmony.capabilities",
}


def get_prober(platform: str) -> CapabilityProber:
    """按 platform 取探测器；未注册/导入失败 → 保守兜底（不阻断 setup）。"""
    module_path = _PROBER_MODULES.get(platform)
    if not module_path:
        return UnregisteredProber()
    try:
        module = importlib.import_module(module_path)
        return module.PlatformCapabilityProber()
    except Exception:                                    # noqa: BLE001 - 探测实现缺失不得阻断
        return UnregisteredProber()


def probe_and_persist(platform: str, ops, package: str, task_id: str = None) -> CapabilityReport:
    """探测并落盘 `capabilities.json`；返回报告（供 device setup 打印摘要）。"""
    report = get_prober(platform).probe(ops, package)
    save_report(report, task_id)
    return report


# ═══════════════════════════════════════════════════════════════════
# 跨平台共用探测片段（只读、幂等；各平台 ops 已按平台分派）
# ═══════════════════════════════════════════════════════════════════

def probe_view_tree(ops, timeout: int = 20):
    """采集一次视图树，返回 `(dump_ok, has_resource_id, evidence)`。

    一次采集同时给出两条结论（避免重复 dump）：
      · 能否采集视图树（`dumpLayout` / `uiautomator` 是否可用、结构是否可解析）；
      · 该平台是否暴露 resource-id（决定上层用 id 定位还是角色/文案定位）。
    """
    import os
    import re
    import tempfile

    path = os.path.join(tempfile.gettempdir(), "_ai_uitest_cap_probe_tree.json")
    try:
        ops.inspect_tree(path, timeout=timeout)
    except Exception as e:                               # noqa: BLE001 - 探测失败即结论
        return False, False, f"采集异常: {str(e)[:120]}"
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return False, False, "采集无输出（页面未注入 dump 能力，或被系统弹窗/IME 遮挡）"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if '"attributes"' not in text:
        return False, False, "采集输出缺少 attributes（设备端实现差异）"
    has_id = bool(re.search(r'"(?:m_id|id|resourceId)"\s*:\s*"[^"]+"', text))
    return True, has_id, f"采集成功（{len(text)}B），resource-id={'有' if has_id else '无'}"


__all__ = [
    "CapabilityProber", "UnregisteredProber", "get_prober",
    "probe_and_persist", "probe_view_tree",
]
