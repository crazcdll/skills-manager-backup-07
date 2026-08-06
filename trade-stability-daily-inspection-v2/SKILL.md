---
name: trade-stability-daily-inspection-v2
description: 交易前端异常日报、周报生成工具（v2）。通过 raptorfe CLI 的 get-summary-table 命令统一查询交易前端项目的监控数据（平铺全量，避免 get-groups 的「其他」聚合桶折叠），生成每日异常报告。较上周首现异常直接取 get-summary-table 返回体自带的 newErrors 字段判断，无需依赖 hotel-raptor-tool。触发词：异常日报、异常周报、前端异常报告、生成报告、Raptor 日报、异常分析报告。
skill-dependencies:
  mtsso-skills-official:
    # 按需声明，只写你实际用到的票据类型

    # 如果需要用户身份票据，声明此项：
    user_access_token_placeholder: ${user_access_token}

metadata:
  skillhub.creator: "yuweijie04"
  skillhub.updater: "yuweijie04"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "108467"
  skillhub.high_sensitive: "false"
---

# 交易前端异常日报、周报生成工具（v2）

---

## 概述
通过 Raptor 大前端监控查询交易前端项目的异常数据并生成分析报告。

**v2 与 v1 的核心差异（方案 A：单一数据源）：**
- v1 的 A1/A2 用 `get-groups`（树形、Top N 截断、含「其他」聚合桶），首现异常（A3）**强依赖** hotel-raptor-tool 的 `RaptorClient.fetchAllErrors()`（需浏览器 Cookie 权限）。
- v2 将 **A1 / A2 / A3 统一到 `raptorfe web error get-summary-table` 单一数据源**：该接口返回平铺全量异常列表（`table.rows`），**不存在「其他」聚合桶折叠问题**，保证异常总数/暴涨数/首现数口径可复现。
- **A3 首现异常直接取 A1 本期返回体自带的 `newErrors` 字段**（同一份返回里既有 `newErrors` 又有 `table.rows` 含 COUNT，无需额外请求、无需 join）。实测与 hotel-raptor-tool 首现数 100% 一致，因此 v2 不再需要 hotel-raptor-tool。

## 前置条件
用户需要安装以下 skill，如果未安装，则需要提醒用户安装：
- infra-raptor（提供 raptorfe CLI，**必需**）
- hotel-raptor-tool（**可选**，仅用于对首现异常做交叉校验；缺失不影响任何功能）

> ⚠️ **鉴权说明**：raptorfe CLI 内置 SSO 自动鉴权（缓存 2.5h），首次触发会向大象 App 推送授权请求。命令执行后可能沉默 10~30 秒属正常现象，遇到鉴权提示时引导用户去大象 App 点击确认，**不要向用户索要 Cookie**。

## 异常报告生成流程

### 第一步：解析参数并预检 token
根据用户提供的 业务方向（category）、项目名称列表（projectNames，可多个）及周期（start, end），确定本周期和较上期周期的时间范围。
- 用户使用时必须提供业务方向(category)
- 如果未提供项目名称列表，则按业务方向去[assets.md](references/assets.md)获取对应方向的对应项目名称列表
- 如果未提供周期，则默认查昨日（北京时间）的数据
- 如果用户提供了上述参数，则按照用户输入的进行查询

**时间格式转换：**
- ⚠️ **时间戳必须通过命令行工具计算，禁止 AI 自行推算**
> 必须先执行以下命令获取正确时间戳，再传给查询工具：
> ```bash
> node -e "d='2026-04-22'; console.log(new Date(d+'T00:00:00+08:00').getTime(), new Date(d+'T23:59:59+08:00').getTime())"
> ```
- raptorfe CLI、hotel-raptor-tool 格式（startMs/endMs）：Unix 毫秒时间戳
- HTML 链接格式：`yyyy-MM-dd HH:mm:ss`

### 第二步：并行查询所有项目数据
假设有 n 个项目，**同时启动 n 个子代理**，每个子代理负责一个项目的全部数据查询。
先使用**raptorfe CLI** (`raptorfe web project search --name`)查询各个项目的 projectId。
返回的示例如下
```
{
  "ok": true,
  "data": [
    {
      "id": 12255,
      "name": "rn_travel_order-detail",
      "displayName": "rn_travel_order-detail",
      "bu": null
    }
  ]
}
```
其中返回的 id 为 projectId。

#### 子代理内部执行顺序（针对单个项目）

