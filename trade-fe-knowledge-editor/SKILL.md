---
name: trade-fe-knowledge-editor
description: 维护 trade-fe-rule 仓库的交易前端知识库编辑（food/gc/ticket/hotel/platform 五组）。当用户说"更新 XX 前端知识库""维护 GC 知识库""仅更新 food page-index""只维护 gc glossary""补全门票订单状态机""自动更新 X 知识库""远程更新""自动化提 PR"等，或在本仓库内对 context-docs/<子目录>/<group>.md 与 spec/{coding-standards,adr,domain-models,pitfalls,nfr}/<group>*.md 做结构化改动时，触发本 skill。支持 **local（本地手动）** 与 **auto（自动拉 master→切分支→生成→提 PR）** 双模式，均支持**范围锁定**（scope）：指定范围时仅在范围内补齐/校验/提交，不联动检测其他文件。**不**覆盖业务写作本身（业务内容由用户/研发提供）。
version: 1.4.0
mode_default: local
mode_allowed: [local, auto]
repo:
  project: nibfe
  repo: trade-fe-rule
  ssh: ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git
  default_branch: master

metadata:
  skillhub.creator: "changsusheng"
  skillhub.updater: "changsusheng"
  skillhub.version: "V4"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "44006"
  skillhub.high_sensitive: "false"
---

# Trade FE Knowledge Editor（交易前端知识库编辑）

**定位**：trade-fe-rule 仓库内，把"维护某业务组知识库"这类**跨多文件的结构化编辑动作**，从人肉搬运升级为**模板驱动 + 模式路由 + Gate 确认 + 硬校验 + 可选自动 PR** 的工作流。

**⚠️ IRON LAW（违反即中止）**

1. **必须**工作在 `trade-fe-rule` 仓库内。工作区合法性判定 = `git remote origin URL 命中 nibfe/trade-fe-rule` **且** `向上存在 AGENTS.md + context-docs/ + spec/`。
   - **local 模式**：不合法 → 硬失败，提示用户 `cd` 进入仓库，**不做任何兜底**。
   - **auto 模式**：不合法 → 自动 `git clone ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git <clone_root>/trade-fe-rule-{ts}` 并 `cd` 进入，再继续流程。`<clone_root>` 由 `scripts/auto-pr.sh _resolve_clone_root` 按优先级动态选择：`$TRADE_FE_CLONE_ROOT` → `$CATPAW_WORKSPACE_ROOT` / `$WORKSPACE_FOLDER` → `$PWD` 向上命中的 `projects/`・`workspace/`・`workspaces/`・`repos/` 父节点 → `$HOME/projects` → `mktemp -d`（最终兜底），**不再写死 `/tmp`**。
2. **禁止**在用户未通过 Confirmation Gate 前写入任何 `.md` 文件。
3. **禁止**修改 frontmatter 以外的用户原文（除非用户明确请求改写），只做**追加 / 合并 / 补段**。
4. **禁止**引入仓库 `meta/doc-template.md` 未登记的 `category` / `domain` 值。
5. **禁止**跳过 `scripts/validate.js`；校验未通过时必须修正或明确告知用户。
6. **范围锁定铁律**：用户显式指定更新范围（如"仅更新 page-index""只维护 glossary、business-rules"）时，**仅可**在范围内的文件上执行读/写/校验/commit/PR；**严禁**读取、扩展检测、"顺带补齐"其他文件，**严禁**向用户推荐范围外文件的变更。范围只在用户明确扩展后才能扩大。
7. **auto 模式三关铁律**：auto 模式必须依次经过 ① workspace 合法性校验（IRON LAW 1，阶段 1）② 单一 Confirmation Gate（写盘前，阶段 4）③ `validate.js --scope` 校验（errors=0，阶段 6）三道关卡；任何一关未通过，**必须**中止流程，**严禁**继续 `git push` / `pr_create`。

---

## 何时触发 / 何时跳过

### local 模式（本地手动 · v1.1 行为）

