---
name: raptorfe-dashboard-create
display_name: Raptor 自定义大盘创建
description: 快速创建 Raptor 自定义监控大盘。支持两种方式：①自然语言描述要监控的指标（如"配置美团iOS WaimaiAddress组件的crash率"），②直接粘贴 Raptor 页面链接（自动解析指标和筛选条件）。自动完成指标查找→大盘创建→Tab创建→图表配置全流程。触发词：创建大盘、新建大盘、创建raptor大盘、创建大前端大盘、创建监控大盘、帮我建个大盘、配置大盘、新建监控看板。
tags: 终端基础技术,Raptor,大前端,大盘,监控
version: 0.2.0
created: 2026-04-23
---

# Raptor 自定义大盘创建

## 目标

帮助用户快速创建 Raptor 自定义监控大盘，无需手动操作 Raptor 页面。支持自然语言描述和直接粘贴链接两种方式，自动完成指标查找、大盘创建、Tab 创建、图表配置的完整流程。

---

## 🔧 前置依赖

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 第一步：引导用户选择创建方式

当用户触发本技能时，**先介绍三种创建方式，引导用户提供配置信息**，不要直接开始执行。

向用户发送以下引导消息（原文输出，格式保持）：

---

📊 **Raptor 自定义大盘创建助手**

我支持以下 **2 种方式** 来创建大盘，请告诉我你想用哪种：

**方式一：自然语言描述**
直接描述你想监控什么，我来帮你找指标、配图表。例如：
- 「配置美团 iOS，WaimaiAddress 组件的 Crash 率和 Crash 次数」
- 「大前端白屏率指标，页面 3624e0d16e0f4c8a//pages/index/index 的趋势图」
- 「美团 Android，ffp_native 首屏时长的 TP90 趋势图」
- 「移动端美团主APP下自定义指标 fnr-ad-entrance-mv-mtnative-android，广告位字段下钻，3个值各一个趋势图」

**方式二：粘贴 Raptor 页面链接**
把你在 Raptor 上查看数据的页面 URL 直接发给我，我自动解析指标和筛选条件，一键生成大盘。支持：
- 自定义指标页面：`raptor.mws.sankuai.com/frontend/custom_key/...`
- MSC 指标页面：`raptor.mws.sankuai.com/msc/overview?shortId=...`
- 移动端端到端页面：`raptor.mws.sankuai.com/client/perf/trend?...`
- Crash 页面：`raptor.mws.sankuai.com/crash/#/crash/...`

---

另外，**大盘必须归属于某个项目（scope）**，请告诉我归属哪个项目。建议使用你自己团队的项目（如 `waimai`、`hotel` 等），如果不知道自己的项目名称或暂时没有，可以使用公共项目 **PERF**（所有人都有权限）。

---

## 第二步：收集必要信息

在用户回复后，确认以下信息是否齐全，缺少时主动询问：

| 信息 | 是否必填 | 说明 |
|------|---------|------|
| 大盘名称 | 必填 | 如未提供，根据指标内容自动生成一个合理名称并告知用户 |
| 归属项目（scope） | 必填 | 优先使用用户自己团队的项目，不知道或没有则默认 PERF |
| 指标描述 / 链接 | 必填 | 自然语言描述或 Raptor 页面 URL |
| Tab 页名称 | 可选 | 默认"默认"，多 Tab 时按内容命名 |
| 大盘描述 | 可选 | 可不填 |

---

## 第三步：指标解析

### 方式一：自然语言描述 → 指标解析

根据用户描述，判断指标类型，然后用对应 CLI 命令查找指标 ID 和维度配置。

**指标类型判断规则（与 raptorfe-allquery 一致）：**

