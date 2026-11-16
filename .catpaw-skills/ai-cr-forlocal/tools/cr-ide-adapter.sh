#!/usr/bin/env bash
# cr-ide-adapter.sh — AI Local CR IDE 适配器入口
#
# 供 IDEA / Cursor / VS Code 插件调用，输出 IDE Diagnostic 格式 JSON
#
# 用法：
#   bash cr-ide-adapter.sh --repo <path> --branch <branch> [--base <base>] [--format <ide|raw>]
#
# 输出格式（--format ide，默认）：
#   IDE Diagnostic JSON（IDEA/Cursor/LSP 通用格式，含 file + line + severity + message）
#
# 输出格式（--format raw）：
#   引擎原始 JSON（与 DLC 格式相同）
#
# 集成示例（IDEA External Tool）：
#   Program: bash
#   Arguments: /path/to/cr-ide-adapter.sh --repo $ProjectFileDir$ --branch $GitBranch$
#   Output: 解析 JSON → Problems 面板 / Annotation

set -e

REPO_PATH=""
BRANCH=""
BASE_BRANCH="master"
OUTPUT_FORMAT="ide"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)    REPO_PATH="$2"; shift 2 ;;
    --branch)  BRANCH="$2";    shift 2 ;;
    --base)    BASE_BRANCH="$2"; shift 2 ;;
    --format)  OUTPUT_FORMAT="$2"; shift 2 ;;
    -h|--help)
      echo "用法: bash cr-ide-adapter.sh --repo <仓库路径> --branch <分支名> [--base <基准>] [--format ide|raw]"
      exit 0
      ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$REPO_PATH" ] || [ -z "$BRANCH" ]; then
  echo '{"error": "缺少必要参数 --repo 或 --branch"}' >&2
  exit 1
fi

REPO_PATH=$(realpath "$REPO_PATH")
REPO_NAME=$(basename "$REPO_PATH")
BRANCH_SAFE=$(echo "$BRANCH" | tr '/' '-')
RESULT_FILE="/tmp/ai_cr_result_${REPO_NAME}_${BRANCH_SAFE}.json"

# 导出环境变量，供 AI 引擎读取
export LOCAL_REPO_PATH="$REPO_PATH"
export LOCAL_BRANCH="$BRANCH"
export BASE_BRANCH="$BASE_BRANCH"
export CR_MODE="local"
export CR_CALLER="ide"   # ← 关键标识：IDE 模式，输出含 file+line 的 Diagnostic JSON

# 写触发信号（供 AI 引擎轮询）
TRIGGER_FILE="/tmp/ai_cr_ide_trigger_$(echo $REPO_PATH | md5sum | cut -c1-8).json"
cat > "$TRIGGER_FILE" <<EOF
{
  "repo": "$REPO_PATH",
  "branch": "$BRANCH",
  "base": "$BASE_BRANCH",
  "caller": "ide",
  "format": "$OUTPUT_FORMAT",
  "triggered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

# 等待结果（最多 180s）
WAIT=0
MAX_WAIT=180
while [ ! -f "$RESULT_FILE" ] && [ $WAIT -lt $MAX_WAIT ]; do
  sleep 2
  WAIT=$((WAIT + 2))
done

if [ ! -f "$RESULT_FILE" ]; then
  echo '{"error": "AI CR 超时，未返回结果"}' >&2
  exit 1
fi

# raw 模式：直接输出原始 JSON
if [ "$OUTPUT_FORMAT" = "raw" ]; then
  cat "$RESULT_FILE"
  exit 0
fi

# ide 模式：转换为 IDE Diagnostic JSON
python3 - "$RESULT_FILE" <<'PYEOF'
import json, sys

result_file = sys.argv[1]
with open(result_file) as f:
    data = json.load(f)

diagnostics = []
severity_map = {
    "P0": "error",    # IDE 标红，Problems 面板显示 Error
    "P1": "warning",  # IDE 标黄，Problems 面板显示 Warning
    "P2": "info",     # IDE 蓝色提示
    "P3": "hint",     # IDE 淡色提示
}

for issue in data.get("issues", []):
    level = issue.get("level", "P2")
    diagnostics.append({
        "file": issue.get("file", ""),
        "line": issue.get("line", 1),
        "column": 1,
        "severity": severity_map.get(level, "info"),
        "code": level,
        "message": f"[{level}] {issue.get('title', '')}",
        "detail": issue.get("detail", ""),
        "suggestion": issue.get("suggestion", ""),
        "source": "AI-CR"
    })

output = {
    "version": "1.0",
    "repo": data.get("repo", ""),
    "branch": data.get("branch", ""),
    "conclusion": data.get("cr_result", "UNKNOWN"),
    "summary": data.get("summary", ""),
    "km_doc_url": data.get("km_doc_url", ""),
    "diagnostics": diagnostics,
    "stats": {
        "p0": data.get("p0_count", 0),
        "p1": data.get("p1_count", 0),
        "p2": data.get("p2_count", 0),
        "p3": data.get("p3_count", 0),
    }
}

print(json.dumps(output, ensure_ascii=False, indent=2))
PYEOF
