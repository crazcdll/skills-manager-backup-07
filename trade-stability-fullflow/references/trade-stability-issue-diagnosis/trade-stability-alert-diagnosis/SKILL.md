---
name: trade-stability-alert-diagnosis
description: 交易前端告警排查专家。作为稳定性全流程第四步「告警路径」的子流程，由 trade-stability-issue-diagnosis 分发调用。
  接收第一步信息提取结果和第二步变更扫描结果后执行专项排查。
  覆盖业务线：餐、综、酒、景。
  支持 5 种告警类型：48小时首现异常、JS异常、CIA客户端交互异常、成功率告警、其他自定义告警。
  排查能力：raptorfe CLI 查异常趋势/分组/堆栈/sourcemap + git diff 代码变更分析 + 有效性判定。
  输入：业务线、Bundle名、告警时间、告警原始文本、变更扫描结果（来自前序步骤）。
  输出：结构化告警排查结论（告警类型、变更关联、异常分析、有效性判断、处理建议、负责人信息）。
  触发词：raptor异常排查、交易告警、告警排查、Raptor告警、48小时首现、新增异常、JS异常、CIA告警、成功率告警、alert investigation、告警分析、餐告警、综告警、酒告警、酒店告警、前端异常排查。
---

# 交易前端告警排查

**覆盖业务线**：餐、综、酒、景。

**定位**：作为全流程第四步的「告警排查路径（路径 A）」子流程，由 [trade-stability-issue-diagnosis](../SKILL.md) 分发调用。接收第一步信息提取结果 + 第二步变更扫描结果，按告警类型执行专项排查，判断告警是否有效，找到根因，给出处理建议。

> 景的研发资产待补充，收到景的告警时可先手动查询对应页面信息。

**工具**：
- **raptorfe CLI（`@mtfe/raptorfe-cli`）** — 查异常趋势、分组、明细、堆栈、sourcemap 还原（主力工具）
- **内网浏览器（intranet-browser / catdesk-browser）** — 访问 Diva / Raptor / Yooz 等 `*.sankuai.com` 页面（备用）
- **git 命令** — 按公共流程进行只读仓库访问与完整 diff 分析

---

## 前置输入（来自 trade-stability-issue-diagnosis 分发）

本 skill 作为全流程第四步「路径 A」子流程，由 [trade-stability-issue-diagnosis](../SKILL.md) 分发调用。应已具备以下上下文：

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 业务线 | 第一步·信息提取 | 餐 / 综 / 酒 / 景 |
| Bundle 名 | 第一步·信息提取 | 如 `rn_meishi_group_order_detail` |
| 告警时间 | 第一步·信息提取 | 问题发生时间 |
| 变更扫描结果 | 第二步·变更查询 | MCM/Diva 是否有变更及相关度、最可疑变更的 commitUrl |
| 告警原始文本 | 用户输入 | 告警完整内容 |

> ⚠️ 若缺少上述任一关键信息，必须先追问补全再开始排查。

---
开始执行第一步前，**必须**先执行以下命令，记录开始时间：
```bash
startTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $startTime
```

## 第一步：识别告警类型 & 加载资产

### 1.1 识别告警类型

从告警文本中判断类型：

| 类型 | 识别特征 | 典型告警名示例 |
|------|---------|---------------|
| **48小时首现** | 告警名含「48小时首现」「新增异常」 | `[48h首现] rn_meishi_xxx 新增异常` |
| **JS异常** | 告警名含「JS异常」「前端异常」「error rate」 | `[JS异常] xxx error rate 上涨` |
| **CIA** | 告警名含「CIA」「客户端交互异常」 | `[CIA] xxx 客户端交互异常率上升` |
| **成功率** | 告警名含「成功率」「success rate」「请求成功率」 | `[成功率] xxx 接口成功率下降` |
| **其他** | 不属于以上类型 | 自定义规则触发的告警 |

### 1.2 加载业务线资产

根据 Bundle 前缀匹配业务线，加载对应资产文件（统一从 trade-stability-fullflow/assets/ 读取）：

