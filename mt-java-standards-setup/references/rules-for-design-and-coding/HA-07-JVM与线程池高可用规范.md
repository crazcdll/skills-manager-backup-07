---
ruleType: Model Request
description: 写线程池/CompletableFuture/ThreadLocal/跨线程透传时读我。是线程池配置与ThreadLocal唯一SSOT：必须通过Rhino创建和管理线程池，禁止Executors、直接使用ThreadPoolExecutor及其子类；CompletableFuture必须指定Rhino线程池、Future.get必须设置超时、ThreadLocal建议finally remove、跨线程池建议用TTL禁InheritableThreadLocal。建线程池或用ThreadLocal时必读。
category: 高可用规范
priority: high
---

# JVM 与线程池高可用规范

## 一、说明

本规范是**线程池配置与 ThreadLocal 使用的唯一权威规范（SSOT）**，涵盖线程池管理、异步并发、ThreadLocal 安全三个领域。

线程池配置不当（无界队列、父子共用线程池、循环创建线程池）是常见的线上故障诱因。`JAVA-04` 并发规范聚焦"并发代码写法（锁/volatile/并发集合）"，本规范聚焦"线程池基础设施治理"。

## 二、规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### HA-J001 [强制] 线程池必须通过 Rhino 创建和管理

线程池必须通过 Rhino 工具类创建和管理；**禁止使用 `Executors`、直接实例化 `ThreadPoolExecutor` 或其子类，也禁止直接调用 `ThreadPoolExecutor` 的方法**。

**说明**：
- 禁止 `Executors.newFixedThreadPool()`（LinkedBlockingQueue 无界，可能 OOM）
- 禁止 `Executors.newCachedThreadPool()`（最大线程数 Integer.MAX_VALUE，可能耗尽资源）
- 禁止直接 `new ThreadPoolExecutor(...)`，以及直接使用 `ThreadPoolExecutor` 子类
- 禁止将线程池声明为 `ThreadPoolExecutor` 或其子类，并调用其 `execute`、`submit`、`shutdown`、`setCorePoolSize` 等方法
- 线程池的容量、拒绝策略、生命周期管理必须通过 Rhino 配置和管理，避免绕过平台治理能力
- 在循环或高频调用路径中反复创建 Rhino 线程池在 CR 中标记为 P1

#### good case:

```java
// 通过 Rhino 创建并管理线程池
private static final ThreadPool THREAD_POOL = Rhino.newThreadPool("{自定义的RhinoKey}",
    DefaultThreadPoolProperties.Setter()
        .withCoreSize(30)
        .withMaxSize(60)
        .withMaxQueueSize(100)
);
```

#### bad case:

```java
// 使用 Executors 工厂方法 — 可能 OOM
ExecutorService executor = Executors.newFixedThreadPool(10);

// 直接创建或调用 ThreadPoolExecutor — 绕过 Rhino 的统一治理
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    1, 1, 0, TimeUnit.MILLISECONDS, new LinkedBlockingQueue<>()
);
executor.setCorePoolSize(20);
executor.shutdown();

// 方法内循环创建线程池 — P1 风险
public void processOrders(List<Order> orders) {
    for (Order order : orders) {
        ExecutorService pool = Executors.newSingleThreadExecutor(); // 每次循环创建，永不关闭！
        pool.submit(() -> process(order));
    }
}
```

---

### HA-J002 [强制] 异步操作必须使用自定义线程池

CompletableFuture 必须指定自定义线程池，禁止使用默认的 ForkJoinPool.commonPool()。

**说明**：
- `CompletableFuture.supplyAsync(task)` 默认使用 commonPool，与其他框架共享，可能被耗尽
- 必须使用 `CompletableFuture.supplyAsync(task, customExecutor)`
- 禁止在 CompletableFuture 回调中创建新的 CompletableFuture 后，使用 `join()` 或 `get()` 同步等待；应使用 `thenComposeAsync`、`thenCombineAsync`、`allOf` 等异步编排，避免线程池死锁
- 禁止使用 `parallelStream`（底层使用 commonPool，不可控）
- 禁止直接 `new Thread()`，必须通过线程池提交任务
- 禁止父子任务共用同一个线程池（可能死锁）

#### good case:

```java
// 指定自定义线程池
CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(
    () -> userService.getUser(userId), customExecutor);
CompletableFuture<List<Order>> orderFuture = CompletableFuture.supplyAsync(
    () -> orderService.listOrders(userId), customExecutor);

CompletableFuture.allOf(userFuture, orderFuture)
    .thenApply(v -> buildResult(userFuture.join(), orderFuture.join()));
```

#### bad case:

```java
// 使用默认 commonPool
CompletableFuture.supplyAsync(() -> userService.getUser(userId));

// 在回调中同步等待新异步任务 — 可能死锁
userFuture.thenApplyAsync(user ->
    orderService.listOrdersAsync(user.getId()).join(), sameExecutor);

// 使用 parallelStream — 不可控
orders.parallelStream().forEach(order -> process(order));
```

