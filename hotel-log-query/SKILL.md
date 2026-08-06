---
name: hotel-log-query
description: 美团酒店生单链路日志查询与枚举值查询的综合 skill。当用户需要查询 apic/generaltrade/aggregate/buy.process.v2 四个服务的生单日志、根据 traceId 追踪链路、分析生单失败原因，或查询枚举值含义时触发此 skill。

metadata:
  skillhub.creator: "wangjingpeng05"
  skillhub.updater: "wangjingpeng05"
  skillhub.version: "V3"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "6212"
  skillhub.high_sensitive: "false"
---

# hotel-log-query

本 skill 整合了酒店生单链路四层服务的日志查询规则，以及四个核心服务的枚举值定义，用于日志查询和错误码分析。

---

## 前置检查：logcenter-query-cli 安装检查与自动安装

> ⚠️ **每次执行日志查询前（代码仓库 clone/pull 操作除外），必须先检查 `logcenter-query-cli` 是否已安装。未安装则自动为用户安装。**

```bash
# 检查 logcenter-query-cli 是否已安装
which logcenter-query-cli
```

**判断逻辑：**
- 如果命令存在（返回路径），继续执行日志查询
- 如果命令不存在（`not found`），**自动执行安装**：

```bash
# 自动安装 logcenter-query-cli
catpaw skill install logcenter-query-cli
```

安装完成后，再次执行 `which logcenter-query-cli` 确认安装成功：
- 安装成功（返回路径）→ 继续执行后续日志查询步骤
- 安装失败 → 输出以下提示后**停止**：

```
❌ logcenter-query-cli 自动安装失败，请手动安装后重试。

手动安装方式：
  catpaw skill install logcenter-query-cli
```

**作用范围**：本 skill 中所有使用 `logcenter-query-cli` 查询日志的操作均需前置检查。代码仓库的 clone/pull/搜索操作不受此限制。

---

## 前置检查：代码仓库准备

当需要结合代码分析日志时，确保本地有以下仓库代码。如缺失，请自动 clone：

| 服务 | 仓库地址 | 本地路径 |
|------|----------|----------|
| apic | `ssh://git@git.sankuai.com/nib/trade-hotel-apic.git` | `{workspace}/trade-hotel-apic` |
| generaltrade | `ssh://git@git.sankuai.com/nib/hotel-order-generaltrade.git` | `{workspace}/hotel-order-generaltrade` |
| aggregate | `ssh://git@git.sankuai.com/nib/trade-hotel-aggregate.git` | `{workspace}/trade-hotel-aggregate` |
| buy.process | `ssh://git@git.sankuai.com/nib/trade-buy-common.git` | `{workspace}/trade-buy-common` |
| 插件包 | `ssh://git@git.sankuai.com/nib/trade-hotel-plugins.git` | `{workspace}/trade-hotel-plugins` |

**自动 clone 命令（如本地不存在）：**
```bash
# 检查并 clone apic
git clone -b master ssh://git@git.sankuai.com/nib/trade-hotel-apic.git

# 检查并 clone generaltrade
git clone -b master ssh://git@git.sankuai.com/nib/hotel-order-generaltrade.git

# 检查并 clone aggregate
git clone -b master ssh://git@git.sankuai.com/nib/trade-hotel-aggregate.git

# 检查并 clone buy.process
git clone -b master ssh://git@git.sankuai.com/nib/trade-buy-common.git

# 检查并 clone 插件包
git clone -b master ssh://git@git.sankuai.com/nib/trade-hotel-plugins.git
```

---

## 一、服务与日志查询规则

### 1. apic 服务（接入层）

- **服务名**：`com.sankuai.mptrade.hotel.apic`
- **查询生单日志的 DSL 条件**：
  - **已知 traceId 时**：
    ```
    traceId__:{traceId}
    ```
  - **仅有 code、无 traceId 时**：
    ```
    path:"/hotelorder/trade/precreate/submit" && "<code>"
    ```
- **CLI 查询命令（已知 traceId）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.apic -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
  ```
- **CLI 查询命令（仅有 code）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.apic -s "{startDate}" -e "{endDate}" -q 'path:"/hotelorder/trade/precreate/submit" && "{keyword}"' --size 50 --json
  ```
- **返回重点**：`message` 字段（包含 error.code 和 error.message）、`traceId__` 字段
- **重点入参**：`userId`、`poiId`、`goodsId`、`skuId`、`checkinDate`、`checkoutDate`、`roomCount`、`roomPrice`
- **重点返回值**：`error.code`、`error.message`、HTTP 状态码

---

### 2. generaltrade 服务（交易层）

- **服务名**：`com.sankuai.mptrade.hotel.generaltrade`
- **查询 DSL 条件**：
  - **已知 traceId 时**：用 `traceId__:` 精确查询
    ```
    traceId__:{traceId}
    ```
  - **仅有 code、无 traceId 时**：
    ```
    "<code>" && "CreateOrderFacadeService.createOrder"
    ```
- **CLI 查询命令（已知 traceId）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.generaltrade -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
  ```
- **CLI 查询命令（仅有 code）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.generaltrade -s "{startDate}" -e "{endDate}" -q '"<code>" && "CreateOrderFacadeService.createOrder"' --size 50 --json
  ```
- **返回重点**：`result=` 后面的内容（包含 `responseHeader.code`、`responseHeader.message`、`partnerId`）
- **重点入参**：`[param]=` 中的 `partnerId`、`goodsId`、`skuId`、`userId`、`checkinDate`、`checkoutDate`、`roomPrice`
- **重点返回值**：`responseHeader.code`、`responseHeader.message`、`partnerId`、`orderId`（如有）

---

### 3. aggregate 服务（聚合层 / agg）

- **服务名**：`com.sankuai.mptrade.hotel.aggregate`
- **查询 DSL 条件**：
  - **已知 traceId 时**：用 `traceId__:` 精确查询
    ```
    traceId__:{traceId}
    ```
  - **仅有 code、无 traceId 时**：
    ```
    "<code>" && "OpOrder4CServiceImpl#createOrder"
    ```
- **CLI 查询命令（已知 traceId）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.aggregate -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
  ```
- **CLI 查询命令（仅有 code）**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.hotel.aggregate -s "{startDate}" -e "{endDate}" -q '"<code>" && "OpOrder4CServiceImpl#createOrder"' --size 50 --json
  ```
- **返回重点**：`[result]=` 后面的内容（包含 `code`、`msg`、`orderId`）；`[param]=` 仅在用户明确要求时返回
- **重点入参**：`[param]=` 中的 `goodsId`（或 `goodId`）、`poiId`、`partnerId`、`userId`、`skuId`、`checkinDate`、`checkoutDate`、`roomPrice`、`activityPrice`
- **重点返回值**：`[result]=` 中的 `code`、`msg`、`orderId`；失败时还需提取 `failSteps`、`riskdetails`
- **关键字段提取**：`goodsId`（或 `goodId`）、`poiId`、`partnerId`、`userId`、`skuId`

---

### 4. buy.process.v2 服务（购买流程层）

- **服务名**：`com.sankuai.mptrade.buy.process.v2`
- **查询 DSL 条件**：
  ```
  traceId__:{traceId}
  ```
- **CLI 查询命令**：
  ```bash
  logcenter-query-cli query -l com.sankuai.mptrade.buy.process.v2 -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
  ```
- **返回重点**：按时间顺序列出所有 `method`、`message` 字段，分析各步骤成功/失败节点及错误码
- **重点入参**：`productId`/`goodsId`、`skuId`、`userId`、`checkinDate`、`checkoutDate`、`roomPrice`、`requestId`（幂等键）
- **重点返回值**：最终 `code`（`OrderResultCodeEnum`）、`message`；失败时还需提取 `bizResultCode`、具体异常信息
- **注意**：实际日志中 `mt_appkey` 为 `com.sankuai.mptrade.buy.process`（无 `.v2` 后缀），这是正常现象，日志主题名仍用 `com.sankuai.mptrade.buy.process.v2` 查询

---

## 二、时间参数规则

- 时间格式：`YYYYMMDDHHmmss`，例如 `20260312002500`
- 用户未指定时间时，默认查询**最近一小时**
- 用户指定"最近 N 小时"时，endDate 取当前时间，startDate 取当前时间减 N 小时
- **查询前必须先用 `date` 命令获取当前时间，不得凭记忆推算**

### Raptor 告警时间解析规则

当用户提供 Raptor 告警信息时，必须从告警内容中**提取数据时间**（而非告警发送时间），并以该时间为中心，前后各扩展 5 分钟作为日志查询的时间窗口。

**Raptor 告警中的时间字段识别：**

告警内容中通常包含以下时间相关字段（按优先级排列）：
1. `数据时间` / `dataTime` / `data_time`：**优先使用此字段**，这是实际产生问题的时间点
2. `告警时间` / `alertTime` / `alert_time`：告警触发/发送的时间（可能有延迟，作为备选）
3. 告警文本中的时间段描述（如 "14:30~14:35 期间"）：取该时间段的中间点

**时间窗口计算：**

```
提取的数据时间: T
startDate = T - 5分钟
endDate = T + 5分钟
```

**示例：**

假设 Raptor 告警内容中包含 `数据时间: 2026-05-21 14:32:00`：
- startDate = `20260521142700`（14:32 - 5分钟 = 14:27）
- endDate = `20260521143700`（14:32 + 5分钟 = 14:37）

**注意事项：**
- 如果告警中同时存在"数据时间"和"告警时间"，**必须使用数据时间**，因为告警发送通常有1-5分钟延迟
- 如果告警中只有"告警时间"而无"数据时间"，则使用告警时间并向前多扩展 5 分钟（即 startDate = 告警时间 - 10分钟，endDate = 告警时间 + 5分钟）
- 如果告警中包含明确的时间段（如 "14:30-14:35"），startDate = 时间段开始 - 5分钟，endDate = 时间段结束 + 5分钟
- 解析告警时间时需要注意日期部分，确保日期正确（尤其是跨天场景）

---

## 三、直接提供 traceId 时的快速查询流程

当用户**直接提供 traceId**（而非 code）时，跳过 code 识别步骤，**立即按 apic → generaltrade → aggregate → buy.process.v2 顺序**依次查询四层日志。

### ⚡ 触发条件
用户输入中包含一串数字形式的 traceId（如 `-1234567890123456789` 或 `1234567890123456789`），且未提供 code 码。

