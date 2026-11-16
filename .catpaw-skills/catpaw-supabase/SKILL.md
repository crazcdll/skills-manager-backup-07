---
name: catpaw-supabase
description: "通过 Supabase MCP Server 操作多租户 Supabase 实例：数据库 CRUD 与聚合、只读 SQL 与迁移建表 DDL、表结构与项目列表、Storage 文件上传下载与 Bucket 管理、Edge Functions 部署与源码、Cron 定时任务、Secret 密钥、日志查询与故障排查；支持 SSO 登录换取会话令牌满足 RLS。当用户提到 Supabase、查数据库/表/数据、写库改数据、执行 SQL、建表迁移 DDL、PostgREST、TS 类型、Storage 文件、Bucket、签名 URL、Edge Function、Cron 定时任务、Secret 密钥、查日志、排障报错、服务异常、根因分析、定位问题时触发。"
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - b5c6e317a8

metadata:
  skillhub.creator: "sunchenyu02"
  skillhub.updater: "sunchenyu02"
  skillhub.version: "V12"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "75213"
  skillhub.high_sensitive: "false"
---

# Supabase MCP Skill

通过 MCP 协议与 Kubeplex Supabase Server 交互，实现对多租户 Supabase 实例的数据库读写和 Storage 文件管理。

## 连接信息

- **Base URL**: `https://kubeplex-mcp.sankuai.com/mcp/supabase/message`
- **协议**: MCP over HTTP（JSON-RPC 2.0）
- **认证**: Bearer Token（用户身份 access_token），服务端通过 SSO OIDC 验票解析 misId

## 认证流程

本 Skill 优先使用 `catdesk auth exchange` 获取用户身份票据，回退到 `mtsso-skills-official`。服务端的 `client_id`（即 audience）为 `b5c6e317a8`，请求时需在 HTTP Header 中携带以该 client_id 为 audience 的用户身份 access_token。

### 获取认证 Token

按以下优先级获取 token，从返回 JSON 中提取 access_token 字段：

**方式一（首选，CatPaw/CatDesk 环境）**：CatDesk 自带登录态，`catdesk` 命令全局可用，零外部依赖，不依赖本机 `agent_info` 文件或环境变量：

```bash
catdesk auth exchange --target-client-id b5c6e317a8
```

从返回 JSON 中提取 `.accessToken` 字段。若 `catdesk` 命令不存在，或 `catdesk auth info` 返回 `loggedIn=false`，则改用方式二。

**方式二（兜底，无 catdesk 的环境）**：依赖 mtsso 官方工具与本机 MOA 登录态：

```bash
npx mtsso-moa-local-exchange --audience "b5c6e317a8"
```

从返回 JSON 中提取 `.access_token` 字段。

### 请求时携带 Token

在所有 HTTP 请求的 Header 中添加：

```
Authorization: Bearer ${user_access_token}
```

其中 `${user_access_token}` 为上一步获取的 access_token。

### 注意事项

- 优先使用方式一（catdesk）；仅当 catdesk 不可用时回退方式二（mtsso）
- catdesk token 有效期约 1 小时，mtsso token 约 3 小时，同会话内相同 audience 可复用缓存
- 若请求返回 401 Unauthorized，说明 token 过期或无效，重新获取即可
- 方式一依赖 CatPaw/CatDesk 已登录；方式二依赖本机 MOA 登录态

## 请求格式

