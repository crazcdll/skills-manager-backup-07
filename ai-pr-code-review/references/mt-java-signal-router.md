# mt-java 规则信号路由表

> 本文件定义 16 个触发信号及其路由规则，用于在 Step 4A 中按需加载 mt-java 审查规则。
> 信号检测基于 Step 2 获取的 diff 文件列表和 diff 内容。

## 信号定义与触发条件

| 信号 | 触发条件 | 说明 |
|------|---------|------|
| SIG-JAVA | 包含 *.java 文件 | 始终触发（只要有 Java 代码变更） |
| SIG-SQL | 包含 *Mapper.xml / *.sql / diff 含 SQL 关键词(SELECT/INSERT/UPDATE/DELETE/JOIN) | SQL 开发与 ORM |
| SIG-DDL | diff 含 CREATE TABLE / ALTER TABLE / ADD INDEX / DROP INDEX | 建表与索引变更 |
| SIG-POM | 包含 pom.xml | 依赖管理 |
| SIG-THRIFT | 包含 *.thrift / *.proto / diff 含 thrift/proto 关键词 | 接口兼容性 |
| SIG-CONCUR | diff 含 synchronized/Lock/Thread/Executor/ThreadPool/CompletableFuture/volatile/Atomic | 并发相关 |
| SIG-RPC | diff 含 @ThriftClient/@OCTO/RPC/HttpClient/RestTemplate/Feign | RPC 调用 |
| SIG-CACHE | diff 含 Squirrel/Cellar/Redis/cache/Cache | 缓存操作 |
| SIG-MQ | diff 含 Mafka/Producer/Consumer/Message/MQ | 消息队列 |
| SIG-EXCEPTION | diff 含 try/catch/throw/Exception/NPE/NullPointerException | 异常处理（增量） |
| SIG-LOG | diff 含 log./logger./Logger/XMDFileAppender/scribeAppender | 日志记录 |
| SIG-TEST | 包含 *Test.java / *Tests.java | 单元测试 |
| SIG-SECURITY | diff 含 password/token/secret/encrypt/decrypt/serialize/deserialize/exec/parse/XML/redirect/cookie/upload/SSRF/XSS | 安全相关 |
| SIG-CONFIG | diff 含 @LionValue/Lion/config/properties/开关/degrade | 配置管理 |
| SIG-ES | diff 含 Eagle/Elasticsearch/ES/SearchIndex/Bulk | 搜索引擎 |
| SIG-HBASE | diff 含 HBase/HTable/Scan/Put/Get/RowKey | HBase 操作 |

## 信号 → 规则文件路由表（含去重说明）

