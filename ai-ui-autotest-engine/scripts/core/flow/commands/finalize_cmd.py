#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flow-finalize CLI 命令：终结阶段。
"""
import subprocess

from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path
from core.util.paths import SKILL_DIR
from core.flow.lifecycle import finalize_flow


def _cmd_flow_finalize(args):
    """flow-finalize

    终结阶段专用：标记当前阶段完成、current_stage=done、生成并上传最终报告。
    """
    run_dir = resolve_case_path(args.dir)
    result = finalize_flow(run_dir)

    if not result.get("ok"):
        raise FlowStateError(f"FLOW-FINALIZE FAIL: {result.get('reason', '未知错误')}")

    if result.get("skipped"):
        print(f"FLOW-FINALIZE SKIP: current_stage=aborted，报告已由 python3 scripts/cli.py flow-fail 生成")
        return

    print(f"FLOW-FINALIZE OK: 阶段 {result.get('stage_id', '?')} 已标记完成，current_stage=done")

    try:
        gen_result = subprocess.run(
            ["python3", "scripts/cli.py", "gen-report"],
            capture_output=True, text=True, timeout=60,
            cwd=SKILL_DIR,
        )
        if gen_result.returncode == 0:
            if gen_result.stdout.strip():
                print(gen_result.stdout.strip())
        else:
            print(f"  报告生成失败（不影响终结）: {gen_result.stderr.strip()}")
            if gen_result.stdout.strip():
                print(gen_result.stdout.strip())
    except Exception as e:
        print(f"  报告生成异常（不影响终结）: {e}")

    try:
        from report.gen_report import generate_batch_report
        class _BatchArgs:
            no_db = False
            output_dir = None
        generate_batch_report(_BatchArgs())
    except Exception as e:
        print(f"  批次聚合报告生成失败（不影响终结）: {e}")