所有请求使用 JSON-RPC 2.0 格式 POST 到 base URL：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {"key": "value"}
  }
}
```

完整的 curl 示例：

```bash
curl -X POST https://kubeplex-mcp.sankuai.com/mcp/supabase/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${user_access_token}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_my_projects","arguments":{}}}'
```

## 可用 Tools

### 项目与元信息

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `list_my_projects` | 列出当前用户有权限的所有项目 | DEVELOPER |
| `list_tables` | 列出项目的所有数据库表 | DEVELOPER |
| `describe_table` | 获取表的完整列定义（类型、可空、默认值、注释） | DEVELOPER |

### 数据库读

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `select_rows` | 结构化查询表数据（支持 filter/order/embed/aggregate） | DEVELOPER |
| `count_rows` | 计算满足条件的行数 | DEVELOPER |

### 数据库写

DEVELOPER 角色调用以下工具须携带 `sessionToken`（受 RLS 约束，见「RLS 与 Session Token」）；ADMIN/OWNER 用 serviceKey 绕过 RLS。

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `insert_rows` | 插入数据行（单次最多 100 行，无需确认） | DEVELOPER |
| `update_rows` | 更新数据行（两阶段确认） | DEVELOPER |
| `delete_rows` | 删除数据行（两阶段确认） | DEVELOPER |
| `upsert_rows` | 插入或更新数据行（冲突时合并，单次最多 100 行） | DEVELOPER |

### 认证（SSO 登录）

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `auth_build_login_url` | 生成 SSO 授权链接（PKCE/implicit），供用户浏览器登录 | DEVELOPER |
| `auth_complete` | 解析登录回调，签发可复用的 `sessionToken`（默认 1h） | DEVELOPER |

### PG 直连（SQL / DDL / 元信息）

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `execute_sql` | 直连 Postgres 执行只读 SQL（READ ONLY 事务，5s 超时，最多 1000 行） | ADMIN |
| `apply_migration` | 执行数据库迁移（建表/DDL），破坏性操作两阶段确认 | ADMIN |
| `list_extensions` | 列出已安装的 PostgreSQL 扩展 | DEVELOPER |
| `generate_typescript_types` | 根据表结构生成 TypeScript 类型定义 | DEVELOPER |

### Storage 文件管理

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `storage_list_buckets` | 列出项目所有 Bucket | DEVELOPER |
| `storage_list` | 列出 bucket 中的文件 | DEVELOPER |
| `storage_download` | 下载文件（base64 返回，>50MB 自动返回签名 URL） | DEVELOPER |
| `storage_upload` | 上传小文件（base64 输入，建议 < 1MB） | ADMIN |
| `storage_upload_url` | 生成签名上传 URL（客户端直传，适合大文件） | ADMIN |
| `storage_signed_url` | 生成限时访问 URL（默认 1h，最长 24h） | DEVELOPER |
| `storage_delete` | 删除文件（两阶段确认） | OWNER |
| `storage_create_bucket` | 创建 Storage Bucket（可指定是否公开） | ADMIN |
| `storage_move` | 移动 Storage 文件（不支持跨 bucket） | ADMIN |
| `storage_copy` | 复制 Storage 文件（不支持跨 bucket） | ADMIN |

### Edge Functions（边缘函数）

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `list_edge_functions` | 列出项目所有边缘函数（含 slug、状态、版本、调用地址） | DEVELOPER |
| `get_edge_function_detail` | 查看单个边缘函数详情与源码文件内容 | DEVELOPER |
| `deploy_edge_function` | 部署/更新边缘函数（首次部署直接执行，覆盖已有函数两阶段确认） | ADMIN |
| `delete_edge_function` | 删除边缘函数（两阶段确认） | OWNER |

### Cron 定时任务

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `list_cron_jobs` | 列出定时任务（不传 id）或查询单个任务详情（传 id） | DEVELOPER |
| `manage_cron_job` | 创建/更新/启停定时任务（action=create/update/setStatus，非破坏） | ADMIN |
| `delete_cron_job` | 删除定时任务（两阶段确认） | ADMIN |

### Secret 密钥

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `list_secrets` | 列出项目密钥（返回明文值，供用户审查/排错） | DEVELOPER |
| `manage_secret` | 创建/更新密钥（action=create/update） | ADMIN |
| `delete_secret` | 删除密钥（两阶段确认） | ADMIN |

### 日志查询

| Tool | 描述 | 最低角色 |
|------|------|---------|
| `query_supabase_logs` | 按容器类型与时间范围查询实例日志（腾讯云 CLS） | DEVELOPER |

## 关键概念

### 项目标识

每个操作（除 `list_my_projects`）都需要指定目标项目，二选一：
- `projectId`（数字）：项目 ID
- `projectUrl`（字符串）：项目 URL，服务端自动反查 projectId

推荐工作流：先调用 `list_my_projects` 获取项目列表，再使用返回的 projectId。

### 角色权限

三种角色权限递增：
- **DEVELOPER**：元信息查询、CRUD 数据操作（select/count/insert/update/delete/upsert，须携带 `sessionToken`，受 RLS 约束）、SSO 登录、列出扩展、生成 TS 类型、Storage 读取、边缘函数详情（get_edge_function_detail）、Cron/Secret 只读（list_cron_jobs、list_secrets）、日志查询（query_supabase_logs）
- **ADMIN**：在 DEVELOPER 基础上增加 PG 直连（execute_sql / apply_migration）、Storage 写操作（上传、创建 Bucket、移动、复制）、边缘函数部署（deploy_edge_function）、Cron 写与删除（manage_cron_job、delete_cron_job）、Secret 写与删除（manage_secret、delete_secret）；CRUD 用 serviceKey 绕过 RLS
- **OWNER**：所有操作（包括 storage_delete、delete_edge_function）

### RLS 与 Session Token

CRUD 工具（`select_rows` / `count_rows` / `insert_rows` / `update_rows` / `delete_rows` / `upsert_rows`）受行级权限（RLS）保护：

- **DEVELOPER 角色**：调用上述任一工具（含只读的 select/count）**必须携带 `sessionToken`**，否则返回 `E_AUTH_REQUIRED`。服务端用用户身份（anonKey + User JWT）访问，RLS 按用户隔离行。
- **ADMIN / OWNER 角色**：忽略 `sessionToken`，统一用 serviceKey 访问（绕过 RLS，可见全量数据）。

获取 `sessionToken` 的流程（仅 DEVELOPER 需要）：

```
1. 调用 auth_build_login_url → 返回 loginUrl（PKCE 模式还返回 codeVerifier）
2. 引导用户在浏览器打开 loginUrl 完成美团 SSO 登录，得到回调 URL
3. 调用 auth_complete（传 callbackUrl，PKCE 模式还需传 codeVerifier）→ 返回 sessionToken
4. 后续 CRUD 调用在 arguments 中携带 sessionToken
```

注意：

- `sessionToken` 默认有效期约 1 小时，过期后返回 `E_SESSION_EXPIRED`，需重新登录
- `sessionToken` 与签发时的 misId、projectId 绑定，不匹配返回 `E_SESSION_MISMATCH`
- 篡改或非法的 token 返回 `E_SESSION_INVALID`

### 两阶段确认（Dangerous Operations）

`update_rows`、`delete_rows`、`storage_delete`、`apply_migration`（破坏性 DDL）、`deploy_edge_function`（覆盖已有函数时）、`delete_edge_function`、`delete_cron_job`、`delete_secret` 使用两阶段确认机制。

**重要**：第一步返回的预览信息（影响行数、将删除的文件列表等）**必须展示给用户**，等用户明确确认后才可执行第二步。禁止自动跳过确认。

**第一步**：不传 `confirmToken`，服务端返回预览信息：
```json
{
  "phase": "preview",
  "affectedEstimate": 5,
  "confirmToken": "<服务端返回的确认令牌>",
  "expiresAt": 1716300000000
}
```

→ **此时必须将预览结果告知用户**，例如：「此操作将影响 5 行数据，确认执行吗？」

**第二步**：用户确认后，使用完全相同的参数 + 返回的 `confirmToken` 再次调用：
```json
{
  "phase": "executed",
  "data": null
}
```

注意：
- confirmToken 30 秒内有效，且只能使用一次
- 若用户未确认或拒绝，**不得执行第二步**
- 若 token 过期，需重新执行第一步获取新 token

### PostgREST 过滤语法

filters 对象中 value 使用 PostgREST 表达式：
- `eq.value` — 等于
- `neq.value` — 不等于
- `gt.value` / `gte.value` — 大于 / 大于等于
- `lt.value` / `lte.value` — 小于 / 小于等于
- `like.*pattern*` / `ilike.*pattern*` — 模糊匹配（ilike 不区分大小写）
- `in.(v1,v2,v3)` — IN 列表
- `is.null` / `is.true` / `is.false` — IS 判断
- `not.eq.value` — 取反

## 各 Tool 详细参数

### list_my_projects

无需参数，返回：
```json
{ "projects": [{ "projectId": 1, "appCategory": "xxx", "url": "https://...", "role": "ADMIN", "projectName": "我的项目" }] }
```

### list_tables

```json
{ "projectId": 123 }
```
返回：`{ "tables": ["users", "orders", "products"], "_meta": { "cache": "hit" } }`

### describe_table

```json
{ "projectId": 123, "table": "users" }
```
返回列定义数组，包含 name、type、nullable、default、comment。

> CRUD 工具（select/count/insert/update/delete/upsert）：DEVELOPER 角色须在 `arguments` 中额外携带 `sessionToken`（见「RLS 与 Session Token」）；ADMIN/OWNER 无需携带。下方示例为简洁省略了该字段。

### select_rows

```json
{
  "projectId": 123,
  "table": "users",
  "columns": ["id", "name", "email"],
  "filters": { "age": "gte.18", "status": "eq.active" },
  "or": ["city=eq.北京", "city=eq.上海"],
  "order": "created_at.desc",
  "limit": 50,
  "offset": 0,
  "embed": ["orders(id,total)"],
  "count": "exact"
}
```

- `limit` 默认 100，最大 1000
- `columns` 支持别名写法 `alias:col`、JSON 路径 `col->>field`
- `embed` 支持 FK 嵌入式资源加载
- `aggregate` + `groupBy` 支持聚合查询

### count_rows

```json
{ "projectId": 123, "table": "orders", "filters": { "status": "eq.pending" } }
```
返回：`{ "total": 42 }`

### insert_rows

```json
{
  "projectId": 123,
  "table": "users",
  "rows": [
    { "name": "张三", "email": "zhangsan@example.com", "age": 28 },
    { "name": "李四", "email": "lisi@example.com", "age": 25 }
  ],
  "returnRepresentation": true
}
```
- 单次最多 100 行
- `returnRepresentation: true` 时返回插入后的完整行

### update_rows

```json
{
  "projectId": 123,
  "table": "users",
  "filters": { "id": "eq.5" },
  "set": { "name": "新名称", "age": 30 },
  "confirmToken": "（第二步时填入第一步返回的 token）"
}
```
- `filters` 必填，禁止无条件更新

### delete_rows

```json
{
  "projectId": 123,
  "table": "users",
  "filters": { "status": "eq.inactive", "last_login": "lt.2025-01-01" },
  "confirmToken": "（第二步时填入第一步返回的 token）"
}
```
- `filters` 必填，禁止无条件删除

### storage_list_buckets

```json
{ "projectId": 123 }
```
返回：`{ "buckets": [{ "id": "avatars", "name": "avatars", "public": true, "createdAt": "...", "updatedAt": "..." }] }`

### storage_list

```json
{ "projectId": 123, "bucket": "avatars", "prefix": "users/", "limit": 100, "offset": 0 }
```

### storage_download

```json
{ "projectId": 123, "bucket": "avatars", "path": "users/avatar1.png" }
```
- 返回 base64 编码的文件内容
- 文件 >50MB 时自动返回签名 URL；有效期 1 小时

### storage_upload

```json
{
  "projectId": 123,
  "bucket": "documents",
  "path": "reports/2026-Q1.pdf",
  "data": "<base64 编码的文件内容>",
  "contentType": "application/pdf",
  "upsert": false
}
```
- **仅适用于文件大小 < 1MB 的情况**；≥ 1MB 的文件请使用 `storage_upload_url` 获取签名 URL 后直传
- 禁止上传危险扩展名（.exe, .sh, .bat, .cmd, .ps1）

### storage_upload_url

```json
{
  "projectId": 123,
  "bucket": "documents",
  "path": "reports/large-report.zip",
  "upsert": true
}
```
返回签名上传 URL，客户端用 PUT 方法直接上传文件二进制内容：
```bash
curl -X PUT "${signedUrl}" \
  -H "Content-Type: application/zip" \
  --data-binary @large-report.zip
