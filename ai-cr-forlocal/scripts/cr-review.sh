#!/usr/bin/env bash
# cr-review.sh — Step 4-Review 编排脚本
# Bug 8 修复：将 4-Review 流程从 SKILL.md 描述收编为可执行脚本
#
# 用法: bash cr-review.sh --repo <REPO_NAME> --repo-path <PATH> [--skill-root <PATH>]
#
# 功能：
#   1. 读取合并后的 issues（/tmp/cr_issues_{repo}_step4.json）
#   2. 判断是否触发复审（P0+P1 >= 3）
#   3. 调用 prep_review_input.py 预处理
#   4. 输出复审指令供主 Agent 执行（spawn 子 Agent 的 task 文本）
#   5. 复审完成后更新 issues 文件

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO="" REPO_PATH="" SKILL_ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)      REPO="$2"; shift 2 ;;
    --repo-path) REPO_PATH="$2"; shift 2 ;;
    --skill-root) SKILL_ROOT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

[ -z "$REPO" ] && { echo "❌ --repo 必填" >&2; exit 1; }
[ -z "$SKILL_ROOT" ] && SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

ISSUES_FILE="/tmp/cr_issues_${REPO}_step4.json"
DIFF_FILE="/tmp/local_cr_diff.txt"
SIGNALS_FILE="/tmp/cr_signals_${REPO}.md"

if [ ! -f "$ISSUES_FILE" ]; then
  echo "❌ Issues 文件不存在: $ISSUES_FILE" >&2
  exit 1
fi

