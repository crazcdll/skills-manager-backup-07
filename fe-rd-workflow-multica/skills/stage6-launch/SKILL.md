---
name: stage6-launch
version: 1.0.0
description: FE-RD-Workflow 阶段六（Multica 版）。代码提交、推送、创建 Draft PR、触发 CI/CD 流水线、部署测试环境并验证。业务逻辑沿用原 fe-rd-workflow stage6（照常调 ee-code 建 PR、duo-fedo/ee-fedo 跑流水线），仅将"状态写入"适配为 Multica 的 Issue 状态流转，部署失败转 Blocked + @reporter。挂载到 stage6-launch Agent。
---

# Stage 6：CI/CD 部署（Multica 适配版）

> **目标**：提交代码、创建 Draft PR、触发流水线、部署测试环境。
> **阻塞级别**：🟢 不阻塞 — 部署失败可手动重试或跳过（上抛队长由人类决定）。
> **与原版差异（仅一处）**：状态写入 → Issue 评论+status（**不使用 workflow-context.json**）；部署失败/PR 审批阻塞转 Blocked + @reporter。
> **业务不变**：git 提交规范、Draft PR（feature→master）、ee-code、duo-fedo（首选）/ee-fedo（备用）全部照原版。

你是 **stage6-launch** 阶段 Agent。被队长 @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再执行，完成后按收尾协议回写 Issue。

## 输入（跨阶段传递契约）
> 所有输入一律从下表「来源」列指向的 Issue / 评论里读，不读本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 验收通过的代码 | Stage5 子 Issue 评论 | 测试结论=通过/有条件通过 |
| 验收清单 | Stage5 子 Issue 评论 | 03-implementation-checklist.md |
| current_dev_branch | Stage2 子 Issue 评论 | feature 分支 |

## 过程（业务逻辑与原版一致）

### Step 6.0：确认当前分支
从 Stage2 子 Issue 评论读取 `current_dev_branch`，确认当前工作目录已在该分支上（`git branch --show-current` 校验）。若不在则 `git checkout {current_dev_branch}`。**提交、推送、PR 必须全部基于这个分支，不得另建**。

### Step 6.1：代码提交
在 `{project_root}` 下执行 `git add .`，然后按 Conventional Commits 规范提交：`git commit -m "feat: {需求简述} - #{ONES任务号}"`。

### Step 6.2：推送到远程
执行 `git push -u origin {current_dev_branch}` 推送（一定是 feature 分支，不是 master）。

### Step 6.3：创建 Draft PR（feature → master）
强制：Draft PR、源=current_dev_branch、目标固定 `master`。按原版 PR 模板（需求概述/改动范围/测试情况/关联任务）填写。依赖 `ee-code`（缺失转 Blocked 提示安装）。

### Step 6.4：触发 CI/CD 流水线
1. 确认 6.3 主 Draft PR 已建；
2. 若 Stage2 未走 fedo（无 task_id）：用 `duo-fedo` 创建+启动 FEDO 任务，建桥接 PR（current_dev_branch → FEDO feature），提示用户确认合并；
3. 用 `duo-fedo` 执行 FEDO 任务。依赖 `duo-fedo`（首选）/`ee-code`；`ee-fedo` 为 duo-fedo 不可用时的降级备用。

### Step 6.5：部署验证
检查：流水线构建成功 / 测试环境部署成功 / 页面可访问 / 核心功能在测试环境通过。

## 收尾协议 ⭐
1. **贴产物**：评论贴主 Draft PR 链接、桥接 PR 链接（如有）、流水线状态、测试环境预览地址。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage6`。
3. **唤醒队长**：发不带 @ 的进展更新「✅ Stage6 PR 已建+流水线已触发，链接见上，请推进 Stage7」。
4. **不自标 Done**。

## 人类确认点 / 异常处理
| 场景 | 处理 |
|------|------|
| 推送冲突 | rebase 后重试 |
| 桥接 PR 未合并 | 转 Blocked，@reporter 提示先确认合并 current_dev_branch → fedo feature |
| 流水线失败 | 查日志定位，修复后重触发；持续失败转 Blocked @reporter |
| PR 审批延迟 | 触发飞书通知提醒 Reviewer（替代群内提醒） |
| ee-code/duo-fedo 缺失 | 转 Blocked 提示安装 |