| 触发 ✅ | 跳过 ❌ |
|--------|--------|
| "更新 GC 前端知识库" / "维护 food overviews" | 业务代码开发（写 tsx/ts） |
| "补全门票状态机 / 酒店 business-rules" | 单纯查询某业务术语（直接读 glossary/<group>.md 即可） |
| "新增一条 ADR 到 platform" | 修改 `meta/*.md` 或根 `AGENTS.md`（走知识库 Owner 流程） |
| "批量改 GC 5 个文件的 frontmatter" | `page-assets/<group>/` 下的提单/订详模块速查和特殊页面（粒度过细，本 skill 不介入；**仅 `page-index.md` 纳入**） |

### auto 模式（v1.2 新增 · 自动拉 master → 切分支 → 提 PR）

| 触发 ✅ | 跳过 ❌ |
|--------|--------|
| "**自动更新** GC 知识库并**提 PR**" / "**自动化**维护 food page-index" | "发个 PR"（不带 `<group>` / scope / 知识库语境，信息不足无法执行，追问后再落模式判定） |
| "**远程更新** ticket 状态机并提 PR" / prompt 内显式带 `mode: auto` / `--mode=auto` | "直接给我合入 master" / "auto merge"（本 skill 只负责 create PR，**不做** merge/approve/decline） |
| "帮我更新并提 PR" / "走自动流程" | 跨组 PR（一个 PR 里改 food + gc）；本 skill **一次只处理一个 `<group>`**，需拆分成多次 auto 任务 |
| 当前工作目录**不在** trade-fe-rule 仓库（P2 兜底，自动 `git clone` 到 `/tmp/…`） | 当前不在仓库内 **且** prompt 无任何 auto 关键词（判定为 local，硬失败要求 cd；必须显式加"自动/提 PR"关键词才降级到 auto clone 兜底） |
| 完整模式判定规则见下方《运行模式》章节 | auto 流程执行中若 working tree 不干净（阶段 3 `git status --porcelain` 非空）→ 中止并提示 `git stash`，**不硬走** |

---

## 合法业务组（严格枚举）

`food` / `gc` / `ticket` / `hotel` / `platform`。用户若说"服务零售" → `gc`；"到餐" → `food`；"门票/景点/度假" → `ticket`；"酒店/酒旅" → `hotel`；"低代码/DUO/组件库/跨组" → `platform`。其它输入必须在阶段 2 追问澄清，**不得默认选择**。

---

## 运行模式（local / auto · 优先级判定）

> **local 模式** = 用户本地工作区内手动更新知识库（v1.1 行为，零回归）。
> **auto 模式** = skill 自动拉 master → 切新分支 → 生成内容 → 提 PR 的完整闭环（v1.2 新增）。

**模式判定（自上而下，命中即停）：**

| 优先级 | 触发条件 | 结果模式 |
|-------|---------|---------|
| P1 | prompt 命中关键词：`自动更新` / `自动化` / `远程更新` / `远程` / `提 PR` / `提交 PR` / `帮我更新并提 PR` / `走自动流程` | **auto** |
| P2 | 当前工作目录**不在** trade-fe-rule 仓库下（workspace 校验不通过） | **auto**（强制切换，走 `git clone /tmp/…` 兜底） |
| P3 | prompt 或上下文中显式出现 `mode: auto` / `--mode=auto` | **auto** |
| 默认 | 以上均未命中，且当前在仓库工作区内 | **local** |

**重要：**
- 模式识别结果**必须明文**回给用户（例："模式 = auto（远程自动提 PR 流程），工作区 = /root/projects/trade-fe-rule-20260422193232（clone_root 来源：\$PWD 继承）"）。
- 模式切换**必须经过 IRON LAW 1 工作区合法性判定**；local 失败硬停，auto 失败走 clone。

---

## 工作流（7 阶段 · 模式路由 + 路由分发 + 安全门控）

> **阶段编号从 1 开始**；阶段 1 / 2 两种模式共用；阶段 3-7 中 auto 模式多出 git/PR 步骤，均在各阶段内明确标注 **[auto-only]**。

### 阶段总览表（一眼看完 7 阶段）