```
- **文件大小 ≥ 1MB 时使用此方式**（无大小限制，文件直传不经过 MCP 服务器）
- 注意：若路径含非 ASCII 字符（如中文），需对签名 URL 的路径部分做 URL encode，再发起 PUT 请求
- 禁止上传危险扩展名（.exe, .sh, .bat, .cmd, .ps1）

### storage_signed_url

```json
{ "projectId": 123, "bucket": "documents", "path": "reports/2026-Q1.pdf", "expiresIn": 7200 }
```
- `expiresIn` 默认 3600 秒，最大 86400 秒（24 小时）

### storage_delete

```json
{
  "projectId": 123,
  "bucket": "temp",
  "paths": ["uploads/old-file.txt", "uploads/draft.doc"],
  "confirmToken": "（第二步时填入第一步返回的 token）"
}
```

### upsert_rows

```json
{
  "projectId": 123,
  "table": "users",
  "rows": [
    { "id": 1, "name": "张三", "email": "zhangsan@example.com" }
  ],
  "returnRepresentation": false
}
```
- 冲突行合并更新（PostgREST `resolution=merge-duplicates`），单次最多 100 行
- DEVELOPER 角色须携带 `sessionToken`

### auth_build_login_url

```json
{ "projectId": 123, "flowType": "pkce", "redirectTo": "https://your-app/callback" }
```
- `flowType` 默认 `pkce`（返回 `loginUrl` + `codeVerifier`）；`implicit` 仅返回 `loginUrl`
- `redirectTo` 需在 Supabase 项目的 Redirect URLs 白名单中；未提供时使用 GoTrue 默认 Site URL

### auth_complete

```json
{ "projectId": 123, "callbackUrl": "https://your-app/callback?code=xxx", "codeVerifier": "（PKCE 模式填 auth_build_login_url 返回的值）" }
```
- implicit 模式：`callbackUrl` 为含 `#access_token=...` 的回调，无需 `codeVerifier`
- 返回：`{ "sessionToken": "...", "expiresAt": 1716300000000 }`

