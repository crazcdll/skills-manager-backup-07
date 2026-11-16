# 零容忍异常检查清单

以下异常类型命中零容忍红线，每引入一个都会影响 WBR 稳定性指标。

> ⚠️ **P0 确认机制（全局规则，对所有下列异常类型生效）**
>
> 命中以下异常模式 ≠ 自动 P0。**必须完成「三要素校验」后才能确定最终级别**：
>
> | 要素 | 校验内容 | 不满足时 |
> |------|---------|---------|
> | ①代码证据 | diff 中有具体行号和代码片段 | 不报 |
> | ②触达可达 | 异常输入能通过实际调用链到达该代码点，外层无 try-catch 阻断 | 归为 P2/P3 |
> | ③线上影响 | 能描述具体业务场景、触发数据、影响范围 | 归为 P2/P3 |
>
> **内部分级规则（直接按最终级别输出，不在文档中体现判定过程）**：
> - ①+②+③全满足 → **P0**
> - 任一要素不满足 → **直接归为 P2 或 P3**（不归 P1）
> - 纯理论风险（"如果出现循环引用"）且业务上极低概率 → 归为 **P3**

## 代码 BUG 类

| 异常类型 | 检查要点 | P0 确认条件（全部满足才报 P0） | 不满足时归为 |
|---------|---------|------------------------------|-------------------|
| `CR:NullPointerException` | 外部调用返回值、方法参数、集合元素、Map.get 拆箱 | ①null 来源可从代码确认（RPC 返回/Map.get/参数传入）②到使用点之间无 null check ③使用点会 NPE（.方法调用/拆箱） | 上层已有 `if (x == null)` 或 `Optional` 保护 → 不报；跨方法推测 → P2 |
| `CR:ClassCastException` | 强制类型转换 | ①代码中有显式 `(TargetType) obj` ②obj 的实际类型可能与 TargetType 不匹配（来自反序列化/泛型擦除/多态返回）③无 instanceof 前置检查 | obj 类型在编译期已确定（如同类赋值）→ 不报 |
| `CR:IndexOutOfBoundsException` | list.get(i)/substring | ①index 来自外部输入或动态计算 ②无 size/length 前置检查 ③diff 中能看到具体调用 | index 为硬编码常量且集合初始化已知 → 不报 |
| `CR:ConcurrentModificationException` | for-each 中修改集合 | ①diff 中有 for-each + 集合修改 ②集合可能被多线程访问或在循环中 add/remove | 单线程 + 循环后 break → 不报 |
| `CR:NumberFormatException` | parseInt/parseLong/valueOf | ①解析的字符串来自外部（用户输入/DB/接口返回/配置）②该调用点无 try-catch 包围 ③外层调用链上也无 catch | 外层方法已有 `catch(Exception)` 包围 → 归为 P2（建议内层也加保护）；数据来自内部枚举/硬编码 → 不报 |
| `CR:StackOverflowError` | 递归调用 | ①递归数据结构来自外部输入（用户可构造任意深度）②无深度限制 ③递归终止条件不可靠 | 数据来自内部系统且业务上有明确层级上限（如导航树≤5层）→ 归为 P3 建议 |
| `CR:OutOfMemoryError` | 无限增长集合/循环内大对象 | ①集合大小不可控（来自外部查询/无 limit）②无分批处理 ③会在单次请求中全量加载 | 有分页/limit/已知数据量上限 → 不报 |
| `CR:NoSuchElementException` | Iterator.next()/Optional.get() | ①调用前无 hasNext()/isPresent() ②Iterator/Optional 的来源数据可能为空 | 上游已有 isEmpty 判断 → 不报 |
| `CR:ArithmeticException` | 除法操作 | ①除数来自外部输入或动态计算 ②无零值检查 | 除数为常量或有业务保证非零 → 不报 |
| `CR:UnsupportedOperationException` | 不可变集合修改 | ①集合来自 Collections.unmodifiable*/List.of()/Arrays.asList() ②后续有 add/remove/set 操作 | — |
| `CR:NoClassDefFoundError` | 依赖缺失 | ①新增 import 的类不在 pom 依赖中 ②或依赖 scope 为 provided/test 但运行时需要 | 依赖已在 pom 中 → 不报 |
| `CR:NoSuchMethodError` | 依赖版本冲突 | ①升级了某个依赖版本 ②被调用方法在新版中签名变更或移除 ③Maven dependency:tree 能确认冲突 | 版本未变更 → 不报 |
| `CR:BigDecimal精度丢失` | `new BigDecimal(double)` 构造 | ①代码中有 `new BigDecimal(0.1)` 等 double 构造 ②用于金额/价格计算 ③无 `BigDecimal.valueOf()` 或字符串构造替代 | 非金额场景 → P2 |
| `CR:浮点数比较Bug` | float/double 用 `==`/`equals` 比较 | ①diff 中有浮点 `==` 或 `Float.equals`/`Double.equals` ②影响业务判断（金额/库存/比例） ③无 epsilon 近似比较或 `BigDecimal.compareTo` 替代 | 纯日志/展示 → P2 |
| `CR:日期跨年Bug-YYYY` | 日期格式化使用大写 `YYYY` | ①代码中有 `YYYY`（大写）的日期格式化 pattern ②用于业务逻辑（订单时间/对账/统计） ③非纯展示场景 | 纯日志展示 → P2 |
| `CR:Collectors.toMap双重炸弹` | `Collectors.toMap()` key 冲突 + null value | ①使用 `Collectors.toMap()` 且未提供 mergeFunction ②数据源可能有重复 key 或 null value（来自 DB/RPC/用户输入） | 数据源已去重且保证非 null → 不报 |

