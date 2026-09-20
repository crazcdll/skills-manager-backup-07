#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单 Case 报告构建（build_case）及其结论计算。"""
import json
import os

from report.data_collector import _read_skill_version, list_dir
from report.model import normalize_step_records
from report.schema import assertion_summary, summary
from report.steps import _note_report, _record_report, _stage_report, build_step


# 原始用例原文记录的 source 标记：仅作为无判定备注展示，不进时间线 raw_records。
_SOURCE_NOTE_KINDS = ("flow_source", "steps_input")


def _verdict_counts(reports):
    return {
        "total": len(reports),
        "pass": sum(1 for item in reports if item["ok"] == 1),
        "warn": sum(1 for item in reports if item["ok"] == 2),
        "fail": sum(1 for item in reports if item["ok"] == 0),
    }


def resolve_case_status(summary_status, steps_finalized, fail_count):
    if summary_status in ("failed", "blocked"):
        return summary_status
    if fail_count:
        return "failed"
    return "completed" if steps_finalized else summary_status


def _wall_clock_duration(case_stages, steps_exec_duration):
    """Case 真实墙钟耗时：优先累加 case_loop 阶段的 duration_ms（覆盖 AI 思考、
    参数组装、命令调度耗时，而不仅是 step 进程内部执行时间）；缺少阶段数据
    时回退到 step 耗时相加。
    """
    stage_total = sum(
        stage["duration_ms"] or 0
        for stage in case_stages
        if stage.get("layer") == "case_loop" and stage.get("duration_ms") is not None
    )
    return stage_total if stage_total > 0 else steps_exec_duration


def _report_missing_flow_source(manifest, context):
    """原始 Flow 原文缺失时上报诊断（case 日志与 manifest 均无内容）。"""
    from core.util.paths import FLOWS_DIR
    from core.audit.exception_reporter import report_exception
    flow_source = manifest.get("flow_source", "")
    flows_dir_exists = os.path.isdir(FLOWS_DIR)
    flows_dir_contents = list_dir(FLOWS_DIR) if flows_dir_exists else []
    flow_basename = os.path.basename(flow_source) if flow_source else ""
    report_exception(
        event="flow_content_empty",
        message="原始 Flow .md 原文缺失（case 日志与 manifest 均无内容）",
        category="script",
        severity="error",
        stage="build_report",
        extra={
            "flow_source": flow_source or "",
            "flow_source_name": manifest.get("flow_source_name", ""),
            "flow_source_basename_in_flows_dir": (
                flow_basename in flows_dir_contents if flow_basename else None
            ),
            "flow_content_in_manifest": bool(manifest.get("flow_content", "")),
            "flows_dir": FLOWS_DIR,
            "flows_dir_exists": flows_dir_exists,
            "flows_dir_contents": flows_dir_contents,
            "case_id": manifest.get("case_id", ""),
            "case_name": manifest.get("case_name", ""),
            "flow_name": context.get("meta", {}).get("flow_name", ""),
        },
    )


