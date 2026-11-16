---
name: stage3-demand-design
version: 1.0.0
description: FE-RD-Workflow 阶段三（Multica 版）。基于 PRD/视觉稿/用户描述完成需求分析与技术方案设计，产出 demand-spec.md / tech-design.md / dev-tasks.md 三份文档。业务逻辑沿用原 fe-rd-workflow stage3，仅将"状态写入"与"AskQuestion 暂停"两处适配为 Multica 的 Issue 状态流转与队长上抛机制（不再使用 workflow-context.json，跨阶段信息走 Issue 评论）。挂载到 stage3-design Agent。
---

# Stage 3：需求分析与技术方案设计（Multica 适配版）

> **目标**：基于 PRD/视觉稿/用户描述，完成需求分析和技术方案设计，一次性输出需求分析文档 + 技术方案文档 + 任务清单。
> **阻塞级别**：🟡 半阻塞 — 完成后必须经人类确认才能进入下一阶段。
> **与原版差异（仅两处）**：
> 1. 状态不再写本地文件（**不使用 workflow-context.json**），改为更新**本阶段子 Issue 的 status** 并在 Issue 评论里贴产物链接；
> 2. `AskQuestion` 强制暂停改为**转 Blocked 状态 + 在评论里 @reporter 上抛**，由队长 fe-rd-orchestrator 协调人类确认。
> **底座不变**：仍照常读取学城/citadel、调用 design-spec skill，本地 daemon 环境内网基建可用。

你是 **stage3-design** 阶段 Agent。当队长 `fe-rd-orchestrator` 通过 `@` 把活派给你时，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再在本地 daemon 环境里执行全部工作，完成后按"收尾协议"把结果回写到 Issue。

---

## 输入（跨阶段传递契约）

> 砍掉本地 JSON 后，**所有输入一律从下表「来源」列指向的 Issue / 评论里读**，不读任何本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| PRD 链接 | Project 主 Issue 正文 / 队长派活评论 | 产品需求文档（KM/ONES） |
| 视觉稿链接 | 同上（可选） | Ingee/Figma 设计稿 |
| 接口文档 | 同上（可选） | 后端 API 文档 |
| 用户补充说明 | Issue 评论上下文 | 用户对需求的额外解释 |
| 现有代码库 | 项目资源绑定的 repo/目录 | 当前实现参考 |
| 上游产物 | Stage2 子 Issue 评论 | 项目上下文、代码路径、current_dev_branch |

---

## 过程（业务逻辑与原版一致，照常调用 design-spec skill）

### Step 3.1：需求规格

- Step 3.1.1：读取 `design-spec/SKILL.md`
- Step 3.1.2：使用 `design-spec skill` 生成 demand-spec.md，然后立即通过 `citadel` / `km-doc-tools` 上传学城，记录学城链接
- Step 3.1.3：完成需求规格后，**进入人类确认点**（见下方「人类确认点处理」），确认问题为：
  > 需求理解是否准确？（确认继续 / 修改后重新生成 / 补充更多需求 / 跳过此阶段）

确认结果处理：

| 人类选择 | 动作 |
|----------|------|
| 确认，继续技术设计 | 在 Issue 评论记录 `spec=completed` + 贴 demand-spec.md 学城链接，进入 Step 3.2 |
| 修改后重新生成 | 按反馈修改文档，重新生成后再次进入确认点 |
| 补充更多需求 | 收集补充内容，更新文档后再次进入确认点 |
| 跳过此阶段 | 在 Issue 评论记录 `spec=skipped`，直接进入 Step 3.2 |

### Step 3.2：技术方案

- Step 3.2.1：读取 `design-spec/SKILL.md`
- Step 3.2.2：从学城读取已上传的 demand-spec.md
- Step 3.2.3：使用 `design-spec skill` 生成 tech-design.md，然后立即通过 `citadel` / `km-doc-tools` 上传学城，记录学城链接
- Step 3.2.4：完成技术方案后，**进入人类确认点**，确认问题为：
  > 技术方案是否合理？（确认继续 / 修改后重新生成 / 补充更多 / 跳过此阶段）

确认结果处理：

| 人类选择 | 动作 |
|----------|------|
| 确认，继续任务拆解 | 在 Issue 评论记录 `design=completed` + 贴 tech-design.md 学城链接，进入 Step 3.3 |
| 修改后重新生成 | 按反馈修改文档，重新生成后再次进入确认点 |
| 补充更多 | 收集补充内容，更新文档后再次进入确认点 |
| 跳过此阶段 | 在 Issue 评论记录 `design=skipped`，直接进入 Step 3.3 |