| 阶段 | 名称 | local | auto | 关键出口 |
|------|------|-------|------|---------|
| 1 | 模式判定 & 工作区就绪 | ✅ | ✅（含 `git clone` 兜底 + `master` 同步 + MIS 解析） | `mode` / `workspace_dir` / `mis?` 确定 |
| 2 | 识别（group + scope） | ✅ | ✅ | `(mode, group, scope, 目标文件清单)` 锁定 |
| 3 | 扫描现状 + [auto-only] 切分支 | ✅（读现状） | ✅（+ `git checkout -b` 新分支） | 变更计划表 (+ `branch_name`) |
| 4 | ⛔ **Confirmation Gate**（唯一人工确认点） | ✅ | ✅ | 获得逐文件决议 |
| 5 | 写盘（追加 / 合并 / 补段） | ✅ | ✅ | 所有队列文件写入完成 |
| 6 | 校验（`validate.js [--scope]`，errors=0 硬门禁） | ✅ | ✅ | 校验摘要写入会话状态 |
| 7 | 交付 + [auto-only] commit/push/PR | ✅（仅交付 Handoff Summary） | ✅（+ `git commit` + `git push` + `pr_create`） | Handoff Summary；auto 模式下输出 PR URL |

> 三道关卡对应位置：① IRON LAW 1 在**阶段 1**；② Confirmation Gate 在**阶段 4**；③ `validate.js` errors=0 在**阶段 6**。

### 阶段 1 · 模式判定 & 工作区就绪

- **操作**：
  1. 按上表判定 `mode ∈ {local, auto}`。
  2. **Workspace 合法性校验**（两条同时成立才合法）：
     - `git -C <cwd> remote get-url origin` 输出包含 `nibfe/trade-fe-rule`；
     - 从 `cwd` 向上查找，存在目录同时包含 `AGENTS.md` + `context-docs/` + `spec/`。
  3. 处理结果：
     - `local` + 合法 → 直接进入阶段 2，`workspace_dir = <仓库根>`。
     - `local` + 不合法 → **硬失败**："当前目录不在 trade-fe-rule 仓库内，请 cd 到仓库后重试；如需远程自动更新，请改说'自动更新…并提 PR'。"
     - `auto` + 合法 → 直接进入阶段 2，`workspace_dir = <仓库根>`。
     - `auto` + 不合法 → 调用 `scripts/auto-pr.sh ensure_workspace auto`，内部执行 `git clone ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git <clone_root>/trade-fe-rule-{yyyyMMddHHmmss}`，`cd` 进入，`workspace_dir = <clone_root>/trade-fe-rule-{ts}`。`<clone_root>` 见上方 IRON LAW 1 注释的 6 级动态选择策略。
  4. **[auto-only]** 在进入阶段 2 前，于 `workspace_dir` 执行：`git fetch origin && git checkout master && git pull --ff-only`，确保 master 最新。
  5. **[auto-only] MIS 解析**（按优先级取第一个非空值）：
     1. 环境变量 `$MIS` 或 `$USER_MIS`；
     2. `git config user.email` → `@` 前半段；
     3. `git config user.name`（若是 mis 格式：4-12 位英文小写字母数字）；
     4. skill 运行宿主 / CatPaw 环境提供的其他 mis 字段；
     5. 全部获取不到 → 留空（分支名退化为无 mis 段）。

- **出口条件**：`mode`、`workspace_dir`、（auto 模式下）`mis` 已确定。

### 阶段 2 · 识别（入口：阶段 1 完成）

