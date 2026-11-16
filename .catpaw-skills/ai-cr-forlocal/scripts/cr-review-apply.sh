#!/usr/bin/env bash
# cr-review-apply.sh — 应用复审结果到 issues 文件
# 用法: bash cr-review-apply.sh --repo <REPO_NAME>

set -eu

REPO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ -z "$REPO" ] && { echo "❌ --repo 必填" >&2; exit 1; }

ISSUES_FILE="/tmp/cr_issues_${REPO}_step4.json"
VERDICT_GLOB="/tmp/cr_review_verdict_${REPO}*.json"

python3 -c "
import json, glob, sys

repo = '$REPO'
issues_file = '$ISSUES_FILE'

# 加载原始 issues
with open(issues_file) as f:
    issues = json.load(f)

# 加载所有 verdict 文件
verdicts = {}
for vf in sorted(glob.glob('$VERDICT_GLOB')):
    try:
        with open(vf) as f:
            data = json.load(f)
        if isinstance(data, list):
            for v in data:
                key = (v.get('file',''), v.get('line',0), v.get('ruleId',''))
                verdicts[key] = v
        elif isinstance(data, dict):
            # 兼容 reviews（step4-review-guide.md 定义）与 verdicts（旧称）
            for v in data.get('reviews', []) or data.get('verdicts', []):
                key = (v.get('file',''), v.get('line',0), v.get('ruleId',''))
                verdicts[key] = v
    except Exception as e:
        print(f'⚠️ verdict 文件解析失败: {vf} ({e})', file=sys.stderr)

if not verdicts:
    print('⚠️ 未找到 verdict 文件或为空，issues 保持不变')
    sys.exit(0)

# 应用 verdict
updated = 0
dismissed = 0
confirmed = 0
to_human = 0

for i in issues:
    key = (i.get('file',''), i.get('line',0), i.get('ruleId',''))
    v = verdicts.get(key)
    if v:
        verdict = v.get('verdict', 'confirmed')
        reason = v.get('reason', '')
        if verdict == 'dismissed':
            i['severity'] = 'dismissed'
            i['description'] = f\"[复审dismissed] {reason}\" + (f\"；{i.get('description','')}\" if i.get('description') else '')
            dismissed += 1
        elif verdict == 'confirmed':
            if reason:
                i['description'] = f\"[复审confirmed] {reason}\" + (f\"；{i.get('description','')}\" if i.get('description') else '')
            confirmed += 1
        elif verdict == 'to_human':
            # to_human → severity 转 confirm（对齐 step4-review-guide.md：留人工判断）
            i['severity'] = 'confirm'
            i['description'] = f\"[需人工复核] {reason}\" + (f\"；{i.get('description','')}\" if i.get('description') else '')
            to_human += 1
        updated += 1

# 写回
with open(issues_file, 'w') as f:
    json.dump(issues, f, ensure_ascii=False, indent=2)

# 统计
sev_counts = {}
for i in issues:
    s = i.get('severity', 'P3')
    sev_counts[s] = sev_counts.get(s, 0) + 1

print(f'✅ 复审结果已应用: 更新 {updated} 条')
print(f'   confirmed={confirmed} dismissed={dismissed} to_human={to_human}')
print(f'   最终计数: ' + ' '.join(f'{k}={v}' for k, v in sorted(sev_counts.items())))
"
