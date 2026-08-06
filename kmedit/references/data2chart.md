# Data2Chart 使用指南

本指南告诉 Agent 如何使用 `kmedit` 已封装好的 Data2Chart 能力。不要把它当成 D2C 接口文档；执行时只需要构造 `kmedit patch` operations。

## 什么时候使用

当用户要在 KM 文档里插入或更新“数据图表 / Data2Chart / D2C 图表”时使用：

- 插入一张基于数据的图表
- 把表格、CSV、业务数据做成图
- 更新已有图表的数据
- 更新已有图表的标题、颜色、图例、坐标轴、图表类型或展示样式
- 在文档指定段落前后展示经营指标、趋势、占比、排行等可交互数据图表

不要把 Data2Chart 降级成图片、iframe、代码块或 markdown 表格。

认证由 `kmedit` 复用 Citadel 官方 SSO audience `com.sankuai.it.ead.citadel`，并通过本机认证链向
Data2Chart 发送 `access-token`。通常不需要单独配置 clientId；`DATA2CHART_SSO_CLIENT_ID` 仅用于兼容性覆盖。
创建图表时 runtime 会补齐官方渲染器默认配置；更新已有图表的样式或数据时，也会自动修复历史节点缺失的
默认字段，无需 Agent 手工拼装完整配置。`check` 与 `patch` 使用同一套最终配置计算；实际写入在
KM step 提交前会再次读取 Provider 的生效 config/source，读回不一致则停止提交。

## 用户输入形态

可接受这些输入，并转换为对应操作：

- 已有 KM 图表：用户给出目标图表、位置描述或上下文文本时，先定位到原生 `data2chart` 节点，再更新。
- 新图表位置：用户给出“插在某段后 / 某标题下 / 文末”等位置时，先定位到对应段落/标题节点的 `nodeId`，再用 `target.nodeId` 插入。
- API-only 本地数据文件：支持 `.csv`；`.xlsx` 先在本地归一化成 `data.rows`，或显式转到 CDP runtime。
- 内联数据：支持用户粘贴的 markdown 表格、CSV 文本、JSON rows、自然语言表格。先在本地生成完整 `.csv` 或 `.xlsx` 文件，再调用数据更新能力。
- 样式要求：支持标题、图表类型、颜色、图例、坐标轴、标签、网格、柱宽、折线样式、饼图半径等常见展示配置。

数据文件要求：

- 第一行必须是字段名。
- 字段名不能重复。
- 必须有一个维度字段，例如 `日期`、`品类`、`渠道`。
- 至少有一个数值字段，例如 `订单量`、`GMV`、`销售额`、`转化率`。
- CSV 推荐 UTF-8 编码；含逗号、换行、双引号的单元格要按标准 CSV 转义。

## 支持的图表类型

创建新图表时，`data2chart.template` 支持以下模板名。用户未指定类型时，Agent 应根据数据和表达目的自行选择。

坐标系图表：

- `折线图`：展示趋势、时间序列、多指标变化。适合日期/时间维度 + 1 到多个数值字段。
- `柱状图`：展示分类对比、排行、分组指标。适合分类维度 + 1 到多个数值字段。
- `面积图`：展示趋势并强调规模、累计感或整体量级。适合日期/时间维度 + 1 到多个数值字段。
- `堆叠图`：展示整体与组成同时变化。适合日期/分类维度 + 多个可相加的数值字段。
- `条形图`：展示横向排行或长分类名对比。适合分类较多、分类名较长的场景。
- `折线柱状图`：展示量级指标和比率指标的组合关系。适合一个维度 + 至少两个不同量纲的数值字段，例如 `销售额` 和 `转化率`。
- `折线散点图`：展示趋势中的离散点、异常点或点线组合。适合连续维度 + 数值字段，或用户明确需要散点效果时。

非坐标系图表：

- `饼图`：展示构成占比。适合分类维度 + 单个数值字段，分类数量最好不超过 8 个。
- `环图`：展示构成占比，视觉上比饼图更适合嵌入汇总信息。适合分类维度 + 单个数值字段。
- `漏斗图`：展示阶段转化、流程流失。适合阶段维度 + 单个数值字段，阶段顺序应有业务含义。
- `南丁格尔图`：展示占比并突出差异。适合分类维度 + 单个数值字段，分类数量不宜过多。

