# PR-only 模式

> 入口路由见 `SKILL.md` 第四章「CR 模式入口」。本文承载 PR-only 模式的完整执行流程，自包含可独立加载。

## 适用范围

以 PR diff 确定审查范围，远程上下文及匹配审查 commit 的仓库快照用于补读实现和调用方。适用于审查远程 PR、当前无匹配仓库或用户指定 PR-only 的场景。用户明确要求仅使用远程证据时，不拉取或读取本地业务代码。

## 执行流程概览

```
Step 0：输入采集
  ├── 0.a 解析 PR 链接 → {org, repo, pr_id}
  ├── 0.b 拉取 PR 元信息：title / description / fromRef / toRef
  ├── 0.c 拉取变更文件清单（pr-changes）
  ├── 0.d 复用或按需拉取匹配审查 commit 的仓库
  ├── 0.e 探测远程上下文工具 code-repo-search 是否可用
  └── 0.f 选择上下文采集策略（with-checkout / with-search / diff-only）

Step 1：输出准备信息（含 PR-only 模式声明）

Step 2：同步并读取平台规则

Step 3：执行审查
  ├── 3.a 拉取每个变更文件的 diff（pr-diff）
  ├── 3.b 补读关键符号定义与引用（仓库快照或远程搜索）
  ├── 3.c [并行] package.json 有组件升级时，subagent 执行依赖升级风险扫描（dep-upgrade-rules.md）
  ├── 3.d [并行] diff 实质修改 MSI Bridge 调用时，subagent 执行 API 契约核对（msi-api-review-rules.md）
  └── 3.e 按规则集做四层审查，证据不足降为 Open Questions

Step 4：复查与校正（subagent 须能感知"远程审查"上下文）

Step 5：组织发现项（P0 / P1 / P2-P3）

Step 6：产出结论报告（diff-only 路径加 banner）

Step 7：落地到 PR（PR 链接已天然就位）

Step 8：上报到 CR 看板（独立运行时；受上层委托跳过）
  ├── 默认启用；用户显式说「不要上报」时跳过
  ├── 从已产出报告 + PR 元信息提取字段，调用 scripts/report-submit.sh
  ├── 失败不阻塞，静默在会话末尾提示
  └── 详见 references/report-submit.md
```

## Step 0：输入采集

命中触发词后，先回复 `🔍 代码审查已启动（PR-only 模式），请稍候…`，再播报 `🟢 开始 Step 0：采集 PR 输入`。

> 流程开始时创建一个 TodoList（如有），以便 Agent 能在长任务中持续跟踪本次 CR 的各阶段任务。其中必须包含两项：**创建 subagent 做复查**（对应 Step 4），以及**输出报告前回忆整个流程，确认没有违反或遗漏**（对应 Step 6 前）。其余 Todo 内容由 Agent 自行组织。

### Step 0.a：解析 PR 链接

从用户输入提取 PR URL，匹配 `dev.sankuai.com/code/repo-detail/{org}/{repo}/pr/{id}`，得到 `{org, repo, pr_id}`。

解析失败 → 停止并请求用户重新粘贴完整 URL。

### Step 0.b：拉取 PR 元信息

```bash
python3 scripts/pr-comment/code_cli.py pr-info --url <PR_URL>
```

字段使用：

- `title` / `description` → 业务背景与变更目标
- `fromRef` / `toRef` → 源/目标分支，作为审查范围标识
- `author` → 用于沟通时锚定责任人

> 鉴权方式与 PR 评论落地共用同一套 cookie 取数链路，详见 `references/pr-comment.md`。

### Step 0.c：拉取变更文件清单

```bash
python3 scripts/pr-comment/code_cli.py pr-changes --url <PR_URL>
```

输出 `{fromHash, toHash, totalFiles, changes[].path/type}`。

**超大 PR 防护**：

- `totalFiles` ≥ 100 → 提示用户 PR 较大，需要重点关注；不自动截断，但 Step 3 拉 diff 时按“高变更文件优先”处理
- `totalFiles` 命中 500 上限 → 提示“PR 触发 Code 平台 500 文件展示上限”，明确告知本次审查可能漏掉超出范围的文件

### Step 0.d：准备仓库

用户明确要求仅使用远程证据时，跳过业务仓库准备，按 Step 0.e / 0.f 选择远程策略；Step 2 规则同步照常执行。

先确定本轮目标 commit：受委托时使用上游冻结的 `TARGET_COMMIT`，增量范围保留 `BASE_COMMIT → TARGET_COMMIT`；独立运行时从 PR 元信息确定源分支 commit，并核对 diff 属于同一范围。

