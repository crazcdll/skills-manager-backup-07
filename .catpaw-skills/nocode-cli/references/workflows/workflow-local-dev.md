# Spec-Driven 本地开发工作流

当用户希望将代码拉到本地修改（而非通过 `nocode send` 让 Agent 修改）时，使用以下阶段式工作流。
本工作流融合了 Spec-Driven 方法论，确保需求清晰、设计合理、实现可验证，并在每个阶段及时同步回 NoCode 验证渲染效果。

## 工作流概览

```
Phase 0: INITIALIZE
    ↓
    nocode code clone → 安装依赖 → 准备开发环境
    ↓
Phase 1: ANALYZE ⭐ 暂停
    ↓
    理解需求 → 生成 requirements.md
    ↓ [🛑 等待用户确认]
Phase 2: DESIGN ⭐ 暂停
    ↓
    技术设计 → 生成 design.md + tasks.md
    ↓ [🛑 等待用户确认]
Phase 3: IMPLEMENT（循环）⭐ 暂停
    ↓
    ⭐ code clone 同步最新 → 编写代码 → build → git push → code pull → screenshot
    ↓ [🛑 每完成一个模块后暂停，等用户确认渲染效果]
Phase 4: VALIDATE
    ↓
    最终 build + screenshot 全面验证
    ↓
Phase 5: HANDOFF
    ↓
    更新文档 → 清理 → 交付
    ↓ [🎉 完成]

⭐ = 关键阶段，必须暂停等待用户确认
```

## ⛔ 核心约束

### ⛔ 架构保护（最高优先级，本地开发前必检）

**每次在本地修改代码前，必须对照 [project-architecture.md](../project-architecture.md) 确认修改不涉及受保护文件：**

1. 完全禁止修改的文件（`vite.config.js`、`src/main.jsx`、`src/contexts/NoCodeContext.jsx` 等）→ **不得编辑、删除、重命名、覆盖**
2. 受限修改的文件（`index.html`、`package.json`）→ 仅允许特定修改（如修改标题、添加业务依赖），禁止删改原有 `<script>` 标签或修改 `scripts` 字段
3. 如果需求涉及 HTML 复刻、数据驱动看板等场景 → 按 [best-practices.md](../best-practices.md) 中的对应流程执行

**意外修改了受保护文件 → 立即 `git checkout -- <文件>` 还原。** 完整受保护清单、后果说明见 [project-architecture.md](../project-architecture.md)。

### 包管理器判断规则（强制）

**所有 install 和 build 操作必须先判断项目使用的包管理器，严禁混用：**

- **NoCode 项目默认使用 yarn 1.x**（非 yarn 2+/berry）
- 检查项目根目录是否有 `yarn.lock`
    - 有 `yarn.lock` → 使用 **yarn**（`yarn install`、`yarn build`）
    - 没有 `yarn.lock` → 使用 **npm**（`npm install`、`npm run build`）
- **严禁混用**：有 `yarn.lock` 用 yarn，没有用 npm
- **必须使用美团源**：`--registry=http://r.npm.sankuai.com`
- **⛔ 必须安装 devDependencies**：在 `NODE_ENV=production` 时会自动跳过 devDependencies（vite、eslint 等构建工具），导致 build 失败。**必须加 `--production=false`**

### 代码同步规则（强制）

- **⛔ 每次修改代码前必须先执行 `nocode code clone <chatId>`**：同步远程最新代码到本地。这是增量更新（fetch + reset），不会重新全量 clone。**跳过此步会导致 `git push` 被拒绝（远程有新提交），需要额外处理 rebase/merge，增加不必要的复杂度**

### 分支规则（强制）

- **⛔ 必须在 `repo.branch` 分支上修改代码**：`nocode code clone` 会自动 checkout 到正确分支，NoCode 只认这个分支，提交到其他分支的代码无法通过 `code pull` 同步回 NoCode
- **⛔ 严禁切换分支或创建新分支开发**

### Commit Message 规范（强制）

- **⛔ 所有 commit message 必须以 `【NoCode CLI】feat:` 前缀开头**，格式：`【NoCode CLI】feat: <描述>`

