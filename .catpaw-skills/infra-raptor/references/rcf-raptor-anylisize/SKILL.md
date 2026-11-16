---
name: rcf-raptor-anylisize
version: "1.1.0"
description: >
  Raptor 实时查询中 RCF 指标（R 交互响应 / C 首屏加载 / F 滑动流畅度）的多维度波动分析，定位 RCF 总分或子指标分数下降的根因。
  支持两种触发方式：①用户明确说"分析"RCF/R/C/F 分数波动、劣化、下降；②用户发送 Raptor 性能大盘页面链接并提出分析诉求（自动解析 URL 参数后重新查询）。
  按子指标拆解→维度下钻→贡献度计算→多维交叉→根因定位的完整 SOP 流程逐步分析，输出根因报告和行动建议。
  覆盖美团/外卖/点评，Android/iOS/HarmonyOS，支持 Native/MRN/KNB/MSC 各技术栈。
  触发词：分析RCF波动、RCF分数下降、R分数劣化、C分数劣化、F分数劣化、分析性能分数、RCF分析、R指标分析、C指标分析、F指标分析、首屏分数下降、交互响应劣化、滑动流畅度下降、性能分数波动。
  注意：如果用户只是简单查询数据（如"查一下最近7天C分数"），不要触发本技能，使用 raptorfe-allquery 子技能即可。

metadata:
  skillhub.creator: "zhangxinyue27"
  skillhub.updater: "zhangxinyue27"
---

# RCF 指标波动分析

## 🔧 前置依赖

本 skill 使用 `raptorfe` CLI（内置鉴权，无需手动传 token）。

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 📖 背景知识：RCF 是什么

### 三个子指标定义

**R 指标（交互响应）**：衡量用户点击/交互后页面的响应速度，基于交互响应延迟指标（`metricx.response.duration`）计算得分，权重 **0.2**。

**C 指标（首屏加载）**：衡量页面打开到屏幕内容稳定的耗时，基于秒开率 2.0 原子指标（`ffp_native`、`ffp_mrn`、`ffp_knb`、`ffp_msc` 等）计算得分，权重 **0.5**。

**F 指标（滑动流畅度）**：衡量页面滑动时的流畅程度，基于滑动掉帧率指标（`mobile.fps.scroll.avg.v2.n`）计算得分，权重 **0.3**。

### 26 年新标准计分规则（平滑过渡计分）

每条日志根据原始耗时值，通过分段函数计算一个分数（范围从 +1 到 -∞）：

| 指标 | 满意（1分） | 可容忍（→0分） | 不满意（→-1分） | 负向体验（→-2分） | 严重负向 | 权重 |
|------|------------|--------------|----------------|-----------------|---------|------|
| **R** | (0, 100ms] | (100, 150ms] | (150, 1000ms] | (1000, 2000ms] | (2000ms, ∞) | **0.2** |
| **C（页面）** | (0, 400ms] | (400, 1000ms] | (1000, 3000ms] | (3000, 4000ms] | (4000ms, ∞) | **0.5** |
| **C（冷启LVC）** | (0, 1500ms] | (1500, 4000ms] | (4000, 5000ms] | (5000, 6000ms] | (6000ms, ∞) | **0.5** |
| **F** | (0, 5ms/s] | (5, 10ms/s] | (10, 160ms/s] | (160, 320ms/s] | (320ms/s, ∞) | **0.3** |

> 平滑减分规则：R/C 指标耗时每增长 1000ms 多减 1 分；F 指标每增长 160ms/s 多减 1 分。

### Raptor 实时计算逻辑

1. **单条日志打分**：每条日志根据原始值通过分段函数计算 weight_factor，再除以采样率（sr × sample_rate × prism_sample_rate）还原为全量权重。
2. **聚合得分**：对某维度组合下所有日志的 weight_factor 求 SUM，再除以该维度组合的全量日志数，得到 R/C/F 分数。
3. **RCF 总分**：`RCF总分 = R分数 × 0.2 + C分数 × 0.5 + F分数 × 0.3`

