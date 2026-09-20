---
name: dashboard-patrol
version: "1.0.0"
description: >
  自定义大盘巡检：用户发送 Raptor 自定义大盘链接（raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=xxx），
  自动读取大盘所有 Tab 页和图表配置，批量查询最近 7 天天粒度数据，逐图表分析是否存在异常波动，
  汇总生成数据报告。若发现异常指标，自动提取该图表的指标名和筛选条件，调用 raptorfe CLI 进行多维度下钻分析，定位根因。
  触发词：巡检大盘、大盘巡检、大盘数据报告、查看大盘数据、分析大盘、大盘异常检测、自定义大盘分析。

metadata:
  skillhub.creator: "zhangxinyue27"
  skillhub.updater: "zhangxinyue27"
---

# 自定义大盘巡检

## 🔧 前置依赖

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 🎯 适用场景

**适用（触发此 skill）**：
- 用户发送 Raptor 自定义大盘链接（URL 含 `dashboardId=`）并要求巡检/分析/查看数据
- 用户说"帮我看看这个大盘最近的数据"、"巡检一下大盘"、"大盘有没有异常"

**不适用（不要触发此 skill）**：
- 用户要**创建**大盘 → 使用 `raptorfe-dashboard-create`
- 用户要查询某个具体指标的数据 → 使用 `raptorfe-allquery`
- 用户发送的是 Crash/性能/FFP 大盘链接（非自定义大盘）→ 使用对应分析子技能

---

## 第零步：提取 dashboardId

从用户发送的链接中提取 `dashboardId` 参数：

```
https://raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=120
                                                                              ^^^
                                                                          dashboardId = 120
```

---

## 第一步：获取大盘完整配置

```bash
raptorfe dashboard get --id <dashboardId> -o json > /tmp/dashboard_<dashboardId>.json
```

从返回的 JSON 中解析以下信息：

| 字段 | 路径 | 说明 |
|------|------|------|
| 大盘名称 | `data.name` | 展示用 |
| 默认时间范围 | `data.timePicker` | JSON 字符串，含 `agg`（day/hour）和 `hoursFromNow` |
| Tab 列表 | `data.tabs[]` | 每个 tab 含 `id`、`name`、`blockList` |
| 图表列表 | `data.tabs[].blockList[]` | 每个 block 含 `id`、`name`、`metricsList`、`chartConfig` |

**图表关键字段提取**（每个 `blockList` 中的 block）：

```
block.id              → 图表 ID
block.name            → 图表标题
block.metricsList[]   → 指标配置列表（一个图表可能有多条指标线）
  .metricsName        → 指标名（c 开头 = composite 复合指标；纯数字 = atom 原子指标）
  .metricsType        → 仅供参考，以 metricsName 前缀为准（c 开头一律用 composite）
  .filters            → 维度过滤条件，JSON 对象，如 {"ffp_allpage": ["WMHomeContainerViewController"]}
  .methods            → 聚合方法，如 ["AVG"]
block.chartConfig.unit → 单位配置（JSON 字符串），含 displayText 和 conversion 字段
```

**单位换算规则**（从 `chartConfig.unit` 的 `conversion` 字段读取）：

| conversion 值 | 展示换算 | 说明 |
|--------------|---------|------|
| `multiply_1000` | 原始值 × 1000 | 千分比，如 0.001562 → 1.562‰ |
| `multiply_100` | 原始值 × 100 | 百分比，如 0.0156 → 1.56% |
| 无 / 其他 | 原始值不变 | 直接展示 |

---

## 第二步：确定巡检时间范围

**默认使用最近 7 天天粒度**（无论大盘 timePicker 配置如何）：

```python
from datetime import date, timedelta
end_date = date.today() - timedelta(days=1)   # 昨天（最新完整数据）
start_date = end_date - timedelta(days=6)      # 往前 7 天
# 格式：YYYY-MM-DD
```

