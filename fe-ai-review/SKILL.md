---
name: fe-ai-review
description: 通用前端代码审查 skill。面向 working tree、staged、commit、branch diff 执行结构化 CR，按通用规则、交易规则和技术栈经验规则输出审查结论；可选将发现项评论到对应 PR。当用户要求代码审查、CR、review xx、提交前检查、push 前检查、review 本地变更、Review PR、PR 审查时使用。

metadata:
  skillhub.creator: "lidingcheng"
  skillhub.updater: "lidingcheng"
  skillhub.version: "V13"
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

## 一、任务目标

- 理解用户指定范围的代码变更，协同用户完成不同类型的 Code Review
- 默认在会话内输出报告；用户要求存档或落盘时写入 Markdown 文件
- 加载规则等资产分三条并行线按需取用：**审查规则**（`base -> stack`，优先远程同步、失败回退本地兜底）、**附加能力模块**（依赖升级扫描 / MSI API 核对，固定本地路径）、**context**（技术栈背景知识，固定本地路径按需补读），详见「五、能力地图」

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

本 skill 按“模式”组织流程。当前提供两种模式，两者共享同一套审查规则与报告模板，差异只在代码来源即上下文获取方式上：

- **本地模式（默认）**。适用于在本地 git 仓库内 review 变更（`staged / working_tree / commit / branch`），可选把报告评论到对应 PR。完整流程见 [`references/modes/local.md`](references/modes/local.md)。
- **PR-only 模式**。适用于本地无对应仓库的场景，基于 PR 远程 diff + （如可用）code-repo-search 远程上下文完成审查。完整流程见 [`references/modes/pr-only.md`](references/modes/pr-only.md)。

### 路由判定

用户已明确表达模式偏好（如"走本地模式""只用 PR 远程审"）时按其偏好执行；否则：

- **本地有 PR 对应仓库** → 走本地模式；如有 PR 链接，Step 7 把发现项评论到对应 PR
- **本地没有 PR 对应仓库** → 走 PR-only 模式，准备信息中会告知"已自动切换"

> "本地有 PR 对应仓库"：当前目录是 git 仓库，且 `git remote origin` 与 PR 仓库一致。
> 仅提供 PR 链接而无本地变更时，也走 PR-only 模式（本地无可审查基准）。

### Stage 心智模型

CR 流程在心智上分为三个 Stage，**模式差异只发生在 Stage 1**，Stage 2/3 全部模式共用：

| Stage | 职责 | 模式差异 | 当前 Step |
|---|---|---|---|
| **Stage 1 上下文准备** | 输入采集、变更范围确定、技术栈识别、规则加载、产出准备信息 | **强相关**（决定模式选择的边界） | Step 0 / Step 1 / Step 2 |
| **Stage 2 执行审查** | 拿到「代码 + 规则」后做四层审查 | 无（不再关心代码来源） | Step 3 |
| **Stage 3 输出与复检** | subagent 复查、组织发现项、产出报告、可选落地到 PR | 无 | Step 4 / Step 5 / Step 6 / Step 7 |

两种模式各自承载完整 Step 0~7，详见各模式文档内的「执行流程概览」。新增模式时按 Stage 1 / 2 / 3 切片思考。

> TODO：Stage 2/3 内容稳定后，抽出 `references/stages/` 共享层，避免两份模式文档重复维护。

## 五、能力地图

本 skill 沉淀了以下能力资产，供本 skill 各模式及上游流程按需取用。

### 输出规范
- 报告结构 + 自检 + 输出风格：[`references/output.md`](references/output.md)
- 完整报告模板：[`references/tpl-report.md`](references/tpl-report.md)

### 审查规则

审查规则条目必须先尝试从远程规则仓库同步，拉取失败时回退到本 skill 自带的兜底副本。详细步骤见 [`references/rules-loading.md`](references/rules-loading.md)，下列路径均相对于该文件确定的读取根目录。

基础规则（每次必读）：
- 通用规则：`base/general-rules.md`
- 交易规则：`base/trade-rules.md`

技术栈规则（按识别到的技术栈选择加载）：
- MRN：`stack/mrn-rules.md`
- Max：`stack/max-rules.md`
- 小程序：`stack/miniprogram-rules.md`
- DUO：`stack/duo-rules.md`

### 附加能力模块（按需执行）

本身是 subagent 执行流程说明，与 Step 3 编排逻辑强耦合，不参与规则仓库同步：
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
