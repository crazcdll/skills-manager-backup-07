# 后端日志查询公共指南

本文档为 APP / H5 / 小程序排查流程的公共参考，包含 `logcenter-query-cli` 的安装、调用方式和查询命令。

---

## 环境检查：logcenter-query-cli

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

## 多 topic 查询策略

页面可能对应多个后端 topic（如团购提单同时有 precreate 和 query 两条链路），按以下优先级查询：

| 用户操作 | 优先查的 topic | 说明 |
|---------|--------------|------|
| 提单/下单失败 | `precreate.apic` / `create.flowservice` | 填单和创建订单链路 |
| 订单详情/支付结果异常 | `foodtrade.groupbuy.apic` | 购后查询链路 |
| 退款失败 | `web.refund.applyproxy` | 退款申请链路 |
| 有 traceId | 所有相关 topic 都查 | traceId 可跨 topic 追踪 |

---

## Step 1：确认存储类型

首次查陌生 topic 时执行，影响后续命令选择：

```bash
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query meta -l {logTopic}
```

- 输出 `storageType: eagle` → 使用 `query` 命令（Lucene 语法）
- 输出 `storageType: influxdb` → 使用 `query-influx` 命令（SQL 语法）
- 餐交易后端日志绝大多数为 Eagle，**熟悉的 topic 可跳过此步直接查询，报错再回来确认**

---

## Step 2：执行查询

### -q 参数构造优先级（按顺序尝试，直到有结果）

1. **traceId**（最优先）：`{traceId值}`
2. **UUID**（APP 场景，从前端日志获取）：`{UUID值}`
3. **userId**：`{userId值}`
4. **手机号**：`{手机号}`
5. **订单号**：`{订单号}`
6. **dealID**：`{dealId值}`
7. **openID**：`{openId值}`
8. **门店id**：`{门店id}`

> H5 / 小程序场景无 UUID，从第 3 项 userId 开始尝试。

### Eagle 存储（Lucene 语法）

```bash
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

# ⚠️ traceId 为负数时，Eagle 存储：在 -q 中用反斜杠转义负号
~/.openclaw/skills/.claude/skills/logcenter-query-cli/scripts/lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '\-3437264558516151002' --size 50 --json 2

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

### InfluxDB 存储（SQL 语法）

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

---

## 时间参数格式说明

> ⚠️ 时间必须用**空格**分隔日期和时分秒，并加**双引号**，不支持 `T` 分隔的 ISO 格式。

- `-s` / `-e` 支持相对时间（如 `3h`、`24h`、`30m`）或绝对时间（`"YYYY-MM-DD HH:MM:SS"`）
- 提供了具体时间（如 4月5号19点11分）→ 查询前后3小时：`-s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00"`
- 仅提供日期 → 查当天全天：`-s "2026-04-05 00:00:00" -e "2026-04-05 23:59:59"`
- 未提供时间 → 查最近 24 小时：`-s 24h`

时间戳转换命令（用于 raptorfe CLI 的毫秒时间戳参数）：

```bash
# macOS
date -j -f "%Y-%m-%d %H:%M:%S" "2026-04-07 15:30:00" +%s000
# Linux
date -d "2026-04-07 15:30:00" +%s%3N
```

---

## 错误处理

| 错误 | 处理方式 |
|------|---------|
| `TOKEN_FAIL_NO_AUTH` | 在 CatDesk 浏览器中访问 aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29t 完成登录后重试 |
| `TOKEN_FAIL_NO_PERMISSION` | 该日志无访问权限，联系日志负责人添加权限后重试 |
| 查询无结果 | 检查：时间范围是否太小？topic 名称是否拼错？字段名是否存在（用 `fields` 确认）？ |

---

## 备用方案（logcenter-query-cli 未安装时）

使用 browser_action 打开 Raptor LogCenter，按 -q 参数优先级构造查询条件：

```
aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2xvZy90b3BpYy92aWV3L3tsb2dUb3BpY30/c2VhcmNoVHlwZT1leHBlcnQmc2VhcmNoR3JhbW1hcj1kc2wmY29uZGl0aW9uPSJ75p+l6K+i5p2h5Lu2fSImdGltZVR5cGU9Q3VzdG9tJnN0YXJ0RGF0ZT17WVlZWU1NRERISG1tc3N9JmVuZERhdGU9e1lZWVlNTURESEhtbXNzfSZpU0xpbWl0PTEwMCZwYWdlTnVtPTEmcGFnZVNpemU9NTA=
```

**参数说明**：

- `logTopic`：从 dev-assets.md 获取
- `查询条件`（按优先级，**双引号包裹**）：
  - 有 traceId：`"2152148484505599702"`
  - 有 UUID：`"000000000000086A17A10FEEA46E98E28F26CBC7034FCA176372508976231228"`（APP 场景）
  - 有用户ID：`"1858800635"`
  - 有手机号：`"18614062344"`
  - 有订单号：`"5026031804325578023"`
  - 有 dealID：`"1024058160584559"`
  - 有 openID：`"oJVP50Eb99tT6NsaSI9iFsFEtmCY"`
  - 有门店id：`"1023637477173558"`
- `startDate` / `endDate`：提供了具体时间（含分钟）则查前后3小时；仅提供日期则查当天全天；未提供时间则查最近 24 小时
