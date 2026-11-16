# P2 规范与架构 — 规则索引

> 本文件是 P2 层的规则索引。每条规则只保留编号、判定逻辑、触发关键词和对应完整规则文件路径。
> 完整规则定义和代码示例见 `checklists/mt-java-coding-standards/`。

> 🚫 **禁止输出纯风格问题**：Import 风格、花括号风格、空行/空格 — 一律不报
> 🚫 **禁止自创规则编号**：只能使用已定义的规则编号

## 1. SOLID 原则 & 设计模式

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| SOLID-01 | 单一职责（SRP） | 一个 Service 同时做校验、业务、发 MQ、写日志 | Service 类过长 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| SOLID-02 | 开闭原则（OCP） | switch-case 判断业务类型，每加类型改一遍 | `switch` + `case` | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| SOLID-03 | 里氏替换（LSP） | 子类重写方法抛出父类未声明的异常 | `@Override` + `throws` | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| SOLID-04 | 接口隔离（ISP） | 一个接口 30 个方法，实现类只用 5 个 | 接口方法数 > 20 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| SOLID-05 | 依赖倒转（DIP） | Service 直接 new XxxDaoImpl() | `new XxxDao` | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |

## 2. 命名规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| NAME-01 | 类名 UpperCamelCase | 不缩写，语义完整 | 类名首字母小写 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-02 | 方法名 lowerCamelCase | 动词开头，CRUD 用 create/get/update/delete | 方法名首字母大写 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-03 | 常量 UPPER_SNAKE | 全大写下划线分隔 | 常量名小写 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-04 | 布尔变量不加 is | POJO 规范，Jackson/MyBatis 序列化兼容 | `isDeleted`, `isActive` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-05 | 避免无意义缩写 | 团队共识缩写除外 | `calcDlPrc` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-06 | 包名规范 | com.meituan.{bu}.{app}.{layer} | 包名不规范 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-07 | 领域术语一致 | 同一概念全仓库用同一个词 | product/goods 混用 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| NAME-08 | 双平台 ID 字段命名 | 双平台 ID 字段建议加前缀 | `poiId` 无前缀 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |

## 3. 代码风格与圈复杂度

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| STYLE-01 | 方法行数 ≤50（硬限 80） | 超过拆分为有命名的私有方法 | 方法过长 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| STYLE-02 | 类行数 ≤300（硬限 500） | 超过按职责拆分 | 类过长 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| STYLE-03 | 参数数量 ≤5 | 超过封装为 Request/Command 对象 | 方法参数 > 5 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| STYLE-04 | 嵌套深度 ≤3 层 | 卫语句提前 return；提取方法 | 嵌套 > 3 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| STYLE-05 | 圈复杂度 ≤10 | 每个 if/for/case/catch/&& 加 1 | if/for 嵌套 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |

