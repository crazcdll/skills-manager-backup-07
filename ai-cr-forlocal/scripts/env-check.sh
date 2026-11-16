#!/usr/bin/env bash
# Step 0：环境自检 + 团队配置加载
# 由 SKILL.md Step 0 引用执行，请勿直接修改主 SKILL.md 中的 Step 0 逻辑
# PID 级缓存（60 分钟过期），避免重复执行

# ── PID 级缓存检查 ───────────────────────────────────────────────────
# 缓存文件基于当前 PID，避免跨进程冲突
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # 提前定义:缓存命中路径的 L2 探测也依赖它
CACHE_FILE="/tmp/cr-env-cache-$$"
CACHE_TTL=60  # 分钟

if [ -f "$CACHE_FILE" ]; then
  CACHE_AGE=$(find /tmp -name "$(basename "$CACHE_FILE")" -mmin -"$CACHE_TTL" 2>/dev/null)
  if [ -n "$CACHE_AGE" ]; then
    echo "✅ 环境自检缓存命中（PID=$$, ${CACHE_TTL}min 内有效），跳过检查"
    source "$CACHE_FILE"
    # GitNexus 安装状态可能变化，每次都检测（不缓存）
    GITNEXUS_INSTALLED=false
    if command -v gitnexus &>/dev/null; then
      GITNEXUS_INSTALLED=true
  else
      export NVM_DIR="$HOME/.nvm"
      [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh" 2>/dev/null && nvm use 22 2>/dev/null
      command -v gitnexus &>/dev/null && GITNEXUS_INSTALLED=true
    fi
    export GITNEXUS_INSTALLED
    # 更新缓存中的 GitNexus 状态
    sed -i "s/export GITNEXUS_INSTALLED=.*/export GITNEXUS_INSTALLED=\"${GITNEXUS_INSTALLED}\"/" "$CACHE_FILE" 2>/dev/null
    # L2 Runner 探测不缓存（安装状态可能变化），缓存命中时仍执行
    _MTSS_RUNNER=$(bash "$_SCRIPT_DIR/fetch_l2_rules.sh" --probe-only 2>/tmp/cr_l2_probe.log)
    _MTSS_RC=$?
    if [ $_MTSS_RC -eq 0 ] && [ -n "$_MTSS_RUNNER" ]; then
      echo "✅ [mt-code-standards-setup] 可用（平台L2规则）"
      grep -q "无认证环境信号" /tmp/cr_l2_probe.log 2>/dev/null && \
        echo "⚠️  Runner 已装但无认证环境信号，运行时 L2 将跳过（在 CatPaw 内运行即可自动认证）"
    else
      echo "ℹ️  [mt-code-standards-setup] 未安装（可选）→ 平台L2规则降级，仓库内规则不受影响"
      echo "   如需团队L2规范自动拉取：mtskills i mt-code-standards-setup"
    fi
    # 仍需输出版本提醒
    echo "💡 提示：AI CR Skill 持续迭代中！"
    echo ""
    return 0 2>/dev/null || exit 0
  fi
fi

# ── 版本提醒（每次触发必须输出）──────────────────────────────────────
echo "💡 提示：AI CR Skill 持续迭代中，效果越来越好！请确保已更新到最新版："
echo "   mtskills i ai-cr-forlocal"
echo ""

# ── 0A. 团队配置加载 ──────────────────────────────────────────────────
# 优先使用 skill 目录下的 cr-config.yaml（从脚本位置推导，避免硬编码 HOME）
CR_CONFIG="$_SCRIPT_DIR/../cr-config.yaml"
if [ ! -f "$CR_CONFIG" ]; then
  CR_CONFIG=$(find ~/.openclaw/workspace -name "cr-config.yaml" 2>/dev/null | head -1)
fi
[ -z "$CR_CONFIG" ] && CR_CONFIG=$(find . -name "cr-config.yaml" -maxdepth 2 2>/dev/null | head -1)

if [ -n "$CR_CONFIG" ]; then
  echo "✅ 发现团队配置文件：$CR_CONFIG"
  CR_TABLE_ID=$(python3 -c "
import re, sys
with open('$CR_CONFIG') as f: content = f.read()
# 优先匹配 db_table_id，兼容 table_id
m = re.search(r'^(?:db_table_id|table_id):\s*(\S+)', content, re.MULTILINE)
print(m.group(1) if m else '')
")
  CR_CITADEL_PARENT=$(python3 -c "
import re, sys
with open('$CR_CONFIG') as f: content = f.read()
m = re.search(r'^citadel_parent_id:\s*(\S+)', content, re.MULTILINE)
print(m.group(1) if m else '')
")
  CR_DOMAIN_KNOWLEDGE=$(python3 -c "
import re, sys
with open('$CR_CONFIG') as f: content = f.read()
m = re.search(r'^domain_knowledge:\s*(\S+)', content, re.MULTILINE)
print(m.group(1) if m else '')
")
  CR_NOTIFY_MIS=$(python3 -c "
import re, sys
with open('$CR_CONFIG') as f: content = f.read()
m = re.search(r'^notify_mis:\s*\[([^\]]+)\]', content, re.MULTILINE)
print(m.group(1).replace(' ','') if m else '')
")
  echo "   table_id: ${CR_TABLE_ID:-（未配置，使用内置默认值）}"
  echo "   citadel_parent_id: ${CR_CITADEL_PARENT:-（未配置，使用内置默认值）}"
  echo "   domain_knowledge: ${CR_DOMAIN_KNOWLEDGE:-（未配置，使用 references/domain-knowledge.md）}"
  echo "   notify_mis: ${CR_NOTIFY_MIS:-（未配置）}"
else
  echo "ℹ️  未发现 cr-config.yaml，使用内置默认配置（适用于供商方向）"
  echo "   如需接入其他团队，请参考文档末尾的「团队接入指南」创建配置文件"
fi

# 设置最终生效值（配置文件优先，否则用内置默认值）
export TABLE_ID="${CR_TABLE_ID:-2751197605}"
export CITADEL_PARENT_ID="${CR_CITADEL_PARENT:-2752508777}"
export DOMAIN_KNOWLEDGE_PATH="$SKILL_ROOT/${CR_DOMAIN_KNOWLEDGE:-references/domain-knowledge.md}"
export NOTIFY_MIS_LIST="${CR_NOTIFY_MIS:-}"

# ── 0B. 工具依赖检查 ──────────────────────────────────────────────────
# 1. code-cli（可选依赖：PR 模式需要 pr-info/pr-diff/comment-add；本地模式用 git diff，不需要）
CODE_CLI_PATH=$(find ~/.claude/skills /root/.openclaw/skills ~/.openclaw/workspace/.claude/skills \
  -name code_cli.py 2>/dev/null | head -1)
if [ -z "$CODE_CLI_PATH" ]; then
  echo "ℹ️  [code-cli] 未安装（可选，本地模式用 git diff 不需要）"
  echo "   如需 PR 模式功能（pr-info/pr-diff/comment-add）：mtskills i code-cli"
  export CODE_CLI=""
else
  export CODE_CLI="python3 $CODE_CLI_PATH"
  if ! $CODE_CLI user-info > /dev/null 2>&1; then
    echo "⚠️  [code-cli] Cookie 失效（本地模式可忽略；PR 模式需浏览器打开 dev.sankuai.com localhost:9222）"
    export CODE_CLI=""
  else
    echo "✅ [code-cli] 可用"
  fi
fi

# 2. code-repo-search：无依赖（Layer 2 = GitNexus 优先 + grep fallback，均为本地反查）

# 3. citadel（Step 6 学城文档）
if ! command -v oa-skills > /dev/null 2>&1; then
  echo "⚠️  [citadel] oa-skills 未找到 → Step 6 学城文档将失败，建议安装："
  echo "   mtskills i citadel"
else
  if oa-skills citadel --help > /dev/null 2>&1; then
    echo "✅ [citadel] 可用"
  else
    echo "⚠️  [citadel] oa-skills 存在但 citadel 子命令不可用，Step 6 可能失败"
  fi
fi

# 4. citadel-database（可选，本地模式不强制）
if ! oa-skills citadel-database --help > /dev/null 2>&1; then
  echo "ℹ️  [citadel-database] 未安装（可选，本地模式不强制）"
else
  echo "✅ [citadel-database] 可用"
fi

# 5. ee-ones（可选，Step 1 ONES 上下文）
if command -v ones > /dev/null 2>&1; then
  echo "✅ [ee-ones] 可用"
else
  echo "ℹ️  [ee-ones] 未安装（可选）→ 无 ONES ID 时不影响流程"
fi

# 6. GitNexus CLI（可选，Layer 2 全仓库反查增强）
# 仅检测是否安装，不执行建图（建图在 SKILL.md Step 0B 同步执行）
GITNEXUS_INSTALLED=false
if command -v gitnexus &>/dev/null; then
  echo "✅ [gitnexus] CLI 已安装：$(gitnexus --version 2>/dev/null || echo 'unknown')"
  GITNEXUS_INSTALLED=true
else
  # 尝试通过 nvm 加载
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    source "$NVM_DIR/nvm.sh" 2>/dev/null
    nvm use 22 2>/dev/null
  fi
  if command -v gitnexus &>/dev/null; then
    echo "✅ [gitnexus] CLI 已安装（via nvm）：$(gitnexus --version 2>/dev/null || echo 'unknown')"
    GITNEXUS_INSTALLED=true
  else
    echo "⚠️  [gitnexus] CLI 未安装 → Layer 2 反查使用 grep fallback"
    echo "   安装：nvm install 22 && npm install -g gitnexus@1.5.3"
  fi
fi
export GITNEXUS_INSTALLED

# 7. mt-code-standards-setup（可选，Step 3A3 平台L2团队规则）
# 弱依赖：未安装仅提醒，L2 能力自动降级，仓库内规则不受影响
# 探测逻辑单一真源：fetch_l2_rules.sh --probe-only
_MTSS_RUNNER=$(bash "$_SCRIPT_DIR/fetch_l2_rules.sh" --probe-only 2>/tmp/cr_l2_probe.log)
_MTSS_RC=$?
if [ $_MTSS_RC -eq 0 ] && [ -n "$_MTSS_RUNNER" ]; then
  echo "✅ [mt-code-standards-setup] 可用（平台L2规则）"
  grep -q "无认证环境信号" /tmp/cr_l2_probe.log 2>/dev/null && \
    echo "⚠️  Runner 已装但无认证环境信号，运行时 L2 将跳过（在 CatPaw 内运行即可自动认证）"
else
  echo "ℹ️  [mt-code-standards-setup] 未安装（可选）→ 平台L2规则降级，仓库内规则不受影响"
  echo "   如需团队L2规范自动拉取：mtskills i mt-code-standards-setup"
fi

echo ""
if [ "${GITNEXUS_INSTALLED:-false}" = "false" ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "⚠️  GitNexus CLI 未安装 → Layer 2 反查将使用 grep fallback"
  echo "   grep 只能搜到直接引用（d=1），容易漏掉间接调用链上的 P0/P1 级风险"
  echo "   安装 GitNexus 后可解锁 symbol 级调用链分析（d=1~3）"
  echo "   安装命令：nvm install 22 && npm install -g gitnexus@1.5.3"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

echo "✅ 环境自检完成，开始执行 CR 流程"

# ── 写入缓存文件 ─────────────────────────────────────────────────────
# 将关键环境变量写入缓存，避免 60 分钟内重复检查
cat > "$CACHE_FILE" << CACHE_EOF
export TABLE_ID="${TABLE_ID}"
export CITADEL_PARENT_ID="${CITADEL_PARENT_ID}"
export DOMAIN_KNOWLEDGE_PATH="${DOMAIN_KNOWLEDGE_PATH}"
export NOTIFY_MIS_LIST="${NOTIFY_MIS_LIST:-}"
export CODE_CLI="${CODE_CLI}"
export GITNEXUS_INSTALLED="${GITNEXUS_INSTALLED:-false}"
CACHE_EOF

echo "✅ 环境缓存已写入：$CACHE_FILE（${CACHE_TTL}min 有效）"
export CR_ENV_CACHE_FILE="$CACHE_FILE"
