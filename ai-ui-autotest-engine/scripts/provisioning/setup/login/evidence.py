#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录阶段的**可观测性**（旁路）：截图 / 时间线事件 / 视图树快照。

登录证据的**唯一写入口**；L3 只表达意图（`shot` / `event` / `tree`），不关心落盘布局。
复用既有机制：截图→`assertion_utils._try_shoot_for_diagnosis`；事件→`runtime_audit.append_event`
（写 run 的 `audit/run-events.jsonl`，与 `environment.prepared` 等同一条时间线）；
视图树→case 的 `diagnostics/`（仅异常路径，避免正常路径产物膨胀）。
旁路语义：任何入口失败都只降级为日志，**绝不改变登录判定**。
"""
import os
from typing import Iterable, Optional

from shared.case_utils import active_case_diagnostics_dir, resolve_case_path
from shared.json_utils import write_json_atomic
from shared.observability.runtime_audit import append_event
from shared.paths import get_active_run

__all__ = ["shot", "event", "tree"]


def shot(tag: str) -> Optional[str]:
    """截当前屏幕归档为登录证据图；失败返回 None（不阻断登录）。

    tag 会进入文件名（形如 `case_01_diag_login_a2_stuck_code_rejected_17.png`），
    因此应保持短小且语义化（≤20 字符，超长会被截断）。
    """
    try:
        from execution.steps.assertion_utils import _try_shoot_for_diagnosis
        return _try_shoot_for_diagnosis(f"login_{tag}")
    except Exception as e:  # noqa: BLE001 —— 证据落盘失败不阻断主流程
        print(f"LOGIN-EVIDENCE: ⚠️ 截图失败（忽略）: {e}")
        return None


def event(name: str, **fields) -> None:
    """向 run 时间线追加一条事件（`audit/run-events.jsonl`）；失败仅记录日志。"""
    case_name = get_active_run()
    if not case_name:
        return
    try:
        append_event(resolve_case_path(case_name), name, {"source": "login", **fields})
    except Exception as e:  # noqa: BLE001 —— 时间线写失败不阻断主流程
        print(f"LOGIN-EVIDENCE: ⚠️ 事件落盘失败（忽略）{name}: {e}")


def tree(tag: str, nodes: Iterable[dict], extra: Optional[dict] = None) -> Optional[str]:
    """把视图树节点快照落盘到 case 的 `diagnostics/`（异常路径专用），返回路径或 None。

    失败诊断时**能回放当时的页面结构**——这是"验证码提交后卡住"这类问题唯一可复盘的
    现场（只有焦点窗口名无法回答"页面上到底有什么"）。
    """
    try:
        diag_dir = active_case_diagnostics_dir()
        if not diag_dir:
            return None
        path = os.path.join(diag_dir, f"login_{tag}.tree.json")
        write_json_atomic(path, {"tag": tag, **(extra or {}), "nodes": list(nodes or [])})
        return path
    except Exception as e:  # noqa: BLE001 —— 快照失败不阻断主流程
        print(f"LOGIN-EVIDENCE: ⚠️ 视图树快照失败（忽略）: {e}")
        return None
