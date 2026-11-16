#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VisualAIStrategy — 纯视觉断言策略。

引擎只做两件事：
  1. **收证据**：落全量目标目录（`dump_index`，供 AI 判断目标是否在视口）；
  2. **交判定**：返回 pending，由 AI 在 `verify_visual_assertion` hook 中
     读**本次运行截图**判定。

关键边界：判定依据只有本次运行截图，不做任何跨图对比或图像比对。
"""

from __future__ import annotations
import os

from aitest.execution.assertions.engine import (
    BaseAssertionStrategy, AssertionSpec, AssertionResult, ExecutionContext,
)
from aitest.execution.assertions.ui.pipeline import vts
from aitest.execution.screen.tree_index import dump_index


class VisualAIStrategy(BaseAssertionStrategy):
    """纯视觉断言（引擎收集证据，AI 在 hook 判定）"""

    def execute(self, spec: AssertionSpec, context: ExecutionContext) -> AssertionResult:
        shot_path = context.screenshot_path
        if not shot_path:
            return AssertionResult.fail_unavailable(spec)

        # 落全量目标目录供 AI 判断目标是否在视口
        diag_dir = os.path.join(context.case_ws, "diagnostics") if context.case_ws else None
        _targets, sidecar_path = dump_index(
            context.sid, "assert=visual", diag_dir=diag_dir, wait_sec=3,
        )

        return AssertionResult.pending_visual(
            spec, screenshot=shot_path, sidecar=sidecar_path,
        )