## KV 数据超限类

| 异常类型 | 检查要点 | P0 确认条件（全部满足才报 P0） | 不满足时归为 |
|---------|---------|------------------------------|-------------------|
| `CR:StoreBigValueException` | Squirrel 单 value 序列化后 < 10KB；批量查询 key 数量有上限 | ①存入的对象大小不可控（来自外部数据/无字段截断）②无分片/压缩处理 ③diff 中能看到 set/put 调用 | 对象字段数固定且已知大小上限 → 不报；有压缩但未验证压缩后大小 → P1 |

## SQL 执行失败类

| 异常类型 | 检查要点 | P0 确认条件（全部满足才报 P0） | 不满足时归为 |
|---------|---------|------------------------------|-------------------|
| `CR:MySQLIntegrityConstraintViolationException` / `CR:DuplicateKeyException` | INSERT 处理唯一键冲突 | ①INSERT 语句涉及唯一键 ②无 ON DUPLICATE KEY UPDATE ③无 catch 处理冲突 | 已有 catch + 业务兜底（如 log + 跳过）→ 不报 |
| `CR:PacketTooBigException` | 批量 SQL 大小控制 | ①批量 INSERT/UPDATE 的数据量不可控（来自外部查询/无 limit）②无分批处理 | 有分批（如 Lists.partition）→ 不报 |
| `CR:MysqlDataTruncation` | 字段值长度校验 | ①写入字段值来自外部输入 ②无长度校验/截断处理 ③DB 字段有长度限制 | 值来自内部枚举/已知固定长度 → 不报 |
| `CR:PoolExhaustedException` | 连接正确释放 + 慢 SQL 治理 | ①diff 中有手动获取连接且无 try-with-resources ②或引入明显慢 SQL（全表扫描/无索引） | 已使用 try-with-resources 或 Spring 管理事务 → 不报 |
| `CR:MyBatisSystemException` | MyBatis 映射配置正确性 | ①diff 中修改了 Mapper XML 或注解 SQL ②参数名/类型与方法签名不匹配 | 参数名一致且类型兼容 → 不报 |

## Spring 异常类

| 异常类型 | 检查要点 | P0 确认条件（全部满足才报 P0） | 不满足时归为 |
|---------|---------|------------------------------|-------------------|
| `CR:BeanCreationException` | Bean 依赖完整性 | ①新增 @Autowired 但被注入的 Bean 未定义 ②或循环依赖且无 @Lazy 打破 | 被注入的 Bean 已在配置中定义 → 不报 |
| `CR:NoSuchBeanDefinitionException` | 包扫描路径正确性 | ①新增 @Component/@Service 的类不在 @ComponentScan 覆盖范围内 ②或配置类中未定义对应 @Bean | 类在扫描路径内 → 不报 |

## 常见 NPE 场景

