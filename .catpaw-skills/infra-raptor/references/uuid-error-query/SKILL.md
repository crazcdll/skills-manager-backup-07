---
name: uuid-error-query
display_name: UUID查询异常日志
description: >
  用户输入一个 uuid（设备标识，通常为 64 位十六进制字符）并提出查询/排查异常诉求时，检索该 uuid（即 deviceId）在最近 7 天内发生过的所有异常，包括崩溃（crash）、ANR、异常退出（watchdog/FOOM）、捕获异常（catchexception）、卡顿（lag_log）以及业务 JS 异常（MRN 容器异常）。逐类拉取异常日志详情后，按时间线汇总该用户的全部异常数据（Raptor 查询链接、每类异常日志摘要、汇总分析结论），串起来高效定位用户问题。
  触发方式：用户输入了 uuid（一般是十六进制字符，长度 64 位）且带着明确的查询异常详情的诉求即触发。若用户没有告知是哪个 APP，必须先提问让用户提供 APP 名称（含平台，如"美团iOS"）。
  触发词：uuid查异常、uuid查崩溃、查这个用户的异常、查这个设备的崩溃、deviceId查异常、设备异常排查、用户异常排查、这个uuid发生过什么问题、查一下这个uuid。
  注意：不涉及 uuid/userid/dpid/unionid 等 ID 互转（万能钥匙能力），如用户要的是 ID 转换，直接拒绝。
tags: 终端基础技术,Raptor,大前端,Crash,异常排查,uuid,deviceId
version: 0.3.0
created: 2026-06-08
metadata:
  skillhub:
    creator: zhangxinyue27
---

# UUID 查询异常日志

## 目标

用户给出一个 **uuid（设备标识 deviceId）** 时，检索该设备在**最近 7 天**内发生过的**所有类型异常**，逐类拉取日志详情，最后按时间线汇总成一份完整的「该用户异常画像」报告：

- 每类异常的 Raptor 页面查询链接
- 每条异常的日志摘要（发生时间、异常类型、聚类、版本）
- 完整堆栈日志
- 综合分析结论（根据发生时间、日志详情，推断该用户出问题的原因）

把一个用户散落在崩溃、ANR、卡顿、JS 异常等多个系统中的问题串起来，排查更高效。

---

## 🔧 前置依赖

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## ⚠️ 重要约束（必读）

1. **最多查最近 7 天**：按 uuid 检索异常日志对服务端查询压力较大，**最多只查最近 7 天**，并且**必须在最终结果里明确说明查询的是哪几天的范围**（如"本次查询范围：2026-06-01 ~ 2026-06-08"）。

2. **稳定性异常：按“上报时间”一次查满 7 天，不要逐天循环**。⚠️**Crash/ANR 的上报时间 ≠ 发生时间**：崩溃发生后要等下一次启动 APP 才会上报，所以查询窗口用**正常查询时间（即服务端落库/上报时间，对应 `mt_datetime`）**去查：用一个 `--start "7天前 00:00:00" --end "今天 23:59:59"` 区间、`--size 200 --excludes log -t 120000` 一次性查完，**返回的 `data[]` 数组长度就是该类型的真实总次数**。⚠️**严禁拿 `crashTime` 去做查询窗口过滤或逐天拆分**：`crashTime` 在部分设备上为空/脏数据（可能恒为 `1970-01-01 08:00:00`），拿它查会大量漏数据（曾导致 crash 真实 21 次被错报成 1 次）。但**排时间线**时按类型选发生时间字段：**watchdog 优先用可靠的 `foomTime`，crash/anr 优先用 `crashTime`**；任一字段取到离谱值（`1970`/空/超出查询窗口）时才回退到 `mt_datetime` 并标注为“(上报)”。