### 禁止事项

- **⛔ 严禁改动 NoCode 工程架构文件**：见上方「架构保护」章节
- **⛔ 本地开发期间禁止通过 `nocode send` 对话修改同一项目**：避免双方同时修改导致冲突
- **⛔ 修改前必须确保该 chatId 没有进行中的 Agent 对话流**

---

## Phase 0: INITIALIZE

**目标：** 拉取代码到本地，搭建开发环境

### 前置检查

- [ ] **确认 Git 已安装**：`git --version`（未安装则提示用户先安装）
- [ ] **确认 nocode CLI 已安装且为最新版**：`nocode --version`
- [ ] **确认已登录**：`nocode status`（未登录则按提示登录）

### Checklist

- [ ] **克隆代码到本地**：

    ```bash
    nocode code clone <chatId>
    # 或指定目录
    nocode code clone <chatId> --dir ~/my-project
    ```

    - 首次执行会全量 clone，后续执行会增量更新（fetch + reset）
    - 默认路径：`~/.nocode/workspaces/nocode-<chatId>/`

- [ ] **进入项目目录**（后续所有命令都在此目录下执行）：

    ```bash
    cd ~/.nocode/workspaces/nocode-<chatId>/
    # 或 cd 到 --dir 指定的目录
    ```

- [ ] **安装依赖**（必须判断包管理器）：

    ```bash
    # 检查是否有 yarn.lock
    ls yarn.lock

    # 有 yarn.lock → 用 yarn（必须加 --production=false 确保安装 devDependencies）
    yarn install --production=false --registry=http://r.npm.sankuai.com

    # 没有 yarn.lock → 用 npm（必须加 --include=dev 确保安装 devDependencies）
    npm install --include=dev --registry=http://r.npm.sankuai.com
    ```

    ⛔ 在 `NODE_ENV=production` 时会自动跳过 devDependencies（vite、eslint 等构建工具），导致 build 失败。**必须加 `--production=false`**

    ⚠️ **install 可能产生额外文件（不要提交）**：
    - **yarn**：本地 yarn 版本与 Sandbox 不同时，可能生成 `.yarn/`、`.yarnrc.yml` 等文件，以及修改 `yarn.lock`
    - **npm**：本地 npm 版本与 Sandbox 不同时，可能修改 `package-lock.json` 的格式/内容
    - **这些都不要提交**，否则会破坏 Sandbox 侧的依赖解析

- [ ] **验证 build 能通过**（确保初始代码可编译）：

    ```bash
    yarn build     # 或 npm run build
    ```

- [ ] **创建文档结构**（在 clone 下来的项目根目录下）：

    ```bash
    # 在项目根目录下创建，会随代码一起 push
    mkdir -p .ai-dev-docs/features .ai-dev-docs/temp
    ```

- [ ] **确定 feature 名称和模式**：
    - 分析用户需求，确定 feature 名称（kebab-case）
    - 判断 CREATE 或 UPDATE 模式
    - 创建或定位 feature 目录：`mkdir -p .ai-dev-docs/features/<feature-name>`

**Phase 0 完成后自动进入 Phase 1**

---

## Phase 1: ANALYZE

**目标：** 理解需求，生成需求规范

### Checklist

- [ ] 分析用户需求
- [ ] 分析现有代码（代码已在本地，直接读取文件即可）
- [ ] 生成 `.ai-dev-docs/features/<feature>/requirements.md`（EARS 格式）
- [ ] 识别依赖和约束

### 🛑 暂停 — 等待用户确认

```
┌─────────────────────────────────────────────────────────────┐
│  🛑 PHASE 1 CHECKPOINT - ANALYZE                           │
├─────────────────────────────────────────────────────────────┤
│  📄 输出: requirements.md                                  │
│  📊 需求数量: [X] 个                                       │
├─────────────────────────────────────────────────────────────┤
│  📋 需求摘要:                                              │
│  1. [需求1]                                                │
│  2. [需求2]                                                │
├─────────────────────────────────────────────────────────────┤
│  🤔 "c" 继续 / "m" 修改 / "a" 终止                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 2: DESIGN

**目标：** 技术设计，拆分任务

### Checklist

- [ ] 生成 `.ai-dev-docs/features/<feature>/design.md`（架构、数据流、接口）
- [ ] 生成 `.ai-dev-docs/features/<feature>/tasks.md`（按模块拆分任务）
- [ ] 每个任务粒度为一个可独立验证的功能模块

### 任务拆分示例

tasks.md 的拆分应考虑**同步验证粒度**：关联的子任务归为一组，每组完成后统一 build → push → sync → 截图。

```markdown
## Tasks

