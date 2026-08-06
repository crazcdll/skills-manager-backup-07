---
name: mcm-cli
description: "MCM 变更管理平台命令行工具的 AI 使用指南。当用户询问变更计划、变更管理、MCM 平台相关问题，或需要查询/分析/创建/更新/执行变更计划、模板、团队变更情况时使用。支持的操作包括：(1) 查询变更计划列表和详情，(2) 查看我的/团队的变更计划，(3) 搜索和筛选计划，(4) 查看计划步骤和进展，(5) 查询变更模板，(6) 变更日历查询，(7) 创建/更新变更计划草稿，(8) 校验变更计划草稿，(9) 创建/更新变更模板，(10) 提交变更计划，(11) 执行变更计划步骤，(12) 复制变更计划，(13) 变更后服务状态检查，(14) 查看历史变更经验，(15) 查询变更事件列表，(16) 查询变更事件详情，(17) 查询变更详情，(18) 变更审批操作（通过/驳回/跳过审批），(19) CloudTrail 追溯事件查询（按服务/操作人/部门/时间范围查询全平台变更记录），(20) 追溯事件详情查询，(21) 按部门/团队追溯变更事件，(22) 获取当前用户信息（含 orgPath）。触发词：MCM、变更计划、变更管理、变更模板、待审核计划、计划驳回、变更日历、计划状态、创建变更、创建计划、创建模板、提交变更、提交计划、执行变更、发布步骤、变更步骤、复制计划、再发变更、发布后验证、变更经验、发布服务、上线发布、发布计划、服务发布、线上发布、灰度发布、部署发布、变更事件、事件详情、变更审批、审批通过、驳回变更、跳过审批、待我处理的变更、变更列表搜索、CloudTrail、追溯事件、变更追溯、变更记录查询、按服务查变更、操作人变更记录、appkey变更历史、我的团队变更、团队变更、部门变更、组织变更、查我们团队。不用于：纯代码审查、架构设计、非MCM平台的变更单查询等非变更操作。"
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - c1e095b546
    prompt: 本技能所需的 user_access_token 占位符，请参考 mtsso-skills-official 的相关说明进行获取和注入
    
tags: [“MWS云管”, “MCM”, “变更计划”]
space: “mws”
logo: “mws-official”

metadata:
  skillhub.creator: "jie.li.sh"
  skillhub.updater: "liyuang"
  skillhub.version: "V21"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3708"
---

# MCM 命令行工具使用指南

mcm-cli 是 MCM（变更管理平台）的命令行工具，默认输出 JSON 格式，所有命令通过全局 `mcm` 命令调用。

## 前置条件

### 第一步：检查并安装/更新 mcm-cli
**仅在对话中首次使用 mcm 命令前**，检查并更新到最新版本：

```bash
mcm --version                                                          # 检查版本（版本 < 0.1.34 或未安装**：**必须立即安装或更新到最新版本**后再继续，否则核心AI功能不可用）
npm install -g @dp/mcm-cli@latest --registry=http://r.npm.sankuai.com  # 安装/更新到最新版（需美团内网）
```
> 如果 node/npm 未安装或版本过低，提示用户先安装/升级 Node.js（推荐通过 nvm 管理）。

### 第二步：认证（支持自动无感登录）
```bash
mcm whoami  # 先检查认证状态，已认证则跳过登录
```

若 `mcm whoami` 返回认证状态为**已认证**，**直接跳过登录步骤**，继续执行后续命令。

若未认证或 token 已过期，按以下顺序尝试登录：

**步骤一（必须先执行，不可跳过）：无感换票登录**

> ⚠️ **必须先读取并执行 `mtsso-skills-official` skill，通过 MOA 换取用户身份票据后再登录，不可直接跳到步骤二。**

```bash
mcm login --token "${user_access_token}"   # ${user_access_token} 须由 mtsso-skills-official 换票后替换为真实 token
```

**步骤二（仅在步骤一失败时回退）：CIBA 手动登录**

> 步骤一失败的判断标准：`mtsso-skills-official` 不存在或执行报错，或换票后 token 为空。

```bash
mcm login --mis <MIS>
```

## ⚡ 路由决策：`mcm` 命令 vs `mcm ai`

**这是最关键的判断**：用户的请求，到底走哪条路？

