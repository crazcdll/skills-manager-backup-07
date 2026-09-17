#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""record-event CLI 命令：向 run-events.jsonl 记录事件。
"""
import json as _json

from core.util.case_utils import resolve_case_path
from core.audit.runtime_audit import append_event, register_evidence


def _cmd_record_event(args):
    """record-event: 向 run-events.jsonl 记录一条事件。

    传了 --evidence-type 即按 evidence 格式记录，否则按普通事件格式。
    """
    from core.util.case_utils import resolve_case_path
    run_dir = resolve_case_path(args.dir)
    details = {}
    if args.details:
        try:
            details = _json.loads(args.details)
        except _json.JSONDecodeError:
            print(f"record-event WARNING: --details JSON 解析失败，将作为纯文本记录")
            details["raw"] = args.details
    if getattr(args, "screenshots", None):
        details["screenshots"] = args.screenshots
    severity = getattr(args, "severity", "info")
    ev_type = getattr(args, "ev_type", None)
    method = getattr(args, "method", None)
    stage = getattr(args, "stage", "")
    case_index = getattr(args, "case_index", None)
    if ev_type or method:
        register_evidence(
            run_dir, ev_type or "", method or "",
            getattr(args, "status", "recorded"),
            artifacts=getattr(args, "artifacts", None),
            details=details, stage=stage, case_index=case_index,
        )
    else:
        if case_index is not None:
            details["case_index"] = case_index
        append_event(run_dir, args.event, details, severity=severity)
    print(f"RECORD-EVENT OK: {args.event}")