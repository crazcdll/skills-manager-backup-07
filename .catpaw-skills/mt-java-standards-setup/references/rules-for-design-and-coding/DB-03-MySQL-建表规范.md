---
ruleType: Model Request
description: 做建表/改表/DDL设计时读我。规定表必备字段(id/create_time/update_time/is_delete)、枚举与布尔建模、字符串类型选择、逻辑删除字段。新建表或加字段前必读。
category: SQL规范
priority: medium
---

# MySQL数据库建表规范

## 一、说明

本规范定义了MySQL数据库建表的标准，包含表引擎选择、必备字段、命名规范、字段类型选择、注释要求等方面的规范。遵循本规范能够确保数据库设计的规范性和一致性。

## 二、规则内容

### N002 [强制] 表必备字段要求

表必备字段：主键。建议字段：创建时间、更新时间。

**说明**：
- 更新时间建议设置默认值DEFAULT NOW() ON UPDATE CURRENT_TIMESTAMP，并增加索引
- 主键类型为BIGINT、单表时自增、步长为1
- 时间字段类型为DATETIME，不建议使用TIMESTAMP

### N006 [推荐] 枚举与布尔字段建模规范

枚举字段应优先选择语义清晰、演进成本可控的建模方式。布尔字段是取值稳定、语义明确的特殊枚举场景。

**说明**：
- **枚举字段**：对查询频繁、取值稳定且性能敏感的状态字段，可使用 TINYINT/SMALLINT 等数值枚举，但**必须通过注释或字典明确取值语义**；一般场景优先使用 VARCHAR 字符串枚举（如 `'active'`/`'inactive'`）
- **布尔字段**：表达「是与否」概念的字段，命名使用 `xxx_flag` / `xxx_status`，类型为 `TINYINT UNSIGNED`（1=是, 0=否），注释中明确 1/0 语义
- **共同要求**：禁止无注释的数字枚举；禁止使用 BOOLEAN 类型（MySQL 的 TINYINT(1) 别名不够明确）

### N008 [推荐] 字符串类型选择

如果存储固定长度的字符串，使用CHAR定长字符串类型。VARCHAR长度不要超过5000，如果存储长度大于此值，定义字段类型为TEXT，独立出来一张表。

### N011 [强制] 逻辑删除建议

数据库中不使用物理删除操作，建议使用逻辑删除。

## 三、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N002 表必备字段要求示例

#### good case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_update_time (update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### bad case:

```sql
CREATE TABLE user_info (
    name VARCHAR(50) NOT NULL,
    create_time TIMESTAMP
) ENGINE=InnoDB;
```

### N006 枚举字段建模规范示例

#### good case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE task_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1-待处理 2-处理中 3-已完成',
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

#### bad case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    status TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

-- 错误原因：使用数值枚举但未通过注释说明取值语义，后续维护成本高

### N007 布尔字段命名规范示例

#### good case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    deleted_flag TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '1-已删除 0-未删除',
    active_status TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1-激活 0-未激活',
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

#### bad case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    is_deleted BOOLEAN DEFAULT FALSE,
    active INT DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

-- 错误原因：命名不统一，且active字段未通过注释说明1/0语义

### N009 字符串类型选择示例

#### good case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    mobile CHAR(11) NOT NULL,
    name VARCHAR(50),
    PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE user_content (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    content TEXT,
    PRIMARY KEY (id),
    KEY idx_user_id (user_id)
) ENGINE=InnoDB;
```

#### bad case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    mobile VARCHAR(11) NOT NULL,
    description VARCHAR(8000),
    PRIMARY KEY (id)
) ENGINE=InnoDB;
```

### N012 逻辑删除建议示例

#### good case:

```sql
CREATE TABLE user_info (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    deleted_flag TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '删除标识：0-未删除 1-已删除',
    PRIMARY KEY (id),
    KEY idx_deleted_flag (deleted_flag)
) ENGINE=InnoDB;

-- 逻辑删除操作
UPDATE user_info SET deleted_flag = 1 WHERE id = 123;
```

#### bad case:

```sql
-- 物理删除操作
DELETE FROM user_info WHERE id = 123;
```

## 四、规范执行要点

- ✗ 禁止表没有主键
- ✗ 禁止使用 TIMESTAMP 类型（时区问题）
- ✗ 禁止枚举字段使用数字（如 1,2,3）
- ✗ 禁止 VARCHAR 超过 5000（应拆分为 TEXT 独立表）
- ✗ 禁止物理删除数据（DELETE 操作）
