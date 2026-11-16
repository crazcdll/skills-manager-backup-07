---
ruleType: Model Request
description: 写Java类/POJO/对象拷贝/数值比较/条件判断时读我。规定类成员访问控制、内存泄漏预防、POJO设计、对象拷贝、数值比较(用compareTo非等号)、条件判断等编码质量。写业务模型或工具类时读我。
category: Java编码规范
priority: high
---

# Java OOP设计规约

## 说明

### 适用场景
本规范适用于所有Java项目的面向对象编程，包括类设计、成员访问控制、资源管理、POJO类设计、对象拷贝、数值比较，以及条件判断等通用编码质量规范。

### 目标
- 规范类成员和方法的访问控制，提升模块解耦能力
- 防止内存泄漏，确保应用程序的稳定性和性能
- 统一POJO类设计标准，保证数据传输对象的一致性
- 规范对象拷贝方式，避免性能问题
- 防止数值比较陷阱（浮点数、BigDecimal、包装类型）

### 依赖Context
无特殊依赖，可独立使用。

---

## 规则内容

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N001 [强制] 类成员与方法访问控制规范和方法定义

类成员与方法访问控制必须从严控制，任何类、方法、参数、变量都应严格控制访问范围。过于宽泛的访问范围不利于模块解耦。

#### 规范说明

**类成员与方法访问控制规范**：
1. 禁止外部实例化类对象，构造方法必须是private

**方法的定义和使用规范**：
6. 禁止使用过时的类或方法

##### good case:
```java
public class MathUtils {
   private MathUtils() {
        throw new UnsupportedOperationException("Utility class");
    }
}

public class UserService {
    private String serviceName;

    private void validateInput(String input) {
        // 内部使用的方法
    }

    @VisibleForTesting
    void processData() {
        // 仅对测试可见的方法
    }
}

// 正确：接口演进时保持向下兼容
public interface UserService {
    void saveUser(User user);

    // 正确：过时方法加@Deprecated注解并说明替代方案
    @Deprecated
    /**
     * @deprecated 该方法已过时，请使用 {@link #saveUser(User)} 代替
     * 将在v2.0版本中移除
     */
    void addUser(User user);

    // 新增方法，不影响现有调用
    void saveUserWithValidation(User user);
}

public class Constants {
    // 正确：public常量不提供getter/setter
    public static final String DEFAULT_ENCODING = "UTF-8";
}
```

##### bad case:
```java
public class BadStringUtils {
    // 错误：工具类允许实例化
    public BadStringUtils() {}

    // 错误：内部方法暴露为public
    public void internalMethod() {}
}

public class BadUserService {
    // 错误：应该使用private
    public String serviceName;

    private String userName;

    // 错误：public成员变量却提供了getter/setter
    public String getServiceName() {
        return serviceName;
    }

    // 错误：getter方法中包含业务逻辑
    public String getUserName() {
        if (userName == null) {
            userName = loadUserNameFromDatabase(); // 业务逻辑
        }
        return userName;
    }

    // 错误：setter方法参数名不一致
    public void setUserName(String name) {
        this.userName = name;
    }
}
```

---

### N002 [强制] 内存泄漏预防

必须采取措施防止内存泄漏，确保应用程序的稳定性和性能。

#### 规范说明

**限定信息**：
1. 最小化作用域
2. 避免在循环中创建对象，尤其是大型对象
3. 优先使用try-with-resources管理资源（完整资源管理规范详见 `HA-03` HA-D004）
4. 长时间存活的对象引用不再需要时应显式置为null
5. 局部变量引用的对象无需显式置null
6. 禁止使用终结器（finalize方法）
7. 确保释放元素时清除对象引用
8. 及时清理ThreadLocal变量（线程池场景下的 remove 规范详见 `HA-07` HA-J003）

