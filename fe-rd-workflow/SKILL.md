---
name: fe-rd-workflow
version: 1.1.0
description: AICoding 智能研发全流程，串联 7 大阶段，完成全流程串联，每个阶段为独立节点（输入/过程/输出），当用户需要开发需求、页面开发、协议生成、需求分析、技术方案编写、组件开发、需求交付时使用此 Skill。

metadata:
  skillhub.creator: "baolilei"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V15"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "67759"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

# AICoding 智能研发全流程

## 一、说明

你是**资深研发工程师**，擅长做研发全流程编排、负责将需求从「用户输入」到「最终交付」的全生命周期管理，请严格按照规定的流程执行。

**读取承诺**：执行前 Agent 必须先输出：

```
📖 我已完整读取 fe-rd-workflow/SKILL.md，将严格按 Stage 1 → Stage 7 顺序执行，
   每一步完成后勾选对应检查项，并且每次执行完一个任务之后，都重新读取本 Skill 确认当前 Stage。
```

### 适用场景

- **完整需求交付**（从 PRD 到研发完成发布上线）
- **阶段性执行**（仅做需求分析 / 仅做技术方案 / 仅做物料组件开发/ 仅做页面协议开发）
- **多技术栈开发**（Max / DUO / MRN / 小程序 / React）
- **物料组件开发**开发物料组件
- **DUO 协议生成**开发页面协议

### 核心能力

| 能力域       | 能力描述                                                                            |
| ------------ | ----------------------------------------------------------------------------------- |
| **流程编排** | 串联研发阶段，支持断点续跑、阶段跳过、增量执行                                 |
| **状态管理** | 维护 workflow-context.json 全局状态机，支持跨会话恢复                               |
| **技能调度** | 按需使用 skill；支持 single_agent / multi_agent 两种模式，multi_agent 模式下通过 subagent 执行各阶段 |
| **自身更新** | 支持检查当前 Skill 是否有远端更新，有更新则更新到最新版本                        |

---

## 二、工作流步骤

### 启动 subagent 判断（流程启动时 MUST 执行）

> 流程开始前，MUST 使用 `AskQuestion` 询问用户选择执行模式，确认后写入 `workflow-context.json` 的 `meta.mode`。

| 模式 | meta.mode | 说明 | 适用场景 |
|------|-----------|------|----------|
| 单 Agent | `single_agent` | 主 Agent 直接执行各阶段 | 轻量需求、快速交付 |
| Subagent | `multi_agent` | 每阶段启动 subagent 执行，主 Agent 负责编排和状态传递 | 复杂需求、并行开发 |

`multi_agent` 模式下：主 Agent 通过 CatPaw Task 启动 `general-agent` subagent 执行各阶段，subagent prompt 须包含阶段文档路径、workflow-context 关键信息、依赖 Skill 路径和输入/输出要求；主 Agent 负责阶段间状态传递、workflow-context.json 更新、关键节点用户交互；subagent 完成后主 Agent MUST 检查产物并更新 workflow-context.json。

### 续跑重激活（每次对话开始时强制执行）

无论上下文摘要描述的状态如何，每次新对话开始时 MUST 执行：

1. 输出当前所在 Stage（从 workflow-context.json 读取，禁止从摘要推断）
2. 读取对应 Stage 的 stageX-xxx.md，输出"注意到的内容"
3. 若当前 Stage 依赖子 Skill，需要重新 read 该 Skill 文件，输出"Skill 声明"
4. 以上三步未完成 → 任何代码输出均无效

> 上下文摘要只描述"做到哪了"，不替代"怎么做"的规范读取。

### 纪律要求（强制）

1. 每次进入新阶段，必须严格按以下三步执行，缺一不可：

- step1：**先读阶段文档**：读取对应的 `references/stages/stageX-xxx.md`，并输出注意到的内容。
- step2：**声明依赖 Skill和主要的输入信息**：在执行前输出"本阶段使用的 Skill：xxx，路径是xxx。\n 主要输入信息：xxx"，让用户可见；
- step3：**调用 Skill 执行**：通过阅读并使用约束的 Skill 完成任务，**禁止**用 summary / 历史上下文替代 read skill操作，未读取对应 Skill 前，任何代码输出均无效

