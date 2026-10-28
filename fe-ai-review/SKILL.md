---
name: fe-ai-review
description: 通用前端代码审查 skill。依赖 mt-code-standards-setup 同步有效编码规范。面向 working tree、staged、commit、branch diff 或 PR 执行结构化 CR；可选将发现项评论到对应 PR。当用户要求代码审查、CR、review xx、提交前检查、push 前检查、review本地变更、Review PR、PR 审查时使用。

metadata:
  skillhub.creator: "lidingcheng"
  skillhub.updater: "lidingcheng"
  skillhub.version: "V23"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "39902"
  skillhub.high_sensitive: "false"
---

# 通用前端 AI CodeReview

## 版本自检

在执行其它任务前，先检查 skill 是否有更新：

```bash
bash <fe_skill_dir>/scripts/self-update.sh
```

`<fe_skill_dir>` 是本 Skill 的安装目录（SKILL.md 所在目录），根据实际安装路径替换。

脚本始终 exit 0，不阻塞后续流程。无论结果如何，只用一行输出说明发生了什么（更新成功、更新失败、跳过原因等）。输出 `开发目录，跳过自动更新` 是正常情况，直接继续。

## AI-Quality-CR-Agent 兼容

受 `ai-quality-cr-agent` 委托时：

- **审查流程**仍按本 Skill 执行，包括平台规则同步。
- **交付结果**按上层交接约定提供发现项、待确认问题、审查范围、覆盖边界及 `rule_bundle` / `rule_sources`；除非明确要求，不额外按 `tpl-report.md` 渲染完整前端报告。
- **最终报告、上层上报和 PR 评论**由 `ai-quality-cr-agent` 统一处理，前端不重复发布或评论。
- **独立运行**时按 Step 8 上报 CR 看板；受上层委托时跳过本 Skill 的上报，由 `ai-quality-cr-agent` 统一发布。

否则沿用本 skill 的默认输出、评论和上报策略。

## 一、任务目标

- 理解用户指定范围的代码变更，协同用户完成不同类型的 Code Review
- 默认在会话内输出报告；用户要求存档或落盘时写入 Markdown 文件
- 使用 `mt-code-standards-setup` 同步的规则包审查变更；需要依赖升级、MSI 或框架背景时按能力地图读取对应资产

## 二、核心原则

1. 默认 `lint / 类型检查 / 基础格式化` 已通过。如果发现大量存在 lint 问题，可以自行合并风格问题的输出，避免逐条刷屏。
2. 审查重心放在静态工具难以稳定发现的问题：逻辑、契约、空值与边界、异常流、并发时序、生命周期、副作用清理、上下游影响、回归风险、敏感字段和 mock 遗留。
3. 审查对象是“当前变更集”，但不能只读 diff。遇到关键逻辑、公共方法、上下游契约时，必须补充阅读完整上下文后再下结论。
4. 候选问题按 [`references/severity.md`](references/severity.md) 补证、定级和分流；覆盖缺口记录为未验证，待确认问题沿用 `Open Questions` 标识。
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
- **PR-only 模式**：以 PR diff 确定范围，按需准备匹配 commit 的仓库补读上下文；无仓库也继续尝试同步规则。审查 PR 且当前无匹配仓库，或用户指定 PR-only 时读取 [`references/modes/pr-only.md`](references/modes/pr-only.md)。

### 路由判定

用户明确指定本地审查范围时，附带 PR 链接不改变范围。明确要求仅使用远程证据时走 PR-only，跳过业务仓库准备与读取，仍同步平台规则。其余按模式偏好和环境选择：

- **本地有 PR 对应仓库** → 走本地模式；如有 PR 链接，Step 7 把发现项评论到对应 PR
- **当前无匹配仓库，或用户明确要求 PR-only** → 按 PR-only Step 0 准备仓库；已有路径可从用户、上游或当前环境获取。

> 匹配 checkout：Git `origin` 包含 PR 的 `{org}/{repo}`。

### Stage 心智模型

CR 流程在心智上分为三个 Stage，**模式差异只发生在 Stage 1**，Stage 2/3 全部模式共用：

| Stage | 职责 | 模式差异 | 当前 Step |
|---|---|---|---|
| **Stage 1 上下文准备** | 输入采集、变更范围确定、技术栈识别、平台规则同步与读取、产出准备信息 | **强相关**（决定模式选择与匹配 checkout 的边界） | Step 0 / Step 1 / Step 2 |
| **Stage 2 执行审查** | 拿到「代码 + 规则」后做四层审查 | 无（不再关心代码来源） | Step 3 |
| **Stage 3 输出与复检** | subagent 复查、组织发现项、产出报告、可选落地到 PR | 无 | Step 4 / Step 5 / Step 6 / Step 7 / Step 8 |

