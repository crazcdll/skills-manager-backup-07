#!/usr/bin/env python3
"""
rule_index.py — AI-CR forLocal 规则匹配引擎
Skill: ai-cr-forlocal

功能：diff 预扫描 → 规则匹配
输入：
  --files  文件列表（每行一个文件路径）
  --diff   diff 内容文件路径
  --index  rule-index.json 路径
输出 JSON：
  matched_groups: 匹配的分组列表
  rule_files: 每组对应的规则文件名列表
  p0_rules: P0 相关规则文件
  p1_rules: P1 相关规则文件
"""

import json
import os
import re
import sys
import argparse


def load_file_list(files_path):
    """加载文件列表"""
    try:
        with open(files_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"读取文件列表失败: {e}", file=sys.stderr)
        return []


def load_diff(diff_path):
    """加载 diff 内容"""
    try:
        with open(diff_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"读取 diff 失败: {e}", file=sys.stderr)
        return ""


def load_rule_index(index_path):
    """加载 rule-index.json"""
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取 rule-index.json 失败: {e}", file=sys.stderr)
        return {"version": "1.0", "groups": {}}


def match_groups(files, diff_text, rule_index):
    """
    匹配规则分组
    返回: matched_groups, rule_files, p0_rules, p1_rules
    """
    groups_config = rule_index.get("groups", {})
    matched_groups = []
    rule_files_map = {}

    for group_name, group_config in groups_config.items():
        trigger_files_exts = group_config.get("trigger_files", [])
        trigger_keywords = group_config.get("trigger_keywords", [])
        rules = group_config.get("rules", [])

        matched = False

        # 检查文件扩展名
        for filepath in files:
            for ext in trigger_files_exts:
                if filepath.endswith(ext):
                    matched = True
                    break
            if matched:
                break

        # 检查 diff 中的关键词
        if not matched and trigger_keywords:
            for kw in trigger_keywords:
                if kw in diff_text:
                    matched = True
                    break

        if matched:
            matched_groups.append(group_name)
            rule_files_map[group_name] = rules

    # P0 规则：所有 zero-tolerance 相关
    # 注：P0/P1 规则列表有意硬编码，不从 rule-index.json 动态加载。
    # 原因：P0/P1 规则集稳定（零容忍 + 稳定性），无需动态配置；
    # 且硬编码可避免因 rule-index.json 配置错误导致 P0/P1 规则遗漏。
    p0_rules = [
        "zero-tolerance-checklist.md",
    ]

    # P1 规则：所有 stability-security 相关
    # 注：同上，有意硬编码。
    p1_rules = [
        "stability-security-checklist.md",
    ]

    return matched_groups, rule_files_map, p0_rules, p1_rules


def main():
    parser = argparse.ArgumentParser(
        description="AI-CR forLocal 规则匹配引擎 (ai-cr-forlocal)"
    )
    parser.add_argument("--files", required=True, help="文件列表文件路径")
    parser.add_argument("--diff", required=True, help="diff 内容文件路径")
    parser.add_argument(
        "--index", required=True, help="rule-index.json 路径"
    )
    parser.add_argument("--output", default="/tmp/cr_matched_rules.json", help="输出 JSON 文件路径")
    parser.add_argument("--output-file", dest="output_file", default=None, help="输出到指定文件（大 diff 时推荐使用，避免 stdout 过大）")

    args = parser.parse_args()

    # 加载输入
    files = load_file_list(args.files)
    diff_text = load_diff(args.diff)
    rule_index = load_rule_index(args.index)

    # 匹配
    matched_groups, rule_files_map, p0_rules, p1_rules = match_groups(
        files, diff_text, rule_index
    )

    # 输出
    result = {
        "matched_groups": matched_groups,
        "rule_files": rule_files_map,
        "p0_rules": p0_rules,
        "p1_rules": p1_rules,
    }

    # 写入文件
    output_path = args.output_file or args.output
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"规则匹配完成 → {output_path}", file=sys.stderr)
    except Exception as e:
        print(f"写入输出文件失败: {e}", file=sys.stderr)

    # 同时输出到 stdout（如果未指定 --output-file，保持原行为；指定了则只输出摘要）
    if args.output_file:
        # 大 diff 模式：stdout 只输出摘要
        print(json.dumps({"matched_groups": result["matched_groups"], "output_file": output_path}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