> ⚠️ 重要：Raptor 大盘**不支持**统计单页面的 RCF 总分（各指标页面字段名和值不统一），单页面 RCF 总分以菠萝蜜为准。Raptor 适合做多维度下钻分析 R/C/F 各子指标。

---

## 🎯 适用场景

**适用（触发此 skill）**：
- 用户明确说"分析"、"要分析" RCF / R / C / F 分数的波动、劣化、下降
- 用户发送 Raptor 性能大盘链接（如 `raptor.mws.sankuai.com/ffp/...`）并提出分析诉求

**不适用（不要触发此 skill）**：
- 仅查询数据（如"查一下最近7天C分数"）→ 使用 `raptorfe-allquery`
- 收到 Crash/ANR/FOOM 告警消息需要根因分析 → 使用 `infra-app-stability` 的 `root-cause` 子技能；大前端监控 PERF 告警 → 使用 `raptorperf-alert-analyzer`
- 仅画趋势图 → 使用 `component-crash-chart`

---

## 第零步：确认分析参数

开始前确认以下信息，缺少时主动询问：

| 参数 | 是否必填 | 说明 |
|------|---------|------|
| APP / project | 必填 | 见下方映射表 |
| 分析对象 | 必填 | RCF总分 / R分数 / C分数 / F分数，或全部 |
| 当前期（T2） | 必填 | 发生波动的时间范围，如"本周"、"今天" |
| 对比期（T1） | 必填 | 基准时间范围，如"上周同期"、"昨天" |
| 技术栈 | 可选 | Native / MRN / KNB / MSC，无则全量分析 |
| 过滤条件 | 可选 | 版本、页面等，无则全量分析 |

### 📎 关于 Raptor 链接的处理方式

Raptor 已全面切换短链模式，URL 中只有 `shortId` 参数，筛选条件存储在服务端。收到 Raptor 链接时，从 URL 中提取 `shortId`，调用以下接口还原完整参数：

```bash
curl -s "https://common-faas.vip.sankuai.com/api/getStoredQuery?id=<shortId>"
```

> ⚠️ 参数名是 `id`，不是 `shortId`。该接口无需任何鉴权，直接调用即可。

**返回数据结构示例**：

```json
{
  "code": 200,
  "data": {
    "global": {
      "agg": "DAY",
      "startTime": "2025-12-02",
      "endTime": "2025-12-09"
    },
    "<workspace>": {
      "<page>": {
        "prismOption": { "projectNames": ["android_platform_monitor"] }
      },
      "prismOption": { "projectNames": ["android_platform_monitor"] }
    }
  }
}
```

> workspace 和 page 从 URL 路径读取，如 `/ffp/index` → workspace=`ffp`、page=`index`。

**从返回数据中提取分析参数**：

| 分析参数 | 取法 |
|---------|------|
| **project** | `data[workspace][page].prismOption.projectNames[0]`，或 `data[workspace].prismOption.projectNames[0]` |
| **startTime / endTime** | `data.global.startTime` / `data.global.endTime` |
| **agg** | `data.global.agg`（DAY / HOUR） |
| **appVersion** | `data[workspace][page].prismOption.filters` 中 tagName=appVersion 的 tagValues |
| **pagePath** | `data[workspace][page].prismOption.filters` 中 tagName=pagePath 的 tagValues |

提取完成后，直接用 `raptorfe` CLI 查询数据进行分析，appVersion / pagePath 等作为 `--filter` 参数传入。

### project 映射表

| 用户说的 | --project 值 |
|---------|-------------|
| 美团 iOS | meituan |
| 美团 Android | android_platform_monitor |
| 美团鸿蒙 | meituan-harmony |
| 外卖 iOS | waimai_ios |
| 外卖 Android | meituanwaimai |
| 外卖鸿蒙 | waimai-harmony |
| 点评 iOS | nova |
| 点评 Android | android-nova |
| 点评鸿蒙 | harmony-nova |
| 其他 | `raptorfe perf metric search --keyword "<APP名>"` 查询 |

### 指标名称对照表

