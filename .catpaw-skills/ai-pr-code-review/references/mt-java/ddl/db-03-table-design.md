## DB-03 MySQL 建表规范（审查精要）

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N001 | 表必须使用 InnoDB 引擎 | P2 |
| MT:N002 | 表必备主键（BIGINT自增），建议含创建时间/更新时间（DATETIME，非TIMESTAMP） | P2 |
| MT:N003 | 表名/字段名只允许字母、数字、下划线，禁用保留字 | P2 |
| MT:N004 | 禁用 MySQL 保留字（DESC/RANGE/MATCH/DELAYED等） | P2 |
| MT:N005 | 表名使用单数形式，不用复数名词 | P2 |
| MT:N006 | 枚举字段优先用字符串；数值枚举必须注释；布尔用 xxx_flag/status + TINYINT UNSIGNED | P2 |
| MT:N007 | 小数类型必须用 DECIMAL，禁止 FLOAT/DOUBLE | P2 |
| MT:N008 | VARCHAR ≤5000，超过用 TEXT 独立表；固定长度用 CHAR | P2 |
| MT:N009 | 修改字段含义必须及时更新注释，建议所有表和字段都有注释 | P2 |
| MT:N010 | 单表 >1000万行或 >80GB 才考虑分库分表，避免过早优化 | P3 |
| MT:N011 | 优先使用逻辑删除，禁止物理删除 | P2 |

### 强制禁止
- ✗ 禁止使用 MyISAM 等非 InnoDB 引擎
- ✗ 禁止表没有主键
- ✗ 禁止使用 TIMESTAMP 类型（时区问题）
- ✗ 禁止表名/字段名使用 MySQL 保留字
- ✗ 禁止表名使用复数形式
- ✗ 禁止小数使用 FLOAT/DOUBLE
- ✗ 禁止 VARCHAR 超过 5000
- ✗ 禁止过早分库分表
- ✗ 禁止物理删除数据

### 检查点
- [ ] 表是否使用 InnoDB 引擎
- [ ] 主键是否 BIGINT 自增
- [ ] 时间字段是否用 DATETIME 而非 TIMESTAMP
- [ ] 枚举字段是否规范（字符串优先/数值需注释）
- [ ] 小数类型是否用 DECIMAL
- [ ] 是否存在物理删除操作

→ 完整规则含示例见 mt-java-coding-standards/DB-03-MySQL-建表规范.md
