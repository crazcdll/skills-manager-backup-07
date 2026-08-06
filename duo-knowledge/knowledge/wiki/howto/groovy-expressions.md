# H3 · 如何编写 DUO Groovy 表达式

> 覆盖范围：五类协议文件的编写步骤、常见业务场景的表达式写法、调试技巧、以及从 JavaScript 迁移时的注意事项。

---

## 1. 编写前的准备

在开始写 Groovy 表达式之前，先明确以下三件事：

**当前处于哪个生命周期？** preview（首次加载）、update（用户交互）、submit（提交）、check（校验）。不同生命周期下可用的变量不同，尤其是 `PAYLOAD` 和 `PREV_DATA`。

**数据从哪里来？** 是从 `PAGE_QUERY`（跳链参数）、`COMMON_PARAMS`（通参）、`DATA_SOURCE`（接口响应）还是 `PREV_DATA`（上次快照）取值？

**数据要给谁用？** 是给接口入参（`requestProps`）、给节点 props（`nodes/*.groovy`），还是给常量（`constData.groovy`）？

---

## 2. constData.groovy 编写指南

`constData.groovy` 定义页面级常量，在 NODE_DATA 阶段最先执行，结果存入 `CONST`。适合放：埋点参数、枚举值、从 PAGE_QUERY 派生的初始值、多处复用的计算结果。

### 2.1 基本类型

```groovy
constant {
  // 字符串
  string('bizCode') {{ 'nib.general.groupbuy' }}

  // 数字
  number('moduleGap') {{ 10 }}

  // 布尔（依赖 PAGE_QUERY）
  bool('isPop') {{
    (PAGE_QUERY.isTransparent == 'true') || (PAGE_QUERY.mrn_transparent == 'true')
  }}
}
```

### 2.2 对象与嵌套对象

```groovy
constant {
  // 整体返回一个 Map（object）
  object('lxValLab') {{
    [
      deal_id: PAGE_QUERY.dealid ?: '-999',
      poi_id: PAGE_QUERY.shopid ?: '-999',
    ]
  }}

  // 有子字段的对象（objectWithSub）：子字段各自独立计算
  objectWithSub('lx') {
    string('cid') {{ 'c_0evvuz5' }}
    string('channelName') {{ 'gc' }}
    string('pageInfoKey') {{ 'gc_order_submit' }}
    object('valLab') {{
      [
        deal_id: PAGE_QUERY.dealid ?: '-999',
        poi_id: PAGE_QUERY.shopid ?: '-999',
      ]
    }}
  }
}
```

`object` vs `objectWithSub` 的选择：如果对象的子字段需要在其他地方单独引用（如 `CONST.lx.cid`），用 `objectWithSub`；如果只整体使用，用 `object`。

### 2.3 多端适配常量

```groovy
constant {
  string('cid') {{
    def systemInfo = COMMON_PARAMS.systemInfo
    systemInfo.IS_DP ? 'dp_cid_value' : 'mt_cid_value'
  }}

  bool('IS_MT') {{
    def systemInfo = COMMON_PARAMS.systemInfo
    // 特殊处理：非美团容器下的 H5 也视为美团端
    systemInfo.IS_MT || (systemInfo.isWeb && !systemInfo.IS_DP)
  }}
}
```

---

## 3. dataSourceMap.groovy 编写指南

### 3.1 requestProps — 构造接口入参

`requestProps` 在每次请求（preview/update/submit/check）时执行，构造业务接口的入参。

**preview/update 分支处理**（最常见模式）：

```groovy
requestProps {
  object('productParam') {{
    // preview 时从 PAGE_QUERY 取初始值
    // update 时从 PAYLOAD 取，PREV_DATA 兜底
    def skuId = PAYLOAD.skuId
    if (PAYLOAD.skuId == null) {
      skuId = PREV_DATA?.productInfoVO?.skuId ?: PAGE_QUERY.skuid
    }

    [
      quantity: PAYLOAD.quantity ?: PREV_DATA?.quantity ?: 1,
      productId: PAGE_QUERY.dealid,
      skuId: skuId,
    ]
  }}
}
```

**读取其他节点的 props（入参场景）**：

```groovy
requestProps {
  object('payParam') {{
    def submitOrderProps = NODE.SubmitOrderModule?.props ?: [:]
    def payMethodProps = NODE.PayMethodSelectModule?.props ?: [:]

    [
      payType: submitOrderProps?.payParams?.productScene ?: 0,
      operatedPayMethod: payMethodProps?.isOperateOpen ? 1 : 0,
    ]
  }}
}
```

**submit 专用逻辑**：

