"""log-record 命令：记录判定结果到 steps.jsonl。"""

from core.errors import FlowStateError
from core.util.case_utils import resolve_case_path, current_case_workspace
from core.flow.flow_context import load_context as fc_load
from core.util.records import StepRecord, SRC_STEP, SRC_NOTE, SHOT_AUTO
from actions.assertion_utils import _resolve_step_ok
from actions.recording.common import (
    _resolve_duration, _validate_screenshot_reference,
    _build_failure_analysis_from_args, _auto_capture_screenshot,
    _report_step_binding, _declared_sids,
    STEP_OK_STATUS, NOTE_STATUS,
)


def _cmd_log_record(args):
    """log-record 命令入口。"""
    root_dir = resolve_case_path(args.dir)
    flow_context = fc_load(root_dir)
    if flow_context is None:
        raise FlowStateError("LOG ABORT: flow-context.json 不存在")
    case_workspace = current_case_workspace(root_dir, flow_context)

    sid = getattr(args, "sid", None)
    log_type = getattr(args, "log_type", "misc") or "misc"
    desc = getattr(args, "desc", "")
    note = getattr(args, "note", "") or ""
    al = getattr(args, "al", None)

    # 只记备注、不做判定：给了 --note 但没有任何判定开关。
    # 用于承载「action 文案口径差异」这类必须留痕、但不能算失败也不能算新通过的结论。
    # 这条记录 ok=None，报告层归入 annotations/notes，不参与统计。
    note_only = bool(note) and not (
        getattr(args, "passed", False)
        or getattr(args, "failed", False)
        or getattr(args, "ok", None) is not None
    )

    ok = _resolve_step_ok(args, allow_none=note_only)
    status_label = NOTE_STATUS if note_only else STEP_OK_STATUS.get(ok, "❌ FAIL")
    duration, _ = _resolve_duration(args, case_workspace)

    fa = _build_failure_analysis_from_args(args)
    img_name = _auto_capture_screenshot(args, case_workspace)
    _validate_screenshot_reference(img_name, case_workspace)

    declared_sids = _declared_sids(flow_context)

    # ── 统一记录契约（StepRecord）────────────────────────────
    record = StepRecord(
        sid=sid or "",
        # note 记录必须用 SRC_NOTE：SRC_STEP 属于执行桶，ok=None 会被当成
        # 步骤的新一条执行记录并抢占终态结论（把已完成的步骤打回 pending）。
        src=SRC_NOTE if note_only else SRC_STEP,
        type=log_type,
        desc=desc,
        ok=ok,
        status=status_label,
        ms=duration,
        note=note,
        failure=fa,
        extra={"al": al},
    )
    record.shot(img_name, label="日志截图", kind=SHOT_AUTO)
    record.append(case_workspace)

    # 输出摘要
    sid_info = f" [{sid}]" if sid else ""
    print(f"LOG-RECORD{sid_info}: {desc} → {status_label} ({duration}ms)")
    if note_only:
        scope = "绑定步骤的 annotations" if sid else "Case notes"
        print(f"  ℹ️  无判定备注：不计入通过/失败统计（作为{scope}展示）")
    elif sid and sid not in declared_sids:
        print(f"  ⚠️  SID '{sid}' 不在 flow-context 的声明步骤中，将作为独立 finding 计入统计")
    _report_step_binding(sid, "log-record", log_type)
