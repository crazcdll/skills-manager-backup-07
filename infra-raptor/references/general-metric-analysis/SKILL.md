---
name: general-metric-analysis
display_name: 通用指标下钻分析
description: >
  对通用类指标（移动端端到端、移动端自定义指标、Perf 指标、Web 端指标、小程序指标）进行多维度下钻分析，定位波动根因。支持两种触发方式：①用户自然语言描述要分析的指标；②用户直接发送 Raptor 页面链接并提出分析诉求。优先下钻版本号、页面等维度，逐步缩小问题范围。不处理 RCF 指标（由 rcf-raptor-anylisize 子技能处理）和稳定性指标 Crash/ANR/FOOM（由 crash-wave-analysis 子技能处理）。触发词：分析指标波动、分析网络成功率、分析耗时、分析性能、分析自定义指标、分析Perf指标、分析web指标、分析小程序指标、指标下钻、根因分析、波动分析。
tags: 终端基础技术,Raptor,指标分析,下钻分析,性能,端到端
version: 0.2.0
created: 2026-04-28
metadata:
  skillhub:
    creator: zhangxinyue27
---

# 通用指标下钻分析

## 目标

对用户指定的通用类指标进行多维度下钻分析，找到波动根因维度。支持一次分析多个指标。

---

## 🔧 前置依赖

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 触发判断与排除

**本技能处理的指标类型：**
- 移动端端到端指标（网络请求量/成功率/耗时/业务成功率）
- 移动端自定义指标（驼峰命名或含点号的指标 key）
- Perf 指标（ffp_、ppf_、feedback_ 等大前端监控指标）
- Web 端性能/自定义指标
- 小程序性能/自定义指标

**以下情况不触发本技能，转交对应子技能：**
- RCF 相关指标 → 读取并执行 `references/rcf-raptor-anylisize/SKILL.md`
- Crash、ANR、FOOM 等稳定性指标 → 读取并执行 `references/stability-wave-analysis/SKILL.md`

---

## 第一步：解析用户输入，确认分析参数

### 场景 A：自然语言描述

从用户描述中提取：
- **指标类型**：参考下方「指标类型判断规则」
- **项目/APP**：如"banma_all"、"美团iOS"、"外卖小程序"等
- **指标名称/接口路径**：如 `peisongapi.meituan.com/v1/user/uploadusercoordinate`、`fnr-ad-entrance-mv-mtnative-android`
- **分析指标**：如"网络成功率"、"耗时 TP90"、"自定义指标均值"
- **时间范围**：用户未指定时默认最近 7 天

### 场景 B：Raptor 页面链接

解析 URL 参数，提取指标配置：

| URL 路径特征 | 指标类型 | 关键参数 |
|------------|---------|---------|
| `/client/perf/trend` | 移动端端到端 | `projectId`、`apiId`、`view`、`start`/`end` |
| `/client/perf/metric` | 移动端自定义指标 | `projectId`（即 appId）、`metricKey`、`start`/`end` |
| `/frontend/custom_key/` | Web/小程序自定义指标 | `projectId`、`customKeyParams` |
| `/frontend/speed/` 或 `/frontend/perf/` | Web 端性能 | `projectId`、`pageId`、`speedPoint`、`start`/`end` |
| `/msc/overview?shortId=` | Perf MSC 指标 | `shortId`（需访问链接获取指标配置） |
| `/perf/` 或 Perf 平台链接 | Perf 指标 | `metricsName`（数字 ID）、`start`/`end` |

**时间参数解析：**
- URL 中 `start=20260421000000` 格式 → 解析为 `2026-04-21 00:00:00`
- URL 中 `startLong=<ms>` 格式 → 直接使用毫秒时间戳（也可转为日期字符串）

### 指标类型判断规则

| 用户描述关键词 | 指标类型 | 使用命令族 |
|-------------|---------|----------|
| 端到端、接口成功率、网络成功率、业务成功率、接口耗时、请求量、`/client/perf/trend` | 移动端端到端 | `raptorfe mobile` |
| 移动端自定义指标、驼峰命名指标（如 `fnr-ad-entrance`）、含点号指标（如 `bizpay.sdk.load`）、`/client/perf/metric` | 移动端自定义指标 | `raptorfe metric` |
| ffp_、ppf_、feedback_、大前端监控、Perf 指标、秒开率、白屏率、`/msc/overview` | Perf 指标 | `raptorfe perf metric` |
| web 端、H5、前端性能、页面加载、`/frontend/speed/`、`/frontend/perf/` | Web 端性能 | `raptorfe web speed` |
| web 自定义指标、`/frontend/custom_key/`（非小程序） | Web 自定义指标 | `raptorfe web custom-metric` |
| 小程序、mp、`com.` 开头项目、`/frontend/custom_key/`（小程序项目） | 小程序指标 | `raptorfe mp` |