**Step A：并行查询异常数据**

先查 [assets.md](references/assets.md) 方向级配置表，读取当前方向的以下配置项，并将其随数据一并返回给主代理：
- `filter_ignored_errors`：决定是否启动 A4
- `surge_threshold`：环比暴涨判定阈值（百分比整数，默认 50），用于第三步计算暴涨条数

> 🟢 **v2 数据源统一（方案 A）**：A1 / A2 / A3 **全部以 `raptorfe web error get-summary-table` 为唯一数据源**。该接口返回**平铺全量**异常列表（`table.rows`，每行一条具体异常 + COUNT），且返回体自带 `newErrors` 字段。
>
> 相比旧的 `get-groups`，`get-summary-table` **不存在「其他」聚合桶折叠问题**——`get-groups` 每个分组默认只展开 Top 20 个高频具体异常，剩余低频异常被合并进一个名为「其他」的桶，只给汇总数字、丢失明细（而首现异常往往就藏在这些低频项里）。用 summary-table 平铺列表可彻底规避该问题，保证异常总数、暴涨数、首现数三个口径可复现、可对齐。

| 请求 | 工具 | 说明 |
|------|------|------|
| A1 | **raptorfe CLI** (`raptorfe web error get-summary-table`) | 查询**本周期完整异常列表**（平铺全量 `table.rows`），**同一次返回体自带 `newErrors` 字段直接供 A3 使用** |
| A2 | **raptorfe CLI** (`raptorfe web error get-summary-table`) | 查询**环比周期完整异常列表**（平铺全量，用于精确环比对比） |
| A3 | **首现异常（直接取 A1 返回的 `newErrors`）** | 较上周首现异常 = A1 本期 summary-table 各页合并去重后的 `newErrors`；**无需单独发起请求**。详见下方【A3 首现异常执行规范】 |
| A4 | **raptorfe CLI** (`raptorfe web error get-summary-table`) | **仅当 `filter_ignored_errors=true` 时执行**：获取已忽略异常名单（STATUS=4 或 5） |

A1、A2 并行执行（两个时间窗各一组分页请求）；A3 直接复用 A1 的返回，不额外请求；A4 仅在 `filter_ignored_errors=true` 时与 A1/A2 **同时并行**启动。

> ⚠️ **`get-summary-table` 分页硬上限（必须遵守，否则死循环）**：该接口**最多只返回前 500 条**（`offset` 达到 500 后，返回体的 `data` 字段会变为 `undefined`/空，即使 `data.total` > 500）。因此分页循环的终止条件必须同时满足：**(1) `offset + limit >= data.total` 或 (2) 本页 `data` 为空/`rows` 为 0 或 (3) `offset >= 500`**。任一命中即停止，禁止仅用 `offset >= total` 作为唯一终止条件。

##### 🔑 突破 500 上限拿精确总数（log-type 分片，`data.total > 500` 时必做）

当某项目 `data.total > 500` 时，不分片只能拿到前 500 条，会同时导致**异常总数被截断**、**首现异常漏统计**（实测门票填单页 31960 曾因此少统计 35 条首现：123 → 实际 158）。此时**必须按 `--log-type` 分片查询后合并去重**来还原精确全量：

- **分片维度**：`--log-type` 取值 `JS_ERROR | AJAX_ERROR | CUSTOM_ERROR`（大写下划线，CLI `--help` 口径；小写 `jsError` 会返回空）。这三类基本覆盖交易前端全部异常，各分片一般都 < 500，从而绕开硬上限。
- **执行**：对每个 log-type 各跑一遍完整分页（终止条件仍遵守 500 硬上限规则，作为兜底保护），拿到各分片的 `rows` 与 `newErrors`。
- **合并**：
  - `currentErrors` = 三分片 `rows` 按 `main.strip()` 去重合并；`newErrors` = 三分片 `data.newErrors` 并集去重。
  - **自检**：合并去重后的条数应等于**不分片查询返回的 `data.total`**（实测 31960：JS_ERROR 86 + AJAX_ERROR 85 + CUSTOM_ERROR 390 = 561 = 不分片 `data.total`）。不相等说明存在第 4 类 log-type 或某分片自身 > 500，需继续拆分（如叠加时间维度分片）。
