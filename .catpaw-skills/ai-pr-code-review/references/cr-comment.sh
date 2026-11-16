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
# 优先用 env-check.sh 注入的 $CODE_CLI_PATH
if [ -n "${CODE_CLI_PATH:-}" ] && [ -f "$CODE_CLI_PATH" ]; then
  CODE_CLI_PY="$CODE_CLI_PATH"
else
  # fallback：find -print -quit（不用 | head -1，避免 set -o pipefail 下 SIGPIPE exit 141）
  CODE_CLI_PY=$(find /root/.openclaw/workspace/.claude/skills ~/.claude/skills ~/.openclaw/skills \
    -name code_cli.py -path "*/code-cli/*" -print -quit 2>/dev/null || true)
fi

if [ -z "$CODE_CLI_PY" ]; then
  echo "❌ 找不到 code_cli.py，请先运行: mtskills i code-cli" >&2
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

# ── 4b. 去重检查（inline 专用）──────────────────────────────────────────────────
# 发评论前拉历史评论，模糊匹配：同文件 + 相近行号(±5) + text 含相同 ruleId/异常关键词
# 第一次调用缓存到 /tmp/cr-comments-{prId}.json，后续复用
COMMENTS_CACHE=""

check_dedup() {
  local file="$1"
  local line="$2"
  local text="$3"

  # 从 URL 提取 prId 用于缓存文件名
  local pr_id
  pr_id=$(echo "$PR_URL" | grep -oP '/pr/\K[0-9]+' || echo "unknown")
  COMMENTS_CACHE="/tmp/cr-comments-${pr_id}.json"

  # 第一次调用：拉取并缓存
  if [ ! -f "$COMMENTS_CACHE" ]; then
    $CODE_CLI pr-comments --url "$PR_URL" 2>/dev/null > "$COMMENTS_CACHE" || true
  fi

  # Python 模糊匹配
  local is_dup
  is_dup=$(python3 -c "
import sys, json, re

cache_file = sys.argv[1]
new_file   = sys.argv[2]
new_line   = int(sys.argv[3])
new_text   = sys.argv[4]
LINE_RANGE = 5  # 行号容差

try:
    with open(cache_file, 'r') as f:
        comments = json.load(f)
except:
    print('no'); sys.exit(0)

if not isinstance(comments, list):
    print('no'); sys.exit(0)

# 从新评论文本中提取 ruleId / 异常类型关键词
# 匹配 [P0-1] [NPE] / [MAGIC_NUMBER] / P1-01 等
rule_patterns = re.findall(r'\[([A-Z][A-Z0-9_-]+)\]', new_text)
# 也提取中文异常类型关键词：空指针、NPE、越权 等
cn_keywords = re.findall(r'[\u4e00-\u9fff]{2,6}(?:异常|风险|泄露|越权|注入|溢出)', new_text)
all_keywords = [k.upper() for k in rule_patterns] + cn_keywords

for c in comments:
    c_file = c.get('file') or ''
    c_line = c.get('line')
    c_text = c.get('text') or ''

    # 1. 文件匹配：尾部包含匹配（处理路径前缀差异）
    if not c_file or not new_file:
        continue
    shorter = min(c_file, new_file, key=len)
    longer  = max(c_file, new_file, key=len)
    if not longer.endswith(shorter) and shorter not in longer:
        continue

    # 2. 行号：全局评论无行号直接跳过，行内评论±LINE_RANGE 容差
    if c_line is None:
        continue
    if abs(c_line - new_line) > LINE_RANGE:
        continue

    # 3. 关键词模糊匹配：任一 ruleId/异常类型在历史评论中出现
    if all_keywords:
        c_text_upper = c_text.upper()
        matched = any(kw in c_text_upper or kw in c_text for kw in all_keywords)
        if matched:
            print('yes'); sys.exit(0)
    else:
        # 没提取到关键词，用文本前 50 字符比较（兜底）
        if new_text[:50] in c_text or c_text[:50] in new_text:
            print('yes'); sys.exit(0)

print('no')
" "$COMMENTS_CACHE" "$file" "$line" "$text" 2>/dev/null)

  if [ "$is_dup" = "yes" ]; then
    return 0  # 是重复
  else
    return 1  # 不是重复
  fi
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

    # 去重检查：同文件 + 相近行号 + 相同 ruleId/异常类型 → 跳过
    if check_dedup "$FILE" "$LINE" "$TEXT"; then
      echo "⏭️  跳过重复评论：$FILE:$LINE 已有相同问题的评论"
      exit 0
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
