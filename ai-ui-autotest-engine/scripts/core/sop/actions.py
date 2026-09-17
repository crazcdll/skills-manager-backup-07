"""步骤动作契约：可用动作集合、CLI flag 声明、动作参数规格与校验。"""



STEP_ACTIONS = frozenset({
    "tap", "tap-text", "scroll-until", "scroll-edge",
    "back", "blur-input", "open-url", "assert-text", "input-text",
})
# ═══════════════════════════════════════════════════════════════════
# Action 参数契约（唯一事实来源，校验/CLI --help 均从此处派生）
# ═══════════════════════════════════════════════════════════════════
_CLI_FLAG_NAMES = {
    "action_arg": "--action-arg",
    "action_x": "--action-x",
    "action_y": "--action-y",
    "asserts": "--asserts",
}
ACTION_SPECS = {
    "tap": {
        "required": ["action_x", "action_y"],
        "usage": "--action-x <x> --action-y <y>（无文案图标先 find-icon 查坐标）",
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
        "usage": "可选 --action-anchor <锚点文案>（不传则自动选取表单 label）",
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
        "required": ["action_arg"],
        "usage": "--action-arg <输入文本>（自动查找输入框坐标）",
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

    return None
