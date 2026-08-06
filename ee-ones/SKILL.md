---
name: ee-ones
description: "通过 `ones` 命令行操作美团 ONES 系统（ones.sankuai.com）。覆盖：工作项（需求/任务/缺陷）的查询、创建、更新、删除、详情、评论、父子关联、资产与附件管理；URL 解析；工时填写/查询/汇总/代填；分支生成/创建/关联/搜索；迭代管理；测试用例/计划/轮次/导入；提测；排期管理；发布计划（上线计划）管理；空间/字段/界面方案查询；DSL 筛选；大象群管理；应用搜索与添加。当用户提到 ONES 相关操作时使用本 skill，如：查需求/任务/缺陷/bug、我的待办、建/改/删需求、拉分支、填工时、排期、发布计划、提测、测试用例、迭代、ONES 链接解析等。"
version: 2.2.55
tag: [ONES, 工作项, 需求, 任务, 缺陷, bug, 分支, 迭代, 冲刺, 测试, 工时, 工作量, 提测, 转测, 空间, 字段, 筛选, 查询, 搜索, 待办, 我的, 评论, 关联, 用例, 轮次, 计划, 开发进展, 进度, 上线, 时间范围, 预计开发, 预计上线, 链接解析, 工作项链接, ones.sankuai.com, 资产, 文档, PRD, MRD, BRD, 设计稿, 技术文档, 测试方案, 排期, 排期事项, 排期进度, UI交付, 排期时间, 交付时间, 附件, 上传附件, 删除附件, 图片, 上传图片, 图片描述, 新建, 创建, 修改, 更新, 删除, 指派, 详情, 状态, 流转, 子任务, 父需求, 工时填写, 工时记录, 工时汇总, 补填, 代填, 团队工时, 大象群, 建群, 工作项群, 延期, 风险, 版本进度, 项目进展, 做到哪了, 谁负责, 分给谁, 拉分支, 提个bug, 填工时, 看详情, 加评论, 建迭代, 写用例, 导入用例, 导入xmind, 上线时间, 什么时候上线, 解析链接, 应用, 服务列表, 搜索应用, 添加应用, 关联应用, SERVER, MAVEN, WEB, APP, DEV, OTHER, appkey, 仓库, 组件, 发布计划, 上线计划, releaseplan]

metadata:
  skillhub.creator: "hequanchuan"
  skillhub.updater: "hequanchuan"
  skillhub.version: "V11"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "21663"
  skillhub.high_sensitive: "false"
---

# ONES CLI 助手

通过 `ones` 命令行管理美团 ONES（ones.sankuai.com）系统的工作项、工时、分支、迭代、测试等。

本 Skill 采用渐进式加载：SKILL.md 包含路由、速查和 Case 精简索引，已覆盖绝大多数场景；只在需要详细参数、写操作确认、完整编排步骤或排查认证问题时，才按需读取 `references/` 下的文件。

---

## 文件结构与加载策略

```
ee-ones/
├── SKILL.md                     ← 路由 + 意图映射 + 强制规则 + Case 精简索引（当前文件）
└── references/
    ├── command-reference.md     ← --help 不够详细、查具体参数时加载
    ├── interactive-params.md    ← 执行创建/更新/删除时加载
    ├── auth-guide.md            ← 遇到认证问题时加载
    ├── filter-query-dsl.md      ← 使用 fi 命令构建 DSL 时加载；
    │                               含「与我相关查询」强制规则（策略 5）
    └── case-examples.md         ← 完整多步骤编排示例（按需加载）
```

| 层级 | 内容 | 加载时机 |
|------|------|---------|
| 元数据 | description + tag | 始终在上下文 |
| SKILL.md 正文 | --help 发现机制 + 意图→指令映射 + 强制规则 + Case 精简索引 + FAQ | Skill 触发时 |
| CLI 自身 | `ones --help` / `ones <模块> --help` / `ones <命令> --help` | 每次触发必探测 |
| references/ | 完整参数、交互流程、认证指南、完整 Case 示例 | 按需读取 |

> 命令的真实参数以 CLI 的 `--help` 为唯一权威来源，SKILL.md 只提供意图路由和强制行为规则。Agent 只需在「查参数」「写操作」「排错」「查看完整编排步骤」时才额外读取 reference 文件。

---

## Step 0: 系统消歧（ONES vs MEP）

美团有两套研发管理系统：ONES（`ones` 命令，本 Skill）和 MEP（`ones2` 命令，ee-mep-ones Skill）。多数用户只用其中一套，通过以下检测避免误触发。

**0.1 检测环境：**

```bash
which ones2
```

- `ones2` **不存在** → 跳过 Step 0，直接进入 Step 1
- `ones2` **存在** → 双 CLI 共存，继续消歧 ↓

**0.2 读取偏好：**

```bash
ones config   # 查看「偏好系统」字段
```

**0.3 按偏好路由：**

| 偏好状态 | 用户意图 | 处理 |
|---------|---------|------|
| 偏好 = ONES | — | 直接进入 Step 1 |
| 偏好 = MEP | — | 告知用户使用 `ones2`（ee-mep-ones Skill），结束 |
| 未设置 | 明确提到 ONES（如 "查ONES需求"、ones.sankuai.com URL） | 执行 `ones config --set-system ONES` 后进入 Step 1 |
| 未设置 | 明确提到 MEP（如 "帮我用MEP查"） | 执行 `ones config --set-system MEP` 后引导到 `ones2` |
| 未设置 | 未指定系统 | 询问用户日常用哪套系统，确认后执行 `ones config --set-system <ONES/MEP>` |