2.1. **业务 JS 异常必查，且必须加大超时**：第二部分（MRN 业务 JS 异常）是**必查项**，iOS/Android/鸿蒙都要查，不允许跳过或以"待查"敷衍。`get-summary-table` 走 `--project-id -1 --fe-type MRN --union-id <uuid> --sort-field DATE` 跨项目查询非常重，**默认 30s 几乎必定超时**，**必须把 `-t 120000` 放在全局位置**（写成 `raptorfe -t 120000 web error get-summary-table ...`；`web error` 子命令本身没有 `--timeout`）。⚠️**超时（`{"ok":false,"error":{"code":"TIMEOUT"}}`）绝不能当成"无数据/0 条"**——必须加大 timeout 重试，这是之前 JS 异常被错报成个位数的首要根因。另⚠️**漏 `--sort-field DATE` 会返回 `table.total=0`**（曾因此把真实 17 聚类错判为查不到）。同时 `--limit 200 --page-size 200` 拉全聚类，**JS 异常总次数 = `data.table.rows[]` 里所有聚类的 `COUNT` 之和**（不是聚类个数，也不是最大那条聚类的 COUNT；实测某设备 17 聚类合计 123 次，其中最大单聚类 COUNT=82）。

2.2. **链接必须拼好**：每一类查到数据的异常，都要在报告里给出拼好真实参数的 Raptor 页面链接（见文末「Raptor 页面查询链接构造」），不能只丢一个首页地址。

3. **必须先确认 APP**：若用户没说是哪个 APP，**先提问**："请问您要查询哪个 APP？请提供 APP 名称和平台，例如「美团iOS」「美团Android」「点评iOS」。" 拿到 APP 后再开始查询。

4. **不做 ID 互转**：本技能只用 uuid（deviceId）检索异常日志，**不提供** uuid↔userid↔dpid↔unionid 的转换。若用户要的是 ID 转换，回复："当前不支持 ID 查询/转换功能，请前往 Raptor 万能钥匙（https://raptor.mws.sankuai.com）系统界面中查询。请注意用户隐私，非必要不查询。"

5. **鉴权全自动**：`raptorfe` CLI 内置 SSO 鉴权，命令执行后可能沉默 10～30 秒（正在获取 token），属正常现象。若 stderr 提示大象 App 授权，引导用户去大象点击确认，**不要向用户索要 Cookie**。

---

## 输入

- **uuid（deviceId）**：64 位十六进制字符（如 `0000000000000168432A8B7FB49A2AE037DA4781AFDBAA173432293986005406`），也可能是其他长度，按用户给的原样使用。
- **APP 名称**：中文含平台（如"美团iOS"、"美团Android"、"点评iOS"）。

### APP 名称 → project 映射

内置常用映射（稳定性指标用 `--project`）：

| APP 名称 | project | 平台 |
| --- | --- | --- |
| 美团iOS | meituan | ios |
| 美团Android | android_platform_monitor | android |
| 点评iOS | nova | ios |
| 点评Android | android-nova | android |
| 外卖iOS | waimai_ios | ios |
| 外卖Android | meituanwaimai | android |
| 鸿蒙美团 | meituan-harmony | harmony |
| 外卖鸿蒙 | waimai-harmony | harmony |
| 点评鸿蒙 | harmony-nova | harmony |

若不在表中，动态查询：

```bash
raptorfe perf app list
```

从返回的 `data[]` 中匹配 `title`（模糊匹配中文名）+ `platform`（ios/android/harmony），取 `metricsProductName` 作为 project。

---

## 查询的异常类型

| type 值 | 含义 | 平台限制 | 说明 |
| --- | --- | --- | --- |
| `crash` | 崩溃 | 无 | 程序崩溃，有完整堆栈 |
| `anr` | ANR | 无 | 主线程执行任务超 5s 触发系统无响应。Android 监听 SIGQUIT 信号，iOS 主线程卡顿 5s |
| `watchdog` | 异常退出 | 无 | 因内存（FOOM/Low Memory）、卡死主线程（FANR）、系统信号（Signaled）等被系统强杀，通常无明确堆栈 |
| `catchexception` | 捕获异常 | **仅 Android** | 代码中 try-catch 捕获并主动上报的非致命错误，用户自定义上报，仅 Android 端 |
| `lag_log` | 卡顿 | 无 | 主线程任务执行耗时过长（默认阻塞超 3s），未达 ANR 标准但已明显掉帧 |

