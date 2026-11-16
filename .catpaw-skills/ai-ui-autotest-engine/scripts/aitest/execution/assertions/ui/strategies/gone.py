#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TextGoneStrategy — 文本消失断言策略。

一次取证完成全部判定（只采集一次视图树）：
  T1   — 当前位置视图树（含视口外节点）+ 向下 1 屏截图均未命中
         → result=pass / verdict=exact（真消失，不是被顶到屏幕外）
  T2   — 文本仍以精确或子串形态存在：复用同一次采集落元素目录交 AI 判定
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


class TextGoneStrategy(BaseAssertionStrategy):
    """文本消失断言（一次整页取证 → 程序化消失 / AI 语义降级）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        # ── Phase 1: 整页取证 ──────────────────────────────────────────
        # 当前屏看不到 ≠ 已消失：新增/折叠可能把原内容顶到屏幕外。
        # 整页扫一遍都没命中，才能下「已消失」的结论（否则会假绿）。
        sweep = safe_sweep({spec.id: spec.expect}, case_ws=context.case_ws,
                           tag=spec.id, step_key=context.sid)
        if not sweep.get("applicable"):
            # 采集失败（dump 超时/异常）不能当作“已消失”，否则会假绿
            return AssertionResult.fail_unavailable(spec)
        hit = (sweep.get("hits") or {}).get(spec.id)

        if not hit:
            # T1 确认消失 — 无需 AI 介入，直接 PASS
            # matched_text 设为 spec.expect 避免日志中显示为空导致歧义
            result = AssertionResult.pass_exact(
                spec=spec, matched_text=spec.expect, matched_node={},
            )
            info = sweep_evidence(sweep)
            if info:
                result.evidence["scroll_sweep"] = info
            return result

        # ── Phase 2: AI 语义分析 ───────────────────────────────────────
        # 文本仍存在 → 复用这次采到的视图树落元素目录，由 AI 判定消失意图是否成立。
        diag_dir = os.path.join(context.case_ws, "diagnostics") if context.case_ws else None
        nodes = sweep.get("nodes") or None
        _targets, sidecar_path = dump_index(
            context.sid, "assert=gone", nodes=nodes, diag_dir=diag_dir, wait_sec=1,
        )

        result = AssertionResult.pending_semantic(
            spec=spec,
            sidecar=sidecar_path,
            screenshot=context.screenshot_path,
        )
        node_info = dict(hit.get("node") or {})
        node_info["match_level"] = hit.get("match_level", -1)
        result.evidence.setdefault("match_level", hit.get("match_level", -1))
        if node_info.get("text"):
            result.evidence["matched_text"] = node_info.get("text")
        if node_info:
            result.evidence["matched_node"] = node_info
        info = sweep_evidence(sweep, spec.id)
        if info:
            result.evidence["scroll_sweep"] = info

        return result