| 指标 | 技术栈 | Raptor 指标名 | 原子指标名 |
|------|--------|-------------|-----------|
| C 分数 | Native | C分数-native | ffp_native |
| C 分数 | MRN | C分数-mrn | ffp_mrn |
| C 分数 | KNB | C分数-knb | ffp_knb |
| C 分数 | MSC | C分数-msc | ffp_msc |
| C 分数 | 汇总 | C分数 | - |
| R 分数 | Native | R分数-native | metricx.response.duration |
| R 分数 | MRN | R分数-mrn | metricx.response.duration |
| R 分数 | KNB | R分数-knb | metricx.response.duration |
| R 分数 | MSC | R分数-msc | metricx.response.duration |
| R 分数 | 汇总 | R分数 | - |
| F 分数 | Native | F分数-native | mobile.fps.scroll.avg.v2.n |
| F 分数 | MRN | F分数-mrn | mobile.fps.scroll.avg.v2.n |
| F 分数 | KNB | F分数-knb | mobile.fps.scroll.avg.v2.n |
| F 分数 | MSC | F分数-msc | mobile.fps.scroll.avg.v2.n |
| F 分数 | 汇总 | F分数 | - |

---

### 📎 指标-tag 映射表（下钻时必查，避免试错）

不同指标的可用 tag 字段名不同，用错会返回空数据或报错：

| 原子指标 | 对应分数 | 页面维度 tag 名 | 常用 project-name |
|---------|---------|----------------|-------------------|
| `metricx.response.duration` | R 分数 | `pageNickname` | `android_platform_monitor`(Android) / `meituan`(iOS) |
| `ffp_native` | C 分数(Native) | `nPage` | `android_platform_monitor`(Android) / `meituan`(iOS) |
| `ffp_mrn` | C 分数(MRN) | `nPage` | 同上 |
| `ffp_msc` | C 分数(MSC) | `nPage` | 同上 |
| `ffp_knb` | C 分数(KNB) | `nPage` | 同上 |
| `mobile.fps.scroll.avg.v2.n` | F 分数 | `pageNickname` | 同上 |

> ⚠️ **`nPage` vs `pageNickname`**：C 分数指标（`ffp_*`）的页面维度 tag 是 `nPage`（注意大写 N 和 P）；R 分数和 F 分数指标的页面维度 tag 是 `pageNickname`（全小写驼峰）。用错会返回空数据。

> ⚠️ **不确定 tag 名时**：先用 `raptorfe perf metric get-tags --appkey PERF --metrics-name <指标名>` 查询该指标支持的所有维度 tag，再选择正确的 tag 名。

---

## 执行流程

每个步骤查询完成后立即展示结果并给出初步判断，不要等所有步骤都完成再输出。

---

### 第一步：查询 R/C/F 子指标分数，定位主要拖累项

**目的**：对比 T1 和 T2 的 R/C/F 分数变化量，计算各子指标对 RCF 总分变化的贡献，找到主要拖累项。

```bash
# 查询 T2 期 R/C/F 分数趋势（按天）
raptorfe perf metric get-trend \
  --project <project> \
  --metric "R分数,C分数,F分数" \
  --start "<T2-start>" --end "<T2-end>" \
  --interval day

# 查询 T1 期 R/C/F 分数趋势（对比基准）
raptorfe perf metric get-trend \
  --project <project> \
  --metric "R分数,C分数,F分数" \
  --start "<T1-start>" --end "<T1-end>" \
  --interval day
```

**贡献度计算**：

```
ΔR = T2期R分数均值 - T1期R分数均值
ΔC = T2期C分数均值 - T1期C分数均值
ΔF = T2期F分数均值 - T1期F分数均值

ΔR 对总分贡献 = ΔR × 0.2
ΔC 对总分贡献 = ΔC × 0.5
ΔF 对总分贡献 = ΔF × 0.3
```

**分析要点**：贡献绝对值最大的子指标即为主要拖累项，优先分析该指标。

> 示例：若 ΔR = -0.05，ΔC = -0.04，ΔF = -0.02，则各贡献为 -0.01、-0.02、-0.006，**C 指标是主要拖累项**。

---