偏好持久化到本地配置文件，跨会话生效，设置一次后不再询问。

---

## Step 1: 指令探测、版本检查与认证（每次触发必做）

ones-cli 频繁更新，先探测可用指令和检查版本，可避免参数变更导致的意外失败。

```bash
# 1.1 探测当前可用指令（⚠️ 必做，作为后续编排的依据）
ones --help
# Agent 必须根据 --help 输出的实际子命令列表来编排指令，
# 不要假设命令存在，以 --help 输出为准。
# 对于不确定参数的子命令，可进一步执行 ones <子命令> --help 查看详细参数。

# 1.2 检查版本是否最新
ones --version
npm view @ee/ones-cli version --registry=http://r.npm.sankuai.com
# 版本不一致 → npm install -g @ee/ones-cli --registry=http://r.npm.sankuai.com

# 1.3 认证（默认策略：先执行，按需认证）
#   token 通常已缓存，Agent 应直接执行目标命令，不要在每次执行前主动走认证步骤。
#   CLI 自动按优先级静默获取凭证：
#     ⓪ MOA 无感登录（CatClaw/CatPaw/CatDesk/Sandbox/1024 等平台自动，无需交互）
#     ① 环境变量 ONES_ACCESS_TOKEN（CI/CD、定时任务）
#     ② 已缓存的 SSO Token（ones sso login 登录过，实际 72h 有效，48h 内免登录）
#     ③ CatPaw 本地降级（自动读取 ~/.catpaw/ 配置）
#   全部不可用时 → 进入认证修复流程（见下方）
```

> **指令探测策略**：`ones --help` 的输出是 Agent 编排指令的唯一权威来源。如果 SKILL.md 速查表中列出了某个命令但 `--help` 输出中不存在，说明当前版本尚未支持，**不要执行该命令**。对于不确定参数的命令，可进一步执行 `ones <子命令> --help` 查看详细参数。
>
> **认证策略（先执行，按需认证）**：
>
> **步骤 A：直接执行目标命令**（如 `ones workbench`、`ones workitem-detail` 等），token 通常已缓存，Agent 不要在每次执行前主动走认证。
> - 成功 → 继续后续流程（无需任何认证操作）
> - 失败（401 / "未登录" / "token expired"）→ 进入步骤 B
>
> **步骤 B：认证修复流程（仅在步骤 A 失败时执行，按顺序尝试）**
>
> | 优先级 | 方式 | 命令 | 说明 |
> |--------|------|------|------|
> | ① | MOA 无感登录 | `ones sso login --moa --mis <misId>` | **CatClaw/CatPaw/CatDesk/Sandbox/1024 等平台首选**，完全自动、非交互式。`--mis` 必传（`--catclaw` 为向后兼容别名） |
> | ② | Token 刷新 | `ones sso refresh` | 使用已保存的 refresh_token 静默续期 |
> | ③ | CIBA 认证 | `ones sso login --ciba --mis <misId> --force` | 大象 App 确认，`--force` 跳过重新登录确认 |
> | ④ | 浏览器 SSO | `ones sso login --browser --force` | 自动打开浏览器完成 SSO，`--force` 跳过重新登录确认 |
> | ⑤ | 手动粘贴 Token | `ones sso login --manual` | **终极兜底**，用户从浏览器复制 Token 粘贴 |
>
> ```
> 命令返回 401 / 未登录
>   ├── ones sso login --moa --mis <misId>
>   │     ├── 成功 → 重试原命令
>   │     └── 失败 ↓
>   ├── ones sso refresh
>   │     ├── 成功 → 重试原命令
>   │     └── 失败 ↓
>   ├── ones sso login --ciba --mis <misId> --force
>   │     ├── 成功 → 重试原命令
>   │     └── 失败 ↓
>   ├── ones sso login --browser --force（浏览器兜底）
>   │     ├── 成功 → 重试原命令
>   │     └── 失败 ↓
>   └── 提示用户手动登录: ones sso login --manual（终极兜底）
>         └── 用户粘贴 Token 后 → 重试原命令
> ```
>
> **`--force` 参数说明**：所有 `sso login` 子命令均支持 `-f / --force`，跳过已登录时的「是否要重新登录？」交互确认，Agent 场景下**必须加 `--force`** 以避免交互阻塞。`sso logout` 同样支持 `--force` 跳过登出确认。
>
> **获取 MIS 号的方式**（按优先级）：
> 1. 从 `ones config` 中读取已保存的 `operator` 字段
> 2. 从沙箱环境上下文获取（如 `USER.md` 或环境变量 `ONES_OPERATOR`）
> 3. 直接询问用户
>
> **MOA 无感登录额外依赖**：MOA 无感登录依赖 `@mtfe/mtsso-auth-official`，CLI 会自动检测并安装。若自动安装失败，执行：`npm install @mtfe/mtsso-auth-official@latest --registry=http://r.npm.sankuai.com`
>
> **Token 时效**：SSO access token 实际有效 72h（3天），CLI 本地 48h 判定过期（留 24h 余量），**48h 内无需二次确认登录**。遇到认证问题读取 [认证指南](./references/auth-guide.md)。
>
> **⚠️ 禁止交互式认证命令**：Agent 场景下所有认证命令**必须**带 `--mis <misId>` 参数，避免产生交互式输入阻塞。**禁止**使用不带 `--mis` 的 `ones sso login --ciba` 或 `ones sso login --moa`。

---

## Step 2: 通过 --help 发现指令（核心机制）

