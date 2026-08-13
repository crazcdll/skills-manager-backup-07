---
name: trade-stability-alert-diagnosis
description: 交易前端告警排查专家。作为稳定性全流程第四步「告警路径」的子流程，由 trade-stability-issue-diagnosis 分发调用。
  接收第一步信息提取结果和第二步变更扫描结果后执行专项排查。
  覆盖业务线：餐、综、酒、景。
  支持 5 种告警类型：48小时首现异常、JS异常、CIA客户端交互异常、成功率告警、其他自定义告警。
  排查能力：告警链接参数完整提取并映射为 raptorfe CLI 命令 + 查异常汇总/明细/堆栈/sourcemap + 有效性判定。
  输入：业务线、Bundle名、告警时间、告警原始文本、变更扫描结果（来自前序步骤）。
  输出：结构化告警排查结论（告警类型、异常分析、堆栈详情、有效性判断、处理建议、负责人信息）。
  触发词：raptor异常排查、交易告警、告警排查、Raptor告警、48小时首现、新增异常、JS异常、CIA告警、成功率告警、alert investigation、告警分析、餐告警、综告警、酒告警、酒店告警、前端异常排查。
---

# 交易前端告警排查

**覆盖业务线**：餐、综、酒、景。

**定位**：作为全流程第四步的「告警排查路径（路径 A）」子流程，由 [trade-stability-issue-diagnosis](../SKILL.md) 分发调用。接收第一步信息提取结果 + 第二步变更扫描结果，按告警类型执行专项排查，判断告警是否有效，找到根因，给出处理建议。

> 景的研发资产待补充，收到景的告警时可先手动查询对应页面信息。

**工具**：
- **raptorfe CLI（`@mtfe/raptorfe-cli`）** — 查异常汇总、明细、堆栈、sourcemap 还原（主力工具）
- **git 命令** — 按公共流程进行只读仓库访问与完整 diff 分析

**⚠️ 核心原则：所有 CLI 命令的参数必须来自告警文本中「点击查看数据」链接的解析结果，禁止自行拼接或猜测。**

---

## 前置输入（来自 trade-stability-issue-diagnosis 分发）

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 业务线 | 第一步·信息提取 | 餐 / 综 / 酒 / 景 |
| Bundle 名 | 第一步·信息提取 | 如 `rn_meishi_group_order_detail` |
| 告警时间 | 第一步·信息提取 | 问题发生时间 |
| 变更扫描结果 | 第二步·变更查询 | MCM/Diva 是否有变更及相关度、最可疑变更的 commitUrl |
| 告警原始文本 | 用户输入 | 告警完整内容（含「点击查看数据」或 「查看数据」链接） |

> ⚠️ 若缺少上述任一关键信息，必须先追问补全再开始排查。

> ⚠️ **告警文本中的「点击查看数据」链接是全部排查的唯一数据源**。后续所有 CLI 命令的 projectId、时间窗口、errorLevel 等参数均从这里提取，不得从资产文件或其他来源猜测。

---

开始执行第一步前，**必须**先执行以下命令，记录开始时间：
```bash
startTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $startTime
```

## 第一步：识别告警类型 & 加载资产 & 解析告警链接

### 1.1 识别告警类型

从告警文本中判断类型：

| 类型 | 识别特征 | 典型告警名示例 |
|------|---------|---------------|
| **48小时首现** | 告警名含「48小时首现」「新增异常」 | `[48h首现] rn_meishi_xxx 新增异常` |
| **JS异常** | 告警名含「JS异常」「前端异常」「error rate」「Error异常量」 | `[JS异常] xxx error rate 上涨` |
| **CIA** | 告警名含「CIA」「客户端交互异常」 | `[CIA] xxx 客户端交互异常率上升` |
| **成功率** | 告警名含「成功率」「success rate」「请求成功率」 | `[成功率] xxx 接口成功率下降` |
| **其他** | 不属于以上类型 | 自定义规则触发的告警 |

### 1.2 加载业务线资产

根据 Bundle 前缀匹配业务线，加载对应资产文件（统一从 trade-stability-fullflow/assets/ 读取）：

- 餐读取 [assets/food-dev-assets.md](../../assets/food-dev-assets.md)
- 综读取 [assets/gc-dev-assets.md](../../assets/gc-dev-assets.md)
- 酒读取 [assets/hotel-dev-assets.md](../../assets/hotel-dev-assets.md)
- 景读取 [assets/travel-dev-assets.md](../../assets/travel-dev-assets.md)