| 请求类型 | 路由 | 理由 |
|------|------|------|
| **变更计划查询**：list、my、detail、search、calendar、count、progress、steps、notice-preview | 路径二：`mcm` 子命令 | 结果确定、结构化、秒级返回，无需 AI 推理 |
| **变更事件查询与审批**：event list、event detail、event get、event accept、event reject、event skip-audit | 路径二：`mcm` 子命令 | 参数明确，直接调用更可靠 |
| **CloudTrail 追溯查询**：cloudtrail list、cloudtrail detail | 路径二：`mcm` 子命令 | 参数明确，直接调用更可靠 |
| **变更模板查询**：template list、detail、preview、history、used | 路径二：`mcm` 子命令 | 同上 |
| **变更模板写操作**：template create、update | 路径二：`mcm` 子命令 | 字段固定，参数明确，直接调用更可靠 |
| **认证相关**：login、whoami、refresh、logout | 通用命令，不涉及路径 | CLI 基础能力 |
| **用户信息查询**：user my | 路径二：`mcm` 子命令 | 结果确定、结构化，无需 AI 推理；orgPath 供后续模板查询使用 |
| **校验变更计划草稿**：validate | 路径二：`mcm` 子命令 | 参数明确（传入 JSON 即可），无需 AI 推理 |
| **提交变更计划**：submit | 路径二：`mcm` 子命令 | 参数明确（仅需计划 ID），无需 AI 推理 |
| **审核通过变更计划**：approve | 路径二：`mcm` 子命令 | 参数明确（计划 ID），无需 AI 推理 |
| **审核驳回变更计划**：reject | 路径二：`mcm` 子命令 | 参数明确（计划 ID），无需 AI 推理 |
| **删除变更计划草稿**：delete | 路径二：`mcm` 子命令 | 参数明确（仅需 ID），命令已内置状态检查和权限校验，无需 AI 推理 |
| **撤销变更计划**：revoke | 路径二：`mcm` 子命令 | 参数明确（仅需计划 ID），命令内置状态校验，适用于 AUDITING/WAIT_RUNNING/RUNNING 状态，AI 需在调用前向用户确认 |
| **重建变更计划**：rebuild | 路径二：`mcm` 子命令 | 参数明确（仅需计划 ID），适用于 STOPPED/REJECTED 状态，AI 需在调用前向用户确认 |
| **创建/复制/编辑变更计划** | 路径一：`mcm ai` | 需跨工具收集上下文（PR diff、appkey、历史计划），多步推理组装字段 |
| **启动/执行变更计划步骤** | 路径一：`mcm ai` | 需要理解计划上下文、判断前置条件、顺序推进，不得手动逐步调用 |
| **发布**（"上线"、"灰度发布"等直接表达发布意图） | 路径一：`mcm ai` | 本质是创建并执行变更计划；**有计划 ID 时直接执行**，无计划 ID 时先创建再执行 |
| **变更后服务状态检查** | 路径一：`mcm ai` | 需跨系统查询并综合判断 |
| **查看变更经验/最佳实践** | 路径一：`mcm ai` | 知识检索与推理 |

> **简单记忆**：**查询、模板写操作、校验/提交/删除草稿走 `mcm` 子命令；变更计划的创建/编辑/启动/执行步骤操作必须走 `mcm ai`。**

---

## 路径一：`mcm ai`（创建/编辑/执行/经验查询）

将用户的完整原始输入原样作为 `question` 传入 `mcm ai`，由服务端 Agent 处理。

### `mcm ai` 命令参考

> 完整文档参考 [references/command-reference.md](references/command-reference.md)

| 命令 | 功能 |
|------|------|
| `mcm ai "<question>"` | 流式问答；不加 `-s` 自动续接最近未过期会话，加 `-s <sessionId>` 指定会话；明确当前 Agent 时须加 `--byAgent <agent名称>`（常见：CatClaw/CatDesk/CatPaw） |
| `mcm ai sync "<question>"` | 同步问答（等待完整 JSON 结果，适合脚本集成）；明确当前 Agent 时须加 `--byAgent <agent名称>`（常见：CatClaw/CatDesk/CatPaw） |
| `mcm ai sessions` | 查询所有活跃会话（24小时内） |
| `mcm ai stop <sessionId>` | 停止会话（中止 AI 推理） |
| `mcm ai reconnect <sessionId>` | 重连当前轮次（仅用于本轮 SSE 中断；若本轮已正常结束则无内容可回放，sessionId 仍可继续用于下一轮对话） |
| `mcm ai answer <sessionId> -e <eventId> -r '<json>'` | 提交 AI 交互问题的回答 |
| `mcm ai resume <sessionId>` | 恢复 Agent 执行（仅用于 ask_question 事件后，内部自动 reconnect 接收后续输出） |

