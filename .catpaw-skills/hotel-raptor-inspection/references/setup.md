# 环境配置指南

## Cookie 获取方法

脚本通过 Raptor Web API 直接拉取数据，需要有效的登录 Cookie。

### 步骤

1. 用浏览器打开 [Raptor 异常分析页](https://raptor.mws.sankuai.com/frontend/error/detail)，确保已登录
2. 打开开发者工具（F12）→ Network 标签
3. 刷新页面，找到任意 XHR/Fetch 请求（如 `summaryTable`）
4. 复制请求头中的 `Cookie` 字段完整值
5. 将 Cookie 写入脚本同目录的 `.raptor_cookie` 文件：

```bash
echo "your_cookie_here" > /path/to/workspace/.raptor_cookie
```

或设置环境变量（适合 CI/定时任务）：

```bash
export RAPTOR_COOKIE="your_cookie_here"
```

### Cookie 优先级

1. `.raptor_cookie` 文件（推荐，持久化）
2. `RAPTOR_COOKIE` 环境变量

### Cookie 有效期

Cookie 通常有效期为数天到数周。若报错 `HTTP Error 302` 或 `未找到 Raptor cookie`，需重新获取。

---

## 关键配置参数（脚本顶部）

### 首现异常

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `NEW_ERROR_MIN_COUNT` | `1` | 首现异常最低次数（过滤极低频噪音） |

### 持续异常（动态阈值）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PERSISTENT_ABS_MIN` | `10` | 绝对下限（次），小项目兜底 |
| `PERSISTENT_RATIO` | `0.005` | 总量比例（0.5%），大项目按比例 |
| `PERSISTENT_TOP_N` | `10` | 最多展示条数 |

实际阈值 = `max(PERSISTENT_ABS_MIN, 当前窗口总量 × PERSISTENT_RATIO)`

### 环比暴涨异常（动态阈值）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SURGE_PCT_THRESHOLD` | `100` | 环比增幅阈值（%） |
| `SURGE_ABS_MIN` | `5` | 绝对下限（次） |
| `SURGE_RATIO` | `0.001` | 总量比例（0.1%） |
| `SURGE_TOP_N` | `10` | 最多展示条数 |

实际阈值 = `max(SURGE_ABS_MIN, 当前窗口总量 × SURGE_RATIO)`

### 其他

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CRITICAL_KEYWORDS` | `submit, pay, 支付, 下单...` | 交易链路关键词，命中则在列表中标记 |
| `STACK_TOP_N` | `5` | ERROR 级别堆栈分析条数上限 |

---

## 数据模式说明

### 模式 A：Raptor Web API（推荐）

需要有效 Cookie，功能完整：

- ✅ 官方 TAG 过滤（自动跳过「完全忽略」「暂时忽略」的异常）
- ✅ 近一周首现（Raptor 官方 `newErrors[]`，与上周同期对比）
- ✅ 动态 projectId 查询（只需传项目名）
- ✅ 异常详情跳转链接（含时间窗口 + keyword + errorName）

### 模式 B：MCP 降级

Cookie 不可用时自动降级，功能受限：

- ❌ 无 TAG 过滤（「忽略」类异常会混入）
- ⚠️ 首现为对比窗口推断（非官方上周同期）
- ✅ 可获取 ERROR 级别堆栈详情（通过 MCP 工具）

---

## 时间窗口逻辑

```
对比窗口  ←24h→  [report_time - 48h  ~  report_time - 24h]
当前窗口  ←24h→  [report_time - 24h  ~  report_time      ]
```

- **环比**：当前窗口 vs 对比窗口（等长 24h 对齐）
- **首现**：由 Raptor `summaryTable` 接口的 `newErrors[]` 字段提供，含义为「较上周同期首现」

---

## 已知限制

- **堆栈内容**：`/cat/fe/log/list` 接口目前返回 404，ERROR 级别分析仅基于异常名称规则推断，无真实堆栈。
- **MCP 降级**：MCP 工具需要 SSE 长连接，初始化有 5~10s 延迟，且无官方 TAG 数据。
