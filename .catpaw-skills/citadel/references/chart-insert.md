# 数据图表新建与编辑操作手册

本文档分两章：
- **第一章**：标准执行 SOP（步骤顺序、参数说明、常见问题）
- **第二章**：各图表类型的 config/dataConfig 参考模板

---

## 第一章：标准执行 SOP

### 1.1 新建图表完整流程（createAndInsertChart）

#### 完整步骤

```
Step 1: AI 准备数据 → 写入临时文件
Step 2: createAndInsertChart（创建骨架 → 上传数据 → 查询 schema → 保存发布）
Step 3: getDocumentXml → 插入 chartXml 节点 → updateDocumentByXml
```

#### 详细命令

```bash
# Step 1：将表格数据写入本地临时文件（必须，避免命令行内联大段 JSON）
# 数据格式：二维 JSON 数组，第 0 行为列名，后续为数据行
# 列顺序约定：第一列为维度（字符串/日期），后续列为数值

# 示例数据文件 /tmp/chart-data.json：
# [
#   ["月份", "销量", "利润"],
#   ["1月", 100, 20],
#   ["2月", 150, 35],
#   ["3月", 120, 28]
# ]

# Step 2：创建图表（基础用法）
oa-skills citadel createAndInsertChart \
  --contentId <文档ID> \
  --title "月度销售趋势" \
  --type line \
  --data-file /tmp/chart-data.json

# Step 2（进阶）：同时指定可视化配置
oa-skills citadel createAndInsertChart \
  --contentId <文档ID> \
  --title "月度销售趋势" \
  --type bar \
  --data-file /tmp/chart-data.json \
  --color-theme tech \
  --legend topCenter \
  --x-axis-name "月份" \
  --y-axis-name "销量（件）" \
  --data-zoom true \
  --toolbox true

# 命令返回值包含：
# - chartId：图表 ID（20位 hex 字符串）
# - chartXml：<km-data2chart chartId="<chartId>" />
# - title：图表标题

# Step 3：将 chartXml 插入文档合适位置
oa-skills citadel getDocumentXml --contentId <文档ID> --output /tmp/doc.xml
# AI 编辑 /tmp/doc.xml，在合适位置插入：
# <km-data2chart chartId="<chartId>" />
oa-skills citadel updateDocumentByXml \
  --contentId <文档ID> \
  --file /tmp/doc.xml \
  --step-version <stepVersion>
```

#### 参数说明

**基础参数**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--contentId` | ✅ | 目标文档 ID |
| `--title` | ✅ | 图表标题 |
| `--type` | ✅ | 图表类型，见下方类型表 |
| `--data` | ⚠️ 二选一 | 内联 JSON 二维数组字符串 |
| `--data-file` | ⚠️ 二选一 | 本地 JSON 文件路径（推荐）|
| `--sub-types` | 仅混合图 | 各数值列子类型，逗号分隔 |

> ⚠️ `--data` 和 `--data-file` 必须提供其中一个。数据量超过几行时强烈推荐使用 `--data-file`。

**可视化配置参数（均为可选）**

| 参数 | 默认值 | 可选值 | 说明 |
|------|--------|--------|------|
| `--color-theme` | `default` | `default` / `tech` / `fresh` / `warm` / `cool` | 图表配色主题 |
| `--legend` | `bottomCenter` | `bottomCenter` / `topCenter` / `leftCenter` / `rightCenter` / `hidden` | 图例位置；`hidden` 表示隐藏图例 |
| `--x-axis` | `show` | `show` / `hide` | X 轴显示（仅坐标系图表：line/bar/area/stack/rotatingBar/scatter） |
| `--x-axis-name` | _(空)_ | 任意字符串 | X 轴标题，显示在坐标轴末端 |
| `--y-axis` | `show` | `show` / `hide` | Y 轴显示（仅坐标系图表） |
| `--y-axis-name` | _(空)_ | 任意字符串 | Y 轴标题 |
| `--data-zoom` | `false` | `true` / `false` | 底部滑动数据缩放条（数据行多时推荐开启） |
| `--toolbox` | `false` | `true` / `false` | 右上角图表下载按钮 |

#### 支持的图表类型

| `--type` 值 | 图表名称 | 数据约束 |
|-------------|----------|----------|
| `line` | 折线图 | 1维度 + ≥1数值 |
| `bar` | 柱状图 | 1维度 + ≥1数值 |
| `area` | 面积图 | 1维度 + ≥1数值 |
| `stack` | 堆叠图 | 1维度 + ≥2数值 |
| `rotatingBar` | 条形图（横向柱状图）| 1维度 + ≥1数值 |
| `scatter` | 散点图 | 1维度 + ≥1数值 |
| `pie` | 饼图 | 1维度 + 1数值（多数值时只渲染第一个） |
| `ring` | 环图 | 1维度 + 1数值 |
| `funnel` | 漏斗图 | 1维度 + 1数值 |
| `nightingale` | 南丁格尔玫瑰图 | 1维度 + 1数值 |
| `line,bar` | 折线+柱状混合图 | 1维度 + ≥2数值，`--type line,bar` |
| `line,scatter` | 折线+散点混合图 | 1维度 + ≥2数值，`--type line,scatter` |

> **混合图表注意事项**：
> - `--type` 传逗号分隔值（如 `line,bar`），系统会将 type 作为数组处理
> - 建议同时传 `--sub-types` 来明确每个数值列的子图表类型（如 `--sub-types "line,bar"`）
> - `--sub-types` 的值数量对应数值列数量（即总列数 - 1）

---

### 1.2 编辑图表数据（updateChartData）

适用场景：修改图表的表格数据，可同时修改标题或图表类型。

```bash
# Step 1：获取 chartId（从文档 Markdown 占位行）
# 占位行格式：📈 **数据图表**（id: <chartId>）
# 无需再手动获取 source_id，命令内部自动获取