```groovy
requestProps {
  object('promoParam') {{
    def promotionVO = PREV_DATA?.promotionVO

    if (COMMON_PARAMS.isSubmit) {
      // submit 时传提交专用参数
      return [
        promoCipher: promotionVO?.promoCipher,
        discountClassifyType: promotionVO?.discountClassifyType,
      ]
    }

    // preview/update 时传查询参数
    [
      operatorPromoType: PAYLOAD.operatorPromoType,
    ]
  }}
}
```

### 3.2 currentData — 映射响应数据

`currentData` 从接口响应（`DATA_SOURCE`）中提取数据，结果存入 `PREV_DATA`，供下次请求的 `requestProps` 和节点 props 使用。

```groovy
currentData {
  // 直接映射
  object('promotionVO') {{ DATA_SOURCE.data?.promotionVO }}
  object('shopInfoVO') {{ DATA_SOURCE.data?.shopInfoVO }}

  // 提取列表中的第一个元素
  object('userAgreementInfo') {{
    def list = DATA_SOURCE.data?.userAgreementVO?.userAgreementInfoList ?: []
    list[0]
  }}

  // 计算派生值
  number('quantity') {{ DATA_SOURCE.data?.productInfoVO?.quantity }}

  bool('isExclusiveCard') {{
    def equityInfoVO = DATA_SOURCE.data?.equityInfoVO
    // 足疗折扣卡(1)或足疗会员卡(2)是互斥卡
    [1, 2].contains(equityInfoVO?.type)
  }}

  // 提取列表并转换
  array('promoSnapshot') {{
    DATA_SOURCE.data?.promotionVO?.promoInfoList?.collect { i ->
      [
        promoId: i.promoId,
        promoDetailType: i.promoDetailType,
        selected: i.selected,
      ]
    }
  }}
}
```

### 3.3 bizRespStatus — 业务状态判断

```groovy
bizRespStatus {
  bool('isError') {{ DATA_SOURCE?.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE?.userMessage ?: '服务异常，请稍后重试' }}

  // 上报额外信息
  object('extra') {{
    def tags = [code: DATA_SOURCE?.code]
    if (DATA_SOURCE?.code != 0) {
      return [
        reportMsg: "${DATA_SOURCE?.code}：${DATA_SOURCE?.message ?: ''}",
        reportTags: tags,
      ]
    }
    [reportTags: tags]
  }}

  errorToast true           // 出错时自动弹 toast
  errorNoReturnStruct true  // 出错时不返回节点树（页面显示错误态）
}
```

---

## 4. struct.groovy 编写指南

### 4.1 基本节点

```groovy
node('NavBar1', '1') {
  label '导航栏'

  // props：传给组件的数据
  props {
    string('title') {{ DATA_SOURCE.data?.statusInfo?.title?.text }}
    bool('shareable') {{ DATA_SOURCE.data?.dealInfo?.dealAction?.shareable }}
    object('systemInfo') {{ COMMON_PARAMS.systemInfo }}
  }

  // styles：传给组件的样式
  style('style') {
    string('backgroundColor') {{ '#FFFFFF' }}
    number('marginBottom') {{ 9 }}
  }

  // 事件绑定
  on('onRefresh') {
    callMethod('MeishiCommonDuoLifecycle1', 'update')
  }
}
```

### 4.2 条件渲染（xIf）

```groovy
node('ErrorModule1', '2') {
  label '错误模块'
  // xIf 为 false 时，节点从树中剪枝，不渲染也不占位
  xIf {{ DATA_SOURCE.data?.showError == true }}
  props {
    string('msg') {{ DATA_SOURCE.data?.errorMsg }}
  }
}

// 多端条件
node('FeedbackModule1', '3') {
  label '点评评价模块'
  xIf {{ !!COMMON_PARAMS.systemInfo?.IS_DP && !!COMMON_PARAMS.systemInfo?.isMRN }}
  props { ... }
}
```

**注意**：`xIf` 表达式建议用 `!!` 确保结果是 boolean，避免 Groovy 的 truthy/falsy 与预期不符。

### 4.3 循环渲染（xFor）

```groovy
node('ListContainer1', '3') {
  label '商品列表'
  nodeType 'LIST_CONTAINER'
  key {{ FOR.item.id }}          // 每个元素的唯一 key
  xFor {{ CONST.productList }}   // 循环的数据源

  slot('children') {
    node('ProductCard1', '4') {
      props {
        string('name') {{ FOR.item.name }}
        string('price') {{ FOR.item.price / 100 }}
        number('index') {{ FOR.index }}
      }
    }
  }
}
```

### 4.4 事件绑定与透传

