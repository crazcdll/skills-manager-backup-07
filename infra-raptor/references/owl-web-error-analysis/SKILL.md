---
name: owl-web-error-analysis
display_name: OWL Web端异常波动分析
description: >
  对 Web 端（OWL）JS 异常进行多维度波动分析，定位异常次数/异常率/影响用户数上涨或下降的根因。
  支持三种触发方式：①用户自然语言描述分析 Web/OWL 端异常波动诉求；②用户发送 Raptor Web 端异常页面链接并提出分析诉求；③用户转发前端异常告警消息。
  分析流程：整体趋势对比→Top N 聚类定位→按页面/容器/OS 等多维下钻→拉取异常日志明细→查看完整堆栈→输出分析报告。
  触发词：分析web异常、分析OWL异常、分析JS错误波动、web端异常分析、前端异常分析、JS_ERROR分析、分析前端异常根因、web异常波动。
  注意：如果用户只是简单查询数据（如"查一下最近7天web异常数量"），不要触发本技能，使用 raptorfe-allquery 子技能即可。
tags: 终端基础技术,Raptor,Web,OWL,前端异常,JS错误
version: 0.1.0
created: 2026-05-26
metadata:
  skillhub:
    creator: zhangxinyue27
---

# OWL Web 端异常波动分析

## 目标

对 Web 端（OWL）的 JS 异常/资源异常/Promise 异常进行多维度波动分析，找到异常次数、异常率、影响用户数上涨或下降的根因，深入堆栈分析并给出可执行的修复建议。

---

## 🔧 前置依赖

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 触发判断

**本技能处理的场景：**
- 用户明确说"分析 web 端 / OWL 端异常"，且有分析诉求（波动、根因、趋势分析）
- 用户发送 `raptor.mws.sankuai.com/frontend/error/...` 或 `/frontend/multi-dimension-analyse` 链接，并要求分析
- 用户转发/粘贴包含 `[前端异常]` 的告警消息

**以下情况不触发本技能：**
- 用户只是简单查数（如"查一下 web 端异常数量"） → 路由到 `raptorfe-allquery`
- 用户分析的是移动端 Crash/ANR/FOOM → 路由到 `crash-wave-analysis`
- 用户分析的是 RCF 分数 → 路由到 `rcf-raptor-anylisize`
- 用户分析的是通用指标（非异常类） → 路由到 `general-metric-analysis`

---

## 第一步：解析用户输入，确认分析参数

### 场景 A：自然语言描述

从用户描述中提取：
- **项目名/项目 ID**：如 `com.sankuai.videoactivity.msc.goodsmarket` 或 `41209`
- **异常类型**：JS_ERROR（默认）/ RESOURCE_ERROR / PROMISE_ERROR
- **时间范围**：用户未指定时默认最近 7 天
- **异常等级**：默认 `error`，用户提到 warn 时加入

若用户只给了项目名（如 `goodsmarket`），先查项目 ID：

```bash
raptorfe web project search --name goodsmarket
```

### 场景 B：Raptor Web 端 URL

解析 URL 参数，提取查询条件：

| URL 路径特征 | 关键参数 |
|------------|---------|
| `/frontend/error/list` | `projectId`、`start`/`end`（格式 `YYYYMMDDHHmmss`）、`errorType`（即 logType） |
| `/frontend/multi-dimension-analyse` | `projectId`、`start`/`end`、`metricName`（errorCount/errorRate/userCount） |

**时间参数解析：**
- URL 中 `start=20260526153800` → 解析为 `2026-05-26 15:38:00`，转为毫秒时间戳或日期字符串
- 注意：URL 中的时间范围通常很短（几分钟），分析时需要扩大时间窗口

### 场景 C：告警消息

从告警文本中提取：

| 字段 | 提取规则 |
|------|---------|
| 告警级别 | `\[(P\d)\]` |
| 项目名 | `\[项目:\s*(.+?)\]` |
| 告警指标 | `\[告警指标:\s*(.+?)\s*\]`（错误总量 / 错误率 / 影响用户数） |
| 触发值 | `最近\d+个点值:\[(.+?)\]` |
| 数据时间 | `数据时间：(.+?)[\(（]` |
| projectId | 从"查看数据"链接中提取 `projectId=(\d+)` |
| logType | 从"查看数据"链接中提取 `errorType=(\w+)`，默认 JS_ERROR |
| 时间范围 | 从"查看数据"链接提取 `start`/`end`，但**必须扩大时间窗口**用于分析 |