> **一切以当前 CLI 的 `--help` 输出为准。** SKILL.md 不枚举命令参数——命令的真实名称、别名、必填项、参数语义都在 `--help` 中。Agent 必须通过 `--help` 动态发现指令，**不要假设命令或参数存在**，更不要凭记忆构造命令。

### 指令发现三步法

```bash
# ① 顶层指令发现（Step 1.1 已执行 ones --help）
#   输出的每个命令都带 description，深模块带「何时用」意图关键词
#   命令名格式：全名|别名（如 releaseplan|rp、filter-issues|fi、worktime|wt）

# ② 深模块子命令发现（命中深模块后，查其子命令）
ones <模块> --help          # 如 ones releaseplan --help / ones branch --help
#   → 列出该模块所有子命令及参数，子命令 description 含 ⚡ Agent 调用提示

# ③ 单命令参数确认（不确定某命令参数时）
ones <命令> --help          # 如 ones wc --help / ones releaseplan create --help
```

### 意图 → 指令映射（先定位模块，再用 --help 查参数）

> 下表只做意图定位，**具体参数一律以 `ones <命令> --help` 为准**。深模块用法统一为 `ones <模块> <子命令> [参数]`。

| 用户意图关键词 | 指令 / 深模块 | 备注 |
|--------------|--------------|------|
| 查需求/任务/缺陷/bug、我的待办、工作台 | `issues`、`my`、`workbench(wb)`、`filter-issues(fi)` | 基础查询，`-p <空间ID>` |
| DSL 复杂筛选、按人员/时间/迭代/视图查 | `filter-issues(fi)`、`filter-views(fv)` | 详见 [DSL 指南](./references/filter-query-dsl.md) |
| 创建/改/删/详情/评论/父子关联工作项 | `workitem-create(wc)`、`workitem-update(wu)`、`workitem-delete(wd)`、`workitem-detail`、`workitem-comment(wco)`、`workitem-child(wch)`、`workitem-parent(wcp)` | ⚠️ 写操作见下方三大规则 |
| 资产/附件/图片/大象群 | `workitem-asset(wa)`、`workitem-attachment(watt)`、`workitem-image(wimg)`、`workitem-xmgroup(wxg)` | watt delete 强制二次确认 |
| 解析 ONES 链接、获取工作项 URL | `url-parse(up)`、`workitem-url(wurl)` | V2 链接提示用 `ones2` |
| 空间、应用（搜索/添加） | `spaces(sp)`、`space-apps(apps)`、`app-search-*`、`app-add-*` | 添加应用先搜后加 |
| 分支（生成/创建/关联/搜索/反查工作项） | `branch` 深模块 | `ones branch --help` 看子命令 |
| 迭代/冲刺 | `iteration` 深模块 | 子命令：list/create/update/delete/set |
| 工时（填/查/汇总/代填/团队） | `worktime(wt)` 深模块 | `ones worktime --help` 看子命令 |
| 排期（时间/事项/上线时间） | `schedule(sch)` 深模块 | 子命令：query/item-create/item-update/item-delete/time-update |
| 提测/转测 | `submittest` 深模块 | 子命令：detail/create/update/list |
| 测试用例/目录/导入 | `case` 深模块 | `ones case --help` 看子命令 |
| 测试计划 | `plan` 深模块 | 子命令：create/update/search/delete/rounds |
| 测试轮次/执行用例/关联缺陷 | `round` 深模块 | `ones round --help` 看子命令 |
| 发布计划/上线计划 | `releaseplan(rp)` 深模块 | 子命令：list/detail/create/delete/lock/unlock/issues/apps/addable-issues/add-issues/remove-issues |
| 字段（查字段/可选值/成员/可流转状态） | `field-search(fs)`、`field-options(fo)` | 更新/创建必用，见三大规则 |
| 界面方案/必填字段 | `view-scheme(vs)` | 创建工作项前查必填字段 |

> **意图匹配依据**：每个深模块的 `--help` description 都带「何时用：用户提到「…」时」关键词，直接对照用户原话即可定位模块。定位后执行 `ones <模块> --help` 获取子命令，再按子命令的 `⚡ Agent 调用提示` 组装参数。

---

## 指令编排模式（Case 精简索引）

以下索引覆盖常见场景的核心命令。完整的多步骤编排流程见 [完整 Case 示例](./references/case-examples.md)。

核心思路：**先执行 `ones --help` 确认可用指令 → 先查后改 → ID 链式传递**。