完整 `config.type` 枚举：

- `"line"`：折线图，对应模板 `折线图`
- `"bar"`：柱状图，对应模板 `柱状图`
- `"area"`：面积图，对应模板 `面积图`
- `"stack"`：堆叠图，对应模板 `堆叠图`
- `"rotatingBar"`：条形图，对应模板 `条形图`
- `["line", "bar"]`：折线柱状图，对应模板 `折线柱状图`
- `["line", "scatter"]`：折线散点图，对应模板 `折线散点图`
- `"pie"`：饼图，对应模板 `饼图`
- `"ring"`：环图，对应模板 `环图`
- `"funnel"`：漏斗图，对应模板 `漏斗图`
- `"nightingale"`：南丁格尔图，对应模板 `南丁格尔图`

使用规则：

- 新建图表时优先通过 `data2chart.template` 选择类型；只有需要明确改类型或保持配置一致时，才在 `update_data2chart_config` 里设置 `config.type`。
- `config.type` 可以是字符串，也可以是数组；组合图必须使用数组形式，例如 `["line", "bar"]`。
- 不要用 ECharts 的近似字段替代 D2C 类型，例如环图用 `"ring"`，南丁格尔图用 `"nightingale"`。

选型规则：

- 用户明确指定图表类型时，优先按用户指定类型执行。
- 用户只说“趋势、走势、变化、按天/周/月看”：选 `折线图`；强调量级填充或累计趋势时选 `面积图`。
- 用户只说“对比、排行、TOP、各品类/各城市/各渠道”：选 `柱状图`；分类名长或类别多时选 `条形图`。
- 用户只说“占比、构成、份额、分布”：选 `饼图`；如果需要更精致或中心留白展示总量，选 `环图`；强调差异可选 `南丁格尔图`。
- 用户只说“转化、漏斗、阶段、流失”：选 `漏斗图`。
- 用户给多个可相加指标并想看整体与组成：选 `堆叠图`。
- 用户给两个不同量纲指标，例如金额和比例、订单量和转化率：选 `折线柱状图`。
- 用户提到异常点、散点、离散分布或点线混合：选 `折线散点图`。
- 没有明显意图时，按数据形态默认选择：时间维度用 `折线图`，分类维度用 `柱状图`，单字段占比用 `饼图`。

## 三个操作的关键参数

通用字段：

- `op`：必填，三种值分别是 `"insert_data2chart"`、`"update_data2chart_config"`、`"update_data2chart_data"`。
- `target`：必填。定位插入点或已有图表节点，必须优先使用 `target.nodeId`，这是最准确、最稳定的定位方式。
- `target.fallback`：仅在无法获得 nodeId 时兜底使用。fallback 文本容易重复，不能作为首选定位方式。
- `target.fallback.nth`：可选，仅用于 fallback 文本匹配多个节点时指定第几个匹配项，从 `0` 开始。
- `position`：仅 `insert_data2chart` 使用，可选值为 `"before"`、`"after"`、`"inside_start"`、`"inside_end"`；默认按 `"after"` 理解，常用 `"after"` 或 `"before"`。

`insert_data2chart`：

- `data2chart`：必填，图表创建参数对象。
- `data2chart.template`：可选，图表模板名，支持本文“支持的图表类型”中列出的模板；默认 `"面积图"`。
- `data2chart.pageId`：可选，默认当前 KM `docId`。
- `data2chart.width`：可选，默认 `600`。
- `data2chart.height`：可选，默认 `400`。
- `data2chart.nodeId`：可选；如果后续要同批更新样式或数据，建议显式指定稳定 nodeId。

`update_data2chart_config`：

- `target`：必填，必须定位到已有原生 `data2chart` 节点。
- `config`：必填，JSON 对象或合法 JSON 字符串；只传要修改的配置片段。
- 常见 `config` 字段包括 `type`、`title`、`color`、`legend`、`tooltip`、`xAxis`、`yGrid`、`lineStyle`、`barStyle`、`radius`。
- `config.type`：可选但常用，完整枚举见本文“完整 `config.type` 枚举”。