> ⚠️ **负数 traceId 注意**：当 traceId 为负数（以 `-` 开头）时，DSL 中必须用引号包裹，否则会触发 `parse_exception`：
> - 正数 traceId：`-q 'traceId__:1234567890123456789'`
> - 负数 traceId：`-q 'traceId__:"-1234567890123456789"'`

### 📋 执行步骤

#### Step 0：获取当前时间
执行 `date` 命令获取当前时间，默认查询**最近一小时**（用户未指定时间时）。

#### Step 1：查询 apic 层

**查询条件**：`traceId__:{traceId}`

**CLI 命令**：
```bash
logcenter-query-cli query -l com.sankuai.mptrade.hotel.apic -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

**提取并输出以下内容**：
- 重点入参：`userId`、`poiId`、`goodsId`/`goodId`、`skuId`、`checkinDate`、`checkoutDate`、`roomCount`、`roomPrice`
- 重点返回值：`error.code`、`error.message`（HTTP 响应中的错误信息）
- 请求时间（`es_datetime`）

#### Step 2：查询 generaltrade 层

**查询条件**：`traceId__:{traceId}`

**CLI 命令**：
```bash
logcenter-query-cli query -l com.sankuai.mptrade.hotel.generaltrade -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

**提取并输出以下内容**：
- 重点入参：`[param]=` 中的 `partnerId`、`goodsId`、`skuId`、`userId`、`checkinDate`、`checkoutDate`、`roomPrice`
- 重点返回值：`result=` 中的 `responseHeader.code`、`responseHeader.message`、`partnerId`、`orderId`（如有）

#### Step 3：查询 aggregate 层

**查询条件**：`traceId__:{traceId}`

**CLI 命令**：
```bash
logcenter-query-cli query -l com.sankuai.mptrade.hotel.aggregate -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

**提取并输出以下内容**：
- 重点入参：`[param]=` 中的 `goodsId`/`goodId`、`poiId`、`partnerId`、`userId`、`skuId`、`checkinDate`、`checkoutDate`、`roomPrice`、`activityPrice`
- 重点返回值：`[result]=` 中的 `code`、`msg`、`orderId`；失败时额外提取 `failSteps`、`riskdetails`

#### Step 4：查询 buy.process.v2 层

**查询条件**：`traceId__:{traceId}`

**CLI 命令**：
```bash
logcenter-query-cli query -l com.sankuai.mptrade.buy.process.v2 -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

**提取并输出以下内容**：
- 重点入参：`productId`/`goodsId`、`skuId`、`userId`、`checkinDate`、`checkoutDate`、`roomPrice`、`requestId`（幂等键）
- 重点返回值：最终 `code`（`OrderResultCodeEnum`）、`message`；失败时额外提取 `bizResultCode`、具体异常堆栈信息
- 按时间顺序列出所有关键 `method` 和 `message`，还原完整流程步骤

#### Step 5：汇总分析

完成四层查询后，输出以下分析报告：

```
📊 链路分析报告

🔗 traceId：{traceId}
⏰ 请求时间：{时间}

【apic 层】
- 入参：userId={}, poiId={}, goodsId={}, skuId={}, checkin={}, checkout={}, roomPrice={}
- 返回：code={}, message={}

【generaltrade 层】
- 入参：partnerId={}, goodsId={}, skuId={}, roomPrice={}
- 返回：responseHeader.code={}, responseHeader.message={}

【aggregate 层】
- 入参：goodsId={}, poiId={}, partnerId={}, userId={}, roomPrice={}, activityPrice={}
- 返回：code={}, msg={}, orderId={}

【buy.process.v2 层】
- 入参：productId={}, skuId={}, userId={}, requestId={}
- 返回：code={}, message={}
- 关键流程步骤：
  1. {时间} [{method}] {message}
  2. ...

🔍 根因分析：
{结合各层日志和枚举值含义，给出精确根因说明}

💡 建议处理方式：
{根据根因给出处理建议}
```

---

## 四、按 code 查询失败原因的完整流程

当用户给出一个 code 码（如告警中的结果值）并要求分析失败原因时，按以下步骤执行：

---

### ⚡ 特殊触发规则：用户同时提到「生单失败」和「枚举 code 值」时

当用户的输入中**同时包含"生单失败"（或"下单失败"）和具体的枚举 code 数值**时，必须严格按以下三步顺序执行，**不得跳过或调换顺序**：

#### 🔍 第一步：检查本地仓库相关代码

在查日志之前，先检查本地代码仓库中与该 code 相关的逻辑：

1. 确认本地仓库是否存在（参考"前置检查：代码仓库准备"章节），如不存在则先 clone
2. 根据 code 前缀判断所属服务，在对应仓库中搜索该枚举值的定义和使用位置：
   - `103100xxx` → 搜索 `hotel-order-generaltrade` 仓库
   - `1030xxx` → 搜索 `trade-hotel-aggregate` 仓库
   - `1200xxx` / `2020xxx` → 搜索 `trade-buy-common` 和 `trade-hotel-plugins` 仓库
   - 其他 → 搜索 `trade-hotel-apic` 仓库
3. 搜索该 code 对应枚举名在代码中的抛出位置（`throw`、`return`、`buildFailed` 等），判断是否存在明显的代码逻辑问题（如近期改动、条件判断异常等）
4. 将代码检查结论告知用户（"代码逻辑正常"或"发现可疑改动：xxx"）

#### 📋 第二步：立即查询枚举值含义并告知用户

代码检查完成后，**立即**从本 skill 内置的枚举定义（第六章节"枚举值定义"及 `references/enum_codes.md`）中查找该 code：

1. 确认 code 所属服务和枚举名称
2. 给出该枚举值的完整含义和业务解释
3. 结合第九章节（aggregate 日志结合代码分析指南）或第十章节（buy 服务生单流程代码分析）中对应场景的说明，给出初步判断方向
4. **在开始查日志之前，先将枚举含义和初步分析结论输出给用户**，格式如下：

```
📌 枚举值解析：
- Code：{code}
- 所属服务：{服务名}
- 枚举名：{枚举名}
- 含义：{含义描述}
- 初步判断：{根据枚举含义给出的可能根因方向}

🔧 代码检查结论：{正常 / 发现可疑点：xxx}

⏳ 接下来将进行日志排查...
```

#### 🔎 第三步：进行日志排查

完成前两步后，再按照下方"标准日志排查流程（Step 1～Step 5）"执行日志查询与分析。

---

### 标准日志排查流程

### Step 1：识别 code 所属服务
对照 `references/enum_codes.md` 中的枚举表，判断该 code 属于哪个服务：
- `103100xxx` → generaltrade
- `1030xxx` → aggregate
- `1200xxx` → buy.process
- 其他 → apic

### Step 2：从 apic 层查日志，提取 traceId
始终先从 apic 层查，以 code 为关键词，提取所有命中的 `traceId__` 字段。

**若 apic 查不到（0 条日志）**，按以下顺序降级，用 code 直接在下层查：
1. 用 code 查 **generaltrade**（条件：`"<code>" && "CreateOrderFacadeService.createOrder"`），从结果中提取 traceId
2. 若 generaltrade 也查不到，用 code 查 **aggregate**（条件：`"<code>" && "OpOrder4CServiceImpl#createOrder"`），从结果中提取 traceId
3. 拿到 traceId 后，继续执行 Step 3

### Step 3：用 traceId 逐层查全量日志
拿到 traceId 后，**按 generaltrade → aggregate → buy.process.v2 顺序**，对每个 traceId 使用 `traceId__:{traceId}` 条件精确查询：
- generaltrade：提取 `result=` 中的 `responseHeader.code`、`responseHeader.message`、`partnerId`
- aggregate：提取 `[result]=` 中的 `code`、`msg`，以及 `goodsId`、`poiId`、`partnerId`、`userId`
- buy.process.v2：提取所有 `method` 和 `message`，按时间顺序还原完整流程步骤

> 已在某层用 code 查到日志并提取了 traceId 的，该层无需重复查询，直接从下一层开始用 `traceId__:{traceId}` 精确查。

### Step 4：⚠️ 强制要求
**任何生单失败分析，都必须查到 buy.process.v2 层，不得仅停留在 aggregate 层就给出结论。**

### Step 5：汇总分析
- 统计各 traceId 的 `goodsId`、`poiId`、`partnerId`、`userId` 是否有重复
- 判断是个例（特定商品/酒店/用户）还是系统性问题（不同商品/酒店均失败）
- 结合 buy.process.v2 的完整流程日志，给出精确根因说明

---

## 五、日志内容提取方式（logcenter-query-cli JSON 输出解析）

`logcenter-query-cli query ... --json` 返回 JSON 数组，每条日志为一个 JSON 对象。直接从 CLI 输出的 JSON 中提取所需字段。

### 5.1 CLI 输出格式说明

`logcenter-query-cli query --json` 返回格式为 JSON 数组，每个元素包含日志字段：

```json
[
  {
    "traceId__": "1234567890123456789",
    "es_datetime": "2026-05-21 14:30:25",
    "message": "...",
    "method": "...",
    "path": "...",
    "mt_appkey": "...",
    ...其他字段
  },
  ...
]
```

### 5.2 提取 traceId 和时间（apic 层）

从 CLI JSON 输出中，直接读取每条记录的 `traceId__` 和 `es_datetime` 字段：

```bash
# 查询并提取 traceId 列表
logcenter-query-cli query -l com.sankuai.mptrade.hotel.apic -s "{startDate}" -e "{endDate}" -q 'path:"/hotelorder/trade/precreate/submit" && "{keyword}"' --size 50 --json
```

从返回的 JSON 数组中提取每条记录的：
- `traceId__`：链路追踪 ID
- `es_datetime`：日志时间
- `message`：包含请求入参和返回值

### 5.3 提取 generaltrade 的 result 内容

```bash
logcenter-query-cli query -l com.sankuai.mptrade.hotel.generaltrade -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

从返回 JSON 的 `message` 字段中匹配 `result=` 后的内容，提取 `responseHeader.code`、`responseHeader.message`、`partnerId`。

### 5.4 提取 aggregate 的 [result]= 内容及关键字段

```bash
logcenter-query-cli query -l com.sankuai.mptrade.hotel.aggregate -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

从返回 JSON 的 `message` 字段中匹配：
- `[result]=` 后的内容：提取 `code`、`msg`、`orderId`
- `"goodsId":(\d+)` 或 `"goodId":(\d+)`
- `"poiId":(\d+)`
- `"partnerId":(\d+)`
- `"userId":(\d+)`

### 5.5 提取 buy.process.v2 的完整流程步骤