- **操作**：
  1. 从 prompt 提取 `<group>`（按同义映射），若无法唯一确定 → 追问（A/B/C 单选）。
  2. 识别**意图范围**（scope）。合法 kind：`overview` / `glossary` / `business-rules` / `design-patterns` / `service-maps` / `coding-standards` / `adr` / `domain-models`（等价三项）/ `domain-entities` / `domain-enums` / `domain-state-machines` / `pitfalls` / `nfr` / `page-index` / **`all`**（全量）。
  3. **范围判定（严格，遵守 IRON LAW 6，两种模式均适用）**：
     - 用户出现"仅""只""仅限""page-index""glossary""business-rules""状态机""ADR"等范围关键词 → 进入 **范围锁定模式**（scoped），`scope = [命中的 kind]`；**禁止**自动添加其他 kind，**禁止**用"顺带补齐"话术诱导用户扩展范围。
     - 用户显式说 "全量更新" / "all" / "一次性完善" → `scope = all`。
     - 用户只说 "更新 XX 前端知识库" 无任何范围信息 → 默认 `scope = [overview]`，并在确认清单里 **单独一行提示**："如需顺带补齐兄弟文件，请回复'扩展到…'"，**绝不**擅自勾选其他文件。
  4. 识别结果明文回复格式：`模式=<mode> / 组=<group> / 范围=<scope>（<锁定标记>）/ 目标文件=N 个`。
- **出口条件**：已锁定 `(mode, <group>, scope, [目标文件清单])`，写入当前会话状态。
- **参考**：`references/file-matrix.md`。

### 阶段 3 · 扫描现状 + [auto-only] 切分支（入口：阶段 2 完成）

- **操作**（**仅对** `[目标文件清单]` 中的文件，**不得**去读取范围外文件作"交叉参考"）：
  1. 若文件存在 → 读取 frontmatter + 所有 H2 标题，与 `references/` 下对应模板对比，列出**缺失章节**和**frontmatter 字段缺口**。
  2. 若文件不存在 → 标记为 **[NEW]**，使用对应模板初始化。
  3. 统计现状行数（仅作为变更计划表的信息列输出，不做上限硬阻塞）。
  4. **范围锁定模式**下，变更计划表的表头必须标注 `范围: <kind list>`，且行数 = 范围内文件数，**不得**出现范围外的文件名。
  5. **[auto-only] 切分支**：
     - 预检测：若 `git status --porcelain` 非空（存在未提交改动）→ 中止并提示用户 `git stash` 或手动处理，**不得**硬走。
     - 分支名：`chore/update-knowledge-{mis?}-{yyyyMMddHHmmss}`（mis 取不到则省略该段，形如 `chore/update-knowledge-20260422193232`）。
     - 若目标分支**已存在**（秒级时间戳重复的极小概率）→ 追加 `-r2`、`-r3` … 后缀重试，直到不冲突。
     - 执行 `git checkout -b <branch>`。分支名记入会话状态。
- **出口条件**：产出一张**变更计划表**（文件 / 现状 / 建议动作 / 风险）。auto 模式下额外包含 `branch_name`。

### 阶段 4 · ⛔ Confirmation Gate(入口：阶段 3 完成；两种模式强制门控)

> **v1.2 语义说明（Q7=Y 的"统一语义化"实现）**：
> - 两种模式**各保留唯一一道 Gate**，位置为"**最后一个不可逆操作之前**"：
>   - **local 模式**：Gate = **写盘前**（与 v1.1 完全一致，零回归；写盘即不可逆）。
>   - **auto 模式**：Gate = **写盘前**（写盘即会产生 working tree 变更，虽然可 reset，但对齐 local 语义，最保守）。
> - **push / pr_create 本身不再设置独立 Gate**；Gate 通过后写盘 → 本地 commit → validate → push/pr_create 一次走完；最终 PR 链接 + 校验结果摘要在阶段 6/7 呈现。
> - 用户若要二次拦截，可在阶段 3 变更计划表回答"跳过"或"改写"；通过 Gate 后流程不再追问。

- **必须**向用户展示变更计划表（**包含 `mode` / `scope` / auto 模式的 `branch_name`**），并**逐文件**收集确认：
  - `[✓ 接受]`：按计划执行（追加/合并）
  - `[✗ 跳过]`：本次不动该文件
  - `[✎ 改写]`：用户提供具体内容替代模板占位
- **禁止**在收到明确确认（"确认/同意/go/执行"）前调用任何写入工具或 git 写操作。
- **出口条件**：获得逐项决议，记录到执行队列。

### 阶段 5 · 写盘（入口：阶段 4 通过）

