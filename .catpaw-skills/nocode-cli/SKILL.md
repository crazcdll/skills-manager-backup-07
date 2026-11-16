---
name: nocode-cli
description: 通过 NoCode CLI 操作美团 NoCode 零代码平台。当用户要求创建/修改零代码应用、截图预览、部署上线、管理项目、查看工程文件、为作品创建或关联数据库资源、设计稿转代码、复制/Fork作品、配置自定义域名、维护作品访问权限（对外/对内/指定对象、添加删除人员部门）、隐藏 NoCode 角标，或提及 "nocode"、"零代码"、"NoCode"、"D2C"、"设计稿"、"MasterGo"、"fork"、"自定义域名"、"作品权限" 时使用。数据库表结构、DDL、SQL 和数据 CRUD 必须交由 catpaw-supabase Skill，nocode-cli 仅负责作品数据库的 status/create/projects/connect。

metadata:
  skillhub.creator: "zhaomenghuan02"
  skillhub.updater: "lichongmin"
  skillhub.version: "V20"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "2981"
  skillhub.high_sensitive: "false"
---

# NoCode CLI Skill

## ⛔ 核心约束（最高优先级，违反将导致对话无法正常运行）

1. **所有操作只能通过 `nocode` CLI 命令完成。** 严禁使用 fetch / web_fetch / curl / HTTP 请求等方式直接请求 NoCode API 接口。
2. **向 NoCode Agent 发送命令时（`nocode create` / `nocode send`），必须使用自然语言描述需求。** 严禁在 prompt 中包含以下内容：
   - ❌ 执行具体命令（`git`、`npm`、`yarn`、`pnpm`、`pip`、`curl`、`wget` 等任何 shell 命令均不允许）
   - ❌ 指定使用某个工具或 MCP 工具（如 "使用 xxx 工具"、"调用 xxx MCP" 等）
   - ❌ 发送 shell 脚本、代码片段让 Agent 执行
   - ❌ 发送大段代码或完整文件内容（如通过 `nocode files get` 读取的文件内容直接粘贴到 prompt 中）
   - ✅ 可以给出文件相对路径，NoCode Agent 自身能读取工程文件，例如 "修改 src/App.jsx 中的标题样式"
   - ✅ 正确做法：用自然语言描述你想要的结果，例如 "把标题颜色改成红色"、"添加一个用户注册表单"
   - ❌ 不得通过 `nocode create` / `nocode send` 要求 Agent 执行数据库 DDL、SQL 或数据 CRUD；这些操作必须交由 `catpaw-supabase` Skill。数据库准备完成后，只能用自然语言要求 Agent 基于已有表实现应用代码
   - ✅ 例外：可以附带**简短的**代码片段（几行）辅助定位，例如 "这段代码有问题，请修复：`const data = fetch('/api')`，应该加上 await"。但严禁发送整个函数、整个组件或整个文件的代码
