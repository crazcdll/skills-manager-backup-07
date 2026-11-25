#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-finalize CLI 命令：终结阶段。

报告在 C5_report 已逐个增量上报，这里只做 **Close**（补传未成功的 Case + 回写最终
run_status + 归档），不再重发全量 cases。
"""
from aitest.shared.errors import FlowStateError
from aitest.shared.case_utils import resolve_case_path
from aitest.execution.engine.flow.lifecycle import finalize_flow


def _cmd_flow_finalize(args):
    """flow-finalize

    终结阶段专用：标记当前阶段完成、current_stage=done、收口并上传最终报告。
    """
    run_dir = resolve_case_path(args.dir)
    result = finalize_flow(run_dir)

    if not result.get("ok"):
        raise FlowStateError(f"FLOW-FINALIZE FAIL: {result.get('reason', '未知错误')}")

    if result.get("skipped"):
        print(f"FLOW-FINALIZE SKIP: current_stage=aborted，报告已由 <入口> flow-fail 生成")
        return

    print(f"FLOW-FINALIZE OK: 阶段 {result.get('stage_id', '?')} 已标记完成，current_stage=done")

    try:
        from aitest.reporting.gen_report import generate_batch_report
        class _BatchArgs:
            no_db = False
            output_dir = None
        generate_batch_report(_BatchArgs())
    except Exception as e:
        print(f"  批次收口失败（不影响终结）: {e}")