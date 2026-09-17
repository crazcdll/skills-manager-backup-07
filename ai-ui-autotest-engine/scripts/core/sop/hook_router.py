"""Hook 路由：按步骤结果生成 hook（T1/T2/T3 + reason hook），并汇总 review 判定。"""
import json
import sys
from core.sop.hook_templates import HOOK_TEMPLATES
from core.sop.on_fail import REASON_CODE_HOOK_MAP
from core.sop.hook_render import _build_expected_fields_list, _finalize_hooks, _select_params


# hook_id → 该 hook 声明的动作必须在 steps.jsonl 里留下对应 sid 的记录。
HOOKS_REQUIRE_STEPS_JSONL_RECORD = {"log_step_warn", "log_step_fail", "verify_text_assertion", "verify_text_visual_recheck", "verify_visual_assertion", "verify_api_fields", "verify_track_fields", "resolve_text_not_found", "resolve_target_unresolved", "resolve_target_ambiguous", "resolve_target_blocked", "resolve_target_viewport", "resolve_scroll_target_not_found", "resolve_scroll_exhausted"}
def compute_review_required(ok_val, ctx=None):
    """推导 AI 是否需要后续处理。

    返回值含义：
      True  — 有断言待处理（PENDING）或步骤失败，需 AI 介入
      False — T1 程序化匹配全部通过，无需 AI 介入
    """
    if ok_val is None:  # PENDING — 有 T2/T3 断言待 AI 判定
        return True
    if ok_val in (0, 2):  # FAIL / WARN
        return True
    if ctx and ctx.get("low_confidence_warning"):
        return True
    return False
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
            "sidecar_path": _evidence_of(text_pending[0], "sidecar") or "(未生成)",
            "assertion_list": _build_assertion_list(text_items),
        })[0]
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
                "sidecar_path": _evidence_of(item, "sidecar") or "(未生成)",
                "assertion_list": _assertion_line(item),
            })[0]
            hooks.append(h_recheck)

    # T3: 纯视觉断言（已有 T3 visual 时不重复生成）
    if visual_items and not text_pending:
        visual_tmpl = HOOK_TEMPLATES["on_visual_assertion"][0]
        h = dict(visual_tmpl)
        h["hint_params"] = _select_params(visual_tmpl["cli_hint"], {
            "screenshot_path": _evidence_of(visual_items[0], "screenshot") or "(未截图)",
            "sidecar_path": _evidence_of(visual_items[0], "sidecar") or "(无 sidecar)",
            "assertion_list": _build_assertion_list(visual_items),
        })[0]
        hooks.append(h)

    # API/Track 字段断言
    api_fields = assertions.get("api_fields")
    if api_fields:
        expected_fields = api_fields.get("expected_fields", [])
        evidence_path = api_fields.get("evidence_path", "")
        lines = _build_expected_fields_list(expected_fields)
        h = dict(HOOK_TEMPLATES["on_api_fields_assertion"][0])
        h["hint_params"] = {
            "evidence_path": evidence_path or "(未生成)",
            "expected_fields_list": lines,
        }
        hooks.append(h)

    track_fields = assertions.get("track_fields")
    if track_fields:
        expected_fields = track_fields.get("expected_fields", {})
        evidence_path = track_fields.get("evidence_path", "")
        lines = _build_expected_fields_list(expected_fields, is_api=False)
        h = dict(HOOK_TEMPLATES["on_track_fields_assertion"][0])
        h["hint_params"] = {
            "evidence_path": evidence_path or "(未生成)",
            "expected_fields_list": lines,
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
def _format_candidate_list(failure_context):
    """候选节点清单（文案 + 可点击 + 坐标）——resolve_text_not_found / resolve_target_ambiguous 共用。

    数据源：handler 的 substring_hints（TEXT_NOT_FOUND）/ candidates（AMBIGUOUS）。
    这里必须把「文案 + 坐标」都渲染出来：模板曾引用「步骤输出的 🔍 列表」，
    那是跨轮的 stdout（AI 回看时早已不在上下文里），只给候选项数时 AI 无法直接行动。
    """
    items = failure_context.get("substring_hints") or failure_context.get("candidates") or []
    lines = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        center = item.get("center")
        flag = "✅" if item.get("clickable") else "  "
        line = f"   [{index}] {flag}「{text}」"
        if center:
            line += f" @ center={list(center)} tap=({center[0]},{center[1]})"
        lines.append(line)
    if not lines:
        return "   （无：视图树中没有任何节点的文案包含目标子串）"
    return "\n".join(lines)
def _format_neighbor_tree(failure_context):
    """UNRESOLVED 的结构邻域树（JSON 文本，供 AI 选真实点击目标）。"""
    subtree = failure_context.get("subtree")
    if not subtree:
        return "   （无结构邻域树：请用 find-node 工具（或 find-icon --anchor <邻近文案>）获取）"
    return json.dumps(subtree, ensure_ascii=False)
def _build_reason_hooks(step_context):
    """从 step_context.failure_context 的 reason_code 生成 Hook 实例列表。

    路由逻辑（每个 reason_code 路由到独立 Hook，AI 无需自行判断场景）：
      - TEXT_NOT_FOUND  → resolve_text_not_found hook（子串扫描元素索引取坐标）
      - UNRESOLVED      → resolve_target_unresolved hook（结构邻域树分析）
      - AMBIGUOUS       → resolve_target_ambiguous hook（多候选消歧）
      - BLOCKED         → resolve_target_blocked hook（遮挡处理）
      - TEXT_OUT_OF_VIEWPORT → resolve_target_viewport hook（滚动）
      - SCROLL_TARGET_NOT_FOUND → resolve_scroll_target_not_found hook（scroll-until 未命中）
      - VERTICAL_SCROLL_EXHAUSTED → resolve_scroll_exhausted hook（纵向滚动耗尽）
      - HORIZONTAL_SCROLL_EXHAUSTED → resolve_scroll_exhausted hook（横向滚动耗尽）
      - 其他（TAP_FAILED / MISSING_COORDS / DEBUG_OVERLAP）
        → 不路由，走标准 on_fail 流程

    Returns:
        list[dict] | None: 携带 hint_params 的 hook 列表，无匹配返回 None。
    """
    failure_context = step_context.get("failure_context") or {}
    screenshot_name = step_context.get("screenshot_path") or step_context.get("screenshot_name", "")
    action_arg = step_context.get("action_arg", "")
    reason = failure_context.get("reason")
    hook_key = REASON_CODE_HOOK_MAP.get(reason)
    if not hook_key:
        return None
    templates = HOOK_TEMPLATES.get(hook_key, [])
    if not templates:
        return None
    center = failure_context.get("center", ["?", "?"])
    # 键名与各模板占位符一一对应：不再共用一个语义漂移的 extra_context
    # （它曾在 on_text_not_found 里当候选清单、在 on_target_ambiguous 里当数量）。
    values = {
        "target_text": action_arg or failure_context.get("arg", ""),
        "screenshot_path": screenshot_name or "",
        "target_x": center[0] if isinstance(center, (list, tuple)) and len(center) > 0 else "?",
        "target_y": center[1] if isinstance(center, (list, tuple)) and len(center) > 1 else "?",
        "viewport_offset": failure_context.get("viewport_offset", "?"),
        "viewport_offset_x": failure_context.get("viewport_offset_x", "?"),
        "scroll_direction": failure_context.get("direction", "?"),
        "swipes": failure_context.get("swipes", "?"),
        "element_index_path": failure_context.get("element_index_path", ""),
        "candidate_list": _format_candidate_list(failure_context),
        "candidate_count": len(failure_context.get("candidates") or failure_context.get("substring_hints") or []),
        "neighbor_tree": _format_neighbor_tree(failure_context),
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
        hooks.append(hook)
    return hooks
