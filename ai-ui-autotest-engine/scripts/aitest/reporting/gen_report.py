#!/usr/bin/env python3
"""报告生成与上报（增量模型：Open → Append × N → Close）。

职责边界：
  · `gen-report`（C5_report，每 Case 一次）—— 生成本 Case 的本地报告，并**立即**把
    这一个 Case 追加到平台报告（`append_case`）。payload 恒为 1 个 Case。
  · `flow-finalize` 触发的批次收尾 —— 只做 **Close**：补传失败/未传的 Case，并把最终
    run_status 写回行级视图（`cases[0]`）。**不再**一次性重发全部 Case，因此不会出现
    「用例越多、请求越大」的 413。
"""
import os
import time

from aitest.shared.case_utils import current_case_workspace, resolve_case_path
from aitest.shared.json_utils import write_json_atomic, read_json
from aitest.shared.output_guard import redact_obj, secrets_from
from aitest.shared.paths import get_active_run
from aitest.reporting import ledger
from aitest.reporting.case_report import build_case
from aitest.reporting.data_collector import load_audit, load_case_data
from aitest.reporting.finalizer import finalize_run
from aitest.reporting.inputs import materialize_inputs
from aitest.reporting.run_report import enrich_case, run_status_for, safe_env, report_row_meta
from aitest.reporting.transport import (
    REPORT_PORTAL_BASE,
    append_case,
    fetch_s3_config,
    format_duration,
    is_partial_rerun,
    is_shared_report,
    open_report_row,
    report_id,
    update_report_row,
    upload_images,
)
from aitest.execution.engine.flow.flow_context import load_context


def _active_context():
    case_name = get_active_run()
    if not case_name:
        raise RuntimeError("未设置 active_run")
    run_dir = resolve_case_path(case_name)
    context = load_context(run_dir)
    if context is None:
        raise RuntimeError(f"flow-context.json 不存在: {run_dir}")
    return run_dir, context


def open_report():
    """Open：为当前 run 预置平台报告空行（幂等；托管运行由编排层预置，这里跳过）。

    幂等两层：已注入 `AI_UITEST_REPORT_ID` 说明报告行归编排层管（insert 是整行 UPSERT，
    重复写会抹掉其他分片已追加的 Case）；本 run 已 Open 过则看台账，避免重复 flow-init
    把已有 cases 冲掉。失败不阻塞执行（首个 Case 追加时平台会自动建行）。
    """
    if is_shared_report():
        return False
    try:
        _, context = _active_context()
        output_dir = context["meta"]["batch_output_dir"]
        book = ledger.load(output_dir)
        if book["opened"] or book["cases"]:
            return False
        meta = report_row_meta(context)
        if not open_report_row(meta):
            return False
        ledger.mark_opened(output_dir, meta["id"])
        return True
    except Exception:  # noqa: BLE001 — 预置是 best-effort
        return False


def _elapsed_ms(context):
    start = context.get("meta", {}).get("run_start_ts")
    if isinstance(start, (int, float)):
        return max(0, int((time.time() - start) * 1000))
    return None


def _current_manifest(context):
    current = context.get("current_case", {})
    case_index = current.get("index")
    manifest = next(
        (item for item in context.get("cases_manifest", []) if item.get("index") == case_index),
        None,
    )
    if manifest is None:
        raise RuntimeError(f"未找到当前 Case 清单: index={case_index}")
    return manifest


def _case_report(context, run_dir, output_dir, s3):
    """构建当前 Case 的本地报告，并归一成最终形态（timeline + 终态）。

    C5_report 与 flow-finalize 复用同一归一函数：上报到平台的 Case 与归档里的
    Case 必须是同一份对象，否则「平台上看到的」与「归档里存的」会各自算一套状态。
    """
    manifest = _current_manifest(context)
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
        # 输入制品（steps.json / steps-input.json）：复制进报告包 + 正文内联，
        # 与 frames 同级归档，平台跨机可见（不依赖对象存储）。
        inputs=materialize_inputs(manifest, context, output_dir),
    )
    case = enrich_case(context, case, load_audit(run_dir))
    report = {
        "report_type": "case",
        "run_id": context["meta"]["batch_run_id"],
        "case": redact_obj(case, secrets_from(context.get("env") or {})),
    }
    write_json_atomic(os.path.join(output_dir, "report.json"), report)
    return report


def _publish_case(context, case, run_status):
    """Append：把单个 Case 追加到平台报告（失败不抛，收尾会自动补传）。"""
    output_dir = context["meta"]["batch_output_dir"]
    rid = report_id(context["meta"]["batch_run_id"])
    if append_case(rid, case, safe_env(context), run_status):
        ledger.mark_case(output_dir, rid, case.get("case_id"), run_status)
        return True
    return False


