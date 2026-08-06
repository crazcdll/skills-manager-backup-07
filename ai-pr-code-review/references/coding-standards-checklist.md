# P2 — 规范与架构 Checklist

> 四层模型第二层：代码规范、架构设计、可维护性审查。
> 发现的问题标记为 🟡 P2，建议本 MR 修复或创建跟进任务。
> 本规范结合美团到店实际研发场景，侧重**可维护性、可测试性、防腐化**。

---

## 1. SOLID 原则 & 设计模式

| 编号 | 检查点 | 反模式 | 正确做法 |
|------|--------|--------|---------|
| CR:SOLID-01 | **单一职责（SRP）** | 一个 Service 同时做校验、业务、发 MQ、写日志 | 拆分：Validator / DomainService / EventPublisher |
| CR:SOLID-02 | **开闭原则（OCP）** | switch-case 判断业务类型（每加一个类型改一遍） | 策略模式 + Spring 容器注入 Map\<Type, Handler\> |
| CR:SOLID-03 | **里氏替换（LSP）** | 子类重写方法抛出父类未声明的异常 | 子类行为是父类契约的子集 |
| CR:SOLID-04 | **接口隔离（ISP）** | 一个 Repository 接口 30 个方法，实现类只用 5 个 | 按聚合根/场景拆接口 |
| CR:SOLID-05 | **依赖倒转（DIP）** | Service 直接 new XxxDaoImpl() | 依赖 Repository 接口，Spring 注入实现 |

### 高频场景：策略模式替代 if-else

```java
// ❌ 每加一种商品类型都要改这个方法
public void process(Deal deal) {
    if (deal.getType() == DealType.NORMAL) {
        // 200 行普通商品逻辑
    } else if (deal.getType() == DealType.GROUP) {
        // 150 行团购商品逻辑
    } else if (deal.getType() == DealType.PACKAGE) {
        // 180 行套餐逻辑
    }
}

// ✅ 策略模式 — 新增类型只加一个 Handler 类
@Component
public class DealProcessorFactory {
    private final Map<DealType, DealProcessor> processorMap;

    public DealProcessorFactory(List<DealProcessor> processors) {
        this.processorMap = processors.stream()
            .collect(Collectors.toMap(DealProcessor::supportType, Function.identity()));
    }

    public DealProcessor get(DealType type) {
        return Optional.ofNullable(processorMap.get(type))
            .orElseThrow(() -> new UnsupportedDealTypeException(type));
    }
}
```

---

## 2. 命名规范

| 编号 | 检查点 | 规则 | 美团场景示例 |
|------|--------|------|-------------|
| CR:NAME-01 | **类名 UpperCamelCase** | 不缩写，语义完整 | ✅ `DealPublishService` ❌ `DPSvc` |
| CR:NAME-02 | **方法名 lowerCamelCase** | 动词开头，CRUD 用 `create/get/update/delete` | ✅ `getDealById()` ❌ `deal()` |
| CR:NAME-03 | **常量 UPPER_SNAKE** | 全大写下划线分隔 | `MAX_BATCH_SIZE`, `DEFAULT_PAGE_SIZE` |
| CR:NAME-04 | **布尔变量不加 is** | POJO 规范，Jackson/MyBatis 序列化兼容 | ❌ `isDeleted` → ✅ `deleted` |
| CR:NAME-05 | **避免无意义缩写** | 团队共识缩写除外（DTO/VO/RPC/MQ/POI） | ❌ `calcDlPrc` → ✅ `calculateDealPrice` |
| CR:NAME-06 | **包名规范** | `com.meituan.{bu}.{app}.{layer}` | `com.meituan.supply.deal.service.impl` |
| CR:NAME-07 | **领域术语一致** | 同一概念全仓库用同一个词 | Deal/商品不要混用 product/goods/deal/item |
| CR:NAME-08 | **双平台 ID 字段命名** | 双平台（mt/dp）ID 字段建议加前缀（`mtShopId`/`dpShopId`），**缺失前缀仅为 P2 规范建议，不得升级为 P0/P1** | ✅ `mtPoiId`/`dpPoiId` ⚠️ `poiId`（需注释说明体系） |

### 美团到店高频领域词汇对照