> 若用户明确指定了时间范围，以用户指定为准。

---

## 第三步：批量查询所有图表数据

对每个 Tab 页的每个图表，逐一查询最近 7 天数据。

**查询命令模板**：

```bash
# c 开头（composite 复合指标）
raptorfe perf metric get-trend \
  --metrics-name <metricsName> \
  --metrics-type composite \
  --agg DAY \
  --start-time "<start_date>" \
  --end-time "<end_date>" \
  --methods <methods_lower> \
  --filters '<filters_json>'

# 纯数字（atom 原子指标）
raptorfe perf metric get-trend \
  --metrics-name <metricsName> \
  --metrics-type atom \
  --agg DAY \
  --start-time "<start_date>" \
  --end-time "<end_date>" \
  --methods <methods_lower> \
  --filters '<filters_json>'
```

**参数处理规则**：

- `metricsName`：直接取 `metricsList[].metricsName`
- `metrics-type`：metricsName 以 `c` 开头 → `composite`；纯数字 → `atom`
- `methods_lower`：将 `metricsList[].methods` 转为小写，如 `["AVG"]` → `avg`
- `filters_json`：将 `metricsList[].filters` 序列化为 JSON 字符串，如 `'{"ffp_allpage":["WMHomeContainerViewController"]}'`；若 filters 为空则不传 `--filters` 参数

> ⚠️ 一个图表若有多条指标线（metricsList 有多个元素），需分别查询每条线的数据。

**效率优化**：Tab 页之间可并行查询；同一 Tab 内图表较多时，按顺序查询并实时输出结果，不要等全部完成再展示。

---

## 第四步：逐图表分析，识别异常波动

查询完每个图表的数据后，立即进行异常判断，**不要等所有图表都查完再分析**。

### 异常判断规则

**规则 1：单日突增/突降（尖刺）**

```
任意一天的值 > 7天均值 × 1.3（上涨 30%）
任意一天的值 < 7天均值 × 0.7（下降 30%）
```

**规则 2：持续上升趋势（连续恶化）**

```
最近 3 天的均值 > 前 4 天的均值 × 1.2（持续上涨 20%）
```

**规则 3：持续下降趋势（连续改善或恶化，视指标方向）**

```
最近 3 天的均值 < 前 4 天的均值 × 0.8（持续下降 20%）
```

> 对于白屏率、异常率等"越低越好"的指标：上涨是异常，下降是正常改善。
> 对于秒开率等"越高越好"的指标：下降是异常，上涨是正常改善。
> 根据大盘名称和图表名称判断指标方向（含"率"、"异常"、"白屏"等词 → 越低越好）。

**规则 4：数据缺失**

```
7 天内有 2 天以上无数据（value 为 null 或接口返回空）→ 标记为"数据缺失"
```

### 异常等级

| 等级 | 标志 | 判断条件 |
|------|------|---------|
| 🔴 严重 | CRITICAL | 单日突增/突降超过 50%，或持续 3 天以上恶化 |
| 🟡 警告 | WARNING | 单日突增/突降 30%~50%，或持续 2 天恶化 |
| 🟢 正常 | NORMAL | 波动在 30% 以内 |
| ⚪ 缺失 | MISSING | 数据缺失 |

---

## 第五步：生成数据报告

所有图表查询和分析完成后，输出完整的数据报告，格式如下：

---

### 📊 大盘巡检报告：`<大盘名称>`

**巡检时间**：`<start_date>` ~ `<end_date>`（最近 7 天，天粒度）
**大盘链接**：`https://raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=<id>`
**异常汇总**：🔴 严重 `N` 个 | 🟡 警告 `N` 个 | 🟢 正常 `N` 个 | ⚪ 缺失 `N` 个

---

#### Tab：`<tab名称>`

