---
# F · DUO 中的 Groovy 表达式

> 覆盖范围：DUO 使用的 Groovy 版本、五类协议文件的语法规范、上下文变量、常用 DF 工具函数、常见陷阱与 JS→Groovy 对照。

---

## 1. 背景

DUO 后端 SDK 使用 **Groovy 2.4.17** 作为表达式引擎，在 StageEnum 的 DATA_SOURCE、STRUCT、NODE_DATA 阶段执行各协议文件中的闭包表达式。Groovy 语法与 Java 高度兼容，同时支持动态类型、闭包、集合操作等特性，但与 JavaScript 有若干关键差异。

---

## 2. 五类协议文件

### 2.1 constData.groovy

定义页面级常量，在 NODE_DATA 阶段最先执行，结果注入 `CONST` 变量。

```groovy
constant {
  // 字符串常量
  string('bizCode') {{ 'nib.general.groupbuy' }}

  // 布尔值（依赖 PAGE_QUERY）
  bool('isPop') {{
    (PAGE_QUERY.isTransparent == 'true') || (PAGE_QUERY.mrn_transparent == 'true')
  }}

  // 对象（依赖 COMMON_PARAMS）
  object('commonParams') {{
    def systemInfo = COMMON_PARAMS.systemInfo
    [
      deal_id: PAGE_QUERY.dealid ?: '-999',
      poi_id: PAGE_QUERY.shopid ?: '-999',
    ]
  }}

  // 嵌套对象（objectWithSub）
  objectWithSub('lx') {
    string('cid') {{ 'c_0evvuz5' }}
    string('channelName') {{ 'gc' }}
  }

  // 数字
  number('moduleGap') {{ 10 }}

  // 数组
  array('basePageModules') {{
    [
      [nodeName: 'NavBar', positionType: 'top'],
      [nodeName: 'ContentModule', positionType: 'content'],
    ]
  }}
}
```

**注意**：`objectWithSub` 用于定义有子字段的对象（子字段各自独立计算），`object` 用于整体返回一个 Map。

### 2.2 dataSourceMap.groovy

定义数据源，包含请求参数构造（`requestProps`）、响应数据映射（`currentData`）、业务状态判断（`bizRespStatus`）。

```groovy
dataSource {
  dataSourceId '15'   // 数据源 ID，对应后端接口配置

  requestProps {
    // 构造接口入参
    object('productParam') {{
      def skuId = PAYLOAD.skuId ?: PREV_DATA?.productInfoVO?.skuId ?: PAGE_QUERY.skuid
      [
        quantity: PAYLOAD.quantity ?: PREV_DATA?.quantity ?: 1,
        productId: CONST.queryDealId,
        skuId: skuId,
      ]
    }}
    string('bizCode') {{ CONST.bizCode }}
  }

  currentData {
    // 从接口响应中提取数据，注入 PREV_DATA
    number('quantity') {{ DATA_SOURCE.data?.productInfoVO?.quantity }}
    object('promotionVO') {{ DATA_SOURCE.data?.promotionVO }}
    bool('isExclusiveCard') {{
      def equityInfoVO = DATA_SOURCE.data?.equityInfoVO
      [1, 2].contains(equityInfoVO?.type)
    }}
  }

  bizRespStatus {
    bool('isError') {{ DATA_SOURCE?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE?.userMessage ?: '服务异常，请稍后重试' }}
    errorToast true              // 自动弹 toast
    errorNoReturnStruct true     // 出错时不返回节点树
  }

  // submit 专用状态判断
  submitBizRespStatus {
    bool('isError') {{ DATA_SOURCE?.code != 0 }}
    string('errorMsg') {{ DATA_SOURCE?.userMessage ?: '服务异常，请稍后重试' }}
    errorToast true
  }
}
```

### 2.3 struct.groovy

定义节点树结构，在 STRUCT 阶段执行。

```groovy
// 普通节点
node('NavBar1', '1') {
  label '导航栏'
  props {
    string('title') {{ DATA_SOURCE.data?.title }}
  }
  style('style') {
    string('backgroundColor') {{ '#FFFFFF' }}
  }
  on('onRefresh') {
    callMethod('Lifecycle1', 'update')
  }
}

// 条件渲染（xIf）
node('ErrorModule1', '2') {
  label '错误模块'
  xIf {{ DATA_SOURCE.data?.showError == true }}
  props {
    string('msg') {{ DATA_SOURCE.data?.errorMsg }}
  }
}

// 循环渲染（xFor）
node('ListContainer1', '3') {
  label '列表容器'
  nodeType 'LIST_CONTAINER'
  key {{ FOR.item.id }}
  xFor {{ CONST.list }}
  slot('children') {
    node('ItemCard1', '4') {
      props {
        string('name') {{ FOR.item.name }}
        number('index') {{ FOR.index }}
      }
    }
  }
}

// 引入外部文件
include 'nodes/MaxLeezCard1.groovy'
```

**事件绑定**：

