#!/usr/bin/env python3
"""全流程编排入口：依次执行采集 → 清洗 → 计算 → 打标 → 输出。"""

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def step(name, cmd, fail_msg=None):
    """执行一个步骤，失败时可选终止"""
    print(f"\n{'='*60}")
    print(f"  ▶ {name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        msg = fail_msg or f"❌ 步骤失败: {name}"
        print(msg)
        sys.exit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser(description="E2E 测试指标全流程")
    parser.add_argument("report_dir", nargs="?", default=".run",
                        help="report.json 所在目录（默认 .run）")
    parser.add_argument("--mapping", help="mapping.yaml 路径（可选）")
    parser.add_argument("--output", default=".metrics", help="输出目录（默认 .metrics）")
    parser.add_argument("--skip-label", action="store_true", help="跳过人工打标")
    parser.add_argument("--previous", help="上一次 metrics.json 路径（回归对比用）")
    parser.add_argument("--from", dest="from_stage", default="collect",
                        choices=["collect", "clean", "calc", "label", "report"],
                        help="从指定阶段开始")
    args = parser.parse_args()

    output = os.path.abspath(args.output)
    os.makedirs(output, exist_ok=True)

    # ── Phase 1: 采集 ──────────────────────────────────────────────────────
    if args.from_stage in ("collect",):
        mapping_opt = f"--mapping {args.mapping}" if args.mapping else ""
        step("Phase 1: 数据采集 (Collect)",
             f"python3 collector.py {args.report_dir} {mapping_opt} --output {output}")

    # ── Phase 2: 清洗 ──────────────────────────────────────────────────────
    if args.from_stage in ("collect", "clean"):
        step("Phase 2: 数据清洗 (Clean)",
             f"python3 cleaner.py --collected {output}/collected.json --output {output}")

    # ── Phase 3: 计算 ──────────────────────────────────────────────────────
    if args.from_stage in ("collect", "clean", "calc"):
        label_opt = f"--label {output}/labeling_result.json" if os.path.isfile(f"{output}/labeling_result.json") else ""
        prev_opt = f"--previous {args.previous}" if args.previous else ""
        step("Phase 3: 指标计算 + 回归对比 + 编码Agent反馈 (Calculate)",
             f"python3 calculator.py --cleaned {output}/cleaned.json {label_opt} {prev_opt} --output {output}")

    # ── Phase 4: 打标 ──────────────────────────────────────────────────────
    if not args.skip_label and args.from_stage in ("collect", "clean", "calc", "label"):
        step("Phase 4: 人工打标 (Label)",
             f"python3 labeler.py --metrics {output}/metrics.json --output {output}")

    # ── Phase 5: 输出 ──────────────────────────────────────────────────────
    metrics_path = f"{output}/metrics_final.json" if os.path.isfile(f"{output}/metrics_final.json") else f"{output}/metrics.json"
    if args.from_stage in ("collect", "clean", "calc", "label", "report"):
        step("Phase 5: 输出报告 (Output)",
             f"python3 reporter.py --metrics {metrics_path} --output {output}")

    # 最终摘要
    print(f"\n{'='*60}")
    print("  ✅ 全流程完成")
    print(f"{'='*60}")
    print(f"  输出目录: {output}")
    for name in ["metrics.json", "metrics_final.json", "metrics_report.md", "metrics_summary.json", "coding_agent_feedback.json"]:
        path = os.path.join(output, name)
        if os.path.isfile(path):
            print(f"    - {name} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()