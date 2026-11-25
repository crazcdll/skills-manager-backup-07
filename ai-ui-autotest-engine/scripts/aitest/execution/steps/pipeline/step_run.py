"""步骤运行的运行时状态容器。

把原先 `_cmd_step` 内 20+ 个局部变量收敛为一个对象，使
「操作 → 等待 → 截图 → 断言 → 收口」各阶段以 run 为唯一入参，
编排保持线性可读，也避免 `_update_flow_context_after_step` 这类函数
出现十几个位置参数。

字段语义：
    action_ok           tri-state：True=通过 / False=失败 / None=handoff（待 AI 决策）
    inspect_tree_impact action 对视图树的影响：none / unknown / ...
    step_result         步骤结论：1=PASS / 2=WARN / 0=FAIL / None=PENDING
"""
from dataclasses import dataclass, field


@dataclass
class StepRun:
    # ── 初始化期 ──
    args: object
    root_dir: str
    flow_context: dict
    case_workspace: str
    case_index: object = None
    step_start: float = 0.0

    # ── sid 解析期 ──
    sid_arg: object = None
    step_definition: object = None
    retry_parent_sid: object = None
    # 归属型兜底（--for-sid）：记录归入该声明步骤证据，但不改其结论。
    for_sid: object = None
    effective_sid: object = None
    current_sid: str = ""

    # ── 运行期 ──
    ops: object = None
    action_ok: object = True
    action_failure_reason: str = ""
    failure_context: dict = field(default_factory=dict)
    inspect_tree_impact: str = "unknown"

    # ── 截图 / 断言 ──
    screenshot_name: object = None
    screenshot_path: object = None
    assertion_results: list = field(default_factory=list)
    assertions_dict: dict = field(default_factory=dict)
    execute_results: list = field(default_factory=list)
    unavailable_assertions: list = field(default_factory=list)
    assertion_failure_reason: str = ""

    # ── 结论 ──
    step_result: object = None
    is_review_required: bool = False
    # 动作层命中方式（handler ctx.action_hit）：非字面精确命中时记录，如唯一子串兜底。
    # 空 dict = 字面精确命中（或未记录）→ 不需人工复核。
    action_hit: dict = field(default_factory=dict)
    duration_ms: int = 0
    record: object = None
