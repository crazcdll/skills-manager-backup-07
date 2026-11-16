# 领域知识库

> CR 时自动注入。命中相关字段/方法时，将对应规则注入审查 prompt。
> 资料来源：
>   - [01.多套ID体系介绍](https://km.sankuai.com/collabpage/1744576703)
>   - [03.ID体系定义](https://km.sankuai.com/collabpage/2457026694)
>   - [平台技术部双平台不一致COE分析](https://km.sankuai.com/page/1305288396)（2021~2023年 31 个 COE，50% 是 ShopId 问题）
> 维护人：孟木子 | 最后更新：2026-03-17

---

## 一、核心认知：美团/点评双平台并存

**美团和点评是两套独立的平台体系，绝大多数实体都有两套 ID。**
新门店/新商品两套 ID 数值可能相同，但老数据两套 ID 不同。
代码中混用 dpId 和 mtId 是最高频的 bug 来源。

> ⚠️ **双平台不一致是近三年排名 #1 的线上 bug 来源（2021~2023 共 31 例，50% 为 ShopId 问题）**

---

## 二、各类 ID 体系详解

### 2.1 门店 ID（PoiId / ShopId）— 最高危 🔴

| 字段 | 体系 | 说明 |
|------|------|------|
| `dpId` / `dpShopId` / `dpPoiId` | 点评体系 | 点评侧门店 ID，老门店与美团不一致 |
| `mtId` / `mtShopId` / `mtPoiId` | 美团体系 | 美团侧门店 ID |

```java
@EqualsAndHashCode @Data @AllArgsConstructor
public class PoiId {
    private Long dpId;   // 点评端使用的ID
    private Long mtId;   // 美团端使用的ID
}
```

**CR 检查点（严格区分命名问题 vs 混用问题）：**

| 场景 | 级别 | 判断依据 |
|------|------|---------|
| 从 Request 直接取 `shopId` 传给点评接口 | **P1** | 点评接口只认 dpShopId，会导致数据错误 |
| 从 shopDTO 取出 shopId 绕过 DTO 转换 | **P1** | 绕过了点评体系转换，运行时数据错误 |
| 美团侧接口传入点评 cityId 做过滤 | **P1** | 会导致美团侧数据为空 |
| 新增 DTO 字段命名为裸 `poiId`/`shopId`（无 mt/dp 前缀），**但实际体系明确、调用方使用正确** | **P2** | 仅命名规范问题，无运行时风险，建议加前缀以提升可读性 |
| 代码中出现裸 `shopId`/`poiId`，**体系来源不明确** | **P1** | 需明确确认体系，存在混用风险 |

> ⚠️ **重要**：字段命名无双平台前缀 ≠ ID 混用。命名是 P2 规范问题；实际传错体系 ID 才是 P1。**禁止仅因字段名无前缀就定 P0。**

**历史典型 COE（3 年 13 例）：**
- 足疗预订商品不展示：dpShopId 未转换到 mtShopId 导致价格查询异常
- 虚拟号无法拨打：改动后直接取 Request 的 ShopId，绕过了 DTO 中的点评体系转换
- 医美商户商品为空：传入了点评 cityId，美团 app 传美团 cityId 时被过滤

---

### 2.2 客户 ID（CustomerId）

| 字段 | 体系 | 说明 |
|------|------|------|
| `bizId` | 到综业务 ID | 到综业务自己使用的 ID |
| `platformId` | 平台 ID | 客户平台（统一客户中心）使用的 ID |

```java
public class CustomerId {
    private Long bizId;       // 业务ID，指到综ID
    private Long platformId;  // 平台ID
}
```

**CR 检查点：**
- 非到综专门业务，尽量使用 platformId（平台 ID）
- bizId 和 platformId 混用 → **P2**，说明接入规范

---

### 2.3 城市 ID（CityId）

| 字段 | 体系 | 说明 |
|------|------|------|
| `dpId` | 点评城市 ID | 点评体系城市标识 |
| `mtId` | 美团城市 ID | 美团体系城市标识 |

```java
public class CityId {
    private Long dpId;  // 点评端使用的ID
    private Long mtId;  // 美团端使用的ID
}
```

**CR 检查点：**
- 使用 `@dp/whereami` 获取的 cityId 在双平台返回相同，使用 `KNB.getCity` 则不同 → 隐私改造时常见问题
- 将 cityId 传给搜索/过滤接口时，必须确认是否做了双平台适配

---

### 2.4 用户 ID（UserId）

用户 ID 有 4 种，代码中经常混用 `userId` 却不说明是哪种：

| 类型 | 说明 |
|------|------|
| 美团实 ID | 美团侧已认证用户 ID |
| 美团虚 ID | 美团侧未认证/游客 ID |
| 点评实 ID | 点评侧已认证用户 ID（`dpId`） |
| 点评虚 ID | 点评侧未认证/游客 ID |

```java
public class UserId {
    private Long dpId;  // 点评实ID
    private Long mtId;  // 美团实ID
    // 虚ID另有字段
}
```

**CR 检查点：**
- 裸 `userId` 字段无注释说明是哪种 → **P2**

---

### 2.5 团购/商品 ID（DealId / ProductId / SkuId）

| 类型 | 说明 |
|------|------|
| 团购 DealID | 不区分美团点评，两套 ID 体系，老团单可能不一致 |
| 美团团单 ID | 平台 ID 和美团 ID 值一致（平台发号器就是美团发号器） |
| 泛商品 SkuID | 不区分美团点评，只有一种 ID |

```java
public class SkuId {
    private Long bizId;       // 业务ID
    private Long platformId;  // 平台ID
}
```

**CR 检查点（团单 ID）：**
- `mtDealId` 传给点评接口 → **P1**，点评接口只接收 `dpDealId`
- 历史典型 COE：分销招商活动使用了 mtDealId 查综合商品，接口只支持 dpDealId，导致商品查询不到

---

### 2.6 类目 ID（Category）

| 类型 | 说明 |
|------|------|
| 平台 ID | 在业务类目 ID 基础上增加前缀：团购+80，泛商品+81 |
| 业务 ID（团购） | 二级：category；三级：serviceType（中文字符串）/ serviceTypeId |
| 业务 ID（泛商品） | 一~五级：productType / spuType / category3 / category4 / category5 |

**CR 检查点：**
- 团购 serviceType 是中文字符串，不要和数字 ID 混用

---

### 2.7 商家账号 ID

| 字段 | 说明 |
|------|------|
| dpId | 点评侧商家账号 ID |
| epassportId / mtId | 美团侧商家账号 ID（也叫 epassportId） |

---

### 2.8 订单 ID

| 类型 | 类型 | 说明 |
|------|------|------|
| 统一订单号（unifiedOrderId） | String | 统一订单中心生成，后端系统交互标准 |
| 老平台短订单号（orderId） | Long | `<19` 位，主要用于 C 端展示，后端避免使用 |
| 新平台订单号（orderId） | Long | 19 位，新平台交易内部使用 |

**CR 检查点：**
- 后端系统交互统一使用 `unifiedOrderId`（String 类型），不要用 Long 类型的 orderId

---

## 三、双平台处理规范

| 场景 | 规范 |
|------|------|
| 历史代码改造 | 充分考虑双平台差异性，特别是改动门店 ID、城市 ID、商品 ID 相关逻辑 |
| 增量代码 | 将双平台 ID 转换抽象为通用能力，业务代码中只走一套体系 |
| ID 升级改造 | 保留原字段传值逻辑，新增字段赋值，不得直接删除原逻辑（见 risk-rules CR:R1-1） |
| 测试要求 | 必须覆盖美团/点评双平台；测试数据必须包含双平台 ID 一致和不一致两种场景 |

---

## 四、命名规范

| 规范 | 说明 |
|------|------|
| 点评体系用 `dp` 前缀 | `dpShopId`、`dpPoiId`、`dpDealId` |
| 美团体系用 `mt` 前缀 | `mtShopId`、`mtPoiId`、`mtDealId` |
| 无前缀字段 ⚠️ 高危 | 必须有注释说明来源体系，否则 CR 标 P2 |
| ID 字段类型 | 平台内部 ID 用 `Long`；三方外部 ID 用 `String` |

---

## 五、门店维度的特殊说明

门店数据在商品体系中有两个维度，极易混用：

| 维度 | 字段 | 含义 |
|------|------|------|
| 商品维度门店（Product 级） | `dpShopIds`、`SYS_SHOP_LIST` | 整个商品适用的门店列表，商家在商品维度编辑 |
| SKU 维度门店（SKU 级） | `dealShops`、`SYS_SKU_SHOPS` | 特定 SKU 适用的门店，可覆盖商品维度门店 |

**CR 检查点：**
- 新增写入 `SYS_SKU_SHOPS` 的逻辑，必须确认消费侧对两个维度门店的优先级处理
- 若消费侧优先读 `SYS_SKU_SHOPS`，则 SKU 旧值会覆盖商家的商品维度门店修改，导致修改不生效

---

## 六、CR 触发规则映射

| 触发关键词 | 注入规则 |
|-----------|---------|
| `shopId`/`poiId`（无 dp/mt 前缀） | 检查 2.1：确认体系来源，建议加前缀 |
| `dpShopId`/`dpPoiId` 传给美团接口，或反之 | **P1**：跨体系 ID 传参 |
| `cityId`（无前缀）传给搜索/过滤接口 | 检查 2.3：确认双平台适配 |
| `mtDealId` 传给点评接口 | **P1**：检查 2.5 |
| `SYS_SKU_SHOPS`、`dealShops` | 检查 5：确认消费侧门店优先级逻辑 |
| 裸 `userId` 无注释 | **P2**：检查 2.4，补充注释说明类型 |
| 裸 `customerId` 无前缀 | **P2**：检查 2.2，确认 bizId vs platformId |
| 三方 ID 传给平台内部字段 | 检查 4：三方 ID 用 String，不可与平台 Long 类型 ID 混用 |
| ID 升级、字段迁移 | risk-rules CR:R1-1：升级不删原逻辑，与下游确认兼容 |