| 领域概念 | 统一命名 | 禁止混用 |
|---------|---------|---------|
| 商品/团购 | `Deal` | product, goods, item |
| 门店 | `Poi` / `Shop` | store, branch |
| 商家 | `Merchant` | vendor, seller, provider |
| 库存 | `Stock` | inventory, quantity |
| 上下架 | `Shelf` (上架 putOnShelf / 下架 putOffShelf) | online/offline, enable/disable |
| SKU | `Sku` | spec, variant |
| 供应商 | `Supplier` | provider, vendor |

---

## 3. 代码风格与圈复杂度

| 编号 | 检查点 | 阈值 | 说明 |
|------|--------|------|------|
| CR:STYLE-01 | **方法行数** | ≤50 行（硬限 80） | 超过拆分为有命名的私有方法 |
| CR:STYLE-02 | **类行数** | ≤300 行（硬限 500） | 超过按职责拆分 |
| CR:STYLE-03 | **参数数量** | ≤5 个 | 超过封装为 Request/Command 对象 |
| CR:STYLE-04 | **嵌套深度** | ≤3 层 | 卫语句提前 return；提取方法 |
| CR:STYLE-05 | **圈复杂度** | ≤10 | 每个 if/for/case/catch/&& 加 1，超标必拆 |

```java
// ❌ 嵌套 4 层，圈复杂度高
public Result processDeal(DealRequest request) {
    if (request != null) {
        if (request.getDealId() != null) {
            Deal deal = dealDao.getById(request.getDealId());
            if (deal != null) {
                if (deal.getStatus() == DealStatus.ACTIVE) {
                    // 真正的业务逻辑埋在第 4 层...
                }
            }
        }
    }
    return Result.fail("参数错误");
}

// ✅ 卫语句拍平
public Result processDeal(DealRequest request) {
    if (request == null || request.getDealId() == null) {
        return Result.fail("参数缺失");
    }
    Deal deal = dealDao.getById(request.getDealId());
    if (deal == null) {
        return Result.fail("商品不存在");
    }
    if (deal.getStatus() != DealStatus.ACTIVE) {
        return Result.fail("商品状态不可操作");
    }
    // 业务逻辑在第 0 层
    return doProcess(deal);
}
```

---

## 4. 魔法值与枚举

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:ENUM-01 | **禁止魔法值** | 所有业务状态/类型用枚举或常量 | ❌ `if (status == 3)` → ✅ `DealStatus.PUBLISHED` |
| CR:ENUM-02 | **枚举持久化** | 数据库存 code(int)，不存 name(String) | 枚举改名不影响数据 |
| CR:ENUM-03 | **枚举转换安全** | 提供 `fromCode()` 方法，处理未知值 | 返回 UNKNOWN 或抛明确异常，不返回 null |
| CR:ENUM-04 | **常量类归属** | 常量定义在最相关的类中，不堆到一个大 Constants 类 | `DealConstants.MAX_TITLE_LENGTH` 而非 `Constants.XXX` |

```java
// ✅ 安全的枚举转换
public enum DealStatus {
    DRAFT(0), PUBLISHED(1), OFFLINE(2);

    private static final Map<Integer, DealStatus> CODE_MAP =
        Arrays.stream(values()).collect(Collectors.toMap(DealStatus::getCode, Function.identity()));

    public static DealStatus fromCode(int code) {
        DealStatus status = CODE_MAP.get(code);
        if (status == null) {
            throw new IllegalArgumentException("Unknown DealStatus code: " + code);
        }
        return status;
    }
}
```

---

## 5. 异常处理规范

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:EX-01 | **领域异常体系** | 按模块建异常基类 → 具体异常 | `SupplyException` → `DealException` → `DealNotFoundException` |
| CR:EX-02 | **异常信息含上下文** | 带关键业务 ID | `"Deal not found, dealId=%d, merchantId=%d"` |
| CR:EX-03 | **禁止空 catch** | catch 后必须日志或重抛 | ❌ `catch(Exception e) {}` — P1 也会审查 |
| CR:EX-04 | **catch 粒度** | 只 catch 预期异常 | ❌ `catch(Exception)` 兜底 → ✅ catch 具体异常分别处理 |
| CR:EX-05 | **异常跨层转换** | DAO 异常不透传到 Controller | `SQLException` → `DataAccessException` → 业务异常 |
| CR:EX-06 | **try-with-resources** | IO 资源必须自动关闭 | InputStream, Connection, ResultSet |
| CR:EX-07 | **RPC 异常降级** | 调用外部 RPC 失败时有降级策略 | 返回默认值 / 走缓存 / 熔断，而非直接抛异常给上层 |

