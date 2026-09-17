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
    "mock_setup": "SNAPSHOT DONE",
    "restore": "RESTORE DONE",
    "mock_enable": "APPMOCK ENABLE OK",
    "mock_on": "APPMOCK ON OK",
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
# Reason Code → Hook 路由（在 docstring 中声明但从未实际定义）
# ═══════════════════════════════════════════════════════════════════
# 将 handler 返回的结构化 reason_code 映射到 HOOK_TEMPLATES 中的模板键。
# _build_reason_hooks() 使用此映射为匹配到的 reason_code 生成 Hook 实例。
REASON_CODE_HOOK_MAP = {
    "TEXT_NOT_FOUND":       "on_text_not_found",
    "UNRESOLVED":           "on_target_unresolved",
    "AMBIGUOUS":            "on_target_ambiguous",
    "BLOCKED":              "on_target_blocked",
    "TEXT_OUT_OF_VIEWPORT": "on_viewport_resolve",
    "TARGET_Y_OUT_OF_VIEWPORT": "on_viewport_resolve",
    "SCROLL_TARGET_NOT_FOUND": "on_scroll_target_not_found",
    "VERTICAL_SCROLL_EXHAUSTED": "on_scroll_exhausted",
    "HORIZONTAL_SCROLL_EXHAUSTED": "on_scroll_exhausted",
}
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