> **平台规则**：若 APP 是 **iOS 或鸿蒙** 平台，跳过 `catchexception`（仅 Android 支持），其余 4 种类型照常查询。
>
> 以上 5 种类型均通过 `raptorfe crash detail list` / `crash detail get` 的 `--type` 参数查询，直接传参即可查通。

---

## 第一部分：稳定性指标查询（crash / anr / watchdog / catchexception / lag_log）

底层命令：`raptorfe crash detail list` + `raptorfe crash detail get`。`--type` 支持上述全部 5 种类型。

### 第一步：计算时间范围

- 用 `date` 命令获取当前日期（不要凭记忆）：`date "+%Y-%m-%d"`。
- 取最近 7 天作为**一个整段区间**：`<7天前> 00:00:00 ~ <今天> 23:59:59`（一次查完，不拆天）。
- 在最终报告里写明查询范围（如"2026-06-02 ~ 2026-06-09"）。

### 第二步：对每种 type，按“上报时间”一次性查满 7 天（不要逐天循环）

对每种类型各执行**一次**（iOS/鸿蒙跳过 catchexception），用整段 7 天区间（按上报/落库时间，即接口默认索引时间）：

```bash
raptorfe crash detail list \
  --project <project> \
  --type <crash|anr|watchdog> \
  --start "<7天前 YYYY-MM-DD> 00:00:00" \
  --end "<今天 YYYY-MM-DD> 23:59:59" \
  --eq "deviceId,<uuid>" \
  --size 200 \
  --excludes log \
  -t 120000
```

> **⚠️ 数据完整性铁律（crash/JS 次数曾被严重统计偏小，务必遵守）：**
>
> 1. **按“上报时间”一次查满 7 天，不要逐天循环**：Crash/ANR 上报时间≠发生时间（崩溃后下次启动才上报），用接口默认的上报/落库时间一个 7 天区间一次就能拿全。**严禁拿 `crashTime` 做查询过滤或逐天拆分**——`crashTime` 在部分设备上为空/脏数据（可能恒为 `1970-01-01`），拿它过滤会大量漏数据。实测某设备一次查 7 天 crash 返回 21 条、watchdog 返回 20 条；若错误地逐天/按 crashTime 查只会命中个位数（曾出现 21 次被错报成 1 次的事故）。
> 2. **`data[]` 数组长度直接就是该类型的真实总次数**：`{"ok":true,"data":[...]}`，`len(data)` 即次数。`data` 里**每个元素就是一次独立异常**，不要去重、不要只取首条、不要只取某一天。`data:[]` 表示该类型无此异常。
> 3. **`--size` 设大（建议 200）+ `-t 120000` + `--excludes log`**：默认 size 仅 20、超时仅 30s。size 不够会截断（若返回条数 == size 需调大重查）；crash/watchdog 返回体大（实测 crash 单次返回可达 **4MB+**），务必 `--excludes log` 减小返回量，否则易超时/截断。
> 3.1. **⚠️ 返回体可能数 MB，必须先落盘再解析，不要直接 pipe 到 python/jq**：返回 JSON 很大时，直接 `raptorfe ... | python3 -c "..."` 会因 shell 管道缓冲被**截断**（报 `Unterminated string` / JSON 解析失败 / 计数为 0，且每次截断位置随机）。正确做法：先 `raptorfe ... > /tmp/q.json 2>/dev/null`，再 `python3 -c "import json; d=json.load(open('/tmp/q.json')); print(len(d['data']))"` 读文件解析。每个 type 单独一条命令落盘，不要在 for 循环里多条快速连发（会互相打断 stdout）。
> 4. **`--type` 仅支持 `crash | anr | watchdog`**：`lag_log`、`catchexception` 若 CLI 报不支持该 type，则该类型按"无数据/不支持"处理并在报告中注明。
> 5. **排时间线：按类型选发生时间字段，离谱时统一回退 `mt_datetime` 并标“(上报)”**：时间线应反映**真实发生时间**。
>   - **watchdog（异常退出/FOOM）优先用 `foomTime`**：实测 watchdog 的 `foomTime`（真实发生时间）**可靠**，且与上报时间仅差几秒（几乎实时上报），所以优先用 `foomTime`。
>   - **crash / anr 优先用 `crashTime`**：但 `crashTime` 在部分设备上为空/脏数据（可能恒为 `1970-01-01 08:00:00`）。
>   - **回退规则（通用）**：无论 `foomTime` 还是 `crashTime`，只要取到的是**离谱值**（为 `1970`、空、或明显超出本次查询窗口的异常时间），则回退到 `mt_datetime`（上报/落库时间，如 `2026-06-02 04:56:14+0800`）并在报告里给该时间加“(上报)”标注。其他可备选时间字段：`es_datetime`、秒级 `ts`。
>   - ⚠️这只影响**排序展示**，**查询窗口依然按上报时间**，两者不要混淆。