> ⚠️ `--debug` 参数仅用于**故障排查**，会打印服务端原始 SSE 数据，正常使用无需开启。

### 流式执行规范

`mcm ai` **直接前台运行**，实时流式输出 AI 内容，进程退出即为完成：

执行过程中可能出现以下几种情况：

- **正常输出**：AI 实时流式输出内容，`✓ 执行完成` 后进程自动退出
- **遇到 `❓ AI 需要你回答以下问题`**：进程已退出，展示问题和选项，按提示执行 `answer` + `resume` 后继续（仅限 ask_question 场景）
- **进程被 SIGTERM 中断**（Ctrl+C、网络中断）、2~3 秒退出无实质输出、或其他异常退出：先按 Session 管理规则处理；若确认非 session 问题，再参考错误排查表

> ⚠️ **禁止后台运行 + sleep + 读 log**：`mcm ai` 是流式前台命令，直接运行即可实时看到输出，无需任何 sleep / tail / log 轮询。
> ⚠️ 不得主动清空 `~/.mcm/ai-session-history.json`（会破坏其他会话）。

### 多轮对话

直接连续发问即可，无需手动管理 sessionId：

```bash
mcm ai "基于这个 PR 创建变更计划 https://..."
mcm ai "发布时间改成下午 3 点"
mcm ai "第一步怎么执行？"
mcm ai "执行第二步" --plan-id 12345   # 已知计划 ID 时必须携带 --plan-id
```

每次不传 `-s` 时，自动续接本地保存的最近一个未过期会话（24小时有效）。`-s` 的使用规则见 Session 管理规则。

> ⚠️ **`--plan-id` 强制携带规则**：只要已知变更计划 ID，执行任何对该计划的操作时**必须**携带 `--plan-id <planId>`，不得省略。这既保证了会话能正确续接到该计划绑定的上下文，也让服务端 Agent 明确知道操作对象。操作不同计划时各自带上对应的 `--plan-id` 即可，会话会自动隔离。

其他操作：
- **交互回答**：AI 提问展示问题和选项 → 执行 `mcm ai answer` 提交选择 → `mcm ai resume` 恢复 Agent 执行（仅限 ask_question 场景）
- **断线重连**：见 Session 管理规则
- **停止**：`mcm ai stop <sessionId>`

### 常见场景

| 场景 | 用户输入示例 | 执行命令 |
|------|------|--------|
| 发布（有计划 ID） | "帮我发布计划 12345" / "执行变更计划 12345" | `mcm ai "帮我发布变更计划 12345" --plan-id 12345`（自动续接 planId=12345 的最新会话） |
| 发布（无计划 ID，需先创建） | "帮我上线 xxx" / "灰度发布" | 先 `mcm ai "基于 xxx 创建变更计划"` 拿到计划 ID，再 `mcm ai "执行变更计划" --plan-id <planId>`（续接该计划绑定的会话） |
| 基于 PR 创建变更计划 | "帮我基于这个 PR 创建变更计划 https://..." | `mcm ai "帮我基于这个 PR 创建变更计划 https://..."` |
| 基于 ONES/MEP 工作项创建 | "基于工作项 https://ones.sankuai.com/... 创建变更计划" | `mcm ai "基于工作项 https://ones.sankuai.com/... 创建变更计划"` |
| 复制变更计划 | "复制这个变更计划，下午 3 点发" | `mcm ai "复制这个变更计划，下午 3 点发"` |
| 合并 PR 到已有草稿 | "把这个 PR https://... 合并到 MCM 草稿 https://..." | `mcm ai "把这个 PR https://... 合并到 MCM 草稿 https://..."` |
| 执行与推进 | "变更计划已创建，第一步怎么做？" | `mcm ai "变更计划已创建，第一步怎么做？" --plan-id <planId>`（已知计划 ID 时必须携带） |
| 进度查询（上下文相关） | "上次创建的变更计划现在在哪一步？" | `mcm ai "上次创建的变更计划现在在哪一步？"`（需结合会话上下文，走 `mcm ai`）|
| 变更后服务验证 | "帮我检查一下服务 com.sankuai.xxx 的状态" | `mcm ai "帮我检查一下服务 com.sankuai.xxx 的状态"` |
| 查看变更经验 | "查看 PLUS 发布的最佳实践" | `mcm ai "查看 PLUS 发布的最佳实践"` |
| 脚本集成 | 需要结构化 JSON 数据输出 | `mcm ai sync "<用户原始输入>"`（同步模式） |
| 复杂交互 | 需要提交回答的多步对话 | `mcm ai answer` + `mcm ai resume` |

### 示例

