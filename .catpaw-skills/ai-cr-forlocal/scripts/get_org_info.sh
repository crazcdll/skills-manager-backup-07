#!/usr/bin/env bash
# get_org_info.sh - 获取员工姓名 + 组织架构路径
# 用法: bash get_org_info.sh <misId>
# 输出: authorName=孟木子 orgPath=服务零售组

set -euo pipefail

MIS="${1:-}"
if [ -z "$MIS" ]; then
  echo "Usage: $0 <misId>" >&2
  exit 1
fi

BASE_URL="http://group.service.meishi.sankuai.com/api/test/org"

# ── 第一步：获取员工基本信息 ──────────────────────────────
fetch_emp() {
  curl -sf --max-time 8 "${BASE_URL}/empInfo?misId=${MIS}" 2>/dev/null
}

# 最多重试 3 次
EMP_RESP=""
for i in 1 2 3; do
  EMP_RESP=$(fetch_emp)
  if echo "$EMP_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('mis') else 1)" 2>/dev/null; then
    break
  fi
  sleep 1
done

if [ -z "$EMP_RESP" ]; then
  echo "authorName=${MIS} orgPath=未知组织"
  exit 0
fi

# 提取基础字段
AUTHOR_NAME=$(echo "$EMP_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('name','') or d.get('mis',''))
" 2>/dev/null)

ORG_ID=$(echo "$EMP_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('orgId',''))
" 2>/dev/null)

ORG_NAME=$(echo "$EMP_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('orgName',''))
" 2>/dev/null)

# ── 第二步：尝试获取多级组织路径 ────────────────────────────
# 尝试通过 orgId 获取组织树路径
ORG_PATH=""
if [ -n "$ORG_ID" ]; then
  ORG_TREE_RESP=$(curl -sf --max-time 8 "${BASE_URL}/orgInfo?orgId=${ORG_ID}" 2>/dev/null || true)
  if [ -n "$ORG_TREE_RESP" ]; then
    ORG_PATH=$(echo "$ORG_TREE_RESP" | python3 -c "
import sys,json
try:
  d=json.load(sys.stdin)
  # 尝试常见的路径字段
  for key in ['orgNamePath','namePath','fullPath','orgPath','path']:
    v = d.get(key,'')
    if v:
      print(v)
      sys.exit(0)
  # 如果没有路径字段，直接用 orgName
  print(d.get('orgName',''))
except:
  pass
" 2>/dev/null || true)
  fi
fi

# 兜底：直接用 empInfo 里的 orgName
if [ -z "$ORG_PATH" ]; then
  ORG_PATH="$ORG_NAME"
fi

# 最终兜底
[ -z "$AUTHOR_NAME" ] && AUTHOR_NAME="$MIS"
[ -z "$ORG_PATH" ] && ORG_PATH="未知组织"

echo "authorName=${AUTHOR_NAME} orgPath=${ORG_PATH}"
