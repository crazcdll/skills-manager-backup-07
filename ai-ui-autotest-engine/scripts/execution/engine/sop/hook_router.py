"""Hook 路由：按步骤结果生成 hook（T1/T2/T3 + reason hook），并汇总 review 判定。"""
import sys
from execution.engine.sop.hook_templates import HOOK_TEMPLATES
from execution.engine.sop.on_fail import reason_hook_template
from execution.engine.sop.hook_render import (_build_expected_fields_list, _finalize_hooks,
                                 _format_track_candidates, _select_params)
from execution.assertions.constants import RESULT_PASS, VERDICT_EXACT
from execution.assertions.engine import action_hit_needs_review, compute_needs_review


# hook_id → 该 hook 声明的动作必须在 steps.jsonl 里留下对应 sid 的记录。
# 否则 hook 完成后若步骤仍为 PENDING，_finalize_effect_pending_step 会**无条件改判 PASS** ——
# 修复类 hook（能得出 FAIL）必须登记，强制先落 override/重试记录。
HOOKS_REQUIRE_STEPS_JSONL_RECORD = {"log_step_warn", "log_step_fail", "verify_text_assertion", "verify_text_visual_recheck", "verify_visual_assertion", "verify_api_fields", "verify_track_fields", "resolve_text_not_found", "resolve_target_unresolved", "resolve_target_ambiguous", "resolve_target_blocked", "resolve_target_viewport", "resolve_scroll_target_not_found", "resolve_scroll_exhausted", "resolve_scroll_substring_ambiguous", "resolve_tap_anchor_not_found", "resolve_tap_anchor_ambiguous", "resolve_tap_failed", "resolve_tap_blocked_by_overlay", "resolve_input_anchor_not_found", "resolve_input_anchor_viewport", "resolve_input_box", "resolve_input_device_failed", "resolve_blur_anchor_not_found", "resolve_open_url_failed", "resolve_back_failed"}
def _attach_element_index(hook, path):
    """把元素目录路径挂到 hook.hint_params（渲染层据此统一追加证据块）。

    元素目录是 AI 定位元素的唯一权威视图，所有需要 AI 定位/选择元素的 hook 都应携带；
    这里集中注入，模板无需各自声明 {element_index_path} 占位符。
    """
    if path:
        hook.setdefault("hint_params", {})["element_index_path"] = path


def _any_assertion_pass_needs_review(assertions):
    """断言集合中是否存在「通过但非精确」的结论（T1.5 语义等价 / AI 语义 / 视觉）。

    与报告层 needs_review 同源（唯一口径见 assertions.engine.compute_needs_review）：
    非 exact 的通过一律需人工复核，因此也需 AI 在控制台被告知。
    """
    if not isinstance(assertions, dict):
        return False
    for items in assertions.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("result") != RESULT_PASS:
                continue
            if compute_needs_review(True, item.get("verdict") or VERDICT_EXACT):
                return True
    return False


def compute_review_required(ok_val, ctx=None, assertions=None):
    """推导 AI/人工是否需要后续处理（唯一口径：通过且非字面精确命中）。

    返回值含义：
      True  — 有断言待处理（PENDING）/ 步骤失败 / 命中方式或断言判定非字面精确（需人工复核）
      False — 字面精确匹配全部通过，无需介入

    与断言层共用同一口径（见 assertions.engine）：引擎「唯一子串兜底 / 语义等价」这类
    推断命中虽然程序化给出结论，仍属非确定性，必须标记复核，不能被静默当作确定通过。
    """
    if ok_val is None:  # PENDING — 有 T2/T3 断言待 AI 判定
        return True
    if ok_val in (0, 2):  # FAIL / WARN
        return True
    if action_hit_needs_review((ctx or {}).get("action_hit")):
        return True
    return _any_assertion_pass_needs_review(assertions)
