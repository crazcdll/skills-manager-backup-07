---
ruleType: Model Request
description: MySQL SQL开发规范，包含禁止使用存储过程、SQL关键字和字段类型大写、必须有测试覆盖的删除修改操作、禁止使用外键和级联、多表操作必须使用表别名、限制IN操作元素数量、使用标准NULL判断、使用COUNT(*)统计行数、注意COUNT DISTINCT的特殊行为、避免SUM函数的NPE问题、使用utf8mb4字符集、禁止DDL操作、控制批量操作数量、禁止使用通配符查询、动态SQL安全校验等15项SQL开发规范
category: SQL规范
priority: high
---

# MySQL SQL开发规范

## 一、说明

本规范定义了MySQL SQL开发的标准，包含存储过程使用、SQL格式、数据操作、字符集、批量操作等方面的规范要求。遵循本规范能够提高SQL的可读性、可维护性和执行效率，避免常见的性能问题和安全风险。

## 二、规则内容

### java-l1:DB-02.N001 [强制] 禁止使用存储过程

禁止使用存储过程，存储过程难以调试和扩展，更没有移植性。

### java-l1:DB-02.N002 [推荐] SQL关键字和字段类型大写

SQL中关键字和字段类型大写，关键字换行对齐。

### java-l1:DB-02.N003 [强制] 必须有测试覆盖的删除修改操作

删除或修改记录等操作时，必须有测试覆盖，避免误操作。建议先SELECT，确认无误才能执行更新语句。

### java-l1:DB-02.N004 [强制] 禁止使用外键和级联

不得使用外键与级联，一切外键概念必须在应用层解决。

**说明**：外键与级联更新适用于单机低并发，不适合分布式、高并发集群；级联更新是强阻塞，存在数据库更新风暴的风险；外键影响数据库的插入速度。

### java-l1:DB-02.N005 [推荐] 多表操作必须使用表别名

对于数据库中表记录的查询和变更，只要涉及多个表，都需要在列名前加表的别名（或表名）进行限定。

### java-l1:DB-02.N006 [推荐] 限制IN操作元素数量

IN操作能避免则避免，若实在避免不了，需要仔细评估IN后边的集合元素数量，控制在200个之内。

### java-l1:DB-02.N007 [强制] 使用标准NULL判断

在条件判断中使用IS NULL / IS NOT NULL来判断NULL值；在表达式中需要为空值兜底时，使用IFNULL()或COALESCE()。

### java-l1:DB-02.N008 [推荐] 使用COUNT(*)统计行数

不要使用COUNT(列名)或COUNT(常量)来替代COUNT(*)，COUNT(*)是SQL92定义的标准统计行数的语法，跟数据库无关，跟NULL和非NULL无关。

### java-l1:DB-02.N009 [推荐] 注意COUNT DISTINCT的特殊行为

COUNT(DISTINCT col)计算该列除NULL之外的不重复行数，注意COUNT(DISTINCT col1, col2)如果其中一列全为NULL，那么即使另一列有不同的值，也返回为0。

### java-l1:DB-02.N010 [强制] 避免SUM函数的NPE问题

当某一列的值全是NULL时，COUNT(col)的返回结果为0；但SUM(col)的返回结果为NULL，因此使用SUM()时需注意NPE问题。

### java-l1:DB-02.N011 [强制] 使用utf8mb4字符集

因国际化需要，所有的字符存储与表示，均采用utf8mb4字符集。表情需要用utf8mb4来进行存储，注意与utf8编码的区别。

### java-l1:DB-02.N012 [强制] 禁止DDL操作

应用程序里的语句，禁止一切DDL操作。DDL走RDS平台。

### java-l1:DB-02.N013 [推荐] 控制批量操作数量

大批量INSERT/UPDATE/DELETE数据时，建议单次操作少于1000条，超过时，要拆分，并在每批之间增加缓冲时间以减少主从延时的影响。**高可用场景（减少锁持有时间）要求每批 ≤200 条，详见 `HA-04` java-l1:HA-04.HA-S002。**

### java-l1:DB-02.N014 [强制] 禁止使用通配符查询

在表查询中，一律不要使用*作为查询的字段列表，需要哪些字段必须明确写明。

**说明**：增减字段容易与resultMap配置不一致；无用字段增加网络消耗，尤其是TEXT类型的字段。

### java-l1:DB-02.N015 [强制] 动态 SQL 必须安全校验

对于无法通过预编译参数绑定（`#{}`）的动态场景——如表名、列名、ORDER BY 字段等——必须实施白名单校验或使用安全 SDK 进行合法性验证。