# Step 2：准备新数据
# /tmp/new-data.json 内容同上格式

# Step 3：更新（AI 自动判断列结构，选择合适接口）
oa-skills citadel updateChartData \
  --contentId <文档ID> \
  --chartId <chartId> \
  --data-file /tmp/new-data.json

# 可选：同时改标题和/或图表类型
oa-skills citadel updateChartData \
  --contentId <文档ID> \
  --chartId <chartId> \
  --data-file /tmp/new-data.json \
  --title "新标题" \
  --type bar

# 可选：同时调整可视化配置
oa-skills citadel updateChartData \
  --contentId <文档ID> \
  --chartId <chartId> \
  --data-file /tmp/new-data.json \
  --legend topCenter \
  --data-zoom true
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--contentId` | ✅ | 文档 ID |
| `--chartId` | ✅ | 图表 ID（来自文档 Markdown 占位行） |
| `--source-id` | 可选 | 数据源 ID（通常无需手动传入，命令内部自动获取）|
| `--data` / `--data-file` | ✅ 二选一 | 新数据集 |
| `--title` | 可选 | 同时更新图表标题 |
| `--type` | 可选 | 同时更新图表类型 |
| 可视化配置参数 | 可选 | 同 1.1 节参数表（`--color-theme` / `--legend` / `--x-axis` 等）|

**内部判断逻辑**：
- 若新旧列名完全相同 → 调用 `PUT /dataset`（复用旧 field_key，保留 alias/type 元数据）
- 若列名有增减或变化 → 调用 `PUT /file` 替换整个数据文件，重新生成 field_key

**自动备份与回滚**：

`updateChartData` 在执行写操作之前会自动调用 `getChartData` 备份当前状态，快照以 JSON 文件形式保存到本地：

```
/tmp/chart-backup-<chartId>-<timestamp>.json
```

快照内容包含完整的 `chartData`（head + body）和 `config`（图表类型、标题、坐标轴等）。

执行成功后，stderr 会输出快照路径和完整回滚命令（包含 `--data-file`、`--title`、`--type`），例如：

```
💾 本次操作前快照已保存至：/tmp/chart-backup-<chartId>-<ts>.json
   如需完整回滚（数据 + 标题 + 类型），请执行：
   oa-skills citadel updateChartData \
     --contentId <文档ID> \
     --chartId <chartId> \
     --data-file /tmp/chart-backup-<chartId>-<ts>.json \
     --title "<原始标题>" \
     --type <原始类型>