## 4. 魔法值与枚举

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| ENUM-01 | 禁止魔法值 | 业务状态/类型用枚举或常量 | `if (status == 3)` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| ENUM-02 | 枚举持久化 | 数据库存 code(int），不存 name(String) | 枚举存 name | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| ENUM-03 | 枚举转换安全 | 提供 fromCode() 方法，处理未知值 | 枚举无 fromCode | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| ENUM-04 | 常量类归属 | 常量定义在最相关的类中 | `Constants.XXX` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |

## 5. 异常处理规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| EX-01 | 领域异常体系 | 按模块建异常基类 → 具体异常 | `new RuntimeException` | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-02 | 异常信息含上下文 | 带关键业务 ID | 异常消息无业务参数 | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-03 | 禁止空 catch | catch 后必须日志或重抛 | `catch(Exception e) {}` | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-04 | catch 粒度 | 只 catch 预期异常 | `catch(Exception)` 兜底 | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-05 | 异常跨层转换 | DAO 异常不透传到 Controller | SQLException 直抛 | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-06 | try-with-resources | IO 资源必须自动关闭 | 手动 close | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| EX-07 | RPC 异常降级 | 调用外部 RPC 失败时有降级策略 | RPC 无 catch | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |

## 6. 返回类型与 Optional

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| RET-01 | 不返回 null 集合 | 返回 Collections.emptyList() | `return null` | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| RET-02 | Optional 表示可能缺失 | 查询单个对象可能为空时返回 Optional | `findById` 返回 T | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| RET-03 | 禁止 Optional 作参数 | Optional 只用于返回值 | Optional 参数 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| RET-04 | 统一 Result 包装 | 对外 API 一律 Result<T> | Controller 返回裸对象 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| RET-05 | 分页结果 | 分页返回 PageResult<T> | 分页无 total | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| RET-06 | void 方法语义 | void 方法应通过异常表示失败 | `boolean updateDeal()` | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |

## 7. Lambda / Stream 规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| LAM-01 | Lambda ≤3 行 | 超过提取为方法引用 | Lambda 体 > 3 行 | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| LAM-02 | 禁止嵌套 Lambda | forEach 内不再嵌套 Lambda | `forEach` + `forEach` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| LAM-03 | Stream 内不 catch | 异常处理提到方法外 | `stream().map` + `try` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| LAM-04 | 禁止 Stream 副作用 | 不在 map/filter 中修改外部变量 | `.peek` 修改外部 | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| LAM-05 | 小集合不 parallel | <1000 元素不用 parallelStream | `parallelStream` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| LAM-06 | collect 要指定类型 | 需要特定 Map/Set 实现时显式指定 | `toMap` 无实现参数 | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |

## 8. 架构分层（DDD / 六边形）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| ARCH-01 | domain 不依赖 infra | domain 包不 import dao/rpc/mq 包 | domain import dao | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| ARCH-02 | Controller 是薄层 | 只做参数校验 + 调 Service + 返回 | Controller > 50 行 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| ARCH-03 | Service 不直接 SQL | 通过 Repository 接口 | `@Select` in Service | checklists/mt-java-coding-standards/DB-01-ORM规范.md |
| ARCH-04 | 跨模块走 API | 模块间通过 Thrift/HTTP API | 直接 import 另一模块 | checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md |
| ARCH-05 | 防腐层 | 外部依赖包一层 Adapter | 外部 API 直接散落 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| ARCH-06 | 配置外置 | 环境相关值放 Lion/配置中心 | 硬编码 IP/端口 | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| ARCH-07 | 领域事件解耦 | 跨聚合的副作用用事件 | Service 直接调多个下游 | checklists/mt-java-coding-standards/HA-06-消息队列高可用规范.md |

## 9. Spring Boot 专项

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| SPRING-TX-01 | 事务传播级别 | 明确指定 propagation；只读用 readOnly=true | `@Transactional` 无参数 | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| SPRING-TX-02 | 事务范围最小化 | @Transactional 不包含 RPC/MQ/HTTP 调用 | `@Transactional` + RPC | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| SPRING-TX-03 | rollbackFor | 显式 rollbackFor = Exception.class | `@Transactional` 无 rollbackFor | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| SPRING-TX-04 | 事务自调用失效 | 同类内 A() 调 B（），B 的 @Transactional 不生效 | 同类方法调用 | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| SPRING-DI-01 | 构造器注入 | 禁止 @Autowired 字段注入 | `@Autowired` 字段 | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| SPRING-DI-02 | 循环依赖 | 不允许循环依赖 | A 依赖 B 依赖 A | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| SPRING-SCOPE-01 | Bean 线程安全 | 单例 Bean 不持有可变实例变量 | `private int` in Service | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| SPRING-ASYNC-01 | @Async 线程池 | 必须指定自定义线程池 Bean | `@Async` 无参数 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| SPRING-CONFIG-01 | @Value 有默认值 | `@Value("${key:default}")` | `@Value("${key}")` | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| SPRING-CONFIG-02 | @ConfigurationProperties | 多个相关配置用类型安全绑定 | 多个 @Value | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| SPRING-SCHED-01 | @Scheduled 异常处理 | 定时任务内 try-catch 全包 | `@Scheduled` 无 try | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| SPRING-INIT-01 | 初始化顺序 | @PostConstruct 不做重操作 | `@PostConstruct` + 重操作 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |

## 10. MyBatis / 数据访问规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| MBT-01 | 禁止 SELECT * | 只查需要的字段 | `SELECT *` | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| MBT-02 | XML 与注解不混用 | 同一 Mapper 统一用 XML 或注解 | 同一 Mapper 混用 | checklists/mt-java-coding-standards/DB-01-ORM规范.md |
| MBT-03 | ResultMap 复用 | 公共映射提取为 BaseResultMap | 重复 ResultMap | checklists/mt-java-coding-standards/DB-01-ORM规范.md |
| MBT-04 | 动态 SQL 安全 | ${} 禁用于用户输入 | `${` | checklists/mt-java-coding-standards/SEC-A-注入安全规范.md |
| MBT-05 | 批量操作 foreach | 大量 INSERT/UPDATE 用 foreach 批量 | 循环内 insert | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| MBT-06 | 分页必须 LIMIT | 查询列表必须带分页参数 | 无 LIMIT 查询 | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| MBT-07 | 逻辑删除一致性 | 全表统一逻辑删除字段命名 | 字段名不一致 | checklists/mt-java-coding-standards/DB-03-MySQL-建表规范.md |
| MBT-08 | 索引覆盖 | WHERE 条件字段必须有索引 | 新增 WHERE 条件 | checklists/mt-java-coding-standards/DB-04-MySQL-索引规范.md |

## 11. 日志规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| LOG-01 | 占位符不拼接 | log.info("dealId={}", id) | `"dealId=" + id` | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| LOG-02 | 日志级别正确 | ERROR=需告警， WARN=可恢复， INFO=关键流程 | 所有 INFO | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| LOG-03 | 关键流程有日志 | 入口/出口/分支/异常四个点打日志 | 无日志的方法 | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| LOG-04 | 日志含业务 ID | traceId + 业务主键 | 无业务 ID 日志 | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| LOG-05 | 异常打全栈 | log.error("msg", e) 传异常对象 | `log.error(e.getMessage())` | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| LOG-06 | 敏感信息脱敏 | 手机号/身份证/token 不能明文打印 | 完整手机号 | checklists/mt-java-coding-standards/SEC-B-数据保护规范.md |
| LOG-07 | Cat 埋点 | 核心链路打 Cat Transaction/Event | 无 Cat 埋点 | checklists/mt-java-coding-standards/HA-02-可观测性规范.md |

## 12. 单元测试

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| TEST-01 | 新增公共方法必须有测试 | 核心逻辑覆盖率 ≥80% | 新增 Service 方法无测试 | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-02 | 测试命名 | 方法名_场景_预期结果 | `test1()` | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-03 | 断言明确 | 用 assertEquals/assertThrows | `assertTrue(result != null)` | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-04 | Mock 外部依赖 | Mock RPC/DB/MQ | 直接调真实依赖 | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-05 | 覆盖边界 | null、空集合、边界值、异常路径 | 无边界测试 | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-06 | 测试独立性 | 测试间不依赖执行顺序 | 共享可变状态 | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |
| TEST-07 | 不测 private | 通过公共方法间接覆盖 | 测试 private 方法 | checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md |

## 13. 并发与线程安全

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CONC-01 | 单例 Bean 无状态 | Spring 单例 Bean 不持有可变成员变量 | `private int` in Service | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-02 | SimpleDateFormat 不共享 | SDF 非线程安全 | `static SimpleDateFormat` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-03 | DCL 懒加载 | 懒加载单例必须 volatile + DCL | 无 volatile 的 DCL | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-04 | 线程池参数 | 自定义线程池，拒绝 Executors.newXxx | `Executors.new` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-05 | HashMap 并发写 | 多线程写 HashMap → ConcurrentHashMap | `HashMap` 多线程 | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-06 | 锁粒度最小化 | synchronized 锁住最小代码块 | `synchronized` 方法 | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CONC-07 | 禁用 DiscardPolicy/DiscardOldestPolicy | 任务被丢弃后 FutureTask 状态仍为 NEW | `DiscardPolicy` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CONC-08 | 在线服务禁用 CallerRunsPolicy | 被拒任务在调用线程执行 → RT 不可控 | `CallerRunsPolicy` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CONC-09 | Runnable 任务内部处理异常 | 未捕获异常 → 线程终止 | Runnable 无 try | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CONC-10 | 自定义线程名称 | 用 ThreadFactoryBuilder 设名称 | `pool-1-thread-1` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |

## 14. 美团中间件使用规范

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| MW-01 | Mafka 消费幂等 | 业务 ID + 去重表/Redis | Mafka 无幂等 | checklists/mt-java-coding-standards/HA-06-消息队列高可用规范.md |
| MW-02 | Mafka Producer 发送失败有重试 | 不能 fire-and-forget | `producer.send` 无重试 | checklists/mt-java-coding-standards/HA-06-消息队列高可用规范.md |
| MW-03 | Squirrel 大 Value 拆分 | >10KB 压缩或拆 key | 大对象 set | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| MW-04 | Squirrel key 命名 | {appkey}:{业务}:{id} | key 无 appkey 前缀 | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| MW-05 | Lion 动态配置有默认值 | Lion 故障时不影响服务启动 | `@MtConfig` 无默认值 | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-06 | Zebra 读写分离正确标注 | 写操作走主库，读操作走从库 | 读写分离标注错误 | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| MW-07 | Cat 核心链路埋点 | 缺少埋点 = 线上黑盒 | 无 Cat Transaction | checklists/mt-java-coding-standards/HA-02-可观测性规范.md |
| MW-08 | Crane 定时任务幂等 | 重复调度不产生脏数据 | `@Scheduled` 无幂等 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| MW-09 | @MtConfig 字段必须 static | 非 static → Lion 配置不生效 | `@MtConfig` 非 static | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-10 | @MdpConfig 字段禁止 static | static → 注入失败，字段为 null | `@MdpConfig` static | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-11 | @MdpConfig key 不加 appkey 前缀 | 框架自动拼接 | key 含 appkey | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-12 | @MdpConfig 默认值不能为空字符串 | 空字符串默认值导致解析异常 | `default = ""` | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-13 | @MdpConfig 所在类必须是 Spring Bean | 非 Bean 类注解不生效 | 非 @Component | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-14 | @MdpConfig 构造方法中禁止使用 | 构造时尚未注入，值为 null | 构造方法引用 @MdpConfig | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-15 | AOP 代理类访问 @MdpConfig 必须走 getter | 直接访问字段绕过代理 | 直接访问 @MdpConfig 字段 | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-16 | @MtConfig 只支持 6 种基本类型 | 不支持 List/Set/Map | `@MtConfig` List | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-17 | Lion 配置加载模式禁止 mcc-lion | 已废弃 | `mcc-lion` | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-18 | @MdpConfig 复杂类型必须用具体实现类+泛型 | 不能用 Map/List 接口 | `@MdpConfig` Map 接口 | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
| MW-19 | 必须使用 Rhino 动态线程池 | 原生 ThreadPoolExecutor 不支持运行时动态调参 | `new ThreadPoolExecutor` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |

## 15. 代码整洁度

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CLEAN-01 | 增量无引用方法 | diff 新增 public/protected 方法，全仓库搜索无引用 | 新增方法无引用 | (self) |
