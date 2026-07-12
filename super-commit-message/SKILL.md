---
name: super-commit-message
description: 自动分析 Git 暂存区变更，生成 Conventional Commits subject +「变更文件」「变更内容」结构的中文提交信息；**默认在同轮对话中执行 git commit**；仅当用户明确声明只要文案、不要提交时才只展示 message。仅基于暂存区变更，不主动 push。Use when user wants commit message, commit staged changes, /super-commit-message, or explicitly "只要文案"、"不要提交"。
---

# Git Commit Message 生成器

自动分析 Git 暂存区（staged）的变更内容，生成 **Conventional Commits subject +「变更文件」「变更内容」** 结构的中文提交信息。**默认行为**：生成并展示 message 后，**在同轮对话中执行 `git commit`**（与显式说「帮我提交」「commit 一下」等价，无需用户重复确认）。**例外**：仅当用户**明确声明只要文案、不要写入仓库**时，才**只展示 message，不执行** `git commit`（见下文「使用方式」中的「只要文案」触发语）。

## ⚠️ 安全原则（必须遵守）

1. **仅提交暂存区变更**：只基于 `git diff --cached` 的结果生成 commit，绝不提交未暂存（unstaged）的变更。
2. **不主动 push**：执行 `git commit` 后流程即结束，绝不执行 `git push`。用户需自行决定何时推送。
3. **不修改 git config**：不更改任何 git 配置。
4. **不跳过 hooks**：不使用 `--no-verify`、`--no-gpg-sign` 等跳过钩子的参数。

## 使用方式

- **默认（提交）**：用户触发本 skill 且**未**附带「只要文案」类声明时（例如仅 `/super-commit-message`、或「生成 commit」「写个 commit message」但未说不要提交）→ 走 Step 1～5：展示后在同轮对话中执行 `git commit`，**不必再问「是否提交」**。
- **显式要提交**：说「帮我提交」「commit 一下」等 → 与默认相同，展示后执行 `git commit`。
- **只要文案（不提交）**：用户**明确说明**不要执行提交、只要文案时，才执行 Step 1～4，**跳过 Step 5**。典型表述包括但不限于：「只要文案」「只给 message」「不要提交」「别 commit」「仅展示」「不要执行 git commit」「写完 message 就好」等；**模糊表述**（如单独说「生成 commit」）**不**视为只要文案，仍按默认提交。

## 执行流程

### Step 1: 检查暂存区状态

```bash
git diff --cached --stat
```

- 若暂存区为空，提示用户「暂存区无变更，请先 `git add` 需要提交的文件」，流程终止。
- 若暂存区有变更，记录变更文件列表和统计信息，继续下一步。

### Step 2: 获取变更详情

在 Step 1 已看过 `--stat` 的前提下，获取用于分析的 diff：

```bash
git diff --cached
```

**diff 过大时**（例如变更文件很多、或合计行数明显超出上下文承载）：不要强行一次性读完整个暂存区 diff。可改为：

- 优先阅读 `--stat` 与关键路径；对核心文件使用 `git diff --cached -- <path>` 分段获取；或
- 对明显机械改动的文件（如整文件格式化）在 message 中概括说明，避免逐行复述。

若暂存区内**明显是两组互不相关的大改动**，应在展示时提示用户：更适合拆成两次 `git add` + 两次提交；若用户坚持一次提交，再合并为一个 message，并在「变更内容」中分块说明。

### Step 3: 分析变更并生成 Commit Message

根据 diff 内容，分析变更的性质和范围，生成 **Conventional Commits subject +「变更文件」「变更内容」** 结构的中文提交信息。

#### Commit Message 格式

第一行仍为 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 的 subject；其后固定两个中文区块：**变更文件**、**变更内容**。

```
<type>(<scope>): <中文描述>

变更文件：
- <相对路径 1>
- <相对路径 2>

变更内容：
- <关键变更点 1>
- <关键变更点 2>
```

**破坏性变更**（按需）：可在 type 后加 `!`，例如 `feat(api)!: 收紧鉴权校验逻辑`；在「变更内容」末尾追加一条 `- BREAKING CHANGE: <说明迁移方式>`。

**关联工单**（按需）：在「变更内容」末尾追加 `- Closes #123` 或 `- Refs #456` 等。

#### type 类型定义

| type | 说明 | 适用场景 |
|------|------|----------|
| `feat` | 新功能 | 新增功能、页面、组件、接口等 |
| `fix` | 修复缺陷 | 修复 bug、异常、错误逻辑等 |
| `docs` | 文档变更 | 仅文档、注释、README 变更 |
| `style` | 代码风格 | 格式化、空格、分号等（不影响逻辑）；整仓 Prettier/Biome 等工具性格式化也可用本 type，subject 可概括如「统一代码格式」 |
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
- 或直接使用模块名（短、可读即可）

**命名建议**：scope 使用小写；单词用短词，多词可用 kebab-case（如 `file-export`），与仓库目录或包名习惯保持一致。

若无法明确推断 scope，可省略 `(<scope>)`。

#### 生成规则

1. **type 选择**：根据 diff 内容判断变更的主要性质，选择最匹配的 type。
2. **描述用中文**：subject 与「变更内容」均使用中文；`BREAKING CHANGE`、`Closes` 等关键字按 Conventional Commits 习惯保留英文。
3. **subject 简洁**：控制在 50 字以内，以动词开头（如「新增」「修复」「优化」「重构」等）。
4. **变更文件**：列出暂存区中**全部**变更文件的相对路径（与 `git diff --cached --stat` 一致），每行一条 `- path`；路径按目录或字母排序均可，保持可读。
5. **变更内容**：用列表概括 diff 中的**实质改动**（做了什么、为何改），而非逐行复述 diff；简单变更 1～2 条，复杂变更 3～6 条；若含破坏性变更或工单关联，放在本区块末尾。
6. **单次提交一个 type**：若暂存区包含多种性质的变更，选择最主要的 type，并在「变更内容」中说明其他变更；能拆分时优先建议用户拆分暂存区而非硬揉一条 message。
7. **空区块**：暂存区仅 1 个文件时仍保留「变更文件」列表；「变更内容」至少 1 条，不可省略整个区块。

