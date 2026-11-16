---
ruleType: Model Request
description: Java异常处理规范，涵盖异常分类、捕获处理、自定义异常设计、异常链传递、资源清理和异常日志记录的完整规范
category: Java编码规范
priority: high
---

# Java异常处理规范

## 一、说明

本规范定义了Java异常处理的标准，涵盖异常分类、捕获处理、自定义异常设计、异常链传递、资源清理和异常日志记录的完整规范。异常机制设计用于应对程序运行时的非预期错误，正确使用异常处理能够提高代码的健壮性和可维护性。

## 二、规则内容

### 异常处理作用域总则表（JAVA-05 / HA-03 / HA-01 边界划分）

| 话题 | `JAVA-05` 异常处理 | `HA-03` 防御性编程 | `HA-01` 失败设计 |
|------|------------------|---------------------|------------------|
| 异常分类 | **java-l1:JAVA-05.N001** 禁用于流程控制、**java-l1:JAVA-05.N005** 类型规范、**java-l1:JAVA-05.N006** 分类处理 | **java-l1:HA-03.HA-D003** 业务/系统/第三方 + 处理策略 | — |
| NPE 防御 | **java-l1:JAVA-05.N002** 7 类高风险场景 | **java-l1:HA-03.HA-D002** 空指针主动防御（Optional/requireNonNull） | — |
| 异常捕获 | **java-l1:JAVA-05.N003** catch 匹配、**java-l1:JAVA-05.N009** 范围/Throwable、**java-l1:JAVA-05.N010** finally 不返回 | — | — |
| 返回值/日志 | **java-l1:JAVA-05.N004** 返回值规范、**java-l1:JAVA-05.N007**/**java-l1:JAVA-05.N008** 预检查/运行时说明 | — | — |
| 资源管理 | — | **java-l1:HA-03.HA-D004** try-with-resources / finally 关闭 | — |
| 参数校验 | — | **java-l1:HA-03.HA-D001** 前置校验（Preconditions） | — |
| 外部调用失败 | — | — | **java-l1:HA-01.HA-F001~F006** 超时/重试/熔断/降级/限流/弱依赖 |

> **边界原则**：JAVA-05 聚焦「异常怎么写」（捕获、日志、返回值）；HA-03 聚焦「防御怎么做」（资源管理、参数校验、异常分类策略）；HA-01 聚焦「外部调用失败怎么应对」（超时/重试/熔断/降级/限流），不讲异常语法。
> **异常框架关系**：JAVA-05 的"稳定代码/非稳定代码"分类与 HA-03 的"业务异常/系统异常"分类是互补的两个维度——HA-03 按异常来源分类，JAVA-05 按代码稳定性分类，两者配合使用，不互相替代。

### java-l1:JAVA-05.N001 [强制] 异常使用规范

异常不得用于流程控制或条件判断，仅用于处理非预期错误场景。

**说明**：异常机制设计用于应对程序运行时的非预期错误，禁止通过捕获异常实现业务逻辑判断（如通过异常判断文件是否存在）。

### java-l1:JAVA-05.N002 [强制] NPE防御规范

必须防御NullPointerException，重点关注7类高风险场景。

**说明**：高风险场景包括：
- 基本类型包装类返回值
- 数据库查询结果
- 集合元素
- 远程调用返回值
- Session数据
- 级联调用
- 并发集合操作

### java-l1:JAVA-05.N003 [强制] 异常捕获匹配规范

捕获异常必须与抛出异常完全匹配或为其父类，确保异常处理逻辑有效。

**说明**：若捕获异常类型与实际抛出类型不匹配，可能导致异常未被正确处理（如捕获Exception却抛出RuntimeException）。

### java-l1:JAVA-05.N004 [推荐] 返回值规范

方法返回值尽量避免null，可返回空集合/空对象或使用Optional，若返回null必须注释说明。

### java-l1:JAVA-05.N005 [强制] 异常类型规范

区分checked/unchecked异常，禁止直接抛出RuntimeException，应使用自定义业务异常。

**说明**：自定义异常需继承特定业务异常基类（如DAOException、ServiceException），避免抛出通用Exception或Throwable。

### java-l1:JAVA-05.N006 [强制] 异常分类处理规范

捕获异常时需区分稳定代码与非稳定代码，对非稳定代码的异常分类处理。

**说明**：大段代码统一try-catch会掩盖异常类型，应针对不同操作分块处理（如用户注册时区分用户名已存在和密码格式错误）。

### java-l1:JAVA-05.N007 [推荐] 可预检查异常规范

可通过预检查规避的RuntimeException（如NPE、IndexOutOfBoundsException）不应通过catch处理。

**说明**：例如：在访问集合元素前先检查索引范围，避免捕获IndexOutOfBoundsException。

### java-l1:JAVA-05.N008 [推荐] 运行时异常说明规范

若因合理原因抛出RuntimeException或其子类，必须在接口文档中明确异常处理逻辑。

### java-l1:JAVA-05.N009 [强制] 异常捕获范围规范

调用RPC、二方包或动态生成类时使用Throwable捕获异常，业务代码禁止捕获Error及其子类。

**说明**：避免捕获VirtualMachineError、OutOfMemoryError等系统级异常，此类异常无法恢复，应终止程序并释放资源。

### java-l1:JAVA-05.N010 [强制] finally返回规范

禁止在finally块中使用return，避免覆盖try块的返回值。

## 三、执行要求

1. 所有异常处理必须遵循本规范要求
2. 代码审查时重点检查异常处理的合理性
3. 对于违反规范的代码必须及时整改
4. 新代码必须严格按照本规范编写

## 四、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:JAVA-05.N002 NPE防御规范示例

#### good case:

```java
// 集合元素NPE防御
List<String> list = new ArrayList<>();
list.add(null);
if (CollectionUtils.isNotEmpty(list)) {
    String first = list.get(0);
    if (first != null) {
        process(first);
    }
}

// 级联调用NPE防御
User user = getUserFromDB();
if (user != null) {
    Address address = user.getAddress();
    if (address != null) {
        String city = address.getCity();
    }
}
```

#### bad case:

```java
// 反例1：自动拆箱NPE
private Integer value = null;
public int getValue() {
    return value; // 自动拆箱抛出NPE
}

// 反例2：并发集合NPE
if (map.get(key) != null) {
    map.get(key).method(); // 线程安全问题，可能NPE
}
```

### java-l1:JAVA-05.N004 返回值规范示例

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

### java-l1:JAVA-05.N006 异常分类处理规范示例

#### good case:

```java
try {
    validateUsername(username);
    validatePassword(password);
} catch (UsernameExistsException e) {
    log.warn("用户名已存在", e);
    return USERNAME_EXISTS;
} catch (PasswordFormatException e) {
    log.error("密码格式错误", e);
    return PASSWORD_INVALID;
}
```

### java-l1:JAVA-05.N009 异常捕获范围规范示例

#### bad case:

```java
// 错误：捕获Exception无法处理NoSuchMethodError
try {
    // 调用二方包方法
} catch (Exception e) {
    // 无法处理类冲突导致的NoSuchMethodError
}
```

### java-l1:JAVA-05.N010 finally返回规范示例

#### bad case:

```java
public int getValue() {
    int result = 10;
    try {
        return result; // try块返回10
    } finally {
        result = 20;
        return result; // finally返回20，覆盖try的返回值
    }
}
```

## 五、规范执行要点

### 核心要求
1. **异常用途**：仅用于处理非预期错误,禁止用于流程控制或条件判断
2. **NPE防御**：必须防御7类高风险场景(包装类、数据库查询、集合元素、RPC返回、Session、级联调用、并发集合)
3. **异常匹配**：捕获异常必须与抛出异常完全匹配或为其父类
4. **返回值规范**：避免返回null,优先返回空集合/空对象或Optional,返回null必须注释说明
5. **自定义异常**：禁止直接抛RuntimeException,必须使用业务异常基类(如DAOException、ServiceException)
6. **异常分类**：区分稳定代码和非稳定代码,对不同操作分块处理异常
7. **预检查优先**：可预检查的异常(NPE、IndexOutOfBoundsException)不应通过catch处理
8. **异常传递**：向上抛出时必须使用原始异常(catch(e) throw new XXX(e))保留异常链
9. **finally资源清理**：必须在finally中关闭资源或使用try-with-resources
10. **异常日志**：catch异常后必须记录详细日志(上下文、堆栈信息)

### 强制禁止
- ✗ 禁止用异常做流程控制(如try获取文件判断是否存在)
- ✗ 禁止直接抛RuntimeException、Exception或Throwable
- ✗ 禁止大段代码统一try-catch(会掩盖异常类型)
- ✗ 禁止吞掉异常(catch后不处理不记录)
- ✗ 禁止向上抛出时丢失原始异常(throw new XXX() 而非 throw new XXX(e))
- ✗ 禁止业务代码捕获Error及其子类
- ✗ 禁止finally块中再抛异常(会覆盖原异常)
- ✗ 禁止catch后return null不记录日志

### 代码审查检查点
- [ ] 是否用异常做流程控制
- [ ] NPE高风险场景是否做了防御判断
- [ ] 返回null的方法是否有注释说明
- [ ] 是否直接抛出了RuntimeException/Exception/Throwable
- [ ] 自定义异常是否继承了业务异常基类
- [ ] 大段代码是否统一try-catch未分块处理
- [ ] 可预检查的异常是否错误地使用了catch
- [ ] 向上抛出异常时是否保留了原始异常
- [ ] finally中是否正确关闭了资源
- [ ] catch异常后是否记录了详细日志