- **分片分页终止条件（务必用 `>=`）**：`offset += limit; if (rows.length === 0) break; if (offset >= total) break; if (offset >= 500) break;`。⚠️ 不要写成 `offset + limit > total` —— 当 `total=390` 时会在 `offset=300`（400>390）提前退出，漏掉最后一页 90 条。
- A2（环比周期）若 `total > 500` 同样按此分片，保证环比口径一致、变化率可比。
- **何时触发**：仅对 `data.total > 500` 的项目分片；`total ≤ 500` 的项目一次分页即可，无需分片，避免多余请求。
- 触发分片时，在项目结果中标注 `method: "sharded-by-logtype(JS_ERROR+AJAX_ERROR+CUSTOM_ERROR)"`，便于 Footer 溯源。

---

#### 【A1 / A2 数据采集执行规范】（v2 核心）

A1（本周期）、A2（环比周期）**均使用 `raptorfe web error get-summary-table`** 拉取平铺全量异常列表。

**调用与分页（以本周期为例，A2 只换时间窗）：**
```bash
raptorfe web error get-summary-table \
  --project-id {projectId} \
  --start-long {startMs} --end-long {endMs} \
  --web-version all \
  --page-size 100 --limit 100 --offset 0 \
  --time-size DAILY \
  --output json
```

**返回体结构（关键字段）：**
```json
{
  "ok": true,
  "data": {
    "total": 429,
    "table": {
      "columns": ["main","CATEGORY","LEVEL","STATUS","COUNT","USER_COUNT","DATE"],
      "rows": [
        {"main":"ct_poi 的值不能是 undefined","CATEGORY":"jsError","LEVEL":"info","STATUS":5,"COUNT":1171294,"USER_COUNT":506303,"DATE":"..."}
      ]
    },
    "newErrors": ["<较上周首现异常名>", "..."],
    "mrnNewErrors": null
  }
}
```

**处理规则：**
1. **循环分页拉全量**：`--limit 100`（最大 100，超过会报「翻页参数异常或单页数量过大」），每轮 `--offset += 100`。**终止条件遵守上方分页硬上限规则**（`offset+limit>=total` 或 本页 `data` 空 或 `offset>=500`，任一命中即停）。合并所有页的 `data.table.rows`。**若首页返回的 `data.total > 500`，改走上方【🔑 突破 500 上限拿精确总数（log-type 分片）】方案，否则总数与首现都会被截断。**
2. **展平构建异常列表**：`rows` 已是平铺结构，直接把每行的 `main`（错误名）与 `COUNT`（出现次数）映射为 `{errorName: row.main.strip(), count: row.COUNT}`。**无需展平树、无需处理「其他」桶**。
3. A1 得 `currentErrors: [{errorName, count}]`；A2 得 `previousErrors: [{errorName, count}]`。
4. `main` 字段可能含尾部空格或转义差异，统一 `.strip()` 后作为 errorName。

---

#### 【A3 首现异常执行规范】（v2 核心）

A3 的目标：拿到 `newErrors`（较上周同期首现异常名列表）及各自出现次数。

**A3 直接复用 A1 本周期 summary-table 的返回，不发起任何新请求：**

1. **`newErrors` 来自 A1 各页返回体的 `data.newErrors` 合并去重**：`newErrors = Set(A1 各页 data.newErrors)`。若返回体同时含 `mrnNewErrors`（MRN 项目专用首现）且非空，一并并入。
2. **出现次数从 A1 同一份 `table.rows` 取**（同源，errorName 完全一致，无 join 失配风险）：
   ```python
   rowCountMap = { row["main"].strip(): row["COUNT"] for row in A1_all_rows }
   newErrorsWithCount = [
       {"errorName": name.strip(), "count": rowCountMap.get(name.strip(), 0)}
       for name in newErrors
   ]
   ```
3. `newErrors` 含义为「本周期相比上周同期新出现」，**不是**「历史上从未出现」。
4. ⚠️ 因 summary-table 分页硬上限 500，若 `data.total > 500`，`newErrors` 只覆盖前 500 条内的首现异常；此时在报告 Footer 注明「首现异常基于前 500 条统计」。

> 📌 **`newErrors` 与 hotel-raptor-tool 完全等价**：hotel-raptor-tool 的 `fetchAllErrors` 与本命令调用的是同一后端接口（`/cat/fe/log/summaryTable`）、读同一个 `newErrors` 字段。实测 7 项目首现数 100% 一致。因此 v2 不再需要 hotel-raptor-tool。

##### （可选备份）hotel-raptor-tool

