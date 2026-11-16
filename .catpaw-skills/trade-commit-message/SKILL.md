---
name: trade-commit-message
description: 自动分析 Git 暂存区变更，生成 Conventional Commits subject +「变更文件」「变更内容」结构的中文提交信息并执行 git commit。仅基于暂存区变更，不主动 push。Use when user wants to generate commit message, commit staged changes, or asks "帮我提交"、"生成 commit message"、"写个 commit"。

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V3"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "58692"
  skillhub.high_sensitive: "false"
---

# Git Commit Message 生成器

自动分析 Git 暂存区（staged）的变更内容，生成 **Conventional Commits subject +「变更文件」「变更内容」** 结构的中文提交信息，并执行 `git commit`。

## ⚠️ 安全原则（必须遵守）

1. **仅提交暂存区变更**：只基于 `git diff --cached` 的结果生成 commit，绝不提交未暂存（unstaged）的变更。
2. **不主动 push**：执行 `git commit` 后流程即结束，绝不执行 `git push`。用户需自行决定何时推送。
3. **不修改 git config**：不更改任何 git 配置。
4. **不跳过 hooks**：不使用 `--no-verify`、`--no-gpg-sign` 等跳过钩子的参数。

## 使用方式

用户只需说「帮我提交」「生成 commit」「写个 commit message」等，Agent 即自动执行以下流程。

## 执行流程

### Step 1: 检查暂存区状态

```bash
git diff --cached --stat
```

- 若暂存区为空，提示用户「暂存区无变更，请先 `git add` 需要提交的文件」，流程终止。
- 若暂存区有变更，记录变更文件列表和统计信息，继续下一步。

### Step 2: 获取变更详情

```bash
git diff --cached
```

**diff 过大时**（变更文件很多、或合计行数明显超出上下文承载）：不要强行一次性读完整个暂存区 diff。可改为：

- 优先阅读 `--stat` 与关键路径；对核心文件使用 `git diff --cached -- <path>` 分段获取；或
- 对明显机械改动的文件（如整文件格式化）在 message 中概括说明，避免逐行复述。

若暂存区内**明显是两组互不相关的大改动**，应在提交前提示用户：更适合拆成两次 `git add` + 两次提交；若用户坚持一次提交，再合并为一个 message，并在「变更内容」中分块说明。

### Step 3: 分析变更并生成 Commit Message

根据 diff 内容，分析变更的性质和范围，生成 **Conventional Commits subject +「变更文件」「变更内容」** 结构的中文提交信息。

#### Commit Message 格式

第一行仍为 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 的 subject；其后固定两个中文区块：**变更文件**、**变更内容**（区块标题后空一行，条目每行一条，行首以 `- ` 开头）。

```
<type>(<scope>): <中文描述>

变更文件：

- <相对路径 1>
- <相对路径 2>

变更内容：

- <关键变更点 1>
- <关键变更点 2>
```

**破坏性变更**（按需）：可在 type 后加 `!`，例如 `feat(api)!: 收紧鉴权校验逻辑`；在「变更内容」末尾追加一行 `- BREAKING CHANGE: <说明迁移方式>`。

**关联工单**（按需）：在「变更内容」末尾追加 `- Closes #123` 或 `- Refs #456` 等。

#### type 类型定义

| type | 说明 | 适用场景 |
|------|------|----------|
| `feat` | 新功能 | 新增功能、页面、组件、接口等 |
| `fix` | 修复缺陷 | 修复 bug、异常、错误逻辑等 |
| `docs` | 文档变更 | 仅文档、注释、README 变更 |
| `style` | 代码风格 | 格式化、空格、分号等（不影响逻辑） |
| `refactor` | 重构 | 代码重构，既非新功能也非修复 |
| `perf` | 性能优化 | 提升性能的代码变更 |
| `test` | 测试 | 添加或修改测试代码 |
| `build` | 构建 | 构建系统或外部依赖变更 |
| `ci` | CI/CD | CI 配置文件和脚本变更 |
| `chore` | 杂项 | 其他不影响源码的变更（如依赖升级、配置调整） |
| `revert` | 回滚 | 回滚之前的提交 |

#### scope 范围

根据变更文件路径推断 scope，常见示例：

- `components`：组件变更
- `pages`：页面变更
- `utils`：工具函数
- `api`：接口相关
- `styles`：样式变更
- `config`：配置变更
- `deps`：依赖变更
- 或直接使用业务模块名

若无法明确推断 scope，可省略 `(<scope>)`（例如 `docs: 初始化需求交付进度文档`）。