**如果一次输入包含多个指标，对每个指标分别执行完整的下钻分析流程。**

---

## 第二步：查找指标 ID 与项目信息

在开始分析前，先确认指标 ID 和项目 ID。

### 移动端端到端

```bash
# 1. 查项目列表（如不知道 projectId）
raptorfe mobile project list

# 2. 查项目下的 API 列表（找到 apiId）
raptorfe mobile api get-by-project --project-id <projectId>

# 3. 查 App 来源枚举（确认 --source 参数值）
raptorfe mobile app list
# 返回中找到对应 APP 的 id，如美团主APP=10，外卖=11，点评=1
```

> **注意：** `raptorfe mobile app get-const` 返回的版本/网络/城市枚举仅适用于美团主 APP（appId=10）等标准 APP，对于 `banma_all` 等特殊项目，版本枚举可能为空或不适用，此时跳过版本维度下钻，直接从平台、网络类型等维度入手。

### 移动端自定义指标

```bash
# 1. 查指标列表（找到 metricKey）
raptorfe metric list --app-id <appId>
# 常用 appId：10=美团主APP，11=外卖，1=点评

# 2. 查指标支持的下钻维度（获取 tagId）
raptorfe metric get-tags --app-id <appId> --metric <metricKey>
```

### Perf 指标

```bash
# 1. 搜索指标 ID（获取数字 ID）
raptorfe perf metric search --appkey PERF --match "<指标名关键词>"

# 2. 查指标支持的下钻维度
raptorfe perf metric get-tags --appkey PERF --metrics-name <数字ID>
# 或查维度分组
raptorfe perf metric get-tag-groups --appkey PERF --metrics-name <数字ID>
```

> ❗ **projectName 参数映射规则：** 当查询参数中 `projectName` 出现在顶层（不在 filters 内）时，必须通过 `--project-name` 参数传入 CLI。CLI 会自动将其合并到 filters.projectName 中。例如查询参数为 `{"projectName":"LongCat-Android", "filters":[{"tagName":"appVersion","tagValues":["1.10.5"]}]}` 时，应传 `--project-name LongCat-Android --filters '{"appVersion":["1.10.5"]}'`。

### Web 端性能

```bash
# 1. 搜索项目（找到 projectId）
raptorfe web project search --name "<项目名关键词>"

# 2. 查页面列表（找到 pageId）
raptorfe web page list --project-id <projectId>

# 3. 查测速点列表（找到 speedPointId）
raptorfe web speed-point list --project-id <projectId>

# 4. 查版本列表
raptorfe web version list --project-id <projectId>
```

### Web 自定义指标

```bash
# 1. 查自定义指标列表（找到 metricKey）
raptorfe web custom-metric list --project-id <projectId>

# 2. 查指标支持的 tag（下钻维度）
raptorfe web custom-metric get-tags --project-id <projectId> --metric-key <key>
```

### 小程序指标

```bash
# 1. 查项目列表
raptorfe mp project list

# 2. 查小程序维度枚举
raptorfe mp meta --project-id <projectId>
```

---

## 第三步：执行多维度下钻分析

**分析原则：每个维度查询完成后立即展示结果并给出初步判断，不要等所有维度都查完再输出。**

下钻优先级：**版本号 > 页面 > 平台（iOS/Android）> 网络类型 > 地区/城市 > 其他业务维度**

---

### 3.1 整体趋势（基线）

先查整体趋势，确认波动的时间范围和幅度。

#### 移动端端到端

```bash
# 查网络成功率趋势（按天）
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId>

# 查请求量趋势
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type request --source <appSourceId>

# 查耗时趋势
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type delay --source <appSourceId>

# 查业务成功率趋势（如有）
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type businessSuccess --source <appSourceId>
```

#### 移动端自定义指标

```bash
raptorfe metric get-trend \
  --app-id <appId> --metric-key <metricKey> \
  --start-str "<YYYY-MM-DD HH:MM>" --end-str "<YYYY-MM-DD HH:MM>" \
  --types COUNT,AVG
```

#### Perf 指标

