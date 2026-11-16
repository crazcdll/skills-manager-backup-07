---
ruleType: Model Request
description: Java单元测试编写规范，定义测试方法编写格式、Mock使用规范和最佳实践
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

### java-l1:JAVA-07.N001 [强制] 测试方法编写规范

#### 注释要求
复杂测试方法建议包含JavaDoc注释，说明测试场景和预期结果；简单且命名自解释的测试可省略：
```java
/**
 * 测试buildBizInternalOrderSnap方法，正常情况下的B2C订单
 */
@Test
public void testBuildBizInternalOrderSnap_B2COrder() {
    // 测试代码
}
```

#### AAA格式
推荐使用 `// Arrange` → `// Act` → `// Assert` 组织测试逻辑；简单场景可不强制添加阶段注释，但测试结构应保持清晰：
```java
@Test
public void testSomeMethod() {
    // Arrange
    when(mockDependency.getData()).thenReturn("test");

    // Act
    String result = obj.someMethod();

    // Assert
    assertEquals("expected", result);
}
```

#### 断言要求
- 每个测试方法必须包含有效断言
- 覆盖正常情况和异常情况
- 使用合适的断言方法（assertEquals、assertTrue、assertNotNull等）

#### 覆盖率要求
- 尽量覆盖所有代码行和分支
- 为所有可能的执行路径编写测试用例
- 覆盖正常流程、边界条件、异常分支

### java-l1:JAVA-07.N002 [推荐] Mock与依赖隔离规范

#### 外部依赖隔离与Mock
- 单元测试应隔离网络、数据库、消息、文件、时间、随机数等不稳定外部依赖
- 对纯内存、无副作用且不会影响测试稳定性的轻量依赖，可按场景决定是否mock
- 使用`@Mock`注解或`mock()`方法创建Mock对象
- 使用`when().thenReturn()`配置Mock行为

#### 静态方法Mock
在`@Before`方法中使用`mockStatic()`：
```java
@Before
public void init() {
    request = initData(SavaOrderSnapExtReq.class);
}
```

#### 静态Mock生命周期管理
使用try-with-resources管理：
```java
@Test
public void testWithStaticMock() {
    try (MockedStatic<SomeClass> mockedStatic = mockStatic(SomeClass.class)) {
        mockedStatic.when(() -> SomeClass.staticMethod()).thenReturn("mocked");
        // Act & Assert
    }
}
```

## 3. 执行要求

### 强制执行
- 必须包含有效断言，覆盖正常和关键异常情况
- 单元测试必须隔离网络、数据库、消息、文件、时间、随机数等不稳定外部依赖
- 静态Mock必须使用try-with-resources管理
- 严格查看方法签名，嵌套时递归查看，避免编译错误

### 推荐执行
- 复杂测试方法建议添加JavaDoc注释（场景+预期结果）
- 推荐使用AAA格式组织测试逻辑，并在复杂测试中添加 `// Arrange`、`// Act`、`// Assert` 注释
- 简单且命名自解释的测试可以采用更紧凑的写法

### 禁止执行
- 禁止测试方法没有有效断言
- 禁止真实外部系统直接参与单元测试导致结果不稳定
- 禁止静态Mock使用后不关闭

### 常见错误
- ❌ 测试逻辑混乱，AAA阶段混在一起
- ❌ 缺少异常情况和边界条件测试
- ❌ 外部依赖未mock导致测试不稳定
- ❌ 静态Mock未关闭影响其他测试

## 4. 示例

### 正确示例

