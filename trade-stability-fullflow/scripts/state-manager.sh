#!/bin/bash
# ============================================================
# 稳定性全流程 — 状态管理脚本
# 兼容 macOS bash 3.x（不使用 declare -A）
#
# 用法:
#   初始化:  ./state-manager.sh init <issue_id> [signal_raw] [enter_step]
#   读取状态: ./state-manager.sh read <issue_id>
#   更新步骤: ./state-manager.sh update <issue_id> <step_name> <status> [json_patch_file]
#   推进状态: ./state-manager.sh advance <issue_id>
#   列出所有: ./state-manager.sh list
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_DIR="${SKILL_ROOT}/states"
TEMPLATE="${SCRIPT_DIR}/state-template.json"

mkdir -p "$STATE_DIR"

# --- 步骤定义（顺序 + 元数据），用平面变量避免 declare -A ---

# 步骤顺序（空格分隔）
STEP_ORDER="S1_INFO_FETCH S2_CHANGE_QUERY S3_CHANGE_STOP S4_DIAGNOSIS S5_REMEDIATION S6_REPORT"

# 每个步骤的显示名称和子 Skill 路径
step_display() {
  case "$1" in
    S1_INFO_FETCH)  echo "信息提取" ;;
    S2_CHANGE_QUERY) echo "变更查询" ;;
    S3_CHANGE_STOP) echo "止损决策与执行" ;;
    S4_DIAGNOSIS)   echo "排查根因" ;;
    S5_REMEDIATION) echo "代码修复" ;;
    S6_REPORT)      echo "复盘报告" ;;
    *) echo "未知" ;;
  esac
}

step_skill() {
  case "$1" in
    S1_INFO_FETCH)  echo "references/trade-stability-information-fetch/SKILL.md" ;;
    S2_CHANGE_QUERY) echo "references/trade-stability-change-query/SKILL.md" ;;
    S3_CHANGE_STOP) echo "references/trade-stability-change-stop/SKILL.md" ;;
    S4_DIAGNOSIS)   echo "references/trade-stability-issue-diagnosis/SKILL.md" ;;
    S5_REMEDIATION) echo "references/trade-stability-issue-remediation/SKILL.md" ;;
    S6_REPORT)      echo "references/trade-stability-issue-report/SKILL.md" ;;
    *) echo "" ;;
  esac
}

# --- 工具函数 ---
get_timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

get_issue_file() {
  echo "${STATE_DIR}/${1}.json"
}