- **操作**（对执行队列中每个文件，按顺序）：
  1. 读目标文件（若存在）。
  2. 合并策略：
     - frontmatter：按 `references/metadata-spec.md`**补齐** `tags` / `last_updated`（今天日期 YYYY-MM-DD），保留已有字段；不删除用户原字段。
     - 正文：对**缺失的 H2 章节**按模板注入占位，保留已有章节不动。用户已填内容优先于模板。
  3. 写回文件。
- **出口条件**：所有队列文件写入完成。

### 阶段 6 · 校验（入口：阶段 5 完成；两种模式强制执行）

- **操作**：
  1. **工作目录必须在 `trade-fe-rule` 仓库内**（根或任意子目录均可，auto 模式下即 `workspace_dir`）。校验命令按模式选择：
     - 全量模式：`node <path-to-skill>/scripts/validate.js <group>`
     - 范围锁定模式：`node <path-to-skill>/scripts/validate.js <group> --scope <kind1,kind2,…>`（`--scope` 与阶段 2 识别结果严格一致，**不得**扩大）
     - **auto 模式强制 `--scope` 路径**：scoped → `--scope <kinds>`；`scope=all` 时也显式传 `--scope all`（便于日志留痕）。
     脚本会从 cwd 自动向上查找仓库根；若 cwd 不在仓库内会报错退出并提示用户 `cd` 进入仓库。范围锁定模式下脚本仅扫描 scope 命中的文件且跳过全局 G12（AGENTS.md 存在性）检查，避免越权。
  2. 若出现 `ERROR` → **两种模式均**中止后续流程：local 回到用户手动修复；auto **禁止** push/pr_create，回到用户修复后人工重入。**范围锁定模式**下仅修复范围内文件的问题，范围外文件即使有历史问题也**不修改、不提示**。若为 `WARN` → 列入交付报告。
  3. 对照 `assets/checklist.md` 逐项打勾。
- **出口条件**：`errors=0`；校验摘要（含规则清单）写入会话状态，供阶段 7 使用。

### 阶段 7 · [auto-only] commit / push / PR & 交付（入口：阶段 6 通过）

> local 模式跳过本阶段的 git 步骤，直接走"交付 Handoff Summary"小节。

- **[auto-only] git 提交**：
  1. `git add <scope 内改动文件>`（**严禁** `git add .` / 全量 add；仅添加 scope 命中的目标文件）。
  2. `git commit -m "chore(knowledge): 更新 <group> <kinds> [mis@yyyyMMdd]"`
     - commit message 正文含：`scope`、变更文件清单、validate 汇总、原始 user prompt 摘要。
     - **单个 commit**：所有改动合成一次 commit（Q13.A）。
  3. `git push origin HEAD`。
     - 失败（网络/权限）→ **保留本地分支和 commit**，输出恢复指引（例：`cd <workspace_dir> && git push origin <branch>`），**不自动回滚**。

- **[auto-only] 创建 PR**（调用 `scripts/auto-pr.sh pr_create_wrapper`，底层引用同目录 `_code_.sh`）：
  - `project = nibfe`, `repo = trade-fe-rule`，`fromRef = <branch>`，`toRef = master`，`reviewers = []`（留空，仓库默认 reviewer 兜底，Q8.C）。
  - **title 规范**：`chore(knowledge): 更新 <group> <kinds> [mis@yyyyMMdd]`
  - **description 规范（四段式）**：
    ```markdown
    ## 变更范围
    - 模式：auto（scoped / full）
    - 业务组：<group>
    - Scope（kinds）：<kind1, kind2, …>
    - 分支：<branch_name>

    ## 变更文件
    - <rel_path_1>
    - <rel_path_2>
    - …

    ## validate.js 校验结果
    命令：node <path-to-skill>/scripts/validate.js <group> --scope <kinds>
    汇总：errors=0 warnings=N
    规则清单：G1 ✓ / G2 ✓ / G5 WARN(1) / …

    ## 原始需求（User Prompt）
    > <用户原 prompt，原封不动引用>

    ---
    by trade-fe-knowledge-editor skill v1.2.1
    ```
  - `pr_create` API 失败 → 打印手动 fallback URL：`https://dev.sankuai.com/code/repo-detail/nibfe/trade-fe-rule/pr/create?sourceBranch=<branch>&targetBranch=master`，**不自动重试**，不回滚本地 commit。

