# NoCode Agent 能力说明

## 什么是 NoCode Agent

NoCode Agent 是运行在 NoCode 平台云端 IDE 容器中的 AI，通过 `nocode create` 和 `nocode send` 触发，负责生成和修改应用代码。作品完成 database 接入后，Agent 生成的运行时代码可以使用预置的 Supabase Client 访问业务数据。

外部编排阶段的数据库表结构、DDL、SQL、查询和数据 CRUD 不属于 NoCode Agent 的职责，必须使用 `catpaw-supabase` Skill。

## 三方职责边界

| 负责方 | 职责 | 不负责 |
|--------|------|--------|
| `nocode-cli` | NoCode 作品生命周期；数据库 `status/create/projects/connect`；容器配置和插件接入；触发应用代码生成 | 不查看表结构，不执行 DDL/SQL/CRUD |
| `catpaw-supabase` | 项目匹配、Schema、DDL、只读 SQL、查询、聚合、CRUD，以及对应的认证、RLS、角色权限和两阶段确认 | 不管理 `chatId`，不生成或部署 NoCode 页面 |
| NoCode Agent | 基于已存在的数据库结构生成页面、交互和运行时数据访问代码 | 不在外部编排阶段建表、改表、执行 SQL 或导入数据 |

**核心原则：NoCode CLI 管资源绑定，catpaw-supabase 管数据库，NoCode Agent 管应用代码。**

## 数据库协作流程

1. 使用 `nocode database status <chatId>` 检查作品绑定状态
2. 未连接时，由用户选择 `create` 或 `projects` + `connect`
3. 从可用状态中取得 `projectUrl`
4. 读取 `catpaw-supabase` Skill，调用 `list_my_projects` 按 URL 精确匹配 `projectId`
5. 使用 `catpaw-supabase` 完成 Schema、DDL、查询和数据准备
6. 完成后再用 `nocode send` 要求 Agent 基于已有表实现应用代码

详细规则见 [database 资源接入与 Supabase 协作规则](commands/cmd-database.md)。

## NoCode Agent 的数据库运行时集成

作品经过 `database create` 或 `database connect` 后，平台会完成 Supabase 插件接入。NoCode Agent 生成的应用代码可通过以下客户端访问数据库：

```javascript
import { supabase } from "@/integrations/supabase/client"
```

这表示应用在运行时可以读取和修改业务数据，不表示外部 Agent 可以通过 `nocode send` 让 NoCode Agent 执行 DDL、SQL 或数据导入。

禁止修改或重建 Supabase 客户端配置文件；连接信息由 NoCode 平台的插件接入流程维护。

## 正确示例

### 纯前端修改

```bash
nocode send <chatId> "把标题改成红色"
```

### 数据库准备完成后生成应用

先通过 `catpaw-supabase` 创建并验证 `todos` 表，再发送：

```bash
nocode send <chatId> "数据库中已经存在 todos 表。请基于该表实现待办列表，支持新增、切换完成状态和删除；不要创建或修改数据库表结构，也不要导入初始化数据。"
```

## 禁止示例

```bash
# 禁止让 NoCode Agent 建表或改表
nocode send <chatId> "创建一个 todos 表，包含 id、title、done 字段"

# 禁止让 NoCode Agent 执行 SQL
nocode send <chatId> "执行 ALTER TABLE todos ADD COLUMN priority int"

# 禁止通过附件让 NoCode Agent 导入数据
nocode send <chatId> "把附件中的 CSV 导入 todos 表" --files ./todos.csv

# 禁止使用旧 CLI 数据面命令
nocode database tables <chatId>
nocode database select <chatId> --table todos
nocode database insert <chatId> --table todos --data '<json>'
```

如果 `catpaw-supabase` 出现权限不足、RLS 登录失败、项目匹配失败、限流或其他调用异常，必须停止数据库操作，并按照其 Skill 的错误处理规则向用户报告具体错误；不得继续尝试其他数据库操作路径。
