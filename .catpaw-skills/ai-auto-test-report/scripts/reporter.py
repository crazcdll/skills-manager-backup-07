#!/usr/bin/env python3
"""Phase 5: 输出报告（Output）— 生成度量报告 + 编码Agent反馈 + 精简数据。"""

import json
import os


def format_duration(ms):
    if ms is None:
        return "N/A"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining = seconds % 60
    return f"{minutes}m{remaining}s" if remaining else f"{minutes}m"


def generate_markdown(metrics):
    """生成 Markdown 格式的可读报告（含回归对比 + 编码Agent反馈）"""
    m = metrics.get("metrics", {})
    reg = metrics.get("regression", {})
    fb = metrics.get("coding_agent_feedback", {})

    lines = [
        "# E2E 自动化测试指标报告",
        "",
        "## 运行信息",
        f"- **批次**: {metrics.get('run_id', 'N/A')}",
        f"- **时间**: {metrics.get('timestamp', 'N/A')}",
        f"- **设备/平台/App**: {metrics.get('meta', {}).get('device', 'N/A')} / {metrics.get('meta', {}).get('platform', 'N/A')} / {metrics.get('meta', {}).get('app', 'N/A')}",
        f"- **状态**: {metrics.get('meta', {}).get('run_status', 'N/A')}",
        "",
        "## 指标总览",
        "| 指标 | 值 | 健康线 | 状态 |",
        "|------|------|--------|------|",
    ]

    ec = m.get("ec_coverage", {})
    ec_val = f"{ec.get('coverage', 0):.1%}"
    ec_ok = "✅" if ec.get("coverage", 0) >= 0.8 else "⚠️"
    lines.append(f"| EC覆盖率 | {ec_val} | ≥ 80% | {ec_ok} |")

    fp = m.get("false_positive", {})
    fp_val = f"{fp.get('false_positive_rate', 0):.1%}"
    fp_ok = "✅" if fp.get("false_positive_rate", 1) < 0.2 else "⚠️"
    lines.append(f"| 误报率 | {fp_val} | < 20% | {fp_ok} |")

    eff = m.get("efficiency", {})
    lines.append(f"| 执行耗时 | {eff.get('e2e_duration_display', 'N/A')} | — | — |")

    dd = m.get("defect_discovery", {})
    if "ai_found" in dd:
        lines.append(f"| AI发现缺陷占比 | {dd.get('ai_ratio', 0):.1%} | — | — |")
    else:
        lines.append(f"| 预估业务缺陷 | {dd.get('estimated_bugs', 'N/A')} 个 | — | ⏳需打标 |")

    # ── 编码Agent 反馈（最优先展示） ──
    lines += ["", "## 🔔 编码Agent 反馈", ""]
    if fb.get("action_required"):
        lines += [
            f"### 🐛 {fb['total_bugs']} 个业务缺陷待修复",
            "",
            "| 优先级 | 用例 | 失败步骤 | 断言详情 | 截图 | 回归状态 |",
            "|--------|------|---------|---------|------|---------|",
        ]
        for bug in fb.get("bugs", []):
            step = bug.get("failed_step", {})
            sid = step.get("sid", "")
            sdesc = step.get("desc", "")
            af = bug.get("assertion_failures", [])
            af_text = "; ".join(f"{a['assertion']}={a['result']}" for a in af[:3])
            if len(af) > 3:
                af_text += f"... (+{len(af)-3})"
            ss = bug.get("screenshot") or bug.get("evidence", {}).get("screenshot_url", "")
            ss_link = f"[截图]({ss})" if ss and ss.startswith("http") else (ss or "无")
            reg_status = {"new": "🆕 新增", "still_failing": "🔄 持续", "fixed": "✅ 已修复", "unknown": "—"}
            lines.append(
                f"| {bug.get('ec_priority', 'P2')} "
                f"| {bug.get('case_name', '')} "
                f"| {sid}: {sdesc} "
                f"| {af_text} "
                f"| {ss_link} "
                f"| {reg_status.get(bug.get('regression', 'unknown'), '—')} |"
            )
        lines.append("")
        if reg.get("has_previous"):
            lines.append(f"**对比上次**: 🆕 新增 {reg.get('new_bugs', 0)} / ✅ 修复 {reg.get('fixed_bugs', 0)} / 🔄 持续 {reg.get('still_failing', 0)}")
    else:
        lines.append("✅ 本轮测试未发现业务缺陷，编码侧无需处理。")
        lines.append("")
        if reg.get("has_previous") and reg.get("fixed_bugs", 0) > 0:
            lines.append(f"✅ 相比上次修复了 {reg['fixed_bugs']} 个缺陷")

    # ── 回归对比摘要 ──
    if reg.get("has_previous"):
        lines += [
            "",
            "## 回归对比",
            f"- **对比基线**: {reg.get('previous_run_id')}",
            f"- **覆盖率变化**: {reg.get('coverage_change', 0):+.1%}",
            f"- **误报率变化**: {reg.get('fpr_change', 0):+.1%}",
            f"- 🆕 新增缺陷: {reg.get('new_bugs', 0)}",
            f"- ✅ 已修复缺陷: {reg.get('fixed_bugs', 0)}",
            f"- 🔄 持续缺陷: {reg.get('still_failing', 0)}",
        ]

    # ── M1 ──
    lines += ["", "## M1: EC 用例执行覆盖率"]
    lines += [f"- **覆盖率**: {ec_val}", f"- **计算方式**: {ec.get('calculation_type', 'N/A')}"]
    if "total_ec_cases" in ec:
        lines += [f"- **EC 总数**: {ec['total_ec_cases']}", f"- **执行通过**: {ec['passed_ec_cases']}"]
        for p, v in ec.get("by_priority", {}).items():
            lines.append(f"- **{p}**: {v['passed']}/{v['total']} ({v['rate']:.1%})")
    else:
        lines += [f"- **Case 总数**: {ec.get('total_cases', 0)}", f"- **通过**: {ec.get('passed_cases', 0)}"]

    # ── M2 ──
    lines += ["", "## M2: 测试执行误报率"]
    lines += [f"- **误报率**: {fp_val}", f"- **总失败**: {fp.get('total_issues', 0)}", f"- **有效缺陷(L3)**: {fp.get('valid_issues', 0)}", f"- **误报**: {fp.get('false_positives', 0)}"]
    for cat, info in fp.get("by_category", {}).items():
        lines.append(f"  - {info['label']}: {info['count']}")

    # ── M4 ──
    lines += ["", "## M4: E2E 执行效率"]
    lines.append(f"- **总耗时**: {eff.get('e2e_duration_display', 'N/A')}")
    for k, v in eff.get("phase_breakdown_display", {}).items():
        lines.append(f"  - {k}: {v}")
    lines += [f"- **总步骤**: {eff.get('total_steps', 0)}", f"- **总重试**: {eff.get('total_retries', 0)}", f"- **平均重试/步**: {eff.get('avg_retries_per_step', 0)}"]

    # ── M5 ──
    lines += ["", "## M5: 缺陷发现"]
    if "ai_found" in dd:
        lines += [f"- **AI 发现**: {dd['ai_found']}", f"- **人工发现**: {dd['human_found']}", f"- **AI 占比**: {dd.get('ai_ratio', 0):.1%}"]
        if "by_severity" in dd:
            lines.append(f"- **严重程度**: {json.dumps(dd['by_severity'])}")
    else:
        lines += [f"- **预估业务缺陷**: {dd.get('estimated_bugs', 'N/A')} 个", f"- *{dd.get('note', '')}*"]

    lines += ["", "---", f"*报告生成时间: {metrics.get('timestamp', 'N/A')}*", ""]
    return "\n".join(lines)