- **交付 Handoff Summary**（两种模式共用）：
  - local 模式：列出改了哪些文件、每个文件改了哪些章节、剩余 TODO 占位、validate 汇总。**范围锁定模式**下 Summary 开头必须明标 `范围: <kind list>（严格锁定）`，摘要里**禁止**提及范围外文件的内容。
  - auto 模式：在 local 输出基础上追加 `branch_name`、`PR URL`、`commit hash`；若 push/PR 失败，明确标注"❌ 待人工接管"并给出恢复指引。

- **出口条件**：用户看到完整摘要；auto 模式下 PR 链接已呈现。

---

## Metadata（frontmatter）硬约束

所有被本 skill 触及的 `.md` 必须满足（字段取值见 `meta/doc-template.md`，**不得引入未登记值**）：

| 字段 | 要求 | 备注 |
|------|------|------|
| `category` | 必填，闭环枚举 | 见 `meta/doc-template.md` |
| `description` | 必填，一句话，≤120 字 | 用于 AI 检索 |
| `domain` | 必填，闭环枚举 | overview 类通常 `domain: <group>` |
| `related` | 可选，相对路径 | 本 skill 自动维护交叉链接 |
| `see-also` | 可选，外部 URL | 学城链接放这里 |
| `tags` | **本 skill 强制补齐** | ≥ 5 个业务/技术高召回词；与 glossary 一致 |
| `last_updated` | **本 skill 强制补齐** | YYYY-MM-DD，每次改动自动刷新 |
| `archived` | 归档时设为 true | 参考 update-guide |

---

## 速查：目标文件矩阵（`<group> ∈ {food,gc,ticket,hotel,platform}`）

| # | 文件路径 | 类型 | 默认模板 |
|---|----------|------|----------|
| 1 | `context-docs/overviews/<group>.md` | overview | `references/template-overview.md` |
| 2 | `context-docs/glossary/<group>.md` | glossary | `references/template-glossary.md` |
| 3 | `context-docs/business-rules/<group>.md` | rules | `references/template-business-rules.md` |
| 4 | `context-docs/design-patterns/<group>.md` | patterns | `references/template-design-patterns.md` |
| 5 | `context-docs/service-maps/<group>.md` | service-map | `references/template-service-maps.md` |
| 6 | `spec/coding-standards/<group>.md` | coding | `references/template-coding-standards.md` |
| 7 | `spec/adr/<group>.md` | architecture | `references/template-adr.md` |
| 8 | `spec/domain-models/<group>/entities.md` | domain-model | `references/template-domain-entities.md` |
| 9 | `spec/domain-models/<group>/enums.md` | domain-model | `references/template-domain-enums.md` |
| 10 | `spec/domain-models/<group>/state-machines.md` | domain-model | `references/template-domain-state-machines.md` |
| 11 | `spec/pitfalls/<group>.md` | pitfall | `references/template-pitfalls.md` |
| 12 | `spec/nfr/<group>.md` | nfr | `references/template-nfr.md` |
| 13 | `context-docs/page-assets/<group>/page-index.md` | page-asset | `references/template-page-index.md` |

**业务流程**文件 `context-docs/business-flows/<group>-<flow>.md` 按命名约定由用户指定 `<flow>`，本 skill 仅校验 frontmatter 与结构，**不自动初始化**。

**page-assets 的其他文件**（`*-order-submit-modules.md`、`*-order-detail-modules.md`、特殊页面）粒度过细 / 结构各异，本 skill **不介入也不校验**（见 `references/file-matrix.md`）。

---

## Anti-Patterns（本 skill 不做）