```bash
# 首次提问
mcm ai "创建变更计划，部署订单服务"

# 多轮续接（自动续接最近会话）
mcm ai "这个计划的第一步怎么做？"

# 指定会话续接
mcm ai "执行计划第 1 步" -s <sessionId>

# 指定计划 ID
mcm ai "执行计划第 1 步" --plan-id 12345

# 脚本集成（获取 JSON）
result=$(mcm ai sync "查询计划进度" --plan-id 12345)

# 处理交互问题
mcm ai answer <sessionId> -e <eventId> -r '{"answers":[...]}'
mcm ai resume <sessionId>

```

### 常见问题

**Q: AI 问我问题，我该怎么回答？**

命令行执行 `mcm ai` 时，遇到 `❓ AI 需要你回答以下问题` 时会展示问题和选项，并输出可直接复制的 `answer` 命令（已填好 sessionId 和 eventId）：

```bash
# 按提示复制并修改 content 为你的选择，然后执行：
mcm ai answer <sessionId> -e <eventId> -r '{"answers":[{"id":"<questionId>","content":"<你的选择或输入>"}]}'
# 所有问题回答后（resume 内部自动 reconnect 接收后续输出）：
mcm ai resume <sessionId>
```

`content` 填写规则：有选项时填选项的 `id`（如 `routine`/`feature`/`bugfix`），无选项时直接填自定义文本。

**Q: 断网了或 AI 卡住了？**

