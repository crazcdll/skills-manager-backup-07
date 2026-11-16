# database 资源接入与 Supabase 协作规则

## 概述

`nocode database` 在本 Skill 中只负责 **NoCode 作品与 database 资源的绑定和工程接入**。允许使用的 action 只有：

- `status`：查询当前 `chatId` 的数据库绑定状态
- `create`：为当前作品新建并接入 database 资源
- `projects`：列出可复用的既有 database 资源
- `connect`：将既有 database 资源绑定并接入当前作品

NoCode 平台的 database 底层是 Supabase（PostgreSQL）。表结构、DDL、SQL、查询及数据增删改必须读取并遵循 `catpaw-supabase` Skill；禁止使用 `nocode database tables/select/insert/update/delete`。若 `catpaw-supabase` 调用失败，必须停止数据库操作并向用户报告具体错误，不得继续尝试其他数据库操作路径。

> 核心边界：`nocode-cli` 管作品和数据库的连接关系，`catpaw-supabase` 管数据库内部内容，NoCode Agent 管应用代码。

## database status — 查看作品数据库绑定状态

```bash
nocode database status <chatId>
```

该命令查询 NoCode 平台记录的作品与数据库关联状态，不是数据库健康检查，也不执行 SQL。

**已连接且已确认：**

```json
{
  "action": "status",
  "status": "success",
  "data": {
    "connected": true,
    "databaseType": "supabase_cloud",
    "isConfirmed": true,
    "url": "https://dbxxx.database.sankuai.com"
  }
}
```

只有 `connected: true` 且 `isConfirmed: true` 才表示数据库可用于后续操作。

**有关联资源但未确认：**

```json
{
  "action": "status",
  "status": "success",
  "data": {
    "connected": true,
    "databaseType": "supabase_cloud",
    "isConfirmed": false,
    "url": "https://dbxxx.database.sankuai.com"
  }
}
```

`isConfirmed: false` 时数据库不可用。必须询问用户选择新建（`create`）还是复用既有（`projects` + `connect`），不得直接访问数据库内容。

**未连接：**

```json
{
  "action": "status",
  "status": "success",
  "data": { "connected": false, "message": "该作品未关联数据库" }
}
```

如果用户只问作品是否关联数据库或绑定了哪个数据库，到这里即可，不需要调用 `catpaw-supabase`。

## database create — 新建并接入 database 资源

```bash
nocode database create <chatId>
```

执行前必须得到用户明确的新建意图。该命令不只是创建数据库，还会完成 NoCode 工程接入：

1. 检查是否已连接且已确认；已完成则返回 `{ created: false }`
2. 分配 database 资源
3. 将连接配置写入作品容器
4. 执行插件接入，安装依赖并生成客户端代码
5. 设置 NoCode SQL 自动执行模式

```json
{ "action": "create", "status": "success", "data": { "created": true } }
```

注意：

- 作品必须已通过 `nocode create` 初始化
- 操作可能超过 30 秒，不要超时中断
- 命令幂等，已完成接入时不会重复创建
- 成功后必须重新执行 `database status` 获取最终 `url` 和确认状态

## database projects — 列出可复用资源

```bash
nocode database projects <chatId>
```

列出当前用户可关联到 NoCode 作品的 database 项目，不暴露 `anonKey`。

```json
{
  "action": "projects",
  "status": "success",
  "data": [
    { "name": "Supabase-xxx", "url": "https://db1.database.sankuai.com" },
    { "name": "Supabase-yyy", "url": "https://db2.database.sankuai.com" }
  ]
}
```

必须把可选项目展示给用户，由用户选择；禁止按名称或 URL 猜测。空列表表示没有可复用资源，应询问用户是否新建。

## database connect — 绑定并接入既有资源

```bash
nocode database connect <chatId> --url <databaseUrl>
```

`--url` 必须来自本次 `database projects` 的结果且由用户明确选择。该命令会：

1. 获取用户可用项目并匹配 URL 对应的连接配置
2. 将项目绑定到当前 `chatId`
3. 写入容器配置并执行插件接入
4. 设置 NoCode SQL 自动执行模式

```json
{ "action": "connect", "status": "success", "data": { "connected": true } }
```

关联同一 database 的多个作品共享数据。成功后必须重新执行 `database status`，确认 `connected: true && isConfirmed: true`，并以返回的 `url` 作为后续 Supabase 项目匹配依据。

## 与 catpaw-supabase 的标准交接

当用户要求查看表结构、执行 DDL/SQL、查询或修改数据时，按以下顺序执行。

### 1. 确认 NoCode 绑定状态

```bash
nocode database status <chatId>
```

- `connected: true && isConfirmed: true`：记录 `data.url` 为 `projectUrl`，继续
- `isConfirmed: false` 或 `connected: false`：询问新建还是复用，完成 `create` 或 `projects` + `connect` 后重新检查

### 2. 读取 catpaw-supabase Skill

必须实际读取 `catpaw-supabase/SKILL.md` 并遵循其最新认证、权限、RLS、确认、限流和工具参数规则。这里不复制具体工具参数，避免两份规则漂移。

### 3. 将 projectUrl 映射为 projectId

调用 `catpaw-supabase` 的 `list_my_projects`，使用 `status.data.url` 精确匹配项目 URL：

1. URL host 转小写
2. 去除末尾 `/`
3. 不按项目名称模糊匹配
4. 唯一匹配后使用其 `projectId`
5. 无匹配时停止并报告权限或项目同步问题
6. 多个匹配时停止并让用户选择，禁止自行判断