- 优先检查当前目录、用户或上游提供的路径，以及当前环境中已知或可快速发现的仓库；校验 remote 对应 `{org}/{repo}` 且包含目标 commit。
- 已有仓库可通过 `git show <commit>:<path>` 读取快照；需要目录检索时使用独立的 detached worktree。不要切换用户分支或读取未提交内容作为 PR 证据。
- 缺少仓库或目标 commit 时，在 Git、现有鉴权和可写临时目录可用的条件下，从已确认的仓库克隆地址按需浅拉取（`--depth 1`）到系统临时目录下本轮独立目录，并定位目标 commit；已有仓库可按需 fetch 缺失 commit。每次 clone / fetch 设置 120 秒超时，失败或超时后走远程降级，不自动改成全量克隆。不安装依赖或执行仓库脚本。
- 拉取失败或条件不具备时，记录原因，继续远程上下文采集和 Step 2 规则同步；不因缺少 checkout 要求用户补路径。

记录可用仓库路径和实际 commit，并传给后续专项审查与复查 Agent。仅存放规则的目录不算业务仓库。主审、专项和复查全部结束后，清理本轮创建的临时仓库与规则目录；worktree 使用 `git worktree remove` 清理。失败产生的临时目录也需回收，不清理复用的用户目录或其中新获取的 Git 对象。

### Step 0.e：探测 code-repo-search 是否可用

执行 `which code-repo-search`，记录是否可用，供下一步选择策略。

### Step 0.f：选择上下文采集策略

仅使用远程证据时，排除 `with-checkout`，根据工具可用性选择 `with-search` 或 `diff-only`。

| 策略 | 触发条件 | 行为 | 报告 banner |
|------|---------|------|-------------|
| `with-checkout` | 已有可读取的目标 commit 快照 | PR diff 确定范围，仓库快照补读实现、依赖和调用方 | 不加 |
| `with-search` | 不使用仓库快照，code-repo-search 可用 | 拉 diff 后用 code-repo-search 反查关键符号定义/引用 | 不加 |
| `diff-only` | 不使用仓库快照且 code-repo-search 不可用 | 仅基于 diff + PR 描述做审查 | **必须加**（见 Step 6 补丁） |

上下文读取均须对应本轮目标 commit；无法核对版本的结果只作线索。

### Step 0.g：识别技术栈

读取 [技术栈识别](../stack-detection.md)，先按 PR 文件清单识别，获取远程 diff 和上下文后补充。采用 `with-checkout` 时，可读取目标 commit 的 package.json 和相关代码；证据不足时记录“未识别”。

## Step 1：输出准备信息

独立运行时按 `references/tpl-report.md`「准备」章节组织内容；受委托时保留相同准备信息用于交接，不要求渲染该章节。至少包含：

- 模式声明：**PR-only 模式**，说明审查 commit 及实际使用的远程上下文或仓库快照
- PR 元信息：org/repo/pr_id、title、author、fromRef → toRef
- 变更摘要：文件数、改动文件列表（按目录归类）
- 上下文策略：`with-checkout`、`with-search` 或 `diff-only`，diff-only 时显式标注"上下文受限"

PR-only 模式下不输出"自由文本可靠性结论"（避免逐次重复输出"需补充材料"刷屏），改为单一阻塞判定：

- **阻塞条件**：`diff-only` 策略 **且**（`totalFiles ≥ 50` **或** 涉及公共模块改动，关键词如 `common / shared / utils / sdk`）
- **命中阻塞** → 先完成 Step 2 规则同步，再提示用户「文件较多 / 公共模块改动，PR-only 上下文有限，建议切到本地模式」，征询是否继续
- **未命中** → 直接进入 Step 2，不再询问

`with-checkout` / `with-search` 路径默认不阻塞，结合 PR 描述完整性自行判断；PR 描述缺失到无法判断变更目标时，请求补充。

## Step 2：读取平台规则

读取 [`references/rules-loading.md`](../rules-loading.md)。同步成功时读取 L1/L2；无论同步结果如何，读取仓库本地的 `.mdp/rules/project/**/*.md` 与 `.fed/` 目录规则，并从适用的 `AGENTS.md`、`README` 等入口发现其声明的审查规则或规则文件；在准备信息记录规则快照、Release、fallback 状态以及实际规则路径、入口来源和范围。

需要理解 MRN / Max 行为时，读取对应 context；识别到 DUO 技术栈时，读取 [DUO context](../context/duo-context.md)。这些内容不作为规则来源。

## Step 3：执行审查

主审读取 [定级与证据判断](../severity.md)，用于候选问题补证和影响判断。

### Step 3.a：拉取变更 diff

受委托时优先使用上游冻结的 diff；重新获取的 diff 必须与本轮 commit 范围一致，不用 PR 后续更新的内容替换。

按 Step 0.c 的文件清单逐个拉取，排除 `.mdp/rules/**` 与 `.fed/**` 规则目录：