# JSON 读写：优先用 python3（macOS 自带），其次 jq
json_set_field() {
  local file="$1" key_path="$2" value="$3"
  python3 -c "
import json, sys
with open('$file', 'r') as f:
    data = json.load(f)
keys = '$key_path'.split('.')
obj = data
for k in keys[:-1]:
    obj = obj.setdefault(k, {})
obj[keys[-1]] = sys.argv[1]
with open('$file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
" "$value"
}

json_set_bool() {
  local file="$1" key_path="$2" value="$3"
  python3 -c "
import json, sys
with open('$file', 'r') as f:
    data = json.load(f)
keys = '$key_path'.split('.')
obj = data
for k in keys[:-1]:
    obj = obj.setdefault(k, {})
obj[keys[-1]] = sys.argv[1].lower() == 'true'
with open('$file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
" "$value"
}

json_get_field() {
  local file="$1" key_path="$2"
  python3 -c "
import json
with open('$file', 'r') as f:
    data = json.load(f)
keys = '$key_path'.split('.')
obj = data
for k in keys:
    if not isinstance(obj, dict) or k not in obj:
        print('')
        exit()
    obj = obj[k]
if obj is None:
    print('')
elif isinstance(obj, bool):
    print('true' if obj else 'false')
else:
    print(obj)
" 2>/dev/null || echo ""
}

json_merge_output() {
  local file="$1" step_name="$2" patch_file="$3"
  python3 -c "
import json
with open('$file', 'r') as f:
    data = json.load(f)
with open('$patch_file', 'r') as f:
    patch = json.load(f)
data['steps']['$step_name']['output'] = patch
with open('$file', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"
}

# --- init ---
# 用法: cmd_init <issue_id> [signal_raw] [enter_step]
# enter_step: 可选，指定直接进入的步骤名（如 S2_CHANGE_QUERY），前序步骤自动标记为 skipped
cmd_init() {
  local issue_id="$1"
  local signal_raw="${2:-}"
  local enter_step="${3:-}"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ -f "$file" ]; then
    echo "⚠️ 问题 ${issue_id} 的状态文件已存在: ${file}"
    echo "当前状态: $(json_get_field "$file" "current_state")"
    return 0
  fi
  
  cp "$TEMPLATE" "$file"
  json_set_field "$file" "issue_id" "$issue_id"
  local ts
  ts=$(get_timestamp)
  json_set_field "$file" "created_at" "$ts"
  json_set_field "$file" "updated_at" "$ts"
  if [ -n "$signal_raw" ]; then
    json_set_field "$file" "signal_raw" "$signal_raw"
  fi
  
  # 如果指定了直接进入的步骤，将前序步骤标记为 skipped
  if [ -n "$enter_step" ]; then
    local found=0
    for step in $STEP_ORDER; do
      if [ "$step" = "$enter_step" ]; then
        found=1
        json_set_field "$file" "current_state" "$enter_step"
        break
      fi
      # 前序步骤标记为 skipped
      json_set_field "$file" "steps.${step}.status" "skipped"
      json_set_bool "$file" "steps.${step}.guard_passed" "true"
    done
    
    if [ "$found" = "0" ]; then
      echo "⚠️ 未知步骤名: ${enter_step}，将以 S0_INIT 初始化"
      json_set_field "$file" "current_state" "S0_INIT"
      echo "✅ 已初始化问题状态文件: ${file}"
      echo "   issue_id: ${issue_id}"
      echo "   current_state: S0_INIT"
      return 0
    fi
    
    echo "✅ 已初始化问题状态文件（独立模式）: ${file}"
    echo "   issue_id: ${issue_id}"
    echo "   current_state: ${enter_step}"
    echo "   前序步骤已标记为 skipped"
  else
    json_set_field "$file" "current_state" "S0_INIT"
    echo "✅ 已初始化问题状态文件: ${file}"
    echo "   issue_id: ${issue_id}"
    echo "   current_state: S0_INIT"
  fi
}

# --- read ---
cmd_read() {
  local issue_id="$1"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ ! -f "$file" ]; then
    echo "❌ 问题 ${issue_id} 的状态文件不存在，请先执行 init"
    exit 1
  fi
  
  local current_state
  current_state=$(json_get_field "$file" "current_state")
  
  echo "📋 问题 ${issue_id} 状态报告"
  echo "=========================================="
  echo "当前状态: ${current_state}"
  echo ""
  echo "各步骤执行情况:"
  echo "------------------------------------------"
  printf "%-20s %-12s %-12s %-25s\n" "步骤" "状态" "守卫通过" "完成时间"
  echo "------------------------------------------"
  
  for step in $STEP_ORDER; do
    local status guard completed_at
    status=$(json_get_field "$file" "steps.${step}.status")
    guard=$(json_get_field "$file" "steps.${step}.guard_passed")
    completed_at=$(json_get_field "$file" "steps.${step}.completed_at")
    
    [ "$guard" = "true" ] && guard="✅" || guard="❌"
    [ -z "$completed_at" ] || [ "$completed_at" = "null" ] && completed_at="—"
    [ -z "$status" ] && status="—"
    
    printf "%-20s %-12s %-12s %-25s\n" "$step" "$status" "$guard" "$completed_at"
  done
  
  echo "------------------------------------------"
  echo ""
  
  # 找到下一个待执行步骤（跳过 skipped 和 completed）
  local next_step=""
  for step in $STEP_ORDER; do
    local status
    status=$(json_get_field "$file" "steps.${step}.status")
    if [ "$status" = "pending" ] || [ -z "$status" ]; then
      next_step="$step"
      break
    fi
  done
  
  if [ -n "$next_step" ]; then
    local display skill
    display=$(step_display "$next_step")
    skill=$(step_skill "$next_step")
    echo "➡️ 下一步待执行: ${next_step} (${display})"
    echo "   读取子 Skill: ${skill}"
  else
    echo "✅ 所有步骤已完成（或已跳过）"
  fi
}

# --- update ---
cmd_update() {
  local issue_id="$1"
  local step_name="$2"
  local status="$3"
  local patch_file="${4:-}"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ ! -f "$file" ]; then
    echo "❌ 问题 ${issue_id} 的状态文件不存在"
    exit 1
  fi
  
  local ts
  ts=$(get_timestamp)
  
  json_set_field "$file" "steps.${step_name}.status" "$status"
  
  if [ "$status" = "running" ]; then
    json_set_field "$file" "steps.${step_name}.started_at" "$ts"
  elif [ "$status" = "completed" ]; then
    json_set_field "$file" "steps.${step_name}.completed_at" "$ts"
    json_set_bool "$file" "steps.${step_name}.guard_passed" "true"
  fi
  
  json_set_field "$file" "updated_at" "$ts"
  
  # 如果有 patch 文件，合并 output
  if [ -n "$patch_file" ] && [ -f "$patch_file" ]; then
    json_merge_output "$file" "$step_name" "$patch_file"
  fi
  
  echo "✅ 已更新 ${step_name}: status=${status}"
}

