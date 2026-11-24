# 信号路由表（Step 3E 专用）

> 本文件为 Step 3E 的静态配置，定义 23 个信号类型、触发模式、规则文件映射、子 Agent 路由。
> 主 Agent 在 Step 3E 执行时 read 本文件，按信号路由表扫描 diff → 生成 ACTIVE_SIGNALS → 写入 `/tmp/cr_signals_{prId}.md`。

---

## 1. 信号路由表

| 信号 ID | 触发模式(diff 中检测) | 命中规则文件 | 子 Agent | 默认 P 级别 |
|---------|----------------------|-------------|-----------|------------|
| SIG-CONCURRENCY | `Thread`\|`Runnable`\|`Executor`\|`ThreadPool\|`synchronized`\|`Lock`\|`volatile`\|`CompletableFuture`\|`parallelStream`\|`ForkJoinPool` | JAVA-04, HA-07 | subagent-java, subagent-ha | P0(强制)→P2 |
| SIG-EXCEPTION | `try`\|`catch`\|`finally`\|`throw`\|`Exception`\|`throws` | JAVA-05, HA-03 | subagent-java, subagent-ha | P0(强制)→P2 |
| SIG-SQL | `@Transactional`\|`Mapper`\|`MyBatis`\|`SELECT`\|`INSERT`\|`UPDATE`\|`DELETE`\|`sql\|`JdbcTemplate` | DB-01, DB-02, DB-04, HA-04 | subagent-db-dep, subagent-ha | P0/P1/P2 |
| SIG-DDL | `CREATE TABLE`\|`ALTER TABLE`\|`ADD COLUMN`\|`DROP COLUMN`\|`MODIFY` | DB-03 | subagent-db-dep | P1(强制)→P2 |
| SIG-CACHE | `Redis`\|`Cache`\|`CacheManager`\|`@Cacheable`\|`Jedis`\|`Lettuce`\|`RedisTemplate` | HA-05 | subagent-ha | P1→P2 |
| SIG-MQ | `Mafka`\|`Consumer`\|`Producer`\|`@KafkaListener`\|`MessageListener`\|`SendResult` | HA-06 | subagent-ha | P0(强制)→P2 |
| SIG-RPC | `OCTO`\|`MTthrift`\|`HttpClient`\|`RestTemplate`\|`@RequestMapping`\|`WebClient`\|`Feign` | HA-01, HA-10 | subagent-ha | P1→P2 |
| SIG-LOG | `log.`\|`Logger`\|`Log4j`\|`scribeAppender`\|`XMDFileAppender`\|`@Slf4j`\|`System.out`\|`System.err`\|`printStackTrace` | JAVA-06, HA-02 | subagent-java, subagent-ha | P1(强制)→P2 |
| SIG-OBSERVABILITY | `AsyncScribe`\|`Metrics`\|`Trace`\|`@Span`\|`AlertRule`\|`dashboard`\|`monitor` | HA-02 | subagent-ha | P0(强制)→P2 |
| SIG-SECURITY | `@PreAuthorize`\|`@RequiresPermission`\|`Token`\|`Password`\|`encrypt`\|`decrypt`\|`SSRF`\|`XSS`\|`CSRF` | SEC-01, SEC-02, SEC-03, HA-12 | subagent-sec, subagent-ha | P0/P1 |
| SIG-CONFIG | `Lion`\|`@Value`\|`@ConfigurationProperties`\|`\.yml`\|`\.properties`\|`Switch`\|`FeatureToggle` | HA-11 | subagent-ha | P2 |
| SIG-COLLECTION | `List`\|`Map`\|`Set`\|`Collection`\|`Iterator`\|`HashMap`\|`ConcurrentHashMap` | JAVA-03 | subagent-java | P2 |
| SIG-OOP | `class`\|`interface`\|`extends`\|`implements`\|`abstract`\|`@Override` | JAVA-02 | subagent-java | P2 |
| SIG-CONSTANT | `static final`\|`enum`\|`Enum`\|`Constants` | JAVA-01 | subagent-java | P2 |
| SIG-INTERFACE | `@RequestMapping`\|`@GetMapping`\|`@PostMapping`\|`interface`\|`DTO`\|`VO`\|`Request`\|`Response` | JAVA-08, HA-10 | subagent-java, subagent-ha | P1→P2 |
| SIG-DEPENDENCY | `<dependency>`\|`pom.xml`\|`<groupId>`\|`<artifactId>`\|`<version>` | DEP-01 | subagent-db-dep | P2（🚨N0004 已删除不检出，见下方删除说明） |
| SIG-ES | `Eagle`\|`Elasticsearch`\|`RestHighLevelClient`\|`SearchRequest`\|`BulkRequest` | HA-13 | subagent-ha | P1→P2 |
| SIG-HBASE | `HBase`\|`HTable`\|`Scan`\|`Put`\|`Get`\|`BufferedMutator` | HA-14 | subagent-ha | P1→P2 |
| SIG-TEST | `@Test`\|`@Mock`\|`@MockBean`\|`Assert`\|`Mockito` | JAVA-07 | subagent-java | P2 |
| SIG-NPE | `.get()`\|`.getXxx()`\|`Optional`\|`null`\|`NullPointerException` | JAVA-05(java-l1:JAVA-05.N002), HA-03(java-l1:HA-03.HA-D002) | subagent-java, subagent-ha | P0/P1 |
| SIG-RESOURCE | `InputStream`\|`OutputStream`\|`Connection`\|`Reader`\|`Writer`\|`BufferedReader` | HA-03(java-l1:HA-03.HA-D004) | subagent-ha | P0(强制)→P2 |
| SIG-IDEMPOTENCY | `RECONSUME_LATER`\|`幂等`\|`idempotent`\|`@Idempotent` | HA-09, HA-06(java-l1:HA-06.HA-M002) | subagent-ha | P0(强制)→P2 |
| SIG-COMPATIBILITY | `@Deprecated`\|`serialVersionUID`\|`FAIL_ON_UNKNOWN_PROPERTIES`\|`optional`\|`reserved` | HA-10 | subagent-ha | P1→P2 |

