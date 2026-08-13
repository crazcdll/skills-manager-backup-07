# 客户端（APP）排查流程

适用场景：**美团 APP / 点评 APP** 移动端（iOS / Android / Harmony）。

> ⚠️ **发布变更记录直接读取第二步变更扫描结果，不再重复查询 Diva。**

## 排查入口选择

根据第二步变更扫描结果和用户标识，决定启动哪些线路：

```
读取第二步变更扫描结果
         ↓
    ┌────┴────┐
  有变更      无变更
    ↓            ↓
线路A + 线路B   线路A（日志查询）
（并行启动）        ↓ 无结论时
                问题与前端代码相关？
                ├─ 是 → 追加线路 C（clone master 分析）
                └─ 否 → 进入汇总分析
```

**无标识时的入口**：
- 有变更 → 直接线路 B
- 无变更 + 问题与代码相关 → 直接线路 C
- 无变更 + 问题与代码无关 → 直接进入汇总分析

**线路A（日志查询）入口选择**：
- 提供了 **userId 或手机号** → A1 查前端异常 → A2 查后端日志
- 提供了 **traceId / 订单号 / dealID / openID / 门店信息** → 跳过 A1，直接 A2 查后端日志
- **以上均未提供** → 跳过线路 A，仅执行线路 B（有变更时）或线路 C（无变更但问题与代码相关时）

> ⚠️ **有变更时，线路 A（日志查询）与线路 B（变更代码分析）必须并行启动，不得等待任意一路完成后再开始另一路。任意一路得出明确结论即可停止等待，直接进入汇总分析。**

---

## 线路 A：日志查询

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
  npm install -g @mtfe/raptorfe-cli@beta --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
  ```
  若安装失败，确认 npm registry 正确后重试，不得跳过 raptorfe 查询。

#### 检查 logcenter-query-cli

参见公共文档：[backend-log-query.md](backend-log-query.md#环境检查logcenter-query-cli)

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

提供 Raptor 前端异常页面链接供用户手动查询：
`aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q/cHJvamVjdElkPXtwcm9qZWN0SWR9JnN0YXJ0RGF0ZT17WVlZWU1NRERISG1tc3N9JmVuZERhdGU9e1lZWVlNTURESEhtbXNzfSZ1bmlvbklkPXtVVUlEfQ==`

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

完整查询步骤（存储类型确认、命令构造、时间格式、错误处理、备用方案）参见公共文档：[backend-log-query.md](backend-log-query.md#后端日志查询步骤)

**A 线结论判断**：
- **前端或后端有明确报错** → 记录错误信息 + traceId，线路 A 得出结论
- **均无报错** → 线路 A 无结论，等待线路 B 结果后进入汇总分析

---

## 代码分析线路（B / C）

本文件只负责 APP 端日志查询。是否执行代码分析由上层决策树决定，具体 Git 操作、完整 diff 范围、风险检查与结论标准统一读取公共文档：

- **线路 B**：前序第二步存在 Diva 变更时，读取 [code-analysis.md](../../references/code-analysis.md#线路-b变更代码分析有-diva-变更时执行)，以 `commitUrl` 的完整 diff 为唯一分析范围。
- **线路 C**：无 Diva 变更、且日志或问题现象指向前端代码时，读取 [code-analysis.md](../../references/code-analysis.md#线路-c默认分支代码分析无变更但问题与代码相关时执行)。

> 不按 DUO、MRN、MAX 等技术栈分支处理，不重新查询 Diva，不修改本地仓库工作区。

---

## 汇总分析（结合两路结果）

> 线路 A 和线路 B 任意一路得出明确结论，即可停止等待另一路，直接进入汇总分析。

| 情况 | 处理方式 |
|------|---------|
| 线路 A 有结论，线路 B 有结论 | 综合分析，判断主因（日志报错 + 变更代码双重印证），进入输出 |
| 线路 A 有结论，线路 B 无结论 | 以日志报错为根因（代码Bug/依赖异常），进入输出 |
| 线路 A 无结论，线路 B 有结论 | 以变更代码为根因，进入输出 |
| 线路 A 无结论，线路 B 无结论 | 无法定位，参考 useful-links.md 推荐辅助工具扩大排查 |
| 无变更，线路 A 无结论，问题与代码相关 | 启动线路 C（默认分支代码分析），以线路 C 结论为根因；线路 C 无结论则参考 useful-links.md |
| 无变更，线路 A 无结论，问题与代码无关 | 无法定位，参考 useful-links.md 推荐辅助工具扩大排查 |
| 线路 C 有结论 | 以默认分支发现的代码逻辑缺陷/配置控制为根因（需结合日志或复现验证），进入输出 |
| 线路 C 无结论 | 无法定位，参考 useful-links.md 推荐辅助工具扩大排查 |
