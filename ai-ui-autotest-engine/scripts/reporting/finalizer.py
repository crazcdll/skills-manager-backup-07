"""批次终结服务：统一构建、归档和落盘最终报告。"""

import json
import os
from datetime import datetime

from shared.json_utils import write_json_atomic, read_json
from shared.output_guard import redact_obj, secrets_from
from reporting.run_report import build_run
from shared.observability.runtime_audit import archive_run

def finalize_run(context, run_dir, cases, audit_events, elapsed_ms, output_dir, run_status):
    """产出一次运行的唯一最终报告，并在归档完成后写入最终审计快照。"""
    import sys
    try:
        archive_dir = archive_run(run_dir, output_dir)
    except Exception as e:
        sys.stderr.write(f"[finalizer] archive_run 归档失败: {e}\n")
        raise
    try:
        run = build_run(
            context=context,
            cases=cases,
            audit_events=audit_events,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_ms_value=elapsed_ms,
        )
    except Exception as e:
        sys.stderr.write(f"[finalizer] build_run 构建报告失败: {e}\n")
        raise
    run["run_status"] = run_status
    run["archive_dir"] = archive_dir
    # 缺失 Case 在这里统一计算一次：report.json 与 meta.json 必须同源，
    # 否则读端（控制台 / 平台）会看到两份不一致的汇总。
    run["batch_summary"]["missing_cases"] = _missing_cases(context, cases)
    # 报告是「离开运行态」的产物：统一脱敏后再落盘（归档已在 archive_run 内脱敏）
    secrets = secrets_from(context.get("env") or {})
    run = redact_obj(run, secrets)
    report_path = os.path.join(output_dir, "report.json")
    os.makedirs(output_dir, exist_ok=True)
    try:
        write_json_atomic(report_path, run)
    except Exception as e:
        sys.stderr.write(f"[finalizer] 写入批次 report.json 失败: {e}\n")
        raise
    _write_run_meta(context, run, run_status, archive_dir, output_dir)
    for manifest in context.get("cases_manifest", []):
        case_obj = next((c for c in cases if str(c.get("case_id")) == str(manifest.get("case_id"))), None)
        if case_obj is None:
            continue
        case_report_path = os.path.join(manifest["output_dir"], "report.json")
        if not os.path.isfile(case_report_path):
            sys.stderr.write(f"[finalizer] 跳过回写 case report.json 不存在: {case_report_path}\n")
            continue
        try:
            case_report = read_json(case_report_path, default={})
            case_report["case"] = redact_obj(case_obj, secrets)
            write_json_atomic(case_report_path, case_report)
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            sys.stderr.write(f"[finalizer] case report 回写失败 ({manifest.get('case_id')}): {exc}\n")
            context.setdefault("errors", []).append(
                {"stage": "finalize_case_writeback", "case_id": manifest.get("case_id"), "error": str(exc)}
            )
    return run, report_path


def _missing_cases(context, cases):
    """manifest 声明了、但本次没有有效报告的 Case（唯一计算入口）。"""
    reported = {str(case.get("case_id")) for case in cases if isinstance(case, dict)}
    return [
        {"case_id": item.get("case_id", ""), "case_name": item.get("case_name", "")}
        for item in context.get("cases_manifest", [])
        if str(item.get("case_id", "")) not in reported
    ]


def _write_run_meta(context, run, run_status, archive_dir, output_dir):
    """目录级索引：读端无需解析目录名即可拿到批次 / run / 状态（稳定契约）。"""
    import sys

    meta = context.get("meta") or {}
    payload = {
        "schema_version": 2,
        "layout": "reports/<batch>/<run>",
        "batch_id": meta.get("batch_id", ""),
        "run_id": os.path.basename(output_dir),
        "run_name": meta.get("run_name", ""),
        "report_id": run.get("id", ""),
        "external_report_id": os.environ.get("AI_UITEST_REPORT_ID", "").strip(),
        "title": run.get("title", ""),
        "run_status": run_status,
        "timestamp": run.get("timestamp", ""),
        "duration_ms": run.get("duration_ms"),
        "device": run.get("device", ""),
        "platform": run.get("platform", ""),
        "app": run.get("app", ""),
        "mis": run.get("mis", ""),
        "skill_version": run.get("skill_version", ""),
        "archive_dir": archive_dir,
        "batch_summary": run.get("batch_summary") or {},
    }
    try:
        write_json_atomic(os.path.join(output_dir, "meta.json"), payload)
    except OSError as exc:
        sys.stderr.write(f"[finalizer] 写入 meta.json 失败: {exc}\n")
