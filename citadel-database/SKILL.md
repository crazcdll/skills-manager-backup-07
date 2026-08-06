---
name: citadel-database
description: "学城多维表格操作工具。支持:文档/表格创建与管理、数据增删改查、批量操作、筛选排序、文件上传、账号转换、多维表格高级权限添加成员、自定义角色删除成员能力。当用户需要操作多维表格、批量处理表格数据、数据同步、数据收集、表格自动化，或给多维表格高级权限角色添加人员/组织/群/邮件组/应用、从自定义角色删除成员时使用。触发词:表格、多维表格、XTable、高级权限、默认角色、自定义角色、多维表格管理员、角色成员、批量操作、数据导入、数据收集。"

metadata:
  skillhub.creator: "zhangshufei02"
  skillhub.updater: "hekai13"
  skillhub.version: "V22"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3859"
  skillhub.high_sensitive: "true"
---

# 📊 学城多维表格 XTable 

学城多维表格操作工具，通过 CLI 快速创建、查询和管理多维表格数据。认证自动处理，支持批量操作。

## 核心特性

- ✅ **HTTP REST API**：直接使用 HTTP 接口，高效稳定
- ✅ **简洁的二维数组格式**：使用 `[["值1", "值2"]]` 格式操作数据，自动类型转换
- ✅ **完整的 CRUD**：支持创建、查询、更新、删除操作
- ✅ **Token 自动缓存**：认证信息自动保存，后续调用无需重复认证
- ✅ **支持筛选和排序**：灵活的数据查询能力
- ✅ **新增公式列** 🧮：支持创建公式列（columnType:9），自动计算数字/日期/文本/货币结果，支持本表列引用 `[#colId]` 和跨表引用 `[$tableId].[#colId]`
- ✅ **编辑列配置** ⚙️：支持修改公式表达式、结果格式（formulaFormat）、数字/日期格式化（formatter）、货币代码、人员列多选等列级配置
- ✅ **高级权限管理** 🔐：支持查询高级权限开关、开启/关闭高级权限、查询角色配置；支持给管理员、自定义角色添加人员/组织/大象群/邮件组/应用；支持从自定义角色删除成员；管理员和默认角色暂不支持删除成员；暂不支持修改权限配置

## 目录

