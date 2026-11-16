---
ruleType: Model Request
description: 写try-catch/抛异常/异常封装/方法返回值时读我。规定异常返回值避免null(用空集合/Optional)、捕获范围(RPC/二方包用Throwable非Exception)、NPE 7类高风险场景防御。写catch块或自定义异常时必读。异常分类与防御见HA-03。
category: Java编码规范
priority: high
---

# Java异常处理规范

## 一、说明

本规范定义了Java异常处理的标准，涵盖异常分类、捕获处理、自定义异常设计、异常链传递、资源清理和异常日志记录的完整规范。异常机制设计用于应对程序运行时的非预期错误，正确使用异常处理能够提高代码的健壮性和可维护性。

## 二、规则内容

### 异常处理作用域总则表（JAVA-05 / HA-03 / HA-01 边界划分）

| 话题 | JAVA-05 | `HA-03` 防御性编程 | `HA-01` 失败设计 |
|------|---------|---------------------|------------------|
| 异常捕获语法（catch 范围 / Throwable） | **N009** | — | — |
| 返回值（避免 null / 空集合 / Optional） | **N004** | — | — |
| 异常分类（业务/系统，触发策略） | — | **HA-D003** | — |
| 空指针防御 | — | **HA-D002** | — |
| 参数前置校验 | — | **HA-D001** | — |
| 资源释放（try-with-resources / finally） | — | **HA-D004** | — |
| 外部调用失败（超时/重试/熔断/降级/限流） | — | — | **HA-F001~F005** |

> **边界原则**：JAVA-05 聚焦「异常怎么写」（捕获、日志、返回值）；HA-03 聚焦「防御怎么做」（资源管理、参数校验、异常分类策略）；HA-01 聚焦「外部调用失败怎么应对」（超时/重试/熔断/降级/限流），不讲异常语法。

### N002 [强制] NPE防御规范

必须防御NullPointerException，重点关注7类高风险场景。

**说明**：高风险场景包括：
- 基本类型包装类返回值
- 数据库查询结果
- 集合元素
- 远程调用返回值
- Session数据
- 级联调用
- 并发集合操作

### N004 [推荐] 返回值规范

方法返回值尽量避免null，可返回空集合/空对象或使用Optional，若返回null必须注释说明。

### N009 [强制] 异常捕获范围规范

调用RPC、二方包或动态生成类时使用Throwable捕获异常，业务代码禁止捕获Error及其子类。

**说明**：避免捕获VirtualMachineError、OutOfMemoryError等系统级异常，此类异常无法恢复，应终止程序并释放资源。

## 三、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N004 返回值规范示例

#### good case:

```java
// 使用空集合替代null
public List<User> getUsers() {
    return Collections.emptyList();
}

// 使用Optional包装可能null的返回值
public Optional<User> findUserById(Long id) {
    // ...
}
```

### N009 异常捕获范围规范示例

#### bad case:

```java
// 错误：捕获Exception无法处理NoSuchMethodError
try {
    // 调用二方包方法
} catch (Exception e) {
    // 无法处理类冲突导致的NoSuchMethodError
}
```

## 四、规范执行要点

- 向上抛出时必须保留原始异常（`catch(e) throw new Xxx(e)`），禁止 `throw new Xxx()` 丢链
- catch 后必须记录详细日志（上下文 + 堆栈），禁止吞异常或 `return null` 不记日志
- finally 中关闭资源或使用 try-with-resources（详见 HA-03 HA-D004）
