---
ruleType: Model Request
description: 写单测/@Test/测试用例时读我。规定测试方法编写格式与最佳实践。新增或修改业务代码需补单测时必读。
category: 代码规范
priority: high
---

# Java单元测试编写规范

## 1. 说明

- **适用场景**：Java项目单元测试编写（JUnit + Mockito）
- **依赖Context**：被测试代码的方法签名和依赖关系
- **期望输入**：待测试的Java类和方法
- **预期输出**：符合规范的单元测试代码

## 2. 规则内容

### N001 [强制] 测试方法编写规范

#### 注释要求
复杂测试方法建议包含JavaDoc注释，说明测试场景和预期结果；简单且命名自解释的测试可省略。

#### AAA格式
推荐使用 `// Arrange` → `// Act` → `// Assert` 组织测试逻辑；简单场景可不强制添加阶段注释，但测试结构应保持清晰。

#### 断言要求
- 每个测试方法必须包含有效断言
- 覆盖正常情况和异常情况
- 使用合适的断言方法（assertEquals、assertTrue、assertNotNull等）

#### 覆盖率要求
- 尽量覆盖所有代码行和分支
- 为所有可能的执行路径编写测试用例
- 覆盖正常流程、边界条件、异常分支

## 3. 执行要求

- 严格查看方法签名，嵌套时递归查看，避免编译错误
- 禁止测试方法没有有效断言

## 4. 示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

```java
// good：AAA 结构 + 有效断言 + 覆盖正常与异常分支
@Test
public void testCalcPrice_normal() {
    // Arrange
    when(mockSku.getPrice()).thenReturn(100);

    // Act
    int result = orderService.calcPrice(request);

    // Assert
    assertEquals(100, result);
}

@Test
public void testCalcPrice_invalidInput_throws() {
    // Arrange
    request.setQty(-1);

    // Act & Assert
    assertThrows(IllegalArgumentException.class, () -> orderService.calcPrice(request));
}
```

```java
// bad：无有效断言，AAA 阶段混乱
@Test
public void testCalc() {
    orderService.calcPrice(request); // 无断言，无法验证结果
}
```
