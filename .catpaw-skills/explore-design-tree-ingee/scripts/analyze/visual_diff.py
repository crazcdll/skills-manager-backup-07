#!/usr/bin/env python3
"""
D2C Visual Diff - 输出极简的视觉级变更摘要

用法:
    python visual_diff.py <before.json> <after.json> [--depth N]

从 match_nodes 的原始标注中提取视觉级摘要，剥离所有结构信息：
  - 不输出 texts_absorbed / texts_removed / texts_added 交叉引用
  - 不输出 similarity / structure_same 等匹配细节
  - 不输出 before/after 的对应关系（避免 Agent 推理"从哪里来"）
  - 只输出：区域名 + nodeId + 变更程度 + 文本预览

设计原则：宁缺毋滥，不给 Agent 任何做结构推理的素材。
"""

import json
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import load_json
from match_nodes import annotate_modules


def classify_matched(entry: dict) -> str:
    """判断 matched 模块的变更程度：unchanged / minor / major"""
    facts = entry["facts"]

    has_text_change = bool(facts.get("texts_added")) or bool(facts.get("texts_removed"))
    has_structure_change = not facts.get("structure_same", True)
    has_children_change = bool(facts.get("children_count"))

    desc_before = facts.get("descendants", {}).get("before", 0)
    desc_after = facts.get("descendants", {}).get("after", 0)
    desc_ratio = min(desc_before, desc_after) / max(desc_before, desc_after, 1)
    has_size_change = desc_ratio < 0.8

    if not has_text_change and not has_structure_change and not has_children_change and not has_size_change:
        return "unchanged"
    if has_size_change or has_structure_change:
        return "major"
    return "minor"


def clean_summary(raw: dict) -> dict:
    """从原始 annotator 输出生成极简视觉摘要"""

    unchanged = []
    changed = []
    new_regions = []
    gone_regions = []

    # ─── matched 模块 ───
    for entry in raw["matched"]:
        level = classify_matched(entry)
        after = entry["after"]

        if level == "unchanged":
            unchanged.append({
                "name": after["name"],
                "id": after["id"],
            })
        else:
            item = {
                "name": after["name"],
                "id": after["id"],
                "level": level,
                "nodes": after["descendants"],
            }
            # 只给文本预览，不给 added/removed 对比
            if after.get("texts_preview"):
                item["texts"] = after["texts_preview"][:5]
            changed.append(item)

    # ─── after_only 模块 ───
    # 检查是否内容实际已在 matched 模块的 before 侧存在（通过 before_only.text_absorbed 反推）
    # 但我们不暴露这个推理给 Agent——只标记为 new，让 Agent 自己看截图判断
    for entry in raw["after_only"]:
        item = {
            "name": entry["name"],
            "id": entry["id"],
            "nodes": entry["descendants"],
        }
        if entry.get("texts_preview"):
            item["texts"] = entry["texts_preview"][:5]
        new_regions.append(item)

    # ─── before_only 模块 ───
    # 不暴露 text_absorbed，只标记为 gone
    for entry in raw["before_only"]:
        item = {
            "name": entry["name"],
            "nodes": entry["descendants"],
        }
        if entry.get("texts_preview"):
            item["texts"] = entry["texts_preview"][:5]
        gone_regions.append(item)

    return {
        "unchanged": unchanged,
        "changed": changed,
        "new": new_regions,
        "gone": gone_regions,
        "counts": {
            "unchanged": len(unchanged),
            "changed": len(changed),
            "new": len(new_regions),
            "gone": len(gone_regions),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="视觉级变更摘要（剥离结构信息）",
    )
    parser.add_argument("before_json", help="旧版设计稿 JSON")
    parser.add_argument("after_json", help="新版设计稿 JSON")
    parser.add_argument("--depth", type=int, default=1)

    args = parser.parse_args()
    before = load_json(args.before_json)
    after = load_json(args.after_json)

    raw = annotate_modules(before, after, module_depth=args.depth)
    summary = clean_summary(raw)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