若已安装 hotel-raptor-tool 且希望用它做交叉校验，可调用 `RaptorClient.fetchAllErrors(projectName, startMs, endMs)` 获取 `{ rows, newErrors }` 与 A1 的 `newErrors` 比对。**但这不是必需路径**——hotel-raptor-tool 未安装、Cookie 抓取失败、接口 302/401、超时等任何情况下，**一律以 A1 summary-table 的 `newErrors` 为准，不中断流程、不向用户索要 Cookie**。可在 Footer 注明 `newErrorsSource`。

---

> ⚠️ **A4 执行规范**（仅 `filter_ignored_errors=true` 时）：
> - ⚠️ **不传 `--log-type` 参数**，这样 summary-table 接口会返回所有类型（jsError、ajaxError 等）的异常汇总，一次性获取完整忽略名单
> - ⚠️ **时间范围必须使用最近 24h**（`startMs = now - 86400000`, `endMs = now`），因为 summary-table 接口对历史时间有限制（太早会报「查询开始时间太早」）。STATUS 标记是全局性的，不随时间段变化，用当前窗口即可获取准确的忽略名单
> - 调用：`raptorfe web error get-summary-table --project-id {projectId} --start-long {startMs} --end-long {endMs} --web-version all --limit 100`
> - ⚠️ `limit` 最大为 **100**，超过会返回「翻页参数异常或单页数量过大」错误
> - rows 路径为 `data.table.rows`（不是 `data.rows`），分页总数取 `data.total`
> - 循环分页（`--offset` 递增 100），直到 offset >= total 为止，合并所有页结果
> - 从返回数据中筛选 `STATUS == 4`（完全忽略）或 `STATUS == 5`（暂时忽略）的条目（无论 `CATEGORY` 是 jsError 还是 ajaxError）
> - 提取这些条目的 `main` 字段，构建**已忽略异常名单** `ignoredErrorNames: Set<string>`
> - 若 A4 调用失败（HTTP 错误或超时），**不阻塞流程**，视为空名单继续执行，并在报告 Footer 注明「已忽略异常过滤不可用」
>
> 示例（伪代码）：
> ```python
> import time
> now_ms = int(time.time() * 1000)
> start_ms = now_ms - 86400000  # 最近24h
> ignoredErrorNames = set()
> offset = 0
> while True:
>     result = get_summary_table(projectId, start_ms, now_ms, limit=100, offset=offset)
>     rows = result['data']['table']['rows']
>     for row in rows:
>         if row['STATUS'] in [4, 5]:
>             ignoredErrorNames.add(row['main'].strip())
>     if offset + 100 >= result['data']['total']:
>         break
>     offset += 100
> ```

> 💡 **实现提示**：A1/A3 与 A4 调用的是同一个 `get-summary-table` 命令，区别在于 A4 用最近 24h 且不传 log-type（拿 STATUS=4/5 忽略名单），A1 用本周期时间窗（同时拿 rows 与 newErrors）。两者时间窗不同（A4 需最近 24h 才能规避历史时间限制），必要时分开调用更稳妥。

**Step B：过滤已忽略异常并汇总返回结果**

等待 A1、A2、A3（以及 A4，若已启动）全部完成后，按以下顺序处理：

**B1：如果 `filter_ignored_errors=true` 且 A4 成功获取了 `ignoredErrorNames`，则执行剔除：**
```python
# 从 currentErrors 中剔除已忽略异常
currentErrors = [e for e in currentErrors if e["errorName"] not in ignoredErrorNames]

# 从 previousErrors 中剔除已忽略异常
previousErrors = [e for e in previousErrors if e["errorName"] not in ignoredErrorNames]

# 从 newErrors 中剔除已忽略异常
newErrors = [name for name in newErrors if name not in ignoredErrorNames]
```
> ⚠️ 剔除在所有计数前执行，剔除后的列表才是后续计算 currentTotalErrors、NEW_COUNT、SURGE_COUNT 的基准。

**B1.5：过滤校验断言（必须执行）**

过滤完成后，**必须**运行以下校验逻辑，确保忽略异常被真正剔除：
```python
# 校验：过滤后的 currentErrors 中不应包含任何已忽略异常
overlap = [e["errorName"] for e in currentErrors if e["errorName"] in ignoredErrorNames]
assert len(overlap) == 0, f"过滤失败！仍有 {len(overlap)} 条已忽略异常残留: {overlap[:5]}"

# 校验：ignoredCount = 过滤前条数 - 过滤后条数，必须 > 0（否则说明匹配规则有问题）
ignoredCount = len_before_filter - len(currentErrors)
if len(ignoredErrorNames) > 0 and ignoredCount == 0:
    # 可能是字段名不匹配（main vs errorName 格式差异），需要做模糊匹配兜底
    print(f"WARNING: ignoredErrorNames 有 {len(ignoredErrorNames)} 条但未命中任何 currentError，检查字段格式")
```