| 用户描述关键词 | 指标类型 | 大盘 dataSource | 技术栈 |
|-------------|---------|----------------|--------|
| Crash、Crash率、ANR、ANR率、FOOM、FOOM率、CPU异常、CPU异常率、Flutter异常 | 稳定性指标 | `perf` | 移动端 |
| RCF、秒开率、白屏率、ffp_、ppf_、feedback_、大前端监控、Perf 指标 | Perf 指标 | `raptor`（指标来源：大前端监控 New） | 取决于指标 |
| 移动端端到端、移动端自定义指标、驼峰命名指标、含点号指标 | 老 Raptor 指标 | `old_raptor` | 移动端 |
| web 端、小程序端、com. 开头项目 | 老 Raptor 指标 | `old_raptor` | Raptor Web端/小程序 |

**APP 字段映射（用于 --project 和 --appkey）：**

| 用户说的 | Crash --project | Perf --appkey/--project-name | 老Raptor --app-id |
|---------|----------------|------------------------------|-----------------|
| 美团 iOS | meituan | PERF / meituan | 10 |
| 美团 Android | android_platform_monitor | PERF / android_platform_monitor | 10 |
| 点评 iOS | nova | — / nova | 1 |
| 外卖 iOS | waimai_ios | — / waimai_ios | 11 |
| 外卖 Android | meituanwaimai | — / meituanwaimai | 11 |

**各类型指标查找命令：**

```bash
# 稳定性指标 —— 直接使用，无需查 ID，metricsName 见下方「稳定性指标映射表」
# dataSource 固定为 "perf"，raptorScope 固定为 ""，methods 固定为 []
# 用 projectNames 指定 APP，不用 filters.project

# Perf 指标 —— 先搜索获取数字 ID
raptorfe perf metric search --appkey PERF --match "ffp_native"
# 返回 id 字段（数字），后续 metricsName 填这个数字

# 老 Raptor 移动端自定义指标 —— 查指标列表
raptorfe metric list --app-id 10
# 或按关键词过滤：raptorfe metric list --app-id 10 | grep "关键词"

# 老 Raptor 移动端端到端 —— 查项目和 API
raptorfe mobile project list
raptorfe mobile api get-by-project --project-id <projectId>

# 老 Raptor web/小程序 —— 查项目
raptorfe web project search --name <关键词>
raptorfe mp project list
```

**查询维度（Tag）和维度值：**

```bash
# Perf 指标维度
raptorfe perf metric get-tags --appkey PERF --metrics-name <数字ID> --metrics-type atom

# 老 Raptor 移动端自定义指标维度
raptorfe metric get-tags --app-id 10 --metric "<指标名>"

# 老 Raptor 大盘维度（用于 old_raptor 数据源的 filters）
raptorfe dashboard old-raptor tags --scope PERF --tech-stack mobile --theme performance
raptorfe dashboard old-raptor tag-values --scope PERF --tech-stack mobile --theme performance --page "<页面路径>"
```

### 方式二：Raptor 页面链接 → 指标解析

根据 URL 格式判断指标类型，从 URL 参数中提取指标和筛选条件：

**URL 类型识别：**

| URL 路径 | 指标类型 | 解析重点 |
|---------|---------|---------|
| `/frontend/custom_key/` | 老 Raptor web/小程序自定义指标 | `projectId`、`customKeyParams`（含 currentKeyId、selectedTags、selectedChartTypes） |
| `/msc/overview?shortId=` | Perf MSC 指标 | 需访问链接获取 shortId 对应的指标配置 |
| `/client/perf/trend` | 老 Raptor 移动端端到端 | `projectId`、`apiId`，对应4个指标：网络请求次数/成功率/耗时/业务成功率 |
| `/crash/#/crash/` | Crash 稳定性指标 | `filterId`、`project`、`type`（crash/anr） |

**解析后的指标配置映射：**

- 老 Raptor 移动端端到端（`/client/perf/trend`）→ `dataSource: "old_raptor"`，技术栈"移动端"
- 老 Raptor web/小程序（`/frontend/custom_key/`）→ `dataSource: "old_raptor"`，技术栈"Raptor Web端/小程序"
- Crash/ANR（`/crash/`）→ `dataSource: "raptor"`，指标来源"稳定性指标"
- Perf/MSC（`/msc/overview`）→ `dataSource: "raptor"`，指标来源"大前端监控（New）"