```bash
raptorfe perf metric get-trend \
  --metrics-name <数字ID> --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --metrics-type <atom|composite> \
  --methods avg,totalCount,tp90 \
  --project-name <项目名，如有>
```

> 如果查询参数中包含顶层 `projectName` 字段，必须通过 `--project-name` 传入，否则数据不会按项目筛选。

#### Web 端性能

```bash
raptorfe web speed get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --type DAILY --metric TP90 \
  --speed-point "<speedPointId>"
```

#### Web 自定义指标

```bash
raptorfe web custom-metric get-trend \
  --project-id <projectId> --metric-key <key> \
  --start-str "<YYYY-MM-DD HH:MM>" --end-str "<YYYY-MM-DD HH:MM>" \
  --types COUNT,AVG
```

#### 小程序性能

```bash
raptorfe mp speed get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --type DAILY --metric TP90 \
  --speed-point <speedPointId>
```

**分析要点：**
- 标记波动的起始时间点和幅度
- 判断是突发型（某天骤降/骤升）还是趋势型（持续恶化）
- 记录波动时间点，后续各维度分析聚焦该时间段

---

### 3.2 版本维度下钻（优先）

**目的：判断波动是否集中在某个 App 版本或 Web 版本。**

> **前置判断：** 若第二步中 `raptorfe mobile app get-const` 对该项目返回空版本列表，则跳过本节，直接进入 3.3 平台维度。

#### 移动端端到端（按版本下钻）

```bash
# 按版本下钻（--group-by-field version）
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --group-by-field version
```

#### 移动端自定义指标（按版本下钻）

```bash
# 先查版本对应的 tagId
raptorfe metric get-tags --app-id <appId> --metric <metricKey>
# 找到 tagName 包含"版本"或"version"的 tagId

# 按版本分组查询
raptorfe metric get-trend \
  --app-id <appId> --metric-key <metricKey> \
  --start-str "<YYYY-MM-DD HH:MM>" --end-str "<YYYY-MM-DD HH:MM>" \
  --types COUNT,AVG \
  --group-by '{"appId":<appId>,"metricKey":"<metricKey>","tagId":<versionTagId>}'
```

#### Perf 指标（按版本下钻）

```bash
# 原子指标：直接下钻
raptorfe perf metric dimension-analyse \
  --metrics-name <数字ID> --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "appVersion" \
  --metrics-type atom \
  --methods avg,totalCount,tp90 \
  --project-name <项目名，如有>

# 复合指标（c 开头）：必须用对应原子指标 + --other-metrics
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "appVersion" \
  --methods avg,totalCount \
  --project-name <项目名，如有> \
  --limit 20
```

> ⚠️ **复合指标（c 开头 ID）不能直接做 `dimension-analyse`，会返回空数据！** 必须找到其对应的原子指标，用原子指标做 `dimension-analyse` 并通过 `--other-metrics` 附带复合指标 ID。返回结果中每个维度值同时包含原子指标数据和复合指标值。

#### Web 端（按版本下钻）

```bash
raptorfe web speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by version
```

#### 小程序（按版本下钻）

```bash
raptorfe mp speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by version
```

**分析要点：**
- 列出各版本的指标值，识别异常版本
- 若某版本明显异常，后续分析聚焦该版本
- 结合整体趋势时间点，判断异常版本的上线时间

---

### 3.3 平台维度下钻（iOS / Android / HarmonyOS）

**目的：判断波动是否只影响特定平台。**

#### 移动端端到端（按平台下钻）

```bash
# iOS
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --platforms 2

# Android
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --platforms 1
```

#### Web 端（按 OS 下钻）

```bash
raptorfe web speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by os
```

#### 小程序（按 OS 下钻）

```bash
raptorfe mp speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by os
```

**分析要点：**
- 对比 iOS 和 Android 的指标差异
- 若只有某平台异常，缩小排查范围

---

### 3.4 页面维度下钻（Web / 小程序适用）

**目的：判断波动是否集中在某个页面或接口路径。**

#### Web 端（按页面下钻）

```bash
# 查各页面的性能汇总
raptorfe web speed get-summary \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId>

# 对异常页面单独查趋势
raptorfe web speed get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --type DAILY --metric TP90 \
  --page-id <pageId> \
  --speed-point "<speedPointId>"
```

#### 小程序（按页面下钻）

```bash
raptorfe mp speed get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --type DAILY --metric TP90 \
  --page-id <pageId> \
  --speed-point <speedPointId>
```

**分析要点：**
- 识别指标最差的 Top 页面
- 对比各页面趋势，判断是全局波动还是特定页面问题

