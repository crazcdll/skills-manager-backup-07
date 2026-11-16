#!/usr/bin/env python3
"""4-Merge: 合并所有子 Agent 的 Issue JSON 文件，去重后写入 step4.json

用法: python3 merge_issues.py --repo <REPO_NAME> [--issues-dir /tmp]

去重规则（对齐 ai-quality-cr-agent 设计）:
1. 精确重复（同 file + line + ruleId）→ 去重，保留首个
2. 完全重叠（同 file + line + anomalyType）→ 合并为一条
   - ruleId 加号拼接（CR: 在前 MT: 在后 L2: 次之 CU: 在最后 BL: 不参与拼装）
   - mergedRuleIds 记录原始各方
   - severity 取更高者
   - description/risk/suggestion/code 取内容更丰富的一方
3. 部分重叠（同 file + line 但 anomalyType 不同）→ 各自独立保留
4. 4-D 与 4-A/4-B/4-C 命中同 file+line+同类问题 → 保留 4-A/B/C 的，丢弃 4-D 的重复项
   （4-D 提供额外业务上下文时可合并到 description 中）
"""

import json
import glob
import os
import sys
import argparse
from collections import defaultdict

SEVERITY_ORDER = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}

# source 字段标识来源
# step4a → 4-A, step4b → 4-B, step4c → 4-C, step4d → 4-D, step4d_logic → 4-D-logic (full 档拆分)
# main_p0/main_p1/main_p3 → 4-A 分路
SOURCE_4D = {'step4d', '4d', 'main_4d', 'step4d_core', 'step4d_logic'}


def load_issues(repo: str, issues_dir: str = '/tmp') -> list:
    """加载所有子 Agent 输出的 Issue JSON 文件"""
    all_issues = []
    pattern = os.path.join(issues_dir, f'cr_issues_{repo}_*.json')
    # 也收集 .json.tmp（子 Agent 只写了 .tmp 未完成 mv 的遗留产物）
    tmp_pattern = os.path.join(issues_dir, f'cr_issues_{repo}_*.json.tmp')
    all_files = sorted(glob.glob(pattern)) + sorted(glob.glob(tmp_pattern))
    seen = set()
    files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            files.append(f)
    
    for f in files:
        basename = os.path.basename(f)
        # 跳过合并产物自身
        if '_step4.json' in basename or '_merged.json' in basename:
            continue
        # .tmp 文件：若对应正式文件存在且完好则跳过（正式版优先）；否则作为恢复源
        if basename.endswith('.tmp'):
            main_f = f[:-4]
            if main_f in seen and os.path.exists(main_f):
                # 正式文件在处理列表中，先验证它是否完好
                try:
                    with open(main_f, encoding='utf-8') as fh:
                        d = json.load(fh)
                        if isinstance(d, list) or (isinstance(d, dict) and isinstance(d.get('issues'), list)):
                            continue  # 正式文件完好，跳过 .tmp
                except Exception:
                    pass  # 正式文件损坏，用 .tmp
        
        try:
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
                # 兼容两种格式：裸数组 [...] 或 {repo,branch,issues:[...]} 包装对象
                issues = data if isinstance(data, list) else (data.get('issues') if isinstance(data, dict) else None)
                if isinstance(issues, list):
                    # 标注来源文件名（用于 4-D 优先丢弃判断）
                    for i in issues:
                        if 'source' not in i or not i['source']:
                            i['source'] = basename[:-len('.json.tmp')] if basename.endswith('.json.tmp') else (basename[:-len('.tmp')] if basename.endswith('.tmp') else basename)
                    all_issues.extend(issues)
                    fmt = '数组' if isinstance(data, list) else 'dict 包装'
                    print(f'  ✅ {basename}: {len(issues)} 条（{fmt}）')
                else:
                    print(f'  ⚠️ {basename}: 既非 JSON 数组也无 issues 字段，跳过')
        except (json.JSONDecodeError, OSError) as e:
            # 原子写兜底：子 Agent 只写了 .tmp 未 mv → 用 .tmp 恢复
            tmp_f = f + '.tmp'
            if os.path.exists(tmp_f):
                try:
                    with open(tmp_f, encoding='utf-8') as fh:
                        data = json.load(fh)
                        issues = data if isinstance(data, list) else (data.get('issues') if isinstance(data, dict) else None)
                        if isinstance(issues, list):
                            os.replace(tmp_f, f)
                            for i in issues:
                                if 'source' not in i or not i['source']:
                                    i['source'] = basename[:-len('.json.tmp')] if basename.endswith('.json.tmp') else (basename[:-len('.tmp')] if basename.endswith('.tmp') else basename)
                            all_issues.extend(issues)
                            print(f'  ✅ {basename}（从 .tmp 恢复）: {len(issues)} 条')
                            continue
                except Exception:
                    pass
            print(f'  ⚠️ {basename}: JSON 解析失败，跳过 ({e})')
    
    return all_issues