> ⚠️ **字段匹配注意事项**：`get-summary-table` 返回的 `main` 字段可能与 `get-groups` 返回的 `errorName` 存在细微格式差异（如尾部空格、特殊字符转义）。过滤时应对两侧做 `.strip()` 处理后再比较。若 strip 后仍匹配率为 0，需在报告中标注「已忽略异常过滤可能未生效」。

**B2：将以下数据结构化返回给主代理：**
```json
{
  "projectName": "<项目名>",
  "projectId": "<projectId>",
  "currentErrors": [
    { "errorName": "<错误名称>", "count": "<出现次数>" }
  ],
  "previousErrors": [
    { "errorName": "<错误名称>", "count": "<出现次数>" }
  ],
  "newErrors": ["<首现异常名称列表>"],
  "newErrorsCount": "<首现异常数>",
  "newErrorsSource": "raptorfe-summary-table",
  "ignoredCount": "<被剔除的已忽略异常数，未启用过滤时为 0>",
  "ignoredErrorNames": ["<被忽略的异常名称列表，用于主流程二次校验>"],
  "surgeThreshold": "<当前方向的暴涨阈值，如 50>",
  "summary": {
    "currentTotalErrors": "<本周期异常总数>",
    "previousTotalErrors": "<环比周期异常总数>"
  }
}
```

> 📌 `newErrorsSource` 字段用于标注本项目首现异常的实际数据来源（默认 `raptorfe-summary-table`；若额外用 hotel-raptor-tool 交叉校验则可标注），供 Footer 汇总提示使用。

### 第三步：异常数量计算规则

> 🔴 **关键**：区分三个不同的异常数量概念，避免混淆

#### 计数规则详解

| 概念 | 定义 | 数据来源 | 计算方法 | 用途 |
|------|------|---------|---------|------|
| **异常条数** | 去重后的异常名称数量 | A1（summary-table 平铺全量 rows） | `len(currentErrors)` | 概览模块的"异常条数" |
| **首现异常数** | 较上周同期首次出现的异常 | A3（A1 summary-table 返回的 newErrors） | `len(newErrors)` | 概览模块的"首现条数" |
| **暴涨异常数** | 变化率超过 `surge_threshold`％ 的异常分组数 | 对比 A1 vs A2 | 逐条计算变化率 | 概览模块的"暴涨条数" |

#### 验证清单（生成HTML前必须验证）

```
# ① 异常条数验证
异常条数 = len(currentErrors)  # 从 A1 summary-table 平铺 rows 直接取
验证：异常条数应该是个合理的数字（如 21，而非 3570）

# ② 首现条数验证（关键！）
首现条数 = len(newErrors)  # 来自 A3（= A1 summary-table 返回的 newErrors）
验证条件：首现条数 ≤ 异常条数

# ③ 暴涨条数验证
暴涨条数 = 0
for error_name in currentErrors:
    current_count = error[error_name].count
    previous_count = previousErrors.get(error_name, {}).count or 0
    if previous_count > 0:
        change_rate = (current_count - previous_count) / previous_count * 100
        if change_rate > surge_threshold:  # 取当前方向的 surge_threshold，默认 50
            暴涨条数 += 1
    else:
        # 环比周期不存在，视为新增，也算暴涨
        暴涨条数 += 1
验证条件：暴涨条数 ≤ 异常条数
```

#### 环比对比规则

对本周期异常列表中的每一条异常，逐条判断：

| 情况 | 判断 | 处理 |
|------|------|------|
| 本周期有，环比周期也有 → 变化率 > `surge_threshold`% | 环比暴涨 ✅ | 纳入暴涨模块 |
| 本周期有，环比周期不存在 | 新增 ✅ | 纳入暴涨模块 |
| 本周期有，环比周期也有 → 变化率 ≤ `surge_threshold`% | 正常波动 | 不纳入暴涨模块 |
| 本周期无，环比周期有 | 已消失 | 在暴涨模块底部灰显 |

### 第三步半：主流程二次校验（生成 HTML 前必须执行）

