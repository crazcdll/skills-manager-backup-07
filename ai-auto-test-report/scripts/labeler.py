#!/usr/bin/env python3
"""Phase 4: 人工打标（Label）— 展示待确认项、收集打标结果、重新计算。"""

import json
import os
import sys


def load_metrics(path):
    """加载指标数据"""
    with open(path) as f:
        return json.load(f)


def show_pending(metrics):
    """展示待人工确认的 FAIL 分类"""
    fp = metrics.get("metrics", {}).get("false_positive", {})
    if not fp:
        print("暂无 FAIL 数据")
        return []

    print("\n=== 待人工确认的 FAIL 分类 ===")
    print(f"总失败数: {fp.get('total_issues', 0)}")
    print(f"AI 预分类:")
    for cat, info in fp.get("by_category", {}).items():
        print(f"  {info['label']}: {info['count']} 项")
    print()

    pending = []
    print("=== 低置信度（需人工确认）===")
    for detail in fp.get("details", []):
        cls = detail.get("classification", {})
        if cls.get("confidence") in ("low", "medium"):
            pending.append(detail)
            print(f"  [{detail.get('case_name', '?')}] {detail.get('sid', '?')}: {detail.get('desc', '')}")
            print(f"    AI分类: {cls.get('category')} (置信度: {cls.get('confidence')})")
            print(f"    匹配关键词: {cls.get('matched_keywords', [])}")
            print()

    return pending


def collect_labeling(pending_items):
    """收集人工打标结果（交互式）"""
    if not pending_items:
        print("✅ 无需人工打标，所有 FAIL 已高置信度分类")
        return {"defects": [], "adjustments": []}

    print("\n===== 人工打标 =====")
    print("以下为 AI 对 FAIL 步骤的自动分类结果，请逐项确认或修正：")
    print("（直接回车 = 确认 AI 分类；输入新分类 = 覆盖）")
    print("可选分类: env / data / script / bug")
    print()

    adjustments = []
    for item in pending_items:
        cls = item.get("classification", {})
        ai_cat = cls.get("category", "unknown")
        print(f"Case: {item.get('case_name', '?')} | Step: {item.get('sid', '?')} | desc: {item.get('desc', '')}")
        user_input = input(f"> 确认分类 [{ai_cat}]: ").strip()
        if user_input and user_input != ai_cat:
            adjustments.append({
                "case_id": item.get("case_id"),
                "sid": item.get("sid"),
                "original_category": ai_cat,
                "corrected_category": user_input,
            })
            print(f"    → 人工修正为: {user_input}")
        print()

    return {"defects": [], "adjustments": adjustments}


def apply_labeling(metrics, labeling):
    """根据打标结果修正指标数据并重新计算"""
    adjustments = labeling.get("adjustments", [])
    if not adjustments:
        print("ℹ️  无修正项，指标保持不变")
        return metrics

    fp = metrics.get("metrics", {}).get("false_positive", {})
    details = fp.get("details", [])

    # 应用修正
    adj_map = {}
    for adj in adjustments:
        key = (adj["case_id"], adj["sid"])
        adj_map[key] = adj["corrected_category"]

    corrected = []
    for d in details:
        key = (d.get("case_id"), d.get("sid"))
        if key in adj_map:
            d["classification"]["category"] = adj_map[key]
            d["classification"]["confidence"] = "manual"
        corrected.append(d)

    # 重新统计
    from collections import Counter
    cats = Counter(d["classification"]["category"] for d in corrected)
    false_positives = sum(cats[c] for c in ("env", "data", "script"))
    valid_issues = cats.get("bug", 0)
    total = len(corrected)
    labels = {"env": "L1 环境框架", "data": "L2 数据依赖", "script": "L2 脚本/Flow", "bug": "L3 业务缺陷"}

    metrics["metrics"]["false_positive"] = {
        "total_issues": total,
        "false_positives": false_positives,
        "valid_issues": valid_issues,
        "false_positive_rate": round(false_positives / total, 4) if total > 0 else 0,
        "valid_rate": round(valid_issues / total, 4) if total > 0 else 0,
        "by_category": {c: {"count": cats.get(c, 0), "label": labels.get(c, c)} for c in labels},
        "details": corrected,
    }

    metrics["labeling"] = labeling
    print(f"✅ 已应用 {len(adjustments)} 项人工修正")
    return metrics


def main():
    import argparse

    parser = argparse.ArgumentParser(description="E2E 测试指标人工打标")
    parser.add_argument("--metrics", default=".metrics/metrics.json", help="指标数据路径")
    parser.add_argument("--output", default=".metrics", help="输出目录")
    parser.add_argument("--non-interactive", action="store_true", help="非交互模式（仅展示不收集）")
    args = parser.parse_args()

    metrics = load_metrics(args.metrics)
    pending = show_pending(metrics)

    if args.non_interactive:
        return

    labeling = collect_labeling(pending)

    # 保存打标结果
    os.makedirs(args.output, exist_ok=True)
    label_path = os.path.join(args.output, "labeling_result.json")
    with open(label_path, "w") as f:
        json.dump(labeling, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存打标结果: {label_path}")

    # 应用修正
    final_metrics = apply_labeling(metrics, labeling)
    final_path = os.path.join(args.output, "metrics_final.json")
    with open(final_path, "w") as f:
        json.dump(final_metrics, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存最终指标: {final_path}")


if __name__ == "__main__":
    main()