```groovy
on('onChange') {
  callMethod('Lifecycle1', 'update')
  // 透传事件回调参数
  transparentArg('value', 'payload.value')
}

on('onUrlUpdate') {
  callMethod('NavBar1', 'onUpdateUrl')
  transparentArg('url', 'url')
  // 带条件
  // emitCondition {{ PAYLOAD.url != null }}
}
```

### 2.4 nodes/<NodeName>.groovy

单个节点的 props/styles/events 定义，从 struct.groovy 中 `include` 引入，或内联在 struct.groovy 中。

```groovy
// nodes/OrderDetailNavBar1.groovy
node('OrderDetailNavBar1', '78') {
  label '订单详情导航栏'
  props {
    string('orderTitle') {{ DATA_SOURCE.data?.statusInfo?.title?.text }}
    bool('shareable') {{ DATA_SOURCE.data?.dealInfo?.dealAction?.shareable }}
    object('lx') {{
      [
        *: CONST.lx,
        kefuMc: [bid: 'b_jctnayif'],
      ]
    }}
  }
  on('onRefresh') {
    callMethod('MeishiCommonDuoLifecycle1', 'update')
  }
}
```

### 2.5 logics.groovy

定义逻辑节点（lifeCycle 物料和事件处理物料），监听生命周期事件。

```groovy
node('MeishiCommonDuoLifecycle1', '13') {
  label '内置物料-页面生命周期'

  // preview 响应后触发
  on('preview.onResponse') {
    callMethod('MeishiCommonEventLx1', 'lxTrackMPT')
    props {
      string('channelName') {{ CONST.lx.channelName }}
      string('cid') {{ CONST.lx.cid }}
    }
    transparentArg('', '')
  }

  // preview 失败时触发
  on('preview.onFail') {
    callMethod('MeishiCommonEventLx1', 'lxTrackModuleView')
    props {
      string('val_bid') {{ 'TODO' }}
    }
  }

  // update 成功时触发
  on('update.onSuccess') {
    callMethod('PageLogic1', 'onRefreshSuccess')
  }
}

node('MeishiCommonEventLx1', '16') {
  label '数据埋点'
}
```

---

## 3. 上下文变量速查

| 变量 | 可用文件 | 说明 |
|------|----------|------|
| `PAGE_QUERY` | 全部 | 跳链参数，如 `PAGE_QUERY.shopid` |
| `COMMON_PARAMS` | 全部（DATA_SOURCE 阶段后） | 通参，含 `systemInfo`、`userInfo`、`cityInfo`、`location`、`isPreview`、`isUpdate`、`isSubmit` |
| `DATA_SOURCE` | currentData、struct、nodes | 业务接口原始响应，如 `DATA_SOURCE.data?.shopInfo` |
| `PREV_DATA` | requestProps（update 时）、nodes | 上一次 currentData 计算结果 |
| `CONST` | struct、nodes | constData.groovy 计算结果 |
| `NODE` | nodes（当前节点之后的节点不可用） | 已计算节点的 props，如 `NODE.NavBar1?.props?.title` |
| `PAYLOAD` | requestProps、nodes（update/submit/check） | 前端 emit 携带的 payload |
| `FOR` | xFor 节点内 | 当前循环项，`FOR.item`、`FOR.index` |

**COMMON_PARAMS 常用字段**：

```groovy
def systemInfo = COMMON_PARAMS.systemInfo
systemInfo.IS_MT      // 是否美团 App
systemInfo.IS_DP      // 是否点评 App
systemInfo.isMRN      // 是否 MRN 容器
systemInfo.isWeb      // 是否 Web/H5

COMMON_PARAMS.isPreview   // 是否 preview 请求
COMMON_PARAMS.isUpdate    // 是否 update 请求
COMMON_PARAMS.isSubmit    // 是否 submit 请求
```

---

## 4. DF 工具函数

`DF` 是 DUO 提供的工具函数集，在所有 Groovy 表达式中可用。

| 函数 | 说明 | 示例 |
|------|------|------|
| `DF.toJsonString(obj)` | 对象转 JSON 字符串 | `DF.toJsonString(PAGE_QUERY)` |
| `DF.toNumber(str)` | 字符串转数字 | `DF.toNumber(PAGE_QUERY.count)` |
| `DF.toBoolean(val)` | 转布尔值 | `DF.toBoolean(PAGE_QUERY.flag)` |

---

## 5. Groovy 与 JavaScript 关键差异

### 5.1 空安全操作符

Groovy 的 `?.` 与 JS 相同，但 `?:` 是 Elvis 操作符（类似 JS 的 `??` 但会对空字符串也生效）：

```groovy
// Groovy
def name = data?.user?.name ?: '默认值'  // null 或 false 时取默认值

// 注意：'' ?: '默认值' 在 Groovy 中返回 '默认值'（空字符串是 falsy）
// 而 JS 中 '' ?? '默认值' 返回 ''
```

### 5.2 Map 字面量

