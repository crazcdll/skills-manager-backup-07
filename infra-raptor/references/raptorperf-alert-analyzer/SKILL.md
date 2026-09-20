---
name: infra-raptorperf-alert-analyzer
display_name: Raptor大前端告警分析
description: >
  自动分析大前端监控告警，通过 Perf MCP 拉取指标数据并多维度下钻，
  输出趋势对比图 + 根因分析报告。支持 ATOM/COMPOSITE 指标。
  当用户转发「大前端监控」告警、粘贴含「指标名:」「PERF:」「触发规则:」「数据时间」
  的告警文本、或说「分析这个告警」「帮我看这个 P1/P2 告警」时触发。
tags: 终端基础技术
version: 1.1.0
created: 2026-03-25
---

# 大前端监控告警自动分析 v2

## 前置依赖

使用 `raptorfe` CLI（内置鉴权，无需 token 申请，无需 mcporter）。

### 环境初始化（每次分析前自动执行）

#### 步骤 1：检查 raptorfe 和 Python 依赖

> **前置预检（一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

```bash
/usr/bin/pip3 install numpy matplotlib --quiet
```

> 使用 `/usr/bin/python3`（系统 Python），避免 arm64 Mac 上架构不兼容问题。
> `raptorfe` CLI 内置鉴权，无需获取 token，无需注册 MCP server。

## 执行流程

### 第一步：解析告警消息

消息包含以下任意特征时触发解析：`[大前端监控]`、`[告警名称:`、`PERF:` 前缀指标名、`[指标名:` 格式、`触发规则:`、`数据时间：` + `告警时间：`。

从告警文本中提取：

| 字段 | 提取方式 |
|------|----------|
| 告警级别 | `\[(P\d)\]` |
| 告警名称 | `\[告警名称:\s*(.+?)\]` |
| 指标列表 | `PERF:(\S+)` 或 `com\.sankuai\.\S+:(\S+)` 或 `\[指标名:\s*(\S+)\]` — 去重 |
| 数据时间 | `数据时间：(.+)` |
| 告警时间 | `告警时间：(.+)` — 提取小时 |
| 持续时长 | `持续时长：(.+)` |
| 业务负责人 | `业务负责人：(.+)` |
| 触发规则 | 每段指标下的触发规则文字 |

指标名处理：
- `PERF:ffp_msc.ratio` → `ffp_msc.ratio`
- `com.sankuai.msc.client:msc.page.white.screen.count.rate` → `msc.page.white.screen.count.rate`
- `[指标名: mobile.outlink.success.android.knb.t2.t1]` → `mobile.outlink.success.android.knb.t2.t1`

#### ⚠️ 识别每个指标的实际统计方式

同一 ATOM 指标可用不同统计方式（totalCount / avg / p50/p75/p90/p99），**统计方式决定值的含义**：

1. **看触发值量级**：整数且 >100 → 大概率 totalCount；小数且 <1 → rate；几百到几千小数 → avg/分位值
2. **看阈值格式**：`>= 2000` + 整数值 → totalCount；`< 0.9994` + 高精度小数 → rate
3. **看指标名语义**：`.rate`/`.ratio` → 比率；`.count` + 大整数 → totalCount；`.duration` → 耗时
4. COMPOSITE 指标无需推断，直接是复合计算结果

**在分析报告中必须对每个指标明确说明其统计含义。**

### 第二步：通过 raptorfe CLI 查询指标数据

**搜索指标 ID：**

```bash
raptorfe perf metric search --appkey PERF --match <metric_name>
```

返回 `id`（数字 = atom 指标，`c` 开头 = composite 指标）。

**查时序数据（小时级）：**

```bash
raptorfe perf metric get-trend \
  --metrics-name <id> \
  --metrics-type atom \
  --agg ONE_HOUR \
  --start-time "YYYY-MM-DD HH:MM:SS" \
  --end-time "YYYY-MM-DD HH:MM:SS" \
  --methods avg,totalCount
```

**维度下钻（排查根因）：**

```bash
# ATOM 指标（纯数字 ID）直接下钻：
raptorfe perf metric dimension-analyse \
  --metrics-name <id> \
  --metrics-type atom \
  --agg DAY \
  --start-time "YYYY-MM-DD" \
  --end-time "YYYY-MM-DD" \
  --tag-names "appVersion,content_type_category" \
  --methods avg,totalCount
```

