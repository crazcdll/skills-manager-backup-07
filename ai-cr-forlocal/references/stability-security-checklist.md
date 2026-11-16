# P1 稳定性与安全 — 规则索引

> 本文件是 P1 层的规则索引。每条规则只保留编号、判定逻辑、触发关键词和对应完整规则文件路径。
> 完整规则定义和代码示例见 `checklists/mt-java-coding-standards/`。

> 🚨 **P1 全局报出规则**：每条疑似 P1 必须完成以下校验：
> | 校验项 | 要求 | 不满足时 |
> |--------|------|---------|
> | 代码证据 | diff 中有具体行号和代码片段 | 不报 |
> | 线上场景 | 能描述具体业务场景 | 归为 P2/P3 |
> | 排除已有保护 | 确认调用链上无 try-catch/降级/兜底等防护 | 有完整防护 → 不报或 P2/P3 |
> | 非猜测性 | 结论基于代码事实 | 归为 P2/P3 |
>
> **禁止报 P1 的场景**：超时时间可能不够（P3）；测试环境直连无 failover（P3）；用户手动重试操作无重试（P3）；跨 RPC 非事务设计（不报）；catch(Exception) 已有 log+Cat（P2）；缓存短暂不一致业务可容忍（P3）

## 1. 异常处理（EH）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:EH-01 | 空 catch 块 | catch 块内无任何操作（不 log、不重抛、不上报） | `catch (Exception` + 空块 | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| CR:EH-02 | catch 范围过宽 | catch(Exception) 掩盖 NPE/ClassCast 等编码错误，已有 log 但未细化 | `catch (Exception` | checklists/mt-java-coding-standards/JAVA-05-异常处理规范.md |
| CR:EH-04 | 异常缺少上下文 | log.error 只打异常，无业务上下文参数 | `log.error("..."` 无参数 | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| CR:EH-05 | 关键异常无监控 | 只 log 不上报 Cat/Metric | `log.error` 无 `Cat.logError` | checklists/mt-java-coding-standards/HA-02-可观测性规范.md |

## 2. 资源管理（RM）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| RM-01/02 | 资源未关闭 | 手动管理 Connection/PreparedStatement/ResultSet，无 try-with-resources | `getConnection`, `prepareStatement` | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| CR:RM-03 | ThreadLocal 泄露 | ThreadLocal.set() 后无 remove（），在线程池环境 | `ThreadLocal`, `.set(` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-04 | 线程池参数 | 无界队列 + 默认拒绝策略 | `LinkedBlockingQueue<>()` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-05 | Future.get() 无超时 | future.get() 无超时参数 | `future.get()` 无参数 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-06 | CompletableFuture.allOf().join() | join() 无超时，异常被包装 | `allOf(`, `.join()` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-07 | supplyAsync/runAsync 无自定义线程池 | 默认 ForkJoinPool，IO 密集场景不足 | `supplyAsync(` 无第二参数 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-08 | 父子任务共用线程池 | 父任务等子任务结果，同一线程池 → 死锁 | `supplyAsync` + `get()` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-09 | 局部线程池未 shutdown | 方法内创建 ThreadPoolExecutor 但无 finally shutdown | `new ThreadPoolExecutor` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-10 | 递归中创建线程/任务 | 递归 submit → 线程数指数增长 | 递归 + `executor.submit` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-11 | 无界队列 | new LinkedBlockingQueue<>() 无容量 | `LinkedBlockingQueue<>()` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:RM-12 | Executors.newXxx 创建线程池 | Executors.newFixedThreadPool/newCachedThreadPool | `Executors.new` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |

## 3. 并发安全（CC）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:CC-02 | SimpleDateFormat 线程不安全 | static SimpleDateFormat，多线程调用 | `SimpleDateFormat` + `static` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CR:CC-04 | 双重检查锁缺 volatile | DCL 单例无 volatile | `instance` + `synchronized` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CR:CC-05 | HashMap 并发写入 | 多线程写 HashMap | `HashMap` + `put` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CR:CC-06 | ConcurrentHashMap null 键/值 | ConcurrentHashMap 的 key 或 value 为 null | `ConcurrentHashMap` + `put(null` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CR:CC-07 | Collectors.toMap key 冲突/null value | 未提供 mergeFunction，数据源可能有重复 key 或 null value | `Collectors.toMap` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |

## 4. 容灾降级（FT）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:FT-01 | RPC 无超时 | RPC 调用无超时设置 | `@Reference`, RPC 调用 | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |
| CR:FT-02 | 无 Fallback 降级 | 非核心依赖无降级策略 | RPC 调用无 catch | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |
| CR:FT-03 | 无限重试 | while(true) 重试，无次数限制 | `while (true)` + `retry` | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |
| CR:FT-04 | 熔断配置缺失分级 | 核心链路 RPC 无熔断配置 | 无 failfast 配置 | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |

## 5. Null 防御（NP）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:NP-01 | 自动拆箱 NPE | Integer 与 int 比较，Integer 为 null 时拆箱 | `Integer` + `<=` / `>=` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:NP-02 | 集合中放入 null | null 元素进入集合，下游遍历可能异常 | `Lists.newArrayList(null` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |

## 6. 安全漏洞（SEC）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:SEC-01 | 越权 | 只校验登录，不校验资源归属 | `@PathVariable` 无归属校验 | checklists/mt-java-coding-standards/SEC-C-访问控制与网络安全规范.md |
| CR:SEC-02 | SQL 注入 | 字符串拼接 SQL，或 MyBatis ${} 用于用户输入 | `String sql = ` + `+` | checklists/mt-java-coding-standards/SEC-A-注入安全规范.md |
| CR:SEC-03 | XSS | 用户输入直接输出到 HTML | `response.getWriter().write(` | checklists/mt-java-coding-standards/SEC-B-数据保护规范.md |
| CR:SEC-04 | URL 重定向 | 用户传入 URL 直接跳转 | `sendRedirect(` | checklists/mt-java-coding-standards/SEC-C-访问控制与网络安全规范.md |
| CR:SEC-05 | SSRF | 用户可控 URL 直接发起服务端请求 | `HttpClient.get(` | checklists/mt-java-coding-standards/SEC-C-访问控制与网络安全规范.md |
| CR:SEC-06 | XXE | XML 解析器默认允许外部实体 | `DocumentBuilderFactory` | checklists/mt-java-coding-standards/SEC-A-注入安全规范.md |
| CR:SEC-07 | 非预期文件操作 | 路径穿越 | `new File(` + 用户输入 | checklists/mt-java-coding-standards/SEC-B-数据保护规范.md |
| CR:SEC-08 | 命令注入 | 拼接用户输入到系统命令 | `Runtime.exec(` | checklists/mt-java-coding-standards/SEC-A-注入安全规范.md |
| CR:SEC-09 | CORS 配置不当 | 允许所有来源 + allowCredentials | `addAllowedOrigin("*")` | checklists/mt-java-coding-standards/SEC-C-访问控制与网络安全规范.md |
| CR:SEC-10 | 逻辑设计缺陷 | 关键操作无幂等保护 | `@PostMapping` 无幂等 | checklists/mt-java-coding-standards/HA-10-接口兼容性规范.md |
| CR:SEC-11 | 敏感信息泄露 | 日志打印完整手机号/密码 | `log.info` + password/phone | checklists/mt-java-coding-standards/SEC-B-数据保护规范.md |
| CR:SEC-12 | 硬编码凭证 | 代码中硬编码密码/密钥 | `password = "`, `apiKey = "` | checklists/mt-java-coding-standards/HA-11-配置安全规范.md |
