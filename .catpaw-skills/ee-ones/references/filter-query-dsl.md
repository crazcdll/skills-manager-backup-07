# ones-filter-issues 命令 DSL Query 构建指南

> **加载时机**：当 Agent 需要根据用户的自然语言筛选条件，拼接 DSL Query JSON 用于 `ones filter-issues --query` 命令时，读取本文件。

---

## 命令概览

**命令名**: `ones filter-issues` (别名: `ones fi`)

**功能**: 使用 ElasticSearch-like DSL 查询语法筛选 ONES 工作项，支持复杂的多条件组合查询。

**两种使用方式**:

1. **快捷参数模式**（适合简单场景）  
   ```bash
   ones fi -p 51145 --name 关键词 --priority 高,紧急 --state 需求设计中 --assigned zhangsan
   ```

2. **DSL Query 模式**（适合复杂场景，agent 推荐使用）  
   ```bash
   ones fi -p 51145 --query '[
     {"field":"name","type":"MATCH","value":"关键词"},
     {"field":"state","type":"TERMS","valueList":["需求设计中","评审中"]},
     {"field":"assigned","type":"TERM","value":"zhangsan"}
   ]'
   ```

3. **混合模式**（两种方式可同时使用，最终合并为一个 query 数组）  
   ```bash
   ones fi -p 51145 --query '[{"field":"createdAt","type":"TIME_RANGE","gte":1773590400000,"lte":1773676800000}]' \
     --name 关键词 --priority 高
   ```

---

## DSL Query 数据结构

每条筛选条件对应一个 JSON 对象，包含以下字段：

```typescript
{
  field: string;           // 字段名（必填）
  type: string;            // 查询类型（必填）
  value?: any;             // 单值（TERM/MATCH 等使用）
  valueList?: any[];       // 多值（TERMS 使用）
  gte?: number | string;   // 大于等于（RANGE/TIME_RANGE 使用）
  lte?: number | string;   // 小于等于（RANGE/TIME_RANGE 使用）
  gt?: number | string;    // 大于（RANGE 使用）
  lt?: number | string;    // 小于（RANGE 使用）
  group?: number;          // 分组编号（默认 1，同组内 AND，不同组间 OR）
}
```

---

## 查询类型（type）详解

### 1. TERM - 精确匹配（单值）

**用途**: 字段值精确等于某个值

**适用字段**: `assigned`(指派给), `priority`(优先级), `state`(状态), `iterationId`(迭代ID) 等

**示例**:
```json
{"field":"assigned","type":"TERM","value":"liqianlong"}
```

---

### 2. TERMS - 精确匹配（多值，OR 关系）

**用途**: 字段值在指定的多个值中（任意一个）

**适用字段**: `state`, `priority`, `assigned`, `iterationId` 等

**示例**:
```json
{"field":"state","type":"TERMS","valueList":["需求设计中","评审中","开发中"]}
```

**等价于**: state = '需求设计中' OR state = '评审中' OR state = '开发中'

---

### 3. MATCH - 全文搜索（模糊匹配）

**用途**: 文本字段包含关键词（分词后模糊匹配）

**适用字段**: `name`(标题)

**示例**:
```json
{"field":"name","type":"MATCH","value":"搜索优化"}
```

**行为**: 标题中包含"搜索"或"优化"的工作项都会匹配

---

### 4. MATCH_PHRASE - 短语搜索（精确短语）

**用途**: 文本字段包含精确短语（不分词）

**适用字段**: `name`

**示例**:
```json
{"field":"name","type":"MATCH_PHRASE","value":"搜索优化"}
```

**行为**: 标题中必须包含完整的"搜索优化"短语

---

### 5. RANGE - 数值范围查询

**用途**: 数值字段在某个范围内

**适用字段**: `id`(工作项ID), `expectTime`(预计工作量) 等数值字段

**示例**:
```json
{"field":"expectTime","type":"RANGE","gte":1,"lte":10}
```

**范围边界**:
- `gte`: >= (大于等于)
- `lte`: <= (小于等于)
- `gt`: > (大于)
- `lt`: < (小于)

