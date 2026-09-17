#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤调度层：命令构建、步骤状态更新、Hook 管理、偏移检测。

依赖关系：step_scheduler → flow_context → core.sop.hook_router（单向，无循环依赖）
"""
import json
import os
import sys
import time

from core.util.case_utils import current_case_workspace
from core.flow.flow_context import load_context, save_context
from core.sop.hook_router import (
    HOOKS_REQUIRE_STEPS_JSONL_RECORD,
    get_hooks_for_result,
)
from core.audit.runtime_audit import append_event
from core.util.records import StepRecord, SRC_EFFECT_VERIFIED


# ═══════════════════════════════════════════════════════════════════
# 步骤命令构建
# ═══════════════════════════════════════════════════════════════════

def _build_step_command(step, ctx):
    """从 step 定义构建 cli.py step 命令。非 UI 步骤只传 sid。

    asserts 数组转为 --asserts JSON 参数传递。
    """
    sid = step.get("sid", "")
    kind = step.get("kind", "ui")

    # 非 UI 步骤（api/track）：用 assert-text 作为保底 action
    # assert-text 在 _cmd_step 中不执行 UI 操作，
    # _dispatch_non_ui_step 已经按 flow-context 的 step_definition 分发到 API/Track 执行器
    # 注意：--sid 必须放在 action 之前（step 解析器层面），subparser 没有 --sid
    if kind != "ui":
        return f"python3 scripts/cli.py step --sid {sid} assert-text"

    parts = [
        "python3 scripts/cli.py step",
        f"--sid {sid}",
    ]

    action = step.get("action")
    if action:
        parts.append(f"{action}")
    action_arg = step.get("action_arg")
    if action_arg:
        parts.append(f'--action-arg "{action_arg}"')
    action_x = step.get("action_x")
    action_y = step.get("action_y")
    # tap/input-text 声明了 action_anchor 但还没坐标时，命令不完整
    if action in ("tap", "input-text") and step.get("action_anchor") and (action_x is None or action_y is None):
        return None
    if action_x is not None and action_y is not None:
        parts.append(f"--action-x {action_x}")
        parts.append(f"--action-y {action_y}")
    direction = step.get("direction")
    if direction and action in ("scroll-until", "scroll-edge"):
        parts.append(f"--direction {direction}")
    screenshot = step.get("screenshot")
    if screenshot:
        parts.append(f"--screenshot {screenshot}")
    # asserts 数组转为 JSON 参数
    asserts = step.get("asserts", [])
    if asserts:
        asserts_json = json.dumps(asserts, ensure_ascii=False)
        parts.append(f'--asserts {asserts_json}')
    step_type = step.get("step-type")
    if step_type:
        parts.append(f"--step-type {step_type}")
    desc = step.get("desc", "")
    if desc:
        parts.append(f'--desc "{desc}"')
    # page_ready: 操作后等待页面渲染稳定再截图/断言
    if step.get("page_ready", False):
        parts.append("--page-ready")

    return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════
# 步骤状态判定
# ═══════════════════════════════════════════════════════════════════

def _find_next_pending_step_index(ctx):
    """下一个未完成的步骤索引，全部完成时返回 len(steps)。"""
    steps = ctx.get("steps", [])
    for i, s in enumerate(steps):
        if not _is_step_done(s):
            return i
    return len(steps)


def _has_incomplete_required_hooks(step):
    """步骤是否有未完成的 required hooks。"""
    return any(h.get("required") and not h.get("completed")
               for h in step.get("hooks", []))


def _is_step_done(step):
    """status 为 completed/failed 且所有 required hooks 已完成即为 done。"""
    if step["status"] == "skipped":
        return True
    if step["status"] not in ("completed", "failed"):
        return False
    return not _has_incomplete_required_hooks(step)


# ═══════════════════════════════════════════════════════════════════
# Step 生命周期
# ═══════════════════════════════════════════════════════════════════

def set_step_started(run_dir, sid):
    ctx = load_context(run_dir)
    if ctx is None:
        return
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for step in ctx.get("steps", []):
        if step.get("sid") == sid:
            step["started_at"] = now
            break
    save_context(run_dir, ctx)


# ═══════════════════════════════════════════════════════════════════
# Step 执行后更新状态
# ═══════════════════════════════════════════════════════════════════

def _merge_step_hooks(prior_hooks, new_hooks):
    """合并新一轮执行生成的 hook 与步骤上已有的 hook。

    规则：
      - 新 hook 按 id 覆盖同 id 的旧 hook（同一步骤重新执行，同类 hook 取最新）；
      - 旧 hook 中「已 relay（携带 ai_result）」或「仍未完成的 required hook」保留。

    为什么不能直接 `step["hooks"] = new_hooks`（历史实现）：
      重跑同一步骤（如 scroll-until 换文案重试、tap-text 换锚点重试）时，新结果往往
      只携带少量/零个 hook，整体覆盖会把上一轮遗留的待处理 hook 冲掉，导致：
        ① AI 无法 relay-hook-result —— 报 `hook not found in sid`，
           reason hook 的 ai_result（如 TEXT_MISMATCH）进不了报告；
        ② PENDING 断言的 verify_text_assertion hook 消失，断言永久悬空
           （报告出现「步骤 PASS + 断言 pending」自相矛盾）；
        ③ 未完成的 required hook 消失后 _is_step_done 误判为已完成，流程被跳过。
    """
    prior_hooks = prior_hooks or []
    new_hooks = new_hooks or []
    new_ids = {h.get("id") for h in new_hooks}
    merged = []
    for h in prior_hooks:
        if h.get("id") in new_ids:
            continue
        if h.get("ai_result") or (h.get("required") and not h.get("completed")):
            merged.append(h)
    merged.extend(new_hooks)
    return merged


def update_step_result(run_dir, sid, ok_val, action_type, screenshot=None,
                       fail_reason=None, needs_ai_followup=False,
                       action_x=None, action_y=None, effect_desc="",
                       assertions=None, step_context=None):
    """更新 JSON 中对应步骤的状态、hooks 和断言摘要。

    ok_val: 1=PASS, None=PENDING（T2/T3 待 AI 判定）, 2=WARN, 0=FAIL
    assertions: dict 格式同 build_assertions_dict 输出，写入 flow-context 供 AI 消费
    step_context: dict | None — 步骤执行上下文，传给 get_hooks_for_result 统一路由
    """
    ctx = load_context(run_dir)
    if ctx is None:
        raise RuntimeError("flow-context.json 不存在，需先执行 flow-init")

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    matched = False
    for step in ctx["steps"]:
        if step["sid"] == sid:
            matched = True
            # PENDING（None）：既有断言数据待 AI 确认，状态为 pending
            if ok_val is None:
                step["status"] = "pending"
            else:
                step["status"] = "completed" if ok_val != 0 else "failed"
            step["ok"] = ok_val
            step["screenshot"] = screenshot
            step["completed_at"] = now
            step["action_type"] = action_type
            step["fail_reason"] = fail_reason
            # 回写运行时坐标
            if action_x is not None:
                step["action_x"] = action_x
            if action_y is not None:
                step["action_y"] = action_y
            if needs_ai_followup:
                step["needs_ai_followup"] = True
            # 写入断言摘要（供 AI 在 hook 阶段消费）
            if assertions:
                step["assertions"] = assertions
            # 生成 hook（统一入口：断言 + reason_code 路由均在此完成）
            hooks = get_hooks_for_result(ok_val, action_type, assertions=assertions,
                                          effect_desc=effect_desc,
                                          step_context=step_context)
            for h in hooks:
                h["completed"] = False
            # 与步骤已有 hook 合并而非整体覆盖：重跑同一步骤时整体覆盖会冲掉上一轮
            # 未完成/已留痕的 hook（详见 _merge_step_hooks 文档）。
            step["hooks"] = _merge_step_hooks(step.get("hooks"), hooks)
            break
    if not matched:
        print(f"  ⚠️ [update_step_result] 未找到 sid={sid!r} 对应的步骤，"
              f"共 {len(ctx.get('steps', []))} 个声明步骤", file=sys.stderr)

    ctx["current_step_index"] = _find_next_pending_step_index(ctx)
    save_context(run_dir, ctx)
    return ctx


def apply_followup_result(run_dir, sid, ok_val, assert_verdicts=None):
    """同步 step 的 status / ok，并把 AI 的逐断言判定回写到 step["assertions"]。

    ok_val: 1=PASS, None=PENDING, 2=WARN, 0=FAIL
    assert_verdicts: dict | None
        {"A1": {"result","verdict","actual","reason","targets"}}（override-step-result 传入）

    回写是必需的：step["assertions"] 只在步骤执行时写入（引擎收集到的初始快照），
    若 AI 判定只留在 followup 记录里，flow-status / flow-case-status 会一直显示 pending，
    AI 会误以为「判定没生效」而重复 override（污染 attempts / retry_count）。
    报告层从记录合并判定，flow-context 这一侧由本函数补齐。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return
    for step in ctx["steps"]:
        if step["sid"] == sid:
            step["ok"] = ok_val
            if ok_val is None:
                step["status"] = "pending"
            elif ok_val > 0:
                step["status"] = "completed"
            else:
                step["status"] = "failed"
            _apply_assertion_verdicts(step, assert_verdicts)
            break
    save_context(run_dir, ctx)


