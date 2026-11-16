# 最佳实践

> 遇到以下场景时，按对应流程执行。

| 触发特征 | 对应场景 |
|---------|---------|
| 用户给了 HTML 文件或 HTML URL（无论表述为"照着做"、"复刻"、"替换 index.html"、"嵌入"、"直接展示这个页面"等） | → 场景 1：HTML 复刻（若 HTML 本身是数据看板/报表，流程中会转入场景 2） |
| 用户给了 JSON/Excel/CSV 数据文件，或给了一个数据看板 HTML，要求做看板/报表 | → 场景 2：数据驱动看板 |
| 需求包含"纯静态"、"换框架"、"SSR"、"TypeScript 重构"等架构级改动 | → 场景 3：架构改动 |

---

## 1. 用户提供 HTML 文件要求实现页面

禁止替换 `index.html` 或其他受保护文件。**无论用户的表述是什么**（"替换 index.html"、"嵌入这个页面"、"跳转到这个 URL"、"直接展示"等），在 NoCode 中实现一个已有 HTML 的标准做法都是：**下载 HTML → 通过 `--files` 传给 NoCode Agent → 让 Agent 在当前工程内复刻。**

**流程：**

1. 如果 HTML 来自远程 URL，先下载到临时路径：`curl -sL '<url>' -o /tmp/ref.html`
2. **判断 HTML 内容类型**：读取下载的 HTML，判断其是否为数据看板/报表/仪表盘（包含表格、图表、动态数据等）：
   - **是数据看板** → 先通过 `--files` 将 HTML 传给 NoCode Agent **完全复刻页面效果**，再按场景 2 完成 database 流程（提取数据结构、建表、导入数据），最后让 NoCode Agent 将页面数据源改为从 database 读取
   - **不是数据看板**（纯展示页、落地页、营销页等）→ 继续步骤 3
3. 通过 `--files` 传给 NoCode Agent，让它基于当前工程技术栈复刻全部内容：
   - `nocode send <chatId> "参照附件 HTML，基于当前工程技术栈复刻其全部内容" --files /tmp/ref.html`

**禁止：**
- ❌ 用 curl/wget/cp 等命令直接覆盖 `index.html`
- ❌ 在 send prompt 中要求删除或修改 `index.html` 原有的 `<script>` 标签，或将其改为纯静态 HTML，或替换 `index.html`
- ❌ 将 HTML 内容粘贴到 prompt 中
- ❌ 用 `window.location.href` / meta refresh 跳转到目标 URL（S3/CDN 链接通常触发下载而非渲染）
- ❌ 用 iframe 嵌入目标 URL（跨域策略和下载头会导致无法渲染）

## 2. 用户提供数据文件（JSON/Excel/CSV）要求实现看板/报表

禁止将数据文件直接作为 `--files` 附件 send 给 NoCode Agent，也禁止让 NoCode Agent 通过 curl 下载数据文件。数据应入库，看板从 database 读取。

**不推荐**让 NoCode Agent 通过请求外部静态数据文件（JSON URL、CSV URL、Excel URL 等）的下载链接来驱动页面。推荐统一走 database 流程：先将数据导入 database，再让页面从 database 读取。

**流程：**

1. 本地读取并分析数据文件的结构（字段名、类型、关系、业务唯一键）
2. 按 [database 资源接入规则](commands/cmd-database.md) 检查作品绑定状态；未连接时引导用户选择新建或复用 database 资源
3. 从 `nocode database status <chatId>` 取得 `projectUrl`，读取 `catpaw-supabase` Skill，通过 `list_my_projects` 按 URL 精确匹配 `projectId`
4. 使用 `catpaw-supabase.apply_migration` 根据数据结构建表，再用 `describe_table` 验证最新 Schema；禁止通过 `nocode send` 建表
5. 将数据在本地整理为 JSON 对象数组，按 `catpaw-supabase` 的单批上限切分，通过 `insert_rows` 或具备业务唯一键时优先通过 `upsert_rows` **串行**导入；禁止逐行或并发写入
6. 数据准备完成后，通过 `nocode send` 让 NoCode Agent 基于已存在的表实现看板，并明确要求不得创建、修改表结构或导入数据

```text
# 示例流程（catpaw-supabase 工具参数以其 SKILL.md 最新定义为准）
nocode database create <chatId>
nocode database status <chatId>              → 取得 projectUrl
catpaw-supabase.list_my_projects              → URL 精确匹配 projectId
catpaw-supabase.apply_migration               → 创建 projects 表
catpaw-supabase.describe_table                → 验证 projects 表结构
catpaw-supabase.insert_rows / upsert_rows     → 按上限分批、串行导入
nocode send <chatId> "数据库中已经存在 projects 表。请从该表读取数据，实现项目看板，包含进度条、状态筛选和截止日期排序；不要创建或修改数据库表结构，也不要导入数据。"
```

**禁止：**
- ❌ `nocode send <chatId> "根据附件数据做一个看板" --files ./data.json`
- ❌ `nocode send <chatId> "执行 curl 下载这个 Excel 文件然后做看板"`
- ❌ 将 JSON/CSV 内容粘贴到 send prompt 中
- ❌ 通过 `nocode send` 创建或修改数据库表
- ❌ 使用 `nocode database tables/select/insert/update/delete` 操作数据库内容
- ❌ 对数据文件逐行调用 `insert_rows`，或并发启动多个数据库请求
- ❌ `catpaw-supabase` 调用失败后继续尝试其他数据库操作路径；此时必须停止数据库操作并向用户报告具体错误

**不推荐：**
- ⚠️ `nocode send <chatId> "请求 https://xxx/data.json 的下载链接获取数据并渲染看板"` — 应改为走 database 流程
- ⚠️ `nocode send <chatId> "请求 https://xxx/board_data.csv 的下载链接渲染报表"` — 应改为走 database 流程

## 3. 用户需求隐含架构改动

如果需求中包含"换成纯静态"、"改用 SSR"、"全部用 TypeScript 重构"等架构级改动，严禁直接 send/create。告知风险后按以下方式处理：

- **需要"纯静态页面"效果** → 按场景 1 处理，通过 `--files` 传给 NoCode Agent 复刻
- **其他架构级改动** → 拆成业务需求，让 NoCode Agent 在现有工程内增量实现
- **需扩展构建能力** → `vite.config.js` 完全禁止修改，在现有架构内寻找替代方案

详细的受保护文件清单和 Prompt 拦截规则见 [project-architecture.md](project-architecture.md)。

