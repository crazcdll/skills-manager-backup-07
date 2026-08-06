# P1 稳定性与安全 — 完整检查清单

> 本文件是 SKILL.md 中 P1 层的详细展开。安全部分对齐美团安全训练平台（security.mws.sankuai.com）12 类漏洞分类。

> 🚨 **P1 全局报出规则（对所有子类别生效，优先级高于各子类别的独立门槛）**
>
> 每条疑似 P1 在内部必须完成以下校验。**不满足的直接按实际级别归类输出，不在文档中出现"降级"字样**：
>
> | 校验项 | 要求 | 不满足时 |
> |--------|------|---------|
> | 代码证据 | diff 中有具体行号和代码片段（不是"可能会调用"） | 不报 |
> | 线上场景 | 能描述具体业务场景：什么请求→什么数据→触发什么异常→影响什么功能 | 归为 P2/P3 |
> | 排除已有保护 | 确认调用链上无 try-catch/降级/兜底等防护，或有防护但防护不充分 | 有完整防护 → 不报或归为 P2/P3 |
> | 非猜测性 | 结论基于代码事实，不是"可能不够"、"理论上会" | 归为 P2/P3 |
>
> **P1 输出格式（强制，每条必须包含）**：
> ```
> **🟠 [P1-xx] {规则编号} — {一句话概括}**
>
> - **文件**：{完整文件名} L{行号}
> - **问题代码**：`{关键代码片段}`
> - **触达分析**：{数据从哪来？经过哪些调用？外层有无保护？}
> - **线上场景**：{什么请求/什么时机/什么数据会触发？发生概率？}
> - **影响范围**：{影响哪个接口？单次失败还是服务级影响？有无降级？}
> - **修复建议**：{具体修复方案，含代码片段}
> ```
>
> **以下场景禁止报 P1（直接归到对应级别，不提"降级"）**：
> | 场景 | 实际级别 | 原因 |
> |------|---------|------|
> | "超时时间可能不够"（无性能数据支撑） | P3 | 纯猜测，没有依据 |
> | "没有 failover/多 IP"（测试环境直连） | P3 | 测试环境本身就是非关键依赖 |
> | "没有重试"（用户主动触发的同步操作） | P3 | 用户可手动重试 |
> | "没有事务保护"（跨 RPC + 乐观锁 + 逐步 catch 设计） | 不报 | 有意为之的非事务设计 |
> | "catch(Exception) 范围过宽"（已有 log.error + Cat 上报） | P2 | 已有监控，仅建议细化 |
> | "缓存可能过期"（业务可容忍短暂不一致） | P3 | 非强一致性要求场景 |

---

## 1.1 异常处理（EH）

> ⚠️ **异常处理类问题的报出门槛（所有 EH-xx 规则必须遵守）：**
>
> 只有同时满足以下三条，才允许报 P1，否则不报或降为 P3 建议：
> 1. **diff 中有明确的调用点**：能在 diff 代码里找到具体的方法调用（如 `GsonUtils.fromJsonString(...)`），而非推测"可能会调用"
> 2. **调用链上确认无保护**：必须从 diff 或完整读取的方法体中确认该调用点**没有** try-catch 包围，而非"可能没有"
> 3. **入参不可信可从代码中直接看出**：数据来源（外部接口、配置中心、用户输入等）能从 diff 代码中直接识别，不能靠猜测或命名推断
>
> **禁止仅凭"该方法可能抛出异常"就报问题**，没有明确代码证据的异常风险一律不报。

### CR:EH-01 空 catch 块

```java
// ❌ 吞掉异常，线上出问题完全无感知
try {
    orderService.createOrder(request);
} catch (Exception e) {
    // 什么都不做
}

// ✅ 至少 log + 业务处理
try {
    orderService.createOrder(request);
} catch (DuplicateOrderException e) {
    log.warn("duplicate order, userId={}, dealId={}", userId, dealId);
    return Result.fail("请勿重复下单");
} catch (Exception e) {
    log.error("createOrder failed, userId={}, request={}", userId, request, e);
    Cat.logError(e);
    return Result.fail("系统异常，请稍后重试");
}
```

### CR:EH-02 catch 范围过宽