两种模式各自承载完整 Step 0~8，详见各模式文档内的「执行流程概览」。

## 五、能力地图

本 skill 沉淀了以下能力资产，供本 skill 各模式及上游流程按需取用。

### 输出规范
- 主审分析候选问题及最终定级前：读取 [`references/severity.md`](references/severity.md)，核对影响、证据和人工注意点准入。
- 报告结构 + 自检 + 输出风格：[`references/output.md`](references/output.md)
- 完整报告模板：[`references/tpl-report.md`](references/tpl-report.md)

### 平台编码规范

`mt-code-standards-setup` 是必需依赖。进入任一模式的 Step 2 时，先读取 [`references/rules-loading.md`](references/rules-loading.md)，再加载该依赖并使用加载结果返回的安装目录 `<setup_skill_dir>` 定位官方 Runner；执行前检查文件存在，不从本 Skill 目录寻找 Runner。首次调用明确传入 `--domain frontend --stage cr`，1024 / CatPaw Studio 及其子 Agent 使用 `--execution-agent agent_1024`。校验新版 receipt、manifest 和受管文件后，实际读取适用规则正文，保留读取记录与规则来源。

### 技术栈识别

确定变更范围后，读取 [`references/stack-detection.md`](references/stack-detection.md) 识别技术栈；PR-only 可使用远程证据及匹配审查 commit 的仓库快照。

### 附加能力模块（按需执行）

在 Step 3 命中对应场景时读取：
- 依赖升级扫描：[`references/rules/base/dep-upgrade-rules.md`](references/rules/base/dep-upgrade-rules.md)（diff 含 package.json 组件版本变化时，由 subagent 并行执行）
- MSI API 契约核对：[`references/rules/base/msi-api-review-rules.md`](references/rules/base/msi-api-review-rules.md)（diff 实质修改 MSI Bridge 调用时，由 subagent 并行执行）

技术栈上下文：

- MRN：需要理解框架行为时，读取 [MRN context](references/context/mrn-context.md)。
- Max：需要理解框架行为时，读取 [Max context](references/context/max-context.md)。
- DUO：识别到该技术栈时，读取 [DUO context](references/context/duo-context.md)。

### MCM 变更同步参考

CR 过程中收集的信息可自动提取为 MCM 变更同步模板的参考内容，减少人工填写工作量。

- 触发条件：用户提及 MCM
- 模板位置：[`references/tpl-report.md`](references/tpl-report.md) 中的「MCM 参考信息」章节
- 参考规范：[交易前端 MCM 变更同步模板](https://km.sankuai.com/collabpage/2752829563)

### PR 评论落地

当报告需要评论到对应 PR 时使用此能力，仅在仓库一致性校验通过后启用。

- 触发条件：用户给出 PR 链接，或明确要求「评论到 PR / 发到 PR」
- 策略：P0 / P1 逐条行内评论；重要且值得人工核实的待确认项额外最多 3 条行内评论，不占用缺陷评论名额。其余待确认项、已评论项索引、P2/P3 和整体结论并入全局摘要，详见评论指引。
- 失败降级：按评论指引处理鉴权失败、重试和结果核验，不阻塞报告产出
- 工具脚本（随 skill 自带，无需额外安装）：
  - [`scripts/pr-comment/cr-comment.sh`](scripts/pr-comment/cr-comment.sh)：行内 / 全局 / 验证 / 删除
  - [`scripts/pr-comment/code_cli.py`](scripts/pr-comment/code_cli.py)：底层 MCode API 调用
- 详细执行步骤、命令参数与评论模板：[`references/pr-comment.md`](references/pr-comment.md)

### 上报看板

独立运行且用户未要求跳过时，把 CR 完成结果上报到美团 AI CR 看板；受上层委托时交付标准化结果，不重复上报。

- 触发条件：Step 6 报告产出后默认自动执行，组装 payload 并运行脚本。
- 跳过：用户显式说「不要上报」「不上报看板」
- 详细字段解析、枚举映射、payload 组装说明：[`references/report-submit.md`](references/report-submit.md)
- 工具脚本：[`scripts/report-submit.sh`](scripts/report-submit.sh)
---

## 六、禁止事项

- 不要默认全仓扫读无关历史
- 不要逐条罗列纯格式问题
- 不要在证据不足时给确定性结论
