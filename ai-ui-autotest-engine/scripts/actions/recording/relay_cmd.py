"""relay-hook-result 命令：把 AI 的 Hook 执行结论写回 flow-context。"""

import json
import sys

from core.errors import FlowStateError, UsageError
from core.util.case_utils import resolve_case_path
from core.flow.step_scheduler import apply_hook_result as fc_apply_hook_result


def _cmd_relay_hook_result(args):
    """relay-hook-result: AI 完成 Hook 后将 ai_result 回写到 flow-context。

    ai_result 包含 verdict/resolution/anomalies，用于报告展示。
    """
    root_dir = resolve_case_path(args.dir)
    sid = getattr(args, "sid", None)
    hook_id = getattr(args, "hook_id", None)
    if not sid or not hook_id:
        raise UsageError("RELAY-HOOK-RESULT ABORT: --sid 和 --hook-id 是必填参数")

    ai_result = {
        "verdict": getattr(args, "verdict", "unresolved"),
        "resolution": getattr(args, "resolution", ""),
        "anomalies": [],
    }
    anomalies_str = getattr(args, "anomalies", None)
    if anomalies_str:
        try:
            ai_result["anomalies"] = json.loads(anomalies_str)
        except json.JSONDecodeError as e:
            print(f"RELAY-HOOK-RESULT WARN: --anomalies JSON 解析失败: {e}", file=sys.stderr)

    note = getattr(args, "note", None)
    if note:
        ai_result["note"] = note

    success, result = fc_apply_hook_result(root_dir, sid, hook_id, ai_result)
    if success:
        remaining = len(result) if isinstance(result, list) else 0
        print(f"RELAY-HOOK-RESULT: ai_result 已写入 (sid={sid}, hook={hook_id})，"
              f"剩余 {remaining} 个待完成 hook")
    else:
        raise FlowStateError(f"RELAY-HOOK-RESULT FAIL: {result}")