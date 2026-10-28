# CLI 命令参考

完整参数说明，基于 `src/citadel-database/cli.ts` 实际实现。

涉及仪表盘或自动化时，必须先遵守 [SKILL.md 的仪表盘与自动化操作边界](../SKILL.md#仪表盘与自动化操作边界必须遵守)。

## 目录

- [CLI 命令参考](#cli-命令参考)
  - [目录](#目录)
  - [通用选项](#通用选项)
  - [createDatabase](#createdatabase)
  - [queryDatabaseTask](#querydatabasetask)
  - [createTable](#createtable)
  - [copyTable](#copytable)
    - [场景说明](#场景说明)
  - [listTables](#listtables)
  - [getTableMeta](#gettablemeta)
  - [checkFormulaCalculation](#checkformulacalculation)
  - [queryTableData](#querytabledata)
  - [addData](#adddata)
  - [updateData](#updatedata)
  - [deleteData](#deletedata)
  - [queryDeletedTables](#querydeletedtables)
  - [deleteTable](#deletetable)
  - [recoveryTable](#recoverytable)
  - [renameTable](#renametable)
  - [sortTable](#sorttable)
  - [copyTable](#copytable-1)
    - [使用场景](#使用场景)
    - [使用示例](#使用示例)
    - [注意事项](#注意事项)
  - [addTableColumns](#addtablecolumns)
    - [JSON 文件输入](#json-文件输入)
    - [`columnMetas` 格式说明](#columnmetas-格式说明)
    - [公式列 columnConfig 详细说明（columnType:9）](#公式列-columnconfig-详细说明columntype9)
    - [使用示例](#使用示例-1)
  - [updateColumnConfig](#updatecolumnconfig)
    - [`--columnConfig` 各列类型支持字段](#--columnconfig-各列类型支持字段)
    - [使用示例](#使用示例-2)
  - [视图管理](#视图管理)
  - [列类型说明](#列类型说明)
    - [富文本节点类型](#富文本节点类型)
    - [文本列完整写入示例](#文本列完整写入示例)
    - [富文本列超链接写入](#富文本列超链接写入)
  - [文件上传工作流](#文件上传工作流)
    - [⭐ 推荐方式：uploadFileAndAddData（一步完成）](#-推荐方式uploadfileandadddata一步完成)
    - [🔧 低层 API：uploadFileByS3Url + addData（分步操作）](#-低层-apiuploadfilebys3url--adddata分步操作)
  - [环境变量](#环境变量)
  - [示例工作流](#示例工作流)
    - [1. 创建完整的项目管理表格](#1-创建完整的项目管理表格)
    - [2. 数据迁移和备份](#2-数据迁移和备份)
    - [3. 附件列数据操作](#3-附件列数据操作)
    - [4. 使用 Token 认证的批量操作](#4-使用-token-认证的批量操作)
  - [getUserInfo - 获取用户信息（账号转换）](#getuserinfo---获取用户信息账号转换)
    - [功能说明](#功能说明)
    - [使用场景](#使用场景-1)
    - [参数说明](#参数说明)
    - [返回字段](#返回字段)
    - [使用示例](#使用示例-3)
      - [1. 查询单个用户信息](#1-查询单个用户信息)
      - [2. 批量查询多个用户](#2-批量查询多个用户)
      - [3. 输出原始 JSON（用于脚本处理）](#3-输出原始-json用于脚本处理)
      - [4. 与人员列配合使用（完整工作流）](#4-与人员列配合使用完整工作流)
      - [5. 批量处理（从文件读取 MIS 列表）](#5-批量处理从文件读取-mis-列表)
    - [注意事项](#注意事项-1)
    - [API 说明](#api-说明)
  - [queryUserIdentityByUid - 通过 UID 查询 MIS/empId](#queryuseridentitybyuid---通过-uid-查询-misempid)
    - [功能说明](#功能说明-1)
    - [使用场景](#使用场景-2)
    - [参数说明](#参数说明-1)
    - [返回字段](#返回字段-1)
    - [使用示例](#使用示例-4)
    - [注意事项](#注意事项-2)
  - [多维表格高级权限](#多维表格高级权限)
    - [getAdvancedPermStatus](#getadvancedpermstatus)
    - [updateAdvancedPermStatus](#updateadvancedpermstatus)
    - [listAdvancedPermRoles](#listadvancedpermroles)
    - [getAdvancedPermRoleDetail](#getadvancedpermroledetail)
    - [createAdvancedPermRole](#createadvancedpermrole)
    - [renameAdvancedPermRole / deleteAdvancedPermRole](#renameadvancedpermrole--deleteadvancedpermrole)
    - [updateAdvancedPermRolePermissions](#updateadvancedpermrolepermissions)
    - [addAdvancedRoleMembers](#addadvancedrolemembers)
    - [deleteAdvancedRoleMembers](#deleteadvancedrolemembers)
      - [二期补充：管理员删除](#二期补充管理员删除)
    - [searchAdvancedMemberRoles](#searchadvancedmemberroles)
    - [updateAdvancedMemberRoles](#updateadvancedmemberroles)
    - [getAdvancedUserTablePermissions](#getadvancedusertablepermissions)
  - [getTableMeta 实用技巧：jq 提取列配置](#gettablemeta-实用技巧jq-提取列配置)
    - [提取单选/多选列的可选项](#提取单选多选列的可选项)
    - [检查人员列是否支持多人](#检查人员列是否支持多人)
    - [查看数字/日期列的格式化规则](#查看数字日期列的格式化规则)
    - [获取所有列 ID 和名称（用于构造 --columnIds）](#获取所有列-id-和名称用于构造---columnids)

## 通用选项

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--mis <mis>` | string | 从 `~/.config/clawdgw.json` 读取 | 用户 MIS 号，用于认证 |
| `--raw` | flag | false | 输出原始 JSON 响应 |
| `--clear-cache` | flag | — | 清除认证缓存后退出，不需要指定命令 |
| `--force-ciba` | flag | false | 强制走 CIBA 认证（仅在认证异常时兜底使用，正常不需要添加） |
| `--kmGray <value>` | string | — | 为 `km.sankuai.com` 请求添加 `Cookie: kmGray=<value>`（可选） |

## createDatabase

创建多维表格文档（包含文档和第一个数据表）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentTitle` | string | ❌ | — | 文档标题，可为空 |
| `--tableTitle` | string | ❌ | — | 数据表标题，可为空 |
| `--parentId` | string | ❌ | — | 父文档 ID |
| `--spaceId` | string | ❌ | — | 空间 ID |
| `--templateId` | string | ❌ | — | 模板 ID |
| `--columnMeta` | JSON | ❌ | — | 列定义 JSON 数组 |
| `--sourceContentId` | string | ❌ | — | 复制来源文档 ID |
| `--keepData` | boolean | ❌ | false | 复制时是否保留数据 |
| `--schemaVersion` | 1 / 2 | ❌ | 服务端默认 1 | 1 为旧版，2 为多维表格新模型（V2，仍在灰度中，灰度资格由服务端判断） |
| `--async` | true / false | ❌ | false | 异步创建后自动轮询最多 5 秒 |

```bash
# 创建空白多维表格
oa-skills citadel-database createDatabase \
  --contentTitle "项目管理" \
  --tableTitle "任务列表"

# 创建带列定义的表格
oa-skills citadel-database createDatabase \
  --contentTitle "项目管理" \
  --tableTitle "任务列表" \
  --columnMeta '[
    {"columnName":"项目名称","columnType":1},
    {"columnName":"负责人","columnType":1},
    {"columnName":"状态","columnType":3,"selectOptions":["待处理","进行中","已完成"]}
  ]'

# 复制已有多维表格文档（仅复制结构，不含数据）
oa-skills citadel-database createDatabase \
  --contentTitle "项目管理（副本）" \
  --sourceContentId "2750138424"

# 复制已有多维表格文档（同时保留数据）
oa-skills citadel-database createDatabase \
  --contentTitle "项目管理（副本）" \
  --sourceContentId "2750138424" \
  --keepData true
```

**输出**：同步创建返回文档 ID、表格 ID。异步创建返回任务 ID，CLI 每秒查询一次，最多等待 5 秒（从创建请求受理后开始计时）；成功时显示文档和表格 ID，失败时显示创建失败。5 秒内未完成则提示“多维表格文档创建中，请稍后再试”，保留任务 ID，使用下方查询命令继续查询，**不要重复执行创建命令**。查询报错时也应保留任务 ID，先查询原任务。

使用 `--schemaVersion 2` 创建 V2 文档；异步创建再加 `--async true`。

`--raw` 输出中，异步创建的 `success` 表示请求已受理，不能据此判断创建完成；仅 `taskStatus: 2` 表示完成。未完成时没有 `tableId`，超时提示在 `message` 中。尚未查到状态时 `taskStatus` 可缺省。

V2 创建无需指定灰度链路。创建失败时保留原始错误；返回业务错误码 `617` 或明确提示用户不在灰度范围时，可提醒用户加入试用群申请资格，普通权限不足不触发该提示。详见 [多维表格新模型试用](../SKILL.md#多维表格新模型试用)。

## queryDatabaseTask

查询已提交的异步创建任务，一次查询，不创建新文档。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `--taskId` | 正整数 | ✅ | 异步创建返回的任务 ID |

```bash
oa-skills citadel-database queryDatabaseTask --taskId 1234567890
```

状态 `taskStatus`：`0` 初始化、`1` 处理中、`2` 成功、`3` 失败。成功时返回 `tableIdList`，任务 ID 即创建文档的 ID；`success` 表示查询接口调用成功。只有状态为 `2` 后，才继续写入数据或授权。状态为 `3` 时停止并告知用户失败。测试环境创建的任务应继续使用 `--access-env test` 查询。

## createTable

在现有文档中创建新的数据表，表格标题可为空。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--tableTitle` | string | ✅ | — | 数据表标题 |
| `--columnMeta` | JSON | ❌* | — | 列定义 JSON 数组 |
| `--columnMetaFile` | string | ❌ | — | 从文件读取 columnMeta 参数（文件包含列定义数组） |
| `--sourceTableId` | string | ❌ | — | 复制来源表格 ID |
| `--keepData` | boolean | ❌ | false | 复制时是否保留数据 |

\* `--columnMeta` 和 `--columnMetaFile` 二选一，**优先使用 `--columnMetaFile`**

```bash
# 创建新表格
oa-skills citadel-database createTable \
  --contentId "2750248577" \
  --tableTitle "任务表" \
  --columnMeta '[{"columnName":"任务名","columnType":1}]'

# 从文件读取列定义（推荐用于复杂的列结构）
cat > columns.json << 'EOF'
[
  {
    "columnName": "姓名",
    "columnType": 1
  },
  {
    "columnName": "年龄",
    "columnType": 2
  },
  {
    "columnName": "状态",
    "columnType": 3,
    "selectOptions": ["在职", "离职", "休假"]
  },
  {
    "columnName": "负责人",
    "columnType": 4
  }
]
EOF

oa-skills citadel-database createTable \
  --contentId "2750248577" \
  --tableTitle "员工信息表" \
  --columnMetaFile columns.json
```

**💡 文件参数优先级**：当同时提供 `--columnMeta` 和 `--columnMetaFile` 时，使用 `--columnMetaFile` 中的数据。

**输出**：表格 ID，以及后端实际返回的非空标题/视图 ID/表格类型（若有）。

## copyTable

复制数据表到指定目标文档或表格。底层 `type` 仅支持：`3=学城文档`、`4=多维表格`；不传 `--targetType` 时会自动识别。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--sourceTableId` | string | ✅ | — | 源表格 ID |
| `--targetParentId` | string | ✅ | — | 目标文档/表格 ID |
| `--targetType` | number | ❌ | 自动识别 | 目标类型：`3=学城文档`、`4=多维表格` |
| `--columnIds` | string/JSON | ❌ | — | 要复制的列 ID（逗号分隔或 JSON 数组） |
| `--rowIds` | string/JSON | ❌ | — | 要复制的行 ID（逗号分隔或 JSON 数组） |
| `--stepVersion` | number | ❌ | — | 步进版本号 |
| `--viewIds` | string/JSON | ❌ | [1000] | 视图 ID 列表（逗号分隔或 JSON 数组，未提供时默认为 [1000]） |

```bash
# 复制整个表格
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424"

# 复制指定列和行
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424" \
  --columnIds "1,2,3" \
  --rowIds "100,101,102"
```

**输出**：新表格 ID、标题、视图 ID、表格类型。

> 说明：不传 `--targetType` 时，CLI 会优先自动识别常见目标类型（`3=学城文档`、`4=多维表格`）；若目标是模板，请显式传 `--targetType 2` 或 `--targetType 5`。

### 场景说明

**场景 A：复制整个多维表格文档**（使用 `createDatabase`，见上方章节）

```bash
# 仅复制结构
oa-skills citadel-database createDatabase \
  --contentTitle "新文档标题" \
  --sourceContentId "<原多维表格 contentId>"

# 同时保留数据
oa-skills citadel-database createDatabase \
  --contentTitle "新文档标题" \
  --sourceContentId "<原多维表格 contentId>" \
  --keepData true
```

**场景 B：将数据表复制到学城文档**（目标是已有学城文档，需额外插入 `:::xtable`）

```bash
# 步骤 1：复制数据表到目标学城文档
oa-skills citadel-database copyTable \
  --sourceTableId "<源 tableId>" \
  --targetParentId "<目标学城文档 contentId>" \
  --targetType 3
# → 得到新 tableId

# 步骤 2：将表格嵌入到学城文档正文（citadel skill）
# CitadelMD 中使用以下语法：
# :::xtable{xtableId="<新 tableId>"}:::
oa-skills citadel updateDocumentByMd \
  --contentId "<目标学城文档 contentId>" \
  --file <citadelmd文件路径>
```

**场景 C：复制数据表到另一个多维表格文档**

```bash
oa-skills citadel-database copyTable \
  --sourceTableId "<源 tableId>" \
  --targetParentId "<目标多维表格 contentId>" \
  --targetType 4
```

## listTables

查询文档下的所有数据表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |

```bash
oa-skills citadel-database listTables --contentId "2750138424"
```

**输出**：表格列表（表格标题、表格 ID）。

## getTableMeta

查询表格元数据（列信息、表版本与公式计算进度）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |

```bash
oa-skills citadel-database getTableMeta --tableId "2750248577"
```

**输出**：默认展示列信息列表（列名、列 ID、列类型、列配置）；加 `--raw` 获取 JSON，其中还包含服务端返回的 `stepVersion`、`formulaStepAppliedTSO`、`formulaStepPendingTSO`。

检查公式是否计算完成时，使用下方 `checkFormulaCalculation`，无需解析这些内部字段。

## checkFormulaCalculation

检查当前版本或指定数据变更的公式是否计算完成。只查询状态，不修改数据；每次调用检查一次，不自动等待。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | number | ✅ | — | 表格 ID，正安全整数 |
| `--stepVersion` | number | ❌ | 查询时的当前表版本 | 同一张表成功写入返回的版本，非负安全整数；指定后只检查该次变更引起的计算 |

```bash
# 检查当前版本
oa-skills citadel-database checkFormulaCalculation --tableId "1760355852"

# 检查指定变更；67018 应替换为本次成功写入返回的 stepVersion
oa-skills citadel-database checkFormulaCalculation \
  --tableId "1760355852" --stepVersion 67018 --raw
```

默认输出“公式计算已完成”“公式计算尚未完成”或“暂时无法确认公式计算是否完成”。`--raw` 输出：

```json
{"tableId":1760355852,"status":"completed"}
```

| status | 含义 | 后续动作 |
|---|---|---|
| `completed` | 当前版本或指定变更引起的公式计算已完成 | 可用 `queryTableData` 读取结果，仍遵守默认 `--max-pages 10` 预览规则 |
| `pending` | 尚未完成 | 如需等待，可间隔 1 秒重查，最多 30 次；不要重复写入 |
| `unknown` | 服务端缺少有效进度信息或返回状态不一致，无法确认 | 停止等待并告知用户无法确认，不视为完成 |

- 检查成功时退出码为 `0`，包括 `pending`、`unknown`；脚本应读取 `status`，不能仅凭退出码判定公式已完成。参数错误或请求失败时非零退出，保留原始错误。
- 写入后需要公式结果时，保留该次成功响应的 `stepVersion`，每次检查都传入同一张表和该版本，无需等待后续其他变更完成。未取得写入版本时，可以检查当前表状态，但不能声称追踪到了该次写入。
- 不传版本时，每次调用检查查询时的当前表状态。完成后再读数据仍可能遇到其他并发写入，不保证读取结果固定在检查时的版本。
- 查询失败或达到等待上限时停止，说明“尚未确认公式计算完成”，不要将未确认的公式值当作最终结果。CLI 已封装版本判断，不需要调用方处理 meta、Applied 或 Pending 字段。

## queryTableData

查询表格数据，支持筛选、排序和分页。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--columnIds` | string/JSON | ❌ | 前10列 | 要查询的列 ID（逗号分隔或 JSON 数组） |
| `--filter` | JSON | ❌ | — | 筛选条件 |
| `--sort` | JSON | ❌ | — | 排序配置，格式：`[{"columnId": 1, "desc": false}]`，**注意是 `desc` 字段（boolean），不是 `order` 字段** |
| `--viewId` | number | ❌ | — | 视图 ID（仅在**未传** `--columnIds`、`--filter`、`--sort` 时生效，直接使用该视图保存的列/筛选/排序配置进行查询） |
| `--pageSize` | number | ❌ | 100 | 每页返回的行数 |
| `--pageToken` | string | ❌ | — | 分页令牌（指定后只取该单页，不自动翻页） |
| `--max-pages` | number | ❌ | — | 最多自动翻页页数（不指定时获取全量数据） |

```bash
# 基础查询
oa-skills citadel-database queryTableData \
  --tableId "2750248577"

# 查询指定列
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --columnIds "1,2,3"

# 带筛选和排序
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --columnIds "1,2,3" \
  --filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"==","filterValue":["值"]}]}' \
  --sort '[{"columnId":2,"desc":true}]'

# 只取前 2 页（每页 100 行，最多 200 行），不获取全量数据
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --max-pages 2

# 按视图查询（使用视图保存的列/筛选/排序，不传 --columnIds/--filter/--sort）
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --viewId 1000 \
  --max-pages 10
```

> ⚠️ `--viewId` 仅在**未传** `--columnIds`、`--filter`、`--sort` 时生效。一旦传入任意一个，`--viewId` 自动忽略。

> 🔍 **链接含 viewId 时的查询规则**：若用户提供的多维表格链接中包含 `?view=<viewId>` 参数，且用户意图明确指向该视图（如"查询这个视图的数据"、"看看这个视图"、"查这个视图"），则执行 `queryTableData` 时**必须传入 `--viewId <id>`**。**禁止**在此场景下忽略链接中的 `viewId` 而执行无视图的全量查询。

**输出**：总行数、返回行数、数据行（包含 rowId 和 cellData）。

## addData

向表格添加新数据（使用二维数组格式）。

文本列支持的全部富文本节点见[文本列完整写入示例](#文本列完整写入示例)；链接专项示例见[富文本列超链接写入](#富文本列超链接写入)。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--columnIds` | string/JSON | ✅ | — | 列 ID（逗号分隔或 JSON 数组） |
| `--data` | JSON | ✅* | — | 二维数组格式的数据 `[["值1","值2"]]` |
| `--file` | string | ❌ | — | 从文件读取 data 参数（文件包含 JSON 数组） |

\* `--data` 和 `--file` 二选一，**优先使用 `--file`**

```bash
# 添加单行数据
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3" \
  --data '[["张三", 25, true]]'

# 添加多行数据
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3" \
  --data '[["张三", 25, true], ["李四", 30, false]]'

# 从文件读取大数据量（推荐用于 > 10 行的数据）
cat > data.json << 'EOF'
[
  ["员工001", 25, true, "2024-01-15"],
  ["员工002", 30, false, "2024-01-16"],
  ["员工003", 28, true, "2024-01-17"]
]
EOF

oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3,4" \
  --file data.json
```

**⚠️ 自动分页**：如果 `data` 超过 500 行，系统会自动分批处理，避免 API 请求失败。

**大数据量导入提醒**：Agent 在拆分批次前，按[多维表格新模型试用](../SKILL.md#多维表格新模型试用)规则统计本次导入总行数并提示用户。

**💡 文件参数优先级**：当同时提供 `--data` 和 `--file` 时，使用 `--file` 中的数据。

**输出**：成功状态、版本号、新增行的 rowIds。

## updateData

更新表格中的现有数据。

修改文本列中的链接或在原内容中追加链接，见[富文本列超链接写入](#富文本列超链接写入)。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--rowIds` | string/JSON | ✅* | — | 行 ID（逗号分隔或 JSON 数组） |
| `--rowIdsFile` | string | ❌ | — | 从文件读取 rowIds 参数（文件包含 JSON 数组） |
| `--columnIds` | string/JSON | ✅ | — | 列 ID（逗号分隔或 JSON 数组） |
| `--data` | JSON | ✅* | — | 二维数组格式的数据 |
| `--file` | string | ❌ | — | 从文件读取 data 参数（文件包含 JSON 数组） |

\* `--rowIds` 和 `--rowIdsFile` 二选一，`--data` 和 `--file` 二选一，**文件参数优先**

```bash
# 更新单行
oa-skills citadel-database updateData \
  --tableId "2750248577" \
  --rowIds "123456" \
  --columnIds "1,2" \
  --data '[["新值1", "新值2"]]'

# 更新多行
oa-skills citadel-database updateData \
  --tableId "2750248577" \
  --rowIds "123456,123457" \
  --columnIds "1,2" \
  --data '[["新值1", "新值2"], ["新值3", "新值4"]]'

# 从文件读取 rowIds 和 data（推荐用于大批量更新）
cat > rowIds.json << 'EOF'
["row_123", "row_124", "row_125"]
EOF

cat > update-data.json << 'EOF'
[
  ["新值1", 100],
  ["新值2", 200],
  ["新值3", 300]
]
EOF

oa-skills citadel-database updateData \
  --tableId "2750248577" \
  --columnIds "1,2" \
  --rowIdsFile rowIds.json \
  --file update-data.json
```

**⚠️ 自动分页**：如果 `data` 超过 500 行，系统会自动分批处理，避免 API 请求失败。

**大数据量导入提醒**：通过 `updateData` 导入数据时，同样遵循[多维表格新模型试用](../SKILL.md#多维表格新模型试用)规则，按本次导入总行数判断。

**💡 文件参数优先级**：
- 当同时提供 `--rowIds` 和 `--rowIdsFile` 时，使用 `--rowIdsFile`
- 当同时提供 `--data` 和 `--file` 时，使用 `--file`

**输出**：成功状态、版本号、更新行数。

## deleteData

删除表格中的数据行。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--rowIds` | string/JSON | ✅* | — | 行 ID（逗号分隔或 JSON 数组） |
| `--rowIdsFile` | string | ❌ | — | 从文件读取 rowIds 参数（文件包含 JSON 数组） |

\* `--rowIds` 和 `--rowIdsFile` 二选一，**优先使用 `--rowIdsFile`**

```bash
# 删除单行
oa-skills citadel-database deleteData \
  --tableId "2750248577" \
  --rowIds "123456"

# 删除多行
oa-skills citadel-database deleteData \
  --tableId "2750248577" \
  --rowIds "123456,123457,123458"

# 从文件读取要删除的行 ID（推荐用于大批量删除）
cat > delete-rows.json << 'EOF'
["row_123", "row_124", "row_125", "row_126"]
EOF

oa-skills citadel-database deleteData \
  --tableId "2750248577" \
  --rowIdsFile delete-rows.json
```

**💡 文件参数优先级**：当同时提供 `--rowIds` 和 `--rowIdsFile` 时，使用 `--rowIdsFile` 中的数据。

**输出**：成功状态、版本号。

## queryDeletedTables

查询已删除的数据表和仪表盘（回收站）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--contentId` | string | ✅ | — | 文档 ID |
| `--pageSize` | number | ❌ | 20 | 每页返回的数量 |
| `--order` | string | ❌ | desc | 排序方式（asc/desc） |

```bash
oa-skills citadel-database queryDeletedTables \
  --contentId "2750138424" \
  --pageSize 20 \
  --order desc
```

**输出**：已删除表格列表（表格标题、表格 ID、删除时间）。

## deleteTable

删除数据表或仪表盘（移至回收站）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |

```bash
oa-skills citadel-database deleteTable --tableId "2750248577"
```

**输出**：成功状态、表格 ID。

## recoveryTable

从回收站恢复已删除的数据表或仪表盘。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--contentId` | string | ❌ | — | 指定恢复到的文档 ID |

```bash
# 恢复到原文档
oa-skills citadel-database recoveryTable --tableId "2750248577"

# 恢复到指定文档
oa-skills citadel-database recoveryTable \
  --tableId "2750248577" \
  --contentId "2750138424"
```

**输出**：成功状态、表格 ID。

## renameTable

重命名数据表。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--title` | string | ✅ | — | 新的表格标题 |

```bash
oa-skills citadel-database renameTable \
  --tableId "2750248577" \
  --title "新的表格名称"
```

**输出**：成功状态、表格 ID、新标题。

## sortTable

调整数据表在文档中的位置（排序）。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--to` | number | ✅ | — | 目标位置索引（从 1 开始） |

```bash
# 将表格移动到第 2 个位置
oa-skills citadel-database sortTable \
  --tableId "2750248577" \
  --to 2
```

**输出**：成功状态、表格 ID、新位置。

## copyTable

将一个数据表（包括结构和数据）复制到指定的目标文档或表格下。底层 `type` 仅支持：`3=学城文档`、`4=多维表格`。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--sourceTableId` | string | ✅ | — | 源多维表格 ID |
| `--targetParentId` | string | ✅ | — | 复制到的目标文档/表格 ID |
| `--targetType` | number | ❌ | 自动识别 | 目标类型：`3=学城文档`、`4=多维表格` |
| `--columnIds` | string/JSON | ❌ | 所有列 | 复制的列 ID 列表（逗号分隔或 JSON 数组） |
| `--rowIds` | string/JSON | ❌ | 所有行 | 复制的行 ID 列表（逗号分隔或 JSON 数组） |
| `--stepVersion` | number | ❌ | — | 复制那一刻的 step 版本（用于保证数据一致性） |
| `--viewIds` | string/JSON | ❌ | [1000] | 视图 ID 列表（逗号分隔或 JSON 数组） |

### 使用场景

- ✅ 复制表格到另一个文档
- ✅ 在模板和文档之间复制表格
- ✅ 选择性复制特定列和行
- ✅ 按指定的 step 版本复制（保证数据一致性）

### 使用示例

```bash
# 基础用法：复制整个表格到文档
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424"

# 目标是学城文档模板时，显式指定 targetType=2
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424" \
  --targetType 2

# 只复制特定列
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424" \
  --columnIds "[1,2,3]"

# 只复制特定行（viewIds 未提供时自动使用默认值 [1000]）
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424" \
  --rowIds "[100,101,102]"

# 复制特定列和行（带 step 版本和视图 ID）
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750138424" \
  --columnIds "[1,2,3]" \
  --rowIds "[100,101,102]" \
  --stepVersion 12345 \
  --viewIds "[1000]"
```

### 注意事项

- 如果目标是模板，必须显式传 `--targetType 2`（学城文档模板）或 `--targetType 5`（多维表格模板）；仅靠 `targetParentId` 无法稳定自动识别模板类型
- 如果目标是普通学城文档或多维表格，不传 `--targetType` 时会自动识别常见类型（`3` / `4`）

- `columnIds` 和 `rowIds` 应使用 JSON 数组格式：`"[1,2,3]"` 或逗号分隔：`"1,2,3"`
- 需要对源表格有浏览权限，对目标文档有编辑权限
- 复制后会生成新的表格 ID 和视图 ID
- 如果不指定 `columnIds`，将复制所有列；如果不指定 `rowIds`，将复制所有行
- `viewIds` 参数未提供时会自动使用默认值 `[1000]`（通常为表格的默认视图）

**输出**：成功状态、新表格 ID、新视图 ID、复制的行数。

## addTableColumns

为数据表新增列，支持文本、数字、单选、人员、多选、附件、日期、货币、**公式**等所有列类型。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--columnMetas` | JSON | ✅* | — | 新增列信息的 JSON 数组 |
| `--columnMetasFile` | string | ❌ | — | 从 UTF-8 JSON 文件读取新增列数组 |

\* `--columnMetas` 和 `--columnMetasFile` 至少提供一个；同时提供时，**文件优先**。

### JSON 文件输入

Windows 下传复杂 JSON 或带引号的公式时，推荐使用文件参数。文件保存为 UTF-8（支持 UTF-8 BOM），内容是原始 JSON：新增列用数组，修改列配置用对象，不要把整个内容再次编码为字符串。公式内的双引号仍按 JSON 规则写为 `\"`，无需再叠加 shell 转义。简单配置仍可使用原有内联参数。

先用 `getTableMeta` 获取真实列 ID；下面的 `103`、`200` 和表格 ID 均需替换。

新增列文件 `columns.json`：

```json
[
  {
    "columnName": "完成提示",
    "columnType": 9,
    "columnConfig": {
      "formula": "IF([#103] = \"完成\", \"已完成\", \"处理中\")"
    }
  }
]
```

```powershell
oa-skills citadel-database addTableColumns --tableId 1234567890 --columnMetasFile .\columns.json
```

修改配置文件 `config.json`（顶层直接是配置对象，不包裹 `columnConfig`）：

```json
{
  "formula": "IF([#103] = \"完成\", \"已完成\", \"处理中\")"
}
```

```powershell
oa-skills citadel-database updateColumnConfig --tableId 1234567890 --columnId 200 --columnConfigFile .\config.json
```

直接传文件路径，让 CLI 读取内容。用 `Get-Content` 读取后再传给 `--columnMetas` 或 `--columnConfig`，仍会经过命令行参数转发，不能规避引号问题。上面的 PowerShell 命令均为单行；本页其他 `bash` 示例中的 `\` 续行符不适用于 PowerShell。

### `columnMetas` 格式说明

JSON 数组，每一个元素代表一个需要新增的列，包含以下属性：

- `columnName`: string（必填）列名，长度限制 1-100 字符
- `columnType`: number（必填）列类型，取值范围：
  - `1`: 文本
  - `2`: 数字
  - `3`: 单选
  - `4`: 人员
  - `5`: 多选
  - `6`: 附件
  - `7`: 日期
  - `8`: 货币
  - `9`: **公式**（计算列，单元格只读，结果由公式自动计算）
  - `201`: 创建人
  - `202`: 创建时间
  - `203`: 最后修改人
  - `204`: 最后修改时间
- `columnConfig`: object（可选）列的额外配置。根据列类型不同，支持以下配置：

| columnType | 支持的 columnConfig 字段 | 说明与示例 |
|------------|--------------------------|------------|
| 1 文本 | 无 | 无需传 columnConfig |
| 2 数字 | `formatter` | 数字格式化：`""` 无格式 / `"0"` 整数 / `"0.00"` 2位小数 / `"0,0"` 千分位 / `"0,0.00"` 千分位2位小数 / `"0%"` 百分比 |
| 3 单选 | `options`（新增时可选） | 选项名称字符串列表，最多512项，每项不超过100字符；示例：`{"options":["未开始","进行中","已完成"]}` |
| 4 人员 | `multiple` | 是否允许多人，默认 `false`；示例：`{"multiple":true}` |
| 5 多选 | `options`（新增时可选） | 同单选，参见 type:3 |
| 6 附件 | 无 | 无需传 columnConfig |
| 7 日期 | `formatter` | 日期格式：`"YYYY/MM/DD"`（默认）/ `"YYYY-MM-DD"` / `"YYYY/MM/DD HH:mm"` / `"YYYY-MM-DD HH:mm"` / `"MM-DD"` / `"MM/DD/YYYY"` / `"DD/MM/YYYY"` |
| 8 货币 | `currencyCode` / `formatter` | 货币代码默认 `"CNY"`，formatter 同数字列；示例：`{"currencyCode":"USD","formatter":"0,0.00"}` |
| **9 公式** | `formula` / `formulaFormat` / `formatter` / `currencyCode` / `multiple` | 见下方「公式列 columnConfig 详细说明」 |

> `currencyCode` 可选值：`CNY`, `USD`, `EUR`, `GBP`, `AED`, `AUD`, `BHD`, `BRL`, `CAD`, `CHF`, `HKD`, `INR`, `IDR`, `JPY`, `KRW`, `KWD`, `MOP`, `MXN`, `MYR`, `OMR`, `PHP`, `PLN`, `QAR`, `RUB`, `SAR`, `SGD`, `THB`, `TRY`, `TWD`, `VND`

---

### 公式列 columnConfig 详细说明（columnType:9）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `formula` | string | ✅ | 公式表达式，使用 `[#列ID]` 引用本表列，`[$表ID].[#列ID]` 引用同文档其他表列 |
| `formulaFormat` | number | ❌ | 结果类型：`2`=数字、`7`=日期、`8`=货币；**结果为文本/字符串时省略** |
| `formatter` | string | ❌ | 显示格式，须与 formulaFormat 类型匹配：数字/货币列用数字格式，日期列用日期格式 |
| `currencyCode` | string | ❌ | 货币代码（仅 formulaFormat:8 时有效），默认 `"CNY"` |
| `multiple` | boolean | ❌ | 是否多值（特殊场景使用） |

**⚠️ 公式语法规则：**

| # | 规则 | ✅ 正确 | 🚫 禁止 |
|---|------|---------|---------|
| 1 | 本表列引用 | `[#1]`（`#` 后接数字 colId） | `[列名]`、`[#列名]` |
| 2 | 跨表列引用 | `[$5000].[#2]`（`$` 后接数字 tableId，`.` 分隔，`#` 后接数字 colId） | `[5000#2]`（合并写法不存在） |
| 3 | 比较相等 | `[#1] = "值"` | `[#1] == "值"` |
| 4 | 单选/人员列转字符串 | `[#1] & ""` | 直接参与字符串运算（缺 `& ""`） |

> 💡 先用 `getTableMeta --tableId <id>` 获取列的 colId（`col.colId` 字段），然后在公式中用 `[#colId]` 引用。

**公式列示例：**

```json
// 数字结果（单价×数量）
{"formula":"[#101] * [#102]","formulaFormat":2,"formatter":"0,0.00"}

// 文本结果（状态判断，不传 formulaFormat）
{"formula":"IF([#103] >= 100, \"已完成\", \"进行中\")"}

// 日期结果（距今剩余天数）
{"formula":"DAYS([#104], TODAY())","formulaFormat":2,"formatter":"0"}

// 货币结果（含货币代码）
{"formula":"[#101] * [#102]","formulaFormat":8,"currencyCode":"CNY","formatter":"0,0.00"}

// 跨表查找（同文档内，[$tableId].[#colId]）
{"formula":"LOOKUP([#1] & \"\", [$5000].[#1], [$5000].[#2])"}
```

---

### 使用示例

```bash
# 新增一个普通文本列、带选项的单选列、日期列和货币列
oa-skills citadel-database addTableColumns \
  --tableId "1234567890" \
  --columnMetas '[
    {"columnName": "备注", "columnType": 1},
    {"columnName": "状态", "columnType": 3, "columnConfig": {"options": ["未开始", "进行中", "已完成"]}},
    {"columnName": "截止日期", "columnType": 7, "columnConfig": {"formatter": "YYYY-MM-DD"}},
    {"columnName": "金额", "columnType": 8, "columnConfig": {"currencyCode": "CNY"}}
  ]'

# 新增公式列（数字结果：单价×数量）
# 💡 先用 getTableMeta 获取"单价"和"数量"列的真实 colId，替换下面的 101、102
oa-skills citadel-database addTableColumns \
  --tableId "1234567890" \
  --columnMetas '[{
    "columnName": "总价",
    "columnType": 9,
    "columnConfig": {
      "formula": "[#101] * [#102]",
      "formulaFormat": 2,
      "formatter": "0,0.00"
    }
  }]'

# 新增公式列（文本结果：状态标识，不传 formulaFormat）
oa-skills citadel-database addTableColumns \
  --tableId "1234567890" \
  --columnMetas '[{
    "columnName": "状态标识",
    "columnType": 9,
    "columnConfig": {
      "formula": "IF([#103] >= 100, \"已完成\", IF([#103] > 0, \"进行中\", \"未开始\"))"
    }
  }]'

# 新增公式列（货币结果）
oa-skills citadel-database addTableColumns \
  --tableId "1234567890" \
  --columnMetas '[{
    "columnName": "税后金额",
    "columnType": 9,
    "columnConfig": {
      "formula": "[#101] * 0.9",
      "formulaFormat": 8,
      "currencyCode": "CNY",
      "formatter": "0,0.00"
    }
  }]'

# 一次新增多列（普通列 + 公式列）
oa-skills citadel-database addTableColumns \
  --tableId "1234567890" \
  --columnMetas '[
    {"columnName": "单价", "columnType": 2, "columnConfig": {"formatter": "0,0.00"}},
    {"columnName": "数量", "columnType": 2, "columnConfig": {"formatter": "0"}},
    {"columnName": "总价", "columnType": 9, "columnConfig": {"formula": "[#新建后替换为单价colId] * [#新建后替换为数量colId]", "formulaFormat": 2, "formatter": "0,0.00"}}
  ]'
```

> ⚠️ **公式列中的列 ID 必须是 `getTableMeta` 返回的数字 colId，不能用列名。** 如果新建多列时公式列引用了同批新建的列，需先建普通列（`addTableColumns`），再用 `getTableMeta` 获取新列 ID，最后再建公式列。

**输出**：成功状态、版本号、新列的 ID 列表（`columnIds`）。

## updateColumnConfig

修改数据表中已有列的配置，支持修改列名、公式表达式、结果格式、数字/日期格式化、货币代码、人员列是否多选、单选/多选 options 等。

> ⚠️ **不支持修改列类型**（columnType），不传的字段保持原值。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `--tableId` | string | ✅ | — | 表格 ID |
| `--columnId` | string | ✅ | — | 列 ID |
| `--columnName` | string | ❌ | — | 要修改成的新列名 |
| `--columnConfig` | JSON | ❌ | — | 列配置 JSON，只传需要修改的字段，其他字段保持原值 |
| `--columnConfigFile` | string | ❌ | — | 从 UTF-8 JSON 文件读取列配置对象，字段与 `--columnConfig` 一致 |
| `--formula` | string | ❌ | — | 公式表达式（等价于 `--columnConfig '{"formula":"..."}'`，兼容旧版参数） |
| `--dangerDeleteMissingOptions` | `true`/`false` | ❌ | `false` | ⚠️ 危险操作，仅单选/多选列。`true` 时 `columnConfig.options` 视为全量列表，缺席的旧选项被删除，服务端清空引用它们的单元格值、默认值与视图筛选条件值，不可撤销；必须在内联或文件提供的列配置中包含 `options`，且先取得用户确认 |

> `--columnName`、`--formula`、`--columnConfig`、`--columnConfigFile` 至少需要提供一个。同时提供 `--columnConfig` 和 `--columnConfigFile` 时，**文件优先**。Windows 复杂 JSON 的文件示例见 [JSON 文件输入](#json-文件输入)。

### `--columnConfig` 各列类型支持字段

| 列类型 | columnType | 支持修改的 columnConfig 字段 | 说明 |
|--------|-----------|------------------------------|------|
| 数字 | 2 | `formatter` | 数字格式（见下方格式表） |
| 单选 | 3 | `options` / `refConfig` | 支持字符串列表或包含 `id`/`label`/`color` 的对象列表；支持改名、排序、新增；缺省不删除已有选项，删除需显式 `--dangerDeleteMissingOptions true`（独立参数，见上表） |
| 人员 | 4 | `multiple` | 是否允许多人：`true` / `false` |
| 多选 | 5 | `options` / `refConfig` | 同单选 |
| 日期 | 7 | `formatter` | 日期格式（见下方格式表） |
| 货币 | 8 | `currencyCode` / `formatter` | 货币代码和数字格式 |
| **公式** | **9** | `formula` / `formulaFormat` / `formatter` / `currencyCode` | 公式表达式、结果类型、显示格式 |

`refConfig` 用于选项引用，来源仅支持普通单选(3)/多选(5)列。对象开启或整体替换引用配置，修改时 `null` 关闭；与 `options`、`defaultValue` 互斥。支持 `filter` 筛选来源记录，使用单层数组条件；固定值、按当前行取值和取消筛选的格式见 [选项引用配置](data-format.md#选项引用配置)。也可在创建文档、创建表格或新增列的 `columnConfig` 中设置。

**数字/货币 formatter 可选值：**
`""` (无格式) / `"0"` (整数) / `"0.0"` / `"0.00"` / `"0.000"` / `"0,0"` (千分位) / `"0,0.00"` / `"0%"` / `"0.00%"`

**日期 formatter 可选值：**
`"YYYY/MM/DD"` (默认) / `"YYYY-MM-DD"` / `"YYYY/MM/DD HH:mm"` / `"YYYY-MM-DD HH:mm"` / `"MM-DD"` / `"MM/DD/YYYY"` / `"DD/MM/YYYY"`

---

### 使用示例

```bash
# 修改列名
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "3" \
  --columnName "新状态名"

# 修改数字列的格式化（千分位+2位小数）
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "101" \
  --columnConfig '{"formatter":"0,0.00"}'

# 修改日期列的格式
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "104" \
  --columnConfig '{"formatter":"YYYY-MM-DD HH:mm"}'

# 修改货币列的货币类型和格式
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "108" \
  --columnConfig '{"currencyCode":"USD","formatter":"0,0.00"}'

# 修改人员列为允许多选
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "104" \
  --columnConfig '{"multiple":true}'

# 修改已有单选/多选列的 options
# 💡 缺省必须保留所有已有选项；支持改名、排序、新增；缺席的旧选项会报错而不是被删除
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "105" \
  --columnConfig '{"options":[{"id":123,"label":"未开始","color":"#E8F3FF"},{"id":124,"label":"进行中","color":"#FFF7E6"},"已完成"]}'

# 删除单选/多选列的选项（⚠️ 危险操作：options 为全量列表，缺席的 id:124 会被删除，
# 引用它的单元格值、默认值与视图筛选条件值被清空且不可撤销；先 getTableMeta 拿全量选项并向用户确认后再执行）
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "105" \
  --columnConfig '{"options":[{"id":123,"label":"未开始","color":"#E8F3FF"},{"id":125,"label":"已完成","color":"#E6FFED"}]}' \
  --dangerDeleteMissingOptions true

# 修改公式列的公式表达式（数字结果）
# 💡 先用 getTableMeta 获取列的真实 colId
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "200" \
  --columnConfig '{"formula":"[#101] * [#102]","formulaFormat":2,"formatter":"0,0.00"}'

# 修改公式列为文本结果（不传 formulaFormat）
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "200" \
  --columnConfig '{"formula":"IF([#103] = \"完成\", \"✅\", \"⏳\")"}'

# 修改公式列为日期结果
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "200" \
  --columnConfig '{"formula":"DAYS([#104], TODAY())","formulaFormat":2,"formatter":"0"}'

# 同时修改列名和公式
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "200" \
  --columnName "总价（含税）" \
  --columnConfig '{"formula":"[#101] * [#102] * 1.13","formulaFormat":2,"formatter":"0,0.00"}'

# 跨表公式（引用同文档其他表的列）
# 💡 用 listTables 获取目标 tableId，用 getTableMeta 获取目标列 colId
oa-skills citadel-database updateColumnConfig \
  --tableId "1234567890" \
  --columnId "200" \
  --columnConfig '{"formula":"LOOKUP([#1] & \"\", [$5000].[#1], [$5000].[#2])"}'
```

**输出**：成功状态、版本号。

## 视图管理

📖 完整视图命令参数、ViewConfig 配置说明、视图筛选语法见 `{baseDir}/references/view-management.md`。

## 列类型说明

| 类型ID | 类型名称 | 数据格式 | 说明 |
|---|---|---|---|
| 1 | 文本（富文本） | `IRichTextNode[]` | 支持纯文本、超链接、@提及、段落节点 |
| 2 | 数字 | `number` | 数值类型 |
| 3 | 单选 | `string` | 单选选项的值 |
| 4 | 人员 | `number[]` | empId 数组 |
| 5 | 多选 | `string[]` | 多选选项的值数组 |
| 6 | 附件 | `string[]` | JSON 字符串数组（每个元素为 `JSON.stringify({attachmentId, name, url, ...})`） |
| 7 | 日期 | `number` | 毫秒时间戳 |
| 8 | 货币 | `number` | 数值类型 |
| 9 | 公式 | 只读 | 不支持写入 |
| 10 | 查找引用 | 只读 | 不支持写入；查询时返回引用值的文本表示 |

### 富文本节点类型

```typescript
// 纯文本
{ type: "text", value: "文本内容" }

// 超链接
{ type: "link", value: "显示文字", link: "<链接URL>" }

// @提及（value 必须以 @ 开头）
{ type: "mention", value: "@用户名", empId: 2015739 }

// 段落（发送前会统一补成 value: " "）
{ type: "paragraph", value: " " }
```

### 文本列完整写入示例

文本列（`columnType: 1`）支持 `text`、`link`、`mention`、`paragraph` 四种节点，字段说明见[富文本格式](data-format.md#富文本格式-textcellvalue)。以下命令在一个单元格内写入全部四种类型：

```bash
oa-skills citadel-database addData \
  --tableId 2750248577 \
  --columnIds "1" \
  --data '[[[
    {"type":"text","value":"请 "},
    {"type":"mention","value":"@张三","empId":2015739},
    {"type":"text","value":" 查看 "},
    {"type":"link","value":"项目文档","link":"https://example.com/docs/project"},
    {"type":"paragraph","value":" "},
    {"type":"text","value":"请在本周五前完成"}
  ]]]'
```

执行前用 `getTableMeta` 确认真实表格和文本列 ID，用 `getUserInfo --misList <用户MIS>` 获取真实 empId，并替换示例中的人员、URL。`mention.value` 使用 `@显示名称`，`empId` 传数字；`paragraph.value` 使用单个空格。

更新已有行时，将命令改为 `updateData` 并加上 `--rowIds '[123456]'`（替换为目标行 ID），传入完整单元格内容。各类型单独写入的完整 JSON 以及可保存到文件的多行示例见[文本列类型示例](data-format.md#1-文本列-columntype-1)。

### 富文本列超链接写入

先用 `getTableMeta --tableId <id>` 确认目标列为文本列（`columnType: 1`），再用 `addData` 新增行或 `updateData` 更新已有行。以下表格 ID、行 ID、列 ID 和 URL 均为示例，执行时替换为实际值。节点字段、数组层级及字符串处理规则见[超链接节点](data-format.md#2-超链接节点)。

**新增一行，单个单元格写入超链接**：

```bash
oa-skills citadel-database addData \
  --tableId 2750248577 \
  --columnIds "1" \
  --data '[[[{"type":"link","value":"项目文档","link":"https://example.com/docs/project"}]]]'
```

**更新已有单元格，混合普通文字和多个链接**：

```bash
oa-skills citadel-database updateData \
  --tableId 2750248577 \
  --rowIds "123456" \
  --columnIds "1" \
  --data '[[[
    {"type":"text","value":"相关资料："},
    {"type":"link","value":"项目文档","link":"https://example.com/docs/project"},
    {"type":"text","value":" / "},
    {"type":"link","value":"验收清单","link":"https://example.com/docs/checklist"}
  ]]]'
```

`updateData` 写入的是目标单元格的完整内容。若只改一个链接或追加链接，先用 `queryTableData --tableId <id> --columnIds <列ID> --max-pages 10 --raw` 查询，按 `rowId` 定位目标行并读取 `textCellValue`；未取到目标行时继续定位，不能当作空内容。保留其他节点，在原数组上修改后整体写回。

**从 JSON 文件写入多行、多列**：以下第 1 列为名称，第 2 列为资料链接，均是文本列；每行的单元格顺序与 `--columnIds "1,2"` 一致。

```bash
cat > hyperlink-data.json << 'EOF'
[
  ["项目 A", [{"type":"link","value":"项目 A 文档","link":"https://example.com/docs/a"}]],
  ["项目 B", [{"type":"link","value":"项目 B 文档","link":"https://example.com/docs/b"}]]
]
EOF

oa-skills citadel-database addData \
  --tableId 2750248577 \
  --columnIds "1,2" \
  --file hyperlink-data.json
```

同一文件也可用于 `oa-skills citadel-database updateData --tableId 2750248577 --rowIds '[123456,123457]' --columnIds "1,2" --file hyperlink-data.json`，两行数据依次对应两个行 ID。写入后用 `queryTableData --raw` 核对目标行的 `textCellValue` 中显示文字 `value` 和地址 `link`。

## 文件上传工作流

向附件列添加文件有两种方式：推荐使用 `uploadFileAndAddData` 一步完成，或使用低层 API `uploadFileByS3Url` 分步操作。

### ⭐ 推荐方式：uploadFileAndAddData（一步完成）

适用场景：上传本地文件并直接写入表格，最常用。

```bash
# 前提：已知 contentId、tableId 和附件列的 columnId

# 步骤 1（可选）：查看表格元数据确认附件列 ID
oa-skills citadel-database getTableMeta --tableId "2752934848"

# 步骤 2：上传文件并写入数据（一步完成）
oa-skills citadel-database uploadFileAndAddData \
  --contentId "2752755021" \
  --tableId "2752934848" \
  --file "/path/to/document.pdf" \
  --columnIds "1,2,3" \
  --data '[["项目需求文档", null, "2024-03-09"]]'
```

**说明**：
- `--file`：本地文件路径（支持图片、PDF、Office 文档等）
- `--columnIds`：要写入数据的所有列 ID（含附件列）
- `--data`：二维数组，附件列位置传 `null` 或占位值，系统自动替换为上传后的附件信息
- 返回 `attachmentId` 和文件 URL，可直接用于后续查询

### 🔧 低层 API：uploadFileByS3Url + addData（分步操作）

适用场景：
- 文件已在 S3 存储，需要关联到多维表格
- 批量处理工作流（避免重复上传）
- 测试和调试文件上传功能

```bash
# 步骤 1: 通过 S3 URL 上传文件（fileName 可选，未提供时从 URL 自动提取）
oa-skills citadel-database uploadFileByS3Url \
  --s3Url "https://km.sankuai.com/api/file/cdn/xxx/file.pdf" \
  --fileName "document.pdf" \
  --contentId "2752755021"

# 输出: { attachmentId: 228822745910, name: "document.pdf", url: "https://..." }

# 步骤 2: 使用返回的 attachmentId 和 url 写入附件列
oa-skills citadel-database addData \
  --tableId "2752934848" \
  --columnIds "1,2" \
  --data '[[
    "项目需求文档",
    JSON.stringify({attachmentId: 228822745910, name: "document.pdf", url: "https://km.sankuai.com/api/file/cdn/xxx/228822745910"})
  ]]'
```

**注意事项**：
- `uploadFileByS3Url` 的 `--s3Url` 必须是有效的 S3 文件 URL
- 如果目标是模板，必须显式传 `--targetType 2`
- 需要对源表格有浏览权限，对目标文档有编辑权限

## 环境变量

| 变量名 | 说明 |
|---|---|
| `USER_ACCESS_TOKEN` | 用于 `${user_access_token}` 占位符的用户身份 token |
| `APP_ACCESS_TOKEN` | 用于 `${app_access_token}` 占位符的应用身份 token |
| `NO_CHECK_VERSION` | 设置为 `"true"` 时跳过 Node.js 版本检查 |

## 示例工作流

### 1. 创建完整的项目管理表格

```bash
# 步骤 1: 创建文档和表格
oa-skills citadel-database createDatabase \
  --contentTitle "项目管理系统" \
  --tableTitle "项目列表" \
  --columnMeta '[
    {"columnName":"项目名称","columnType":1},
    {"columnName":"负责人","columnType":1},
    {"columnName":"状态","columnType":3,"selectOptions":["未开始","进行中","已完成","暂停"]},
    {"columnName":"优先级","columnType":3,"selectOptions":["高","中","低"]},
    {"columnName":"进度","columnType":2},
    {"columnName":"开始日期","columnType":7},
    {"columnName":"截止日期","columnType":7}
  ]'

# 假设返回 tableId: 2750248577

# 步骤 2: 添加数据
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3,4,5,6,7" \
  --data '[
    ["项目A", "张三", "进行中", "高", 75, 1710000000000, 1712592000000],  // 开始: 2024-03-09, 截止: 2024-04-08
    ["项目B", "李四", "未开始", "中", 0, 1710000000000, 1715088000000]  // 开始: 2024-03-09, 截止: 2024-05-07
  ]'

# 步骤 3: 查询数据
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --filter '{"conjunction":"and","conditions":[{"columnId":3,"operator":"==","filterValue":["进行中"]}]}'
```

### 2. 数据迁移和备份

```bash
# 步骤 1: 查询源表格数据
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --raw > backup.json

# 步骤 2: 复制表格结构到新文档
oa-skills citadel-database copyTable \
  --sourceTableId "2750248577" \
  --targetParentId "2750999999"

# 步骤 3: 从备份恢复数据（需要解析 backup.json 并转换格式）
```

### 3. 附件列数据操作

```bash
# 步骤 1: 创建包含附件列的表格
oa-skills citadel-database createDatabase \
  --contentTitle "文档管理" \
  --tableTitle "文档列表" \
  --columnMeta '[
    {"columnName":"文档标题","columnType":1},
    {"columnName":"附件","columnType":6},
    {"columnName":"上传日期","columnType":7}
  ]'

# 假设返回 tableId: 2750248577

# 步骤 2: 添加附件数据（单个附件）
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3" \
  --data '[[
    "项目需求文档",
    JSON.stringify({
      attachmentId: 0,
      name: "requirements.pdf",
      url: "<文件URL>",
      size: 123456,
      mimeType: "application/pdf"
    }),
    1710000000000  // 上传日期: 2024-03-09
  ]]'

# 步骤 3: 添加多个附件
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2" \
  --data '[[
    "设计稿",
    [
      JSON.stringify({
        attachmentId: 0,
        name: "design-v1.png",
        url: "<文件URL1>",
        size: 6105,
        width: 1920,
        height: 1080,
        mimeType: "image/png"
      }),
      JSON.stringify({
        attachmentId: 0,
        name: "design-v2.png",
        url: "<文件URL2>",
        size: 7200,
        width: 1920,
        height: 1080,
        mimeType: "image/png"
      })
    ]
  ]]'
```

**⚠️ 附件格式要点**：
- 每个附件必须使用 `JSON.stringify()` 序列化
- 必填字段：`attachmentId`（新建时为 0）、`name`、`url`
- 可选字段：`size`、`width`、`height`、`mimeType`
- 多个附件使用数组包裹多个 JSON 字符串

### 4. 使用 Token 认证的批量操作

```bash

# 批量查询多个表格
for tableId in 2750248577 2750248578 2750248579; do
  oa-skills citadel-database queryTableData \
    --tableId "$tableId" \
    --raw >> all_data.json
done
```

## getUserInfo - 获取用户信息（账号转换）

### 功能说明

`getUserInfo` 命令用于批量查询用户信息，支持 MIS 到 uid/empId/姓名等字段的转换。这是在操作人员列数据时必不可少的功能。

### 使用场景

- ✅ 查询用户的 empId（用于人员列数据）
- ✅ MIS 账号转换为 uid/empId
- ✅ 批量获取用户信息（姓名、头像等）
- ✅ 验证用户账号是否存在

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--misList` | string \| string[] | 是 | MIS 账号列表，支持 JSON 数组或逗号分隔格式 |

### 返回字段

每个用户的信息包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 大象 UID |
| `mis` | string | MIS 账号 |
| `name` | string | 用户姓名 |
| `empId` | number | 员工 ID（**用于人员列数据**） |
| `avatarUrl` | string | 头像 URL（200x200） |
| `bigAvatarUrl` | string | 大头像 URL |

### 使用示例

#### 1. 查询单个用户信息

```bash
# 逗号分隔格式（推荐）
oa-skills citadel-database getUserInfo --misList 'zhangsan'

# 或 JSON 数组格式
oa-skills citadel-database getUserInfo --misList '["zhangsan"]'
```

输出示例：
```
✅ 查询成功！找到 1 个用户

👤 MIS: zhangsan
   ├─ 姓名: 张三
   ├─ UID: 1027950
   ├─ EmpID: 2015738
   ├─ 头像: <头像URL>
   └─ 大头像: <大头像URL>
```

#### 2. 批量查询多个用户

```bash
# 逗号分隔格式（推荐）
oa-skills citadel-database getUserInfo --misList 'zhangsan,lisi,wangwu'

# 或 JSON 数组格式
oa-skills citadel-database getUserInfo --misList '["zhangsan", "lisi", "wangwu"]'
```

#### 3. 输出原始 JSON（用于脚本处理）

```bash
oa-skills citadel-database getUserInfo \
  --misList '["zhangsan", "lisi"]' \
  --raw
```

输出示例：
```json
{
  "zhangsan": {
    "uid": "1027950",
    "mis": "zhangsan",
    "name": "张三",
    "avatarUrl": "<头像URL>",
    "bigAvatarUrl": "<大头像URL>",
    "empId": 2015738
  },
  "lisi": {
    "uid": "1027951",
    "mis": "lisi",
    "name": "李四",
    "avatarUrl": "<头像URL>",
    "bigAvatarUrl": "<大头像URL>",
    "empId": 2015739
  }
}
```

#### 4. 与人员列配合使用（完整工作流）

```bash
# 步骤 1: 查询 empId
RESULT=$(oa-skills citadel-database getUserInfo \
  --misList '["zhangsan", "lisi"]' \
  --raw)

# 步骤 2: 提取 empId（使用 jq）
EMP_IDS=$(echo "$RESULT" | jq -r '[.[] | .empId]')
# 输出: [2015738, 2015739]

# 步骤 3: 添加人员列数据
oa-skills citadel-database addData \
  --tableId "456789" \
  --columnIds "4" \
  --data "[[$EMP_IDS]]"
```

#### 5. 批量处理（从文件读取 MIS 列表）

```bash
# 从文件读取 MIS 列表（每行一个 MIS）
MIS_LIST=$(cat users.txt | jq -R . | jq -s .)

# 批量查询
oa-skills citadel-database getUserInfo \
  --misList "$MIS_LIST" \
  --raw > user_info.json
```

### 注意事项

1. **不存在的账号**
   - 不存在的 MIS 账号不会出现在返回结果中
   - 命令会在标准输出中提示哪些账号未找到
   - 不会导致命令失败

2. **批量查询建议**
   - 建议单次查询不超过 100 个用户
   - 对于大量用户，可以分批查询

3. **缓存机制**
   - 用户信息相对稳定，建议在应用层缓存查询结果
   - 头像 URL 可能会过期，建议定期更新

4. **人员列数据格式**
   - 人员列使用 **empId**（number 类型）
   - 必须先通过此命令获取 empId，再操作人员列
   - 示例：`[[2015738, 2015739]]` 表示一行包含两个人员

### API 说明

底层调用的是多维表格 v2 API：

```
GET /xtable/data-api/v2/users/getUsersByMis?misList=mis1,mis2
```

返回格式：
```json
{
  "success": true,
  "data": {
    "mis1": { ... },
    "mis2": { ... }
  }
}
```

## queryUserIdentityByUid - 通过 UID 查询 MIS/empId

### 功能说明

`queryUserIdentityByUid` 命令用于批量根据 UID 查询用户身份信息，返回对应的 MIS 和 empId。适用于已拿到大象 UID、需要继续操作人员列或回填账号信息的场景。

### 使用场景

- ✅ UID 转换为 MIS
- ✅ UID 转换为 empId
- ✅ 校验 UID 是否存在
- ✅ 为人员列、账号回填等场景补齐身份字段

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--uidList` | string \| string[] | 是 | UID 列表，支持 JSON 数组或逗号分隔格式 |

### 返回字段

每个用户的信息包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `uid` | string | 大象 UID |
| `mis` | string | MIS 账号 |
| `empId` | string | 员工 ID |

### 使用示例

```bash
# 逗号分隔格式（推荐）
oa-skills citadel-database queryUserIdentityByUid --uidList '1027950,1027951'

# 或 JSON 数组格式
oa-skills citadel-database queryUserIdentityByUid --uidList '["1027950", "1027951"]'
```

输出示例：
```
✅ 查询成功！找到 1 个用户

👤 UID: 1027950
   ├─ MIS: zhangsan
   └─ EmpID: 2015738

⚠️  以下 UID 未找到: 1027951
```

### 注意事项

1. 不存在的 UID 不会出现在返回结果中，命令会额外提示未找到的 UID。
2. 该命令底层复用共享用户转换能力，返回字段只包含身份映射所需的最小信息：`uid`、`mis`、`empId`。
3. 适合脚本模式配合 `--raw` 使用。

## 多维表格高级权限

高级权限是多维表格自己的权限体系，不等同于学城文档权限。以下命令走学城主服务 `/api/permission/*`。

> 当前 CLI 的角色权限写入只支持数据表，不允许修改仪表盘高级权限。`createAdvancedPermRole`、`updateAdvancedPermRolePermissions` 的 `permissionDetails` 不得传入仪表盘 ID；查询结果中的既有仪表盘权限只允许读取，不得新增、修改或删除。

### getAdvancedPermStatus

查询高级权限开关状态。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |

```bash
oa-skills citadel-database getAdvancedPermStatus \
  --contentId "4295357904" \
  --mis hekai13
```

### updateAdvancedPermStatus

开启或关闭高级权限开关。该命令走 `POST /api/permission/xtable/{contentId}/advancedOn` 或 `POST /api/permission/xtable/{contentId}/advancedOff`。

开启/关闭会改变多维表格实际生效权限。Agent 执行前必须先查询 `getAdvancedPermStatus`，向用户复述目标 `contentId`、目标状态和当前高级权限状态；如果不是首次开启，还要查询 `listAdvancedPermRoles --roleType custom --raw` 判断是否存在已有成员；关闭时提示角色权限将失效、用户按文档权限访问全部内容；用户明确确认后才执行。

开启时命令会根据原高级权限内容不同而不同：

- `advancedPerm=0` 未初始化：首次开启，不传 `--preserveOriginalRole`。
- `advancedPerm=1/2` 且没有自定义角色成员：非首次开启，CLI 会自动补 `preserveOriginalRole=true`，也可显式传 `--preserveOriginalRole true`。
- `advancedPerm=1/2` 且已有自定义角色成员：必须显式传 `--preserveOriginalRole true` 或 `--preserveOriginalRole false`。如果省略，CLI 会停止执行并要求明确选择。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--status` | string | 是 | `enabled`、`disabled`；也支持 `on/off`、`true/false`、`1/2` |
| `--preserveOriginalRole` | boolean | 否 | 仅开启时可传；有历史成员时必传，表示是否保留已有高级权限角色成员 |

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status enabled \
  --preserveOriginalRole true \
  --mis hekai13
```

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status disabled \
  --mis hekai13
```

### listAdvancedPermRoles

查询管理员、默认角色、自定义角色的成员和权限配置。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleType` | string | 否 | `all`、`admin`、`default`、`custom`，默认 `all` |

```bash
oa-skills citadel-database listAdvancedPermRoles \
  --contentId "4295357904" \
  --roleType custom \
  --mis hekai13
```

### getAdvancedPermRoleDetail

查询单个角色详情。管理员或默认角色不传 `--roleId` 时会先查询对应类型的唯一角色并自动解析 `roleId`；自定义角色支持通过 `--roleName` 精确匹配。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleType` | string | 否 | `admin`、`default`、`custom`，默认 `custom` |
| `--roleId` | number | 否 | 角色 ID；管理员/默认角色省略时自动查询唯一角色 |
| `--roleName` | string | custom 二选一 | 自定义角色名称，精确匹配 |

```bash
oa-skills citadel-database getAdvancedPermRoleDetail \
  --contentId "4295357904" \
  --roleName "自定义角色1" \
  --mis hekai13

oa-skills citadel-database getAdvancedPermRoleDetail \
  --contentId "4295357904" \
  --roleType default \
  --mis hekai13
```

### createAdvancedPermRole

创建高级权限自定义角色。`permissionDetails` 可直接传 JSON，或用 `--permissionDetailsFile` 读取文件；两者二选一，且只能包含数据表 ID，不能包含仪表盘 ID。成员参数可选，格式同 `addAdvancedRoleMembers`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleName` | string | 是 | 新角色名称 |
| `--permissionDetails` | JSON | 二选一 | 数据表权限数组，元素包含 `tableId`、`permGroupType`、可选 `extraConfig`；禁止使用仪表盘 ID |
| `--permissionDetailsFile` | path | 二选一 | 数据表权限数组 JSON 文件；禁止包含仪表盘 ID |
| 成员参数 | string/JSON | 否 | `--person`、`--orgs`、`--xmGroupIds`、`--mails`、`--appIds` |

```bash
oa-skills citadel-database createAdvancedPermRole \
  --contentId "4295357904" \
  --roleName "运营角色" \
  --permissionDetails '[{"tableId":123456,"permGroupType":5}]' \
  --mis hekai13
```

### renameAdvancedPermRole / deleteAdvancedPermRole

重命名或删除自定义角色。执行前先读取角色详情；删除必须获得用户明确确认。

```bash
oa-skills citadel-database renameAdvancedPermRole \
  --contentId "4295357904" \
  --roleName "运营角色" \
  --newRoleName "运营只读" \
  --mis hekai13

oa-skills citadel-database deleteAdvancedPermRole \
  --contentId "4295357904" \
  --roleId 88 \
  --mis hekai13
```

### updateAdvancedPermRolePermissions

更新默认或自定义角色的数据表级权限及 `extraConfig`，不支持修改仪表盘高级权限。表级 `permGroupType`：`-1` 无权限、`0` 可浏览、评论、`2` 可编辑、`4` 可管理、`5` 仅浏览。

该枚举对齐 Data API 消费的 XTable 高级权限模型；不要传通用文档权限枚举中的 `1`、`3`。

默认 `--replace false`，按 `tableId` 合并现有配置；`--replace true` 会完整替换，使用前必须读取当前角色详情并获得明确确认。如果完整替换会新增、修改或删除任何仪表盘权限项，则禁止执行。

同一数据表的 `permGroupType` 不变时，省略 `extraConfig` 会保留现有详细配置；切换 `permGroupType` 时，省略 `extraConfig` 会清除旧权限组的详细配置，避免产生权限组与行列配置不匹配的请求。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleType` | string | 是 | `default`、`custom` |
| `--roleId` / `--roleName` | number/string | 视角色而定 | custom 可按名称精确解析；default 不传时自动查询唯一角色 |
| `--permissionDetails` / `--permissionDetailsFile` | JSON/path | 二选一 | 数据表权限数组；禁止使用仪表盘 ID |
| `--replace` | boolean | 否 | 默认 false；true 为完整替换 |

`extraConfig` 可包含 `rowOperation`、`rowRanges`、`columnRanges`、`viewOperation`。操作位：`1` 可见、`2` 可新增、`4` 可编辑、`8` 可删除、`16` 新增时可编辑，组合权限使用按位或。

可浏览、评论和仅浏览权限（`permGroupType=0/5`）中，`rowOperation`、`viewOperation` 只能为 `1`；指定行时 `rowRanges` 必须同时且仅包含 key `1`；`columnRanges` 的权限值只能为 `0/1`；`others` 省略时默认补 `0`，传入时只能为 `0/1`。

可编辑权限中，`rowOperation` 仅支持 `5/7/13/15`，`viewOperation` 仅支持 `1/15`；指定行时必须同时传完全一致的 `rowRanges.4` 和 `rowRanges.8`，`others` 省略时默认补 `1`。`columnRanges` 的权限值仅支持 `0/1/21`。`rowOperation=7/15` 时，CLI 会读取表元数据并把固定的“行创建人包含当前用户”条件补到两份行范围的第一条；`rowOperation=5/13` 时不强制或自动补创建人条件，传入的筛选条件按原样保留。

指定行筛选中，用户未指定“任一/全部”时，`rowOperation=7/15` 默认使用 `or`，`rowOperation=5/13` 以及可浏览权限默认使用 `and`；用户明确指定时保留用户选择。

无权限和可管理（`permGroupType=-1/4`）不支持 `extraConfig`；更新命令只在明确清除旧配置时允许传 `extraConfig:null`。CLI 在写入前会通过 Data API 的 `listTables` 校验所有目标 ID，只允许当前文档中的数据表；仪表盘或无效 ID 会被拒绝。`--replace true` 还会检查现有角色权限，避免完整替换隐式删除仪表盘权限。

> `rowRanges.*.filter` 使用 Data API 消费的 XTable 权限模型元组 `["and"|"or", [[operator, colId, value, colType], ...]]`，其中 `and`=符合全部条件、`or`=符合任一条件。普通 `queryTableData --filter` 使用的 `{ "conjunction": ..., "conditions": ... }` 是 Data API 对外查询 DTO，不能未经转换直接写入高级权限 `extraConfig`。构造普通列条件时建议先执行 `getTableMeta --tableId <id>`；CLI 会校验可编辑权限结构，但不校验普通筛选条件中的选项 ID 是否存在。完整说明见 [高级权限说明](advanced-permission.md#指定行筛选格式写入前必读)。

```bash
oa-skills citadel-database updateAdvancedPermRolePermissions \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "运营角色" \
  --permissionDetails '[{"tableId":123456,"permGroupType":2,"extraConfig":{"rowOperation":15,"columnRanges":{"1001":1},"viewOperation":1}}]' \
  --mis hekai13
```

### addAdvancedRoleMembers

给管理员、默认角色或自定义角色添加成员。`--mis` 是 CLI 通用执行人参数；被添加的人员 MIS 使用 `--person`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleType` | string | 是 | `admin`、`default`、`custom` |
| `--roleId` | number | 否 | 角色 ID；admin/default 不传时自动查询唯一角色，custom 可用 `--roleName` 自动解析 |
| `--roleName` | string | 否 | 自定义角色名称，会自动解析 `roleId` |
| `--person` | string | 否 | 要添加的人员 MIS，支持逗号分隔或 JSON 数组 |
| `--orgs` | JSON | 否 | 组织数组，`orgId` 支持数字 ID 或部门全路径；`contractTypes`/`orgRoles` 支持 key 或名称，`country` 使用国家地区 code，未传默认 `["101"]`/`[]`/`["CHN"]` |
| `--xmGroupIds` | string | 否 | 大象群 ID，支持逗号分隔或 JSON 数组 |
| `--mails` | string | 否 | 邮箱，支持逗号分隔或 JSON 数组 |
| `--appIds` | string | 否 | 应用权限 ID，支持逗号分隔或 JSON 数组 |

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType default \
  --person "zhangsan" \
  --mis hekai13

oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --person "zhangsan,lisi" \
  --mis hekai13
```

添加组织示例：

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "2753245361" \
  --roleType custom \
  --roleName "角色 1" \
  --orgs '[{"orgId":"美团/核心本地商业","contractTypes":["全日制"],"orgRoles":["行政"],"country":["CHN"]}]' \
  --mis hekai13
```

### deleteAdvancedRoleMembers

从管理员、默认角色或自定义角色删除成员。`--mis` 是 CLI 通用执行人参数；被删除的人员 MIS 使用 `--person`。

删除前 CLI 会先查询角色详情，并按传入的人员、组织、大象群、邮件组或应用匹配现有成员；管理员成员按 `permId` 删除，默认和自定义角色成员按 `userGroupId` 删除。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--contentId` | number | 是 | 多维表格文档 ID |
| `--roleType` | string | 是 | `admin`、`default`、`custom` |
| `--roleId` | number | 否 | 角色 ID；admin/default 不传时自动查询唯一角色，custom 可用 `--roleName` 自动解析 |
| `--roleName` | string | 否 | 自定义角色名称，会自动解析 `roleId`；仅 custom 支持 |
| `--person` | string | 否 | 要删除的人员 MIS，支持逗号分隔或 JSON 数组 |
| `--orgs` | JSON | 否 | 组织数组，`orgId` 支持数字 ID 或部门全路径，例如 `[{"orgId":"美团/核心本地商业"}]` |
| `--xmGroupIds` | string | 否 | 大象群 ID，支持逗号分隔或 JSON 数组 |
| `--mails` | string | 否 | 邮箱，支持逗号分隔或 JSON 数组 |
| `--appIds` | string | 否 | 应用权限 ID，支持逗号分隔或 JSON 数组 |

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType default \
  --person "zhangsan" \
  --mis hekai13

oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --person "zhangsan,lisi" \
  --mis hekai13
```

#### 二期补充：管理员删除

管理员删除仍使用 `deleteAdvancedRoleMembers`，将 `--roleType` 设为 `admin`；未传 `--roleId` 时自动查询唯一管理员角色。删除前必须读取角色详情并核对实际匹配成员。

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType admin \
  --person "zhangsan" \
  --mis hekai13
```

### searchAdvancedMemberRoles

按关键词反查成员以及其当前所属高级权限角色。

```bash
oa-skills citadel-database searchAdvancedMemberRoles \
  --contentId "4295357904" \
  --keyword "zhangsan" \
  --raw \
  --mis hekai13
```

### updateAdvancedMemberRoles

覆盖指定 `userGroupId` 的角色列表。先用 `searchAdvancedMemberRoles` 获取准确的成员 ID 和当前角色。该命令是覆盖语义；移除全部可分配角色必须显式使用 `--clear true`，并在执行前获得用户明确确认。

```bash
oa-skills citadel-database updateAdvancedMemberRoles \
  --contentId "4295357904" \
  --userGroupId 10001 \
  --roleIds "88,89" \
  --mis hekai13
```

### getAdvancedUserTablePermissions

查询当前认证用户在一个或多个数据表上的实际生效权限。

```bash
oa-skills citadel-database getAdvancedUserTablePermissions \
  --contentId "4295357904" \
  --tableIds "123456,123457" \
  --raw \
  --mis hekai13
```

## getTableMeta 实用技巧：jq 提取列配置

`getTableMeta` 返回的原始 JSON 包含完整的列元数据，使用 `jq` 可以快速提取所需信息。

### 提取单选/多选列的可选项

```bash
# 获取所有单选/多选列的名称和可选项
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '[.columns[] | select(.columnType==3 or .columnType==5) | {columnName, columnType, options: .columnConfig.options}]'

# 输出示例：
# [
#   {
#     "columnName": "状态",
#     "columnType": 3,
#     "options": [{"label": "待处理"}, {"label": "进行中"}, {"label": "已完成"}]
#   },
#   {
#     "columnName": "标签",
#     "columnType": 5,
#     "options": [{"label": "紧急"}, {"label": "重要"}, {"label": "普通"}]
#   }
# ]
```

### 检查人员列是否支持多人

```bash
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '.columns[] | select(.columnType==4) | {columnName, multiple: .columnConfig.multiple}'

# 输出示例：
# {"columnName": "负责人", "multiple": true}
```

### 查看数字/日期列的格式化规则

```bash
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '[.columns[] | select(.columnType==2 or .columnType==7 or .columnType==8) | {columnName, columnType, formatter: .columnConfig.formatter}]'

# 输出示例：
# [
#   {"columnName": "进度", "columnType": 2, "formatter": "0.00%"},
#   {"columnName": "截止日期", "columnType": 7, "formatter": "YYYY-MM-DD"},
#   {"columnName": "预算", "columnType": 8, "formatter": "¥#,##0.00"}
# ]
```

### 获取所有列 ID 和名称（用于构造 --columnIds）

```bash
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '[.columns[] | {colId, columnName, columnType}]'

# 输出可用于确定 --columnIds 的值和顺序
```