主流程在读取各子代理返回的 JSON 数据后、生成 HTML 之前，**必须**对 `filter_ignored_errors=true` 的方向执行以下校验：

```python
# 对每个项目，用返回的 ignoredErrorNames 做交叉检查
for project in projects:
    ignored_set = set(project.get("ignoredErrorNames", []))
    if not ignored_set:
        continue
    current_names = {e["errorName"] for e in project["currentErrors"]}
    overlap = current_names & ignored_set
    if overlap:
        raise ValueError(f"[{project['projectName']}] 过滤未生效！{len(overlap)} 条忽略异常仍在 currentErrors 中: {list(overlap)[:5]}")
    print(f"✅ {project['projectName']}: 过滤验证通过，已剔除 {project['ignoredCount']} 条忽略异常")
```

> 若校验失败（overlap > 0），**不得继续生成 HTML**，而是重新执行该项目的过滤流程（strip 后重新匹配）。

### 第四步：生成 HTML
等多 agent 执行完成后，将上面多个项目汇总后生成一个 HTML 文件，如果多个业务方向，则生成多个 html 文件。

#### HTML 报告输出规范

> ❌ **禁止出现以下模块**（无论理由多充分，一律不得添加）：全量异常明细、完整异常列表、所有异常、异常汇总表、明细表格，或任何以"全量/完整/所有/汇总"命名的模块。HTML 中只允许存在：Header、项目概览、Tab 导航 + Tab 详情面板（每个面板含概览 KPI / 首现异常 / 环比暴涨三个 section）、Footer，共五个部分。

**必须严格以 [references/report-template.html](references/report-template.html) 为基础生成 HTML，不得自行设计样式或结构。** 生成步骤如下：

##### 4-1 读取模板
用 Python 读取模板文件内容作为字符串基础：
```python
with open('references/report-template.html', 'r') as f:
    template = f.read()
```

##### 4-2 填充全局占位符

| 占位符 | 填充值 |
|--------|--------|
| `{{DIRECTION}}` | 业务方向中文名，如"餐"、"综"、"酒"、"景" |
| `{{DIRECTION_ICON}}` | 对应 emoji：餐→🍜 综→🛒 酒→🏨 景→🎡 |
| `{{DATE}}` | 统计日期，格式 `YYYY-MM-DD` |
| `{{PERIOD_START}}` | 本周期开始，格式 `YYYY-MM-DD 00:00` |
| `{{PERIOD_END}}` | 本周期结束，格式 `YYYY-MM-DD 23:59` |
| `{{PROJECT_COUNT}}` | 项目总数（整数） |
| `{{FIRST_PROJECT_ID}}` | 第一个项目的 projectId（用于 JS 默认激活） |
| `{{THRESHOLD_TIP}}` | 首现异常标题旁提示文字：查 [assets.md](references/assets.md) 方向级配置表取当前方向的 `new_error_min_count`；若 > 1，填入 `<span class="threshold-tip">次数 &lt; {new_error_min_count} 不展示</span>`；若 == 1，填入空字符串 `''` |
| `{{IGNORED_TIP}}` | 已忽略异常过滤提示：若 `filter_ignored_errors=true` 且各项目共剔除了 N 条已忽略异常（汇总所有项目的 `ignoredCount`），填入 `<span class="threshold-tip">已过滤 {N} 条忽略异常</span>`；若 N == 0 或未启用过滤，填入空字符串 `''`；若 A4 失败，填入 `<span class="threshold-tip">已忽略异常过滤不可用</span>` |

##### 4-3 为每个项目生成 overview-card（项目概览区）

模板中有一个示例 `overview-card` 块，**按项目数量循环生成，替换掉模板中的示例块**。

每张卡片填充规则：

| 占位符 | 填充值 |
|--------|--------|
| `{{PROJECT_NAME}}` | 项目显示名称 |
| `{{TOTAL}}` | 本周期异常总数（`len(currentErrors)`） |
| `{{TOTAL_RATE}}` | 环比变化率，格式 `+29.5%` 或 `-5.2%`；若环比为 0 则显示 `N/A` |
| `{{NEW_COUNT}}` | 首现异常条数（`len(newErrors)`） |
| `{{SURGE_COUNT}}` | 暴涨类型数 |