```java
// ✅ 美团场景：RPC 调用异常降级
public DealExtra getDealExtra(long dealId) {
    try {
        TResult<DealExtra> result = dealExtraThriftService.getById(dealId);
        if (result == null || result.getCode() != 0) {
            log.warn("getDealExtra failed, dealId={}, result={}", dealId, result);
            Cat.logEvent("DealExtra_Degrade", String.valueOf(dealId));
            return DealExtra.empty();  // 降级返回空对象
        }
        return result.getData();
    } catch (Exception e) {
        log.error("getDealExtra exception, dealId={}", dealId, e);
        Cat.logError(e);
        return DealExtra.empty();
    }
}
```

---

## 6. 返回类型与 Optional

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:RET-01 | **不返回 null 集合** | 返回 `Collections.emptyList()` | 调用方省去 `!= null` 判断 |
| CR:RET-02 | **Optional 表示可能缺失** | 查询单个对象可能为空时返回 Optional | `Optional<Deal> findById(long id)` |
| CR:RET-03 | **禁止 Optional 作参数** | Optional 只用于返回值 | 参数缺失用方法重载或 @Nullable 标注 |
| CR:RET-04 | **统一 Result 包装** | 对外 API 一律 `Result<T>` | 含 code + message + data，前端统一解析 |
| CR:RET-05 | **分页结果** | 分页返回 `PageResult<T>` | 包含 total / list / pageNo / pageSize |
| CR:RET-06 | **void 方法语义** | void 方法应通过异常表示失败，不用返回 boolean | ❌ `boolean updateDeal()` → ✅ `void updateDeal() throws XxxException` |

---

## 7. Lambda / Stream 规范

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:LAM-01 | **Lambda ≤3 行** | 超过提取为方法引用 | 可读性 + 可复用 + 可单测 |
| CR:LAM-02 | **禁止嵌套 Lambda** | forEach 内不再嵌套 Lambda | 提取为独立方法 |
| CR:LAM-03 | **Stream 内不 catch** | 异常处理提到方法外 | 保持 Stream 管道清爽 |
| CR:LAM-04 | **禁止 Stream 副作用** | 不在 map/filter 中修改外部变量 | ❌ `stream().peek(x -> map.put(...))` |
| CR:LAM-05 | **小集合不 parallel** | <1000 元素不用 `parallelStream()` | 调度开销大于收益（P3 也会审查） |
| CR:LAM-06 | **collect 要指定类型** | 需要特定 Map/Set 实现时显式指定 | `toMap(... , LinkedHashMap::new)` 保序 |

---

## 8. 架构分层（DDD / 六边形）

| 编号 | 检查点 | 规则 | 典型违规 |
|------|--------|------|---------|
| CR:ARCH-01 | **domain 不依赖 infra** | domain 包不 import dao/rpc/mq 包 | domain 层直接调 MyBatis Mapper → 加 Repository 接口 |
| CR:ARCH-02 | **Controller 是薄层** | 只做参数校验 + 调 Service + 返回 | ❌ Controller 里写 50 行业务逻辑 |
| CR:ARCH-03 | **Service 不直接 SQL** | 通过 Repository 接口 | ❌ Service 里 `@Select` 写 SQL |
| CR:ARCH-04 | **跨模块走 API** | 模块间通过 Thrift/HTTP API | ❌ 直接 import 另一个模块的 internal 类 |
| CR:ARCH-05 | **防腐层** | 外部依赖（第三方 API、旧系统）包一层 Adapter | 直接散落在业务代码中 → 改接口要全局改 |
| CR:ARCH-06 | **配置外置** | 环境相关值放 Lion/配置中心 | ❌ 硬编码 IP/端口/超时值 |
| CR:ARCH-07 | **领域事件解耦** | 跨聚合的副作用用事件（MQ/EventBus） | ❌ 商品上架 Service 里直接调库存/搜索/营销 |