### execute_sql

```json
{ "projectId": 123, "sql": "SELECT id, name FROM users WHERE age >= 18 LIMIT 100" }
```
- 只读事务（READ ONLY），5s 超时，最多返回 1000 行（超出标记 `truncated`）
- 支持只读函数调用 `SELECT * FROM fn(args)`；写操作/DDL 请用 `apply_migration`

### apply_migration

```json
{
  "projectId": 123,
  "name": "create_orders_table",
  "sql": "CREATE TABLE orders (id bigserial primary key, amount numeric);",
  "confirmToken": "（破坏性 DDL 第二步时填入）"
}
```
- 非破坏性 DDL 直接执行；破坏性操作（任意 `DROP ...`、`TRUNCATE`）走两阶段确认
- 成功后自动执行 `GRANT` + `NOTIFY pgrst, 'reload schema'` 并记录迁移版本

### list_extensions

```json
{ "projectId": 123 }
```
返回已安装扩展列表（extname、schema、version）。

### generate_typescript_types

```json
{ "projectId": 123, "schemas": ["public"] }
```
- `schemas` 默认 `["public"]`，返回各表的 Row / Insert / Update 类型定义

### storage_create_bucket

```json
{ "projectId": 123, "name": "avatars", "public": false }
```
- `name` 仅允许字母数字下划线点连字符；`public` 默认 false