**默认规则：一个指标配置一个图表**（除非用户明确说多个统计方式放同一图表）。

---

## 第四步：构建图表配置

### `--metrics` JSON 格式

每个图表的 `--metrics` 是一个 JSON 数组，每项代表一条指标线：

```json
[
  {
    "metricsName": "c11725",          // 指标名称或数字ID
    "description": "白屏率 美团iOS",  // ⚠️ 必填！图表中每条线的图例名，同一图表内不能重复
    "dataSource": "raptor",           // raptor | perf | old_raptor
    "raptorScope": "PERF",            // 业务域，raptor 数据源必填
    "metricsType": "atom",            // atom | composite
    "methods": ["AVG"],               // 聚合方法
    "filters": {                      // 维度过滤（可选）
      "app": ["com.sankuai.meituan"],
      "ffp_allpage": ["003f9bc374244937//pages/order/index"]
    }
  }
]
```

> ⚠️ **`description` 是图表中每条线的图例名，同一图表内所有指标线的 `description` 必须各不相同，否则重复的线会被合并只显示一条。**
>
> **`description` 命名规则**：`<metricsName> + <区分维度>`，区分维度按优先级取：
> 1. 有 `projectNames` → 拼 APP 名，如 `"Crash率 美团iOS"`、`"Crash率 美团Android"`
> 2. 有 `filters` → 拼筛选值，如 `"白屏率 订单页"`、`"ffp_native WaimaiAddress"`
> 3. 无任何区分维度 → 加序号后缀，如 `"Crash率-1"`、`"Crash率-2"`

### 指标来源与 dataSource / metricsType 对应关系

| 指标类型 | dataSource | raptorScope | metricsType | methods |
|---------|-----------|-------------|-------------|---------|
| 稳定性指标（Crash/ANR/FOOM/CPU异常/Flutter异常） | `perf` | `""` | `composite`（服务端自动设置） | `[]` |
| Perf 指标（大前端监控 New），id 为纯数字 | `raptor` | `PERF` | **`atom`** | 如 `["AVG"]` |
| Perf 复合指标，id 为 `c` 开头 | `raptor` | `PERF` | **`composite`** | 如 `["AVG"]` |
| 老 Raptor 移动端 | `old_raptor` | 对应业务域 | — | — |
| 老 Raptor Web/小程序 | `old_raptor` | 对应业务域 | — | — |

> **Perf 指标 metricsType 判断规则**：`perf metric search` 返回的 `id` 是纯数字（如 `98468`）→ `atom`；`id` 是 `c` 开头（如 `c11725`）→ `composite`。

### 稳定性指标完整映射表

稳定性指标不走 `raptor` 数据源，走独立的 `perf` 数据源，配置格式固定：

```json
{
  "metricsName": "<见下表>",
  "dataSource": "perf",
  "raptorScope": "",
  "isCrashMetrics": true,
  "projectNames": ["<APP标识>"],
  "methods": [],
  "filters": null
}
```

| 用户说的 | metricsName | validAlarmErrorTypes |
|---------|------------|---------------------|
| Crash次数 | `Crash` | `["crash"]` |
| Crash率 | `Crash率` | `["crash"]` |
| ANR次数 | `ANR` | `["anr"]` |
| ANR率 | `ANR率` | `["anr"]` |
| FOOM次数 | `Foom` | `["watchdog"]` |
| FOOM率 | `FOOM率` | `["watchdog"]` |
| CPU异常次数 | `CPU异常` | `["generalException"]` |
| CPU异常率 | `CPU异常率` | `["generalException"]` |
| Flutter异常次数 | `Flutter` | `["fmp"]` |
| Flutter异常率 | `Flutter异常率` | `["fmp"]` |

> ⚠️ **注意**：`metricsName` 大小写和中文必须与上表完全一致，例如 FOOM次数是 `Foom`（首字母大写其余小写），不是 `FOOM`。`validAlarmErrorTypes` 由服务端根据 `metricsName` 自动填充，CLI 传入时可省略，传错了服务端会覆盖。