def _close_report(context, run):
    """Close：补传未成功的 Case + 把最终 run_status 写回行级视图。

    平台把 `cases[0]` 当报告级视图（状态徽标 / 环境 / skill 版本），因此收尾必须
    重发本 run 的**首个** Case —— 同 case_id 幂等覆盖，体积仍是一个 Case。
    """
    cases = run.get("cases") or []
    if not cases:
        return False
    output_dir = context["meta"]["batch_output_dir"]
    rid = report_id(context["meta"]["batch_run_id"])
    env = safe_env(context)
    run_status = run.get("run_status") or "incomplete"

    book = ledger.load(output_dir)
    if book["closed"]:
        print(f"  ✅ 报告已收尾（跳过重复上报）: {REPORT_PORTAL_BASE}{rid}")
        return True

    ok = True
    for case in cases:
        case_id = str(case.get("case_id"))
        if book["cases"].get(case_id):
            continue
        if append_case(rid, case, env, run_status):
            book = ledger.mark_case(output_dir, rid, case_id, run_status)
        else:
            ok = False

    first = cases[0]
    first_id = str(first.get("case_id"))
    if (book["cases"].get(first_id) or {}).get("run_status") != run_status:
        if append_case(rid, first, env, run_status):
            book = ledger.mark_case(output_dir, rid, first_id, run_status)
        else:
            ok = False

    if ok:
        # 补测/重测只覆盖部分 Case：报告级 duration 是首轮全量口径，不能拿本轮短跑覆盖
        _sync_row_meta(context, run, opened=book["opened"], preserve_duration=is_partial_rerun())
        ledger.mark_closed(output_dir, rid)
        print(f"  🔗 平台报告: {REPORT_PORTAL_BASE}{rid}")
    return ok


def _sync_row_meta(context, run, opened, preserve_duration=False):
    """Close 时回写 append 覆盖不到的列。

    `duration` 只有收尾才知道；`platform` / `app` 由引擎按真实运行平台纠正（编排层预置时
    只能给默认值）。Open 没成功（行是首个 append 建的，行级列全为 NULL）时，把整份行级
    元信息一起补上，避免门户列表页标题/时间/设备为空。

    `preserve_duration=True`（补测/重测）：只覆盖被重跑的 Case，行级 duration 保持首轮
    全量口径不写回——否则一条 Case 的短跑时长会把整份报告时长改成几分钟。
    """
    meta = report_row_meta(context)
    shared = is_shared_report()
    fields = {
        "platform": meta["platform"],
        "app": meta["app"],
    }
    if not preserve_duration:
        fields["duration"] = format_duration(run.get("duration_ms")) or ""
    # 共享报告的行级元信息由编排层 Open 时写死，分片不得改写（title 口径不同）
    if not opened and not shared:
        fields.update({key: meta[key] for key in ("title", "device", "timestamp", "user_id", "run_type")})
    cases = run.get("cases") or []
    # 只有独立运行的单 Case 报告才有「所属 EC 用例」概念；共享报告多分片会把该列抢成最后一个
    if not shared and len(cases) == 1:
        fields["ec_case_id"] = str(cases[0].get("case_id") or "") or None
    update_report_row(report_id(context["meta"]["batch_run_id"]), fields)


def generate_case_report(args):
    """C5_report：生成当前 Case 报告 + 增量上报（Append）。"""
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
        if not getattr(args, "no_db", False):
            _close_report(context, run)
        print(f"  📄 report.json: file://{report_path}")
        return

    # 正常路径：本 Case 一收口就追加，单次 payload = 1 个 Case。
    # 此时批次尚未结束 → 行级 run_status 先记 incomplete，flow-finalize 再写终态。
    if not getattr(args, "no_db", False):
        _publish_case(context, case, "incomplete")


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
    """批次收尾：只做 Close（不重发全量 Case）。"""
    cases, missing = _load_case_reports(context)
    if not cases:
        # 一个 Case 报告都没有（如环境准备阶段直接失败）：归档已由 flow-fail 完成，
        # 这里跳过收口即可，不能抛错（否则会打断/污染收尾序列）。
        print("  ⏭️ 无 Case 报告，跳过批次收口")
        return
    run, report_path = finalize_run(
        context=context,
        run_dir=run_dir,
        cases=cases,
        audit_events=load_audit(run_dir),
        elapsed_ms=_elapsed_ms(context),
        output_dir=context["meta"]["batch_output_dir"],
        run_status=run_status_for(context, cases),
    )
    if not args.no_db:
        _close_report(context, run)
    print(f"  ✅ 聚合报告已生成: {report_path}")
    print(f"  📊 Case {len(cases)}/{len(context['cases_manifest'])} · 步骤 {run['batch_summary']['total_steps']} · 通过 {run['batch_summary']['pass']} · 警告 {run['batch_summary']['warn']} · 失败 {run['batch_summary']['fail']}")
    if missing:
        # 缺失 Case 已经反映在 run_status=incomplete 上：收口本身是 best-effort，
        # 不能因为「报告不完整」把 flow-finalize 判成失败（否则设备/租约收尾会被中断）。
        print(f"  ⚠️ 报告不完整: {len(missing)} 个 Case 缺失（run_status=incomplete）")
