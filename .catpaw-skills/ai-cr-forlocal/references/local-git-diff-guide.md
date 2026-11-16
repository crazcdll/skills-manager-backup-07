# 本地 git diff 入口指南（Step 1A）

### Step 1A. 本地 git diff 获取（本地分支模式）

> **场景**：分支仅存在于本地，未推送远端，无任何 PR，通过本地文件系统直接获取变更。
> 运行环境：CatPaw IDE 沙箱，可直接访问本地文件系统。

**1A-1. 验证仓库与分支**

```bash
# 1. 验证路径是 git 仓库
cd "$LOCAL_REPO_PATH" && git rev-parse --is-inside-work-tree 2>/dev/null || {
  echo "❌ 路径不是 git 仓库：$LOCAL_REPO_PATH"; exit 1
}

# 2. 验证分支存在
git branch --list "$LOCAL_BRANCH" | grep -q "$LOCAL_BRANCH" || {
  echo "❌ 分支不存在：$LOCAL_BRANCH"; exit 1
}

# 3. 提取基本信息
REPO_NAME=$(basename "$LOCAL_REPO_PATH")
LAST_COMMIT=$(git log "$LOCAL_BRANCH" --oneline -1)
echo "✅ 仓库：$REPO_NAME | 分支：$LOCAL_BRANCH | 最新提交：$LAST_COMMIT"
```

**1A-2. 获取变更文件列表**

```bash
cd "$LOCAL_REPO_PATH"

# 获取变更文件列表（相对路径）
# 三点 diff 优先，失败则回退到两点 diff
git diff "$BASE_BRANCH...$LOCAL_BRANCH" --name-only --diff-filter=ACM > /tmp/local_cr_files.txt 2>/dev/null || {
  echo "⚠️ 三点 diff 失败（base 分支可能不存在），回退到两点 diff"
  git diff "$BASE_BRANCH" "$LOCAL_BRANCH" --name-only --diff-filter=ACM > /tmp/local_cr_files.txt 2>/dev/null || {
    echo "⚠️ 两点 diff 也失败，回退到 HEAD~1 比较"
    git diff HEAD~1 HEAD --name-only --diff-filter=ACM > /tmp/local_cr_files.txt
  }
}
TOTAL_FILES=$(wc -l < /tmp/local_cr_files.txt)
echo "变更文件数：$TOTAL_FILES"
cat /tmp/local_cr_files.txt
```

**1A-3. 获取完整 diff**

```bash
cd "$LOCAL_REPO_PATH"

# 获取带上下文的完整 diff（存文件，后续 Step 3 用）
# 三点 diff 优先，失败则回退
git diff "$BASE_BRANCH...$LOCAL_BRANCH" --unified=5 > /tmp/local_cr_diff.txt 2>/dev/null || {
  echo "⚠️ 三点 diff 失败，回退到两点 diff"
  git diff "$BASE_BRANCH" "$LOCAL_BRANCH" --unified=5 > /tmp/local_cr_diff.txt 2>/dev/null || {
    echo "⚠️ 两点 diff 也失败，回退到 HEAD~1 比较"
    git diff HEAD~1 HEAD --unified=5 > /tmp/local_cr_diff.txt
  }
}
echo "diff 大小：$(wc -l < /tmp/local_cr_diff.txt) 行"
```

**1A-4. 获取行数统计**

```bash
cd "$LOCAL_REPO_PATH"

# 解析 git diff --stat 获取增删行数
STAT=$(git diff "$BASE_BRANCH...$LOCAL_BRANCH" --stat 2>/dev/null | tail -1)
if [ -z "$STAT" ]; then
  STAT=$(git diff "$BASE_BRANCH" "$LOCAL_BRANCH" --stat 2>/dev/null | tail -1)
fi
if [ -z "$STAT" ]; then
  STAT=$(git diff HEAD~1 HEAD --stat | tail -1)
fi
# 输出格式如：12 files changed, 345 insertions(+), 67 deletions(-)
ADDITIONS=$(echo "$STAT" | grep -oP '\d+(?=\s+insertion)' || echo 0)
DELETIONS=$(echo "$STAT" | grep -oP '\d+(?=\s+deletion)' || echo 0)
echo "行数变化：+$ADDITIONS / -$DELETIONS"
```

**1A-5. 设置模式标识**

```bash
CR_MODE="local"              # 本地分支模式
OPERATOR_MIS=$(git -C "$LOCAL_REPO_PATH" config user.email 2>/dev/null | cut -d@ -f1)
if [ -z "$OPERATOR_MIS" ] || [ "$OPERATOR_MIS" = "root" ]; then
  OPERATOR_MIS=$(python3 -c "
import yaml
with open('$SKILL_ROOT/cr-config.yaml') as f:
    c = yaml.safe_load(f)
print(c.get('operator_mis', ''))
" 2>/dev/null || echo "")
fi
if [ -z "$OPERATOR_MIS" ]; then
  echo "⚠️ 无法确定 OPERATOR_MIS，请在 cr-config.yaml 中配置 operator_mis"
  OPERATOR_MIS="unknown"
fi
export OPERATOR_MIS
```

**1A-6. 分批判断**

满足任一 → 分批：文件数 > 30 / 高危层文件 > 15 / 高危触发器 > 3

进入 Step 3（Layer 1 用本地文件读取，见 3A）。