```java
// ❌ catch Exception 掩盖了 NPE、ClassCast 等编码错误
try {
    process(data);
} catch (Exception e) {
    log.error("process error", e);
}

// ✅ 精确 catch，编码错误让它暴露出来
try {
    process(data);
} catch (BusinessException e) {
    log.warn("biz error: {}", e.getMessage());
    return Result.fail(e.getCode(), e.getMessage());
} catch (TimeoutException e) {
    log.error("process timeout, data={}", data.getId(), e);
    Cat.logError(e);
    return Result.fail("处理超时");
}
// NPE/ClassCastException 等不 catch，让上层兜底 + 告警
```

### CR:EH-04 异常缺少上下文

```java
// ❌ 只打异常，没有业务上下文
log.error("query failed", e);

// ✅ 带入关键业务参数
log.error("query failed, shopId={}, dealId={}, operator={}", shopId, dealId, operator, e);
```

### CR:EH-05 关键异常无监控

```java
// ❌ 只 log 不上报
log.error("payment callback verify failed", e);

// ✅ 同时上报监控（Cat / Metric）
log.error("payment callback verify failed, orderId={}", orderId, e);
Cat.logError("PaymentVerifyFailed", e);
// 或
MetricManager.count("payment_verify_fail", 1, Map.of("reason", e.getClass().getSimpleName()));
```

---

## 1.2 资源管理（RM）

### CR:RM-01 / CR:RM-02 资源关闭

```java
// ❌ 手动关闭，异常时可能泄露
Connection conn = dataSource.getConnection();
try {
    PreparedStatement ps = conn.prepareStatement(sql);
    ResultSet rs = ps.executeQuery();
    // ... 处理
    rs.close();
    ps.close();
} finally {
    conn.close();  // 如果 rs.close() 抛异常，ps 和 conn 都泄露
}

// ✅ try-with-resources，自动关闭所有资源
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql);
     ResultSet rs = ps.executeQuery()) {
    // ... 处理
}
```

### CR:RM-03 ThreadLocal 泄露

```java
// ❌ set 后无 remove，线程池复用时数据串到下一个请求
public class UserContext {
    private static final ThreadLocal<User> USER = new ThreadLocal<>();
    
    public static void set(User user) { USER.set(user); }
    public static User get() { return USER.get(); }
}
// 在 Controller 中 set 了，但忘了 remove

// ✅ 在 Filter/Interceptor 的 afterCompletion 中清理
@Override
public void afterCompletion(HttpServletRequest req, HttpServletResponse resp, Object handler, Exception ex) {
    UserContext.remove();  // 必须在 finally 语义中执行
}
```

### CR:RM-04 线程池参数

```java
// ❌ 无界队列 + 默认拒绝策略
ExecutorService pool = new ThreadPoolExecutor(
    2, 2,                          // 核心和最大都是 2
    60, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>()    // 无界队列 → 任务堆积 → OOM
);

// ✅ 有界队列 + 明确拒绝策略 + 线程命名
ExecutorService pool = new ThreadPoolExecutor(
    4, 8,
    60, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),                       // 有界
    new ThreadFactoryBuilder().setNameFormat("order-async-%d").build(),
    new ThreadPoolExecutor.CallerRunsPolicy()              // 拒绝策略
);
```

### CR:RM-05 Future.get() 必须设超时

```java
// ❌ 无超时，下游卡住 → 当前线程永久阻塞 → 线程池打满
Future<Result> future = executor.submit(task);
Result result = future.get();  // 永久阻塞！

// ✅ 必须设置超时时间
Result result = future.get(500, TimeUnit.MILLISECONDS);
```

### CR:RM-06 禁止 CompletableFuture.allOf().join()

```java
// ❌ join() 无超时，且异常被包装为 CompletionException
CompletableFuture.allOf(futures).join();

// ✅ 使用 get 并设置超时
CompletableFuture.allOf(futures).get(3, TimeUnit.SECONDS);
```

### CR:RM-07 supplyAsync/runAsync 必须指定自定义线程池

```java
// ❌ 默认 ForkJoinPool，核心线程数 = CPU-1，IO 密集场景严重不足 + 无界队列 OOM
CompletableFuture.supplyAsync(() -> queryFromDB(id));

// ✅ 指定自定义线程池
CompletableFuture.supplyAsync(() -> queryFromDB(id), bizThreadPool);
```

### CR:RM-08 禁止父子任务共用线程池