从资产文件获取：**仓库 SSH 地址**、**projectId**（用于校验，以告警链接中的 projectId 为准）、**Diva bundleId**

### 1.3 解析告警链接 → 提取 CLI 命令参数（⚠️ 核心步骤）

告警文本中的「点击查看数据」链接是 Raptor 网页上筛选查看异常列表的等效入口。**必须从链接中完整提取每个参数，精确映射为 raptorfe CLI 命令参数，确保 CLI 查出的数据与打开链接看到的数据完全一致。**

> ⚠️ **链接是唯一数据源**：projectId、时间窗口、webVersion 等全部从链接提取，不得从资产文件或其他来源猜测。资产文件中的 projectId 仅用于交叉校验。

#### 1.3.1 提取链接

从告警原始文本中找到所有 `https://raptor.mws.sankuai.com/frontend/error/list?...` 格式的链接。典型链接格式：

```
https://raptor.mws.sankuai.com/frontend/error/list?type=datetimerange&start=20260811171000&end=20260811171200&projectId=37345&errorLevel=error&webVersion=all
```

> ⚠️ 告警文本中可能有多个链接（如分别对应「影响用户数」和「错误总量」），projectId 相同但 start/end 可能不同。取 **errorLevel=error** 的链接为准；若无 errorLevel 参数则取第一个链接。

#### 1.3.2 链接参数 → CLI 参数映射表

| 链接 query 参数 | CLI 命令参数 | 说明 |
|-----------------|------------|------|
| `projectId=37345` | `--project-id 37345` | 直接使用，这是最关键参数 |
| `start=20260811171000` | `--start-long {毫秒时间戳}` | 需从 `yyyyMMddHHmmss` 转为毫秒 |
| `end=20260811171200` | `--end-long {毫秒时间戳}` | 需从 `yyyyMMddHHmmss` 转为毫秒 |
| `errorLevel=error` | ⚠️ 不传 LEVEL 过滤 | 见下方说明 |
| `webVersion=all` | `--web-version all` | 直接使用 |
| `errorListCurrentPage=1` | `--offset 0` | 页码转为 offset（page-1)*limit |

**⚠️ 关于 errorLevel 参数的处理**：

告警链接中通常有 `errorLevel=error` 参数，但 Raptor 网页实际展示的是**所有未被忽略的异常**（包括 error、warn、info 级别）。因此 CLI 查询时**不传 LEVEL 过滤条件**（不传 `--query-param`），查出全部级别异常后，在 jq 过滤阶段统一排除 STATUS=3/4/5 的异常。这样确保 warn 级别异常（如「渠道：查询支付宝优惠信息异常」这类容器渠道异常）和 info 级别异常不被遗漏。

**⚠️ 关于 log-type 参数**：

链接中没有 logType 参数，说明网页展示的是全部异常类型（jsError + ajaxError + resourceError）。CLI 也不传 `--log-type`，确保不遗漏 API 异常和 script 异常。

**⚠️ 链接中无对应 CLI 参数的字段**（如 `metric`、`speedPoint`、`perfBundleId`）是性能监控参数，异常分析不需要，忽略。

#### 1.3.3 时间格式转换

```bash
# macOS date 转换：yyyyMMddHHmmss → 毫秒时间戳
start_ms=$(date -j -f "%Y%m%d%H%M%S" "20260811171000" +%s000)
end_ms=$(date -j -f "%Y%m%d%H%M%S" "20260811171200" +%s000)
echo "start_ms=$start_ms, end_ms=$end_ms"
```

#### 1.3.4 参数提取输出

提取完成后，在上下文中记录以下结构化参数（后续全部使用这些参数）：

```
【告警链接参数 → CLI 命令参数】
- --project-id: {projectId}（来源：链接 projectId 参数）
- --start-long: {start_ms}（{start_human}，来源：链接 start 参数转换）
- --end-long: {end_ms}（{end_human}，来源：链接 end 参数转换）
- --web-version: {webVersion，默认 all，来源：链接 webVersion 参数}
- 不传 --query-param（不按 LEVEL 过滤，查全部级别）
- 不传 --log-type（查全部异常类型）
- --time-size: MINUTE（告警窗口 ≤1天时用 MINUTE）
- --limit: 50
```

> ⚠️ **后续 A1、A2 全部使用以上参数，禁止重新拼接或修改。**

