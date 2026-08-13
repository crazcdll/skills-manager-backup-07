# 后端日志查询公共指南

本文档为 APP / H5 / 小程序排查流程的公共参考，包含 `logcenter-query-cli` 的调用方式和查询命令。

---

## 环境检查：logcenter-query-cli

`logcenter-query-cli` 是查询后端日志的 CLI 工具，速度比页面快 10x+。

> ℹ️ 本工具已作为 Agent Skill 关联，无需手动安装。以下命令中的 `lc-query` 均指路径 `logcenter-query-cli/scripts/lc-query`。
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

## 鉴权机制与重试策略

> ⚠️ **首次查询某日志主题时，建议加 `--verbose` 标志**，可观察鉴权过程，便于快速定位失败原因。

`lc-query` 查询前需完成**两步鉴权链**，任何一步失败都会导致查询无法执行：

| 步骤 | 操作 | 说明 |
|------|------|------|
| **Step 1** | SSO 本地换票（MOA → mtsso） | 通过 MIS 账号本地换取 SSO 票据，可能因网络抖动或缓存未就绪而瞬态失败 |
| **Step 2** | 用 SSO 票据换取日志主题 Token | 调 Raptor API 获取该日志主题的专用 access token |

### 鉴权失败处理（必须重试）

当遇到 `TOKEN_FAIL_NO_PERMISSION` 报错时，**并非一定是权限问题**，很可能是 SSO 换票环节瞬态失败。按以下流程处理：

```
lc-query query 报 TOKEN_FAIL_NO_PERMISSION？
  ├─ 第一次失败 → 加 --verbose 重试（观察鉴权日志）
  │    ├─ verbose 日志显示「MOA 换票成功 → Token 获取成功」→ 查询成功，继续排查
  │    └─ verbose 日志显示「MOA 换票失败」→ 再重试一次（共 2 次重试）
  │         ├─ 仍失败 → 确认是否首次访问该 topic（可能无权限）
  │         │    ├─ 是首次 → 联系日志负责人添加权限
  │         │    └─ 非首次 → 提 TT 工单排查 SSO/MOA 环境
  │         └─ 重试成功 → 继续排查
  └─ 重试成功 → 继续排查
```

> 💡 **经验**：实际排查中，第一次查询报 `TOKEN_FAIL_NO_PERMISSION`，加 `--verbose` 重试后即成功的场景非常常见。SSO 换票瞬态失败是常态而非例外，**遇到此报错务必先重试再判断权限问题**。

---

## Step 1：确认存储类型

首次查陌生 topic 时执行，影响后续命令选择：

```bash
lc-query meta -l {logTopic}
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
lc-query query \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  -q '{构造的查询条件}' --size 50 --json 2
```

**具体示例**：

```bash
# 有 traceId 时（正数）
lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '464458784842137394' --size 50 --json 2

# ⚠️ traceId 为负数时，Eagle 存储：在 -q 中用反斜杠转义负号
lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '\-3437264558516151002' --size 50 --json 2

# userId 查询
lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '123456789' --size 50 --json 2

# 手机号查询
lc-query query \
  -l com.sankuai.grouptrade.precreate.apic \
  -s "2026-04-05 16:11:00" -e "2026-04-05 22:11:00" \
  -q '13800138000' --size 50 --json 2
```

### InfluxDB 存储（SQL 语法）

```bash
lc-query query-influx \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  --sql "SELECT * FROM log WHERE uuid='{UUID}' LIMIT 50"

# ⚠️ InfluxDB 中负数 traceId 必须用 --sql，-q 会报错
lc-query query-influx \
  -l {logTopic} -s "{开始时间}" -e "{结束时间}" \
  --sql "SELECT * FROM log WHERE traceId='-1438874095498651105' LIMIT 20"
```

**字段名不确定时**，先查字段列表：

```bash
lc-query fields -l {logTopic}
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
| `TOKEN_FAIL_NO_AUTH` | 未登录，访问 `raptor.mws.sankuai.com` 完成登录后重试 |
| `TOKEN_FAIL_NO_PERMISSION` | **先加 `--verbose` 重试**（SSO 换票瞬态失败很常见）；重试 2 次仍失败，确认是否首次访问该 topic，是→联系日志负责人加权限，否→提 TT 工单排查 SSO/MOA 环境。详见上方「鉴权机制与重试策略」 |
| 查询无结果 | 检查：时间范围是否太小？topic 名称是否拼错？字段名是否存在（用 `fields` 确认）？ |

---
