---
ruleType: Model Request
description: 写delete/update/批量IN/动态SQL/COUNT(DISTINCT)/DDL语句时读我。强制删除修改必须有测试覆盖、禁止外键级联、限制IN元素数≤200、禁止DDL、批量≤1000(高可用≤200见HA-04)、动态SQL安全校验。写DML或批量操作时必读。
category: SQL规范
priority: high
---

# MySQL SQL开发规范

## 一、说明

本规范定义了MySQL SQL开发的标准，包含存储过程使用、SQL格式、数据操作、字符集、批量操作等方面的规范要求。遵循本规范能够提高SQL的可读性、可维护性和执行效率，避免常见的性能问题和安全风险。

## 二、规则内容

### N003 [强制] 必须有测试覆盖的删除修改操作

删除或修改记录等操作时，必须有测试覆盖，避免误操作。建议先SELECT，确认无误才能执行更新语句。

### N004 [强制] 禁止使用外键和级联

不得使用外键与级联，一切外键概念必须在应用层解决。

**说明**：外键与级联更新适用于单机低并发，不适合分布式、高并发集群；级联更新是强阻塞，存在数据库更新风暴的风险；外键影响数据库的插入速度。

### N006 [推荐] 限制IN操作元素数量

IN操作能避免则避免，若实在避免不了，需要仔细评估IN后边的集合元素数量，控制在200个之内。

### N009 [推荐] 注意COUNT DISTINCT的特殊行为

COUNT(DISTINCT col)计算该列除NULL之外的不重复行数，注意COUNT(DISTINCT col1, col2)如果其中一列全为NULL，那么即使另一列有不同的值，也返回为0。

### N012 [强制] 禁止DDL操作

应用程序里的语句，禁止一切DDL操作。DDL走RDS平台。

### N013 [推荐] 控制批量操作数量

大批量INSERT/UPDATE/DELETE数据时，建议单次操作少于1000条，超过时，要拆分，并在每批之间增加缓冲时间以减少主从延时的影响。**高可用场景（减少锁持有时间）要求每批 ≤200 条，详见 `HA-04` HA-S002。**

### N015 [强制] 动态 SQL 必须安全校验

对于无法通过预编译参数绑定（`#{}`）的动态场景——如表名、列名、ORDER BY 字段等——必须实施白名单校验或使用安全 SDK 进行合法性验证。

**说明**：
- 动态表名/列名 `${}` 使用与白名单校验详见 `DB-01` ORM002；ORDER BY/GROUP BY 动态字段名的 `SecSdk.isValidSqlIdentifier()` 校验与 SDK 依赖详见 `SEC-01` SEC-A003
- **查询结果数量上限**：对外暴露的查询接口必须设置 LIMIT 上限（建议 ≤100 条），防止性能问题和数据泄露

## 三、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N003 必须有测试覆盖的删除修改操作示例

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

### N004 禁止使用外键和级联示例

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

### N006 限制IN操作元素数量示例

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

### N009 注意COUNT DISTINCT的特殊行为示例

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

### N012 禁止DDL操作示例

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

### N013 控制批量操作数量示例

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

### N015 动态 SQL 必须安全校验示例

> 动态列名 `${}` / SecSdk 校验的示例详见 `DB-01` ORM002 与 `SEC-01` SEC-A003，本节仅展示 DB-02 独有的查询结果数量上限。

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

## 四、规范执行要点

- ✗ 禁止查询接口不设 LIMIT 上限（可能导致全表扫描或大量数据泄露）
- ✗ 禁止 IN 操作超过 200 个元素、单次批量操作超过 1000 条
- ✗ 禁止应用程序执行 DDL（走 RDS 平台）