**组合示例**:
```json
// ID <= 100
{"field":"id","type":"RANGE","lte":100}

// 预计工作量 > 0 且 <= 5
{"field":"expectTime","type":"RANGE","gt":0,"lte":5}
```

---

### 6. TIME_RANGE - 时间范围查询

**用途**: 时间字段在某个时间范围内

**适用字段**: `createdAt`(创建时间), 自定义时间字段（如 `customField13031`）

**时间格式**: 毫秒时间戳（13 位数字）

**示例**:
```json
{
  "field":"createdAt",
  "type":"TIME_RANGE",
  "gte":1773590400000,
  "lte":1773676800000
}
```

**日期转毫秒时间戳**:
```javascript
// JavaScript
new Date('2026-03-14').getTime()  // 1773590400000

// Python
import datetime
int(datetime.datetime(2026, 3, 14).timestamp() * 1000)
```

---

### 7. EXISTS - 字段存在（有值）

**用途**: 查询某字段有值的记录

**示例**:
```json
{"field":"assigned","type":"EXISTS"}
```

**行为**: 返回指派给字段不为空的工作项

---

### 8. NOTEXISTS - 字段不存在（无值）

**用途**: 查询某字段为空的记录

**示例**:
```json
{"field":"iterationId","type":"NOTEXISTS"}
```

**行为**: 返回未分配迭代的工作项

---

### 9. NOTMATCH - 不包含关键词

**用途**: 文本字段不包含关键词

**适用字段**: `name`

**示例**:
```json
{"field":"name","type":"NOTMATCH","value":"已废弃"}
```

**行为**: 标题中不包含"已废弃"的工作项

---

## 常用字段一览表(以下 variable **全平台统一**，可直接使用，无需查询)

| 字段变量名 | 中文名称 | 字段类型 | 推荐查询类型 | 示例值 |
|-----------|---------|---------|------------|-------|
| `name` | 标题 | 文本 | MATCH / MATCH_PHRASE / NOTMATCH | "搜索优化" |
| `state` | 状态 | 枚举 | TERM / TERMS | "需求设计中", "开发中" |
| `priority` | 优先级 | 枚举 | TERM / TERMS | "1"(低), "2"(中), "3"(高), "4"(紧急) |
| `assigned` | 指派给 | 用户 | TERM / TERMS / EXISTS / NOTEXISTS | "zhangsan" (MIS 号) |
| `iterationId` | 迭代 | 关联字段 | TERM / TERMS / EXISTS / NOTEXISTS | "122123" (迭代ID) |
| `id` | 工作项ID | 数值 | RANGE / TERM | 93779430 |
| `createdAt` | 创建时间 | 时间 | TIME_RANGE | 1773590400000 |
| `expectTime` | 预计工作量 | 数值 | RANGE | 1.5 (天) |
| `customField*` | 自定义字段 | 多种 | 根据字段类型选择 | 见自定义字段部分 |

> **开发进展相关时间字段**（以下 variable **全平台统一**，可直接使用，无需查询）：
>
> | 字段名 | variable | 类型 | 说明 |
> |--------|----------|------|------|
> | `预计开始时间` | `expectStart` | `component_time` | 广义计划开始 |
> | `预计结束时间` | `expectClose` | `component_time` | 广义计划结束 |
> | `预计开发开始时间` | `customField13641` | `component_time` | 研发维度开始 |
> | `预计开发结束时间` | `customField13642` | `component_time` | 研发维度结束 |
> | `预计提测时间` | `customField11681` | `component_time` | 提测计划日期 |
> | `预计上线时间` | `customField13200` | `component_time` | 上线计划日期 |

> **人员角色字段**（以下 variable **全局唯一、所有空间通用**，可直接使用，无需查询）：
>
> | 角色名 | variable | 类型 | DSL 筛选别名 | 说明 |
> |--------|----------|------|-------------|------|
> | `产品主R` | `customField13161` | `component_user` | — | 产品负责人 |
> | `技术主R` | `customField24214` | `component_user` | `rdMasters` | 技术负责人 |
> | `测试主R` | `customField24215` | `component_user` | — | 测试负责人 |
> | `开发人员` | `developer` | `component_user` | `developers` | 开发人员（多选） |
>
> DSL 筛选中可使用 variable 或别名（如有）：
> ```json
> {"field":"customField24214","type":"TERM","value":"<misId>"}
> {"field":"rdMasters","type":"TERM","value":"<misId>"}
> ```
> 两种写法等价。**注意**：ONES 中只有 `component_user` 类型，没有 `component_container_user` 类型。