| Case | 场景 | 核心命令 | 要点 |
|------|------|---------|------|
| 1 | 查工时 & 补填 | `ones wts` → `ones wtsearch` → `ones wtadd` | 先查汇总找缺填日期，再逐天填写 |
| 2 | 为需求建分支 | `git remote get-url origin` → `ones workitem-detail` → `ones apps` → `ones bg` → `ones bc` | **优先用当前仓库 remote 地址搜索应用**，详情获取空间ID，生成分支名后创建 |
| 3 | 创建需求到迭代 | `ones sp` → `ones vs` → `ones wc` → `ones iter` → `ones si` | 查空间→子类型→创建→查迭代→指派 |
| 4 | 查分支和提测 | `ones workitem-detail` → `ones branch` → `ones st` | 先查详情获取空间ID |
| 5 | 完整测试流程 | `ones plan-c` → `ones round-c` → `ones round-ca` → `ones round-cu` | 计划→轮次→用例→执行 |
| 6 | 改/删工时记录 | `ones wtd` → `ones wtu` / `ones wtdel` | 先查日志获取记录ID |
| 7 | 批量填工时 | `ones wtsearch` → `ones wtadd -d 起~止 -y` | 日期范围 + `-y` 跳过确认 |
| 8 | 创建工作项引导 | `ones sp` → `ones fo` → `ones vs` → `ones fs` → `ones fo` → `ones wc` | ⚠️ 必填字段未填齐会被 CLI 阻断，详见下方说明 |
| 9 | ⚠️ 查我的工作项 | `ones fi --assigned <misId> --state TODO,DOING` | **必须带人员筛选**，[详见策略5](./references/filter-query-dsl.md) |
| 10 | 按时间查开发/上线 | `ones fi -f "...,customField13641,...,customField13200" --json` | 时间字段可能为空，先拉取再做区间计算 |
| 11 | 延期风险分析 | `ones fi -f "...,stateCategory,..." --json` | 按 stateCategory 分层判断风险 |
| 12 | 管理资产/文档 | `ones wa list` → `ones wa add/update/remove` | type 可选: PRD/TD/DESIGN_DRAFT 等 |
| 13 | 创建大象群 | `ones wxg create -i <ID> -t <TYPE>` | 自动幂等检查，已关联则跳过 |
| 14 | 查排期 & 设时间 | `ones sq` → `ones sctu --release-time` | 查排期→修改排期时间字段 |
| 15 | 新建排期事项 | `ones sq` → `ones sic` → `ones siu` | 工作量/时间设在子事项上 |
| 16 | 解析 ONES 链接 | `ones url-parse -u <URL>` → `ones workitem-detail` | V2 URL 提示用 `ones2` |
| 17 | 更新不确定的字段 | `ones workitem-detail` → `ones fs -n "关键词"` → `ones fo` → `ones wu -F` | ⚠️ 必须通过接口查字段详情和可选值，见规则一 |
| 18 | 添加应用到空间 | `ones app-search-server/maven/web/app/dev` → `ones app-add-server/maven/web/app/dev/other` | 先搜索获取应用信息，再添加到空间；添加后用 `ones space-apps` 验证 |
| 19 | 手动录入仓库 | `git remote get-url origin` → `ones app-add-other -p <空间ID> -r <repoUrl>` | 直接通过仓库地址手动录入 OTHER 类型应用 |
| 20 | 导入用例文件 | `ones case-tree -p <空间ID> --list-dirs` → `ones case-import -p <空间ID> --test-set-id <目录ID> -f <文件>` | 先查目录树获取目录ID，再导入（自动验证目录归属） |
| 21 | 管理发布计划 | `ones rp-ls --space <空间ID>` → `ones rp-c` → `ones rp-ai` → `ones rp-i` | 查列表→建计划→添加工作项（须有关联分支）→查计划内工作项 |

> **关键提示**：
> - **⛔ Case 8 创建工作项必填字段校验**：`ones wc` 会在创建前自动查询子类型界面方案（CREATE_VIEW），提取所有 `required=true` 的必填字段并校验。**如果存在未填的必填字段，CLI 会直接阻断创建并一次性列出所有缺失字段**（含 variable、type、id 和补充方式）。Agent 收到阻断信息后：
>   1. **不要重试相同的命令** — 必须先补齐缺失字段再执行
>   2. **根据 CLI 输出的缺失清单**，逐个补充：CLI 参数可覆盖的（如 `--assigned`、`--desc`）直接加参数；其他字段通过 `-F / --field` 传入
>   3. **字段可选值获取**：`ones fo -p <空间ID> -f <字段ID> -t <字段类型>` 查询可选值，不要猜测
>   4. **如果界面方案查询本身失败**（网络/权限问题），CLI 同样会阻断，此时应提示用户检查空间 ID、子类型 ID 和权限
>   5. **面向用户的提示**：告知用户「该空间的子类型要求必须填写 XX、YY 等字段，请提供这些信息后再创建」，而不是静默跳过
> - Case 9 **「与我相关」查询必须带人员筛选**，查不到禁止去掉 `--assigned` 重试。详细规则见 [DSL 筛选指南 - 策略 5](./references/filter-query-dsl.md)
> - Case 9/10/11 相关的**全局字段 variable（所有空间通用，无需查询）**：时间字段 `customField13641`(预计开发开始)、`customField13642`(预计开发结束)、`customField11681`(预计提测)、`customField13200`(预计上线)；人员角色字段 `customField13161`(产品主R)、`customField24214`(技术主R，DSL 别名 `rdMasters`)、`customField24215`(测试主R)、`developer`(开发人员，DSL 别名 `developers`)。人员组件类型统一为 `component_user`，ONES 中**不存在** `component_container_user` 类型
> - Case 16 若 URL 为 V2 格式（含 `app/ones/space/`），命令会中止并提示使用 `ones2`

---

## ⛔ Agent 交互式命令禁令（违反即严重错误）

> **Agent 场景下严禁使用任何交互式命令。** 所有操作必须通过非交互式参数一次性传入，不允许依赖 stdin 交互输入。

### 交互式 vs 非交互式命令对照表

