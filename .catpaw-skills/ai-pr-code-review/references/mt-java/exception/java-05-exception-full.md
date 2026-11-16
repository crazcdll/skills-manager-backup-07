## JAVA-05 异常处理规范（完整审查精要）

> 本文件提取 JAVA-05 的完整规则集，用于 SIG-EXCEPTION 触发场景。

| 编号 | 规则 | 级别 |
|------|------|------|
| MT:N001 | 异常不得用于流程控制或条件判断，仅用于处理非预期错误 | P1 |
| MT:N002 | 必须防御NPE，重点关注7类高风险场景（包装类/DB查询/集合元素/RPC返回/Session/级联/并发集合） | P0 |
| MT:N003 | 捕获异常必须与抛出异常完全匹配或为其父类 | P1 |
| MT:N004 | 方法返回值尽量避免null，可返回空集合/空对象或Optional，返回null必须注释说明 | P1 |
| MT:N005 | 禁止直接抛出RuntimeException，应使用自定义业务异常继承业务异常基类 | P1 |
| MT:N006 | 捕获异常时需区分稳定代码与非稳定代码，对非稳定代码分块处理 | P1 |
| MT:N007 | 可通过预检查规避的RuntimeException不应通过catch处理 | P1 |
| MT:N008 | 因合理原因抛出RuntimeException必须在接口文档中明确异常处理逻辑 | P1 |
| MT:N009 | 调用RPC/二方包/动态生成类时用Throwable捕获，业务代码禁止捕获Error及其子类 | P1 |
| MT:N010 | 禁止在finally块中使用return，避免覆盖try块的返回值 | P1 |

### 强制禁止
- ✗ 禁止用异常做流程控制
- ✗ 禁止直接抛 RuntimeException、Exception 或 Throwable
- ✗ 禁止大段代码统一 try-catch（会掩盖异常类型）
- ✗ 禁止吞掉异常（catch后不处理不记录）
- ✗ 禁止向上抛出时丢失原始异常（`throw new XXX()` 而非 `throw new XXX(e)`）
- ✗ 禁止业务代码捕获 Error 及其子类
- ✗ 禁止 finally 块中再抛异常
- ✗ 禁止 catch 后 return null 不记录日志

### 检查点
- [ ] 是否用异常做流程控制
- [ ] NPE 高风险场景是否做了防御
- [ ] 返回 null 的方法是否有注释说明
- [ ] 是否直接抛出了 RuntimeException/Exception/Throwable
- [ ] 自定义异常是否继承了业务异常基类
- [ ] 大段代码是否统一 try-catch 未分块处理
- [ ] 向上抛出异常时是否保留了原始异常
- [ ] finally 中是否正确关闭了资源
- [ ] catch 异常后是否记录了详细日志

→ 完整规则含示例见 mt-java-coding-standards/JAVA-05-异常处理规范.md
