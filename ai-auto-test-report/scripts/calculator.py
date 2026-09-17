#!/usr/bin/env python3
"""Phase 3: 指标计算（Calculate）— M1~M5 核心指标计算 + 回归对比 + 编码Agent反馈。"""

import json
import os
from collections import Counter

from cleaner import classify_failure, split_phase_duration


# ── M1: EC 用例执行覆盖率 ────────────────────────────────────────────────────


def calc_coverage(cases):
    """计算 EC 用例执行覆盖率"""
    has_ec = any(c.get("ec_case_id") for c in cases)

    if has_ec:
        ec_results = {}
        for case in cases:
            ec_id = case.get("ec_case_id")
            if not ec_id:
                continue
            if ec_id not in ec_results:
                ec_results[ec_id] = {
                    "statuses": set(),
                    "priority": case.get("ec_priority", "P2"),
                    "page": case.get("ec_page", "unknown"),
                }
            ec_results[ec_id]["statuses"].add(case.get("status", "unknown"))

        total_ec = len(ec_results)
        passed_ec = 0
        for ec_id, info in ec_results.items():
            if "completed" in info["statuses"]:
                related = [c for c in cases if c.get("ec_case_id") == ec_id]
                if not any(c.get("summary", {}).get("fail", 0) > 0 for c in related):
                    passed_ec += 1

        by_priority = {}
        for p in ["P0", "P1", "P2"]:
            group = {k: v for k, v in ec_results.items() if v["priority"] == p}
            if group:
                passed = sum(1 for k, v in group.items() if "completed" in v["statuses"])
                by_priority[p] = {
                    "total": len(group),
                    "passed": passed,
                    "rate": round(passed / len(group), 4),
                }

        return {
            "total_ec_cases": total_ec,
            "passed_ec_cases": passed_ec,
            "coverage": round(passed_ec / total_ec, 4) if total_ec > 0 else 0,
            "by_priority": by_priority,
            "calculation_type": "ec_case_level",
        }
    else:
        total = len(cases)
        passed = sum(1 for c in cases if c["status"] == "completed")
        return {
            "total_cases": total,
            "passed_cases": passed,
            "coverage": round(passed / total, 4) if total > 0 else 0,
            "calculation_type": "case_status_level",
            "note": "无 EC 映射，用例级覆盖率降级为 case 执行覆盖率",
        }


# ── M2: 测试执行误报率 ──────────────────────────────────────────────────────


def calc_false_positive(cases):
    """计算测试执行误报率"""
    total_fails = 0
    classified_fails = []

    for case in cases:
        for step in case.get("steps", []):
            if step.get("ok") == 0:
                total_fails += 1
                cls = classify_failure(step.get("evidence", {}))
                classified_fails.append({
                    "case_id": case.get("case_id"),
                    "case_name": case.get("case_name"),
                    "sid": step.get("sid"),
                    "desc": step.get("desc"),
                    "classification": cls,
                })

        for finding in case.get("findings", []):
            if finding.get("ok") == 0:
                total_fails += 1
                cls = classify_failure(finding.get("evidence", {}))
                classified_fails.append({
                    "case_id": case.get("case_id"),
                    "sid": finding.get("sid", "finding"),
                    "desc": finding.get("desc", ""),
                    "classification": cls,
                    "is_finding": True,
                })

    false_positives = [f for f in classified_fails
                       if f["classification"]["category"] in ("env", "data", "script")]
    valid_issues = [f for f in classified_fails
                    if f["classification"]["category"] == "bug"]

    by_category = {}
    labels = {"env": "L1 环境框架", "data": "L2 数据依赖", "script": "L2 脚本/Flow", "bug": "L3 业务缺陷"}
    for cat in ["env", "data", "script", "bug"]:
        group = [f for f in classified_fails if f["classification"]["category"] == cat]
        by_category[cat] = {"count": len(group), "label": labels[cat]}

    return {
        "total_issues": total_fails,
        "false_positives": len(false_positives),
        "valid_issues": len(valid_issues),
        "false_positive_rate": round(len(false_positives) / total_fails, 4) if total_fails > 0 else 0,
        "valid_rate": round(len(valid_issues) / total_fails, 4) if total_fails > 0 else 0,
        "by_category": by_category,
        "details": classified_fails,
    }