---

### HA-J003 [推荐] ThreadLocal 建议安全使用

ThreadLocal 变量**建议在 finally 块中 remove**，跨线程池传递建议使用 TTL（TransmittableThreadLocal）。

**说明**：
- 线程池中的线程会被复用，ThreadLocal 不 remove 会导致数据泄漏和业务错误
- 跨线程池传递 ThreadLocal 建议使用 `TransmittableThreadLocal`（TTL），**不建议使用 `InheritableThreadLocal`**（在线程池场景下不可靠）
- Mtrace 上下文的线程池传递也依赖 TTL

#### good case:

```java
private static final ThreadLocal<UserContext> USER_CONTEXT = new ThreadLocal<>();

public void handleRequest(Request request) {
    USER_CONTEXT.set(new UserContext(request.getUserId()));
    try {
        doBusinessLogic();
    } finally {
        USER_CONTEXT.remove(); // 建议 remove，防止线程池复用时数据污染
    }
}

// 跨线程池传递使用 TTL
private static final TransmittableThreadLocal<String> TRACE_ID = new TransmittableThreadLocal<>();
```

#### bad case:

```java
// 不 remove — 线程池复用时数据泄漏
USER_CONTEXT.set(new UserContext(request.getUserId()));
doBusinessLogic();
// 忘记 remove，下一个请求复用此线程时拿到错误的 UserContext

// 使用 InheritableThreadLocal — 在线程池场景不可靠
private static final InheritableThreadLocal<String> context = new InheritableThreadLocal<>();
```

---

### HA-J004 [推荐] 并发安全高可用增量

并发安全的基础规则（volatile/DCL、并发集合）详见 `JAVA-04` N011~N013。本条从高可用角度强调：

**说明**：
- 并发 Map 的 `computeIfAbsent` 优于 `putIfAbsent`（原子性更强，避免竞态条件导致的重复初始化）
- 配置告警：线程池活跃度、队列堆积超阈值时建议通过 Raptor 配置告警

---

### HA-J005 [强制] Future 获取结果必须设置超时

禁止无参调用 `Future.get()`；必须使用带超时参数的 `get(timeout, unit)`，避免任务异常或下游阻塞时无限等待。

#### good case:

```java
try {
    Result result = future.get(3, TimeUnit.SECONDS);
    handle(result);
} catch (TimeoutException e) {
    future.cancel(true);
    throw new ServiceException("异步任务执行超时", e);
} catch (InterruptedException e) {
    Thread.currentThread().interrupt();
    throw new ServiceException("异步任务被中断", e);
} catch (ExecutionException e) {
    throw new ServiceException("异步任务执行失败", e);
}
```

#### bad case:

```java
Result result = future.get(); // 无超时等待，可能导致调用线程永久阻塞
```

---

## 三、实践建议

1. 所有线程池必须通过 Rhino 创建和管理
2. CompletableFuture 必须指定 Rhino 线程池
3. Future 获取结果必须设置超时
4. ThreadLocal 建议在 finally 中 remove
5. 代码审查重点检查线程池创建和生命周期管理

## 四、规范执行要点

### 禁止做法
- ✗ 禁止使用 `Executors.newFixedThreadPool()` / `newCachedThreadPool()`
- ✗ 禁止直接实例化 `ThreadPoolExecutor` 或其子类
- ✗ 禁止直接调用 `ThreadPoolExecutor` 的方法
- ✗ 禁止绕过 Rhino 自行配置线程池的队列、拒绝策略或生命周期
- ✗ 禁止 CompletableFuture 使用默认 commonPool
- ✗ 禁止在 CompletableFuture 回调中同步等待新异步任务
- ✗ 禁止使用 parallelStream
- ✗ 禁止直接 new Thread()
- ✗ 禁止父子任务共用同一线程池
- ✗ 禁止无参调用 `Future.get()`
- ✗ 不建议在循环/方法内反复创建线程池（P1）
- ✗ 不建议 ThreadLocal 不 remove
- ✗ 不建议使用 InheritableThreadLocal

### 代码审查检查点
- [ ] 线程池是否全部通过 Rhino 创建和管理
- [ ] 是否直接实例化、声明或调用 `ThreadPoolExecutor` 及其子类
- [ ] 是否绕过 Rhino 自行配置线程池的队列、拒绝策略或生命周期
- [ ] CompletableFuture 是否指定了 Rhino 线程池
- [ ] 是否在 CompletableFuture 回调中同步等待新异步任务，或使用 parallelStream
- [ ] Future.get() 是否设置超时
- [ ] ThreadLocal 是否在 finally 中 remove
- [ ] 是否使用了 InheritableThreadLocal
- [ ] DCL 是否使用了 volatile（见 JAVA-04 N011）