---

### 3.5 网络类型维度下钻

**目的：判断波动是否与网络环境相关（WiFi vs 4G/5G）。**

#### 移动端端到端

```bash
# 按网络类型下钻（--networks 参数值从 raptorfe mobile app get-const 获取）
# 常见：1=WiFi, 2=4G, 3=5G

# WiFi
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --networks 1

# 4G
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --networks 2
```

#### Web 端

```bash
raptorfe web speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by network
```

**分析要点：**
- 若 WiFi 正常但移动网络异常，可能是网络质量问题
- 若全网络类型均异常，排除网络因素

---

### 3.6 地区/城市维度下钻

**目的：判断波动是否集中在特定地区。**

#### 移动端端到端

```bash
# 按城市下钻（--group-by-field city）
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --group-by-field city
```

#### Web 端

```bash
raptorfe web speed get-dimension-dist \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --speed-point <speedPointId> \
  --group-by region
```

**分析要点：**
- 若只有特定城市/地区异常，可能是 CDN 或机房问题
- 若全国均异常，排除地区因素

---

### 3.7 业务自定义维度下钻

**目的：对指标特有的业务维度进行下钻（如广告位、容器类型、业务场景等）。**

#### 移动端自定义指标（按业务 Tag 下钻）

```bash
# 查所有可用 Tag
raptorfe metric get-tags --app-id <appId> --metric <metricKey>

# 对每个关键 Tag 进行下钻
raptorfe metric get-trend \
  --app-id <appId> --metric-key <metricKey> \
  --start-str "<YYYY-MM-DD HH:MM>" --end-str "<YYYY-MM-DD HH:MM>" \
  --types COUNT,AVG \
  --group-by '{"appId":<appId>,"metricKey":"<metricKey>","tagId":<tagId>}'
```

#### Perf 指标（按业务维度下钻）

```bash
# 查所有可用维度（用原子指标查询）
raptorfe perf metric get-tags --appkey PERF --metrics-name <原子指标ID>

# 原子指标：直接下钻
raptorfe perf metric dimension-analyse \
  --metrics-name <数字ID> --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "<tagName1>,<tagName2>" \
  --metrics-type atom \
  --methods avg,totalCount,tp90 \
  --project-name <项目名，如有>

# 复合指标（c 开头）：用原子指标 + --other-metrics 下钻
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "<tagName1>,<tagName2>" \
  --methods avg,totalCount \
  --project-name <项目名，如有> \
  --limit 20
```

#### Web 自定义指标（按 Tag 下钻）

```bash
# 查 Tag 列表
raptorfe web custom-metric get-tags --project-id <projectId> --metric-key <key>

# 按 Tag 分组查询
raptorfe web custom-metric get-trend \
  --project-id <projectId> --metric-key <key> \
  --start-str "<YYYY-MM-DD HH:MM>" --end-str "<YYYY-MM-DD HH:MM>" \
  --types COUNT,AVG \
  --group-by <tagName>
```

**分析要点：**
- 识别业务维度中的异常值
- 结合版本、平台等维度做交叉分析

---

### 3.8 多维交叉分析

在前面各维度分析的基础上，对高风险组合进行交叉验证。

#### 移动端端到端（版本 + 平台交叉）

```bash
# 异常版本 + iOS
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --app-versions <versionId> --platforms 2

# 异常版本 + Android
raptorfe mobile api get-trend \
  --api-id <apiId> --project-id <projectId> \
  --start-time <time> --end-time <time> \
  --time-type day --type netWorkSuccess --source <appSourceId> \
  --app-versions <versionId> --platforms 1
```

#### Perf 指标（多维度交叉）

```bash
# 原子指标：直接交叉下钻
raptorfe perf metric dimension-analyse \
  --metrics-name <数字ID> --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "appVersion,<其他维度>" \
  --filters '{"appVersion":["<异常版本>"]}' \
  --metrics-type atom \
  --methods avg,totalCount,tp90 \
  --project-name <项目名，如有>

# 复合指标（c 开头）：用原子指标 + --other-metrics 交叉下钻
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time <YYYY-MM-DD> --end-time <YYYY-MM-DD> \
  --tag-names "<其他维度>" \
  --filters '{"appVersion":["<异常版本>"]}' \
  --methods avg,totalCount \
  --project-name <项目名，如有> \
  --limit 20
```

**分析要点：**
- 结合版本、平台、页面、网络等多维度，寻找共同特征
- 缩小问题范围，为根因定位提供依据

