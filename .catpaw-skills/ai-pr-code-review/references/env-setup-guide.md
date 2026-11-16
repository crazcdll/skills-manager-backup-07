# 环境依赖说明

## Skill 依赖清单

| Skill | 安装命令 | 缺失影响 | 是否自动安装 |
|-------|---------|---------|------------|
| **code-cli** | `mtskills i code-cli` | ❌ 核心流程不可用 | ✅ 强制安装 |
| **code-repo-search** | `mtskills i code-repo-search` | ⚠️ Layer 2 降级 | ✅ 强制安装 |
| **citadel** | `mtskills i citadel` | ⚠️ Step 6 学城文档失败 | ✅ 强制安装 |
| **citadel-database** | `mtskills i citadel-database` | ⚠️ Step 9 多维表格失败 | ✅ 强制安装 |
| **ee-ones**（可选） | `mtskills i ee-ones` | ℹ️ 无 ONES 上下文 | ✅ 强制安装 |

## Skill 安装检测脚本

```bash
SKILL_DIRS=(
  "$HOME/.claude/skills"
  "$HOME/.openclaw/workspace/.claude/skills"
  "/root/.openclaw/workspace/.claude/skills"
)

check_skill_installed() {
  local skill_name="$1"
  for dir in "${SKILL_DIRS[@]}"; do
    [ -d "$dir/$skill_name" ] && return 0
  done
  return 1
}
```

## 工具路径定位

**⚠️ 必须实际执行以下命令赋值，禁止把 `$(...)` 当文本字面量处理：**

```bash
# 定位 code-cli（按优先级依次尝试）
CODE_CLI_PATH=$(find /root/.openclaw/workspace/.claude/skills -name code_cli.py 2>/dev/null | head -1)
if [ -z "$CODE_CLI_PATH" ]; then
  CODE_CLI_PATH=$(find ~/.claude/skills -name code_cli.py 2>/dev/null | head -1)
fi
if [ -z "$CODE_CLI_PATH" ]; then
  echo "❌ code_cli.py 未找到，请先运行: mtskills i code-cli" && exit 1
fi
CODE_CLI="python3 $CODE_CLI_PATH"
echo "CODE_CLI=$CODE_CLI"  # 必须打印确认，路径为空则停止

# 定位 code-repo-search
REPO_SEARCH_PATH=$(find /root/.openclaw/workspace/.claude/skills ~/.openclaw/skills ~/.claude/skills -path "*/code-repo-search/repo_search.py" 2>/dev/null | head -1)
REPO_SEARCH="python3 $REPO_SEARCH_PATH"
echo "REPO_SEARCH=$REPO_SEARCH"
```

**路径定位优先级（按顺序尝试）：**

```bash
# 1. 优先用 Skill 内置版本（含 SSO 无感登录，零配置）
SKILL_DIR=$(dirname "$(find ~/.openclaw/workspace/.claude/skills/ai-pr-code-review -name 'SKILL.md' 2>/dev/null | head -1)")
BUILTIN_CODE_CLI="$SKILL_DIR/scripts/code_cli.py"
if [ -f "$BUILTIN_CODE_CLI" ]; then
  CODE_CLI_PATH="$BUILTIN_CODE_CLI"
fi

# 2. fallback：已安装的外部 code-cli
if [ -z "$CODE_CLI_PATH" ]; then
  CODE_CLI_PATH=$(find /root/.openclaw/workspace/.claude/skills -name code_cli.py 2>/dev/null | head -1)
fi
if [ -z "$CODE_CLI_PATH" ]; then
  CODE_CLI_PATH=$(find ~/.claude/skills -name code_cli.py 2>/dev/null | head -1)
fi
```

> **内置版本特性**：CatClaw 沙箱下通过 MOA SSO 无感登录自动鉴权，无需配置 Cookie。
> 其他环境自动 fallback 到 Cookie 文件 / CDP 浏览器。

## GitNexus 沙箱建图（ai-pr-code-review 新增）

> **不依赖 `gitnexus serve`**，Step 0C-2 在沙箱内主动 clone + `gitnexus analyze` 后即可离线运行 `impact` / `context`。

```bash
# 1. 检查 CLI 是否就绪
which gitnexus && gitnexus --version

# 2. 异步 clone + index（Step 2 拿到 org/repo 后立即启动，不阻塞后续步骤）
REPO_DIR="/tmp/gitnexus-index/{org}/{repo}"
mkdir -p $REPO_DIR && cd $REPO_DIR
git clone --depth 1 ssh://git@git.sankuai.com/{org}/{repo}.git . 2>1 || \
git clone --depth 1 https://git.sankuai.com/{org}/{repo}.git . 2>1

# 3. 建图（通常 5\~30 秒，大仓库 1\~3 分钟）
npx gitnexus analyze 2>&1 | tail -5

# 4. 验证 index 已就绪
npx gitnexus status 2>&1
```

```bash
# 后续 3B subagent 调用示例：
cd /tmp/gitnexus-index/{org}/{repo}
npx gitnexus impact 2>&1                    # 全量影响分析
npx gitnexus context --symbol "{methodName}" 2>&1  # 符号上下文
```

> FTS 扩展（全文搜索）缺失不影响 `impact` / `context`。`gitnexus doctor` 可查具体状态。

**行内评论命令示例（`comment-add`）：**

```bash
$CODE_CLI comment-add \
  --url "$PR_URL" \
  --file "完整文件路径（与 pr-changes 返回的 path 完全一致）" \
  --line 23 \
  --line-type ADDED \
  --text "评论内容" 2>&1
```

成功返回示例：`{"ok": true, "id": 50319159, "text": "..."}`
失败则重试最多 4 次（间隔 2s），全部失败降级为全局评论并标注文件名+行号。

## 降级规则

| 状态 | AI 行为 |
|------|--------|
| `BROWSER_AUTH=false` | **优先扫码引导**：检测沙箱有无 Chromium（9222端口）→ 有则用 agent-browser 打开大象网页二维码，截图发给用户扫码重登录 → 成功后重取 Cookie 继续；无 Chromium 或超时则输出手动复制 Cookie 的提示，等用户确认"继续"才往下走；禁止静默降级 |
| `REPO_SEARCH_AVAILABLE=false` | 告知 Layer 2 降级影响，询问是否继续；禁止静默跳过 |

**浏览器未登录时受限功能：**
- Step 2：无法拉取 PR 元信息（核心功能）
- Step 3 Layer 2：无法反查仓库引用
- Step 7：无法发 PR 评论