```bash
logcenter-query-cli query -l com.sankuai.mptrade.buy.process.v2 -s "{startDate}" -e "{endDate}" -q 'traceId__:{traceId}' --size 50 --json
```

从返回的 JSON 数组中，按 `es_datetime` 时间顺序，提取每条记录的：
- `es_datetime`：步骤执行时间
- `method`：调用方法名
- `message`：日志内容（取前 250 字符）

重点关注 `message` 中包含以下关键词的记录（失败节点）：
- `fail`、`conflict`、`PROMOTION`、`success`、`error`、`exception`

### 5.6 CLI 查询注意事项

- **时间格式**：`-s` 和 `-e` 参数使用 `YYYYMMDDHHmmss` 格式，如 `20260521143000`
- **负数 traceId**：当 traceId 为负数时，DSL 中需要用引号包裹：`'traceId__:"-1234567890123456789"'`
- **JSON 解析**：CLI 输出为标准 JSON，可直接用 `python3 -c "import json,sys; data=json.load(sys.stdin); ..."` 进行结构化处理
- **结果为空**：如果返回空数组 `[]`，说明该时间段无匹配日志，需扩大时间范围或检查 DSL 条件

---

## 六、buy.process.v2 典型失败模式

根据实际分析积累，以下是常见失败链路模式：

### 模式一：营销属性冲突（PROMOTION_VALIDATE_FAIL）
```
TpSceneService.getForBuy → success
FloorPriceBusiness 价格模式 → priceMode=N
promotion property conflict (rulePropertyTypeCode:17/18) ← ⚠️ 冲突点
RiskEventService.riskLevel → success
OpPromotionService.lockPromotion → invoke success（但内部失败）
lockPreAmountDetail fail ← ❌ 锁定失败
CreateOrderAsyncProcessor async task fail: 优惠暂不可用 ← ❌
createOrder failed: PROMOTION_VALIDATE_FAIL - 优惠暂不可用 ← ❌ 根因
CreateOrderService.createOrder process failed ← ❌ 最终失败
OpPromotionService.unLockPromotion → 回滚
```
**根因**：营销规则 rulePropertyTypeCode 17（折扣率）/ 18（优惠金额）存在互斥冲突，导致优惠锁定失败。

---

## 六、枚举值定义

枚举值详见 `references/enum_codes.md`，包含以下四个服务的完整枚举：

- **apic**：`OhCreateOrderErrorCodeEnum`、`ErrorEnum`
- **generaltrade**：`CreateOrderErrorEnum`（code 前缀 `1031xxxxx`）
- **aggregate**：`OpCodeEnum`（code 前缀 `1030xxx`）
- **buy.process**：`OrderResultCodeEnum`（code 前缀 `1200xxx`）

### 常用 code 速查

| code | 服务 | 含义 |
|------|------|------|
| 103100000 | generaltrade | BOOK_FAIL - 预订失败（透传下层错误） |
| 1030008 | aggregate | RPC_UNKNOWN_ERROR - 远程调用未知异常 |
| 1030026 | aggregate | STOCK_DEDUCT_ERROR - 库存扣减失败 |
| 1030092 | aggregate | ZHILIAN_PHOENIX_NO_GOODS_INFO - 调直连Phoenix查不到商品信息/超时 |
| 1200306 | buy.process | PROMOTION_VALIDATE_FAIL - 营销校验失败（优惠暂不可用） |
| 1200304 | buy.process | PRODUCT_VALIDATE_FAIL - 商品校验失败 |
| 1200350 | buy.process | PAY_FAIL - 支付失败 |
| 5000 | buy.process | 订单支付单不存在 |

### 使用方式

当用户询问某个枚举值时：
1. 从 `references/enum_codes.md` 中查找该枚举值
2. 返回其所属服务、枚举名称和描述
3. 结合日志上下文给出业务含义解释

---

## 七、apic 代码层：`/hotelorder/trade/precreate/submit` 生单流程

> 本章节记录 apic 服务的代码调用链路与返回值处理逻辑，用于日志结合代码联合分析。

### 7.1 整体调用链路

```
客户端 HTTP POST /hotelorder/trade/precreate/submit
    └─ PreCreateOrderController.doBizSubmit()
           ├─ OrderSubmitConverter.convert(request)
           │      → 将 HTTP 请求参数转换为 PreCreateOrderContext
           │      → 失败时抛 ParamConvertFailException → code=500
           └─ CreateOrderFacade.execute(httpBaseRequest, preCreateOrderContext)
                  ├─ validate()
                  │      → PreCreateOrderUtil.doValidateParam4Submit()
                  │      → 失败时抛 ParamFailValidationException → code=500/1400
                  ├─ buildAsyncContext()  [异步并发构建]
                  │      ├─ WxOpenIdClientDuo          [微信渠道解密 openId，弱依赖]
                  │      ├─ AbtestClient               [AB 实验参数，弱依赖]
                  │      ├─ AbTestStrategyClient       [策略 AB 实验，弱依赖]
                  │      └─ CreateOrderClientDuo
                  │             └─ GeneralTradeBuyService.createOrder(CreateOrderParam)
                  │                    ↑ 核心强依赖 RPC，调用 generaltrade 服务
                  └─ mappingToResult()
                         → 将 CreateOrderResult 映射为 HttpResult
                         → 根据 responseHeader.code 决定返回成功/失败/弹窗
```

### 7.2 传给 generaltrade 的核心参数（CreateOrderParam）

| 参数组 | 关键字段 | 说明 |
|--------|---------|------|
| `UserInfoParam` | mtUserId、dpUserId、mtRealUserId、token | 用户身份 |
| `BookInfoParam` | checkInTime、checkOutTime、roomCount、guestList | 预订信息 |
| `GoodInfoParam` | goodId（goodsId）、spuId、isOverseaGoods | 商品信息 |
| `PayInfoParam` | roomMoney、payMoney、discountsMoney、redPacketsMoney | 支付金额 |
| `PromotionParam` | activitiesIds、redPacketCodes、superDealApplyId | 营销活动 |
| `MemberInfoParam` | needVip、rightInfoParams | 会员权益 |
| `MboxInfoParam` | mmcPreToken、mboxId | 神会员券包 |
| `RescheduleInfoParam` | relatedOrderId、diffMoney | 改签场景 |
| `EnvironmentStatInfoParam` | platform、version、userIp、uuid、utmSource、lat/lng | 环境信息 |
| `BusinessChannelParam` | specialChannel、thirdSupplyMode、superDealSceneType | 渠道信息 |
| `ExtraBusinessParam` | traceIdFromOrderBefore、repeatOrderCheck、returnPointsParam | 扩展业务参数 |
| `PlusGoodsParam` | groupBuyInfoParam、insureInfoParam | 超团/保险 |

### 7.3 返回值结构

```json
{
  "error": { "code": <int>, "message": "<string>", "type": "<string|null>" },
  "data": {
    "orderId": "<string>",
    "payMoney": <int>,
    "tradeNo": "<string>",
    "payToken": "<string>",
    "code": <int>,
    "prompt": { "type": 1, "title": "...", "text": "...", "hasLeftBtn": true, ... }
  },
  "traceId": "<string>"
}
```

- **成功**：`error` 为 `null`，`data.orderId` 有值
- **失败（直接报错）**：`error.code` 非零，`data` 为 `null`
- **失败（弹窗交互）**：`error` 为 `null`，`data.prompt` 有值，客户端展示弹窗

### 7.4 apic 自身 code（`ErrorEnum`，在 generaltrade 调用前产生）

| code | 枚举名 | 触发场景 |
|------|--------|---------|
| 200 | SUCCESS | 成功 |
| 401 | NOT_LOGIN | 登录验证失败 |
| 500 | SERVER_INTERNAL_ERROR | 服务端异常（兜底） |
| 500 | PARAM_VALIDATION_FAILED | 请求参数错误 |
| 500 | CREATE_PARAM_VALID_FAILED | 生单参数验证失败（ParamConvertFailException） |
| 50002 | BOOK_FAIL | generaltrade 返回 null 时的兜底 |

### 7.5 generaltrade 透传 code（`CreateOrderErrorEnum`，前缀 `1031xxxxx`）

境内场景下，apic **直接透传** generaltrade 的 `responseHeader.code`。

#### 基础错误（`10310 0xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103100000 | BOOK_FAIL | 预订失败（通用兜底） | buildFailed，message="预订失败" |
| 103100001 | PARAM_ERROR | 生单参数错误 | buildFailed |
| 103100002 | IDENTITY_INFO_VERIFY_ERROR | 身份信息验证失败 | buildFailed |
| 103100003 | CORP_PAY_ERROR | 非企业支付营销活动无法下单 | buildFailed |
| 103100007 | SAME_GOOD_REPEAT | 相同商品重单 | **buildSuccess + 弹窗**（可继续下单） |
| 103100008 | OTHER_GOODS_REPEAT | 同时段其他商品重单 | **buildSuccess + 弹窗**（可继续下单） |
| 103100016 | CANCEL_RULE_CHECK_FAIL | 改签取消规则校验失败 | **buildSuccess + 弹窗**（取消规则变化提示） |
| 103100017 | RHINO_LIMIT_REACHED | 生单限流 | buildFailed |
| 103100025 | RESERVE_TIME_EQUALS_TYPE_LIMIT_VALUE | 钟点房预订时间住满 | **buildSuccess + 弹窗** |
| 103100026 | RESERVE_TIME_LESS_TYPE_LIMIT_VALUE | 钟点房预订时间未住满 | **buildSuccess + 弹窗** |
| 103100030 | CREATE_ORDER_FAIL_BY_PRICE_MODE_ERROR | 产品价格模式不一致 | buildFailed |
| 103100032 | DISTRIBUTION_ORDER_PRICE_CHECK_FAIL | 分销价校验失败 | buildFailed |