def get_hooks_for_result(ok_val, action_type, assertions=None, effect_desc="",
                         step_context=None):
    """根据断言类型和执行结果生成 hooks 列表。

    统一入口：操作 Hook（按 ok_val + reason_code 路由）+ 断言 Hook
    （按 assertions verdict）由两阶段独立逻辑叠加生成。

    设计原则：操作完成度与校验完整度是两个正交维度。
    - 操作 Hook：基于 handler 返回的 action_ok/reason_code，处理操作层面的问题
    - 断言 Hook：基于 assertion engine 收集的 verdict，处理校验层面的判定
    两阶段 Hook 可以并存于同一步骤，无互斥关系。

    step_context: dict — 步骤执行上下文，含 hook 格式化所需的所有字段：
        failure_context : dict | None — handler 失败上下文（含 reason_code）
        screenshot_name : str — 截图文件名（用于 cli_hint 格式化）
        action_arg     : str — 操作参数（用于 cli_hint 格式化）
        # 未来可扩展：retry_count, confidence, extra_debug_info 等

    assertions: dict — 断言结果，按 kind 分组：{"text": [...], "visual": [...]}
    条目为结构化断言结果：{id, kind, match?, expect, targets?, criteria?, on_fail?,
                            result, verdict?, actual?, reason?, evidence, available}
    根据断言 kind / result 生成对应的 verify_text_assertion / verify_visual_assertion hook。

    双断言机制：
    - text 断言 result=pending → verify_text_assertion（语义确认）
      + verify_text_visual_recheck（视觉复核，校验元素目录与真实渲染一致）
    - visual 断言 → verify_visual_assertion（视觉判定）
    上述 hook 共用同一份 --assert-verdict（一个步骤只写一次 override）。

    ok_val 约定（tri-state）：
      0=FAIL（真失败：设备/参数错误）— 断言无意义，仅生成操作 hook
      1=PASS（通过）
      2=WARN（警告）— 断言无意义，仅生成操作 hook
      None=PENDING — 可能是 handoff（handler 返回 ok=None，等待 AI 根据 reason hook 决策）
                       或断言 PENDING（assertion 引擎收集完数据，等待 AI 语义匹配）
    """
    failure_context = (step_context or {}).get("failure_context")
    hooks = []

    # ═══════════════════════════════════════════════════════════════
    # 阶段 1：操作 Hook — 基于 ok_val + reason_code
    # ═══════════════════════════════════════════════════════════════

    # 真失败（设备/参数错误）：断言校验无意义，直接返回
    if ok_val == 0:
        hooks = [dict(h) for h in HOOK_TEMPLATES["on_fail"]]
        return _extend_reason_hooks(hooks, step_context)

    # WARN：校验无意义，直接返回
    if ok_val == 2:
        if action_type == "back":
            hooks = [dict(h) for h in HOOK_TEMPLATES["on_back_unexpected"]]
        else:
            hooks = [dict(h) for h in HOOK_TEMPLATES["on_warn"]]
        return _extend_reason_hooks(hooks, step_context)

    # Handoff / PASS：可能同时有断言需要校验，继续进入阶段 2
    if ok_val is None and failure_context and failure_context.get("reason"):
        reason_hooks = _build_reason_hooks(step_context)
        if reason_hooks:
            hooks.extend(reason_hooks)

    # ═══════════════════════════════════════════════════════════════
    # 阶段 2：断言 Hook — 基于 assertions 的 result（pass/fail/pending）
    # ═══════════════════════════════════════════════════════════════
    if not assertions:
        return _finalize_hooks(hooks)

    text_items = assertions.get("text", []) or []
    visual_items = assertions.get("visual", []) or []

    def _evidence_of(item, key):
        return (item.get("evidence") or {}).get(key, "")

    def _assertion_line(item):
        bits = [f"id={item.get('id', '')}", f"kind={item.get('kind', '')}"]
        if item.get("kind") == "text":
            bits.append(f"match={item.get('match', '')}")
        line = "   [" + " ".join(bits) + f"] expect=\"{item.get('expect', '')}\""
        for idx, target in enumerate(item.get("targets") or [], 1):
            label = target if isinstance(target, str) else target.get("expect", "")
            line += f"\n       {idx}. {label}"
        return line

    def _build_assertion_list(items):
        return "\n".join(_assertion_line(it) for it in items)

    # 待 AI 判定的文本断言（T1 未命中 → T2 语义确认）
    text_pending = [it for it in text_items if it.get("result") == "pending"]

    if text_pending:
        text_tmpl = HOOK_TEMPLATES["on_text_assertion"][0]
        h_text = dict(text_tmpl)
        h_text["hint_params"] = _select_params(text_tmpl["cli_hint"], {
            "assertion_list": _build_assertion_list(text_items),
        })[0]
        _attach_element_index(h_text, _evidence_of(text_pending[0], "sidecar"))
        hooks.append(h_text)

        # T2 语义确认后的视觉复核（每个待判 text 断言一个）：
        # 职责是校验元素目录与真实渲染是否一致，与 verify_visual_assertion
        # （判定 visual 断言）职责分离，因此用独立模板 / 独立 hook id。
        recheck_tmpl = HOOK_TEMPLATES["on_text_visual_recheck"][0]
        for item in text_pending:
            h_recheck = dict(recheck_tmpl)
            # 本步骤另有 visual 断言时，复核必须完成（否则非必需）
            h_recheck["required"] = bool(visual_items)
            h_recheck["hint_params"] = _select_params(recheck_tmpl["cli_hint"], {
                "screenshot_path": _evidence_of(item, "screenshot") or "(未截图)",
                "assertion_list": _assertion_line(item),
            })[0]
            _attach_element_index(h_recheck, _evidence_of(item, "sidecar"))
            hooks.append(h_recheck)

    # T3: 纯视觉断言（已有 T3 visual 时不重复生成）
    if visual_items and not text_pending:
        visual_tmpl = HOOK_TEMPLATES["on_visual_assertion"][0]
        h = dict(visual_tmpl)
        h["hint_params"] = _select_params(visual_tmpl["cli_hint"], {
            "screenshot_path": _evidence_of(visual_items[0], "screenshot") or "(未截图)",
            "assertion_list": _build_assertion_list(visual_items),
        })[0]
        _attach_element_index(h, _evidence_of(visual_items[0], "sidecar"))
        hooks.append(h)

    # API/Track 字段断言
    api_fields = assertions.get("api_fields")
    if api_fields:
        expected_fields = api_fields.get("expected_fields", [])
        evidence_path = api_fields.get("evidence_path", "")
        lines = _build_expected_fields_list(expected_fields)
        h = dict(HOOK_TEMPLATES["on_api_fields_assertion"][0])
        # 浅骨架单独落文件（diagnostics/response_skeleton_<sid>.md），由证据路径推导，供 AI 直接 read_file
        skeleton_path = ""
        if evidence_path and "api_evidence_" in evidence_path:
            skeleton_path = evidence_path.replace(
                "api_evidence_", "response_skeleton_"
            ).rsplit(".", 1)[0] + ".md"
        h["hint_params"] = {
            "evidence_path": evidence_path or "(未生成)",
            "expected_fields_list": lines,
            "skeleton_path": skeleton_path or "(未生成)",
        }
        hooks.append(h)

    track_fields = assertions.get("track_fields")
    if track_fields:
        expected_fields = track_fields.get("expected_fields", {})
        evidence_path = track_fields.get("evidence_path", "")
        candidates = track_fields.get("candidates") or []
        lines = _build_expected_fields_list(expected_fields, is_api=False)
        h = dict(HOOK_TEMPLATES["on_track_fields_assertion"][0])
        h["hint_params"] = {
            "match": track_fields.get("match", ""),
            "evidence_path": evidence_path or "(未生成)",
            "expected_fields_list": lines,
            "candidate_list": _format_track_candidates(candidates),
            "candidate_count": len(candidates),
        }
        hooks.append(h)

    return _finalize_hooks(hooks)
