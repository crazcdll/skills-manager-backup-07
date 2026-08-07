# 小程序 & H5 排查流程

适用场景：**美小（美团小程序）/ 点小（点评小程序）/ DUO 转 H5 / MAX 转 H5 / i 版 H5**。

小程序和 H5 均没有 UUID，**只查后端日志**，无需走 Diva 发布记录线路。

根据用户提供的信息，选择对应入口：
- 提供了 **userId 或手机号** → 直接进入 A1 查后端日志
- 提供了 **traceId / 订单号 / dealID / openID** → 直接进入 A1，以对应字段查询
- **以上均未提供** → 无法查日志，提示用户补充 userId 或手机号

---

## 线路 A：查后端日志（唯一排查线路）

### 环境检查

在执行任何查询命令前，先确认 CLI 工具可用，必要时自动安装/更新。

#### 检查 logcenter-query-cli

`logcenter-query-cli` 是查询后端日志的 CLI 工具，速度比页面快 10x+。

**安装/更新工具**

```bash
mkdir -p ~/.openclaw/skills && cd ~/.openclaw/skills && mtskills pull logcenter-query-cli && echo "ok" || echo "missing"
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

### A1. 查询后端日志

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

**-q 参数构造优先级**（按顺序尝试，直到有结果）：

1. **traceId**（最优先）：`{traceId值}`
2. **userId**（从 userId / 手机号转换）：`{userId值}`
3. **手机号**：`{手机号}`
4. **订单号**：`{订单号}`
5. **dealID**：`{dealId值}`
6. **openID**：`{openId值}`
7. **门店id**：`{门店id}`

Eagle 存储（Lucene 语法）：

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
  --sql "SELECT * FROM log WHERE userId='{userId}' LIMIT 50"

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

---

### A2. 结论判断

- **后端有明确报错** → 记录错误信息 + traceId，直接输出结论
- **后端无日志** → 按场景兜底：
  - 小程序 → 使用小程序实时日志（需 openId）：
    ```
    https://logan.mws.sankuai.com/rtl/web?tab=advancedQuery&categoryId=38
    ```
    openId 可通过以下地址查询：`https://admin-user.sankuai.com/service/normal/userinfo`
- **userId 和手机号均未提供** → 无法查日志，提示用户补充
