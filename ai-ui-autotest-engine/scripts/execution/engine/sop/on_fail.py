"""on-fail 策略：默认规则、成功标志、5 种失败策略及其读取入口。"""

# 默认规则
DEFAULT_RULES = {
    "forbid_back_key": False,
    "forbid_rerun_step": True,
    "forbid_code_modify": True,
    "screenshot_required": True,
    "on_step_fail": "log_and_continue",
    "on_step_warn": "log_and_continue",
    "max_retries_per_step": 1,
    "password_mask": True,
    "no_bare_imeituan_calls": True,
    "coordinate_from_inspect_tree": True,
}
# 默认成功标志
DEFAULT_SUCCESS_MARKERS = {
    "mock_preflight": "MOCK-PREFLIGHT OK",
    "mock_apply": "MOCK-APPLY OK",
    "mock_restore": "MOCK-RESTORE",
    "bundle_lock": "BUNDLE-LOCK",
    "flow_init": "FLOW-INIT OK",
    "hook_done": "HOOK-DONE OK",
    "flow_status": "FLOW-STATUS:",
    "open_url": "OPEN-URL OPENED",
    "record_start": "RECORD START OK",
    "login_input_code": "LOGIN INPUT-CODE OK",
    "swimline_add": "SWIMLINE ADD OK",
    "swimline_switch": "SWIMLINE SWITCH OK",
    "swimline_verify": "SWIMLINE VERIFY OK",
    "env_set": "APPMOCK ENV SET OK",
    "url_mapping_ensure": "ENSURE:",
}
# on_fail 策略常量：SOP 阶段失败时的处理方式
#   abort            — 记录异常 + 生成报告 + 终止流程（环境准备阶段专用）
#   pause            — 暂停，用 AskQuestion 让用户选择（重试/跳过/终止）
#   log_and_continue — 记录后继续下一步（步骤走查阶段专用）
#   best_effort      — 尽力执行，失败不影响后续（收尾清理阶段专用）
#   skip_to_next_case — 标记当前 case 失败，跳到下一个 case（batch case 循环体专用）
ON_FAIL_ABORT = "abort"
ON_FAIL_PAUSE = "pause"
ON_FAIL_LOG_AND_CONTINUE = "log_and_continue"
ON_FAIL_BEST_EFFORT = "best_effort"
ON_FAIL_SKIP_TO_NEXT_CASE = "skip_to_next_case"
# ═══════════════════════════════════════════════════════════════════
# Reason Code + 动作意图 → Hook 路由
# ═══════════════════════════════════════════════════════════════════
# 为什么必须按「意图」分派：同一个 reason_code 在不同动作下，修复动作不同 ——
#   点击类：用坐标补点一次；
#   输入类：重新定位可编辑元素后**重跑 input-text**。
# 只按 reason 映射会把输入场景引导成「坐标点击」（错配）。因此以
# (意图, reason) 为主键，意图从动作名推导。
INTENT_CLICK = "click"
INTENT_INPUT = "input"
INTENT_BLUR = "blur"