| 触发信号 | 加载的规则文件 | 注入层级 | 与 CR: 规则去重说明 |
|---------|-------------|---------|-------------------|
| SIG-JAVA（始终触发） | `_always/java-01-constants.md`, `_always/java-02-oop-core.md`, `_always/java-05-exception-core.md` | P0: MT:N002(NPE); P2: MT:N001, JAVA-01, JAVA-02 | MT:N002 与 CR:NP-01/CR:NP-02 重叠 → NPE 检查以 CR: 为主，MT: 只报 CR: 未覆盖的 7 类高风险场景（包装类拆箱、级联调用、并发集合等） |
| SIG-SQL | `sql/db-01-orm.md`, `sql/db-02-sql-dev.md`, `sql/ha-04-storage-ha.md` | P0: MT:ORM002(SQL注入); P1: CR:DB-02, CR:HA-04; P2: MT:ORM001/003 | MT:ORM002 与 CR:SEC-02 重叠 → SQL 注入以 CR:SEC-02 为主，MT: 只报 ORM 层特有的注入场景（如 MyBatis ${} 拼接） |
| SIG-DDL | `ddl/db-03-table-design.md`, `ddl/db-04-index.md` | P2: CR:DB-03(建表规范); P3: CR:DB-04(索引优化) | 无重叠（CR: 无 DDL 规范） |
| SIG-POM | `dependency/dep-01-dependency.md` | P0: MT:N0004(SNAPSHOT); P1: MT:N0006(版本冲突); P2: 其余 | 无重叠（CR: 无依赖管理） |
| SIG-THRIFT | `api-compat/ha-10-api-compat.md`, `api-compat/java-08-api-design.md` | P0: MT:HA-API001(字段删除/改类型，**仅限跨部署单元契约 + 需调用方反查证据**); P1: MT:HA-API002/003 | 无重叠（CR: 无 Thrift/API 兼容性规则）。⚠️ MT:HA-API001 判 P0 前必须校验前置条件：载体为 Thrift IDL / 对外 interface / 二方库 public API / 序列化 DTO，且附带外部调用点「文件+行号」。`*Impl` 内部签名变更 / 无调用方证据 → 最高 P2 |
| SIG-CONCUR | `concurrency/java-04-concurrency.md`, `concurrency/ha-07-threadpool.md` | P0: MT:HA-J001(Executors禁用/无界队列); P1: MT:HA-J002/J003; P2: JAVA-04 | MT:HA-J001 与 CR:RM-11/CR:RM-12 重叠 → Executors 禁用 + 无界队列以 CR: 为主；MT: 只报 CR: 未覆盖的（DiscardPolicy 禁用、局部线程池 shutdown） |
| SIG-RPC | `rpc/ha-01-failure-design.md`, `rpc/ha-02-observability.md` | P1: MT:HA-F001~F006(失败设计); P1: MT:HA-O001(Metrics) | MT:HA-F001 与 CR:FT-01(RPC超时) 部分重叠 → 超时以 CR:FT-01 为主；MT: 只报 CR: 未覆盖的（failover 策略、降级链路、重试退避） |
| SIG-CACHE | `cache/ha-05-cache-ha.md`, `cache/ha-09-consistency.md` | P1: MT:HA-C001~C004(缓存高可用); P1: MT:HA-EC004(缓存DB一致性) | MT:HA-C001~C004 与 CR:CACHE-01~05 部分重叠 → 缓存穿透/击穿/雪崩以 CR: 为主；MT: 只报 CR: 未覆盖的（缓存DB一致性、Cellar/Squirrel 特有规范） |
| SIG-MQ | `mq/ha-06-mq-ha.md`, `cache/ha-09-consistency.md` | P0: MT:HA-M002(消费端幂等), MT:HA-EC001(通用幂等); P1: MT:HA-M001/M003/M004, MT:HA-EC002~EC005 | 无重叠（CR: 无 MQ 规范） |
| SIG-EXCEPTION | `exception/java-05-exception-full.md`, `exception/ha-03-defensive.md` | P1: MT:JAVA-05(异常处理完整); P1: MT:HA-D003/D004(异常分类/资源释放) | MT:JAVA-05(N001/N003~N009) 与 CR:EH-01/02/04/05 部分重叠 → 空 catch/catch 过宽以 CR: 为主；MT: 只报 CR: 未覆盖的（异常分类、业务异常 vs 系统异常分离、Throwable 捕获场景） |
| SIG-LOG | `log/java-06-logging.md` | P0: MT:N004(敏感信息脱敏); P1: MT:N002/N003; P2: MT:N001 | MT:N004 与 CR:SEC-11(敏感信息泄露) 部分重叠 → 敏感信息以 CR:SEC-11 为主；MT: 只报 CR: 未覆盖的（日志框架配置、日志级别规范、traceId 要求） |
| SIG-TEST | `test/java-07-unit-test.md` | P1: MT:N001/N002 | 无重叠（CR: 无测试规范） |
| SIG-SECURITY | `security/sec-a-injection.md`, `security/sec-b-data-protection.md`, `security/sec-c-access-control.md`, `security/ha-12-auth.md` | P0: 全部（安全类规则零容忍） | MT:SEC-A003 与 CR:SEC-02(SQL注入) 重叠 → 以 CR: 为主；MT:SEC-A001 与 CR:SEC-08(命令注入) 重叠 → 以 CR: 为主；MT:SEC-A002 与 CR:SEC-06(XXE) 重叠 → 以 CR: 为主；MT:SEC-A005 与 CR:SEC-04(URL重定向) 重叠 → 以 CR: 为主；MT: 只报 CR: 未覆盖的（Cookie 安全头、CSRF 防护、CORS 配置） |
| SIG-CONFIG | `config/ha-11-config-safety.md` | P2: MT:HA-CF001~CF003 | 无重叠（CR: 无配置管理规范） |
| SIG-ES | `es/ha-13-es-ha.md` | P1: MT:HA-ES003(Mapping); P2/P3: 其余 | 无重叠（CR: 无 ES 规范） |
| SIG-HBASE | `hbase/ha-14-hbase-ha.md` | P1: MT:HA-HB002(Scan边界); P2: 其余 | 无重叠（CR: 无 HBase 规范） |

## 去重原则

1. **CR: 优先**：当 MT: 规则与 CR: 规则覆盖同一问题时，以 CR: 规则为主，MT: 规则只报 CR: 未覆盖的部分
2. **不重复报**：同一问题不因两套规则重复报告，只报一次，规则编号标注以命中的规则为准
3. **MT: 补充定位**：MT: 规则的价值在于覆盖 CR: 未涉及的领域（MQ 幂等、DDL 建表、Thrift API 兼容性、ES/HBase、配置安全等）

## 加载策略

### 始终加载（SIG-JAVA 自动触发）
- `_always/` 目录下的 3 个文件在检测到任何 `.java` 文件变更时自动加载
- 包含最基础的规则：常量定义、OOP 核心（N005/N006）、NPE 防御

### 按需加载（其他信号触发）
- 每个信号对应一组规则文件，只在 diff 命中触发条件时加载
- 同一规则文件可能被多个信号引用（如 `ha-09-consistency.md` 同时被 SIG-CACHE 和 SIG-MQ 加载）
- 信号可叠加：一次 PR 变更可能触发多个信号，对应规则文件取并集

### 规则编号前缀
- 所有规则编号在精要版中统一加 `MT:` 前缀（如 `MT:N001`、`MT:HA-J001`、`MT:ORM002`）
- 原始文件中编号格式为 `N001`、`HA-J001`、`ORM002` 等

### P 层级注入说明
- **P0（零容忍）**：安全问题、NPE 风险、SQL 注入、SNAPSHOT 依赖、Executors 禁用 → 阻断级
- **P1（稳定性）**：高可用规则、异常处理、日志规范、测试规范 → 重要级
- **P2（规范）**：编码规范、建表规范、OOP 设计 → 建议级
- **P3（性能）**：索引优化、ES 调优 → 优化级
