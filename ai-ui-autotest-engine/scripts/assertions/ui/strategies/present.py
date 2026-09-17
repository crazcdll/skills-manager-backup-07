#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TextPresentStrategy — 文本出现断言策略。

三层渐进式：
  T1   — 程序化精确匹配：vts.locate_anchor() 命中则 result=pass / verdict=exact，无 hook
  T1.5 — 程序化子串回退：候选文案形态唯一时语义等价，result=pass / verdict=semantic，无 hook
  T2   — AI 语义确认：以上均未命中或候选形态不唯一，构建 element_index 供 AI 理解，生成 hook
"""

from __future__ import annotations
import os
from assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from assertions.ui.pipeline import vts


class TextPresentStrategy(BaseAssertionStrategy):
    """文本出现断言（T1 程序化匹配 → T2 AI 语义降级）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        # ── Phase 1: T1 程序化匹配 ──────────────────────────────────────
        anchor = vts.locate_anchor(spec.expect, wait_sec=3)

        if anchor.get("found"):
            # T1 命中 — 无需 AI 介入，直接 PASS
            node_info = anchor.get("nodes_info", {})
            return AssertionResult.pass_exact(
                spec=spec,
                matched_text=node_info.get("text", spec.expect),
                match_level=node_info.get("match_level", -1),
                matched_node=node_info,
            )

        # ── Phase 1.5: 唯一子串回退（语义等价，无需 AI 介入）────────────────
        # 判定口径明确认可「expect 是页面复合文案的子串 → pass/semantic」
        # （如 expect「没有更多了」/ 页面「- 没有更多了 -」）。候选文案形态唯一时
        # 结论是确定的，不该再消耗一轮 AI hook（实测单次 ~24s + 读目录/读图）。
        substr = vts.locate_anchor_substring(spec.expect, wait_sec=1)
        if substr.get("unique"):
            return AssertionResult.pass_semantic(
                spec=spec,
                matched_text=substr["texts"][0],
                match_level=substr.get("match_level", -1),
                matched_node=substr.get("node"),
            )

        # ── Phase 2: T2 AI 语义降级 ─────────────────────────────────────
        # 未命中，或子串候选存在多种形态（语义不确定），构建元素目录交 AI 判定
        index = vts.build_element_index(wait_sec=3)
        if not index.get("available"):
            return AssertionResult.fail_unavailable(spec)

        sidecar_path = ""
        if context.sid and context.case_ws:
            diag_dir = os.path.join(context.case_ws, "diagnostics")
            os.makedirs(diag_dir, exist_ok=True)
            sidecar_path = os.path.join(diag_dir, f"element_index_{context.sid}.catalog.md")
            vts.write_element_catalog(index, sidecar_path)

        return AssertionResult.pending_semantic(
            spec=spec,
            sidecar=sidecar_path,
            screenshot=context.screenshot_path,
        )