##### good case:
```java
public class ResourceManager {
    // 正确使用try-with-resources
    public String readFile(String fileName) {
        try (BufferedReader reader = Files.newBufferedReader(Paths.get(fileName))) {
            return reader.lines().collect(Collectors.joining("\n"));
        } catch (IOException e) {
            throw new RuntimeException("File read failed", e);
        }
    }
}

// IO操作：缓冲流 + try-with-resources
try (BufferedReader reader = new BufferedReader(new FileReader("data.txt"));
     BufferedWriter writer = new BufferedWriter(new FileWriter("output.txt"))) {
    String line;
    while ((line = reader.readLine()) != null) {
        writer.write(line);
    }
}
```

##### bad case:
```java
public class BadResourceManager {
    // 错误：没有使用try-with-resources，资源可能泄漏
    public String readFile(String fileName) {
        BufferedReader reader = null;
        try {
            reader = Files.newBufferedReader(Paths.get(fileName));
            return reader.lines().collect(Collectors.joining("\n"));
        } catch (IOException e) {
            throw new RuntimeException("File read failed", e);
        }
        // 没有finally关闭资源
    }

    // 错误：在循环中创建大对象
    public void processLargeData() {
        for (int i = 0; i < 1000000; i++) {
            LargeObject obj = new LargeObject(); // 每次循环创建大对象
        }
    }

    // 错误：使用finalize
    @Override
    protected void finalize() throws Throwable {
        super.finalize();
    }
}
```

---

### N003 [强制] POJO类设计和实现规范

定义POJO类（DO/DTO/VO等）时必须遵循统一的设计和实现规范，确保类的正确性和一致性。

#### 规范说明

**限定信息**：
2. 不要设定任何属性默认值，由使用者显式赋值
7. 可使用@ToString注解自动生成，继承时需设置callSuper = true

##### good case:
```java
public class UserDO {
    private Long id; // 对应数据库BIGINT
    private String name; // 对应数据库VARCHAR
    private Integer age; // 对应数据库INT
    private Boolean active; // 对应数据库TINYINT(1)
    private LocalDateTime createTime; // 对应数据库DATETIME
}

@ToString(callSuper = true)
public class Employee extends Person {
    private Long employeeId;
    private String department;
    // 使用lombok自动生成toString
}
```

##### bad case:
```java
public class BadOrderDTO {
    private Long orderId;
    private String orderStatus = "PENDING"; // 错误：设置了默认值
}

public class BadUserDTO {
    private Boolean active;

    // 错误：同一属性同时存在isActive和getActive
    public Boolean isActive() {
        return active;
    }

    public Boolean getActive() {
        return active;
    }

    // 错误：没有status属性却定义了getter
    public String getStatus() {
        return "ACTIVE";
    }

    // 错误：业务处理方法与访问器方法重名
    public void setActive() {
        // 这是业务处理方法，但与setter重名
    }
}
```

---

### N004 [强制] 对象拷贝方法选择规范

对象拷贝时应选择合适的方法和工具，避免使用有问题的拷贝方式，确保拷贝的正确性和性能。

#### 规范说明

**限定信息**：
1. Object的clone方法、Apache BeanUtils、Spring BeanUtils、Cglib BeanCopier均为浅拷贝，MapStruct支持深拷贝
2. 避免使用Apache BeanUtils进行属性拷贝，性能最差
4. 数据量大的场景，建议用Cglib BeanCopier或MapStruct
5. 涉及大量数据转换、属性映射、格式转换等，用MapStruct

##### good case:
```java
// 正确：使用MapStruct进行对象转换
@Mapper
public interface UserConverter {
    UserConverter INSTANCE = Mappers.getMapper(UserConverter.class);

    @Mapping(source = "userName", target = "name")
    UserVO toVO(UserDO userDO);
}
```

##### bad case:
```java
public class BadUserConverter {
    // 错误：使用Apache BeanUtils，性能差
    public UserVO convertToVO(UserDO userDO) {
        UserVO userVO = new UserVO();
        try {
            BeanUtils.copyProperties(userVO, userDO); // Apache BeanUtils
        } catch (Exception e) {
            throw new RuntimeException("Copy failed", e);
        }
        return userVO;
    }
}
```