`update_data2chart_data`：

- `target`：必填，必须定位到已有原生 `data2chart` 节点。
- `data`：必填，数据源替换参数对象。
- `data.path` 或 `data.file.path`：必填，本地 `.csv` 文件路径；XLSX API-only 需要同时提供已归一化的 `data.rows`。
- `data.header`：必填，文件第一行字段名列表；字段名不能为空且不能重复。
- `data.dimensionField`：可选，维度字段；默认 `header[0]`。
- `data.numberFields`：可选，数值字段列表；默认除维度字段外的全部字段。
- `data.filename` 或 `data.file.name`：可选，上传文件名；当本地临时文件没有 `.xlsx` / `.csv` 扩展名时必须提供。
- `data.file.mimeType`：可选，通常不需要；`.xlsx` 和 `.csv` 会自动推断。
- `data.rows`：可选的已归一化二维数据；CSV 未提供时从文件读取。XLSX API-only 必填，避免在编辑链路中引入浏览器 Office renderer。

## 标准 Workflow

### 1. 插入一张新图表

适用于用户说“在这里插入一张图表 / 根据这些数据生成图表”。
1. 选择合适模板。
2. 给新图表指定稳定 `nodeId`，便于后续同批更新。
3. 使用 `insert_data2chart` 插入默认图表。
4. 如有样式要求，追加 `update_data2chart_config`。
5. 如有数据，先生成 `.csv` 或 `.xlsx`，再追加 `update_data2chart_data`。

示例：

```json
{
  "operations": [
    {
      "op": "insert_data2chart",
      "position": "after",
      "target": { "nodeId": "anchor_paragraph_node" },
      "data2chart": {
        "template": "折线图",
        "width": 760,
        "height": 420,
        "nodeId": "orders_trend_chart"
      }
    },
    {
      "op": "update_data2chart_config",
      "target": { "nodeId": "orders_trend_chart" },
      "config": {
        "type": "line",
        "title": { "show": true, "text": "每日订单趋势" },
        "tooltip": { "show": true, "trigger": "axis" },
        "legend": { "show": true, "top": "85%" },
        "color": ["#486BEF", "#FFA924"]
      }
    },
    {
      "op": "update_data2chart_data",
      "target": { "nodeId": "orders_trend_chart" },
      "data": {
        "path": "/tmp/orders.csv",
        "header": ["日期", "订单量", "GMV"],
        "dimensionField": "日期",
        "numberFields": ["订单量", "GMV"]
      }
    }
  ]
}
```

### 2. 更新已有图表样式

适用于用户说“把图表标题改成... / 换成柱状图 / 改颜色 / 显示图例 / 调整坐标轴”。

1. 定位已有 `data2chart` 节点。
2. 只传需要修改的配置片段。
3. 使用 `update_data2chart_config`，不要用 `update_data2chart`。

示例：

```json
{
  "operations": [
    {
      "op": "update_data2chart_config",
      "target": { "nodeId": "existing_data2chart_node" },
      "config": {
        "type": "bar",
        "title": { "show": true, "text": "品类经营对比" },
        "color": ["#486BEF", "#82ECCD", "#FFA924"],
        "tooltip": { "show": true, "trigger": "axis" },
        "legend": { "show": true, "top": "85%" },
        "barCategoryGap": "24%",
        "barStyle": { "barBorderRadius": 4 }
      }
    }
  ]
}
```

### 3. 更新已有图表数据

适用于用户说“把这张图的数据换成... / 用这个 CSV 更新 / 根据这张表更新图表”。

1. 定位已有 `data2chart` 节点。
2. 将用户数据整理成完整 `.csv` 或 `.xlsx` 文件。
3. 明确 `header`、`dimensionField`、`numberFields`。
4. 使用 `update_data2chart_data`。

CSV 示例：

```json
{
  "operations": [
    {
      "op": "update_data2chart_data",
      "target": { "nodeId": "channel_share_chart" },
      "data": {
        "path": "/tmp/channel-share.csv",
        "header": ["渠道", "访问量", "下单量", "转化率"],
        "dimensionField": "渠道",
        "numberFields": ["下单量"]
      }
    }
  ]
}
```

XLSX 示例：

