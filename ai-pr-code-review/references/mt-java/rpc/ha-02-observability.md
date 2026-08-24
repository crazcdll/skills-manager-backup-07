## HA-02 可观测性规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-O001 | 核心接口必须覆盖四黄金指标（延迟/流量/错误率/饱和度），通过Cat SDK埋点 | P1 |
| MT:HA-O002 | 所有请求必须通过Mtrace透传traceId，异步操作必须手动传递上下文（TTL） | P1 |
| MT:HA-O003 | 告警必须分级（P0/P1/P2）+ 降噪策略（5分钟内不重复），内容含服务/接口/当前值/阈值/持续时间 | P1 |
| MT:HA-O004 | 远程日志必须使用 AsyncScribe，禁止 Async + Scribe 组合 | P0 |
| MT:HA-O005 | 生产环境禁止标准输出日志，禁止 Console Appender | P0 |
| MT:HA-O006 | 单条日志必须限制输出长度，PatternLayout 中限制消息长度 | P0 |
| MT:HA-O007 | 异常堆栈必须使用简化格式，PatternLayout 必须包含 `%ex` | P0 |

### 强制禁止
- ✗ 禁止 Transaction name 包含动态值（用户ID、订单号等）
- ✗ 禁止核心接口无 Metrics 埋点就上线
- ✗ 禁止不配置告警就上线
- ✗ 禁止将 Async 与 Scribe 组合使用（必须用 AsyncScribe）
- ✗ 禁止生产环境配置 Console / SYSTEM_OUT / SYSTEM_ERR
- ✗ 禁止 PatternLayout 不限制消息输出长度
- ✗ 禁止 PatternLayout 缺少 `%ex` 导致输出未简化堆栈

### 检查点
- [ ] 核心接口是否有 Raptor Metrics 埋点
- [ ] Transaction name 是否包含动态值
- [ ] 异步操作是否正确透传 traceId（TTL）
- [ ] 是否配置了分级告警
- [ ] 远程日志是否使用 AsyncScribe
- [ ] 生产环境是否有标准输出日志
- [ ] PatternLayout 是否限制消息长度
- [ ] 异常堆栈是否使用简化格式（含 `%ex`）

→ 完整规则含示例见 mt-java-coding-standards/HA-02-可观测性规范.md
