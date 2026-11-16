# P3 性能与现代化 — 完整检查清单

> 本文件是 SKILL.md 中 P3 层的详细展开，提供每条规则的反模式代码示例和正确做法。

---

## 3.1 数据库访问（DB）

### CR:DB-01 N+1 查询

```java
// ❌ 循环内逐条查询
for (Long userId : userIds) {
    User user = userMapper.selectById(userId);  // N 次 SQL
    result.add(convert(user));
}

// ✅ 批量查询
List<User> users = userMapper.selectBatchIds(userIds);  // 1 次 SQL
Map<Long, User> userMap = users.stream()
    .collect(Collectors.toMap(User::getId, Function.identity()));
for (Long userId : userIds) {
    result.add(convert(userMap.get(userId)));
}
```

### CR:DB-02 大 IN 查询分批

```java
// ❌ IN 子句无上限
List<Order> orders = orderMapper.selectByIds(allIds);  // allIds 可能 10000+

// ✅ 分批，每批 ≤ 200
List<Order> orders = Lists.partition(allIds, 200).stream()
    .flatMap(batch -> orderMapper.selectByIds(batch).stream())
    .collect(Collectors.toList());
```

**为什么是 200？** MySQL 的 IN 子句在超过 200~500 个元素后查询计划可能从索引查找退化为全表扫描；同时避免单条 SQL 超过 `max_allowed_packet`。

### CR:DB-03 避免 SELECT *

```java
// ❌
@Select("SELECT * FROM deal_group WHERE id = #{id}")
DealGroup selectById(Long id);

// ✅ 只取需要的字段
@Select("SELECT id, title, price, status FROM deal_group WHERE id = #{id}")
DealGroupDTO selectBasicById(Long id);
```

### CR:DB-04 批量写入

```java
// ❌ 循环内逐条 INSERT
for (OrderItem item : items) {
    orderItemMapper.insert(item);  // N 次 round-trip
}

// ✅ MyBatis foreach 批量 INSERT
// <insert id="batchInsert">
//   INSERT INTO order_item (order_id, sku_id, quantity)
//   VALUES
//   <foreach collection="list" item="item" separator=",">
//     (#{item.orderId}, #{item.skuId}, #{item.quantity})
//   </foreach>
// </insert>
orderItemMapper.batchInsert(items);
```

### CR:DB-05 大表查询加 LIMIT

```java
// ❌ 无 LIMIT 的大表查询
@Select("SELECT * FROM order_log WHERE create_time > #{startTime}")
List<OrderLog> selectByTime(Date startTime);  // 可能返回百万行

// ✅ 分页 + 游标
@Select("SELECT * FROM order_log WHERE create_time > #{startTime} AND id > #{lastId} ORDER BY id LIMIT 500")
List<OrderLog> selectByTimePaged(Date startTime, Long lastId);
```

### CR:DB-06 事务范围最小化

```java
// ❌ 事务内包含 RPC 调用
@Transactional
public void createOrder(OrderRequest req) {
    orderMapper.insert(order);
    inventoryRpc.deduct(req.getSkuId(), req.getQuantity());  // RPC 超时会导致事务长时间持有连接
    paymentRpc.create(order.getId());  // 另一个 RPC
}

// ✅ RPC 移到事务外
public void createOrder(OrderRequest req) {
    // 1. 先调 RPC（事务外）
    inventoryRpc.deduct(req.getSkuId(), req.getQuantity());

    // 2. 只有 DB 操作在事务内
    createOrderInTransaction(order);

    // 3. 后续 RPC（事务外）
    paymentRpc.create(order.getId());
}

@Transactional
public void createOrderInTransaction(Order order) {
    orderMapper.insert(order);
    orderItemMapper.batchInsert(order.getItems());
}
```

---

## 3.2 缓存使用（CACHE）

### CR:CACHE-01 高频读数据加缓存

```java
// ❌ 每次请求都查 DB
public ShopInfo getShopInfo(Long shopId) {
    return shopMapper.selectById(shopId);  // 高频接口，QPS 5000+
}

// ✅ 加 Squirrel 缓存
public ShopInfo getShopInfo(Long shopId) {
    String key = "shop:info:" + shopId;
    ShopInfo cached = squirrelClient.get(key, ShopInfo.class);
    if (cached != null) return cached;

    ShopInfo info = shopMapper.selectById(shopId);
    if (info != null) {
        squirrelClient.set(key, info, 300);  // TTL 5min
    }
    return info;
}
```

