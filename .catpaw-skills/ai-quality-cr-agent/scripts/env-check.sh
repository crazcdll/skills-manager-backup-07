#!/usr/bin/env bash
# Step 0：环境自检 + 配置加载
# 由 SKILL.md Step 0 引用执行。
# 规则：任何核心依赖缺失 → 直接 exit 1 终止本次 CR，不设等待点、不降级继续。
# 工具路径写死（沙箱统一环境），不做 find/mtskills path 搜索。

set -uo pipefail

# ── 0A. 配置加载（硬编码默认，废弃 cr-config.yaml）──────────────────────
export CITADEL_PARENT_ID="2771240961"          # 学城文档父目录 ID（接口非空时覆盖）
export TEAM_CHAT_GROUP_ID=""                    # 团队大象群 ID（接口非空时覆盖）

# ── 0C. 工具路径（写死）──────────────────────────────────────────────────
export SKILL_DIR="${ai_skill_directory}/ai-quality-cr-agent"
export CODE_CLI="python3 $SKILL_DIR/scripts/code_cli.py"
export REPO_SEARCH="python3 $SKILL_DIR/scripts/repo_search.py"
export REPO_SEARCH_JSON="python3 $SKILL_DIR/scripts/repo_search_json.py"
export REPO_SEARCH_AVAILABLE=true
export DOMAIN_KNOWLEDGE_PATH="$SKILL_DIR/references/checklists/domain-knowledge.md"

echo "✅ 配置已加载（硬编码默认）"
echo "   SKILL_DIR=$SKILL_DIR"
echo "   CITADEL_PARENT_ID=$CITADEL_PARENT_ID"
echo "   DOMAIN_KNOWLEDGE_PATH=$DOMAIN_KNOWLEDGE_PATH"
echo ""

# ── 0B. 工具依赖检查 ──────────────────────────────────────────────────
SKILL_CHECK_PASS=true

# 1. code_cli.py（内置，核心依赖，缺失 = 沙箱异常）
CODE_CLI_PATH="$SKILL_DIR/scripts/code_cli.py"
if [ ! -f "$CODE_CLI_PATH" ]; then
  echo "❌ [code_cli] 内置脚本缺失：$CODE_CLI_PATH → 沙箱异常，终止"
  SKILL_CHECK_PASS=false
else
  if ! $CODE_CLI user-info > /dev/null 2>&1; then
    echo "❌ [code_cli] Cookie 失效 → 请确认浏览器已打开 dev.sankuai.com（localhost:9222）"
    SKILL_CHECK_PASS=false
  else
    echo "✅ [code_cli] 可用"
  fi
fi

# 2. repo_search.py（内置，核心依赖，缺失 = 沙箱异常）
REPO_SEARCH_PATH="$SKILL_DIR/scripts/repo_search.py"
if [ ! -f "$REPO_SEARCH_PATH" ]; then
  echo "❌ [repo_search] 内置脚本缺失：$REPO_SEARCH_PATH → 沙箱异常，终止"
  SKILL_CHECK_PASS=false
else
  if $REPO_SEARCH --help > /dev/null 2>&1; then
    echo "✅ [repo_search] 可用"
  else
    echo "❌ [repo_search] 脚本存在但执行失败 → 沙箱异常，终止"
    SKILL_CHECK_PASS=false
  fi
fi

# 2b. repo_search_json.py（机器可读搜索入口，缺失 = 不允许继续）
REPO_SEARCH_JSON_PATH="$SKILL_DIR/scripts/repo_search_json.py"
if [ ! -f "$REPO_SEARCH_JSON_PATH" ]; then
  echo "❌ [repo_search_json] 内置脚本缺失：$REPO_SEARCH_JSON_PATH → 沙箱异常，终止"
  SKILL_CHECK_PASS=false
else
  if $REPO_SEARCH_JSON --help > /dev/null 2>&1; then
    echo "✅ [repo_search_json] 可用"
  else
    echo "❌ [repo_search_json] 脚本存在但执行失败 → 沙箱异常，终止"
    SKILL_CHECK_PASS=false
  fi
fi

# 3. citadel（Step 6 学城文档，核心依赖；oa-skills 沙箱未预置，缺失则自动安装）
if ! command -v oa-skills > /dev/null 2>&1; then
  echo "ℹ️  [citadel] oa-skills 未安装，自动安装中..."
  if npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com > /dev/null 2>&1; then
    echo "✅ [citadel] oa-skills 安装成功"
  else
    echo "❌ [citadel] oa-skills 安装失败 → Step 6 学城文档不可用"
    SKILL_CHECK_PASS=false
  fi
fi
if [ "$SKILL_CHECK_PASS" = "true" ]; then
  if oa-skills citadel --help > /dev/null 2>&1; then
    echo "✅ [citadel] 可用"
  else
    echo "❌ [citadel] oa-skills 存在但 citadel 子命令不可用"
    SKILL_CHECK_PASS=false
  fi
fi

# 4. ee-ones（可选，Step 1 ONES 上下文，缺失不阻塞）
if command -v ones > /dev/null 2>&1; then
  echo "✅ [ee-ones] 可用"
else
  echo "ℹ️  [ee-ones] 未安装（可选）→ 无 ONES ID 时不影响流程"
fi

echo ""
if [ "$SKILL_CHECK_PASS" = "false" ]; then
  echo "⛔ 环境自检失败，核心依赖缺失，终止本次 CR"
  exit 1
fi

echo "✅ 环境自检全部通过，开始执行 CR 流程"
