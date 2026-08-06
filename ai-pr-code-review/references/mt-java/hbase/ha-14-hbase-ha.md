## HA-14 HBase高可用规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-HB001 | RowKey必须使用Hash前缀(0000-9999)散列到不同Region，禁止时间戳前缀（热点写入） | P2 |
| MT:HA-HB002 | Scan必须指定StartRow和StopRow（P0），禁止全表Scan，建议setCaching(100) | P1 |
| MT:HA-HB003 | 重要数据同步写入，异步写入必须监听异常，禁止循环逐条flush，单个Cell ≤10MB | P2 |
| MT:HA-HB004 | 客户端配置：rpc.timeout 30s，meta.operation.timeout ≤10s，retries 3-5次，commons-io ≥2.4 | P2 |
| MT:HA-HB005 | 必须有容灾降级：Lion开关切流，降级不阻断核心业务，Raptor告警 | P2 |

### 强制禁止
- ✗ 禁止使用时间戳作为 RowKey 前缀（热点写入）
- ✗ 禁止 Scan 不指定 StartRow 和 StopRow（P0）
- ✗ 禁止在循环中逐条 flush（每次flush都是一次RPC）
- ✗ 禁止单个 Cell 超过 10MB
- ✗ 禁止不配置 HBase 容灾降级

### 检查点
- [ ] RowKey 是否使用 Hash 前缀散列
- [ ] Scan 是否指定了 StartRow 和 StopRow
- [ ] 重要数据是否使用同步写入
- [ ] 异步写入是否设置了异常监听
- [ ] 客户端超时参数是否显式配置
- [ ] 是否配置了 HBase 容灾降级

→ 完整规则含示例见 mt-java-coding-standards/HA-14-HBase高可用规范.md
