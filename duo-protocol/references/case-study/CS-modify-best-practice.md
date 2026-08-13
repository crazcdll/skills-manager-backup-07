# 案例：改协议 Best Practice

通过 Good / Bad 案例帮助 AI 理解如何**安全地修改 DUO 页面协议**。基于到餐提单页（`nibfe/duo-food-order-submit`，pageId=12413，protocolId=0401）与酒店提单页（`nibfe/duo-hotel-order-submit`，pageId=12450，protocolId=0238）的真实 `protocol/` 目录源文件。

> ⚠️ 协议源文件在仓库 `protocol/` 目录下，为拆分文件（`.groovy` 与 `.json` 都要理解怎么改）：`struct.groovy` / `logics.groovy` / `dataSourceMap.groovy` / `constData.groovy` / `pageBuildConfig.json` / `dependencies.json` / `componentsMap.json`。修改的就是这些文件。

## 真实协议语法速览（改前必读）

DUO 协议用 `node(){}` 组织，真实写法（非伪代码）：

```groovy
// struct.groovy 中的典型节点
node('BottomBar', '798') {          // nodeName + 物料ID（资产平台注册的物料 id，从物料平台/现有协议查询）
  label '酒店提单-底部提单栏'          // 中文描述
  xIf {{ COMMON_PARAMS.systemInfo.isMRN }}    // 条件渲染（全局变量）
  props {                           // 属性 + Groovy 表达式
    bool('isOversea') {{ CONST.baseInfo?.isOversea }}
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    string('currencySymbol') {{ '¥' }}
    array('priceItemList') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
  }
  on('onKeyBoardShow') {            // 事件
    callMethod('GuestCard', 'onKeyBoardShow')
  }
}
```

### 全局变量体系（十分重要）

| 变量 | 含义 | 典型用法 |
|------|------|---------|
| `CONST` | 页面初始化常量/跳链参数 | `CONST.goodsID`、`CONST.baseInfo.checkin` |
| `DATA_SOURCE` | 数据源返回 | `DATA_SOURCE?.data?.priceVO?.totalPayAmount` |
| `NODE` | 某个节点 | `NODE.BookTime?.props?.checkInPeriod` |
| `PAYLOAD` | update/submit 入参 | `PAYLOAD?.roomNum?.value` |
| `PREV_DATA` | 上一轮数据 | `PREV_DATA.isManagedTargetRoomUpgrade` |
| `COMMON_PARAMS` | 公共参数（location/city/systemInfo） | `COMMON_PARAMS.systemInfo.isMRN` |
| `PAGE_QUERY` | 页面 query 参数 | `PAGE_QUERY.goods_id` |
| `PROPS` | 父级传入的 props | `PROPS.isChecked` |

### 错误标记

```groovy
// duo ignore-check-var   # 告诉检查器忽略某个变量（如 CONST.language 这类动态键）
```

---

## 案例一：在价格明细加一个"已优惠"字段（酒店 priceCard→BottomBar 的 priceItemList）

**需求**：在酒店提单页底部提单栏展示已优惠金额。

### Bad 做法
```groovy
// 在一个已有节点上"重新赋值"一个不存在的字段，且用了 JS 语法
node('BottomBar', '798') {
  props {
    // ❌ 1. fakeDiscount 变量不存在（数据源没有）
    // ❌ 2. includes 是 JS，Groovy 无此方法
    bool('hasDiscount') {{ node.price.includes('discount') }}
    // ❌ 3. 覆盖已存在的 totalPayAmount（破坏现有逻辑）
    number('totalPayAmount') {{ '0' }}
  }
}
```
问题：
- `fakeDiscount`/`node.price` 不在真实数据源中
- `includes` 是 JS，Groovy 应写 `contains`
- 盲目覆盖 `totalPayAmount`，破坏现有价格链路
- 用 `node` 变量，但真实协议里是 `NODE`/`DATA_SOURCE`/`CONST`

### Good 做法
```groovy
// Step1：确认 priceVO 里有优惠字段（如 totalPromotionAmount）
// Step2：在 BottomBar 的 props 中新增一个不覆盖他人的字段
node('BottomBar', '798') {
  props {
    // ✅ 保留原有 totalPayAmount 不动
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    // ✅ 新增：优惠展示，且用 Groovy 三目 + 空值兜底
    number('discountDisplay') {{
      def promotion = DATA_SOURCE?.data?.priceVO?.totalPromotionAmount
      return promotion != null && promotion > 0 ? promotion : 0
    }}
  }
}
```
要点：
- 变量名来自真实数据源 `DATA_SOURCE.data.priceVO`
- **增量新增**，不覆盖已有字段
- Groovy 三目 / 空值兜底
- 若需要展示层文案，在对应视图节点 props 挂展示表达式

---

## 案例二：改商品/卡片的展示条件（到餐 Product 节点）

**需求**：在某场景下隐藏某个商品模块。

### Bad
```groovy
node('Product', '1056') {
  // ❌ 用 JS 语法且条件写死反向
  xIf {{ node.hidden.includes('yes') ? false : true }}
}
```

### Good
```groovy
node('Product', '1056') {
  // ✅ xIf 是真实的条件渲染入口，Groovy 判断
  xIf {{ !CONST.baseInfo.isXXX }}   // 具体条件变量需先读协议确认
  label '到餐提单-商品卡'
}
```
要点：
- 条件渲染用 `xIf {{ }}`（真实机制）
- 判断变量来自 `CONST`/`DATA_SOURCE`/`COMMON_PARAMS`，先确认存在
- 不改动节点 props 内部其它逻辑

---

## 案例三：新增一个模块（酒店 add「同行人」提示卡）

**需求**：入住人卡片（GuestCard）下加一行提示。

### 正确顺序
1. **struct.groovy**：找到 `GuestCard`（706）节点，在合适位置新增节点
2. **确认物料**：新节点引用的组件（如 `@max/leez-tip`）须已在 `componentsMap`/`dependencies` 有引用；未引用先补
3. **数据源**：若需新数据字段，确认 `DATA_SOURCE` 已返回
4. **logics.groovy**：如需交互（如点击收起），新增事件

### 常见错误
- 在 struct 加节点，但物料未在 componentsMap/依赖里 → 编译失败
- 引用后端未返回的字段 → 渲染为空
- 新增节点时误动相邻节点的 `updateBy`（如动了 GuestCard 的 `onChangeGuestInfo`）→ 破坏入住人联动
- 新节点若用错物料 ID（套用其它物料）→ 渲染异常

---

## 总结：改协议 checklist（提单页）

- [ ] 读取 `protocol/struct.groovy` / `logics.groovy` / `dataSourceMap.groovy` 现状
- [ ] 变量来自 `CONST`/`DATA_SOURCE`/`NODE`/`COMMON_PARAMS`/`PAGE_QUERY`/`PREV_DATA`/`PAYLOAD`，不编造
- [ ] 新增物料已在 componentsMap/dependencies 引用；物料 ID 从物料平台/现有协议查询，不编造、不套用其它物料 ID
- [ ] 增量改动，不覆盖已有字段/节点
- [ ] 不破坏 updateBy、事件、submit 链路
- [ ] 新增字段后端已返回
- [ ] 条件渲染用 `xIf`，事件用 `on(...)`
- [ ] 说明验证方式（duo dev 协议同步 / 配置平台预览）
