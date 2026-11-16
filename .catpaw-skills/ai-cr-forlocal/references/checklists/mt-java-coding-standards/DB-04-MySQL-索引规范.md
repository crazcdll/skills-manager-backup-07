---
ruleType: Model Request
description: MySQL数据库索引规范，包含避免索引创建误解、SQL性能优化目标、组合索引字段顺序、VARCHAR字段索引长度、JOIN字段索引与复杂度控制、ORDER BY索引优化、覆盖索引使用、大分页优化、防止隐式转换、唯一索引命名规范等索引规范
category: SQL规范
priority: medium
---

# MySQL数据库索引规范

## 一、说明

本规范定义了MySQL数据库索引的标准，包含索引创建原则、性能优化目标、组合索引设计、索引命名规范等方面的规范要求。合理使用索引能够显著提升查询性能。

## 二、规则内容

### java-l1:DB-04.N001 [推荐] 避免索引创建误解

创建索引时避免有如下误解：

**说明**：
1. 索引宁滥勿缺。认为一个查询就需要建一个索引
2. 吝啬索引的创建。认为索引会消耗空间、严重拖慢记录的更新以及行的新增速度
3. 抵制唯一索引。认为唯一索引一律需要在应用层通过"先查后插"方式解决

### java-l1:DB-04.N002 [推荐] SQL性能优化目标

SQL性能优化的目标：至少要达到range级别，要求是ref级别，如果可以是const最好。

**说明**：
1. const 单表中最多只有一个匹配行（主键或者唯一索引），在优化阶段即可读取到数据
2. ref 指的是使用普通的索引（normal index）
3. range 对索引进行范围检索

### java-l1:DB-04.N003 [推荐] 组合索引字段顺序

建组合索引的时候，区分度最高的在最左边。

**说明**：
- 建议基于实际场景（如查询频率等）、考虑数据特点（如数据分布，表结构等）并借助执行计划进行判断
- 存在非等号和等号混合判断条件，在建索引时，请把等号条件的列前置

### java-l1:DB-04.N004 [推荐] VARCHAR字段索引长度

在VARCHAR字段上建立索引时，指定索引长度，索引长度可以根据实际文本区分度决定。

**说明**：一般对字符串类型数据，长度为20的索引，区分度会高达90%，可以使用COUNT(DISTINCT LEFT(列名，索引长度)) / COUNT(*)的区分度来确定。

### java-l1:DB-04.N005 [强制] JOIN字段索引与复杂度控制

多表关联查询应控制JOIN复杂度，并结合执行计划评估性能。需要JOIN的字段，数据类型保持一致；多表关联查询时，保证被关联的字段具备索引。OLTP场景下若超过三个表JOIN，应重点评估是否可以拆分查询、调整模型或补充过滤条件。

### java-l1:DB-04.N006 [推荐] ORDER BY索引优化

ORDER BY的场景，请注意利用索引的有序性。

**说明**：ORDER BY最后的字段是组合索引的一部分，并且放在索引组合顺序最后，避免出现filesort，影响查询性能。

### java-l1:DB-04.N007 [推荐] 覆盖索引使用

利用覆盖索引来进行查询操作，避免回表。

**说明**：能够建立索引的种类分为主键索引、唯一索引、普通索引三种，而覆盖索引只是查询的效果，用EXPLAIN的结果，extra列会出现：using index。

### java-l1:DB-04.N008 [强制] 大分页优化

利用延迟关联或者子查询优化超多分页场景。

**说明**：MySQL并不跳过offset行，而是取offset+N行，然后返回放弃前offset行，返回N行。**`offset > 10000` 即为深分页**，效率非常低下，必须改用延迟关联或游标分页（详见 `HA-04` java-l1:HA-04.HA-S001）。

### java-l1:DB-04.N009 [强制] 防止隐式转换

防止因字段类型不同造成的隐式转换，导致索引失效。

### java-l1:DB-04.N010 [推荐] 唯一索引命名规范

唯一索引建议以'uniq_字段1_字段2'形式命名，非唯一索引建议以'idx_字段1_字段2'形式命名。若字段过多可使用缩写。

## 三、执行要求

1. 所有索引创建必须遵循本规范要求
2. 索引设计前必须进行性能评估
3. 对于不合理的索引必须及时优化
4. 新索引必须严格按照本规范设计

