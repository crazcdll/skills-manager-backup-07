## HA-03 防御性编程规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-D001 | 外部输入（RPC/HTTP/MQ）必须在方法入口前置校验，数值参数校验上下限 | P1 |
| MT:HA-D002 | 可能为null的返回值必须做null检查，Optional替代多级判空，集合返回空集合非null | P1 |
| MT:HA-D003 | 业务异常与系统异常必须分离：业务异常不触发熔断/告警，系统异常触发熔断/告警 | P1 |
| MT:HA-D004 | 资源必须安全释放：优先try-with-resources，连接池必须归还，finally释放不能覆盖原异常 | P1 |

### 强制禁止
- ✗ 禁止不校验参数直接使用外部输入
- ✗ 禁止对 Optional 直接 `.get()` 不做 `.isPresent()` 检查
- ✗ 禁止空 catch（`catch(Exception e) {}`）
- ✗ 禁止丢失异常链（`throw new XXX("msg")` 而非 `throw new XXX("msg", e)`）
- ✗ 禁止业务异常触发熔断计数
- ✗ 禁止资源使用后不释放

### 检查点
- [ ] 外部输入是否有前置校验
- [ ] 可能为 null 的返回值是否做了处理
- [ ] 业务异常和系统异常是否分离
- [ ] catch 块是否有实际处理逻辑
- [ ] 异常链是否完整保留
- [ ] 资源是否确保释放（try-with-resources 或 finally）

→ 完整规则含示例见 mt-java-coding-standards/HA-03-防御性编程规范.md