# 点击类（tap-text / scroll-until / tap）：默认意图
_CLICK_REASON_HOOK_MAP = {
    "TEXT_NOT_FOUND":           "on_text_not_found",
    "UNRESOLVED":               "on_target_unresolved",
    "AMBIGUOUS":                "on_target_ambiguous",
    "BLOCKED":                  "on_target_blocked",
    "TEXT_OUT_OF_VIEWPORT":     "on_viewport_resolve",
    "TARGET_Y_OUT_OF_VIEWPORT": "on_viewport_resolve",
    "SCROLL_TARGET_NOT_FOUND":  "on_scroll_target_not_found",
    # scroll 子串多候选（仅 scroll-until 产生）：历史上漏配 → 该步 PENDING 却无任何
    # hook 指引（AI 空转）。补专用模板：必须"选定元素后用真实文案重跑"，不是坐标点击。
    "SUBSTRING_AMBIGUOUS":      "on_scroll_substring_ambiguous",
    "VERTICAL_SCROLL_EXHAUSTED": "on_scroll_exhausted",
    "HORIZONTAL_SCROLL_EXHAUSTED": "on_scroll_exhausted",
    # tap 锚点形态（--action-anchor）：锚点行没有唯一可点击目标时的两条路径。
    # 「锚点未命中」与「行内无可点击目标」的处置相同（读图 → 换锚点或坐标兜底），
    # 因此共用同一模板；「多候选」需 AI 按上下文选定，单独一条。
    "ANCHOR_NOT_FOUND":         "on_tap_anchor_not_found",
    "ANCHOR_NO_CLICKABLE":      "on_tap_anchor_not_found",
    "ANCHOR_AMBIGUOUS":         "on_tap_anchor_ambiguous",
    # 设备/环境级动作失败（非语义可判定）：各给一条专用修复模板
    "TAP_FAILED":               "on_tap_failed",
    "DEBUG_OVERLAP":            "on_tap_blocked_by_overlay",
    "PUSH_FAILED":              "on_open_url_failed",
    "BACK_FAILED":              "on_back_failed",
}

INTENT_REASON_HOOK_MAP = {
    INTENT_CLICK: _CLICK_REASON_HOOK_MAP,
    INTENT_INPUT: {
        "TEXT_NOT_FOUND":       "on_input_anchor_not_found",
        # 只给锚点/语义描述、锚点行内解析不出唯一输入框 → 专用 hook：AI 自己找输入框后坐标兜底重跑
        "INPUT_TARGET_UNRESOLVED": "on_input_box_resolve",
        # 已定位并聚焦，但文本注入失败（ADBKeyboard/焦点）→ 设备级问题，与「找不到输入框」分治
        "INPUT_FAILED":         "on_input_device_failed",
        "TEXT_OUT_OF_VIEWPORT": "on_input_anchor_viewport",
    },
    INTENT_BLUR: {
        "ANCHOR_NOT_FOUND": "on_blur_anchor_not_found",
    },
}

# ── 有意「不配 hook」的 reason（守卫白名单） ────────────────────────────
# 这些是**引擎内部错误**（命令参数不合法 / 缺少 URL 等）：代表「命令被写错了」，
# 处置是修正命令重跑，而非给 AI 一套场景修复指引。
# test_every_emittable_reason_has_hook_or_is_declared_internal 据此放行；
# 新增可 emit 的 reason 若忘了加映射，守卫会直接报红（避免静默死端）。
REASONS_WITHOUT_HOOK = frozenset({
    "MISSING_COORDS", "MISSING_ANCHOR", "MISSING_INPUT_TEXT", "MISSING_URL",
})

# 动作名 → 意图（未列出的动作一律按点击类处理）
_ACTION_INTENT = {
    "input-text": INTENT_INPUT,
    "blur-input": INTENT_BLUR,
}


def intent_of_action(action_name):
    """动作名 → 意图。"""
    return _ACTION_INTENT.get(action_name or "", INTENT_CLICK)


def reason_hook_template(action_name, reason_code):
    """(动作名, reason_code) → HOOK_TEMPLATES 模板键。

    未覆盖的组合回退到点击类意图：这是**兜底**（避免 hook 静默丢失），
    不是历史兼容 —— 已声明的 (意图, reason) 一律走精确映射。
    """
    intent = intent_of_action(action_name)
    table = INTENT_REASON_HOOK_MAP.get(intent) or {}
    return table.get(reason_code) or _CLICK_REASON_HOOK_MAP.get(reason_code)
def _get_on_fail_policy(stage):
    """从 stage 中提取 on_fail 策略。"""
    on_fail = stage.get("on_fail", {})
    if isinstance(on_fail, dict):
        return on_fail.get("policy", ON_FAIL_PAUSE)
    return ON_FAIL_PAUSE
def _get_on_fail_config(stage):
    """返回完整的 on_fail 结构化声明。"""
    on_fail = stage.get("on_fail", {})
    if isinstance(on_fail, dict):
        return on_fail
    return {"policy": ON_FAIL_PAUSE}