---

## 第二步：告警数据分析（raptorfe CLI）

> ⚠️ **本步骤全部使用第一步 1.3.4 提取的 CLI 参数，禁止手动拼接。**

### A0. 检查 raptorfe CLI

```bash
raptorfe --version 2>/dev/null && echo "ok" || echo "missing"
```

- **输出 ok** → 直接使用
- **输出 missing** → 安装：
  ```bash
  npm install -g @mtfe/raptorfe-cli@beta --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
  ```
  若安装失败，确认 npm registry 正确后重试，不得跳过 raptorfe 查询。

### A1. 查询异常汇总表格（定位告警主因异常）

> ⚠️ **必须使用 `get-summary-table`，不得使用 `get-groups`。** `get-groups` 返回原始上报总量（同一页面反复触发会累加），`get-summary-table` 返回去重后的异常实例数，与 Raptor 网页展示一致。

> ⚠️ **参数必须来自告警链接解析结果**（见 1.3.4），不传 `--query-param`（不按 LEVEL 过滤），不传 `--log-type`（查全部异常类型）。

```bash
raptorfe web error get-summary-table \
  --project-id {projectId} \
  --start-long {start_ms} \
  --end-long {end_ms} \
  --web-version {webVersion} \
  --limit 50 \
  --time-size MINUTE
```

返回值关键字段（`data.table.rows[]`）：

| 字段 | 说明 |
|------|------|
| `main` | 异常名称（即 errorCategory），用于 A2 查明细 |
| `CATEGORY` | 异常类型（`jsError` / `ajaxError` / `resourceError`） |
| `LEVEL` | 错误级别（`error` / `warn` / `info`） |
| `COUNT` | 去重后异常实例数（与网页一致） |
| `USER_COUNT` | 影响用户数 |
| `STATUS` | 告警状态（1=未设置，3=已解决，4=完全忽略，5=暂时忽略） |
| `DATE` | 最近上报时间 |

**⚠️ 必须过滤后再分析**（对齐 Raptor 告警实际统计口径）：

| 排除条件 | 对应字段值 | 说明 |
|---------|-----------|------|
| 完全忽略 | `STATUS=4` | 已被业务标记为永久忽略 |
| 暂时忽略 | `STATUS=5` | 已被业务标记为临时忽略 |
| 已解决 | `STATUS=3` | 已处理完毕 |

> ⚠️ **不要按 CATEGORY 过滤**：`ajaxError`（API 异常）和 `resourceError`（script 加载失败）都是有效告警，必须保留。
>
> ⚠️ **不要按 LEVEL 过滤**：`warn` 级别异常（如「渠道：查询支付宝优惠信息异常」这类容器渠道异常）和 `info` 级别异常也可能是告警主因或重要线索，必须保留。

过滤命令（管道一键过滤+排序+汇总）：

```bash
raptorfe web error get-summary-table --project-id {projectId} --start-long {start_ms} --end-long {end_ms} --web-version {webVersion} --limit 50 --time-size MINUTE 2>/dev/null | grep -o '{"ok".*' | jq '[.data.table.rows[] | select(.STATUS != 3 and .STATUS != 4 and .STATUS != 5)] | sort_by(-.COUNT) | {total_count: (map(.COUNT) | add), total_rows: length, rows: (map({LEVEL, CATEGORY, STATUS, COUNT, USER_COUNT, main}))}'
```

**分析要点**：
- 过滤后 COUNT 最高的异常即为**告警主因**，重点排查
- **所有未被忽略的异常都需要排查**，无论 LEVEL 是 error/warn/info，也无论 CATEGORY 是什么类型：
  - `LEVEL=error` → 高优先级，必须全部排查
  - `LEVEL=warn` → 中优先级，COUNT 较高（≥10）的也需排查（如「渠道：查询支付宝优惠信息异常」这类容器渠道异常）
  - `LEVEL=info` → 低优先级，COUNT 极高时关注
  - `CATEGORY=jsError` → JS 代码异常（TypeError、unhandledrejection 等），需查堆栈
  - `CATEGORY=ajaxError` 且 `main` 为 URL（如 `https://apihotel.meituan.com/...`）→ **后端接口异常**
  - `CATEGORY=ajaxError` 且 `main` 为业务名（如 `preview: 网络异常`）→ 前端接口请求异常
  - `CATEGORY=resourceError` 且 `main` 为 `script` → **JS 资源加载失败**
  - `CATEGORY=resourceError` 且 `main` 为 `img` → 图片资源加载失败
