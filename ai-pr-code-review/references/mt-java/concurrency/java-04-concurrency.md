## JAVA-04 并发处理规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N001 | 单例对象必须线程安全（饿汉/双检锁+volatile/静态内部类） | P2 |
| MT:N002 | 创建线程/线程池时必须指定有意义的名称 | P2 |
| MT:N003 | 高并发场景优化锁粒度，优先使用无锁数据结构，缩小锁代码块范围 | P2 |
| MT:N004 | lock()必须在try块外调用，确保finally中unlock()正常执行 | P2 |
| MT:N005 | tryLock()必须先判断锁持有状态，释放规则与阻塞锁一致 | P2 |
| MT:N006 | 并发修改同一记录需用乐观锁（冲突<20%）或悲观锁，乐观锁重试≥3次 | P2 |
| MT:N007 | 多线程定时任务禁止用Timer，推荐ScheduledThreadPoolExecutor | P2 |
| MT:N009 | CountDownLatch必须确保每个线程执行countDown()，await()需设超时 | P2 |
| MT:N010 | 多线程场景必须用ThreadLocalRandom替代Random | P2 |
| MT:N011 | 延迟初始化：非静态用volatile+双检锁，静态用静态内部类 | P2 |
| MT:N012 | volatile仅适用一写多读，多写需结合同步机制 | P2 |
| MT:N013 | 多线程禁止使用HashMap，推荐ConcurrentHashMap；computeIfAbsent优于putIfAbsent | P2 |
| MT:N014 | 高并发避免用"等于"判断作为中断条件，采用区间判断（≤0 替代 ==0） | P2 |
| MT:N015 | 避免不必要的装箱拆箱，频繁计数用LongAdder替代AtomicLong | P2 |

### 强制禁止
- ✗ 禁止多线程共享 Random 实例
- ✗ 禁止锁整个方法体或使用类锁（除非必要）
- ✗ 禁止在高并发场景使用 HashMap 等非线程安全集合
- ✗ 禁止 lock() 在 try 块内调用

### 检查点
- [ ] 单例对象是否线程安全
- [ ] 线程和线程池是否有明确命名
- [ ] 锁粒度是否合理
- [ ] Random 使用是否正确（ThreadLocalRandom vs Random）
- [ ] 并发集合选择是否正确（ConcurrentHashMap vs HashMap）
- [ ] volatile 使用场景是否正确（一写多读）

→ 完整规则含示例见 mt-java-coding-standards/JAVA-04-并发处理规范.md
