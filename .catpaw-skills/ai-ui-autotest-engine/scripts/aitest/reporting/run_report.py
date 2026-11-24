#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次报告构建（build_run）、单 Case 终态归一（enrich_case）与平台/App/设备类型标签。"""
from datetime import datetime

from aitest.reporting.case_report import resolve_case_status
from aitest.reporting.data_collector import _load_check_deps, skill_version
from aitest.reporting.schema import aggregate_assertion_summaries
from aitest.reporting.timeline import _build_timeline_events
# 环境展示白名单（与 Console 发现层共用同一口径：含 B 的 swimline / E 的 url_mappings）
from aitest.shared.env_view import SAFE_ENV_KEYS
_PLATFORM_LABELS = {"android": "Android", "harmony": "HarmonyOS"}

# Case 终态：只有这些状态才算「本 Case 已走完」（决定 timeline 是否已收口）
TERMINAL_CASE_STATUS = frozenset({"completed", "failed", "skipped"})


def _platform_label(platform):
    return _PLATFORM_LABELS.get(platform, platform.capitalize() if platform else "Android")


_APP_LABELS = {"meituan": "美团", "dianping": "点评"}

_DEVICE_TYPE_LABELS = {
    "sandbox": "云模拟器",
    "local": "本地真机",
    "local-emulator": "本地模拟器",
    "cloud-emulator": "云模拟器（Conan）",
    "cloud_device": "云真机",
}


def _app_label(app):
    return _APP_LABELS.get(app, app or "美团")


def _device_type_label(device_type):
    """返回人类可读的设备类型标签，替代无意义的设备序列号。"""
    return _DEVICE_TYPE_LABELS.get(device_type, device_type or "本地真机")


def report_row_meta(context):
    """平台报告行的行级元信息（Open 用；首写优先，后续 append 不会覆盖）。

    行级字段只能在报告行首次创建时写入：门户列表页的时间排序、设备标签、
    归属人都取这里。共享报告由编排层预置，独立运行由引擎 `flow-init` 预置。
    """
    from aitest.reporting.transport import is_shared_report, report_id

    meta = context.get("meta") or {}
    row = {
        "id": report_id(meta.get("batch_run_id", "")),
        "title": meta.get("flow_name", "") or "UI 自动化走查",
        "device": _device_type_label(meta.get("device_type", "")),
        "platform": _platform_label(meta.get("platform", "android")),
        "app": _app_label(meta.get("app", "meituan")),
        "timestamp": _row_timestamp(meta),
        "user_id": meta.get("user_mis", ""),
        # 回归 / 需求验证 / 未声明：报告列表按此字段筛选（首写优先）
        "run_type": meta.get("run_type") or "adhoc",
    }
    # 「所属 EC 用例」只在独立运行的单 Case 报告上成立（共享报告多分片会互相覆盖）
    manifest = context.get("cases_manifest") or []
    if len(manifest) == 1 and not is_shared_report():
        row["ec_case_id"] = str(manifest[0].get("case_id") or "") or None
    return row


def _row_timestamp(meta):
    """报告行时间 = run 开始时间（取不到才用当前时间）。"""
    start = meta.get("run_start_ts")
    if isinstance(start, (int, float)):
        return datetime.fromtimestamp(start).strftime("%Y-%m-%d %H:%M:%S")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_env(context):
    """上报用的环境快照（白名单脱敏 + 运行域）。

    单 Case 增量上报与批次报告共用同一口径：平台把 `cases[0].env_config` 当作
    报告级环境展示，因此每个 case 都必须带同一份快照。
    """
    env = {k: v for k, v in (context.get("env") or {}).items() if k in SAFE_ENV_KEYS}
    # AppMock 运行域（号池租约）是本次执行的实际工作域：平台详情页据此定位
    # 「这条用例跑在哪个号上」；场景规则本身按 mockId 从规则库直取。
    runtime_domain = str((context.get("meta") or {}).get("mock_runtime_domain") or "").strip()
    if runtime_domain:
        env["mock_domain"] = runtime_domain
    return env