| 操作 | ❌ 交互式（Agent 禁用） | ✅ 非交互式（Agent 必须使用） |
|------|------------------------|------------------------------|
| 创建工作项 | `ones wc -t 需求`（会触发空间/子类型选择交互） | `ones wc -t REQUIREMENT -p <空间ID> -s <子类型ID> --priority 中 --name "标题" -y` |
| 更新工作项 | `ones wu -i <ID>`（缺参数时等待输入） | `ones wu -i <ID> --priority 高 -y` 或 `ones wu -i <ID> -F '<JSON>' -y` |
| 工作台检索 | `ones search`（交互式选择） | `ones search --no-interactive --json` |
| 空间内检索 | `ones space-search -p <ID>`（交互式） | `ones ss -p <ID> --no-interactive --json` |
| 创建迭代 | `ones ci`（逐步引导填写） | `ones ci -p <空间ID> -n "名称" -s 2026-04-01 -e 2026-04-15 -y` |
| 填写工时 | `ones wtadd`（交互输入） | `ones wtadd -i <ID> --hours 8 -d 2026-04-13 -y` |
| 创建分支 | `ones bc -i <ID>`（交互选择应用） | `ones bc -i <ID> -a <应用ID> [-t feature] [-b master] -y`（**优先用当前仓库 remote 地址**：`git remote get-url origin` → 将完整地址直接传入 `ones apps -p <空间ID> -n <remote地址>` 获取 `id`；不在 git 仓库中时再询问用户；**搜索无结果禁止换关键词重试**，应询问用户提供准确的仓库名或 appkey） |
| 创建提测单 | `ones stc`（交互式引导） | `ones stc -p <空间ID> --title "标题" -y` |
| 删除操作 | `ones wd -i <ID>`（等待确认） | `ones wd -i <ID> -y` |
| 用例搜索 | `ones case-ss -p <ID>`（交互式） | `ones case-ss -p <ID> --no-interactive --json` |
| 创建用例 | `ones case-c`（交互选空间/子类型/字段） | `ones case-c -p <空间ID> --title "标题" --priority 中 -y` |
| 更新用例 | `ones case-u -i <ID>`（交互选字段/输入值） | `ones case-u -i <ID> -f 优先级 --val 高 -y` |
| 创建测试计划 | `ones plan-c`（交互选场景/空间/标题） | `ones plan-c -c REQUIREMENT -p <空间ID> --title "标题" -y` |
| 更新测试计划 | `ones plan-u`（交互选字段/输入值） | `ones plan-u -i <ID> -p <空间ID> -f 标题 --val "新标题" -y` |
| 添加轮次用例 | `ones round-ca`（交互选用例） | `ones round-ca -p <空间ID> -r <轮次ID> --plan-id <计划ID> -a ADD --case-ids "ID1,ID2" -y` |
| 更新执行用例状态 | `ones round-cu`（交互选用例/状态） | `ones round-cu -p <空间ID> -r <轮次ID> -s SUCCESS --items "执行ID:用例ID" -y` |
| 更新执行用例执行人 | `ones round-ce`（交互选用例/执行人） | `ones round-ce -r <轮次ID> --items "用例ID:MIS号" -y` |
| 更新提测状态 | `ones stu`（交互选状态） | `ones stu -p <空间ID> -i <提测单ID> -s "已准入" -y` |
| 导入用例 | `ones case-import`（缺参数报错） | `ones case-import -p <空间ID> --test-set-id <目录ID> -f <文件路径> [--mode 1]` |

**关键原则**：
1. 所有写操作（创建/更新/删除）**必须加 `-y / --yes`** 跳过确认
2. 所有搜索/检索命令**必须加 `--no-interactive --json`**（如支持）
3. 所有必填参数**必须通过命令行参数一次性传入**，不允许依赖交互式 prompt
4. 分支创建需要 `-a <应用ID>` 避免交互选择（**优先用当前仓库 remote 地址**：执行 `git remote get-url origin` 获取完整仓库地址，直接将完整地址传入 `ones apps -p <空间ID> -n <remote地址>` 搜索获取；**若当前不在 git 仓库中或无 remote，再询问用户提供仓库名/appkey**；**若搜索无结果，禁止自行更换关键词重试，应立即询问用户提供准确的仓库名 repoName 或 appkey**）
5. 附件删除（`watt delete`）**强制二次确认且无法跳过**，不适合 Agent 自动化

---

## ⛔ Agent 写操作三大强制规则（违反即严重错误）

### 规则一：更新操作 — 必须通过接口查字段详情和可选值，严禁猜测

> **更新工作项时，Agent 必须先通过字段查询接口定位用户描述的字段（获取 variable、type、id），再通过字段下拉接口获取可选值，更新的值必须使用接口返回的 `value` 而非用户描述的文本。Agent 绝对不允许让用户提供字段 variable、字段 ID 或字段 value 等技术参数。**

**⚠️ 核心原则：用户只需要说"帮我改状态"，Agent 负责通过接口查到一切技术细节。**

用户说的是自然语言（如"状态"、"优先级"、"归属模块"），Agent 必须自己通过以下步骤将自然语言映射到技术参数，**不允许反问用户"请提供字段 variable / 字段 ID / 字段类型 / 可选值"**。

**强制流程**：