---

### N005 [强制] 数值比较规范

数值比较必须使用正确的比较方式，避免精度损失和语义错误。

#### 规范说明

1. **包装类型**：`Integer`/`Long` 等包装类型禁止用 `==` 比较（`-128~127` 范围外结果不正确），必须用 `.equals()`
2. **浮点数**：禁止用 `==` 直接比较 `double`/`float`，应使用差值与精度阈值比较
3. **BigDecimal**：禁止用 `.equals()` 比较（会比较精度，`1.0` 和 `1.00` 返回 `false`），必须用 `.compareTo()`；禁止用 `double` 构造 `BigDecimal`（精度损失），必须用 `String` 或 `BigDecimal.valueOf()`

##### good case:
```java
// 包装类型用 equals
Integer a = 200, b = 200;
boolean eq = a.equals(b); // 正确

// 浮点数用误差比较
double x = 0.1 + 0.2;
boolean close = Math.abs(x - 0.3) < 1e-9; // 正确

// BigDecimal 用 compareTo，用 String/valueOf 构造
BigDecimal price1 = new BigDecimal("1.0");
BigDecimal price2 = BigDecimal.valueOf(1.00);
boolean same = price1.compareTo(price2) == 0; // 正确，不比较精度
```

##### bad case:
```java
Integer a = 200, b = 200;
boolean eq = (a == b);          // 错误：超出缓存范围结果不正确

double x = 0.1 + 0.2;
boolean wrong = (x == 0.3);     // 错误：浮点精度问题

BigDecimal p1 = new BigDecimal(0.1);  // 错误：double 构造有精度损失
boolean bad = p1.equals(new BigDecimal("0.1")); // 错误：equals 比较精度
```

---

### N006 [推荐] 条件判断可读性与方法调用优化规范

复杂条件判断结果应赋值给语义化布尔变量；热点方法使用 `static`/`final` 减少虚方法查找；深度递归（>1000层）改用迭代。

#### 规范说明

1. 复杂条件的判断结果赋值给布尔变量，提升可读性，避免在条件中执行复杂逻辑
2. 热点路径方法优先使用 `static`/`final`/`private` 修饰，减少虚方法表查找
3. 深度递归（>1000 层）会导致 `StackOverflowError`，改用迭代实现
4. 避免过深的调用链（建议 ≤5 层），否则考虑内联或重构

##### good case:
```java
// 条件结果语义化命名
boolean isEligible = user.getAge() >= 18 && user.getStatus() == ACTIVE;
if (isEligible) { processUser(user); }

// 迭代代替深递归
public int factorial(int n) {
    int result = 1;
    for (int i = 1; i <= n; i++) { result *= i; }
    return result;
}

public static int compute(int a, int b) { return a + b; } // static，无虚方法表查找
```

##### bad case:
```java
if (user.getAge() >= 18 && user.getStatus() == ACTIVE && checkExtra(user)) {
    // 条件逻辑太复杂，难以阅读
}
```

---

## 执行要求

### 强制禁止
- ✗ 禁止工具类有公共构造方法
- ✗ 禁止内部方法暴露为 public
- ✗ 禁止不使用 try-with-resources 管理资源（详见 `HA-03` HA-D004）
- ✗ 禁止在循环中反复创建大对象
- ✗ 禁止 POJO 类属性设置默认值
- ✗ 禁止使用 Apache BeanUtils 拷贝对象
- ✗ 禁止使用 `==` 比较包装类型
- ✗ 禁止使用 `==` 比较浮点数
- ✗ 禁止用 `double` 构造 `BigDecimal`
- ✗ 禁止用 `.equals()` 比较 `BigDecimal`（应用 `.compareTo()`）
- ✗ 禁止过时 API（`@Deprecated`）