### 常用 methods（聚合方式）

| 用户说的 | methods 值 |
|---------|-----------|
| 平均值、均值 | `["AVG"]` |
| TP90、P90 | `["TP90"]` |
| TP99、P99 | `["TP99"]` |
| 总量、次数、COUNT | `["COUNT"]` |
| 去重数 | `["distinct-count"]` |
| 多种统计方式 | `["AVG", "COUNT"]` 等 |

### 单位配置（--unit，可选）

```json
// 百分比（需乘100）
{"type":"percent","subOption":"multiply_100","conversion":"multiply_100","displayText":"百分比 - 需乘100做转换"}

// 毫秒
{"type":"ms","displayText":"毫秒"}

// 次数（无需单位配置，可省略）
```

---

## 第五步：执行创建流程

### 完整创建步骤

```bash
# Step 1：创建大盘（同时设置管理员为创建人）
# ⚠️ 必须通过 --admins 把当前用户的 MIS 账号加入管理员，否则大盘无法编辑
# 当前用户 MIS 账号获取优先级：环境变量 ME2B_MOA_MIS_ID > whoami > 询问用户
# 先执行：echo $ME2B_MOA_MIS_ID 获取 MIS 账号，若为空则执行 whoami
raptorfe dashboard create \
  --name "<大盘名称>" \
  --scope <PERF或其他项目> \
  --admins "<用户MIS账号>" \
  --desc "<描述（可选）>"
# ⚠️ 记录返回的大盘 ID（dashboardId）

# Step 2：查询大盘默认 Tab，准备后续删除
# 大盘创建后系统会自动生成一个名为"第一个Tab页"的默认 Tab，需要在创建完自己的 Tab 后删除
raptorfe dashboard get --id <dashboardId>
# 记录默认 Tab 的 id（tabs[0].id）

# Step 3：创建业务 Tab 页
raptorfe dashboard tab create \
  --dashboard-id <dashboardId> \
  --name "<Tab名称>"
# ⚠️ 记录返回的 Tab ID（tabId）

# Step 4a：添加单个图表
raptorfe dashboard chart add \
  --dashboard-id <dashboardId> \
  --tab-id <tabId> \
  --name "<图表名称>" \
  --metrics '<JSON数组>' \
  --unit '<单位JSON（可选）>'

# Step 4b：批量添加多个图表（推荐，图表数 >= 2 时使用）
# 先将图表配置写入临时 JSON 文件，再批量添加
raptorfe dashboard chart add-batch \
  --dashboard-id <dashboardId> \
  --tab-id <tabId> \
  --file /tmp/charts_<dashboardId>.json

# Step 5：尝试删除系统默认的空白 Tab 页
# ⚠️ 当前后端对 tab remove 返回 HTTP 405，CLI 无法删除，执行后若报错请跳过
# 最终在输出结果中提示用户手动到大盘页面删除"第一个Tab页"
raptorfe dashboard tab remove \
  --dashboard-id <dashboardId> \
  --tab-id <默认TabId> \
  || true  # 405 报错时忽略，继续后续步骤

# Step 6：验证结果
raptorfe dashboard get --id <dashboardId>
```

### 批量图表 JSON 文件格式

```json
[
  {
    "name": "Crash率（美团iOS & Android）",
    "type": 0,
    "metricsList": [
      {
        "metricsName": "Crash率",
        "description": "Crash率 美团iOS",
        "dataSource": "perf",
        "raptorScope": "",
        "isCrashMetrics": true,
        "projectNames": ["meituan"],
        "methods": [],
        "filters": null
      },
      {
        "metricsName": "Crash率",
        "description": "Crash率 美团Android",
        "dataSource": "perf",
        "raptorScope": "",
        "isCrashMetrics": true,
        "projectNames": ["android_platform_monitor"],
        "methods": [],
        "filters": null
      }
    ],
    "chartConfig": {
      "isFromYZero": false,
      "lastPeriods": []
    }
  },
  {
    "name": "ffp_native TP90",
    "type": 0,
    "metricsList": [
      {
        "metricsName": "98468",
        "description": "ffp_native TP90",
        "dataSource": "raptor",
        "raptorScope": "PERF",
        "metricsType": "atom",
        "methods": ["TP90"],
        "filters": null
      }
    ],
    "chartConfig": {
      "isFromYZero": false,
      "lastPeriods": []
    }
  }
]
```

