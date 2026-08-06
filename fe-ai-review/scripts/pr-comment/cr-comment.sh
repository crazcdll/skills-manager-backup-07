#!/usr/bin/env bash
# cr-comment.sh — AI CR 评论发送工具
# 封装 code_cli.py 的 comment-add / comment-delete 操作，消除 AI 拼参数的不确定性
#
# 用法：
#   # 发行内评论（P0/P1）— AI 只传文件名关键词，脚本自动从 pr-changes 解析完整 path
#   bash cr-comment.sh inline \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff" \
#     --file-keyword "DealGroupExtendPriceProcessor.java" \
#     --line 42 \
#     --line-type ADDED \
#     --text "评论内容"
#
#   # 也支持直接传完整 path（兼容旧用法，但优先推荐 --file-keyword）
#   bash cr-comment.sh inline \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff" \
#     --file "price-display-service/src/main/.../Foo.java" \
#     --line 42 \
#     --line-type ADDED \
#     --text "评论内容"
#
#   # 发全局评论（P2/P3/摘要）
#   bash cr-comment.sh global \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff" \
#     --text "评论内容"
#
#   # 删除评论
#   bash cr-comment.sh delete \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff" \
#     --comment-id 50318595
#
#   # 验证评论（列出 PR 所有评论）
#   bash cr-comment.sh verify \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff"
#
#   # 列出 PR 所有变更文件的 path（用于调试路径问题）
#   bash cr-comment.sh list-paths \
#     --url "https://dev.sankuai.com/code/repo-detail/org/repo/pr/123/diff"

set -euo pipefail

# ── 1. 定位 code_cli.py ─────────────────────────────────────────────────────
# 优先级：①脚本同目录（fe-ai-review 自带副本）→ ②用户环境常见路径 → ③全局搜索兜底
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PATH="$SCRIPT_DIR/code_cli.py"
KNOWN_PATH="/root/.openclaw/workspace/.claude/skills/code-cli/code-cli/scripts/code_cli.py"

if [ -f "$LOCAL_PATH" ]; then
  CODE_CLI_PY="$LOCAL_PATH"
elif [ -f "$KNOWN_PATH" ]; then
  CODE_CLI_PY="$KNOWN_PATH"
else
  CODE_CLI_PY=$(find /root/.openclaw/workspace/.claude/skills ~/.claude/skills ~/.openclaw/skills -name code_cli.py 2>/dev/null | head -1)
fi

if [ -z "$CODE_CLI_PY" ]; then
  echo "❌ 找不到 code_cli.py（期望位置：$LOCAL_PATH）" >&2
  exit 1
fi

CODE_CLI="python3 $CODE_CLI_PY"

# ── 2. 解析子命令 ─────────────────────────────────────────────────────────────
SUBCMD="${1:-}"
shift || true

if [ -z "$SUBCMD" ]; then
  echo "用法: bash cr-comment.sh <inline|global|delete|verify|list-paths> [参数...]" >&2
  exit 1
fi

# ── 3. 解析参数 ───────────────────────────────────────────────────────────────
PR_URL=""
FILE=""
FILE_KEYWORD=""
LINE=""
LINE_TYPE="ADDED"
TEXT=""
COMMENT_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)          PR_URL="$2";        shift 2 ;;
    --file)         FILE="$2";          shift 2 ;;
    --file-keyword) FILE_KEYWORD="$2";  shift 2 ;;
    --line)         LINE="$2";          shift 2 ;;
    --line-type)    LINE_TYPE="$2";     shift 2 ;;
    --text)         TEXT="$2";          shift 2 ;;
    --comment-id)   COMMENT_ID="$2";    shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$PR_URL" ]; then
  echo "❌ 缺少 --url 参数" >&2; exit 1
fi

