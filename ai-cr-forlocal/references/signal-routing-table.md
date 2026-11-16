# 信号路由表（Step 3B 专用）

> 本文件为 Step 3B 的静态配置，定义 21 个信号类型、触发模式、规则文件映射、子 Agent 路由。
> 主 Agent 在 Step 3B 执行时 read 本文件，按信号路由表扫描 git diff → 生成 ACTIVE_SIGNALS → 写入 `/tmp/cr_signals_{repo}.md`。

---

## 1. 信号路由表

| 信号 ID | 触发模式（git diff 中检测） | 命中规则文件 | 子 Agent | 默认 P 级别 |
|---------|----------------------|-------------|-----------|------------|
| SIG-CONCURRENCY | `Thread`\|`Runnable`\|`Executor`\|`ThreadPool\|`synchronized`\|`Lock`\|`volatile`\|`CompletableFuture`\|`parallelStream`\|`ForkJoinPool` | JAVA-04, HA-07 | subagent-java, subagent-ha | P0（强制）→P2 |
| SIG-EXCEPTION | `try`\|`catch`\|`finally`\|`throw`\|`Exception`\|`throws` | JAVA-05, HA-03 | subagent-java, subagent-ha | P0（强制）→P2 |
| SIG-SQL | `@Transactional`\|`Mapper`\|`MyBatis`\|`SELECT`\|`INSERT`\|`UPDATE`\|`DELETE`\|`sql\|`JdbcTemplate` | DB-01, DB-02, DB-04, HA-04 | subagent-db-dep, subagent-ha | P0/P1/P2 |
| SIG-DDL | `CREATE TABLE`\|`ALTER TABLE`\|`ADD COLUMN`\|`DROP COLUMN`\|`MODIFY` | DB-03 | subagent-db-dep | P1（强制）→P2 |
| SIG-CACHE | `Redis`\|`Cache`\|`CacheManager`\|`@Cacheable`\|`Jedis`\|`Lettuce`\|`RedisTemplate` | HA-05 | subagent-ha | P1→P2 |
| SIG-MQ | `Mafka`\|`Consumer`\|`Producer`\|`@KafkaListener`\|`MessageListener`\|`SendResult` | HA-06 | subagent-ha | P0（强制）→P2 |
| SIG-RPC | `OCTO`\|`MTthrift`\|`HttpClient`\|`RestTemplate`\|`@RequestMapping`\|`WebClient`\|`Feign` | HA-01, HA-10 | subagent-ha | P1→P2 |
| SIG-LOG | `log.`\|`Logger`\|`Log4j`\|`scribeAppender`\|`XMDFileAppender`\|`@Slf4j`\|`AsyncScribe`\|`Metric`\|`Raptor`\|`Cat.`\|`Transaction` | JAVA-06, HA-02 | subagent-java, subagent-ha | P1（强制）→P2 |
| SIG-SECURITY | `@PreAuthorize`\|`@RequiresPermission`\|`Token`\|`Password`\|`encrypt`\|`decrypt`\|`SSRF`\|`XSS`\|`CSRF` | SEC-01, SEC-02, SEC-03, HA-12 | subagent-sec, subagent-ha | P0/P1 |
| SIG-CONFIG | `Lion`\|`@Value`\|`@ConfigurationProperties`\|`\.yml`\|`\.properties`\|`Switch`\|`FeatureToggle` | HA-11 | subagent-ha | P2 |
| SIG-COLLECTION | `List`\|`Map`\|`Set`\|`Collection`\|`Iterator`\|`HashMap`\|`ConcurrentHashMap` | JAVA-03 | subagent-java | P2 |
| SIG-OOP | `class`\|`interface`\|`extends`\|`implements`\|`abstract`\|`@Override` | JAVA-02 | subagent-java | P2 |
| SIG-CONSTANT | `static final`\|`enum`\|`Enum`\|`Constants` | JAVA-01 | subagent-java | P2 |
| SIG-INTERFACE | `@RequestMapping`\|`@GetMapping`\|`@PostMapping`\|`interface`\|`DTO`\|`VO`\|`Request`\|`Response` | JAVA-08, HA-10 | subagent-java, subagent-ha | P1→P2 |
| SIG-DEPENDENCY | `<dependency>`\|`pom.xml`\|`<groupId>`\|`<artifactId>`\|`<version>` | DEP-01 | subagent-db-dep | P2 |
| SIG-ES | `Eagle`\|`Elasticsearch`\|`RestHighLevelClient`\|`SearchRequest`\|`BulkRequest` | HA-13 | subagent-ha | P1→P2 |
| SIG-HBASE | `HBase`\|`HTable`\|`Scan`\|`Put`\|`Get`\|`BufferedMutator` | HA-14 | subagent-ha | P1→P2 |
| SIG-TEST | `@Test`\|`@Mock`\|`@MockBean`\|`Assert`\|`Mockito` | JAVA-07 | subagent-java | P2 |
| SIG-NPE | `.get()`\|`.getXxx()`\|`Optional`\|`null`\|`NullPointerException` | JAVA-05(java-l1:JAVA-05.N002), HA-03(java-l1:HA-03.HA-D002) | subagent-java, subagent-ha | P0/P1 |
| SIG-RESOURCE | `InputStream`\|`OutputStream`\|`Connection`\|`Reader`\|`Writer`\|`BufferedReader` | HA-03(java-l1:HA-03.HA-D004) | subagent-ha | P0（强制）→P2 |
| SIG-IDEMPOTENCY | `RECONSUME_LATER`\|`幂等`\|`idempotent`\|`@Idempotent` | HA-09, HA-06(java-l1:HA-06.HA-M002) | subagent-ha | P0（强制）→P2 |
| SIG-COMPATIBILITY | `@Deprecated`\|`serialVersionUID`\|`FAIL_ON_UNKNOWN_PROPERTIES`\|`optional`\|`reserved` | HA-10 | subagent-ha | P1→P2 |