```

> ℹ️ **快照文件可直接传入 `--data-file`**：
>
> `updateChartData` 支持两种 `--data-file` 格式：
> - 标准二维数组（`[["列1","列2"], ...]`）
> - `getChartData` 完整快照（`{"chartData": {"head": [...], "body": [...]}, "config": {...}}`）
>
> 传入快照文件时，CLI 会自动检测格式并提取 `chartData.head`（列名）和 `chartData.body`（数据行）重组为二维数组，无需手动转换，**回滚命令可直接执行**。
>
> 回滚命令会同时还原数据、标题和图表类型，实现完整状态恢复。若只需恢复数据可省略 `--title` / `--type`。
>
> 备份失败不会中止主流程，但此时若执行出错则无快照可用，请谨慎操作。

---

### 1.3 编辑图表配置（updateChartConfig）

适用场景：仅修改图表类型或标题，不改变底层数据。

```bash
# 改图表类型
oa-skills citadel updateChartConfig \
  --contentId <文档ID> \
  --chartId <chartId> \
  --type bar

# 改标题
oa-skills citadel updateChartConfig \
  --contentId <文档ID> \
  --chartId <chartId> \
  --title "新标题"

# 同时改两者
oa-skills citadel updateChartConfig \
  --contentId <文档ID> \
  --chartId <chartId> \
  --title "Q2 销售数据" \
  --type pie

# 改为混合图
oa-skills citadel updateChartConfig \
  --contentId <文档ID> \
  --chartId <chartId> \
  --type line,bar \
  --sub-types "line,bar"

# 仅调整可视化样式（不改数据/类型）
oa-skills citadel updateChartConfig \
  --contentId <文档ID> \
  --chartId <chartId> \
  --legend rightCenter \
  --color-theme tech \
  --toolbox true
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--contentId` | ✅ | 文档 ID |
| `--chartId` | ✅ | 图表 ID |
| `--title` | ⚠️ 至少提供一个 | 新标题 |
| `--type` | ⚠️ 至少提供一个 | 新图表类型 |
| `--sub-types` | 可选 | 混合图时各数值列子类型 |
| 可视化配置参数 | 可选 | 同 1.1 节参数表（`--color-theme` / `--legend` / `--x-axis` 等）|

> ⚠️ `--title`、`--type`、可视化配置参数三者至少提供其中一个，否则命令会报错提示无需更新。

**自动备份与回滚**：

`updateChartConfig` 在执行写操作之前会自动调用 `getChartData` 备份当前图表配置，快照路径同 1.2 节：

```
/tmp/chart-backup-<chartId>-<timestamp>.json
```

执行成功后，stderr 会输出快照路径以及可直接执行的回滚命令（包含原始 `--title` 和 `--type` 值），例如：

```
💾 本次操作前快照已保存至：/tmp/chart-backup-<chartId>-<ts>.json
   如需回滚图表配置，请执行：
   oa-skills citadel updateChartConfig \
     --contentId <文档ID> \
     --chartId <chartId> \
     --title "<原始标题>" \
     --type <原始类型>
   （完整备份含 config 明细，可在 /tmp/chart-backup-<chartId>-<ts>.json 中查阅）
```

> ⚠️ **回滚注意事项**：
>
> 上述回滚命令仅能还原 `title` 和 `type`，**无法**还原精细的可视化配置（颜色主题、图例位置、坐标轴标题等）。如需完整还原，需打开快照文件查看 `config.label` 中的字段，手动拼接对应的 `--color-theme` / `--legend` 等参数。
>
> 备份失败不会中止主流程，但此时若执行出错则无快照可用，请谨慎操作。

---

### 1.4 读取图表数据（getChartData）

```bash
# 从 getSimpleMarkdown 的输出找到占位行：
# > 📈 **数据图表**（id: <chartId>）

