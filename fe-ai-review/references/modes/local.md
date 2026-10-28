# 本地 CR 模式

> 入口路由见 `SKILL.md` 第四章「CR 模式入口」。本文承载本地模式的完整执行流程，自包含可独立加载。

## 适用范围

基于本地 git 仓库的代码变更（`staged / working_tree / commit / branch`）做结构化代码审查。

以 PR 为审查对象且当前无匹配 Git 仓库时，转 PR-only（见 Step 0.c）。明确要求本地审查但当前无 Git 仓库时，请求提供本地路径。

## 执行流程概览

```
Step 0：判定范围与可靠性
  ├── 0.a 有有效变更范围（staged / working_tree / commit / branch）→ 进入 Step 1
  ├── 0.b 无有效变更范围 → 停止并告知用户
  └── 0.c 用户提供了 PR 链接 → 仓库一致性校验；不一致默认转发 PR-only 模式（用户已明确表达「走本地」时除外）

Step 1：输出准备信息（上下文感知）
  └── 参照 tpl-report.md「准备」章节输出，存在风险时要求用户确认是否继续

Step 2：同步并读取平台规则

Step 3：执行审查
  ├── [并行] package.json 有组件升级时，subagent 执行依赖升级风险扫描（dep-upgrade-rules.md）
  ├── [并行] diff 实质修改 MSI Bridge 调用时，subagent 执行 API 契约核对（msi-api-review-rules.md）
  ├── [主线] 先看高优阻塞项（P0）再看建议项（P1 / P2-P3）
  └── 关键逻辑必须补读完整上下文，不能只读 diff

Step 4：复查与校正
  └── 候选问题交 subagent 复查 → 去重 / 校正严重度 / 收敛，直至达成共识

Step 5：组织发现项（P0 / P1 / P2-P3）

Step 6：产出结论报告
  ├── 独立运行按 tpl-report.md 输出；受委托按上层约定交付：审查概要（含上线风险）、发现项（P0→P1→P2-P3）、Open Questions、覆盖自评
  └── 输出方式：默认输出到会话；用户要求存档或需要产物归档时落盘，落盘后在会话中展示路径与摘要

Step 7：落地到 PR（可选后置动作）
  ├── 触发：用户提供了 PR 链接 或 明确要求「发到 PR」
  └── 策略：P0/P1 逐条行内评论，待确认项额外最多 3 条行内评论，其余合并全局摘要；详见 references/pr-comment.md

Step 8：上报到 CR 看板（独立运行时；受上层委托跳过）
  ├── 默认启用；用户显式说「不要上报」时跳过
  ├── 从已产出报告 + git 环境提取字段，组装 payload，调用 scripts/report-submit.sh
  ├── 失败不阻塞，静默在会话末尾提示
  └── 详见 references/report-submit.md
```

## Step 0: 判定范围与可靠性

命中触发词后，立即回复用户审查已启动。例如：`🔍 代码审查已启动，请稍候…`。随后在各阶段开始执行时播报 `🟢 开始 Step N：xxx`。

> 流程开始时创建一个 TodoList（如有），以便 Agent 能在长任务中持续跟踪本次 CR 的各阶段任务。其中必须包含两项：**创建 subagent 做复查**（对应 Step 4），以及**输出报告前回忆整个流程，确认没有违反或遗漏**（对应 Step 6 前）。其余 Todo 内容由 Agent 自行组织。

### Step 0.a：确定变更范围

用户以 PR 为审查对象时先执行 Step 0.c；明确指定本地范围或没有 PR 时，按用户输入或 Git 状态确定变更范围：

- `staged`：`git diff --cached --name-only` + `git diff --cached`
- `working_tree`：`git diff --name-only` + `git diff`
- `commit:<sha>`：`git show --stat --name-only <sha>` + `git show <sha>`
- `branch:<base>...HEAD`：`git diff --name-only <base>...HEAD` + `git diff <base>...HEAD`

确定范围时排除 `.mdp/rules/**` 与 `.fed/**`。Git 支持 pathspec 时，使用 `-- . ':(exclude).mdp/rules/**' ':(exclude).fed/**'`；否则从文件清单中剔除这两个前缀。规则包不属于业务变更。用户要求核验规则同步时，检查 receipt 和 manifest，不审查规则文本。

### Step 0.b：异常处理

若没有发现有效的变更内容，直接停止并告知用户。

### Step 0.c：仓库一致性校验（仅当用户给了 PR 链接时执行）

用户明确指定本地 staged、working tree、commit 或 branch 范围时，沿用 Step 0.a；PR 链接仅用于背景和后续评论，先校验仓库是否一致，不一致时继续本地审查但不向该 PR 评论。