```java
// ❌ 商品上架 Service 直接调用 N 个下游 — 强耦合
public void publishDeal(long dealId) {
    Deal deal = dealRepository.getById(dealId);
    deal.publish();
    dealRepository.save(deal);
    stockService.initStock(dealId);        // 直接耦合
    searchService.indexDeal(dealId);        // 直接耦合
    marketingService.notifyNewDeal(dealId); // 直接耦合
}

// ✅ 领域事件解耦 — 上架只管上架，副作用由事件驱动
public void publishDeal(long dealId) {
    Deal deal = dealRepository.getById(dealId);
    deal.publish();
    dealRepository.save(deal);
    eventPublisher.publish(new DealPublishedEvent(dealId));
    // 库存/搜索/营销各自监听事件处理
}
```

---

## 9. Spring Boot 专项

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:SPRING-TX-01 | **事务传播级别** | 明确指定 propagation；只读用 `readOnly=true` | 默认 REQUIRED 可能引发嵌套事务问题 |
| CR:SPRING-TX-02 | **事务范围最小化** | @Transactional 不包含 RPC/MQ/HTTP 调用 | 长事务 → 连接池耗尽 → 服务不可用（P1 级） |
| CR:SPRING-TX-03 | **rollbackFor** | 显式 `rollbackFor = Exception.class` | 默认只回滚 unchecked exception |
| CR:SPRING-TX-04 | **事务自调用失效** | 同类内 A() 调 B()，B 的 @Transactional 不生效 | 提取到另一个 Bean 或用 AopContext |
| CR:SPRING-DI-01 | **构造器注入** | 禁止 @Autowired 字段注入 | 不可变 + 可测试 + 必需依赖明确 |
| CR:SPRING-DI-02 | **循环依赖** | 不允许循环依赖 | Spring Boot 2.6+ 默认禁止，引入事件/中间层解耦 |
| CR:SPRING-SCOPE-01 | **Bean 线程安全** | 单例 Bean 不持有可变实例变量 | 用 ThreadLocal 或方法参数传递 |
| CR:SPRING-ASYNC-01 | **@Async 线程池** | 必须指定自定义线程池 Bean | 默认 SimpleAsyncTaskExecutor 每次 new Thread |
| CR:SPRING-CONFIG-01 | **@Value 有默认值** | `@Value("${key:default}")` | 配置中心故障时服务仍能启动 |
| CR:SPRING-CONFIG-02 | **@ConfigurationProperties** | 多个相关配置用类型安全绑定 | 类型校验 + IDE 补全 + 集中管理 |
| CR:SPRING-SCHED-01 | **@Scheduled 异常处理** | 定时任务内 try-catch 全包 | 未捕获异常导致后续调度停止 |
| CR:SPRING-INIT-01 | **初始化顺序** | @PostConstruct 不做重操作 | 阻塞应用启动；重操作放 ApplicationRunner + 异步 |

---

## 10. MyBatis / 数据访问规范

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:MBT-01 | **禁止 SELECT *** | 只查需要的字段 | 表加字段不影响既有查询；减少传输量 |
| CR:MBT-02 | **XML 与注解不混用** | 同一 Mapper 统一用 XML 或注解 | 维护一致性 |
| CR:MBT-03 | **ResultMap 复用** | 公共映射提取为 BaseResultMap | 减少重复定义 |
| CR:MBT-04 | **动态 SQL 安全** | `${}` 禁用于用户输入（SQL 注入） | 用户输入必须用 `#{}` |
| CR:MBT-05 | **批量操作 foreach** | 大量 INSERT/UPDATE 用 `<foreach>` 批量 | 单条循环 → 批量 DML（P3 也关注性能） |
| CR:MBT-06 | **分页必须 LIMIT** | 查询列表必须带分页参数 | 防止全表扫描 |
| CR:MBT-07 | **逻辑删除一致性** | 全表统一逻辑删除字段命名（`deleted`） | 不要一个表 `is_del`，另一个 `status` |
| CR:MBT-08 | **索引覆盖** | WHERE 条件字段必须有索引 | 新增查询时 DBA 确认索引是否需要新建 |

---