def is_from_4d(issue: dict) -> bool:
    """判断 issue 是否来自 4-D 子 Agent"""
    source = issue.get('source', '')
    rule_id = issue.get('ruleId', '')
    return source in SOURCE_4D or source.startswith('step4d') or source.startswith('main_4d') or rule_id.startswith('BL:')


def merge_two(a: dict, b: dict) -> dict:
    """合并两条 issue（完全重叠场景）
    
    - ruleId 加号拼接（排序：CR:、MT:、L2:、CU:、FE:；BL: 不参与）
    - mergedRuleIds 记录原始各方
    - severity 取更高者
    - description/risk/suggestion/code 取内容更丰富的一方
    """
    # ruleId 拼装
    PREFIX_ORDER = {'CR:': 0, 'MT:': 1, 'L2:': 2, 'CU:': 3, 'FE:': 4, 'BL:': 5}
    all_rids = set()
    for i in (a, b):
        rid = i.get('ruleId', '')
        if rid:
            # 拆开已有的合并 ruleId
            for part in rid.split(' + '):
                part = part.strip()
                if part:
                    all_rids.add(part)
    
    # 4-D 的 BL: 不参与 ruleId 拼装，但记录到 mergedRuleIds
    bl_rids = {r for r in all_rids if r.startswith('BL:')}
    non_bl_rids = all_rids - bl_rids
    
    sorted_rids = sorted(non_bl_rids, key=lambda r: PREFIX_ORDER.get(r[:3], 9))
    merged_rule_id = ' + '.join(sorted_rids) if sorted_rids else (a.get('ruleId', '') or b.get('ruleId', ''))
    
    # mergedRuleIds 记录全部原始 ruleId
    existing_merged = set()
    for i in (a, b):
        existing_merged.update(i.get('mergedRuleIds', []))
        rid = i.get('ruleId', '')
        if rid:
            for part in rid.split(' + '):
                part = part.strip()
                if part:
                    existing_merged.add(part)
    existing_merged.update(bl_rids)
    
    # severity 取更高者
    sev_a = a.get('severity', 'P3')
    sev_b = b.get('severity', 'P3')
    primary = a if SEVERITY_ORDER.get(sev_a, 3) <= SEVERITY_ORDER.get(sev_b, 3) else b
    secondary = b if primary is a else a
    
    merged = dict(primary)  # 以 severity 更高的为基础
    merged['ruleId'] = merged_rule_id
    merged['mergedRuleIds'] = sorted(existing_merged) if existing_merged else []
    
    # description/risk/suggestion/code 取内容更丰富的一方
    for field in ('description', 'risk', 'suggestion', 'code'):
        val_p = primary.get(field, '') or ''
        val_s = secondary.get(field, '') or ''
        if len(val_s) > len(val_p):
            merged[field] = val_s
    
    return merged