def generate_json_report(metrics, output_path):
    """输出精简版 JSON 供外部消费"""
    m = metrics.get("metrics", {})
    flat = {
        "run_id": metrics.get("run_id"),
        "timestamp": metrics.get("timestamp"),
        "summary": metrics.get("summary_line", ""),
        "coverage": {
            "rate": m.get("ec_coverage", {}).get("coverage"),
            "total_ec": m.get("ec_coverage", {}).get("total_ec_cases", m.get("ec_coverage", {}).get("total_cases")),
        },
        "false_positive": {
            "rate": m.get("false_positive", {}).get("false_positive_rate"),
            "total_issues": m.get("false_positive", {}).get("total_issues"),
            "valid_issues": m.get("false_positive", {}).get("valid_issues"),
        },
        "efficiency": {
            "duration_ms": m.get("efficiency", {}).get("e2e_duration_ms"),
            "duration_display": m.get("efficiency", {}).get("e2e_duration_display"),
            "retry_per_step": m.get("efficiency", {}).get("avg_retries_per_step"),
        },
        "defect_discovery": m.get("defect_discovery", {}),
        "regression": {
            "has_previous": metrics.get("regression", {}).get("has_previous", False),
            "coverage_change": metrics.get("regression", {}).get("coverage_change"),
            "fpr_change": metrics.get("regression", {}).get("fpr_change"),
            "new_bugs": metrics.get("regression", {}).get("new_bugs"),
            "fixed_bugs": metrics.get("regression", {}).get("fixed_bugs"),
            "still_failing": metrics.get("regression", {}).get("still_failing"),
        },
        "coding_agent": {
            "action_required": metrics.get("coding_agent_feedback", {}).get("action_required", False),
            "total_bugs": metrics.get("coding_agent_feedback", {}).get("total_bugs", 0),
            "summary": metrics.get("coding_agent_feedback", {}).get("summary", ""),
        },
    }
    with open(output_path, "w") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)