```
用户说"把状态改成已完成"（或任意字段更新意图）
  │
  ├── Step 1: 查工作项详情 → ones workitem-detail -i <工作项ID> --json
  │           → 获取空间 ID（projectId）和工作项类型（type）
  │
  ├── Step 2: 定位用户描述的字段（⚠️ 必做，不允许跳过）
  │   ├── 如果是内置快捷字段（priority/assigned/name/desc）→ 直接使用对应 CLI 参数
  │   └── 如果不确定字段的 variable / type / id → 用关键词查字段元信息：
  │           ones fs -p <空间ID> -t <工作项类型> -n "状态" --json
  │           → 返回: [{variable: "state", type: "component_state", id: 2368, name: "状态"}, ...]
  │           → 从结果中匹配用户描述的字段，获取 variable、type、id
  │
  ├── Step 3: 查询该字段的可选值（⚠️ 必做，不允许跳过）
  │           ones fo -p <空间ID> -f <字段ID> -t <字段类型> --json
  │           → 特殊：状态字段(component_state)需加 -i <工作项ID> 获取可流转状态
  │           → 返回: [{"value": "xxx", "displayValue": "已完成"}, ...]
  │
  ├── Step 4: 匹配用户描述 → "已完成" 对应 value="xxx"（取 value，不取 displayValue）
  │
  └── Step 5: 使用接口返回的 value 执行更新
              → ones wu -i <ID> -F '{"variable":"state","name":"状态","type":"component_state","multiple":false,"fieldValue":"xxx"}' -y
              → 或内置字段：ones wu -i <ID> --priority 3 -y
```

**常见字段定位参考**（Agent 遇到以下用户描述时应查询对应字段）：

| 用户可能的描述 | 字段关键词（用于 `ones fs -n`） | 备注 |
|--------------|-------------------------------|------|
| 改状态、流转状态、改成已完成 | `状态` | type=`component_state`，需加 `-i <工作项ID>` 查可流转状态 |
| 改优先级 | `优先级` | 内置字段 `--priority`，但仍需查可选值确认 |
| 改指派人、转给XX | `指派` | 内置字段 `--assigned`，值为 MIS 号 |
| 改子类型 | `子类型` | type=`component_subtype` |
| 改归属模块 | `模块` 或 `归属` | 自定义字段，必须查 |
| 改标签 | `标签` | 可能是 `list` 或自定义组件 |
| 改预计工时、工作量 | `工作量` 或 `预计工时` | 自定义字段，可能是数值型 |
| 改截止时间 | `截止` | 自定义时间字段 |

**完整编排示例**：

```bash
# Step 1: 查询工作项详情，获取空间ID、工作项类型和当前字段值
ones workitem-detail -i <工作项ID> --json

# Step 2: 通过关键词查字段元信息（获取 variable、type、id）
# ⚠️ 不确定字段 variable 时必须查询，不允许猜测或让用户提供
ones fs -p <空间ID> -t <工作项类型> -n "用户描述的字段关键词" --json

# Step 3: 查询字段可选值（所有下拉/枚举/状态类字段必须查询）
ones fo -p <空间ID> -f <字段ID> -t <字段类型> --json
# 状态字段特殊：需要加 -i <工作项ID> 获取当前可流转的目标状态
ones fo -p <空间ID> -f <字段ID> -t component_state -i <工作项ID> --json

# Step 4: 从返回值中匹配用户描述，取 value 字段
# ⚠️ 严禁使用 displayValue，必须使用 value

# Step 5: 执行更新
ones wu -i <工作项ID> -F '{"variable":"<variable>","name":"<name>","type":"<type>","multiple":false,"fieldValue":"<value>"}' -y
```

**⛔ 绝对禁止**：
- **让用户提供字段的 variable、id、type 等技术参数**（用户不知道也不应该知道）
- **让用户猜测字段可选值**（必须通过 `ones fo` 接口查询）
- 直接用用户描述的文本（如"高"、"紧急"、"已完成"）作为更新值
- 猜测字段的 value 值而不查询接口
- 使用 `displayValue` 而非 `value`
- 跳过字段查询和可选值查询直接更新
- 在字段查询失败时放弃，而不是尝试不同的搜索关键词

### 规则二：创建操作 — 必须携带 interfaceType（界面方案类型）

> **创建工作项时，Agent 必须明确使用哪种创建界面方案来确定必填字段和字段校验规则。**

ONES 系统有两种创建界面方案：
- `QUICK_CREATE_VIEW`：快捷创建界面，字段较少，配合 `fastIssue` 接口
- `CREATE_VIEW`：完整创建界面，字段完整，配合 `issue` 接口

**CLI 当前行为**：`ones wc` 命令使用 `CREATE_VIEW` 完整创建界面，会自动校验该界面方案下所有必填字段。

**强制流程**：

```
创建工作项
  ├── Step 1: 查询空间列表 → ones sp -n "关键词" --json
  ├── Step 2: 查询界面方案（确认必填字段）
  │           → ones vs -p <空间ID> -s <子类型ID> --json
  │           返回的字段列表中 required=true 的即为必填字段
  ├── Step 3: 对每个必填的下拉/枚举字段，查询可选值
  │           → ones fo -p <空间ID> -f <字段ID> -t <字段类型> --json
  ├── Step 4: 组装完整参数（包含所有必填字段），一次性创建
  │           → ones wc -t <类型> -p <空间ID> -s <子类型ID> --priority <值> --name "标题" \
  │             -F '<字段1 JSON>' -F '<字段2 JSON>' -y
  └── Step 5: 如果 CLI 阻断报缺失字段 → 按缺失清单补齐后重新执行
```

**⛔ 绝对禁止**：
- 不查询界面方案就直接创建（会被 CLI 阻断）
- 忽略界面方案中的必填字段
- 跳过字段可选值查询，猜测字段取值

### 规则三：查询操作 — 未封装的字段值必须前置查询

> **当用户查询的条件涉及 CLI 未直接封装的字段（如自定义字段、状态名称、子类型等），Agent 必须先通过字段接口查询该字段的可选值，再使用接口返回的 `value` 构建查询条件。**

**判断逻辑**：