用户以 PR 为审查对象时，按以下步骤确定范围：

1. 从 PR URL 解析 `{org}/{repo}`
2. 在当前目录执行 `git remote get-url origin`（失败说明非 git 仓库）
3. 比对：origin URL 中含 `{org}/{repo}` 即视为一致

校验结果分支：

- ✅ **一致** → 先核对 PR 本轮 diff 与目标 commit，按 [PR-only Step 0.d](pr-only.md#step-0d准备仓库) 复用或准备对应快照；按冻结的 PR 范围审查，不以未更新的本地远程分支或工作区内容替代。
- ❌ **不一致** 或 **当前目录非 git 仓库** → 告知用户后转 PR-only 模式（按 SKILL.md 第四章重新路由）：

```
ℹ️ 检测到当前目录与 PR 仓库不一致（或非 git 仓库），已自动切换到 PR-only 模式。如果你只想 review 本地变更，请明确告知。

PR 仓库：{org}/{repo}
当前目录：{actual_remote 或 "非 git 仓库"}
```

用户要求只看本地变更但未指定具体范围时，按 Step 0.a 的本地规则推断，不因附带 PR 链接转为 PR 范围。

> 不要用当前目录的变更代替 PR 变更——那不是用户期望的审查对象。

### Step 0.d：识别技术栈

读取 [技术栈识别](../stack-detection.md)，结合本次变更文件、对应依赖和目录结构识别技术栈；允许命中多个，证据不足时记录“未识别”。

## Step 1: 输出准备信息

独立运行时按 `references/tpl-report.md`「准备」章节组织内容；受委托时保留相同准备信息用于交接，不要求渲染该章节。至少包含：

- 识别出的改动文件 / 目录
- 对变更内容的理解
- 已读上下文、未读或未验证范围
- 可靠性结论：`可信 / 需补充材料 / 不建议继续`

结论分支：

- `可信` → 自动进入 Step 2
- `需补充材料` → 先补材料后继续
- `不建议继续` → 向用户说明风险，由用户决定是否继续

## Step 2: 读取平台规则

读取 [`references/rules-loading.md`](../rules-loading.md)。同步成功时读取 L1/L2；无论同步结果如何，读取仓库本地的 `.mdp/rules/project/**/*.md` 与 `.fed/` 目录规则，并从适用的 `AGENTS.md`、`README` 等入口发现其声明的审查规则或规则文件；在准备信息记录规则快照、Release、fallback 状态以及实际规则路径、入口来源和范围。

需要理解 MRN / Max 行为时，读取对应 context；识别到 DUO 技术栈时，读取 [DUO context](../context/duo-context.md)。这些内容不作为规则来源。

## Step 3: 执行审查

主审读取 [定级与证据判断](../severity.md)，用于候选问题补证和影响判断。

### 依赖升级风险扫描（subagent 并行）

变更文件含 `package.json` 时，必须判定是否触发依赖扫描，不得跳过。详细判定规则见 `references/rules/base/dep-upgrade-rules.md`「触发条件」一节，核心要点：

- 内部业务组件（`@mtfe/*`、`@meishi/*` 等）：任何版本变化即触发，包括 prerelease/beta
- 公共开源组件：仅 major 升级触发
- resolutions 新增/变更：触发

触发后创建 subagent 按 `dep-upgrade-rules.md` 执行完整扫描，发现项在 Step 5 合并。

### MSI API 契约核对（subagent 并行）

本地 diff 出现 MSI Bridge 调用时，必须先判断调用是否被实质修改，不得仅因上下文行出现 MSI 调用就触发。详细判定与执行方式见 `references/rules/base/msi-api-review-rules.md`，核心要点：

- 支持 `msi.xxx`、`MSI.xxx`、`preset.xxx` 和 `@mtfe/msi-*` 容器包调用
- Bridge 名称、入参、返回字段读取、回调、Promise 或错误处理发生变化时触发
- 普通 `KNB.xxx`、纯格式修改、文件移动或未改动的上下文行不触发

触发后创建独立 subagent，只加载 `infra-msi` 的 api-query 子能力做 API 文档契约核对。发现项在 Step 5 合并；Skill 或 API 明细不可用时记录为未验证，不阻塞主审查。

### 代码审查

审查时遵循以下约束：

- 先看阻塞项，再看建议项
- 先看真实行为风险，再看写法和可维护性
- 重点核对：
  - 结合需求或技术方案，判断业务逻辑是否正确
  - 空值、异常流、边界条件是否完整
  - 导出函数、组件、参数、默认值是否破坏旧契约
  - 状态、缓存、监听器、定时器、副作用是否有清理和生命周期边界
  - 请求、重试、重复提交、异步竞态是否安全
  - 公共代码、跨端代码、平台能力是否考虑兼容性
  - 是否遗留 mock、调试代码、敏感信息、预发字段、灰度开关

上下文不足时：

- 继续补读相关实现、调用方、类型、测试
- 仍无法确认 → 按 [定级与证据判断](../severity.md) 筛选待确认问题；无具体核实价值的猜测不输出

## Step 4: 复查与校正

简易复查步骤：

0. [You] 完成首轮分析，已形成初步候选问题
1. [You] 创建独立 subagent，要求复查候选问题
2. [Check_Subagent] 执行复查，过程中如果发现了其它问题也一并返回
3. [You] 环境中 subagent 不可用，则告知用户并跳过，由你自行**再次评估**
4. [You] 基于 subagent 的复查结果对候选问题去重、确认严重程度；存在争议时和 subagent 协商

注意：subagent 只聚焦复查与挑错，不单独输出最终结论或改写报告结构。不要直接信任 subagent 的判断，以你为准。证据不足、结论冲突的问题列入 `Open Questions`

## Step 5: 组织发现项

主审按 [定级与证据判断](../severity.md) 收敛全部候选，包括专项扫描和复查返回项。最终发现项按 `P0 / P1 / P2-P3` 分组；待确认问题沿用 `Open Questions`，不计入缺陷数。

整理要求：

- 一条问题只说一个核心风险
- 包含：问题类型、原因、位置、修复建议
- 可自动修复的风格问题合并为一条，不逐行展开
- 需要展开说明时，在详项区补充置信度、原因、回归提示
- 命中规则时按 `rules-loading.md` 记录 `rule_sources`；纯上下文发现项传空数组

## Step 6: 产出结论报告

**输出前，在回忆整个 CR 流程（Step 0 ~ Step 5），确认没有遗漏或违反任何步骤。如发现遗漏，先补齐再输出报告。**

受上层委托时按 [`output.md`](../output.md) 交付结果，由上层组织最终报告；除非明确要求，不额外渲染完整前端报告。

独立运行时按 `references/tpl-report.md` 输出中文报告，至少包含：

- 审查概要：变更摘要、审查结论、上线风险、P0-P3 统计
- 发现项：P0 → P1 → P2-P3
- Open Questions
- 覆盖自评

具体输出内容及风格，详见 `references/output.md`。

此报告输出一次即可。最终总结时，无需再重复输出此报告。

### MCM 参考信息

用户提及 MCM 时，按 `references/tpl-report.md`「MCM 参考信息」章节的字段，从当前 CR 过程收集的信息中提取并附加到报告末尾。未提及时不输出。

## Step 7: 落地到 PR（可选后置动作）

上层负责统一发布时跳过本步骤，避免重复评论。以下适用于独立运行。

当本地 CR 产出报告后，若用户提供了 PR 链接（且已通过 Step 0.c 仓库一致性校验）或明确要求「发到 PR」，自动把发现项评论到对应 PR。该动作**不改变前面 Step 0~6 的任何流程**，只复用已产出的 `P0 / P1 / P2-P3 / Open Questions`。

- **触发**（默认启用）：用户给出 `dev.sankuai.com/.../pr/{id}` 链接，或显式说「评论到 PR」「发到 PR」
- **跳过**：用户显式说「只看本地」「只出报告」「不要发 PR」
- **评论策略**：
  - P0 / P1 → **行内评论**（逐条，锚定 file + line + ADDED）
  - 待确认问题 → 重要且值得人工核实的最多 3 条行内评论，独立限额；其余详情及已评论项索引与 P2/P3、整体结论合并为全局摘要，选择与去重方式见 `references/pr-comment.md`
- **失败降级**：按评论指引处理鉴权失败、重试和结果核验，不阻塞报告产出
- **详细执行步骤、命令参数、评论模板**：`references/pr-comment.md`

## Step 8: 上报到 CR 看板（独立运行时的可选后置动作）

受 `ai-quality-cr-agent` 委托时跳过，由上层统一发布。


Step 6 报告产出后，在本步骤按 [`references/report-submit.md`](../report-submit.md) 组装 CR 看板 payload 并运行上报脚本。用户说「不要上报」时跳过；上报失败时在会话末尾提示。

## 修复检查（增量复查）

当用户后续提出类似"已修复，再看一轮"时，进入复查流程：

1. 以上一轮发现的问题为基准，先验证是否已修复
2. 再检查修复过程是否引入新问题或回归
3. 输出可简化为增量附录形式：列出 `resolved / unresolved / new findings / open questions` 四组，无需重新输出准备章节
4. 落盘规则：默认在会话内输出；需要产物归档时主文件追加附录，不重新生成整份报告