**说明**：
- ORDER BY / GROUP BY 中的动态字段名校验、安全 SDK 依赖版本详见 `SEC-01` java-l1:SEC-01.SEC-A003
- `${}` 仅可在动态表名/列名场景使用，且必须白名单校验（详见 `DB-01` java-l1:DB-01.ORM002）
- **查询结果数量上限**：对外暴露的查询接口必须设置 LIMIT 上限（建议 ≤100 条），防止性能问题和数据泄露

## 三、执行要求

1. 所有SQL语句必须遵循本规范要求
2. 代码审查时重点检查SQL语句的规范性
3. 对于违反规范的SQL必须及时整改
4. 新SQL必须严格按照本规范编写

## 四、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:DB-02.N001 禁止使用存储过程示例

#### good case:

```sql
-- 在应用层处理业务逻辑
SELECT * FROM user WHERE status = 'active';

-- 使用普通SQL语句完成操作
UPDATE user SET last_login = NOW() WHERE id = 1;
```

#### bad case:

```sql
-- 创建存储过程
CREATE PROCEDURE GetActiveUsers()
BEGIN
    SELECT * FROM user WHERE status = 'active';
END;

-- 调用存储过程
CALL GetActiveUsers();
```

### java-l1:DB-02.N002 SQL关键字和字段类型大写示例

#### good case:

```sql
-- 关键字大写，换行对齐
SELECT id, name, email
FROM user_table
WHERE status = 'active'
  AND create_time > '2023-01-01'
ORDER BY create_time DESC;

-- 字段类型大写
CREATE TABLE user_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    PRIMARY KEY (id)
);
```

#### bad case:

```sql
-- 关键字小写，格式混乱
select id,name,email from user_table where status='active' and create_time>'2023-01-01' order by create_time desc;

-- 字段类型小写
CREATE TABLE user_table (
    id bigint not null auto_increment,
    name varchar(50) not null,
    email varchar(100) not null,
    primary key (id)
);
```

### java-l1:DB-02.N003 必须有测试覆盖的删除修改操作示例

#### good case:

```sql
-- 先查询确认影响范围
SELECT COUNT(*) FROM user_table WHERE status = 'inactive' AND last_login < '2023-01-01';

-- 确认无误后执行删除
DELETE FROM user_table WHERE status = 'inactive' AND last_login < '2023-01-01';

-- 带限制条件的更新
UPDATE user_table SET status = 'archived' WHERE id = 123 AND status = 'inactive';
```

#### bad case:

```sql
-- 直接执行删除，没有先确认
DELETE FROM user_table WHERE status = 'inactive';

-- 没有WHERE条件的危险操作
DELETE FROM user_table;
UPDATE user_table SET status = 'inactive';
```

### java-l1:DB-02.N004 禁止使用外键和级联示例

#### good case:

```sql
-- 在应用层处理外键关系
CREATE TABLE user_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE order_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id)
);

-- 在应用层验证关联关系
-- 先查询用户是否存在，再插入订单
```

#### bad case:

```sql
-- 使用外键约束
CREATE TABLE order_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES user_table(id) ON DELETE CASCADE
);
```

### java-l1:DB-02.N005 多表操作必须使用表别名示例

#### good case:

```sql
-- 使用表别名限定列名
SELECT t1.name, t2.amount, t1.create_time
FROM user_table AS t1
JOIN order_table AS t2 ON t1.id = t2.user_id
WHERE t1.status = 'active';

-- 更新操作也要使用表别名
UPDATE user_table AS u
SET u.last_login = NOW()
WHERE u.id IN (
    SELECT o.user_id
    FROM order_table AS o
    WHERE o.create_time > '2023-01-01'
);
```

#### bad case:

```sql
-- 没有使用表别名限定列名
SELECT name, amount, create_time
FROM user_table
JOIN order_table ON id = user_id
WHERE status = 'active';

-- 列名可能产生歧义
SELECT id, name FROM user_table, order_table WHERE id = user_id;
```

### java-l1:DB-02.N006 限制IN操作元素数量示例

#### good case:

```sql
-- 元素数量控制在200以内
SELECT * FROM user_table WHERE id IN (1, 2, 3, 4, 5);

-- 使用连续数值时用BETWEEN
SELECT * FROM user_table WHERE id BETWEEN 1 AND 100;

-- 分批查询大量数据
SELECT * FROM user_table WHERE id >= 1 AND id <= 200;
SELECT * FROM user_table WHERE id >= 201 AND id <= 400;
```