**返回字段说明：**

| 字段 | 含义 |
| --- | --- |
| `id` | 事件唯一标识（UUID 形式），用于查详情 |
| `crashTime` / `crashTimeDate` | **crash/anr 的真实发生时间**（崩溃那一刻）；部分设备为空/脏数据（如恒为 `1970-01-01 08:00:00`）。crash/anr **排时间线优先用它，离谱时回退 mt_datetime**；不要拿它做查询过滤 |
| `foomTime` | **watchdog 的真实发生时间**；实测**可靠**且与上报时间仅差几秒。watchdog **排时间线优先用它**；若也为离谱值（1970/空/超出查询窗口）同样回退 mt_datetime 并标“(上报)” |
| `mt_datetime` / `es_datetime` / `uploadTime` | **上报/落库时间**（crash/anr 是崩溃后下次启动上报那一刻；watchdog 几乎实时）；**查询窗口统一按它**。发生时间字段（crashTime/foomTime）离谱时用它排序并标“(上报)” |
| `ts` | 秒级时间戳（同上报时间），也用于查详情 |
| `message` | 异常聚类标识（栈顶签名），同一 message 表示同一类异常 |
| `appVersion` | 发生时的 APP 版本 |
| `hash` | 聚类 hash（另一种聚类标识，部分 type 用 hash 而非 message 作为主聚类键） |

> 返回 `{"ok":true,"data":[]}` 表示该类型在这 7 天无数据，正常跳过即可。

### 第三步：对每条记录拉取完整日志详情

对第二步查到的**每条事件记录**，用其 `id` 和 `ts` 拉详情：

```bash
raptorfe crash detail get \
  --id "<上一步返回的 id>" \
  --ts <上一步返回的 ts> \
  --project <project> \
  --type <对应的 type>
```

返回完整堆栈日志（iOS 为 `iosLog` 字段，Android 为 `androidLog` 字段）以及全部设备/环境信息、`loganId`（可跳转 Logan 查完整日志）。

---

## 第二部分：业务 JS 异常查询（MRN 容器）—— ⚠️ 必查，不可跳过

> **强约束：业务 JS 异常（MRN 容器异常）是本技能的必查项，无论 iOS / Android / 鸿蒙都必须查，不允许以"后续可补充""待查"等理由跳过。** 这类异常（JS OOM、容器注册失败、接口报错等）往往和稳定性 watchdog/crash 强关联，是定位根因的关键一环。**第一部分稳定性查询和第二部分 JS 异常查询都跑完，才算完成一次完整排查。**

底层命令：`raptorfe web error get-summary-table` / `get-error-detail` / `get-log-detail`。通过 `--union-id`（即 uuid/deviceId）+ `--fe-type MRN --project-id -1` 跨项目检索该设备的 MRN 容器 JS 异常。

### 前置：计算时间范围

CLI 的时间参数同时支持**毫秒时间戳**和**日期字符串**（如 `"2026-06-01"` / `"2026-06-01 10:00:00"`），推荐直接使用日期字符串：
- `startLong` = 7 天前的日期，如 `"<7天前 YYYY-MM-DD>"`
- `endLong` = 今天的日期，如 `"<今天 YYYY-MM-DD>"`

### 第一步：查异常聚类列表 + 次数（⚠️ 必须传 --limit 拉全）

```bash
raptorfe -t 120000 web error get-summary-table \
  --project-id -1 \
  --start-long "<7天前 YYYY-MM-DD>" \
  --end-long "<今天 YYYY-MM-DD>" \
  --union-id <uuid> \
  --fe-type MRN \
  --sort-field DATE \
  --sort-order DESC \
  --limit 200 \
  --page-size 200
```

