#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VisualAIStrategy — 纯视觉断言策略。

引擎职责：落全量目标目录（统一目标模型 dump_index）+ 确认截图存在。
AI 在 verify_visual_assertion hook 中读该目录判断目标是否在视口，
不在视口时由 AI 在 hook 中调用 scroll-until 滚动后重新截图确认。
"""

from __future__ import annotations
import os
from execution.assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from execution.assertions.ui.pipeline import vts
from execution.screen.tree_index import dump_index


class VisualAIStrategy(BaseAssertionStrategy):
    """纯视觉断言（引擎只收集数据，AI 在 hook 判定）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        shot_path = context.screenshot_path
        if not shot_path:
            return AssertionResult.fail_unavailable(spec)

        # 落全量目标目录供 AI 判断目标是否在视口
        diag_dir = os.path.join(context.case_ws, "diagnostics") if context.case_ws else None
        _targets, sidecar_path = dump_index(
            context.sid, "assert=visual", diag_dir=diag_dir, wait_sec=3,
        )

        return AssertionResult.pending_visual(spec, screenshot=shot_path, sidecar=sidecar_path)