def enrich_case(context, case, audit_events, check_deps=None):
    """把单个 Case 归一成「最终形态」：补全 timeline + 解析终态。

    唯一口径：C5_report 的增量上报与 flow-finalize 的本地 report.json 都走本函数，
    否则「平台上看到的」与「归档里存的」会各自算一套状态。
    """
    case = dict(case)
    if check_deps is None:
        check_deps = _load_check_deps()
    case_index = case.get("case_index", 0)
    case["timeline"] = _build_timeline_events(context, case_index, audit_events, check_deps)
    summary_status = next(
        (item.get("status") for item in context.get("cases_summary", [])
         if item.get("case_id") == case.get("case_id")),
        case.get("status", "pending"),
    )
    timeline_finalized = bool(case["timeline"]) and all(
        stage["status"] in TERMINAL_CASE_STATUS for stage in case["timeline"]
        if stage.get("_type") == "sop_stage"
    )
    case["status"] = resolve_case_status(
        summary_status, timeline_finalized, (case.get("summary") or {}).get("fail", 0)
    )
    return case


def run_status_for(context, cases):
    """本 run 的终态：声明 Case 是否全部产出了有效报告。"""
    reported = {str(case.get("case_id")) for case in cases if isinstance(case, dict)}
    missing = [
        item for item in context.get("cases_manifest", [])
        if str(item.get("case_id", "")) not in reported
    ]
    return "incomplete" if missing else "complete"


def build_run(context, cases, audit_events, timestamp, duration_ms_value, run_status):
    summaries = {item.get("case_id"): item for item in context.get("cases_summary", [])}

    # 加载 check-deps 结果：整批只读一次，避免每个 case 重复读盘
    check_deps = _load_check_deps()

    # 构建 timeline 并入 case，不原地修改传入的 cases
    cases = [
        enrich_case(context, case, audit_events, check_deps=check_deps)
        for case in cases
    ]

    case_summaries = [case["summary"] for case in cases]
    batch_assert_stats = aggregate_assertion_summaries(case_summaries)
    return {
        "id": context.get("meta", {}).get("batch_run_id", ""),
        "title": context.get("meta", {}).get("flow_name", "酒店 UI 自动化走查"),
        "timestamp": timestamp,
        "duration_ms": duration_ms_value,
        "device": _device_type_label(context.get("meta", {}).get("device_type", "")),
        "mis": context.get("meta", {}).get("user_mis", ""),
        "platform": _platform_label(context.get("meta", {}).get("platform", "android")),
        "app": _app_label(context.get("meta", {}).get("app", "meituan")),
        "env_config": safe_env(context),
        "run_status": run_status,
        "cases": cases,
        "batch_summary": {
            "total_cases": len(context.get("cases_manifest", [])),
            "reported_cases": len(cases),
            "failed_cases": sum(1 for case in cases if case["status"] == "failed"),
            "blocked_cases": sum(1 for case in cases if case["status"] == "blocked"),
            # 只计「已声明的走查步骤」：findings（未绑定步骤的独立发现）单独统计，
            # 与平台 payload（transport.append_case 按 cases[].steps 重算）同一口径。
            "total_steps": sum(item.get("total_steps", item["total"]) for item in case_summaries),
            "total_findings": sum(item.get("total_findings", 0) for item in case_summaries),
            "pass": sum(item["pass"] for item in case_summaries),
            "warn": sum(item["warn"] for item in case_summaries),
            "fail": sum(item["fail"] for item in case_summaries),
            "assert_results": batch_assert_stats["results"],
            "assert_verdicts": batch_assert_stats["verdicts"],
            # 需人工复核的断言数（通过但非字面精确：语义/视觉）——batch 级供平台打标
            "assert_needs_review": batch_assert_stats["needs_review"],
            # 需人工复核的步骤数（断言层 + 动作层）= 卡片徽标数，step_needs_review 为同值旧字段
            "needs_review": sum(int(item.get("needs_review") or 0) for item in case_summaries),
            "step_needs_review": sum(int(item.get("step_needs_review") or 0) for item in case_summaries),
        },
        "skill_version": skill_version(),
    }