- 餐读取 [assets/food-dev-assets.md](../../assets/food-dev-assets.md)
- 综读取 [assets/gc-dev-assets.md](../../assets/gc-dev-assets.md)
- 酒读取 [assets/hotel-dev-assets.md](../../assets/hotel-dev-assets.md)
- 景读取 [assets/travel-dev-assets.md](../../assets/travel-dev-assets.md)

从资产文件获取：**仓库 SSH 地址**、**projectId**、**Diva bundleId**

---

## 第二步：并行双线路排查

> ⚠️ **线路 A（告警分析）与线路 B（变更代码分析）必须并行启动，不得等待任意一路完成后再开始另一路。任意一路得出明确结论即可停止等待，直接进入第三步汇总分析。**
>
> **仅当第二步变更扫描结果中存在 Diva 变更时才执行线路 B**；无变更时仅执行线路 A。

```
第二步变更扫描结果
        ↓
   ┌────┴────┐
 有变更      无变更
   ↓            ↓
线路A + 线路B   线路A（告警分析）
（并行启动）        ↓ 线路A无结论，告警判断与前端代码相关？
                ├─ 是 → 追加线路 C（clone master 代码分析）
                └─ 否 → 进入第三步汇总分析
```

---

### 线路 A：告警分析（raptorfe CLI）

#### A0. 检查 raptorfe CLI

```bash
raptorfe --version 2>/dev/null && echo "ok" || echo "missing"
```

- **输出 ok** → 直接使用
- **输出 missing** → 安装：
  ```bash
  npm install -g @mtfe/raptorfe-cli@beta --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
  ```
  若安装失败，回退到备用方案（浏览器访问 Raptor 页面）。

#### A1. 查询异常趋势（判断告警是否真实）

```bash
raptorfe web error get-trend \
  --project-id {projectId} \
  --start-long {告警时间前2小时毫秒时间戳} \
  --end-long {告警时间后1小时毫秒时间戳} \
  --metric-type errorCount \
  --time-size MINUTE
```

> 时间戳转换：`date -j -f "%Y-%m-%d %H:%M:%S" "2026-04-07 15:30:00" +%s000`（macOS）

**分析要点**：
- 趋势是**突然大量出现**还是**缓慢增长**？
- 是否在告警时间点前后有明显拐点？
- 若趋势平稳无异常 → 大概率误告，记录结论，线路 A 提前结束

#### A2. 查询异常汇总表格（定位具体异常名）

> ⚠️ **必须使用 `get-summary-table`，不得使用 `raptorfe get-groups`。**
> 两者统计口径不同：`get-groups` 返回原始上报总量（同一页面反复触发会累加），`get-summary-table` 返回去重后的异常实例数，与网页展示一致。

```bash
raptorfe web error get-summary-table \
  --project-id {projectId} \
  --start-long {告警时间前2小时毫秒时间戳} \
  --end-long {告警时间后1小时毫秒时间戳} \
  --web-version all \
  --log-type JS_ERROR \
  --limit 20 \
  --time-size MINUTE
```

返回值关键字段（`data.table.rows[]`）：

| 字段 | 说明 |
|------|------|
| `main` | 异常名称（即 errorCategory），用于 A3 查明细 |
| `CATEGORY` | 异常类型（`jsError` / `ajaxError` / `resourceError`） |
| `LEVEL` | 错误级别（`error` / `warn` / `info`） |
| `COUNT` | 去重后异常实例数（与网页一致） |
| `USER_COUNT` | 影响用户数 |
| `STATUS` | 告警状态（1=未创建工单，4=完全忽略，5=暂时忽略） |
| `DATE` | 最近上报时间 |

**⚠️ 必须按告警规则过滤后再分析**（对齐 Raptor 告警实际统计口径）：

Raptor JS异常告警默认排除以下异常，**这些异常不参与告警计数，分析时必须忽略**：

| 排除条件 | 对应字段 | 说明 |
|---------|---------|------|
| 完全忽略 | `STATUS=4` | 已被业务标记为永久忽略 |
| 暂时忽略 | `STATUS=5` | 已被业务标记为临时忽略 |
| 已解决 | `STATUS=3` | 已处理完毕 |
| debug/info 级别 | `LEVEL=debug` 或 `LEVEL=info` | 非错误级别 |
| 静态资源异常 | `CATEGORY=resourceError` | 资源加载失败，非业务逻辑异常 |

