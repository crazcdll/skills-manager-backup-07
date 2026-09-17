#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VisualAIStrategy — 纯视觉断言策略。

引擎职责：构建 element_index + 确认截图存在。
AI 在 verify_visual_assertion hook 中读 element_index 判断目标是否在视口，
不在视口时由 AI 在 hook 中调用 scroll-until 滚动后重新截图确认。
"""

from __future__ import annotations
import os
from assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from assertions.ui.pipeline import vts


class VisualAIStrategy(BaseAssertionStrategy):
    """纯视觉断言（引擎只收集数据，AI 在 hook 判定）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        shot_path = context.screenshot_path
        if not shot_path:
            return AssertionResult.fail_unavailable(spec)

        # 构建结构化元素目录供 AI 判断目标是否在视口
        index = vts.build_element_index(wait_sec=3)
        sidecar_path = ""
        if index.get("available") and context.sid and context.case_ws:
            diag_dir = os.path.join(context.case_ws, "diagnostics")
            os.makedirs(diag_dir, exist_ok=True)
            sidecar_path = os.path.join(diag_dir, f"element_index_{context.sid}.catalog.md")
            vts.write_element_catalog(index, sidecar_path)

        return AssertionResult.pending_visual(spec, screenshot=shot_path, sidecar=sidecar_path)