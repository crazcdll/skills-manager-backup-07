# P3 性能与现代化 — 规则索引

> 本文件是 P3 层的规则索引。每条规则只保留编号、判定逻辑、触发关键词和对应完整规则文件路径。
> 完整规则定义和代码示例见 `checklists/mt-java-coding-standards/`。

## 数据库访问（DB）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:DB-01 | N+1 查询 | 循环内逐条查询 | `for` + `selectById` | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:DB-02 | 大 IN 查询分批 | IN 子句无上限 | `IN (` 无上限 | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:DB-03 | 避免 SELECT * | 只查需要的字段 | `SELECT *` | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:DB-04 | 批量写入 | 大量 INSERT 用 foreach 批量 | 循环内 insert | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:DB-05 | 大表查询加 LIMIT | 无 LIMIT 的大表查询 | 无 LIMIT 查询 | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:DB-06 | 事务范围最小化 | 事务内包含 RPC 调用 | `@Transactional` + RPC | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |

## 缓存使用（CACHE）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:CACHE-01 | 高频读数据加缓存 | 每次请求都查 DB | `selectById` 无缓存 | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| CR:CACHE-02 | 缓存必须设 TTL | 无过期时间 | `squirrelClient.set` 无 TTL | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| CR:CACHE-03 | 缓存穿透防护 | 查不到直接返回，不缓存空值 | 无空值缓存 | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| CR:CACHE-04 | 缓存击穿防护 | 无 singleflight 模式 | 无击穿防护 | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |
| CR:CACHE-05 | 缓存雪崩防护 | 所有 key 同一 TTL | 无 TTL 抖动 | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |

## 集合与数据结构（COLL）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:COLL-01 | 字符串拼接 | 循环内 += 拼接 | `+=` 循环 | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| COLL-02/03 | 预分配容量 | ArrayList/HashMap 未指定初始容量 | `new ArrayList<>()` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| CR:COLL-04 | 频繁查找用 Set | List.contains() 是 O(n) | `List` + `contains` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| CR:COLL-06 | 小集合不 parallelStream | <1000 元素不用 parallelStream | `parallelStream` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |

## RPC 与 IO（RPC）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:RPC-01 | 串行 → 并行 | 串行调多个 RPC | 串行 RPC 调用 | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |
| CR:RPC-02 | 循环内 RPC → 批量接口 | 循环内逐条 RPC | `for` + RPC 调用 | checklists/mt-java-coding-standards/HA-01-失败设计规范.md |
| CR:RPC-04 | 日志精简 | 打印完整请求/响应 | 完整请求/响应日志 | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |

## 对象与内存（MEM）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:MEM-01 | 循环外复用不可变对象 | 循环内重复创建 | `new SimpleDateFormat` 循环内 | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| CR:MEM-03 | 避免热路径自动装箱 | 自动装箱产生大量临时对象 | `Integer` + `+` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| CR:MEM-04 | 正则 Pattern 复用 | 循环内编译正则 | `Pattern.matches` 循环内 | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |

## JDK 17+ 现代化（JDK）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:JDK-01 | Pattern Matching for instanceof | instanceof + 强制类型转换 | `instanceof` + cast | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| CR:JDK-03 | Record 替代数据类 | 传统 POJO 可用 Record 替代 | 大量 getter/setter | checklists/mt-java-coding-standards/JAVA-02-OOP设计规约.md |
| CR:JDK-05 | Virtual Threads | IO 密集场景可用虚拟线程 | `newFixedThreadPool` IO 密集 | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