---

## 自定义字段查询

### 获取自定义字段信息

```bash
# 1. 查询空间字段列表
ones fs -p 51145 -t REQUIREMENT

# 输出示例:
# ┌─────┬──────────────┬───────────────────┬─────────────────┬────┐
# │ 序号 │ 字段名        │ variable          │ 类型            │ 默认│
# ├─────┼──────────────┼───────────────────┼─────────────────┼────┤
# │ 23  │ 实际上线时间   │ customField13031  │ component_time  │    │
# │ 45  │ 上次状态变更人 │ customField25261  │ component_user  │    │
# └─────┴──────────────┴───────────────────┴─────────────────┴────┘
```

### 自定义字段查询示例

**时间类字段** (`component_time`):
```json
{
  "field":"customField13031",
  "fieldName":"实际上线时间",
  "type":"TIME_RANGE",
  "gte":1773590400000,
  "lte":1773763199999
}
```

**用户类字段** (`component_user`):
```json
{
  "field":"customField25261",
  "fieldName":"上次状态变更人",
  "type":"TERMS",
  "valueList":["zhangsan","lisi"]
}
```

**数值类字段** (`int`, `float`):
```json
{
  "field":"customField23767",
  "fieldName":"预计工作量",
  "type":"RANGE",
  "gte":1,
  "lte":10
}
```

---

## 条件分组（AND / OR 组合）

通过 `group` 字段控制条件间的逻辑关系：

- **同一组内（同 group 值）**: AND 关系（同时满足）
- **不同组间**: OR 关系（满足任一组即可）

**默认行为**: 不指定 `group` 时默认为 `1`，即所有条件 AND

### 示例 1: 全部 AND（默认）

**需求**: 标题包含"搜索" AND 状态=需求设计中 AND 指派给=zhangsan

```json
[
  {"field":"name","type":"MATCH","value":"搜索","group":1},
  {"field":"state","type":"TERM","value":"需求设计中","group":1},
  {"field":"assigned","type":"TERM","value":"zhangsan","group":1}
]
```

### 示例 2: OR 组合

**需求**: (标题包含"搜索" AND 状态=需求设计中) OR (指派给=zhangsan)

```json
[
  {"field":"name","type":"MATCH","value":"搜索","group":1},
  {"field":"state","type":"TERM","value":"需求设计中","group":1},
  {"field":"assigned","type":"TERM","value":"zhangsan","group":2}
]
```

**逻辑**: `(group1.condition1 AND group1.condition2) OR (group2.condition1)`

### 示例 3: 复杂组合

**需求**: (高优 OR 紧急) AND (需求设计中 OR 开发中) AND 指派给zhangsan

```json
[
  {"field":"priority","type":"TERMS","valueList":["3","4"],"group":1},
  {"field":"state","type":"TERMS","valueList":["需求设计中","开发中"],"group":1},
  {"field":"assigned","type":"TERM","value":"zhangsan","group":1}
]
```

**说明**: TERMS 类型本身就是 OR（valueList 中任意匹配），整体再 AND

---

## 命令行快捷参数映射规则

Agent 可以优先使用快捷参数，简化命令：

| 快捷参数 | 映射的 DSL | 说明 |
|---------|-----------|------|
| `--name 关键词` | `{"field":"name","type":"MATCH","value":"关键词"}` | 标题全文搜索 |
| `--priority 高,紧急` | `{"field":"priority","type":"TERMS","valueList":["3","4"]}` | 优先级（支持逗号分隔）|
| `--state 需求设计中` | `{"field":"state","type":"TERM","value":"需求设计中"}` | 单个状态 |
| `--state 设计中,开发中` | `{"field":"state","type":"TERMS","valueList":["设计中","开发中"]}` | 多个状态 |
| `--assigned zhangsan` | `{"field":"assigned","type":"TERM","value":"zhangsan"}` | 单个指派人 |
| `--assigned zhang,li` | `{"field":"assigned","type":"TERMS","valueList":["zhang","li"]}` | 多个指派人 |
| `--iteration-id 122123` | `{"field":"iterationId","type":"TERM","value":"122123"}` | 单个迭代 |