#### 示例

**简单变更：**
```
feat(components): 新增可访问性友好的 Tabs 组件

变更文件：
- src/components/Tabs.tsx

变更内容：
- 新增支持键盘导航与 ARIA 属性的 Tabs 组件。
```

**复杂变更：**
```
feat(file-export): 支持将表格数据导出为 CSV

变更文件：
- src/components/DataTable.tsx
- src/utils/csv.ts
- src/utils/csv.test.ts

变更内容：
- 增加「导出」按钮与导出进度提示。
- 封装 CSV 转义与 UTF-8 BOM，兼容 Excel 打开。
- 大数据量时分块写入，减轻主线程压力。
- 补充导出工具函数的单元测试。
```

**文档类（hook 自动提交场景）：**
```
docs(hooks): 记录 Codex 对话日志

变更文件：
- docs/progress/targeted-room-upgrade-turn-log-events.jsonl
- docs/progress/targeted-room-upgrade-turn-log.jsonl
- docs/progress/targeted-room-upgrade-turn-log.md
- docs/progress/targeted-room-upgrade-turn-log-errors.jsonl

变更内容：
- 自动记录 Codex turn `019e4fcd-244e-76c0-b4dd-65ff94f6c58e` 的开始时间、结束时间、耗时和回复预览。
- 由项目级 Codex Stop hook 自动提交，仅包含对话时间日志文件。
```

**修复类：**
```
fix(api): 修复列表分页在快速切换页码时响应乱序

变更文件：
- src/api/list.ts

变更内容：
- 为分页请求增加序号校验，丢弃过期响应，避免快速切页时数据错乱。
```

### Step 4: 展示

将生成的 commit message 展示给用户，格式如下（**用户已声明只要文案**时到此结束，不进入 Step 5）：

```
📋 变更文件（N 个文件）：
  - src/components/DataTable.tsx
  - src/utils/csv.ts
  ...

📝 生成的 Commit Message：
────────────────────────────
feat(file-export): 支持将表格数据导出为 CSV

变更文件：
- src/components/DataTable.tsx
- src/utils/csv.ts
- src/utils/csv.test.ts

变更内容：
- 增加「导出」按钮与导出进度提示。
- 封装 CSV 转义与 UTF-8 BOM，兼容 Excel 打开。
- 大数据量时分块写入，减轻主线程压力。
- 补充导出工具函数的单元测试。
────────────────────────────
```

若用户本轮**未**声明只要文案（见「使用方式」），展示后**直接进入 Step 5**，不必再问「是否提交」。

### Step 5: 执行提交

**前提**：用户在本轮对话中**未**声明只要文案、不要提交（见「使用方式」）；已声明只要文案时不要执行本节。

message 含多段（subject + 变更文件 + 变更内容）时，**不要**把整个 message 塞进单个 `-m "..."`（引号与换行易出错）。任选其一：

**方式 A（推荐）**：`git` 的多个 `-m` 会按段落拼接，段落之间自动空一行。按顺序传四段——subject、变更文件区块、空行占位（若 git 已自动空行可省略）、变更内容区块：

```bash
git commit \
  -m "feat(file-export): 支持将表格数据导出为 CSV" \
  -m "变更文件：
- src/components/DataTable.tsx
- src/utils/csv.ts
- src/utils/csv.test.ts" \
  -m "变更内容：
- 增加「导出」按钮与导出进度提示。
- 封装 CSV 转义与 UTF-8 BOM，兼容 Excel 打开。
- 大数据量时分块写入，减轻主线程压力。
- 补充导出工具函数的单元测试。"
```

**方式 B（更稳妥）**：将**最终完整** message（含空行）写入临时文件（如 `mktemp` 或 `/tmp` 下文件，**勿**将该文件加入暂存区），再执行：

```bash
git commit -F /path/to/commit-msg.txt
```

完成后删除临时文件。多段、含反引号或特殊字符时优先用方式 B。

提交完成后展示提交结果（`git log -1 --oneline`）。

## 注意事项

1. **默认执行提交**：用户未在本轮明确声明只要文案、不要提交时，展示 message 后应执行 `git commit`（见「使用方式」）。
2. **暂存区为空时终止**：不主动 `git add`，由用户自行决定要提交的文件。
3. **不处理未跟踪文件**：`git add` 仅由用户手动执行，Agent 不添加未跟踪文件。
4. **不 amend**：不使用 `--amend` 修改历史提交。
5. **不 force push**：任何情况下都不执行 force push。
6. **中文描述**：commit 的 subject 与「变更内容」以中文为主，便于团队阅读；`BREAKING CHANGE`、`Closes` 等关键字按规范使用英文（见生成规则第 2 条）。
7. **固定结构**：每条 message 均含 subject、「变更文件」「变更内容」三段，勿回退为纯 bullet body 的旧格式。
8. **type 准确**：优先选择最能反映变更本质的 type，避免滥用 `chore`。
9. **敏感信息**：若 diff 中出现疑似密钥、token、Cookie 等，不要原样复述进聊天或 message；应提示用户先移出暂存区或脱敏后再提交。