oa-skills citadel getChartData --contentId <文档ID> --chartId <chartId>
```

返回关键字段：
- `chartData.head[i].name`：列名
- `chartData.head[i].key`：内部 field_key（编辑时需要）
- `chartData.head[i].type`：1=维度，3=数值
- `chartData.body`：数据行
- `config.type`：图表类型
- `config.dataConfig.source_id`：数据源 ID（`updateChartData` 内部已自动获取，无需手动记录）
- `config.title.text`：图表标题

---

### 1.5 意图判断矩阵

| 用户意图 | 使用命令 | 必须先执行 |
|---------|---------|-----------|
| 新建图表并插入文档 | `createAndInsertChart` + 文档插入三步流程 | 无（先准备数据） |
| 更新图表数据（数值/新增行等） | `updateChartData` | 无（有 chartId 即可，source_id 自动获取） |
| 更换图表类型（折线→柱状等） | `updateChartConfig` | 无（有 chartId 即可） |
| 同时改数据+类型 | `updateChartData --type xxx` | 无（有 chartId 即可） |
| 仅调整视觉样式（颜色/图例/坐标轴等） | `updateChartConfig --color-theme xxx --legend xxx` 等 | 无（有 chartId 即可） |
| 读取/查看图表数据 | `getChartData` | 无 |

---

### 1.6 常见问题

**Q：createAndInsertChart 命令返回了 chartXml，图表为什么没出现在文档里？**

A：`createAndInsertChart` 只是创建并发布图表对象，**不会自动插入文档**。必须额外执行三步：
1. `getDocumentXml --output /tmp/doc.xml`
2. 在 XML 合适位置插入 `<km-data2chart chartId="<chartId>" />`
3. `updateDocumentByXml --file /tmp/doc.xml`

---

**Q：updateChartData 报错 `400 非法 headers key`**

A：通常是传入了错误的 `--source-id`。`--source-id` 现为可选参数，命令内部会自动从 GET /api/chart/:id 获取 source_id，**建议不要手动传入**。如确需手动指定，必须确保来源正确（来自 `getChartData` 或 GET /api/chart/:id 的响应）。

---

**Q：饼图、漏斗图数据有多个数值列，但只渲染了第一列**

A：非坐标系图表（pie/ring/funnel/nightingale）只使用第一个数值列作为度量，多余数值列会被忽略。若需展示多系列，请改用柱状图或堆叠图。

---

**Q：混合图 `--type line,bar` 执行后，两个数值列显示类型相同**

A：需要通过 `--sub-types` 明确指定：`--sub-types "line,bar"`（与数值列顺序对应，第一个数值列用折线，第二个用柱状）。

---

**Q：图表创建成功但刷新文档看不到**

A：确认执行了文档插入三步流程，且 `updateDocumentByXml` 返回成功。若命令都返回成功，尝试强制刷新浏览器（Cmd+Shift+R）。

---

## 第二章：各图表类型 config/dataConfig 参考模板

以下模板描述 `saveAndPublishChart` 时传入的 `config` 结构，供 AI 理解底层接口。
实际使用时，AI 只需传入 `--type`，CLI 会自动构建 config；以下模板供调试和高级定制参考。

---

### 2.1 折线图（line）

```json
{
  "type": "line",
  "settings": {
    "chartType": "line",
    "theme": "default",
    "legend": { "show": true, "position": "bottom" },
    "xAxis": { "show": true, "name": "" },
    "yAxis": { "show": true, "name": "" }
  },
  "dataConfig": {
    "source_id": "<sourceId>",
    "dimension": { "field_key": "<维度列 key>" },
    "metrics": [
      { "field_key": "<数值列1 key>" },
      { "field_key": "<数值列2 key>" }
    ],
    "filter": []
  }
}
```

**数据示例**：
```json
[
  ["日期", "访问量", "注册量"],
  ["2024-01", 1200, 80],
  ["2024-02", 1500, 120],
  ["2024-03", 1100, 95]
]
```

---

### 2.2 柱状图（bar）

config 结构与折线图相同，`type` 改为 `"bar"`，`settings.chartType` 改为 `"bar"`。

**适用数据**：1维度 + 多数值，各系列并排展示。

---

### 2.3 面积图（area）

config 结构与折线图相同，`type` 改为 `"area"`。

---

### 2.4 堆叠图（stack）

```json
{
  "type": "stack",
  "settings": {
    "chartType": "stack"
  },
  "dataConfig": {
    "source_id": "<sourceId>",
    "dimension": { "field_key": "<维度列 key>" },
    "metrics": [
      { "field_key": "<数值列1 key>" },
      { "field_key": "<数值列2 key>" }
    ],
    "filter": []
  }
}
```

**注意**：至少需要 2 个数值列，否则堆叠效果不明显。

---

### 2.5 条形图（rotatingBar）

config 结构与柱状图相同，`type` 改为 `"rotatingBar"`。适合横向展示分类对比，例如不同产品线的销售额排名。

---

### 2.6 散点图（scatter）

config 结构与折线图相同，`type` 改为 `"scatter"`，`settings.chartType` 改为 `"scatter"`。

---

### 2.7 饼图（pie）

```json
{
  "type": "pie",
  "settings": {
    "chartType": "pie",
    "theme": "default",
    "legend": { "show": true, "position": "bottom" }
  },
  "dataConfig": {
    "source_id": "<sourceId>",
    "dimension": { "field_key": "<分类列 key>" },
    "metrics": [
      { "field_key": "<数值列 key>" }
    ],
    "filter": []
  }
}
```

**数据示例**：
```json
[
  ["产品", "销售额"],
  ["产品A", 35],
  ["产品B", 25],
  ["产品C", 40]
]
```

**约束**：1维度（分类） + 1数值（大小）；多个数值列时仅第一列生效。

---

### 2.8 环图（ring）

config 结构与饼图相同，`type` 改为 `"ring"`。视觉上在饼图中心挖出圆形空白。

---

### 2.9 漏斗图（funnel）

```json
{
  "type": "funnel",
  "settings": {
    "chartType": "funnel",
    "funnelSortType": "descending"
  },
  "dataConfig": {
    "source_id": "<sourceId>",
    "dimension": { "field_key": "<阶段列 key>" },
    "metrics": [
      { "field_key": "<数量列 key>" }
    ],
    "filter": []
  }
}
```

**数据示例**：
```json
[
  ["转化阶段", "人数"],
  ["浏览", 10000],
  ["加购", 3000],
  ["下单", 1500],
  ["支付", 800]
]
```

**说明**：数值默认按降序排列（`funnelSortType: "descending"`），通常用于展示转化漏斗。

---

### 2.10 南丁格尔玫瑰图（nightingale）

config 结构与饼图相同，`type` 改为 `"nightingale"`。各扇形角度相同，通过面积（半径）大小展示数值差异。

---

### 2.11 折线+柱状混合图（line,bar）

```json
{
  "type": ["line", "bar"],
  "settings": {
    "chartType": "line",
    "theme": "default",
    "legend": { "show": true, "position": "bottom" },
    "xAxis": { "show": true, "name": "" },
    "yAxis": { "show": true, "name": "" }
  },
  "dataConfig": {
    "source_id": "<sourceId>",
    "dimension": { "field_key": "<维度列 key>" },
    "metrics": [
      { "field_key": "<数值列1 key>", "chartType": "line" },
      { "field_key": "<数值列2 key>", "chartType": "bar" }
    ],
    "filter": []
  }
}
```

**数据示例**：
```json
[
  ["月份", "销量", "增长率%"],
  ["1月", 1200, 5.2],
  ["2月", 1500, 25.0],
  ["3月", 1100, -26.7]
]
```

**说明**：
- `type` 为数组 `["line", "bar"]`
- `metrics` 中每项可以指定 `chartType` 覆盖默认类型
- `--sub-types "line,bar"` 对应 CLI 的混合图子类型参数

---

### 2.12 折线+散点混合图（line,scatter）

结构与 line,bar 相同，将第二个 metrics 的 `chartType` 改为 `"scatter"`：

```json
"metrics": [
  { "field_key": "<趋势线 key>", "chartType": "line" },
  { "field_key": "<散点 key>", "chartType": "scatter" }
]
```

---

## 附录：数据列类型规则

| type 值 | 含义 | 通常作为 |
|---------|------|---------|
| `1` | 字符串/日期（维度） | `dimension` |
| `3` | 数值 | `metrics` |

CLI 自动判断规则：
- `type=1` 的第一列 → 自动设为 `dimension`
- 若所有列均为 `type=1`（纯文本数据），则取第一列为 dimension
- 其余列 → 按顺序加入 `metrics`

若发现维度/指标识别有误（如日期列被识别为数值），可通过数据预处理解决：确保日期/类别列值为字符串格式（如 `"2024-01"` 而非 `20240101`）。