过滤命令（单行管道，无需临时文件）：

```bash
raptorfe web error get-summary-table --project-id {projectId} --start-long {START_MS} --end-long {END_MS} --web-version all --log-type JS_ERROR --limit 30 --time-size MINUTE 2>/dev/null | grep -o '{"ok".*' | jq '[.data.table.rows[] | select(.STATUS != 3 and .STATUS != 4 and .STATUS != 5 and .LEVEL != "debug" and .LEVEL != "info" and .CATEGORY != "resourceError")] | {total_count: (map(.COUNT) | add), total_rows: length, newErrors: "见原始输出", rows: (sort_by(-.COUNT) | map({LEVEL, STATUS, COUNT, USER_COUNT, main}))}'
```

> `grep -o '{"ok".*'` 用于从 CLI 混合输出中提取 JSON 部分，`jq` 直接过滤并汇总。

**分析要点**：
- **以过滤后的列表为准**，过滤前的 Top 异常（如 STATUS=5 的高频 warn）不参与告警，不是主因
- 过滤后 COUNT 最高的异常即为**告警主因**，重点排查
- **重点关注 `LEVEL=error` 的异常**，`warn` 级别通常为业务主动上报（无堆栈），需结合 customInfo 判断
- **48小时首现告警**：重点关注 `data.newErrors` 字段，为空则无新增异常，告警无效
- `CATEGORY=ajaxError` 的异常通常为后端接口问题，需结合后端日志排查
- 若 warn 级别异常无堆栈但 COUNT 极高，需查 `customInfo` 中的错误详情（如接口返回值、错误码）

#### A3. 查询异常明细，获取 errorLogId

```bash
raptorfe web error get-error-detail \
  --project-id {projectId} \
  --start-long {毫秒时间戳} \
  --end-long {毫秒时间戳} \
  --error-category "{A2中的异常名称}" \
  --limit 5
```

返回值关键字段：

| 字段 | 说明 |
|------|------|
| `errorLogId` | 格式 `CHL-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`，用于 A4 |
| `clientTime` | 上报时间（毫秒时间戳），用于 A4 的 `--log-date` |
| `unionId` | 用户 UUID |
| `containerType` | 容器类型（MRN / DUO / MAX / H5） |
| `os` | 操作系统（iOS / Android） |

#### A4. 查询日志详情 & SourceMap 还原

**Step 1：获取原始日志详情**

```bash
raptorfe web error get-log-detail \
  --error-log-id {errorLogId} \
  --log-date {clientTime毫秒时间戳}
```

返回值关键字段：

| 字段 | 说明 |
|------|------|
| `baseInfo.pageId` | 页面实例 ID |
| `baseInfo.User Agent` | 客户端信息（App版本、系统版本、机型） |
| `otherInfo.tag4` | bundleVersion（bundle 版本号） |
| `otherInfo.tag5` | appVersion（App 版本号） |
| `otherInfo.tag6` | bundle 名称 |
| `otherInfo.customInfo` | 自定义上报信息（JSON字符串，含 traceId、错误码等） |
| `stackInfo` | 原始堆栈（压缩后） |

**Step 2：SourceMap 还原堆栈（MRN 页面）**

若 `otherInfo.appKey` 字段存在，说明是 MRN 类型异常，使用 sourcemap-mrn 一键还原：

```bash
raptorfe web error sourcemap-mrn \
  --error-log-id {errorLogId} \
  --log-date {clientTime毫秒时间戳}
```

还原后可直接获得原始代码文件路径和行号，无需手动解析。

**Step 3：SourceMap 还原堆栈（H5 / Web 页面）**

若为 H5/Web 页面，从 `stackInfo` 中提取 `jsUrl`、`line`、`column`，逐帧还原：

```bash
raptorfe web error sourcemap \
  --line {行号} \
  --column {列号} \
  --js-url "{jsUrl}" \
  --env production \
  --project {项目名}
```

