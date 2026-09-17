#!/usr/bin/env python3
"""Phase 1: 数据采集（Collect）— 从 report.json / mapping.yaml 读取原始数据。"""

import json
import os
import sys


def collect_report(path):
    """采集报告主数据，返回结构化字典"""
    with open(path) as f:
        report = json.load(f)

    run_meta = {
        "run_id": report.get("id"),
        "title": report.get("title"),
        "timestamp": report.get("timestamp"),
        "duration_ms": report.get("duration_ms"),
        "device": report.get("device"),
        "platform": report.get("platform"),
        "app": report.get("app"),
        "mis": report.get("mis"),
        "run_status": report.get("run_status"),
        "skill_version": report.get("skill_version"),
    }

    batch_summary = report.get("batch_summary", {})

    cases = []
    for case in report.get("cases", []):
        cases.append({
            "case_id": case.get("case_id"),
            "case_name": case.get("case_name"),
            "status": case.get("status"),
            "summary": case.get("summary", {}),
            "steps": case.get("steps", []),
            "findings": case.get("findings", []),
            "timeline": case.get("timeline", []),
            "notes": case.get("notes", []),
        })

    return {"run_meta": run_meta, "batch_summary": batch_summary, "cases": cases}


def collect_mapping(path):
    """采集 mapping.yaml 中的 Flow → EC 用例映射"""
    try:
        import yaml
    except ImportError:
        print("⚠️  PyYAML 未安装，尝试安装...", file=sys.stderr)
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
        import yaml

    with open(path) as f:
        mapping = yaml.safe_load(f)

    flow_ec_map = {}
    for flow in mapping.get("flows", []):
        flow_path = flow.get("flow") or flow.get("path", "")
        ec_case_id = flow.get("ec_case_id") or flow.get("case_id", "")
        priority = flow.get("priority", "P2")
        page = flow.get("page", "unknown")
        if flow_path and ec_case_id:
            flow_ec_map[flow_path] = {
                "ec_case_id": ec_case_id,
                "priority": priority,
                "page": page,
            }

    gaps = mapping.get("gaps", [])
    return {"flow_ec_map": flow_ec_map, "gaps": gaps, "summary": mapping.get("summary", {})}


def find_report(report_dir):
    """在指定目录下查找 report.json"""
    candidates = [
        os.path.join(report_dir, "report.json"),
        os.path.join(report_dir, "output", "report.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def main():
    """CLI 入口：python3 collector.py <report_dir> [--mapping <yaml_path>] [--output <dir>]"""
    import argparse

    parser = argparse.ArgumentParser(description="采集 E2E 测试报告数据")
    parser.add_argument("report_dir", help="报告目录（含 report.json）")
    parser.add_argument("--mapping", help="mapping.yaml 路径（可选）")
    parser.add_argument("--output", default=".metrics", help="输出目录（默认 .metrics）")
    args = parser.parse_args()

    report_path = find_report(args.report_dir)
    if not report_path:
        print(f"❌ 找不到 report.json: {args.report_dir}")
        sys.exit(1)

    print(f"📄 读取报告: {report_path}")
    collected = collect_report(report_path)
    print(f"   → {len(collected['cases'])} 个 case, {collected['run_meta']['run_id']}")

    if args.mapping and os.path.isfile(args.mapping):
        print(f"📄 读取映射: {args.mapping}")
        mapping_data = collect_mapping(args.mapping)
        collected["mapping"] = mapping_data
        print(f"   → {len(mapping_data['flow_ec_map'])} 条 Flow-EC 映射")

    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "collected.json")
    with open(out_path, "w") as f:
        json.dump(collected, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ 已保存采集数据: {out_path}")


if __name__ == "__main__":
    main()