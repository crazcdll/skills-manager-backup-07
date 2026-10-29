# 客户端（APP）排查流程

适用场景：**美团 APP / 点评 APP** 移动端（iOS / Android / Harmony）。

根据用户提供的信息，选择对应入口：
- 提供了 **userId 或手机号** → 走线路 A：A1 查前端日志 → A2 查后端日志
- 提供了 **traceId / 订单号 / dealID / openID/ 门店信息** → 跳过 A1，直接从 A2 查后端日志
- **以上均未提供** → 跳过线路 A，直接执行线路 B 查发布记录

---

## 线路 A：查询日志

### 环境检查

在执行任何查询命令前，先确认 CLI 工具可用，必要时自动安装/更新。

#### 检查 raptorfe CLI

```bash
# 能输出版本号即为可用
raptorfe --version 2>/dev/null && echo "ok" || echo "missing"
```

- **输出 ok** → 直接进入查询步骤，同时在后台静默更新
- **输出 missing** → 立即安装，等待完成后再查询：
  ```bash
  npm install -g @mtfe/raptorfe-cli@beta --registry http://r.npm.sankuai.com
  ```
  若安装失败，回退到备用方案（browser_action）。

#### 检查 logcenter-query-cli

`logcenter-query-cli` 是查询后端日志的 CLI 工具，速度比页面快 10x+。

**安装/更新工具**

```bash
mtskills pull logcenter-query-cli && echo "ok" || echo "missing"
```

- **输出 ok** → 直接进入查询步骤
- **输出 missing** → 先安装：
  ```bash
  mkdir -p ~/.openclaw/skills && cd ~/.openclaw/skills && mtskills i logcenter-query-cli
  ```
  若安装失败，回退到备用方案（browser_action）。

**调用方式**

> `lc-query` 不在 PATH 中，必须使用**绝对路径**调用：
>
> ```
> ~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query
> ```
>
> 以下文档中所有 `lc-query` 命令均指此绝对路径，执行时请替换。

验证可用：

```bash
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query --version
```

---

### A1. 查询前端异常

**Step 1：获取 UUID**

用户提供的是 userId 或手机号时，先参照 [get-uuid.md](get-uuid.md) 获取对应的 UUID。

**Step 2：确定查询参数**

- `--project-id`：从 dev-assets.md 获取对应页面的 `projectId`
- `--start-long` / `--end-long`：**毫秒级时间戳（13位）**，按以下规则确定范围：
  - 提供了具体时间（如 4月5号19点11分）→ 查询前后3小时，即 `[16:11, 22:11]`
  - 仅提供日期（如 4月5号）→ 查询当天全天 `[00:00, 23:59]`
  - 未提供时间 → 查最近 24 小时
  - 时间戳转换命令：
    ```bash
    # macOS
    date -j -f "%Y-%m-%d %H:%M:%S" "2026-04-07 15:30:00" +%s000
    # Linux
    date -d "2026-04-07 15:30:00" +%s%3N
    ```
- `--union-id`：Step 1 获取的完整 UUID（大写十六进制字符串）

**Step 3：进入 A1.1 查询异常汇总**

---

#### A1.1. 查询该用户的异常汇总（异常名称、数量）

```bash
raptorfe web error get-summary-table \
  --project-id {projectId} \
  --start-long {毫秒时间戳} \
  --end-long {毫秒时间戳} \
  --union-id {UUID}
```

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `table.rows[].main` | 异常名称（即 error-category） |
| `table.rows[].COUNT` | 该异常上报次数 |
| `table.rows[].USER_COUNT` | 影响用户数 |
| `table.rows[].CATEGORY` | 错误类型（jsError / apiError 等） |
| `table.rows[].LEVEL` | 错误级别（error / warn） |
| `table.rows[].DATE` | 最近上报时间 |
| `newErrors` | 新增异常列表（48小时内首次出现） |

- **rows 为空** → 该用户在此时间段内无前端异常，线路 A 前端侧无结论
- **rows 有数据** → 记录所有异常名称，逐条进入 A1.2 查明细

---

#### A1.2. 查询每条异常的明细，获取 errorLogId

```bash
raptorfe web error get-error-detail \
  --project-id {projectId} \
  --start-long {毫秒时间戳} \
  --end-long {毫秒时间戳} \
  --error-category "{异常名称}" \
  --union-id {UUID} \
  --limit 5
```

> `--error-category` 值取 A1.1 返回的 `rows[].main` 字段，若含空格需加引号。

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `result.table.rows[].id` | **errorLogId**（格式：`CHL-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`），用于 A1.3 |
| `result.table.rows[].main` | 上报时间 |
| `result.table.rows[].data4` | 用户 unionId（可用于核对） |
| `result.table.rows[].data5` | 容器类型（MRN / DUO / MAX / H5） |
| `result.table.rows[].data6` | 操作系统（iOS / Android） |

记录所有 `id`（errorLogId）和对应上报时间，进入 A1.3 查日志详情。

---

#### A1.3. 用 errorLogId 查询日志详情

```bash
raptorfe web error get-log-detail \
  --error-log-id {errorLogId} \
  --log-date {上报时间对应的毫秒时间戳}
```