---

## 第四步：输出分析报告

汇总各维度分析结果，按以下模板输出：

```markdown
# 指标下钻分析报告

## 基本信息
- 指标：<指标名称/接口路径>
- 指标类型：<移动端端到端 / 移动端自定义指标 / Perf 指标 / Web 端 / 小程序>
- 分析时间范围：<start> ~ <end>
- 分析指标：<网络成功率 / 耗时 TP90 / 自定义指标均值 等>

## 1. 整体趋势
- 趋势描述：<平稳 / 波动 / 持续下降 / 突发异常>
- 波动时间点：<具体日期>
- 波动幅度：<从 X% 降至 Y%，降幅 Z%>

## 2. 版本维度
- 异常版本：<版本号>（指标值 X，全量均值 Y）
- 正常版本：<版本号>（指标值 Z）
- 结论：<波动是否与版本相关>

## 3. 平台维度
- iOS：<指标值>
- Android：<指标值>
- 结论：<是否平台差异显著>

## 4. 页面维度（Web/小程序适用）
- 最差页面：<页面路径>（指标值 X）
- 结论：<是全局问题还是特定页面问题>

## 5. 网络类型维度
- WiFi：<指标值>
- 4G/5G：<指标值>
- 结论：<是否网络相关>

## 6. 地区维度
- 异常地区：<地区名>（指标值 X）
- 结论：<是否地区性问题>

## 7. 业务维度（如有）
- 异常维度值：<维度名>=<值>（指标值 X）
- 结论：<是否特定业务场景问题>

## 8. 根因定位
**初步根因：**
<综合以上分析，初步判断根因为...>

**优化建议：**
1. <建议1>
2. <建议2>
3. <建议3>
```

> 如果一次分析多个指标，对每个指标分别输出一份报告，最后给出综合结论。

---

## CLI 命令速查

### 移动端端到端（raptorfe mobile）

| 命令 | 用途 |
|------|------|
| `raptorfe mobile project list` | 获取项目列表（含 projectId） |
| `raptorfe mobile api get-by-project --project-id <id>` | 获取项目下 API 列表（含 apiId） |
| `raptorfe mobile api get-trend` | 查询 API 趋势（请求量/成功率/耗时） |
| `raptorfe mobile app list` | 获取 App 列表（含 source/appId 映射） |
| `raptorfe mobile app get-const` | 获取所有维度枚举（版本/网络/城市/平台等，仅标准 APP 有效） |
| `raptorfe mobile app get-api-report` | 查询 API 汇总报表 |

**`raptorfe mobile api get-trend` 关键参数：**

| 参数 | 说明 |
|------|------|
| `--type` | `request`（请求量）\| `netWorkSuccess`（网络成功率）\| `businessSuccess`（业务成功率）\| `delay`（耗时）\| `summary`（汇总） |
| `--time-type` | `minute`（分钟粒度）\| `day`（天粒度） |
| `--source` | App 来源 ID，10=美团主APP，11=外卖，1=点评 |
| `--platforms` | 1=Android，2=iOS，3=HarmonyOS |
| `--group-by-field` | 下钻维度：`version`、`city` |
| `--app-versions` | App 版本 ID（数字，从 `mobile app get-const` 获取，仅标准 APP 有效） |
| `--networks` | 网络类型 ID（从 `mobile app get-const` 获取） |
| `--cities` | 城市 ID（从 `mobile app get-const` 获取） |

> **注意：** `--app-versions` 参数需要传版本的数字 ID，而非版本号字符串。对于 `banma_all` 等非标准 APP 项目，`mobile app get-const` 可能无法返回有效版本枚举，此时版本维度下钻不适用，跳过该步骤。

---

### 移动端自定义指标（raptorfe metric）

| 命令 | 用途 |
|------|------|
| `raptorfe metric list --app-id <id>` | 查指标列表（含 metricKey） |
| `raptorfe metric get-tags --app-id <id> --metric <key>` | 查指标支持的下钻维度（tagId） |
| `raptorfe metric get-trend` | 查指标趋势（支持分组下钻） |

**`raptorfe metric get-trend` 关键参数：**

| 参数 | 说明 |
|------|------|
| `--types` | `COUNT,AVG,DIST_90` 等，逗号分隔 |
| `--group-by` | 分组维度 JSON：`{"appId":<id>,"metricKey":"<key>","tagId":<tagId>}` |
| `--tag-filters` | 维度过滤 JSON：`[{"tagId":1,"valueIds":[101,102]}]`，`valueIds=[]` 表示不过滤 |

