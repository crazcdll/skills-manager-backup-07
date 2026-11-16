# 第零步：环境依赖预检查

在执行评估流程前，检测所需 Skill 工具和 Python 依赖是否就绪，避免在评估中途因依赖缺失而中断。

---

## 依赖清单

| 依赖 | 安装命令 | 缺失影响 | 强制级别 |
|------|---------|---------|---------|
| **PyYAML** | `pip3 install 'PyYAML>=6,<7'` | 无法解析 pnpm mono-repo 成员清单 | mono-repo 检测必须 |
| **code-repo-search** | `mtskills i code-repo-search` | 远程仓库模式不可用 | 远程模式必须 |
| **citadel** | `npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com` | 报告无法保存到学城 | **强制（缺失时停止，必须安装后继续）** |

---

## 检测脚本

### Skill 目录搜索路径（按优先级依次检查）

```bash
SKILL_DIRS=(
  "$HOME/.claude/skills"
  "$HOME/.openclaw/workspace/.claude/skills"
  "/root/.openclaw/workspace/.claude/skills"
  "$HOME/.catpaw/skills/skills-market"
)
```

### 检测函数

```bash
check_skill_installed() {
  local skill_name="$1"
  for dir in "${SKILL_DIRS[@]}"; do
    [ -d "$dir/$skill_name" ] && return 0
  done
  return 1
}
```

### 执行检测

```bash
# 定位 install_deps.py（与本文件同级的 ../scripts/ 目录）
INSTALL_DEPS_PY="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." 2>/dev/null && pwd)/scripts/install_deps.py"

# 1. 检测 PyYAML（pnpm workspace 结构化解析）
python3 "$INSTALL_DEPS_PY" pyyaml

# 2. 检测 code-repo-search
if check_skill_installed "code-repo-search"; then
  echo "✅ code-repo-search 已安装"
  REPO_SEARCH_AVAILABLE=true
else
  python3 "$INSTALL_DEPS_PY" code-repo-search
  # 安装后重新检测
  if check_skill_installed "code-repo-search"; then
    REPO_SEARCH_AVAILABLE=true
  else
    REPO_SEARCH_AVAILABLE=false
  fi
fi

# 3. 检测 citadel（学城文档操作）
if check_skill_installed "citadel"; then
  echo "✅ citadel 已安装"
  CITADEL_AVAILABLE=true
else
  python3 "$INSTALL_DEPS_PY" citadel
  # 安装后重新检测
  if check_skill_installed "citadel"; then
    CITADEL_AVAILABLE=true
  else
    CITADEL_AVAILABLE=false
  fi
fi

```

---

## 工具路径定位（code-repo-search）

**优先使用已知稳定路径**（省去 find 耗时）：

```
REPO_SEARCH_PATH=/root/.openclaw/workspace/.claude/skills/code-repo-search/repo_search.py
```

若稳定路径不存在，Fallback 到 find：

```bash
if [ ! -f "$REPO_SEARCH_PATH" ]; then
  REPO_SEARCH_PATH=$(find "$HOME/.claude/skills" \
    "$HOME/.openclaw/workspace/.claude/skills" \
    "/root/.openclaw/workspace/.claude/skills" \
    "$HOME/.catpaw/skills/skills-market" \
    -name repo_search.py 2>/dev/null | head -1)
fi

if [ -z "$REPO_SEARCH_PATH" ]; then
  echo "❌ repo_search.py 未找到，请先运行: mtskills i code-repo-search"
  REPO_SEARCH_AVAILABLE=false
else
  REPO_SEARCH="python3 $REPO_SEARCH_PATH"
  echo "REPO_SEARCH=$REPO_SEARCH"  # 打印确认，路径为空则停止
fi
```

---

## 检查结果处理规则

| 场景 | 处理方式 |
|------|---------|
| **pnpm-workspace.yaml 存在 + PyYAML 缺失** | 输出安装命令，**停止**，不得用字符串匹配猜测成员 |
| **远程模式 + code-repo-search 缺失** | 输出安装命令，**停止**，不继续 |
| **citadel 缺失** | 输出安装命令，**停止**，必须安装后再继续（报告必须保存到学城） |
| **任意依赖缺失** | 必须明确告知用户，**禁止静默降级** |

---

## 模式判断（预检查完成后）

```
若用户提供了 https://dev.sankuai.com/code/repo-detail/* 链接：
  → 检查 REPO_SEARCH_AVAILABLE=true，否则停止
  → 读取 step7-remote-mode.md 执行远程模式，完成后跳回第七步
否则：
  → 继续本地模式（当前工作目录）
```