```groovy
// Groovy Map（注意 key 不需要引号，除非含特殊字符）
def m = [name: 'foo', count: 1]

// 展开操作符（类似 JS 的 spread）
def merged = [*: CONST.lx, extraKey: 'value']

// 访问
m.name      // 'foo'
m['name']   // 'foo'
```

### 5.3 集合操作

```groovy
// collect（类似 JS map）
def names = list.collect { it.name }

// findAll（类似 JS filter）
def active = list.findAll { it.active == true }

// inject（类似 JS reduce）
def total = list.inject(0) { acc, item -> acc + item.price }

// 链式
def result = list
  .findAll { it.type == 1 }
  .collect { [id: it.id, name: it.name] }
```

### 5.4 字符串

```groovy
// GString（类似 JS 模板字符串）
def msg = "Hello ${name}!"

// 多行字符串
def text = """
  第一行
  第二行
"""

// 注意：DUO 协议中反引号（`）是特殊字符，需要转义
string('brandName') {{ '`尾`\n款买单#2' + '!' }}
```

### 5.5 闭包语法

DUO 协议中的表达式使用双花括号 `{{ }}` 包裹，这是 Groovy 闭包的特殊写法：

```groovy
// 单行表达式（最后一行自动作为返回值）
string('title') {{ DATA_SOURCE.data?.title }}

// 多行表达式（需要显式 return 或确保最后一行是返回值）
object('param') {{
  def shopId = DATA_SOURCE.data?.shopInfo?.poiId
  if (!shopId) {
    return null
  }
  [poiId: shopId, type: 1]
}}
```

### 5.6 常见陷阱

**陷阱1：`==` 比较字符串**

```groovy
// Groovy 中 == 调用 equals()，字符串比较是安全的
PAGE_QUERY.isTransparent == 'true'  // 正确

// 但注意 PAGE_QUERY 的值都是字符串，不要用 === 或 !==
```

**陷阱2：数字类型**

```groovy
// PAGE_QUERY 的值都是字符串，需要转换
def count = DF.toNumber(PAGE_QUERY.count)  // 转为数字
def price = DATA_SOURCE.data?.price / 100  // 整数除法可能丢精度，用 100.0
```

**陷阱3：null 与空集合**

```groovy
// 安全写法
def list = DATA_SOURCE.data?.items ?: []
list.collect { it.name }  // 不会 NPE

// 危险写法
DATA_SOURCE.data?.items.collect { it.name }  // items 为 null 时 NPE
```

**陷阱4：`return` 在闭包中**

```groovy
// 在 collect/findAll 等闭包中，return 只退出当前闭包迭代，不退出外层
list.collect { item ->
  if (item.type == 0) return null  // 只跳过当前 item，不退出 collect
  item.name
}
```

**陷阱5：`NODE` 变量的可用性**

```groovy
// NODE 只包含在当前节点之前已计算的节点
// 如果 NodeA 依赖 NodeB 的 props，NodeB 必须在 struct.groovy 中排在 NodeA 之前
NODE.NodeB?.props?.someValue  // NodeB 必须先于 NodeA 定义
```

---

## 6. 典型模式速查

### 6.1 preview/update 分支处理

```groovy
object('param') {{
  if (COMMON_PARAMS.isPreview) {
    // preview 时从 PAGE_QUERY 取初始值
    return [skuId: PAGE_QUERY.skuid]
  }
  // update 时从 PAYLOAD 或 PREV_DATA 取
  [skuId: PAYLOAD.skuId ?: PREV_DATA?.productInfoVO?.skuId]
}}
```

### 6.2 多端适配

```groovy
string('cid') {{
  def systemInfo = COMMON_PARAMS.systemInfo
  systemInfo.IS_DP ? 'dp_cid_value' : 'mt_cid_value'
}}
```

### 6.3 安全的列表截取

```groovy
array('labels') {{
  def tags = DATA_SOURCE.data?.tags ?: []
  if (tags.size() > 3) tags = tags.subList(0, 3)
  tags.collect { [text: it.tagValue] }
}}
```

### 6.4 Map 合并（展开操作符）

```groovy
object('lx') {{
  [
    *: CONST.lx,                          // 展开基础 lx 配置
    valLab: [*: CONST.lx.valLab, deal_id: PAGE_QUERY.dealid],  // 覆盖 valLab
    cardMv: [bid: 'b_special_groupon_xxx_mv'],
  ]
}}
```

### 6.5 bizRespStatus 错误上报

```groovy
bizRespStatus {
  bool('isError') {{ DATA_SOURCE?.code != 0 }}
  string('errorMsg') {{ DATA_SOURCE?.userMessage ?: '服务异常，请稍后重试' }}
  object('extra') {{
    if (DATA_SOURCE?.code != 0) {
      return [
        reportMsg: DATA_SOURCE?.code + '：' + (DATA_SOURCE?.message ?: ''),
        reportTags: [code: DATA_SOURCE?.code]
      ]
    }
    [reportTags: [code: 0]]
  }}
  errorToast true
  errorNoReturnStruct true
}
```