# --- advance ---
cmd_advance() {
  local issue_id="$1"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ ! -f "$file" ]; then
    echo "❌ 问题 ${issue_id} 的状态文件不存在"
    exit 1
  fi
  
  # 找到下一个未完成步骤（跳过 completed 和 skipped）
  local next_step=""
  for step in $STEP_ORDER; do
    local status
    status=$(json_get_field "$file" "steps.${step}.status")
    if [ "$status" != "completed" ] && [ "$status" != "skipped" ]; then
      next_step="$step"
      break
    fi
  done
  
  if [ -z "$next_step" ]; then
    json_set_field "$file" "current_state" "S7_DONE"
    local ts
    ts=$(get_timestamp)
    json_set_field "$file" "updated_at" "$ts"
    echo "✅ 所有步骤已完成，状态推进到 S7_DONE"
    return 0
  fi
  
  json_set_field "$file" "current_state" "$next_step"
  local ts
  ts=$(get_timestamp)
  json_set_field "$file" "updated_at" "$ts"
  
  local display skill
  display=$(step_display "$next_step")
  skill=$(step_skill "$next_step")
  
  echo "🚦 状态推进到: ${next_step} (${display})"
  echo "   读取子 Skill: ${skill}"
  echo "   执行前请先读取该子 Skill 的完整内容"
}

