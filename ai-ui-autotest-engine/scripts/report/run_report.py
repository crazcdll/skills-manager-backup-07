#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批次报告构建（build_run）与平台/App/设备类型标签。"""
from report.case_report import resolve_case_status
from report.data_collector import _load_check_deps, _read_skill_version
from report.schema import aggregate_assertion_summaries
from report.timeline import _build_timeline_events


# 环境配置脱敏白名单——只保留非敏感字段
SAFE_ENV_KEYS = {"type", "env_name", "auth_method", "ptest", "mock_ids", "bundle_lock"}
_PLATFORM_LABELS = {"android": "Android", "harmony": "HarmonyOS"}


def _platform_label(platform):
    return _PLATFORM_LABELS.get(platform, platform.capitalize() if platform else "Android")


_APP_LABELS = {"meituan": "美团", "dianping": "点评"}

_DEVICE_TYPE_LABELS = {"sandbox": "云模拟器", "local": "本地真机", "cloud_device": "云真机"}


def _app_label(app):
    return _APP_LABELS.get(app, app or "美团")


def _device_type_label(device_type):
    """返回人类可读的设备类型标签，替代无意义的设备序列号。"""
    return _DEVICE_TYPE_LABELS.get(device_type, device_type or "本地真机")


def build_run(context, cases, audit_events, timestamp, duration_ms_value):
    terminal = {"completed", "failed", "skipped"}
    summaries = {item.get("case_id"): item for item in context.get("cases_summary", [])}

    # 加载 check-deps 结果
    check_deps = _load_check_deps()

    # 构建 timeline 并入 case，不原地修改传入的 cases
    cases = [dict(case) for case in cases]
    for case in cases:
        case_index = case.get("case_index", 0)
        case["timeline"] = _build_timeline_events(context, case_index, audit_events, check_deps)
        summary_status = summaries.get(case.get("case_id"), {}).get("status", case.get("status", "pending"))
        timeline_finalized = bool(case["timeline"]) and all(
            stage["status"] in terminal for stage in case["timeline"]
            if stage.get("_type") == "sop_stage"
        )
        case["status"] = resolve_case_status(summary_status, timeline_finalized, case["summary"].get("fail", 0))

    # 白名单脱敏，只保留非敏感字段
    env = {k: v for k, v in context.get("env", {}).items() if k in SAFE_ENV_KEYS}
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
        "env_config": env,
        "cases": cases,
        "batch_summary": {
            "total_cases": len(context.get("cases_manifest", [])),
            "reported_cases": len(cases),
            "failed_cases": sum(1 for case in cases if case["status"] == "failed"),
            "blocked_cases": sum(1 for case in cases if case["status"] == "blocked"),
            # 只计「已声明的走查步骤」：findings（未绑定步骤的独立发现）单独统计，
        # 与平台 payload（transport.insert_report 按 cases[].steps 重算）同一口径。
        "total_steps": sum(item.get("total_steps", item["total"]) for item in case_summaries),
        "total_findings": sum(item.get("total_findings", 0) for item in case_summaries),
            "pass": sum(item["pass"] for item in case_summaries),
            "warn": sum(item["warn"] for item in case_summaries),
            "fail": sum(item["fail"] for item in case_summaries),
            "assert_results": batch_assert_stats["results"],
            "assert_verdicts": batch_assert_stats["verdicts"],
            # 需人工复核的断言数（AI 主观判定通过）——batch 级供平台打标
            "assert_needs_review": batch_assert_stats["needs_review"],
        },
        "skill_version": _read_skill_version(),
    }