#### bad case:

```sql
-- IN后面元素过多
SELECT * FROM user_table WHERE id IN (1, 2, 3, ..., 500); -- 超过200个元素

-- 可以用BETWEEN但使用了IN
SELECT * FROM user_table WHERE id IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
```

### java-l1:DB-02.N007 使用标准NULL判断示例

#### good case:

```sql
-- 使用IS NULL / IS NOT NULL进行条件判断
SELECT * FROM table1 WHERE column1 IS NULL AND column3 IS NOT NULL;

-- 使用IFNULL处理表达式中的空值
SELECT id, IFNULL(name, '未知') AS name FROM user_table;

-- 使用COALESCE按优先级选择非NULL值
SELECT COALESCE(nickname, name, '游客') AS display_name FROM user_table;
```

#### bad case:

```sql
-- 直接与NULL比较
SELECT * FROM table1 WHERE column1 = NULL; -- 永远返回NULL
SELECT * FROM table1 WHERE column1 <> NULL; -- 永远返回NULL

-- 在条件判断中混淆空值判断和默认值兜底语义
SELECT * FROM table1 WHERE IFNULL(column1, '') = '';
```

### java-l1:DB-02.N008 使用COUNT(*)统计行数示例

#### good case:

```sql
-- 使用COUNT(*)统计行数
SELECT COUNT(*) FROM user_table WHERE status = 'active';

-- 统计非NULL值使用COUNT(列名)
SELECT COUNT(email) FROM user_table; -- 统计email非NULL的行数
```

#### bad case:

```sql
-- 使用COUNT(1)替代COUNT(*)
SELECT COUNT(1) FROM user_table WHERE status = 'active';

-- 使用COUNT(常量)
SELECT COUNT(0) FROM user_table WHERE status = 'active';
```

### java-l1:DB-02.N009 注意COUNT DISTINCT的特殊行为示例

#### good case:

```sql
-- 单列去重统计
SELECT COUNT(DISTINCT user_id) FROM order_table;

-- 多列去重统计时确保列都不为NULL
SELECT COUNT(DISTINCT user_id, product_id)
FROM order_table
WHERE user_id IS NOT NULL AND product_id IS NOT NULL;
```

#### bad case:

```sql
-- 多列去重统计时未考虑NULL值
SELECT COUNT(DISTINCT user_id, product_id) FROM order_table;

-- 如果product_id列全为NULL，即使user_id有不同值，结果也是0
```

### java-l1:DB-02.N010 避免SUM函数的NPE问题示例

#### good case:

```sql
-- 使用IFNULL避免NPE问题
SELECT IFNULL(SUM(amount), 0) FROM order_table WHERE user_id = 123;

-- 使用COALESCE处理NULL值
SELECT COALESCE(SUM(amount), 0) FROM order_table WHERE status = 'cancelled';
```

#### bad case:

```sql
-- 直接使用SUM，可能返回NULL
SELECT SUM(amount) FROM order_table WHERE user_id = 999; -- 如果没有数据，返回NULL

-- 在应用层可能导致NPE
-- Java代码: Integer total = result.getInt("total"); // 如果SUM返回NULL会抛异常
```

### java-l1:DB-02.N011 使用utf8mb4字符集示例

#### good case:

