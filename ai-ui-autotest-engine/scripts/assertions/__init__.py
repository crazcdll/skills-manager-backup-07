#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断言引擎包入口。"""

from assertions.engine import (
    AssertionSpec, AssertionResult, ExecutionContext,
    BaseAssertionStrategy, AssertionEngine,
    parse_asserts, compute_step_ok, build_assertions_dict,
    merge_targets, apply_verdicts, apply_verdicts_grouped,
    compute_result_from_entries,
)
from assertions.constants import (
    KIND_TEXT, KIND_VISUAL, MATCH_PRESENT, MATCH_GONE,
    RESULT_PASS, RESULT_FAIL, RESULT_PENDING,
    VERDICT_EXACT, VERDICT_SEMANTIC, VERDICT_VISUAL,
    RESULT_LABELS, VERDICT_LABELS, KIND_LABELS, MATCH_LABELS,
)
from assertions.registry import REGISTRY

__all__ = [
    "AssertionSpec", "AssertionResult", "ExecutionContext",
    "BaseAssertionStrategy", "AssertionEngine", "REGISTRY",
    "parse_asserts", "compute_step_ok", "build_assertions_dict",
    "merge_targets", "apply_verdicts", "apply_verdicts_grouped",
    "compute_result_from_entries",
    "KIND_TEXT", "KIND_VISUAL", "MATCH_PRESENT", "MATCH_GONE",
    "RESULT_PASS", "RESULT_FAIL", "RESULT_PENDING",
    "VERDICT_EXACT", "VERDICT_SEMANTIC", "VERDICT_VISUAL",
    "RESULT_LABELS", "VERDICT_LABELS", "KIND_LABELS", "MATCH_LABELS",
]