- [ ] 1. 用户注册模块           ← 第1组：1.1~1.3 关联，一起实现后统一验证
    - [ ] 1.1 注册表单组件
    - [ ] 1.2 表单验证逻辑
    - [ ] 1.3 API 对接
- [ ] 2. 数据展示模块           ← 第2组：2.1~2.2 关联，一起实现后统一验证
    - [ ] 2.1 数据列表组件
    - [ ] 2.2 分页逻辑
```

每个顶层模块（1、2）即为一个同步验证组。Phase 3 会按组循环。

### 🛑 暂停 — 等待用户确认

```
┌─────────────────────────────────────────────────────────────┐
│  🛑 PHASE 2 CHECKPOINT - DESIGN                            │
├─────────────────────────────────────────────────────────────┤
│  📄 输出: design.md, tasks.md                              │
│  📊 任务数: [X] 个                                         │
├─────────────────────────────────────────────────────────────┤
│  🤔 "c" 继续 / "m" 修改 / "a" 终止                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 3: IMPLEMENT（核心循环）

**目标：** 按任务清单在本地编写代码，完成一组可验证的功能后同步验证

### ⭐ 同步验证的粒度

tasks.md 中的子任务之间往往有关联性（比如"表单组件"和"表单验证"必须一起才能看到效果），不需要每个子任务都单独同步。**同步验证的粒度是"一组可独立验证的关联任务"**：

- 多个紧密关联的子任务 → **一起实现，统一 build → push → sync → 截图**
- 独立的功能模块 → 单独一轮循环

**示例：**

```markdown
## Tasks

- [ ] 1. 用户注册模块           ← 1.1~1.3 关联，一起实现后统一验证
    - [ ] 1.1 注册表单组件
    - [ ] 1.2 表单验证逻辑
    - [ ] 1.3 API 对接
    → 完成 1.1~1.3 后：build → push → code pull → screenshot → 暂停

- [ ] 2. 数据展示模块           ← 2.1~2.2 关联，一起实现后统一验证
    - [ ] 2.1 数据列表组件
    - [ ] 2.2 分页逻辑
    → 完成 2.1~2.2 后：build → push → code pull → screenshot → 暂停
```

### ⭐ 实现-验证循环

**对每组关联任务，重复以下循环：**

