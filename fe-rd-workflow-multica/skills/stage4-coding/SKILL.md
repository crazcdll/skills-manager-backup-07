---
name: stage4-coding
version: 1.0.0
description: FE-RD-Workflow 阶段四（Multica 版）。按技术方案和任务清单完成物料组件开发、页面协议开发与业务逻辑实现。业务逻辑沿用原 fe-rd-workflow stage4（照常调 max-material-dev / duo-protocol skill、duo publish-procode 发布），仅将"状态写入"适配为 Multica 的 Issue 状态流转，P0 阻塞改为转 Blocked + @reporter。挂载到 stage4-coding Agent。
---

# Stage 4：物料组件与页面协议开发（Multica 适配版）

> **目标**：按技术方案和任务清单完成物料组件、页面协议、业务逻辑开发。
> **阻塞级别**：🔴 阻塞 — 开发问题在本阶段修复；无法修复转 Blocked 上抛队长。
> **与原版差异（仅一处）**：状态写入从本地文件改为 Issue 评论+status（**不使用 workflow-context.json**）；P0 卡点转 Blocked + @reporter。
> **底座/业务不变**：先物料后协议的顺序、max-material-dev / duo-protocol skill 调用、duo publish-procode 发布全部照原版。

你是 **stage4-coding** 阶段 Agent。被队长 @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再执行，完成后按收尾协议回写 Issue。

## 入场门禁
执行前在 Issue 评论逐条确认（缺一不得继续）：

- ☐ 已从 Stage2 子 Issue 评论读取 `current_dev_branch`，并已切换到该分支（**禁止另建新分支**）
- ☐ 已读取 Stage3 产物（tech-design.md / dev-tasks.md 学城链接）
- ☐ 已判断需求类型：A直接开发 / B完整流程 / P发布 / T测试，并写明依据
- ☐ 将先开发物料组件、再开发页面协议，顺序不变

## 输入（跨阶段传递契约）
> 所有输入一律从下表「来源」列指向的 Issue / 评论里读，不读本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 技术方案 | Stage3 子 Issue 评论 | tech-design.md 链接 |
| 开发任务 | Stage3 子 Issue 评论 | dev-tasks.md 链接 |
| current_dev_branch | Stage2 子 Issue 评论 | 开发所在 feature 分支 |
| 物料 skill | 本地 | `max-material-dev` |
| 协议 skill | 本地 | `duo-protocol` |

## 过程（业务逻辑与原版一致，顺序不可变）

### Step 4.0：切换到开发分支
执行 `git checkout {current_dev_branch}` 切换到 Stage2 已创建的 feature 分支。若本地不存在则 `git checkout -b {current_dev_branch} origin/{current_dev_branch}` 拉取远程分支。**严禁自行创建新分支**，所有开发必须在此分支上进行。

### Step 4.1：物料组件开发与发布
1. **先读 `max-material-dev/SKILL.md`**（禁止用 summary/历史上下文替代 read，未读完不得动手）。
2. 输出「物料组件开发 Skill 声明」，列出已读 skill 路径。
3. **4.1.1 开发**：完全遵循 `max-material-dev` 规范，覆盖所有开发任务，不跳过；验证也在本阶段完成。
4. **4.1.2 发布**（条件触发）：新增物料 / description.json 修改时**必须**发布；其他情况提醒用户自行决定。
   - 更新 `package.json` 版本号（semver）→ 读 max-material-dev 发布规范 → `duo publish-procode -y`。
   - 依赖 `duo-cli`，缺失时转 Blocked 提示安装。

### Step 4.2：页面协议开发
1. **先读 `duo-protocol/SKILL.md`**（同样禁止 summary 替代 read）。
2. 输出「协议开发 Skill 声明」。
3. 完全遵循 `duo-protocol` 规范开发，覆盖所有任务，不跳过、不自行实现。

## 收尾协议 ⭐
1. **贴产物**：评论贴物料源码路径（material/packages/*/src/）、DUO 协议文件路径（protocol/）、业务代码路径（src/）、发布版本号（如有）。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage4`。
3. **唤醒队长**：发不带 @ 的进展更新「✅ Stage4 物料与协议开发完成，产物见上，请推进 Stage5」。
4. **不自标 Done**。

## 人类确认点 / 异常处理
| 场景 | 处理 |
|------|------|
| duo-cli 缺失（需发布） | 转 Blocked，@reporter 提示 `npm i -g @meishi/duo-cli` |
| 开发任务存在歧义 | 转 Blocked，@reporter 上抛澄清（🟡 软阻塞，可附推荐方案） |
| 物料/协议开发失败无法自修复 | 转 Blocked，记 failed，@reporter 上抛，严禁标 Done |