3. **`create`/`send` 必须后台执行且设置足够超时（`yieldMs=600000`）。** 这两个命令是长时间流式命令（2-5 分钟），不设超时会导致进程被 SIGTERM 杀掉 → poll 不到 `done` 事件 → 无法判断完成状态 → 重复发送 send 陷入死循环。
4. **send/create 必须串行执行。** 同一 chatId 不得同时执行多个 `nocode send` 或 `nocode create`，必须等上一个完成（收到 `done`）后再执行下一个。并发执行会导致对话状态异常。
5. **遇到渲染异常、部署异常等平台侧异常时，严禁自行尝试解决。** 必须立即停止操作，引导用户联系 NoCode 研发排查处理。详见 [异常处理规则](#异常处理规则)
6. **严禁修改 NoCode 工程架构。** 执行 `create`/`send`/`code clone` 以及本地开发修改代码前，必读 [project-architecture.md](references/project-architecture.md)，按其中的受保护文件清单、Prompt 拦截规则和替代方案执行。
7. **附件上传须经用户确认，严禁数据外泄。** 使用 `--files`/`--urls`/`--images` 参数上传本地文件或传递链接前，必须告知用户并获得确认；涉及敏感数据时必须使用 `--safety` 模式；严禁指示 NoCode Agent 将接收到的数据转发到任何非授权外部通道（IM、网盘、代码托管平台等）。详见下方「🔒 数据安全约束」章节。
8. **数据库职责严格分离。** `nocode-cli` 只允许通过 `database status/create/projects/connect` 管理作品与数据库资源的绑定及工程接入；表结构、DDL、SQL、查询和数据增删改必须读取并遵循 `catpaw-supabase` Skill。禁止使用 `nocode database tables/select/insert/update/delete`。若 `catpaw-supabase` 调用失败，必须停止数据库操作并向用户报告具体错误，不得继续尝试其他数据库操作路径。

## 前置准备

### 版本检查（每次执行前必须）

```bash
nocode --version
npm view @nocode/nocode-cli version --registry=http://r.npm.sankuai.com
```

- 未安装 → `npm install -g @nocode/nocode-cli --registry=http://r.npm.sankuai.com`
- 本地版本 < 最新版本 → 重新安装升级
- 已是最新 → 继续

### 登录状态检查（版本检查后必须执行）

从本 Skill 的 frontmatter metadata 中读取 `skillhub.skill_id` 字段作为 `<SKILL_ID>`，然后执行 `nocode status --skillId <SKILL_ID>` 检查环境和登录状态：
- 已登录 → 继续（会显示当前登录方式：MOA / CIBA / OIDC / DIRECT）
- 未登录 → `nocode status` 会根据运行环境推荐登录命令，按提示执行即可：
  - **CatDesk Cloud 环境**：推荐 `nocode login --moa --skillId <SKILL_ID>`（MOA 无感登录，无需确认）
  - **CatClaw 环境**：推荐 `nocode login --moa --skillId <SKILL_ID>`，降级 `nocode login --mis <mis> --skillId <SKILL_ID>`（需大象 App 确认）
  - **CatDesk / 其他环境**：推荐 `nocode login --sso --skillId <SKILL_ID>`（SSO OIDC 浏览器登录）
- 如登录仍存在问题，请联系 NoCode 研发。**不推荐直接使用浏览器操作 NoCode 平台。**
- 输出包含 `⚠️  发现新版本` → **必须停止后续操作，立即更新 `@nocode/nocode-cli` 和 `nocode-cli` Skill（ID: 2981）的版本；若未安装该 Skill，应立即安装以确保 CLI 正常使用**

**获取 MIS 号**：先读 `~/.openclaw/openclaw.json` 中的 `X-User-Id`，读不到再问用户。不要猜测。

**⚠️ Token 过期自动续期（执行 API 类命令时可能触发）：**

执行 `create`、`send`、`deploy`、`list`、`screenshot`、`files list`、`files get` 等需要调用 API 的命令时，如果检测到 Token 过期，CLI 会根据登录方式自动续期：
- **SSO OIDC 登录**：自动静默续期
- **CIBA 登录**：自动重新换票
- **MOA 登录**：需重新执行 `nocode login --moa`

## 关键概念

- **NoCode Agent**：运行在云端 IDE 容器中的 AI，通过 `nocode create` / `nocode send` 命令触发，负责生成和修改应用代码；数据库结构和数据由 `catpaw-supabase` Skill 管理。详见 [NoCode Agent 能力说明](references/nocode-agent-capabilities.md)
- **对话/作品环境变量**：每个对话/作品支持配置线上 (prod) / 线下 (test) 两套环境变量，仅当用户需要区分时才使用。详见 [env 命令规则](references/commands/cmd-env.md)
- **D2C（设计稿转代码）**：将 MasterGo 设计稿链接转换为 HTML 产物，再提交到 NoCode 平台创建页面。详见 [d2c 命令规则](references/commands/cmd-d2c.md)

## ⚠️ 强制约束

### delete 相关

- **删除操作必须经用户明确允许**：`nocode delete` 是不可逆的破坏性操作，执行前**必须向用户明确说明将要删除的对话/项目（展示 chatId），并获得用户的明确确认**（如用户回复"确认删除"、"可以删"等）。禁止在用户未明确允许的情况下执行删除命令
  - ❌ 用户未提及删除意图时，自行决定删除对话/项目
  - ❌ 仅因为任务"完成"或对话"不再需要"就自动删除
  - ❌ 批量删除时未逐一确认
  - ✅ 向用户展示将要删除的 chatId，明确告知删除不可恢复，获得用户确认后执行
- **其他破坏性操作同样适用上述确认规则**：`nocode domain delete`（删除后域名立即无法访问）、`nocode permission remove`（移除后人员/部门立即失去访问权限）均需先展示具体对象并获得用户明确确认

### send 相关

- **按功能模块拆分**：每次 `nocode send` 只包含**一个内聚的功能模块或一组紧密相关的修改**。多个不相关的功能必须拆分为多次 send，逐步 send → 截图确认 → 再 send 下一步。违反此规则会导致 NoCode Agent 生成质量严重下降甚至失败。
  - ❌ `nocode send <chatId> "添加用户注册表单并加验证，同时加一个登录页面，再把导航栏颜色改成深蓝色"` — 多个不相关功能混在一条
  - 完整拆分示例和原则见 [create & send 规则](references/commands/cmd-create-send.md)「每次 send 只包含一个功能模块」章节

### 代码同步（code clone / code pull）

- **`code clone` 用于将作品代码克隆到本地**：首次全量 clone，后续增量更新
- **`code pull` 用于将远程仓库的最新代码同步到 Sandbox**：当用户需要在 Sandbox 中获取仓库最新代码时使用
- **有本地变更时 pull 需确认**：`code pull` 检测到 Sandbox 有未推送变更时会拒绝执行，需 `--force` 跳过确认
- **⭐ 本地开发工作流**：当用户要求"拉代码到本地改"、"本地开发"、"本地修改代码"时，**必须先读取 [workflow-local-dev.md](references/workflows/workflow-local-dev.md) 并严格按其 Spec-Driven 流程执行**（Phase 0~5：INITIALIZE → ANALYZE → DESIGN → IMPLEMENT → VALIDATE → HANDOFF）。不要自行编排流程

### 链接与展示

- **预览页面只能通过截图或 chatUrl**：给用户预览效果时，只能使用 `nocode screenshot` 截图展示，或提供 chatUrl（形如 `https://nocode.sankuai.com/#/chat?pageId=xxx`）让用户自行查看。**严禁将 renderUrl**（形如 `https://xxx.sandbox.nocode.sankuai.com`）**展示给用户**——renderUrl 仅供 CLI 内部截图使用，且容器未启动时访问会 404
  - ❌ 错误：`https://xxx.sandbox.nocode.sankuai.com` ← 不要给用户
  - ✅ 正确：`https://nocode.sankuai.com/#/chat?pageId=xxx` ← 给用户
- **chatId 链接**：必须使用 `[{chatId}]({chatUrl})` 格式（可同时展示纯文本 chatId 供复制）
- **部署地址链接**：必须使用 `[{externalUrl}]({externalUrl})` 格式
- **域名链接**：展示域名时使用 `[{url}]({url})` 格式。**严禁将 `deployUrl`（真实部署链接）展示给用户**，仅 `url`（用户访问地址）可对外展示
- 禁止以纯文本输出 URL，所有面向用户的链接必须可点击

### 自定义域名与作品权限

- **域名操作前必须先查看现状**：执行 `domain create` / `modify` / `delete` 前，必须先 `nocode domain list <chatId>` 确认各条记录的真实 `domainType`
- **⛔ 两类域名语义完全不同，不可混淆**：
  - **系统前缀域名**（`init_prefix_custom_domain` / `prefix_custom_domain`，形如 `https://xxxxx.mynocode.host`）：由部署自动产生，每个作品**有且只有一条**。**只能改前缀，不能新增、不能删除**；改后直接生效，**无需**配置 Oceanus
  - **Oceanus 自有域名**（`fully_custom_domain`，即「完全自定义域名」）：可新增多条、可删除；新增/修改后**必须**提醒用户去 Oceanus 配置映射规则才能访问
  - 负数 ID 的 `history_deploy_domain` 是后端合成的**只读虚拟记录**，不可修改/删除
- **权限切换涉及信息安全，必须经用户确认**：切换到「外部公开」（`EVERYONE`）意味着非美团人员也能访问，**必须先向用户说明风险并获得明确确认**；切换到「内部公开」（`MEITUAN`）需提醒用户所有内部员工均可访问
- **删除域名、移除人员/部门权限必须经用户明确确认**，且需展示将要删除/移除的具体对象（域名 URL、人员姓名/MIS 号、部门路径）
- **禁止猜测 MIS 号和部门路径**：添加人员前用 `permission search-user` 校验。**`search-org` 是完整路径精确匹配，传简称会返回空数组（不报错），无法凭简称反查完整路径**。用户只给简称时，应引导其**从大象用户信息卡片的「部门」一栏整段复制**，禁止自行拼接或用简称反复尝试
- **权限被团队策略或审批流拦截时禁止重试绕过**：遇到「团队已设置强制指定对象」「有审批中的权限变更申请」等错误，必须如实告知用户，不得重试

### 文件与数据库

- **查看文件必须用 files 命令**：使用 `nocode files list` / `nocode files get`，禁止通过 `nocode send` 获取文件内容
- **先判断是否只需查看绑定状态**：如果用户只问作品是否有数据库、绑定了哪个数据库，仅执行 `nocode database status <chatId>`，无需调用 `catpaw-supabase`
- **新建或复用必须由用户决定**：数据库未连接或 `isConfirmed: false` 时，必须询问用户是为当前作品**新建 database 资源**（`nocode database create`），还是**复用既有资源**（`nocode database projects` + `connect`）；禁止未经确认直接 `create`
- **数据库可用状态**：只有 `database status` 返回 `connected: true` 且 `isConfirmed: true` 才可继续。`connected: true` 但 `isConfirmed: false` 仍然不可用
- **数据库内容操作必须委托 `catpaw-supabase`**：从 `status.data.url` 取得 `projectUrl` 后，立即读取 `catpaw-supabase` Skill，调用其 `list_my_projects` 按规范化 URL 精确匹配唯一项目，再使用 `projectId` 完成表结构、DDL、SQL 和 CRUD。匹配失败、权限不足或调用异常时，必须停止数据库操作并向用户报告具体错误，禁止猜测项目或继续尝试其他数据库操作路径
- **NoCode Agent 只负责应用代码**：数据库准备完成后，才可通过 `nocode send` 要求 Agent 基于已存在的表实现页面；prompt 必须说明表已存在且不得创建、修改表结构或导入数据
- **数据驱动需求必须先入库**：看板、报表、仪表盘等场景禁止将数据文件直接 `--files` send 给 NoCode Agent，也禁止让 Agent 下载外部静态数据文件。应在本地分析数据，再按 `catpaw-supabase` 的限制串行导入，详见 [best-practices.md](references/best-practices.md) 场景 2

### 📌 最佳实践

遇到 HTML 复刻、数据驱动看板、架构改动需求等场景时，**必读 [best-practices.md](references/best-practices.md)**，按其中的对应流程执行。

## 命令速查

**⚠️ 强制规则：执行有"详细规则"链接的命令前，必须先读取对应的 references 文件，按其中的规则执行。不可跳过。**

| 命令 | 用途 | 备注 | 详细规则（执行前必读） |
|------|------|------|---------|
| `nocode create "<prompt>"` | 创建应用 | NDJSON 流式，需后台执行（`yieldMs=600000`）+ poll。支持 `--images`/`--files`/`--urls`/`--safety`/`--skillId` | ⚠️ [命令必读](references/commands/cmd-create-send.md) · [架构保护必读](references/project-architecture.md) |
| `nocode send <chatId> "<msg>"` | 发送修改 | NDJSON 流式，需后台执行（`yieldMs=600000`）+ poll。支持 `--images`/`--files`/`--urls`/`--safety`/`--skillId` | ⚠️ [命令必读](references/commands/cmd-create-send.md) · [架构保护必读](references/project-architecture.md) |
| `nocode files list <chatId> [path]` | 查看目录树 | 边界标记 `---TREE_START/END---` | ⚠️ [必读](references/commands/cmd-files.md) |
| `nocode files get <chatId> <path>` | 查看文件内容 | 边界标记 `---FILE_CONTENT_START/END---` | ⚠️ [必读](references/commands/cmd-files.md) |
| `nocode screenshot <chatId>` | 截图预览 | 返回 S3 URL，失败不阻塞 | ⚠️ [必读](references/commands/cmd-screenshot.md) |
| `nocode deploy <chatId>` | 部署上线 | 自动用最新版本，渲染失败会拦截。`--skillId <id>` 上报调用来源 | ⚠️ [必读](references/commands/cmd-deploy.md) |
| `nocode env <action> <chatId>` | 对话/作品环境变量管理 | list / set / delete / switch | ⚠️ [必读](references/commands/cmd-env.md) |
| `nocode domain <action> <chatId>` | 域名管理 | list / create / modify / delete。前缀域名只能 `modify`，自有域名才能 `create`/`delete`。操作前必须先 `list` | ⚠️ [必读](references/commands/cmd-domain.md) |
| `nocode permission <action> <chatId>` | 作品权限管理 | get / set / add / remove / search-user / search-org / badge。切外部公开须用户确认 | ⚠️ [必读](references/commands/cmd-permission.md) |
| `nocode status` | 检查环境和登录状态 | 显示运行环境（CatDesk Cloud / CatClaw / CatDesk / 其他）、登录方式、版本信息。`--skillId <id>` 上报调用来源 | — |
| `nocode login` | 登录 | `--moa`（MOA 无感）/ `--mis <mis>`（CIBA）/ `--sso`（SSO OIDC）/ `--token <token>`（手动）。`--skillId <id>` 上报调用来源 | — |
| `nocode logout` | 登出 | 清除本地凭证 | — |
| `nocode list` | 项目列表 | `--page N --size N --json` | — |
| `nocode detail <chatId>` | 查看详情 | JSON 输出 | — |
| `nocode messages <chatId>` | 查看消息列表 | `--page N --size N --json` | — |
| `nocode versions <chatId>` | 版本列表 | — | — |
| `nocode delete <chatId> --confirm` | 删除对话/项目 | ⛔ **必须经用户明确允许后才能执行，严禁自行决定删除。** `--confirm` 为必需参数 | — |
| `nocode code clone <chatId>` | 克隆作品代码到本地 | 智能增量更新，支持 `--dir`、`--json` | ⚠️ [命令必读](references/commands/cmd-code.md) |
| `nocode code pull <chatId>` | 从远程仓库拉取代码到 Sandbox | 支持 `--force`（跳过确认）、`--json` | ⚠️ [命令必读](references/commands/cmd-code.md) |
| `nocode answer <chatId> <eventId> <conversationId>` | 回答 NoCode Agent 提问 | 根据 `question` 事件的 `answer_hint` 拼接参数，支持 `--select`/`--text`/`--cancel` | ⚠️ [必读](references/commands/cmd-create-send.md) |
| `nocode database status/create/projects/connect <chatId>` | 作品数据库资源接入 | 仅管理绑定与工程接入；表结构、DDL、SQL、CRUD 使用 `catpaw-supabase` | ⚠️ [必读](references/commands/cmd-database.md) |
| `nocode fork <chatId>` | 复制（Fork）作品 | 完整复制作品（含代码、配置、数据库），支持 `--branch`（同仓建分支） | ⚠️ [必读](references/commands/cmd-fork.md) |
| `nocode d2c "<design-link>"` | 设计稿转代码 | 生成 HTML + 截图，需配合 `nocode create` 提交平台 | ⚠️ [必读](references/commands/cmd-d2c.md) |

## 典型工作流

> 以下为概览示例。执行具体命令前，**必须先读取命令速查表中对应的「详细规则」链接**，按其中的完整规则执行。

```bash
# 1. 登录（从本 Skill 的 metadata.skillhub.skill_id 获取 SKILL_ID）
# CatDesk Cloud / CatClaw 环境推荐：
nocode login --moa --skillId <SKILL_ID>
# 其他环境推荐：
# nocode login --sso --skillId <SKILL_ID>

# 2. 创建（NDJSON 流式输出，done 事件包含 chatId）
nocode create "做一个宣传页面" --skillId <SKILL_ID>

# 3. 修改
nocode send <chatId> "把主色调改成深蓝色" --skillId <SKILL_ID>

# 4. 截图确认
nocode screenshot <chatId>

# 5. 部署
nocode deploy <chatId> --skillId <SKILL_ID>

# 6. 遇到问题时：先查代码再精确修改（禁止用 send 获取文件内容）
nocode files list <chatId>                        # 查看工程目录结构
nocode files list <chatId> src                    # 浏览子目录
nocode files get <chatId> src/App.jsx             # 读取相关文件内容
# → 分析代码，定位问题原因
nocode send <chatId> "具体的修改指令" --skillId <SKILL_ID>  # 发送精确修改
nocode screenshot <chatId>                  # 截图确认修改效果
```

### 部署后：配置域名与权限

```bash
# 1. 查看域名现状，确认各条记录的真实类型
nocode domain list <chatId>

# 1a. 系统前缀域名（*.mynocode.host）：由部署产生、全局唯一
#     只能改前缀，不能新增/删除；改后直接生效，无需配 Oceanus
nocode domain modify <chatId> <domainId> new-prefix.mynocode.host --path /

# 1b. Oceanus 自有域名（= 完全自定义域名）：可新增多条、可删除
nocode domain create <chatId> example.sankuai.com --path /app
# → 成功后提醒用户前往 Oceanus 完成映射规则配置（仅自有域名需要）

# 2. 查看当前权限配置
nocode permission get <chatId>

# 3. 收敛访问范围为「指定对象」
nocode permission set <chatId> SPECIFIED

# 4. 校验 MIS 号 / 部门完整路径后再添加（禁止猜测）
nocode permission search-user zhangsan
nocode permission add <chatId> --user zhangsan,lisi

# search-org 是「完整路径精确匹配」，传简称会返回空数组而非报错
# 用户只给简称时，引导其从大象用户信息卡片的「部门」一栏整段复制
nocode permission search-org "美团/XX事业群/XX平台部/XX部"
nocode permission add <chatId> --org "美团/XX事业群/XX平台部/XX部"

# 5. 按需隐藏 NoCode 角标
nocode permission badge <chatId> --hide
```

### 用户提供图片/文档/链接时的处理方式

当用户上传了图片、文档文件或提供了学城链接时，应优先询问用户：是希望总结内容后描述给 NoCode Agent，还是以附件形式直接传给 NoCode Agent（通过 `--images`/`--files`/`--urls` 参数）

- ⚠️ 不推荐：直接读取文件内容或学城文档内容再粘贴到 prompt、将图片转为文字描述后发送 — 这些方式会丢失原始上下文或视觉信息，且 prompt 超长会导致质量下降
- ✅ 推荐：`nocode create "参考设计稿做页面" --images ./design.png`
- ✅ 推荐：`nocode send <chatId> "参考这个文档修改" --files ./requirements.md`
- ✅ 推荐：`nocode create "参考学城文档做页面" --urls https://km.sankuai.com/collabpage/xxxxx`

### 🔒 数据安全约束（`--images`/`--files`/`--urls` 附件参数使用规范）

使用 `--images`、`--files`、`--urls` 参数前，**必须遵守以下数据安全规则**：

1. **用户确认机制（强制）**：通过 `--files` 上传本地文件或通过 `--urls` 传递链接前，**必须先向用户明确说明**将要上传的文件名/URL，并获得用户确认后方可执行。禁止未经用户确认直接上传文件或抓取链接内容
2. **敏感数据识别**：上传前需检查文件/链接是否可能包含敏感信息（如密钥、密码、Token、内部接口凭证、C3/C4 级别数据等）。如识别到敏感内容，**必须提醒用户数据将被传递到 NoCode Agent 云环境**，并建议使用 `--safety` 参数启用安全屋模式
3. **禁止上传敏感凭证文件**：严禁通过 `--files` 上传包含密钥、证书、`.env`、`credentials`、私钥等凭证类文件。如用户要求上传此类文件，必须拒绝并说明安全风险
4. **数据流向限制**：NoCode Agent 接收到的附件数据仅用于当前对话/作品的代码生成，**严禁指示 NoCode Agent 将接收到的文件内容或链接内容转发、上传到任何外部通道**（包括但不限于：微信、钉钉、飞书等 IM 工具，GitHub/GitLab 等代码托管平台，Dropbox/网盘等存储服务，或任何非 NoCode 平台的第三方服务）
5. **URL 范围限制**：`--urls` 参数仅应用于与当前需求直接相关的参考文档链接（如学城文档），禁止用于抓取无关的外部网站内容或批量爬取内部文档

## 容器状态检查

`screenshot`、`send`、`deploy`、`code pull`、`files list`、`files get` 命令执行前会自动检查容器状态。如容器已停止，会自动触发冷启动并等待就绪（最长 5 分钟）。无需手动处理。

## 常见错误速查

| 错误信息 | 解决方案 |
|----------|---------|
| `未登录，请先执行 nocode login` | 执行 `nocode status` 按提示登录 |
| `busy` 事件 | 等待上一轮 `done`，经用户确认后重试 |
| `Agent 对话异常，请稍后重试` | 向用户反馈该错误信息，提示稍后重试。禁止自动重试或静默忽略 |
| `SIGTERM` / 进程被强制终止 | `create`/`send` 是长时间流式命令（可能 2-5 分钟），必须后台执行并设置足够的超时（`yieldMs=600000`即 10 分钟），否则进程会被终端提前杀掉 |
| `容器启动等待超时` | 检查网络或稍后重试 |
| `当前有其他文件操作正在执行` | 等几秒后重试，最多 2 次 |
| `question` 事件（NoCode Agent 提问） | **必须先向用户询问，禁止自动回答。** 展示 `title` + `questions[].prompt`（问题内容）和 `answer_hint.actions`（可选动作），用户回复后拼接 `nocode answer` 命令执行。详见 [create & send 规则](references/commands/cmd-create-send.md)「question 事件处理」章节 |
| `暂无可部署版本` | 先创建或修改生成代码 |
| `域名已被占用` / `域名格式不正确` | 请用户更换域名；域名只传主体，不包含 `https://` 前缀 |
| `属于系统前缀域名，不支持新增` | 前缀域名全局唯一、由部署产生，改用 `nocode domain modify` 修改已有的那一条 |
| `系统前缀域名 xxx 不可删除` | 删除后作品将无法访问，只能改前缀 |
| `由部署历史自动生成（只读），不可删除` | 负数 ID 为虚拟记录；可通过修改前缀域名刷新 `external_url` 清除残留 |
| `团队已设置「作品权限强制指定对象」` / `有权限变更申请正在审批中` | **⛔ 禁止重试绕过。** 如实告知用户（仅团队管理员可变更 / 需等审批完成） |
| `MIS 号不存在` | 用 `nocode permission search-user` 查询确认，禁止猜测 |
| `search-org` 返回空数组 | **大概率是传了简称而非完整路径**，不要误判为「部门不存在」。引导用户从大象用户信息卡片的「部门」一栏整段复制完整路径 |
| `非最新版本，无法变更权限控制` | 提示用户先切换到最新版本 |
| `获取文件内容失败` | 检查路径，先用 `nocode files list <chatId>` 确认文件存在 |
| 渲染失败 / 截图白屏 / 部署异常 / 页面无法访问 | **⛔ 平台侧异常，禁止自行修复。** 停止操作，告知用户并引导联系 NoCode 研发排查 |
| Agent 连续 2 次 `error` 事件 | **⛔ 停止重试，** 告知用户并引导联系 NoCode 研发排查 |

## 🚨 异常处理规则

遇到平台侧异常（渲染失败、部署失败、容器崩溃、Agent 连续失败等）时，严禁自行解决，必须立即停止操作并引导用户联系 NoCode 研发排查。

**禁止的处理方式：**

- ❌ 尝试通过 `nocode send` 让 Agent 修复渲染问题（如 "修复页面白屏"）
- ❌ 反复重试部署命令期望异常自行恢复
- ❌ 猜测异常原因并自行实施修复方案
- ❌ 不告知用户异常情况就静默重试

**正确做法：** 停止操作 → 告知用户具体错误信息 → 建议联系 NoCode 研发排查处理