```groovy
// 简单事件：触发生命周期
on('onChange') {
  callMethod('MeishiCommonDuoLifecycle1', 'update')
}

// 透传参数：将事件回调参数映射到 callMethod 的入参
on('onSelectAddrChange') {
  callMethod('MeishiCommonDuoLifecycle1', 'update')
  transparentArg('addr', 'payload.addr')  // 将回调的 addr 参数映射到 payload.addr
}

// 带条件的事件
on('onUrlUpdate') {
  callMethod('NavBar1', 'onUpdateKefuUrl')
  transparentArg('url', 'url')
}

// 带 props 的事件（传递额外参数给被调用方法）
on('onRefresh') {
  callMethod('MeishiCommonDuoLifecycle1', 'update')
  props {
    number('debounceDelay') {{ 500 }}
  }
}
```

### 4.5 propConfig — 双向绑定与请求参数

```groovy
node('StepperModule1', '5') {
  props {
    number('count') {{ PREV_DATA?.quantity ?: 1 }}
  }
  propConfig('count') {
    updateBy 'onChange'      // onChange 事件触发时自动更新 count 的值
    isRequestArg true        // update 时将 count 的当前值发给后端
    lock true                // 请求进行中时不触发双向绑定
  }
  on('onChange') {
    callMethod('MeishiCommonDuoLifecycle1', 'update')
  }
}
```

### 4.6 拆分节点文件（splitFile）

节点较多时，可将单个节点拆分到独立文件：

```groovy
// struct.groovy 中引入
include 'nodes/OrderDetailNavBar1.groovy'
include 'nodes/OrderDetailOrderStatus1.groovy'
```

```groovy
// nodes/OrderDetailNavBar1.groovy
node('OrderDetailNavBar1', '78') {
  label '订单详情导航栏'
  props {
    string('orderTitle') {{ DATA_SOURCE.data?.statusInfo?.title?.text }}
  }
  on('onRefresh') {
    callMethod('MeishiCommonDuoLifecycle1', 'update')
  }
}
```

---

## 5. logics.groovy 编写指南

`logics.groovy` 定义逻辑节点，主要用于：监听生命周期事件（lifeCycle 物料）、处理跨节点事件（事件处理物料）。

```groovy
node('MeishiCommonDuoLifecycle1', '13') {
  label '内置物料-页面生命周期'

  // 生命周期事件格式：{lifecycle}.{event}
  // lifecycle: preview | update | submit | check
  // event: onResponse | onSuccess | onFail | onCancel

  on('preview.onResponse') {
    // preview 成功后触发埋点
    callMethod('MeishiCommonEventLx1', 'lxTrackMPT')
    props {
      string('channelName') {{ CONST.lx.channelName }}
      string('cid') {{ CONST.lx.cid }}
      string('pageInfoKey') {{ CONST.lx.pageInfoKey }}
      object('param') {{
        [order_id: PAGE_QUERY.orderId ?: '-999']
      }}
    }
    transparentArg('', '')  // 透传所有参数
  }

  on('preview.onFail') {
    // preview 失败时的兜底埋点
    callMethod('MeishiCommonEventLx1', 'lxTrackModuleView')
    props {
      string('val_bid') {{ 'b_error_bid' }}
    }
  }

  on('update.onSuccess') {
    callMethod('PageLogicModule1', 'onRefreshSuccess')
  }

  on('update.onFail') {
    callMethod('PageLogicModule1', 'onRefreshFail')
  }
}

// 纯事件处理物料（无需配置，只需声明）
node('MeishiCommonEventLx1', '16') {
  label '数据埋点'
}
```

---

## 6. 常见业务场景

### 6.1 从接口响应构造埋点参数

```groovy
object('lx') {{
  [
    *: CONST.lx,   // 展开基础埋点配置
    valLab: [
      *: CONST.lx.valLab,
      deal_id: DATA_SOURCE.data?.dealInfo?.dealId ?: '-999',
      poi_id: DATA_SOURCE.data?.shopInfo?.poiId ?: '-999',
    ],
    cardMv: [bid: 'b_meishi_xxx_mv'],
    cardMc: [bid: 'b_meishi_xxx_mc'],
  ]
}}
```

### 6.2 列表截取与转换

```groovy
array('labels') {{
  def tags = DATA_SOURCE.data?.tags ?: []
  // 最多取前 3 个
  if (tags.size() > 3) tags = tags.subList(0, 3)
  tags.collect { [text: it.tagValue, type: it.type] }
}}
```

### 6.3 多条件判断

```groovy
string('buttonText') {{
  def orderStatus = DATA_SOURCE.data?.orderInfo?.status
  if (orderStatus == 1) return '去使用'
  if (orderStatus == 2) return '已完成'
  if (orderStatus == 3) return '已退款'
  '查看详情'  // 默认值
}}
```

