# 视图管理

视图命令完整参数说明。

# 目录

- [视图查询规则（链接含 viewId 时）](#视图查询规则链接含-viewid-时)
- [queryTableViewList](#querytableviewlist)
- [addTableView](#addtableview)
  - [ViewConfig 类型说明](#viewconfig-类型说明)
  - [ViewConfig.filter（FILTER_CONFIG）](#viewconfigfilterfilter_config)
  - [ViewConfig.conditionColor（ConditionColorConfig[]）](#viewconfigconditioncolorconditioncolorconfig)
  - [ViewConfig.colInfos（Record\<number, ModelColInfo\>）](#viewconfigcolinfosrecordnumber-modelcolinfo)
  - [ViewConfig.notice（INotice）](#viewconfignoticeinotice)
- [updateTableView](#updatetableview)
- [deleteTableView](#deletetableview)

# 视图查询规则（链接含 viewId 时）

若用户提供的多维表格链接中包含 `?view=<viewId>` 参数，且用户意图明确指向该视图（如"查询这个视图的数据"、"看看这个视图"、"查这个视图"），执行 `queryTableData` 时**必须传入 `--viewId <id>`**。**禁止**在此场景下忽略链接中的 `viewId` 而执行无视图的全量查询。

> ⚠️ `--viewId` 仅在**未传** `--columnIds`、`--filter`、`--sort` 时生效。一旦传入任意一个，`--viewId` 自动忽略。

# queryTableViewList

查询数据表下的所有视图列表。

| 参数        | 类型   | 必填 | 默认值 | 说明    |
| ----------- | ------ | ---- | ------ | ------- |
| `--tableId` | string | ✅   | —      | 表格 ID |

```bash
oa-skills citadel-database queryTableViewList \
  --tableId "1234567890"
```

**输出**：视图列表，包含每个视图的 `viewId`、`name`、`type`、`config`。

---

# addTableView

新增视图，支持表格视图、表单视图、甘特图视图。

| 参数         | 类型   | 必填 | 默认值 | 说明                                                |
| ------------ | ------ | ---- | ------ | --------------------------------------------------- |
| `--tableId`  | string | ✅   | —      | 表格 ID                                             |
| `--viewName` | string | ✅   | —      | 视图名称                                            |
| `--viewType` | string | ✅   | —      | 视图类型：`TableModel` / `FormModel` / `GanttModel` |
| `--config`   | JSON   | ❌   | —      | 视图配置（见下方 ViewConfig 说明）                  |

## ViewConfig 类型说明

```typescript
{
  name?: string;                              // 视图名称
  groups?: Array<{ id: number; desc: boolean }>;  // 分组配置
  sorts?: Array<{ id: number; desc: boolean }>;   // 排序配置（desc=true 降序）
  lineHeight?: number;                        // 行高
  fixedColumn?: number;                       // 固定列数（从左起冻结的列数）
  columns?: number[];                         // 显示列 ID 列表（控制列可见性和顺序）
  filter?: FILTER_CONFIG;                     // 筛选配置（⚠️ 元组格式，见下方详细说明）
  conditionColor?: ConditionColorConfig[];    // 条件颜色规则（见下方详细说明）
  colInfos?: Record<number, ModelColInfo>;    // 列级配置，key 为列 ID（见下方详细说明）
  notice?: INotice;                           // 视图公告栏（见下方详细说明）
  description?: IRichTextNode[];              // 视图描述（富文本节点数组）
  timeBarStartDateId?: number;                // 甘特图专用：开始日期列 ID
  timeBarEndDateId?: number;                  // 甘特图专用：结束日期列 ID
}
```

---

## ViewConfig.filter（FILTER_CONFIG）

> ⚠️ **注意**：`ViewConfig.filter` 使用**元组（Tuple）格式**，与 `queryTableData --filter` 的对象格式**完全不同**，请勿混用。

**格式定义：**

```
FILTER_CONFIG = [conjunction, conditions]
```

| 位置 | 字段          | 类型              | 说明                                   |
| ---- | ------------- | ----------------- | -------------------------------------- |
| 0    | `conjunction` | `"and"` \| `"or"` | conditions 之间的逻辑关系              |
| 1    | `conditions`  | Array             | 条件数组，每个元素是叶子条件或嵌套子组 |

**叶子条件（FILTER_CONDITION_LEAF）格式：**

```
[operator, columnId, filterValue, columnType]
```

| 位置 | 字段          | 类型                          | 说明                                   |
| ---- | ------------- | ----------------------------- | -------------------------------------- |
| 0    | `operator`    | string                        | 操作符（见下表）                       |
| 1    | `columnId`    | number                        | 列 ID                                  |
| 2    | `filterValue` | string \| number \| undefined | 筛选值（类型因列类型而异，见下方说明） |
| 3    | `columnType`  | number                        | 列类型                                 |

**`filterValue` 按列类型的取值规则：**

| 列类型      | columnType | filterValue 类型      | 说明与示例                                                                                |
| ----------- | ---------- | --------------------- | ----------------------------------------------------------------------------------------- |
| 文本        | 1          | `string`              | 将 `IRichTextNode[]` 序列化为字符串后传入。如："[{\"type\":\"text\",\"value\":\"张三\"}]" |
| 数字        | 2          | `number`              | 直接传数值，如 `100`                                                                      |
| 单选        | 3          | `string`              | 将选项 ID 数组序列化为 JSON 字符串，如 `"[123456]"`。可通过 `getTableMeta` 获取选项 ID    |
| 人员        | 4          | `string`              | 将 empId 数组序列化为 JSON 字符串，如 `"[2015738,2015739]"`                               |
| 多选        | 5          | `string`              | 同单选，将选项 ID 数组序列化为 JSON 字符串，如 `"[123456,123457]"`                        |
| 日期        | 7          | `number`              | 毫秒时间戳，如 `1746028800000`                                                            |
| 货币        | 8          | `number`              | 直接传数值，如 `99.99`                                                                    |
| 为空/不为空 | 任意       | `null` \| `undefined` | `isnull`/`notnull` 操作符时传 `null`                                                      |

**操作符枚举：**

| 操作符          | 含义     | 适用列类型                                                       |
| --------------- | -------- | ---------------------------------------------------------------- |
| `"=="`          | 等于     | 文本、数字、单选、日期、人员                                     |
| `"!="`          | 不等于   | 文本、数字、单选、日期、人员                                     |
| `">"`           | 大于     | 数字（columnType=2）、日期（columnType=7）、货币（columnType=8） |
| `">="`          | 大于等于 | 数字、日期、货币                                                 |
| `"<"`           | 小于     | 数字、日期、货币                                                 |
| `"<="`          | 小于等于 | 数字、日期、货币                                                 |
| `"contains"`    | 包含     | 文本（columnType=1）、多选（columnType=5）                       |
| `"notcontains"` | 不包含   | 文本、多选                                                       |
| `"isnull"`      | 为空     | 所有列类型（filterValue 传 `null`）                              |
| `"notnull"`     | 不为空   | 所有列类型（filterValue 传 `null`）                              |

**示例（JSON 格式，用于 --config 的 filter 字段）：**

```json
// 示例1：单条件 — 文本列(id=1)包含"张三"
["and",[["contains",1,"[{\"type\":\"text\",\"value\":\"张三\"}]",1]]]

// 示例2：AND 多条件 — 单选列(id=3)等于"进行中" 且 数字列(id=2)大于100
["and", [
  ["==", 3, "[1]", 3],
  [">", 2, 100, 2]
]]

// 示例3：OR 多条件 — 状态等于"待处理" 或 等于"进行中"
["or", [
  ["==", 3, "[1]", 3],
  ["==", 3, "[2]", 3]
]]

// 示例4：为空判断 — 人员列(id=4)为空
["and", [
  ["isnull", 4, null, 4]
]]

// 示例5：嵌套条件 — (状态=进行中 AND 优先级=高) OR (日期列(id=7) < 某时间戳)
["or", [
  ["and", [
    ["==", 3, "[3]", 3],
    ["==", 5, "[5]", 5]
  ]],
  ["<", 7, 1746028800000, 7]
]]
```

**完整 --config 示例（带 filter 的视图）：**

```bash
# 新增只显示"进行中"状态的过滤视图（单选列 id=3）
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "进行中任务" \
  --viewType "TableModel" \
  --config '{"filter":["and",[["==",3,"[3549643]",3]]],"sorts":[{"id":7,"desc":true}]}'

# 新增"高优先级且未完成"的过滤视图（AND 多条件）
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "高优先级待处理" \
  --viewType "TableModel" \
  --config '{"filter":["and",[["==",5,"[4565425]",5],["!=",3,"[6467945]",3]]]}'
```

---

## ViewConfig.conditionColor（ConditionColorConfig[]）

```typescript
Array<{
  id: number; // 规则 ID（唯一标识，同一视图内不可重复）
  name?: string; // 规则名称（可选，便于识别）
  type: "cell" | "row" | "col" | "header"; // 着色范围
  //   cell   — 仅着色满足条件的单元格
  //   row    — 着色整行
  //   col    — 着色整列（配合 colsFilter 指定列）
  //   header — 仅着色列头
  color: string; // 颜色（十六进制，如 "#FF6B6B"）
  bold?: boolean; // 是否加粗文字（可选）
  colsFilter?: number[]; // 仅对哪些列 ID 应用着色（type=col/cell 时有效）
  rowsFilter?: FILTER_CONFIG; // 触发着色的行筛选条件（格式同上方 filter）
}>;
```

---

## ViewConfig.colInfos（Record\<number, ModelColInfo\>）

`colInfos` 以**列 ID 为 key**，对每一列单独设置显示和交互属性。表格视图中可控制列宽/隐藏/聚合，表单视图中可控制字段标签/说明/必填/输入方式等。

```typescript
{
  [columnId: number]: {
    // ── 表格视图通用 ──
    hidden?: boolean;           // 是否隐藏（true=隐藏）
    aggregate?: AggregateType;  // 聚合方式，枚举值见下方说明
    width?: number;             // 列宽（像素）

    // ── 表单视图专用 ──
    label?: string;             // 表单字段自定义标签（覆盖列名）
    describe?: IRichTextNode[]; // 表单字段说明文字（富文本）
    require?: boolean;          // 表单提交时是否必填
    inputSource?: "ALL" | "ONLY_CAMERA";
                                // 附件列输入来源限制
                                //   ALL         — 允许从相册、文件、相机选择（默认）
                                //   ONLY_CAMERA — 仅允许拍照
    selectType?: "FLAT" | "DROP_DOWN";
                                // 单选/多选列的选择器样式
                                //   FLAT        — 平铺展示所有选项
                                //   DROP_DOWN   — 下拉选择
  }
}
```

**示例：**

```json
// 隐藏列 id=5，设置列 id=2 的宽度和聚合
{ "5": { "hidden": true }, "2": { "width": 120, "aggregate": "sum" } }

// 表单视图：列 id=1 必填 + 自定义标签，列 id=6 仅允许拍照
{ "1": { "require": true, "label": "项目名称（必填）" }, "6": { "inputSource": "ONLY_CAMERA" } }
```

**`aggregate` 枚举值（AggregateType）：**

| 枚举值                | 说明                       | 适用列类型       |
| --------------------- | -------------------------- | ---------------- |
| `""`                  | 不聚合（关闭）             | 所有列           |
| `"count"`             | 总数                       | 所有列           |
| `"empty"`             | 未填写数量                 | 所有列           |
| `"setted"`            | 已填写数量                 | 所有列           |
| `"unique"`            | 唯一值数量                 | 所有列           |
| `"emptyPercent"`      | 未填写占比                 | 所有列           |
| `"settedPercent"`     | 已填写占比                 | 所有列           |
| `"uniquePercent"`     | 唯一值占比                 | 所有列           |
| `"min"`               | 最小值（日期列为最早时间） | 数字、货币、日期 |
| `"max"`               | 最大值（日期列为最晚时间） | 数字、货币、日期 |
| `"sum"`               | 求和                       | 数字、货币       |
| `"sum2"`              | 平方和                     | 数字、货币       |
| `"average"`           | 平均值                     | 数字、货币       |
| `"variance"`          | 方差                       | 数字、货币       |
| `"dateRangeOfDays"`   | 日期范围（天）             | 日期             |
| `"dateRangeOfMonths"` | 日期范围（月）             | 日期             |

---

## ViewConfig.notice（INotice）

`notice` 为视图顶部**公告栏**，展示一段富文本说明，可设置背景色和默认展开状态。

```typescript
{
  content: IRichTextNode[];   // 公告内容（富文本节点数组，格式同 description）
  backgroundColor: string;   // 背景色（十六进制，如 "#FFF9C4"）
  defaultOpen: boolean;      // 进入视图时是否默认展开（true=展开）
}
```

**示例：**

```bash
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "只读视图" \
  --viewType "TableModel" \
  --config '{"notice":{"content":[{"type":"text","value":"⚠️ 本视图仅供只读，请勿修改数据"}],"backgroundColor":"#FFF3CD","defaultOpen":true}}'
```

**示例：**

```bash
# 新增普通表格视图
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "我的视图" \
  --viewType "TableModel"

# 新增带排序和固定列的视图
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "按日期排序" \
  --viewType "TableModel" \
  --config '{"sorts":[{"id":2,"desc":true}],"fixedColumn":1}'

# 新增只显示指定列的视图
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "精简视图" \
  --viewType "TableModel" \
  --config '{"columns":[1,3,5]}'

# 新增表单视图
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "数据收集表单" \
  --viewType "FormModel"

# 新增甘特图视图（需指定开始/结束日期列 ID）
oa-skills citadel-database addTableView \
  --tableId "1234567890" \
  --viewName "项目甘特图" \
  --viewType "GanttModel" \
  --config '{"timeBarStartDateId":3,"timeBarEndDateId":4}'
```

**输出**：成功状态、新视图 ID、版本号。

---

# updateTableView

更新视图的名称或配置，两个可选参数至少提供一个。

| 参数         | 类型   | 必填 | 默认值 | 说明                                          |
| ------------ | ------ | ---- | ------ | --------------------------------------------- |
| `--tableId`  | string | ✅   | —      | 表格 ID                                       |
| `--viewId`   | string | ✅   | —      | 视图 ID                                       |
| `--viewName` | string | ❌   | —      | 新视图名称                                    |
| `--config`   | JSON   | ❌   | —      | 视图配置（结构同 addTableView 的 `--config`） |

> ⚠️ **重要：属性覆盖语义**
>
> `updateTableView` 对 `config` 的更新是**属性级覆盖**：传入 `--config` 中的每个顶层字段会**整体替换**视图中对应的原有值，而未传入的字段保持不变。
>
> 因此，凡是涉及"修改已有配置中的某一条"、"删除配置中的某个条件"、"在已有排序/分组/筛选/colInfos/填色条件 上追加新条件"等操作，**必须先执行 `queryTableViewList` 读取目标视图的当前配置**，在原有值的基础上做修改后再传入，否则会丢失其他已有条件。
>
> **需要先查询的场景举例：**
>
> - 在已有两条排序规则的视图上再加一条排序 → 先取出原有 `sorts`，append 后整体传入
> - 把筛选条件从"状态=待处理"改为"状态=已完成" → 先取出原有 `filter`，替换对应条件后整体传入
> - 隐藏某一列（修改 `colInfos`）同时保留其他列已有的宽度设置 → 先取出原有 `colInfos`，合并后整体传入
> - 删除分组中的某一条规则 → 先取出原有 `groups`，过滤掉目标项后整体传入
>
> **无需先查询的场景：**
>
> - 仅修改视图名称（`--viewName`，不涉及 `config`）
> - 明确要**全量覆盖**某个字段（如清空所有排序、重新设置所有筛选条件）

```bash
# 仅重命名视图（无需先查询）
oa-skills citadel-database updateTableView \
  --tableId "1234567890" \
  --viewId "1000" \
  --viewName "新视图名称"

# 在已有排序上追加新排序条件（必须先查询，避免丢失原有排序）
# 1. 先查询视图列表获取当前 config
oa-skills citadel-database queryTableViewList --tableId "1234567890" --raw
# 2. 取出原有 sorts，append 新条件后整体传入
oa-skills citadel-database updateTableView \
  --tableId "1234567890" \
  --viewId "1000" \
  --config '{"sorts":[{"columnId":2,"desc":true},{"columnId":3,"desc":false}]}'

# 全量覆盖筛选（明确要重置，无需先查询）
oa-skills citadel-database updateTableView \
  --tableId "1234567890" \
  --viewId "1000" \
  --config '{"filter":["and",[["==",1001,"已完成",3]]]}'
```

**输出**：成功状态、版本号。

---

# deleteTableView

删除指定视图。

| 参数        | 类型   | 必填 | 默认值 | 说明    |
| ----------- | ------ | ---- | ------ | ------- |
| `--tableId` | string | ✅   | —      | 表格 ID |
| `--viewId`  | string | ✅   | —      | 视图 ID |

```bash
oa-skills citadel-database deleteTableView \
  --tableId "1234567890" \
  --viewId "1001"
```

**输出**：成功状态、版本号。