#### 商品/库存错误（`10310 2xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103102000 | GOOD_PRICE_CHANGE | 商品变价 | buildFailed（变价类） |
| 103102001 | GOODS_BASIC_INFO_ERROR | 查询产品基础信息失败 | **buildSuccess + 弹窗**（"房型已被抢完"） |
| 103102002 | INVENTORY_INFO_ERROR | 查询产品库存信息失败 | buildFailed |
| 103102003 | INVENTORY_SHORTAGE_ERROR | 库存不足 | **buildSuccess + 弹窗**（"房型已被抢完"） |
| 103102004 | GOOD_STATUS_ERROR | 房态不可订 | **buildSuccess + 弹窗**（"房型已被抢完"） |
| 103102005 | ROOM_FULL_ERROR | 满房 | **buildSuccess + 弹窗**（message 透传） |
| 103102008 | SPOT_PAY_PRICE_CHANGE | 现付价格变价 | buildFailed（变价类） |
| 103102009 | GOODS_CALENDAR_ERROR | 商品日历解析错误 | buildFailed |
| 103102011 | STOCK_DEDUCT_ERROR | 库存扣减失败 | **buildSuccess + 弹窗**（"房型售罄"，左按钮"知道了"） |
| 103102013 | GOODS_PRICE_LOCAL_CHANGE | 商品原币种变价 | buildFailed（变价类） |
| 103102014 | GOODS_PRICE_EXCHANGE_CHANGE | 商品汇率变价 | buildFailed（变价类） |
| 103102015 | ROOM_LIMIT_EXCEED_ERROR | 限购商品超购 | **buildSuccess + 弹窗**（"已超过最大购买量"） |

#### 营销/风控错误（`10310 3xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103103000 | ACTIVITY_PRICE_CHANGE | 活动变价 | buildFailed（变价类） |
| 103103001 | COUPON_PRICE_CHANGE | 券变价 | buildFailed（变价类） |
| 103103002 | PROMOTION_RISK_CHANGE | 大额风控失败 | **buildSuccess + 弹窗**（可去掉活动继续） |
| 103103003 | POINT_PRICE_CHANGE | 积分变价 | buildFailed（变价类） |
| 103103004 | MBOX_PRICE_CHANGE | 神会员券包变价 | buildFailed（变价类） |
| 103103005 | SPEED_8_ACTIVITY_REPEAT_CHANGE | 速8专享活动重单 | **buildSuccess + 弹窗** |
| 103110000 | TRADE_DEFAULT_PRICE_CHANGE | trade 默认变价 | buildFailed（变价类） |
| 103110001 | TRADE_SPOT_PAY_TYPE_CHANGE | 担保/支付类型变更 | **buildSuccess + 弹窗**（message 透传） |

#### 风控错误（`10310 4xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103104000 | RISK_FAIL | 风控失败 | **buildSuccess + 弹窗**（可去掉活动继续；周寄单直接 buildFailed） |
| 103104001 | DELAY_USER_RISK_FAIL | 逾期用户风控 | **buildSuccess + 弹窗**（"去还款"按钮） |

#### 会员/权益错误（`10310 5xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103105000 | FLAGSHIP_GOODS_CHECK_FAIL | 旗舰店商品校验失败 | buildFailed（"房型已被抢完"） |
| 103105001 | BIZ_TRAVEL_CHECK_ERROR | 商旅权益返现失败 | **buildSuccess + 弹窗**（extraErrorInfo 中的 message） |
| 103105002 | BIZ_TRAVEL_PLUGIN_CHECK_ERROR | 商旅权益生单校验失败 | buildFailed（"房型已被抢完"） |
| 103105003 | RIGHT_DXSF_CHECK_ERROR | 定向升房失败 | **buildSuccess + 弹窗**（message 透传） |

#### 实名/超团错误（`10310 6/7xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103106000 | SUPER_GROUP_PRICE_CHECK_FAIL | 超团价格校验失败 | buildFailed（"请选择对应超团券"） |
| 103106001 | SUPER_GROUP_USER_CHECK_FAIL | 超团用户实名校验失败 | buildFailed（"需实名购买"） |
| 103107000 | REAL_NAME_PROMOTION_CHECK_EMPTY | 实名用户不存在 | **buildSuccess + 弹窗**（"去实名"按钮） |
| 103107001 | REAL_NAME_PROMOTION_CHECK_FAIL | 实名与入住人不一致 | **buildSuccess + 弹窗**（"修改入住人"按钮） |

#### 保险错误（`10310 8xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103108000 | INSURANCE_CHECK_ERROR | 保险校验失败 | buildFailed（统一文案：保险查询异常） |
| 103108001 | INSURED_PERSON_OVER_LIMIT | 被保人超限 | buildFailed（统一文案） |
| 103108002 | QUERY_INSURANCE_INFO_ERROR | 查询保险信息失败 | buildFailed（统一文案） |
| 103108003 | INSURANCE_PACKAGE_NOT_MATCH | 保险套餐不匹配 | buildFailed（统一文案） |
| 103108004 | INSURED_PERSON_ID_CHECK_ERROR | 被保人证件校验失败 | buildFailed（统一文案） |
| 103108005 | PREMIUM_NOT_MATCH | 保险保费不匹配 | buildFailed（统一文案） |
| 103108006 | USER_NOT_REAL_NAME | 账户未实名无法投保 | buildFailed（统一文案） |

#### 神会员（`10310 9xxx`）

| code | 枚举名 | 含义 | apic 处理方式 |
|------|--------|------|--------------|
| 103109000 | MERGE_COUPON_PACKAGE_BOOK_FAIL | 神会员券包合并下单失败 | **buildSuccess + 弹窗**（"网络异常，请稍后刷新重试"） |

### 7.6 境外场景 code 转换（`OhCreateOrderErrorCodeEnum`）

境外生单时，apic **不透传** generaltrade 的 `1031xxxxx` code，而是映射为：

| apic 返回 code | 枚举名 | 含义 | 对应 generaltrade code |
|----------------|--------|------|----------------------|
| 0 | SUCCESS | 成功 | 103100000（SUCCESS） |
| 500 | BOOK_FAIL / RATE_LIMIT | 预订失败 / 限流 | 其他未映射 code |
| 1001 | GOODS_SOLD_OUT | 商品售罄 | 103102001/03/04/05/11 等 |
| 1400 | PARAM_ERROR | 参数错误 | 103100001 |
| 2001 | REAL_NAME_VALIDATE_FAIL | 实名认证校验失败 | OH_REAL_NAME_CHECK_ERROR |
| 2002 | CREATE_ORDER_RISK_FAIL | 生单风控校验失败 | 103104000/103103002 |
| 2004 | HK_GUEST_NUM_OVER_LIMIT | 港旅局实名券入住人数超限 | OH_REAL_NAME_HK_USE_LIMIT |
| 2005 | PRICE_CHANGE_UP | 产品涨价 | 变价类 code（实际价 > 期望价） |
| 2006 | PRICE_CHANGE_DOWN | 产品降价 | 变价类 code（实际价 < 期望价） |
| 2007 | CANCEL_RULE_CHANGE | 取消规则变更 | 103100016 |
| 2008 | SUPER_GROUP_CHECK_FAIL | 超团券校验失败 | — |
| 2009 | MERGE_COUPON_PACKAGE_BOOK_FAIL | 神会员券包合并失败 | 103109000 |
| 10000 | UNITY_RESULT_EMPTY | Unity 结果为空 | 103100009 |

> **变价判断逻辑**：境外变价时，apic 比较「用户填单时的期望支付金额」与「generaltrade 返回的实际支付金额」，差值超过阈值（Lion 配置）才展示变价提示，否则视为成功。

### 7.7 异常处理兜底（`OrderSubmitExceptionHandler`）

| 异常类型 | 返回 code | 说明 |
|---------|-----------|------|
| `ParamConvertFailException` | 500 | 参数转换失败，showMsg 不为空时透传 showMsg |
| `ParamFailValidationException` | 500/1400 | 参数校验失败 |
| `VersionException` | 500 | 版本不支持（如注册会员需升级版本） |
| `SnapshotValidationException` | 500 | Snapshot 校验失败 |
| 其他 `Exception` | 500 | SERVER_INTERNAL_ERROR 兜底 |
| `Throwable`（非 Exception） | 500 | SERVER_INTERNAL_ERROR 兜底 |

### 7.8 日志结合代码分析指南

当 apic 日志中出现某个 code 时，结合本章节判断根因：

**场景一：apic 日志 code=500，message="服务端异常"**
→ 说明 generaltrade 调用抛出了未预期异常，或参数转换失败
→ 需查 generaltrade 日志确认是否有 RPC 超时/异常

**场景二：apic 日志 code=103100000（BOOK_FAIL）**
→ generaltrade 透传了下层（aggregate/buy.process）的失败
→ 必须继续查 generaltrade → aggregate → buy.process.v2 链路

**场景三：apic 日志 code=103102003/04/05/11（库存/房态/满房/扣减失败）**
→ 商品层问题，查 aggregate 的 `[result]=` 确认具体 code
→ 再查 buy.process.v2 确认是否到达扣减步骤

**场景四：apic 日志 code=103103002/103104000（风控）**
→ 营销风控问题，查 buy.process.v2 的 `OpPromotionService` 相关日志
→ 关注 `lockPromotion` 是否成功，`failActivityIds` 是哪些活动

**场景五：apic 日志 code=103103000/01/03/04（变价类）**
→ 价格不一致，查 buy.process.v2 的 `FloorPriceBusiness` 日志
→ 对比 `priceMode`、`priceTypeToSale` 与填单时的价格

**场景六：apic 日志 error=null 但 data.prompt 有值**
→ 属于"软失败"，客户端展示弹窗，用户可选择继续或取消
→ 查 data.code 字段确认具体原因（如 103100007=重单、103104000=风控）

---

## 八、generaltrade 代码层：`createOrder` 生单流程

> 本章节记录 generaltrade 服务的代码调用链路、异步 Ability 框架、下游 RPC 交互与错误码转换逻辑，用于日志结合代码联合分析生单失败根因。

### 8.1 整体调用链路

```
apic → GeneralTradeBuyService.createOrder(CreateOrderParam)
    └─ CreateOrderFacadeService.createOrder()          [Facade 层]
           ├─ 参数校验（validateParam）
           │      → 失败时抛 ParamErrorException → code=103100001
           ├─ CreateOrderAggregateService.createAggregateResult()  [Aggregate 层]
           │      → 使用异步 Ability 框架并发调用多个下游能力
           │      → 返回 CreateOrderAggregateResult
           └─ 异常捕获 & code 映射（handleXxxException）
                  → 将各类业务异常映射为 CreateOrderErrorEnum
                  → 封装为 CreateOrderResult 返回给 apic
```

### 8.2 Facade 层异常处理（`CreateOrderFacadeService`）

Facade 层捕获 Aggregate 层抛出的各类业务异常，统一映射为 `CreateOrderErrorEnum`：