```java
// ❌ 父任务等子任务结果，子任务在同一线程池排队 → 死锁（重启无法恢复）
CompletableFuture<Void> parent = CompletableFuture.runAsync(() -> {
    CompletableFuture<String> child = CompletableFuture.supplyAsync(() -> "data", samePool);
    child.get();  // 父线程在此阻塞，子任务在队列等线程 → 死锁
}, samePool);

// ✅ 父子任务使用不同线程池
CompletableFuture.runAsync(() -> {
    CompletableFuture.supplyAsync(() -> "data", childPool).get(500, TimeUnit.MILLISECONDS);
}, parentPool);
```

### CR:RM-09 局部线程池必须在 finally 中 shutdown

```java
// ❌ 局部创建后未 shutdown → 线程泄漏 → OOM
ExecutorService pool = new ThreadPoolExecutor(...);
pool.submit(task);
// 方法结束但线程池还活着

// ✅ finally 中关闭
ExecutorService pool = new ThreadPoolExecutor(...);
try {
    pool.submit(task);
} finally {
    pool.shutdown();
}
```

### CR:RM-10 禁止在递归方法中创建线程/任务

```java
// ❌ 递归创建线程，深度不可控时线程数爆炸 → OOM
void processTree(Node node) {
    executor.submit(() -> {
        process(node);
        for (Node child : node.children) {
            processTree(child);  // 递归 submit → 线程数指数增长
        }
    });
}

// ✅ 用队列 + 迭代替代递归提交
Queue<Node> queue = new LinkedList<>(List.of(root));
while (!queue.isEmpty()) {
    Node node = queue.poll();
    executor.submit(() -> process(node));
    queue.addAll(node.children);
}
```

### CR:RM-11 禁止无界队列

```java
// ❌ 不指定容量 = Integer.MAX_VALUE → 任务堆积 → OOM
new LinkedBlockingQueue<>()

// ✅ 显式指定合理容量
new LinkedBlockingQueue<>(1000)
```

### CR:RM-12 禁止 Executors.newXxx 创建线程池

```java
// ❌ FixedThreadPool / SingleThreadPool 内部无界队列 → OOM
// ❌ CachedThreadPool / ScheduledThreadPool 最大线程数 Integer.MAX_VALUE → OOM
ExecutorService pool = Executors.newFixedThreadPool(10);

// ✅ 必须使用 ThreadPoolExecutor 显式指定所有参数（或使用 Rhino 动态线程池）
ThreadPoolExecutor pool = new ThreadPoolExecutor(
    10, 20, 60, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),
    new ThreadFactoryBuilder().setNameFormat("biz-pool-%d").build(),
    new ThreadPoolExecutor.CallerRunsPolicy()
);
```

---

## 1.3 并发安全（CC）

### CR:CC-02 SimpleDateFormat 线程不安全

```java
// ❌ static SimpleDateFormat，多线程调用 format/parse 输出乱码
private static final SimpleDateFormat SDF = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

public String formatDate(Date date) {
    return SDF.format(date);  // 并发时输出错误结果
}

// ✅ DateTimeFormatter（不可变，线程安全）
private static final DateTimeFormatter DTF = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

public String formatDate(LocalDateTime dateTime) {
    return DTF.format(dateTime);
}
```

### CR:CC-04 双重检查锁

```java
// ❌ 缺少 volatile，可能读到半初始化对象
private static Singleton instance;
public static Singleton getInstance() {
    if (instance == null) {
        synchronized (Singleton.class) {
            if (instance == null) {
                instance = new Singleton();  // 指令重排序风险
            }
        }
    }
    return instance;
}

// ✅ volatile 禁止指令重排序
private static volatile Singleton instance;
```

### CR:CC-05 HashMap 并发写入

```java
// ❌ 多线程写 HashMap
private Map<Long, OrderInfo> orderCache = new HashMap<>();
// 在多线程中 put → JDK 7 死循环，JDK 8+ 数据丢失

// ✅ ConcurrentHashMap
private Map<Long, OrderInfo> orderCache = new ConcurrentHashMap<>();
```

### CR:CC-06 ConcurrentHashMap 禁止 null 键/值

```java
// ❌ ConcurrentHashMap 的 key 和 value 均不允许 null（与 HashMap 不同）
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();
map.put(null, "value");   // NPE！
map.put("key", null);     // NPE！

// ✅ 存入前确保非 null
if (key != null && value != null) {
    map.put(key, value);
}
```