### CR:CACHE-02 缓存必须设 TTL

```java
// ❌ 无过期时间
squirrelClient.set(key, value);  // 永不过期，数据变更后长期不一致

// ✅ 根据业务场景设合理 TTL
squirrelClient.set(key, value, 300);     // 读多写少：5min
squirrelClient.set(key, value, 30);      // 准实时：30s
squirrelClient.set(key, value, 86400);   // 静态配置：1day
```

### CR:CACHE-03 缓存穿透防护

```java
// ❌ 查不到直接返回，不缓存空值
public DealInfo getDeal(Long dealId) {
    DealInfo cached = cache.get(key);
    if (cached != null) return cached;
    DealInfo info = dealMapper.selectById(dealId);
    if (info != null) {
        cache.set(key, info, 300);
    }
    return info;  // 恶意请求不存在的 ID，每次都穿透到 DB
}

// ✅ 缓存空值（短 TTL）
public DealInfo getDeal(Long dealId) {
    DealInfo cached = cache.get(key);
    if (cached != null) return cached == NULL_PLACEHOLDER ? null : cached;

    DealInfo info = dealMapper.selectById(dealId);
    if (info != null) {
        cache.set(key, info, 300);
    } else {
        cache.set(key, NULL_PLACEHOLDER, 60);  // 空值缓存 60s
    }
    return info;
}
```

### CR:CACHE-04 缓存击穿防护

```java
// ✅ singleflight 模式（只允许一个线程回源）
private final Map<String, CompletableFuture<Object>> flights = new ConcurrentHashMap<>();

public Object getWithSingleFlight(String key, Supplier<Object> loader) {
    Object cached = cache.get(key);
    if (cached != null) return cached;

    CompletableFuture<Object> future = flights.computeIfAbsent(key, k ->
        CompletableFuture.supplyAsync(() -> {
            Object value = loader.get();
            cache.set(key, value, 300);
            return value;
        }).whenComplete((v, e) -> flights.remove(key))
    );
    return future.join();
}
```

### CR:CACHE-05 缓存雪崩防护

```java
// ❌ 所有 key 同一 TTL
cache.set("shop:" + shopId, info, 300);  // 批量刷新时同时过期

// ✅ TTL 加随机抖动
int baseTtl = 300;
int jitter = ThreadLocalRandom.current().nextInt(0, 60);  // ±20%
cache.set("shop:" + shopId, info, baseTtl + jitter);
```

---

## 3.3 集合与数据结构（COLL）

### CR:COLL-01 字符串拼接

```java
// ❌ 循环内 += 拼接（每次创建新 String 对象，O(n²) 复杂度）
String result = "";
for (String item : items) {
    result += item + ",";
}

// ✅ StringBuilder
StringBuilder sb = new StringBuilder(items.size() * 16);
for (String item : items) {
    sb.append(item).append(",");
}

// ✅ 或 String.join（JDK 8+）
String result = String.join(",", items);
```

### CR:COLL-02 / CR:COLL-03 预分配容量

```java
// ❌
List<UserDTO> list = new ArrayList<>();           // 默认 10，扩容多次
Map<Long, User> map = new HashMap<>();            // 默认 16

// ✅
List<UserDTO> list = new ArrayList<>(users.size());
Map<Long, User> map = new HashMap<>(users.size() * 4 / 3 + 1);  // 避免 rehash
```

### CR:COLL-04 频繁查找用 Set

```java
// ❌ List.contains() 是 O(n)
List<Long> blacklist = loadBlacklist();
if (blacklist.contains(userId)) { ... }  // 每次 O(n) 遍历

// ✅ Set.contains() 是 O(1)
Set<Long> blacklist = new HashSet<>(loadBlacklist());
if (blacklist.contains(userId)) { ... }
```

### CR:COLL-06 小集合不要 parallelStream

```java
// ❌ 50 个元素用并行流（ForkJoinPool 调度开销 > 计算收益）
List<String> names = users.stream()
    .parallel()
    .map(User::getName)
    .collect(Collectors.toList());

// ✅ 小集合用顺序流
List<String> names = users.stream()
    .map(User::getName)
    .collect(Collectors.toList());
```

**经验阈值：** 元素 < 10000 且计算不密集时，顺序流通常更快。