### 多 Tab 大盘

如果用户需要多个 Tab（如 Android/iOS 分开），对每个 Tab 重复 Step 3 + Step 4，最后统一执行 Step 5 删除默认 Tab：

```bash
# Tab 1
raptorfe dashboard tab create --dashboard-id <id> --name "Android"
raptorfe dashboard chart add-batch --dashboard-id <id> --tab-id <tabId1> --file /tmp/charts_android.json

# Tab 2
raptorfe dashboard tab create --dashboard-id <id> --name "iOS"
raptorfe dashboard chart add-batch --dashboard-id <id> --tab-id <tabId2> --file /tmp/charts_ios.json

# 最后尝试删除默认 Tab（后端当前返回 405，失败则跳过，提示用户手动删）
raptorfe dashboard tab remove --dashboard-id <id> --tab-id <默认TabId> || true
```

---

## 第六步：输出结果

创建完成后，输出以下内容：

```
✅ 大盘创建成功！

📊 大盘名称：<名称>
🔗 访问链接：https://raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=<dashboardId>
📁 归属项目：<scope>

Tab 页：
  - <Tab名称>（<图表数>个图表）
    - <图表1名称>：<指标描述>
    - <图表2名称>：<指标描述>
    ...

⚠️ 还有一步需要手动操作：大盘默认会带一个空白的「第一个Tab页」，CLI 暂时无法自动删除（后端返回 405）。请打开大盘链接，在 Tab 栏找到「第一个Tab页」，手动将其删除。
```

> ⚠️ 访问链接格式固定为 `https://raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=<id>`，不要使用旧格式 `/dashboard/<id>`。

---

## 典型场景示例

### 场景 A：Crash 稳定性指标（自然语言）

用户：「配置美团 iOS，WaimaiAddress 组件的 Crash 率和 Crash 次数」

解析：
- 指标类型：稳定性指标 → `dataSource: "perf"`，`projectNames: ["meituan"]`
- 组件过滤：WaimaiAddress（通过 `filters` 的 `default_component` 字段）
- 图表1：Crash率；图表2：Crash次数

```bash
# 先获取 MIS 账号（优先环境变量，其次 whoami）
MIS_ID=$(echo $ME2B_MOA_MIS_ID); [ -z "$MIS_ID" ] && MIS_ID=$(whoami)
raptorfe dashboard create --name "美团iOS WaimaiAddress Crash监控" --scope PERF --admins "$MIS_ID"
# 记录 dashboardId 和默认 tabId
raptorfe dashboard tab create --dashboard-id <id> --name "Crash监控"
# 写入 charts.json 后批量添加
raptorfe dashboard chart add-batch --dashboard-id <id> --tab-id <tabId> --file /tmp/charts.json
# 删除默认 Tab
raptorfe dashboard tab remove --dashboard-id <id> --tab-id <默认tabId>
```

charts.json 示例：
```json
[
  {
    "name": "WaimaiAddress Crash率",
    "type": 0,
    "metricsList": [{
      "metricsName": "Crash率",
      "dataSource": "perf",
      "raptorScope": "",
      "isCrashMetrics": true,
      "projectNames": ["meituan"],
      "methods": [],
      "filters": {"default_component": ["WaimaiAddress"]}
    }],
    "chartConfig": {"isFromYZero": false, "lastPeriods": []}
  },
  {
    "name": "WaimaiAddress Crash次数",
    "type": 0,
    "metricsList": [{
      "metricsName": "Crash",
      "dataSource": "perf",
      "raptorScope": "",
      "isCrashMetrics": true,
      "projectNames": ["meituan"],
      "methods": [],
      "filters": {"default_component": ["WaimaiAddress"]}
    }],
    "chartConfig": {"isFromYZero": false, "lastPeriods": []}
  }
]
```