```bash
python3 scripts/pr-comment/code_cli.py pr-diff --url <PR_URL> --file <path> --context 5
```

> diff 用于定位变更；需要完整实现时，按 Step 3.b 补读上下文。

**优先级编排**（文件多时按此顺序消费）：

1. 业务核心目录（含 `pages` / `services` / `domain` / `core` 关键词）
2. 修改行数 ≥ 50 行的文件
3. 公共目录（含 `common` / `shared` / `utils`）
4. 其它

### Step 3.b：补读上下文

`with-checkout` 使用目标 commit 的仓库快照，`with-search` 使用可核对版本的远程搜索。针对以下情况查找定义和引用：

- 改动了导出符号（函数 / 组件 / 类型）→ 反查全仓引用，评估破坏性
- 引用了陌生符号 → 反查定义，确认契约
- 跨文件状态变更 → 反查相关 store / context 定义

`diff-only` 策略下跳过本节，相关结论一律降为 Open Questions。

### Step 3.c：依赖升级风险扫描（subagent 并行）

变更文件含 `package.json` 时，**必须判定是否触发依赖扫描，不得跳过**。详细判定规则见 `references/rules/base/dep-upgrade-rules.md`「触发条件」一节，核心要点：

- 内部业务组件（`@mtfe/*`、`@meishi/*` 等）：任何版本变化即触发，包括 prerelease/beta
- 公共开源组件：仅 major 升级触发
- resolutions 新增/变更：触发

触发后创建 subagent 按 `dep-upgrade-rules.md` 执行完整扫描，发现项在 Step 5 合并。

> PR-only 模式下 `npm pack` 不依赖本地仓库可正常执行；扫描项目使用方式时优先读取目标 commit 的仓库快照；上下文不足时标注未验证。

### Step 3.d：MSI API 契约核对（subagent 并行）

PR diff 出现 MSI Bridge 调用时，必须先判断调用是否被实质修改，不得仅因上下文行出现 MSI 调用就触发。详细判定与执行方式见 `references/rules/base/msi-api-review-rules.md`，核心要点：

- 支持 `msi.xxx`、`MSI.xxx`、`preset.xxx` 和 `@mtfe/msi-*` 容器包调用
- Bridge 名称、入参、返回字段读取、回调、Promise 或错误处理发生变化时触发
- 普通 `KNB.xxx`、纯格式修改、文件移动或未改动的上下文行不触发

触发后创建独立 subagent，只加载 `infra-msi` 的 api-query 子能力做 API 文档契约核对。向 subagent 提供 PR diff、目标 commit 和当前可用的仓库快照或远程上下文；无法获得完整调用或平台分支时，相关结论降为 `Open Questions`。发现项在 Step 5 合并，Skill 或 API 明细不可用时记录为未验证，不阻塞主审查。

### Step 3.e：按规则集做四层审查

审查时遵循以下约束：

- 先看阻塞项，再看建议项
- 先看真实行为风险，再看写法和可维护性
- 重点核对：
  - 结合需求或 PR 描述，判断业务逻辑是否正确
  - 空值、异常流、边界条件是否完整
  - 导出函数、组件、参数、默认值是否破坏旧契约
  - 状态、缓存、监听器、定时器、副作用是否有清理和生命周期边界
  - 请求、重试、重复提交、异步竞态是否安全
  - 公共代码、跨端代码、平台能力是否考虑兼容性
  - 是否遗留 mock、调试代码、敏感信息、预发字段、灰度开关

PR-only 模式下的差异处理：

- 无法判断"修改是否破坏旧契约" → 列为 Open Questions，请提交人补充对全仓影响的说明
- 无法验证"删除的文件/函数是否仍有引用"（diff-only 路径）→ 列为 Open Questions
- 涉及配置 / 灰度开关 / 环境变量 → 一律标注"PR-only 模式无法核实运行时取值"
- 仍无法确认 → 按 [定级与证据判断](../severity.md) 筛选待确认问题；无具体核实价值的猜测不输出

## Step 4：复查与校正

简易复查步骤：

0. [You] 完成首轮分析，已形成初步候选问题
1. [You] 创建独立 subagent，要求复查候选问题
2. [Check_Subagent] 执行复查，过程中如果发现了其它问题也一并返回
3. [You] 环境中 subagent 不可用，则告知用户并跳过，由你自行**再次评估**
4. [You] 基于 subagent 的复查结果对候选问题去重、确认严重程度；存在争议时和 subagent 协商

注意：subagent 只聚焦复查与挑错，不单独输出最终结论或改写报告结构。不要直接信任 subagent 的判断，以你为准。证据不足、结论冲突的问题列入 `Open Questions`