### CR:CC-07 Collectors.toMap() 必须处理 key 冲突和 null value

```java
// ❌ 重复 key → IllegalStateException，null value → NPE
Map<String, Integer> map = list.stream()
    .collect(Collectors.toMap(Item::getKey, Item::getValue));

// ✅ 处理 key 冲突 + null value
Map<String, Integer> map = list.stream()
    .collect(Collectors.toMap(
        Item::getKey,
        item -> Optional.ofNullable(item.getValue()).orElse(0),  // null 兜底
        (existing, replacement) -> existing  // key 冲突取先到的
    ));
```

---

## 1.4 容灾降级（FT）

### CR:FT-01 RPC 超时

```java
// ❌ 无超时，下游卡住 → 当前线程阻塞 → 线程池打满
ShopInfo shop = shopRpc.getShop(shopId);

// ✅ 显式超时
ShopInfo shop = shopRpc.getShop(shopId, RpcConfig.builder()
    .connectTimeout(200)   // 连接超时 200ms
    .readTimeout(500)      // 读超时 500ms
    .build());
```

### CR:FT-02 Fallback 降级

```java
// ❌ 推荐服务挂了 → 整个页面不可用
List<Deal> recommended = recommendRpc.getRecommends(userId);

// ✅ 非核心依赖降级
List<Deal> recommended;
try {
    recommended = recommendRpc.getRecommends(userId);
} catch (Exception e) {
    log.warn("recommend fallback, userId={}", userId);
    recommended = getDefaultRecommends();  // 兜底：热门 / 缓存 / 空列表
}
```

### CR:FT-03 重试策略

```java
// ❌ 无限重试，加剧下游压力
while (true) {
    try { return rpcCall(); }
    catch (Exception e) { Thread.sleep(100); }
}

// ✅ 有限次 + 指数退避
int maxRetries = 3;
for (int i = 0; i < maxRetries; i++) {
    try {
        return rpcCall();
    } catch (RetryableException e) {
        if (i == maxRetries - 1) throw e;
        Thread.sleep((long) Math.pow(2, i) * 100);  // 100ms, 200ms, 400ms
    }
}
```

### CR:FT-04 熔断配置缺失的分级判定

> ⚠️ **RPC 熔断配置缺失不一定是 P1，必须结合调用链上下文判定级别：**
>
> | 场景 | 级别 | 理由 |
> |------|------|------|
> | 无超时 + 无 catch + 无熔断 → 下游挂了主流程直接阻塞 | **P1** | 真实稳定性风险 |
> | 已有超时 + 已有 catch-all 兜底，但缺少 `failfast` 熔断配置 | **P3** | 异常已被降级，仅影响性能（超时堆积拉高 TP99），不影响功能正确性 |
> | 核心链路（如支付/下单）的 RPC，无熔断 | **P1** | 核心链路不容有失 |
> | 非核心链路（如推荐/标签/空间库），已有降级兜底 | **P3** | 不影响主业务 |
>
> **关键原则**：已有 catch-all 降级保护的非核心 RPC 调用，缺少熔断配置 = **P3 性能建议**，不升 P1。
> 不要因为"理论上高并发下可能有超时堆积"就升级为稳定性问题——已有 catch 保护意味着业务功能不受影响。

---

## 1.5 Null 防御（NP）

> ⚠️ **Null 相关问题的报出门槛（所有 NP-xx 规则必须遵守）：**
>
> 只有同时满足以下条件，才允许报 P1：
> 1. **能从 diff 代码中直接确认 null 的来源**：变量来自外部输入（RPC 返回值、配置中心、用户参数、Map.get 等明确可能为 null 的 API），或变量声明时允许 null 赋值
> 2. **调用链上确认无 null 保护**：从 diff 或完整方法体中确认该变量在使用点之前**没有** null 检查
> 3. **null 到达使用点后会导致明确的运行时异常**：NPE（拆箱、方法调用）、下游系统异常（null 值传入查询导致脏数据/报错）
>
> **禁止仅凭"该参数名看起来可能为 null"就报 P1**——必须追溯调用链确认来源：
> - 如果上层调用方已有 null 校验（如 `if (dpPoiId == null) return`）或参数标注 `@NonNull`，则该点不可能为 null，**不报**
> - 如果无法从 diff 中确认调用链（diff 范围不含上层调用方），应**降为 P2 建议**（"建议加 null 校验"），不报 P1
> - **推测性的 null 风险**（"若某些场景下为 null"）最多 P2，绝不报 P1

