#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TextPresentStrategy — 文本出现断言策略。

一次取证完成全部判定（只采集一次视图树）：
  T1   — 当前位置视图树精确匹配（含视口外节点）：命中则 pass / exact
  T1.5 — 同一棵树里的唯一子串形态：语义等价，pass / semantic
  T2   — 未命中：复用这次采到的视图树落元素目录，交 AI 语义确认；
         同时把滚动补看截图（当前屏 + 向下 1 屏）一并交给 AI
"""

from __future__ import annotations
import os
from aitest.execution.assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from aitest.execution.assertions.ui.pipeline.sweep import (
    safe_sweep, sweep_evidence,
)
from aitest.execution.screen.tree_index import dump_index


class TextPresentStrategy(BaseAssertionStrategy):
    """文本出现断言（一次整页取证 → 程序化命中 / AI 语义降级）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        # ── Phase 1: 当前位置取证（一次采集匹配 → 未命中向下补看 1 屏截图）─────────
        # 同一步内后续断言直接复用第一次的采集结果与截图，不重复滚动/采集。
        sweep = safe_sweep({spec.id: spec.expect}, case_ws=context.case_ws,
                           tag=spec.id, step_key=context.sid)

        hit = (sweep.get("hits") or {}).get(spec.id)
        if hit:
            # 命中口径：L0/L1 精确 → exact；唯一子串 → semantic
            if hit.get("verdict") == "exact":
                result = AssertionResult.pass_exact(
                    spec=spec,
                    matched_text=hit.get("matched_text", spec.expect),
                    match_level=hit.get("match_level", -1),
                    matched_node=hit.get("node"),
                )
            else:
                result = AssertionResult.pass_semantic(
                    spec=spec,
                    matched_text=hit.get("matched_text", spec.expect),
                    match_level=hit.get("match_level", -1),
                    matched_node=hit.get("node"),
                )
            result.evidence["scroll_sweep"] = sweep_evidence(sweep, spec.id)
            return result

        # ── Phase 2: AI 语义降级 ───────────────────────────────────────
        # 复用这次采到的视图树落元素目录，不再额外采集一次。
        diag_dir = os.path.join(context.case_ws, "diagnostics") if context.case_ws else None
        nodes = sweep.get("nodes") or None
        targets, sidecar_path = dump_index(
            context.sid, "assert=present", nodes=nodes, diag_dir=diag_dir, wait_sec=3,
        )
        if not targets.get("available"):
            return AssertionResult.fail_unavailable(spec)

        result = AssertionResult.pending_semantic(
            spec=spec,
            sidecar=sidecar_path,
            screenshot=context.screenshot_path,
        )
        # 已扫过整页的结论随证据交给 AI：目录里也没有 → 可据实判不存在
        sweep_info = sweep_evidence(sweep)
        if sweep_info:
            result.evidence["scroll_sweep"] = sweep_info
        return result