---

### Perf 指标（raptorfe perf metric）

| 命令 | 用途 |
|------|------|
| `raptorfe perf metric search --appkey PERF --match <关键词>` | 搜索指标（获取数字 ID） |
| `raptorfe perf metric get-tags --appkey PERF --metrics-name <id>` | 查指标支持的维度 |
| `raptorfe perf metric get-trend` | 查指标时序数据（支持 `--project-name`） |
| `raptorfe perf metric dimension-analyse` | 指标维度下钻分析（支持 `--project-name`） |
| `raptorfe perf metric get-tag-values` | 查某维度的可选值列表 |

**metricsType 判断：** `perf metric search` 返回的 `id` 是纯数字 → `atom`；`c` 开头 → `composite`

> ⚠️ **复合指标 dimension-analyse 规则**：复合指标（c 开头 ID）不能直接做 `dimension-analyse`（会返回空数据）。必须找到其对应的原子指标（通过 `perf metric search` 搜索相关关键词），用原子指标做 `dimension-analyse` 并通过 `--other-metrics` 参数附带复合指标 ID。返回结果中每个维度值同时包含原子指标字段和复合指标字段值。`get-trend` 不受此限制，复合指标可直接查询趋势。

> ❗ **projectName 参数规则：** 当查询参数中 `projectName` 出现在顶层（不在 filters 数组/对象内）时，必须通过 `--project-name <值>` 传入 `get-trend` 或 `dimension-analyse`。CLI 会自动将其合并到 filters.projectName 中发送给后端。不传此参数会导致查询未按项目筛选，数据不准确。

---

### Web 端（raptorfe web）

| 命令 | 用途 |
|------|------|
| `raptorfe web project search --name <关键词>` | 搜索 web 项目 |
| `raptorfe web page list --project-id <id>` | 查页面列表（含 pageId） |
| `raptorfe web version list --project-id <id>` | 查版本列表 |
| `raptorfe web speed-point list --project-id <id>` | 查测速点列表 |
| `raptorfe web speed get-trend` | 查性能趋势 |
| `raptorfe web speed get-dimension-dist` | 按维度下钻（os/network/region/container/version） |
| `raptorfe web speed get-summary` | 查性能汇总报表 |
| `raptorfe web custom-metric list --project-id <id>` | 查自定义指标列表 |
| `raptorfe web custom-metric get-tags` | 查自定义指标维度 |
| `raptorfe web custom-metric get-trend` | 查自定义指标趋势 |

---

### 小程序（raptorfe mp）

| 命令 | 用途 |
|------|------|
| `raptorfe mp project list` | 查小程序项目列表 |
| `raptorfe mp speed get-trend` | 查性能趋势 |
| `raptorfe mp speed get-dimension-dist` | 按维度下钻（os/network/region/version） |
| `raptorfe mp custom-metric list --project-id <id>` | 查自定义指标列表 |
| `raptorfe mp custom-metric get-trend` | 查自定义指标趋势 |
| `raptorfe mp request get-trend` | 查请求趋势 |

---

## 注意事项

**时间格式：**
- `raptorfe mobile api get-trend`：`--start-time` / `--end-time` 支持毫秒时间戳或日期字符串
- `raptorfe metric get-trend`：`--start-str` / `--end-str` 为 `"YYYY-MM-DD HH:MM"` 格式
- `raptorfe perf metric get-trend`：DAY 粒度用 `YYYY-MM-DD`，分钟粒度用 `"YYYY-MM-DD HH:MM:SS"`
- `raptorfe web speed get-trend`：`--start-long` / `--end-long` 支持毫秒时间戳或日期字符串

**版本维度限制：** `raptorfe mobile app get-const` 仅对美团主 APP、外卖、点评等标准 APP 返回版本枚举；`banma_all` 等非标准项目无版本枚举，版本维度下钻不适用，跳过。

**分析顺序：** 先查整体趋势确认波动时间点，再针对波动时间段做版本、页面等维度的深入分析，避免全量扫描浪费时间。

**多指标分析：** 用户一次输入多个指标时，对每个指标独立执行完整分析流程，最后给出综合结论。

**数据展示：** 查询结果用 Markdown 表格展示，关键数据（如异常版本、最差页面）用**加粗**标注。

**鉴权：** raptorfe CLI 内置自动 SSO 鉴权，无需手动传 Cookie。命令执行后可能沉默 10～30 秒，属正常现象。