| 异常类型 | 映射 code | 枚举名 | 说明 |
|---------|-----------|--------|------|
| `ParamErrorException` | 103100001 | PARAM_ERROR | 参数校验失败 |
| `GoodsBasicInfoException` | 103102001 | GOODS_BASIC_INFO_ERROR | 商品基础信息查询失败 |
| `InventoryInfoException` | 103102002 | INVENTORY_INFO_ERROR | 库存信息查询失败 |
| `InventoryShortageException` | 103102003 | INVENTORY_SHORTAGE_ERROR | 库存不足 |
| `GoodStatusException` | 103102004 | GOOD_STATUS_ERROR | 房态不可订 |
| `RoomFullException` | 103102005 | ROOM_FULL_ERROR | 满房 |
| `StockDeductException` | 103102011 | STOCK_DEDUCT_ERROR | 库存扣减失败 |
| `GoodPriceChangeException` | 103102000 | GOOD_PRICE_CHANGE | 商品变价 |
| `ActivityPriceChangeException` | 103103000 | ACTIVITY_PRICE_CHANGE | 活动变价 |
| `CouponPriceChangeException` | 103103001 | COUPON_PRICE_CHANGE | 券变价 |
| `PromotionRiskException` | 103103002 | PROMOTION_RISK_CHANGE | 大额风控失败 |
| `RiskFailException` | 103104000 | RISK_FAIL | 风控失败 |
| `IdentityInfoVerifyException` | 103100002 | IDENTITY_INFO_VERIFY_ERROR | 身份信息验证失败 |
| `RhinoLimitException` | 103100017 | RHINO_LIMIT_REACHED | 生单限流 |
| `TradeDefaultPriceChangeException` | 103110000 | TRADE_DEFAULT_PRICE_CHANGE | trade 默认变价 |
| `TradeSpotPayTypeChangeException` | 103110001 | TRADE_SPOT_PAY_TYPE_CHANGE | 担保/支付类型变更 |
| 其他 `Exception` | 103100000 | BOOK_FAIL | 兜底失败（透传下层 message） |

> **关键**：日志中出现 `BOOK_FAIL`（103100000）时，说明是兜底异常，需要查看 generaltrade 日志中的 `cause` 或 `exception` 字段，找到真正的异常类型，再对应上表定位根因。

### 8.3 Aggregate 层异步 Ability 框架

`CreateOrderAggregateService.createAggregateResult()` 使用自研异步框架并发执行多个 Ability：

**核心类说明：**

- `AsyncAbilityImpl`：异步 Ability 基类，将 Ability 的 `run()` 提交到线程池执行，返回 `CompletableFuture`
- `AsyncResultWrapper`：包装异步结果，调用 `getResult()` 时阻塞等待 `CompletableFuture` 完成
- `AsyncComplexAbilityBuilder`：组合多个 Ability，通过 `assemble()` 并发执行，通过 `chooseExecute()` 按条件选择执行路径

**典型执行流程：**

```
createAggregateResult()
    ├─ [并发] GoodsInfoAbility          → 查询商品基础信息
    ├─ [并发] InventoryAbility          → 查询库存信息
    ├─ [并发] PriceCheckAbility         → 价格校验
    ├─ [并发] PromotionCheckAbility     → 营销活动校验
    ├─ [并发] RiskCheckAbility          → 风控校验
    ├─ [串行] StockDeductAbility        → 库存扣减（依赖前置结果）
    └─ [路由] CreateOrderAbility        → 实际下单（按路由策略选择）
           ├─ NibCreateOrderAbility     → NIB 链路（IOpOrder4CService）
           ├─ TradeGeneralCreateOrderAbility → Trade 通用链路（IOrderTradePreSaleTFService）
           └─ TradeThirdCreateOrderAbility   → Trade 第三方链路
```

### 8.4 下游 RPC 客户端与 code 转换

#### NIB 链路（`NibCreateOrderAbility` → `NibCreateOrderClient`）

- **下游服务**：`IOpOrder4CService`（Thrift）
- **请求方法**：`opOrder4C.createOrder(OpCreateOrderRequest)`
- **响应**：`OpCreateOrderResponse`，包含 `resultCode`（NIB 自定义 code）
- **code 转换**（`NibCreateOrderResultUtil.convertNibCode()`）：

| NIB resultCode | 映射 CreateOrderErrorEnum | 说明 |
|----------------|--------------------------|------|
| SUCCESS | BOOK_SUCCESS | 成功 |
| INVENTORY_SHORTAGE | INVENTORY_SHORTAGE_ERROR | 库存不足 |
| ROOM_FULL | ROOM_FULL_ERROR | 满房 |
| GOOD_STATUS_ERROR | GOOD_STATUS_ERROR | 房态不可订 |
| PRICE_CHANGE | GOOD_PRICE_CHANGE | 价格变化 |
| STOCK_DEDUCT_FAIL | STOCK_DEDUCT_ERROR | 库存扣减失败 |
| RISK_FAIL | RISK_FAIL | 风控失败 |
| 其他失败 | BOOK_FAIL | 兜底失败 |

#### Trade 通用链路（`TradeGeneralCreateOrderAbility` → `TradeGeneralCreateOrderClient`）

- **下游服务**：`IOrderTradePreSaleTFService`（Thrift）
- **请求方法**：`tradeService.createOrder(TradeCreateOrderRequest)`
- **响应**：`TradeCreateOrderResponse`，包含 `code`（Trade 自定义 code）
- **code 转换**（`TradeCreateOrderResultUtil.convertTradeCreateOrderResultCode()`）：

| Trade code | 映射 CreateOrderErrorEnum | 说明 |
|------------|--------------------------|------|
| SUCCESS | BOOK_SUCCESS | 成功 |
| INVENTORY_SHORTAGE | INVENTORY_SHORTAGE_ERROR | 库存不足 |
| ROOM_FULL | ROOM_FULL_ERROR | 满房 |
| PRICE_CHANGE | GOOD_PRICE_CHANGE | 价格变化 |
| SPOT_PAY_PRICE_CHANGE | SPOT_PAY_PRICE_CHANGE | 现付价格变价 |
| STOCK_DEDUCT_FAIL | STOCK_DEDUCT_ERROR | 库存扣减失败 |
| RISK_FAIL | RISK_FAIL | 风控失败 |
| PROMOTION_RISK | PROMOTION_RISK_CHANGE | 大额风控 |
| PAY_TYPE_CHANGE | TRADE_SPOT_PAY_TYPE_CHANGE | 支付类型变更 |
| 其他失败 | TRADE_DEFAULT_PRICE_CHANGE 或 BOOK_FAIL | 视具体 code 决定 |

### 8.5 日志结合代码分析指南

当 generaltrade 日志中出现某个 code 或异常时，结合本章节判断根因：

**场景一：generaltrade 日志 code=103100000（BOOK_FAIL）**
→ 兜底异常，说明下游 RPC 抛出了未被特定异常类捕获的错误
→ 查 generaltrade 日志中的 `exception`/`cause` 字段
→ 若是 NIB 链路，查 `NibCreateOrderClient` 的 `resultCode` 字段
→ 若是 Trade 链路，查 `TradeGeneralCreateOrderClient` 的 `code` 字段
→ 再对照 8.4 节的 code 转换表找到下游原始错误

**场景二：generaltrade 日志 code=103102003/04/05/11（库存/房态/满房/扣减失败）**
→ 商品层问题，说明 NIB 或 Trade 下游返回了对应的库存/房态错误
→ 查 generaltrade 日志中 `NibCreateOrderAbility` 或 `TradeGeneralCreateOrderAbility` 的调用结果
→ 确认是哪条路由链路（NIB/Trade）触发的失败

**场景三：generaltrade 日志 code=103102000/103103000/01/03（变价类）**
→ 价格不一致，下游返回了价格变化信号
→ 查 generaltrade 日志中 `PriceCheckAbility` 的执行结果
→ 对比请求中的 `payMoney` 与下游返回的实际价格

**场景四：generaltrade 日志 code=103104000（RISK_FAIL）或 103103002（PROMOTION_RISK_CHANGE）**
→ 风控/营销风控失败，下游 RPC 返回了风控拒绝信号
→ 查 generaltrade 日志中 `RiskCheckAbility` 的执行结果
→ 结合 buy.process.v2 日志确认风控规则触发原因

**场景五：generaltrade 日志出现 `AsyncResultWrapper.getResult()` 超时或 `CompletableFuture` 异常**
→ 异步 Ability 执行超时，说明某个下游 RPC 调用耗时过长
→ 查 generaltrade 日志中各 Ability 的耗时（`cost` 字段）
→ 定位是哪个 Ability（GoodsInfo/Inventory/Risk 等）超时

**场景六：generaltrade 日志 code=103100017（RHINO_LIMIT_REACHED）**
→ 生单限流，说明触发了犀牛限流策略
→ 通常是短时间内同一用户/商品下单频率过高
→ 查 Lion 配置中的限流阈值是否有近期变更

**场景七：generaltrade 日志 code=103110001（TRADE_SPOT_PAY_TYPE_CHANGE）**
→ Trade 链路返回了支付类型变更信号（如担保→现付）
→ 查 `TradeGeneralCreateOrderClient` 的响应，确认 Trade 侧的 `payType` 变化
→ 通常需要客户端重新拉取商品信息后再下单

---

## 九、aggregate 代码层：`ICreateOrderAggregateService#createOrder` 生单流程

> 本章节记录 trade-hotel-aggregate 服务的 `createOrder` 完整编排流程，包括调用了哪些下游服务的哪些接口、返回值 code 的转换逻辑，用于日志结合代码联合分析生单失败根因。

### 9.1 整体调用链路

```
generaltrade → IOpOrder4CService.createOrder(TFCreateOrderParam)   [Thrift 入口]
    └─ OpOrder4CFacade.createOrder()
           ├─ 改签/代订场景：加全局锁后调用
           └─ ICreateOrderAggregateService.createOrder(CreateOrderContext)
                  └─ CreateOrderAggregateServiceImpl.createOrder()   [核心编排]
```

### 9.2 `createOrder` 编排步骤（串行主流程）

