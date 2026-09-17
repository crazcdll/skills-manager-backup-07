#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ack CLI 命令：通用门禁确认。
"""
import json

from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path
from core.flow.state import ack_generic


def _cmd_ack(args):
    """ack --key <key> [--result <json>]

    通用门禁确认命令：完成某个 stage 的 requires_ack 声明动作后调用。
    """
    run_dir = resolve_case_path(args.dir)
    result_data = None
    if getattr(args, "result", None):
        try:
            result_data = json.loads(args.result)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ACK WARNING: --result JSON 解析失败: {e}，将忽略 result")
    result = ack_generic(run_dir, args.key, result_data=result_data)

    if not result.get("ok"):
        raise FlowStateError(f"ACK FAIL: {result.get('detail', result.get('reason', ''))}")

    print(f"ACK OK: 已记录 {result.get('key', '')} 完成证据")

    hook_info = result.get("hook_auto_completed")
    if hook_info:
        if "error" in hook_info:
            print(f"  ⚠️ Hook 联动警告: verify_effect ({hook_info['sid']}) 自动完成失败 — {hook_info['error']}")
            print(f"     请手动执行: python3 scripts/cli.py flow-next --done-hooks verify_effect")
        else:
            print(f"  ✅ Hook 联动: verify_effect ({hook_info['sid']}) 已自动完成，步骤 ok 值已修正为 PASS")
            print(f"     （无需再调 flow-next --done-hooks，直接 flow-advance 即可）")