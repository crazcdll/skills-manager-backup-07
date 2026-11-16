"""步骤动作契约：可用动作集合、CLI flag 声明、动作参数规格与校验。"""



STEP_ACTIONS = frozenset({
    "tap", "tap-text", "scroll-until", "scroll-edge",
    "back", "blur-input", "open-url", "assert-text", "input-text",
})

# ── 不可原地重跑的动作（重跑会在设备上留下额外、不可撤销的副作用） ──
# 判据：重跑会在设备上累积**不可撤销**的副作用（不是"结果不确定"，而是"做了就回不去"）。
#   · back       —— 每次执行都多退一页（实测：原地重跑 pending 的 back，把页面退出了目标页）
#   · input-text —— 重复输入会在已填字段上叠加，且焦点/光标状态已变
# 幂等/可重放的动作（assert-text / scroll-* / open-url / blur-input / tap-text）不在此列：
# 重跑它们要么无副作用，要么能回到同一状态。
# 已执行过的步骤若确需再执行，必须换新 sid（如 `--sid S3b`）—— 那是"新的一次执行"，
# 会作为父步骤的 retry 记录归属，而不是原地覆盖。
NON_IDEMPOTENT_ACTIONS = frozenset({"back", "input-text"})

# ── 动作 → 可 emit 的 reason 注册表（**唯一事实来源**） ──────────────────
# 这里是「某交互类型在哪些异常场景下会 handoff/失败」的协议声明：
#   · 新增一个 reason 必须先注册在此，再在 on_fail.INTENT_REASON_HOOK_MAP 配 hook；
#   · 守卫 check_target_model.test_action_reason_registry_covers_hooks_and_labels
#     会校验「注册表 → 有 hook 指引」且「各 handler 的 _REASON_LABELS 与注册表逐字一致」，
#     漏配映射会直接报红（handoff 时无指引 = 静默死端）。
# 有意「不配 hook」的引擎内部错误见 on_fail.REASONS_WITHOUT_HOOK。
ACTION_REASONS = {
    "open-url": frozenset({"MISSING_URL", "UNRESOLVED_PLACEHOLDER", "PUSH_FAILED"}),
    "tap": frozenset({
        "MISSING_COORDS", "DEBUG_OVERLAP", "TAP_FAILED",
        "ANCHOR_NOT_FOUND", "ANCHOR_NO_CLICKABLE", "ANCHOR_AMBIGUOUS",
    }),
    "tap-text": frozenset({
        "TEXT_NOT_FOUND", "UNRESOLVED", "AMBIGUOUS",
        "TEXT_OUT_OF_VIEWPORT", "BLOCKED", "TAP_FAILED",
    }),
    "scroll-until": frozenset({
        "SCROLL_TARGET_NOT_FOUND", "SUBSTRING_AMBIGUOUS", "UNRESOLVED",
        "TARGET_Y_OUT_OF_VIEWPORT", "VERTICAL_SCROLL_EXHAUSTED", "HORIZONTAL_SCROLL_EXHAUSTED",
    }),
    "scroll-edge": frozenset({
        "SCROLL_TARGET_NOT_FOUND", "SUBSTRING_AMBIGUOUS", "UNRESOLVED",
        "TARGET_Y_OUT_OF_VIEWPORT", "VERTICAL_SCROLL_EXHAUSTED", "HORIZONTAL_SCROLL_EXHAUSTED",
    }),
    "back": frozenset({"BACK_FAILED"}),
    "input-text": frozenset({
        "MISSING_INPUT_TEXT", "MISSING_ANCHOR", "TEXT_NOT_FOUND",
        "INPUT_TARGET_UNRESOLVED", "TEXT_OUT_OF_VIEWPORT", "INPUT_FAILED",
    }),
    "blur-input": frozenset({"ANCHOR_NOT_FOUND"}),
}
# ═══════════════════════════════════════════════════════════════════
# Action 参数契约（唯一事实来源，校验/CLI --help 均从此处派生）
# ═══════════════════════════════════════════════════════════════════
_CLI_FLAG_NAMES = {
    "action_arg": "--action-arg",
    "action_anchor": "--action-anchor",
    "action_x": "--action-x",
    "action_y": "--action-y",
    "asserts": "--asserts",
}
ACTION_SPECS = {
    "tap": {
        # 两种合法形态：坐标兜底（hook 用）或锚点定位（声明步骤用，禁止写坐标）。
        # 用 any_of 表达"二选一"，让校验、--help、生成器共享同一契约。
        "any_of": [["action_x", "action_y"], ["action_anchor"]],
        "usage": "--action-anchor <锚点>（锚点行唯一可点击目标 / 无文案图标；多或无可点击目标转 AI）"
                 " | --action-x <x> --action-y <y>（坐标兜底，坐标须来自 find-icon / 截图）",
    },
    "tap-text": {
        "required": ["action_arg"],
        "usage": "--action-arg <文案>",
    },
    "scroll-until": {
        "required": ["action_arg"],
        "usage": "--action-arg <目标文案> [--direction down/up/right/left]（用户语义：想看的方向，纵向默认由 viewport_offset 自动推断）",
    },
    "scroll-edge": {
        "required": [],
        "usage": "可选 --direction down/up/right/left（用户语义：想看的方向，默认 down）",
    },
    "back": {
        "required": [],
        "usage": "无需参数",
    },
    "blur-input": {
        "required": [],
        "usage": "可选 --action-arg <锚点文案>（不传则自动选取表单上不可点击的文案）",
    },
    "open-url": {
        "required": ["action_arg"],
        "usage": "--action-arg <url>",
    },
    "assert-text": {
        "required": [],
        "at_least_one_of": ["asserts"],
        "usage": "--asserts <JSON数组>（纯断言，需配合 --step-type assert）",
    },
    "input-text": {
        # 两种形态（与 tap 对称）：锚点/语义描述（声明步骤用）或 --action-x/--action-y（hook 兜底回写输入框坐标）。
        # 二选一由 handler 判定，不在此强约束；action_arg 恒必填（承载要输入的文本 / 锚点+文本 JSON）。
        "required": ["action_arg"],
        "usage": "--action-arg <输入文本>（自动查找输入框坐标）"
                 " | --action-x <x> --action-y <y> --action-arg '{\"text\":\"<值>\"}'（坐标兜底输入）",
    },
}
def validate_action_args(action, args):
    """通用参数契约校验。返回 None 表示通过，字符串表示错误信息。

    支持两种约束：
    - required：所有字段必须存在
    - at_least_one_of：至少一个字段存在
    """
    spec = ACTION_SPECS.get(action)
    if not spec:
        return None  # 未知 action 交给后续分发逻辑报"未知 action"

    # 1) required 约束：每个字段必须存在
    missing = [f for f in spec.get("required", []) if not getattr(args, f, None)]
    if missing:
        missing_flags = [_CLI_FLAG_NAMES.get(f, f) for f in missing]
        return (f"缺少参数 {', '.join(missing_flags)}。"
                f"标准用法: step {action} {spec['usage']}")

    # 2) at_least_one_of 约束：至少一个字段存在
    at_least_one = spec.get("at_least_one_of", [])
    if at_least_one:
        has_any = any(getattr(args, f, None) for f in at_least_one)
        if not has_any:
            flags = [_CLI_FLAG_NAMES.get(f, f) for f in at_least_one]
            return (f"缺少参数 {' 或 '.join(flags)}。"
                    f"标准用法: step {action} {spec['usage']}")

    # 3) any_of 约束：若干"参数组"中至少有一组被完整满足。
    #    用于表达「二选一形态」——如 tap 要么给坐标（--action-x/--action-y），
    #    要么给锚点（--action-anchor）；只给一半坐标不算满足。
    any_of = spec.get("any_of", [])
    if any_of:
        satisfied = any(all(getattr(args, f, None) for f in group) for group in any_of)
        if not satisfied:
            groups = " 或 ".join(
                " ".join(_CLI_FLAG_NAMES.get(f, f) for f in group) for group in any_of
            )
            return (f"缺少参数 {groups}。"
                    f"标准用法: step {action} {spec['usage']}")

    return None
