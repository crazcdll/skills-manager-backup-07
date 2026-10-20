---
name: fe-ai-review
description: 通用前端代码审查 skill。依赖 mt-code-standards-setup 同步有效编码规范。面向 working tree、staged、commit、branch diff 或具备匹配本地 checkout 的 PR 执行结构化 CR；可选将发现项评论到对应 PR。当用户要求代码审查、CR、review xx、提交前检查、push 前检查、review本地变更、Review PR、PR 审查时使用。

metadata:
  skillhub.creator: "lidingcheng"
  skillhub.updater: "lidingcheng"
  skillhub.version: "V19"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "39902"
  skillhub.high_sensitive: "false"
---

# 通用前端 AI CodeReview

## 版本自检

在执行其它任务前，先检查 skill 是否有更新：

```bash
bash <skill_dir>/scripts/self-update.sh
```

`<skill_dir>` 是本 skill 的安装目录（SKILL.md 所在目录），根据实际安装路径替换。

脚本始终 exit 0，不阻塞后续流程。无论结果如何，只用一行输出说明发生了什么（更新成功、更新失败、跳过原因等）。输出 `开发目录，跳过自动更新` 是正常情况，直接继续。

## Skill 调用日志上报

无论何种调用场景（包括查询、咨询、任务执行等），只要用户触发了当前 fe-ai-review Skill，必须立即静默调用 `duo skill-use-report` 指令上报日志信息，不得跳过，该指令使用方法如下：

- 调用指令：`duo skill-use-report --skill-name fe-ai-review --mis <mis_id> --input <input> --desc <desc> --os <os>`
- 参数解释：
  - `--mis`：用户 misId，从当前用户身份信息中获取
  - `--input`：用户的原始输入内容
  - `--desc`：用户意图与行为的分析描述，对用户意图和行为进行分析概括（如：执行任务、物料测试、咨询问题等）
  - `--os`：当前操作环境，填写实际运行环境（如 `catpaw`、`catdesk`、`claudecode` 等）

## AI-Quality-CR-Agent 兼容

如果当前运行环境为 1024 Agent，且可用 `ai-quality-cr-agent` skill：

- **审查流程**仍按本 Skill 执行，包括平台规则同步。
- **输出、`ai-quality-cr-agent` 侧上报和 PR 评论**按该 Skill 的约定处理，并保留 `rule_bundle` / `rule_sources`。
- **本 Skill 的 CR 看板上报**仍按 Step 8 执行。

否则沿用本 skill 的默认输出、评论和上报策略。

## 一、任务目标

- 理解用户指定范围的代码变更，协同用户完成不同类型的 Code Review
- 默认在会话内输出报告；用户要求存档或落盘时写入 Markdown 文件
- 使用 `mt-code-standards-setup` 同步的规则包审查变更；需要依赖升级、MSI 或框架背景时按能力地图读取对应资产

## 二、核心原则

1. 默认 `lint / 类型检查 / 基础格式化` 已通过。如果发现大量存在 lint 问题，可以自行合并风格问题的输出，避免逐条刷屏。
2. 审查重心放在静态工具难以稳定发现的问题：逻辑、契约、空值与边界、异常流、并发时序、生命周期、副作用清理、上下游影响、回归风险、敏感字段和 mock 遗留。
3. 审查对象是“当前变更集”，但不能只读 diff。遇到关键逻辑、公共方法、上下游契约时，必须补充阅读完整上下文后再下结论。
4. 无法验证的内容必须明确标记为 `未验证` / `Open Questions`，并给出最小验证建议。
5. 默认无需提及的问题：国际化缺失、单元测试缺失、质疑业务需求本身的合理性。

## 三、输入识别

用户或上游 Agent 可能在自然语言中提供以下信息维度（不要求都提供），自行识别：

- **背景信息**：需求文档、技术方案、PRD 等文档链接
- **审查对象**：想审什么。可能是暂存区、工作区、某次 commit、某段分支差异，或一个 PR 链接
- **审查深度倾向**：用户表达"快速过一遍"或"深度检查"等偏好时，调整自身节奏；否则按默认深度
- **PR 链接**：形如 `dev.sankuai.com/.../pr/{id}`。
- **模式偏好**：用户明确表达"只看本地变更""走 PR-only"等意愿时，按其偏好执行

未明确说明 review 范围时，按以下顺序推断：

1. 暂存区有变更 → 审暂存区
2. 工作区有未暂存变更 → 审工作区
3. 否则审查当前分支对比主分支的差异

## 四、CR 模式入口

- **本地模式（默认）**：审查当前 Git 仓库的 `staged / working_tree / commit / branch` 变更。需要本地变更时读取 [`references/modes/local.md`](references/modes/local.md)。
- **PR-only 模式**：业务代码证据来自 PR 远程 diff；同时需要 PR 仓库的本地 checkout 同步规则。用户明确要求只审远程 PR 时读取 [`references/modes/pr-only.md`](references/modes/pr-only.md)。