| 反模式 | 本 skill 的正确姿势 |
|--------|-------------------|
| AI 擅自编造业务术语/状态码填模板 | 留 `<!-- TODO: 由用户补充 -->` 占位 |
| 把 `meta/` 或根 `AGENTS.md` 也一并改了 | 只改 `spec/` 和 `context-docs/` 下的 `<group>` 文件 |
| 引入 `agents/global/` 等学城 wiki 提到但仓库未采纳的目录 | 以仓库现状为准（见 `references/conflict-notes.md`） |
| 把多个组的修改合并到一个 PR/改动 | 一次只处理一个 `<group>`，交付后再开下一个 |
| 擅自处理 `page-assets/<group>/` 下的模块速查/特殊页面文件 | 只动 `page-index.md`，其余引导用户自行维护 |
| 跳过校验脚本 | 每次交付必跑 `scripts/validate.js`（范围锁定模式加 `--scope`） |
| 删除/改写用户已有内容 | 只追加/补段/补 frontmatter 字段 |
| 用户说"仅更新 page-index"，AI 却去检查 overview/glossary 等并提示补齐 | 严格按 scope 锁定，范围外文件不读不写不提示 |
| 在 Handoff Summary 里"顺带提醒"范围外文件的历史问题 | Summary 只提范围内文件；历史问题等下次用户主动扩展范围再处理 |
| auto 模式下 `git add .` 全量 add，带入范围外 working tree 残留 | 仅 `git add <scope 内文件>`，严守范围锁定 |
| auto 模式下 validate 报错却硬走 push / pr_create | IRON LAW 7：校验未过必须中止，**禁止**继续 git 写操作 |
| auto 模式下从用户私人分支（非 master）切出新分支 | 阶段 1 强制 `git checkout master && git pull --ff-only`，一律基于 master 最新 |
| auto 模式下把 user prompt 以外的 AI 自造话术塞进 PR description | PR description 四段式严格对齐模板，user prompt 原封不动引用 |

---

## References（按需读取；不要一次性全加载）

- `references/file-matrix.md` -- 目标文件矩阵 + 优先级 + 冲突处理
- `references/metadata-spec.md` -- frontmatter 字段规范、tags 生成规则
- `references/template-overview.md` -- `context-docs/overviews/<group>.md` 模板
- `references/template-glossary.md` -- `context-docs/glossary/<group>.md` 模板
- `references/template-business-rules.md` -- `context-docs/business-rules/<group>.md` 模板
- `references/template-design-patterns.md` -- `context-docs/design-patterns/<group>.md` 模板
- `references/template-service-maps.md` -- `context-docs/service-maps/<group>.md` 模板
- `references/template-coding-standards.md` -- `spec/coding-standards/<group>.md` 模板
- `references/template-adr.md` -- `spec/adr/<group>.md` 模板
- `references/template-domain-entities.md` -- `spec/domain-models/<group>/entities.md` 模板
- `references/template-domain-enums.md` -- `spec/domain-models/<group>/enums.md` 模板
- `references/template-domain-state-machines.md` -- `spec/domain-models/<group>/state-machines.md` 模板
- `references/template-pitfalls.md` -- `spec/pitfalls/<group>.md` 模板
- `references/template-nfr.md` -- `spec/nfr/<group>.md` 模板
- `references/template-page-index.md` -- `context-docs/page-assets/<group>/page-index.md` 模板
- `references/conflict-notes.md` -- 学城 wiki vs 仓库现状冲突备忘
- `references/quality-gates.md` -- 质量门禁规则（行数/有效行/术语一致性）
- `assets/checklist.md` -- 交付前 Pre-Delivery Checklist
- `scripts/validate.js` -- 结构/frontmatter/大小 硬校验器（支持 `--scope` 范围锁定 & `--pr-summary` 输出 PR 可嵌入摘要）
- `scripts/auto-pr.sh` -- [auto-only] workspace 校验 / git master 同步 / 切分支 / commit / push / pr_create 全流程封装
- `scripts/_code_.sh` -- Code 平台 REST API 封装（hfe_stash 服务账号），`auto-pr.sh` 通过 source 本文件调用 `pr_create` / `repo_ref_exists` 等
- `evals/evals.json` -- 触发/路由/生成质量测试集（含 v1.2 新增 `auto-mode` 类别）