```
┌─── 第 N 组任务 ───────────────────────────────────────────┐
│                                                            │
│  0. ⛔ 同步远程最新代码到本地（强制，不可跳过）           │
│       nocode code clone <chatId>                           │
│       跳过 → push 被拒绝，需额外处理 rebase              │
│       ↓                                                    │
│  1. 📝 在本地实现该组所有关联子任务                        │
│       ↓                                                    │
│  2. 🔨 本地 build 验证                                     │
│       yarn build  (或 npm run build)                       │
│       ↓ build 失败 → 修复后重新 build                      │
│       ↓ build 成功 ↓                                       │
│  3. 📤 提交并推送                                          │
│       git add <具体文件>                                   │
│       git commit -m "【NoCode CLI】feat: 第N组描述"                      │
│       git push                                             │
│       ↓                                                    │
│  4. 🔄 同步回 NoCode Sandbox                               │
│       nocode code pull <chatId>                            │
│       ↓                                                    │
│  5. 📸 截图验证渲染效果                                    │
│       nocode screenshot <chatId>                           │
│       ↓                                                    │
│  6. ✅ 更新 tasks.md 标记该组任务完成                      │
│                                                            │
│  🛑 暂停 — 展示截图，等待用户确认渲染效果                  │
│     "c" 继续下一组                                         │
│     "m" 修改当前实现                                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 实现步骤详解

#### 步骤 0: 同步远程最新代码（⛔ 强制，每次修改前必做，不可跳过）

```bash
nocode code clone <chatId>
```

- **⛔ 每次开始修改代码前必须执行**，确保本地代码是最新的
- `code clone` 是增量更新（fetch + reset），不会重新全量 clone，执行速度很快
- **跳过的后果**：如果远程有新提交（如上一轮 code pull 触发 Sandbox 重建产生的 commit），`git push` 会被拒绝，需要额外处理 `git stash → git pull --rebase → git stash pop → git push`，增加不必要的复杂度和冲突风险
- ⚠️ 增量更新会丢弃本地未提交的修改（`reset --hard`），所以确保上一组任务已 commit + push 后再执行

#### 步骤 1: 编写代码

- 在本地 clone 的项目中修改文件
- 遵循项目现有代码风格
- 添加有意义的注释

#### 步骤 2: 本地 build 验证（⭐ 每次必做）

```bash
# 根据包管理器执行
yarn build     # 或 npm run build
```

- build 失败 → **必须修复后再继续**，不要将有错误的代码推送
- build 成功 → 继续下一步

#### 步骤 3: 提交并推送

```bash
# ⚠️ 推荐：只 add 你实际修改的文件，避免意外提交
git add src/pages/Index.jsx src/components/Foo.jsx   # 精确指定文件
# 或者用 git add . 但必须先检查 status
git status   # 确认没有 .DS_Store、.yarn/、yarn.lock 等意外文件
git commit -m "【NoCode CLI】feat: <模块描述>"
git push
```

- **⛔ commit message 必须以 `【NoCode CLI】feat:` 前缀开头**，不可省略
- **⚠️ 避免 `git add .` 引入意外文件**：
    - `.DS_Store`（macOS 系统文件）
    - `.yarn/`、`.yarnrc.yml`（本地 yarn 版本产生的文件）
    - `yarn.lock` 变更（本地 yarn 版本与 Sandbox 不同时会被修改）
    - `package-lock.json` 变更（本地 npm 版本与 Sandbox 不同时会被修改）
    - `node_modules/`（应在 `.gitignore` 中）
    - `.ai-dev-docs/temp/`（过程文档）
- **推荐用 `git add <具体文件>` 而非 `git add .`**
- 确保推送到 `nocode detail <chatId>` 返回的 `repo.branch` 分支
- 每组关联任务一次 commit，保持提交粒度清晰

#### 步骤 4: 同步回 NoCode Sandbox

```bash
nocode code pull <chatId>
```

- 如果提示 Sandbox 有未推送的本地变更，展示警告给用户确认后再加 `--force`
- 详细规则参见 [cmd-code.md](../commands/cmd-code.md)

#### 步骤 5: 截图验证

```bash
nocode screenshot <chatId>
```

- 展示截图给用户确认渲染效果
- 如果渲染异常（白屏、样式错乱），**不要自行通过 `nocode send` 修复**，参见异常处理规则

#### 步骤 6: 更新 tasks.md

```markdown
- [x] 1.1 注册表单组件 ✅ 2025-04-10
- [ ] 1.2 表单验证逻辑 (next)
```

### 🛑 暂停 — 每个模块完成后暂停

```
┌─────────────────────────────────────────────────────────────┐
│  🛑 模块 [N] 完成                                          │
├─────────────────────────────────────────────────────────────┤
│  📸 截图: [screenshot URL]                                 │
│  📊 进度: [X/Y] 任务完成                                   │
├─────────────────────────────────────────────────────────────┤
│  🤔 确认渲染效果：                                         │
│  - "c" 继续下一个模块                                      │
│  - "m" 修改当前模块                                        │
│  - "a" 终止                                                │
└─────────────────────────────────────────────────────────────┘
```

### 所有模块完成后

```
┌─────────────────────────────────────────────────────────────┐
│  🛑 PHASE 3 CHECKPOINT - IMPLEMENT                         │
├─────────────────────────────────────────────────────────────┤
│  📊 完成度: [X/X] 全部完成                                 │
│  📁 修改文件: [列表]                                       │
├─────────────────────────────────────────────────────────────┤
│  🤔 "c" 继续到验证阶段 / "m" 补充修改                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 4: VALIDATE