> 🚨 **定级特例（2026-09-16 确认）**：DEP-01 的 `java-l1:DEP-01.N0004`（线上环境SNAPSHOT禁止规则）→ **一律 P2（建议级）**，不作为阻断项。理由：各团队依赖治理流程不同，PR 阶段 CR 检出多为误告（服务零售侧反馈），建议文案统一为「发布前替换为 RELEASE 版本」。该特例优先于本表任何默认级别。
>
> > 🚨 **forlocal 场景豁免表（2026-10-22 确认，仅适用于本地分支 CR）**，优先级高于上条特例及本表所有默认级别：
> > - **跳过不产出 issue**：`java-l1:DEP-01.N0004`、`java-l1:HA-10.HA-API004`、`java-l1:HA-02.HA-O005`
> > - **降为 P3，标注「上线前检查」**：`java-l1:HA-01.HA-F003/F004/F005`、`java-l1:HA-07.HA-J001`、`java-l1:HA-02.HA-O003`、`java-l1:HA-06.HA-M004`、`java-l1:HA-04.HA-S004`（仅读写分离条款）、`java-l1:SEC-03.SEC-C002`（仅「禁止访问内网地址」条款；用户输入驱动 URL 时仍按原级别）
> > - 完整豁免表及跳过/降级细则见 `subagent-task-template.md` 严重级别映射段

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

---

## 3. 子 Agent 路由映射（V115 逻辑域分组）

根据 ACTIVE_SIGNALS 确定哪些逻辑域需要启动，以及各自加载哪些规则文件：