**badge 条件渲染**：
- `NEW_COUNT > 0`：显示 `<span class="badge badge-new">首现 N 条</span>`；否则不渲染该 badge
- `SURGE_COUNT > 0`：显示 `<span class="badge badge-surge">暴涨 N 项</span>`；否则显示 `<span class="badge badge-ok">无暴涨</span>`

**`stat-sub` 变化率 class**：
- 变化率为正（上涨）→ `class="stat-sub rate-up"`
- 变化率为负（下降）→ `class="stat-sub rate-down"`

##### 4-4 为每个项目生成 tab-btn（Tab 导航栏）

模板中有两个示例 `tab-btn`，**按项目数量循环生成，替换掉模板中的示例按钮**。

- 第一个项目的按钮加 `class="tab-btn active"`，其余只有 `class="tab-btn"`
- `onclick="switchTab('{{PROJECT_ID}}')"` 和 `id="btn-{{PROJECT_ID}}"` 填入实际 projectId
- `NEW_COUNT > 0` 或 `SURGE_COUNT > 0` 时，在按钮文字前加 `<span class="dot"></span>`；否则不加

##### 4-5 为每个项目生成 tab-pane（Tab 详情面板）

模板中有一个示例 `tab-pane`，**按项目数量循环生成，替换掉模板中的示例面板**。

- 第一个项目的面板加 `class="tab-pane active"`，其余只有 `class="tab-pane"`
- `id="tab-{{PROJECT_ID}}"` 填入实际 projectId

**概览 KPI section**（三张 kpi-card，只填数字，不改结构）：

| 占位符 | 填充值 |
|--------|--------|
| `{{TOTAL}}` | 本周期异常总数 |
| `{{TOTAL_RATE}}` | 环比变化率（带正负号） |
| `{{NEW_COUNT}}` | 首现异常条数 |
| `{{SURGE_COUNT}}` | 暴涨类型数 |

`kpi-sub` 变化率 class 同 4-3 规则。

**首现异常 + 环比暴涨两列并排**：

模板中首现异常和环比暴涨被包裹在 `<div class="two-col">` 容器中，形成左右两列并排布局。生成时必须保留此结构，不得拆成上下堆叠。

**左列 - 首现异常 section**：

- `NEW_COUNT > 0`：渲染 `<table class="err-table">` 表格，每条首现异常一行：
  - `<td class="idx">序号</td>`
  - `<td class="err-name"><a href="Raptor详情链接" target="_blank">{{ERR_NAME}}</a></td>`（错误名称需 URL encode）
  - `<td class="err-cnt">{{ERR_COUNT}}</td>`
  - 按 `ERR_COUNT` 降序排列
  - ⚠️ **首现异常展示阈值过滤**：查 [assets.md](references/assets.md) 方向级配置表取当前方向的 `new_error_min_count`；`ERR_COUNT < new_error_min_count` 的首现异常**不渲染到表格中**（但仍计入 `NEW_COUNT` 数字）；若过滤后无可展示条目，tbody 渲染一行空状态：`<tr class="empty-row"><td colspan="3">本周期首现异常均低于展示阈值（&lt;{new_error_min_count}次）</td></tr>`
- `NEW_COUNT == 0`：表格 tbody 渲染一行空状态：`<tr class="empty-row"><td colspan="3">本周期无首现异常</td></tr>`

**右列 - 环比暴涨 section**：

- `SURGE_COUNT > 0`：渲染 `<table class="err-table">` 表格，列为：异常名称 / 本周期 / 环比 / 变化率
  - 异常名称列用 `<a>` 链接到 Raptor 详情页（错误名称需 URL encode）
  - 变化率为正 → `class="rate-up"`；为负 → `class="rate-down"`
  - 表格末尾追加已消失异常行（灰显）：`<tr style="opacity:.45">` 显示错误名称、`-`、上周期次数、`已消失`
- `SURGE_COUNT == 0` 且无已消失异常：表格 tbody 渲染一行空状态：`<tr class="empty-row"><td colspan="4">本周期无暴涨异常类型</td></tr>`
- `SURGE_COUNT == 0` 但有已消失异常：表格 tbody 只渲染已消失行（无需空状态行）

> ⚠️ **环比对比数据处理规则（必须遵守）**：
>
> | 情况 | 判断 | 处理 |
> |------|------|------|
> | 本周期有，环比周期也有 → 变化率 > `surge_threshold`% | 环比暴涨 ✅ | 纳入暴涨表格 |
> | 本周期有，环比周期不存在 | 新增 ✅ | 纳入暴涨表格，环比列显示 `-`，变化率显示 `新增` |
> | 本周期有，环比周期也有 → 变化率 ≤ `surge_threshold`% | 正常波动 | 不纳入暴涨表格 |
> | 本周期无，环比周期有 | 已消失 | 在暴涨表格底部灰显 |

