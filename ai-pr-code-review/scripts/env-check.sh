#!/bin/bash
# ============================================================
# Step 0 一键环境自检（ai-pr-code-review 优化版）
#
# 设计思路：缓存 + 并行 + 合并
#   - 首次执行：完整检测 → 写缓存文件（~15-60s）
#   - 后续执行：读缓存 + 校验关键文件存在 → 直接输出（~0.2s）
#   - --force：强制重建缓存
#
# 输出：所有环境变量写入 ENV_FILE，主 Agent source 后直接用
# 用法：
#   bash env-check.sh [--force]
#   source /tmp/cr-env.env
# ============================================================

set -euo pipefail

ENV_FILE="/tmp/cr-env.env"
CACHE_STAMP="/tmp/cr-env-ready"
FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

# ============================================================
# 快速路径：缓存命中
# ============================================================
if [[ "$FORCE" == false && -f "$CACHE_STAMP" && -f "$ENV_FILE" ]]; then
  # 校验关键文件是否仍然存在（防止 skill 目录被删重装）
  source "$ENV_FILE" 2>/dev/null || true
  if [[ -n "${CODE_CLI_PATH:-}" && -f "$CODE_CLI_PATH" ]] && \
     [[ -n "${REPO_SEARCH_PATH:-}" && -f "$REPO_SEARCH_PATH" ]]; then
    echo "✅ ENV_CACHED: 环境缓存命中（$(cat "$CACHE_STAMP")），跳过自检"
    cat "$ENV_FILE"
    exit 0
  else
    echo "⚠️ 缓存失效（关键文件不存在），重新自检..."
  fi
fi

echo "▶️ Step 0：环境自检开始..."

# ============================================================
# 0A. mtskills CLI 安装
# ============================================================
if ! command -v mtskills &>/dev/null; then
  echo "⬇️ 0A: mtskills 未安装，正在安装..."
  npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com 2>&1 | tail -3
  if ! command -v mtskills &>/dev/null; then
    echo "❌ 0A: mtskills 安装失败"
    exit 1
  fi
fi
echo "✅ 0A: mtskills 已就绪"

# ============================================================
# 0B. Skill 依赖检测 + 并行安装缺失项
# ============================================================
REQUIRED_SKILLS="code-cli code-repo-search citadel citadel-database ee-ones"

SKILL_DIRS=(
  "$HOME/.claude/skills"
  "$HOME/.openclaw/workspace/.claude/skills"
  "/root/.openclaw/workspace/.claude/skills"
  "$HOME/.openclaw/skills"
)

check_skill_installed() {
  local skill_name="$1"
  for dir in "${SKILL_DIRS[@]}"; do
    [[ -d "$dir/$skill_name" ]] && return 0
  done
  return 1
}