### 第二步：在目标子指标中，按维度下钻

**目的**：找到对分数变化贡献最大的维度值（如哪个页面、哪个版本）。

**推荐下钻维度优先级**（从高到低）：

| 优先级 | 维度 | 说明 |
|--------|------|------|
| 1 | **页面（pagePath / pageNickname）** | **必须首先下钻**，最直接的定位维度，流量大的页面影响最大，最终根因必须落到具体页面 |
| 2 | **appVersion（版本号）** | 判断是否某个版本引入了问题 |
| 3 | **ffp_business / 业务 tag** | 区分业务线归因 |
| 4 | **renderType / 技术栈** | Native / MRN / KNB / MSC 分别分析 |
| 5 | **publishId（动态包发布 ID）** | 排查动态包发布引入的问题 |
| 6 | **deviceLevel（设备档位）** | 排查低端机问题 |

> 🔑 **页面维度是分析的核心**：无论分析哪个子指标（R/C/F），都必须先按 `pagePath` 或 `pageNickname` 下钻，找到贡献最大的页面。后续所有维度的下钻都应在该页面的过滤条件下进行，最终根因必须落到"**哪个页面**"。

```bash
# 【必做】第一步：按页面维度下钻（T2 期）
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<T2-start>" --end-time "<T2-end>" \
  --tag-names "nPage" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"]}' \
  --limit 20

# 【必做】按页面维度下钻（T1 期，用于对比）
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<T1-start>" --end-time "<T1-end>" \
  --tag-names "nPage" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"]}' \
  --limit 20

# 在确定关键页面后，继续下钻其他维度（加 filter 限定页面）
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<T2-start>" --end-time "<T2-end>" \
  --tag-names "appVersion" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"],"nPage":["<关键页面路径>"]}' \
  --limit 20
```

> ⚠️ **复合指标维度下钻的关键规则**：
>
> **复合指标（c 开头的 ID，如 c17947）不能直接做 `dimension-analyse`，会返回空数据！** 必须用对应的原子指标做 `dimension-analyse`，通过 `--other-metrics` 参数附带复合指标 ID。返回结果中每个维度值会同时包含原子指标的 avg/totalCount 和复合指标的值（字段名为复合指标 ID）。
>
> **复合指标 → 原子指标映射表**：
>
> | 复合指标 | 复合指标 ID | 原子指标 | 原子指标 ID |
> |---------|-----------|---------|-----------|
> | C分数-26年-Native | c17947 | ffp_native.score | 210754 |
> | C分数-26年-MRN | c17949 | ffp_mrn.score | 210755 |
> | C分数-26年-MSC | c17950 | ffp_msc.score | 210756 |
> | C分数-26年-KNB | c17951 | ffp_knb.score | 210757 |
> | C分数-native | c11663 | ffp_native | 98468 |
> | C分数-mrn | c11666 | ffp_mrn | 98494 |
> | C分数-knb | c11664 | ffp_knb | 98508 |
> | C分数-msc | c11667 | ffp_msc | 98521 |
>
> **查找未知复合指标的原子指标**：`raptorfe perf metric search --appkey PERF --match "<原子指标关键词>"`
>
> **dimension-analyse 返回数据格式**：每个维度值的 `valueMap` 中包含原子指标字段（avg、totalCount 等）和复合指标字段（字段名就是复合指标 ID，如 `c17947`），使用复合指标字段的值做贡献度计算。

> ⚠️ 注意：不同子指标支持的维度不同。例如 C分数-native 没有 publishId 维度，不要对其下钻 publishId。可用 `raptorfe perf metric get-tags --appkey PERF --metrics-name <原子指标ID>` 查询支持的维度列表。

> ⚠️ **dimension-analyse 多维下钻 Duplicate key 错误（重要）**：`--tag-names` 同时传多个维度（如 `'appVersion,deviceLevel'`）时，某些指标会触发后端 `Duplicate key` API 错误。**建议优先单维度下钻**；遇到 `Duplicate key` 错误时**立即降级为单维度逐个查询**，不要用相同多维度参数重试。

