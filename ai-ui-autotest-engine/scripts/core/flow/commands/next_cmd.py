#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-next / flow-advance CLI 命令。

职责：解析 CLI 参数 → 获取下一步动作 → 格式化输出。
"""
from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path
from core.flow.flow_context import load_context
from core.flow.lifecycle import advance_stage
from core.flow.state import get_next_action
from core.flow.step_scheduler import _ASSERT_FIELDS_HOOKS, mark_hook_done


def _dispatch_next_action(run_dir, label):
    """获取并输出下一步命令，共享给 flow-next 和 flow-advance。"""
    skip_count = 0
    while True:
        result = get_next_action(run_dir)
        action = result.get("action", "")

        if action == "error":
            print(f"{label} ERROR: {result.get('message', '')}")
            return

        if action == "done":
            print(f"{label}: 全流程已完成")
            return

        if action == "aborted":
            print(f"{label} ABORTED: {result.get('message', '')}")
            errors = result.get("errors", [])
            if errors:
                print("  异常记录:")
                for e in errors[-5:]:
                    print(f"    [{e.get('stage', '?')}] {e.get('error', '')}")
            print("  流程已终止，不再执行后续步骤。如需重新开始，请执行 preflight-clean 后重新 flow-init。")
            return

        if action == "sop_advance":
            if label == "FLOW-ADVANCE":
                stage = advance_stage(run_dir)
                if stage is None:
                    print(f"{label}: 全流程已完成")
                    return
                newly_skipped = stage.pop("_advance_skipped", [])
                if newly_skipped:
                    skip_names = ", ".join(f"{s['id']}({s.get('desc', '')[:20]})" for s in newly_skipped)
                    print(f"{label}: 连续推进到 {stage['id']}: {stage.get('desc', '')}（自动跳过 {len(newly_skipped)} 个阶段: {skip_names}）")
                else:
                    print(f"{label}: 连续推进到 {stage['id']}: {stage.get('desc', '')}")
                continue
            print(f"{label}: {result.get('message', '')}")
            print("  执行 python3 scripts/cli.py flow-advance 推进到下一阶段")
            return

        if action == "sop_skip":
            print(f"{label}: {result.get('message', '')}")
            stage = advance_stage(run_dir)
            if stage is None:
                print(f"{label}: 全流程已完成")
                return
            skip_count += 1
            if skip_count > 20:
                print(f"{label} ERROR: 连续跳过超过 20 个阶段，疑似死循环")
                return
            continue

        if action == "step_continue":
            print(f"{label}: {result.get('message', '')}")
            print("  执行 python3 scripts/cli.py flow-next 查看下一步")
            return

        if action == "complete_hooks":
            print(f"{label}: {result.get('message', '')}")
            step_sid = result.get("step_sid", "<sid>")
            hooks = result.get("hooks", [])
            first_hook = hooks[0] if hooks else None
            if first_hook:
                hid = first_hook["id"]
                desc = first_hook.get("desc", "")
                print(f"  hook [TODO] {hid}: {desc}")
                print(f"  详情: python3 scripts/cli.py hook-info --hook-id {hid} --sid {step_sid}")
                if hid in _ASSERT_FIELDS_HOOKS:
                    print(f"  ⚠️ 该 hook 必须经 assert-fields 提交结论（埋点多候选用 --picked <序号> 消歧），"
                          f"不能 flow-next --done-hooks 空标记")
                else:
                    print(f"  标记完成: python3 scripts/cli.py flow-next --done-hooks {hid}")
                if len(hooks) > 1:
                    remaining_names = ", ".join(h["id"] for h in hooks[1:])
                    print(f"  ⏩ 后续 {len(hooks)-1} 个 hook 待完成: {remaining_names}")
            else:
                print(f"  无待完成 hook，直接 flow-advance 推进")
            return

        if action == "locate_first":
            print(f"{label}: {result.get('message', '')}")
            print(f"  第一步，查坐标: {result.get('locate_command', '')}")
            print(f"  第二步，读元素树确认坐标后执行: {result.get('next_command_template', '')}")
            return

        if action == "execute_step":
            print(f"{label}: 执行步骤 {result.get('sid', '?')}: {result.get('desc', '')}")
            _asserts = result.get("asserts", [])
            if _asserts:
                kinds_summary = {}
                for a in _asserts:
                    if not isinstance(a, dict):
                        continue
                    # 注意变量名不要用 label：label 是本函数的入参（FLOW-NEXT: 前缀）
                    kind_label = a.get("kind") or "text"
                    if kind_label == "text":
                        kind_label = f"text/{a.get('match') or 'present'}"
                    kinds_summary[kind_label] = kinds_summary.get(kind_label, 0) + 1
                summary_parts = [f"{cnt}×{t}" for t, cnt in kinds_summary.items()]
                print(f"  [ASSERTS] {' · '.join(summary_parts)}（引擎收集数据，AI 在 hook 阶段做断言）")
            else:
                print(f"  [ASSERTS] 无断言，执行后直接 PASS（仅依赖截图证据）")
            pre_hooks = result.get("pre_hooks", [])
            if pre_hooks:
                pre_names = ", ".join(h["id"] for h in pre_hooks)
                print(f"  PRE-STEP auto: {pre_names}")
            print(f"  CMD: {result.get('command', '')}")
            print("  执行后调 flow-next 查看待完成 hooks")
            return

        if action == "execute_sop_stage":
            print(f"{label}: 执行阶段 {result.get('stage_id', '?')}: {result.get('stage_desc', '')}")
            for cmd in result.get("commands", []):
                print(f"  CMD: {cmd}")
            markers = result.get("success_markers", [])
            if markers:
                print(f"  成功标志: {', '.join(markers)}")
            on_fail = result.get("on_fail", "pause")
            print(f"  失败策略: {on_fail}")
            if result.get("needs_visual_check"):
                print(f"  [NEEDS_VISUAL_CHECK] {result.get('visual_check_hint', '')}")
            if result.get("notes"):
                print(f"  [NOTE] {result['notes']}")
            acks = result.get("requires_ack", [])
            if acks:
                for a in acks:
                    print(f"  [ACK_REQUIRED] 完成后执行: python3 scripts/cli.py ack --key {a['key']}")
                    if a.get("hint"):
                        print(f"    说明: {a['hint']}")
            if result.get("terminal"):
                print("  该阶段为终结阶段，执行完所有命令后流程即结束（无需推进）")
            else:
                print("  完成后执行 python3 scripts/cli.py flow-advance 推进到下一阶段")
            return

        print(f"{label}: 未知 action {action}")
        return


def _cmd_flow_next(args):
    """flow-next [--done-hooks hook_id]

    获取当前阶段内下一步命令，不推进 SOP 阶段。
    --done-hooks 标记当前步骤的单个 hook 完成。
    """
    run_dir = resolve_case_path(args.dir)

    done_hooks = getattr(args, "done_hooks", None)
    if done_hooks:
        hook_ids = [h.strip() for h in done_hooks.split(",") if h.strip()]
        if len(hook_ids) > 1:
            raise FlowStateError(
                f"FLOW-NEXT HOOK-DONE REJECTED: 一次只能标记一个 hook（收到 {len(hook_ids)} 个: {', '.join(hook_ids)}）；"
                f"请逐个完成: 先完成第一个 hook 后，flow-next 会自动展示下一个"
            )
        ctx = load_context(run_dir)
        if ctx is None:
            print("FLOW-NEXT ERROR: flow-context.json 不存在")
            return
        target_sid = None
        for s in ctx.get("steps", []):
            if s.get("status") in ("completed", "failed", "in_progress", "pending"):
                if any(h.get("required") and not h.get("completed") for h in s.get("hooks", [])):
                    target_sid = s["sid"]
                    break
        if target_sid is None:
            print("FLOW-NEXT: 无需标记 hooks（未找到有未完成 hooks 的步骤），直接获取下一步")
        else:
            hook_id = hook_ids[0]
            success, remaining = mark_hook_done(run_dir, target_sid, hook_id)
            if not success:
                if isinstance(remaining, str):
                    raise FlowStateError(f"FLOW-NEXT HOOK-DONE REJECTED: {remaining}")
                raise FlowStateError(f"FLOW-NEXT HOOK-DONE FAIL: sid={target_sid} hook={hook_id} 未找到")
            if remaining:
                names = ", ".join(h["id"] for h in remaining)
                print(f"FLOW-NEXT: hook {hook_id} marked completed（剩余 {len(remaining)}: {names}）")
            else:
                print(f"FLOW-NEXT: hook {hook_id} marked completed — 所有 required hooks 已完成")

    _dispatch_next_action(run_dir, "FLOW-NEXT")


def _cmd_flow_advance(args):
    """flow-advance [--force]

    标记当前 SOP 阶段完成并推进到下一阶段。
    --force 跳过完成证据校验强制推进。
    """
    run_dir = resolve_case_path(args.dir)
    force = getattr(args, "force", False)
    stage = advance_stage(run_dir, force=force)
    if isinstance(stage, dict) and stage.get("error") == "evidence_missing":
        raise FlowStateError(
            f"FLOW-ADVANCE REJECTED: 阶段 {stage['stage_id']} 未通过 completion_check；"
            f"原因: {stage['reason']}；"
            "请先执行命令确认成功后再用 python3 scripts/cli.py flow-advance 推进。"
        )
    if stage is not None:
        newly_skipped = stage.pop("_advance_skipped", [])
        if newly_skipped:
            skip_names = ", ".join(f"{s['id']}({s.get('desc', '')[:20]})" for s in newly_skipped)
            print(f"FLOW-ADVANCE: 推进到 {stage['id']}: {stage.get('desc', '')}（自动跳过 {len(newly_skipped)} 个阶段: {skip_names}）")
        else:
            print(f"FLOW-ADVANCE: 推进到 {stage['id']}: {stage.get('desc', '')}")
    else:
        print("FLOW-ADVANCE: 全流程已完成")
        return

    _dispatch_next_action(run_dir, "FLOW-ADVANCE")