> **⚠️ 三个必须，缺一即查不准（按 CLI 内置「MRN 跨项目查询」官方示例）：**
>
> 1. **必须把 `-t 120000` 放在全局位置（`raptorfe -t 120000 web error ...`，子命令前）**：`web error` 子命令**没有** `--timeout`，超时只能用全局 `-t`。`--project-id -1 --fe-type MRN` 跨项目查询很重，默认 30s 几乎必定超时。一旦返回 `{"ok":false,"error":{"code":"TIMEOUT",...}}`，**这是超时不是没数据**，必须用更大 timeout 重试，**绝不能当成 0 条**。这是 JS 异常被错报成个位数的首要根因。
> 2. **必须 `--union-id <uuid> --fe-type MRN --sort-field DATE`**：⚠️`--union-id` 接收的就是 64 位 uuid/deviceId（CLI 官方示例与 KM 文档均如此）；`--fe-type MRN` 才能让 `--project-id -1` 生效做跨项目查询；**`--sort-field DATE` 不能省**——实测漏掉它会返回 `table.total=0`（曾因此把真实的 17 聚类错报成查不到）。
> 3. **必须 `--limit 200 --page-size 200`**：默认 `limit=20`，不传会只返回前 20 个聚类，漏掉低频聚类（实测某设备真实有 17 个聚类）。

**⚠️ 返回结构（极易解析错，务必按此路径取数）：**

返回 JSON 的结构是 **`data.table.rows[]`**（不是 `data.rows[]`），聚类总数在 **`data.total`**：

```json
{"ok":true,"data":{"total":17,"limit":20,"table":{"rows":[
  {"main":"下单任务按钮配置下发不符合预期","COUNT":82,"CATEGORY":"customError","LEVEL":"info","USER_COUNT":2,"DATE":"2026-06-09 05:14:41"},
  {"main":"msiError-getCityInfo","COUNT":8,"CATEGORY":"customError","LEVEL":"info","DATE":"2026-06-03 05:26:55"}
]}}}
```

| 字段（在 `data.table.rows[]` 内） | 含义 |
| --- | --- |
| `main` | 异常名称（errorCategory），后续查明细用它 |
| `COUNT` | **该聚类的发生次数** |
| `USER_COUNT` | 影响用户数 |
| `CATEGORY` | 错误类型（jsError / ajaxError / resourceError / customError） |
| `DATE` | 最近上报时间 |
| `LEVEL` | 错误等级（error / warn / info） |

> **⚠️ JS 异常总次数 = `data.table.rows[]` 里所有聚类的 `COUNT` 之和**，不是聚类个数（`data.total`），也不是某一个聚类的 COUNT。实测某设备 17 个聚类、COUNT 分别为 82/8/8/4/4/4/2/2/2/1×... → JS 异常总次数 = 全部相加 = **123 次**；而其中最大的单个聚类「下单任务按钮配置下发不符合预期」COUNT=82（对应页面 `shortId` 那一条）。报告里的「业务JS异常」总数必须用这个累加值，**严禁把某个聚类的 COUNT（如 82）当成总数，也严禁只数前几条或只取最大那条**。
>
> **解析步骤（务必校验路径与字段名）**：聚类数组在 `data.table.rows[]`；每条用大写字段 `COUNT`（次数）、`main`（异常名）、`CATEGORY`（类型）、`USER_COUNT`（影响用户数）、`LEVEL`（等级）、`DATE`（最近上报）。`COUNT_TOTAL = sum(rows[i].COUNT)`；聚类数 = `len(rows)`，应等于 `data.total`。

### 第二步：查某个异常的日志明细列表（拿 errorLogId）

对第一步返回的**每个** `rows[].main`（建议优先查 COUNT 高、LEVEL=error 的聚类）执行：

```bash
raptorfe -t 120000 web error get-error-detail \
  --project-id -1 \
  --start-long "<7天前 YYYY-MM-DD>" \
  --end-long "<今天 YYYY-MM-DD>" \
  --error-category "<第一步返回的 rows[].main>" \
  --union-id <uuid> \
  --fe-type MRN
```