## 11. 日志规范

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:LOG-01 | **占位符不拼接** | `log.info("dealId={}", id)` | ❌ `"dealId=" + id` — 性能损耗 |
| CR:LOG-02 | **日志级别正确** | ERROR=需告警, WARN=可恢复, INFO=关键流程, DEBUG=调试 | ❌ 所有日志都 INFO |
| CR:LOG-03 | **关键流程有日志** | 入口/出口/分支/异常 四个点打日志 | 线上排查问题靠日志链路 |
| CR:LOG-04 | **日志含业务 ID** | traceId + 业务主键（dealId/orderId/poiId） | 快速定位问题数据 |
| CR:LOG-05 | **异常打全栈** | `log.error("msg", e)` 传异常对象 | ❌ `log.error(e.getMessage())` 丢堆栈 |
| CR:LOG-06 | **敏感信息脱敏** | 手机号/身份证/token 不能明文打印 | `138****8888`（与 P1 CR:SEC-11 呼应） |
| CR:LOG-07 | **Cat 埋点** | 核心链路打 Cat Transaction/Event | 美团标准监控手段，问题溯源必备 |

```java
// ✅ 美团标准日志 + Cat 埋点
Transaction t = Cat.newTransaction("DealService", "publishDeal");
try {
    log.info("publishDeal start, dealId={}, operator={}", dealId, operator);
    Deal deal = dealRepository.getById(dealId);
    // ... 业务逻辑
    log.info("publishDeal success, dealId={}, cost={}ms", dealId, sw.elapsed());
    t.setStatus(Transaction.SUCCESS);
} catch (Exception e) {
    log.error("publishDeal failed, dealId={}", dealId, e);
    Cat.logError(e);
    t.setStatus(e);
    throw e;
} finally {
    t.complete();
}
```

---

## 12. 单元测试

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:TEST-01 | **新增公共方法必须有测试** | 核心逻辑覆盖率 ≥80% | PR 中新增 Service 方法须附带测试 |
| CR:TEST-02 | **测试命名** | `方法名_场景_预期结果` | `publishDeal_dealNotFound_throwsException` |
| CR:TEST-03 | **断言明确** | 用 `assertEquals/assertThrows` | ❌ `assertTrue(result != null)` |
| CR:TEST-04 | **Mock 外部依赖** | Mock RPC/DB/MQ，不 mock 被测类内部 | 测试行为不测实现 |
| CR:TEST-05 | **覆盖边界** | null、空集合、边界值、异常路径 | 正常 + 异常 + 边界 三条路径 |
| CR:TEST-06 | **测试独立性** | 测试间不依赖执行顺序 | 不共享可变状态 |
| CR:TEST-07 | **不测 private** | 通过公共方法间接覆盖 private | 需要测 private → 说明该方法应该提取为独立类 |

---

## 13. 并发与线程安全

| 编号 | 检查点 | 规则 | 说明 |
|------|--------|------|------|
| CR:CONC-01 | **单例 Bean 无状态** | Spring 单例 Bean 不持有可变成员变量 | ❌ `private int count = 0;` 在 Service 中 |
| CR:CONC-02 | **SimpleDateFormat 不共享** | SDF 非线程安全 | 用 DateTimeFormatter（线程安全）或 ThreadLocal |
| CR:CONC-03 | **double-check locking** | 懒加载单例必须 volatile + DCL | 不加 volatile 有指令重排风险 |
| CR:CONC-04 | **线程池参数** | 自定义线程池，拒绝 Executors.newXxx | `newFixedThreadPool` 用无界队列会 OOM |
| CR:CONC-05 | **HashMap 并发写** | 多线程写 HashMap → ConcurrentHashMap | 否则死循环（JDK7）或数据丢失（JDK8+） |
| CR:CONC-06 | **锁粒度最小化** | synchronized 锁住最小代码块 | 不要锁整个方法，只锁临界区 |
| CR:CONC-07 | **禁用 DiscardPolicy/DiscardOldestPolicy** | 任务被丢弃后 FutureTask 状态仍为 NEW | `future.get()` 永久阻塞；如必须使用需自定义策略 + get 设超时 |
| CR:CONC-08 | **在线服务禁用 CallerRunsPolicy** | 被拒任务在调用线程执行 → RT 不可控 | 有父子任务依赖时可能死锁 |
| CR:CONC-09 | **Runnable 任务内部处理异常** | 未捕获异常 → 线程终止 → 线程池缩水 | 用 Callable 替代，或设置 UncaughtExceptionHandler |
| CR:CONC-10 | **自定义线程名称** | 默认 `pool-1-thread-1` 无业务含义 | 用 ThreadFactoryBuilder 设 `setNameFormat("biz-%d")` |

