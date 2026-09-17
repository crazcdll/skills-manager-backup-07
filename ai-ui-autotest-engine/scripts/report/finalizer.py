"""批次终结服务：统一构建、归档和落盘最终报告。"""

import json
import os
from datetime import datetime

from core.util.json_utils import write_json_atomic, read_json
from report.run_report import build_run
from core.audit.runtime_audit import archive_run

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
    report_path = os.path.join(output_dir, "report.json")
    os.makedirs(output_dir, exist_ok=True)
    try:
        write_json_atomic(report_path, run)
    except Exception as e:
        sys.stderr.write(f"[finalizer] 写入批次 report.json 失败: {e}\n")
        raise
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
            case_report["case"] = case_obj
            write_json_atomic(case_report_path, case_report)
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            sys.stderr.write(f"[finalizer] case report 回写失败 ({manifest.get('case_id')}): {exc}\n")
            context.setdefault("errors", []).append(
                {"stage": "finalize_case_writeback", "case_id": manifest.get("case_id"), "error": str(exc)}
            )
    return run, report_path