> ⚠️ 同样：`web error` 子命令没有 `--timeout`，超时用全局 `-t 120000`（放在 `raptorfe` 后、子命令前）。`--error-category` 必须精确等于第一步返回的 `rows[].main` 原文（含中文、冒号、空格）。

**⚠️ 返回结构：明细在 `data.result.table.rows[]`**（比 summary 多一层 `result`），该聚类总次数在 `data.result.total`（与 summary 的 COUNT 一致，可二次校验）：

| 字段（在 `data.result.table.rows[]` 内） | 含义 |
| --- | --- |
| `id` | errorLogId（如 `CHL-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`） |
| `main` | 上报时间（字符串，如 `2026-06-06 16:39:44`） |
| `data3` | 异常类型 |
| `data4` | 用户 ID（unionId） |
| `data5` | 容器（MRN） |
| `data6` | 系统（Android/iOS） |

### 第三步：查单条日志完整详情（堆栈）

对第二步返回的**每条记录**执行（`--log-date` 用第二步 `rows[].main` 的时间，支持日期字符串或毫秒时间戳）：

```bash
raptorfe web error get-log-detail \
  --error-log-id <第二步的 rows[].id> \
  --log-date "<第二步 rows[].main 对应的日期字符串或毫秒时间戳>"
```

**返回字段说明：**

| 字段 | 含义 |
| --- | --- |
| `stackInfo` | 完整堆栈 |
| `baseInfo.上报时间` | 上报时间 |
| `baseInfo.错误类型` | 错误类型 |
| `baseInfo.unionId` | 设备 unionId |
| `baseInfo.User Agent` | UA 信息（含 APP 版本、设备型号） |
| `locationInfo` | IP / 地点 / 运营商 / 网络 |
| `otherInfo.customInfo` | JSON 字符串，含 appVersion、bundleName、bundleVersion、device、systemVersion 等 |

---

## 第三部分：汇总输出报告

把第一、二部分查到的所有异常合并，**按发生时间倒序**展示，输出结构化报告：

```markdown
# UUID 异常排查报告

## 基本信息
- uuid（deviceId）：<uuid>
- APP：<APP 名称>（project: <project>，platform: <平台>）
- **查询时间范围：<YYYY-MM-DD> ~ <YYYY-MM-DD>（最近 7 天）**

## 异常总览
| 异常类型 | 发生次数 | 涉及版本 | 首次发生 | 最近发生 | Raptor 链接 |
| --- | --- | --- | --- | --- | --- |
| 崩溃(crash) | <n=data数组长度> | <版本> | <时间> | <时间> | <crash 页链接> |
| ANR | <n> | ... | ... | ... | <anr 页链接> |
| 异常退出(watchdog) | <n> | ... | ... | ... | <watchdog 页链接> |
| 捕获异常(catchexception) | <n> | ... | ... | ... | <仅Android> |
| 卡顿(lag_log) | <n> | ... | ... | ... | <lag_log 页链接> |
| 业务JS异常(MRN) | <n=所有聚类COUNT之和> | ... | ... | ... | <mrn-dashboard 链接> |

> 「发生次数」务必是真实值：稳定性类 = 一次查 7 天返回的 `data[]` 数组长度；业务JS = 所有聚类 COUNT 之和。每一行的 Raptor 链接都要拼好真实参数（见文末「链接构造」）。

## 异常时间线（按发生时间倒序）
| 发生时间 | 异常类型 | 异常聚类(message/errorCategory) | APP版本 | 摘要 |
| --- | --- | --- | --- | --- |
| <watchdog 优先 foomTime；crash/anr 优先 crashTime；任一为1970/空/超出窗口时用 mt_datetime 并加“(上报)”> | <type> | <message 或 hash 或 errorCategory> | <appVersion> | <堆栈栈顶/关键信息> |
| ... | ... | ... | ... | ... |

> 时间线按**真实发生时间**排序：**watchdog 优先取可靠的 `foomTime`，crash/anr 优先取 `crashTime`**；若该发生时间字段为 `1970-01-01`、空、或明显超出查询窗口，则回退用 `mt_datetime`（上报时间）并在该时间后加“(上报)”。

## 每类异常详情
### 崩溃(crash)
- 聚类：<message>
- 关键堆栈：
  ```
  <堆栈关键帧>
  ```
- Raptor 查询链接：<拼好的 crash 页链接>

### 业务JS异常(MRN)
- 聚类清单（按 COUNT 倒序，逐条列出，不得只列前几条）：

  | 聚类(errorCategory) | 类型(CATEGORY) | 等级(LEVEL) | 次数(COUNT) | 最近上报 |
  | --- | --- | --- | --- | --- |
  | <main> | <jsError/customError/...> | <error/warn/info> | <COUNT> | <DATE> |
  | ... | ... | ... | ... | ... |
  | **合计** | | | **<所有COUNT之和>** | |

- Raptor 查询链接：<拼好的 mrn-dashboard 链接（带 userId）>

（其余类型同理逐一展开）

## 综合分析结论
根据该用户异常发生的**时间先后**和**日志详情**，分析出问题的原因，例如：
- 是否集中在某个版本（升级后引入）
- 是否集中在某个时间段（某次操作触发连环异常）
- 崩溃/ANR/卡顿之间是否有关联（如内存问题先卡顿后 watchdog 退出）
- 是否为业务 JS 异常导致的连锁问题

## 备注
- 本次查询范围为最近 7 天，更早的数据不在查询范围内。
- catchexception 仅 Android 端支持；iOS/鸿蒙平台无此类数据。
```