def generate_coding_feedback_json(metrics, output_path):
    """输出专供编码Agent 消费的结构化反馈"""
    fb = metrics.get("coding_agent_feedback", {})
    reg = metrics.get("regression", {})

    payload = {
        "type": "e2e_test_feedback",
        "run_id": metrics.get("run_id"),
        "timestamp": metrics.get("timestamp"),
        "action_required": fb.get("action_required", False),
        "total_bugs": fb.get("total_bugs", 0),
        "summary": fb.get("summary", ""),
        "regression": {
            "has_previous": reg.get("has_previous", False),
            "new_bugs": reg.get("new_bugs", 0),
            "fixed_bugs": reg.get("fixed_bugs", 0),
            "still_failing": reg.get("still_failing", 0),
        } if reg.get("has_previous") else None,
        "bugs": [
            {
                "case_name": b.get("case_name"),
                "ec_case_id": b.get("ec_case_id"),
                "ec_priority": b.get("ec_priority", "P2"),
                "severity": b.get("severity", "P2"),
                "failed_step": b.get("failed_step"),
                "assertion_failures": b.get("assertion_failures", []),
                "screenshot_url": b.get("screenshot") or b.get("evidence", {}).get("screenshot_url"),
                "reason": b.get("evidence", {}).get("reason", ""),
                "regression": b.get("regression", "unknown"),
            }
            for b in fb.get("bugs", [])
        ],
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main():
    import argparse

    parser = argparse.ArgumentParser(description="生成 E2E 测试指标报告")
    parser.add_argument("--metrics", default=".metrics/metrics.json", help="指标数据路径")
    parser.add_argument("--output", default=".metrics", help="输出目录")
    parser.add_argument("--md-only", action="store_true", help="仅输出 Markdown 报告")
    args = parser.parse_args()

    with open(args.metrics) as f:
        metrics = json.load(f)

    os.makedirs(args.output, exist_ok=True)

    # Markdown 报告
    md_content = generate_markdown(metrics)
    md_path = os.path.join(args.output, "metrics_report.md")
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"✅ Markdown 报告: {md_path}")

    if not args.md_only:
        # 精简 JSON
        flat_path = os.path.join(args.output, "metrics_summary.json")
        generate_json_report(metrics, flat_path)
        print(f"✅ 精简指标数据: {flat_path}")

        # 编码Agent 反馈（独立文件，Agent 可直接读取）
        fb_path = os.path.join(args.output, "coding_agent_feedback.json")
        fb = generate_coding_feedback_json(metrics, fb_path)
        print(f"✅ 编码Agent反馈: {fb_path}")
        if fb.get("action_required"):
            print(f"  🐛 {fb['total_bugs']} 个缺陷待修复")
        else:
            print(f"  ✅ 无待修复缺陷")

    print(f"\n📊 {metrics.get('summary_line', '')}")


if __name__ == "__main__":
    main()