def build_case(manifest, context, records, images):
    case_id = str(manifest.get("case_id", ""))
    declared_steps = context.get("steps", [])
    normalized, finding_records, note_records = normalize_step_records(
        records, [step.get("sid") for step in declared_steps]
    )
    steps = [
        build_step(step, normalized[step.get("sid")], images)
        for step in declared_steps
    ]
    findings = [_record_report(record, images) for record in finding_records]
    # 步骤口径与独立发现口径分列：两者性质不同（步骤=声明的走查项，
    # findings=未绑定步骤的独立判定）。历史上混在同一个 total 里，
    # 导致「report 说 11 步、平台 payload 说 10 步」的口径矛盾。
    # total / pass / warn / fail 保留为「步骤 + 独立发现」同权合计（报告页总览用），
    # 步骤真实数量统一看 total_steps。
    step_values = [step["ok"] for step in steps if step["ok"] is not None]
    finding_values = [finding["ok"] for finding in findings]
    all_values = step_values + finding_values
    counts = summary(
        total=len(all_values),
        passed=sum(1 for value in all_values if value == 1),
        warned=sum(1 for value in all_values if value == 2),
        failed=sum(1 for value in all_values if value == 0),
    )
    case_index = manifest["index"]
    case_stages = [
        _stage_report(stage)
        for stage in context.get("sop", {}).get("stages", [])
        if stage.get("case_index") is None or stage.get("case_index") == case_index
    ]
    steps_exec_duration = sum(step["duration_ms"] or 0 for step in steps)
    total_duration = _wall_clock_duration(case_stages, steps_exec_duration)
    summary_status = next(
        (item.get("status") for item in context.get("cases_summary", [])
         if item.get("case_id") == manifest.get("case_id")),
        "pending",
    )
    steps_finalized = bool(steps) and all(
        step["status"] in ("completed", "failed", "skipped") for step in steps
    )
    case_status = resolve_case_status(summary_status, steps_finalized, counts["fail"])

    # 原始用例原文（Flow md / steps-input）由 case-init 在执行期直接写进本 case 的
    # steps.jsonl（source 字段标记）。报告只从日志记录读取 —— 不再按路径重查，
    # 路径变动/目录清理都不会丢内容。
    notes = []
    embedded = {}
    for record in note_records:
        src = record.get("source")
        if src in _SOURCE_NOTE_KINDS and src not in embedded:
            embedded[src] = record

    flow_note = embedded.get("flow_source")
    if flow_note:
        notes.append(_note_report(flow_note, images))
    else:
        # 原文由 case-init 随日志落盘；记录缺失即异常，上报诊断。
        _report_missing_flow_source(manifest, context)

    steps_note = embedded.get("steps_input")
    if steps_note:
        notes.append(_note_report(steps_note, images))

    notes.extend(
        _note_report(record, images) for record in note_records
        if record.get("source") not in _SOURCE_NOTE_KINDS
    )

    # ack --result 的人工结论：以前只写入 flow-context 却无任何消费方（静默丢失），
    # 这里落到 notes（无判定备注），保证 AI 通过 ack 写下的结论在报告中可追溯。
    ack_evidence = (context.get("evidence") or {}).get("ack_evidence") or {}
    for ack_key, payload in ack_evidence.items():
        notes.append({
            "sid": None,
            "source": "ack",
            "kind": "ui",
            "desc": f"门禁确认 {ack_key}",
            "ok": None,
            "ok_label": None,
            "status": "note",
            "timestamp": None,
            "duration_ms": None,
            "duration_ms_inferred": False,
            "screenshot": None,
            "screenshots": [],
            "note": payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
            "evidence": None,
        })

    assert_stats = assertion_summary(steps)

    # kind_stats 和 detail_stats 合并为一次遍历
    kind_stats = {"ui": 0, "api": 0, "track": 0}
    detail_stats = {"ui": {}, "api": {}, "track": {}}
    for s in steps:
        k = s.get("kind", "ui")
        if k in kind_stats:
            kind_stats[k] += 1

        if k == "ui":
            ok_label = s.get("ok_label", "unknown")
            detail_stats["ui"][ok_label] = detail_stats["ui"].get(ok_label, 0) + 1
        elif k == "api":
            meta = (s.get("evidence") or {}).get("metadata", {})
            code = str(meta.get("http_code") or "")
            prefix = code[:1] if code else "unknown"
            key = f"http_{prefix}xx"
            detail_stats["api"][key] = detail_stats["api"].get(key, 0) + 1
        elif k == "track":
            meta = (s.get("evidence") or {}).get("metadata", {})
            m = meta.get("matched")
            key = "matched" if m else "unmatched" if m is False else "unknown"
            detail_stats["track"][key] = detail_stats["track"].get(key, 0) + 1

    return {
        "case_id": case_id,
        "case_name": manifest.get("case_name", ""),
        "case_index": case_index,
        "status": case_status,
        "skill_version": _read_skill_version(),
        "landing_scheme": manifest.get("landing_scheme", ""),
        # timeline 在 build_run 中统一构建（合并所有数据源），此处仅保留 SOP 阶段
        "timeline": case_stages,
        "steps": steps,
        # raw_records 供时间线完整展示。原始用例原文已在 notes 中呈现，
        # 必须从 raw_records 剔除，否则同一份 md / steps-input 会在上报 payload 里重复两份。
        "raw_records": [r for r in records if r.get("source") not in _SOURCE_NOTE_KINDS],
        "findings": findings,
        "notes": notes,
        "summary": {
            **counts,
            "total_steps": len(step_values),
            "total_findings": len(finding_values),
            "findings": _verdict_counts(findings),
            "duration_ms": total_duration,
            "steps_exec_duration_ms": steps_exec_duration,
            "kind_counts": kind_stats,
            "detail_stats": detail_stats,
            "assert_results": assert_stats["results"],
            "assert_verdicts": assert_stats["verdicts"],
            # 需人工复核的断言数（AI 主观判定通过）——case 级供平台打标
            "assert_needs_review": assert_stats["needs_review"],
        },
    }
