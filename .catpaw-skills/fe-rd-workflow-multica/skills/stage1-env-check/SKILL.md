---
name: stage1-env-check
version: 1.0.0
description: FE-RD-Workflow 阶段一（Multica 版）。完成中断恢复、模型能力确认、权限设置、环境依赖检查、业务输入参数提取，为后续阶段提供可靠基础设施。业务逻辑沿用原 fe-rd-workflow stage1（照常跑 node/CLI/skill 依赖检查），仅将"AskQuestion 暂停"与"状态写入"两处适配为 Multica 的 Issue 状态流转（不再使用 workflow-context.json，跨阶段信息一律走 Issue 评论）。挂载到 stage1-env-check Agent。
---

# Stage 1：前置准备与环境检查（Multica 适配版）

> **目标**：完成中断恢复、模型能力确认、权限设置、环境依赖检查、业务输入参数提取。
> **阻塞级别**：🔴 阻塞 — 任一核心检查项不通过则该子 Issue 转 Blocked 并上抛队长，不得推进 Stage2。
> **与原版差异（仅两处）**：① AskQuestion 暂停 → 转 Blocked + @reporter 上抛；② 状态不写本地文件 → 更新子 Issue status + Issue 评论留痕（**不使用 workflow-context.json**）。
> **底座不变**：node/oa-skills/fedo/mtskills/duo-cli/check-deps.js 全部照常在本地 daemon 执行。

你是 **stage1-env-check** 阶段 Agent。被队长 `fe-rd-orchestrator` @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再在本地执行全部检查，完成后按"收尾协议"回写 Issue。

## 输入（跨阶段传递契约）

> 砍掉本地 JSON 后，**所有输入一律从下表「来源」列指向的 Issue / 评论里读**，不得读任何本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| PRD/学城链接 | Project 主 Issue 正文 / 队长派活评论 | 用于解析 contentId、提取业务参数 |
| mis | git/whoami 或用户告知 | skill 安装、学城 CRUD 一律用此 mis |
| 项目路径 | 项目资源绑定 / pwd | 工作根目录 |

## 过程（业务逻辑与原版一致）

### Step 1.0：中断恢复检查
`demand_description` = 学城链接里需求描述的英文名。中断恢复**改为读 Issue**：查本子 Issue 当前 status + 评论历史（队长/本 Agent 之前贴的产物与确认单）→ 与当前派活输入精确匹配 → 命中则从上次断点续做，未命中按全新执行。（不再依赖 `.duo/.../workflow-context.json`；Issue 状态对队长和全体队员可见，比本地文件更可靠。）

### Step 1.1：模型要求
确认当前模型具备 Groovy DSL/JSON 处理、编码、逻辑、上下文理解能力（推荐 Claude 3.5 Sonnet / Opus / GPT-4o 级别）。

### Step 1.2：权限设置
获取用户 mis（git/whoami → 用户告知 → 主动询问），后续 skill 安装与学城 CRUD 一律用此 mis。

### Step 1.3：环境依赖检查（全部必选，缺一阻断）
- Node.js ≥ 20（`node -v`，否则 `nvm use 20`）
- CLI：`oa-skills citadel --help` / `fedo sso status` / `mtskills -h` / `duo -h`；缺失按原版表自动安装（`npm i -g @it/oa-skills@latest` 等，registry=http://r.npm.sankuai.com）。`@meishi/duo-cli` ≥ 0.4.62。
- Git：版本 ≥ 2.0、在仓库内、远程 origin 可访问。
- 业务权限：FEDO SSO 登录态、学城读写、Code PR 权限。
- Skill 依赖：`node {fe-rd-workflow}/scripts/check-deps.js`（`--install` 自动装；exit 0=ready,1=fail,2=有更新）。
- Skill 自更新：`check-deps.js --self-check` / `--self-update`。

### Step 1.4：输入检查
提取必填参数 `mis` / `prd_link` / `km_parent_id` / `api_link`，可选 `ux_link` / `fedo_info`。解析 contentId、从文档表格提取字段、从 fedo 地址解析 groupId/sprintId。

### Step 1.5：当前项目环境检查
OS/shell/时间/用户、工作目录/项目路径、Git 分支、项目是否存在、组件体系/项目类型。

## 输出：阶段一执行确认单

在 Issue 评论里**逐项**输出确认单（不得用"已全部通过"一句话替代，每项基于本次实际命令输出），标题为「📋 阶段一执行确认单」，至少覆盖以下各项并标注实际结果：

- 1.0 中断恢复：续做 / 全新执行，依据
- 1.1 模型能力：实际确认结果
- 1.2 权限 / mis：实际确认结果
- 1.3 依赖：Node / oa-skills / fedo-cli / mtskills / duo-cli / Git / SSO / KM 各项通过情况，check-deps N/N PASS
- 1.4 输入：prd_link / km_parent_id / api_link（可选项注明是否提供）
- 1.5 项目环境：实际检查结果

最后注明：全部 PASS，可进入后续阶段。

## 人类确认点处理（替代原 AskQuestion）
确认单出现任一 ❌ 或非核心缺失需用户拍板时：
1. 子 Issue status → `Blocked`（`multica issue update <id> --status blocked`）；
2. 评论里 `@reporter` 列出缺失项 + 修复建议 + 选项（确认继续 / 修复后重检 / 补充 / 跳过）；
3. 停。人类回复后改回 `In Progress`，按其选择执行。

## 收尾协议 ⭐
全部 PASS 后依次做完：
1. **贴产物**：在子 Issue 评论贴完整确认单（队长据此判断可否标 Done）。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage1`（失败静默不阻塞）。
3. **唤醒队长**：发一条**不带 @** 的进展更新，如「✅ Stage1 环境检查全部 PASS，确认单见上，请推进 Stage2」。
4. **不自标 Done**：Done 由队长校验后流转。

## 异常处理
| 场景 | 处理 |
|------|------|
| Git 未安装 | 转 Blocked，@reporter 提示安装 |
| CLI 缺失 | 自动安装；失败转 Blocked |
| Skill 依赖缺失 | `check-deps.js --install`；失败转 Blocked |
| 权限缺失（非核心） | 记 warning，后续涉及时再上抛 |
| 学城读取 60s 超时 | 提醒关注大象账号授权 |
