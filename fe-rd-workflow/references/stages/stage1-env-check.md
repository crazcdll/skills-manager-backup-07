# Stage 1：前置准备与环境检查

> **🔴 MUST：完成所有前置准备并输出「阶段一执行确认单」后，才可进入阶段二。**
> **本文件是阶段一的强制执行手册，MUST_NOT 只读摘要就跳到执行。**

## 阶段概述

> **目标**：完成中断恢复检查、模型能力确认、权限设置、环境依赖检查和业务输入参数提取，为后续阶段提供可靠的基础设施。
> **阻塞级别**：🔴 阻塞 — 任一核心检查项不通过则终止整个流程。

### 职责边界

中断恢复、模型能力确认、权限设置、Git 状态、依赖检查、工作空间结构、业务输入参数提取。

### 入口铁律

Agent MUST 严格按以下顺序执行，缺一不可：

```
Step 0: 中断恢复检查（workflow-context.json 已存在时 MUST 执行）
  ↓
Step 1: 完整阅读本文件              ← 不得只读目录
  ↓
Step 2: 按 1.1 → 1.5 逐条执行     ← 严格按本文档命令，不得凭记忆推断
  ↓
Step 3: 输出「阶段一执行确认单」    ← 见文档末尾模板
  ↓
Step 4: 全部 PASS 后才可进入后续阶段
```

---
## 过程

### Step 1.0：中断恢复检查

`demand_description`是用户输入的学城链接中需求描述的英文名字。

> `.duo/{demand_description}/workflow-context.json` 已存在时，MUST 先执行 [check.md](../check.md) 的中断恢复检查，让用户确认已完成阶段后再继续；否则跳过中断检查，执行下一步。

1. find {project_root}/.duo -name "workflow-context.json"
2. 对每个找到的文件，读取 input.prd_link 和 input.user_description
3. 与当前输入的学城链接/需求描述做精确匹配
4. 命中 → 执行中断恢复；未命中 → 跳过

### Step 1.1：模型要求

| 能力要求           | 说明                                              |
| ------------------ | ------------------------------------------------- |
| 强大的文本处理能力 | 能够准确理解和生成 Groovy DSL 语法、JSON 配置文件 |
| 优秀的编码能力     | 能够编写规范的代码，避免语法错误和类型错误        |
| 严谨的逻辑思维     | 能够正确处理变量作用域、数据类型、表达式计算等    |
| 良好的上下文理解   | 能够理解多个协议文件之间的关联关系                |

**推荐模型**：Claude 3.5 Sonnet、Claude 3 Opus、GPT-4o 等高级模型,如果没有选择当前模型

### Step 1.2：权限设置

获取用户的mis号，安装 skill、学城文档的增删改查一律使用从输入中获取的 `mis` 来进行，获取方式如下：
- 方式1：从当前环境中检测，例如从 git / whoami 获取
- 方式2：用户在对话中直接告知
- 方式3：主动询问用户

### Step 1.3：环境依赖检查

####  Node.js 要求

| 工具    | 最低版本 | 说明                                                         |
| ------- | -------- | ------------------------------------------------------------ |
| Node.js | 20       | `mtskills`、`oa-skills` 和依赖自动安装流程要求 Node.js >= 20 |

```bash
node -v          # 确保 >= 20，否则 nvm use 20
```

> 🔴 依赖检查失败 MUST 立即终止流程并提示用户安装。

#### CLI 依赖检查

```bash
oa-skills citadel --help          # citadel（学城文档 CRUD）
fedo sso status                   # FEDO 平台操作
mtskills -h                       # Skill 包管理器
duo -h
```

缺失时自动安装：

| 工具           | 用途                        | 安装命令                                                                  |
| -------------- | --------------------------- | ------------------------------------------------------------------------- |
| @it/oa-skills  | 学城文档 CRUD               | `npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com` |
| @ee/fedo-cli   | FEDO 平台 CLI               | `npm install -g @ee/fedo-cli --registry=http://r.npm.sankuai.com`         |
| @mtfe/mtskills | Skill 管理工具              | `npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com`       |
| @meishi/duo-cli | duo CLI            | `npm install -g @meishi/duo-cli@latest --registry=http://r.npm.sankuai.com`       |

> 所有 CLI 环境依赖均为必选，缺任何一个都阻断流程。
> @meishi/duo-cli 版本要求 >= 0.4.62，进行检查确认，不符合要求进行升级到最新。

