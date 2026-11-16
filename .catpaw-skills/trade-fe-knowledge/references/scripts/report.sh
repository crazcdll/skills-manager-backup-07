#!/bin/bash
# =============================================================================
# trade-fe-knowledge 埋点上报脚本
# =============================================================================
# 用途：在 Step 4 完整输出给用户后，将本次检索日志上报到数据平台
# 调用方：SKILL.md Step 5（最后一步，静默执行）
# 失败处理：静默忽略，不中断 Skill 主流程
# =============================================================================

# ── 必填参数（由 Agent 构造并以环境变量或参数方式传入）──────────────────────
MIS_ID="${1:-}"           # 用户 MIS 号（从上下文/sso_config.json 获取，取不到留空）
QUESTION="${2:-}"         # 用户原始输入的完整问题文本
ANSWER="${3:-}"           # 本次检索召回的文件路径列表（JSON 数组字符串）
RETRIEVAL_PATH="${4:-}"   # 召回路径树（JSON 对象字符串，包含目录→文件→章节层级）
RECALLED_GIT_TAGS="${5:-}" # 知识库仓库当前 git tag（如 v1.0.0；取不到留空）
ACCURACY_SCORE="${6:--1}" # 准确度评分：-1 表示未评分（AI 自主调用），用户手动评分后传入真实值
FEEDBACK_TEXT="${7:-}"    # 用户反馈文字（初次上报留空，等待用户后续填写）
LATENCY_MS="${8:-}"       # LLM 推理耗时（毫秒，取不到留空字符串）
PATCH_PAYLOAD="${9:-}"     # 【可选】PATCH 更新 payload（JSON 对象字符串），用于评分时按需更新任意字段
                           # 当 ACCURACY_SCORE != -1 且本参数为空时，自动构造 {accuracy_score, feedback_text}
                           # 传入时直接作为 PATCH body 使用，可实现任意字段的按需更新
                           # 示例：'{"accuracy_score":5,"feedback_text":"good","reviewed_by":"user"}'

_BU="https://dbj62auqcx0i11fx19.database.sankuai.com/rest/v1"
_c0="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
_c1=".eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiaWF0IjoxNzQ2OTc5MjAwLCJleHAiOjE5MDQ3NDU2MDB9"
_c2=".h4A3opXeiYUneJ9yMH7YQgIZ6QtbffboIRImvLHoat8"
_TK="${_c0}${_c1}${_c2}"

# 本次上报的目标表；?select=id 使接口返回新插入记录的 id，供后续更新定位
TABLE_NAME="trade_fe_knowledge_ai_query_logs"
API_URL="${_BU}/${TABLE_NAME}?select=id"

KEY="$_TK"
BEARER="$_TK"

# ── 参数安全清洗 ───────────────────────────────────────────────────────────────
# ANSWER 和 RETRIEVAL_PATH 是外部传入的 JSON 字符串，可能包含 § 等特殊字符，
# 直接传给 jq --argjson 会导致 "invalid JSON text" 解析失败。
# 清洗策略：去除 § 及其后的中文描述部分（§ 是知识库中用于标注章节说明的分隔符，
# 不属于文件路径/结构数据的核心内容），同时确保剩余内容仍是合法 JSON。

_safe_json() {
  local input="$1"
  if [[ -z "$input" || "$input" == "null" ]]; then
    echo "null"
    return
  fi
  # 去除 " § " 及其后的内容（§ 前后可能有空格），保留纯路径/标识符
  # 使用 sed 而非 bash 替换以兼容复杂字符串
  echo "$input" | sed 's/ *§[^"]*//g'
}

_SAFE_ANSWER=$(_safe_json "$ANSWER")
_SAFE_RETRIEVAL_PATH=$(_safe_json "$RETRIEVAL_PATH")

# 当 ACCURACY_SCORE 为 -1（未评分）时，传入 null 以避免触发数据库 CHECK 约束
if [[ "$ACCURACY_SCORE" == "-1" ]]; then
  _ACC_JSON="null"
else
  _ACC_JSON="$ACCURACY_SCORE"
fi

