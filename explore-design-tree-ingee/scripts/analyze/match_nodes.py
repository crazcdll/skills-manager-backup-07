#!/usr/bin/env python3
"""
D2C Module Annotator - 标注模块对应关系，不做行动判断

用法:
    python match_nodes.py <before.json> <after.json> [--depth N] [--verbose]

输出每个模块的对应关系和事实性标注：
  - matched:    在新旧版本中都存在，附带相似度和变化事实
  - before_only: 仅在旧版中存在
  - after_only:  仅在新版中存在

不输出 skip/patch/new/removed 等行动指令——交给 coding agent 结合代码上下文判断。
"""

import json
import argparse
import sys
from typing import Dict, List, Tuple
from collections import defaultdict

import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from _common import load_json, node_name


# ─── 基础工具 ─────────────────────────────────────────────────────────────────

def parse_px(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("px", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def collect_subtree_texts(node: Dict) -> List[str]:
    """收集子树中所有文本（去重保序）"""
    texts = []
    seen = set()
    def _walk(n):
        t = n.get("textContent", "")
        if t and t.strip():
            ts = t.strip()
            if ts not in seen:
                seen.add(ts)
                texts.append(ts)
        for c in n.get("children", []):
            _walk(c)
    _walk(node)
    return texts


def count_descendants(node: Dict) -> int:
    c = 1
    for ch in node.get("children", []):
        c += count_descendants(ch)
    return c


def subtree_structure_sig(node: Dict, max_depth: int = 3) -> str:
    def _sig(n, d):
        tag = n.get("tag", "?")
        children = n.get("children", [])
        if d >= max_depth or not children:
            return f"{tag}({len(children)})"
        child_sigs = ",".join(_sig(c, d + 1) for c in children)
        return f"{tag}[{child_sigs}]"
    return _sig(node, 0)


def extract_bbox(node: Dict) -> Dict:
    style = node.get("style", {})
    top = parse_px(style.get("top", 0))
    left = parse_px(style.get("left", 0))
    width = parse_px(style.get("width", 0))
    height = parse_px(style.get("height", 0))
    return {"top": top, "left": left, "width": width, "height": height,
            "bottom": top + height, "right": left + width}


# ─── 模块特征 ─────────────────────────────────────────────────────────────────

def module_profile(node: Dict) -> Dict:
    texts = collect_subtree_texts(node)
    style = node.get("style", {})
    children = node.get("children", [])
    return {
        "id": node.get("id", "?"),
        "name": node_name(node),
        "tag": node.get("tag", "?"),
        "descendants": count_descendants(node),
        "texts": texts,
        "text_set": set(texts),
        "children_count": len(children),
        "children_tags": [c.get("tag", "?") for c in children],
        "structure_sig": subtree_structure_sig(node, max_depth=2),
        "display": style.get("display", ""),
        "flex_dir": style.get("flexDirection", ""),
        "bbox": extract_bbox(node),
        "node": node,
    }


# ─── 模块匹配 ─────────────────────────────────────────────────────────────────

def text_overlap(a_set: set, b_set: set) -> float:
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def module_similarity(a: Dict, b: Dict) -> float:
    score = 0.0
    max_score = 0.0

    max_score += 10
    score += 10 * text_overlap(a["text_set"], b["text_set"])

    max_score += 4
    if a["name"] == b["name"]:
        score += 4
    elif a["name"] in b["name"] or b["name"] in a["name"]:
        score += 2

    max_score += 3
    if a["structure_sig"] == b["structure_sig"]:
        score += 3

    max_score += 2
    ratio = min(a["descendants"], b["descendants"]) / max(a["descendants"], b["descendants"], 1)
    score += 2 * ratio

    max_score += 1
    if a["display"] == b["display"] and a["flex_dir"] == b["flex_dir"]:
        score += 1

    return score / max_score if max_score > 0 else 0


def match_modules(old_modules: List[Dict], new_modules: List[Dict],
                  threshold: float = 0.4) -> Dict:
    pairs = []
    for i, om in enumerate(old_modules):
        for j, nm in enumerate(new_modules):
            sim = module_similarity(om, nm)
            if sim >= threshold:
                pairs.append((sim, i, j))

    pairs.sort(reverse=True)
    matches = {}
    used_old = set()
    used_new = set()
    for sim, oi, ni in pairs:
        if oi not in used_old and ni not in used_new:
            matches[oi] = (ni, sim)
            used_old.add(oi)
            used_new.add(ni)
    return matches


# ─── 事实性标注（不做行动判断）──────────────────────────────────────────────────

def annotate_facts(old_mod: Dict, new_mod: Dict) -> Dict:
    """收集两个匹配模块之间的事实性差异，不做 skip/patch 判断"""
    facts = {}

    old_texts = old_mod["text_set"]
    new_texts = new_mod["text_set"]
    added = new_texts - old_texts
    removed = old_texts - new_texts
    shared = old_texts & new_texts
    if added:
        facts["texts_added"] = sorted(added)[:15]
    if removed:
        facts["texts_removed"] = sorted(removed)[:15]
    facts["texts_shared"] = len(shared)
    facts["texts_total_before"] = len(old_texts)
    facts["texts_total_after"] = len(new_texts)

    if old_mod["children_count"] != new_mod["children_count"]:
        facts["children_count"] = {
            "before": old_mod["children_count"],
            "after": new_mod["children_count"],
        }

    facts["structure_same"] = old_mod["structure_sig"] == new_mod["structure_sig"]

    if old_mod["display"] != new_mod["display"] or old_mod["flex_dir"] != new_mod["flex_dir"]:
        facts["layout_changed"] = {
            "before": f'{old_mod["display"]} {old_mod["flex_dir"]}'.strip(),
            "after": f'{new_mod["display"]} {new_mod["flex_dir"]}'.strip(),
        }

    facts["descendants"] = {
        "before": old_mod["descendants"],
        "after": new_mod["descendants"],
    }

    if old_mod["name"] != new_mod["name"]:
        facts["name_changed"] = {
            "before": old_mod["name"],
            "after": new_mod["name"],
        }

    return facts


def detect_text_absorption(before_only_mods: List[Dict],
                           after_mods_by_id: Dict[str, Dict],
                           matched_entries: List[Dict],
                           after_only_entries: List[Dict]) -> Dict[str, Dict]:
    """
    检测 before_only 模块的文本是否被其他 after 侧模块吸收。
    返回 {before_module_id: {"absorbed_by": id, "coverage": float, ...}}
    """
    after_pools = []
    for entry in matched_entries:
        after_id = entry.get("after", {}).get("id")
        if after_id and after_id in after_mods_by_id:
            after_pools.append((after_id, entry["after"]["name"],
                               after_mods_by_id[after_id]["text_set"]))
    for entry in after_only_entries:
        after_id = entry.get("id")
        if after_id and after_id in after_mods_by_id:
            after_pools.append((after_id, entry["name"],
                               after_mods_by_id[after_id]["text_set"]))

    absorptions = {}
    for bmod in before_only_mods:
        meaningful_texts = {t for t in bmod["text_set"] if len(t) > 1}
        if not meaningful_texts:
            continue

        best_id = None
        best_name = None
        best_coverage = 0.0
        best_texts = []

        for pool_id, pool_name, pool_texts in after_pools:
            covered = meaningful_texts & pool_texts
            coverage = len(covered) / len(meaningful_texts)
            if coverage > best_coverage and coverage >= 0.3:
                best_coverage = coverage
                best_id = pool_id
                best_name = pool_name
                best_texts = sorted(covered)

        if best_id:
            absorptions[bmod["id"]] = {
                "absorbed_by": best_id,
                "absorbed_by_name": best_name,
                "coverage": round(best_coverage, 2),
                "absorbed_texts": best_texts[:10],
            }

    return absorptions


# ─── 模块过滤 ─────────────────────────────────────────────────────────────────

def is_meaningful_module(node: Dict, min_descendants: int = 3) -> bool:
    desc = count_descendants(node)
    if desc >= min_descendants:
        return True
    if node.get("textContent", "").strip():
        return True
    return False


def get_modules(root: Dict, depth: int = 1, min_descendants: int = 3) -> List[Dict]:
    if depth <= 1:
        children = root.get("children", [])
        return [module_profile(c) for c in children if is_meaningful_module(c, min_descendants)]
    modules = []
    for child in root.get("children", []):
        for grandchild in child.get("children", []):
            if is_meaningful_module(grandchild, min_descendants):
                modules.append(module_profile(grandchild))
    return modules


# ─── 序列化辅助 ────────────────────────────────────────────────────────────────

def module_summary(mod: Dict) -> Dict:
    bbox = mod["bbox"]
    result = {
        "id": mod["id"],
        "name": mod["name"],
        "tag": mod["tag"],
        "descendants": mod["descendants"],
        "children_count": mod["children_count"],
        "texts_preview": mod["texts"][:8],
    }
    if bbox["height"] > 0:
        result["bbox"] = {"top": round(bbox["top"]), "height": round(bbox["height"])}
    return result


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def annotate_modules(before_root: Dict, after_root: Dict,
                     module_depth: int = 1, verbose: bool = False) -> Dict:
    """
    标注两个设计版本的模块对应关系。
    不做行动判断，只输出事实。
    """
    before_mods = get_modules(before_root, module_depth)
    after_mods = get_modules(after_root, module_depth)

    if verbose:
        print(f"[info] Before: {len(before_mods)} modules, After: {len(after_mods)} modules",
              file=sys.stderr)

    matches = match_modules(before_mods, after_mods)
    matched_new_indices = {ni for ni, _ in matches.values()}
    matched_old_indices = set(matches.keys())
    after_mods_by_id = {m["id"]: m for m in after_mods}

    # matched
    matched_entries = []
    for old_idx, (new_idx, sim) in sorted(matches.items()):
        old_mod = before_mods[old_idx]
        new_mod = after_mods[new_idx]
        facts = annotate_facts(old_mod, new_mod)
        matched_entries.append({
            "status": "matched",
            "similarity": round(sim, 2),
            "before": module_summary(old_mod),
            "after": module_summary(new_mod),
            "facts": facts,
        })

    # after_only
    after_only_entries = []
    for j, nm in enumerate(after_mods):
        if j not in matched_new_indices:
            after_only_entries.append({
                "status": "after_only",
                **module_summary(nm),
            })

    # before_only + text absorption
    before_only_mods = [before_mods[i] for i in range(len(before_mods)) if i not in matched_old_indices]
    absorptions = detect_text_absorption(before_only_mods, after_mods_by_id,
                                         matched_entries, after_only_entries)

    before_only_entries = []
    for om in before_only_mods:
        entry = {"status": "before_only", **module_summary(om)}
        if om["id"] in absorptions:
            entry["text_absorbed"] = absorptions[om["id"]]
        before_only_entries.append(entry)

    return {
        "summary": {
            "before_modules": len(before_mods),
            "after_modules": len(after_mods),
            "matched": len(matched_entries),
            "before_only": len(before_only_entries),
            "after_only": len(after_only_entries),
            "text_absorbed": len(absorptions),
        },
        "matched": matched_entries,
        "after_only": after_only_entries,
        "before_only": before_only_entries,
    }


def main():
    parser = argparse.ArgumentParser(description="模块级对应关系标注（不做行动判断）")
    parser.add_argument("before_json", help="旧版设计稿 JSON")
    parser.add_argument("after_json", help="新版设计稿 JSON")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    before = load_json(args.before_json)
    after = load_json(args.after_json)

    result = annotate_modules(before, after, module_depth=args.depth, verbose=args.verbose)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
