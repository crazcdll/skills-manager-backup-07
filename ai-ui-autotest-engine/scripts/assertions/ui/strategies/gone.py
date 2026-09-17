#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TextGoneStrategy — 文本消失断言策略。

两层渐进式：
  T1 — 程序化确认消失：vts.locate_anchor_gone() 带重试，且确认文本未以子串形态残留
       → result=pass / verdict=exact
  T2 — AI 语义分析：文本仍以精确或子串形态存在，构建 element_index 供 AI 判定
"""

from __future__ import annotations
import os
from assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from assertions.ui.pipeline import vts


class TextGoneStrategy(BaseAssertionStrategy):
    """文本消失断言（T1 程序化匹配 → T2 AI 语义降级）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        # ── Phase 1: T1 程序化确认消失 ─────────────────────────────────
        gone = vts.locate_anchor_gone(spec.expect, wait_sec=3, max_retry=2)

        # 精确匹配级已消失还不够：文本可能仍以子串形态留在页面上
        # （页面「- 没有更多了 -」/ expect「没有更多了」）。若此时就直接判消失，
        # gone 断言会对「文本明明还在」误判通过。
        anchor = {"found": False, "nodes_info": None}
        if gone.get("gone"):
            substr = vts.locate_anchor_substring(spec.expect, wait_sec=1)
            if not substr.get("matched"):
                # T1 确认消失 — 无需 AI 介入，直接 PASS
                # matched_text 设为 spec.expect 避免日志中显示为空导致歧义
                return AssertionResult.pass_exact(
                    spec=spec,
                    matched_text=spec.expect,
                    matched_node=gone.get("node", {}),
                )
            anchor = {"found": True, "nodes_info": substr.get("node") or {}}
        else:
            anchor = vts.locate_anchor(spec.expect, wait_sec=1)

        # ── Phase 2: T2 AI 语义分析 ─────────────────────────────────────
        # 文本仍以精确或子串形态存在，构建元素目录供 AI 判定消失意图是否成立
        index = vts.build_element_index(wait_sec=1)

        sidecar_path = ""
        if index.get("available") and context.sid and context.case_ws:
            diag_dir = os.path.join(context.case_ws, "diagnostics")
            os.makedirs(diag_dir, exist_ok=True)
            sidecar_path = os.path.join(diag_dir, f"element_index_{context.sid}.catalog.md")
            vts.write_element_catalog(index, sidecar_path)

        result = AssertionResult.pending_semantic(
            spec=spec,
            sidecar=sidecar_path,
            screenshot=context.screenshot_path,
        )
        # 携带 T1 匹配到的文本信息（写入 evidence，供 AI 与报告消费）
        if anchor.get("found"):
            node_info = anchor.get("nodes_info", {})
            result.evidence.setdefault("match_level", node_info.get("match_level", -1))
            if node_info.get("text"):
                result.evidence["matched_text"] = node_info.get("text")
            if node_info:
                result.evidence["matched_node"] = node_info

        return result