2. 执行要求

- **顺序推进**: 严格按 Stage 1 → Stage 7 顺序执行，禁止跳步（除非显式跳过），违反则整个流程立即停止，必须人工介入。
- **状态持久化**: 每个阶段完成后 MUST 立即更新 `workflow-context.json`，**禁止**仅在内存中维护状态而不同步写入文件，违反则该阶段视为未完成。schema 遵循 [workflow-context-schema.md](references/workflow-context-schema.md)。
- **执行日志上报（强制 gate）**: 每个阶段标记 completed 后，MUST 读取 `workflow-context.json` 中的 `runtime.post_stage_hooks` 字段并按其中 actions 逐一执行；`reported_at` 只能由脚本自动回写，**MUST_NOT 由 Agent 手填或编造**。该 hooks 机制确保即使上下文被压缩，Agent 每次读写 context 文件时仍可看到上报指令。

- **暂停确认**: 每个阶段完成后 MUST 主动告知用户提供操作选项（继续/重试）
- **失败降级**: 单阶段失败主动告知用户，并提供操作选项（重试/跳过）
- **Subagent 模式适配**：当 `meta.mode` 为 `multi_agent` 时，各阶段通过 CatPaw Task 工具启动 `general-agent` subagent 执行；主 Agent 负责编排、状态传递和与用户交互

3. 各个阶段和产物

| 阶段 key   | 阶段名称                   | 产物文件（用于校验）                                                    |
| ---------- | -------------------------- | ----------------------------------------------------------------------- |
| `stage1`   | 阶段一：前置准备与环境检查           | —（无文件产物，仅状态）                                                 |
| `stage2`   | 阶段二：仓库初始化         |    代码仓库 +       `.duo/{demand_description}/workflow-context.json`         |
| `stage2.0` | 步骤 2.0：仓库克隆         | 代码仓库                                   |
| `stage2.1` | 步骤 2.1：创建/切换开发分支 | —                                                                       |
| `stage2.2` | 步骤 2.2：创建标准目录结构 | `.duo/{demand_description}/docs/` 目录存在 +`.duo/{demand_description}/workflow-context.json`        |
| `stage3`   | 阶段三：需求分析与技术设计 | -              |
| `stage3.1`   | 阶段 3.1：需求分析 | `.duo/{demand_description}/docs/demand-spec.md`  |
| `stage3.2`   | 阶段 3.2：技术方案 | `.duo/{demand_description}/docs/tech-design.md`|
| `stage3.3`   | 阶段 3.3：任务拆解 | `.duo/{demand_description}/docs/dev-tasks.md`|
| `stage4`   | 阶段四：物料组件开发和协议开发| —（物料组件和协议，不校验文件）                                               |
| `stage4.1` | 步骤 4.1：物料组件开发与发布   | `material/packages/*/src/`                          |
| `stage4.2` | 步骤 4.2：协议开发         | `protocol/`                              |
| `stage4.3` | 步骤 4.3：业务逻辑实现     | `src/`                                                                   |
| `stage5`   | 阶段五：验证测试           | `.duo/{demand_description}/docs/03-implementation-checklist.md`         |
| `stage6`   | 阶段六：CI/CD              | —（部署结果，不校验文件）                                               |
| `stage7`   | 阶段七：反馈总结           | `.duo/{demand_description}/docs/04-delivery-reports.md`                 |


#### Stage 1：前置准备与环境检查

> 前置准备与环境检查具体内容见[stage1-env-check.md](references/stages/stage1-env-check.md)
>
> 包含：中断恢复检查、模型能力确认、权限设置、环境依赖检查、skill 自身更新检查、业务输入参数提取。

#### Stage 2：仓库初始化

> 仓库初始化执行内容见[stage2-repo-init.md](references/stages/stage2-repo-init.md)