# ── 1. 统计 P0/P1 数量，判断是否触发复审 ──
P0_P1_COUNT=$(python3 -c "
import json
with open('$ISSUES_FILE') as f:
    issues = json.load(f)
p0_p1 = sum(1 for i in issues if i.get('severity') in ('P0', 'P1'))
print(p0_p1)
" 2>/dev/null || echo 0)

if [ "$P0_P1_COUNT" -lt 3 ]; then
  echo "⏭️ P0+P1=$P0_P1_COUNT ≤ 2，跳过机器复审"
  echo "   建议人工复核该 ${P0_P1_COUNT} 条"
  echo "REVIEW_STATUS=skipped"
  exit 0
fi

echo "▶️ P0+P1=$P0_P1_COUNT ≥ 3，触发复审"

# ── 2. 读取 cr-config.yaml 判断漏报扫描开关 ──
MISS_SCAN=$(python3 -c "
import yaml, os
config_path = os.path.join('$SKILL_ROOT', 'cr-config.yaml')
try:
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}
    print('true' if cfg.get('review_miss_scan', False) else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")

echo "   漏报扫描: $MISS_SCAN"

# ── 3. 预处理（上下文预切 + 仓库预读）──
if [ ! -f "$DIFF_FILE" ]; then
  echo "⚠️ diff 文件不存在: $DIFF_FILE，复审降级" >&2
  echo "REVIEW_STATUS=degraded"
  exit 0
fi

echo "📦 预处理复审输入..."
python3 "$SKILL_ROOT/scripts/prep_review_input.py" \
  --repo "$REPO" --repo-path "$REPO_PATH" \
  --diff "$DIFF_FILE" \
  --issues "$ISSUES_FILE" \
  --signals "$SIGNALS_FILE" --skill-root "$SKILL_ROOT" 2>&1 || {
  echo "⚠️ 预处理失败，复审降级为全 confirmed" >&2
  echo "REVIEW_STATUS=degraded"
  exit 0
}

# ── 4. 判断分流策略 ──
REVIEW_META=$(python3 -c "
import json
with open('/tmp/cr_review_meta_${REPO}.json') as f:
    meta = json.load(f)
mode = meta.get('mode', 'small')
files = meta.get('file_count', 0)
issues = meta.get('p01_count', 0)
shards = len(meta.get('shards', [])) if mode == 'large' else 1
print(f'{mode}|{files}|{issues}|{shards}')
" 2>/dev/null || echo "small|0|0|1")

MODE=$(echo "$REVIEW_META" | cut -d'|' -f1)
FILE_COUNT=$(echo "$REVIEW_META" | cut -d'|' -f2)
ISSUE_COUNT=$(echo "$REVIEW_META" | cut -d'|' -f3)
SHARDS=$(echo "$REVIEW_META" | cut -d'|' -f4)

echo "📋 复审分流: mode=$MODE files=$FILE_COUNT issues=$ISSUE_COUNT shards=$SHARDS"

# ── 5. 输出完整 task 文本（主 Agent 照抄 spawn，禁止自行编造路径）──
REVIEW_RULES="/tmp/cr_review_rules_${REPO}.md"
REVIEW_MISS="/tmp/cr_review_miss_${REPO}.json"

echo ""
echo "════════════════════════════════════════════"
echo "  复审子 Agent spawn 指令"
echo "════════════════════════════════════════════"
echo ""
echo "模式: $MODE | P0/P1: $ISSUE_COUNT | 文件: $FILE_COUNT | 分片: $SHARDS"
echo "超时: 1200s | 漏报扫描: $MISS_SCAN"
echo ""

# 输出单个 task 的函数
emit_task() {
  local idx="$1"      # 1=small 只有一路; >=1 = large 分片编号
  local input_file="$2"
  local output_file="$3"
  local label="$4"   # task 标签

echo "---TASK $label BEGIN---"
echo "## 任务：P0/P1 快速复审（错报过滤）- $label"
echo ""
echo "你是 AI Code Review 流水线中的复审子 Agent。只做判定，不修改代码。"
echo ""
echo "### 输入文件（精确路径，禁止自行编造路径或创建目录）"
echo "- 输入: $input_file"
echo "- 规则: $REVIEW_RULES"
if [ "$MISS_SCAN" = "true" ] && [ "$idx" = "1" ]; then
echo "- 漏报扫描输入: $REVIEW_MISS"
fi
echo ""
echo "### 执行步骤"
echo "1. 读取 ${input_file}（JSON 数组，每条含 file/line/ruleId/severity/summary/context）"
echo "2. 读取 ${REVIEW_RULES}（规则文件合集）"
echo "3. 对每条 issue 只看注入的 context（±30 行），禁止读取仓库/diff 文件"
echo "4. 独立判定（不看原 description，避免锚定效应）："
echo "   - confirmed：问题确实存在"
echo "   - dismissed：高置信误报（必须引用具体代码证据，如"diff L42 已有 null check"）"
echo "   - to_human：上下文不足，转 confirm 留人工"
echo "5. 输出 verdict JSON 数组到 ${output_file}（文件写入工具一次性直写，禁止终端命令）"
echo ""
echo "### DISMISS 证据门槛（缺一不可）"
echo "- reason 中必须引用具体代码证据"
echo "- 证据类型限定：已有防护 / 规则不适用 / 路径不可达"
echo "- 只凭"感觉不对"→ 只能给 to_human，禁止 DISMISS"
echo ""
echo "### 输出格式"
echo "JSON 数组，每条：{\"file\":\"\",\"line\":0,\"ruleId\":\"\",\"verdict\":\"confirmed|dismissed|to_human\",\"reason\":\"\"}"
echo "写入 $output_file"
echo ""
if [ "$MISS_SCAN" = "true" ] && [ "$idx" = "1" ]; then
echo "### 漏报扫描（第二轮）"
echo "读取 $REVIEW_MISS，逐文件扫描高风险模式（NPE/资源未关闭/并发/SQL拼接/空catch）"
echo "命中的在 verdict JSON 中追加 {\"type\":\"missed\",\"file\":\"\",\"line\":0,\"pattern\":\"\",\"reason\":\"\"}"
fi
echo "---TASK $label END---"
echo ""
}

if [ "$MODE" = "large" ]; then
  for i in $(seq 1 "$SHARDS"); do
    emit_task "$i" \
      "/tmp/cr_review_input_${REPO}_shard_${i}.json" \
      "/tmp/cr_review_verdict_${REPO}_shard_${i}.json" \
      "shard-${i}"
  done
  echo "⚠️ 主 Agent spawn 时："
  echo "   - 共 $SHARDS 个子 Agent，每个使用对应 ---TASK shard-N BEGIN/END--- 之间的文本"
  echo "   - attachments 注入: 对应分片 input JSON + $REVIEW_RULES"
  echo "   - runTimeoutSeconds=1200"
  echo "   - 子 Agent 全部完成后执行：bash $SCRIPT_DIR/cr-review-apply.sh --repo $REPO"
else
  emit_task "1" \
    "/tmp/cr_review_input_${REPO}.json" \
    "/tmp/cr_review_verdict_${REPO}.json" \
    "review"
  echo "⚠️ 主 Agent spawn 时："
  echo "   1. task 用上面 ---TASK review BEGIN--- 到 ---TASK review END--- 之间的文本"
  echo "   2. attachments 注入: /tmp/cr_review_input_${REPO}.json + $REVIEW_RULES"
  if [ "$MISS_SCAN" = "true" ]; then echo "   3. 漏报扫描附件: $REVIEW_MISS"; fi
echo "   runTimeoutSeconds=1200"
  echo "   子 Agent 完成后执行：bash $SCRIPT_DIR/cr-review-apply.sh --repo $REPO"
fi

echo ""
echo "REVIEW_STATUS=ready"