def dedup_issues(issues: list) -> list:
    """三级去重（对齐 ai-quality-cr-agent 设计）
    
    1. 精确重复（同 file + line + ruleId）→ 保留首个
    2. 完全重叠（同 file + line + anomalyType）→ 合并为一条
    3. 4-D 与 4-A/B/C 命中同 file+line+同类问题 → 丢弃 4-D 的重复项
    """
    # === 第一级：4-D 优先丢弃 ===
    # 先按 file+line 分组，如果 4-D 和 4-A/B/C 命中同一位置+同类问题，丢弃 4-D
    non_4d = []
    four_d = []
    for i in issues:
        if is_from_4d(i):
            four_d.append(i)
        else:
            non_4d.append(i)
    
    # 建 4-A/B/C 的 (file, line, anomalyType) 索引
    non_4d_keys = set()
    for i in non_4d:
        key = (i.get('file', ''), i.get('line', 0), i.get('anomalyType', ''))
        non_4d_keys.add(key)
    
    kept_4d = []
    dropped_4d = 0
    for i in four_d:
        key = (i.get('file', ''), i.get('line', 0), i.get('anomalyType', ''))
        if key in non_4d_keys:
            dropped_4d += 1
            print(f'  🔀 4-D 去重: {i.get("ruleId","?")} @ {key[0]}:{key[1]} 与 4-A/B/C 重叠，丢弃 4-D')
        else:
            kept_4d.append(i)
    
    all_issues = non_4d + kept_4d
    if dropped_4d > 0:
        print(f'  4-D 优先丢弃: {dropped_4d} 条')
    
    # === 第二级：精确重复（同 file + line + ruleId）→ 保留首个 ===
    exact_seen = {}
    exact_dups = 0
    for i in all_issues:
        key = (i.get('file', ''), i.get('line', 0), i.get('ruleId', ''))
        if key not in exact_seen:
            exact_seen[key] = i
        else:
            exact_dups += 1
    
    if exact_dups > 0:
        print(f'  精确重复去除: {exact_dups} 条')
    
    first_pass = list(exact_seen.values())
    
    # === 第三级：完全重叠（同 file + line + anomalyType）→ 合并 ===
    overlap_groups = defaultdict(list)
    no_overlap = []
    for i in first_pass:
        # 用 anomalyType 做合并键；无 anomalyType 的不参与合并
        at = i.get('anomalyType', '')
        if not at:
            no_overlap.append(i)
            continue
        key = (i.get('file', ''), i.get('line', 0), at)
        overlap_groups[key].append(i)
    
    merged_issues = list(no_overlap)
    merged_count = 0
    for key, group in overlap_groups.items():
        if len(group) == 1:
            merged_issues.append(group[0])
        else:
            # 逐个合并
            result = group[0]
            for other in group[1:]:
                result = merge_two(result, other)
            merged_issues.append(result)
            merged_count += len(group) - 1
            print(f'  🔀 完全重叠合并: {key[0]}:{key[1]} {key[2]} → {len(group)} 条合并为 1 条')
    
    if merged_count > 0:
        print(f'  完全重叠合并: 减少 {merged_count} 条')
    
    return merged_issues


def validate_issues(issues: list) -> list:
    """基础格式校验：过滤掉缺必填字段的条目"""
    required = {'severity', 'ruleId', 'file', 'line', 'summary', 'description', 'suggestion', 'source'}
    valid = []
    for i in issues:
        missing = required - set(i.keys())
        if missing:
            print(f'  ⚠️ 缺字段 {missing}：{i.get("ruleId","?")} @ {i.get("file","?")}:{i.get("line","?")}，跳过', file=sys.stderr)
            continue
        valid.append(i)
    return valid


def main():
    parser = argparse.ArgumentParser(description='4-Merge: 合并去重子 Agent Issue JSON')
    parser.add_argument('--repo', required=True, help='仓库名（用于匹配 /tmp/cr_issues_{repo}_*.json）')
    parser.add_argument('--issues-dir', default='/tmp', help='Issue 文件目录（默认 /tmp）')
    parser.add_argument('--output', help='输出文件路径（默认 /tmp/cr_issues_{repo}_step4.json）')
    args = parser.parse_args()
    
    output_path = args.output or os.path.join(args.issues_dir, f'cr_issues_{args.repo}_step4.json')
    
    print(f'📦 合并 {args.repo} 的 Issue 文件...')
    
    # 1. 加载
    all_issues = load_issues(args.repo, args.issues_dir)
    print(f'  共加载 {len(all_issues)} 条 issue')
    
    if not all_issues:
        print('⚠️ 未收集到任何 issue（检查子 Agent 是否全部正常返回）')
    
    # 2. 校验
    valid_issues = validate_issues(all_issues)
    if len(valid_issues) < len(all_issues):
        print(f'  ⚠️ 格式校验过滤 {len(all_issues) - len(valid_issues)} 条')
    
    # 3. 去重
    print(f'🔀 去重中...')
    deduped = dedup_issues(valid_issues)
    
    # 4. 写入
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    
    # 统计
    sev_counts = defaultdict(int)
    for i in deduped:
        sev_counts[i.get('severity', 'P3')] += 1
    
    print(f'✅ 合并完成: {len(deduped)} 条 issue → {output_path}')
    print(f'   P0={sev_counts["P0"]} P1={sev_counts["P1"]} P2={sev_counts["P2"]} P3={sev_counts["P3"]}')


if __name__ == '__main__':
    main()
