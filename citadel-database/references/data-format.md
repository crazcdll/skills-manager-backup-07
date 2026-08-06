# 数据格式参考

多维表格数据格式说明，包含列类型、单元格数据结构和转换规则。

## 目录

- [数据格式参考](#数据格式参考)
  - [目录](#目录)
  - [列类型 (ColumnType)](#列类型-columntype)
  - [列配置 (columnConfig) 说明](#列配置-columnconfig-说明)
    - [TypeScript 类型定义](#typescript-类型定义)
    - [按列类型分类的配置说明](#按列类型分类的配置说明)
      - [formatter 格式规则](#formatter-格式规则)
    - [使用示例](#使用示例)
  - [富文本格式 (TextCellValue)](#富文本格式-textcellvalue)
    - [节点类型](#节点类型)
      - [1. 纯文本节点](#1-纯文本节点)
      - [2. 超链接节点](#2-超链接节点)
      - [3. @提及节点](#3-提及节点)
      - [4. 段落节点](#4-段落节点)
      - [5. 混合格式](#5-混合格式)
    - [自动转换规则](#自动转换规则)
  - [二维数组格式](#二维数组格式)
    - [基本结构](#基本结构)
    - [列对应关系](#列对应关系)
    - [类型示例](#类型示例)
      - [1. 文本列 (columnType: 1)](#1-文本列-columntype-1)
      - [2. 数字列 (columnType: 2)](#2-数字列-columntype-2)
      - [3. 单选列 (columnType: 3)](#3-单选列-columntype-3)
      - [4. 人员列 (columnType: 4)](#4-人员列-columntype-4)
      - [5. 多选列 (columnType: 5)](#5-多选列-columntype-5)
      - [6. 附件列 (columnType: 6)](#6-附件列-columntype-6)
      - [7. 日期列 (columnType: 7)](#7-日期列-columntype-7)
      - [8. 货币列 (columnType: 8)](#8-货币列-columntype-8)
  - [查询响应格式](#查询响应格式)
    - [QueryTableDataResponse](#querytabledataresponse)
    - [TableMetaResponse](#tablemetaresponse)
  - [筛选条件格式 (FilterConfig)](#筛选条件格式-filterconfig)
    - [支持的操作符](#支持的操作符)
    - [筛选示例](#筛选示例)
  - [排序配置格式 (SortConfig)](#排序配置格式-sortconfig)
    - [排序示例](#排序示例)
  - [常见错误和解决方案](#常见错误和解决方案)
    - [1. 列类型不匹配](#1-列类型不匹配)
    - [2. empId 类型错误](#2-empid-类型错误)
    - [3. 富文本嵌套层级](#3-富文本嵌套层级)
    - [4. 二维数组结构](#4-二维数组结构)
    - [5. 日期格式](#5-日期格式)
  - [数据转换工具函数](#数据转换工具函数)
    - [JavaScript/TypeScript](#javascripttypescript)
    - [Bash](#bash)
  - [批量操作模式](#批量操作模式)
    - [批量新增](#批量新增)
    - [批量更新](#批量更新)
  - [API 响应示例](#api-响应示例)
    - [成功响应](#成功响应)
    - [错误响应](#错误响应)
    - [数据查询响应（完整示例）](#数据查询响应完整示例)
  - [公式语法速查](#公式语法速查)
    - [公式列概述](#公式列概述)
    - [运算符表](#运算符表)
    - [完整函数表](#完整函数表)
    - [CLI 快速操作示例](#cli-快速操作示例)
    - [常见公式模板](#常见公式模板)

## 列类型 (ColumnType)

| 类型ID | 类型名称 | TypeScript 类型 | API 字段名 | 输入格式 | 说明 |
|---|---|---|---|---|---|
| 1 | 文本（富文本） | `IRichTextNode[]` | `textCellValue` | 字符串或节点数组 | 支持纯文本、超链接、@提及、段落节点 |
| 2 | 数字 | `number` | `numberCellValue` | `number` | 数值类型 |
| 3 | 单选 | `string` | `selectCellValue` | `string` | 单选选项的值 |
| 4 | 人员 | `number[]` | `peopleCellValue` | `number[]` 或 `string[]` | empId 数组 |
| 5 | 多选 | `string[]` | `multipleSelectCellValue` | `string[]` | 多选选项的值数组 |
| 6 | 附件 | `string[]` | `fileCellValue` | `string[]` (JSON 字符串) | 附件 JSON 字符串数组 |
| 7 | 日期 | `string` 或 `number` | `dateCellValue` | `string`（推荐）或 `number` | 日期字符串自动按本地时区转换；或传毫秒时间戳 |
| 8 | 货币 | `number` | `numberCellValue` | `number` | 数值类型 |
| 9 | 公式 | 只读 | - | - | 不支持写入 |
| 10 | 查找引用 | 只读 | - | - | 不支持写入；查询时返回引用值的文本表示 |

## 列配置 (columnConfig) 说明

`getTableMeta` 返回的每列元数据中包含 `columnConfig` 字段，描述列的配置属性。不同 columnType 支持不同的配置项。

### TypeScript 类型定义

```typescript
interface ColumnConfig {
  /** 公共属性：列的默认值，适用于单选、多选、人员等类型 */
  defaultValue?: any;

  /** 选项配置（单选 type:3、多选 type:5）：可选项列表 */
  options?: Array<{
    id: string;       // 选项 ID
    label: string;    // 选项显示名称（数据中实际使用的值）
    color?: string;   // 选项颜色代码
  }>;

  /** 人员配置（人员 type:4）：是否支持多人选择 */
  multiple?: boolean;  // true=多人, false=单人

  /** 格式化配置（数字 type:2、日期 type:7、货币 type:8）：UI 展示格式规则 */
  formatter?: string;
}
```

### 按列类型分类的配置说明

**公共属性 — `defaultValue`**
- 适用类型：单选(3)、多选(5)、人员(4)
- 说明：列的默认值，新建行时自动填充
- 示例：单选列设置 `defaultValue: "待处理"` 则新行自动选中"待处理"

**选项配置 — `options`**（单选 type:3、多选 type:5）
- 说明：可选项列表，每项包含 `id`、`label`、`color`
- 写入数据时传的值必须匹配 `label`
- 新增单选/多选列时，`columnConfig.options` 传选项名称字符串列表，例如：`{"options":["未开始","进行中","已完成"]}`
- 修改已有单选/多选列时，`updateColumnConfig --columnConfig` 支持两种 options 项：
  - 字符串：`"已完成"`，按 label 匹配旧选项或新建选项
  - 对象：`{"id":123,"label":"进行中","color":"#E8F3FF"}`，用于保留/改名/改色已有选项
- 修改 options 时必须保留所有已有选项；支持保留 id 后修改 label、调整数组顺序、新增 label；不支持删除已有选项，缺少已有选项会报错
- 写入时可传 `--allowCreateOptions <true|false>`：
  - 默认 `true`：值不在 options 中时自动新建选项
  - 传 `false`：值必须已存在于 options 中，否则报错

**人员配置 — `multiple`**（人员 type:4）
- 说明：是否支持多人选择
- `true`：人员列接受 empId 数组，如 `[2015738, 2015739]`
- `false`：人员列只接受单个 empId，如 `2015738`

**格式化配置 — `formatter`**（数字 type:2、日期 type:7、货币 type:8）
- ⚠️ **重要：formatter 只影响 UI 展示，不影响数据读写**
- 数据传输时仍使用原始类型：数字传数字、日期传时间戳
- 业务侧可根据 formatter 决定展示方式，但不需要按格式转换数据后再提交

#### formatter 格式规则

| 列类型 | formatter 示例 | 说明 |
|--------|----------------|------|
| 数字 (type:2) | `"0.00"` | 2 位小数 |
| 数字 (type:2) | `"0,0.00%"` | 百分比 + 千分位 + 2位小数（numerify 格式） |
| 数字 (type:2) | `"#,##0"` | 千分位整数 |
| 日期 (type:7) | `"YYYY-MM-DD"` | 日期（moment.js 格式） |
| 日期 (type:7) | `"YYYY/MM/DD HH:mm"` | 日期+时间 |
| 货币 (type:8) | `"¥#,##0.00"` | 人民币格式 |
| 货币 (type:8) | `"$0.00"` | 美元格式 |

### 使用示例

```bash
# 查看"状态"列的选项配置
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '.columns[] | select(.columnName=="状态") | {columnName, columnType, columnConfig}'

# 输出示例：
# {
#   "columnName": "状态",
#   "columnType": 3,
#   "columnConfig": {
#     "defaultValue": "待处理",
#     "options": [
#       {"id": "opt1", "label": "待处理", "color": "#999"},
#       {"id": "opt2", "label": "进行中", "color": "#1890ff"},
#       {"id": "opt3", "label": "已完成", "color": "#52c41a"}
#     ]
#   }
# }

# 查看所有单选/多选列的可选项
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '[.columns[] | select(.columnType==3 or .columnType==5) | {columnName, columnType, options: .columnConfig.options}]'

# 查看人员列是否支持多人
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '.columns[] | select(.columnType==4) | {columnName, multiple: .columnConfig.multiple}'

# 查看数字/日期列的格式化规则
oa-skills citadel-database getTableMeta --tableId "2750248577" --raw | \
  jq '[.columns[] | select(.columnType==2 or .columnType==7 or .columnType==8) | {columnName, columnType, formatter: .columnConfig.formatter}]'
```

## 富文本格式 (TextCellValue)

文本列（columnType: 1）支持富文本节点数组 `IRichTextNode[]`。

### 节点类型

#### 1. 纯文本节点

```typescript
{
  type: "text",
  value: "纯文本内容"
}
```

**示例**：
```json
[
  { "type": "text", "value": "Hello World" }
]
```

#### 2. 超链接节点

```typescript
{
  type: "link",
  value: "显示文字",
  link: "<链接URL>"
}
```

**示例**：
```json
[
  { "type": "text", "value": "访问 " },
  { "type": "link", "value": "美团官网", "link": "https://meituan.com" }
]
```

#### 3. @提及节点

```typescript
{
  type: "mention",
  value: "@用户名",  // value 必须以 @ 开头
  empId: 2015739   // 必须是 number 类型
}
```

**示例**：
```json
[
  { "type": "text", "value": "负责人：" },
  { "type": "mention", "value": "@张三", "empId": 2015739 }
]
```

#### 4. 段落节点

```typescript
{
  type: "paragraph",
  value: " "
}
```

说明：
- `paragraph` 节点发送前会统一补成 `value: " "`
- 如果传了其他 `value`，CLI 会在发送前规范化为单个空格

**示例**：
```json
[
  { "type": "text", "value": "第一段" },
  { "type": "paragraph", "value": " " },
  { "type": "text", "value": "第二段" }
]
```

#### 5. 混合格式

```json
[
  { "type": "text", "value": "请 " },
  { "type": "mention", "value": "@张三", "empId": 2015739 },
  { "type": "text", "value": " 查看 " },
  { "type": "link", "value": "项目文档", "link": "https://km.sankuai.com/page/123" },
  { "type": "text", "value": " 并在本周五前完成" }
]
```

### 自动转换规则

CLI 会自动将简单字符串转换为富文本格式：

```bash
# 输入：简单字符串
--data '[["任务A"]]'

# 自动转换为：
[{"type": "text", "value": "任务A"}]
```

如需使用超链接、@提及或段落节点，必须手动构造富文本节点数组。

## 二维数组格式

### 基本结构

所有数据操作（addData、updateData）都使用**二维数组**格式：

```typescript
[
  ["行1列1", "行1列2", "行1列3"],  // 第1行
  ["行2列1", "行2列2", "行2列3"]   // 第2行
]
```

### 列对应关系

数据列的顺序必须与 `--columnIds` 参数指定的列 ID 顺序一致：

```bash
--columnIds "1,2,3"
--data '[["值1", "值2", "值3"]]'
       # ↑对应列1  ↑对应列2  ↑对应列3
```

### 类型示例

#### 1. 文本列 (columnType: 1)

```json
// 简单文本
[["简单文本"]]

// 富文本（超链接）
[[[
  {"type":"text","value":"查看"},
  {"type":"link","value":"文档","link":"https://km.sankuai.com/page/123"}
]]]

// 富文本（段落）
[[[
  {"type":"text","value":"第一段"},
  {"type":"paragraph", "value": " "},
  {"type":"text","value":"第二段"}
]]]

// 富文本（@提及）
[[[
  {"type":"text","value":"负责人："},
  {"type":"mention","value":"@张三","empId":2015739}
]]]
```

#### 2. 数字列 (columnType: 2)

```json
[[100]]           // 整数
[[3.14]]          // 浮点数
[[0]]             // 零
[[-50]]           // 负数
```

#### 3. 单选列 (columnType: 3)

```json
[["待处理"]]      // 必须是已定义的选项值
[["进行中"]]
[["已完成"]]
```

**注意**：值必须精确匹配 `selectOptions` 中定义的选项。

#### 4. 人员列 (columnType: 4)

```json
[[2015739]]                 // 单人（数字）
[["2015739"]]               // 单人（字符串）
[[2015739, 2015740]]        // 多人（数字数组）
[["2015739", "2015740"]]    // 多人（字符串数组）
```

#### 5. 多选列 (columnType: 5)

```json
[["选项1"]]                  // 单选
[["选项1", "选项2"]]         // 多选
[[[]]]                       // 空值
```

#### 6. 附件列 (columnType: 6)

附件列使用 **JSON 字符串数组**格式，每个附件必须序列化为 JSON 字符串。

**附件对象结构**：
```typescript
interface FileAttachment {
  attachmentId: number;  // 必填：附件 ID（新建时设为 0）
  name: string;          // 必填：文件名
  url: string;           // 必填：文件 URL
  size?: number;         // 可选：文件大小（字节）
  width?: number;        // 可选：图片宽度
  height?: number;       // 可选：图片高度
  mimeType?: string;     // 可选：MIME 类型
}
```

**示例**：

```json
// 单个附件
[[
  JSON.stringify({
    attachmentId: 0,
    name: "logo.png",
    url: "<文件URL>",
    size: 6105,
    width: 300,
    height: 300,
    mimeType: "image/png"
  })
]]

// 多个附件
[[
  [
    JSON.stringify({
      attachmentId: 0,
      name: "file1.png",
      url: "<文件URL1>",
      size: 6105,
      mimeType: "image/png"
    }),
    JSON.stringify({
      attachmentId: 0,
      name: "file2.jpg",
      url: "<文件URL2>",
      size: 7475,
      mimeType: "image/jpeg"
    })
  ]
]]

// 最简格式（仅必填字段）
[[
  JSON.stringify({
    attachmentId: 0,
    name: "document.pdf",
    url: "<文件URL>"
  })
]]
```

**⚠️ 重要提示**：
- 必须使用 `JSON.stringify()` 将附件对象序列化为字符串
- `attachmentId`、`name`、`url` 三个字段必填
- 新建附件时 `attachmentId` 设为 0
- 其他字段可选，但建议提供以获得更好的展示效果

**CLI 示例**：
```bash
# 添加单个附件
oa-skills citadel-database addData \
  --tableId "456789" \
  --columnIds "1,2" \
  --data '[[
    "任务A",
    JSON.stringify({
      attachmentId: 0,
      name: "logo.png",
      url: "<文件URL>",
      mimeType: "image/png"
    })
  ]]'

# 添加多个附件
oa-skills citadel-database addData \
  --tableId "456789" \
  --columnIds "3" \
  --data '[[
    [
      JSON.stringify({attachmentId: 0, name: "file1.png", url: "<文件URL1>"}),
      JSON.stringify({attachmentId: 0, name: "file2.jpg", url: "<文件URL2>"})
    ]
  ]]'
```

#### 7. 日期列 (columnType: 7)

> ✅ **推荐直接传日期字符串**：CLI 内部自动按本地时区解析，无需手动计算时间戳。

```json
// ✅ 推荐：日期字符串，CLI 自动按本地时区转换
[["2026-04-27"]]             // 日期
[["2026-04-27T09:00"]]       // 日期+时间
[["2026-04-27T09:00:00+08:00"]]  // 带显式时区

// ✅ 兼容：毫秒时间戳（如传数字必须由代码计算，禁止手写）
[[1745712000000]]

// 空日期
[[0]]
```

#### 8. 货币列 (columnType: 8)

```json
[[100.50]]          // 金额（数值）
[[0]]               // 零
[[-50.25]]          // 负数（退款等场景）
```

## 查询响应格式

### QueryTableDataResponse

```typescript
{
  rows: [
    {
      rowId: 184484716,              // 行 ID
      cellData: [                     // 单元格数据数组
        {
          colId: 1,                   // 列 ID
          textCellValue: [            // 文本列数据
            { type: "text", value: "任务A" }
          ]
        },
        {
          colId: 2,
          numberCellValue: 100        // 数字列数据
        },
        {
          colId: 3,
          selectCellValue: "进行中"   // 单选列数据
        }
      ],
      createdBy: 2015738,             // 创建人 empId
      createdTime: 1773884148000,     // 创建时间: 2026-03-19
      lastModifiedBy: 2015738,        // 最后修改人 empId
      lastModifiedTime: 1773884148000 // 最后修改时间: 2026-03-19
    }
  ],
  total: 1                            // 总行数
}
```

### TableMetaResponse

```typescript
{
  columns: [
    {
      colId: 1,                       // 列 ID
      columnName: "任务名称",         // 列名
      columnType: 1,                  // 列类型
      selectOptions?: string[]        // 单选/多选的选项列表（可选）
    }
  ]
}
```

## 筛选条件格式 (FilterConfig)

```typescript
{
  conjunction: "and" | "or",          // 条件连接方式
  conditions: [
    {
      columnId: 1,                      // 列 ID
      operator: "==",                 // 操作符
      filterValue: ["值"]             // 筛选值（始终为 string[]）
    }
  ],
  children: [                           // 可选：继续嵌套一层筛选组
    {
      conjunction: "or",
      conditions: [
        {
          columnId: 2,
          operator: ">",
          filterValue: ["100"]
        }
      ]
    }
  ]
}
```

### 支持的操作符

| 操作符 | 说明 |
|---|---|
| `>` | 大于 |
| `>=` | 大于等于 |
| `<` | 小于 |
| `<=` | 小于等于 |
| `==` | 等于 |
| `!=` | 不等于 |
| `isnull` | 为空 |
| `notnull` | 不为空 |
| `contains` | 包含 |
| `notcontains` | 不包含 |

**注意：并不是所有列类型都支持所有操作符，必须按列类型选择。**

| 列类型 | 支持的操作符 | `filterValue` 校验 |
|---|---|---|
| 文本 | `==` `!=` `contains` `notcontains` `isnull` `notnull` | 最多 1 个元素 |
| 数字 / 货币 | `==` `!=` `>` `>=` `<` `<=` `isnull` `notnull` | 最多 1 个元素；若有值需可转成 float |
| 单选 / 多选 | `==` `!=` `contains` `notcontains` `isnull` `notnull` | 可多个元素 |
| 人员 / 创建人 / 修改人 | `==` `!=` `contains` `notcontains` `isnull` `notnull` | 可多个元素；所有值都需可转成 int |
| 附件 | `isnull` `notnull` | 不消费 `filterValue`，传 `[]` |
| 日期 / 创建时间 / 修改时间 | `==` `!=` `>` `<` `isnull` `notnull` | 最多 1 个元素；需符合接口支持的日期格式 |
| 公式 | `==` `!=` `>` `>=` `<` `<=` `contains` `notcontains` `isnull` `notnull` | 最多 1 个元素 |

### 筛选示例

```bash
# 1. 单条件筛选（状态等于"进行中"）
--filter '{"conjunction":"and","conditions":[{"columnId":3,"operator":"==","filterValue":["进行中"]}]}'

# 2. 多条件筛选（AND）
--filter '{"conjunction":"and","conditions":[
  {"columnId":3,"operator":"==","filterValue":["进行中"]},
  {"columnId":2,"operator":">","filterValue":["50"]}
]}'

# 3. 多条件筛选（OR）
--filter '{"conjunction":"or","conditions":[
  {"columnId":3,"operator":"==","filterValue":["待处理"]},
  {"columnId":3,"operator":"==","filterValue":["进行中"]}
]}'

# 4. 文本包含筛选
--filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"contains","filterValue":["项目"]}]}'

# 5. 日期范围筛选（日期列使用 > / <，值传字符串）
--filter '{"conjunction":"and","conditions":[
  {"columnId":7,"operator":">","filterValue":["2025-06-01"]},
  {"columnId":7,"operator":"<","filterValue":["2025-07-01"]}
]}'

# 6. 空值筛选（isnull / notnull 必须传空数组）
--filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"isnull","filterValue":[]}]}'

# 7. 非空筛选
--filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"notnull","filterValue":[]}]}'

# 8. 不包含筛选
--filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"notcontains","filterValue":["项目"]}]}'

# 9. 嵌套一层 children
--filter '{"conjunction":"and","conditions":[{"columnId":1,"operator":"!=","filterValue":["哈哈1"]}],"children":[{"conjunction":"or","conditions":[{"columnId":2,"operator":">","filterValue":["123"]},{"columnId":3,"operator":"notnull","filterValue":[]}]}]}'
```

## 排序配置格式 (SortConfig)

```typescript
// ✅ 正确格式
[{ columnId: 2, desc: true }]

// ❌ 错误格式（不存在 order 字段）
[{ columnId: 2, order: "desc" }]   // 无效，服务端会忽略
```

```typescript
[
  {
    columnId: 2,          // 列 ID
    desc: true            // boolean，不是字符串 "desc"/"asc"
  }
]
```

### 排序示例

```bash
# 1. 单列排序（按进度降序）
--sort '[{"columnId":4,"desc":true}]'

# 2. 多列排序（先按状态升序，再按进度降序）
--sort '[{"columnId":3,"desc":false},{"columnId":4,"desc":true}]'
```

## 常见错误和解决方案

### 1. 列类型不匹配

**错误**：将字符串传给数字列
```json
// ❌ 错误
[["100"]]  // 数字列接收字符串

// ✅ 正确
[[100]]    // 数字列接收数字
```

### 2. empId 类型错误

**错误**：empId 使用字符串类型
```json
// ❌ 错误（在富文本中）
{"type":"mention","value":"@张三","empId":"2015739"}

// ✅ 正确
{"type":"mention","value":"@张三","empId":2015739}
```

### 3. 富文本嵌套层级

**错误**：富文本数据嵌套层级错误
```json
// ❌ 错误（缺少外层数组）
{"type":"text","value":"文本"}

// ✅ 正确
[{"type":"text","value":"文本"}]
```

### 4. 二维数组结构

**错误**：一维数组而非二维数组
```json
// ❌ 错误
["值1", "值2"]

// ✅ 正确（单行数据也要用二维数组）
[["值1", "值2"]]
```

### 5. 日期格式

**错误**：使用非标准格式的日期字符串
```json
// ❌ 错误：新式日期格式不支持
[["2026/04/27"]]
[["27-04-2026"]]

// ✅ 正确：直接传标准日期字符串，CLI 自动按本地时区转换
[["2026-04-27"]]
[["2026-04-27T09:00"]]
```

### 6. 手写时间戳导致年份错误

**错误**：凯记忆或估算手写毫秒时间戳，导致年份偏差
```bash
# ❌ 错误：LLM 从训练数据中复用历史年份时间戳，導致年份错误
# 手写 1745683200000 → 对应 2025-04-27，而非 2026-04-27

# ✅ 正确：直接传日期字符串，CLI 自动处理，彻底避免此问题
--data '[["2026-04-27"]]'

# ⚠️ 若必须传数字时间戳，则须用代码计算，禁止手写
node -e "console.log(new Date('2026-04-27').getTime())"
# → 1745712000000
```

> ⚠️ **关键风险（东传数字时）**：手写的错误时间戳是合法的 13 位数字，API 不会报错，错误会被静默写入。推荐优先使用字符串格式彻底避免。

### 7. 时区陷阱

**原因**：`new Date("YYYY-MM-DD")` 被 V8 按 UTC 解析，结果比本地时间少8 小时，在 UI 上会显示为前一天
```bash
# ❌ 此方式将 "2026-04-27" 按 UTC 解析，在本地时区 UI 上会显示为 2026-04-26
new Date('2026-04-27').getTime()

# ✅ 最简方案：传日期字符串给 CLI，内部自动按本地时间解析
--data '[["2026-04-27"]]'

# ⚠️ 若必须手动计算数字时间戳：用空格替换 T（V8 对空格分隔格式按本地时间解析）
node -e "console.log(new Date('2026-04-27 00:00:00').getTime())"
# → 1745683200000（本地时间的 2026-04-27 00:00:00）
```

## 数据转换工具函数

### JavaScript/TypeScript

```typescript
// 日期转时间戳
function dateToTimestamp(dateStr: string): number {
  return new Date(dateStr).getTime();
}

// 字符串转富文本
function textToRichText(text: string): IRichTextNode[] {
  return [{ type: "text", value: text }];
}

// 创建超链接富文本
function createLink(text: string, url: string): IRichTextNode[] {
  return [
    { type: "text", value: "查看" },
    { type: "link", value: text, link: url }
  ];
}

// empId 数组转换
function parseEmpIds(input: string | number | (string | number)[]): number[] {
  if (Array.isArray(input)) {
    return input.map(id => typeof id === 'string' ? parseInt(id) : id);
  }
  return [typeof input === 'string' ? parseInt(input) : input];
}
```

### Bash

```bash
# 获取当前时间戳（毫秒）
timestamp=$(date +%s)000

# 格式化 JSON 数据
data=$(cat <<EOF
[
  ["项目A", "张三", "进行中", 75],
  ["项目B", "李四", "待处理", 0]
]
EOF
)

# 转义 JSON 用于命令行
escaped_data=$(echo "$data" | jq -c .)
```

## 批量操作模式

### 批量新增

```bash
# 准备数据文件 data.json
cat > data.json <<EOF
[
  ["项目A", "张三", "进行中", 75, 1710000000000],   // 日期: 2024-03-09
  ["项目B", "李四", "待处理", 0, 1710086400000],    // 日期: 2024-03-10
  ["项目C", "王五", "已完成", 100, 1709827200000]   // 日期: 2024-03-07
]
EOF

# 批量新增
oa-skills citadel-database addData \
  --tableId "2750248577" \
  --columnIds "1,2,3,4,5" \
  --data "$(cat data.json)"
```

### 批量更新

```bash
# 1. 查询需要更新的行
oa-skills citadel-database queryTableData \
  --tableId "2750248577" \
  --filter '{"conjunction":"and","conditions":[{"columnId":3,"operator":"==","filterValue":["待处理"]}]}' \
  --raw > rows_to_update.json

# 2. 提取 rowIds（使用 jq）
rowIds=$(jq -r '.rows[].rowId' rows_to_update.json | tr '\n' ',' | sed 's/,$//')

# 3. 批量更新状态
oa-skills citadel-database updateData \
  --tableId "2750248577" \
  --rowIds "$rowIds" \
  --columnIds "3" \
  --data '[["进行中"]]'  # 所有行都更新为"进行中"
```

## API 响应示例

### 成功响应

```json
{
  "success": true,
  "stepVersion": 5
}
```

### 错误响应

```json
{
  "code": 400,
  "message": "列ID 999 不存在于表格元数据中。可用的列ID: 1, 2, 3, 4, 5"
}
```

### 数据查询响应（完整示例）

```json
{
  "rows": [
    {
      "rowId": 184484716,
      "cellData": [
        {
          "colId": 1,
          "textCellValue": [
            { "type": "text", "value": "查看" },
            { "type": "link", "value": "项目文档", "link": "https://km.sankuai.com/page/123" }
          ]
        },
        {
          "colId": 2,
          "textCellValue": [
            { "type": "mention", "value": "@张三", "empId": 2015739 }
          ]
        },
        {
          "colId": 3,
          "selectCellValue": "进行中"
        },
        {
          "colId": 4,
          "numberCellValue": 75
        },
        {
          "colId": 5,
          "dateCellValue": 1710000000000  // 2024-03-09
        }
      ],
      "createdBy": 2015738,
      "createdTime": 1773884148000,     // 2026-03-19
      "lastModifiedBy": 2015738,
      "lastModifiedTime": 1773884148000  // 2026-03-19
    }
  ],
  "total": 1,
  "pageToken": "next_page_token_here"
}
```

## 公式语法速查

> 🚨 **生成任何公式前必须满足的三条硬性约束（违反必出错，无例外）**
>
> | # | ❌ 禁止 | ✅ 正确 |
> |---|--------|--------|
> | 1 | 使用 `TEXT()`、`VLOOKUP()`、`DATEDIF()`、`EDATE()`、`NOW()`、`CONCAT()` 等 Excel/Google Sheets 函数 | **只能使用下方「完整函数表」中列出的函数**；白名单是封闭集，不在其中的函数在本系统中不存在，不要从 Excel/Sheets 经验推断 |
> | 2 | `[#1] == "值"` 或 `[#1] === "值"`（双/三等号） | `[#1] = "值"`（**等于判断只写单个 `=`**，`==` 是语法错误，会导致公式执行失败） |
> | 3 | `[5000#2]`、`[$5000#2]` 等合并写法（tableId 和 colId 连写） | `[$5000].[#2]`（**跨表引用必须用 `.` 分开两段**：`$` 后接目标表 tableId，`#` 后接目标列 colId，顺序不可颠倒） |

### 公式列概述

公式列（`columnType: 9`）是一种计算列，**单元格内容由公式自动计算，不可手动写入**。公式表达式存储在列的 `columnConfig.formula` 中。

**关键特性：**
- **字段引用格式：`[#colId]`**（`#` 加列的数字 colId，通过 `getTableMeta` 获取）；**不支持 `[列名]` 格式**
- **跨表引用语法：`[$表ID].[#列ID]`**，可引用同一 contentId 下其他数据表的整列数据
- 公式计算结果在查询时通过 `textCellValue` 返回（统一为字符串形式）
- 支持引用同一数据表中的其他列（**包括公式列**），跨表场景同样支持引用另一张表的公式列；需避免循环引用
- **`formulaFormat` 控制结果类型**：2=数字、7=日期、8=货币；**结果为文本/字符串时不传此字段**（或省略）

**`formulaFormat` 与 `formatter` 配套规则：**

| 公式结果类型 | formulaFormat | formatter 示例 | 说明 |
|---|---|---|---|
| 文本 / 字符串 | 不传（省略） | 不传 | IF/IFS/拼接等返回字符串的公式 |
| 数字 | `2` | `"0"` / `"0.00"` / `"0,0.00"` | 同数字列 formatter 规则 |
| 日期 | `7` | `"YYYY/MM/DD"` / `"YYYY-MM-DD"` | 同日期列 formatter 规则 |
| 货币 | `8` | `"0,0.00"` | 同货币列 formatter 规则，可配合 currencyCode/currencySymbol |

> ⚠️ **formatter 是类型相关的**：`formulaFormat:2`（数字）时用数字格式串；`formulaFormat:7`（日期）时用日期格式串；两者不能混用。

**CLI 操作：**
```bash
# 新增数字公式列（总价 = 单价 × 数量，formulaFormat:2）
oa-skills citadel-database addTableColumns \
  --tableId <id> \
  --columnMetas '[{"columnName":"总价","columnType":9,"columnConfig":{"formula":"[#101] * [#102]","formulaFormat":2,"formatter":"0,0.00"}}]'

# 新增文本公式列（结果为字符串时，不传 formulaFormat）
oa-skills citadel-database addTableColumns \
  --tableId <id> \
  --columnMetas '[{"columnName":"状态标识","columnType":9,"columnConfig":{"formula":"IF([#103] >= 100, \"✅已完成\", \"🔄进行中\")"}}]'

# 修改已有公式列（推荐：用 --columnConfig 可同时修改 formula/formulaFormat/formatter）
oa-skills citadel-database updateColumnConfig \
  --tableId <id> \
  --columnId <cid> \
  --columnConfig '{"formula":"[#101] * [#102] * (1 - IFBLANK([#103], 0))","formulaFormat":2,"formatter":"0.00"}'
```

---

### 运算符表

| 符号类型 | 运算符 | 说明 | 示例 |
|----------|--------|------|------|
| 数值运算 | `+` | 加法 | `[#101] + [#102]` |
| 数值运算 | `-` | 减法 | `[#101] - [#102]` |
| 数值运算 | `*` | 乘法 | `[#101] * [#102]` |
| 数值运算 | `/` | 除法 | `[#101] / [#102]` |
| 文本拼接 | `&` | 将两侧值转为字符串并拼接 | `[#103] & "-" & [#104]` |
| 比较 | `>` / `>=` | 大于 / 大于等于 | `[#105] >= 90` |
| 比较 | `<` / `<=` | 小于 / 小于等于 | `[#106] < 10` |
| 比较 | `=` | 等于（**注意：只写 `=`，禁止写 `==`**） | `[#107] = "完成"` |
| 比较 | `!=` | 不等于（**禁止写 `!==`**） | `[#108] != "已删除"` |
| 逻辑 | `&&` | 与（AND） | `[#101] > 0 && [#102] > 0` |
| 逻辑 | `\|\|` | 或（OR） | `[#101] = "是" \|\| [#102] = "是"` |

> ⚠️ 单选/多选/人员列参与字符串运算时需加 `& ""` 转为字符串：`[#107] & "" = "进行中"`
>
> ⚠️ **等于判断符只能用 `=`，严禁写 `==`**（`==` 不是有效运算符，会导致语法错误）。`!=` 表示不等于，同样无 `!==`

---

### 完整函数表

#### 逻辑函数

| 函数 | 参数说明 | 示例 |
|------|----------|------|
| `AND(条件1, 条件2, ...)` | 所有条件均为 TRUE 时返回 TRUE | `AND([#101] > 0, [#102] > 0)` |
| `OR(条件1, 条件2, ...)` | 任一条件为 TRUE 时返回 TRUE | `OR([#103] = "完成", [#103] = "关闭")` |
| `NOT(条件)` | 逻辑取反 | `NOT([#104] = "是")` |
| `IF(条件, 真値, 假値)` | 条件判断 | `IF([#105] >= 60, "及格", "不及格")` |
| `IFS(条件1, 值1, 条件2, 值2, ...)` | 多条件分支 | `IFS([#105] >= 90, "优", [#105] >= 60, "良", "差")` |
| `SWITCH(表达式, 值1, 结果1, ...)` | 多值匹配分支 | `SWITCH([#106], "P5", "初级", "P6", "中级", "高级")` |
| `IFBLANK(値, 默认値)` | 空值判断，空时返回默认值 | `IFBLANK([#107], "无")` |
| `IFERROR(値, 错误默认)` | 错误判断，出错时返回默认值 | `IFERROR([#108] / [#109], 0)` |
| `ISBLANK(値)` | 是否为空，返回 true/false | `IF(ISBLANK([#107]), "空", [#107])` |
| `ISERROR(値)` | 是否出错，返回 true/false | `IF(ISERROR([#108]/[#109]), "错误", [#108]/[#109])` |
| `TRUE()` | 返回逻辑真 | `IF(TRUE(), "yes", "no")` |
| `FALSE()` | 返回逻辑假 | `AND(FALSE(), TRUE())` |

#### 数字函数

| 函数 | 参数说明 | 示例 |
|------|----------|------|
| `ROUND(数値, 位数)` | 四舍五入到指定小数位 | `ROUND([#101] * [#102], 2)` |
| `ROUNDUP(数値, 位数)` | 向上舍入 | `ROUNDUP([#103], 0)` |
| `ROUNDDOWN(数値, 位数)` | 向下舍入（截断） | `ROUNDDOWN([#104] * 100, 0)` |
| `ABS(数値)` | 绝对值 | `ABS([#105])` |
| `POWER(底数, 指数)` | 幂运算 | `POWER([#106], 2)` |
| `VALUE(文本)` | 文本转数字（从左起第一个数） | `VALUE([#107] & "")` |
| `SUM(値1, 値2, ...)` | 求和 | `SUM([#101], [#102], [#103], [#104])` |
| `AVERAGE(値1, 値2, ...)` | 平均值 | `AVERAGE([#101], [#102], [#103])` |
| `MAX(値1, 値2, ...)` | 最大值 | `MAX([#101], [#102])` |
| `MIN(値1, 値2, ...)` | 最小值 | `MIN([#101], [#102])` |
| `COUNTA(値1, ...)` | 非空值计数 | `COUNTA(LIST([#101], [#102], [#103]))` |

#### 日期函数

| 函数 | 参数说明 | 示例 |
|------|----------|------|
| `TODAY()` | 返回今天的日期 | `DAYS([#101], TODAY())` |
| `DATE(年, 月, 日)` | 构造日期 | `DATE(2026, 12, 31)` |
| `DAYS(结束日期, 起始日期)` | 两日期之间的天数（**剩余天数用 `DAYS([#截止日期], TODAY())`，禁用 `DATEDIF()`**） | `DAYS([#101], [#102])` |
| `YEAR(日期)` | 提取年份 | `YEAR([#103])` |
| `MONTH(日期)` | 提取月份 | `MONTH([#101])` |
| `DAY(日期)` | 提取日 | `DAY([#101])` |
| `HOUR(时间)` | 提取小时 | `HOUR([#104])` |
| `MINUTE(时间)` | 提取分钟 | `MINUTE([#104])` |
| `SECOND(时间)` | 提取秒钟 | `SECOND([#104])` |
| `WEEKDAY(日期, [类型])` | 星期几（1=周日起，2=周一起） | `WEEKDAY([#101], 2)` |

#### 文本函数

| 函数 | 参数说明 | 示例 |
|------|----------|------|
| `LEFT(文本, 字符数)` | 从左取 N 个字符 | `LEFT([#101], 20)` |
| `RIGHT(文本, 字符数)` | 从右取 N 个字符 | `RIGHT([#102], 4)` |
| `MID(文本, 起始, 长度)` | 从指定位置取子串 | `MID([#103], 7, 8)` |
| `LEN(文本)` | 字符串长度 | `LEN([#104])` |
| `TRIM(文本)` | 去除前后空格 | `TRIM([#105])` |
| `UPPER(文本)` | 转大写 | `UPPER([#106])` |
| `LOWER(文本)` | 转小写 | `LOWER([#107])` |
| `CONCATENATE(串1, 串2, ...)` | 拼接多个字符串 | `CONCATENATE([#108], "-", [#109])` |
| `FIND(查找值, 范围, [起始])` | 查找位置（不存在返回 -1） | `FIND("@", [#110])` |
| `REPLACE(文本, 位置, 长度, 新文本)` | 替换指定位置内容 | `REPLACE([#111], 4, 4, "****")` |
| `SUBSTITUTE(文本, 被替换, 替换, [第N个])` | 替换字符串内容 | `SUBSTITUTE([#104], "旧", "新")` |
| `CONTAINTEXT(文本, 查找文本)` | 是否包含（返回 true/false） | `CONTAINTEXT([#112], "紧急")` |

#### 集合/统计函数

| 函数 | 参数说明 | 示例 |
|------|----------|------|
| `LIST(値1, 値2, ...)` | 构造数组 | `SUM(LIST([#101], [#102], [#103]))` |
| `ARRAYJOIN(数组, 分隔符)` | 数组转字符串 | `ARRAYJOIN(LIST([#101], [#102]), ", ")` |
| `UNIQUE(値1, 値2, ...)` | 去重 | `UNIQUE([#103], [#104])` |
| `LISTCOMBINE(字段1, 字段2, ...)` | 合并多组字段/列表 | `LISTCOMBINE([#101], [#102], LIST(1,2))` |
| `CONTAIN(范围, 値)` | 是否包含（精确匹配） | `CONTAIN(LIST("A","B","C"), [#105])` |
| `SUMIF(范围, 条件)` | 条件求和 | `SUMIF(LIST([#101],[#102],[#103]), CurrentValue > 0)` |
| `COUNTIF(范围, 条件)` | 条件计数 | `COUNTIF(LIST([#101],[#102],[#103]), CurrentValue != "")` |
| `数据范围.FILTER(条件)` | 筛选数组 | `LIST(1,2,3,4).FILTER(CurrentValue > 2)` |
| `LOOKUP(搜索值, 匹配字段, 结果字段)` | 查表 | `LOOKUP([#105], LIST(1,2,3), LIST("a","b","c"))` |

---

### CLI 快速操作示例

```bash
# 1. 先查表格列结构（必须先做，获取各列 colId 用于公式引用）
oa-skills citadel-database getTableMeta --tableId 123456789
# 假设返回：单价列 colId=101，数量列 colId=102，进度列 colId=103，折扣列 colId=104

# 2a. 新增公式列（总价 = 单价 × 数量）
# ⚠️ 字段引用必须用 [#colId] 格式，不支持列名
oa-skills citadel-database addTableColumns \
  --tableId 123456789 \
  --columnMetas '[{"columnName":"总价","columnType":9,"columnConfig":{"formula":"[#101] * [#102]","formulaFormat":2,"formatter":"0,0.00"}}]'

# 2b. 新增复杂公式列（多条件状态标识，结果为文本时不传 formulaFormat）
# IFS 的最后一个 else 分支必须用 TRUE() 作条件
oa-skills citadel-database addTableColumns \
  --tableId 123456789 \
  --columnMetas '[{"columnName":"状态标识","columnType":9,"columnConfig":{"formula":"IF([#103] >= 100, \"✅已完成\", IF([#103] > 0, \"🔄进行中\", \"⬜未开始\"))"}}]'

# 3a. 修改已有公式列（推荐：用 --columnConfig 可同时修改 formula/formulaFormat/formatter）
oa-skills citadel-database updateColumnConfig \
  --tableId 123456789 \
  --columnId 5 \
  --columnConfig '{"formula":"[#101] * [#102] * (1 - IFBLANK([#104], 0))","formulaFormat":2,"formatter":"0.00"}'

# 3b. 修改已有公式列（兼容旧写法：--formula 只传表达式，等价于 --columnConfig '{"formula":"..."}'）
oa-skills citadel-database updateColumnConfig \
  --tableId 123456789 \
  --columnId 5 \
  --formula "[#101] * [#102] * (1 - IFBLANK([#104], 0))"
```

---

### 常见公式模板

> 💡 以下模板中的 `[#101]`、`[#102]` 等均为示例 colId，**实际使用时请替换为 `getTableMeta` 返回的真实列 colId**。字段引用只支持 `[#colId]` 格式，不支持列名。

```
# 计算总价（数字 × 数字，单价列colId=101，数量列colId=102）
# formulaFormat: 2，formatter: "0,0.00"
[#101] * [#102]

# 计算含税总价（保留2位小数）
# formulaFormat: 2，formatter: "0,0.00"
ROUND([#101] * [#102] * 1.13, 2)

# 剩余天数（截止日期列colId=103，结果为数字，formulaFormat: 2，formatter: "0"）
DAYS([#103], TODAY())

# 任务状态（多级判断，进度列colId=104，结果为文本，不传 formulaFormat）
# IFS 最后一个 else 分支必须用 TRUE() 作条件
IFS([#104] >= 100, "✅ 已完成", [#104] > 0, "🔄 进行中", TRUE(), "⬜ 未开始")

# 分数等级（总分列colId=105，结果为文本，不传 formulaFormat）
# IFS 最后一个 else 分支必须用 TRUE() 作条件
IFS([#105] >= 90, "A", [#105] >= 75, "B", [#105] >= 60, "C", TRUE(), "不及格")

# 人员 + 备注拼接（负责人列colId=106，备注列colId=107；单选/人员列需 & "" 转字符串）
# 结果为文本，不传 formulaFormat
[#106] & "" & IF(ISBLANK([#107]), "", " (" & [#107] & ")")

# 百分比展示（完成数量列colId=108，总数量列colId=109，结果为文本，不传 formulaFormat）
ROUND([#108] / [#109] * 100, 1) & "%"

# 手机号脱敏（手机列colId=110，结果为文本，不传 formulaFormat）
REPLACE([#110], 4, 4, "****")

# 日期转 YYYYMM（无 TEXT 函数，用数学拼接，创建时间列colId=111）
# formulaFormat: 2，formatter: "0"
YEAR([#111]) * 100 + MONTH([#111])

# 日期取年月显示（YYYY/MM 字符串，结果为文本，不传 formulaFormat）
YEAR([#111]) & "/" & MONTH([#111])

# 计算工作完成率（防除零，完成列colId=112，总数列colId=113，结果为文本，不传 formulaFormat）
IFERROR(ROUND([#112] / [#113] * 100, 1) & "%", "0%")

# 多选标签包含判断（标签列colId=114；& "" 转字符串后用 CONTAINTEXT，结果为文本，不传 formulaFormat）
IF(CONTAINTEXT([#114] & "", "紧急"), "🔴 紧急", "🟢 正常")
```

> ⚠️ **注意事项**
> - **字段引用只支持 `[#colId]` 格式**（`#` 加列的数字 colId），`[列名]` 格式不支持
> - `colId` 通过 `getTableMeta` 获取，是一个数字，不是列名字符串
> - 单选/多选/人员列参与字符串运算时需加 `& ""` 转为字符串
> - 公式列单元格不可写入数据；若误操作写入，API 会报错
> - 公式列**支持引用其他公式列**（同表或跨表均可）；但禁止循环引用（A→B→A 会报错）
> - **`IFS` 的最后一个 else 分支必须用 `TRUE(), <默认值>` 格式**，不能直接放裸值
> - **本系统函数是封闭白名单**：上方表格是全部可用函数，不在表中的函数不存在。不要从 Excel/Sheets 经验推测函数名，如需替代写法，查 SKILL.md 的「需求→正确写法对照表」
> - **比较运算符用单等号 `=`（不是 `==`）**，不等于用 `!=`（不是 `!==`）

---

### 跨表公式

**跨表引用语法：`[$表ID].[#列ID]`**

- 引用同一 contentId（文档/空间）下其他数据表的**整列数据**
- `$` 后接目标表的 `tableId`（数字），`#` 后接目标列的 `colId`（数字）
- 常与 `LOOKUP`、`FILTER`、`COUNTIF`、`SUMIF` 等集合函数配合使用

**使用前必须先收集的信息：**

```bash
# Step 1：列出同一 contentId 下的所有表，确认目标表和当前表在同一文档中
oa-skills citadel-database listTables --contentId <contentId>
# 记录：目标表名称对应的 tableId（如 5000）

# Step 2：获取目标表的列结构
oa-skills citadel-database getTableMeta --tableId <目标表tableId>
# 记录：用于匹配的列 colId 和用于取值的列 colId

# Step 3：获取当前表的列结构（如尚未获取）
oa-skills citadel-database getTableMeta --tableId <当前表tableId>
# 记录：用于匹配的列 colId
```

> ⚠️ **跨表约束**：跨表公式只能引用**同一 contentId** 下的表；`$` 后的表 ID 必须通过 `listTables` 获取，不能手写或猜测。
> 💡 **数字范围区分**：`tableId` 是较长数字（通常 10 位，如 `2750248577`）；`colId` 是较短数字（通常 1-3 位，如 `101`）。`[$表ID]` 后接 `tableId`，`[#列ID]` 后接 `colId`，注意不要颠倒。

**跨表公式模板（tableId 和 colId 均需先用上述步骤获取）：**

```
# 从"商品信息"表（tableId=5000）中，按当前行的商品ID列（列ID=201）查出对应单价列（列ID=202）
LOOKUP([#201], [$5000].[#201], [$5000].[#202])

# 统计"订单"表（tableId=6000）中产品名称列（列ID=301）与当前行匹配的行数
[$6000].[#301].COUNTIF(CurrentValue = [#301])

# 对"明细"表（tableId=7000）金额列（列ID=401）按项目 ID列（列ID=402）求和
[$7000].[#401].FILTER(LOOKUP(CurrentValue, [$7000].[#401], [$7000].[#402]) = [#402]).SUMIF(CurrentValue > 0)

# 获取"员工"表（tableId=8000）中整列手机号（列ID=501）
[$8000].[#501]
```

> 💡 **跨表使用建议**
> - 跨表公式中 `$` 加的是目标表的 tableId，`#` 加的是目标列的 colId
> - 目标 tableId 必须通过 `listTables` 获取，目标列 colId 通过 `getTableMeta` 获取
> - 对大量数据的跨表聚合（SUMIF、COUNTIF）可能影响计算性能，建议在数据量较小时使用
