# P0 零容忍异常 — 规则索引

> 本文件是 P0 层的规则索引。每条规则只保留编号、判定逻辑、触发关键词和对应完整规则文件路径。
> 完整规则定义和代码示例见 `checklists/mt-java-coding-standards/`。

> ⚠️ **P0 确认机制（全局规则）**：命中异常模式 ≠ 自动 P0。必须完成「三要素校验」：
> | 要素 | 校验内容 | 不满足时 |
> |------|---------|---------|
> | ①代码证据 | diff 中有具体行号和代码片段 | 不报 |
> | ②触达可达 | 异常输入能通过实际调用链到达该代码点，外层无 try-catch 阻断 | 归为 P2/P3 |
> | ③线上影响 | 能描述具体业务场景、触发数据、影响范围 | 归为 P2/P3 |
>
> - ①+②+③全满足 → **P0**
> - 任一要素不满足 → **直接归为 P2 或 P3**（不归 P1）
> - 纯理论风险且业务上极低概率 → 归为 **P3**

## 代码 BUG 类

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:NullPointerException | NullPointerException | 外部调用返回值/方法参数/集合元素/Map.get 拆箱，无 null check 到使用点 | `.get(`, `null`, `.getName()` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:ClassCastException | ClassCastException | 显式强制类型转换，obj 实际类型可能不匹配 | `(TargetType)` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:IndexOutOfBoundsException | IndexOutOfBoundsException | list.get(i)/substring，index 来自外部或动态计算 | `.get(`, `.substring(` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:ConcurrentModificationException | ConcurrentModificationException | for-each 中修改集合 | `for (`, `add`, `remove` | checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md |
| CR:NumberFormatException | NumberFormatException | parseInt/parseLong/valueOf，字符串来自外部，无 try-catch | `parseInt`, `parseLong`, `valueOf` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:StackOverflowError | StackOverflowError | 递归调用，无深度限制 | 递归方法调用 | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:OutOfMemoryError | OutOfMemoryError | 无限增长集合/循环内大对象，无分批处理 | `new ArrayList<>()`, `addAll` | checklists/mt-java-coding-standards/HA-07-JVM与线程池高可用规范.md |
| CR:NoSuchElementException | NoSuchElementException | Iterator.next()/Optional.get() 前无 hasNext()/isPresent() | `.next()`, `.get()` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:ArithmeticException | ArithmeticException | 除法操作，除数来自外部或动态计算，无零值检查 | `/` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:UnsupportedOperationException | UnsupportedOperationException | 不可变集合修改 | `List.of`, `Arrays.asList`, `Collections.unmodifiable` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |
| CR:NoClassDefFoundError | NoClassDefFoundError | 新增 import 的类不在 pom 依赖中 | `import` | checklists/mt-java-coding-standards/DEP-01-依赖规范.md |
| CR:NoSuchMethodError | NoSuchMethodError | 依赖版本冲突，被调用方法签名变更或移除 | 依赖版本变更 | checklists/mt-java-coding-standards/DEP-01-依赖规范.md |
| CR:BigDecimal | BigDecimal 精度丢失 | `new BigDecimal(double)` 用于金额/价格计算 | `new BigDecimal(` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| CR：浮点数比较Bug | 浮点数比较 Bug | float/double 用 ==/equals 比较，影响业务判断 | `==`, `equals` | checklists/mt-java-coding-standards/JAVA-01-常量定义规范.md |
| CR：日期跨年Bug-YYYY | 日期跨年 Bug | 日期格式化使用大写 YYYY | `YYYY` | checklists/mt-java-coding-standards/JAVA-06-日志记录规范.md |
| CR:Collectors | Collectors.toMap 双重炸弹 | Collectors.toMap() 未提供 mergeFunction，数据源可能有重复 key 或 null value | `Collectors.toMap` | checklists/mt-java-coding-standards/JAVA-03-集合处理规范.md |

## KV 数据超限类

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:StoreBigValueException | StoreBigValueException | Squirrel 单 value 序列化后 >10KB，无分片/压缩处理 | `squirrelClient.set`, `cache.set` | checklists/mt-java-coding-standards/HA-05-缓存高可用规范.md |

## SQL 执行失败类

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:DuplicateKeyException | DuplicateKeyException | INSERT 涉及唯一键，无 ON DUPLICATE KEY UPDATE，无 catch 处理冲突 | `INSERT`, `INSERT INTO` | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:PacketTooBigException | PacketTooBigException | 批量 INSERT/UPDATE 数据量不可控，无分批处理 | `batchInsert`, `batch` | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:MysqlDataTruncation | MysqlDataTruncation | 写入字段值来自外部输入，无长度校验/截断处理 | 字段写入 | checklists/mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md |
| CR:PoolExhaustedException | PoolExhaustedException | 手动获取连接且无 try-with-resources，或引入明显慢 SQL | `getConnection`, `DataSource` | checklists/mt-java-coding-standards/HA-04-存储高可用规范.md |
| CR:MyBatisSystemException | MyBatisSystemException | 修改了 Mapper XML 或注解 SQL，参数名/类型与方法签名不匹配 | `@Select`, `@Insert`, `resultMap` | checklists/mt-java-coding-standards/DB-01-ORM规范.md |

## Spring 异常类

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| CR:BeanCreationException | BeanCreationException | 新增 @Autowired 但被注入的 Bean 未定义，或循环依赖无 @Lazy | `@Autowired`, `@Resource` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |
| CR:NoSuchBeanDefinitionException | NoSuchBeanDefinitionException | 新增 @Component/@Service 不在 @ComponentScan 覆盖范围内 | `@Component`, `@Service` | checklists/mt-java-coding-standards/HA-03-防御性编程规范.md |

## 下线/删除类变更（DEL-01）

| 编号 | 规则 | 判定逻辑 | 触发关键词 | 完整规则文件 |
|------|------|---------|-----------|------------|
| DEL-01 | 被删内容消费方存活检查 | 方法/字段/监控被删除：消费方反查用 GitNexus/grep（Step 2B 本地反查）；删除 public 方法/对外接口时，跨仓库消费方本地无法覆盖，issue 必须标注「⚠️ 跨仓库消费方未验证」 | `set*()` 删除， 字段删除， 监控删除 | — |

> **DEL-01 搜索结果判定**：无命中 → 不报；有命中且有 null 判断 → 不报；有命中无 null 判断 → P1；监控删除无替代 → P2
