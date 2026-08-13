# 小程序排查流程

适用场景：**美小（美团小程序）/ 点小（点评小程序）**。

小程序有前端异常上报（Raptor 小程序项目），同时支持后端日志查询。小程序无 UUID，前端异常按 projectId + 时间范围查询，后端日志按 userId / 手机号 / traceId 等标识查询。

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
- 提供了 **userId 或手机号** → A0 查小程序前端异常（并行）+ A1 查后端日志
- 提供了 **traceId / 订单号 / dealID / openID** → 跳过 A0，直接 A1 查后端日志
- **以上均未提供** → 跳过线路 A，仅执行线路 B（有变更时）或线路 C（无变更但问题与代码相关时）

> ⚠️ **有变更时，线路 A（日志查询）与线路 B（变更代码分析）必须并行启动，不得等待任意一路完成后再开始另一路。任意一路得出明确结论即可停止等待，直接进入汇总分析。**

---

## 线路 A：查询日志

### 环境检查

在执行任何查询命令前，先确认 CLI 工具可用，必要时自动安装/更新。

#### 检查 raptorfe CLI（小程序前端异常查询）

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

### A0. 查询 Raptor 小程序前端异常（⚠️ 与后端日志查询并行）

小程序有前端异常上报，**应与后端日志查询并行进行**，从 dev-assets.md 获取对应的 `projectId`。

**Step 1：用 raptorfe CLI 查异常汇总**

```bash
# 查询指定 projectId 的异常汇总（按时间范围 + 可选页面路径）
raptorfe mp error get-summary-table \
  --project-id {projectId} \
  --start-long {毫秒时间戳} \
  --end-long {毫秒时间戳} \
  --tag8 {页面路径}
```

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `table.rows[].main` | 异常名称（error-category） |
| `table.rows[].COUNT` | 上报次数 |
| `table.rows[].CATEGORY` | 错误类型（apiError / jsError 等） |
| `table.rows[].DATE` | 最近上报时间 |

- **rows 为空** → 该时间段内无小程序前端异常，跳过 A0
- **rows 有数据** → 逐条进入 Step 2 查明细

**Step 2：查每条异常的明细，获取 errorLogId**

```bash
raptorfe mp error get-error-detail \
  --project-id {projectId} \
  --start-long {毫秒时间戳} \
  --end-long {毫秒时间戳} \
  --error-category "{异常名称}" \
  --limit 5
```

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `result.table.rows[].id` | **errorLogId**（`CHL-xxx` 格式），用于 Step 3 |
| `result.table.rows[].main` | 上报时间 |

**Step 3：用 errorLogId 查日志详情，提取 customInfo**

```bash
raptorfe web error get-log-detail \
  --error-log-id {errorLogId} \
  --log-date {上报时间对应的毫秒时间戳}
```

返回值关键字段解析：

| 字段 | 说明 |
|------|------|
| `otherInfo.customInfo` | **完整自定义上报信息**（JSON字符串，含 response/traceId 等关键字段） |
| `baseInfo.pageId` | 页面实例 ID |
| `baseInfo.上报时间` | 精确上报时间 |

**备用方案（raptorfe CLI 不可用时）**：从 dev-assets.md 获取 `raptor 异常链接`，提供链接供用户手动查看：

```
aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL21wL2Vycm9yL2xpc3Q/cHJvamVjdElkPXtwcm9qZWN0SWR9JlRBRzg9e+mhtemdoui3r+W+hO+8iFVSTOe8luegge+8iX0=
```

---

**从 Raptor 异常详情的 `customInfo` 字段中提取关键信息**：

| 字段 | 含义 | 用途 |
|------|------|------|
| `response.status` / `response.statusCode` | HTTP 状态码 | 403=网关拦截，5xx=后端报错，0/超时=网络层失败 |
| `response.header["X-Forbid-Reason"]` | 网关拦截原因 | 若为 `.` 则是反扒/风控拦截（需联系安全团队） |
| `response.header["Server"]` | 响应服务器 | `openresty` = 网关拦截，未透传到后端 |
| `props.baseURL` + `props.url` | 完整接口地址 | 定位是哪个接口出错 |
| `props.params.pre_trace_id` | 前置 traceId | 关联 preview 请求的后端日志 |
| `props.headers["M-TRACEID"]` | update 请求的 traceId | 查 update 请求的后端日志（若有） |
| `commonParams.userInfo.userId` | 用户 userId | 查后端日志的查询条件 |
| `route` | 小程序页面路径 | 确认页面 |