---

## 3.4 RPC 与 IO（RPC）

### CR:RPC-01 串行 → 并行

```java
// ❌ 串行调 3 个 RPC，总耗时 = RT1 + RT2 + RT3
UserInfo user = userRpc.getUser(uid);
ShopInfo shop = shopRpc.getShop(shopId);
DealInfo deal = dealRpc.getDeal(dealId);

// ✅ 并行调用，总耗时 = max(RT1, RT2, RT3)
CompletableFuture<UserInfo> userFuture = CompletableFuture.supplyAsync(() -> userRpc.getUser(uid));
CompletableFuture<ShopInfo> shopFuture = CompletableFuture.supplyAsync(() -> shopRpc.getShop(shopId));
CompletableFuture<DealInfo> dealFuture = CompletableFuture.supplyAsync(() -> dealRpc.getDeal(dealId));
CompletableFuture.allOf(userFuture, shopFuture, dealFuture).join();
```

### CR:RPC-02 循环内 RPC → 批量接口

```java
// ❌
for (Long shopId : shopIds) {
    ShopInfo info = shopRpc.getShop(shopId);  // N 次 RPC
}

// ✅
Map<Long, ShopInfo> shopMap = shopRpc.batchGetShops(shopIds);  // 1 次 RPC
```

### CR:RPC-04 日志精简

```java
// ❌ 打印完整请求/响应（可能含大 List，日志体积爆炸）
log.info("rpc request={}, response={}", request, response);

// ✅ 只打关键字段
log.info("getShop shopId={}, status={}, rt={}ms", shopId, response.getStatus(), cost);
// 异常时才打详情
log.error("getShop failed, shopId={}, request={}", shopId, request, e);
```

---

## 3.5 对象与内存（MEM）

### CR:MEM-01 循环外复用不可变对象

```java
// ❌ 循环内重复创建
for (Order order : orders) {
    SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd");  // 每次 new
    order.setDateStr(sdf.format(order.getCreateTime()));
}

// ✅ 提到循环外（或用 static final DateTimeFormatter）
private static final DateTimeFormatter DTF = DateTimeFormatter.ofPattern("yyyy-MM-dd");
for (Order order : orders) {
    order.setDateStr(DTF.format(order.getCreateTime()));
}
```

### CR:MEM-03 避免热路径自动装箱

```java
// ❌ 自动装箱产生大量临时 Integer 对象
long sum = 0;
for (Integer price : priceList) {  // 拆箱
    sum += price;                   // 可能 NPE（如果 price 为 null）
}

// ✅ 使用 IntStream
int sum = priceList.stream()
    .filter(Objects::nonNull)
    .mapToInt(Integer::intValue)
    .sum();
```

### CR:MEM-04 正则 Pattern 复用

```java
// ❌ 循环内编译正则（compile 开销大）
for (String line : lines) {
    if (Pattern.matches("\\d{4}-\\d{2}-\\d{2}", line)) { ... }
}

// ✅ 预编译为 static final
private static final Pattern DATE_PATTERN = Pattern.compile("\\d{4}-\\d{2}-\\d{2}");
for (String line : lines) {
    if (DATE_PATTERN.matcher(line).matches()) { ... }
}
```

---

## 3.6 JDK 17+ 现代化（JDK）

### CR:JDK-01 Pattern Matching for instanceof

```java
// ❌ JDK 16 以前
if (obj instanceof String) {
    String s = (String) obj;
    return s.length();
}

// ✅ JDK 16+
if (obj instanceof String s) {
    return s.length();
}
```

### CR:JDK-03 Record 替代数据类

```java
// ❌ 传统 POJO（50 行 boilerplate）
public class UserDTO {
    private final String name;
    private final int age;
    // constructor, getters, equals, hashCode, toString...
}

// ✅ Record（1 行）
public record UserDTO(String name, int age) {}
```

### CR:JDK-05 Virtual Threads（JDK 21+）

```java
// ❌ 平台线程池（有限线程数，IO 密集时容易耗尽）
ExecutorService executor = Executors.newFixedThreadPool(200);

// ✅ 虚拟线程（IO 密集场景，线程数不再是瓶颈）
ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
```

**适用场景：** IO 密集型（RPC、数据库查询），不适合 CPU 密集型计算。

---

*文件版本：v1.0 | 对应 SKILL.md P3 层 | 27 条检查规则*