| 图表 | 指标 | 7天均值 | 最大值 | 最小值 | 趋势 | 状态 | 备注 |
|------|------|--------|--------|--------|------|------|------|
| 外卖首页-iOS | c11792（白屏率） | 1.56‰ | 1.69‰ | 1.48‰ | ↗ | 🟡 WARNING | 4/27 较均值上涨 8.4% |
| 外卖首页-Android | c11725（白屏率） | 0.82‰ | 0.95‰ | 0.71‰ | → | 🟢 NORMAL | 波动正常 |

> 数值展示时按 `chartConfig.unit` 的换算规则转换后展示（如 × 1000 后加 ‰，× 100 后加 %）。

---

（每个 Tab 一个表格，依次输出）

---

### 🔴 异常指标汇总

列出所有状态为 CRITICAL 或 WARNING 的图表，格式：

```
1. [🔴 CRITICAL] Tab: 外卖主站业务 | 图表: 外卖首页-iOS
   指标: c11792（白屏率）| 过滤: ffp_allpage=WMHomeContainerViewController
   异常: 4/27 值 1.69‰，较 7 天均值 1.56‰ 上涨 8.4%
   → 建议下钻分析

2. [🟡 WARNING] Tab: H5-KNB白屏 | 图表: 神抢手-券详评价二级页-Android
   指标: c11734 | 过滤: 无
   异常: 4/24、4/26 值约 0.211，较正常值 0.008 异常偏高（疑似数据问题）
   → 建议下钻分析
```

---

## 第六步：异常指标下钻分析

**触发条件**：报告中存在 CRITICAL 或 WARNING 级别的异常图表。

输出报告后，询问用户：

> 发现 `N` 个异常指标，是否对以上异常指标进行多维度下钻分析？

**若用户选择"是"（或用户在发送链接时已说"分析"）**，对每个异常图表执行以下下钻流程：

### 下钻流程

#### 1. 查询该指标支持的维度列表

```bash
raptorfe perf metric get-tags \
  --metrics-name <metricsName> \
  --metrics-type <composite|atom>
```

#### 2. 按优先维度逐一下钻

推荐下钻维度优先级（根据实际支持的维度选择）：

| 优先级 | 维度 | 说明 |
|--------|------|------|
| 1 | `appVersion` | 判断是否某版本引入 |
| 2 | `ffp_allpage` / `pageId` | 页面级定位（若图表已按页面过滤，跳过此维度） |
| 3 | `app` | 区分 App（美团/外卖/点评） |
| 4 | `deviceLevel` | 排查低端机问题 |
| 5 | `networkType` | 排查网络环境问题 |

```bash
# ATOM 指标（纯数字 ID）直接下钻：
raptorfe perf metric dimension-analyse \
  --metrics-name <metricsName> \
  --metrics-type atom \
  --agg DAY \
  --start-time "<start_date>" \
  --end-time "<end_date>" \
  --tag-names "<维度名>" \
  --methods avg \
  --filters '<原始filters_json>'
```

> ⚠️ **COMPOSITE 指标（c 前缀 ID）不能直接做 dimension-analyse**，会返回空数据。必须先用 `get-compound-detail` 获取 atom 子指标 ID：
>
> ```bash
> # 1. 获取复合指标的子指标详情
> raptorfe perf metric get-compound-detail --appkey PERF --metric-ids <c开头的ID>
> # 返回 expression 和每个子指标的 atom metricId
>
> # 2. 用 atom 子指标 ID 做 dimension-analyse
> raptorfe perf metric dimension-analyse \
>   --metrics-name <atom_id> \
>   --metrics-type atom \
>   --agg DAY \
>   --start-time "<start_date>" \
>   --end-time "<end_date>" \
>   --tag-names "<维度名>" \
>   --methods avg \
>   --filters '<原始filters_json>' \
>   --other-metrics <composite_id>
> ```

#### 3. 识别贡献最大的维度值

对下钻结果按均值降序排列，找出 Top 3 贡献最大的维度值（对于"越低越好"的指标，均值最高的维度值是问题最严重的）。