```
用户查询条件
  ├── 已封装为 CLI 参数的字段（直接使用）
  │   ├── --priority（优先级）→ 直接传 低/中/高/紧急 或 1/2/3/4
  │   ├── --assigned（指派给）→ 直接传 MIS 号
  │   ├── --state（状态名称）→ 直接传状态名，CLI 自动匹配
  │   ├── -n（标题关键词）→ 直接传关键词
  │   └── -i（迭代 ID）→ 直接传迭代 ID
  │
  └── 未封装的自定义字段（必须前置查询）
      ├── Step 1: ones fs -p <空间ID> -n "字段关键词" --json  → 获取字段 variable、type、id
      ├── Step 2: ones fo -p <空间ID> -f <字段ID> -t <字段类型> --json  → 获取可选值
      ├── Step 3: 匹配用户描述 → 取 value
      └── Step 4: 构建 DSL 查询
          ones fi -p <空间ID> --query '[{"field":"<variable>","type":"TERM","value":"<value>"}]' --json
```

**常见需前置查询的场景**：

| 场景 | 前置查询命令 | 说明 |
|------|-------------|------|
| 按子类型筛选 | `ones vs -p <空间ID> -s <子类型ID>` | 获取子类型 ID |
| 按自定义下拉字段筛选 | `ones fo -p <空间ID> -f <字段ID> -t <字段类型> --json` | 获取可选值的 value |
| 按状态流转 | `ones fo -p <空间ID> -f <状态字段ID> -t component_state -i <工作项ID> --json` | 获取可流转的目标状态 |
| 按迭代筛选 | `ones iter -p <空间ID> --json` | 获取迭代 ID |
| 按人员角色筛选 | `ones fo -p <空间ID> -f <角色字段ID> -t component_user --json` | 获取人员 MIS |

**⛔ 绝对禁止**：
- 猜测自定义字段的 value 构建查询条件
- 不查询就直接用用户描述的文本作为筛选值
- 跳过字段可选值查询直接构造 DSL

---

## 编排原则

> **⛔ 严禁直接调用 CLI 内部 API / 源码**
>
> Agent **只允许通过终端执行 `ones` 命令行指令**来操作 ONES 系统。**绝对禁止**以下行为：
> - 读取 ones-cli 的源码（`src/api/`、`src/commands/`、`src/utils/` 等）后直接调用内部函数或 API
> - 绕过 CLI 命令，直接向 ONES 后端发送 HTTP 请求（如直接 `curl` ones.sankuai.com 的内部接口）
> - 通过 `require()`/`import` 引入 ones-cli 的模块来执行操作
> - 从源码中提取接口路径、请求格式等信息后自行构造请求
>
> ones-cli 的源码仅用于 CLI 自身的开发和维护，**不是** Agent 的操作接口。所有操作必须且只能通过 `ones <子命令>` 命令行完成。

1. **先探测可用指令** — 每次触发必先执行 `ones --help`，根据实际输出的子命令列表来编排指令，**不假设命令存在**；对不确定参数的子命令执行 `ones <子命令> --help` 确认
2. **先查后改** — ONES 系统 ID 无法猜测，写操作前必须先查询获取 ID
3. **ID 链式传递** — 前一个命令输出的 ID 作为下一个命令的输入
4. **`--json`** — 需要程序化解析字段值时使用
5. **`-y`** — 批量操作或自动化时跳过确认，避免交互阻塞
6. **`--no-interactive`** — 搜索/检索命令使用此参数避免交互阻塞
7. **`--help`** — 不确定参数时查看帮助
8. **按需加载 reference** — 只在需要时读取，不要一次性全部加载
9. **⛔ 空间权限前置校验** — CLI 在**所有涉及空间的操作（尤其是创建、更新、删除等写操作）开始时**，会立即校验用户是否有目标空间的权限，无权限时直接阻断，不继续执行后续逻辑（如字段校验、界面方案查询等）。Agent 编排时应遵循：
   - **创建工作项**：`wc` 命令在参数解析后、字段校验和界面方案查询之前，会前置调用 `assertSpacePermission` 校验空间权限，无权限直接退出
   - **更新工作项**：`wu` 命令在解析工作项 ID 后，会先查询工作项详情获取所属空间并校验权限，无权限直接退出，不会进入字段校验和预计工作量换算等重操作
   - **查询/删除/迭代/分支等操作**：服务层方法已在调用前校验空间权限
   - 若遇到「无权限操作空间」或「操作被阻断」错误，**不应重试或绕过**，应提示用户：① 确认空间 ID 是否正确（`ones spaces` 查看有权限的空间）；② 联系 ONES 管理员申请加入空间