**时间转换：** `ts`（秒级）转可读时间用 `date -r <ts> "+%Y-%m-%d %H:%M:%S"`，或在报告中说明对应的日期时间。

---

## Raptor 页面查询链接构造（⚠️ 必须拼好链接发出来）

> **强约束：查到每一类异常后，都要把对应的 Raptor 页面链接拼好、直接放进报告里**（不是只给一个 `https://raptor.mws.sankuai.com/crash` 首页）。让用户点开就能看到该 deviceId 的异常列表，便于人工核对。下面给出可直接拼接的规则。

### 一、稳定性异常（crash / anr / watchdog / lag_log / catchexception）

聚类列表页 URL 格式（参考 KM《Crash工作台url参数拼接规则》 https://km.sankuai.com/collabpage/2765211466）：

```
https://raptor.mws.sankuai.com/crash/#/crash/new/overview/index?project=<project>&type=<type>&filter=<filterJSON>
```

- `project`：APP 对应的 project（如 `meituan`）。
- `type`：异常类型，取值 `crash` / `anr` / `watchdog` / `lag_log` / `catchexception`。
- `filter`：**JSON 数组**，每个筛选项是 `{"k":"<字段>","v":"<值>"}`。按 deviceId 检索时，至少放入 deviceId 和时间范围：

```json
[{"k":"deviceId","v":"<uuid>"},{"k":"start","v":"2026-06-02 00:00:00"},{"k":"end","v":"2026-06-09 23:59:59"}]
```

**拼接注意（KM 规则）：**

1. `filter` 整体要做 URL 编码（`[`→`%5B`、`{`→`%7B`、`"`→`%22`、空格→`%20`、`:`→`%3A` 等）；尤其 `+` 必须替换为 `%2B`。
2. 一个筛选项有多个值时，值之间用 `||` 连接。
3. "堆栈"维度筛选要额外加 `{"o":"contain"}`（本场景按 deviceId 检索一般用不到）。

> 实际拼接可用脚本对 filter JSON 做 `urlencode` 后嵌入，避免手工转义出错。例如 Python：
> `import urllib.parse,json; f=urllib.parse.quote(json.dumps([{"k":"deviceId","v":uuid},{"k":"start","v":start},{"k":"end","v":end}],ensure_ascii=False))`

### 二、业务 JS 异常（MRN Web 端）

按 **userId（即 uuid/deviceId）** 维度查看某设备的 MRN 异常明细页 URL 格式：

```
https://raptor.mws.sankuai.com/mrn-dashboard/layout/error/js-detail?errorListCurrentPage=1&userId=<uuid>
```