**混合使用示例**:
```bash
ones fi -p 51145 \
  --name 搜索 \
  --priority 高,紧急 \
  --query '[{"field":"createdAt","type":"TIME_RANGE","gte":1773590400000}]'
```

**等价 DSL**:
```json
[
  {"field":"name","type":"MATCH","value":"搜索","group":1},
  {"field":"priority","type":"TERMS","valueList":["3","4"],"group":1},
  {"field":"createdAt","type":"TIME_RANGE","gte":1773590400000,"group":1}
]
```

---

## Agent 编排最佳实践

### 策略 1: 简单场景用快捷参数

**User**: "查看空间 51145 中标题包含'优化'、高优先级、指派给我的需求"

**Command**:
```bash
ones fi -p 51145 -t REQUIREMENT --name 优化 --priority 高 --assigned $OPERATOR
```

---

### 策略 2: 复杂场景用 --query JSON

**User**: "查询创建时间在本周、状态不是已完成、且预计工作量大于 5 天的任务"

**Step 1**: 计算时间范围
```javascript
const startOfWeek = new Date('2026-03-10').getTime();  // 1773590400000
const endOfWeek = new Date('2026-03-16 23:59:59').getTime();  // 1774195199000
```

**Step 2**: 构建 DSL
```json
[
  {"field":"createdAt","type":"TIME_RANGE","gte":1773590400000,"lte":1774195199000,"group":1},
  {"field":"state","type":"NOTMATCH","value":"已完成","group":1},
  {"field":"expectTime","type":"RANGE","gt":5,"group":1}
]
```

**Step 3**: 执行命令
```bash
ones fi -p 51145 -t DEVTASK --query '[
  {"field":"createdAt","type":"TIME_RANGE","gte":1773590400000,"lte":1774195199000},
  {"field":"state","type":"NOTMATCH","value":"已完成"},
  {"field":"expectTime","type":"RANGE","gt":5}
]' --json
```

---

### 策略 3: 混合模式（推荐）

**User**: "查询迭代 122123 中，标题包含'接口'、高优或紧急的需求"

**Command**:
```bash
ones fi -p 51145 -t REQUIREMENT \
  --iteration-id 122123 \
  --name 接口 \
  --priority 高,紧急
```

**等价 DSL（自动生成）**:
```json
[
  {"field":"iterationId","type":"TERM","value":"122123","group":1},
  {"field":"name","type":"MATCH","value":"接口","group":1},
  {"field":"priority","type":"TERMS","valueList":["3","4"],"group":1}
]
```

---

### 策略 4: 时间范围内开发进展查询（两阶段策略）

> 适用场景：用户询问「我本周/今天/当月开发的工作项」、「本周预计开发的工作项」、「本月预计上线的需求」等**时间范围内开发进展**相关的查询。

**为什么要两阶段？**

预计开发开始/结束、上线时间等字段值可能为空，若直接作为筛选条件会漏掉字段未填写的工作项。所以：先用稳定条件宽松捞取，再把时间字段带到展示列，在返回数据里做时间区间计算。

> 以下时间字段 variable **全平台统一**，可直接使用：
> - `expectStart` — 预计开始时间（广义）
> - `expectClose` — 预计结束时间（广义）
> - `customField13641` — 预计开发开始时间
> - `customField13642` — 预计开发结束时间
> - `customField11681` — 预计提测时间
> - `customField13200` — 预计上线时间

**Phase 1 — 宽松筛选 + 用 `-f` 带出时间字段**

```bash
ones fi -p <空间ID> -t REQUIREMENT \
  --assigned <misId> \
  --state "开发中,待开发,已提测" \
  -f "name,state,priority,customField13641,customField13642,customField13200,customField11681" \
  --json
```

**Phase 2 — 从返回数据中计算过滤**

拿到 `--json` 输出后，根据目标场景对时间字段做区间判断：