### storage_move

```json
{ "projectId": 123, "bucket": "avatars", "sourcePath": "tmp/a.png", "destinationPath": "users/a.png" }
```
- 仅支持同一 bucket 内移动，**不支持跨 bucket**（源和目标共用 `bucket` 参数）

### storage_copy

```json
{ "projectId": 123, "bucket": "avatars", "sourcePath": "users/a.png", "destinationPath": "backup/a.png" }
```
- 仅支持同一 bucket 内复制，**不支持跨 bucket**（源和目标共用 `bucket` 参数）

### list_edge_functions

```json
{ "projectId": 123 }
```
返回函数列表，每项含 `slug`、`name`、`status`、`version`、`verifyJwt`、`invokeUrl`（调用地址 `{实例URL}/functions/v1/{slug}`）等。

### deploy_edge_function

```json
{
  "projectId": 123,
  "slug": "hello-world",
  "code": "Deno.serve(req => new Response('ok'))",
  "entrypointPath": "index.ts",
  "verifyJwt": true,
  "confirmToken": "（覆盖已有函数第二步时填入）"
}
```
- `slug` 仅允许字母数字下划线连字符；`entrypointPath` 默认 `index.ts`，须以 .ts/.js/.tsx/.jsx 结尾
- 首次部署直接执行；覆盖同名函数走两阶段确认（第一步返回 `confirmToken` + 当前版本预览）
- 部署后自动触发同步即时生效；返回含 `invokeUrl`、`invokeExample`（curl）、`sdkExample`

### delete_edge_function

```json
{ "projectId": 123, "slug": "hello-world", "confirmToken": "（第二步时填入）" }
```
- 破坏性操作，两阶段确认；删除后自动触发同步即时生效

### get_edge_function_detail