**关键：告警消息中"查看数据"链接的时间范围通常只有几分钟，不能直接用于分析。** 需要根据告警时间，构造以下对比时间窗口：
- 当前窗口：告警时间前 1 小时
- 对比窗口 1：24 小时前同时段
- 对比窗口 2：7 天前同时段（168 小时前）

---

## 第二步：查整体趋势（基线）

对三个核心指标分别查询趋势，确认波动的时间点和幅度。

```bash
# 1. 错误次数趋势
raptorfe web error get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --metric-type errorCount \
  --log-type JS_ERROR \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY

# 2. 错误率趋势
raptorfe web error get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --metric-type errorRate \
  --log-type JS_ERROR \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY

# 3. 影响用户数趋势
raptorfe web error get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --metric-type userCount \
  --log-type JS_ERROR \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY
```

**参数说明：**
- `--metric-type`：`errorCount`（错误次数）| `errorRate`（错误率）| `userCount`（影响用户数）
- `--log-type`：`JS_ERROR` | `RESOURCE_ERROR` | `PROMISE_ERROR`
- `--page-id`：页面 ID，不传则查全部页面。若已知页面 ID 可加 `--page-id <id>`
- `--query-param`：JSON 字符串过滤条件，如 `'{"LEVEL":["error"]}'`
- `--time-size`：`DAILY`（天级）| `HOURLY`（小时级）| `MINUTELY`（分钟级）
- `--start-long` / `--end-long`：毫秒时间戳或日期字符串（如 `"2026-05-26"`）

**分析要点：**
- 标记波动的起始时间点和幅度（如"5月25日错误量从 100 骤升到 500"）
- 判断是突发型（某天骤升）还是趋势型（持续恶化）
- 三个指标若趋势一致，说明是真实异常增长；若 errorCount 增但 errorRate 降，可能是流量增长

**告警场景的时间对比策略：**

当从告警消息触发时，需要做多时段对比。假设告警时间为 T：

```bash
# 当前时段（告警前 1 小时，分钟级）
--start-long <T - 1h> --end-long <T> --time-size MINUTELY

# 24 小时前对比（同样 1 小时窗口）
--start-long <T - 25h> --end-long <T - 24h> --time-size MINUTELY

# 7 天前对比
--start-long <T - 169h> --end-long <T - 168h> --time-size MINUTELY
```

若需要看更大趋势，再查最近 7 天天级数据：

```bash
--start-long <T - 7d> --end-long <T> --time-size DAILY
```

---

## 第三步：查 Top N 异常聚类

定位贡献最大的异常名称（errorCategory），这是后续下钻和堆栈分析的入口。

```bash
raptorfe web error get-groups \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --log-type JS_ERROR \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY \
  --limit 20
```

**分析要点：**
- 按错误次数排序，找出 Top 5 贡献最大的异常
- 对比波动时间段和基线时间段，找出**新增的**或**增长幅度最大的**异常聚类
- 记录异常名称（errorCategory），用于后续 get-error-detail 查询

---

## 第四步：多维下钻

在确认了 Top 异常聚类后，进一步分析各维度的分布情况。

### 4.1 按页面维度下钻（优先级最高）

```bash
# 指定特定页面查趋势
raptorfe web error get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --metric-type errorCount \
  --log-type JS_ERROR \
  --page-id <pageId> \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY
```

> 若不知道页面列表，可以从 get-error-detail 返回的 `data1`（页面 URL）字段聚合分析。

**分析要点：**
- 是全部页面都异常，还是集中在某几个页面
- 若集中在特定页面，记录页面路径，后续聚焦该页面分析

### 4.2 按容器维度下钻

从 get-error-detail 返回的 `data5`（容器）字段聚合分析：
- 区分 Chrome PC / 美团小程序 / 微信小程序 / App WebView 等
- 判断是否只有某种容器环境出问题

### 4.3 按 OS 维度下钻

从 get-error-detail 返回的 `data6`（系统）字段聚合分析：
- 区分 Android / iOS / Mac OS X / Windows 等
- 判断是否与操作系统相关

### 4.4 按异常类型维度（logType）

分别查 JS_ERROR、RESOURCE_ERROR、PROMISE_ERROR 的趋势对比：

