"""流程生命周期编排：阶段推进、终结、失败收口。
"""
from core.flow.lifecycle.advance import _render_template, get_current_stage, advance_stage, finalize_flow
from core.flow.lifecycle.fail import fail_stage

__all__ = [
    "_render_template", "get_current_stage", "advance_stage", "finalize_flow",
    "fail_stage",
]