复查 Agent 接收相同的 diff 范围、目标 commit 和上下文来源；有仓库时提供路径及快照读取方式，无仓库时说明远程证据范围。

## Step 5：组织发现项

主审按 [定级与证据判断](../severity.md) 收敛全部候选，包括专项扫描和复查返回项。最终发现项按 `P0 / P1 / P2-P3` 分组；待确认问题沿用 `Open Questions`，不计入缺陷数。

整理要求：

- 一条问题只说一个核心风险
- 包含：问题类型、原因、位置、修复建议
- 可自动修复的风格问题合并为一条，不逐行展开
- 需要展开说明时，在详项区补充置信度、原因、回归提示
- 命中规则时按 `rules-loading.md` 记录 `rule_sources`；纯上下文发现项传空数组

## Step 6：产出结论报告

**输出前，在回忆整个 CR 流程（Step 0 ~ Step 5），确认没有遗漏或违反任何步骤。如发现遗漏，先补齐再输出报告。**

受上层委托时按 [`output.md`](../output.md) 交付结果，由上层组织最终报告；除非明确要求，不额外渲染完整前端报告。

独立运行时按 `references/tpl-report.md` 输出中文报告，至少包含：

- 审查概要：变更摘要、审查结论、上线风险、P0-P3 统计
- 发现项：P0 → P1 → P2-P3
- Open Questions
- 覆盖自评

具体输出内容及风格，详见 `references/output.md`。

此报告输出一次即可。最终总结时，无需再重复输出此报告。

### PR-only 报告补丁

以下用于前端报告；受委托时将实际模式、commit 和上下文限制作为交接信息返回，由上层安排展示。

**模式声明（始终添加）**：报告概要紧随标题之后插入一行：

```
> 审查模式：PR-only；审查 commit：<commit>；上下文：<仓库快照 / 远程搜索 / 仅 diff>
```

**上下文受限 banner（仅 diff-only 路径添加）**：紧跟在模式声明下方，使用引用块强调：

```
> ⚠️ 本次审查未启用远程符号检索，跨文件影响、调用方一致性等结论可能有遗漏。
> 建议合并前由 PR 作者补充影响范围说明，或切换至本地模式复核。
```

`with-checkout` / `with-search` 路径不加该 banner，但仍保留模式声明。

### MCM 参考信息

用户提及 MCM 时，按 `references/tpl-report.md`「MCM 参考信息」章节的字段，从当前 CR 过程收集的信息中提取并附加到报告末尾。未提及时不输出。

## Step 7：落地到 PR（可选后置动作）

上层负责统一发布时跳过本步骤，避免重复评论。以下适用于独立运行。

PR-only 模式下天然有 PR 链接，无需仓库一致性校验，触发逻辑保持一致：用户给出“评论到 PR / 发到 PR”或默认开启时直接执行。

- **触发**（默认启用）：用户给出的 PR 链接已经在手，或显式说「评论到 PR」「发到 PR」
- **跳过**：用户显式说「只出报告」「不要发 PR」
- **评论策略**：
  - P0 / P1 → **行内评论**（逐条，锚定 file + line + ADDED）
  - 待确认问题 → 重要且值得人工核实的最多 3 条行内评论，独立限额；其余详情及已评论项索引与 P2/P3、整体结论合并为全局摘要，选择与去重方式见 `references/pr-comment.md`
- **失败降级**：按评论指引处理鉴权失败、重试和结果核验，不阻塞报告产出
- **详细执行步骤、命令参数、评论模板**：`references/pr-comment.md`

> 已知现象：PR-only 模式下，行内评论的文件 / 行号锚定可能因 diff `fromHash` 解析受限而被 MCode 平台退化为全局评论（`verify` 输出 `file: null`）。评论内容完整可见，**不视为发送失败**，无需重试。如需精确锚定，请走本地模式。

## Step 8: 上报到 CR 看板（独立运行时的可选后置动作）

受 `ai-quality-cr-agent` 委托时跳过，由上层统一发布。


读取 [`references/report-submit.md`](../report-submit.md)，组装 CR 看板 payload 并运行上报脚本。用户说「不要上报」时跳过；上报失败时在会话末尾提示。`operator` 从 PR 作者取得，`repo` / `branch` 从 PR 元信息取得。

## 修复检查（增量复查）

当用户后续提出类似“已修复，再看一轮”时：

1. 以上一轮发现的问题为基准，先验证是否已修复
2. 再检查修复过程是否引入新问题或回归
3. 输出可简化为增量附录形式：列出 `resolved / unresolved / new findings / open questions` 四组，无需重新输出准备章节

PR-only 模式下重新执行时需重新拉取 `pr-changes` 与 `pr-diff`（PR 可能已更新），不得用上一轮的 diff 缓存做判断；重新核对目标 commit，按需准备对应仓库快照。
