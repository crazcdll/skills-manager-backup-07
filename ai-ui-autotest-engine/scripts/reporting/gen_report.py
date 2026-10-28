#!/usr/bin/env python3
import json
import os
import time

from shared.case_utils import current_case_workspace, resolve_case_path
from shared.json_utils import write_json_atomic, read_json
from shared.output_guard import redact_obj, secrets_from
from shared.paths import get_active_run
from reporting.case_report import build_case
from reporting.data_collector import load_audit, load_case_data
from reporting.finalizer import finalize_run
from reporting.transport import REPORT_PORTAL_BASE, fetch_s3_config, insert_report, upload_images
from execution.engine.flow.flow_context import load_context


def _active_context():
    case_name = get_active_run()
    if not case_name:
        raise RuntimeError("未设置 active_run")
    run_dir = resolve_case_path(case_name)
    context = load_context(run_dir)
    if context is None:
        raise RuntimeError(f"flow-context.json 不存在: {run_dir}")
    return run_dir, context


def _elapsed_ms(context):
    start = context.get("meta", {}).get("run_start_ts")
    if isinstance(start, (int, float)):
        return max(0, int((time.time() - start) * 1000))
    return None


def _case_report(context, run_dir, output_dir, s3):
    current = context.get("current_case", {})
    case_index = current.get("index")
    manifest = next((item for item in context.get("cases_manifest", []) if item.get("index") == case_index), None)
    if manifest is None:
        raise RuntimeError(f"未找到当前 Case 清单: index={case_index}")
    workspace = current_case_workspace(run_dir, context)
    records = load_case_data(workspace)
    images = upload_images(
        s3=s3,
        case_workspace=workspace,
        output_dir=output_dir,
        run_id=context["meta"]["batch_run_id"],
        case_tag=manifest["case_tag"],
    )
    case = build_case(
        manifest=manifest,
        context=context,
        records=records,
        images=images,
    )
    report = {
        "report_type": "case",
        "run_id": context["meta"]["batch_run_id"],
        "case": redact_obj(case, secrets_from(context.get("env") or {})),
    }
    write_json_atomic(os.path.join(output_dir, "report.json"), report)
    return report


def generate_case_report(args):
    run_dir, context = _active_context()
    output_dir = args.output_dir or context.get("current_case", {}).get("output_dir")
    if not output_dir:
        raise RuntimeError("当前 Case 缺少 output_dir")

    s3 = fetch_s3_config()
    report = _case_report(context, run_dir, output_dir, s3)
    case = report["case"]
    case_path = os.path.join(output_dir, "report.json")
    print(f"  ✅ Case 报告已生成: {case_path}")
    print(f"  📊 {case['case_name']} · 步骤 {case['summary']['total']} · 通过 {case['summary']['pass']} · 警告 {case['summary']['warn']} · 失败 {case['summary']['fail']}")

    stage = context.get("sop", {}).get("current_stage")
    if stage == "aborted":
        # 标题在 build_run 阶段就要带上，meta.json 才能与 report.json 一致
        context["meta"]["flow_name"] = f"[环境准备失败] {context['meta'].get('flow_name', '')}"
        # 缺失 Case 由 finalizer 统一计算并写入 report.json / meta.json，此处不再二次回写
        run, report_path = finalize_run(
            context=context,
            run_dir=run_dir,
            cases=[case],
            audit_events=load_audit(run_dir),
            elapsed_ms=_elapsed_ms(context),
            output_dir=context["meta"]["batch_output_dir"],
            run_status="aborted",
        )
        if not getattr(args, 'no_db', False):
            insert_report(run)
        print(f"  📄 report.json: file://{report_path}")
        return

    # 批次聚合报告由 flow-finalize 统一生成，C4 只做本地 Case 报告
    # 提前终止（aborted）时仍需生成批次报告用于入库（已在上面处理）


def _load_case_reports(context):
    cases = []
    missing = []
    for manifest in context.get("cases_manifest", []):
        path = os.path.join(manifest["output_dir"], "report.json")
        payload = read_json(path)
        case = payload.get("case")
        if (
            payload.get("report_type") != "case"
            or payload.get("run_id") != context.get("meta", {}).get("batch_run_id")
            or not isinstance(case, dict)
            or case.get("case_id") != str(manifest.get("case_id", ""))
        ):
            missing.append({"case_id": manifest.get("case_id", ""), "case_name": manifest.get("case_name", ""), "reason": "report_missing_or_invalid"})
            continue
        cases.append(case)
    return cases, missing


def generate_batch_report(args):
    run_dir, context = _active_context()
    return _generate_batch_report(args, run_dir, context)


def _generate_batch_report(args, run_dir, context):
    cases, missing = _load_case_reports(context)
    if not cases:
        raise RuntimeError("没有可用的 Case 报告")
    run, report_path = finalize_run(
        context=context,
        run_dir=run_dir,
        cases=cases,
        audit_events=load_audit(run_dir),
        elapsed_ms=_elapsed_ms(context),
        output_dir=context["meta"]["batch_output_dir"],
        run_status="complete" if not missing else "incomplete",
    )
    if not args.no_db:
        insert_report(run)
    print(f"  ✅ 聚合报告已生成: {report_path}")
    print(f"  📊 Case {len(cases)}/{len(context['cases_manifest'])} · 步骤 {run['batch_summary']['total_steps']} · 通过 {run['batch_summary']['pass']} · 警告 {run['batch_summary']['warn']} · 失败 {run['batch_summary']['fail']}")
    print(f"  🔗 平台报告: {REPORT_PORTAL_BASE}{run['id']}")
    if missing:
        print(f"  ⚠️ 报告不完整: {len(missing)} 个 Case 缺失")
        raise RuntimeError("批次报告不完整")