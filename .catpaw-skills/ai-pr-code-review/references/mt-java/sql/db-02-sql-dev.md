## DB-02 MySQL SQL开发规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N001 | 禁止使用存储过程 | P1 |
| MT:N002 | SQL关键字和字段类型大写，关键字换行对齐 | P2 |
| MT:N003 | 删除/修改操作必须先SELECT确认，必须有测试覆盖 | P1 |
| MT:N004 | 禁止使用外键和级联，外键概念在应用层解决 | P1 |
| MT:N005 | 多表操作必须使用表别名限定列名 | P1 |
| MT:N006 | IN操作元素数量控制在200个之内 | P1 |
| MT:N007 | 条件判断用 IS NULL / IS NOT NULL；表达式兜底用 IFNULL()/COALESCE() | P1 |
| MT:N008 | 使用 COUNT(*) 统计行数，不用 COUNT(列名)/COUNT(常量) | P2 |
| MT:N009 | 注意 COUNT(DISTINCT col1, col2) 某列全NULL时返回0 | P2 |
| MT:N010 | SUM(col) 全NULL时返回NULL，需防范NPE（用 IFNULL 包裹） | P1 |
| MT:N011 | 必须使用 utf8mb4 字符集 | P1 |
| MT:N012 | 应用程序禁止DDL操作，DDL走RDS平台 | P1 |
| MT:N013 | 批量操作单次 ≤1000 条（高可用场景 ≤200 条），超过需拆分 | P1 |
| MT:N014 | 禁止 SELECT *，必须明确指定字段 | P2 |
| MT:N015 | 动态SQL必须安全校验（SecSdk白名单），查询接口设LIMIT上限(≤100) | P1 |

### 强制禁止
- ✗ 禁止使用存储过程
- ✗ 禁止使用外键和级联
- ✗ 禁止应用程序执行DDL
- ✗ 禁止 SELECT * 通配符查询
- ✗ 禁止 IN 元素超过200个
- ✗ 禁止批量操作超过1000条
- ✗ 禁止直接拼接用户输入到SQL

### 检查点
- [ ] SQL关键字是否大写
- [ ] DELETE/UPDATE前是否先SELECT确认
- [ ] IN元素数量是否超过200
- [ ] SUM函数是否做了NULL值处理
- [ ] 批量操作是否超过1000条
- [ ] 动态表名/列名是否经过SecSdk校验
- [ ] 查询接口是否设置LIMIT上限

→ 完整规则含示例见 mt-java-coding-standards/DB-02-MySQL-SQL开发规范.md