##### 4-6 文件命名与保存

- 单项目：`{projectName}-{YYYY-MM-DD}.html`
- 多项目：`{category}-{YYYY-MM-DD}.html`（如 `can-2026-04-07.html`）
- 保存到工作区目录

##### 4-7 上传 sankuai.com

询问用户是否需要上传到 *.sankuai.com，如果需要则使用 [references/upload.py](references/upload.py) 脚本上传：
- 单项目：`/reports-v2/{projectName}-{YYYY-MM-DD}.html`
- 多项目：`/reports-v2/{category}-{YYYY-MM-DD}.html`
- Content-Type 设为 `text/html; charset=utf-8`
- 如果上传失败，则输出 md 及 html 文件给用户

#### 异常详情链接
严格按照下面格式输出 html 中的链接，否则会导致点击无反应

> ⚠️ **时间参数必须使用 `yyyyMMddHHmmss` 格式**，禁止使用 `yyyy-MM-dd HH:mm:ss` 或任何含空格/冒号的格式，否则浏览器会截断参数导致链接报错。
> 例如：`2026-04-07 00:00:00` → `20260407000000`，`2026-04-07 23:59:59` → `20260407235959`

**正确的 Raptor 列表 URL 格式：**
```
https://raptor.mws.sankuai.com/frontend/error/list?type=datetimerange&webVersion=all&metric=TP90&speedPoint=11,16,18,25&singleSpeedPoint=16&isPerfInMp=false&perfBundleId=3763&dyeingId=&start=20260407000000&end=20260407235959&projectId={projectId}&errorListCurrentPage=1
```
按错误类型筛选（追加参数）：
- AJAX 错误：`&logType=JS_ERROR&errorType=AJAX_ERROR`
- JS 错误：`&logType=AJAX_ERROR&errorType=JS_ERROR`

**按具体错误名称跳转详情页：**
```
https://raptor.mws.sankuai.com/frontend/error/detail?type=daterange&webVersion=all&dyeingId=&start=20260407000000&end=20260407235959&projectId={projectId}&errorName={错误名称}&errorDetailCurrentPage=1&errorDetailCurrentPageSize=50
```
这里错误名称需要 URL encoded

## 注意事项
1. 时间格式统一用 `yyyy-MM-dd HH:mm:ss`（如 `2026-03-10 00:00:00`）
2. 每个子代理只负责数据查询，必须返回完整的 currentErrors（本周期全量异常列表）、previousErrors（环比周期全量异常列表）、newErrors（首现异常列表），不得截断或省略任何条目，并将结果保存到本地 JSON 文件（如 /tmp/can_result.json 等）
3. 子代理全部完成后，主进程读取各方向 JSON 文件，用 Python 脚本在本地计算环比数据（逐条对比 currentErrors vs previousErrors，变化率超过当前方向的 `surge_threshold`％或环比不存在则纳入暴涨模块），生成四个方向的 HTML 文件。禁止把数据传给子代理让其生成 HTML，否则会导致环比数据丢失。
4. **异常列表统一用 summary-table 平铺全量（方案 A）**：currentErrors / previousErrors / newErrors 均来自 `get-summary-table` 的 `table.rows` 与 `newErrors` 字段，**同源无 join 失配**，且不存在 `get-groups` 的「其他」聚合桶折叠问题。因此**不再需要**旧版那种“用 get-groups --error-name 逐条补查低频首现异常次数”的补全动作；首现异常的次数直接从同一份 `rows` 的 COUNT 取得。唯一限制：summary-table 分页硬上限 500 条，超过部分无法获取，需在 Footer 注明。
5. **v2 数据源提示（方案 A）**：A1/A2/A3 统一以 raptorfe `get-summary-table` 为唯一数据源，A3 首现异常直接取 A1 本期返回的 `newErrors` 字段（无需单独请求）。hotel-raptor-tool **仅为可选交叉校验备份**，未安装/无 Cookie/接口异常均不影响主流程，一律以 summary-table 的 `newErrors` 为准；禁止因 hotel-raptor-tool 无权限而中断流程或向用户索要 Cookie。可在 Footer 用 `newErrorsSource` 标注实际来源。