> ⚠️ **大 JSON 处理提示**：`dimension-analyse` 返回的 JSON 可能很大（多维度值 × 多指标），直接保留在上下文中会导致 input 膨胀。建议在 bash 中用 `python -c` 或 `jq` 提取关键字段（维度值、avg、复合指标值）后再回传给模型：
> ```bash
> raptorfe perf metric dimension-analyse ... -o json | \
>   python3 -c "import sys,json; data=json.load(sys.stdin); [print(f\"{d['tagValue']}: avg={d['valueMap'].get('avg','N/A')}, score={d['valueMap'].get('c17947','N/A')}\") for d in data['data']['dimensionResult']]"
> ```

---

### 第三步：计算各维度值的贡献度

**目的**：量化每个维度值对整体分数变化（ΔS = S2 - S1）的贡献，区分"性能真实劣化"和"流量结构变化"。

**权重（流量占比）计算**：

```
wi,1 = 维度值 i 在 T1 期的全量数 / 整体在 T1 期的总全量数
wi,2 = 维度值 i 在 T2 期的全量数 / 整体在 T2 期的总全量数
```

> ⚠️ 全量数（reckonCount）= 样本数 / 采样率，必须使用全量数而非原始样本数，否则权重计算不准确。

**贡献度分解公式**：

```
分数变化贡献（ScoreEffect_i）= wi,2 × (Pi,2 - Pi,1)
样本变化贡献（WeightEffect_i）= (wi,2 - wi,1) × (Pi,1 - S1)
总贡献（TotalContrib_i）= ScoreEffect_i + WeightEffect_i
```

其中：
- `Pi,1`、`Pi,2`：维度值 i 在 T1、T2 期的分数
- `S1`：整体在 T1 期的分数

**验证**：`Σ TotalContrib_i ≈ ΔS`（允许微小误差）

**查询全量数的命令**：

```bash
# 查询某维度值的全量数（reckonCount）
raptorfe perf metric get-buckets \
  --project <project> \
  --metric "<目标指标名>" \
  --start "<start>" --end "<end>" \
  --filter "<维度名>:<维度值>"
```

---

### 第四步：识别贡献最大的维度值

按 `|TotalContrib_i|` 降序排列所有维度值，取 Top 5。

同时区分两类贡献来源：

- **ScoreEffect 主导**：说明该维度值自身性能发生了变化（如某页面的 C 分数下降），是**真实的性能劣化**。
- **WeightEffect 主导**：说明该维度值的流量结构发生了变化（如某页面访问量激增），是**流量迁移**导致的分数变化，不一定是性能劣化。

> 判断阈值：贡献度绝对值超过 `|ΔS| × 10%` 视为显著贡献者。

---

### 第五步：多维度组合下钻，锁定根因

对第四步中找到的关键维度值，继续下钻到下一个维度，重复第三步和第四步的贡献度计算。

> 🔑 **下钻必须经过页面维度**：下钻路径中必须包含 `pagePath` 维度，最终根因必须落到具体页面。若第二步已确定关键页面，后续所有下钻都应在该页面的 `--filter` 条件下进行。

**典型下钻路径示例**：

```
整体 C 分数下降
  └─ 【必做】按页面下钻 → 发现"外卖首页（/waimai/index）"贡献最大（TotalContrib = -0.018）
       └─ 按版本下钻（filter: pagePath=/waimai/index）→ 发现"8.x.x 版本"贡献最大
            └─ 按技术栈下钻（filter: pagePath=/waimai/index + appVersion=8.x.x）→ 发现"Native 技术栈"贡献最大
                 └─ 根因结论：8.x.x 版本下外卖首页（/waimai/index）Native 技术栈的 C 分数劣化
```

**下钻时的 CLI 命令（加 filters 参数）**：

```bash
# 在已知页面的基础上，继续下钻版本维度
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<start>" --end-time "<end>" \
  --tag-names "appVersion" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"],"nPage":["<关键页面路径>"]}' \
  --limit 20

# 在已知页面 + 版本的基础上，继续下钻技术栈维度
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<start>" --end-time "<end>" \
  --tag-names "renderType" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"],"nPage":["<关键页面路径>"],"appVersion":["<关键版本>"]}' \
  --limit 20
```