10. **人员标识使用 MIS 号** — ONES 系统中所有涉及人员的参数（如 `--assigned`、`--operator`、`--users`、`--owner`、`--admins` 等）必须使用用户的 **MIS 号**。MIS 号由用户的中文名称（或英文名称，如海外员工）加上重名数字 ID 组成（如 `zhangsan02`）；如果没有重名则没有后面的数字 ID，就是纯中文或纯英文（如 `zhangsan`、`JohnSmith`）。**不能使用中文姓名或者纯数字id作为参数值**，必须转换为对应的 MIS 号
11. **「与我相关」查询必须带人员筛选** — 当用户描述的意图涉及「自己的工作项」（如「我的需求」、「我在做的任务」、「帮我查查要开发什么」、「我的待办」等），查询条件中**必须**包含当前用户的人员筛选（`--assigned <misId>` 或 DSL 中 `assigned`/`customField24214`(技术主R)/`developer`(开发人员) 等字段）。如果筛选后结果为空，**不要自行扩大搜索范围或去掉人员筛选条件**，而是直接告诉用户「在当前筛选条件（指派给/技术主R/开发人员为您的 MIS）下，未找到匹配的工作项」，让用户自行决定是否调整筛选条件
12. **⛔ 创建工作项必填字段不可跳过** — `ones wc` 创建前会强制校验子类型界面方案的必填字段，缺失任何必填字段都会被阻断（`exit 1`）。Agent 遇到阻断后必须根据 CLI 输出的缺失字段清单补齐所有必填字段，然后重新执行；**禁止绕过校验或忽略缺失字段直接调用后端接口**。如果是交互式场景，应将缺失字段列表展示给用户并询问对应的值
13. **字段取值规则** — 创建/更新工作项通过 `-F` 传入自定义字段时：① 下拉字段取 `value` 而非 `displayValue`；② **级联字段（cascader）只能选最末级节点，各层 value 用 `^` 拼接**（如 `"1^2^3"`），CLI 会自动调用 `field-options` 接口获取可选值树，**校验传入的值是否在可选值范围内且为末级节点**，不合法时会阻断并列出当前层级的合法可选值；③ 组织类字段（`component_new_org`）需用户提供完整部门链（可从**大象个人名片**中查找，如：美团/行政/行政BP中心），通过 `getOrgByPath` 接口获取组织 ID 后填入；④ **⛔ 分类字段必填时禁止选「未分类」** — 若界面方案中分类字段（如「需求分类」「缺陷分类」等 cascader 类型字段）设置为必填（`required=true`），则创建和更新时**不允许选择「未分类」**作为值。Agent 必须通过 `ones fo` 查询该字段可选值树，引导用户从实际的分类节点中选取末级节点，而不是传「未分类」或空值。详见 [写操作参数 - 字段取值规则](./references/interactive-params.md)
14. **`space-apps` 默认使用当前仓库 remote 地址查询** — 当需要搜索空间应用（获取应用 ID）时，Agent 应**优先自动获取当前工作区 git remote 地址**作为 `-n` 参数：① 执行 `git remote get-url origin`；② 将返回的完整地址直接作为 `-n` 参数传入（如 `ones apps -p <空间ID> -n "ssh://git@git.sankuai.com/ee/ones-cli.git"`），无需提取仓库名。**降级逻辑**：若 `git remote get-url origin` 失败（不在 git 仓库 / 无 remote），再询问用户提供仓库名或 appkey
15. **字段全局唯一** — ONES 中的字段 variable（如 `customField24214`、`developer`）**全局唯一、所有空间通用**，不因空间不同而变化。常用人员角色字段：产品主R=`customField13161`、技术主R=`customField24214`、测试主R=`customField24215`、开发人员=`developer`，这些可直接使用无需查询。人员组件类型统一为 `component_user`

---

## 常见问题速查

| 问题 | 解决 |
|------|------|
| `command not found: ones` | `npm i -g @ee/ones-cli --registry=http://r.npm.sankuai.com` |
| 401 / 认证失败 | 按顺序尝试：① `ones sso login --moa --mis <MIS>` → ② `ones sso refresh` → ③ `ones sso login --ciba --mis <MIS> --force` → ④ `ones sso login --browser --force` → ⑤ 提示用户 `ones sso login --manual`；CI/CD 场景确认 `ONES_ACCESS_TOKEN` 已设置，详见 [认证指南](./references/auth-guide.md) |
| 无权限操作该空间 / 操作被阻断 | CLI 在操作开始时前置校验空间权限，无权限直接阻断。确认空间 ID 是否正确（`ones sp -n "关键词"` 查看自己有权限的空间）；若空间正确则联系 ONES 管理员申请加入。**不要重试或绕过** |
| 不知道空间 ID | `ones sp -n "关键词"` 搜索，或使用 `ones up -u <URL>` 从 ONES URL 中自动解析 |
| 收到 ONES 链接想知道是什么 | `ones up -u "<链接"` 解析出空间 ID / 工作项 ID / 类型，然后用 `ones workitem-detail -i <ID>` 查详情 |
| 不知道命令参数 | `ones <命令> --help`，或读取 [命令速查](./references/command-reference.md) |
| 删除不可恢复 | 所有 delete 操作不可撤销，务必先确认 |
| 子类型更新报错 | 子类型只能更新为相同工作项类型下的合法子类型 |
| 工时记录 ID 怎么获取 | `ones wtd -i <工作项ID>` 查询工时日志 |
| 工时校验不通过 | 检查空间是否要求填写投入类型，或日期是否在允许范围内 |

---

## References

按需加载，不要一次性全部读取：

| 文件 | 加载时机 |
|------|---------|
| [命令参数速查](./references/command-reference.md) | `--help` 输出仍不够详细时 |
| [写操作参数](./references/interactive-params.md) | 创建/更新/删除前确认必填参数 |
| [认证排错](./references/auth-guide.md) | 401、Token 过期、登录失败、环境变量 / CatPaw 降级认证 |
| [DSL 筛选指南](./references/filter-query-dsl.md) | 使用 `ones fi` 构建复杂筛选；「与我相关查询」规则（策略 5） |
| [完整 Case 示例](./references/case-examples.md) | 上方精简索引不够详细时，查看完整的多步骤编排示例 |

**外部资源：** [ONES 系统](https://ones.sankuai.com) · [CIBA 认证文档](https://km.sankuai.com/collabpage/2732221228) · [内部 npm 源](http://r.npm.sankuai.com)