```json
{
  "operations": [
    {
      "op": "update_data2chart_data",
      "target": { "nodeId": "orders_trend_chart" },
      "data": {
        "path": "/tmp/orders.xlsx",
        "header": ["日期", "订单量", "GMV", "履约率"],
        "dimensionField": "日期",
        "numberFields": ["订单量", "GMV", "履约率"],
        "rows": [
          ["2026-07-27", 143, 4210, 0.982],
          ["2026-07-28", 168, 4960, 0.987]
        ]
      }
    }
  ]
}
```

临时文件没有扩展名时，必须提供上传文件名：

```json
{
  "operations": [
    {
      "op": "update_data2chart_data",
      "target": { "nodeId": "orders_trend_chart" },
      "data": {
        "file": {
          "path": "/tmp/raw-data",
          "name": "orders.csv"
        },
        "header": ["日期", "订单量"],
        "dimensionField": "日期",
        "numberFields": ["订单量"]
      }
    }
  ]
}
```

### 4. 同时更新数据和样式

推荐顺序：

1. `update_data2chart_config`
2. `update_data2chart_data`

如果是新图表：

1. `insert_data2chart`
2. `update_data2chart_config`
3. `update_data2chart_data`

数据更新会根据新文件字段重建图表字段映射，因此放在最后更稳。

## 配置写法速查

只传需要修改的字段，不要复制整份 config。

通用：

```json
{
  "title": { "show": true, "text": "图表标题" },
  "color": ["#486BEF", "#FFA924", "#82ECCD"],
  "legend": { "show": true, "icon": "circle", "left": "center", "top": "85%" }
}
```

折线图：

```json
{
  "type": "line",
  "tooltip": { "show": true, "trigger": "axis" },
  "lineStyle": { "width": 2, "type": "solid" },
  "symbolSize": 8
}
```

柱状图：

```json
{
  "type": "bar",
  "tooltip": { "show": true, "trigger": "axis" },
  "barCategoryGap": "24%",
  "barStyle": { "barBorderRadius": 4 }
}
```

饼图：

```json
{
  "type": "pie",
  "tooltip": { "show": true, "trigger": "item" },
  "radius": [0, "62%"],
  "label": { "percent": 1, "colorTheme": "default" }
}
```

坐标轴：

```json
{
  "xAxis": {
    "name": "日期",
    "axisLabel": { "rotate": 0 }
  },
  "yGrid": {
    "splitLine": {
      "show": true,
      "lineStyle": { "type": "dashed", "color": "#D3D8E4" }
    }
  }
}
```

## 数据构造建议

- 优先生成 CSV：简单、稳定、适合 LLM 从文本/表格转换。
- 用户提供 Excel 或需要保留 Excel 工作流时使用 XLSX。
- 不要把单位写进数值单元格，例如用 `0.052` 而不是 `5.2%`，除非用户明确要求文本展示。
- 日期建议用 `YYYY-MM-DD` 字符串。
- 数值字段保持 number，不要混入中文单位。
- 饼图通常只选一个数值字段。
- 多指标趋势图可选多个数值字段。
- 如果用户给的是局部新增/修改行，Agent 应生成完整新文件后全量替换图表数据。

## 禁止做法

- 不要自己生成或伪造图表 `id`。
- 不要直接修改 KM `data2chart` attrs 来更新真实图表。
- 不要在 API-only 使用 `update_data2chart`；它只改 KM 节点 attrs、无法完成 Provider 读回。统一使用
  `update_data2chart_config` / `update_data2chart_data`。
- 不要手工改 `label.dataConfig` 字段 key；数据更新能力会处理字段映射。
- 不要把 Data2Chart 转成静态图片、普通链接、iframe、代码块或 markdown 表格。

## 成功判断

一次正确的 Data2Chart 操作应满足：

- 新图表插入后返回图表 id 和 nodeId。
- 样式更新使用 `update_data2chart_config`。
- 数据更新使用 `update_data2chart_data`。
- 文档保存成功。
- `readback.providers.data2chart` 中对应图表 `verified/configMatched/sourceMatched` 均为 `true`。
- 用户打开 KM 文档时能看到可交互 Data2Chart 图表，而不是静态替代物。
