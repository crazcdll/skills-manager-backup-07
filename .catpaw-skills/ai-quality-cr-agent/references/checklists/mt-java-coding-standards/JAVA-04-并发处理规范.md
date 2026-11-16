---
ruleType: Model Request
description: Java并发处理规范，聚焦并发代码写法：单例线程安全、线程命名、锁粒度/操作/tryLock/乐观锁/CountDownLatch、随机数、延迟初始化、volatile、ConcurrentHashMap、并发条件安全、装箱拆箱优化。线程池配置（Executors禁用/有界队列/拒绝策略）与ThreadLocal remove规范详见 HA-07。
category: Java编码规范
priority: medium
---

# Java并发处理规范

## 一、说明

本规范定义了Java编码过程中涉及**并发代码写法**的规范要求——怎么写才线程安全、怎么用锁才正确。

**线程池参数配置（coreSize/maxSize/queue/拒绝策略）、Executors 禁用、CompletableFuture 自定义线程池、ThreadLocal remove/TTL 跨线程池传递等，统一在 `HA-07-JVM与线程池高可用规范.md` 中规定。**

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:JAVA-04.N001 [强制] 单例对象线程安全规范

获取单例对象需保证线程安全，且方法实现需同步控制。

**说明**：资源驱动类、工具类、单例工厂类需采用线程安全的单例模式，包括饿汉模式、懒汉同步模式、双重检查锁或静态内部类实现。

#### good case:

```java
// 饿汉单例
public class HungrySingleton {
    private static final HungrySingleton INSTANCE = new HungrySingleton();
    private HungrySingleton() {}
    public static HungrySingleton getInstance() { return INSTANCE; }
}

// 双重检查锁（volatile 必须）
public class DCLSingleton {
    private static volatile DCLSingleton instance;
    private DCLSingleton() {}
    public static DCLSingleton getInstance() {
        if (instance == null) {
            synchronized (DCLSingleton.class) {
                if (instance == null) { instance = new DCLSingleton(); }
            }
        }
        return instance;
    }
}

// 静态内部类（推荐）
public class StaticInnerSingleton {
    private static class Holder {
        private static final StaticInnerSingleton INSTANCE = new StaticInnerSingleton();
    }
    public static StaticInnerSingleton getInstance() { return Holder.INSTANCE; }
}
```

---

### java-l1:JAVA-04.N002 [强制] 线程命名规范

创建线程或线程池时需指定有意义的名称，避免异步场景死锁。

**说明**：自定义线程工厂，按业务特征（如机房编号、模块名）分组命名，父子任务避免共享同一线程池以防止死锁。

---

### java-l1:JAVA-04.N003 [推荐] 锁性能优化规范

高并发场景需优化锁粒度，减少同步损耗。

**说明**：优先使用无锁数据结构，缩小锁代码块范围，避免锁整个方法体或使用类锁。

---

### java-l1:JAVA-04.N004 [强制] 锁操作规范

阻塞获取锁需在try块外，避免异常导致锁无法释放。

**说明**：lock()方法需在try块外调用，且中间无异常抛出点，确保finally中unlock()正常执行。

#### bad case:

```java
// 错误：lock在try块内，若lock()本身抛出异常，finally中unlock()会执行但未加锁
try {
    lock.lock(); // 错误位置
    doBusiness();
} finally {
    lock.unlock();
}
```

---

### java-l1:JAVA-04.N005 [强制] tryLock使用规范

使用tryLock获取锁时，必须先判断锁持有状态，释放规则与阻塞锁一致。

#### good case:

```java
if (lock.tryLock()) {
    try {
        // 业务逻辑
    } finally {
        lock.unlock();
    }
}
```

---

### java-l1:JAVA-04.N006 [推荐] 并发更新锁策略规范

并发修改同一记录时，需通过应用层锁、缓存锁或数据库乐观锁避免更新丢失。

**说明**：冲突概率<20%时推荐乐观锁（version字段），否则使用悲观锁，乐观锁重试次数≥3次。

---

### java-l1:JAVA-04.N007 [强制] 定时任务线程池规范

多线程定时任务禁止使用Timer，定时线程池同样必须通过 Rhino 创建和管理，禁止直接 `new ScheduledThreadPoolExecutor`。

**说明**：定时任务线程池的创建、容量与队列配置、生命周期管理遵循 `HA-07` java-l1:HA-07.HA-J001（必须通过 Rhino，禁止直接实例化 `ThreadPoolExecutor` 及其子类）；禁止使用 Timer（单线程、异常未捕获会导致整个定时任务停止）。

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

