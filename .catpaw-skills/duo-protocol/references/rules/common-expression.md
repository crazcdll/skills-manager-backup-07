# 常见表达式规则

DUO 页面协议表达式是放在 `props` 内 `{{ }}` 中的 **Groovy 2.4.17** 代码。

## 一、语法铁律

| # | 规则 |
|---|------|
| 1 | 表达式写在 `props {}` 内，形如 `number('xx') {{ Groovy代码 }}` |
| 2 | 兼容 Groovy 2.4.17，禁止 JS 语法与高版本 Groovy |
| 3 | 外部用 `{{` + `}}` 包裹，内部是 Groovy 代码 |
| 4 | 求值类型须与声明的字段类型一致（bool/number/string/object/array） |

## 二、字段类型声明

```groovy
props {
  bool('isOversea') {{ CONST.baseInfo?.isOversea }}
  number('totalPay') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
  string('currency') {{ '¥' }}
  object('common') {{ [ cid: CONST.cid ] }}
  array('list') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
}
```

## 三、真实协议常见表达式

| 场景 | 表达式 |
|------|--------|
| 空值兜底 | `DATA_SOURCE?.data?.priceVO?.totalPayAmount ?: 0` |
| 条件判断 | `COMMON_PARAMS.systemInfo.isMRN` |
| 三目 | `def x = a != null ? a : b` |
| 列表查找 | `DATA_SOURCE?.data?.promotionVO?.availableCouponVOList?.find { it.selectStatus == true }` |
| 列表判断 | `def l = ... ; l != null && l.size() > 0` |
| 字符串包含（Groovy） | `xxx.contains('券')` |
| 可选链 | `DATA_SOURCE?.data?.guestVO?.age` |

## 四、Common Bad Case

| Bad | 问题 |
|-----|------|
| `xxx.includes('a')` | includes 是 JS，Groovy 用 `contains` |
| `xxx.map/y.filter/xxx.reduce` | JS 数组方法，Groovy 用 `.collect{}/.findAll{}/.find{}` |
| `xxx == '2'`（数字 vs 字符串） | 强类型比较，用 `== 2` 或转字符串 |
| `const x = 1` | Groovy 用 `def x = 1` |
| 裸 `disabled = xxx` 而非 `bool('disabled') {{ xxx }}` | 字段未类型化声明 |

## 五、注意 static/逻辑节点

静态/逻辑节点（`CommonParams`、`Static`、`LifecycleLogic`）里的 props 是**逻辑参数**，不是渲染表达式。渲染表达式要放在对应**视图节点**的 props 中。

## 六、预加载

`duo-expression-transform` 支持表达式预加载，构建期可预解析。大量表达式时可考虑，非默认。

## 七、排查

1. 是否在 props 的 `{{ }}` 内？
2. 变量是否来自 `CONST/DATA_SOURCE/NODE/PAYLOAD/PREV_DATA/COMMON_PARAMS/PAGE_QUERY/PROPS`？
3. 是否 Groovy 2.4.17？
4. 字段是否类型化声明且值类型匹配？
5. 是否 `?.` 防空？
6. 是否误放 static/逻辑节点？
7. 用 duo-debug-panel 验证求值