- **48小时首现告警**：若过滤后无任何级别异常，大概率误告

### A2. 查询异常明细 & 堆栈（对所有未忽略异常全部执行）

> ⚠️ **必须对 A1 过滤后的 Top 5 异常全部执行**，不能只查第一个。不同异常可能有不同根因。
>
> ⚠️ **不能只关注 `LEVEL=error`**：`warn` 级别异常（如容器渠道异常、第三方 SDK 异常）和 `info` 级别异常也可能是告警主因或重要线索，必须一并排查。
>
> ⚠️ **CLI 参数（projectId、时间窗口）必须来自告警链接解析结果**（见 1.3.4），不得自行修改。

对 A1 过滤后的每个 Top 异常（按 COUNT 降序取前 5，覆盖 error/warn/info 所有级别），按以下 **三步链路** 依次执行：

#### A2a. 查询异常明细，获取 errorLogId

```bash
raptorfe web error get-error-detail \
  --project-id {projectId} \
  --start-long {start_ms} \
  --end-long {end_ms} \
  --error-category "{A1中的异常名称 main 字段}" \
  --limit 5
```

返回值关键字段：

| 字段 | 说明 |
|------|------|
| `errorLogId` | 格式 `CHL-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`，用于 A2b |
| `main` | 上报时间（`YYYY-MM-DD HH:mm:ss`），转为毫秒时间戳用于 `--log-date` |
| `data4` | 用户 ID |
| `data5` | 容器类型（微信小程序 / MRN / DUO / Chrome PC 等） |
| `data6` | 操作系统（iOS / Android / HarmonyOS） |

#### A2b. 查询日志详情，获取堆栈

对 A2a 返回的每条 errorLogId，将 `main`（上报时间）转为毫秒时间戳后查询：

```bash
# 时间转换（macOS）
log_date=$(date -j -f "%Y-%m-%d %H:%M:%S" "{main时间}" +%s000)

raptorfe web error get-log-detail \
  --error-log-id {errorLogId} \
  --log-date {log_date}
```

返回值关键字段：

| 字段 | 说明 |
|------|------|
| `baseInfo.User Agent` | 客户端信息（App版本、系统版本、机型） |
| `otherInfo.appKey` | MRN bundle 标识（存在 → MRN 类型异常，走 A2c；不存在 → H5/Web，走 A2d） |
| `otherInfo.customInfo` | 自定义上报信息（JSON字符串，含 traceId、错误码等） |
| `stackInfo` | 原始堆栈（见下方格式判断） |
| `otherInfo.other.traceid` | 后端 traceId（若有，用于通知后端排查） |

> ⚠️ **stackInfo 四种格式处理**：
> - **标准堆栈字符串**（含 `at xxx (file:line:col)`）→ 走 A2c/A2d sourcemap 还原
> - **URL 字符串**（如 `https://apihotel.meituan.com/...`）→ API 异常的请求地址，非代码堆栈，**直接记录 URL 和错误码，不走 sourcemap**
> - **业务文案字符串**（如 `渠道：查询支付宝优惠信息异常`）→ 业务自定义 catch 上报的异常，**直接记录文案和 customInfo 中的详细信息，不走 sourcemap**
> - **JSON 字符串**（如 `{"code":1,"message":"Request timeout"}`）→ 运行时错误信息，**直接记录错误内容，不走 sourcemap**
> - **空字符串** → 结合 customInfo 判断错误内容

#### A2c. SourceMap 还原堆栈（MRN 页面，一步到位）

> `sourcemap-mrn` 会自动拉取日志详情并还原完整堆栈，无需先手动调用 `get-log-detail` 再单独 sourcemap。

若 A2b 中 `otherInfo.appKey` 字段存在（MRN 类型异常），直接使用 `sourcemap-mrn` 一键还原：

```bash
raptorfe web error sourcemap-mrn \
  --error-log-id {errorLogId} \
  --log-date {log_date}
```

内部流程：自动调用 `get-log-detail` → 解析堆栈 → 提取 bundleName/bundleVersion → 计算 jsUrl → 调用 sourcemap API 批量反解 → 返回原始代码位置。

> 若 `otherInfo.appKey` 为空（非 MRN 类型），返回错误提示「该日志不是 MRN 类型异常」，转 A2d。

