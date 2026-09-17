#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-fail / skip-case CLI 命令：失败收口与跳过 case。
"""
from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path
from core.flow.flow_context import load_context
from core.flow.lifecycle import fail_stage
from core.flow.state import skip_current_case
from core.sop.on_fail import _get_on_fail_config


def _cmd_flow_fail(args):
    """flow-fail --stage <stage_id> --error <error_msg>

    SOP 阶段失败收口。
    """
    run_dir = resolve_case_path(args.dir)
    ctx = load_context(run_dir)
    if ctx is None:
        raise FlowStateError("FLOW-FAIL ERROR: flow-context.json 不存在，需先执行 flow-init")

    stage_id = args.stage
    error_msg = args.error

    stage = None
    for s in ctx.get("sop", {}).get("stages", []):
        if s.get("id") == stage_id:
            stage = s
            break

    on_fail_config = _get_on_fail_config(stage) if stage else {"policy": "abort"}
    generate_report = on_fail_config.get("generate_report", False)
    cleanup = on_fail_config.get("cleanup", False) or getattr(args, "cleanup", False)

    result = fail_stage(
        run_dir, stage_id, error_msg,
        generate_report=generate_report,
        cleanup=cleanup,
    )

    if not result.get("ok"):
        raise FlowStateError(f"FLOW-FAIL ERROR: {result.get('reason', '未知错误')}")

    if result.get("skipped_to_next"):
        print(f"FLOW-FAIL: 阶段 {stage_id} 失败，已跳到下一个 case")
        print(f"  异常原因: {error_msg}")
        print("  执行 python3 scripts/cli.py flow-next 获取下一个 case 的命令")
    elif result.get("best_effort"):
        print(f"FLOW-FAIL: 阶段 {stage_id} 失败（best_effort，不终止流程）")
        print(f"  异常原因: {error_msg}")
        print("  执行 python3 scripts/cli.py flow-next 获取下一阶段命令")
    else:
        print(f"FLOW-FAIL: 阶段 {stage_id} 失败已记录，流程已终止")
        print(f"  异常原因: {error_msg}")
        evidence = result.get("evidence") or {}
        evidence_state = evidence.get("state")
        if result.get("report_path"):
            print(f"  失败报告: file://{result['report_path']}")
        elif evidence_state == "archived_only":
            print(f"  失败报告: 未生成（尚未进入 Case），原始产物已归档: file://{evidence.get('detail', '')}")
        elif evidence_state == "failed":
            print(f"  失败报告: 生成失败（{evidence.get('detail', '')}）")
            print("  现场已保留在 .run/，请处理后手动执行 python3 scripts/cli.py gen-report")
        else:
            print("  失败报告: 未生成（未走终止路径）")
        if result.get("cleanup"):
            cu = result["cleanup"]
            if cu.get("ok"):
                print("  清理: 全部完成")
            else:
                failed = [d for d in cu.get("details", []) if not d.get("ok")]
                names = ", ".join(d.get("cmd", "?") for d in failed)
                print(f"  清理: 部分失败（{names}）")
            if cu.get("skipped_post_clean"):
                print(f"  ⚠️  未执行 post-clean: {cu['skipped_post_clean']}")
        print("  如需上报诊断原因（分析根因后调用）:")
        print(f"    python3 scripts/cli.py report-error --message \"{error_msg}\" --stage {stage_id} --category <infra|env|payload|device|app|script|assertion|unknown> --severity fatal")
        print("  如需重新开始: preflight-clean → 重新 flow-init")


def _cmd_skip_case(args):
    """skip-case --reason <原因>

    AI 主动结束当前 case：前置不成立、页面异常等继续走查已无意义的场景。
    """
    run_dir = resolve_case_path(args.dir)
    result = skip_current_case(run_dir, args.reason)

    if not result.get("ok"):
        raise FlowStateError(f"SKIP-CASE ERROR: {result.get('reason', '未知错误')}")

    print(f"SKIP-CASE: 当前 case 已结束（blocked）: {result.get('case_name', '')}")
    print(f"  原因: {args.reason}")
    print("  执行 python3 scripts/cli.py flow-next 进入 C4 生成报告并推进到下一个 case")