#### 生成规则

1. **type 选择**：根据 diff 内容判断变更的主要性质，选择最匹配的 type。
2. **描述用中文**：subject 与「变更内容」均使用中文；`BREAKING CHANGE`、`Closes` 等关键字按 Conventional Commits 习惯保留英文。
3. **subject 简洁**：控制在 50 字以内，以动词开头（如「新增」「修复」「优化」「重构」等）。
4. **变更文件**：列出暂存区中**全部**变更文件的相对路径（与 `git diff --cached --stat` 一致），每行一条 `- <路径>`；按目录或字母排序均可，保持可读。
5. **变更内容**：用自然语言概括 diff 中的**实质改动**（做了什么、改了什么），每行一条 `- <说明>`，而非逐行复述 diff；可按文件分条（如 `- AGENTS.md 补充…`），也可按功能合并；简单变更 1～2 条，复杂变更 3～6 条。
6. **单次提交一个 type**：若暂存区包含多种性质的变更，选择最主要的 type，并在「变更内容」中说明其他变更；能拆分时优先建议用户拆分暂存区。
7. **区块不可省略**：即使仅 1 个文件，仍须保留「变更文件」「变更内容」两个区块；「变更内容」至少 1 条。

#### 示例

**文档类（与用户约定格式一致）：**

```
docs: 初始化需求交付进度文档并补充协作规范

变更文件：

- AGENTS.md
- docs/progress.md
- voice-prompt/else.md

变更内容：

- 新增 docs/progress.md，涵盖开发、Bug 修复、联调、测试、CR、上线六个维度的进度跟踪
- AGENTS.md 补充「Node 版本规范」章节，明确 v16/v24 的使用场景与切换命令
- voice-prompt/else.md 补录 ELSE-010、ELSE-011 两条语音指令台账
```

**功能类：**

```
feat(order): 新增订单详情页退款入口

变更文件：

- src/pages/OrderDetail.tsx
- src/components/RefundModal.tsx
- src/api/refund.ts

变更内容：

- 在订单详情页新增「申请退款」按钮与退款原因选择弹窗
- 实现退款金额计算逻辑并对接退款提交接口
```

**修复类：**

```
fix(api): 修复订单列表分页参数丢失导致重复数据

变更文件：

- src/api/orderList.ts

变更内容：

- 请求分页时补全 page/pageSize 参数，丢弃乱序响应避免列表重复
```

### Step 4: 直接提交

生成 commit message 后直接执行提交，无需等用户确认。

message 含多段（subject + 变更文件 + 变更内容）时，**不要**把整个 message 塞进单个 `-m "..."`（引号与换行易出错）。优先使用 HEREDOC：

```bash
git commit -m "$(cat <<'EOF'
docs: 初始化需求交付进度文档并补充协作规范

变更文件：

- AGENTS.md
- docs/progress.md
- voice-prompt/else.md

变更内容：

- 新增 docs/progress.md，涵盖开发、Bug 修复、联调、测试、CR、上线六个维度的进度跟踪
- AGENTS.md 补充「Node 版本规范」章节，明确 v16/v24 的使用场景与切换命令
- voice-prompt/else.md 补录 ELSE-010、ELSE-011 两条语音指令台账
EOF
)"
```

**备选**：将完整 message 写入临时文件（勿加入暂存区），再 `git commit -F /path/to/commit-msg.txt`，提交后删除临时文件。含反引号或特殊字符时优先用此方式。

提交完成后展示结果：

```bash
git log -1 --oneline
```

## 注意事项

1. **直接提交不确认**：生成 commit message 后直接执行 `git commit`，无需等待用户确认。
2. **暂存区为空时终止**：不主动 `git add`，由用户自行决定要提交的文件。
3. **不处理未跟踪文件**：`git add` 仅由用户手动执行，Agent 不添加未跟踪文件。
4. **不 amend**：不使用 `--amend` 修改历史提交。
5. **不 force push**：任何情况下都不执行 force push。
6. **中文描述**：commit 的 subject 与「变更内容」以中文为主，便于团队阅读。
7. **固定结构**：每条 message 均含 subject、「变更文件」「变更内容」三段；两个区块内条目须以 `- ` 列表形式书写，勿省略区块或去掉行首 `-`。
8. **type 准确**：优先选择最能反映变更本质的 type，避免滥用 `chore`。
9. **敏感信息**：若 diff 中出现疑似密钥、token、Cookie 等，不要原样复述进 message；应提示用户先移出暂存区或脱敏后再提交。