**目标：** 确认 Sandbox 侧与本地一致，最终验证

### Checklist

- [ ] **确认本地所有修改已 push**：

    ```bash
    git status                     # 确认 working tree clean
    git log --oneline -3           # 确认最新 commit 已推送
    ```

- [ ] **确认 Sandbox 已同步最新代码**：

    ```bash
    nocode code pull <chatId>      # 确保 Sandbox 是最新的
    ```

- [ ] **最终截图验证**（确认 Sandbox 渲染正确）：

    ```bash
    nocode screenshot <chatId>
    ```

- [ ] **核对 tasks.md 所有任务已完成**

**Phase 4 完成后自动进入 Phase 5**

---

## Phase 5: HANDOFF

**目标：** 更新文档，清理，交付

### Checklist

- [ ] **更新 feature 文档**：
    - 确保 requirements.md 反映最终实现
    - 确保 design.md 包含所有设计决策
    - 确保 tasks.md 所有任务标记完成

- [ ] **提交文档更新**：

    ```bash
    git add .ai-dev-docs/
    git commit -m "【NoCode CLI】feat: update spec docs"
    git push
    nocode code pull <chatId>
    ```

- [ ] **清理 temp 目录**：

    ```bash
    rm -rf .ai-dev-docs/temp/*
    ```

- [ ] **最终交付**：

    ```
    ┌─────────────────────────────────────────────────────────────┐
    │  🎉 本地开发完成                                            │
    ├─────────────────────────────────────────────────────────────┤
    │  📊 完成度: [X/X] 全部完成                                 │
    │  📸 最终截图: [URL]                                        │
    │  🔗 作品链接: [chatUrl]                                    │
    ├─────────────────────────────────────────────────────────────┤
    │  📁 文档:                                                  │
    │  - requirements.md ✅                                      │
    │  - design.md ✅                                            │
    │  - tasks.md ✅                                             │
    └─────────────────────────────────────────────────────────────┘
    ```

---

## 🚨 异常处理

### Build 失败

- **不要将有错误的代码推送到仓库**
- 阅读错误日志，修复后重新 build
- 常见问题：
    - 缺少依赖（需要 install）
    - TypeScript 类型错误、import 路径错误
    - `This package doesn't seem to be present in your lockfile` → 需要先执行 `yarn install`
    - `vite: command not found` 或 `Cannot find module 'vite'` → devDependencies 未安装，需加 `--production=false` 重新 install（原因：`NODE_ENV=production` 导致 yarn 跳过了 devDeps）

### 截图渲染异常（白屏、样式错乱）

**首先区分是本地代码问题还是平台侧异常：**

#### 本地代码问题（可自行修复）

- **⛔ 不要通过 `nocode send` 修复**，这会导致与本地修改冲突
- 在本地排查 → 修复 → 重新走 build → push → code pull → screenshot 循环
- 常见原因：
    - 构建产物未正确生成 → 检查 build 输出
    - 依赖缺失 → 在美团源重新 install
    - NoCode 架构文件被意外修改（见上方「禁止事项」清单）→ 立即 `git checkout -- <文件>` 还原
    - 代码逻辑错误（语法错误、组件报错）→ 检查浏览器控制台

#### 平台侧异常（⛔ 严禁自行修复）

- 如果本地 build 正常、代码无误，但截图仍然白屏/异常 → 可能是平台侧问题
- **停止操作 → 告知用户 → 引导联系 NoCode 研发排查**
- 参见 SKILL.md [异常处理规则]

### Git 冲突

- 如果 `git pull` 出现冲突，必须先解决冲突再继续
- 通常是因为用户在主站通过对话修改了代码，同时本地也做了修改
- 解决方案：手动合并冲突 → 重新 build 验证 → 继续流程

### code pull 失败

- 如果提示 Sandbox 有未推送的本地变更，展示警告给用户
- 用户确认后可以加 `--force` 强制同步
- 详细规则参见 [cmd-code.md](../commands/cmd-code.md)