MISSING=()
INSTALLED_COUNT=0
for skill in $REQUIRED_SKILLS; do
  if check_skill_installed "$skill"; then
    INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
  else
    MISSING+=("$skill")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "⬇️ 0B: 缺失 ${#MISSING[@]} 个 Skill，并行安装: ${MISSING[*]}"
  INSTALL_PIDS=()
  for skill in "${MISSING[@]}"; do
    (
      mtskills i "$skill" -y 2>&1 | tail -2
      echo "  ✅ $skill 安装完成"
    ) &
    INSTALL_PIDS+=($!)
  done
  # 等待全部安装完成
  INSTALL_FAIL=0
  for pid in "${INSTALL_PIDS[@]}"; do
    if ! wait "$pid"; then
      INSTALL_FAIL=$((INSTALL_FAIL + 1))
    fi
  done
  if [[ $INSTALL_FAIL -gt 0 ]]; then
    echo "❌ 0B: ${INSTALL_FAIL} 个 Skill 安装失败"
    exit 1
  fi
  INSTALLED_COUNT=$((INSTALLED_COUNT + ${#MISSING[@]}))
fi
echo "✅ 0B: 全部 ${INSTALLED_COUNT} 个 Skill 已就绪"

# ============================================================
# 0C. 工具路径定位（find 只在缓存 miss 时执行一次）
# ============================================================

# SKILL_DIR = ai-pr-code-review 自身的目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# 1. 优先用 Skill 内置 code_cli.py（SSO 无感登录）
CODE_CLI_PATH=""
BUILTIN="$SKILL_DIR/scripts/code_cli.py"
if [[ -f "$BUILTIN" ]]; then
  CODE_CLI_PATH="$BUILTIN"
fi

# 2. fallback：外部 code-cli Skill
if [[ -z "$CODE_CLI_PATH" ]]; then
  CODE_CLI_PATH=$(find /root/.openclaw/workspace/.claude/skills ~/.claude/skills ~/.openclaw/skills \
    -name code_cli.py -path "*/code-cli/*" -print -quit 2>/dev/null || true)
fi
if [[ -z "$CODE_CLI_PATH" ]]; then
  echo "❌ 0C: code_cli.py 未找到"
  exit 1
fi
CODE_CLI="python3 $CODE_CLI_PATH"

# code-repo-search
REPO_SEARCH_PATH=$(find /root/.openclaw/workspace/.claude/skills ~/.claude/skills ~/.openclaw/skills \
  -path "*/code-repo-search/repo_search.py" -print -quit 2>/dev/null || true)
REPO_SEARCH_AVAILABLE=true
if [[ -z "$REPO_SEARCH_PATH" ]]; then
  REPO_SEARCH_AVAILABLE=false
  REPO_SEARCH_PATH=""
  echo "⚠️ 0C: code-repo-search 未找到，Layer 2 将降级"
else
  REPO_SEARCH="python3 $REPO_SEARCH_PATH"
fi

# gitnexus（可选）
GITNEXUS_AVAILABLE=false
if command -v gitnexus &>/dev/null; then
  GITNEXUS_AVAILABLE=true
fi

echo "✅ 0C: 路径定位完成"
echo "  CODE_CLI=$CODE_CLI_PATH"
echo "  REPO_SEARCH=$REPO_SEARCH_PATH"
echo "  GITNEXUS=$GITNEXUS_AVAILABLE"

# ============================================================
# 0D. 配置加载（纯 bash grep，不依赖 Python/PyYAML）
# ============================================================
CONFIG_FILE=""
for candidate in \
  ".cr-config.yaml" \
  "$HOME/.openclaw/workspace/.cr-config.yaml" \
  "$SKILL_DIR/cr-config.yaml"; do
  if [[ -f "$candidate" ]]; then
    CONFIG_FILE="$candidate"
    break
  fi
done

# 从 YAML 提取值（简单 key-value，纯 bash）
yaml_get() {
  local key="$1" file="$2"
  grep "^  ${key}:" "$file" 2>/dev/null | sed 's/^[^:]*: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | head -1
}

TABLE_ID=""
CITADEL_PARENT_ID=""
TEAM_CHAT_GROUP_ID=""
DOMAIN_KNOWLEDGE_PATH=""
NOTIFY_MIS_LIST=""

if [[ -n "$CONFIG_FILE" ]]; then
  TABLE_ID=$(yaml_get "table_id" "$CONFIG_FILE")
  CITADEL_PARENT_ID=$(yaml_get "citadel_parent_id" "$CONFIG_FILE")
  TEAM_CHAT_GROUP_ID=$(yaml_get "chat_group_id" "$CONFIG_FILE")
  DOMAIN_KNOWLEDGE_PATH=$(yaml_get "domain_knowledge" "$CONFIG_FILE")
  NOTIFY_MIS_LIST=$(yaml_get "notify_mis" "$CONFIG_FILE")
  echo "✅ 0D: 配置已加载（$CONFIG_FILE）"
else
  echo "⚠️ 0D: 未找到配置文件，使用内置默认值"
  TABLE_ID="2751197605"
  CITADEL_PARENT_ID="2771240961"
  DOMAIN_KNOWLEDGE_PATH="references/domain-knowledge.md"
fi

# domain_knowledge 相对路径 → 绝对路径
if [[ -n "$DOMAIN_KNOWLEDGE_PATH" && "$DOMAIN_KNOWLEDGE_PATH" != /* ]]; then
  DOMAIN_KNOWLEDGE_PATH="$SKILL_DIR/$DOMAIN_KNOWLEDGE_PATH"
fi

# get_org_info.py 路径
GET_ORG_INFO_PATH="$SKILL_DIR/scripts/get_org_info.py"

# cr-comment.sh 路径
CR_COMMENT_SH="$SKILL_DIR/references/cr-comment.sh"

# notify.py 路径
NOTIFY_PY="$SKILL_DIR/scripts/notify.py"

echo "✅ 0D: 配置变量就绪"

# ============================================================
# 写缓存
# ============================================================
cat > "$ENV_FILE" <<EOF
# Auto-generated by env-check.sh — $(date)
# Source this file: source $ENV_FILE

SKILL_DIR="$SKILL_DIR"
CODE_CLI_PATH="$CODE_CLI_PATH"
CODE_CLI="python3 $CODE_CLI_PATH"
REPO_SEARCH_PATH="$REPO_SEARCH_PATH"
REPO_SEARCH="python3 $REPO_SEARCH_PATH"
REPO_SEARCH_AVAILABLE=$REPO_SEARCH_AVAILABLE
GITNEXUS_AVAILABLE=$GITNEXUS_AVAILABLE
TABLE_ID="$TABLE_ID"
CITADEL_PARENT_ID="$CITADEL_PARENT_ID"
TEAM_CHAT_GROUP_ID="$TEAM_CHAT_GROUP_ID"
DOMAIN_KNOWLEDGE_PATH="$DOMAIN_KNOWLEDGE_PATH"
NOTIFY_MIS_LIST="$NOTIFY_MIS_LIST"
GET_ORG_INFO_PATH="$GET_ORG_INFO_PATH"
CR_COMMENT_SH="$CR_COMMENT_SH"
NOTIFY_PY="$NOTIFY_PY"
CONFIG_FILE="$CONFIG_FILE"
EOF

date "+%Y-%m-%d %H:%M:%S" > "$CACHE_STAMP"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Step 0 完成 — 环境就绪"
echo "  Skill 依赖: ${INSTALLED_COUNT} 个"
echo "  code-cli: 内置SSO版"
echo "  repo-search: $( [[ "$REPO_SEARCH_AVAILABLE" == true ]] && echo '可用' || echo '不可用(降级)' )"
echo "  gitnexus: $( [[ "$GITNEXUS_AVAILABLE" == true ]] && echo '可用' || echo '不可用(跳过)' )"
echo "  配置源: ${CONFIG_FILE:-内置默认}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "ENV_FILE=$ENV_FILE"