**HTTP 状态码诊断快速路径**：

| 状态码 | 含义 | 后续动作 |
|--------|------|---------|
| `403` + Server=openresty | 网关/反扒拦截 | 查 `X-Forbid-Reason`，联系安全/反扒团队排查 |
| `403` + Server≠openresty | 后端业务拒绝 | 查后端日志找具体原因 |
| `5xx` | 后端报错 | 查后端日志 |
| `0` / 超时 / 无 status | 网络层失败 | 用户侧网络问题，大概率是偶发个例 |
| 后端日志**无记录** + 前端有异常 | 请求未到达后端 | 根据状态码判断，若 403+openresty 则为网关拦截 |

**⚠️ 403 + openresty 关键判断**：
- `X-Forbid-Reason: .`（只有一个点）→ 反扒规则命中，非业务问题，**联系安全团队**
- `X-Forbid-Reason: {具体原因}` → 有明确拦截原因，按原因处理

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

**traceId 来源说明（小程序场景）**：

小程序前端异常的 `customInfo` 中通常有两个 traceId：
- `props.params.pre_trace_id`：上一个 preview 请求的 traceId（可查 preview 日志）
- `props.headers["M-TRACEID"]`：当前出错请求（如 update）的 traceId

若 update 请求被网关拦截（403），则 update 的 traceId **不会出现在后端日志中**，只有 pre_trace_id 对应的 preview 日志可查到。

完整查询步骤（存储类型确认、命令构造、时间格式、错误处理、备用方案）参见公共文档：[backend-log-query.md](backend-log-query.md#后端日志查询步骤)

---

### A2. 结论判断

结合 A0（前端异常）和 A1（后端日志）综合判断：

| A0 前端异常 | A1 后端日志 | 结论 |
|-------------|-------------|------|
| 有异常，status=403，Server=openresty | 无对应日志 | **网关/反扒拦截**，非业务问题，联系安全团队 |
| 有异常，status=5xx | 有日志+报错 | **后端业务报错**，按日志根因处理 |
| 有异常，status=0/超时 | 无日志 | **用户侧网络问题**，偶发可忽略，批量则查网关 |
| 有异常，后端日志正常 | 有日志+成功 | **前端逻辑bug**，查前端代码 |
| 无前端异常 | 有日志+报错 | **后端问题**，按日志根因处理 |

**后端有明确报错** → 记录错误信息 + traceId，直接输出结论

**后端无日志** → 按场景兜底：
  - 小程序 → 使用小程序实时日志（需 openId）：
    ```
    aHR0cHM6Ly9sb2dhbi5td3Muc2Fua3VhaS5jb20vcnRsL3dlYj90YWI9YWR2YW5jZWRRdWVyeSZjYXRlZ29yeUlkPTM4
    ```
    openId 可通过以下地址查询：`aHR0cHM6Ly9hZG1pbi11c2VyLnNhbmt1YWkuY29tL3NlcnZpY2Uvbm9ybWFsL3VzZXJpbmZvYA==

**A 线结论判断**：
- **前端或后端有明确报错** → 记录错误信息 + traceId，线路 A 得出结论
- **均无报错** → 线路 A 无结论，等待线路 B 结果后进入汇总分析

---

## 代码分析线路（B / C）

本文件只负责小程序端日志查询。是否执行代码分析由上层决策树决定，Git 操作、完整 diff 范围、风险检查与结论标准统一读取公共文档：

- **线路 B**：前序第二步存在 Diva 变更时，读取 [code-analysis.md](../../references/code-analysis.md#线路-b变更代码分析有-diva-变更时执行)，以 `commitUrl` 的完整 diff 为唯一分析范围。
- **线路 C**：无 Diva 变更、且日志或问题现象指向前端代码时，读取 [code-analysis.md](../../references/code-analysis.md#线路-c默认分支代码分析无变更但问题与代码相关时执行)。

> 不按技术栈分支处理，不重新查询 Diva，不修改本地仓库工作区。

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