---

## 2. 规则文件名 → 完整路径映射

| 规则编号 | 文件路径 |
|---------|---------|
| JAVA-01 | `references/checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md` |
| JAVA-02 | `references/checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md` |
| JAVA-03 | `references/checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md` |
| JAVA-04 | `references/checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md` |
| JAVA-05 | `references/checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md` |
| JAVA-06 | `references/checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md` |
| JAVA-07 | `references/checklists/mt-java-coding-standards/JAVA-07-单元测试编写规范.md` |
| JAVA-08 | `references/checklists/mt-java-coding-standards/JAVA-08-接口设计规范.md` |
| DB-01 | `references/checklists/mt-java-coding-standards/DB-01-ORM规范.md` |
| DB-02 | `references/checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md` |
| DB-03 | `references/checklists/mt-java-coding-standards/DB-03-MySQL-建表规范.md` |
| DB-04 | `references/checklists/mt-java-coding-standards/DB-04-MySQL-索引规范.md` |
| DEP-01 | `references/checklists/mt-java-coding-standards/DEP-01-依赖规范.md` |
| HA-01 | `references/checklists/mt-java-coding-standards/HA-01-失败设计规范.md` |
| HA-02 | `references/checklists/mt-java-coding-standards/HA-02-可观测性规范.md` |
| HA-03 | `references/checklists/mt-java-coding-standards/HA-03-防御性编程规范.md` |
| HA-04 | `references/checklists/mt-java-coding-standards/HA-04-存储高可用规范.md` |
| HA-05 | `references/checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md` |
| HA-06 | `references/checklists/mt-java-coding-standards/HA-06-消息队列高可用规范.md` |
| HA-07 | `references/checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md` |
| HA-09 | `references/checklists/mt-java-coding-standards/HA-09-最终一致性规范.md` |
| HA-10 | `references/checklists/mt-java-coding-standards/HA-10-接口兼容性规范.md` |
| HA-11 | `references/checklists/mt-java-coding-standards/HA-11-配置安全规范.md` |
| HA-12 | `references/checklists/mt-java-coding-standards/HA-12-安全编码规范.md` |
| HA-13 | `references/checklists/mt-java-coding-standards/HA-13-搜索引擎高可用规范.md` |
| HA-14 | `references/checklists/mt-java-coding-standards/HA-14-HBase高可用规范.md` |
| SEC-01 | `references/checklists/mt-java-coding-standards/SEC-01-注入安全规范.md` |
| SEC-02 | `references/checklists/mt-java-coding-standards/SEC-02-数据保护规范.md` |
| SEC-03 | `references/checklists/mt-java-coding-standards/SEC-03-访问控制与网络安全规范.md` |

