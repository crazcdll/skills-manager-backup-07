# Stage 2：仓库初始化

## 阶段概述

> **目标**：初始化项目标准目录结构、创建 workflow-context.json、准备分支和文档目录。
> **阻塞级别**：🔴 阻塞 — 初始化失败则终止流程。

---

## 输入

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 环境检查报告 | Stage 1 输出 | 必须为 passed/warning（前置准备与环境检查阶段产出） |
| 项目路径 | 用户输入 / pwd | 工作根目录 |

---

## 过程

### Step 2.0：仓库初始化
- step1：先检查当前工作目录下是否已经存在项目仓库，如果已经存在则直接输出仓库地址和分支信息，跳过后面的步骤
- step2：创建仓库，把项目clone下来，使用`git clone`，输出仓库地址和分支信息

### Step 2.1：创建/切换开发分支

使用 `AskQuestion` 工具让用户选择分支创建方式，默认选中方案1：

```
AskQuestion({
  title: "分支创建方式",
  questions: [
    {
      id: "branch_strategy",
      prompt: "请选择开发分支的创建方式：",
      options: [
        { id: "fedo", label: "方案1：基于FEDO任务创建分支（推荐）" },
        { id: "local", label: "方案2：本地创建分支" },
        { id: "existing", label: "方案3：使用已有分支" }
      ]
    }
  ]
})
```

根据用户选择执行对应方案：

| 用户选择 | 执行方案 |
|----------|----------|
| `fedo`（基于FEDO任务创建分支） | 执行方案1：通过 `duo-fedo skill` 创建任务并生成分支 |
| `local`（本地创建分支） | 执行方案2：基于当前需求在本地创建分支 |
| `existing`（使用已有分支） | 执行方案3：提示用户输入已有分支名称并切换 |

#### 方案1：基于FEDO任务创建分支

- step1：检查当前是否在`feature/xx`开发分支上，如果已经切换分支检查是否关联`fedo`任务，检查都通过直接输出开发分支和`fedo`任务完整链接（不能只把taskId输出出来，需要完整链接），跳过后面的步骤
- step2：分支的创建由`duo-fedo skill` 完成，在`duo-fedo`创建任务的时候生成新分支，`fedo`任务创建完成输出任务链接。
- step3：启动新创建的`fedo`任务，输出创建的分支，并切换到新的开发分支
- step4：将创建的分支作为current_dev_branch，保存在workflow-context.json中

#### 方案2：本地创建分支
- step1: 切换到master分支，如果有未提交的先进行提交再切换到master。
- step2: 基于当前需求创建分支，作为current_dev_branch，保存在workflow-context.json中

#### 方案3：使用已有分支
- 需要用户输入分支名称，作为current_dev_branch，保存在workflow-context.json中

### Step 2.2：创建标准目录结构

- `.duo` 文件夹要放到项目目录`project_root`下，如果没有需要新建
- 产出的文档按需求维度来区分,在`.duo`目录下建文件夹`{demand_description}/docs`,如果没有需要新建，`{demand_description}` 文件夹使用英文命名。

目录如下：
```
{project_root}/
├── .duo/{demand_description}/
│                 ├── docs/                    # 文档产出目录
│                 │   ├── demand-spec.md
│                 │   ├── tech-design.md
│                 │   ├── dev-tasks.md
│                 │   ├── 03-implementation-checklist.md
│                 │   └── 04-delivery-reports.md
│                 └── workflow-context.json     # 全局状态文件
├── material/                     # 物料组件（如涉及）
└── src/                          # 源码目录
```

### Step 2.3：初始化 workflow-context.json

- workflow-context.json 文件放到`{project_root}/.duo/{demand_description}`下，如果没有需要新建，否则跳过
- 将 Stage 1 环境检查提取参数和当前初始化信息写入 `workflow-context.json`。

> ⚠️ **初始化模板以 [`workflow-context-schema.md`](../workflow-context-schema.md) 中"初始化模板"章节为唯一权威来源，禁止使用其他简化版本。**
> 写入时需将以下占位值替换为实际值：
> - `meta.started_at` → 当前 ISO8601 时间
> - `meta.project_root` → 仓库根目录绝对路径
> - `meta.mode` → 用户在流程启动时确认的执行模式（`single_agent` 或 `multi_agent`）
> - `input.*` → Stage 1 提取的所有参数
> - `runtime.post_stage_hooks.skill_root` → fe-rd-workflow skill 的绝对路径
> - `outputs.branch.feature` → Step 2.1 确定的开发分支名
> - `outputs.branch.repo_ssh` → 仓库 SSH 地址

### Step 2.4：写入初始状态

将 Stage 1 的环境检查报告和当前初始化信息写入 `workflow-context.json`。

### Step 2.5：代码知识图谱就绪检查

`.code-graph` 与 `.duo` 同级，均位于 `{project_root}` 下。

```bash
[ -f {project_root}/.code-graph/meta.json ] || python3 {mt-graphify-lite-skill-path}/scripts/generate.py ensure --repo-root {project_root}
```

---

## 输出

| 产出物 | 路径 | 说明 |
|--------|------|------|
| 标准目录结构 | `{project_root}/.duo/` | 含 docs/ 和 workflow-context.json |
| 开发分支 | Git | feature/xxx |
| 初始状态 | `.duo/{demand_description}/workflow-context.json` | 全流程状态基线 |

---

## 异常处理

| 场景 | 处理方式 |
|------|----------|
| 分支创建失败 | 提醒用户使用`duo-fedo skill`创建分支 |
| 目录创建失败 | 检查权限，并进行尝试 |
| workflow-context 写入失败 | 检查磁盘空间和权限，并进行尝试 |

---