- **开发进展场景**：工作项的开发区间（`customField13641` ~ `customField13642`）与目标时间范围有交集
  - 判断条件：`customField13641 <= 目标结束时间 AND customField13642 >= 目标开始时间`
  - 若某端为空，退化为单字段判断（`customField13642` 在目标范围内，或 `customField13641` 在目标范围内）
- **上线进展场景**：`customField13200`（预计上线时间）落在目标月份内
- **提测进展场景**：`customField11681`（预计提测时间）落在目标时间范围内

**备选：DSL OR 组合宽泛捞取（时间字段有值时快速过滤）**

当字段填写率较高时，可以在 Phase 1 直接用 DSL 做初筛（能命中的一定在范围内，但字段为空的会漏）：

```bash
# 捞取「开发开始在本周」OR「开发结束在本周」的工作项（本周示例: gte=1773936000000, lte=1774540799000）
ones fi -p <空间ID> -t REQUIREMENT \
  -f "name,state,customField13641,customField13642,customField13200" \
  --query '[
    {"field":"assigned","type":"TERM","value":"<misId>","group":1},
    {"field":"customField13641","type":"TIME_RANGE","gte":1773936000000,"lte":1774540799000,"group":1},
    {"field":"assigned","type":"TERM","value":"<misId>","group":2},
    {"field":"customField13642","type":"TIME_RANGE","gte":1773936000000,"lte":1774540799000,"group":2}
  ]' --json
# group1: assigned=我 AND 预计开发开始在本周
# group2: assigned=我 AND 预计开发结束在本周
# 两组 OR → 覆盖开发区间与本周有交集的大部分情况（字段为空的需 Phase 1 宽松结果兜底）
```

---

## 常见场景 DSL 模板

### 模板 1: 查询指定迭代下的工作项

```bash
# 快捷参数（等价于 --query）
ones fi -p 51145 -t REQUIREMENT --iteration-id 12345

# 等价的 DSL 写法
ones fi -p 51145 -t REQUIREMENT --query '{"field":"iterationId","type":"TERM","value":"12345"}'

# 查询迭代下多个类型（REQUIREMENT + DEFECT），结合指派人筛选
ones fi -p 51145 -t REQUIREMENT --query '[
  {"field":"iterationId","type":"TERM","value":"12345","group":1},
  {"field":"assigned","type":"TERM","value":"zhangsan","group":1}
]'
```

> 提示：如需查看迭代工作项的树形展示（含子工作项层级），可使用专门的 `ones ii` (`iteration-issues`) 命令。

---

### 模板 2: 查询未分配迭代的高优需求

```json
[
  {"field":"iterationId","type":"NOTEXISTS","group":1},
  {"field":"priority","type":"TERMS","valueList":["3","4"],"group":1}
]
```

### 模板 3: 查询本月创建的所有工作项

```json
[
  {
    "field":"createdAt",
    "type":"TIME_RANGE",
    "gte":1773590400000,
    "lte":1776182399000
  }
]
```

### 模板 4: 查询时间范围内开发/上线进展的工作项

