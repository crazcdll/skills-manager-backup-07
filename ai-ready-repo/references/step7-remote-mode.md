# 远程仓库模式

支持对美团内部代码平台（dev.sankuai.com）的远程仓库进行 AI-Ready 评估，无需在本地克隆仓库。

---

## 触发条件

满足以下任意条件时激活远程模式：
- 用户提供了 `https://dev.sankuai.com/code/repo-detail/*` 格式的链接
- 用户明确说"评估远程仓库 AI-Ready"、"扫描远程仓库"

---

## 前置条件

**code-repo-search 必须已安装**（第零步检查 `REPO_SEARCH_AVAILABLE=true`）。

若未安装，立即停止并提示：
```
❌ 远程模式需要 code-repo-search，请先运行：mtskills i code-repo-search
```

---

## 执行流程

### Step R1：解析仓库信息

从用户提供的 URL 中提取仓库标识：

```
URL 示例：https://dev.sankuai.com/code/repo-detail/tuangou/deal-shelf/
解析结果：org=tuangou，repo=deal-shelf
```

若 URL 格式无法解析，询问用户：
- 仓库名称（`org/repo` 格式，如 `tuangou/deal-shelf`）
- 分支名称（未提供则询问，缺省使用 `master`）

### Step R2：使用 code-repo-search 拉取完整仓库

```bash
TIMESTAMP=$(date +%Y%m%d%H%M%S)
TMP_DIR="/tmp/ai-ready-${REPO_NAME//\//-}-${TIMESTAMP}"

$REPO_SEARCH clone \
  --repo "<org>/<repo>" \
  --branch "<branch>" \
  --output "$TMP_DIR"

echo "仓库已拉取至：$TMP_DIR"
```

拉取完成后，将工作目录切换到 `$TMP_DIR`，按**本地模式**完整执行**第一步至第六步**。

> 远程模式下，所有 bash 检查命令均在 `$TMP_DIR` 目录内执行，与本地模式完全一致。

**第六步归档注意**：远程模式下临时目录名带时间戳（如 `ai-ready-tuangou-deal-shelf-20260731...`），
**不可**用目录名作为报告标题中的仓库名。须使用 Step R1 解析出的仓库名本体（`<repo>`，如 `deal-shelf`），
并按 [step6-report-template.md](step6-report-template.md) 的规范生成标题与归档到当月目录：

```bash
PARENT_ID=$(python3 "$SKILL_ROOT/scripts/km_report_dir.py" resolve --quiet)
TITLE=$(python3 "$SKILL_ROOT/scripts/km_report_dir.py" title \
          --repo-name "<org>/<repo>" --parent-id "$PARENT_ID")
```

### Step R3：评估完成后清理临时目录

第六步（生成评估报告）完成后，删除临时目录：

```bash
rm -rf "$TMP_DIR"
echo "临时目录已清理：$TMP_DIR"
```

清理完成后，继续执行**第七步**（上报评分数据）。

---

## 降级规则

| 错误类型 | 处理方式 |
|---------|---------|
| code-repo-search 不可用 | **停止**，提示 `mtskills i code-repo-search` |
| 网络超时 | 提示用户检查网络后重试，不继续 |
| 仓库无权限（403/404） | 提示用户确认仓库访问权限，不继续 |
| 分支不存在 | 询问用户重新输入分支名 |

**禁止静默忽略错误**：任何拉取失败必须告知用户，不可跳过。