```bash
# 对比不同 logType
raptorfe web error get-trend \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --metric-type errorCount \
  --log-type RESOURCE_ERROR \
  --query-param '{"LEVEL":["error"]}' \
  --time-size DAILY
```

---

## 第五步：拉取异常日志明细

对 Top 异常聚类，拉取具体的日志记录。

```bash
raptorfe web error get-error-detail \
  --project-id <projectId> \
  --start-long <time> --end-long <time> \
  --error-category "<异常名称>" \
  --limit 5 --page-size 5
```

**返回字段：**

| 字段 | 含义 |
|------|------|
| `main` | 上报时间 |
| `id` | errorLogId（用于查完整堆栈） |
| `data1` | 页面 URL |
| `data2` | 资源 URL（RESOURCE_ERROR 时有值） |
| `data3` | 异常类型（jsError / resourceError / promiseError） |
| `data4` | 用户 ID（unionId） |
| `data5` | 容器（Chrome PC / 美团小程序 等） |
| `data6` | 系统（Android / iOS / Mac OS X 等） |

**分析要点：**
- 汇总 data5（容器）、data6（系统）的分布 → 补充第四步的容器/OS 维度结论
- 汇总 data1（页面 URL）的分布 → 确认是否集中在特定页面
- 提取 id（errorLogId）用于下一步堆栈分析

---

## 第六步：查看完整堆栈

对 Top 异常的多条日志（建议至少 3 条），拉取完整堆栈：

```bash
raptorfe web error get-log-detail \
  --error-log-id <errorLogId> \
  --log-date <对应时间的毫秒时间戳或日期字符串>
```

> `--log-date` 使用该条日志 `main` 字段对应的时间戳（毫秒时间戳或日期字符串均可）。

**堆栈分析要点：**
- 提取堆栈中的**文件路径**和**行号**
- 识别是业务代码还是框架/三方库代码
- 判断错误模式：空指针（Cannot read properties of undefined）、类型错误、网络错误等
- 若多条日志的堆栈指向同一位置，确认该位置为根因代码

---

## 第七步：输出分析报告

汇总各步骤分析结果，输出结构化报告：

```markdown
# Web 端异常波动分析报告

## 基本信息
- 项目：<项目名>（projectId: <id>）
- 异常类型：<JS_ERROR / RESOURCE_ERROR / PROMISE_ERROR>
- 分析时间范围：<start> ~ <end>
- 告警级别：<P1/P2/P3>（如有）

## 1. 整体趋势
- 错误次数：<趋势描述，如"5月25日从日均100次骤升至500次">
- 错误率：<趋势描述>
- 影响用户数：<趋势描述>
- 波动类型：<突发型 / 趋势型 / 周期性>

## 2. Top 异常聚类
| 排名 | 异常名称 | 错误次数 | 影响用户数 | 是否新增 |
|------|---------|---------|-----------|---------|
| 1 | <errorCategory> | <count> | <users> | <是/否> |
| ... | ... | ... | ... | ... |

## 3. 维度下钻
### 页面维度
- 异常集中页面：<页面路径>
- 结论：<全局问题 / 特定页面问题>

### 容器维度
- 异常分布：<Chrome PC: X%, 美团小程序: Y%...>
- 结论：<是否特定容器问题>

### 系统维度
- 异常分布：<Android: X%, iOS: Y%...>
- 结论：<是否特定系统问题>

## 4. 堆栈分析
### 异常 1：<errorCategory>
- 错误信息：<error message>
- 关键堆栈：
  ```
  <堆栈关键帧>
  ```
- 根因判断：<空指针/类型错误/接口异常/资源加载失败等>
- 涉及文件：<文件路径:行号>

## 5. 根因定位
**初步根因：**
<综合以上分析，初步判断根因为...>

**影响范围：**
- 影响页面：<X 个页面>
- 影响用户：<约 X 人>
- 影响时间：<从 XX 开始，持续 X 小时>

## 6. 修复建议
1. <建议1：如修复空指针检查>
2. <建议2：如增加异常兜底处理>
3. <建议3：如回滚某版本>
```

---

## CLI 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|---------|
| `raptorfe web project search --name <关键词>` | 查项目 ID | 模糊匹配项目名 |
| `raptorfe web error get-trend` | 异常趋势（错误量/率/用户数） | `--metric-type`、`--log-type`、`--time-size` |
| `raptorfe web error get-groups` | Top N 异常聚类 | `--limit` |
| `raptorfe web error get-error-detail` | 某异常的日志明细列表 | `--error-category`、`--limit`、`--page-size` |
| `raptorfe web error get-log-detail` | 单条日志的完整堆栈 | `--error-log-id`、`--log-date` |