> 适用场景：「本周预计开发的工作项」、「当月预计上线的需求」等。详细策略说明见 [策略 4](#策略-4-时间范围内开发进展查询两阶段策略)。
>
> 时间字段 variable 全平台统一，无需查询：`customField13641`（预计开发开始）、`customField13642`（预计开发结束）、`customField13200`（预计上线）、`customField11681`（预计提测）、`expectStart`（预计开始）、`expectClose`（预计结束）。

**Step 1 — 宽松筛选 + 带出时间字段（用 `-f` 展示，供二次计算）**
```bash
ones fi -p <空间ID> -t REQUIREMENT \
  --assigned <misId> \
  -f "name,state,priority,customField13641,customField13642,customField13200,customField11681" \
  --json
```

**Step 2 — 从返回数据中过滤目标时间范围内的工作项**

- 开发进展：开发区间（`customField13641` ~ `customField13642`）与目标时间范围有交集
- 上线进展：`customField13200` 落在目标月份内
- 提测进展：`customField11681` 落在目标时间范围内

### 模板 5: 查询标题不包含"测试"且状态为开发中的任务

```json
[
  {"field":"name","type":"NOTMATCH","value":"测试","group":1},
  {"field":"state","type":"TERM","value":"开发中","group":1}
]
```

### 模板 6: 查询预计工作量在 1-3 天的中低优任务

```json
[
  {"field":"expectTime","type":"RANGE","gte":1,"lte":3,"group":1},
  {"field":"priority","type":"TERMS","valueList":["1","2"],"group":1}
]
```

### 模板 7: 复杂 OR 组合 - (高优 OR 紧急) 且 (未分配 OR 分配给我)

```json
[
  {"field":"priority","type":"TERMS","valueList":["3","4"],"group":1},
  {"field":"assigned","type":"NOTEXISTS","group":2},
  {"field":"assigned","type":"TERM","value":"zhangsan","group":3}
]
```

**逻辑**: (priority IN [3,4]) AND (assigned is null OR assigned = 'zhangsan')

---

### 模板 8: 查询有延期风险的工作项

> 适用场景：「有哪些工作项开发延期」、「本迭代有没有风险需求」、「有没有上线时间超期的工作项」等。

**为什么按状态分层而不是直接用时间字段过滤？**

不同阶段的工作项关注的风险维度不同：开发前需要检查所有时间节点，进入测试后开发延期已不再有意义，只需关注提测和上线节点。若直接用时间字段做 DSL 过滤，会造成阶段混淆（把测试阶段的工作项误判为开发延期），且字段为空的工作项会被漏掉。正确做法是先宽松拉取，再在返回数据中按 `stateCategory` 分层判断。具体状态名因空间而异，不要硬编码，以语义判断为准。

**Step 1 — 宽松拉取候选需求，带出所有时间字段和 stateCategory**

```bash
# 按指派人查
ones fi -p <空间ID> -t REQUIREMENT \
  --assigned <misId> \
  -f "name,state,stateCategory,priority,customField13641,customField13642,customField11681,customField13200" \
  --json

# 或按迭代查（覆盖全迭代所有人）
ones fi -p <空间ID> -t REQUIREMENT \
  --iteration-id <迭代ID> \
  -f "name,state,stateCategory,priority,customField13641,customField13642,customField11681,customField13200" \
  --json
```

**Step 2 — 根据 stateCategory 确定阶段，选择对应的风险判断维度**

- 如果 `stateCategory` = `TODO`（开发前）→ 执行 Step 3A
- 如果 `stateCategory` = `DOING` 且 `state` 语义为"开发中"（未进入测试）→ 执行 Step 3B
- 如果 `stateCategory` = `DOING` 且 `state` 语义为"已进入测试/上线阶段"→ 执行 Step 3C
- 如果 `stateCategory` = `DONE`（已完成）→ 跳过，无需判断

**Step 3A — 开发前（TODO）：检查所有时间节点**

逐一比对，字段为空则跳过该维度：
- `customField13641`（预计开发开始时间）< 今天 → 开发未按时启动
- `customField13642`（预计开发结束时间）< 今天 → 开发可能延期
- `customField11681`（预计提测时间）< 今天 → 提测延期风险
- `customField13200`（预计上线时间）< 今天 → 上线延期风险

**Step 3B — 开发中（DOING，未进入测试）：检查开发结束及后续节点**

- `customField13642`（预计开发结束时间）< 今天 → 开发可能延期
- `customField11681`（预计提测时间）< 今天 → 提测延期风险
- `customField13200`（预计上线时间）< 今天 → 上线延期风险

**Step 3C — 测试/上线阶段（DOING，开发已完成）：只关注后续节点**

开发已结束，不判断开发延期，只检查：
- `customField11681`（预计提测时间）< 今天 → 提测延期风险
- `customField13200`（预计上线时间）< 今天 → 上线延期风险

**Step 4 — 同步拉取子任务（DEVTASK）并判断**

```bash
ones fi -p <空间ID> -t DEVTASK \
  --assigned <misId> \
  -f "name,state,stateCategory,priority,expectStart,expectClose" \
  --json
```

对每条子任务：
- 如果 `stateCategory` = `TODO` 且 `expectStart` < 今天 → 任务未按时开始
- 如果 `stateCategory` ≠ `DONE` 且 `expectClose` < 今天 → 任务延期

> `--json` 输出采用 `TREE_MODE`，顶层需求的 `children` 数组直接包含子任务，可直接定位"哪个需求下的哪个任务"异常，无需额外查询。时间字段为空时，视为该节点无约束，跳过该条风险判断。

**备选：DSL 初筛（字段填写率高时可快速捞出明显超期工作项）**

当字段填写率较高时，可先用 DSL 定位明显超期的工作项，再用 Step 1 的宽松结果兜底补全字段为空的漏网之鱼。

```bash
# 捞取"开发前且预计开发结束时间已过"或"非完成状态且预计上线时间已过"
# ⚠️ <now> 替换为当前毫秒时间戳
ones fi -p <空间ID> -t REQUIREMENT \
  -f "name,state,stateCategory,customField13642,customField13200" \
  --query '[
    {"field":"stateCategory","type":"TERM","value":"TODO","group":1},
    {"field":"customField13642","type":"TIME_RANGE","lte":<now>,"group":1},
    {"field":"stateCategory","type":"TERM","value":"DOING","group":2},
    {"field":"customField13200","type":"TIME_RANGE","lte":<now>,"group":2}
  ]' --json
```

group1 捞取"开发前（TODO）且预计开发结束已过"的工作项；group2 捞取"进行中（DOING）且预计上线时间已过"的工作项。两组 OR，合并覆盖主要超期场景。`DONE` 状态的工作项不会出现在任意一组中，无需额外排除。

---

## 调试与验证

### 1. 使用 --json 查看完整 DSL

```bash
ones fi -p 51145 --name 搜索 --priority 高 --json | jq '.query'
```

**输出**:
```json
[
  {"field":"name","type":"MATCH","value":"搜索","group":1},
  {"field":"priority","type":"TERMS","valueList":["3"],"group":1}
]
```

### 2. 验证字段名是否正确

```bash
# 查询空间字段列表
ones fs -p 51145 -t REQUIREMENT

# 确认 variable 和 type（用于构建正确的 DSL）
```

### 3. 验证时间戳是否正确

```bash
# JavaScript 快速验证
node -e "console.log(new Date(1773590400000))"  # 输出: 2026-03-14T00:00:00.000Z
```

---

## 错误排查

| 错误信息 | 原因 | 解决方法 |
|---------|-----|---------|
| `--query 参数不是合法的 JSON` | JSON 格式错误 | 检查引号、括号、逗号是否正确 |
| `优先级参数无效` | 优先级值不在 1-4 范围 | 使用 低/1、中/2、高/3、紧急/4 |
| `查询返回 0 条` | 条件过于严格或字段名错误 | 1. 用 --json 查看 DSL 是否正确<br>2. 用 `ones fs` 验证字段名<br>3. 逐步减少条件排查 |
| `认证失败 401` | Token 过期 | `ones sso refresh` |

---

## 参考资源

- [命令完整参数](./command-reference.md) - 查看 filter-issues 命令的所有参数
- [字段管理](./command-reference.md#字段管理) - 如何查询空间字段列表和可选值
- ONES API 文档: https://s3plus-bj02.vip.sankuai.com/supabase-bucket/ones-api-skill.md

---

## ⚠️ 策略 5: 「与我相关的工作项查询」强制规则

> 适用场景：用户询问「我的需求」「我在开发什么」「帮我看看待开发的」「我有哪些 bug」「我的待办」等**涉及自己的工作项**查询。这是最常见的查询场景之一，必须严格遵循以下规则。

### 规则 1: 必须带上当前用户的人员筛选

无论用户如何描述，筛选条件中**必须**包含当前用户（通过 `ones config` 或 `ones sso status` 获取 operator/MIS）。人员筛选使用 `--assigned`（指派给）；如果用户明确说是"技术主R"或"开发人员"则使用对应的 DSL 字段（`rdMasters` / `developers`）。

**禁止**在「与我相关」场景下执行不带人员筛选的宽泛查询。

### 规则 2: 「待开发/要开发/开发中」的状态映射

不同空间的状态名称不同，**不能硬编码状态值**。正确做法：

1. **优先询问用户**希望查找的工作项状态范围，提供以下选项供参考：
   - **待开发**（还未开始）：对应 `stateCategory = TODO`，即所有「待处理」类状态
   - **开发中**（正在进行）：对应 `stateCategory = DOING`，即所有「进行中」类状态
   - **待开发 + 开发中**：同时包含 TODO 和 DOING

2. **如果用户未明确指定**，默认使用 `--state TODO,DOING`（对应 `stateCategory` 而非具体状态名）筛选「未完成的工作项」

3. **用户也可以自定义状态范围**：如果用户说"帮我查评审中的需求"，直接使用 `--state 评审中`

### 规则 3: 查不到时的处理

如果按照上述筛选条件查询结果为空：
- **禁止**自行去掉人员筛选条件、扩大搜索范围或换其他方式重试
- **必须**明确告知用户：「在您的筛选条件（指派给/技术主R/开发人员 = 您的 MIS，状态 = XXX）下，未找到匹配的工作项」
- 可以建议用户调整筛选条件，例如：换一个状态范围、换一个空间、检查是否用对了空间 ID 等

### 模板 9: 查我的待开发 / 开发中工作项

```bash
# 获取当前用户 MIS
ones sso status   # 从输出的 operator 字段获取 MIS 号

# 查我的未完成需求（默认 TODO+DOING = 待开发+开发中）
ones fi -p <空间ID> -t REQUIREMENT --assigned <misId> --state TODO,DOING --json

# 如果用户只要"待开发"（还没开始的）
ones fi -p <空间ID> -t REQUIREMENT --assigned <misId> --state TODO --json

# 如果用户只要"开发中"（正在做的）
ones fi -p <空间ID> -t REQUIREMENT --assigned <misId> --state DOING --json

# 查我的未完成任务
ones fi -p <空间ID> -t DEVTASK --assigned <misId> --state TODO,DOING --json

# 查我的未完成缺陷
ones fi -p <空间ID> -t DEFECT --assigned <misId> --state TODO,DOING --json

# 查我是技术主R的需求（customField24214 或别名 rdMasters 均可）
ones fi -p <空间ID> -t REQUIREMENT \
  --query '[{"field":"customField24214","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json

# 查我是开发人员的任务（developer 或别名 developers 均可）
ones fi -p <空间ID> -t DEVTASK \
  --query '[{"field":"developer","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json
```

> **人员角色字段 variable（全局唯一）**：产品主R=`customField13161`、技术主R=`customField24214`（别名 `rdMasters`）、测试主R=`customField24215`、开发人员=`developer`（别名 `developers`）。
> **如何获取当前用户 MIS**：`ones sso status` 的 operator 字段，或 `ones config` 的 operator 字段。如果均为空，需要先让用户登录。

**如果结果为空**，直接告知用户：
> 「在指派给 = `<misId>`、状态 = 待开发+开发中的筛选条件下，未找到匹配的工作项。您可以尝试：(1) 切换到其他空间查询 (2) 调整状态范围 (3) 确认空间 ID 是否正确」

❌ 禁止自行去掉 `--assigned` 或 `--state` 重新查询。

---

## 总结

1. **优先使用快捷参数**（`--name` / `--priority` / `--state` / `--assigned` / `--iteration-id`）简化命令
2. **复杂查询用 `--query` JSON**（时间范围、自定义字段、NOTEXISTS、范围查询等）
3. **两者可混合使用**，最终自动合并为一个 query 数组
4. **同组内 AND，不同组间 OR**（通过 `group` 字段控制）
5. **用 `--json` 调试**，查看完整的 DSL 和响应数据
6. **用 `ones fs` 和 `ones fo`** 查询字段信息和可选值，确保 DSL 正确
7. **开发进展时间查询用两阶段策略**：预计开发开始/结束、上线时间等自定义时间字段优先作为 `-f` 展示列输出，宽松捞取后客户端二次过滤，避免字段为空导致漏项
8. **「与我相关」查询必须带人员筛选**：详见 [策略 5](#⚠️-策略-5-与我相关的工作项查询强制规则)，禁止不带人员条件的宽泛查询
