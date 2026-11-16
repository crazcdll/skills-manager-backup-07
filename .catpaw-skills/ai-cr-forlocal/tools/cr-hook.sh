#!/usr/bin/env bash
# cr-hook.sh — AI Local CR Git Hook 入口（pre-push）
#
# 安装方式（在仓库根目录执行）：
#   bash ~/.openclaw/skills/ai-cr-forlocal/tools/cr-hook.sh --install
#
# 卸载方式：
#   bash ~/.openclaw/skills/ai-cr-forlocal/tools/cr-hook.sh --uninstall
#
# 阻断策略：
#   P0 → exit 0（警告提示，放行 push）
#   P1 → exit 0（警告提示，放行 push）
#   P2/P3 → 静默，不输出到终端

set -e

HOOK_CONTENT='#!/usr/bin/env bash
# AI Local CR — pre-push hook (由 cr-hook.sh 安装)
# 阻断策略：全部 exit 0（提醒为主，不阻断 push）

CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "HEAD")
REPO_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
BASE_BRANCH=$(git remote show origin 2>/dev/null | grep "HEAD branch" | awk "{print \$NF}" || echo "master")

# 跳过 merge/rebase 分支
if [[ "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "develop" ]]; then
  echo "⏭  [AI CR Hook] 跳过主干分支 push，不触发 CR"
  exit 0
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       AI Local Code Review           ║"
echo "║       Git Hook 模式 (pre-push)       ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "📁 仓库：$REPO_PATH"
echo "🌿 分支：$CURRENT_BRANCH → $BASE_BRANCH"
echo "🔍 正在运行 AI CR，仅展示 P0/P1 问题..."
echo ""

# 导出环境变量
export LOCAL_REPO_PATH="$REPO_PATH"
export LOCAL_BRANCH="$CURRENT_BRANCH"
export BASE_BRANCH="$BASE_BRANCH"
export CR_MODE="local"
export CR_CALLER="hook"   # ← 关键标识：Hook 模式，引擎只输出 P0/P1，P0 exit 1

# 写入触发信号文件（供 AI 引擎轮询读取）
TRIGGER_FILE="/tmp/ai_cr_hook_trigger_$(echo $REPO_PATH | md5sum | cut -c1-8).json"
cat > "$TRIGGER_FILE" <<EOF
{
  "repo": "$REPO_PATH",
  "branch": "$CURRENT_BRANCH",
  "base": "$BASE_BRANCH",
  "caller": "hook",
  "triggered_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📡 已写入触发信号：$TRIGGER_FILE"
echo "⏳ 请在 CatPaw 中触发 ai-cr-forlocal（CR_CALLER=hook）"
echo ""
echo "   等待 AI CR 结果..."

# 轮询结果文件（最多等 120s）
RESULT_FILE="/tmp/ai_cr_result_$(basename $REPO_PATH)_$(echo $CURRENT_BRANCH | tr "/" "-").json"
WAIT=0
MAX_WAIT=120
while [ ! -f "$RESULT_FILE" ] && [ $WAIT -lt $MAX_WAIT ]; do
  sleep 2
  WAIT=$((WAIT + 2))
  echo -n "."
done
echo ""

if [ ! -f "$RESULT_FILE" ]; then
  echo "⚠️  [AI CR Hook] 等待超时（${MAX_WAIT}s），放行 push（CR 未完成）"
  exit 0
fi

# 解析结果
CR_RESULT=$(python3 -c "import json,sys; d=json.load(open(\"$RESULT_FILE\")); print(d.get(\"cr_result\",\"UNKNOWN\"))" 2>/dev/null || echo "UNKNOWN")
P0=$(python3 -c "import json,sys; d=json.load(open(\"$RESULT_FILE\")); print(d.get(\"p0_count\",0))" 2>/dev/null || echo "0")
P1=$(python3 -c "import json,sys; d=json.load(open(\"$RESULT_FILE\")); print(d.get(\"p1_count\",0))" 2>/dev/null || echo "0")
KM_URL=$(python3 -c "import json,sys; d=json.load(open(\"$RESULT_FILE\")); print(d.get(\"km_doc_url\",\"\") or \"\")" 2>/dev/null || echo "")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 AI CR 结果：$CR_RESULT"
echo "   P0=$P0  P1=$P1"
[ -n "$KM_URL" ] && echo "   学城文档：$KM_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# P0 → 警告提示，放行
if [ "$P0" -gt 0 ]; then
  echo ""
  echo "⚠️  [AI CR Hook] 发现 P0 问题 $P0 个（提醒，push 放行）"
  echo "   强烈建议修复后再合并 PR！详情见：$KM_URL"
  echo ""
  python3 -c "
import json
d = json.load(open(\"$RESULT_FILE\"))
issues = [i for i in d.get(\"issues\",[]) if i.get(\"level\")==\"P0\"]
for i, issue in enumerate(issues, 1):
    print(f\"  [{i}] {issue.get('file','')}:{issue.get('line','')} — {issue.get('title','')}\")
    print(f\"      建议：{issue.get('suggestion','')}\")
    print()
" 2>/dev/null
fi

# P1 → 警告提示，放行
if [ "$P1" -gt 0 ]; then
  echo ""
  echo "⚠️  [AI CR Hook] 发现 P1 问题 $P1 个（提醒，push 放行）"
  echo "   请在 PR 阶段关注修复。详情见：$KM_URL"
  python3 -c "
import json
d = json.load(open(\"$RESULT_FILE\"))
issues = [i for i in d.get(\"issues\",[]) if i.get(\"level\")==\"P1\"]
for i, issue in enumerate(issues, 1):
    print(f\"  [{i}] {issue.get('file','')}:{issue.get('line','')} — {issue.get('title','')}\")
    print()
" 2>/dev/null
fi

echo "✅ [AI CR Hook] push 放行"
exit 0
'

# ── 安装 / 卸载 命令 ──────────────────────────────

ACTION="${1:-}"

if [ "$ACTION" = "--install" ]; then
  REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
  if [ -z "$REPO_ROOT" ]; then
    echo "❌ 当前目录不是 git 仓库"
    exit 1
  fi

  HOOK_FILE="$REPO_ROOT/.git/hooks/pre-push"

  if [ -f "$HOOK_FILE" ]; then
    echo "⚠️  已存在 pre-push hook，备份到 $HOOK_FILE.bak"
    cp "$HOOK_FILE" "$HOOK_FILE.bak"
  fi

  echo "$HOOK_CONTENT" > "$HOOK_FILE"
  chmod +x "$HOOK_FILE"

  echo "✅ AI CR pre-push hook 已安装到：$HOOK_FILE"
  echo "   P0/P1 → 警告提示，push 放行（提醒为主）"
  echo ""
  echo "卸载：bash $(realpath "$0") --uninstall"

elif [ "$ACTION" = "--uninstall" ]; then
  REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
  HOOK_FILE="$REPO_ROOT/.git/hooks/pre-push"

  if [ -f "$HOOK_FILE.bak" ]; then
    mv "$HOOK_FILE.bak" "$HOOK_FILE"
    echo "✅ 已恢复原 pre-push hook"
  elif [ -f "$HOOK_FILE" ]; then
    rm "$HOOK_FILE"
    echo "✅ AI CR pre-push hook 已卸载"
  else
    echo "（未找到 hook 文件）"
  fi

else
  echo "用法："
  echo "  安装：bash $(basename "$0") --install   （在目标仓库根目录执行）"
  echo "  卸载：bash $(basename "$0") --uninstall"
fi