> `--log-date` 填 A1.2 中该条记录的上报时间对应毫秒时间戳（精确到分钟即可）。

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `baseInfo.上报时间` | 精确上报时间 |
| `baseInfo.pageId` | 页面实例 ID，可用于关联后端日志 |
| `baseInfo.unionId` | 用户 UUID |
| `baseInfo.User Agent` | 客户端信息（App版本、系统版本、机型） |
| `otherInfo.tag4` | bundleVersion（bundle 版本号） |
| `otherInfo.tag5` | appVersion（App 版本号） |
| `otherInfo.tag6` | bundle 名称（如 `rn_hotel_rn-hotel-poidetail_hotel-poidetail`） |
| `otherInfo.tag7` | 客户端标识（meituan / dianping） |
| `otherInfo.customInfo` | **自定义上报信息**（JSON字符串，含 traceId、错误码、错误信息等关键字段） |
| `stackInfo` | JS 堆栈（通常为空，需结合 customInfo 分析） |
| `locationInfo` | 用户地理位置、运营商、网络类型 |

**customInfo 解析重点**（JSON.parse 后分析）：

| 字段 | 说明 |
|------|------|
| `traceId` | 后端链路追踪 ID，用于 A2 查后端日志 |
| `code` / `error.code` | 后端错误码 |
| `error.message` | 后端错误信息 |
| `bizRes.error` | 业务层错误详情 |

**初步分析结论**：根据 customInfo 中的错误码和错误信息，判断是前端逻辑问题还是后端接口返回错误。若为后端接口拦截，提取 traceId 供 A2 使用，继续深入排查。

**备用方案（raptorfe-cli 安装失败时）**：

使用 browser_action 打开 Raptor 前端异常页面，按 projectId + 时间 + UUID 筛选：
```
https://raptor.mws.sankuai.com/frontend/error/list?projectId={projectId}&startDate={YYYYMMDDHHmmss}&endDate={YYYYMMDDHHmmss}&unionId={UUID}
```

---

### A2. 查询后端日志

**多 topic 查询策略**：

页面可能对应多个后端 topic（如团购提单同时有 precreate 和 query 两条链路），按以下优先级查询：

| 用户操作 | 优先查的 topic | 说明 |
|---------|--------------|------|
| 提单/下单失败 | `precreate.apic` / `create.flowservice` | 填单和创建订单链路 |
| 订单详情/支付结果异常 | `foodtrade.groupbuy.apic` | 购后查询链路 |
| 退款失败 | `web.refund.applyproxy` | 退款申请链路 |
| 有 traceId | 所有相关 topic 都查 | traceId 可跨 topic 追踪 |

**Step 1：确认存储类型**（首次查陌生 topic 时执行，影响后续命令选择）

```bash
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query meta -l {logTopic}
```

- 输出 `storageType: eagle` → 使用 `query` 命令（Lucene 语法）
- 输出 `storageType: influxdb` → 使用 `query-influx` 命令（SQL 语法）
- 到餐交易后端日志绝大多数为 Eagle，**熟悉的 topic 可跳过此步直接查询，报错再回来确认**

**Step 2：执行查询**

Eagle 存储（Lucene 语法）：

**-q 参数构造优先级**（按顺序尝试，直到有结果）：

1. **traceId**（最优先）：`{traceId值}`
2. **UUID**（从前端日志获取）：`{UUID值}`
3. **用户ID**：`{userId值}`
4. **手机号**：`{手机号}`
5. **订单号**：`{订单号}`
6. **dealID**：`{dealId值}`
7. **openID**：`{openId值}`
8. **门店id**：`{门店id}`

**查询命令**：

```bash
# 查询（用绝对路径，下同）
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  -q '{构造的查询条件}' --size 50 --json 2
```

**具体示例**：
```bash
# 有 traceId 时（正数）
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '464458784842137394' --size 50 --json 2

# ⚠️ traceId 为负数时，Eagle 存储：缩小时间窗口 + 用门店ID/userId 作为 -q，在结果里找对应 traceId
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 19:47:00" -e "2026-04-05 19:48:00" \
  -q '1023637477173558' --size 50 --json 2

# userId 查询
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '123456789' --size 50 --json 2

# 手机号查询
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '13800138000' --size 50 --json 2
```

InfluxDB 存储（SQL 语法）：

```bash
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query-influx \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  --sql "SELECT * FROM log WHERE uuid='{UUID}' LIMIT 50"

# ⚠️ InfluxDB 中负数 traceId 必须用 --sql，-q 会报错
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query-influx \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  --sql "SELECT * FROM log WHERE traceId='-1438874095498651105' LIMIT 20"
```

**字段名不确定时**，先查字段列表：

```bash
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query fields -l {logTopic}
```

**时间参数格式说明**：

> ⚠️ 时间必须用**空格**分隔日期和时分秒，并加**双引号**，不支持 `T` 分隔的 ISO 格式。