```
1. 入住人数前置校验（checkParam4GuestNames）
   → 超出间数11倍 → OpCodeEnum.GUEST_NAMES_OVER_ROOM_COUNT_11_TIMES (1030093)
   → 姓名超DB长度128 → OpCodeEnum.GUEST_NAME_OVER_DB_SIZE_128 (1030094)
   → 姓名重复（C端）→ OpCodeEnum.GUEST_NAME_REPEAT (1030095)

2. 改签/代订原单查询与校验（getAndCheckTransferInfo）
   → 调用 queryOrderDelegate.findAggregateOrderForceMaster()
   → 校验原单状态、转移类型、跨供应商等
   → 失败抛 OpResultException(OpCodeEnum.NOT_SUPPORT_TRANSFER 等)

3. 分销前置校验（checkParam4Distribution）
   → 校验 thirdOrderId、openSaleId、source、thirdAccess
   → 失败 → OpCodeEnum.PARAM_ERROR (1030007)

4. 微信极简支付参数校验（checkParamAndPrepare4QuickAndPay）
   → 校验 weChatRiskParam 不为空
   → 失败 → OpCodeEnum.PARAM_ERROR (1030007)

5. [可选] 创建父订单（domainBuyDelegate.createParentOrder）
   → 仅带保险时触发
   → 调用 buy 域 CreateOrderService.createParentOrder()

6. [可选] 预生成 orderId（domainBuyDelegate.createOrderIdAndBuyerId）
   → 境外无 orderId 或改签代订场景触发
   → 调用 buy 域 CreateOrderIdService.createOrderId()

7. ★ 核心生单（domainBuyDelegate.createOrder）
   → 调用 buy 域 CreateOrderService.createOrder()
   → 返回 CreateOrderRes（含 OrderDTO、tradeOrderId）
   → 特殊 code 处理（见 9.3 节）

8. 变价检测（addFailSteps + failIfNotSupportPriceChange）
   → 对比请求金额与生单结果金额，填充 failSteps
   → 若不支持变价且有变价 → OpCodeEnum.CREATE_ORDER_FAIL_BY_PRICE_CHANGE (1030067)

9. 分销验价（domainBizFactory.getService(bizCode).checkPrice4Distribution）
   → 国内分销：逐日校验 sellPrice/settlePrice
   → 境外分销：总价误差率校验（默认千分之8.75）
   → 失败 → OpCodeEnum.DISTRIBUTION_ORDER_PRICE_CHECK_FAIL (1030065)

10. 询价请求校验（inquiryRequestCheck）
    → 校验虚拟活动与真实活动不能同时存在
    → 失败 → OpCodeEnum.INQUIRY_WITH_VIRTUAL_AND_ACTUAL_ACTIVITY

11. 清空旧未支付订单（clearUnpayOrderService.asyncClearUnPayOrder）
    → 异步，不影响主流程

12. ★ 库存扣减/占用（domainBizFactory.getService(bizCode).lockOrDeductAndUpdateCreateSteps）
    → 新逻辑（灰度）：occupyStock → CreateOrderStep.INVENTORY
    → 老逻辑：deductStock → CreateOrderStep.INVENTORY
    → 失败 → OpCodeEnum.STOCK_DEDUCT_ERROR (1030026)
    → 同时调用 domainBuyDelegate.mergeOrderExtra() 保存库存快照

13. ★ 直连 double check（thirdPartyCreateOrder）
    → 调用 domainBizDelegate.thirdPartyCreateOrder()
    → 仅直连（直连BLD等）场景有实际逻辑
    → 失败 → OpCodeEnum.THIRD_PARTY_CREATE_ORDER_ERROR (1030075)

14. ★ 完成生单（domainBuyDelegate.finishCreateOrder）
    → 调用 buy 域 CreateOrderService.finishCreateOrder()
    → 触发 buy 域内部的营销锁定、风控等流程

15. [可选] 创建保险（orderInsuranceService.createInsurance）
    → 仅带保险时触发
    → 失败 → OpCodeEnum.CREATE_INSURANCE_FAIL (1030071)

16. ★ 预支付（domainBuyDelegate.prepayOrder / prepayOrder4NoPay）
    → 调用 buy 域 OrderPayService.prepayOrder()
    → 返回 OrderPrepayRes（含 tradeNo、payToken、thirdPayChannelType）
    → 失败 → OpCodeEnum.PREPAY_FAIL (1030020)

17. [可选] 创建权益单（createRightOrderServiceRouter.getService().createRightsOrder）
    → 仅有 rightsInfos4HotelMember 时触发

18. 状态变更通知（orderChangeNotifyService.asyncStatusChangeNotify）
    → 异步，CREATE → PAYING

19. 组装返回结果（genOrderResult）
    → code = PriceChangeUtil.parseCreateCodeByFailStep(failSteps)
    → 成功时 code = OpCodeEnum.SUC (1030000)，变价时返回对应变价 code
```

### 9.3 核心生单（buy 域）返回值 code 转换

`domainBuyDelegate.createOrder()` 调用 buy 域 `CreateOrderService.createOrder()`，返回 `CreateOrderRes`，其中 `header.resultCode` 为 buy 域自定义 code（`OrderResultCodeEnum`，前缀 `1200xxx`）。

**转换逻辑（`DomainBuyDelegateImpl.createOrder()`）：**

| buy 域 resultCode | 触发条件 | 映射 OpCodeEnum | aggregate code |
|-------------------|---------|----------------|----------------|
| `CREDIT_VALIDATE_FAIL` + riskLevel=逾期 | 逾期用户风控 | `DELAY_USER_RISK_FAIL` | 1030053 |
| `CREDIT_VALIDATE_FAIL` + 其他 | 风控拦截 | `RISK_FAIL` | 1030048 |
| 其他失败 | 通用失败 | 透传 buy 域 code/msg | buy 域原始 code |
| 成功 | — | `SUC` | 1030000 |

**特殊 code 处理（`dealCreateOrderResult()`）：**

| buy 域 productQueryResult.code | 含义 | 映射 OpCodeEnum | aggregate code |
|-------------------------------|------|----------------|----------------|
| 2020608 | 直连商品满房 | `ROOM_FULL` | 1030016 |
| 2020611 | 直连 Phoenix 查询超时 | `ZHILIAN_PHOENIX_NO_GOODS_INFO` | 1030092 |
| 2020612 | 直连 Phoenix 查询为空 | `ZHILIAN_PHOENIX_NO_GOODS_INFO` | 1030092 |

### 9.4 库存扣减 code 转换

`domainStockDelegate.deductStock()` / `occupyStock()` 调用商品平台库存接口（`OrderStockResponse`）：

- **成功或未知异常**：均标记 `CreateOrderStep.INVENTORY`（后续失败需归还库存）
- **明确失败**：抛 `OpResultException(OpCodeEnum.STOCK_DEDUCT_ERROR)`，code=1030026

### 9.5 变价 code 转换（`PriceChangeUtil.parseCreateCodeByFailStep`）

生单成功后，aggregate 对比请求金额与实际金额，按优先级（高→低）返回变价 code：

| 优先级 | failStep | OpCodeEnum | aggregate code |
|--------|---------|------------|----------------|
| 最高 | SKU_PRICE_EXCHANGE_CHANGE | `SKU_PRICE_EXCHANGE_CHANGE` | 1030097 |
| ↑ | SKU_PRICE_LOCAL_CHANGE | `SKU_PRICE_LOCAL_CHANGE` | 1030096 |
| ↑ | SKU_PRICE_CHANGE | `SKU_PRICE_CHANGE` | 1030051 |
| ↑ | ACTIVITY_PRICE_CHANGE | `ACTIVITY_PRICE_CHANGE` | 1030050 |
| ↑ | COUPON_PRICE_CHANGE | `COUPON_PRICE_CHANGE` | 1030049 |
| 最低 | POINT_PRICE_CHANGE | `POINT_PRICE_CHANGE` | — |

> **注意**：变价时生单仍然**成功**（订单已创建），aggregate 返回变价 code 是为了告知上游（generaltrade/apic）价格已变化，由上游决定是否展示弹窗或报错。

### 9.6 失败回滚逻辑（`rollback4Create`）

生单过程中任意步骤抛出异常，进入 catch 块执行回滚：

```
1. 取消 buy 域订单（domainBuyDelegate.cancelOrder）
   → 触发 buy 域营销回滚（解锁优惠券等）
   → 失败时原地重试一次

2. 老单停止转移（改签代订场景）
   → ExtraDataOpProxyService.resetTransFlagAndCheckInStatusForOldOrder()

3. 状态变更通知（CREATE → DELETED）

4. 归还魔盒库存（如有 INVENTORY_4_MBOX 步骤）
   → 异步延迟 500ms 执行

5. 归还普通库存（如有 INVENTORY 步骤）
   → 异步延迟 500ms 执行
   → 直连 doubleCheck 失败（THIRD_PARTY_CREATE_ORDER_ERROR）且非占用逻辑时，不归还库存
```

### 9.7 aggregate 对外返回的 `TFCreateOrderResult` 结构

```java
TFCreateOrderResult {
    int code;           // OpCodeEnum code（1030xxx）
    String msg;         // 错误描述
    TFPrepayInfo4CreateOrderDTO prepayInfo {
        Long orderId;
        String tradeNo;     // 支付流水号
        String payToken;    // 支付 token
        int orderPrice;     // 实付金额（分）
        int totalRoomPrice; // 房费总价（不含税）
        List<Integer> failSteps;    // 变价步骤列表
        List<TFPromotionInfoDTO> failPromotions; // 变价营销列表
    }
    boolean successForCombine; // 成功或变价时为 true（用于组合订单）
}
```

### 9.8 日志结合代码分析指南

当 aggregate 日志中出现某个 code 时，结合本章节判断根因：

**场景一：aggregate 日志 code=1030008（RPC_UNKNOWN_ERROR）**
→ buy 域 RPC 调用超时或网络异常
→ 查 aggregate 日志中 `createOrder未知异常` / `prepayOrder未知异常` 关键字
→ 确认是哪个 buy 域接口超时（createOrder/prepayOrder/finishCreateOrder）

**场景二：aggregate 日志 code=1030026（STOCK_DEDUCT_ERROR）**
→ 商品平台库存扣减失败
→ 查 aggregate 日志中 `deductStock` / `occupyStock` 的调用结果
→ 确认是库存不足还是商品平台接口异常

**场景三：aggregate 日志 code=1030048（RISK_FAIL）**
→ buy 域风控拦截（`CREDIT_VALIDATE_FAIL`）
→ 查 aggregate 日志中 `riskdetails` 字段，获取 `prompt`/`usedMobile`/`buyerTime`
→ 结合 buy.process.v2 日志确认具体风控规则

**场景四：aggregate 日志 code=1030053（DELAY_USER_RISK_FAIL）**
→ 逾期用户风控管制下单
→ buy 域返回 `CREDIT_VALIDATE_FAIL` 且 riskLevel=逾期
→ 用户有未还款记录，apic 会展示"去还款"弹窗

**场景五：aggregate 日志 code=1030075（THIRD_PARTY_CREATE_ORDER_ERROR）**
→ 直连 double check 失败（直连BLD等场景）
→ 查 aggregate 日志中 `ZL_DOUBLE_CHECK_TRANSACTION` CAT 打点
→ 注意：此场景下**不归还库存**（直连侧已重新推余量）