```json
{ "projectId": 123, "slug": "hello-world" }
```
- `slug` 必填，仅允许字母、数字、下划线、连字符
- 返回函数元数据（`slug`、`name`、`status`、`version`、`entrypointPath`、`verifyJwt`、`createdAt`、`updatedAt`）与源码文件数组 `files`（每项含 `name`、`content`、`hash`）
- 函数不存在返回 `E_FUNCTION_NOT_FOUND`

### list_cron_jobs

```json
{ "projectId": 123, "id": 5 }
```
- 不传 `id`：返回任务列表 `{ "jobs": [...], "total": n }`
- 传 `id`：返回单个任务详情 `{ "task": {...} }`（含 `cronExpression`、`functionSlug`、`status`、`lastExecutionTime`、`nextExecutionTime` 等）

### manage_cron_job

```json
{
  "projectId": 123,
  "action": "create",
  "taskName": "每天同步",
  "functionSlug": "my-function",
  "cronExpression": "0 0 2 * * ?",
  "httpMethod": "POST",
  "requestBody": "{\"key\":\"value\"}"
}
```
- `action` 必填，取值 `create` / `update` / `setStatus`
- `create`：需 `taskName`、`functionSlug`（字母数字下划线连字符）、`cronExpression`（Spring 6 段格式）
- `update`：需 `id`，其余字段可选覆盖
- `setStatus`：需 `id` 与 `status`（`ENABLED` / `DISABLED`）
- 非破坏性操作，无需两阶段确认

### delete_cron_job

```json
{ "projectId": 123, "id": 5, "confirmToken": "（第二步时填入）" }
```
- `id` 必填，破坏性操作，两阶段确认

### list_secrets

```json
{ "projectId": 123 }
```
- 返回 `{ "secrets": [{ "secretName": "OPENAI_API_KEY", "secretValue": "sk-<your-openai-key>", "description": "...", "createdAt": ..., "updatedAt": ... }], "total": n }`
- 边缘函数 Secret 由用户自定义，返回明文值以便审查/排错

### manage_secret

```json
{
  "projectId": 123,
  "action": "create",
  "secretName": "OPENAI_API_KEY",
  "secretValue": "sk-<your-openai-key>",
  "description": "openai key",
  "encrypt": true
}
```
- `action` 必填，取值 `create` / `update`（更新为先删后建）
- `secretName` 必填，仅允许字母、数字、下划线；`secretValue` 必填（明文）
- 出参回显明文 `secretValue` 以便审查；更新的密钥不存在返回 `E_SECRET_NOT_FOUND`

### delete_secret

```json
{ "projectId": 123, "secretName": "OPENAI_API_KEY", "confirmToken": "（第二步时填入）" }
```
- `secretName` 必填，破坏性操作，两阶段确认

### query_supabase_logs

```json
{
  "projectId": 123,
  "containerName": "supabase-db",
  "from": 1716300000000,
  "to": 1716303600000,
  "query": "error",
  "limit": 10
}
```
- 无需传 `supabaseId`（服务端由 `projectId` 自动推导）
- `containerName` 从枚举中选择，默认 `supabase-db`：`supabase-kong`（Proxy）、`supabase-rest`（REST）、`supabase-auth`（Auth）、`supabase-storage`（Storage）、`edge`（Functions 边缘函数日志）、`supabase-realtime`（Realtime）、`supabase-meta`（Meta）、`supabase-studio`（Studio）、`supabase-db`（Database）
- `from` / `to` 为毫秒时间戳，未传默认最近 30 分钟；要求 `from < to`
- `limit` 默认 10，自动钳制到 [1, 1000]
- 返回 `{ "containerName", "from", "to", "limit", "hasLogs", "logCount", "logs": [...], "finalQuery", "message" }`

**错误排查场景的使用约定**：当用户是为了排查错误/报错/服务异常/定位问题而查日志时，若关键信息缺失，**必须先向用户询问以下必要信息后再调用**，不要盲目用默认值查询：

1. **组件（containerName）**：出问题的是哪个组件？（如 API 网关 `supabase-kong`、REST 接口 `supabase-rest`、认证 `supabase-auth`、存储 `supabase-storage`、边缘函数 `edge`、数据库 `supabase-db`、实时 `supabase-realtime` 等）—— 若用户不确定，可先列出枚举帮其判断。
2. **发生时间**：错误大约发生在什么时间？据此换算 `from`/`to`（默认仅最近 30 分钟，历史问题极易漏查）。
3. **错误描述**：报错的关键信息（错误码、关键字、接口路径等），据此设置 `query` 过滤，精准定位相关日志。