### 场景 B：Perf 指标（自然语言）

用户：「配置美团 Android，ffp_native 首屏时长的 TP90 趋势图」

解析：
- 指标类型：Perf 指标 → 先搜索 ID，`metricsType: "atom"`
- `raptorfe perf metric search --appkey PERF --match "ffp_native"` → 获取数字 ID
- methods：TP90

### 场景 C：维度下钻多图表（自然语言）

用户：「移动端美团主APP下自定义指标 fnr-ad-entrance-mv-mtnative-android，广告位字段下钻，广告位有3个值，每个值一个趋势图」

解析：
1. 先查维度值：`raptorfe metric get-tags --app-id 10 --metric "fnr-ad-entrance-mv-mtnative-android"`
2. 找到广告位字段的 tagId，再查可选值
3. 为每个广告位值创建一个图表，filters 中指定该值

### 场景 D：白屏率多页面（自然语言）

用户：「大前端白屏率指标，每个图表都是页面离开白屏率和页面5s类型白屏率，页面分别有3个，根据页面名称灵活设置图表标题」

解析：
- 指标：ppf_WhitePage（离开白屏率）和 ppf_WhitePage_on5s（5s白屏率）→ Perf 指标，`metricsType: "atom"`
- 3个图表，每个图表包含2条指标线，filters 中指定不同页面
- 图表标题根据页面路径最后一段命名

### 场景 E：Raptor 链接解析

用户粘贴：`https://raptor.mws.sankuai.com/client/perf/trend?projectId=3998&apiId=36658`

解析：
- URL 类型：移动端端到端 → `old_raptor`
- 提取 projectId=3998，apiId=36658
- 默认配置4个图表：网络请求次数、网络成功率、网络请求耗时、业务成功率

---

## 注意事项

**鉴权**：与 raptorfe-allquery 相同，CLI 内置自动 SSO 鉴权，无需手动传 Cookie。命令执行后可能沉默 10～30 秒，属正常现象。

**指标 ID**：Perf 指标的 metricsName 是数字 ID（从 `perf metric search` 获取），不是指标名称字符串。稳定性指标和老 Raptor 指标直接填名称字符串。

**metricsType**：Perf 指标中 id 为纯数字的填 `atom`，id 为 `c` 开头的填 `composite`。稳定性指标的 `metricsType` 由服务端自动覆盖，传什么都行。

**稳定性指标**：`dataSource` 是 `"perf"`，不是 `"raptor"`。用 `projectNames` 指定 APP，不用 `filters.project`。`metricsName` 必须与映射表完全一致（注意大小写，如 FOOM次数是 `Foom` 不是 `FOOM`）。

**管理员**：`dashboard create` 时必须通过 `--admins` 传入当前用户 MIS 账号，否则大盘创建后无法编辑。MIS 账号获取优先级：先执行 `echo $ME2B_MOA_MIS_ID` 获取环境变量，若为空则执行 `whoami`，两者都为空时才询问用户。

**默认 Tab 清理**：大盘创建后系统自动生成一个"第一个Tab页"的空白 Tab。当前后端对 `tab remove` 接口返回 HTTP 405，CLI 无法自动删除，执行报错时直接跳过。需在最终输出中提示用户打开大盘页面手动删除"第一个Tab页"。

**访问链接**：新 Raptor 大盘链接格式为 `https://raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=<id>`，不要使用旧格式 `/dashboard/<id>`。

**scope 参数**：`dashboard create` 的 `--scope` 是项目标识（如 PERF），不是 appkey。

**临时文件清理**：批量添加图表时写入的临时 JSON 文件（如 `/tmp/charts_*.json`），在 `chart add-batch` 执行成功后删除。

**指标查找失败时**：优先调用 `raptorfe-allquery` 技能（读取 `references/raptorfe-allquery/SKILL.md`）来辅助查找指标，或直接询问用户提供更多信息。
