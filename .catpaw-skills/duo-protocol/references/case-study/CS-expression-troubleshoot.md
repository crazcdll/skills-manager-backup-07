# 案例：表达式排错

通过实际案例帮助 AI 快速定位 DUO 协议表达式不生效或报错的根因。基于到餐提单页（`nibfe/duo-food-order-submit`）与酒店提单页（`nibfe/duo-hotel-order-submit`）的真实协议。

> 真实协议表达式写法：`type('字段名') {{ Groovy代码 }}`，放在 props 内。变量来自 `CONST` / `DATA_SOURCE` / `NODE` / `PAYLOAD` / `PREV_DATA` / `COMMON_PARAMS` / `PAGE_QUERY` / `PROPS`。

## 案例一：JS 与 Groovy 混用（到餐 ProductTotal 中判断）

**现象**：价格展示字段不生效，控制台报语法错。

### Bad（混用 JS）
```groovy
props {
  number('discount') {{ DATA_SOURCE.data.priceVO.discountList.includes('券') }}
}
```
`includes` 是 JS，Groovy 里应写 `contains`。

### 修复
```groovy
props {
  number('discount') {{ DATA_SOURCE?.data?.priceVO?.discountList?.contains('券') }}
}
```

## 案例二：变量名不存在（酒店 GuestCard 年龄）

**现象**：入住人字段 preview 报错。

### Bad
```groovy
props {
  number('age') {{ guestAge }}   // guestAge 不存在
}
```

### 修复
- 先读协议/数据源确认字段。入住人数据通常在 `DATA_SOURCE.data`，用可选链避免空指针：
```groovy
props {
  number('age') {{
    def guest = DATA_SOURCE?.data?.guestVO
    return guest?.age != null ? guest.age : 0
  }}
}
```

## 案例三：类型不匹配（到餐数量 leez-stepper）

### Bad
```groovy
number('count') {{ CONST.baseInfo.count == '2' }}   // 数字 vs 字符串
```

### 修复
```groovy
number('count') {{ CONST.baseInfo.count == 2 }}
// 或
number('count') {{ CONST.baseInfo.count?.toString() == '2' }}
```

## 案例四：空值导致白屏（酒店房费 × 晚数）

**现象**：某字段为 null，`price * nights` 报错/白屏。

### Bad
```groovy
number('total') {{ DATA_SOURCE.data.priceVO.roomFee * CONST.baseInfo.nightCount }}
```

### 修复（空值兜底）
```groovy
number('total') {{
  def fee = DATA_SOURCE?.data?.priceVO?.roomFee ?: 0
  def nights = CONST.baseInfo?.nightCount ?: 1
  return fee * nights
}}
```

## 案例五：静态/逻辑节点里误放渲染表达式

**现象**：把展示表达式写在 `MeishiCommonDuoParams`（757）/ `Static`（1340）等 static/逻辑节点 props，但不渲染。

**修正**：
- `CommonParams`（酒店 757）、`MeishiCommonDuoParams`（到餐 757）是**静态公共参数**，只放参数字段
- `Logic`（到餐 1339）/ `Static`（到餐 1340）是逻辑节点，不渲染
- 渲染表达式放在对应**视图节点**（Product / BottomBar / 卡片）的 props

## 案例六：Groovy 2.4.17 不支持的高阶语法

**现象**：用了 JS 风格 filter/map/reduce 或 Groovy 高版本 `switch 表达式`。

**修正**：用 Groovy 2.4.17 支持的 `?.`、`?:`、`.find{}`、`.any{}`、`def`，参考真实协议 `./protocol/*.groovy` 中的既有写法保持一致。

---

## 排查 checklist

- [ ] 是否在 props 内的 `{{ }}` Groovy 代码块？
- [ ] 变量来自 `CONST/DATA_SOURCE/NODE/PAYLOAD/PREV_DATA/COMMON_PARAMS/PAGE_QUERY/PROPS`？
- [ ] 是否 Groovy 2.4.17 语法（不用 JS includes/map/filter）？
- [ ] 类型是否匹配（number/bool/string/array）？
- [ ] 是否加 `?.` 可选链防空？
- [ ] 是否误放 static/逻辑节点？
- [ ] 是否用 duo-debug-panel 验证求值？