### CR:NP-01 自动拆箱 NPE

```java
// ❌ Integer 与 int 比较，Integer 为 null 时拆箱 NPE
Integer threshold = config.getThreshold();  // 可能返回 null
if (value <= threshold) { ... }  // NPE！

// ✅ 先判空
if (threshold == null || value <= threshold) { ... }
```

### CR:NP-02 集合中放入 null

```java
// ❌ null 元素进入集合，下游遍历/查询时可能异常
scope.setShopIds(Lists.newArrayList(dpPoiId));  // dpPoiId 可能为 null

// ✅ 先校验
if (dpPoiId == null) {
    log.warn("dpPoiId is null, skip query");
    return;
}
scope.setShopIds(Lists.newArrayList(dpPoiId));
```

---

## 1.6 安全漏洞（SEC）

> 对齐美团安全训练平台 12 类安全漏洞

### CR:SEC-01 越权

```java
// ❌ 只校验登录，不校验资源归属
@GetMapping("/order/{orderId}")
public OrderInfo getOrder(@PathVariable Long orderId) {
    return orderService.getById(orderId);  // 任意登录用户可查任意订单
}

// ✅ 校验当前用户对资源的归属权
@GetMapping("/order/{orderId}")
public OrderInfo getOrder(@PathVariable Long orderId) {
    Long currentUserId = UserContext.getUserId();
    OrderInfo order = orderService.getById(orderId);
    if (!order.getUserId().equals(currentUserId)) {
        throw new ForbiddenException("无权访问该订单");
    }
    return order;
}

// ✅ 垂直越权：管理员接口校验角色
@PreAuthorize("hasRole('ADMIN')")
@PostMapping("/admin/audit")
public Result audit(@RequestBody AuditRequest req) { ... }
```

### CR:SEC-02 SQL 注入

```java
// ❌ 字符串拼接 SQL
String sql = "SELECT * FROM users WHERE name = '" + userName + "'";
// 输入 ' OR '1'='1 → 返回所有用户

// ✅ MyBatis 参数化
@Select("SELECT * FROM users WHERE name = #{userName}")
User selectByName(@Param("userName") String userName);

// ⚠️ MyBatis ${} 是字符串替换，不是参数化！
// ❌ @Select("SELECT * FROM ${tableName} WHERE id = #{id}")
// ✅ 动态表名用白名单校验
if (!ALLOWED_TABLES.contains(tableName)) {
    throw new IllegalArgumentException("非法表名");
}
```

### CR:SEC-03 跨站脚本攻击（XSS）

```java
// ❌ 用户输入直接输出到 HTML
response.getWriter().write("<div>" + userInput + "</div>");
// 输入 <script>alert('xss')</script> → 执行恶意脚本

// ✅ HTML 转义
import org.apache.commons.text.StringEscapeUtils;
response.getWriter().write("<div>" + StringEscapeUtils.escapeHtml4(userInput) + "</div>");

// ✅ 富文本用白名单过滤
import org.jsoup.Jsoup;
import org.jsoup.safety.Safelist;
String safe = Jsoup.clean(richTextInput, Safelist.relaxed());
```

### CR:SEC-04 URL 重定向

```java
// ❌ 用户传入 URL 直接跳转
@GetMapping("/redirect")
public void redirect(@RequestParam String url, HttpServletResponse resp) {
    resp.sendRedirect(url);  // 可被利用做钓鱼
}

// ✅ 白名单校验
private static final Set<String> ALLOWED_DOMAINS = Set.of("meituan.com", "sankuai.com", "dianping.com");

@GetMapping("/redirect")
public void redirect(@RequestParam String url, HttpServletResponse resp) {
    URI uri = URI.create(url);
    if (!ALLOWED_DOMAINS.contains(extractDomain(uri.getHost()))) {
        throw new IllegalArgumentException("非法跳转地址");
    }
    resp.sendRedirect(url);
}
```

### CR:SEC-05 服务端请求伪造（SSRF）