> ⚠️ 规则文件内的规则编号格式为 `java-l1:文件前缀编号.规则编号`（如 `java-l1:JAVA-05.N002`、`java-l1:HA-03.HA-D002`）。信号路由表中标注的 `(java-l1:XX-NN.YYY)` 表示该规则文件中特定规则编号，子 Agent 加载文件后按编号定位具体规则。

> 🚨 **规则删除（2026-10-29 确认）**：DEP-01 的 **N0004 线上环境SNAPSHOT禁止规则已删除，不再检出**（2026-09-16 曾降级为 P2 建议级，本次彻底移除）。原因：各团队依赖治理流程不同（联调/安全包场景合理使用 SNAPSHOT），PR 阶段检出多为误告。子 Agent 加载 DEP-01 文件时**跳过 N0004 规则，不产出任何 SNAPSHOT 相关 issue（含 P2/P3）**。

---

## 3. 子 Agent 路由映射

根据 ACTIVE_SIGNALS 确定哪些子 Agent 需要启动，以及各自加载哪些规则文件：

| 子 Agent | 触发信号 → 规则文件 |
|-----------|-------------------|
| **subagent-java** | SIG-CONCURRENCY→JAVA-04; SIG-EXCEPTION→JAVA-05; SIG-LOG→JAVA-06; SIG-COLLECTION→JAVA-03; SIG-OOP→JAVA-02; SIG-CONSTANT→JAVA-01; SIG-INTERFACE→JAVA-08; SIG-TEST→JAVA-07; SIG-NPE→JAVA-05 |
| **subagent-db-dep** | SIG-SQL→DB-01,DB-02,DB-04; SIG-DDL→DB-03; SIG-DEPENDENCY→DEP-01 |
| **subagent-ha** | SIG-CONCURRENCY→HA-07; SIG-EXCEPTION→HA-03; SIG-SQL→HA-04; SIG-CACHE→HA-05; SIG-MQ→HA-06; SIG-RPC→HA-01; SIG-LOG→HA-02; SIG-OBSERVABILITY→HA-02; SIG-CONFIG→HA-11; SIG-INTERFACE→HA-10; SIG-ES→HA-13; SIG-HBASE→HA-14; SIG-NPE→HA-03; SIG-RESOURCE→HA-03; SIG-IDEMPOTENCY→HA-09; SIG-COMPATIBILITY→HA-10; SIG-SECURITY→HA-12 |
| **subagent-sec** | SIG-SECURITY→SEC-01,SEC-02,SEC-03 |

---

## 4. 检测流程

1. 对 diff 中所有 **ADDED** 和 **MODIFIED** 行做关键词匹配（不区分大小写）
2. 一个信号触发即标记为 active，不累计命中次数（信号是布尔值，不是计数）
3. 多个关键词命中同一信号 ID 只算一次
4. 将所有 active 信号收集为 `ACTIVE_SIGNALS` 列表

---

## 5. 跳过与兜底规则

**跳过规则**：若某子 Agent 的所有触发信号均未命中，该子 Agent **不启动**，主 Agent 在播报中注明"未触发相关信号，跳过"。

**兜底规则**：若 ACTIVE_SIGNALS 为空（极罕见，diff 中无任何可识别模式），**全部 4 个子 Agent 正常启动**，加载各自全部分组规则文件——安全兜底优先于节省 token。

---

## 6. 输出格式

将 ACTIVE_SIGNALS 写入 `/tmp/cr_signals_{prId}.md`，格式：

```
ACTIVE_SIGNALS: SIG-CONCURRENCY, SIG-EXCEPTION, SIG-SQL, SIG-NPE
subagent-java: JAVA-04, JAVA-05, JAVA-03(NPE signal)
subagent-db-dep: DB-01, DB-02, DB-04
subagent-ha: HA-07, HA-03, HA-04
subagent-sec: (skipped - no SIG-SECURITY hit)
```

**播报**：`✅ Step 3E:检测到 {n} 个活跃信号 → subagent-java({x}文件), subagent-db-dep({x}文件), subagent-ha({x}文件), subagent-sec({skipped/x}文件)`

> 🚨 **Step 3E 完成后立即并行启动适用的 Step 4-A、Step 4-B 和 Step 4-C。ACTIVE_SIGNALS 透传给 Step 4-B；本轮仓库规则回执和其中的有效缓存路径透传给 Step 4-C。**