def _extend_reason_hooks(hooks, step_context):
    """前置插入 reason_code 驱动的 Hook（如有）。

    reason hook（如 resolve_text_not_found）排在最前面，
    确保 AI 先看到具体的 action 修复引导，再看到通用分析模板。
    所有返回路径统一经过 _finalize_hooks 规范化（剥离 cli_hint）。
    """
    if not step_context:
        return _finalize_hooks(hooks)
    failure_context = step_context.get("failure_context")
    if not failure_context:
        return _finalize_hooks(hooks)
    reason_hooks = _build_reason_hooks(step_context)
    if reason_hooks:
        hooks[0:0] = reason_hooks  # 前置插入
    return _finalize_hooks(hooks)
def _build_reason_hooks(step_context):
    """从 step_context 的 reason_code 生成 Hook 实例列表。

    路由键是 **(动作名, reason_code)**（见 execution/engine/sop/on_fail.reason_hook_template）：
    同一 reason 在点击类与输入类下的修复动作不同，只按 reason 会把输入场景错配成
    「坐标点击」。

    Returns:
        list[dict] | None: 携带 hint_params 的 hook 列表，无匹配返回 None。
    """
    failure_context = step_context.get("failure_context") or {}
    screenshot_name = step_context.get("screenshot_path") or step_context.get("screenshot_name", "")
    action_type = step_context.get("action_type", "")
    action_arg = step_context.get("action_arg", "")
    reason = failure_context.get("reason")
    hook_key = reason_hook_template(action_type, reason)
    if not hook_key:
        return None
    templates = HOOK_TEMPLATES.get(hook_key, [])
    if not templates:
        return None
    center = failure_context.get("center", ["?", "?"])
    _hit = failure_context.get("hit") or {}
    if _hit:
        overlay_hit = (f"「{_hit.get('text', '')}」({_hit.get('class_name', '')})"
                       f" bounds={_hit.get('bounds')}")
    else:
        overlay_hit = "（未上报）"
    # 候选清单由 handler 用统一渲染器（tree_index.render_candidates）产出后随 ctx 传入，
    # 这里只做占位符替换，不再自己拼装（避免与目标模型脱节，也避开 input 的 JSON action_arg）。
    values = {
        "target_text": failure_context.get("arg") or action_arg or "",
        "screenshot_path": screenshot_name or "",
        "target_x": center[0] if isinstance(center, (list, tuple)) and len(center) > 0 else "?",
        "target_y": center[1] if isinstance(center, (list, tuple)) and len(center) > 1 else "?",
        "viewport_offset": failure_context.get("viewport_offset", "?"),
        "viewport_offset_x": failure_context.get("viewport_offset_x", "?"),
        "scroll_direction": failure_context.get("direction", "?"),
        "swipes": failure_context.get("swipes", "?"),
        "element_index_path": failure_context.get("element_index_path", ""),
        "candidate_list": failure_context.get("candidate_list") or "   （无候选）",
        "candidate_count": failure_context.get("candidate_count", 0),
        "overlay_hit": overlay_hit,
    }
    hooks = []
    for tmpl in templates:
        hook = dict(tmpl)
        cli_hint = tmpl.get("cli_hint")
        if cli_hint:
            params, missing = _select_params(cli_hint, values)
            if missing:
                print(f"  ⚠️ hook[{tmpl.get('id')}] 模板占位符缺少取值: {missing}", file=sys.stderr)
            hook["hint_params"] = params
        # 元素目录统一挂载：handler 落盘后经 ctx 透传，渲染层集中追加证据块
        # （模板不再各自声明占位符，避免漏挂 → AI 拿不到结构视图树只能重采）。
        _attach_element_index(hook, values.get("element_index_path"))
        hooks.append(hook)
    return hooks