```java
// ❌ 用户可控 URL 直接发起服务端请求
@PostMapping("/fetch")
public String fetchUrl(@RequestParam String url) {
    return HttpClient.get(url);  // 可访问内网 / 云元数据 / 本地服务
}

// ✅ 校验 URL 协议 + 禁止内网地址
public String safeFetch(String url) {
    URI uri = URI.create(url);
    // 1. 只允许 http/https
    if (!"http".equals(uri.getScheme()) && !"https".equals(uri.getScheme())) {
        throw new IllegalArgumentException("非法协议");
    }
    // 2. 解析 IP，禁止内网/回环/私有地址
    InetAddress addr = InetAddress.getByName(uri.getHost());
    if (addr.isLoopbackAddress() || addr.isSiteLocalAddress() || addr.isLinkLocalAddress()) {
        throw new IllegalArgumentException("禁止访问内网地址");
    }
    return HttpClient.get(url);
}
```

### CR:SEC-06 XML 外部实体注入（XXE）

```java
// ❌ 默认 XML 解析器允许外部实体
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
Document doc = factory.newDocumentBuilder().parse(inputStream);
// 恶意 XML: <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>

// ✅ 禁用外部实体 + DTD
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
```

### CR:SEC-07 非预期文件操作

```java
// ❌ 路径穿越
@GetMapping("/download")
public void download(@RequestParam String filename, HttpServletResponse resp) {
    File file = new File("/data/files/" + filename);  // filename = "../../etc/passwd"
    // ...
}

// ✅ 路径规范化 + 白名单目录校验
String basePath = "/data/files/";
Path resolved = Paths.get(basePath, filename).normalize();
if (!resolved.startsWith(basePath)) {
    throw new IllegalArgumentException("非法文件路径");
}
```

### CR:SEC-08 命令注入

```java
// ❌ 拼接用户输入到系统命令
Runtime.getRuntime().exec("ping " + userInput);
// 输入 "8.8.8.8; rm -rf /" → 灾难

// ✅ 参数化调用
ProcessBuilder pb = new ProcessBuilder("ping", "-c", "3", userInput);
// 更好：完全避免系统命令，用 Java 原生库实现
InetAddress.getByName(userInput).isReachable(3000);
```

### CR:SEC-09 CORS 配置不当

```java
// ❌ 允许所有来源
@Bean
public CorsFilter corsFilter() {
    config.addAllowedOrigin("*");        // 危险
    config.setAllowCredentials(true);    // 和 * 一起用更危险
}

// ✅ 白名单 Origin
config.setAllowedOrigins(List.of(
    "https://www.meituan.com",
    "https://www.dianping.com"
));
config.setAllowCredentials(true);
```

### CR:SEC-10 逻辑设计缺陷

```java
// ❌ 关键操作无幂等保护
@PostMapping("/pay")
public Result pay(@RequestBody PayRequest req) {
    paymentService.deduct(req.getAmount());  // 重复提交 → 重复扣款
}

// ✅ 幂等 token
@PostMapping("/pay")
public Result pay(@RequestBody PayRequest req) {
    if (!idempotentService.tryAcquire(req.getIdempotentKey())) {
        return Result.fail("请勿重复提交");
    }
    paymentService.deduct(req.getAmount());
}
```

### CR:SEC-11 敏感信息泄露

```java
// ❌ 日志打印完整手机号/密码
log.info("user login, phone={}, password={}", phone, password);

// ✅ 脱敏
log.info("user login, phone={}****{}", phone.substring(0,3), phone.substring(7));

// ❌ API 响应暴露堆栈
@ExceptionHandler(Exception.class)
public Result handleException(Exception e) {
    return Result.fail(e.getMessage() + "\n" + ExceptionUtils.getStackTrace(e));
}

// ✅ 只返回友好提示
@ExceptionHandler(Exception.class)
public Result handleException(Exception e) {
    log.error("unexpected error", e);  // 详情只写日志
    return Result.fail("系统异常，请稍后重试");
}
```

### CR:SEC-12 硬编码凭证

```java
// ❌ 代码中硬编码
private static final String DB_PASSWORD = "***";
private static final String API_KEY = "***";

// ✅ 使用配置中心 / 环境变量 / 密钥管理服务
@Value("${db.password}")
private String dbPassword;

// 或通过美团 Lion 配置中心
String apiKey = LionManager.get("xxx.api.key");
```

---

*文件版本：v1.0 | 对应 SKILL.md P1 层 | 5 维度 29 条规则（17 稳定性 + 12 安全）*
*安全部分对齐：美团安全训练平台 security.mws.sankuai.com 基础分类*