- `userId`：直接填 uuid（设备 deviceId / unionId）。
- `errorListCurrentPage=1`：明细列表页码，固定 1 即可。
- 若要直接定位到**某个具体异常聚类**，可再带上 `shortId=<聚类短ID>`（Raptor 对 errorCategory 的短 hash）。`shortId` 非必需——不带 shortId 时页面展示该 userId 下全部聚类，带上则直接跳到该聚类。本技能在拿不到 shortId 时省略该参数即可。

> 示例（仅按设备查全部 JS 异常）：
> `https://raptor.mws.sankuai.com/mrn-dashboard/layout/error/js-detail?errorListCurrentPage=1&userId=0000000000000D402E686788146618AF6439F852DD5FFA168632797986143613`

### 三、链接输出要求

报告里**每一类查到数据的异常**都要给出对应链接：稳定性类给「一、」的 crash 页链接（type 换成对应类型），JS 异常给「二、」的 mrn-dashboard 链接。链接里的 `<uuid>`、时间范围都用本次查询的真实值填好。

---

## CLI 命令速查

| 命令 | 用途 | 关键参数 |
| --- | --- | --- |
| `raptorfe perf app list` | APP 中文名 → project 映射 | 取 `metricsProductName` |
| `raptorfe crash detail list` | 按 deviceId 一次查 7 天某类型事件列表 | `--type`、`--eq "deviceId,<uuid>"`、`--size 200 -t 120000` |
| `raptorfe crash detail get` | 拉单条稳定性事件完整堆栈 | `--id`、`--ts`、`--type` |
| `raptorfe -t 120000 web error get-summary-table` | 按 union-id(=uuid) 查 MRN 异常聚类列表+次数 | `--union-id`、`--fe-type MRN`、`--project-id -1`、`--sort-field DATE`、`--limit 200`；超时用全局 `-t` |
| `raptorfe -t 120000 web error get-error-detail` | 查某 MRN 异常明细（拿 errorLogId） | `--error-category`、`--union-id`、`--fe-type MRN`；超时用全局 `-t` |
| `raptorfe web error get-log-detail` | 查单条 MRN 异常完整堆栈 | `--error-log-id`、`--log-date`（毫秒） |

### 时间格式对照

| 模块 | 参数 | 格式 |
| --- | --- | --- |
| `crash detail list` | `--start` / `--end` | `"YYYY-MM-DD HH:MM:SS"` |
| `crash detail get` | `--ts` | 秒级时间戳或日期字符串 |
| `web error *` | `--start-long` / `--end-long` / `--log-date` | 毫秒时间戳或日期字符串 |
| `web error *` | 超时 | 子命令无 `--timeout`，统一用全局 `raptorfe -t 120000 web error ...` |

---

## 注意事项

1. **APP 未知必须先问**：用户没说 APP 时，先提问再查，不要默认猜测。
2. **稳定性按上报时间一次查 7 天、JS 异常加大超时**：Crash/ANR 上报时间≠发生时间（崩溃后下次启动才上报；watchdog 几乎实时），查询窗口统一按上报/落库时间（`mt_datetime`）用一个 7 天区间一次查完（`--size 200 -t 120000`），不拿 crashTime 做查询过滤/逐天拆；**排时间线按类型取发生时间：watchdog 优先 `foomTime`（可靠）、crash/anr 优先 `crashTime`，任一为 1970/空/超出窗口时回退 mt_datetime 并标“(上报)”**。JS 异常跨项目查询必须 `-t 120000`，超时不能当成无数据。
3. **结果必须标注时间范围**：报告里务必写明查询的是哪 7 天。
4. **catchexception 平台限制**：iOS/鸿蒙跳过该类型。
5. **空数据正常**：`{"ok":true,"data":[]}` 表示该类型在这 7 天无异常，跳过即可，不是报错。
6. **当前日期用 date 命令获取**：不要凭记忆写年份，所有时间计算基于 `date` 命令的真实输出。
7. **隐私保护**：仅在用户有明确排查诉求时查询，不做 ID 互转，不主动外泄设备/用户信息。
8. **鉴权**：CLI 自动 SSO，命令沉默 10～30s 属正常，遇大象授权提示引导用户确认，不索要 Cookie。