**场景六：aggregate 日志 code=1030092（ZHILIAN_PHOENIX_NO_GOODS_INFO）**
→ 直连 Phoenix 商品查询超时或为空
→ buy 域 productQueryResult.code=2020611/2020612
→ 通常是直连供应商侧问题，可查直连服务日志

**场景七：aggregate 日志 code=1030051/1030049/1030050（变价类）**
→ 生单成功但价格已变化
→ 查 aggregate 日志中 `failSteps` 字段确认变价类型
→ 对比请求中的 roomPrice/activityPrice/couponPrice 与生单结果

**场景八：aggregate 日志 code=1030067（CREATE_ORDER_FAIL_BY_PRICE_CHANGE）**
→ 因变价导致生单失败（strategy4PriceChange 不允许变价）
→ 查 aggregate 日志中 `failSteps` 确认变价类型
→ 通常是分销场景或特殊渠道不允许变价下单

---

## 十、buy 服务生单流程代码分析（trade-buy-common + trade-hotel-plugins）

### 10.1 服务入口：`CreateOrderServiceImpl#createOrder`

**文件**：`trade-buy-process-starter/.../order/CreateOrderServiceImpl.java`

buy 服务以 Thrift 方式对外暴露，端口 9001。入口方法：

```java
// 1. 通过 OnceBizSessionInvoke 包装，自动处理 BPF Session 上下文
CreateOrderResponse innerResp = createOrderDomainService.createOrder(
    ProcessStarterTransUtils.buildCreateOrderRequest(request)
);
// 2. 通过 TradeHotspotTracker 上报 CAT 业务指标
TradeHotspotTracker.getInstance().reportCatBusiness("createOrder", innerResp);
// 3. 将内部 CreateOrderResponse 转换为 Thrift 协议的 CreateOrderRes 返回
return ProcessStarterTransUtils.buildCreateOrderRes(createOrderResponse);
```

**关键点**：`OnceBizSessionInvoke` 保证每次 RPC 调用只执行一次，防止重复调用。

---

### 10.2 核心流程：`CreateOrderDomainServiceImpl#createOrder`

**文件**：`trade-buy-domain/.../service/CreateOrderDomainServiceImpl.java`

整体流程分为以下阶段（**所有步骤均通过 `getFirstSupportedAbility` 调用插件包扩展点**）：

```
① 限流检查（createOrderLimiter）
② 参数校验（CreateOrderRequestValidator.validateCreateOrder）
③ 构建扩展数据（buildExtDataWhenCreateOrder → BuildExtDataAbility）
④ 买家 ID 转换（buyerIdTransfer → BuyerIdTransferAbility）
⑤ 查询商品信息（productInfoQuery → BuildProductInfoAbility）  ← 调用商品平台
⑥ 查询其他信息（otherInfoQuery → OtherInfoQueryAbility）
⑦ 保存订单映射（saveOrderMapping → SaveOrderMappingAbility）
⑧ 幂等检查（requestIdempotentCheck → DB 唯一键插入）
⑨ 构建交易订单（buildTradeOrder → BuildTradeOrderAbility）
⑩ 查询价格中心（queryPriceCenter → NotifyPriceCenterAbility）
⑪ 获取关单时间（getOrderCloseTime → SubmitCloseOrderTaskAbility）
⑫ 订单校验（createOrderValidate → 参数/商品/价格/限购）
⑬ [新流程] 异步提交签约（asyncSubmitSign）
⑭ 价格锁定（orderPriceFixing → OrderPriceFixingAbility）  ← 调用营销平台
⑮ [新流程] 异步锁营销（asyncLockPromotion → PromotionLockBizV2）
⑯ [新流程] 异步风控校验（asyncRiskValidate → CreateOrderRiskDomainService）
⑰ 保存商品快照（saveSnapshot → ProductBiz.saveProductSnapshot）
⑱ 持久化订单（orderRepository.createOrderV2）
⑲ 等待异步任务完成（createOrderAsyncProcessor.end）
⑳ 提交关单任务 + 发送状态变更消息
```

**新旧流程区分**：`createOrderStandardizationFlowController.isNew(context)` 控制走新流程（标准化流程）还是老流程。新流程将锁营销、风控、签约异步化，先落库再等待异步结果。

---

### 10.3 插件机制：`getFirstSupportedAbility` 与 `executeFirstMatched`

buy 服务采用 BPF（Business Plugin Framework）插件架构，所有业务逻辑通过扩展点（Ability）调用插件包实现：

```
OrderBaseDomainService.getFirstSupportedAbility(bizCode, abilityCode, context)
  → 根据 bizCode 匹配插件包（hotel-buy-app）
  → 调用插件包中对应 BusinessExt 实现类的方法
```

**酒店插件包**：`trade-hotel-plugins/hotel-buy-app`

核心扩展点与插件实现对应关系：

| Ability 接口 | 酒店插件实现类 | 功能 |
|---|---|---|
| `BuildProductInfoAbility` | `CommonProductInfoQueryBusinessExtImpl` | 查询商品信息（调用商品平台） |
| `OrderPriceFixingAbility` | `CommonOrderPriceFixingBusinessExtImpl` | 价格锁定（调用营销平台） |
| `BuildTradeOrderAbility` | `CommonBuildTradeOrderBusinessExtImpl` | 构建订单对象 |
| `OrderParamsValidateAbility` | `CommonCreateOrderParamsValidateBusinessExtImpl` | 参数校验 |
| `ProductValidateAbility` | `CommonProductValidateBusinessExtImpl` | 商品校验 |
| `ProductPriceValidateAbility` | `CommonProductPriceValidateBusinessExtImpl` | 价格校验 |
| `BuildExtDataAbility` | `CommonBuildExtDataBusinessExtImpl` | 构建扩展数据 |
| `ModifyOrderExtDataAbility` | `CommonModifyOrderExtDataBusinessExtImpl` | 修改订单扩展数据 |

---

### 10.4 查商品流程（`productInfoQuery`）

**调用链**：`OrderBaseDomainService.productInfoQuery` → `BuildProductInfoAbility.buildProductInfo` → `CommonProductInfoQueryBusinessExtImpl.buildProductQuery` → `ProductBiz.queryProductInfo`

**外部 RPC**：`ProductTradeQueryService#queryProductInfo`（商品平台）

**`CommonProductInfoQueryBusinessExtImpl.buildProductQuery` 关键逻辑**：

1. **日期处理**：
   - 钟点房（`HOURLY_ROOM`）或同一天入离：`checkoutTime = checkinTime`
   - 多间夜：`checkoutTime = checkoutTime - 1天`（商品平台要求最后一晚日期）

2. **销售渠道（saleChannel）设置**：
   - 企业差旅 + 分销渠道 → `SaleChannelEnum.DISTRIBUTION`
   - C 端图商供给（`isDistributionSupply4C`）→ `SaleChannelEnum.DISTRIBUTION`
   - B 端分销定价供给（`distributionSupplyMode`）→ `SaleChannelEnum.DISTRIBUTION`

3. **扩展参数（extParam）**：
   - `GuestCount`：成人/儿童数量及年龄
   - `StrategyQueryInfo`：是否查询早餐（钟点房场景）
   - `ExtraQueryParam`：
     - `mtUserId`：用户 ID
     - `superDealSceneType`：超级团购场景
     - `specialChannel`：盲盒（`BLIND_BOX`）/ 图商（`BAI_DU`）
     - `distributorId`：分销商 ID
     - `orderPromoteChannelType`：分销渠道（`DISTRIBUTION`）或主搜（`MAIN_SEARCH`）
     - `requestScene`：API B 端（`APIB_ORDER`）/ 图商（`GRAPHIC_ORDER`）
     - `rightsFreeCancelTimeMill`：会员权益免费取消时间
     - `offlineSourceType`：线下扫码专享价

4. **价格保障参数**：若请求中有 `priceGuaranteeIds`，设置 `needQueryGuaranteeRule=true`

**`ProductBiz.queryProductInfo` 关键逻辑**：
- 构建 `ProductQueryRequest`，包含 `productId`、`skuIds`、`saleChannel`、`start/end`（日期）、`userId`、`saleEndPoint`（APP/MOBILE/PC/APPLETS）
- 调用 `productTradeQueryService.queryProductInfo`
- 失败时抛 `TradeException(OrderResultCodeEnum.EXTERNAL_CALL_ERROR)`

**日志分析**：buy.process.v2 日志中搜索 `productTradeQueryService.queryProductInfo failed` 可定位商品查询失败原因。

---

### 10.5 价格锁定流程（`orderPriceFixing`）

**调用链**：`OrderBaseDomainService.orderPriceFixing` → `OrderPriceFixingAbility.fixPrice` → `CommonOrderPriceFixingBusinessExtImpl`（内部调用营销平台）

**`CommonOrderPriceFixingBusinessExtImpl` 核心逻辑**：

#### 10.5.1 营销校验参数构建（`bizParamForPromotionCheckOnCreateOrder`）

向营销平台传递的关键参数（`PromotionCheckBizParamSDO`）：

- **订单维度**：
  - `commissionRate`：平均佣金率（百分比单位）
  - `commissionPrice`：平均佣金金额
  - `price`：国内传最低售卖价，海外传含税房费均值
  - `partnerId` / `customerId`：供应商 ID
  - `poiMember`：是否门店会员（0/1）
  - `gpsMtCityId`：GPS 城市 ID
  - `longitude` / `latitude`：经纬度
  - `mobile`：注册手机号
  - `optSourceType`：分销场景传 `HOTEL_RETAIL_STORE`
  - `tunLiangStockpiling`：占房/转售场景传库存操作标识

- **购买项维度**（每间夜）：
  - `reservePrice`：结算价（底价）
  - `commissionPrice`：佣金金额
  - `commissionRate`：佣金率
  - `date`：日期（yyyyMMdd）

#### 10.5.2 营销校验失败处理（`needBreakWhenDiscountValidateFailedRequest`）

```java
// 营销风控 code=1007 → 直接抛异常，生单失败
if (PROMOTION_RISK_CODE.equals(proCheckCode)) {
    throw new HotelTradeBizException(PluginOpCodeEnum.PROMOTION_RISK_FAIL);
}
// 底价商促价格为负数 → 抛异常
throw new HotelTradeBizException(PluginOpCodeEnum.FLOOR_PRICE_AMOUNT_ERROR);
// 其他营销失败 → 根据 strategy4PriceChange 决定是否继续下单
// strategy=SUC(允许变价) → 返回 false（继续下单）
// strategy≠SUC → 返回 true（中断下单）
```

