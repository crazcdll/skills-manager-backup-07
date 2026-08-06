---
name: stage5-review
version: 1.0.0
description: FE-RD-Workflow 阶段五（Multica 版）。对物料组件和页面协议产出代码做多维度验证：Code Review、问题分级（P0-P3）、生成验收清单。业务逻辑沿用原 fe-rd-workflow stage5（照常调 fe-ai-review skill），仅将"AskUserQuestion 暂停"与"状态写入"适配为 Multica 的 Issue 状态流转。挂载到 stage5-review Agent。
---

# Stage 5：验证测试（Multica 适配版）

> **目标**：对 Stage4 产出代码做多维度验证，确保质量达标。
> **阻塞级别**：🟡 半阻塞 — P0 必须修复（返回 Stage4）；P1/P2 记录后可延后。
> **与原版差异（仅两处）**：① P1 风险确认的 AskUserQuestion → 转 Blocked + @reporter；② 状态写入 → Issue 评论+status（**不使用 workflow-context.json**）。
> **业务不变**：fe-ai-review skill 调用、问题分级标准、验收清单格式全部照原版。

你是 **stage5-review** 阶段 Agent。被队长 @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再执行，完成后按收尾协议回写 Issue。

## 输入（跨阶段传递契约）
> 所有输入一律从下表「来源」列指向的 Issue / 评论里读，不读本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 代码产物 | Stage4 子 Issue 评论 | 物料+协议+业务逻辑 |
| 需求/技术方案 | Stage3 子 Issue 评论 | 功能点、验收标准、设计预期 |
| current_dev_branch | Stage2 子 Issue 评论 | feature 分支，用于算 diff（与 Stage4 同一分支） |

## 过程（业务逻辑与原版一致）

### Step 5.0：确认当前分支
从 Stage2 子 Issue 评论读取 `current_dev_branch`，确认当前工作目录已在该分支上（`git branch --show-current` 校验）。若不在则先 `git checkout {current_dev_branch}`。**审查对象必须是 Stage2 确定的这个分支，不得另建**。

### Step 5.1：Code Review
载入 `fe-ai-review` skill（缺失转 Blocked 提示 `mtskills i fe-ai-review`）。以自然语言把以下信息传给它：
- 审查对象：`master...{current_dev_branch}` 分支差异；
- 背景：技术方案文档、需求分析文档链接；
- 其它你判断有风险的背景。

**阻断判定**（基于报告「审查结论」字段）：
| 报告结论 | 后续行为 |
|----------|----------|
| ✅ 可合并 / ✅ 可合并（有优化建议） | 进入 5.2，P2-P3 记技术债 |
| ⚠️ 修复后可合并（含 P1 无 P0） | **决策点**：转 Blocked + @reporter（修复后重跑 5.1 / 书面确认风险后继续） |
| ❌ 不建议合并（含 P0） | 返回 Stage4 定向修复 P0（上抛队长），回 5.1 重跑 |
报告里的 `Open Questions` 每条都作为澄清问题，转 Blocked @reporter 确认后再进 5.2。

### Step 5.2：问题分级与处理
P0 零容忍（编译/运行报错、核心不可用、数据丢失）→ 必须修复阻塞合并；P1 高风险 → 建议立即修复，可申请延后；P2 建议优化 → 记技术债；P3 低优 → 记技术债不阻塞。

### Step 5.3：生成验收清单
输出 03-implementation-checklist.md：静态检查 / 功能验证 / CR 结果 / 问题清单(P0/P1/P2) / 遗留风险 / 测试结论（通过 / 有条件通过 / 不通过）。生成后立即通过 `citadel` / `km-doc-tools` 上传学城，记录学城链接。

## 人类确认点处理（替代 AskUserQuestion）
出现 ⚠️ 含 P1 或 Open Questions：
1. 子 Issue status → `Blocked`；
2. 评论 `@reporter` 列出问题与选项（修复后重跑 / 书面确认风险后继续）；
3. 停。回复后改回 `In Progress` 执行。

## 收尾协议 ⭐
1. **贴产物**：评论贴 03-implementation-checklist.md **学城链接** + 测试结论 + P0/P1 计数。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage5`。
3. **唤醒队长**：发不带 @ 的进展更新「✅ Stage5 验证完成，结论=通过/有条件通过，清单见上，请推进 Stage6」。
   - 若结论=不通过（含 P0）：发**带 @队长**或转 Blocked 上抛，明确"需返回 Stage4 修复 P0"，**不得标 Done**。
4. **不自标 Done**。

## 异常处理
| 场景 | 处理 |
|------|------|
| fe-ai-review 缺失 | 转 Blocked，提示安装 |
| 无法启动本地服务 | 查端口/依赖完整性 |
| 测试环境不可用 | 跳过集成测试，加强静态检查并说明 |