### 6.4 安全的嵌套取值

```groovy
object('payParam') {{
  // 多层嵌套时，每层都用 ?. 防止 NPE
  def tradeExtra = NODE.SubmitOrderModule?.props?.payParams?.tradeOrderGenParamsExtraInfo
  [
    tradeOrderGenParamsExtra: tradeExtra ? DF.toJsonString(tradeExtra) : null,
    uniqueIdentifyCode: PREV_DATA?.payTypeInfoVO?.uniqueIdentifyCode,
  ]
}}
```

### 6.5 update 时的联动逻辑

```groovy
object('promoParam') {{
  def promotionVO = PREV_DATA?.promotionVO

  if (!COMMON_PARAMS.isUpdate) {
    return null
  }

  // 根据操作模块决定联动逻辑
  def operatorPromoType
  if (PAYLOAD.operatorModule == 'EquityTyingModule') {
    operatorPromoType = 'equityDeskCard'
  } else if (PAYLOAD.operatorModule == 'VipCardModule') {
    operatorPromoType = 'equityDeskCard'
  }

  if (!operatorPromoType) return null

  // 构造优惠快照
  def promoSnapshot = promotionVO?.promoInfoList?.collect { i ->
    [
      promoId: i.promoId,
      promoDetailType: i.promoDetailType,
      selected: operatorPromoType == i.promoDetailType ? (i.selected == 1 ? 0 : 1) : i.selected,
    ]
  }

  [
    operatorPromoType: operatorPromoType,
    promoSnapshot: promoSnapshot,
  ]
}}
```

---

## 7. 调试技巧

### 7.1 查看接口入参和出参

连接 AppMock 后，DUO 端到端接口（URL 含 `duo_csdk_v` 参数）的响应中会包含：
- `bizReq`：实际业务接口入参（`requestProps` 的计算结果）
- `bizRes`：实际业务接口出参

通过对比 `bizReq` 和预期值，可以快速定位 `requestProps` 中的表达式问题。

### 7.2 Mock 数据验证

使用 AppMock 或 Lyrebird 拦截请求，在 request body 中注入 `lyrebirdMockResp` 字段，可以模拟任意接口响应，验证 `currentData` 和节点 props 的计算结果。

```json
{
  "lyrebirdMockResp": {
    "code": 0,
    "data": {
      "title": "测试标题",
      "showError": false
    }
  }
}
```

同时在 request header 添加 `lyrebird: mock` 和 `mockRespV2: 1`。

### 7.3 常见报错排查

**`NullPointerException` in Groovy**：通常是没有用 `?.` 安全访问。检查所有链式访问，确保每一层都有 `?.`。

**`MissingPropertyException: No such property: XXX`**：变量名拼写错误，或在不可用的阶段使用了该变量（如在 `constData.groovy` 中使用 `DATA_SOURCE`）。

**`GroovyCastException`**：类型不匹配。常见于将字符串直接用于数字运算，需要 `DF.toNumber()` 转换。

**表达式返回 `null` 但预期有值**：检查 Elvis 操作符 `?:` 的使用，Groovy 中空字符串 `''` 也是 falsy，会被 `?:` 替换为默认值。

---

## 8. JavaScript 迁移对照

| 场景 | JavaScript | Groovy |
|------|-----------|--------|
| 可选链 | `a?.b?.c` | `a?.b?.c`（相同） |
| 空值合并 | `a ?? b` | `a ?: b`（但空字符串也触发） |
| 数组 map | `arr.map(i => i.name)` | `arr.collect { it.name }` |
| 数组 filter | `arr.filter(i => i.ok)` | `arr.findAll { it.ok }` |
| 数组 reduce | `arr.reduce((acc, i) => acc + i, 0)` | `arr.inject(0) { acc, i -> acc + i }` |
| 对象展开 | `{...a, key: val}` | `[*: a, key: val]` |
| 模板字符串 | `` `Hello ${name}` `` | `"Hello ${name}"` |
| 三元表达式 | `a ? b : c` | `a ? b : c`（相同） |
| 类型转换 | `Number(str)` | `DF.toNumber(str)` |
| JSON 序列化 | `JSON.stringify(obj)` | `DF.toJsonString(obj)` |
| 字符串比较 | `a === 'foo'` | `a == 'foo'`（Groovy `==` 调用 equals） |
| 数组长度 | `arr.length` | `arr.size()` |
| 数组截取 | `arr.slice(0, 3)` | `arr.subList(0, 3)` |
| 包含判断 | `arr.includes(x)` | `arr.contains(x)` |
| 对象 key 列表 | `Object.keys(obj)` | `obj.keySet()` |