### java-l1:JAVA-04.N008 [推荐] 金融场景锁策略建议

资金相关敏感操作推荐使用悲观锁，确保数据一致性。

**说明**：悲观锁遵循"一锁二判三更新四释放"原则，避免乐观锁冲突处理复杂度。

---

### java-l1:JAVA-04.N009 [强制] CountDownLatch使用规范

使用CountDownLatch时，确保每个线程执行countDown()，避免主线程永久等待。

**说明**：await()需设置超时时间，并在finally块中处理异常，保证countDown()被调用。

---

### java-l1:JAVA-04.N010 [强制] 随机数生成规范

多线程场景推荐使用ThreadLocalRandom替代Random，提升性能和随机性。

**说明**：ThreadLocalRandom避免种子竞争，性能比Random高约20倍，直接使用nextInt()等方法。

---

### java-l1:JAVA-04.N011 [推荐] 延迟初始化规范

谨慎使用延迟初始化，根据场景选择双重检查锁或静态内部类模式。

**说明**：
- 非静态成员变量延迟初始化需用volatile修饰（双重检查锁，见N001示例）
- 静态成员变量推荐静态内部类模式（见N001示例）

---

### java-l1:JAVA-04.N012 [强制] volatile使用规范

volatile适用于一写多读场景，多写场景需结合同步机制。

**说明**：多写场景推荐使用ConcurrentHashMap、LongAdder等线程安全类，避免竞态条件。

---

### java-l1:JAVA-04.N013 [强制] 并发集合使用规范

多线程场景禁止使用HashMap，推荐ConcurrentHashMap。

**说明**：ConcurrentHashMap通过分段锁保证线程安全，避免HashMap resize时的环形链表死锁问题。并发Map的computeIfAbsent优于putIfAbsent（原子性更强）。

---

### java-l1:JAVA-04.N014 [强制] 控制语句并发安全规范

高并发场景避免使用"等于"判断作为中断条件，采用区间判断。

**说明**：例如用"剩余数量<=0"替代"剩余数量==0"，防止并发时数值瞬间负数导致逻辑错误。

---

### java-l1:JAVA-04.N015 [推荐] 装箱拆箱优化规范

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

### java-l1:JAVA-04.N016 [推荐] 方法调用优化规范

方法调用层级、深度递归、热点方法优化等通用方法优化规范详见 `JAVA-02` java-l1:JAVA-04.N006（含 good case），本规范不再重复。

---

## 三、执行要求

### 核心要求
1. **单例模式**：必须线程安全（饿汉/双检锁+volatile/静态内部类）
2. **线程命名**：创建线程或线程池时必须指定有意义的名称
3. **线程池创建**：禁止使用Executors，禁止直接实例化`ThreadPoolExecutor`或其子类，必须通过Rhino创建和管理，详见 `HA-07` java-l1:HA-07.HA-J001
4. **ThreadLocal清理**：线程池场景下必须在finally中remove()，详见 `HA-07` java-l1:HA-07.HA-J003
5. **锁粒度优化**：优先使用无锁数据结构，缩小锁代码块范围
6. **Random使用**：多线程场景必须使用ThreadLocalRandom，禁止共享Random实例
7. **volatile语义**：只用于一写多读场景，多写必须加锁

### 强制禁止
- ✗ 禁止使用Executors创建线程池（完整规范见 `HA-07`）
- ✗ 禁止直接实例化`ThreadPoolExecutor`或其子类（如`ScheduledThreadPoolExecutor`），必须通过Rhino创建（见 `HA-07` java-l1:HA-07.HA-J001）
- ✗ 禁止多线程共享Random实例
- ✗ 禁止锁整个方法体或使用类锁（除非必要）
- ✗ 禁止在高并发场景使用HashMap等非线程安全集合

### 代码审查检查点
- [ ] 单例对象是否线程安全
- [ ] 线程和线程池是否有明确命名
- [ ] 是否使用了Executors创建线程池（见 `HA-07`）
- [ ] 是否直接实例化了`ThreadPoolExecutor`或其子类，未通过Rhino创建（见 `HA-07` java-l1:HA-07.HA-J001）
- [ ] ThreadLocal是否在finally中remove（见 `HA-07`）
- [ ] 锁粒度是否合理，是否可用无锁数据结构替代
- [ ] Random使用是否正确（ThreadLocalRandom vs Random）
- [ ] 并发集合选择是否正确（ConcurrentHashMap vs HashMap）