拿到上述信息后再发起查询；若查询无结果，主动建议用户扩大时间范围或更换组件重试。

**组件崩溃根因联查（关键）**：当查日志发现某组件挂掉/崩溃/重启/OOM（如日志出现 `panic`、`fatal`、`OOMKilled`、`exit`、`restart`、`terminated`、连接骤断等），**不要止步于"该组件挂了"这一结论，必须继续联查以定位触发崩溃的根因请求**：

1. **锁定崩溃时刻**：先从崩溃组件日志中确定精确的崩溃/重启时间点 `T`。
2. **回溯上游/网关日志**：以 `T` 前一段窗口（建议 `from = T - 2min`、`to = T`）查询上游组件，重点查网关 `supabase-kong`（含请求路径/方法/状态码/客户端），找出崩溃前最后经过的请求；再按需联查直接调用该组件的上游（如 `supabase-rest`、`supabase-auth`、`edge`、`supabase-realtime`）。
3. **定位嫌疑请求**：在上游日志中寻找异常特征——超大 body、异常路径/参数、高频重试、慢请求、5xx/499、超时等，锁定崩溃前的最后一个/异常请求作为嫌疑触发源。
4. **交叉验证**：若崩溃组件为 `supabase-db`，同时联查 `supabase-rest`/`edge` 找出触发的 SQL 或函数调用；必要时用 `execute_sql` 查慢查询/锁等待等佐证。
5. **输出根因链路**：向用户给出"嫌疑请求 → 经过组件 → 触发崩溃"的完整链路与时间线，而非仅报告"组件挂了"。

联查时应主动串联多个组件、逐段回溯时间窗口，直到找到可解释崩溃的根因请求为止。

## 错误码速查

| 错误码 | 含义 | 常见原因 |
|--------|------|---------|
| E_PROJECT_REQUIRED | 未指定项目 | 用户有多个项目但未传 projectId |
| E_NO_PERMISSION | 无项目权限 | misId 在该项目无任何角色 |
| E_ROLE_FORBIDDEN | 角色不足 | 如 DEVELOPER 尝试写操作 |
| E_RATE_LIMITED | 请求频率超限 | 默认 60 QPM |
| E_LIMIT_EXCEEDED | limit 超限 | select_rows limit > 1000 |
| E_BATCH_TOO_LARGE | 批量过大 | insert_rows > 100 行 |
| E_FILTER_REQUIRED | 缺少 filter | update/delete 未指定过滤条件 |
| E_CONFIRM_TOKEN_INVALID | 确认 token 无效 | 过期/已消耗/参数不匹配 |
| E_FILE_TOO_LARGE | 文件过大 | 上传 > 50MB |
| E_EXPIRES_TOO_LONG | 过期时间过长 | signed_url expiresIn > 86400 |
| E_DANGEROUS_FILE_TYPE | 危险文件类型 | 上传 .exe/.sh 等 |
| E_AUTH_REQUIRED | 需先完成 SSO 登录 | DEVELOPER 调 CRUD 未带 sessionToken |
| E_SESSION_EXPIRED | Session Token 过期 | sessionToken 超过有效期（默认 1h） |
| E_SESSION_INVALID | Session Token 无效 | token 被篡改或格式非法 |
| E_SESSION_MISMATCH | Session Token 不匹配 | misId/projectId 与签发时不一致 |
| E_AUTH_IDENTITY_MISMATCH | 登录身份不一致 | auth_complete 回调 JWT 身份与当前用户不符 |
| E_AUTH_FAILED | SSO 换票失败 | callbackUrl 无效或换票超时 |
| E_INVALID_PARAMS | 参数非法 | 缺少必填参数 / 标识符非法 |
| E_SQL_TIMEOUT | SQL 执行超时 | execute_sql 超过 5s |
| E_PG_UNAVAILABLE | PG 直连不可用 | 项目未配置 PG 直连地址（tenantId 缺失） |
| E_EDGE_FUNCTION_LIST_FAILED | 边缘函数列表获取失败 | 平台 API 异常；部署时为避免误覆盖会拒绝 |
| E_EDGE_FUNCTION_DEPLOY_FAILED | 边缘函数部署失败 | 平台 API 异常或源码非法 |
| E_EDGE_FUNCTION_DELETE_FAILED | 边缘函数删除失败 | 平台 API 异常 |
| E_FUNCTION_NOT_FOUND | 函数不存在 | get_edge_function_detail 指定 slug 不存在 |
| E_FUNCTION_DETAIL_FAILED | 函数详情/源码获取失败 | 平台 API 异常 |
| E_CRON_NOT_FOUND | 定时任务不存在 | 指定 id 的任务不存在 |
| E_CRON_LIST_FAILED | 定时任务列表/详情获取失败 | 平台 API 异常 |
| E_CRON_WRITE_FAILED | 定时任务创建/更新/启停失败 | 平台 API 异常 |
| E_CRON_DELETE_FAILED | 定时任务删除失败 | 平台 API 异常 |
| E_SECRET_NOT_FOUND | 密钥不存在 | 更新的密钥不存在 |
| E_SECRET_LIST_FAILED | 密钥列表获取失败 | 平台 API 异常 |
| E_SECRET_WRITE_FAILED | 密钥创建/更新失败 | 平台 API 异常（如名称已存在） |
| E_SECRET_DELETE_FAILED | 密钥删除失败 | 平台 API 异常 |
| E_LOG_QUERY_FAILED | 日志查询失败 | CLS 返回 success=false 或网络异常 |