```sql
-- 创建表时指定utf8mb4字符集
CREATE TABLE user_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 修改现有表的字符集
ALTER TABLE user_table CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### bad case:

```sql
-- 使用utf8字符集（不支持4字节字符如表情）
CREATE TABLE user_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 使用latin1字符集
CREATE TABLE user_table (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
```

### java-l1:DB-02.N012 禁止DDL操作示例

#### good case:

```sql
-- 应用程序中只执行DML操作
SELECT * FROM user_table WHERE id = 1;
INSERT INTO user_table (name, email) VALUES ('John', 'john@example.com');
UPDATE user_table SET last_login = NOW() WHERE id = 1;
DELETE FROM user_table WHERE id = 1;
```

#### bad case:

```sql
-- 应用程序中执行DDL操作
CREATE TABLE temp_table (id INT, name VARCHAR(50));
ALTER TABLE user_table ADD COLUMN phone VARCHAR(20);
DROP TABLE temp_table;
CREATE INDEX idx_name ON user_table(name);
```

### java-l1:DB-02.N013 控制批量操作数量示例

#### good case:

```sql
-- 分批插入数据
INSERT INTO user_table (name, email) VALUES
('User1', 'user1@example.com'),
('User2', 'user2@example.com'),
-- ... 不超过1000条
('User999', 'user999@example.com');

-- 分批更新数据
UPDATE user_table SET status = 'active' WHERE id BETWEEN 1 AND 1000;

-- 等待一段时间后继续下一批
UPDATE user_table SET status = 'active' WHERE id BETWEEN 1001 AND 2000;
```

#### bad case:

```sql
-- 一次性插入大量数据
INSERT INTO user_table (name, email) VALUES
('User1', 'user1@example.com'),
('User2', 'user2@example.com'),
-- ... 超过1000条甚至更多
('User5000', 'user5000@example.com');

-- 一次性更新大量数据
UPDATE user_table SET status = 'active' WHERE create_time < '2023-01-01'; -- 可能影响数万条记录
```

### java-l1:DB-02.N014 禁止使用通配符查询示例

#### good case:

```sql
-- 明确指定需要的字段
SELECT id, name, email, status FROM user_table WHERE id = 1;

-- 即使查询所有字段，也要明确列出
SELECT id, name, email, phone, address, create_time, update_time
FROM user_table WHERE status = 'active';
```

#### bad case:

```sql
-- 使用通配符*查询
SELECT * FROM user_table WHERE id = 1;

-- 查询大表时使用*，可能包含TEXT字段
SELECT * FROM user_table WHERE status = 'active';
```

### java-l1:DB-02.N015 动态 SQL 必须安全校验示例

> 动态列名/字段名的 SecSdk 校验示例详见 `SEC-01` java-l1:SEC-01.SEC-A003，本节仅展示 LIMIT 上限控制。

#### good case:

```java
// 查询接口设置 LIMIT 上限
int limit = Integer.parseInt(request.getParameter("limit"));
if (limit > 100) { limit = 100; }
String sql = "SELECT id, name FROM user_table LIMIT ? OFFSET ?";
```

#### bad case:

```java
// 不设 LIMIT - 可能返回大量数据
String sql = "SELECT * FROM user_table";  // 无上限!
```

## 五、规范执行要点

### 核心要求
1. **存储过程**：禁止使用存储过程(难以调试、扩展和移植)
2. **SQL格式**：关键字和字段类型必须大写,关键字换行对齐
3. **删除修改操作**：必须先SELECT确认后再执行UPDATE/DELETE
4. **外键和级联**：禁止使用,一切外键概念在应用层解决
5. **表别名**：多表操作必须使用表别名限定列名
6. **IN操作**：尽量避免,必须使用时控制在200个元素以内
7. **NULL判断**：条件判断使用IS NULL / IS NOT NULL，表达式兜底使用IFNULL()或COALESCE()
8. **行数统计**：必须使用COUNT(*),不使用COUNT(列名)或COUNT(常量)
9. **COUNT DISTINCT**：注意如果某列全为NULL会返回0
10. **SUM函数**：注意列全为NULL时返回NULL,需防范NPE
11. **字符集**：必须使用utf8mb4字符集(支持表情和国际化)
12. **DDL操作**：应用程序禁止DDL操作,DDL走RDS平台
13. **批量操作**：单次操作少于1000条,超过需拆分并增加缓冲时间
14. **字段列表**：禁止使用SELECT *,必须明确指定字段
15. **动态SQL安全**：表名列名必须使用 SecSdk 白名单校验,查询需设 LIMIT 上限(≤100)
- ✗ 禁止直接拼接用户输入到 SQL（必须参数化或 SecSdk 校验）
- ✗ 禁止查询接口不设 LIMIT 上限（可能导致全表扫描或大量数据泄露）

### 代码审查检查点
- [ ] 是否使用了存储过程
- [ ] SQL关键字和字段类型是否大写
- [ ] DELETE/UPDATE前是否先SELECT确认
- [ ] 是否使用了外键或级联
- [ ] 多表操作是否使用了表别名
- [ ] IN操作元素数量是否超过200个
- [ ] 条件判断是否使用了IS NULL / IS NOT NULL
- [ ] 行数统计是否使用了COUNT(*)
- [ ] SUM函数是否做了NULL值处理
- [ ] 是否使用了utf8mb4字符集
- [ ] 应用程序中是否存在DDL操作
- [ ] 批量操作是否超过1000条
- [ ] 是否使用了SELECT *通配符
- [ ] 动态表名/列名是否经过 SecSdk 或白名单校验
- [ ] 对外查询接口是否设置了 LIMIT 上限(建议 ≤100)
