#!/usr/bin/env bash
#
# fe-rd-workflow-multica 一键创建脚本
# ------------------------------------------------------------
# 作用：在 Multica 平台一键搭好"前端研发全流程"编排：
#   1. 创建队长 Agent（fe-rd-orchestrator）
#   2. 创建 Squad（fe-rd-squad），指定队长
#   3. 创建 7 个阶段 Agent，各自挂载对应 stageN skill
#   4. 把 7 个 Agent 加入 Squad
#   5. 写入 Squad Instructions
#
# 设计原则：参数化 / 幂等（已存在则复用） / 支持 --dry-run 预览
# 依赖：multica CLI 已登录；jq 已安装；本仓库目录结构完整。
#
# 用法：
#   ./setup-squad.sh                                # 真正执行
#   ./setup-squad.sh --dry-run                      # 只打印将执行的命令，不落地
#   ./setup-squad.sh --squad-name my-fe-rd          # 自定义 squad 名
#   ./setup-squad.sh --runtime-id <UUID>            # 直接指定运行时 ID
# ------------------------------------------------------------
set -euo pipefail

# ---------- 0. 基础变量 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$ROOT_DIR/skills"
SQUAD_INSTRUCTIONS_FILE="$ROOT_DIR/squad/orchestrator-instructions.md"

SQUAD_NAME="fe-rd-squad"
LEADER_NAME="fe-rd-orchestrator"
DRY_RUN=0
AGENT_RUNTIME_ID=""
AGENT_SUFFIX=""

# 7 个阶段：Agent 名 | 挂载的 skill 目录名 | 子 Issue 标题 | Agent 描述 | 绑定的平台 skill（逗号分隔）
# skill 目录名对应 skills/<dir>/SKILL.md；平台 skill 名对应 multica skill list 中已注册的 skill
STAGES=(
  "stage1-env-check|stage1-env-check|S1 环境与依赖检查|校验 Node/依赖/CLI 环境就绪，输出环境报告|citadel,citadel-database,fe-rd-workflow,mtsso-skills-official"
  "stage2-repo-init|stage2-repo-init|S2 仓库初始化与项目上下文|拉取仓库、确定 feature 分支、建工作目录、记录项目上下文|citadel,citadel-database,ee-code,fe-rd-workflow,mtsso-skills-official"
  "stage3-design|stage3-demand-design|S3 需求分析与技术方案设计|基于 PRD 渐进产出 spec/design/tasks 三份文档并上传学城|citadel,citadel-database,design-spec,fe-rd-workflow,mt-graphify-lite,mtsso-skills-official"
  "stage4-coding|stage4-coding|S4 物料组件与页面协议开发|在 feature 分支上完成物料组件、DUO 协议和业务逻辑编码|citadel,citadel-database,duo-protocol,ee-code,fe-rd-workflow,ingee-flex,max-material-dev,mtsso-skills-official"
  "stage5-review|stage5-review|S5 代码审查|对 feature 分支代码做多维度 CR，输出验收清单并上传学城|citadel,citadel-database,ee-code,fe-ai-review,fe-rd-workflow,mtsso-skills-official"
  "stage6-launch|stage6-launch|S6 构建发布|提交推送、创建 Draft PR、触发 FEDO 构建部署|citadel,citadel-database,duo-fedo,ee-code,ee-fedo,ee-talos,fe-rd-workflow,mtsso-skills-official"
  "stage7-feedback|stage7-feedback|S7 反馈收集与复盘|汇总全流程产物、生成交付报告上传学城、闭环流程|citadel,citadel-database,fe-rd-workflow,mtsso-skills-official"
)

# 队长绑定的平台 skill（逗号分隔）
LEADER_SKILLS="citadel,citadel-database,mtsso-skills-official,fe-rd-workflow"

