# PR-only 模式

> 入口路由见 `SKILL.md` 第四章「CR 模式入口」。本文承载 PR-only 模式的完整执行流程，自包含可独立加载。

## 适用范围

无需克隆本地仓库，仅基于 PR 远程 diff 与远程上下文完成代码审查。典型场景：

- 当前目录不是 PR 对应仓库，且不便切换或克隆
- 需要快速过一遍他人提的 PR
- 用户明确表达「走 PR-only 模式」

## 执行流程概览

```
Step 0：输入采集
  ├── 0.a 解析 PR 链接 → {org, repo, pr_id}
  ├── 0.b 拉取 PR 元信息：title / description / fromRef / toRef
  ├── 0.c 拉取变更文件清单（pr-changes）
  ├── 0.d 探测远程上下文工具 code-repo-search 是否可用
  └── 0.e 选择上下文采集策略（with-search / diff-only）

Step 1：输出准备信息（含 PR-only 模式声明）

Step 2：识别技术栈并加载规则

Step 3：执行审查
  ├── 3.a 拉取每个变更文件的 diff（pr-diff）
  ├── 3.b 关键符号远程反查（仅 with-search 策略）
  ├── 3.c [并行] package.json 有组件升级时，subagent 执行依赖升级风险扫描（dep-upgrade-rules.md）
  ├── 3.d [并行] diff 实质修改 MSI Bridge 调用时，subagent 执行 API 契约核对（msi-api-review-rules.md）
  └── 3.e 按规则集做四层审查，证据不足降为 Open Questions

Step 4：复查与校正（subagent 须能感知"远程审查"上下文）

Step 5：组织发现项（P0 / P1 / P2-P3）

Step 6：产出结论报告（diff-only 路径加 banner）

Step 7：落地到 PR（PR 链接已天然就位）

Step 8：上报到 CR 看板（优先 后台 subagent 静默执行）
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

### Step 0.d：探测 code-repo-search 是否可用

执行 `which code-repo-search`，记录两种状态：

- 可用 → 进入 Step 0.e 的 `with-search` 策略
- 不可用 → 进入 Step 0.e 的 `diff-only` 策略

> `diff-only` 是合法降级路径——不要因为缺工具不使用本节路径，仅是上下文受限。

### Step 0.e：选择上下文采集策略

| 策略 | 触发条件 | 行为 | 报告 banner |
|------|---------|------|-------------|
| `with-search` | code-repo-search 可用 | 拉 diff 后用 code-repo-search 反查关键符号定义/引用 | 不加 |
| `diff-only` | code-repo-search 不可用 | 仅基于 diff + PR 描述做审查 | **必须加**（见 Step 6 补丁） |

策略一旦确定，全程不再切换。

## Step 1：输出准备信息

严格按 `references/tpl-report.md`「准备」章节组织内容，至少包含：

- 模式声明：**PR-only 模式（未拉取本地代码）**
- PR 元信息：org/repo/pr_id、title、author、fromRef → toRef
- 变更摘要：文件数、改动文件列表（按目录归类）
- 上下文策略：`with-search` 或 `diff-only`，diff-only 时显式标注"上下文受限"

PR-only 模式下不输出"自由文本可靠性结论"（避免逐次重复输出"需补充材料"刷屏），改为单一阻塞判定：

- **阻塞条件**：`diff-only` 策略 **且**（`totalFiles ≥ 50` **或** 涉及公共模块改动，关键词如 `common / shared / utils / sdk`）
- **命中阻塞** → 提示用户「文件较多 / 公共模块改动，PR-only 上下文有限，建议切到本地模式」，征询是否继续
- **未命中** → 直接进入 Step 2，不再询问

`with-search` 路径默认不阻塞，结合 PR 描述完整性自行判断；PR 描述缺失到无法判断变更目标时，请求补充。

## Step 2：识别技术栈并加载规则

**下列规则覆盖的是高频风险，不是审查边界。结合上下文和工程常识独立判断，看到明显问题就指出，不需要被规则条文局限。**

PR-only 模式下，技术栈识别在无本地仓库时退化为基于 PR 文件后缀 + 路径特征推断（如 `.tsx + react-native` 包路径 → MRN；`max-components` 引用 → Max；`pages/` + `app.json` → 小程序），准确度低于本地模式。识别不出时按通用前端规则集处理，并在报告中标注"技术栈未确认"。

先执行规则同步动作，确定本次规则读取根目录，详见 `references/rules-loading.md`。不得未尝试拉取规则直接使用本地兜底规则。

规则加载顺序（路径相对于已确定的读取根目录）：

1. **必读**：`base/general-rules.md` + `base/trade-rules.md`
2. **按技术栈选择**：MRN / Max / 小程序 / DUO stack 规则
   - MRN → `stack/mrn-rules.md`
   - Max → `stack/max-rules.md`
   - 小程序 → `stack/miniprogram-rules.md`
   - DUO → `stack/duo-rules.md`
3. **按需补读**：框架背景 context 规则（`references/context/mrn-context.md` / `references/context/max-context.md`，固定读本 skill 自带路径，不受规则同步动作影响）
4. **项目层规则**：用户显式提供时加载

## Step 3：执行审查

### Step 3.a：拉取变更 diff

按 Step 0.c 的文件清单逐个拉取：

```bash
python3 scripts/pr-comment/code_cli.py pr-diff --url <PR_URL> --file <path> --context 5
```

> `--context 5` 比默认 3 多两行，PR-only 上下文只能从 diff 自身扩展。

**优先级编排**（文件多时按此顺序消费）：

1. 业务核心目录（含 `pages` / `services` / `domain` / `core` 关键词）
2. 修改行数 ≥ 50 行的文件
3. 公共目录（含 `common` / `shared` / `utils`）
4. 其它

### Step 3.b：远程上下文反查（仅 with-search 策略）

针对以下情况调 `code-repo-search`：

- 改动了导出符号（函数 / 组件 / 类型）→ 反查全仓引用，评估破坏性
- 引用了陌生符号 → 反查定义，确认契约
- 跨文件状态变更 → 反查相关 store / context 定义

`diff-only` 策略下跳过本节，相关结论一律降为 Open Questions。

### Step 3.c：依赖升级风险扫描（subagent 并行）

变更文件含 `package.json` 时，**必须判定是否触发依赖扫描，不得跳过**。详细判定规则见 `references/rules/base/dep-upgrade-rules.md`「触发条件」一节，核心要点：

- 内部業务組件（`@mtfe/*`、`@meishi/*` 等）：任何版本变化即触发，包括 prerelease/beta
- 公共开源组件：仅 major 升级触发
- resolutions 新增/变更：触发

触发后创建 subagent 按 `dep-upgrade-rules.md` 执行完整扫描，发现项在 Step 5 合并。

> PR-only 模式下 `npm pack` 不依赖本地仓库可正常执行；但扫描项目使用方式时只能基于 PR diff 搜索，发现项置信度相应下调。

### Step 3.d：MSI API 契约核对（subagent 并行）

PR diff 出现 MSI Bridge 调用时，必须先判断调用是否被实质修改，不得仅因上下文行出现 MSI 调用就触发。详细判定与执行方式见 `references/rules/base/msi-api-review-rules.md`，核心要点：

- 支持 `msi.xxx`、`MSI.xxx`、`preset.xxx` 和 `@mtfe/msi-*` 容器包调用
- Bridge 名称、入参、返回字段读取、回调、Promise 或错误处理发生变化时触发
- 普通 `KNB.xxx`、纯格式修改、文件移动或未改动的上下文行不触发

触发后创建独立 subagent，只加载 `infra-msi` 的 api-query 子能力做 API 文档契约核对。只向 subagent 提供 PR diff 和当前能够获取的远程上下文；无法获得完整调用或平台分支时，相关结论降为 `Open Questions`。发现项在 Step 5 合并，Skill 或 API 明细不可用时记录为未验证，不阻塞主审查。

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
- 仍无法确认 → 降为 `Open Questions`，**不要**伪造确定性结论

## Step 4：复查与校正

简易复查步骤：

0. [You] 完成首轮分析，已形成初步候选问题
1. [You] 创建独立 subagent，要求复查候选问题
2. [Check_Subagent] 执行复查，过程中如果发现了其它问题也一并返回
3. [You] 环境中 subagent 不可用，则告知用户并跳过，由你自行**再次评估**
4. [You] 基于 subagent 的复查结果对候选问题去重、确认严重程度；存在争议时和 subagent 协商

注意：subagent 只聚焦复查与挑错，不单独输出最终结论或改写报告结构。不要直接信任 subagent 的判断，以你为准。证据不足、结论冲突的问题列入 `Open Questions`

**PR-only 特别提醒**：传给 subagent 的 prompt **必须**包含以下说明，避免 subagent 误以为可读本地代码：

> "本次审查在 PR-only 模式下执行，无本地代码可读；候选问题的证据仅来自 PR diff{ + 远程符号搜索}。"

## Step 5：组织发现项

发现项统一收敛为 `P0 / P1 / P2-P3` 三组：

- `P0`：零容忍，建议阻塞合并或停止提交
- `P1`：高风险，需修复或明确给出业务依据
- `P2-P3`：建议优化、低优问题、工具可处理问题

整理要求：

- 一条问题只说一个核心风险
- 包含：问题类型、原因、位置、修复建议
- 可自动修复的风格问题合并为一条，不逐行展开
- 需要展开说明时，在详项区补充置信度、原因、回归提示
- 问题命中规则库条目（`general-rules.md` / `trade-rules.md` / `stack/*.md`）时，标注对应规则编号（如 `R09`、`T02`、`MRN05`），0~n 个均可；纯上下文/业务逻辑判断没有对应规则时留空，不得编造

## Step 6：产出结论报告

**输出前，在回忆整个 CR 流程（Step 0 ~ Step 5），确认没有遗漏或违反任何步骤。如发现遗漏，先补齐再输出报告。**

严格按 `references/tpl-report.md` 输出中文报告，至少包含：

- 审查概要：变更摘要、审查结论、上线风险、P0-P3 统计
- 发现项：P0 → P1 → P2-P3
- Open Questions
- 覆盖自评

具体输出内容及风格，详见 `references/output.md`。

此报告输出一次即可。最终总结时，无需再重复输出此报告。

### PR-only 报告补丁

**模式声明（始终添加）**：报告概要紧随标题之后插入一行：

```
> 审查模式：PR-only（未拉取本地代码，基于 PR 远程 diff 完成审查）
```

**上下文受限 banner（仅 diff-only 路径添加）**：紧跟在模式声明下方，使用引用块强调：

```
> ⚠️ 本次审查未启用远程符号检索，跨文件影响、调用方一致性等结论可能有遗漏。
> 建议合并前由 PR 作者补充影响范围说明，或切换至本地模式复核。
```

`with-search` 路径不加该 banner，但仍保留模式声明。

### MCM 参考信息

用户提及 MCM 时，按 `references/tpl-report.md`「MCM 参考信息」章节的字段，从当前 CR 过程收集的信息中提取并附加到报告末尾。未提及时不输出。

## Step 7：落地到 PR（可选后置动作）

PR-only 模式下天然有 PR 链接，无需仓库一致性校验，触发逻辑保持一致：用户给出“评论到 PR / 发到 PR”或默认开启时直接执行。

- **触发**（默认启用）：用户给出的 PR 链接已经在手，或显式说「评论到 PR」「发到 PR」
- **跳过**：用户显式说「只出报告」「不要发 PR」
- **评论策略**：
  - P0 / P1 / P2 → **行内评论**（逐条，锚定 file + line + ADDED）
  - P3 + Open Questions + 整体结论 → 合并为**一条全局摘要**
- **失败降级**：重试 4 次仍失败 → 在会话输出，不阻塞报告产出
- **详细执行步骤、命令参数、评论模板**：`references/pr-comment.md`

> 已知现象：PR-only 模式下，行内评论的文件 / 行号锚定可能因 diff `fromHash` 解析受限而被 MCode 平台退化为全局评论（`verify` 输出 `file: null`）。评论内容完整可见，**不视为发送失败**，无需重试。如需精确锚定，请走本地模式。

## Step 8: 上报到 CR 看板（可选后置动作）

报告产出后，按 `references/report-submit.md` 的要求组装 payload 并通过脚本提交。

- **触发**（默认启用）：Step 6 完成后自动执行
- **跳过**：用户显式说「不要上报」「不上报看板」
- **执行**：按 `references/report-submit.md` 中「执行」一节的要求，通过临时文件传入 payload 并运行脚本
- **失败**：在会话末尾静默附加一行 `⚠️ CR 看板上报失败：<原因>`，不重试，不阻塞
- **PR-only 特别说明**：无本地 git 环境时，`operator` 从 PR 元信息 `author` 字段提取；`repo` / `branch` 从 PR URL 解析结果中取得
- **字段解析、枚举映射、payload 组装**：详见 [`references/report-submit.md`](../report-submit.md)

## 修复检查（增量复查）

当用户后续提出类似“已修复，再看一轮”时：

1. 以上一轮发现的问题为基准，先验证是否已修复
2. 再检查修复过程是否引入新问题或回归
3. 输出可简化为增量附录形式：列出 `resolved / unresolved / new findings / open questions` 四组，无需重新输出准备章节

PR-only 模式下重新执行时需重新拉取 `pr-changes` 与 `pr-diff`（PR 可能已更新），不得用上一轮的 diff 缓存做判断。
