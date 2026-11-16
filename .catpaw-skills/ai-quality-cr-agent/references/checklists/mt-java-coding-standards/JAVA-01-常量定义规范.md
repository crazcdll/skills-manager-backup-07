---
ruleType: Model Request
description: Java常量定义和使用规范，包含魔法值避免、long类型赋值、枚举类型使用等常量处理要求
category: Java编码规范
priority: medium
---

# Java常量定义规范

## 一、说明

本规范定义了Java常量定义和使用的标准，包含魔法值避免、long类型赋值规范、枚举类型使用建议等内容。统一的常量定义能够提高代码的可读性和可维护性。

## 二、规则内容

### java-l1:JAVA-01.N001 [推荐] 魔法值建议避免

除字符串模板外，代码中不建议直接使用魔法值（未经定义的数值或字符串）。

**说明**：应该将数值或字符串定义为常量并统一维护，同时确保不定义逻辑相同但字面值不同的常量，以防止混淆和错误。

### java-l1:JAVA-01.N002 [强制] long类型赋值规范

long或Long赋值，数值后使用大写L，避免小写l和数字1混淆。

### java-l1:JAVA-01.N003 [推荐] 枚举类型使用建议

如果变量值仅在一个固定范围内变化，用enum类型来定义。

**说明**：推荐使用枚举类型代替int常量，只要有一组在编译时已知的成员常量，就可以使用枚举。

## 三、执行要求

1. 所有常量定义必须遵循本规范要求
2. 代码审查时重点检查魔法值使用
3. 对于违反规范的代码必须及时整改
4. 新代码必须严格按照本规范编写

## 四、示例

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### java-l1:JAVA-01.N001 魔法值示例

#### good case:

```java
private static final String SUCCESS_MESSAGE = "操作成功";
```

#### bad case:

```java
if (status == 1) {
    logger.info("状态为成功");
}
```

### java-l1:JAVA-01.N002 long类型赋值规范示例

#### good case:

```java
long count = 2000L;
Long maxValue = 999999999999L;
```

#### bad case:

```java
long count = 2000l;
Long maxValue = 999999999999l;
```

### java-l1:JAVA-01.N003 枚举类型使用建议示例

#### good case:

```java
public enum Status {
    PENDING,
    PROCESSING,
    COMPLETED,
    FAILED
}

public enum Priority {
    LOW(1),
    MEDIUM(2),
    HIGH(3);

    private final int value;

    Priority(int value) {
        this.value = value;
    }
}
```

#### bad case:

```java
public static final int STATUS_PENDING = 0;
public static final int STATUS_PROCESSING = 1;
public static final int STATUS_COMPLETED = 2;
public static final int STATUS_FAILED = 3;
```

## 五、规范执行要点

### 核心要求
1. **魔法值**：代码中不建议直接使用未定义的数值或字符串(字符串模板除外)
2. **常量定义**：数值和字符串必须定义为常量并统一维护
3. **long类型赋值**：数值后必须使用大写L,禁止小写l(易与数字1混淆)
4. **枚举类型优先**：固定范围的值必须使用enum类型,而非int常量

### 强制禁止
- ✗ 不建议直接使用魔法值(如if(status==1))
- ✗ 不建议定义逻辑相同但字面值不同的常量(如SUCCESS="success", OK="success")
- ✗ 禁止long赋值使用小写l(如long time=123456789l)
- ✗ 禁止用int常量代替枚举(如STATUS_PENDING=0, STATUS_PROCESSING=1)

### 代码审查检查点
- [ ] 是否存在魔法值(未定义的数值或字符串)
- [ ] 常量是否统一定义和管理
- [ ] long类型赋值是否使用了大写L
- [ ] 固定范围的值是否使用了enum而非int常量
- [ ] 是否存在逻辑相同但字面值不同的重复常量定义