# --- list ---
cmd_list() {
  echo "📋 所有问题状态列表"
  echo "=========================================="
  if [ ! -d "$STATE_DIR" ] || [ -z "$(ls -A "$STATE_DIR" 2>/dev/null)" ]; then
    echo "（暂无问题状态文件）"
    return 0
  fi
  
  printf "%-30s %-20s %-25s\n" "issue_id" "current_state" "updated_at"
  echo "------------------------------------------"
  
  for f in "$STATE_DIR"/*.json; do
    [ -f "$f" ] || continue
    local id state updated
    id=$(json_get_field "$f" "issue_id")
    state=$(json_get_field "$f" "current_state")
    updated=$(json_get_field "$f" "updated_at")
    printf "%-30s %-20s %-25s\n" "$id" "$state" "$updated"
  done
}

# --- step: read + advance + update running (3-in-1) ---
cmd_step() {
  local issue_id="$1"
  local step_name="${2:-}"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ ! -f "$file" ]; then
    echo "❌ 问题 ${issue_id} 的状态文件不存在，请先执行 init"
    exit 1
  fi
  
  # 如果没有指定步骤名，自动读取状态并推进
  if [ -z "$step_name" ]; then
    local current_state
    current_state=$(json_get_field "$file" "current_state")
    
    # 找到下一个未完成步骤
    local next_step=""
    for step in $STEP_ORDER; do
      local status
      status=$(json_get_field "$file" "steps.${step}.status")
      if [ "$status" != "completed" ] && [ "$status" != "skipped" ]; then
        next_step="$step"
        break
      fi
    done
    
    if [ -z "$next_step" ]; then
      echo "✅ 所有步骤已完成"
      json_set_field "$file" "current_state" "S7_DONE"
      local ts
      ts=$(get_timestamp)
      json_set_field "$file" "updated_at" "$ts"
      return 0
    fi
    
    step_name="$next_step"
  fi
  
  local ts
  ts=$(get_timestamp)
  
  # 推进状态到目标步骤
  json_set_field "$file" "current_state" "$step_name"
  # 标记为 running
  json_set_field "$file" "steps.${step_name}.status" "running"
  json_set_field "$file" "steps.${step_name}.started_at" "$ts"
  json_set_field "$file" "updated_at" "$ts"
  
  local display skill
  display=$(step_display "$step_name")
  skill=$(step_skill "$step_name")
  
  echo "🚦 进入步骤: ${step_name} (${display})"
  echo "   读取子 Skill: ${skill}"
  echo "   执行前请先读取该子 Skill 的完整内容"
}

# --- done（完成步骤）：update completed + advance 二合一 ---
cmd_done() {
  local issue_id="$1"
  local step_name="$2"
  local patch_file="${3:-}"
  local file
  file=$(get_issue_file "$issue_id")
  
  if [ ! -f "$file" ]; then
    echo "❌ 问题 ${issue_id} 的状态文件不存在"
    exit 1
  fi
  
  local ts
  ts=$(get_timestamp)
  
  # 标记为 completed
  json_set_field "$file" "steps.${step_name}.status" "completed"
  json_set_field "$file" "steps.${step_name}.completed_at" "$ts"
  json_set_bool "$file" "steps.${step_name}.guard_passed" "true"
  json_set_field "$file" "updated_at" "$ts"
  
  # 如果有 patch 文件，合并 output
  if [ -n "$patch_file" ] && [ -f "$patch_file" ]; then
    json_merge_output "$file" "$step_name" "$patch_file"
  fi
  
  # 自动推进到下一步
  local next_step=""
  for step in $STEP_ORDER; do
    local status
    status=$(json_get_field "$file" "steps.${step}.status")
    if [ "$status" != "completed" ] && [ "$status" != "skipped" ]; then
      next_step="$step"
      break
    fi
  done
  
  if [ -z "$next_step" ]; then
    json_set_field "$file" "current_state" "S7_DONE"
    json_set_field "$file" "updated_at" "$ts"
    echo "✅ ${step_name} 已完成。所有步骤已完成，状态推进到 S7_DONE"
  else
    json_set_field "$file" "current_state" "$next_step"
    json_set_field "$file" "updated_at" "$ts"
    local display skill
    display=$(step_display "$next_step")
    skill=$(step_skill "$next_step")
    echo "✅ ${step_name} 已完成。下一步: ${next_step} (${display})"
    echo "   子 Skill: ${skill}"
  fi
}

# --- 主入口 ---
case "${1:-}" in
  init)
    [ -z "${2:-}" ] && echo "用法: $0 init <issue_id> [signal_raw] [enter_step]" && exit 1
    cmd_init "$2" "${3:-}" "${4:-}"
    ;;
  read)
    [ -z "${2:-}" ] && echo "用法: $0 read <issue_id>" && exit 1
    cmd_read "$2"
    ;;
  update)
    [ -z "${2:-}" ] && echo "用法: $0 update <issue_id> <step_name> <status> [json_patch_file]" && exit 1
    cmd_update "$2" "$3" "${4:-}" "${5:-}"
    ;;
  advance)
    [ -z "${2:-}" ] && echo "用法: $0 advance <issue_id>" && exit 1
    cmd_advance "$2"
    ;;
  step)
    [ -z "${2:-}" ] && echo "用法: $0 step <issue_id> [step_name]" && exit 1
    cmd_step "$2" "${3:-}"
    ;;
  done)
    [ -z "${2:-}" ] && echo "用法: $0 done <issue_id> <step_name> [json_patch_file]" && exit 1
    [ -z "${3:-}" ] && echo "用法: $0 done <issue_id> <step_name> [json_patch_file]" && exit 1
    cmd_done "$2" "$3" "${4:-}"
    ;;
  list)
    cmd_list
    ;;
  *)
    echo "用法: $0 <init|step|done|read|update|advance|list> ..."
    echo ""
    echo "命令:"
    echo "  init   <issue_id> [signal_raw] [enter_step]  初始化问题状态文件（enter_step 用于独立模式，前序步骤自动 skipped）"
    echo "  step   <issue_id> [step_name]              进入下一步（read+advance+running 三合一）"
    echo "  done   <issue_id> <step_name> [patch]      完成步骤（completed+advance 二合一）"
    echo "  read   <issue_id>                            读取问题状态，查看各步骤执行情况"
    echo "  update <issue_id> <step> <status> [patch]   更新步骤状态（手动模式）"
    echo "  advance <issue_id>                           推进到下一个待执行状态（手动模式）"
    echo "  list                                         列出所有问题"
    exit 1
    ;;
esac
