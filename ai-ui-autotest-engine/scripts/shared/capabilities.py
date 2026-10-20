#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设备能力闸 —— 「声明 × 实测 × 三态」的统一模型（跨层纯数据 + 消费入口）。

【为什么需要它】
平台差异过去只在少数地方用**静态能力位**声明（如 `PlatformOps.can_verify_appmock_state`），
而"声明 ≠ 实际可用"在鸿蒙上反复咬人：`atm perm` 子命令不存在（预授权形同虚设）、
`uitest dumpLayout` 间歇性结构异常、系统 IME 抢走 foreground/dump 窗口……
缺少"声明 → 探测 → 闸门"这一环时，只能靠各处 `try/except + 日志降级`，
代价是**每轮 stderr 噪音**与**假成功**（例：`✅ 运行时权限已预授予` 实际 0/2）。

【三层分工】本模块负责第 1、3 层：
  1. 数据模型 + 消费入口（本模块）：`CapabilityState` /
     `CapabilityReport` / `state_of()`，并负责 `capabilities.json` 读写；
  2. 探测实现：`devices/capabilities.py`（策略注册表）+ `devices/<platform>/capabilities.py`
     （平台实测；只在 `device setup` 跑一次并落盘）；
  3. 闸门：调用方用 `state_of()` 判定，**不再写** `getattr(ops, "can_*", True)`。

【分层约束】本模块属 `shared`，只允许依赖 `shared`：
  · 不 import `devices`（探测实现由 `devices` 侧主动调用本模块）；
  · `platform` 层（如 AppMock 设备端）也能安全使用 `state_of()` —— 这是把
    "平台差异的唯一声明点"从各处 `can_*` 收敛到一张表的关键。

【三态语义】对齐"不把已下发当已达成"：
  · `available`   声明支持且实测通过 → 可依赖；
  · `degraded`    实测不支持/间歇，但**有可用降级路径**（如鸿蒙预授权 → 靠弹窗澄清），
                  调用方可继续但**不得计入成功**；
  · `unavailable` 声明不支持或实测失败且无降级路径 → 硬依赖场景应快速失败。
"""
from enum import Enum

from shared import paths
from shared.json_utils import read_json, write_json_atomic


# ═══════════════════════════════════════════════════════════════════
# 能力标识（唯一事实来源：新增能力 = 在这里加一个常量）
# ═══════════════════════════════════════════════════════════════════

CAP_APP_MOCK_STATE = "appmock_state"        # 能否查 AppMock 真实开关状态
CAP_RUNTIME_GRANT = "runtime_grant"         # 能否预授权运行时权限（atm perm / pm grant）
CAP_FOREGROUND_QUERY = "foreground_query"   # 焦点/前台通道是否可用
CAP_VIEW_TREE_DUMP = "view_tree_dump"       # 视图树采集是否可用（dumpLayout / uiautomator）
CAP_RESOURCE_ID = "resource_id"             # 视图树是否暴露 resource-id
CAP_IME_CONTROL = "ime_control"             # 能否编程控制输入法（收起/切换）

ALL_CAPABILITIES = (
    CAP_APP_MOCK_STATE, CAP_RUNTIME_GRANT, CAP_FOREGROUND_QUERY,
    CAP_VIEW_TREE_DUMP, CAP_RESOURCE_ID, CAP_IME_CONTROL,
)


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

    @property
    def ok(self) -> bool:
        """可依赖（available/degraded 都允许继续，但 degraded 不计入成功）。"""
        return self is not CapabilityState.UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════
# 报告（探测结果的载体，可序列化到 capabilities.json）
# ═══════════════════════════════════════════════════════════════════

class CapabilityReport:
    """一次探测的结论：能力 → (state, evidence)。"""

    def __init__(self, platform: str = "", entries=None):
        self.platform = platform
        self._entries = dict(entries or {})   # cap -> {"state": str, "evidence": str}

    def set(self, cap: str, state: CapabilityState, evidence: str = ""):
        self._entries[cap] = {"state": state.value, "evidence": str(evidence)[:300]}
        return self

    def state(self, cap: str):
        """返回 CapabilityState 或 None（未探测）。"""
        e = self._entries.get(cap)
        if not e:
            return None
        try:
            return CapabilityState(e.get("state"))
        except ValueError:
            return None

    def evidence(self, cap: str) -> str:
        return (self._entries.get(cap) or {}).get("evidence", "")

    def to_dict(self) -> dict:
        return {"platform": self.platform, "capabilities": dict(self._entries)}

    @classmethod
    def from_dict(cls, data: dict):
        return cls(platform=(data or {}).get("platform", ""),
                   entries=(data or {}).get("capabilities") or {})

    def summary_lines(self):
        """人类可读摘要（device setup 打印 / 排查用）。"""
        out = []
        for cap in ALL_CAPABILITIES:
            st = self.state(cap)
            if st is None:
                continue
            out.append(f"{cap}={st.value}({self.evidence(cap)})")
        return out


# ═══════════════════════════════════════════════════════════════════
# 持久化（workspace 级；无 workspace 时静默不落盘）
# ═══════════════════════════════════════════════════════════════════

def save_report(report: CapabilityReport, task_id: str = None) -> bool:
    try:
        write_json_atomic(paths.capabilities_path(task_id), report.to_dict())
        return True
    except Exception:      # noqa: BLE001 — 落盘失败不得打断 device setup
        return False


def load_report(task_id: str = None):
    """读取本 workspace 的能力报告；无报告/不可读返回 None。"""
    try:
        data = read_json(paths.capabilities_path(task_id), default=None)
    except Exception:      # noqa: BLE001 — 读失败按"未探测"处理
        return None
    if not isinstance(data, dict):
        return None
    return CapabilityReport.from_dict(data)


# ═══════════════════════════════════════════════════════════════════
# 消费入口（闸门）—— 业务层唯一用法
# ═══════════════════════════════════════════════════════════════════

def state_of(cap: str, declared: bool = True) -> CapabilityState:
    """取能力状态：**实测优先，缺省回落到声明**。

    Args:
        cap:      能力标识（CAP_*）
        declared: 该平台"声明"是否支持；无实测报告时以其为准
                  （探针未跑时不误判不可用，保持历史行为）
    """
    report = load_report()
    if report is not None:
        st = report.state(cap)
        if st is not None:
            return st
    return CapabilityState.AVAILABLE if declared else CapabilityState.UNAVAILABLE


__all__ = [
    "CapabilityState", "CapabilityReport",
    "CAP_APP_MOCK_STATE", "CAP_RUNTIME_GRANT", "CAP_FOREGROUND_QUERY",
    "CAP_VIEW_TREE_DUMP", "CAP_RESOURCE_ID", "CAP_IME_CONTROL",
    "ALL_CAPABILITIES",
    "save_report", "load_report", "state_of",
]