#### 4. 继续下钻（可选）

若 Top 1 维度值的均值显著高于其他值（超过 2 倍），在该维度值的 filter 条件下继续下钻下一个维度：

```bash
# ATOM 指标直接下钻：
raptorfe perf metric dimension-analyse \
  --metrics-name <metricsName> \
  --metrics-type atom \
  --agg DAY \
  --start-time "<start_date>" \
  --end-time "<end_date>" \
  --tag-names "<下一维度>" \
  --methods avg \
  --filters '<原始filters + 新增维度值>'

# COMPOSITE 指标同理，使用 atom 子指标 ID + --other-metrics <composite_id>
```

#### 5. 输出下钻结论

```
📍 [外卖首页-iOS] 下钻分析结论：
  - 按 appVersion 下钻：8.x.x 版本白屏率 2.3‰，显著高于其他版本（均值 1.2‰）
  - 按 deviceLevel 下钻（filter: appVersion=8.x.x）：低端机（level=1）白屏率 4.1‰，高端机 1.1‰
  - 根因推断：8.x.x 版本在低端机上白屏率异常偏高，建议排查该版本低端机相关代码变更
```

---

## ⚠️ 常见注意事项

**关于 metricsType 判断**：`metricsList[].metricsType` 字段不可靠，以 `metricsName` 前缀为准：
- `c` 开头（如 `c11792`、`c11725`）→ COMPOSITE 指标，`get-trend` 用 `--metrics-type composite`；**但 `dimension-analyse` 不能直接用 composite，需先 `get-compound-detail` 拿 atom ID**
- 纯数字（如 `107582`）→ ATOM 指标，使用 `--metrics-type atom`

**关于 filters 为空的情况**：若 `metricsList[].filters` 为空对象 `{}` 或 `null`，查询时不传 `--filters` 参数。

**关于一图多线**：一个图表的 `metricsList` 可能有多个元素（多条指标线），需分别查询，分别展示在报告中（同一行用不同列区分，或拆成多行）。

**关于数据异常值**：若某天数据值远超其他天（如 100 倍以上），优先判断为数据上报异常（如采样率问题），在报告中标注"疑似数据问题"，不作为真实异常处理。

**关于 searchForm**：`tab.searchForm` 是大盘级全局筛选条件（如版本选择器），巡检时默认不加全局筛选，以图表自身的 `filters` 为准。若用户明确指定了版本等条件，将其合并到每个图表的 `filters` 中。

**关于并发查询**：图表数量较多时（超过 10 个），先输出"正在查询第 X/N 个图表..."的进度提示，避免用户等待时无反馈。

---

## 📋 CLI 命令速查

```bash
# 获取大盘完整配置（含所有 Tab 和图表）
raptorfe dashboard get --id <dashboardId>

# 查询指标趋势（天粒度）
raptorfe perf metric get-trend \
  --metrics-name <metricsName> \
  --metrics-type <composite|atom> \
  --agg DAY \
  --start-time "<YYYY-MM-DD>" \
  --end-time "<YYYY-MM-DD>" \
  --methods avg \
  --filters '<json>'

# 查询指标支持的维度列表
raptorfe perf metric get-tags \
  --metrics-name <metricsName> \
  --metrics-type <composite|atom>

# 获取复合指标的子指标详情（composite → atom 映射）
raptorfe perf metric get-compound-detail --appkey PERF --metric-ids <c开头的ID>

# 维度下钻分析（仅支持 atom 指标）
raptorfe perf metric dimension-analyse \
  --metrics-name <atom_metricsName> \
  --metrics-type atom \
  --agg DAY \
  --start-time "<YYYY-MM-DD>" \
  --end-time "<YYYY-MM-DD>" \
  --tag-names "<维度名>" \
  --methods avg \
  --filters '<json>' \
  --other-metrics <composite_id>   # 可选，传入 composite ID 同时返回复合值
```
