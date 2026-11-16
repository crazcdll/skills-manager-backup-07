---
name: fe-rd-workflow-multica
version: 1.0.0
description: 在 Multica 平台一键搭建前端研发 7 阶段全流程编排（Squad + 队长 + 7 个阶段 Agent）。通过 AskQuestion 收集运行时、后缀、Squad 名称等参数后执行 setup-squad.sh 完成创建。

metadata:
  skillhub.creator: "renrunbin"
  skillhub.updater: "renrunbin"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "95763"
  skillhub.high_sensitive: "false"
---

# FE-RD-Workflow Multica 一键建队

> **功能**：在 Multica 平台创建一个完整的前端研发流程小队，包含 1 个队长 Agent + 7 个阶段 Agent，各自挂载对应 SKILL.md。
> **依赖**：multica CLI 已安装并登录、jq 已安装。

## 执行流程

### Step 1：前置检查

确认 multica CLI 和 jq 已安装。若未安装则尝试自行安装：

- multica CLI：`bash -c "$(curl -sL https://s3plus.sankuai.com/multica/releases/download/install.sh)"`
- jq：`brew install jq`（macOS）

安装完成后验证 `multica --version` 和 `jq --version` 均可正常输出。若安装失败则告知用户手动安装。

### Step 2：获取可用运行时

执行 `multica runtime list --output json`，用 jq 解析出所有运行时的 name 字段，构建选项列表。若获取失败或列表为空，提示用户先注册运行时。

### Step 3：收集用户参数

通过 AskQuestion 一次性收集以下参数：

| 参数 | 类型 | 是否必填 | 说明 |
|------|------|----------|------|
| 运行时 | 单选 | 必填 | 从 Step 2 获取的运行时列表中选择，Agent 绑定的执行环境 |
| Agent 名称后缀 | 文本 | 必填 | 追加到队长和每个阶段 Agent 名后（如填 v2 则 fe-rd-orchestrator-v2、stage1-env-check-v2、…） |
| Squad 名称 | 文本 | 必填 | 小队名称 |

### Step 4：确认参数

将收集到的参数汇总展示给用户确认，格式如下：

- Squad 名称：{squad_name}
- 运行时：{runtime}
- Agent 后缀：{suffix}
- 将创建的 Agent：fe-rd-orchestrator-{suffix}、stage1-env-check-{suffix}、stage2-repo-init-{suffix}、…、stage7-feedback-{suffix}

等用户确认后再执行。

### Step 5：执行建队脚本

根据收集的参数拼接命令行参数，执行 setup-squad.sh：

`bash {SKILL_DIR}/scripts/setup-squad.sh --runtime {runtime} --agent-suffix {suffix} --squad-name {squad_name}`

观察脚本输出，若出错则把错误信息反馈给用户。

### Step 6：结果汇报

脚本执行成功后，汇总输出给用户：

- Squad ID 和名称
- 队长 Agent 名称
- 7 个阶段 Agent 名称及绑定的运行时
- 下一步操作提示：创建 Multica Project 并派活队长即可启动流程
