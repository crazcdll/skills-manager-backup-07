## HA-07 JVM与线程池高可用规范（审查精要）

> 本规范是线程池配置与 ThreadLocal 使用的唯一权威规范（SSOT）。

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:HA-J001 | 禁止使用Executors工厂方法，必须有界队列，禁止DiscardPolicy/DiscardOldestPolicy，局部线程池必须shutdown（P0） | P0 |
| MT:HA-J002 | CompletableFuture必须指定自定义线程池，禁止默认commonPool，禁止嵌套join，禁止parallelStream | P1 |
| MT:HA-J003 | ThreadLocal必须在finally中remove，跨线程池必须用TTL，禁止InheritableThreadLocal | P1 |
| MT:HA-J004 | 并发Map用computeIfAbsent优于putIfAbsent；遍历时禁止修改；线程池需配置告警 | P1 |

### 强制禁止
- ✗ 禁止 `Executors.newFixedThreadPool()`（LinkedBlockingQueue 无界，OOM）
- ✗ 禁止 `Executors.newCachedThreadPool()`（线程数 Integer.MAX_VALUE）
- ✗ 禁止使用无界队列
- ✗ 禁止使用 DiscardPolicy / DiscardOldestPolicy（静默丢弃任务）
- ✗ 禁止在循环/方法内反复创建线程池（P0）
- ✗ 禁止 CompletableFuture 使用默认 commonPool
- ✗ 禁止嵌套 join（可能导致线程池死锁）
- ✗ 禁止使用 parallelStream
- ✗ 禁止直接 `new Thread()`
- ✗ 禁止父子任务共用同一线程池
- ✗ 禁止 ThreadLocal 不 remove
- ✗ 禁止使用 InheritableThreadLocal

### 检查点
- [ ] 线程池是否使用有界队列
- [ ] 拒绝策略是否合理（非静默丢弃）
- [ ] 局部线程池是否在使用后 shutdown
- [ ] CompletableFuture 是否指定了自定义线程池
- [ ] 是否存在嵌套 join 或 parallelStream
- [ ] ThreadLocal 是否在 finally 中 remove
- [ ] 是否使用了 InheritableThreadLocal

→ 完整规则含示例见 mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md