# ── M4: E2E 提效分析 ──────────────────────────────────────────────────────


def calc_efficiency(cases, run_meta, batch_summary):
    """计算 E2E 执行提效数据"""
    e2e_duration_ms = run_meta.get("duration_ms") or sum(
        c.get("summary", {}).get("duration_ms") or 0
        for c in cases if c.get("summary")
    )

    phase_breakdown = {}
    if cases:
        phase_breakdown = split_phase_duration(cases[0].get("timeline", []))

    case_durations = []
    for case in cases:
        d = case.get("summary", {}).get("duration_ms") or 0
        case_durations.append({
            "case_id": case.get("case_id"),
            "case_name": case.get("case_name"),
            "duration_ms": d,
            "duration_display": f"{d//60000}m{d%60000//1000}s" if d else "N/A",
        })

    total_retries = sum(
        step.get("retry_count", 0)
        for case in cases
        for step in case.get("steps", [])
    )
    total_steps = batch_summary.get("total_steps", 0)

    return {
        "e2e_duration_ms": e2e_duration_ms,
        "e2e_duration_display": f"{e2e_duration_ms//60000}m{e2e_duration_ms%60000//1000}s",
        "phase_breakdown": phase_breakdown,
        "phase_breakdown_display": {
            k: f"{v['duration_ms']//60000}m{v['duration_ms']%60000//1000}s ({round(v['ratio']*100)}%)"
            for k, v in phase_breakdown.items()
        } if phase_breakdown else {},
        "case_durations": case_durations,
        "total_cases": len(cases),
        "total_steps": total_steps,
        "total_retries": total_retries,
        "avg_retries_per_step": round(total_retries / total_steps, 2) if total_steps > 0 else 0,
    }


# ── M5: AI 测试发现缺陷占比 ────────────────────────────────────────────────


def calc_defect_discovery(collected_cases, labeled=None):
    """计算 AI 测试发现缺陷占比。labeled 为人工打标结果"""
    if labeled and labeled.get("defects"):
        ai_found = sum(1 for d in labeled["defects"] if d.get("discovered_by") == "ai")
        human_found = sum(1 for d in labeled["defects"] if d.get("discovered_by") == "human")

        by_severity = {}
        for d in labeled["defects"]:
            sev = d.get("severity", "P2")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        by_type = {}
        for d in labeled["defects"]:
            dt = d.get("type", "unknown")
            by_type[dt] = by_type.get(dt, 0) + 1

        return {
            "ai_found": ai_found,
            "human_found": human_found,
            "ai_ratio": round(ai_found / (ai_found + human_found), 4) if (ai_found + human_found) > 0 else 0,
            "total_defects": ai_found + human_found,
            "by_severity": by_severity,
            "by_type": by_type,
        }
    else:
        fp_result = calc_false_positive(collected_cases)
        estimated_bugs = fp_result["valid_issues"]
        return {
            "estimated_bugs": estimated_bugs,
            "note": "无人工打标数据，使用 AI 预分类的 L3 业务缺陷估算值",
            "requires_labeling": True,
        }


# ── 回归对比 ──────────────────────────────────────────────────────────────────