| 逻辑域 | 触发信号 → 规则文件 |
|--------|-------------------|
| **code-data** | SIG-CONCURRENCY→JAVA-04; SIG-EXCEPTION→JAVA-05; SIG-LOG→JAVA-06; SIG-COLLECTION→JAVA-03; SIG-OOP→JAVA-02; SIG-CONSTANT→JAVA-01; SIG-INTERFACE→JAVA-08; SIG-TEST→JAVA-07; SIG-NPE→JAVA-05; SIG-SQL→DB-01,DB-02,DB-04; SIG-DDL→DB-03; SIG-DEPENDENCY→DEP-01 |
| **runtime** | SIG-CONCURRENCY→HA-07; SIG-EXCEPTION→HA-03; SIG-SQL→HA-04; SIG-CACHE→HA-05; SIG-MQ→HA-06; SIG-RPC→HA-01,HA-10; SIG-LOG→HA-02; SIG-CONFIG→HA-11; SIG-INTERFACE→HA-10; SIG-HBASE→HA-14; SIG-NPE→HA-03; SIG-RESOURCE→HA-03; SIG-IDEMPOTENCY→HA-09,HA-06; SIG-COMPATIBILITY→HA-10; SIG-ES→HA-13 |
| **security-search** | SIG-SECURITY→SEC-01,SEC-02,SEC-03,HA-12; SIG-ES→HA-13 |

> ⚠️ HA-12（安全编码）和 HA-13（搜索引擎）归 security-search 域；其余 HA-* 规则归 runtime 域。
> 4-C（自定义规则 + 平台L2规则）不参与信号映射，由 prep 产物驱动（V117 恢复独立路）：route_plan 读 `/tmp/cr_custom_rules_{repo}.md`（3A2）与 `/tmp/cr_l2_rules_{repo}.md`（3A3）的存在性决定是否开 4-C lane，与 ACTIVE_SIGNALS 无关。

---

## 4. 检测流程

1. 对 git diff 中所有 **ADDED** 和 **MODIFIED** 行做关键词匹配（不区分大小写）
   - 本地模式：使用 `grep -rn` 在本地代码仓库中扫描 diff 内容
   - 示例：`git diff HEAD~1 --name-only | xargs grep -rn "Thread\|Runnable\|Executor"`
2. 一个信号触发即标记为 active，不累计命中次数（信号是布尔值，不是计数）
3. 多个关键词命中同一信号 ID 只算一次
4. 将所有 active 信号收集为 `ACTIVE_SIGNALS` 列表

---

## 5. 跳过与兜底规则

**跳过规则**：若某逻辑域的所有触发信号均未命中，该逻辑域 **不启动**，主 Agent 在播报中注明"未触发相关信号，跳过"。

**兜底规则**：若 ACTIVE_SIGNALS 为空（极罕见，git diff 中无任何可识别模式），**只启动 code-data 逻辑域**（全规则）），不三域齐开——安全兜底优先于节省 token。

---

## 6. 输出格式

将 ACTIVE_SIGNALS 写入 `/tmp/cr_signals_{repo}.md`，格式：

```
ACTIVE_SIGNALS: SIG-CONCURRENCY, SIG-EXCEPTION, SIG-SQL, SIG-NPE
code-data: JAVA-04, JAVA-05, JAVA-03(NPE signal), DB-01, DB-02, DB-04
runtime: HA-07, HA-03, HA-04
security-search: (skipped - no SIG-SECURITY hit)
```

**播报**：`✅ Step 3B:检测到 {n} 个活跃信号 → code-data({x}文件), runtime({x}文件), security-search({skipped/x}文件)`

> 🚨 **Step 3B 完成后立即按路由计划并行启动 Step 4 各子 Agent（spawn），不得停顿。** ACTIVE_SIGNALS 透传给 Step 4-B 使用；`/tmp/cr_custom_rules_{repo}.md` 与 `/tmp/cr_l2_rules_{repo}.md` 透传给 Step 4-C 使用（V117 独立路，均无则 4-C 不 spawn）。**开哪几路由 `/tmp/cr_route_plan.json` 决定，不硬编码路数。**