不得把 `anonKey`、service key、SSO access token 或 Supabase `sessionToken` 放进 `nocode send` prompt、日志或面向用户的输出。

### 4. 数据库内容全部由 catpaw-supabase 操作

| 意图 | catpaw-supabase 能力 |
|------|----------------------|
| 查看表列表 | `list_tables` |
| 查看字段结构 | `describe_table` |
| 查询数据 | `select_rows` |
| 统计数据 | `count_rows` |
| 插入数据 | `insert_rows` |
| 插入或更新 | `upsert_rows` |
| 更新数据 | `update_rows` |
| 删除数据 | `delete_rows` |
| 执行只读 SQL | `execute_sql` |
| 建表、改表、迁移 | `apply_migration` |
| 生成 TypeScript 类型 | `generate_typescript_types` |

权限不足、RLS 登录失败、项目未找到、限流或其他 MCP 错误必须按 `catpaw-supabase` 规则处理：立即停止数据库操作并向用户报告具体错误，不得继续尝试其他数据库操作路径。

### 5. 数据库完成后再交给 NoCode Agent

数据库结构和必要数据准备完成后，才可让 NoCode Agent 实现应用代码。prompt 必须明确数据库对象已经存在，并禁止 Agent 再次修改数据库，例如：

```bash
nocode send <chatId> "数据库中已经存在 projects 表。请基于该表实现项目看板，包含进度展示、状态筛选和截止日期排序；不要创建或修改数据库表结构，也不要导入数据。"
```

NoCode Agent 运行时代码继续使用作品中已接入的 Supabase Client；这不等同于允许 Agent 在编排阶段执行 DDL 或导入数据。

## 写操作和批量数据规则

所有规则以 `catpaw-supabase` Skill 的最新定义为准，并额外遵守：

- 写入、upsert、migration 前展示目标项目、表名、记录数或 SQL 摘要，并获得用户确认
- `update_rows`、`delete_rows` 和破坏性 migration 必须完成服务端两阶段确认；第一阶段预览必须展示给用户
- DEVELOPER 的 CRUD 必须使用与目标项目绑定的 `sessionToken` 并遵循 RLS
- ADMIN/OWNER 可能通过 service key 绕过 RLS；在访问全量数据前必须向用户说明权限语义
- 批量插入按 `catpaw-supabase` 单批上限切分，串行执行，禁止并发
- 大批量导入优先设计业务唯一键并使用 `upsert_rows`，以便失败后安全续传
- Schema 变更后重新调用 `describe_table`，不得沿用变更前结构

## 禁用的旧路径

以下命令即使当前 CLI 版本仍支持，也不得在新流程中调用：

```bash
nocode database tables <chatId>
nocode database select <chatId> --table <name>
nocode database insert <chatId> --table <name> --data '<json>'
nocode database update <chatId> --table <name> --id <id> --data '<json>'
nocode database delete <chatId> --table <name> --id <id>
```

同样禁止：

```bash
nocode send <chatId> "创建/修改某张表或执行某段 SQL"
nocode send <chatId> "把附件数据导入数据库"
```

若 `catpaw-supabase` 调用失败，必须停止数据库操作并向用户报告具体错误；不得执行以上旧路径，也不得尝试任何其他数据库操作方式。

## 异常处理

| 情况 | 处理方式 |
|------|---------|
| `database status` 未连接或 `isConfirmed: false` | 询问用户新建还是复用，再执行对应接入流程 |
| `database create` 失败 | 检查作品是否已通过 `nocode create` 初始化；平台异常则停止并联系 NoCode 研发 |
| `database connect` 未找到项目 | 重新执行 `projects`，只允许用户从真实列表选择 |
| `list_my_projects` 找不到 status URL | 规范化 URL 后仅重查一次；仍无匹配则报告权限或同步问题并停止 |
| Supabase 角色不足 | 告知所需角色，不得通过旧 CLI 或 Agent 绕过 |
| `E_AUTH_REQUIRED` / Session 错误 | 按 `catpaw-supabase` 的 SSO Session 流程处理 |
| 两阶段确认 token 过期 | 重新获取预览并再次展示，不得自动执行 |
| 限流或批次过大 | 按 Skill 的上限减小批次并串行处理，不得并发重试 |

## 典型流程

### 新建数据库并创建业务表

```text
1. 用户确认新建
2. nocode database create <chatId>
3. nocode database status <chatId> → 取得 projectUrl
4. 读取 catpaw-supabase Skill
5. list_my_projects → URL 精确匹配 projectId
6. apply_migration → 创建表
7. describe_table → 验证结构
8. nocode send → 仅生成基于已有表的应用代码
```

### 复用既有数据库

```text
1. nocode database projects <chatId>
2. 展示列表并由用户选择
3. nocode database connect <chatId> --url <用户选择的 URL>
4. nocode database status <chatId> → 确认可用
5. list_my_projects → 匹配 projectId
6. 后续 Schema/SQL/CRUD 全部使用 catpaw-supabase
```

### 查询或修改作品数据

```text
1. database status → projectUrl
2. list_my_projects → projectId
3. list_tables / describe_table → 确认目标表
4. select_rows / count_rows / insert_rows / upsert_rows / update_rows / delete_rows
5. 写操作按权限和两阶段确认规则执行
```
