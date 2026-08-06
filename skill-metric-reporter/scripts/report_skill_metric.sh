#!/usr/bin/env bash
# report_skill_metric.sh
#
# 功能：上报 Skill 运行时指标。
#       通过 --phase 指定上报时机（skill_start 或 skill_end），脚本内部自动获取当前毫秒时间戳。
#
# 参数：
#   --request-id     <id>          必填，对话 ID（优先取 conversationId，其次 requestId/turnId，其次 sessionId）
#   --user-mis       <mis>         必填，用户 MIS 号
#   --skill-name     <skillName>   必填，Skill 名称
#   --phase          <phase>       必填，上报时机：skill_start=Skill 开始前，skill_end=Skill 结束后
#   --success        <true|false>  可选，是否执行成功；--phase skill_end 时必传
#   --failure-reason <reason>      可选，失败原因；仅当 success=false 时填写，由模型用一句话描述阻断性问题
#   --skill-id       <skillId>     可选，Skill ID
#   --skill-version  <version>     可选，Skill 版本号
#   --model-name     <modelName>   可选，使用的模型名称
#   --input-tokens   <count>       可选，Input Token 消耗量（--phase skill_end 时填写）
#   --output-tokens  <count>       可选，Output Token 消耗量（--phase skill_end 时填写）
#   --source         <source>      可选，当前客户端来源：catclaw / catdesk / catpaw / unknown
#
# 示例（开始时上报）：
#   ./report_skill_metric.sh \
#     --request-id  "req-abc123" \
#     --user-mis    "zhangsan" \
#     --skill-name  "代码审查" \
#     --phase       skill_start \
#     --skill-id    "skill_456" \
#     --model-name  "gpt-4o"
#
# 示例（结束时上报，成功）：
#   ./report_skill_metric.sh \
#     --request-id    "req-abc123" \
#     --user-mis      "zhangsan" \
#     --skill-name    "代码审查" \
#     --phase         skill_end \
#     --success       true \
#     --input-tokens  512 \
#     --output-tokens 128
#
# 示例（结束时上报，失败）：
#   ./report_skill_metric.sh \
#     --request-id      "req-abc123" \
#     --user-mis        "zhangsan" \
#     --skill-name      "代码审查" \
#     --phase           skill_end \
#     --success         false \
#     --failure-reason  "读取文件时发生 IOError，导致 Skill 提前终止"
#
# 退出码：
#   0 - 上报成功
#   1 - 参数错误
#   2 - 网络请求失败

set -euo pipefail

# ─── 默认配置 ────────────────────────────────────────────────────
SERVER_URL="${SERVER_URL:-https://mcphub.sankuai.com}"
REPORT_ENDPOINT="/public/skill/metric/report"
CONNECT_TIMEOUT=5
MAX_TIME=10

# ─── 获取当前毫秒时间戳（macOS / Linux 兼容）────────────────────
now_ms() {
    python3 -c "import time; print(int(time.time() * 1000))"
}

# ─── 参数默认值 ───────────────────────────────────────────────────
REQUEST_ID=""
USER_MIS=""
SKILL_ID=""
SKILL_NAME=""
SKILL_VERSION=""
PHASE=""
SUCCESS=""
FAILURE_REASON=""
MODEL_NAME=""
INPUT_TOKENS=""
OUTPUT_TOKENS=""
SOURCE=""

# ─── 解析命令行参数 ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --request-id)     REQUEST_ID="$2";      shift 2 ;;
        --user-mis)       USER_MIS="$2";        shift 2 ;;
        --skill-id)       SKILL_ID="$2";        shift 2 ;;
        --skill-name)     SKILL_NAME="$2";      shift 2 ;;
        --skill-version)  SKILL_VERSION="$2";   shift 2 ;;
        --phase)          PHASE="$2";           shift 2 ;;
        --success)        SUCCESS="$2";         shift 2 ;;
        --failure-reason) FAILURE_REASON="$2";  shift 2 ;;
        --model-name)     MODEL_NAME="$2";      shift 2 ;;
        --input-tokens)   INPUT_TOKENS="$2";    shift 2 ;;
        --output-tokens)  OUTPUT_TOKENS="$2";   shift 2 ;;
        --source)         SOURCE="$2";          shift 2 ;;
        -h|--help)
            sed -n '4,49p' "$0" | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo "[ERROR] 未知参数: $1" >&2
            exit 1
            ;;
    esac
done

# ─── 必填参数校验 ────────────────────────────────────────────────
validate_required() {
    local param_name="$1"
    local param_value="$2"
    if [[ -z "$param_value" ]]; then
        echo "[ERROR] 缺少必填参数: $param_name" >&2
        exit 1
    fi
}

validate_required "--request-id" "$REQUEST_ID"
validate_required "--skill-name" "$SKILL_NAME"
validate_required "--phase"      "$PHASE"

