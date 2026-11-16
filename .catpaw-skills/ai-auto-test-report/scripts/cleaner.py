#!/usr/bin/env python3
"""Phase 2: 数据清洗（Clean）— 失败分类、EC 映射注入、阶段耗时拆分。"""

import os
import json
from collections import Counter


# ── 失败分类规则引擎 ──────────────────────────────────────────────────────────

FAILURE_CLASSIFIER = {
    "env": {
        "label": "L1 环境框架问题",
        "weight": 1,
        "keywords": [
            "超时", "timeout", "设备", "模拟器", "sandbox", "ADB", "连接失败",
            "无法连接", "无响应", "创建失败", "device", "emulator", "云模拟器",
            "云真机", "install", "安装失败", "网络", "network", "断开",
        ],
    },
    "data": {
        "label": "L2 数据依赖问题",
        "weight": 2,
        "keywords": [
            "Mock", "mock", "数据", "data", "录制", "AppMock", "appmock",
            "泳道", "swimline", "域名映射", "找不到元素", "resource-id",
            "content-desc", "view tree", "视图树", "inspect-tree",
        ],
    },
    "script": {
        "label": "L2 脚本/Flow问题",
        "weight": 3,
        "keywords": [
            "步骤", "脚本", "断言错误", "sid", "action_arg", "action_anchor",
            "landing_scheme", "steps-input", "占位符", "assert",
            "action", "参数错误",
        ],
    },
}


def classify_failure(evidence):
    """对单条 evidence 做失败分类。

    返回: {category, confidence, matched_keywords, all_matches}
    """
    reason = (evidence.get("reason") or "").lower()
    raw_fa = evidence.get("raw", {}) or {}
    fa_error = (raw_fa.get("error") or "").lower()
    fa_reason = (raw_fa.get("reason") or "").lower()

    text = f"{reason} {fa_error} {fa_reason}"

    matches = []
    for cat, rule in FAILURE_CLASSIFIER.items():
        for kw in rule["keywords"]:
            if kw.lower() in text:
                matches.append({"category": cat, "keyword": kw, "rule_label": rule["label"]})

    if matches:
        cat_counts = Counter(m["category"] for m in matches)
        top_cat = cat_counts.most_common(1)[0][0]
        top_count = cat_counts.most_common(1)[0][1]
        confidence = "high" if top_count >= 3 else ("medium" if top_count >= 2 else "low")
        return {
            "category": top_cat,
            "confidence": confidence,
            "matched_keywords": [m["keyword"] for m in matches],
            "all_matches": matches,
        }

    return {"category": "bug", "confidence": "low", "matched_keywords": [], "all_matches": []}


# ── EC 映射注入 ──────────────────────────────────────────────────────────────


def inject_ec_mapping(cases, flow_ec_map):
    """从 flow 文件名匹配 mapping.yaml 的映射关系，注入 ec_case_id"""
    import os

    for case in cases:
        flow_source = None
        for note in case.get("notes", []):
            if note.get("source") == "flow_source":
                flow_source = note.get("desc", "")
                break

        if flow_source:
            for flow_path, mapping in flow_ec_map.items():
                if os.path.basename(flow_path) == flow_source or flow_path.endswith(flow_source):
                    case["ec_case_id"] = mapping["ec_case_id"]
                    case["ec_priority"] = mapping["priority"]
                    case["ec_page"] = mapping.get("page", "unknown")
                    break

        if not case.get("ec_case_id"):
            case["ec_case_id"] = None
            case["ec_priority"] = None
            case["ec_page"] = None


# ── 阶段耗时拆分 ──────────────────────────────────────────────────────────────


def split_phase_duration(timeline):
    """从 timeline 事件拆分各阶段耗时"""
    phases = {
        "env_prep": {"label": "环境准备", "stages": ["B0", "B1", "B2", "B3"], "duration_ms": 0},
        "exec": {"label": "用例执行", "stages": ["C0", "C1", "C2", "C3", "C4", "C5"], "duration_ms": 0},
        "report": {"label": "报告生成", "stages": ["T0", "T1", "T2"], "duration_ms": 0},
    }

    for event in timeline:
        stage_id = event.get("id", "")
        duration = event.get("duration_ms") or 0
        for phase_key, phase in phases.items():
            if any(stage_id.startswith(s) for s in phase["stages"]):
                phase["duration_ms"] += duration
                break

    total = sum(p["duration_ms"] for p in phases.values())
    for phase in phases.values():
        phase["ratio"] = round(phase["duration_ms"] / total, 4) if total > 0 else 0

    return phases


# ── 清洗主流程 ────────────────────────────────────────────────────────────────


def clean(collected, mapping_data=None):
    """全流程清洗：注入 EC 映射 + 对各 case 的 FAIL 步骤分类 + 拆分阶段耗时"""
    cases = collected.get("cases", [])

    # 注入 EC 映射
    if mapping_data and mapping_data.get("flow_ec_map"):
        inject_ec_mapping(cases, mapping_data["flow_ec_map"])
        print(f"  → EC 映射注入完成")

    # 对每个 FAIL 步骤分类
    total_fails = 0
    classified = []
    for case in cases:
        for step in case.get("steps", []):
            if step.get("ok") == 0:
                total_fails += 1
                cls = classify_failure(step.get("evidence", {}))
                step["_failure_category"] = cls["category"]
                step["_failure_confidence"] = cls["confidence"]
                classified.append({
                    "case_id": case["case_id"],
                    "sid": step["sid"],
                    "category": cls["category"],
                    "confidence": cls["confidence"],
                })

        for finding in case.get("findings", []):
            if finding.get("ok") == 0:
                total_fails += 1
                cls = classify_failure(finding.get("evidence", {}))
                finding["_failure_category"] = cls["category"]
                finding["_failure_confidence"] = cls["confidence"]

    print(f"  → 已分类 {total_fails} 个 FAIL 步骤")

    # 阶段耗时拆分（取第一个 case 的 timeline）
    if cases:
        timeline = cases[0].get("timeline", [])
        phase_breakdown = split_phase_duration(timeline)
    else:
        phase_breakdown = {}

    return {
        "phase_breakdown": phase_breakdown,
        "total_fails_classified": total_fails,
        "classification_summary": dict(Counter(item["category"] for item in classified)),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="清洗 E2E 测试数据")
    parser.add_argument("--collected", default=".metrics/collected.json", help="采集数据路径")
    parser.add_argument("--output", default=".metrics", help="输出目录")
    args = parser.parse_args()

    with open(args.collected) as f:
        collected = json.load(f)

    mapping_data = collected.get("mapping")
    result = clean(collected, mapping_data)

    result["cases"] = collected["cases"]
    result["run_meta"] = collected["run_meta"]

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "cleaned.json")
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ 已保存清洗后数据: {out_path}")


if __name__ == "__main__":
    main()