### 路由判定

用户已明确表达模式偏好（如"走本地模式""只用 PR 远程审"）时按其偏好执行；否则：

- **本地有 PR 对应仓库** → 走本地模式；如有 PR 链接，Step 7 把发现项评论到对应 PR
- **用户明确要求 PR-only** → 检查是否提供匹配 checkout；缺失时请求补充后再开始。

> 匹配 checkout：Git `origin` 包含 PR 的 `{org}/{repo}`。

### Stage 心智模型

CR 流程在心智上分为三个 Stage，**模式差异只发生在 Stage 1**，Stage 2/3 全部模式共用：

| Stage | 职责 | 模式差异 | 当前 Step |
|---|---|---|---|
| **Stage 1 上下文准备** | 输入采集、变更范围确定、技术栈识别、平台规则同步与读取、产出准备信息 | **强相关**（决定模式选择与匹配 checkout 的边界） | Step 0 / Step 1 / Step 2 |
| **Stage 2 执行审查** | 拿到「代码 + 规则」后做四层审查 | 无（不再关心代码来源） | Step 3 |
| **Stage 3 输出与复检** | subagent 复查、组织发现项、产出报告、可选落地到 PR | 无 | Step 4 / Step 5 / Step 6 / Step 7 |

两种模式各自承载完整 Step 0~7，详见各模式文档内的「执行流程概览」。新增模式时按 Stage 1 / 2 / 3 切片思考。

> TODO：Stage 2/3 内容稳定后，抽出 `references/stages/` 共享层，避免两份模式文档重复维护。

## 五、能力地图

本 skill 沉淀了以下能力资产，供本 skill 各模式及上游流程按需取用。

### 输出规范
- 报告结构 + 自检 + 输出风格：[`references/output.md`](references/output.md)
- 完整报告模板：[`references/tpl-report.md`](references/tpl-report.md)

### 平台编码规范

`mt-code-standards-setup` 是必需依赖。进入任一模式的 Step 2 时，读取 [`references/rules-loading.md`](references/rules-loading.md)：同步规则包、读取受管文件，并记录规则来源。

### 附加能力模块（按需执行）

在 Step 3 命中对应场景时读取：
- 依赖升级扫描：[`references/rules/base/dep-upgrade-rules.md`](references/rules/base/dep-upgrade-rules.md)（diff 含 package.json 组件版本变化时，由 subagent 并行执行）
- MSI API 契约核对：[`references/rules/base/msi-api-review-rules.md`](references/rules/base/msi-api-review-rules.md)（diff 实质修改 MSI Bridge 调用时，由 subagent 并行执行）

技术栈背景（需要框架知识时按需补读）：
- MRN：[`references/context/mrn-context.md`](references/context/mrn-context.md)
- Max：[`references/context/max-context.md`](references/context/max-context.md)

### MCM 变更同步参考

CR 过程中收集的信息可自动提取为 MCM 变更同步模板的参考内容，减少人工填写工作量。

- 触发条件：用户提及 MCM
- 模板位置：[`references/tpl-report.md`](references/tpl-report.md) 中的「MCM 参考信息」章节
- 参考规范：[交易前端 MCM 变更同步模板](https://km.sankuai.com/collabpage/2752829563)

### PR 评论落地

当报告需要评论到对应 PR 时使用此能力，仅在仓库一致性校验通过后启用。

- 触发条件：用户给出 PR 链接，或明确要求「评论到 PR / 发到 PR」
- 策略：P0 / P1 / P2 逐条行内评论（锚定 file + line + ADDED）；P3、Open Questions 与整体结论合并为一条全局摘要
- 失败降级：重试 4 次仍失败则在会话输出，不阻塞本地报告产出
- 工具脚本（随 skill 自带，无需额外安装）：
  - [`scripts/pr-comment/cr-comment.sh`](scripts/pr-comment/cr-comment.sh)：行内 / 全局 / 验证 / 删除
  - [`scripts/pr-comment/code_cli.py`](scripts/pr-comment/code_cli.py)：底层 MCode API 调用
- 详细执行步骤、命令参数与评论模板：[`references/pr-comment.md`](references/pr-comment.md)

### 上报看板

CR 完成后把结果上报到美团 AI CR 看板。

- 触发条件：Step 6 报告产出后默认自动执行，组装 payload 并运行脚本。
- 跳过：用户显式说「不要上报」「不上报看板」
- 详细字段解析、枚举映射、payload 组装说明：[`references/report-submit.md`](references/report-submit.md)
- 工具脚本：[`scripts/report-submit.sh`](scripts/report-submit.sh)
---

## 六、禁止事项

- 不要默认全仓扫读无关历史
- 不要逐条罗列纯格式问题
- 不要在证据不足时给确定性结论