#### Git 环境检查

```
检查项：
□ Git 是否已安装
□ 当前目录是否在 Git 仓库内
□ 当前分支状态（是否有未提交的更改）
□ 远程仓库是否可访问
```

**通过标准**：
- Git 版本 ≥ 2.0
- 远程 origin 可访问

#### 业务权限验证

```
检查项：
□ FEDO SSO 登录态是否有效（fedo sso status）
□ 学城 KM 文档读写权限是否正常（oa-skills citadel getMarkdown 测试）
□ Code 平台 PR 权限是否正常（如需 PR 操作）
```

**通过标准**：
- 核心业务权限有效；缺失时给出警告但不阻断（除非后续阶段明确需要）
- 学城文档读取 60s超时中断，提醒用户关注大象账号授权。

#### Skill 依赖检查

```bash
node {fe-rd-workflow}/scripts/check-deps.js            # 检查依赖
node {fe-rd-workflow}/scripts/check-deps.js --install  # 自动安装缺失依赖
```

> `skills.json` 是依赖注册的唯一清单文件。`check-deps.js` 执行时会将 `scripts/skill-deps.json`（真实源）同步到 `skills.json`。
> **核心铁律：所有 Skill 依赖和 CLI 环境依赖均为必选。缺任何一个必须先中断流程。**

**注意**
- 1. 检查通过之后，工作目录`workspace root`发现有`.catpaw/skills`目录，把`.claude/skills`下面的文件复制到`.catpaw/skills`目录下；否则跳过
- 2. 如果有新安装skill，需要把新安装 skill 从`.claude/skills` 下面的文件复制到`.catpaw/skills`目录下一份，后续有新增的skill也按照此规则执行。

#### Skill 自身更新检查

> 🔴 **每次启动流程时 MUST 执行**。检查当前 `fe-rd-workflow` Skill 自身是否有远端更新，确保使用最新版本。

```bash
# 仅检查是否有更新（不执行更新，exit code 2 表示有更新可用）
node {fe-rd-workflow}/scripts/check-deps.js --self-check

# 检查并自动更新到最新版本
node {fe-rd-workflow}/scripts/check-deps.js --self-update
```

**执行逻辑**：

1. 通过 `mtskills search` 获取远端最新版本信息
2. 比较本地 SKILL.md 中的 `version` 字段与远端版本号
3. 若版本号不可用，则比较本地文件修改时间与远端更新时间
4. 有更新时：
   - `--self-check`：仅报告更新，exit code 2，提示用户使用 `--self-update`
   - `--self-update`：自动执行 `mtskills pull fe-rd-workflow` 更新，更新后重新同步 `skills.json`

**更新后行为**：
- 更新成功后，MUST 重新读取 SKILL.md 和当前阶段文档，确保使用最新流程规范
- 更新失败时输出手动更新命令：`mtskills pull fe-rd-workflow`

| 场景 | 建议操作 |
|------|----------|
| 首次启动流程 | 执行 `--self-update` 确保最新 |
| 续跑恢复 | 执行 `--self-check`，有更新时询问用户是否更新 |
| 用户主动要求检查 | 执行 `--self-check` 并报告结果 |

### Step 1.4：输入检查

> 从用户提供的信息中提取后续所有阶段需要的前置参数。参数不是现成变量，必须主动向用户索要并从文档中提取。

#### 必填参数

| 参数          | 说明                                  | 来源                     |
| ------------- | ------------------------------------- | ------------------------ |
| `mis`         | 用户 MIS 号                           | 用户直接告知             |
| `prd_link`    | PRD 链接                              | 文档表格提取或用户提供   |
| `km_parent_id`| 学城需求记录文档 contentId            | 从学城链接解析           |
| `api_link`    | 接口文档链接                          | 文档表格提取             |

#### 可选参数

| 参数          | 说明                                  |
| ------------- | ------------------------------------- |
| `ux_link`     | 印迹视觉稿链接                       |
| `fedo_info`   | Fedo 任务信息（ones_link / iteration_name / task_name 等） |

#### 提取流程

1. 从用户提供的学城链接解析 `contentId`（`km.sankuai.com/collabpage/{contentId}`）
2. 从文档表格中提取 `mis` / `ones` / `PRD` / `视觉稿` / `fedo地址` / `接口文档` 等字段
3. 从 fedo 地址解析 `groupId` / `sprintId`
4. 两者均失败才提示用户手动补充