> ⚠️ **COMPOSITE 指标（c 前缀 ID）不能直接做 dimension-analyse**，会返回空数据。必须先获取其 atom 子指标 ID：
>
> ```bash
> # 1. 获取复合指标的子指标详情
> raptorfe perf metric get-compound-detail --appkey PERF --metric-ids <c开头的ID>
> # 返回 expression（如 A/(A+B)）和每个子指标的 atom metricId
>
> # 2. 用 atom 子指标 ID 做 dimension-analyse，同时传 composite ID 到 --other-metrics
> raptorfe perf metric dimension-analyse \
>   --metrics-name <atom_id> \
>   --metrics-type atom \
>   --agg DAY \
>   --start-time "YYYY-MM-DD" \
>   --end-time "YYYY-MM-DD" \
>   --tag-names "appVersion" \
>   --methods totalCount \
>   --other-metrics <composite_id>
> # --other-metrics 会让返回结果同时包含复合指标的计算值，用于验证
> ```

脚本分析流程：
1. 探测每个指标类型（ATOM/COMPOSITE）
2. 用 `raptorfe perf metric search` 获取指标 ID
3. **若为 COMPOSITE 指标**：用 `get-compound-detail` 获取 atom 子指标 ID 和计算公式
4. 查询告警日 + 参考日小时级趋势（`get-trend`，`--agg ONE_HOUR`）
5. 对关键维度（appVersion、content_type_category 等）用 `dimension-analyse` 下钻（COMPOSITE 需用 atom ID）
6. 计算变化率 → 排序 → 标记异常（>threshold）
7. 找出 top3 变化最大的根因维度
8. 生成图表 + 输出分析结论

### 第三步：上传图表 + 输出报告

**上传图表：** 优先使用 `s3plus-upload` skill；若未安装，直接在报告中附本地图片路径。

**输出报告格式：**

```
🚨 **{告警级别} {告警名称}**

**告警概况：**
- 指标：{指标名}（{类型}，统计含义：{例如"样本数/次数" 或 "成功率" 或 "平均耗时ms"}）
- 数据时间：{数据时间}，持续 {持续时长}
- 触发值：{最近点值}，规则：{触发规则}
- 业务负责人：{负责人}

**趋势对比摘要（{告警日} vs {参考日}）：**
- 告警日均值：{today_avg}，参考日均值：{compare_avg}，变化：{change_pct}%（↑/↓）
- 峰值：{peak_hour}:00 = {peak_value}，谷值：{trough_hour}:00 = {trough_value}
- 一句话概括：{告警时段的主要趋势描述}

**多维度下钻（{N}个维度有数据）：**
- {dim1}：{top3值+变化率，⚠️标注异常}
- {dim2}：...（按维度逐一列出，异常维度置顶）

**根因分析：**
- 主要异常维度（top3）：{dim}, {dim}, {dim}
- 变化情况：{异常维度下的值 + 变化率}，异常集中在 {pagePath/版本等}
- 建议：{1-3条具体操作建议}

![分析图表](S3Plus URL 或本地路径)
```

## 示例

**输入（告警消息片段）：**
```
[大前端监控][P2] 告警名称: 首页FFP下降
数据时间：2026-03-18 14:00  告警时间：2026-03-18 14:05
PERF:ffp_msc.ratio  触发规则: < 0.88，最近3个点值 [0.85, 0.84, 0.83]
业务负责人：zhangsan
```

**输出摘要：**
```
🚨 P2 首页FFP下降
指标：ffp_msc.ratio（COMPOSITE，统计含义：FFP 成功率比率）
趋势：告警日均值 0.843，参考日 0.891，下降 5.4%↓，14:00 出现明显拐点
异常维度 top1：appVersion（12.53 ⚠️ -8.2%，12.52 正常）
建议：重点排查 12.53 版本近期发版变更，确认是否引入回归
```

## 注意事项

- ATOM 指标用 `--metrics-type atom`，COMPOSITE 指标用 `--metrics-type composite`
- 趋势查询建议 `--agg ONE_HOUR`；如需日级对比用 `--agg DAY`
- 若 `get-trend` 返回空数据，可尝试调整时间范围或使用 `dimension-analyse` 替代
- 维度优先级与超高基数维度跳过规则详见 [references/dims.md](references/dims.md)