def load_previous_metrics(path):
    """加载上一次执行的指标数据，用于回归对比"""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def calc_regression(current, previous):
    """对比本次与上次的指标，识别新增/修复/持续失败的用例"""
    if not previous:
        return {"has_previous": False, "note": "首次执行，无历史对比"}

    prev_fp = previous.get("metrics", {}).get("false_positive", {})
    curr_fp = current.get("false_positive", {})

    prev_details = {_bug_key(d): d for d in prev_fp.get("details", [])
                    if d.get("classification", {}).get("category") == "bug"}
    curr_details = {_bug_key(d): d for d in curr_fp.get("details", [])
                    if d.get("classification", {}).get("category") == "bug"}

    prev_bug_keys = set(prev_details.keys())
    curr_bug_keys = set(curr_details.keys())

    new_bugs = curr_bug_keys - prev_bug_keys
    fixed_bugs = prev_bug_keys - curr_bug_keys
    still_failing = curr_bug_keys & prev_bug_keys

    prev_cov = previous.get("metrics", {}).get("ec_coverage", {}).get("coverage", 0)
    curr_cov = current.get("metrics", {}).get("ec_coverage", {}).get("coverage", 0)
    prev_fpr = previous.get("metrics", {}).get("false_positive", {}).get("false_positive_rate", 0)
    curr_fpr = current.get("metrics", {}).get("false_positive", {}).get("false_positive_rate", 0)

    return {
        "has_previous": True,
        "previous_run_id": previous.get("run_id"),
        "coverage_change": round(curr_cov - prev_cov, 4),
        "fpr_change": round(curr_fpr - prev_fpr, 4),
        "new_bugs": len(new_bugs),
        "fixed_bugs": len(fixed_bugs),
        "still_failing": len(still_failing),
        "new_bug_details": [curr_details[k] for k in sorted(new_bugs)],
        "fixed_bug_details": [prev_details[k] for k in sorted(fixed_bugs)],
        "still_failing_details": [curr_details[k] for k in sorted(still_failing)],
    }


def _bug_key(detail):
    """生成 bug 的唯一标识 key"""
    return f"{detail.get('case_id', '')}:{detail.get('sid', '')}"


# ── 编码Agent 反馈 ──────────────────────────────────────────────────────────


def build_coding_feedback(cases, regression, labeled=None):
    """构建面向编码Agent 的可操作反馈。

    从 FAIL 步骤中筛选出 L3 业务缺陷（或人工打标确认的缺陷），
    附上截图、断言对比、回归状态等信息，生成 actionable 的修复指引。
    """
    bugs = []

    # 优先从人工打标结果取缺陷
    if labeled and labeled.get("defects"):
        for d in labeled["defects"]:
            if d.get("discovered_by") == "ai":
                bugs.append(d)
        labeled_bug_keys = {_bug_key(d) for d in bugs}
    else:
        labeled_bug_keys = set()

    # 从 FAIL 步骤中收集 L3 业务缺陷
    for case in cases:
        case_id = case.get("case_id", "")
        case_name = case.get("case_name", "")
        ec_id = case.get("ec_case_id") or ""

        for step in case.get("steps", []):
            if step.get("ok") != 0:
                continue

            # 分类
            cat = step.get("_failure_category") or ""
            if cat != "bug":
                continue

            key = _bug_key({"case_id": case_id, "sid": step.get("sid", "")})
            # 如果已在打标结果中，跳过（避免重复）
            if key in labeled_bug_keys:
                continue

            evidence = step.get("evidence", {}) or {}
            meta = evidence.get("metadata", {}) or {}
            raw = evidence.get("raw", {}) or {}

            # 提取断言对比
            fields = evidence.get("fields", {}) or {}
            assert_details = []
            for fk, fv in fields.items():
                if fk.startswith("assert_"):
                    assert_details.append({"assertion": fk, "result": fv})

            bug_entry = {
                "case_id": case_id,
                "case_name": case_name,
                "ec_case_id": ec_id,
                "ec_priority": case.get("ec_priority", "P2"),
                "failed_step": {
                    "sid": step.get("sid"),
                    "desc": step.get("desc"),
                    "action": step.get("action"),
                    "step_type": step.get("step_type"),
                },
                "assertion_failures": assert_details,
                "evidence": {
                    "reason": evidence.get("reason", ""),
                    "screenshot_url": evidence.get("screenshot") or step.get("screenshot"),
                    "http_code": meta.get("http_code"),
                    "api_matched": meta.get("matched"),
                    "event_nm": meta.get("event_nm"),
                },
                "classification": {
                    "category": "bug",
                    "confidence": step.get("_failure_confidence", "medium"),
                },
                "severity": "P2",  # 默认，打标后可修正
                "discovered_by": "ai",
                "screenshot": step.get("screenshot"),
            }
            bugs.append(bug_entry)

    # 回归状态标记
    if regression and regression.get("has_previous"):
        new_set = {_bug_key(d) for d in regression.get("new_bug_details", [])}
        fixed_set = {_bug_key(d) for d in regression.get("fixed_bug_details", [])}
        still_set = {_bug_key(d) for d in regression.get("still_failing_details", [])}
        for bug in bugs:
            key = _bug_key(bug)
            if key in new_set:
                bug["regression"] = "new"
            elif key in still_set:
                bug["regression"] = "still_failing"
            else:
                bug["regression"] = "unknown"
    else:
        for bug in bugs:
            bug["regression"] = "new"

    action_required = len(bugs) > 0

    return {
        "action_required": action_required,
        "total_bugs": len(bugs),
        "bugs": bugs,
        "summary": (
            f"{len(bugs)} 个业务缺陷待修复"
            if action_required
            else "本轮测试未发现业务缺陷"
        ),
    }