```java
// ❌ 链式调用未判空
String name = userService.getUserById(id).getName();

// ✅ 判空处理
User user = userService.getUserById(id);
if (user == null) {
    log.warn("user not found, id={}", id);
    return Result.fail("用户不存在");
}

// ❌ Map.get 直接拆箱
int count = map.get(key); // key 不存在时 NPE

// ✅ getOrDefault
int count = map.getOrDefault(key, 0);

// ❌ 集合为 null 时遍历
for (Item item : list) { ... } // list 为 null 时 NPE

// ✅ 空安全
if (CollectionUtils.isNotEmpty(list)) {
    for (Item item : list) { ... }
}

// ❌ 集合直接调用 contains/get 等方法，未判 null
list.contains(value); // list 为 null 时 NPE

// ✅ 空安全
if (CollectionUtils.isNotEmpty(list) && list.contains(value)) { ... }
```

> ⚠️ **集合 NPE 上下文感知规则（避免误报）**：
> 判断 `collection.contains()` / `collection.get()` / `collection.size()` 等调用是否有 NPE 风险时，**必须向上追溯同一个集合引用是否已经过 null-safe 保护**：
> - `CollectionUtils.isNotEmpty(collection)` — 已保护（false-on-null），不报 NPE
> - `CollectionUtils.isEmpty(collection)` — 已保护（true-on-null），不报 NPE
> - `collection != null` — 已保护，不报 NPE
> - `Objects.nonNull(collection)` — 已保护，不报 NPE
> - `Optional.ofNullable(collection).isPresent()` — 已保护，不报 NPE
>
> **误报场景示例**：
> ```java
> // 上游已有保护：
> if (CollectionUtils.isNotEmpty(j.getGrayCustomers())) {
>     // 此处 .contains() 是安全的，不应报 NPE
>     j.getGrayCustomers().contains(customerId);
> }
>
> // 或 Stream.filter 链中前置判断：
> .filter(j -> CollectionUtils.isNotEmpty(j.getGrayCustomers())
>           && j.getGrayCustomers().contains(Long.valueOf(customerId)))
> // ↑ isNotEmpty 已在同一布尔表达式前置短路，contains 安全，不报 NPE
> ```
>
> **注意**：追溯范围仅限**同一方法/lambda 作用域内的直接前置条件**，跨方法调用或不同路径下的保护不计入。
```

## 下线/删除类变更专项（CR:DEL-01）

> **触发条件**：PR 中存在以下任意模式时，**必须执行本节检查，不可跳过**
> - 方法体内 `set*()`/`write*()` 调用被删除
> - 类字段被删除（尤其是 Future/Container/DTO 字段）
> - 接口实现类、公共方法被删除
> - 监控打点（Cat.logEvent/logError/logMetric）被删除
> - MdpConfig/Feature 开关分支被整体移除

### CR:DEL-01 被删内容消费方存活检查

**必须执行**：用 `$REPO_SEARCH`（已在 Step 0 定义，即 `python3 repo_search.py`）逐一搜索所有被删内容的消费方

```bash
# $REPO_SEARCH 已在 /tmp/cr-env.env 中定义，source 后直接使用

# 搜索被删 setter 对应的 getter 引用
$SEARCH -r {org}/{repo} -k "getProductAddingItemFutures" --ext .java --json

# 搜索被删类字段名
$SEARCH -r {org}/{repo} -k "productSkuFutures" --ext .java --json
```

| 搜索结果 | 结论 | 级别 |
|---------|------|------|
| 无命中 | ✅ 已验证无残留消费方 | — |
| 有命中，命中处有 null 判断 | ✅ 已验证消费方有兜底 | — |
| 有命中，无 null 判断 | 🟠 残留消费方未同步删除，存在 NPE | **P1** |
| 监控删除但无替代监控 | 🟡 失去告警覆盖 | **P2** |

**禁止**：把"建议确认"甩给提交人，**能查的必须自己搜完再下结论**。

---

## 常见 Squirrel 大 Value 场景

```java
// ❌ 批量查询不限制 size
List<DealGroup> groups = queryService.queryByIds(allIds);

// ✅ 分批查询
Lists.partition(allIds, 200).forEach(batch -> {
    queryService.queryByIds(batch);
});
```
