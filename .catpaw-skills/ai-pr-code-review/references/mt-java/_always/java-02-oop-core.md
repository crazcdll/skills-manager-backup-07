## JAVA-02 OOP设计规约 — 核心审查精要（N005/N006）

> 本文件仅提取路由表指定的 N005（数值比较）和 N006（条件判断与可读性）子集。

### MT:N005 数值比较规范

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N005a | 包装类型（Integer/Long）禁止用 `==` 比较，必须用 `.equals()` | P2 |
| MT:N005b | 浮点数禁止用 `==` 直接比较，应使用差值与精度阈值比较 | P2 |
| MT:N005c | BigDecimal禁止用 `.equals()` 比较（会比较精度），必须用 `.compareTo()` | P2 |
| MT:N005d | 禁止用 `double` 构造 `BigDecimal`，必须用 `String` 或 `BigDecimal.valueOf()` | P2 |

### MT:N006 条件判断与代码可读性规范

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N006a | 复杂条件判断结果赋值给语义化布尔变量 | P2 |
| MT:N006b | 热点路径方法优先使用 static/final/private 修饰 | P2 |
| MT:N006c | 深度递归（>1000层）改用迭代实现 | P2 |
| MT:N006d | 避免过深的调用链（建议 ≤5 层） | P2 |

### 强制禁止
- ✗ 禁止使用 `==` 比较包装类型（-128~127范围外结果不正确）
- ✗ 禁止使用 `==` 比较浮点数
- ✗ 禁止用 `double` 构造 `BigDecimal`
- ✗ 禁止用 `.equals()` 比较 `BigDecimal`（应 `.compareTo()`）

### 检查点
- [ ] 包装类型比较是否用了 `.equals()`
- [ ] BigDecimal 是否用了 `.compareTo()` 且用 String/valueOf 构造
- [ ] 复杂条件是否赋值给布尔变量
- [ ] 是否存在深度递归

→ 完整规则含示例见 mt-java-coding-standards/JAVA-02-OOP设计规约.md
