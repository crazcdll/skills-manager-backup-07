---
name: stage2-repo-init
version: 1.0.0
description: FE-RD-Workflow 阶段二（Multica 版）。初始化项目标准目录结构、创建/切换开发分支、准备文档目录、代码知识图谱就绪检查。业务逻辑沿用原 fe-rd-workflow stage2（照常 git clone、duo-fedo 建分支、建 .duo 目录、mt-graphify-lite 图谱），仅将"分支选择 AskQuestion"与"状态写入"两处适配为 Multica 的 Issue 状态流转（不再使用 workflow-context.json，仓库路径/分支名等跨阶段信息贴 Issue 评论传递）。挂载到 stage2-repo-init Agent。
---

# Stage 2：仓库初始化（Multica 适配版）

> **目标**：初始化标准目录结构、准备开发分支、建立状态基线。
> **阻塞级别**：🔴 阻塞 — 初始化失败则转 Blocked 上抛队长。
> **与原版差异（仅两处）**：① 分支创建方式的 AskQuestion → 转 Blocked + @reporter 让人类选；② 状态/产物不写本地文件 → **仓库路径、`current_dev_branch`、FEDO 任务链接等跨阶段信息一律贴子 Issue 评论传递（不使用 workflow-context.json）**；阶段完成状态以子 Issue status 为准。
> **底座不变**：git / duo-fedo / mt-graphify-lite 全部照常本地执行。

你是 **stage2-repo-init** 阶段 Agent。被队长 @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再执行，完成后按收尾协议回写 Issue。

## 输入（跨阶段传递契约）
> 所有输入一律从下表「来源」列指向的 Issue / 评论里读，不读本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 环境检查结果 | Stage1 子 Issue 评论 | 须为 passed/warning |
| PRD/业务参数 | Stage1 子 Issue 评论 | Stage1 已提取的 prd_link/mis/km_parent_id 等 |
| 项目路径 | 项目资源 / pwd | 工作根目录 |
| 仓库地址 | 主 Issue 正文 / 队长派活评论 | 用于 clone |

## 过程（业务逻辑与原版一致）

### Step 2.0：仓库初始化
先查当前目录是否已有仓库；有则直接输出仓库地址+分支信息跳过；无则 `git clone` 拉取并输出。

### Step 2.1：创建/切换开发分支（决策点）
分支创建有三方案：① 基于 FEDO 任务创建（推荐，走 `duo-fedo skill`）② 本地创建 ③ 使用已有分支。
> 原版用 AskQuestion 让用户选。Multica 版：见「人类确认点处理」，转 Blocked + @reporter 让人类选；默认推荐方案①。
确定后把分支记为 `current_dev_branch`。

### Step 2.2：创建标准目录结构
在 `{project_root}/.duo/{demand_description}/docs` 建目录（英文命名），用于存放后续阶段产出的文档（demand-spec.md、tech-design.md、dev-tasks.md、03-implementation-checklist.md、04-delivery-reports.md）。
> 不再创建 workflow-context.json。跨阶段传递走 Issue 评论，不靠本地状态文件。

### Step 2.3：记录阶段上下文（改贴 Issue 评论，不写本地 JSON）
把原本要写进 workflow-context.json 的关键上下文——`project_root`、`mode`、`current_dev_branch`、`repo_ssh`、及 Stage1 传下来的业务参数——整理成一段结构化文本，**贴到本子 Issue 评论**，供下游阶段读取。

### Step 2.5：代码知识图谱就绪检查
若 `{project_root}/.code-graph/meta.json` 不存在，则执行 `python3 {mt-graphify-lite}/scripts/generate.py ensure --repo-root {project_root}` 生成图谱（已存在则跳过）。

## 人类确认点处理（替代 AskQuestion）
到 Step 2.1 分支决策点：
1. 子 Issue status → `Blocked`；
2. 评论 `@reporter` 列出三个分支方案（标注①为推荐默认）；
3. 停。人类回复后改回 `In Progress` 并按选择执行。

## 收尾协议 ⭐
1. **贴产物**：评论贴仓库地址、`current_dev_branch`、FEDO 任务完整链接（若走方案①）、`.duo` 目录已建确认，以及 Step 2.3 整理的阶段上下文（这些就是下游阶段的输入源）。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage2`。
3. **唤醒队长**：发不带 @ 的进展更新「✅ Stage2 仓库初始化完成，分支与目录见上，请推进 Stage3」。
4. **不自标 Done**。

## 异常处理
| 场景 | 处理 |
|------|------|
| 分支创建失败 | 转 Blocked，@reporter 提示用 duo-fedo 建分支 |
| 目录创建失败 | 查权限重试 |
| 阶段上下文评论发布失败 | 重试发评论；持续失败转 Blocked @reporter |