# ── 汇总 ─────────────────────────────────────────────────────────────────────


def calculate_all(run_meta, cases, batch_summary, labeled=None, previous_metrics_path=None):
    """计算全部指标 + 回归对比 + 编码Agent反馈"""
    metrics = {
        "ec_coverage": calc_coverage(cases),
        "false_positive": calc_false_positive(cases),
        "efficiency": calc_efficiency(cases, run_meta, batch_summary),
        "defect_discovery": calc_defect_discovery(cases, labeled),
    }

    # 回归对比
    previous = load_previous_metrics(previous_metrics_path)
    regression = calc_regression({"metrics": metrics}, previous)

    # 编码Agent 反馈
    feedback = build_coding_feedback(cases, regression, labeled)

    summary_parts = [
        f"EC覆盖率: {metrics['ec_coverage']['coverage']:.1%}",
        f"误报率: {metrics['false_positive']['false_positive_rate']:.1%}",
        f"耗时: {metrics['efficiency']['e2e_duration_display']}",
    ]
    if feedback["action_required"]:
        summary_parts.append(f"缺陷: {feedback['total_bugs']} 个待修复")

    return {
        "run_id": run_meta.get("run_id"),
        "timestamp": run_meta.get("timestamp"),
        "meta": {
            "device": run_meta.get("device"),
            "platform": run_meta.get("platform"),
            "app": run_meta.get("app"),
            "mis": run_meta.get("mis"),
            "run_status": run_meta.get("run_status"),
            "skill_version": run_meta.get("skill_version"),
        },
        "metrics": metrics,
        "regression": regression,
        "coding_agent_feedback": feedback,
        "summary_line": " | ".join(summary_parts),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="计算 E2E 测试指标")
    parser.add_argument("--cleaned", default=".metrics/cleaned.json", help="清洗后数据路径")
    parser.add_argument("--label", help="人工打标结果路径（可选）")
    parser.add_argument("--previous", help="上一次 metrics.json 路径（用于回归对比）")
    parser.add_argument("--output", default=".metrics", help="输出目录")
    args = parser.parse_args()

    with open(args.cleaned) as f:
        cleaned = json.load(f)

    labeled = None
    if args.label and os.path.isfile(args.label):
        with open(args.label) as f:
            labeled = json.load(f)

    total_steps = sum(len(c.get("steps", [])) for c in cleaned.get("cases", []))
    result = calculate_all(
        cleaned.get("run_meta", {}),
        cleaned.get("cases", []),
        {"total_steps": total_steps},
        labeled,
        previous_metrics_path=args.previous,
    )

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "metrics.json")
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存指标数据: {out_path}")
    print(f"📊 {result['summary_line']}")

    feedback = result.get("coding_agent_feedback", {})
    if feedback.get("action_required"):
        print(f"🐛 {feedback['total_bugs']} 个业务缺陷，反馈已就绪")
        for bug in feedback.get("bugs", []):
            print(f"   - [{bug.get('ec_priority', 'P2')}] {bug.get('case_name')} | {bug.get('failed_step', {}).get('sid', '')}: {bug.get('failed_step', {}).get('desc', '')}")


if __name__ == "__main__":
    main()