- `-s` / `-e` 支持相对时间（如 `3h`、`24h`、`30m`）或绝对时间（`"YYYY-MM-DD HH:MM:SS"`）
- 提供了具体时间（如 4月5号19点11分）→ 查询前后3小时：`-s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00"`
- 仅提供日期 → 查当天全天：`-s "2026-04-05 00:00:00" -e "2026-04-05 23:59:59"`
- 未提供时间 → 查最近 24 小时：`-s 24h`

**错误处理**：

| 错误 | 处理方式 |
|------|---------|
| `TOKEN_FAIL_NO_AUTH` | 在 CatDesk 浏览器中访问 https://raptor.mws.sankuai.com 完成登录后重试 |
| `TOKEN_FAIL_NO_PERMISSION` | 该日志无访问权限，联系日志负责人添加权限后重试 |
| 查询无结果 | 检查：时间范围是否太小？topic 名称是否拼错？字段名是否存在（用 `fields` 确认）？ |

**备用方案（logcenter-query-cli 未安装时）**：

使用 browser_action 打开 Raptor LogCenter，按 -q 参数优先级构造查询条件：
```
https://raptor.mws.sankuai.com/log/topic/view/{logTopic}?searchType=expert&searchGrammar=dsl&condition="{查询条件}"&timeType=Custom&startDate={YYYYMMDDHHmmss}&endDate={YYYYMMDDHHmmss}&iSLimit=100&pageNum=1&pageSize=50
```

**参数说明**：

- `logTopic`：从 dev-assets.md 获取
- `查询条件`（按优先级，**双引号包裹**）：
  - 有 traceId：`"2152148484505599702"`
  - 有 UUID：`"000000000000086A17A10FEEA46E98E28F26CBC7034FCA176372508976231228"`
  - 有用户ID：`"1858800635"`
  - 有手机号：`"18614062344"`
  - 有订单号：`"5026031804325578023"`
  - 有 dealID：`"1024058160584559"`
  - 有 openID：`"oJVP50Eb99tT6NsaSI9iFsFEtmCY"`
  - 有门店id：`"1023637477173558"`

- `startDate` / `endDate`：提供了具体时间（含分钟）则查前后3小时；仅提供日期则查当天全天；未提供时间则查最近 24 小时

**A 线结论判断**：
- **前端或后端有明确报错** → 记录错误信息 + traceId，**线路 A 得出结论，可停止线路 B**
- **均无报错** → 线路 A 无结论，继续执行线路 B

---

## 线路 B：查发布记录

### B1. 查 Diva 发布记录

根据bundle名，使用 [diva-bundle-version-query.md](diva-bundle-version-query.md) 接口查询该 bundle 的发布记录。

兜底方案：
使用 browser_action 打开 Diva，查看最近 5 天发布记录：
```
https://diva.sankuai.com/bundle/{bundle名}/versions?env=prod
```

- **最近 5 天无发布** → 线路 B 无结论，等待线路 A 结果
- **有发布** → 按以下规则确定问题版本：
  - 取**问题发生时间之前、最近一次**上线的版本作为问题版本
  - 若问题时间恰好在两个版本之间，取较早那个（即问题发生时已生效的版本）
  - 获取该版本的 commit hash 和上一版本的 commit hash，进入 B2

### B2. 分析代码变更

根据页面技术栈选择对应分析方式：

#### DUO 页面：分析 componentsMap.json

1. clone 或更新仓库（SSH 地址从 dev-assets.md 的 `gitSSH` 字段获取）：
   ```bash
   cd /Users/All_deal_project
   git clone {仓库SSH地址}   # 已存在则：cd {仓库目录} && git pull origin master
   ```

2. 对比 componentsMap.json 变更：
   ```bash
   git log --oneline -20
   git diff {上一版本commitHash}..{问题版本commitHash} -- componentsMap.json
   ```

3. 识别变更组件（重点关注 `npmVersion` 字段）：
   ```json
   "组件名": { "name": "@meishi/组件包名", "npmVersion": "x.x.x" }
   ```

4. 在 Yooz 查看组件详情，获取组件仓库 SSH 地址：
   ```
   https://yooz.sankuai.com/client-platform/material/component?keyword={组件名}
   ```

5. clone 组件仓库，分析具体代码变更：
   ```bash
   cd /Users/All_deal_project
   git clone {组件仓库SSH地址}
   git log --oneline -10
   git diff {旧版本tag}..{新版本tag}
   ```
   重点关注样式文件（.less/.css）、布局组件、文案相关改动。

#### MRN / MAX 页面：直接分析代码变更

1. clone 或更新仓库：
   ```bash
   cd /Users/All_deal_project
   git clone {仓库SSH地址}   # 已存在则：cd {仓库目录} && git pull origin master
   ```

2. 找到问题版本对应 commit，分析全量代码变更：
   ```bash
   git log --oneline -20
   git diff {上一版本commitHash}..{问题版本commitHash}
   ```

3. 重点关注业务逻辑、接口调用、样式相关改动，识别可疑变更。

**B 线结论判断**：
- **找到与问题强相关的变更** → 记录变更内容，**线路 B 得出结论，可停止线路 A**
- **未找到相关变更** → 线路 B 无结论，等待线路 A 结果
