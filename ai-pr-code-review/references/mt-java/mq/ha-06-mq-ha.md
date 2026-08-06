## HA-06 消息队列高可用规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-M001 | 生产端必须检查SendResult，失败时有补偿机制（重试或本地消息表），消息Key必须含业务含义 | P1 |
| MT:HA-M002 | 消费端必须幂等（P0），必须全量catch(Throwable)，失败返回RECONSUME_LATER，禁止CONSUME_FAILURE | P0 |
| MT:HA-M003 | 顺序消息：相同业务Key路由到同一partition，parallel.num=1，失败不能跳过 | P1 |
| MT:HA-M004 | 积压必须有告警（>1000条）和处理策略（增加消费者/提高并发/跳过非核心消息） | P1 |

### 强制禁止
- ✗ 禁止不检查消息发送结果（fire-and-forget）
- ✗ 禁止消费逻辑不保证幂等
- ✗ 禁止使用 CONSUME_FAILURE（消息会被直接丢弃）
- ✗ 禁止消费方法不做全量 catch
- ✗ 禁止通过清空 topic 处理积压

### 检查点
- [ ] 消息发送后是否检查 SendResult
- [ ] 发送失败是否有补偿机制
- [ ] 消费逻辑是否保证幂等
- [ ] 消费方法是否全量 catch(Throwable)
- [ ] 消费失败是否返回 RECONSUME_LATER
- [ ] 是否配置了积压告警
- [ ] 顺序消息是否正确配置并发度

→ 完整规则含示例见 mt-java-coding-standards/HA-06-消息队列高可用规范.md