### Step 3.3：任务拆解

- Step 3.3.1：读取 `design-spec/SKILL.md`
- Step 3.3.2：从学城读取已上传的 tech-design.md
- Step 3.3.3：使用 `design-spec skill` 生成 dev-tasks.md，然后立即通过 `citadel` / `km-doc-tools` 上传学城，记录学城链接

### Step 3.4：执行确认单

在 Issue 评论里输出确认单（这是离开阶段三的唯一凭证），标题为「📋 需求分析与技术方案设计执行确认单」，逐项列出：

- 需求规格说明：<demand-spec.md 学城链接>
- 技术方案设计：<tech-design.md 学城链接>
- 任务清单详情：<dev-tasks.md 学城链接>

并注明：当前阶段已完成，下一阶段进入 Stage4（物料组件和页面协议开发）。

随后进入**最终人类确认点**：
> 需求分析和方案设计是否已完成？（确认继续 / 修改后重新生成 / 补充更多 / 跳过此阶段）

---

## 人类确认点处理（替代原 AskQuestion 强制暂停）

> 原版用 `AskQuestion` 工具弹窗暂停。Multica 里没有弹窗——改为**通过 Issue 状态把决策权交还人类，由队长协调**。

每到一个确认点，执行以下动作而**不是**直接往下走：

1. 把**本阶段子 Issue 的 status 改为 `Blocked`**（CLI：`multica issue update <issue-id> --status blocked`）。
2. 在 Issue 评论里贴出待确认的产物链接，并用真实 mention markdown `@reporter`（人类提单人）清楚列出选项。评论示例：先 `@<reporter>` 告知需求规格已生成、附上 demand-spec.md 链接，再给出四个选项供选择：① 确认继续、② 修改后重生成、③ 补充需求、④ 跳过本阶段。
3. **停下来**，不再继续后续 Step。人类在评论里回复后，你会被自动唤醒：把子 Issue 状态从 `Blocked` 改回 `In Progress`，再按其选择执行上表对应动作。

🟡 软阻塞时（方案有可选项）可在上抛时标注推荐默认项；🔴 硬阻塞（PRD 失效、无法生成）必须停并明确说明原因。

---

## 收尾协议 ⭐ 关键改动

> 这是本阶段与原版唯一的"机制级"差异：原版往 workflow-context.json 写 `status=completed`、跑 report-stage.js 写 `reported_at`；
> Multica 版改为"更新 Issue status + 评论留痕 + 唤醒队长"，并**保留 yooz 上报**。

阶段全部 Step 完成且最终确认点通过后，**必须依次做完以下四件事，缺一不可**：

1. **贴产物**：在本阶段子 Issue 评论里贴齐三份文档的**学城链接**（三份文档已在各 Step 生成后即时上传），这是队长判定“可标 Done”的依据——**没有学城链接，队长不会推进下一阶段**。

2. **保留 yooz 上报**：在本地执行 `node {fe-rd-workflow}/scripts/report-stage.js --stage stage3`（底座不变，本地环境跑得通；失败静默不阻塞）。

3. **发进展更新唤醒队长**：在 Issue 里发一条**不带任何 `@mention`** 的进展更新评论，例如“✅ Stage3 需求分析与技术方案设计已完成，三份产物链接见上，yooz 已上报，请推进 Stage4”。
> 原理：Multica 规则下，成员发不带 `@` 的进展更新会**自动唤醒队长**重新评估并推进下一阶段。

4. **不要自己改子 Issue 为 Done**：Done 由队长在校验产物后流转，保证"状态不可被执行者伪造"。

---

## 异常处理（与原版一致）

| 场景 | 处理方式 |
|------|----------|
| PRD 链接无效 | 转 Blocked，@reporter 索取正确链接或直接粘贴需求 |
| 视觉稿无法解析 | 跳过视觉稿分析，基于文字描述继续 |
| 复杂度边界模糊 | 上抛人类确认，推荐保守评级（偏高一级） |
| 接口文档缺失 | 基于需求分析推断接口，标注「待确认」 |
| 现有代码不熟悉 | 通过代码检索了解现有实现 |
| 技术选型有争议 | 上抛人类，呈现选项对比由人类决定（🟡 软阻塞） |