**终止条件**：
- 已找到最细粒度的维度组合（**必须包含具体页面**，如 页面 + 版本 + 技术栈）
- 子维度的贡献度均低于阈值（不显著）
- 已定位到可操作的根因（根因必须能落到某个具体页面）

---

### 第六步：区分根因类型，指导后续排查

根据贡献度分解结果，判断根因类型：

**若 ScoreEffect 主导（性能真实劣化）**：

- **R 指标劣化**：检查该维度组合下的交互响应延迟分布变化，重点关注满意全量数是否减少，排查代码变更、主线程阻塞等问题。
  ```bash
  # 查 R 指标原子指标的 TP 耗时分布
  raptorfe perf metric get-trend \
    --project <project> \
    --metric "metricx.response.duration" \
    --start "<start>" --end "<end>" \
    --filter "<维度名>:<维度值>" \
    --aggregation tp90,tp75,avg
  ```

- **C 指标劣化**：分析首屏加载耗时波动，排查资源加载、网络请求、渲染链路等问题；结合秒开率（`ffp_xxx.ratio`）和 TP 耗时（P75/P90）辅助判断。
  ```bash
  # 查 C 指标原子指标的 TP 耗时和秒开率
  raptorfe perf metric get-trend \
    --project <project> \
    --metric "ffp_native" \
    --start "<start>" --end "<end>" \
    --filter "<维度名>:<维度值>" \
    --aggregation tp90,tp75,ratio
  ```

- **F 指标劣化**：评估滑动掉帧率变化，排查渲染性能、主线程卡顿、动画帧率等问题。
  ```bash
  # 查 F 指标原子指标的掉帧率分布
  raptorfe perf metric get-trend \
    --project <project> \
    --metric "mobile.fps.scroll.avg.v2.n" \
    --start "<start>" --end "<end>" \
    --filter "<维度名>:<维度值>" \
    --aggregation tp90,avg
  ```

**若 WeightEffect 主导（流量结构变化）**：

- 分析该维度值的流量为何增加/减少（如推广活动、版本灰度放量、业务策略调整）。
- 若高分页面流量减少或低分页面流量增加，会导致整体分数下降，但不代表性能劣化。
- 结合发布记录（publishId）、版本灰度情况交叉验证。

---

### 第七步：输出分析结论

整理分析结论，包含以下要素：

1. **整体波动摘要**：ΔS 是多少，主要拖累的子指标是哪个（R/C/F）
2. **关键贡献维度值**：Top 3-5 的维度值及其贡献度（TotalContrib、ScoreEffect、WeightEffect）
3. **下钻路径**：从整体到根因的完整下钻链路（**必须包含页面维度**）
4. **根因结论**：用自然语言描述，**必须明确指出是哪个页面**，例如"整体 RCF 分数下降主要由于 8.x.x 版本下**外卖首页（/waimai/index）** Native 技术栈的 C 分数降低，首屏加载耗时增加导致满意全量数减少"
5. **行动建议**：针对根因的优化方向

---

### 第八步：询问是否进行页面级深度分析

**触发条件**：当根因已定位到某个具体页面（即第七步结论中明确了关键页面）时，执行本步骤。

向用户提问：

> 已定位到关键页面：**`<页面路径>`**（`<子指标>` 分数劣化，贡献度 `<TotalContrib>`）。
>
> 是否需要对该页面进行**深度性能分析**？可调用 `infra-app-performance` 技能中的 `rcf-analysis` 子技能，从代码层面分析该页面的性能劣化根因（支持 Native/MRN/KNB/MSC 各技术栈）。

**若用户选择"是"**，执行以下流程：

#### 1. 安装 `infra-app-performance` 技能

```bash
# 检查是否已安装
ls ~/.catpaw/skills/skills-market/infra-app-performance/skill/SKILL.md 2>/dev/null \
  || ls "/Users/work/Desktop/catpaw desk/.catpaw/skills/skills-market/infra-app-performance/skill/SKILL.md" 2>/dev/null \
  && echo "已安装" || echo "未安装"
```