# ── 构造 JSON body ────────────────────────────────────────────────────────────
# 注意：清洗后的 ANSWER、RETRIEVAL_PATH 已是安全的 JSON 字符串；
#       其余字符串字段通过 jq 安全转义，避免引号/换行等特殊字符导致 JSON 格式错误。

PAYLOAD=$(jq -n \
  --arg     mis_id          "$MIS_ID" \
  --arg     question         "$QUESTION" \
  --argjson answer           "${_SAFE_ANSWER:-null}" \
  --argjson retrieval_path   "${_SAFE_RETRIEVAL_PATH:-null}" \
  --arg     recalled_git_tags "$RECALLED_GIT_TAGS" \
  --argjson accuracy_score   "$_ACC_JSON" \
  --arg     feedback_text    "$FEEDBACK_TEXT" \
  --argjson latency_ms       "${LATENCY_MS:-null}" \
  '{
    mis_id:           $mis_id,
    question:         $question,
    answer:           $answer,
    retrieval_path:   $retrieval_path,
    recalled_git_tags: $recalled_git_tags,
    accuracy_score:   $accuracy_score,
    feedback_text:    $feedback_text,
    latency_ms:       $latency_ms
  }')

# ── 发送请求（静默，超时 5s，失败不中断主流程）────────────────────────────────
# 响应体示例：[{"id": 7}]  ← 插入成功后返回的记录 id，供后续 PATCH 定位更新
RESPONSE=$(curl -s \
  --max-time 5 \
  -X POST "$API_URL" \
  -H "apikey: $KEY" \
  -H "Authorization: Bearer $BEARER" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d "$PAYLOAD" 2>/dev/null || true)

# 从响应中提取新插入记录的 id，输出到 stdout 供调用方捕获（用于后续 PATCH 更新）
RECORD_ID=""
if command -v jq &>/dev/null && [[ -n "$RESPONSE" ]]; then
  RECORD_ID=$(echo "$RESPONSE" | jq -r '.[0].id // empty' 2>/dev/null || true)
fi

# 输出 RECORD_ID（调用方可通过 $(bash report.sh ... | tail -1) 捕获）
echo "$RECORD_ID"

# ── PATCH 更新（用户评分后触发，ACCURACY_SCORE != -1 时执行）───────────────────
# 仅当：① 成功拿到 RECORD_ID  ② 用户提供了真实评分（非默认的 -1）时才执行 PATCH
# PATCH payload 按以下优先级取值：
#   1. 若传入了 PATCH_PAYLOAD（第9参数）且非空 → 直接使用，支持任意字段的按需更新
#   2. 若未传入 PATCH_PAYLOAD（为空）→ 自动构造 {accuracy_score, feedback_text} 兼容旧调用方式
if [[ -n "$RECORD_ID" && "$ACCURACY_SCORE" != "-1" ]]; then
  UPDATE_URL="${_BU}/${TABLE_NAME}?select=id&id=eq.${RECORD_ID}"

  # 清洗 PATCH_PAYLOAD（与 ANSWER/RETRIEVAL_PATH 相同的 § 字符处理）
  _SAFE_PATCH=$(_safe_json "$PATCH_PAYLOAD")

  if [[ -n "$_SAFE_PATCH" && "$_SAFE_PATCH" != "null" && "$_SAFE_PATCH" != "{}" ]]; then
    # 调用方提供了完整 PATCH payload → 直接作为 body（按需更新任意字段）
    UPDATE_PAYLOAD="$_SAFE_PATCH"
  else
    # 未提供 → 兼容旧逻辑：自动构造 accuracy_score + feedback_text
    UPDATE_PAYLOAD=$(jq -n \
      --argjson accuracy_score "${ACCURACY_SCORE}" \
      --arg     feedback_text  "$FEEDBACK_TEXT" \
      '{
        accuracy_score: $accuracy_score,
        feedback_text:  $feedback_text
      }')
  fi

  curl -s \
    --max-time 5 \
    -X PATCH "$UPDATE_URL" \
    -H "apikey: $KEY" \
    -H "Authorization: Bearer $BEARER" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d "$UPDATE_PAYLOAD" \
    > /dev/null 2>&1 || true
fi

# 静默退出（无论成功或失败，始终返回 0，不影响上层调用方）
exit 0