- [📊 学城多维表格 XTable](#-学城多维表格-xtable)
  - [核心特性](#核心特性)
  - [目录](#目录)
  - [前置检查](#前置检查)
    - [Node.js 版本检查](#nodejs-版本检查)
    - [CLI 可用性检查](#cli-可用性检查)
  - [意图路由](#意图路由)
    - [用户贴入多维表格链接时的处理规则（必须遵守）](#用户贴入多维表格链接时的处理规则必须遵守)
  - [CLI 速查](#cli-速查)
  - [典型工作流](#典型工作流)
    - [📝 文档级别操作（使用 citadel 命令）](#-文档级别操作使用-citadel-命令)
  - [在学城文档内插入多维表格（标准流程）](#在学城文档内插入多维表格标准流程)
    - [创建多维文档后的授权收尾](#创建多维文档后的授权收尾)
  - [复制数据表](#复制数据表)
  - [账号转换（MIS ↔ empId ↔ UID）](#账号转换mis--empid--uid)
  - [列类型速查](#列类型速查)
  - [视图管理](#视图管理)
  - [AI 写公式](#ai-写公式-)
  - [约束](#约束)
  - [暂不支持](#暂不支持)
  - [认证](#认证)
  - [安全屋](#安全屋)
  - [多维表格链接格式](#多维表格链接格式)
  - [最佳实践](#最佳实践)
  - [常见问题](#常见问题)
  - [问题反馈](#问题反馈)

## 前置检查

### Node.js 版本检查

执行 xtable skill 时会自动检查 Node.js 版本是否符合要求（>= 18.0.0）。如果版本过低，系统会：

1. **自动检测并安装 nvm**（如未安装）
2. **通过 nvm 自动安装并切换到 Node.js 18 或更高版本**
3. **重新执行命令**，使用新的 Node.js 版本

**无需手动干预，版本升级完全自动化。** ✨

### CLI 可用性检查

每次 skill 激活时或首次执行命令前，先检查 `oa-skills` 是否存在；不存在时再执行安装。

```bash
node -e "const cp=require('child_process'); const probe=process.platform==='win32'?'where oa-skills':'command -v oa-skills'; try{cp.execSync(probe,{stdio:'ignore',shell:true})}catch{cp.execSync('npm install -g @it/oa-skills --registry=http://r.npm.sankuai.com',{stdio:'inherit',shell:true})}"
```

**此步骤必须执行一次，否则新环境中可能不存在 CLI 命令导致运行失败。**

## 意图路由

### 用户贴入多维表格链接时的处理规则（必须遵守）

当用户**仅贴入多维表格链接**（`km.sankuai.com/xtable/...`）而**未附带明确操作指令**时，禁止自动拉取数据，按以下步骤处理：

1. 从链接提取 `contentId`（路径中的数字）、`tableId`（`?table=` 参数，可能没有）、`viewId`（`?view=` 参数，可能没有）
2. 若链接只有 `contentId` 无 `tableId`，先执行 `listTables --contentId <id>` 获取表格列表
3. 执行 `getTableMeta --tableId <id>` 读取表格结构（列名、列类型、列ID等）
4. **将表格结构以简明方式展示给用户，然后停下来，询问用户想对这个表格做什么**（例如：查询数据、筛选分析、添加数据、更新数据等）
5. **收到用户的明确指令后**，再按需执行后续操作

> ⚠️ **禁止行为**：不得在仅收到链接时自动执行 `queryTableData` 拉取数据。只有用户明确说"查询数据""分析数据""拉取所有数据"等指令后才能拉取。

> 🔍 **视图查询规则**：若链接中包含 `viewId`（`?view=` 参数），且用户的意图明确指向该视图（如"查询这个视图的数据"、"看看这个视图"、"查这个视图"），执行 `queryTableData` 时**必须传入 `--viewId <id>`**，以使用该视图保存的列/筛选/排序配置进行查询。**注意**：`--viewId` 仅在未传 `--columnIds`/`--filter`/`--sort` 时生效，若用户同时指定了这些参数，则 `--viewId` 自动忽略。

**⚠️ 群权限提醒**：如果是在大象群里创建多维表格，创建后需要执行以下**两步授权**：① 使用 `oa-skills citadel grant --pageId <id> --xm-group-ids <群ID> --perm "仅浏览"` 为当前群授予浏览权限；② 使用 `oa-skills citadel grant --pageId <id> --person <管理员mis> --perm "可管理"` 为群助理的管理员授予管理权限。

### 多维表格高级权限路由规则

当用户明确提到"多维表格高级权限"、"默认角色"、"自定义角色"、"多维表格管理员"、"给角色加人/删人/加组织/删组织/加群/删群/加邮件组/删邮件组/加应用/删应用"时，加载 `{baseDir}/references/advanced-permission.md`，不要使用学城文档权限命令替代。

当前只支持：

- 查询高级权限开关状态
- 开启或关闭高级权限开关
- 查询管理员、默认角色、自定义角色配置
- 通过自定义角色名称精确匹配 `roleId`
- 给管理员、自定义角色添加人员、组织、大象群、邮件组、应用
- 从自定义角色删除人员、组织、大象群、邮件组、应用

当前不支持直接执行：

- 给默认角色添加成员
- 给管理员或默认角色删除成员
- 修改角色权限、更新成员角色

| 用户意图                    | 命令                                    |
| -------------------------- | --------------------------------------- |
| 创建一个新的多维表格文档     | `createDatabase [--contentTitle <标题>] [--tableTitle <表格>]` <br/>💡 标题可为空；不指定 `--parentId` 时创建在用户自己空间下，无需 `--mis` 参数 |
| 复制整个多维表格文档         | `createDatabase --contentTitle <标题> --sourceContentId <原文档ID> [--keepData true]` |
| 在现有文档中创建新数据表     | `createTable --contentId <id> [--tableTitle "任务表"] --columnMeta '[{"columnName":"任务名","columnType":1}]'` |
| 复制数据表到多维文档/学城文档 | `copyTable --sourceTableId <源ID> --targetParentId <目标ID> [--targetType <3\|4>]` <br/>💡 目标是学城文档时需额外执行 `updateDocumentByMd` 插入 `:::xtable` |
| 查看文档下有哪些表格         | `listTables --contentId <id>`                 |
| 查询表格的列结构（columnId） | `getTableMeta --tableId <id>`                          |
| 查询表格中的数据             | `queryTableData --tableId <id> [--columnIds <列ID>] [--filter <条件>] [--sort <排序>] --max-pages 10` <br/>💡 默认加 `--max-pages 10` 预览前 10 页，需全量时再去掉 <br/>💡 按视图查询时可传 `--viewId <id>`（仅在**未传** `--columnIds`/`--filter`/`--sort` 时生效，直接使用视图的列/筛选/排序配置） |
| 向表格中添加新数据           | `addData --tableId <id> --columnIds <列ID> --data '[...]'` |
| 更新表格中的数据             | `updateData --tableId <id> --rowIds <行ID> --data '[...]'` |
| 删除表格中的数据             | `deleteData --tableId <id> --rowIds "123456,123457"` |
| 重命名数据表                 | `renameTable --tableId <id> --title "新表格名称"`    |
| 数据表排序                   | `sortTable --tableId <id> --to 2`                    |
| 为数据表新增列               | `addTableColumns --tableId <id> --columnMetas '[{"columnName":"名称", "columnType": 1}]'` <br/>⚠️ 单选(3)/多选(5)列必须提供 `columnConfig.options`，例如：`{"columnName":"状态","columnType":3,"columnConfig":{"options":["选项1","选项2"]}}` <br/>各列类型 columnConfig 字段详见下方**列类型速查** |
| **新增公式列** 🧮          | `addTableColumns --tableId <id> --columnMetas '[{"columnName":"总价","columnType":9,"columnConfig":{"formula":"[#列ID1] * [#列ID2]","formulaFormat":2,"formatter":"0,0.00"}}]'` <br/>💡 `columnType:9` 为公式列，必须在 `columnConfig.formula` 中提供公式表达式；字段引用格式为 `[#列ID]`（需先用 `getTableMeta` 获取列ID，**不支持 `[列名]` 格式**）；**`formulaFormat` 控制结果类型：2=数字、7=日期、8=货币；结果为文本/字符串时不传此字段**；公式只能使用 `{baseDir}/references/data-format.md` 「完整函数表」中列出的函数 |
| **修改列配置** ⚙️         | `updateColumnConfig --tableId <id> --columnId <cid> --columnConfig '{"formula":"[#列ID1] + [#列ID2]"}'` <br/>💡 支持修改公式表达式、结果格式、formatter、货币代码、人员列是否多选、单选/多选 options 等；不传的字段保持原值；**不支持修改列类型** |
| **设置跨表公式** 🔗      | 先 `listTables --contentId <id>` 列出同文档所有表获取目标 tableId，再 `getTableMeta --tableId <目标表id>` 获取目标列 colId，然后用 `[$表ID].[#列ID]` 语法构造公式写入 `addTableColumns` 或 `updateColumnConfig` <br/>⚠️ 跨表公式只能引用**同一 contentId** 下的表；`$` 后接 tableId（较长数字），`#` 后接 colId（较短数字），不要颠倒；**跨表引用支持公式列和非公式列** |

> 🚨 **写公式前必读——三条硬性禁止（违反必出错）**
>
> | # | ❌ 禁止 | ✅ 正确 |
> |---|--------|--------|
> | 1 | `TEXT()`、`VLOOKUP()`、`DATEDIF()`、`EDATE()`、`NOW()`、`CONCAT()` 等 Excel/Sheets 函数 | **只能用** `{baseDir}/references/data-format.md` 「完整函数表」里列出的函数，白名单之外的函数在本系统中不存在 |
> | 2 | `[#1] == "值"`（双等号比较） | `[#1] = "值"`（**单等号**，本系统等于判断只用 `=`，`==` 是语法错误） |
> | 3 | `[5000#2]`（tableId 和 colId 合并写法）或 `[$5000#2]` | `[$5000].[#2]`（**`$tableId` 和 `#colId` 必须用 `.` 分开**，`$` 接目标表 tableId，`#` 接目标列 colId） |
| 修改已有列名称          | `updateColumnConfig --tableId <id> --columnId <cid> --columnName "新名称"` |
| 查询视图列表             | `queryTableViewList --tableId <id>` |
| 新增视图                 | `addTableView --tableId <id> --viewName "视图名" --viewType "TableModel\|FormModel\|GanttModel" [--config <json>]` |
| 更新视图名称或配置       | `updateTableView --tableId <id> --viewId <id> [--viewName "新名"] [--config <json>]` <br/>⚠️ **修改/追加/删除配置中的某一条时，必须先执行 `queryTableViewList` 读取当前 config，在原值基础上修改后整体传入**——这些字段是整体覆盖，直接传新值会丢失其余条件。仅重命名或明确全量覆盖时无需先查询。 |
| 删除视图                 | `deleteTableView --tableId <id> --viewId <id>` |
| **查询用户信息（账号转换）** | `getUserInfo --misList 'mis1,mis2'`                     |
| **通过 UID 查询 MIS/empId** | `queryUserIdentityByUid --uidList 'uid1,uid2'`         |
| **上传本地文件到表格**       | `uploadFile --contentId <id> --tableId <id> --file <路径>` |
| **上传文件并添加到附件列** ⭐ | `uploadFileAndAddData --contentId <id> --tableId <id> --file <路径> --columnIds <列ID> --data '[...]'` |
| 通过 S3 URL 上传文件 🔧      | `uploadFileByS3Url --s3Url <S3地址> [--fileName <文件名>] --contentId <id>` |
| 在学城文档内插入多维表格     | `依次执行：createTable → addData → updateDocumentByMd` |
| **查询高级权限开关** 🔐  | `getAdvancedPermStatus --contentId <id>` |
| **开启/关闭高级权限开关** 🔐  | 开启前先执行 `getAdvancedPermStatus --contentId <id>` 判断是否首次开启；状态 `0` 直接执行 `updateAdvancedPermStatus --contentId <id> --status enabled`；状态 `1/2` 再查 `listAdvancedPermRoles --roleType custom --raw`，无成员 CLI 自动补 `preserveOriginalRole=true`，有成员必须询问用户并传 `--preserveOriginalRole true\|false`；关闭用 `updateAdvancedPermStatus --contentId <id> --status disabled` |
| **添加高级权限角色成员** 🔐  | `addAdvancedRoleMembers --contentId <id> --roleType admin\|custom (--roleId <id> \| --roleName <自定义角色名>) [--person <mis>] [--orgs <json>] [--xmGroupIds <ids>] [--mails <mail>] [--appIds <ids>]` |
| **删除高级权限自定义角色成员** 🔐  | `deleteAdvancedRoleMembers --contentId <id> --roleType custom (--roleId <id> \| --roleName <自定义角色名>) [--person <mis>] [--orgs <json>] [--xmGroupIds <ids>] [--mails <mail>] [--appIds <ids>]` |

**图例说明**：⭐ 推荐使用 | 🔧 低层 API（调试/特殊集成用）

## CLI 速查

**命令格式**：`oa-skills citadel-database <command> [options]`  
**通用选项**：`--mis <mis>` | `--raw` | `--clear-cache` | `--force-ciba`（仅在认证异常时兜底使用，正常不需要添加）

📖 执行具体命令前，加载 `{baseDir}/references/cli-reference.md` 获取完整参数、示例和工作流

## 典型工作流

```
1. 准备阶段 → 2. 权限管理 → 3. 数据操作 → 4. 验证结果
```

**阶段 1: 准备** — `getTableMeta` 获取列 ID、列类型、列配置

**阶段 2: 权限管理**（大象群建文档时必需）— 文档级权限使用 `oa-skills citadel` 两步授权；多维表格高级权限使用本 skill，加载 `{baseDir}/references/advanced-permission.md`

**阶段 3: 数据操作** — `addData` / `updateData` / `queryTableData` / `deleteData`

**阶段 4: 验证** — `queryTableData` 确认修改成功；若操作涉及日期列，必须检查返回的 `dateCellValue` 对应日期是否与预期一致

### 📝 文档级别操作（使用 citadel 命令）

对于文档级别操作（删除/恢复/移动文档、获取评论、权限管理），请使用 `oa-skills citadel` 命令。禁止自己猜测 citadel skill 支持的命令，需要通过 `--help` 参数查看。

## 在学城文档内插入多维表格（标准流程）

当用户需要"创建一篇文档，文档内插入多维表格"时，必须严格按以下 4 步执行：

1. **建普通学城文档**（`citadel` skill）
   ```bash
   oa-skills citadel createDocument --title <标题> --content "<文档初始内容（可为空字符串）>"
   # → 得到 docContentId
   # ⚠️ --content 为必填参数（可传空字符串 ""），不传会报错
   ```

2. **直接在这篇学城文档内建数据表**（在此定义列结构）
   ```bash
   oa-skills citadel-database createTable \
     --contentId <docContentId> \
     --tableTitle <表格名> \
     --columnMeta '[{"columnName":"列名","columnType":1}]'
   # → 得到 tableId
   ```

3. **写入数据**
   ```bash
   oa-skills citadel-database addData \
     --tableId <tableId> \
     --columnIds "1,2,3" \
     --data '[...]'
   ```

4. **将多维表格嵌入学城文档**（`citadel` skill）
   ```bash
   # CitadelMD 中使用以下语法嵌入（新增节点时可省略 nodeId）：
   :::xtable{xtableId="<tableId>"}:::

   oa-skills citadel updateDocumentByMd \
     --contentId <docContentId> \
     --file <citadelmd文件路径>
   ```

**⚠️ 注意事项：**

- 在学城文档内插入多维表格时，**不需要**先创建多维表格文档，直接调用 `createTable` 即可
- `createTable` 的 `--contentId` 就是这篇学城文档 ID（`docContentId`）
- `addData` 使用的是返回的 `tableId`，不是 `contentId`
- `:::xtable` 的属性名是 `xtableId`，这里传的是数据表 ID（`tableId`），不是学城文档 ID（`docContentId`）
- `nodeId` 逻辑遵循 `citadel/references/doc-syntax.md`：编辑已有 `:::xtable` 节点时保留原值；新增节点时可以省略，由转换器自动生成

### 创建多维文档后的授权收尾

每次 `createDatabase` 成功后，必须询问用户是否需要授权。若场景为**大象群**，自动执行两步授权。当用户需要为文档授权、改权、移权、管理权限继承时，加载 `{baseDir}/references/permission-management.md`。

## 复制数据表

根据目标不同分三个场景：A) 复制整个多维表格文档用 `createDatabase --sourceContentId`；B) 复制数据表到学城文档需 `copyTable` 后再插入 `:::xtable`；C) 复制数据表到另一个多维文档用 `copyTable --targetType 4`。详细步骤见 `{baseDir}/references/cli-reference.md` 的 `createDatabase` / `copyTable` 章节。

## 账号转换（MIS ↔ empId ↔ UID）

| 命令 | 用途 | 输入格式 |
|------|------|----------|
| `getUserInfo --misList 'mis1,mis2'` | MIS → uid/empId/姓名 | 逗号分隔或 JSON 数组 |
| `queryUserIdentityByUid --uidList 'uid1,uid2'` | UID → mis/empId | 逗号分隔或 JSON 数组 |

详细参数和示例见 `{baseDir}/references/cli-reference.md` 的 getUserInfo / queryUserIdentityByUid 章节。

## 列类型速查

| columnType | 类型 | 数据结构 | 示例 |
|------------|------|----------|------|
| 1 | 文本 | `IRichTextNode[]` | `[{type:"text",value:"任务A"}]` |
| 2 | 数字 | `number` | `100` |
| 3 | 单选 | `string` | `"进行中"` |
| 4 | 人员 | `empId[]` | `[2015738,2015739]` |
| 5 | 多选 | `string[]` | `["标签1","标签2"]` |
| 6 | 附件 | `string[]` (JSON) | `[JSON.stringify({attachmentId:0,name:"f.png",url:"…"})]` |
| 7 | 日期 | `string` (日期字符串，推荐) 或 `number` (timestamp ms) | `"2026-04-27"` 或 `"2026-04-27T09:00"` |
| 8 | 货币 | `number` | `99.99` |
| 9 | 公式 | 只读（列内单元格不可写入） | 公式列的表达式在 `columnConfig.formula` 中配置 |
| 10 | 查找引用 | 只读 | 不支持写入 |

### 新增/编辑列时 columnConfig 各类型说明

> 适用于 `addTableColumns` 和 `updateColumnConfig --columnConfig`，不传的字段保持原值（编辑时）。

| columnType | 支持的 columnConfig 字段 | 说明与示例 |
|------------|--------------------------|------------|
| 1 文本 | 无 | 无需传 columnConfig |
| 2 数字 | `formatter` | 数字格式化：`""` 无格式 / `"0"` 整数 / `"0.00"` 2位小数 / `"0,0"` 千分位 / `"0,0.00"` 千分位2位小数 / `"0%"` 百分比 |
| 3 单选 | `options` | 新增时传选项名称字符串列表；编辑已有列时支持字符串列表或包含 `id`/`label`/`color` 的对象列表，支持改名、排序、新增；不支持删除已有选项；最多512项，每项 label 不超过100字符；示例：`{"options":["未开始","进行中","已完成"]}` 或 `{"options":[{"id":123,"label":"进行中","color":"#E8F3FF"}]}` |
| 4 人员 | `multiple` | 是否允许多人，默认 `false`；示例：`{"multiple":true}` |
| 5 多选 | `options` | 同单选，参见 type:3 |
| 6 附件 | 无 | 无需传 columnConfig |
| 7 日期 | `formatter` | 日期格式：`"YYYY/MM/DD"`（默认）/ `"YYYY-MM-DD"` / `"YYYY/MM/DD HH:mm"` / `"YYYY-MM-DD HH:mm"` / `"MM-DD"` / `"MM/DD/YYYY"` / `"DD/MM/YYYY"` |
| 8 货币 | `currencyCode` / `currencySymbol` / `formatter` | 货币代码默认 `"CNY"`，符号默认 `"¥"`，formatter 同数字列；示例：`{"currencyCode":"USD","currencySymbol":"$","formatter":"0,0.00"}` |
| 9 公式 | `formula` / `formulaFormat` / `formatter` / `currencyCode` / `currencySymbol` / `multiple` | `formula`：公式表达式；`formulaFormat`：结果类型，`2`=数字 / `7`=日期 / `8`=货币；`formatter` 与 `formulaFormat` 对应类型匹配；示例：`{"formula":"[#101]*[#102]","formulaFormat":2,"formatter":"0,0.00"}` |

```bash
# 逗号分隔格式（推荐）
oa-skills citadel-database getUserInfo --misList 'zhangsan,lisi'
# 或 JSON 数组格式
oa-skills citadel-database getUserInfo --misList '["zhangsan", "lisi"]'
```

**📖 完整数据格式文档**：操作文本/附件/日期/人员列、构造筛选/排序条件时，加载 `{baseDir}/references/data-format.md`（富文本节点、附件格式、筛选/排序语法、列配置、常见错误）

## AI 写公式 🧮

> 🚨 **公式语法红线（生成公式前必读，违反必出错）**
>
> | # | 规则 | ✅ 正确（数字ID） | 🚫 禁止 |
> |---|------|---------|---------|
> | 1 | 本表列引用 | `[#1]`（`#` 后接数字 colId） | `[列名]`、`[#列名]` |
> | 2 | 跨表列引用 | `[$5000].[#2]`（`$` 后接数字 tableId，`#` 后接数字 colId，两段用 `.` 连接） | `[5000#2]`（合并写法，**语法不存在**） |
> | 3 | 跨表 LOOKUP | `LOOKUP([#1] & "", [$5000].[#1], [$5000].[#2])` | `LOOKUP([#1], [5000#1], [5000#2])` |
> | 4 | 跨表 COUNTIF | `[$5000].[#2].COUNTIF(CurrentValue & "" = [#1] & "")` | `COUNTIF([5000#2], [#1])` |
> | 5 | 跨表 SUMIF | `[$5000].[#3].FILTER(CurrentValue = [#1]).SUMIF(CurrentValue > 0)` | `SUMIF([5000#3], [#1])` |
> | 6 | 比较等于 | `[#1] = "值"` | `[#1] == "值"` |
> | 7 | 单选/人员列转字符串 | `[#1] & ""` | 直接用 `[#1]` 参与字符串运算（缺 `& ""`） |

当用户说"帮我写一个公式"、"添加公式列"、"计算xxx"时，**先执行 `getTableMeta` 获取真实 colId，再生成公式，最后写入**。

**写入命令：**
- 新增公式列：`addTableColumns --tableId <id> --columnMetas '[{"columnName":"<列名>","columnType":9,"columnConfig":{"formula":"<表达式>"[,"formulaFormat":<类型>,"formatter":"<格式>"]}}]'`
- 修改已有公式列：`updateColumnConfig --tableId <id> --columnId <cid> --columnConfig '{"formula":"<表达式>"[,"formulaFormat":<类型>]}'`
- 跨表公式：先 `listTables` 获取目标 tableId，再 `getTableMeta` 获取目标 colId，用 `[$tableId].[#colId]` 引用；**只能引用同一 contentId 下的表**

**`formulaFormat`**：结果为数字传 `2`、日期传 `7`、货币传 `8`；**结果为文本/字符串时省略**

### 🔒 函数白名单（封闭集）

**以下是本系统支持的全部函数。不在此表中的函数不存在，必须用表中函数组合实现。**

| 类别 | 可用函数 |
|------|----------|
| 逻辑 | `IF` · `IFS` · `SWITCH` · `IFBLANK` · `IFERROR` · `ISBLANK` · `ISERROR` · `AND` · `OR` · `NOT` · `TRUE()` · `FALSE()` |
| 数字 | `ROUND` · `ROUNDUP` · `ROUNDDOWN` · `ABS` · `POWER` · `VALUE` · `SUM` · `AVERAGE` · `MAX` · `MIN` · `COUNTA` |
| 日期 | `TODAY()` · `DATE` · `DAYS` · `YEAR` · `MONTH` · `DAY` · `HOUR` · `MINUTE` · `SECOND` · `WEEKDAY` |
| 文本 | `CONCATENATE` · `LEFT` · `RIGHT` · `MID` · `LEN` · `TRIM` · `UPPER` · `LOWER` · `FIND` · `REPLACE` · `SUBSTITUTE` · `CONTAINTEXT` · `&`（拼接运算符） |
| 集合/统计 | `LIST` · `ARRAYJOIN` · `UNIQUE` · `LISTCOMBINE` · `CONTAIN` · `LOOKUP` · `SUMIF` · `COUNTIF` · `.FILTER()` |

### 需求 → 正确写法对照表

| 需求场景 | ❌ 模型容易犯的错 | ✅ 唯一正确写法 |
|----------|-------------------|----------------|
| 保留 N 位小数显示 | `TEXT(值, "0.0")` | `ROUND(值, N) & "后缀"` |
| 百分比文本（如 "80.0%"） | `TEXT(值*100, "0.0") & "%"` | `ROUND(值 * 100, 1) & "%"` |
| 防除零的百分比 | `TEXT(IF(b=0,0,a/b), "0.0%")` | `IFERROR(ROUND(a / b * 100, 1) & "%", "0%")` |
| 两个日期相差天数 | `DATEDIF(开始, 结束, "D")` | `DAYS(结束, 开始)` |
| 距今天还有几天 | `DATEDIF(TODAY(), 日期, "D")` | `DAYS(日期, TODAY())` |
| 工作日天数计算 | `NETWORKDAYS(开始, 结束)` | ⚠️ 不支持，告知用户无法实现 |
| 日期加减 N 个月 | `EDATE(日期, N)` | ⚠️ 不支持，告知用户无法实现 |
| 当前时间 | `NOW()` | `TODAY()`（仅支持日期，不支持时分秒） |
| 拼接字符串 | `CONCAT(a, b)` | `CONCATENATE(a, b)` 或 `a & b` |
| 格式化日期为文本 | `TEXT(日期, "YYYY-MM")` | `YEAR(日期) & "-" & MONTH(日期)` |
| 月份/日期补零（如 `03`） | `TEXT(MONTH(日期), "00")` | `IF(MONTH(日期) < 10, "0" & MONTH(日期), MONTH(日期) & "")` |
| 格式化为 `YYYY/MM`（月份补零） | `TEXT(日期, "YYYY/MM")` | `YEAR(日期) & "/" & IF(MONTH(日期) < 10, "0" & MONTH(日期), MONTH(日期) & "")` |
| 查表取值 | `VLOOKUP()` / `XLOOKUP()` | `LOOKUP(搜索值, 匹配列, 取值列)` |
| 多条件求和/计数 | `SUMIFS()` / `COUNTIFS()` | `[$5000].[#3].FILTER(CurrentValue = [#1]).SUMIF(CurrentValue > 0)` |
| 判断相等 | `[#1] == "值"` | `[#1] = "值"` |
| 判断不等 | `[#1] !== "值"` | `[#1] != "值"` |
| 人员/单选列拼接到文本 | `"负责人：" & [#1]` | `"负责人：" & [#1] & ""`（人员/单选必须加 `& ""` 转字符串） |
| IFS 最后的 else 分支 | 裸值（如 `IFS(..., "默认")`） | `TRUE(), "默认"` |

📖 完整运算符表、函数参数说明、公式模板见 `{baseDir}/references/data-format.md`「公式语法速查」章节
## 视图管理

| 用户意图 | 命令 |
|---------|------|
| 查看表格下所有视图 | `queryTableViewList --tableId <id>` |
| 新建视图 | `addTableView --tableId <id> --viewName "视图名" --viewType "TableModel\|FormModel\|GanttModel" [--config <json>]` |
| 修改视图名称或配置 | `updateTableView --tableId <id> --viewId <id> [--viewName "新名"] [--config <json>]` |
| 删除视图 | `deleteTableView --tableId <id> --viewId <id>` |

> ⚠️ **`updateTableView` 注意**：修改/追加/删除 config 中某一条时，必须先执行 `queryTableViewList` 读取当前配置，在原值基础上修改后整体传入，否则会丢失其余条件。仅重命名时无需先查询。

📖 完整参数和 ViewConfig 配置说明见 `{baseDir}/references/view-management.md`。

## 约束

> ### 🚫 日期字段强制规则（最高优先级，执行前必读）
>
> **禁止手写或心算毫秒时间戳。** LLM 训练数据含历史年份，手写时间戳必然导致年份错误（通常偏差约1年）。
>
> **唯一正确做法：直接传日期字符串，CLI 自动转换：**
>
> ❌ 禁止：`--data '[["2026-05-09"]]'` 改为手写时间戳 `--data '[[1778256000000]]'`  
> ✅ 正确：`--data '[["2026-05-09"]]'`（字符串，CLI 自动按本地时区转换）
>
> 若业务场景必须用数字时间戳，必须先执行以下命令获取，禁止估算：
> ```
> node -e "console.log(new Date('2026-05-09').getTime())"
> ```

- `--mis` 参数可选，未指定时从 `~/.config/clawdgw.json` 读取
- 缺少关键参数时只追问必要字段（--contentId / --tableId / --columnIds），不给笼统报错
- 列 ID 格式灵活：支持逗号分隔 `"1,2,3"` 或 JSON 数组 `[1,2,3]`
- **列类型严格校验**：必须按列类型表传入正确格式，否则 API 报错
- **数据量限制**：单次操作最多 500 行；批量写建议每批 ≤100 行，超 500 行自动分批
- **列类型选择强制要求**：创建表格时必须根据数据用途选对应列类型，不要全部用文本列
- **单选/多选列必须提供 options**：新增单选（columnType: 3）或多选（columnType: 5）列时，`columnConfig.options` 为必填项且至少需要一个选项，否则命令报错。示例：`{"columnName":"状态","columnType":3,"columnConfig":{"options":["未开始","进行中","已完成"]}}`
- **筛选语法**：`operator` 只使用"筛选和排序"章节列出的枚举值；`filterValue` 始终传 `string[]`，`isnull`/`notnull` 传 `[]`
- **单选/多选列 options 不允许删除已有选项**：修改已有单选/多选列的 `options` 时，先用 `getTableMeta` 获取当前 `columnConfig.options`，必须保留所有已有选项；对象项可用 `id` 保留/改名/改色，调整数组顺序即可改选项顺序，新增选项可追加 label；缺少已有选项会报错
- **列配置修改必须串行执行**：对同一张表执行多个 `updateColumnConfig` 或 `addTableColumns` 时，必须串行执行（命令间用 `&&` 顺序连接），**禁止并发**（`&` 后台并行），否则版本号冲突会导致部分操作静默失败
- **风控要求**：不得在输出中包含内部 IP、Token、敏感密钥
- **日期列必须传字符串**：日期列（columnType: 7）必须直接传 `"YYYY-MM-DD"` 或 `"YYYY-MM-DDTHH:mm"` 字符串，CLI 内部自动按本地时区转换为毫秒时间戳，无需手动计算。若传数字时间戳，禁止手写或估算，必须通过上方命令实时计算

## 暂不支持

- **修改列类型**（不支持将已有列改为其他类型）
- **列的删除**
- LOOKUP（查找引用）列及系统列（code ≥ 101）的创建

用户要求时明确说明"当前暂不支持"。替代方案：可通过 Web UI 手动操作。

## 认证

根据运行环境选择合适的策略，优先 SSO 无感登录。Token 自动缓存。认证失败时执行 `oa-skills citadel-database --clear-cache` 后重试。详细说明见 `{baseDir}/references/cli-reference.md`。

## 安全屋

读写 C4 级别的多维表格数据需要在安全屋模式下运行。

**使用方式**：在 大象助理 中开启安全屋模式，之后正常执行命令即可，无需额外参数。

**错误提示**：若未开启安全屋，操作 C4 数据时可能收到如下提示：

> 当前数据返回不完整，请打开安全屋模式查看完整数据返回。

遇到此提示时，在 大象助理 中开启安全屋后重新执行命令。

## 多维表格链接格式

**线上环境**：
```
https://km.sankuai.com/xtable/{contentId}?table={tableId}&view={viewId}
```

**测试环境**（`--access-env test`）：
```
https://km.it.test.sankuai.com/xtable/{contentId}?table={tableId}&view={viewId}
```

参数说明：`contentId`（文档 ID，必需）、`tableId`（表格 ID，可选）、`viewId`（视图 ID，可选）

## 最佳实践

1. **先查询元数据**：使用 `getTableMeta` 获取列 ID、列类型、列配置后再操作数据
   - 从 `columnConfig.options` 获取单选/多选的有效选项
   - 检查 `columnConfig.multiple` 确认人员列是否支持多选
2. **数据查询默认用预览模式**：执行 `queryTableData` 时，除非用户明确说"获取全部数据""导出所有""分析全量"，否则**必须加 `--max-pages 10`**，取到数据后展示摘要并询问用户是否需要继续获取剩余数据
3. **数据格式准备**：单选/多选用 `options.label`；人员列用 empId；日期列直接传字符串（见「约束」章节日期规则）；`formatter` 只影响 UI 展示
4. **群场景建表后补权限**：在大象群创建文档后立即执行两步授权
5. **错误排查**：检查错误信息中的 TraceID 用于问题追踪

## 常见问题

**Q: 如何获取列ID？**  
A: `getTableMeta` 查询表格元数据。

**Q: 日期格式如何处理？**  
A: 直接传日期字符串（如 `"2026-04-27"` 或 `"2026-04-27T09:00"`），CLI 自动转换。详见上方「约束」章节日期规则。

**Q: 如何处理人员类型？**  
A: 人员类型使用 empId 数字数组，用 `getUserInfo` 命令转换 MIS → empId。

**Q: 单选/多选需要提前创建选项吗？**  
A: 不需要，系统自动创建。用 `getTableMeta` 查看现有选项。

**Q: 如何删除多维表格文档？**  
A: `oa-skills citadel deleteDocument --contentId <id>`（文档级操作由 citadel skill 负责）。

**Q: 认证失败怎么办？**  
A: `oa-skills citadel-database --clear-cache`。

## 问题反馈
点击 https://applink.neixin.cn/profile?gid=70411238253 加入学城多维表格官方 Skill 客服群大象群