**A 线结论判断**：
- **堆栈清晰 + 指向业务代码** → 记录出错文件路径、函数名、错误类型，线路 A 得出结论
- **第三方库/SDK 内部报错** → 记录，评估影响范围
- **趋势平稳 / 低频偶发 / 特定老版本 App** → 大概率误告或低优先级，记录结论

**备用方案（raptorfe CLI 安装失败时）**：

```
aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPXtwcm9qZWN0SWR9JnR5cGU9ZGF0ZXRpbWVyYW5nZSZzdGFydD17SVNP5qC85byPfSZlbmQ9e0lTT+agvOW8j30=
```

---

### 线路 B：变更代码分析（有变更时与线路 A 并行）

> ⚠️ **直接读取第二步变更扫描结果中的最可疑变更版本和 commitUrl，不重新查询 Diva。**

完整步骤参见公共文档：[code-analysis.md](../../references/code-analysis.md#线路-b变更代码分析有-diva-变更时执行)

将线路 A 得到的异常文件、函数、版本和调用栈作为 `code-analysis.md` 的输入。公共流程已覆盖全量 diff、异步生命周期、状态、依赖与重构风险；本路径只额外要求优先验证与堆栈文件名/函数名直接对应的改动。

---

### 线路 C：master 最新代码分析（无变更时，告警指向代码问题）

> 适用场景：无 Diva 变更，但线路 A 分析后判断告警与前端代码逻辑相关（如堆栈指向具体业务文件、但无对应变更记录）。

完整步骤参见公共文档：[code-analysis.md](../../references/code-analysis.md#线路-c默认分支代码分析无变更但问题与代码相关时执行)

线路 C 的代码读取、配置/实验识别和结论标准统一以 `code-analysis.md` 为准；不得在此重复维护另一套代码分析规则。

---

## 第三步：汇总分析

> 线路 A 和线路 B 任意一路得出明确结论，即可停止等待另一路，直接进入汇总分析。

| 情况 | 处理方式 |
|------|---------|
| 线路 A 有结论，线路 B 有结论 | 综合分析，判断主因（堆栈 + 变更代码双重印证），进入输出 |
| 线路 A 有结论，线路 B 无结论 | 以堆栈报错为根因（代码Bug/依赖异常），进入输出 |
| 线路 A 无结论，线路 B 有结论 | 以变更代码为根因，进入输出 |
| 线路 A 无结论，线路 B 无结论 | 无法定位，扩大排查（见下方特殊场景） |
| 无变更，线路 A 有结论且指向代码 | 启动线路 C（clone master 分析），以线路 C 结论为根因；无结论则扩大排查 |
| 无变更，线路 A 无结论 | 无法定位，扩大排查 |
| 线路 C 有结论 | 以默认分支发现的代码逻辑缺陷/配置控制为根因（需结合日志或复现验证），进入输出 |
| 线路 C 无结论 | 无法定位，扩大排查（见下方特殊场景） |

---

## 第四步：输出排查报告

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
| 异常类型 | {TypeError / CIA交互异常 / 成功率下降 / ...} |
| 影响范围 | {用户数 / 设备数 / 请求量 / 影响页面} |
| 代码定位 | {文件路径:行号 + 函数名 或「未定位到具体代码」} |
| 堆栈详情 | {sourcemap 还原后的原始代码位置（文件路径:行号:函数名）或成功率趋势描述} |
| 关联变更 | {变更来源} {版本号} {发布时间} @{mis_id}（相关度：高/中/低）/ 无变更 |
| 关键变更摘要 | {diff 核心内容，与堆栈的关联说明 / 无} |
| 有效性判断 | ✅ 有效告警（需处理）/ ❌ 无效告警（可忽略）/ ⚠️ 待观察 |
| 根因结论 | {根因说明 + 两路关联证据 / 原因说明} |
| 建议处理 | {立即回滚 / 通知负责人修复 / 升级依赖 / 进一步排查方向} |
| 页面负责人 | @{mis_id}（{姓名}） |
| 代码仓库 | {SSH 地址} |

➡️ **进入第五步：输出结论与代码修复**

---