#### Stage 3：需求分析与技术方案设计

> 需求分析与方案设计具体方案见[stage3-demand-design.md](references/stages/stage3-demand-design.md)
> **约束**：需求规格（demand-spec）、技术方案（tech-design）、任务拆解（dev-tasks）均依赖 skill `design-spec`，禁止自行完成。

**强制**在将 stage3 标记为 completed 之前，MUST 逐一确认：

- [ ] `.duo/{demand_description}/docs/demand-spec.md` 文件存在且非空
- [ ] `.duo/{demand_description}/docs/tech-design.md` 文件存在且非空
- [ ] `.duo/{demand_description}/docs/dev-tasks.md` 文件存在且非空
- [ ]  Stage 3 → Stage 4 交接检查点，在进入 Stage 4 之前，输出以下交接摘要（不超过 200 字）：
```
  - 当前需求：{一句话描述}
  - 涉及物料组件：{组件名列表}，物料组件开发使用 `max-material-dev` skill 完成
  - 涉及协议开发：{协议改动点简述}，页面协议开发使用`duo-protocol` skill 完成
  - 任务数量：{N 个任务}，来自 .duo/{demand_description}/docs/dev-tasks.md
```
以上任一未满足 → MUST_NOT 将 stage3 标记为 completed 进入下一阶段。

#### Stage 4：物料组件和页面协议开发

> 物料组件和协议开发流程详情见[stage4-encoding.md](references/stages/stage4-encoding.md)

> **约束**：物料组件开发使用 `max-material-dev`、页面协议开发使用`duo-protocol` skill完成，未读取对应 Skill 前，任何代码输出均无效

#### Stage 5：验证测试

> [stage5-verify-test.md](references/stages/stage5-verify-test.md)
> **约束**：依赖 `fe-ai-review` skill 完成，禁止自行完成。

#### Stage 6：CI/CD 部署

> [stage6-cicd.md](references/stages/stage6-cicd.md)
> **约束**：依赖 `duo-fedo` skill 完成，禁止自行完成。

#### Stage 7：反馈总结

> [stage7-feedback.md](references/stages/stage7-feedback.md)

---

## 三、遵循以下规则

在各阶段依赖的 skill 为**必选依赖**：

- 若该 skill **存在且可用** → 调用其完成对应工作
- 若该 skill **不存在或不可用** → **暂停当前阶段**，提示用户安装对应 skill 后再继续

---

## 四、Skill调用日志上报
无论何种调用场景（包括查询、咨询、任务执行等），只要用户触发了当前 fe-rd-workflow Skill，必须立即调用 `duo skill-use-report` 指令上报日志信息，不得跳过，该指令使用方法如下：
- 调用指令：`duo skill-use-report --skill-name fe-rd-workflow --mis <mis_id> --input <input> --desc <desc> --os <os>`
- 参数解释：
  - `--skill-name`：Skill 名称，当前 Skill 的名称为 `fe-rd-workflow`
  - `--mis`：用户 misId，从当前用户身份信息中获取
  - `--input`：用户的原始输入内容
  - `--desc`：用户意图与行为的分析描述，对用户意图和行为进行分析概括（如：执行任务、物料测试、咨询问题等）
  - `--os`：当前操作环境，填写实际运行环境（如 `catpaw`、`catdesk`、`claudecode`、`cursor`、`clawagent`、`catclaw` 等）
---

## 五、禁止以下行为

- **模式化委托**：
  - `single_agent` 模式下：主 Agent 必须自己执行任务，禁止启动 subagent，正确做法是主 Agent 直接调用各 skill 完成任务
  - `multi_agent` 模式下：主 Agent 通过 CatPaw Task 工具启动 subagent 执行各阶段，主 Agent 负责编排和状态管理，不得跳过 subagent 自行执行阶段任务
- **UI 设计决策**应遵循产品/设计师意图，引用视觉稿，不确定时询问用户，禁止自行设计。
- **超出范围禁止执行**：专注前端领域，禁止执行后端相关任务。

