---
ruleType: Model Request
description: 写Controller/API/对外接口时读我。规定返回值统一封装(HttpResponse类)、分页、异常处理、兼容性。新建接口或设计返回结构时必读。
category: Java编码规范
priority: medium
---

# Java接口设计规范

## 概述

本规范定义了Java接口设计的标准，涵盖接口命名、参数设计、返回值封装、幂等性、文档规范、性能优化（分页）、异常处理、兼容性等核心接口设计原则。

## 核心规范

以下示例仅用于说明规则边界与意图，不代表唯一实现方式；实际生成或审查代码时，应优先复用项目现有框架、工具类、SDK 与命名，并以是否满足规则约束为判断标准。

### N003 [强制] 接口返回值规范

接口必须返回封装结果对象，禁止直接返回原始数据或null；成功与失败结果需统一格式

- 使用泛型结果包装类`Result<T>`，包含状态码、消息、数据字段，避免空指针风险

##### good case:

```java

// 统一结果封装

public interface UserService {

    Result<UserDTO> getUserById(Long userId);

    Result<Boolean> deleteUser(Long userId);

}

// 结果封装类

public class Result<T> {

    private int code;

    private String message;

    private T data;

    // 构造方法与业务静态方法

    public static <T> Result<T> success(T data) { /*...*/ }

    public static <T> Result<T> fail(int code, String message) { /*...*/ }

}

```

##### bad case:

```java

// 直接返回原始数据与null

public interface UserService {

    UserDTO getUserById(Long userId); // 可能返回null

    boolean deleteUser(Long userId); // 无状态码说明失败原因

}

```

### N005 [强制] 接口性能与分页规范

接口应设定响应时间目标（交互型 ≤500ms），列表接口必须分页，禁止无上限返回数据。

**说明**：
- 列表接口必须支持分页参数（`page`、`size`）或等价能力
- 单页数据量建议不超过 100 条，导出/批处理使用专用接口
- 对外查询接口 LIMIT 上限详见 `DB-02` N015

##### good case:

```java
public interface UserService {
    // 分页查询接口
    Result<UserPageDTO> listUsers(UserQueryRequest request, int page, int size);
}

// 分页结果封装
public class UserPageDTO {
    private List<UserDTO> records;
    private long total;
    private int page;
    private int size;
}
```

### N006 [强制] 接口异常处理规范

接口必须抛出统一业务异常，禁止抛出技术异常或直接使用Exception，确保调用方易处理

- 自定义业务异常继承`BusinessException`，包含业务错误码与消息，避免暴露技术细节

##### good case:

```java

public interface OrderService {

    // 声明业务异常

    Result<OrderDTO> createOrder(OrderCreateRequest request) throws OrderException;

}

// 业务异常类

public class OrderException extends BusinessException {

    public OrderException(String code, String message) {

        super(code, message);

    }

    // 预定义异常实例

    public static final OrderException STOCK_INSUFFICIENT = new OrderException("ORD-001", "库存不足");

}

```

### N007 [强制] 接口兼容性规范

接口升级时必须保证向后兼容，字段变更、序列化安全、版本管理的完整规范详见 `HA-10-接口兼容性规范.md`。

**核心原则**：禁止删除已有接口方法或字段，不兼容变更必须通过新增方法/字段实现，并至少保留旧版本 2 个迭代周期。
