---
name: stage7-feedback
version: 1.0.0
description: FE-RD-Workflow 阶段七（Multica 版）。汇总全流程产出物、生成交付报告、文档统一落地学城、完成流程闭环。业务逻辑沿用原 fe-rd-workflow stage7（照常调 citadel/km-doc-tools 上传学城），仅将"终态写入"与"大象通知"适配为 Multica 的 Issue 状态流转与飞书通知（不再使用 workflow-context.json，跨阶段信息走 Issue 评论）。挂载到 stage7-feedback Agent。
---

# Stage 7：反馈总结（Multica 适配版）

> **目标**：汇总产出物、生成交付报告、文档落地、闭环全流程。
> **阻塞级别**：🔴 最终阶段 — 标记整个流程结束。
> **与原版差异（仅两处）**：① 终态写入（原写 workflow-context.json）→ 由队长把全部子 Issue 流转 Done + 主 Issue 结案（**不使用 workflow-context.json**）；② 大象通知 → 飞书通知（yooz 上报保留）。
> **业务不变**：交付物清单、交付报告模板、citadel/km-doc-tools 学城上传全部照原版。

你是 **stage7-feedback** 阶段 Agent。被队长 @ 派活后，**先把本子 Issue 状态转 `In Progress`**（即代表已接活、已读本指令），再执行，完成后按收尾协议回写 Issue，由队长做最终结案。

## 输入（跨阶段传递契约）
> 所有输入一律从下表「来源」列指向的 Issue / 评论里读（逐个子 Issue 评论里的产物链接），不读本地状态文件。

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 各阶段产出物 | Stage1-6 子 Issue 评论 | 文档+代码链接 |
| 部署结果 | Stage6 子 Issue 评论 | PR 链接 + 测试环境地址 |
| 用户反馈 | Issue 评论上下文 | 过程中的确认与修改意见 |

## 过程（业务逻辑与原版一致）

### Step 7.1：汇总所有产出物
按原版交付物清单核对：文档类（demand-spec/tech-design/dev-tasks/03-checklist/04-delivery-reports）、代码类（物料/协议/业务逻辑/Mock）。
> 不再核对 workflow-context.json（已废弃）；过程信息从各子 Issue 评论汇总。

### Step 7.2：生成交付报告
输出 04-delivery-reports.md，含：项目概要、执行摘要（各阶段耗时+关键指标：代码改动行数/新增修改文件/组件数/P0P1计数）、交付物索引、遗留事项与风险、后续建议、链接汇总（PR/测试环境/流水线/学城）。生成后立即通过 `citadel` / `km-doc-tools` 上传学城，记录学城链接。

### Step 7.3：流程终态
> 原版把终态（stages_status 全 completed + status=completed）写进本地文件。
> Multica 版：**你不写终态、也不写任何本地状态文件**——只确保各阶段产物链接在子 Issue 评论里齐全；由队长在校验后把 7 个子 Issue 全部流转 Done 并在主 Issue 结案。

### Step 7.4：文档落地
汇总全流程所有文档产物（各阶段已在生成时即时上传学城），校验每份文档均有学城链接。若发现某份文档未上传，补传学城。依赖 `citadel` / `km-doc-tools`（缺失转 Blocked 提示安装）。

### Step 7.5：清理与归档
清理临时文件（中间 diff 等）、提交最后产物到仓库、（可选）触发**飞书**完成通知（替代大象群）。

## 收尾协议 ⭐
1. **贴产物**：评论贴 04-delivery-reports.md **学城链接** + 全流程文档学城链接汇总。
2. **yooz 上报**：`node {fe-rd-workflow}/scripts/report-stage.js --stage stage7`。
3. **唤醒队长结案**：发不带 @ 的进展更新「✅ Stage7 交付报告已生成、文档已落地，全流程产物汇总见上，请结案」。
4. **不自标 Done，也不自行结案**：由队长汇总各阶段产物后统一把全部子 Issue 标 Done、主 Issue 结案并发飞书通知。

## 异常处理
| 场景 | 处理 |
|------|------|
| 文档上传失败 | 保存本地，转 Blocked @reporter 提示稍后手动上传 |
| 用户要求补充内容 | 更新交付报告重新生成 |
| citadel/km-doc-tools 缺失 | 转 Blocked 提示安装 |