```java
package com.sankuai.tsp.order.trade.stellaris.plugin.health.provider.buy;
import com.alibaba.fastjson.JSON;
import com.google.common.collect.Lists;
import com.google.common.collect.Maps;
import com.sankuai.meituan.waimai.kv.domain.order.*;
import com.sankuai.tsp.order.trade.stellaris.client.constant.OrderTagEnum;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.AbstractHealthJunitTest;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.constant.HealthFunctionKeyEnum;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.constant.SnapKeyConstants;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.lion.HealthDynamicConfigEnum;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.model.HealthAgingRouteQueryBizInfo;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.service.HealthWmsService;
import com.sankuai.tsp.order.trade.stellaris.plugin.health.utils.HealthUtil;
import com.sankuai.tsp.order.trade.stellaris.sdk.dto.request.*;
import com.sankuai.tsp.order.trade.stellaris.sdk.dto.request.buy.SavaOrderSnapExtReq;
import org.junit.Before;
import org.junit.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class HealthSaveOrderSnapExtTest extends AbstractHealthJunitTest {

    @InjectMocks
    private HealthSaveOrderSnapExt healthSaveOrderSnapExt;

    @Mock
    private HealthWmsService healthWmsService;

    @Mock
    private HealthUtil healthUtil;

    private SavaOrderSnapExtReq request;

    @Before
    public void init() {
        request = initData(SavaOrderSnapExtReq.class);
    }

    /**
     * 测试getExtensionName方法
     */
    @Test
    public void testGetExtensionName() {
        // Act
        String result = healthSaveOrderSnapExt.getExtensionName();

        // Assert
        assertEquals("HealthSaveOrderSnapExt", result);
    }

    /**
     * 测试buildBizInternalOrderSnap方法，正常情况下的B2C订单
     */
    @Test
    public void testBuildBizInternalOrderSnap_B2COrder() {
        // Arrange
        when(mockConfigEnum(HealthDynamicConfigEnum.HEALTH_PRODUCT_PIC_LIST_ORDER_SNAP_SAVE_ENABLE)).thenReturn(true);
        request.setAllCalTagSet(new HashSet<>(Arrays.asList(OrderTagEnum.B2C_ORDER.getCode())));
        request.setUserDeviceExt(initData(UserDeviceExt.class));
        request.setMerchantInfoExt(initData(MerchantInfoExt.class));
        request.setBuyOrderExt(initData(UserBuyOrderExt.class));
        request.getBuyOrderExt().setDelayDeliverySelected(true);
        request.getMerchantInfoExt().setDelayDeliveryGift("测试礼物");
        mockSdkVersionControlAdapter(HealthFunctionKeyEnum.HEALTH_SAVE_TRANS_SNAP_VERSION_CONTROL, true);
        when(healthWmsService.getAgingRoute(any())).thenReturn(new HealthAgingRouteQueryBizInfo());

        // Act
        Map<String, String> result = healthSaveOrderSnapExt.buildBizInternalOrderSnap(request);

        // Assert
        assertNotNull(result);
        assertTrue(result.containsKey("longCycleTrans"));
        assertEquals("测试礼物", result.get(SnapKeyConstants.DELAY_DELIVERY_GIFT));
    }

    /**
     * 测试buildBizInternalOrderSnap方法，正常情况下的O2O订单
     */
    @Test
    public void testBuildBizInternalOrderSnap_O2OOrder() {
        // Arrange
        when(mockConfigEnum(HealthDynamicConfigEnum.HEALTH_PRODUCT_PIC_LIST_ORDER_SNAP_SAVE_ENABLE)).thenReturn(true);
        request.setUserDeviceExt(initData(UserDeviceExt.class));
        mockSdkVersionControlAdapter(HealthFunctionKeyEnum.HEALTH_SAVE_TRANS_SNAP_VERSION_CONTROL, true);

        // Act
        Map<String, String> result = healthSaveOrderSnapExt.buildBizInternalOrderSnap(request);

        // Assert
        assertNotNull(result);
        assertTrue(result.containsKey("shortCycleTrans"));
    }
}
```

## 5. 总结

- 复杂测试方法建议补充JavaDoc注释，简单测试保持自解释即可
- 推荐使用AAA格式组织测试逻辑，重点在结构清晰而非注释数量
- 包含正常和异常情况的断言，覆盖关键执行路径
- 隔离不稳定外部依赖，确保单元测试独立性
- 静态Mock使用try-with-resources管理生命周期
- 尽量覆盖所有代码行和关键分支
- 严格查看方法签名，嵌套时递归查看，避免编译错误