#### 10.5.3 改签代订垫付策略（`dianfuStrategy`）

改签场景下计算垫付金额：
- `needPay > couldDianfuAmount`：少补（`SUPPLEMENTAL_PAYMENT`）
- `needPay < couldDianfuAmount`：多退（`REFUNDS_OVERPAID`）
- `needPay == couldDianfuAmount`：平账（`ACCOUNT_BALANCE`）

---

### 10.6 营销锁定流程（`asyncLockPromotion` → `PromotionLockBizV2`）

**文件**：`trade-buy-domain/.../biz/promotion2/PromotionLockBizV2.java`

**外部 RPC**：`OpPromotionService#lockPromotion`（营销平台）

**关键逻辑**：
1. 只锁独占营销（`isPrivatePromotion`），共享营销在父单流程锁
2. 转移营销（改签代订）不需要 lock
3. 锁营销失败 → 抛 `TradeException(OrderResultCodeEnum.PROMOTION_VALIDATE_FAIL, "优惠暂不可用")`

**日志分析**：buy.process.v2 日志中搜索 `lockPreAmountDetail fail` 可定位营销锁定失败。

---

### 10.7 风控校验流程（`asyncRiskValidate` → `CreateOrderRiskDomainServiceImpl`）

**文件**：`trade-buy-domain/.../service/CreateOrderRiskDomainServiceImpl.java`

风控分三层兼容：
1. **新扩展点独立风控**（`OrderRiskValidateAbility.validate`）：餐团等新业务
2. **老扩展点批价风控**（`OrderPriceFixingAbility.createOrderRiskValidate`）：酒店走此路径
3. **老扩展点独立风控**（`OrderRiskValidateAbility.validateStandardOld`）：综合等

**酒店风控参数**（`CommonOrderPriceFixingBusinessExtImpl.bizRiskValidationParamAppend`）：

| 参数 | 说明 |
|---|---|
| `partner` | 风控合作方（国内=YUFU_PARTNER，海外=OVERSEA_PARTNER） |
| `platform` | 平台（美团/点评） |
| `checkInTime` / `checkOutTime` | 入离时间（毫秒时间戳字符串） |
| `fingerprint` | 设备指纹 |
| `app` | 应用标识 |
| `bizOldContext` | 旧版风控上下文（JSON），包含：roomName、goodsId、originalPrice、price、roomerList、supplier、offlineOrder、hotelMember、profitAmount、merReduce 等 |
| `notifyMobile` | 联系人手机号 |
| `mobile` | 注册手机号 |
| `orderType` | 订单类型 |
| `isBizhotelorderid` | 是否企业差旅（0/1） |
| `isWytorder` | 是否无忧取消权益（0/1） |
| `isHoarding` | 是否占房转售订单（0/1） |

---

### 10.8 幂等检查（`requestIdempotentCheck`）

**文件**：`trade-buy-domain/.../biz/idempotent/RequestIdempotentBiz.java`

通过 DB 唯一键插入实现幂等：
- 插入成功（`affectedRows > 0`）→ 继续下单
- 插入失败（`affectedRows == 0`，重复 requestId）→ 抛 `TradeException(OrderResultCodeEnum.IDEMPOTENT_ERROR)`

**酒店分销特殊处理**：幂等失败时，查询上一次下单的订单信息返回给调用方（而非直接报错）。

---

### 10.9 异常处理与 code 转换

`CreateOrderDomainServiceImpl.createOrder` 的 catch 块：

| 异常类型 | `OrderResultCodeEnum` | 说明 |
|---|---|---|
| `TradeValidateException` / `IllegalArgumentException` | `BAD_REQUEST` | 参数校验失败 |
| `TradeException` | 异常中携带的 `resultCode` | 业务异常（商品查询失败、营销失败等） |
| `TradeBizException` | `EXT_EXCEPTION` + `bizResultCode` | 插件包抛出的业务异常（如 `PluginOpCodeEnum`） |
| `Throwable` | `UNKNOWN_ERROR` | 未知异常 |

**`TradeBizException` 与 `PluginOpCodeEnum`**：酒店插件包（`hotel-buy-app`）通过 `HotelTradeBizException` 抛出，携带 `PluginOpCodeEnum` 中定义的 bizResultCode，最终在 aggregate 层转换为对应的 `OpCodeEnum`。

**`OrderResultCodeEnum` 常见值**（buy 服务对外返回）：

| code | 枚举名 | 含义 |
|---|---|---|
| 200 | `SUCCESS` | 成功 |
| 400 | `BAD_REQUEST` | 参数错误 |
| 500 | `UNKNOWN_ERROR` | 未知异常 |
| 2020001 | `EXTERNAL_CALL_ERROR` | 外部调用失败（商品平台/营销平台等） |
| 2020002 | `PROMOTION_VALIDATE_FAIL` | 营销校验/锁定失败 |
| 2020003 | `IDEMPOTENT_ERROR` | 幂等冲突 |
| 2020004 | `ORDER_CREATE_RATE_LIMIT` | 下单限流 |
| 2020005 | `EXT_EXCEPTION` | 插件包业务异常（需看 bizResultCode） |
| 2020611 | `PRODUCT_NOT_FOUND` | 商品不存在（直连场景） |
| 2020612 | `PRODUCT_QUERY_TIMEOUT` | 商品查询超时（直连场景） |

---

### 10.10 日志结合代码分析指南

查询 buy.process.v2 日志时，结合本章节判断根因：

**场景一：buy 日志 code=2020001（EXTERNAL_CALL_ERROR）**
→ 外部服务调用失败
→ 搜索 `productTradeQueryService.queryProductInfo failed` → 商品平台异常
→ 搜索 `PromotionLockBizV2.lockPromotion error` → 营销平台异常
→ 确认是超时还是业务错误

**场景二：buy 日志 code=2020002（PROMOTION_VALIDATE_FAIL）**
→ 营销锁定失败（优惠券已被使用/过期）
→ 搜索 `lockPreAmountDetail fail` 获取 `mpUnifiedResponseCode` 和 `mpUnifiedResponseMsg`
→ 结合营销平台日志确认具体原因

**场景三：buy 日志 code=2020005（EXT_EXCEPTION）+ bizResultCode**
→ 酒店插件包（hotel-buy-app）抛出业务异常
→ 查看 `bizResultCode` 对应 `PluginOpCodeEnum` 含义
→ 常见：`PROMOTION_RISK_FAIL`（营销风控拦截）、`FLOOR_PRICE_AMOUNT_ERROR`（底价商促价格异常）、`ABANDON_ZERO_ORDER_TRANSFER`（0元单禁止改签）

**场景四：buy 日志 code=400（BAD_REQUEST）**
→ 参数校验失败
→ 搜索 `createOrder failed with Exception` 获取具体错误信息
→ 通常是请求参数缺失或格式错误

**场景五：buy 日志 code=2020003（IDEMPOTENT_ERROR）**
→ 重复下单（相同 requestId）
→ 搜索 `RequestIdempotentBiz.requestIdempotentCheck param` 获取 requestId
→ 确认是否为客户端重试导致

**场景六：buy 日志 code=2020004（ORDER_CREATE_RATE_LIMIT）**
→ 下单限流（用户下单过快）
→ 搜索 `您创建订单过快` 关键字
→ 通常是用户短时间内多次点击下单按钮

**场景七：aggregate 日志 code=1030048（RISK_FAIL）→ buy 日志 code=2020005 + bizResultCode=风控相关**
→ 风控拦截
→ 搜索 buy.process.v2 日志中 `bizRiskValidationParamAppend` 相关日志
→ 查看 `bizOldContext` 中的 `price`、`supplier`、`roomerList` 等风控参数
→ 结合风控平台日志确认具体拦截规则

**场景八：aggregate 日志 code=1030092（ZHILIAN_PHOENIX_NO_GOODS_INFO）→ buy 日志 code=2020611/2020612**
→ 直连商品查询失败
→ 搜索 buy.process.v2 日志中 `productTradeQueryService.queryProductInfo failed`
→ 确认是商品不存在（2020611）还是查询超时（2020612）
→ 通常是直连供应商侧问题

---

### 10.11 buy 服务生单完整调用链总结

```
aggregate 层
  └─ DomainBuyDelegateImpl.createOrder
       └─ [Thrift RPC] CreateOrderService#createOrder (buy.process.v2:9001)
            └─ CreateOrderServiceImpl.createOrder
                 └─ CreateOrderDomainServiceImpl.createOrder
                      ├─ [插件] BuildExtDataAbility → CommonBuildExtDataBusinessExtImpl
                      ├─ [插件] BuyerIdTransferAbility → CommonBuyerIdTransferBusinessExtImpl
                      ├─ [插件] BuildProductInfoAbility → CommonProductInfoQueryBusinessExtImpl
                      │    └─ [RPC] ProductTradeQueryService#queryProductInfo (商品平台)
                      ├─ [插件] OtherInfoQueryAbility → CommonCashierOrderInfoQueryBusinessExtImpl
                      ├─ [插件] SaveOrderMappingAbility
                      ├─ [DB] RequestIdempotentBiz.requestIdempotentCheck (幂等表唯一键)
                      ├─ [插件] BuildTradeOrderAbility → CommonBuildTradeOrderBusinessExtImpl
                      ├─ [插件] NotifyPriceCenterAbility (查价格中心)
                      ├─ [插件] OrderParamsValidateAbility → CommonCreateOrderParamsValidateBusinessExtImpl
                      ├─ [插件] ProductValidateAbility → CommonProductValidateBusinessExtImpl
                      ├─ [插件] ProductPriceValidateAbility → CommonProductPriceValidateBusinessExtImpl
                      ├─ [插件] BuyLimitAbility (限购校验)
                      ├─ [插件] OrderPriceFixingAbility → CommonOrderPriceFixingBusinessExtImpl
                      │    └─ [RPC] OpPromotionService (营销平台 checkPromotion)
                      ├─ [异步] PromotionLockBizV2.lockPromotionUnchecked
                      │    └─ [RPC] OpPromotionService#lockPromotion (营销平台 lock)
                      ├─ [异步] CreateOrderRiskDomainService.validate
                      │    └─ [插件] OrderPriceFixingAbility.createOrderRiskValidate (风控)
                      ├─ [RPC] SkuSnapshotSaveService (商品快照)
                      └─ [DB] OrderRepository.createOrderV2 (落库)
```