## 四、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:DB-04.N001 避免索引创建误解示例

#### good case:

```sql
-- 合理创建索引，基于实际查询需求
CREATE INDEX idx_user_status_create_time ON user_table(status, create_time);

-- 对于唯一性约束，使用唯一索引
CREATE UNIQUE INDEX uniq_user_email ON user_table(email);
```

#### bad case:

```sql
-- 为每个字段都创建索引（索引宁滥勿缺）
CREATE INDEX idx_user_id ON user_table(id);
CREATE INDEX idx_user_name ON user_table(name);
CREATE INDEX idx_user_age ON user_table(age);
CREATE INDEX idx_user_phone ON user_table(phone);

-- 拒绝创建任何索引（吝啬索引创建）
-- 应用层通过"先查后插"方式处理唯一性（抵制唯一索引）
```

### java-l1:DB-04.N002 SQL性能优化目标示例

#### good case:

```sql
-- const级别：主键查询
SELECT * FROM user_table WHERE id = 1;

-- ref级别：普通索引查询
SELECT * FROM user_table WHERE status = 'active';

-- range级别：范围查询
SELECT * FROM user_table WHERE create_time BETWEEN '2023-01-01' AND '2023-12-31';
```

#### bad case:

```sql
-- type = index，索引物理文件全扫描
SELECT * FROM user_table WHERE UPPER(name) = 'JOHN';
```

### java-l1:DB-04.N003 组合索引字段顺序示例

#### good case:

```sql
-- 等号条件列前置
CREATE INDEX idx_d_c ON table_name(d, c); -- WHERE c > ? AND d = ?

-- 区分度高的列在前（如果a列值几乎唯一）
CREATE INDEX idx_a ON table_name(a); -- WHERE a = ? AND b = ?
```

#### bad case:

```sql
-- 区分度低的列在前
CREATE INDEX idx_status_id ON user_table(status, id); -- status只有几个值，区分度低

-- 非等号条件列前置
CREATE INDEX idx_c_d ON table_name(c, d); -- WHERE c > ? AND d = ?
```

### java-l1:DB-04.N004 VARCHAR字段索引长度示例

#### good case:

```sql
-- 指定合适的索引长度
CREATE INDEX idx_user_name ON user_table(name(20));

-- 计算区分度来确定索引长度
SELECT COUNT(DISTINCT LEFT(name, 10)) / COUNT(*) FROM user_table;
SELECT COUNT(DISTINCT LEFT(name, 20)) / COUNT(*) FROM user_table;
```

#### bad case:

```sql
-- 未指定索引长度，可能造成索引过大
CREATE INDEX idx_user_description ON user_table(description);

-- 索引长度过短，区分度不够
CREATE INDEX idx_user_name ON user_table(name(5));
```

### java-l1:DB-04.N005 JOIN字段索引与复杂度控制示例

#### good case:

```sql
-- 两表JOIN，关联字段有索引且类型一致
SELECT u.name, o.amount
FROM user_table u
JOIN order_table o ON u.id = o.user_id
WHERE u.status = 'active';

-- 确保关联字段都有索引
CREATE INDEX idx_user_id ON user_table(id);
CREATE INDEX idx_order_user_id ON order_table(user_id);
```

#### bad case:

```sql
-- 四表JOIN且缺少必要过滤条件，也未先验证执行计划
SELECT * FROM table1 t1
JOIN table2 t2 ON t1.id = t2.t1_id
JOIN table3 t3 ON t2.id = t3.t2_id
JOIN table4 t4 ON t3.id = t4.t3_id;

-- 关联字段类型不一致
-- user_table.id 是 BIGINT，order_table.user_id 是 INT
SELECT * FROM user_table u JOIN order_table o ON u.id = o.user_id;
```

### java-l1:DB-04.N006 ORDER BY索引优化示例

#### good case:

```sql
-- 利用组合索引的有序性
CREATE INDEX idx_a_b_c ON table_name(a, b, c);
SELECT * FROM table_name WHERE a = ? AND b = ? ORDER BY c;
```

#### bad case:

```sql
-- 索引存在范围查询，无法利用有序性
CREATE INDEX idx_a_b ON table_name(a, b);
SELECT * FROM table_name WHERE a > 10 ORDER BY b; -- 无法利用索引排序
```

