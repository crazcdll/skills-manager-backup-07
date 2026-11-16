#!/usr/bin/env bash
# Phase 0: 环境准备与输入检查 + 编排入口
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 默认值 ──────────────────────────────────────────────────────────────────
REPORT_DIR="${REPORT_DIR:-".run"}"
MAPPING_PATH="${MAPPING_PATH:-""}"
OUTPUT_DIR="${OUTPUT_DIR:-".metrics"}"
SKIP_LABEL="${SKIP_LABEL:-""}"
PREVIOUS_METRICS="${PREVIOUS_METRICS:-""}"

echo "=========================================="
echo "  E2E 自动化测试指标 — 数据流水线"
echo "=========================================="
echo ""

# ── 检查输入源 ─────────────────────────────────────────────────────────────
echo "▶ Phase 0: 环境检查"

REPORT_PATH=""
if [ -f "$REPORT_DIR/report.json" ]; then
  REPORT_PATH="$REPORT_DIR/report.json"
elif [ -f "$REPORT_DIR/output/report.json" ]; then
  REPORT_PATH="$REPORT_DIR/output/report.json"
fi

if [ -z "$REPORT_PATH" ]; then
  echo "❌ 找不到 report.json，请指定 REPORT_DIR"
  echo "   用法: REPORT_DIR=<目录> $0"
  exit 1
fi
echo "  ✅ 发现报告: $REPORT_PATH"

HAS_MAPPING=false
if [ -n "$MAPPING_PATH" ] && [ -f "$MAPPING_PATH" ]; then
  echo "  ✅ 发现映射表: $MAPPING_PATH"
  HAS_MAPPING=true
else
  echo "  ℹ️  未提供 mapping.yaml，EC 覆盖率将降级"
fi

mkdir -p "$OUTPUT_DIR"

# ── 中控参数 ──────────────────────────────────────────────────────────────
PYTHON="${PYTHON:-python3}"
MAPPING_ARG=""
$HAS_MAPPING && MAPPING_ARG="--mapping $MAPPING_PATH"
LABEL_ARG=""
[ -n "$SKIP_LABEL" ] && LABEL_ARG="--skip-label"
PREV_ARG=""
[ -n "$PREVIOUS_METRICS" ] && PREV_ARG="--previous $PREVIOUS_METRICS"

# ── 执行全流程 ─────────────────────────────────────────────────────────────
echo ""
echo "▶ 启动 pipeline（采集 → 清洗 → 计算 → 打标 → 输出）"

cd "$SCRIPT_DIR"
$PYTHON pipeline.py "$REPORT_DIR" \
  $MAPPING_ARG \
  --output "$OUTPUT_DIR" \
  $LABEL_ARG \
  $PREV_ARG