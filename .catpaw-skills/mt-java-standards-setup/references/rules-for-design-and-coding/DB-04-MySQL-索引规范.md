---
ruleType: Model Request
description: 建索引/优化慢SQL/设计查询条件时读我。规定VARCHAR索引长度、覆盖索引使用、唯一索引命名。写where条件或加索引前读我防索引失效。
category: SQL规范
priority: medium
---

# MySQL数据库索引规范

## 一、说明

本规范定义了MySQL数据库索引的标准，包含索引创建原则、性能优化目标、组合索引设计、索引命名规范等方面的规范要求。合理使用索引能够显著提升查询性能。

## 二、规则内容

### N004 [推荐] VARCHAR字段索引长度

在VARCHAR字段上建立索引时，指定索引长度，索引长度可以根据实际文本区分度决定。

**说明**：一般对字符串类型数据，长度为20的索引，区分度会高达90%，可以使用COUNT(DISTINCT LEFT(列名，索引长度)) / COUNT(*)的区分度来确定。

### N007 [推荐] 覆盖索引使用

利用覆盖索引来进行查询操作，避免回表。

**说明**：能够建立索引的种类分为主键索引、唯一索引、普通索引三种，而覆盖索引只是查询的效果，用EXPLAIN的结果，extra列会出现：using index。

### N010 [推荐] 唯一索引命名规范

唯一索引建议以'uniq_字段1_字段2'形式命名，非唯一索引建议以'idx_字段1_字段2'形式命名。若字段过多可使用缩写。

## 三、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N004 VARCHAR字段索引长度示例

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

### N007 覆盖索引使用示例

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

### N010 唯一索引命名规范示例

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

## 四、规范执行要点

### 代码审查检查点
- [ ] VARCHAR索引是否指定了长度
- [ ] 是否使用了覆盖索引优化
- [ ] 索引命名是否规范（uniq_/idx_ 前缀）