# ── 4. 从 pr-changes 解析完整 path（--file-keyword 模式）─────────────────────
# 输入：文件名关键词（如 "Foo.java" 或部分路径 "processor/Foo.java"）
# 输出：pr-changes 返回的完整 path（如 "src/main/.../Foo.java"），写入 FILE 变量
resolve_file_path() {
  local keyword="$1"

  # 拉取 pr-changes
  local changes_json
  changes_json=$($CODE_CLI pr-changes --url "$PR_URL" 2>&1)

  if ! echo "$changes_json" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
    echo "❌ pr-changes 返回非 JSON，无法解析路径: $changes_json" >&2
    exit 1
  fi

  # 用关键词模糊匹配（包含匹配），找所有命中的 path
  local matches
  matches=$(echo "$changes_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
keyword = sys.argv[1]
hits = [c['path'] for c in data.get('changes', []) if keyword in c['path']]
print('\n'.join(hits))
" "$keyword" 2>/dev/null)

  local match_count
  if [ -z "$matches" ]; then
    match_count=0
  else
    match_count=$(echo "$matches" | wc -l | tr -d ' ')
  fi

  if [ "$match_count" -eq 0 ]; then
    echo "❌ 在 pr-changes 中找不到包含关键词 '$keyword' 的文件" >&2
    echo "📋 所有变更文件：" >&2
    echo "$changes_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('changes', []):
    print(f\"  {c['path']}\")
" >&2
    exit 1
  fi

  if [ "$match_count" -gt 1 ]; then
    echo "⚠️  关键词 '$keyword' 匹配到多个文件，请使用更精确的关键词：" >&2
    echo "$matches" | sed 's/^/  /' >&2
    exit 1
  fi

  # 精确匹配到 1 个
  FILE="$matches"
  echo "🔍 路径解析：'$keyword' → '$FILE'"
}

# ── 5. 带重试的执行 ───────────────────────────────────────────────────────────
run_with_retry() {
  local max=4
  local interval=2
  for i in $(seq 1 $max); do
    local result
    result=$("$@" 2>&1) && echo "$result" && return 0
    echo "⚠️  第 $i 次失败: $result" >&2
    [ "$i" -lt "$max" ] && sleep $interval
  done
  echo "❌ 重试 $max 次均失败" >&2
  return 1
}

# ── 6. 执行对应操作 ───────────────────────────────────────────────────────────
case "$SUBCMD" in
  inline)
    [ -z "$LINE" ]  && { echo "❌ inline 需要 --line 参数" >&2; exit 1; }
    [ -z "$TEXT" ]  && { echo "❌ inline 需要 --text 参数" >&2; exit 1; }

    # 路径解析：优先 --file-keyword，其次 --file（兼容旧用法）
    if [ -n "$FILE_KEYWORD" ]; then
      resolve_file_path "$FILE_KEYWORD"
    elif [ -n "$FILE" ]; then
      echo "📝 使用传入路径: $FILE（建议改用 --file-keyword 更安全）"
    else
      echo "❌ inline 需要 --file-keyword 或 --file 参数" >&2; exit 1
    fi

    echo "📝 发行内评论 → $FILE:$LINE ($LINE_TYPE)"
    RESULT=$(run_with_retry $CODE_CLI comment-add \
      --url "$PR_URL" \
      --file "$FILE" \
      --line "$LINE" \
      --line-type "$LINE_TYPE" \
      --text "$TEXT")

    echo "$RESULT"

    # Bitbucket API 返回 ok=true + id 即表示行内评论已创建
    # 锚定结果由 Bitbucket 服务端决定，无需回查（回查接口结构与发送接口不一致）
    COMMENT_ID_RETURNED=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
    OK=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok',''))" 2>/dev/null)

    if [ "$OK" = "True" ] && [ -n "$COMMENT_ID_RETURNED" ]; then
      echo "✅ 行内评论发送成功（id=$COMMENT_ID_RETURNED），已带 anchor 锚定到 $FILE:$LINE"
    else
      echo "❌ 评论发送失败，请检查返回信息" >&2; exit 1
    fi
    ;;

  global)
    [ -z "$TEXT" ] && { echo "❌ global 需要 --text 参数" >&2; exit 1; }
    echo "📝 发全局评论"
    run_with_retry $CODE_CLI comment-add \
      --url "$PR_URL" \
      --text "$TEXT"
    echo "✅ 全局评论发送成功"
    ;;

  delete)
    [ -z "$COMMENT_ID" ] && { echo "❌ delete 需要 --comment-id 参数" >&2; exit 1; }
    echo "🗑️  删除评论 #$COMMENT_ID"
    run_with_retry $CODE_CLI comment-delete \
      --url "$PR_URL" \
      --comment-id "$COMMENT_ID"
    echo "✅ 删除成功"
    ;;

  verify)
    echo "🔍 验证 PR 评论列表"
    $CODE_CLI pr-comments --url "$PR_URL" 2>&1
    ;;

  list-paths)
    # 列出本 PR 所有变更文件的完整 path，供调试用
    echo "📋 PR 变更文件列表："
    $CODE_CLI pr-changes --url "$PR_URL" 2>&1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('changes', []):
    print(f\"  [{c['type']:6}] {c['path']}\")
"
    ;;

  *)
    echo "❌ 未知子命令: $SUBCMD（支持 inline / global / delete / verify / list-paths）" >&2
    exit 1
    ;;
esac