# ---------- 1. 参数解析 ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)        DRY_RUN=1; shift ;;
    --squad-name)     SQUAD_NAME="$2"; shift 2 ;;
    --leader-name)    LEADER_NAME="$2"; shift 2 ;;
    --runtime-id)     AGENT_RUNTIME_ID="$2"; shift 2 ;;
    --agent-suffix)   AGENT_SUFFIX="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

# ---------- 2. 工具函数 ----------
log()  { printf '\033[0;36m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn ]\033[0m %s\n' "$*"; }
err()  { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }

# run：DRY_RUN 时只打印，否则执行
run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\033[0;90m$ %s\033[0m\n' "$*"
  else
    log "执行：$*"
    "$@"
  fi
}

# run_json：执行命令并返回 JSON stdout（dry-run 时返回 {"id":"DRYRUN-ID"} 占位）
run_json() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\033[0;90m$ %s\033[0m\n' "$*" >&2
    echo '{"id":"DRYRUN-ID"}'
  else
    "$@"
  fi
}

# extract_id：从 JSON 输出中提取 .id 字段
extract_id() {
  jq -r '.id' 2>/dev/null
}

# 检查 multica CLI（dry-run 模式下仅告警，便于无 CLI 环境预览完整流程）
check_cli() {
  if ! command -v multica >/dev/null 2>&1; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      warn "未找到 multica CLI；DRY-RUN 模式继续，仅打印将执行的命令。"
    else
      err "未找到 multica CLI，请先安装并登录（multica auth login）。"
      exit 1
    fi
  fi
  if ! command -v jq >/dev/null 2>&1; then
    err "需要 jq 来解析 CLI 输出，请先安装 jq。"
    exit 1
  fi
}

# 检查 squad 是否已存在，存在则回显其 id（幂等）
squad_id_by_name() {
  local name="$1"
  multica squad list --output json 2>/dev/null \
    | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' 2>/dev/null | head -n1
}

agent_id_by_name() {
  local name="$1"
  multica agent list --output json 2>/dev/null \
    | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' 2>/dev/null | head -n1
}

# 根据 runtime name 查找 runtime id
runtime_id_by_name() {
  local name="$1"
  multica runtime list --output json 2>/dev/null \
    | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' 2>/dev/null | head -n1
}

# 根据 skill name 列表（逗号分隔）解析为 skill id 列表（逗号分隔）
# 首次调用时缓存 skill list 结果，后续复用
SKILL_LIST_CACHE=""
resolve_skill_ids() {
  local skill_names="$1"  # 逗号分隔的 skill name
  if [[ -z "$skill_names" ]]; then
    echo ""
    return
  fi
  # 懒加载 skill list
  if [[ -z "$SKILL_LIST_CACHE" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]] && ! command -v multica >/dev/null 2>&1; then
      echo ""
      return
    fi
    SKILL_LIST_CACHE="$(multica skill list --output json 2>/dev/null)" || true
  fi
  if [[ -z "$SKILL_LIST_CACHE" ]]; then
    echo ""
    return
  fi
  # 用 jq 把 name 列表映射为 id 列表
  echo "$SKILL_LIST_CACHE" | jq -r --arg names "$skill_names" '
    ($names | split(",")) as $wanted |
    [ .[] | select(.name as $n | $wanted | index($n)) | .id ] |
    join(",")
  ' 2>/dev/null
}

# ---------- 3. 前置校验 ----------
check_cli
[[ -f "$SQUAD_INSTRUCTIONS_FILE" ]] || { err "找不到 Squad Instructions：$SQUAD_INSTRUCTIONS_FILE"; exit 1; }
log "工程根目录：$ROOT_DIR"
[[ "$DRY_RUN" -eq 1 ]] && warn "DRY-RUN 模式：只打印命令，不会真正创建任何资源。"

# ---------- 3.5 Agent 名称后缀 ----------
if [[ -z "$AGENT_SUFFIX" ]]; then
  printf '[setup] 请输入 Agent 名称后缀（可选，直接回车跳过，示例: -v2、-test）: '
  read -r AGENT_SUFFIX
fi
if [[ -n "$AGENT_SUFFIX" ]]; then
  # 确保后缀以 - 开头
  [[ "$AGENT_SUFFIX" != -* ]] && AGENT_SUFFIX="-${AGENT_SUFFIX}"
  log "Agent 名称后缀：$AGENT_SUFFIX（如 stage1-env-check${AGENT_SUFFIX}）"
else
  log "不添加 Agent 名称后缀"
fi

# ---------- 3.6 选择 Agent 运行时 ----------
if [[ -z "$AGENT_RUNTIME_ID" ]]; then
  log "正在获取可用运行时列表…"
  RUNTIME_LIST_JSON="$(multica runtime list --output json 2>/dev/null)" \
    || { err "无法获取运行时列表，请确认 multica CLI 已登录。"; exit 1; }

  # 构建可选列表
  RUNTIME_ENTRIES=()
  while IFS=$'\t' read -r rid rname; do
    [[ -n "$rid" ]] && RUNTIME_ENTRIES+=("$rid|$rname")
  done < <(echo "$RUNTIME_LIST_JSON" | jq -r '.[] | [.id, .name] | @tsv' 2>/dev/null)

  if [[ ${#RUNTIME_ENTRIES[@]} -eq 0 ]]; then
    err "未找到任何可用运行时，请先通过 multica runtime 注册。"; exit 1
  fi

  log "请选择 Agent 绑定的运行时："
  for i in "${!RUNTIME_ENTRIES[@]}"; do
    IFS='|' read -r _id _name <<< "${RUNTIME_ENTRIES[$i]}"
    echo "  $((i+1))) $_name ($_id)"
  done
  printf '  请输入编号 [1]: '
  read -r runtime_choice
  runtime_choice="${runtime_choice:-1}"

  if [[ "$runtime_choice" -ge 1 && "$runtime_choice" -le ${#RUNTIME_ENTRIES[@]} ]] 2>/dev/null; then
    IFS='|' read -r AGENT_RUNTIME_ID _selected_name <<< "${RUNTIME_ENTRIES[$((runtime_choice-1))]}"
  else
    err "无效选择：$runtime_choice"; exit 1
  fi
fi
log "已选择运行时 ID：$AGENT_RUNTIME_ID"

# ============================================================
# 执行顺序：
#   Step 1 → 创建队长 Agent（因为 Squad 创建时 --leader 为必填）
#   Step 2 → 创建 Squad 并指定 --leader（队长自动成为 Squad 成员）
#   Step 3 → 创建 7 个阶段 Agent 并加入 Squad
#   Step 4 → 写入 Squad Instructions
# ============================================================

# ---------- 4. 创建队长 Agent ----------
FULL_LEADER_NAME="${LEADER_NAME}${AGENT_SUFFIX}"
log "==== Step 1/4：创建队长 Agent [$FULL_LEADER_NAME] ===="
LEADER_ID="$(agent_id_by_name "$FULL_LEADER_NAME" || true)"
if [[ -n "${LEADER_ID:-}" && "$DRY_RUN" -eq 0 ]]; then
  warn "队长 Agent 已存在（id=$LEADER_ID），复用。"
else
  LEADER_ID="$(run_json multica agent create \
    --name "$FULL_LEADER_NAME" \
    --description "前端研发流程队长：读 Issue → 派活 → 记 evaluation → 停" \
    --instructions "$(cat "$SQUAD_INSTRUCTIONS_FILE")" \
    --runtime-id "$AGENT_RUNTIME_ID" \
    --output json | extract_id)"
  log "队长 Agent 已创建：id=$LEADER_ID"
fi

# 绑定队长的平台 skill
leader_skill_ids="$(resolve_skill_ids "$LEADER_SKILLS")"
if [[ -n "$leader_skill_ids" ]]; then
  log "  绑定队长 skill：$LEADER_SKILLS"
  run multica agent skills set "$LEADER_ID" --skill-ids "$leader_skill_ids"
else
  warn "  未能解析队长 skill id，跳过绑定。"
fi

# ---------- 5. 创建 / 复用 Squad ----------
log "==== Step 2/4：创建 Squad [$SQUAD_NAME] 并指定队长 ===="
EXIST_SQUAD="$(squad_id_by_name "$SQUAD_NAME" || true)"
if [[ -n "${EXIST_SQUAD:-}" && "$DRY_RUN" -eq 0 ]]; then
  warn "Squad [$SQUAD_NAME] 已存在（id=$EXIST_SQUAD），复用之。"
  SQUAD_ID="$EXIST_SQUAD"
  # 确保 leader 是最新的
  run multica squad update "$SQUAD_ID" --leader "$LEADER_ID"
else
  SQUAD_ID="$(run_json multica squad create \
    --name "$SQUAD_NAME" \
    --description "前端研发 7 阶段全流程编排（fe-rd-workflow Multica 版）" \
    --leader "$LEADER_ID" \
    --output json | extract_id)"
  log "Squad 已创建：id=$SQUAD_ID"
fi

# ---------- 6. 创建 7 个阶段 Agent，挂 skill，并加入 Squad ----------
log "==== Step 3/4：创建 7 个阶段 Agent 并挂载 skill ===="
declare -a AGENT_IDS=()
for entry in "${STAGES[@]}"; do
  IFS='|' read -r agent_name skill_name _issue_title agent_desc platform_skills <<< "$entry"
  skill_path="$SKILLS_DIR/$skill_name/SKILL.md"

  # 拼接后缀
  full_agent_name="${agent_name}${AGENT_SUFFIX}"

  log "-- Agent [$full_agent_name]（skill: $skill_name）"
  aid="$(agent_id_by_name "$full_agent_name" || true)"
  if [[ -z "${aid:-}" || "$DRY_RUN" -eq 1 ]]; then
    # 读取 SKILL.md 作为 Agent 指令
    instructions=""
    if [[ -f "$skill_path" ]]; then
      instructions="$(cat "$skill_path")"
    fi
    aid="$(run_json multica agent create \
      --name "$full_agent_name" \
      --description "$agent_desc" \
      --instructions "$instructions" \
      --runtime-id "$AGENT_RUNTIME_ID" \
      --output json | extract_id)"
    log "  Agent 已创建：id=$aid"
  else
    warn "  Agent 已存在（id=$aid），复用。"
  fi
  AGENT_IDS+=("$aid")

  if [[ ! -f "$skill_path" ]]; then
    warn "  未找到 $skill_path；请补齐该 stage 的 SKILL.md 后重跑或通过 agent update --instructions 手动补充。"
  fi

  # 绑定平台 skill
  if [[ -n "${platform_skills:-}" ]]; then
    skill_ids="$(resolve_skill_ids "$platform_skills")"
    if [[ -n "$skill_ids" ]]; then
      log "  绑定 skill：$platform_skills"
      run multica agent skills set "$aid" --skill-ids "$skill_ids"
    else
      warn "  未能解析 skill id，跳过绑定。"
    fi
  fi

  # 加入 Squad
  run multica squad member add "$SQUAD_ID" --member-id "$aid"
done

# ---------- 7. 写入 Squad Instructions ----------
log "==== Step 4/4：写入 Squad Instructions ===="
run multica squad update "$SQUAD_ID" --instructions "$(cat "$SQUAD_INSTRUCTIONS_FILE")"

# ---------- 8. 总结 ----------
echo
log "✅ 完成。结构概览："
echo "   Squad   : $SQUAD_NAME (id=${SQUAD_ID:-?})"
echo "   Leader  : $FULL_LEADER_NAME (id=${LEADER_ID:-?})  ← 挂 orchestrator-instructions.md"
echo "   Members : ${STAGES[*]%%|*}"
echo
log "下一步：创建 Multica Project 并派活队长即可启动流程。"
[[ "$DRY_RUN" -eq 1 ]] && warn "（以上为 DRY-RUN 预览，未真正创建。去掉 --dry-run 即可执行。）"