def _apply_assertion_verdicts(step, assert_verdicts):
    """把 AI 的逐断言判定合并进 step["assertions"]，并按断言修正步骤结论。

    护栏与报告层共用 compute_result_from_entries，且**单向**：
    断言含 result=fail 时步骤不得为 PASS（回退为 FAIL）；
    但不把 AI 显式给出的 FAIL 提升为 PASS —— 步骤可能因断言之外的原因失败
    （页面报错、数据异常等），结论权在 AI。
    """
    grouped = step.get("assertions")
    if not assert_verdicts or not grouped:
        return
    # 延迟导入：避免 core.flow 在 import 期反向依赖断言包（断言包会拉起策略与探针）
    from assertions.engine import apply_verdicts_grouped, compute_result_from_entries

    merged = apply_verdicts_grouped(grouped, assert_verdicts)
    step["assertions"] = merged
    if compute_result_from_entries(merged) == 0 and step.get("ok") != 0:
        step["ok"] = 0
        step["status"] = "failed"


def apply_hook_result(run_dir, sid, hook_id, ai_result):
    """AI 完成 Hook 后调用，将 ai_result（含 verdict/resolution/anomalies）写入钩子记录。

    ai_result: dict
        - verdict: "resolved" | "partially" | "unresolved"
        - resolution: str (如 "semantic_match", "viewport_scroll")
        - anomalies: list[dict] — 每项含 type/severity/detail
        - note: str (optional)

    Returns:
        (True, remaining_hooks) 或 (False, error_msg)
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return False, "flow-context.json not found"
    for step in ctx["steps"]:
        if step["sid"] == sid:
            found = False
            for hook in step.get("hooks", []):
                if hook["id"] == hook_id:
                    hook["ai_result"] = ai_result
                    found = True
            save_context(run_dir, ctx)
            if not found:
                return False, f"hook {hook_id} not found in sid {sid}"
            return True, [h for h in step.get("hooks", [])
                          if h.get("required") and not h.get("completed")]
    return False, f"sid {sid} not found"


# ═══════════════════════════════════════════════════════════════════
# steps.jsonl 查询
# ═══════════════════════════════════════════════════════════════════

def _steps_jsonl_any(run_dir, predicate):
    """检查 steps.jsonl 中是否存在满足 predicate 的记录。"""
    ctx = load_context(run_dir)
    if ctx is None:
        return False
    path = os.path.join(current_case_workspace(run_dir, ctx), "steps.jsonl")
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if predicate(rec):
                    return True
    except IOError:
        pass
    return False

def _steps_jsonl_has_sid(run_dir, sid):
    """检查 steps.jsonl 中是否存在指定 sid 的记录。"""
    return _steps_jsonl_any(run_dir, lambda rec: rec.get("sid") == sid)




# ═══════════════════════════════════════════════════════════════════
# Hook 管理
# ═══════════════════════════════════════════════════════════════════

def _append_effect_verified_record(run_dir, sid, step):
    """PENDING 自动修正为 PASS 时，向 steps.jsonl 追加一条记录。
    记录由引擎自动追加，无需 AI 手动调用 override-step-result。
    如有重复记录（即 steps.jsonl 中已有相同 sid 的 effect_verified），跳过。
    """
    if _steps_jsonl_any(run_dir, lambda rec: rec.get("sid") == sid and rec.get("_src") == "effect_verified"):
        return  # 防重：已有 effect_verified 记录，不再追加
    ctx = load_context(run_dir)
    if ctx is None:
        return
    case_ws = current_case_workspace(run_dir, ctx)
    record = StepRecord(
        sid=sid,
        src=SRC_EFFECT_VERIFIED,
        type=step.get("step-type", "interaction"),
        desc=step.get("desc", ""),
        ok=1,
        status="PASS",
        asserts=step.get("asserts", []),
    )
    try:
        record.append(case_ws)
    except (IOError, OSError):
        pass  # 追加失败不阻断主流程


def _resolve_effect_pending_step(ctx, sid):
    """检查步骤是否处于 PENDING 状态，返回 step 或 None。"""
    for step in ctx.get("steps", []):
        if step["sid"] == sid and step.get("ok") is None:
            return step
    return None


def _finalize_effect_pending_step(run_dir, ctx, sid, step):
    """将 PENDING 步骤修正为 PASS（双写 flow-context + steps.jsonl）。"""
    step["ok"] = 1
    step["status"] = "completed"
    step["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _append_effect_verified_record(run_dir, sid, step)


def _mark_hook_done_core(run_dir, ctx, step, hook_id):
    """Hook 完成标记：hook 完成 → 状态推进 → PENDING 修正。
    返回 (success, remaining) 或 (False, reason_str)。
    """
    if hook_id in HOOKS_REQUIRE_STEPS_JSONL_RECORD:
        if not _steps_jsonl_has_sid(run_dir, step["sid"]):
            return False, (
                f"steps.jsonl 中未找到 sid={step['sid']} 的记录 —— "
                f"标记 {hook_id} 前必须先调用 override-step-result 记录该步骤的最终结果"
            )
    for h in step.get("hooks", []):
        if h["id"] == hook_id and not h.get("completed"):
            h["completed"] = True
    remaining = [h for h in step.get("hooks", [])
                 if h.get("required") and not h.get("completed")]
    # 当所有 required hooks 完成时，自动推进步骤状态
    # 兼容 status=pending（PENDING 步骤）和 status=in_progress
    if not remaining and step.get("status") in ("in_progress", "pending"):
        step["status"] = "completed"
        step["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        # Ack-Hook 联动：PENDING → 自动修正为 PASS
        if step.get("ok") is None:
            _finalize_effect_pending_step(run_dir, ctx, step["sid"], step)
    save_context(run_dir, ctx)
    return True, remaining


def mark_hook_done(run_dir, sid, hook_id):
    """AI 完成一个 hook 操作后调用，标记为 completed。
    返回 (success, remaining_required_hooks) 或 (False, reason_str)。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return False, []

    for step in ctx["steps"]:
        if step["sid"] == sid:
            result = _mark_hook_done_core(run_dir, ctx, step, hook_id)
            # 追加审计事件（新增强化：不破坏原有逻辑）
            if result[0]:
                append_event(run_dir, "hook.completed",
                             {"sid": sid, "hook_id": hook_id,
                              "remaining": len(result[1]) if isinstance(result[1], list) else 0})
            return result

    return False, []