## 典型工作流示例

### 查询数据

```
1. 调用 list_my_projects → 获取项目列表
2. 调用 list_tables → 查看有哪些表
3. 调用 describe_table → 了解表结构
4. 调用 select_rows → 查询需要的数据
```

### 修改数据

```
1. 调用 select_rows 确认要修改的记录存在
2. 调用 update_rows（不带 confirmToken）→ 获取预览和 token
3. 确认影响行数合理后，调用 update_rows（带 confirmToken）→ 执行更新
```

### 文件上传

上传前检查文件大小，选择对应方式：
```
文件 < 1MB：
  python <skill_dir>/storage_upload.py --token "<token>" --project-id <id> --bucket <bucket> --path <remote_path> [--content-type <mime>] [--upsert] <local_file>

文件 ≥ 1MB：
  1. 调用 storage_upload_url 获取签名上传 URL
  2. curl -X PUT "<signed_url>" -H "Content-Type: <mime_type>" --data-binary @<local_file>
     （若 URL 路径含非 ASCII 字符，需对路径部分做 URL encode）
```

### 文件下载

```
调用 storage_download：
  - 若返回 base64，用脚本保存：
    python <skill_dir>/storage_download.py base64 "<base64_data>" <output_path>
    （若 base64 过长无法作为命令行参数，先写入临时文件再用 base64file 模式）
    python <skill_dir>/storage_download.py base64file <tmp_file> <output_path>
  - 若返回签名 URL（大文件 >50MB）：
    curl -o <output_path> "<signed_url>"
```

### 文件管理

```
1. storage_list_buckets → 查看 Bucket
2. storage_list → 浏览文件列表
3. 下载/上传：按上方对应策略操作
4. storage_signed_url → 生成分享链接
```

## 安全规范

本 Skill 所有操作均通过 Kubeplex Supabase MCP Server 执行，服务端内置多层安全机制（身份认证、权限校验、数据脱敏、操作审计），确保数据访问可控、可审计、可追溯。详细安全设计见 [SECURITY.md](./SECURITY.md)。

核心保障：
- 全链路 SSO OIDC 身份认证，操作绑定 misId 可追溯
- 三级角色权限（DEVELOPER → ADMIN → OWNER）最小权限原则
- 敏感列服务端自动脱敏，系统表自动过滤不可见
- 签名 URL 短时效（下载 1h / 上传 10min），防泄露转发
- 危险操作两阶段确认 + 服务端完整审计日志
- QPM 限流 + 批量拉取防护，防暴力遍历

## 注意事项

- **禁止自行编写上传/下载脚本**，必须使用本 Skill 目录下已有的 `storage_upload.py` 和 `storage_download.py`
- url 上传/下载统一使用 curl 命令
- 所有操作受 QPM 限流（默认 60 次/分钟）
- Schema 自省结果缓存 60 秒
- 系统表（kp_*、auth.*、storage.* 前缀）已自动过滤，不可见
- 写操作前务必确认 filters 正确，避免误操作
- confirmToken 有效期仅 30 秒，获取后需尽快使用