### Step 1.5：当前项目环境检查

```
检查项：
□ 操作系统 / shell / 日期时间 / 用户信息
□ 工作目录 / 项目路径
□ Git 分支
□ 检查当前项目是否存在
□ 组件体系 / 项目类型
```

## 输出

### 状态判定规则

| 总体状态 | 条件 | 后续动作 |
|----------|------|----------|
| `passed` | 所有核心检查项通过 | → 进入 Stage 2 |
| `warning` | 核心通过，非核心有缺失 | → 提示用户，继续进入 Stage 2 |
| `failed` | 任一核心检查项失败 | → 终止流程，输出修复建议 |

---

### 阶段一执行确认单输出

> **这是离开阶段一、进入阶段二的唯一凭证。未输出 = 未完成阶段一。**

### 确认单模板

```
📋 阶段一执行确认单
═══════════════════════════════════════════════════════════
【1.0 中断恢复】
  ✅ workflow-context.json：[不存在/已恢复确认]

【1.1 模型要求】
  ✅ 当前模型：[模型名称]

【1.2 权限设置】
  ✅ mis：[用户提供的 mis 号]

【1.3 依赖检查】
  — 环境 CLI（全部必选）—
  ✅ Node.js 版本：vXX.XX.X（≥20：PASS）
  ✅ oa-skills CLI：已安装（`oa-skills citadel --help` 验证）
  ✅ @ee/fedo-cli：已安装（`fedo sso status` 验证）
  ✅ @mtfe/mtskills：已安装（`mtskills -h` 验证）
  ✅ @meishi/duo-cli：已安装，版本 ≥ 0.4.49

  — Git 环境 —
  ✅ Git 版本：vXX.XX.X（≥2.0：PASS）
  ✅ 远程仓库：可访问

  — 业务权限 —
  ✅ FEDO SSO：有效
  ✅ 学城 KM：可读写

  — Skill 依赖（18 个，全部必选）—
  ✅ check-deps.js 执行结果：18/18 PASS
  ✅ skills.json 已同步

  — Skill 自身更新检查 —
  ✅ fe-rd-workflow 版本：[本地版本号]（远端：[远端版本号]，状态：[已最新/有更新/已更新]）

【1.4 输入检查】
  ✅ mis：[已获取]
  ✅ prd_link：[已获取]
  ✅ km_parent_id：[已获取]
  ✅ api_link：[已获取/可选未提供]

【1.5 项目环境】
  ✅ 操作系统 / shell / 日期时间 / 用户：[已检查]
  ✅ 工作目录 / 项目路径 / Git 分支 / 组件体系 / 项目类型：[已检查]
═══════════════════════════════════════════════════════════
✅ 全部 PASS，可进入后续阶段
```

### 确认单规则

- 任一项 ❌ 或"未 PASS"→ **立即中断**，明确告知缺失项并提供修复建议
- 修复后必须重新执行 1.1 → 1.5 全部子步骤，重新输出完整确认单
- 确认单必须**逐项输出**，不得用"已全部通过"一句话替代
- 每项状态基于**本次对话实际执行的命令输出**，不得凭记忆填写


完成确认单后，如果有未PASS的**必须使用 `AskQuestion` 工具暂停并等待用户确认**：

```
AskQuestion({
  title: "前置准备和环境检查",
  questions: [
    {
      id: "env_check",
      prompt: "环境检查是否通过？",
      options: [
        { id: "yes", label: "确认，继续下一步" },
        { id: "no", label: "修改后重新检查" },
        { id: "supplement", label: "补充更多内容" },
        { id: "skip", label: "跳过此阶段" }
      ]
    }
  ]
})
```

根据用户选择执行对应动作：

| 用户选择 | 动作 |
|----------|------|
| `yes`（确认，继续下一步） | 进入 Step 2 |
| `no`（修改后重新检查） | 根据用户反馈修改 |
| `supplement`（补充更多） | 收集补充内容 |
| `skip`（跳过此阶段） | 直接进入 Stage 2 |


---

## 异常处理

- Git 未安装: 提示用户安装 Git，终止流程
- 权限缺失: 记录到 warnings，后续涉及时再提示
- CLI 缺失: 自动安装，安装失败则终止流程
- Skill 依赖缺失: 执行 `check-deps.js --install`，安装失败则终止流程