执行 `mcm ai reconnect <sessionId>` 重连，持续失败则向用户汇报。详见 [Session 管理规则](#session-管理规则agent-必须遵守)。

**Q: 可以中途停止对话吗？**
```bash
mcm ai stop <sessionId>
```

---

## 路径二：`mcm` 子命令（查询 / 校验 / 提交 / 删除 / 变更模板写操作）

### 命令参考文档
- 执行命令前不确定参数含义或返回字段结构时，读取 [references/commands.md](references/commands.md)
- 状态码对照表见 [references/commands.md#附录枚举值参考](references/commands.md#附录枚举值参考)
- 变更计划/模板的完整 API 数据结构见 [references/plan-create-api-schema.md](references/plan-create-api-schema.md)

### 核心原则
- **输出格式**：命令可加 `-f json` 确保 AI 解析（默认就是 json，但显式指定更可靠）
- **分页规则**：默认 10 条/页，需更多数据用 `--page-size` 调整（≤100），全量数据用 `--page` 翻页（注意：此处 `-s` 为 `--page-size` 缩写，与 `mcm ai -s <sessionId>` 的会话参数含义不同）
- **时间格式**：统一使用 `yyyy-MM-dd HH:mm:ss`；用户输入仅含月日时，**⚠️ 年份必须取当前年份，禁止猜测或使用历史年份**，必须用 shell 命令动态获取：`$(date +%Y)-07-17 15:00:00`，当前年份是 `$(date +%Y)`
- **返回结构**：分页接口返回 `{ items: [...], totalCount, totalPage, page, pageSize }`，错误返回 `{ code: 非0值, message, data: null }`

### 命令速查

#### 认证相关
```bash
mcm login                  # CIBA 认证（推荐）
mcm whoami                 # 查看当前认证状态
mcm refresh                # 强制刷新 token
mcm logout                 # 清除本地认证缓存
```

#### 用户信息查询
```bash
# 获取当前认证用户信息（含 orgPath，可用于模板查询）
mcm user my [-f json]

# 典型用法：取 orgPath 后查询部门模板
mcm user my -f json | jq '.orgPath'
mcm template list --org <orgPath> -f json
```

> 返回字段：`mis`（MIS 号）、`name`（姓名）、`orgId`（部门 ID）、`orgPath`（组织路径 ID 链，如 `88888-100046-150042-1573`）、`orgNamePath`（组织名称路径链）。

#### 变更计划查询
```bash
mcm plan list [--page 1] [--page-size 10] [--name <名称>] [--creator <mis>] [--status <状态>] [--change-mode <1|2>] [--scene <场景>] [--change-type <类型>] [--app-key <appKey>]
mcm plan my [--type <LAUNCHED|TODO|DONE|ORG|ALL>]   # 查看我的计划（默认 LAUNCHED）
mcm plan detail <id>                                 # 查看计划详情
mcm plan steps <planId>                              # 查看计划步骤列表
mcm plan progress <id>                               # 查看计划进展（审批流程、操作记录）
mcm plan search --user <mis> [--type <ALL|CREATED|OPERATING|CC>]
mcm plan calendar --org <组织路径ID> --start <时间> --end <时间>
mcm plan count                                       # 查看计划数量统计
mcm plan status                                      # 查看所有可用的计划状态值
mcm plan notice-preview <id>                         # 查询变更计划周知详情
```

#### 变更事件查询与审批

> `--operator` 默认从本地 SSO 配置自动获取，获取失败时需手动传入。

```bash
# 查询变更列表（默认返回待我处理 TODO，支持筛选）
mcm event list [--query-type <LAUNCHED|TODO|DONE|ORG|ALL>] [--operator <mis>] [--name <名称>]
               [--launcher <mis>] [--status <状态,逗号分隔>] [--page 1] [--page-size 10]

# 查询事件详情
mcm event detail --account-name <系统名称> --event-name <事件名称>

# 查询变更详情
mcm event get <changeId>

# 审批操作
mcm event accept <changeId> [--operator <mis>] [--comment <意见>]       # 通过变更
mcm event reject <changeId> [--operator <mis>] --comment <驳回原因>      # 驳回变更（--comment 必填）
mcm event skip-audit <changeId> [--operator <mis>] --comment <跳过理由>  # 跳过审批（--comment 必填）
```

> ⚠️ `reject` 和 `skip-audit` 的 `--comment` 为**必填**，缺少时命令直接报错退出。

#### CloudTrail 追溯查询

覆盖全平台系统变更操作记录，通过 MCP Hub SSE 协议调用。
> ⚠️⚠️⚠️ **调用前必须先判断是只查 `cloudtrail list` 还是要同时加查 `paas-trace.sh`**：这里的"是否指定系统"专指有没有指定 `--account-name`（如 Lion、Plus、Squirrel 等变更系统名），**与 `--appkey`（服务名，如 `com.sankuai.xxx.xxx`）无关**——只查询了 appkey、没提任何 `--account-name` 系统名时，即属于"未指定系统"，两者都要查、各出一张独立表格，这是最容易被误判的一步。完整判断规则、固定命令、输出格式见 [「CloudTrail 全局通用规则」](references/commands.md#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)，**必须先读该节再调用命令，禁止只看下方示例就直接执行**。
>
> ⚠️⚠️⚠️ **请求出现 `--org-id`/`--user-org`/`--user-org-id` 或"我/我们团队""XX 部门/组织成员"+"变更"时**，无论是否已切换过 `event`/`cloudtrail` 等命令试错，禁止自行拼参数或直接作答（`event list -t ORG` 不是团队变更的正确查询方式），**必须先完整读取** [「user-org - 按团队/组织查询变更事件」](references/commands.md#user-org---按团队组织查询变更事件) **章节，严格照章节里的固定命令和输出模板执行**——该章节对调用参数、分页次数、回复正文格式（必须是表格而非文字总结）都有强制规定，任何一处凭经验自由发挥都会导致结果不合规。

```bash
# 查询追溯事件列表（默认近 24 小时）
mcm cloudtrail list [--begin <时间>] [--end <时间>] [--appkey <appkey,逗号分隔>] [--username <mis>]
                    [--event-name <名称>] [--account-name <系统名,逗号分隔>] [--env <prod|test>]
                    [--user-type <user|api>] [--event-uuid <uuid>] [--event-parent-id <id>]
                    [--org-id <orgId>] [--user-org-id <userOrgId>] [--user-org] [--custom-resource-type <类型>] [--custom-resource-names <名称,逗号分隔>]
                    [--page 1] [--page-size 20]

# 查询追溯事件详情（按 eventUuid）
mcm cloudtrail detail <eventUuid> [--begin <时间>] [--end <时间>]
```

> ⚠️ 查询追溯事件/查询变更调用前必读 [「CloudTrail 全局通用规则」](references/commands.md#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)（相对时间换算、原样输出禁令等）。

#### 变更模板查询
```bash
mcm template list [--name <名称>] [--org <组织路径>] [--admin <管理员>] [--type <类型>]
mcm template detail <id>             # 查看模板详情（含步骤模板）
mcm template preview <id> [--ones-app-id <onesAppId>] [--ones-issue-id <onesIssueId>] [--pipeline-job-id <pipelineJobId>]  # 预览模板（含动态步骤填充，可传 ONES/Pipeline 上下文参数）
mcm template history <id>            # 查看模板历史版本
mcm template used --user <mis>       # 查看指定用户最近使用的模板
```

#### 变更计划删除操作
```bash
mcm plan delete <id> [-y]                              # 删除变更计划草稿（仅限 PLANNING 状态，仅发起人可操作）
```

#### 变更计划撤销与重建操作

> ⚠️ **高风险操作**：revoke 和 rebuild 均会改变计划状态，Agent 调用前**必须先向用户确认**。RUNNING(6) 状态撤销时需额外提示"当前计划正在执行，撤销将中断执行"。

```bash
mcm plan revoke <id> [-y]                              # 撤销变更计划（适用于 AUDITING/WAIT_RUNNING/RUNNING 状态，撤销后状态变为 STOPPED）
mcm plan rebuild <id> [-y]                             # 重建变更计划（适用于 STOPPED/REJECTED 状态，重建后进入 PLANNING 草稿状态）
```

**触发使用场景：**

| 命令 | 适用状态 | 使用时机 |
|------|---------|---------|
| `mcm plan revoke` | AUDITING(1)、WAIT_RUNNING(5)、RUNNING(6) | 用户需要修改已提交/待变更/执行中的计划时，先撤销再重建 |
| `mcm plan rebuild` | STOPPED(4)、REJECTED(2) | 计划被撤销或审核驳回后，重建为草稿状态以便编辑 |

**正例（正确用法）：**
```bash
# 修改待审核计划：先撤销，再重建，然后编辑
mcm plan detail 12345                                  # 确认当前状态为 AUDITING(1)
mcm plan revoke 12345 -y                               # 撤销（需用户已确认）
mcm plan rebuild 12345 -y                              # 重建为 PLANNING 草稿

# 修改审核驳回的计划：直接重建
mcm plan detail 12345                                  # 确认当前状态为 REJECTED(2)
mcm plan rebuild 12345 -y                              # 重建为 PLANNING 草稿
```

**反例（错误用法）：**
```bash
# ❌ 不要对 PLANNING(9) 状态的计划调用 revoke（该状态直接编辑即可，无需撤销）
mcm plan revoke 12345  # 错误：PLANNING 状态会被命令直接拒绝

# ❌ 不要跳过用户确认直接自动执行高风险操作（RUNNING 状态需额外确认）
mcm plan revoke 12345 -y  # 错误：RUNNING 状态下 Agent 不得未确认直接加 -y 执行

# ❌ 不要对终态计划（SUCCEED/FAILED）调用 revoke 或 rebuild（应走复制流程）
mcm plan revoke 12345     # 错误：SUCCEED/FAILED 状态不支持撤销
mcm plan rebuild 12345    # 错误：SUCCEED/FAILED 状态不支持重建
```

#### 变更模板写操作
```bash
mcm template create -n <名称> [选项] [-y]              # 创建模板
mcm template update --template-id <id> [选项] [-y]     # 更新模板
```

#### 变更计划校验/提交操作
```bash
mcm plan validate --data <完整JSON>                    # 校验计划草稿
mcm plan submit <id> [-y]                              # 提交变更计划
```

#### 变更计划审核操作

> ⚠️ **重要：approve 的 `--approve-level` 必填；reject 的 `--comment` 必填，务必带齐！**

```bash
mcm plan approve <id> --approve-level <层级> [--comment <评论>] [-y]   # 审核通过（状态: 待审核 → 下一阶段/待变更）
mcm plan reject  <id> --comment <驳回原因> [--approve-level <层级>] [-y]  # 审核驳回（状态: 待审核 → 已驳回）
```

| 参数 | approve | reject | 说明 |
|------|---------|--------|------|
| `--approve-level <层级>` | ✅ **必填** | 可选 | 审核层级，整数，通过 `mcm plan detail <id>` 查看 `approveLevel` 字段，通常为 `1`|
| `--comment <评论>` | 可选 | ✅ **必填** | approve 填通过原因（可不填）；reject 必须填写驳回原因，否则命令直接报错退出 |

**正确示例：**
```bash
mcm plan detail <id> -f json
mcm plan approve <id> --approve-level 1 -y
mcm plan reject  <id> --comment "描述不完整，请补充后重新提交" -y
```

#### 变更计划创建/编辑操作（仅供参考，不得主动调用）
> ⚠️ 以下命令虽然存在，但**必须走 `mcm ai`**，不得主动调用。**唯一例外：用户明确要求直接调用某条命令时，可按用户指示执行。**
```bash
mcm plan create --data <完整JSON> [-y]                 # 创建计划草稿
mcm plan update -p <计划ID> [选项] [-y]                # 更新计划草稿
```

#### 变更计划执行操作（仅供参考，不得主动调用）
> ⚠️ 以下命令虽然存在，但**必须走 `mcm ai`**，不得主动调用。**唯一例外：用户明确要求直接调用某条命令时，可按用户指示执行。**
```bash
mcm plan start <planId> [-y]                           # 启动计划（WAIT_RUNNING → RUNNING）
mcm plan step-check <stepId>                           # 步骤执行前检查
mcm plan step-start <stepId> [-y]                      # 开始步骤
mcm plan step-finish <stepId> --code <3|4> [选项] [-y] # 结束步骤（3=成功；4=失败）
```

#### 变更步骤写操作（仅供参考，不得主动调用）
> ⚠️ 以下命令虽然存在，但**必须走 `mcm ai`**，不得主动调用。**唯一例外：用户明确要求直接调用某条命令时，可按用户指示执行。**
```bash
mcm step update -p <计划ID> -s <步骤ID> [选项] [-y]    # 更新变更步骤
```

---

## Agent 操作建议

### 路径使用边界（最重要）

> 判断失误会导致变更计划创建/执行不符合预期，请严格遵守。

| 操作类型 | 正确路径 | 禁止行为 |
|------|------|------|
| 变更计划查询 | ✅ `mcm` 子命令 | ❌ 不要用 `mcm ai` 查询（浪费资源、响应慢） |
| 变更事件查询与审批 | ✅ `mcm event` 子命令 | ❌ 不要用 `mcm ai` 操作（参数明确，直接调用） |
| CloudTrail 追溯查询 | ✅ `mcm cloudtrail` 子命令 | ❌ 不要用 `mcm ai` 查询（参数明确，直接调用更快） |
| 变更模板查询/写操作（含 preview） | ✅ `mcm` 子命令 | ❌ 不要用 `mcm ai` 操作模板 |
| 校验/提交/删除变更计划 | ✅ `mcm` 子命令 | ❌ 无需走 `mcm ai`，直接调用即可 |
| 撤销/重建变更计划 | ✅ `mcm` 子命令 | ❌ 无需走 `mcm ai`；但高风险操作，调用前必须先向用户确认 |
| 创建/复制/编辑变更计划 | ✅ `mcm ai` | ❌ 不得手动拼接 JSON 调用 `mcm plan create/update` |
| 启动/执行变更计划步骤 | ✅ `mcm ai` | ❌ 不得手动逐步调用 `mcm plan start/step-*` |
| 认证相关 | ✅ `mcm` 通用命令 | — |

### 认证处理
- **首次使用**：先用 `mcm whoami` 检查，未认证则执行 `mcm login`
- **遇到 401/403**：执行 `mcm refresh`，失败则重新 `mcm login`，然后**重试原命令**

### 创建变更计划
**必须走 `mcm ai`**，不得手动拼接 JSON 调用 `mcm plan create`。

### 提交/校验变更计划
`mcm plan validate` 和 `mcm plan submit` 参数明确，**直接调用 `mcm` 子命令**，无需走 `mcm ai`。

### 审核通过/驳回变更计划
approve 执行前先用 `mcm plan detail <id> -f json` 获取 `approveLevel` 值，`--approve-level` 为 approve 必填（缺少直接报错退出）；reject 的 `--comment` 为必填（缺少直接报错退出），`--approve-level` 可不填。

### 撤销/重建变更计划

`mcm plan revoke` 和 `mcm plan rebuild` 均为高风险操作，执行前**必须向用户确认**：
- `revoke` 适用于 AUDITING(1)、WAIT_RUNNING(5)、RUNNING(6) 状态；RUNNING 状态需额外警示"当前计划正在执行，撤销将中断执行"
- `rebuild` 适用于 STOPPED(4)、REJECTED(2) 状态，重建后进入 PLANNING 草稿
- PLANNING(9) 状态**不需要**撤销，直接编辑即可
- 终态（SUCCEED/FAILED）既不能撤销也不能重建，需走复制流程

### 启动/执行变更计划步骤
**必须走 `mcm ai`**，不得手动逐步调用 `mcm plan start/step-*`。
执行过程中如遇交互询问，通过 `mcm ai answer` + `mcm ai resume` 响应。

### Session 管理规则（Agent 必须遵守）

**核心原则**：除非用户明确要求启动新会话，否则始终执行 `mcm ai "<question>"`（不传 `-s`），自动续接本地最近 24 小时内未过期的会话；若本地无有效会话，命令内部会自动创建新 session，无需 Agent 干预。

**`--plan-id` 与会话续接的关系**：当命令携带 `--plan-id <planId>` 时，自动续接规则如下：
1. **有匹配**：续接与该 `planId` 绑定的最新未过期会话
2. **无匹配**：直接新建会话（不续接其他计划的会话，避免上下文污染）

因此，针对同一个变更计划（相同 planId）的多次操作，无论中间插入了其他计划的操作，都能正确回到对应的会话上下文。首次操作某个 planId 时，会自动开启一个干净的新会话。

#### 1. 同一任务禁止新建会话

对同一个变更计划的操作（编辑、执行步骤等）应始终在同一 session 中完成。**禁止在同一任务中未经用户同意创建新会话**，否则会导致多个 Agent 并行控制同一计划，造成"控制权混乱"和算力浪费。

> 注：创建阶段（尚无 planId）和执行阶段（已有 planId）天然是两个 session，这是正常的，不属于此规则约束的范围。

`-s` 参数的唯一合法使用场景：
- **切换到指定历史会话**：用户明确要求基于某个历史会话继续时，传对应的 sessionId
- **开启新会话**：用户明确要求新开时，生成新 UUID 传入（按优先级选择可用命令）
  ```bash
  mcm ai "<用户输入>" -s $(uuidgen | tr '[:upper:]' '[:lower:]')                          # macOS/Linux 优先
  mcm ai "<用户输入>" -s $(node -e "console.log(require('crypto').randomUUID())")          # uuidgen 不可用时
  mcm ai "<用户输入>" -s $(python -c "import uuid; print(uuid.uuid4())")                  # node 也不可用时（优先 python，其次 python3，兼容python版本不同情况）
  ```

#### 2. 中断后优先 reconnect，不要新开会话

进程被 SIGTERM 中断（Ctrl+C、超时、网络中断）或 2~3 秒退出无实质输出时：

> ⚠️ **认知重点**：`reconnect` 看起来像是"重新推进"，**实际只是回放历史输出**；服务端 AI Agent 在中断后通常仍在继续运行，重连后即可收到后续结果。

```bash
mcm ai reconnect <sessionId>  # 回放历史并等待服务端结果
```

若 reconnect 持续失败，执行规则 4（汇报用户）。

❌ **禁止**：进程中断后就认为 session 失效，直接用 `-s` 开新 session。

#### 3. `mcm ai resume` 仅用于 ask_question 场景

当 AI 通过 `ask_question` 提问时：
```bash
mcm ai answer <sessionId> -e <eventId> -r '{...}'  # 回答问题
mcm ai resume <sessionId>                            # 恢复 Agent 执行（内部自动 reconnect）
```
`resume` **不是通用的会话恢复手段**，其他场景（如断连、超时）不要使用。

#### 4. reconnect 持续失败时汇报用户，不自行决策

当 reconnect 持续失败时：
- ✅ 暂停，向用户汇报当前情况和 sessionId
- ❌ 不要自作主张（不要新开会话、不要重复执行步骤、不要无限重试）
- 由用户决定下一步操作；无论用户后续发出什么指令，只要触发 `mcm ai`，**仍使用原 sessionId 续接，不得新开会话**

---

## 错误排查

| 错误信息 | 原因 | 解决方法 |
|------|------|--------|
| `mcm: command not found` | mcm-cli 未安装或不在 PATH | 执行安装命令 |
| `Unauthorized / 401` | 未登录或 token 已过期 | `mcm refresh`，失败则 `mcm login` |
| `sessionId 无效` | 格式错误、已过期或不存在 | 先按 Session 管理规则判断是否可 reconnect；确需新开时由用户决定 |
| `question 为空` | 缺少必填参数 | 提供有效的问题内容 |
| `plan-id 格式错误` | 应该是整数格式 | 检查格式，例如 `--plan-id 12345` |
| `mcm ai` 2~3 秒退出无输出 | 旧会话已停止，或会话异常断开（服务端仍在执行） | 先执行 `mcm ai reconnect <sessionId>` 重连；重连持续失败后再向用户汇报，由用户决定下一步 |
| `SSE 连接中断` | 网络波动或推理超时 | `mcm ai reconnect <sessionId>`（仅本轮推理中有效） |
| `SSE 收到异常数据 / 流式解析异常` | 服务端数据格式问题 | 加 `--debug` 参数重跑命令，查看原始 SSE 数据辅助定位（仅故障排查时使用） |
| `Connection refused` | API 服务离线或网络问题 | 检查网络连接，或联系运维 |
| `answer_question 返回错误` | 回答格式不正确 | 确保 `--result` 是有效 JSON 字符串 |
| `400 Bad Request` | 请求参数不合法 | 检查 sessionId、question、result 格式 |
| `429 Too Many Requests` | 请求过于频繁 | 等待几秒后重试 |

