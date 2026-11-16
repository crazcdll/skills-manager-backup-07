# 案例：协议骨架搭建（到餐/酒店提单页）

通过 Good / Bad 案例帮助 AI 正确地从零搭建/理解 DUO 页面协议骨架。基于到餐提单页（`nibfe/duo-food-order-submit`）与酒店提单页（`nibfe/duo-hotel-order-submit`）的**真实 `protocol/struct.groovy` 节点清单**。

## 到餐提单页真实节点骨架（pageId=12413 · protocolId=0401）

从 `protocol/struct.groovy` 提取的真实节点：

| 节点名 | 物料ID | 说明 |
|--------|:---:|------|
| `MeishiCommonDuoParams` | 757 | 静态公共参数 |
| `MeishiCommonEleLine` | 41 | 分割线 |
| `TopBottomSlide` | 136 | 上中下滑动布局 |
| `NavBar` | 1523 | 导航栏 |
| `MeishiGroupBuyTab` | 1732 | 团购 tab |
| `Product` | 1056 | 商品卡 |
| `ProductTips` | 1084 | 商品提示 |
| `ProductTotal` | 1527 | 商品合计 |
| `MeishiGroupSubmitCoupons` | 1650 | 团购券 |
| `SubmitRisk` | 192 | 提交风险 |
| `BottomBar` | 402 | 底部提单栏 |
| `Logic` / `Static` | 1339 / 1340 | 逻辑/静态节点 |

## 酒店提单页真实节点骨架（pageId=12450 · protocolId=0238）

| 节点名 | 物料ID | 说明 |
|--------|:---:|------|
| `CommonParams` | 757 | 静态公共参数 |
| `LayoutTopBottom` | 7 | 上中下布局（根） |
| `LifecycleLogicStatic` | 1205 | 生命周期（静态） |
| `LoadingFill` | 1204 | 加载填充 |
| `BaseInfo` | 800 | 基本信息 |
| `GuestCard` | 706 | 入住人/联系人 |
| `RoomUpgrade` | 844 | 房型升级 |
| `PromotionDiscountCard` | 784 | 优惠折扣 |
| `Invoice` | 842 | 发票 |
| `BookTime` | 811 | 入住时间 |
| `BottomBar` | 798 | 底部提单栏（提交） |

---

## Good 做法：在 hotel struct 中正确组织节点

```groovy
// protocol/struct.groovy
node('LayoutTopBottom', '7') {        // 根布局
  node('CommonParams', '757') {       // 静态公共参数
    props {
      object('lxCommonParams') {{ [...] }}
    }
  }
  node('LifecycleLogicStatic', '1205') { ... }   // 生命周期静态
  // ... 各业务卡片
  node('GuestCard', '706') {
    props {
      number('adultNum') {{ CONST.baseInfo.adultNum }}
    }
    on('onChangeGuestInfo') { ... }   // updateBy 触发点
  }
  node('BottomBar', '798') {          // 底部提单栏
    props {
      number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    }
  }
}
```
特征：
- **nodeName + 物料 ID** 一一对应（物料 ID 是资产平台注册的物料 id）
- 用 `props{}` 定义字段，用 `{{ }}` 写 Groovy
- 事件用 `on('xxx') {}`
- 变量来自 CONST / DATA_SOURCE / COMMON_PARAMS

## Bad 做法

```groovy
// ❌ 1. 物料ID编造（'7' 是 LayoutTopBottom 的物料ID，不能给别的节点用；root1 无此物料）
// ❌ 2. 用 JS 语法 props 赋值
// ❌ 3. 变量 fakeSource 不存在
node('root1', '7') {                    // ❌ 误用 LayoutTopBottom 的物料ID 7（物料ID需从物料平台查询对应物料的真实ID）
  props {
    disabled = {{ node.fake.includes('x') }}   // ❌ JS+编造变量
  }
}
```
问题：
- 物料 ID `7` 对应的是 `LayoutTopBottom` 物料，被错用为 `root1` 节点
- 无 `label`，节点语义不明
- JS 语法 + 编造变量
- 没有用 `bool/number/string/object/array` 的类型化字段声明

## Good / Bad 对比表

| 维度 | Good | Bad |
|------|------|-----|
| 节点命名 | 语义化（BottomBar） | 无意义（root1） |
| 物料 ID | 从物料平台查询真实 ID | 编造/套用其它物料 ID |
| 字段声明 | `bool/number/string/object/array('name')` | 裸 `xxx =` |
| 表达式 | Groovy，变量真实 | JS 语法，变量编造 |
| 条件渲染 | `xIf {{ }}` | 不用 |
| 事件 | `on('xxx')` | 无 |

## 搭建 checklist

- [ ] 节点名语义化
- [ ] 第二个参数是**物料在资产平台注册的物料 ID**（从物料平台 / componentsMap / 现有协议查询，禁止编造或套用其它物料的 ID）
- [ ] 用 `props { bool/number/string/object/array }` 声明字段
- [ ] 表达式 Groovy 2.4.17，变量来自 CONST/DATA_SOURCE/etc
- [ ] 条件渲染用 `xIf`
- [ ] 事件用 `on(...)`，跨节点 `callMethod('NodeName', 'method')` / `updateBy`
- [ ] 静态/逻辑节点（CommonParams/Static/Lifecycle）与视图节点区分
- [ ] 引用的物料在 componentsMap/dependencies 有记录
- [ ] 提交链路（BottomBar + submit logics）有承接