#### A2d. SourceMap 还原堆栈（H5 / Web 页面）

若为 H5/Web 页面（或 `sourcemap-mrn` 失败），从 `stackInfo` 中提取 `jsUrl`、`line`、`column`，逐帧还原：

```bash
raptorfe web error sourcemap \
  --line {行号} \
  --column {列号} \
  --js-url "{jsUrl}" \
  --env production \
  --project {项目名}
```

> 小程序项目需额外传 `--wx-app-version "{版本号}"`。

### A2 汇总输出

对 Top 5 异常全部查询完成后，输出汇总表格：

```
【异常明细汇总】

| 排名 | 异常名称 | 类型(CATEGORY) | 级别(LEVEL) | COUNT | USER_COUNT | 堆栈/错误内容 | 容器 | OS | traceId |
|------|---------|---------------|------|-------|------------|-------------|------|-----|---------|
| 1 | {main} | {CATEGORY} | {LEVEL} | {COUNT} | {USER_COUNT} | {堆栈摘要或错误内容} | {容器} | {OS} | {traceId或无} |
| 2 | ... | | | | | | | | |
| 3 | ... | | | | | | | | |
| 4 | ... | | | | | | | | |
| 5 | ... | | | | | | | | |
```

**结论判断**：
- **堆栈清晰 + 指向业务代码** → 记录出错文件路径、函数名、错误类型，得出结论
- **stackInfo 为 URL** → API 请求异常，记录请求地址和错误码，判断是否为后端问题
- **stackInfo 为业务文案** → 业务自定义 catch 上报，从 customInfo 中提取详细信息（如 dealId、userId、错误详情），结合 UA 判断容器环境
- **stackInfo 为 JSON 错误信息** → 运行时错误（如接口超时、网络异常），判断是否为后端/网络问题
- **第三方库/SDK 内部报错** → 记录，评估影响范围
- **低频偶发 / 特定老版本 App / 特定容器（如支付宝、建行）** → 大概率误告或低优先级

若 raptorfe CLI 持续安装失败，提供 Raptor 页面链接供用户手动查看：

`aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPXtwcm9qZWN0SWR9JnR5cGU9ZGF0ZXRpbWVyYW5nZSZzdGFydD17SVNP5qC85byPfSZlbmQ9e0lTT+agvOW8j30=`

---

## 第三步：输出排查报告

输出报告前，**必须**先执行以下命令，获取结束时间：

```bash
endTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $endTime
```
> 💡 **耗时计算**：用 endTime 减去前置步骤记录的 startTime，精确到分钟，格式如「约 X 分钟」。

✅ **第四步【路径A】：告警排查结论**（完成时间：{endTime 命令输出}  耗时：{约 X 分钟}）

| 字段 | 内容 |
|------|------|
| 告警类型 | 48h首现 / JS异常 / CIA / 成功率 / 其他 |
| 业务线 | 餐 / 综 / 酒 / 景 |
| Bundle / 项目 | {bundle名 或 服务名} |
| 告警时间 | YYYY-MM-DD HH:mm |
| 告警内容 | {摘要} |
| 告警链接参数 | projectId={projectId}，告警窗口={start}~{end}，webVersion={webVersion} |
| 异常类型 | {TypeError / API异常 / script加载失败 / 容器渠道异常 / ...} |
| 影响范围 | {用户数 / 设备数 / 请求量 / 影响页面} |
| 代码定位 | {文件路径:行号 + 函数名 或「未定位到具体代码」} |
| 堆栈详情 | {sourcemap 还原后的原始代码位置（文件路径:行号:函数名）或错误内容摘要} |
| 异常明细汇总 | {Top 5 异常的名称、类型、级别、COUNT、用户数、容器、堆栈摘要、traceId，详见 A2 汇总表格} |
| 关联变更 | {变更来源} {版本号} {发布时间} @{mis_id}（相关度：高/中/低）/ 无变更 |
| 有效性判断 | ✅ 有效告警（需处理）/ ❌ 无效告警（可忽略）/ ⚠️ 待观察 |
| 根因结论 | {根因说明} |
| 建议处理 | {立即回滚 / 通知负责人修复 / 升级依赖 / 进一步排查方向} |
| 页面负责人 | @{mis_id}（{姓名}） |
| 代码仓库 | {SSH 地址} |

➡️ **进入第五步：输出结论与代码修复**

---