```java
// ❌ Executors 的隐患
ExecutorService pool = Executors.newFixedThreadPool(10);
// 内部用 LinkedBlockingQueue（无界队列），任务堆积 → OOM

// ✅ 自定义线程池
ThreadPoolExecutor pool = new ThreadPoolExecutor(
    10, 20, 60, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),
    new ThreadFactoryBuilder().setNameFormat("deal-publish-%d").build(),
    new ThreadPoolExecutor.CallerRunsPolicy()  // 拒绝策略：调用方执行
);
```

---

## 14. 美团中间件使用规范

| 编号 | 中间件 | 检查点 | 说明 |
|------|--------|--------|------|
| CR:MW-01 | **Mafka** | 消费幂等（业务 ID + 去重表/Redis） | 消息至少投递一次，消费端必须幂等 |
| CR:MW-02 | **Mafka** | Producer 发送失败有重试 + 告警 | 不能 fire-and-forget |
| CR:MW-03 | **Squirrel** | 大 Value 拆分（>10KB 压缩或拆 key） | 大 Value 影响 Redis 集群性能 |
| CR:MW-04 | **Squirrel** | key 命名 `{appkey}:{业务}:{id}` | 便于运维排查；避免 key 冲突 |
| CR:MW-05 | **Lion** | 动态配置有默认值兜底 | Lion 故障时不影响服务启动 |
| CR:MW-06 | **Zebra** | 读写分离正确标注 | 写操作走主库，读操作走从库 |
| CR:MW-07 | **Cat** | 核心链路有 Transaction 埋点 | 缺少埋点 = 线上黑盒，出问题无法排查 |
| CR:MW-08 | **Crane** | 定时任务有幂等保护 | 重复调度不产生脏数据 |
| CR:MW-09 | **Lion(@MtConfig)** | @MtConfig 字段**必须** static | 非 static → Lion 配置不生效（COE-278569） |
| CR:MW-10 | **MDP(@MdpConfig)** | @MdpConfig 字段**禁止** static | static → 注入失败，字段为 null |
| CR:MW-11 | **MDP(@MdpConfig)** | @MdpConfig key 不加 appkey 前缀 | 框架自动拼接，手动加会导致 key 不匹配 |
| CR:MW-12 | **MDP(@MdpConfig)** | @MdpConfig 默认值不能为空字符串 | 空字符串默认值会导致解析异常 |
| CR:MW-13 | **MDP(@MdpConfig)** | @MdpConfig 所在类必须是 Spring Bean | 非 Bean 类注解不生效，配置无法注入 |
| CR:MW-14 | **MDP(@MdpConfig)** | 构造方法中禁止使用 @MdpConfig 字段 | 构造时尚未注入，值为 null |
| CR:MW-15 | **MDP(@MdpConfig)** | AOP 代理类访问 @MdpConfig 必须走 getter | 直接访问字段绕过代理，获取未注入值 |
| CR:MW-16 | **Lion(@MtConfig)** | @MtConfig 只支持 6 种基本类型 | 不支持 List/Set/Map，需自定义 Converter |
| CR:MW-17 | **Lion** | 配置加载模式禁止 mcc-lion | 已废弃，会触发两次监听器回调 |
| CR:MW-18 | **MDP(@MdpConfig)** | 复杂类型必须用具体实现类+泛型 | 不能用 Map/List 接口，不能用裸类型 |
| CR:MW-19 | **Rhino** | 必须使用 Rhino 动态线程池 | 原生 ThreadPoolExecutor 不支持运行时动态调参和实时监控 |

---

## 审查输出格式

```
🟡 P2 | {编号} | {文件}:{行号}
问题：{具体描述}
建议：{修改方案 + 代码示例（如需要）}
```

示例：
```
🟡 P2 | CR:ARCH-07 | DealPublishService.java:45
问题：商品上架后直接调用 stockService/searchService/marketingService，强耦合 3 个下游
建议：发布 DealPublishedEvent 领域事件，各下游监听事件独立处理，解耦后上架逻辑不受下游变更影响

🟡 P2 | CR:CONC-04 | TaskExecutorConfig.java:12
问题：使用 Executors.newFixedThreadPool(20)，内部无界队列任务堆积会 OOM
建议：改用 new ThreadPoolExecutor(...)，指定有界队列 + CallerRunsPolicy 拒绝策略

🟡 P2 | CR:MW-01 | DealChange