### 时间格式

所有时间参数均支持**毫秒时间戳或日期字符串**（`--start-long` / `--end-long` / `--log-date`），如 `"2026-05-26"` / `"2026-05-26 10:00:00"`。

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--project-id` | 项目 ID（数字） | 必填 |
| `--start-long` | 开始时间（毫秒时间戳或日期字符串） | 必填 |
| `--end-long` | 结束时间（毫秒时间戳或日期字符串） | 必填 |
| `--log-type` | 异常类型 | `JS_ERROR` |
| `--page-id` | 页面 ID，不传查全部 | - |
| `--query-param` | JSON 过滤条件 | `'{"LEVEL":["error"]}'` |
| `--time-size` | 时间粒度 | `DAILY` |
| `--limit` | 返回条数 | 10 / 20 |

---

## 告警消息解析规则

### 识别特征

消息包含以下**任意组合**时触发：
- `[前端异常]` 标签
- `[告警指标: 错误总量]` 或类似格式
- `raptor.mws.sankuai.com/frontend/error/` 链接
- `raptor.mws.sankuai.com/frontend/multi-dimension-analyse` 链接

### 字段提取

```
[P3]                                    → 告警级别
[前端异常]                               → 触发本技能
[项目: com.sankuai.xxx.goodsmarket]      → 项目名
[告警名称: Raptor项目组测试告警-忽略]      → 告警名称
[告警指标: 错误总量]                      → 分析指标（errorCount/errorRate/userCount）
最近3个点值:[1,2,2]                      → 触发值序列
数据时间：2026-05-26 15:40:00            → 数据时间点
告警时间：2026-05-26 15:41:36            → 告警时间点
```

从"查看数据"链接中提取：
```
http://raptor.mws.sankuai.com/frontend/error/list?type=datetimerange&start=20260526153800&end=20260526154000&projectId=41209&errorType=JS_ERROR
→ projectId=41209, logType=JS_ERROR, start/end（仅供参考，需扩大）
```

### 告警指标映射

| 告警文本 | metric-type |
|---------|-------------|
| 错误总量 | errorCount |
| 错误率 | errorRate |
| 影响用户数 | userCount |

---

## 注意事项

1. **时间参数必须忠实于原始输入**：从 URL 或告警消息中解析出的时间（如 `start=20260526154100` → `2026-05-26 15:41:00`），传给 CLI 时**必须严格使用解析出的年月日**，禁止手动重新输入年份。推荐直接传日期字符串（如 `--start-long "2026-05-26 15:41:00"`），也可传毫秒时间戳。

2. **时间窗口扩大**：告警消息中的链接时间范围通常只有几分钟，分析时必须扩大到至少 1 小时，并与 24h 前、7d 前对比。

3. **分析顺序**：先看整体趋势确认波动 → 再看聚类定位罪魁祸首 → 再做多维下钻确认影响范围 → 最后看堆栈定位代码。每一步完成后立即输出中间结论，不要等所有步骤做完再输出。

4. **堆栈分析深度**：对 Top 3 异常聚类，每个至少看 3 条堆栈日志，确认是同一根因还是多因叠加。

5. **代码仓库定位**：当堆栈指向压缩后的代码（如 `chunk-xxx.js:1:23456`），无法直接对应源码，此时仅分析错误模式和上下文。若能从项目名推断出代码仓库（如 `com.sankuai.xxx.perf` → `met/perf`），可在报告中给出仓库链接 `https://dev.sankuai.com/code/repo-detail/<project>/<repo>/file/list` 供人工进一步排查，不要尝试自动检索代码内容。

6. **鉴权**：`raptorfe` CLI 内置自动 SSO 鉴权，无需手动传 Cookie。命令执行后可能沉默 10～30 秒，属正常现象。

7. **logType 默认值**：若用户未指定异常类型，默认分析 `JS_ERROR`。若 JS_ERROR 趋势正常但整体异常量升高，需要逐一排查 RESOURCE_ERROR 和 PROMISE_ERROR。

8. **数据展示**：查询结果用 Markdown 表格展示，异常数据用**加粗**标注。趋势数据可配合文字描述波动方向和幅度。
