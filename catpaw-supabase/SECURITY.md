# Supabase MCP Skill 安全规范

本 Skill 所有操作均通过 Kubeplex Supabase MCP Server 执行，服务端内置多层安全机制，确保数据访问可控、可审计、可追溯。

## 文件下载安全

- **身份鉴权**：所有下载请求经 SSO OIDC 验票，服务端解析 misId 后校验其在目标项目中的角色权限，无权限用户无法访问任何文件
- **Bucket 权限隔离**：private bucket 中的文件下载必须经过服务端签名验证，无法通过直链访问
- **签名 URL 时效控制**：大文件（>50MB）返回的签名 URL 有效期仅 1 小时，过期自动失效，无法长期持有或转发
- **访问范围限制**：用户仅能下载其已授权项目内的文件，跨项目访问会返回 `E_NO_PERMISSION` 错误

## 数据查询安全

- **身份级权限控制**：所有查询请求经 OIDC 验票解析 misId，查询范围严格限定在用户有角色权限的项目内
- **系统表过滤**：系统表（`kp_*`、`auth.*`、`storage.*` 前缀）已在服务端自动过滤，不可见、不可查询
- **敏感列自动脱敏**：服务端对包含敏感信息的列（如 password、secret、token 等关键字前缀/后缀的列）自动脱敏后返回，Agent 和用户无法获取原始明文
- **批量拉取防护**：`select_rows` 单次最大返回 1000 行，且全局 QPM 限流 60 次/分钟，防止通过高频请求批量拖取数据
- **查询审计日志**：服务端记录所有查询操作的完整日志，包括操作者 misId、查询表名、过滤条件、返回行数和时间戳

## 文件上传审计

- **签名 URL 绑定身份**：`storage_upload_url` 生成的签名 URL 由服务端创建，内含上传者 misId、目标 bucket/path、生成时间戳等信息，所有上传行为可追溯到具体操作者
- **签名 URL 短时效**：签名上传 URL 默认有效期 10 分钟，过期即失效，无法被重放或转发利用
- **服务端操作日志**：文件上传完成后，Storage 服务端自动记录完整的审计日志（操作者 misId、文件路径、文件大小、Content-Type、上传时间戳），不依赖客户端日志
- **文件类型白名单**：服务端强制校验文件扩展名，禁止上传危险文件类型（.exe, .sh, .bat, .cmd, .ps1），即使通过签名 URL 直传也会被拒绝
- **角色权限门槛**：上传操作（`storage_upload` 和 `storage_upload_url`）最低要求 ADMIN 角色，DEVELOPER 无法执行上传

## 通用安全机制

- **全链路身份认证**：所有请求必须携带有效的 SSO OIDC access_token，服务端验票后绑定 misId，每一次操作可追溯到具体操作者
- **Token 短有效期**：access_token 有效期约 3 小时，降低 token 泄露后的影响窗口
- **QPM 限流**：全局 60 次/分钟限流，防止暴力遍历和批量数据拖取
- **危险操作两阶段确认**：`update_rows`、`delete_rows`、`storage_delete`、`apply_migration`（破坏性 DDL）、`manage_cron`（unschedule）使用两阶段确认机制，服务端生成短时有效的一次性 confirmToken，防止误操作和自动化攻击
- **最小权限原则**：三级角色（DEVELOPER → ADMIN → OWNER）权限递增；DEVELOPER 的 CRUD 操作须携带 Session Token，由 RLS + 数据库 GRANT 兜底行级与表级权限，ADMIN/OWNER 以 serviceKey 执行