### java-l1:DB-04.N007 覆盖索引使用示例

#### good case:

```sql
-- 创建覆盖索引
CREATE INDEX idx_user_status_name ON user_table(status, name);

-- 查询字段都在索引中，避免回表
SELECT status, name FROM user_table WHERE status = 'active';
```

#### bad case:

```sql
-- 查询字段不在索引中，需要回表
CREATE INDEX idx_user_status ON user_table(status);
SELECT status, name, email FROM user_table WHERE status = 'active'; -- name, email不在索引中
```

### java-l1:DB-04.N008 大分页优化示例

#### good case:

```sql
-- 使用延迟关联优化大分页
SELECT t1.id, t1.columnA, t1.columnB
FROM table1 AS t1, (SELECT id FROM table1 WHERE 条件 LIMIT 100000, 20) AS t2
WHERE t1.id = t2.id;

-- 使用游标分页
SELECT * FROM table1 WHERE id > ? ORDER BY id LIMIT 20;
```

#### bad case:

```sql
-- 直接使用大OFFSET
SELECT * FROM table1 WHERE 条件 LIMIT 100000, 20; -- 效率极低
```

### java-l1:DB-04.N009 防止隐式转换示例

#### good case:

```sql
-- 字段类型匹配
CREATE INDEX idx_user_age ON user_table(age); -- age是INT类型
SELECT * FROM user_table WHERE age = 25; -- 使用INT值查询
```

#### bad case:

```sql
-- 类型不匹配导致隐式转换
CREATE INDEX idx_user_age ON user_table(age); -- age是INT类型
SELECT * FROM user_table WHERE age = '25'; -- 使用字符串查询，导致索引失效
```

### java-l1:DB-04.N010 唯一索引命名规范示例

#### good case:

```sql
-- 唯一索引命名
CREATE UNIQUE INDEX uniq_user_email ON user_table(email);
CREATE UNIQUE INDEX uniq_user_phone_status ON user_table(phone, status);

-- 普通索引命名
CREATE INDEX idx_user_create_time ON user_table(create_time);
CREATE INDEX idx_user_status_type ON user_table(status, type);
```

#### bad case:

```sql
-- 命名不规范
CREATE UNIQUE INDEX user_email_unique ON user_table(email);
CREATE INDEX index_on_user_create_time ON user_table(create_time);
CREATE INDEX user_idx ON user_table(status);
```

## 五、规范执行要点

### 核心要求
1. **性能目标**：SQL执行计划至少达到range级别,要求ref级别,最好const级别
2. **组合索引顺序**：区分度最高的字段在最左边,等号条件列前置于非等号条件
3. **VARCHAR索引长度**：必须指定索引长度,根据区分度决定(通常20长度可达90%区分度)
4. **JOIN字段要求**：关联字段必须有索引,数据类型必须绝对一致,避免超过3表JOIN
5. **ORDER BY优化**：ORDER BY字段应是组合索引的一部分且放在索引最后,避免filesort
6. **覆盖索引**：SELECT字段在索引列之内可避免回表,提升性能
7. **唯一索引命名**：格式为uk_字段名,普通索引为idx_字段名

### 强制禁止
- ✗ 禁止索引宁滥勿缺(不是每个查询都需要索引)
- ✗ 禁止吝啬索引创建(合理索引性能收益远大于维护成本)
- ✗ 禁止超过3个表JOIN(性能问题)
- ✗ 禁止大分页查询使用LIMIT 100000,20(必须使用延迟关联或子查询优化)
- ✗ 禁止WHERE条件字段类型与表字段类型不一致(导致索引失效)
- ✗ 禁止在索引列上做任何计算/函数/类型转换(导致索引失效)

### 代码审查检查点
- [ ] 执行计划是否达到range级别以上
- [ ] 组合索引顺序是否合理(区分度高的在左)
- [ ] VARCHAR索引是否指定了长度
- [ ] JOIN字段是否都有索引,类型是否一致
- [ ] 是否使用了覆盖索引优化
- [ ] 大分页查询是否优化(避免深分页)
- [ ] 索引命名是否规范(uk_/idx_前缀)
- [ ] WHERE条件是否存在隐式类型转换