若未安装，使用 skill installer 安装到全局：

```bash
# 使用 catpaw-skill-installer 安装（market ID: 2984）
INSTALLER=$(find ~/.catpaw/skills ~/.catpaw/projects -name "catpaw-skills-darwin-arm64" 2>/dev/null | head -1)
"$INSTALLER" install -g market:2984
```

> 安装路径：`~/.catpaw/skills/skills-market/infra-app-performance/`

#### 2. 读取并执行 `rcf-analysis` 子技能

安装完成后，读取子技能文件并按其 SOP 执行深度分析：

```
~/.catpaw/skills/skills-market/infra-app-performance/skill/references/rcf-analysis/SKILL.md
```

将以下上下文作为输入传递给子技能：
- **project**：`<project>`
- **页面路径**：`<关键页面路径>`
- **劣化子指标**：`<R/C/F 分数>`
- **时间范围**：T1 `<T1-start>` ~ `<T1-end>`，T2 `<T2-start>` ~ `<T2-end>`
- **已知过滤条件**：`<appVersion、renderType 等已确认的维度值>`

**若用户选择"否"**，直接结束分析，输出第七步的结论报告即可。

---

## ⚠️ 常见注意事项

**关于全量数**：Raptor 中查询样本数时必须使用全量数（reckonCount），即已还原采样率的数据，否则权重计算会严重偏差。

**关于维度值 `scout.others`**：表示维度值超限或上报了空值，无法直接分析，建议查离线表原始数据获取详细内容。

**关于维度值 `other`**：表示原始值上报了 other，或该维度有白名单但未注册，可在 Raptor 系统的维度值管理中查看白名单配置。

**关于 RCF 总分口径差异**：Raptor 的 RCF 总分计算方式与菠萝蜜不同（Raptor 是 R/C/F 分别加权，菠萝蜜是先算单页面 RCF 再按 C 样本量加权），**总分以菠萝蜜为准，Raptor 总分仅供参考**。R/C/F 各子分数两者口径一致。

**关于技术栈区分**：不同技术栈的指标名不同（如 `C分数-native`、`C分数-mrn`、`C分数-knb`、`C分数-msc`），下钻时注意区分，避免混用。

**关于 Raptor 链接解析**：若用户发送 Raptor 性能大盘链接，解析 URL 中的 project、metric、filterId、appVersion、pagePath 等参数，作为分析的初始过滤条件，再用 CLI 重新查询数据进行分析。

---

## 📋 常用 CLI 命令速查

```bash
# 搜索指标（获取数字 ID）
raptorfe perf metric search --appkey PERF --match "<关键词>"

# 查询指标支持的维度（tag）列表
raptorfe perf metric get-tags --appkey PERF --metrics-name <数字ID>

# 查询指标趋势（按天/小时）
raptorfe perf metric get-trend \
  --metrics-name <数字ID> --metrics-type <atom|composite> \
  --agg DAY \
  --start-time "<start>" --end-time "<end>" \
  --methods avg,totalCount

# 查询指标按维度下钻（复合指标必须用原子指标 + --other-metrics）
raptorfe perf metric dimension-analyse \
  --metrics-name <原子指标ID> --metrics-type atom \
  --other-metrics "<复合指标ID>" \
  --agg DAY \
  --start-time "<start>" --end-time "<end>" \
  --tag-names "<dimension>" \
  --methods avg,totalCount \
  --filters '{"app":["com.meituan.imeituan","com.sankuai.meituan"]}' \
  --limit 20

# 查询维度值列表
raptorfe perf metric get-tag-values \
  --project-name FSP --metrics-name <指标名> \
  --tag <dimension> \
  --start-time "<start>" --end-time "<end>"

# 查询指标趋势（带维度过滤）
raptorfe perf metric get-trend \
  --metrics-name <数字ID> --metrics-type <atom|composite> \
  --agg DAY \
  --start-time "<start>" --end-time "<end>" \
  --methods avg,totalCount \
  --filters '{"nPage":["<页面路径>"]}'
```