# ═══════════════════════════════════════════════════════════════════
# 偏移检测
# ═══════════════════════════════════════════════════════════════════

def check_drift(run_dir, current_sid):
    """检查上一步是否有未完成的 hooks。
    返回 (warning_msg, prior_sid, incomplete_hooks) 或 (None, None, [])。
    """
    ctx = load_context(run_dir)
    if ctx is None:
        return None, None, []

    steps = ctx.get("steps", [])
    if not steps:
        return None, None, []

    current_idx = None
    for i, s in enumerate(steps):
        if s["sid"] == current_sid:
            current_idx = i
            break

    if current_idx is None or current_idx == 0:
        return None, None, []

    prev = steps[current_idx - 1]
    if prev["sid"] == current_sid:
        return None, None, []

    prev_status = prev.get("status", "pending")
    if prev_status in ("pending", "skipped"):
        return None, None, []

    incomplete = [h for h in prev.get("hooks", [])
                  if h.get("required") and not h.get("completed")]

    if not incomplete:
        return None, None, []

    hook_names = ", ".join(h["id"] for h in incomplete)
    warning = (f"上一步 [{prev['sid']}] ({prev.get('desc', '')[:30]}) "
               f"有 {len(incomplete)} 个未完成的操作: {hook_names}")
    return warning, prev["sid"], incomplete