# ─── 从 openclaw.json 读取用户 MIS，优先级高于 --user-mis 参数 ────
OPENCLAW_CONFIG="${HOME}/.openclaw/openclaw.json"
if [[ -f "$OPENCLAW_CONFIG" ]] && command -v python3 &>/dev/null; then
    _OPENCLAW_MIS=$(python3 -c "
import json, sys
try:
    with open('${OPENCLAW_CONFIG}') as f:
        data = json.load(f)
    val = data.get('models', {}).get('providers', {})
    for provider in val.values():
        uid = provider.get('headers', {}).get('X-User-Id', '')
        if uid and uid.strip():
            print(uid.strip())
            sys.exit(0)
except Exception:
    pass
" 2>/dev/null)
    # 仅当读取值非空且为合法 MIS 格式（字母数字）时采用
    if [[ -n "$_OPENCLAW_MIS" ]] && [[ "$_OPENCLAW_MIS" =~ ^[a-zA-Z0-9_.-]+$ ]] && [[ "$_OPENCLAW_MIS" != "unknown" ]]; then
        USER_MIS="$_OPENCLAW_MIS"
    fi
fi

# 经过上面兜底后再校验
validate_required "--user-mis" "$USER_MIS"

# ─── phase 值校验 ────────────────────────────────────────────────
if [[ "$PHASE" != "skill_start" && "$PHASE" != "skill_end" ]]; then
    echo "[ERROR] 参数 --phase 必须为 skill_start 或 skill_end，实际值: $PHASE" >&2
    exit 1
fi

# ─── 根据 phase 自动生成时间戳 ──────────────────────────────────
CURRENT_MS=$(now_ms)
START_TIME=""
END_TIME=""
if [[ "$PHASE" == "skill_start" ]]; then
    START_TIME="$CURRENT_MS"
else
    END_TIME="$CURRENT_MS"
fi

# ─── 数值参数校验 ────────────────────────────────────────────────
validate_integer() {
    local param_name="$1"
    local param_value="$2"
    if [[ -n "$param_value" ]] && ! [[ "$param_value" =~ ^[0-9]+$ ]]; then
        echo "[ERROR] 参数 $param_name 必须为非负整数，实际值: $param_value" >&2
        exit 1
    fi
}

validate_integer "--input-tokens"  "$INPUT_TOKENS"
validate_integer "--output-tokens" "$OUTPUT_TOKENS"

# ─── success 值归一化 ─────────────────────────────────────────────
SUCCESS_LOWER=""
if [[ -n "$SUCCESS" ]]; then
    SUCCESS_LOWER=$(echo "$SUCCESS" | tr '[:upper:]' '[:lower:]')
    if [[ "$SUCCESS_LOWER" != "true" && "$SUCCESS_LOWER" != "false" ]]; then
        echo "[ERROR] 参数 --success 必须为 true 或 false，实际值: $SUCCESS" >&2
        exit 1
    fi
fi

# ─── JSON 工具函数 ────────────────────────────────────────────────
escape_json_string() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    echo "$s"
}

json_string_or_null() {
    local val="$1"
    if [[ -n "$val" ]]; then
        echo "\"$(escape_json_string "$val")\""
    else
        echo "null"
    fi
}

json_number_or_null() {
    local val="$1"
    if [[ -n "$val" ]]; then
        echo "$val"
    else
        echo "null"
    fi
}

# ─── 构造请求体 ───────────────────────────────────────────────────
REQUEST_BODY="{"
REQUEST_BODY+="\"requestId\":\"$(escape_json_string "$REQUEST_ID")\","
REQUEST_BODY+="\"userMis\":\"$(escape_json_string "$USER_MIS")\","
REQUEST_BODY+="\"skillId\":$(json_string_or_null "$SKILL_ID"),"
REQUEST_BODY+="\"skillName\":\"$(escape_json_string "$SKILL_NAME")\","
REQUEST_BODY+="\"skillVersion\":$(json_string_or_null "$SKILL_VERSION"),"
REQUEST_BODY+="\"startTime\":$(json_number_or_null "$START_TIME"),"
REQUEST_BODY+="\"endTime\":$(json_number_or_null "$END_TIME"),"
if [[ -n "$SUCCESS_LOWER" ]]; then
    REQUEST_BODY+="\"success\":${SUCCESS_LOWER},"
else
    REQUEST_BODY+="\"success\":null,"
fi
REQUEST_BODY+="\"modelName\":$(json_string_or_null "$MODEL_NAME"),"
REQUEST_BODY+="\"failureReason\":$(json_string_or_null "$FAILURE_REASON"),"
REQUEST_BODY+="\"inputTokens\":$(json_number_or_null "$INPUT_TOKENS"),"
REQUEST_BODY+="\"outputTokens\":$(json_number_or_null "$OUTPUT_TOKENS"),"
REQUEST_BODY+="\"source\":$(json_string_or_null "$SOURCE")"
REQUEST_BODY+="}"

# ─── 发送 HTTP 请求 ───────────────────────────────────────────────
if ! command -v curl &>/dev/null; then
    echo "[ERROR] 未找到 curl 命令，请先安装 curl" >&2
    exit 2
fi

REQUEST_URL="${SERVER_URL%/}${REPORT_ENDPOINT}"

HTTP_RESPONSE=$(curl \
    --silent \
    --show-error \
    --write-out "\n%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    --request POST \
    --header "Content-Type: application/json" \
    --data "$REQUEST_BODY" \
    "$REQUEST_URL" 2>&1) || {
        echo "[ERROR] 网络请求失败，请检查服务地址是否可达: $REQUEST_URL" >&2
        exit 2
    }

HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -n 1)

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
    echo "[OK] 上报成功 (HTTP $HTTP_CODE)"
    exit 0
else
    echo "[ERROR] 上报失败，HTTP 状态码: $HTTP_CODE，响应: $HTTP_BODY" >&2
    exit 2
fi
