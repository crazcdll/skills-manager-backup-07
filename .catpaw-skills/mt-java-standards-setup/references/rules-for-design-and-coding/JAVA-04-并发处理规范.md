---
ruleType: Model Request
description: 写多线程/锁/定时任务/并发集合/volatile时读我。规定线程命名、定时任务线程池、金融锁策略、锁性能、延迟初始化(DCL)、volatile一写多读、并发集合用ConcurrentHashMap。线程池配置(Executors禁用/有界队列)与ThreadLocal remove见HA-07。
category: Java编码规范
priority: medium
---

# Java并发处理规范

## 一、说明

本规范定义了Java编码过程中涉及**并发代码写法**的规范要求——怎么写才线程安全、怎么用锁才正确。

**线程池参数配置（coreSize/maxSize/queue/拒绝策略）、Executors 禁用、CompletableFuture 自定义线程池、ThreadLocal remove/TTL 跨线程池传递等，统一在 `HA-07-JVM与线程池高可用规范.md` 中规定。**

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N002 [强制] 线程命名规范

创建线程或线程池时需指定有意义的名称，避免异步场景死锁。

**说明**：自定义线程工厂，按业务特征（如机房编号、模块名）分组命名，父子任务避免共享同一线程池以防止死锁。

---

### N007 [强制] 定时任务线程池规范

多线程定时任务禁止使用Timer，定时线程池同样必须通过 Rhino 创建和管理，禁止直接 `new ScheduledThreadPoolExecutor`。

**说明**：定时任务线程池的创建、容量与队列配置、生命周期管理遵循 `HA-07` HA-J001（必须通过 Rhino，禁止直接实例化 `ThreadPoolExecutor` 及其子类）；禁止使用 Timer（单线程、异常未捕获会导致整个定时任务停止）。

#### good case:

```java
// 定时线程池同样通过 Rhino 创建和管理，禁止直接 new ScheduledThreadPoolExecutor
private static final ThreadPool SCHEDULE_POOL = Rhino.newThreadPool("{schedulePoolKey}",
    DefaultThreadPoolProperties.Setter()
        .withCoreSize(5)
        .withMaxSize(10)
        .withMaxQueueSize(100)
);
// 定时调度逻辑按 Rhino 提供的调度能力使用，容量/拒绝策略由 Rhino 统一治理
```

---

### N008 [推荐] 金融场景锁策略建议

资金相关敏感操作推荐使用悲观锁，确保数据一致性。

**说明**：悲观锁遵循"一锁二判三更新四释放"原则，避免乐观锁冲突处理复杂度。

---

### N009 [强制] CountDownLatch使用规范

使用CountDownLatch时，确保每个线程执行countDown()，避免主线程永久等待。

**说明**：await()需设置超时时间，并在finally块中处理异常，保证countDown()被调用。

---

### N011 [推荐] 延迟初始化规范

谨慎使用延迟初始化，根据场景选择双重检查锁或静态内部类模式。

**说明**：
- 非静态成员变量延迟初始化需用volatile修饰（双重检查锁）
- 静态成员变量推荐静态内部类模式

---

### N012 [强制] volatile使用规范

volatile适用于一写多读场景，多写场景需结合同步机制。

**说明**：多写场景推荐使用ConcurrentHashMap、LongAdder等线程安全类，避免竞态条件。

---

### N013 [强制] 并发集合使用规范

多线程场景禁止使用HashMap，推荐ConcurrentHashMap。

**说明**：ConcurrentHashMap通过分段锁保证线程安全，避免HashMap resize时的环形链表死锁问题。并发Map的computeIfAbsent优于putIfAbsent（原子性更强）。

---

### N015 [推荐] 装箱拆箱优化规范

避免不必要的自动装箱拆箱，基本类型数组替代包装类型数组，使用原始类型操作类。

**说明**：
- 频繁计数场景用LongAdder（分段累加），避免Integer.valueOf()隐式装箱
- 基本类型数组优于包装类型数组（减少对象分配）
- 高并发计数用LongAdder替代AtomicLong（减少自旋开销）

```java
// good case: 原始类型数组 + LongAdder
int[] ids = new int[1000];
for (int i = 0; i < ids.length; i++) { ids[i] = i; }

LongAdder counter = new LongAdder();
for (int i = 0; i < 10000; i++) { counter.increment(); }
long result = counter.sum();
```

---

### N016 [推荐] 方法调用优化规范

热点方法优化（static/final 减少虚方法表查找）、深度递归改迭代、调用链 ≤5 层等通用方法调用优化详见 `JAVA-02` N006（含 good/bad 示例）。本条不重复正文。

> 注：方法调用优化与并发无直接关系，归入 JAVA-02 OOP 设计规约；JAVA-04 仅在并发场景下强调锁内热点路径避免虚方法调用等并发特有约束。

---

## 三、执行要求

- 创建线程或线程池时必须指定有意义的名称
- ✗ 禁止使用 Executors 创建线程池，禁止直接实例化 ThreadPoolExecutor 或其子类，必须通过 Rhino 创建和管理（完整规范见 `HA-07` HA-J001）
- 线程池场景下 ThreadLocal 必须在 finally 中 remove（见 `HA-07` HA-J003）
