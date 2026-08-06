# duo 页面结构规则（struct.groovy）

> 协议规范来源：https://km.sankuai.com/collabpage/1749282893

## 目录

- [一、PageNode 结构总览](#一pagenode-结构总览) — nodeId/nodeType/materialId/resource/slots 接口定义
- [二、Groovy DSL 语法（struct.groovy）](#二groovy-dsl-语法structgroovy) — node/props/style/propConfig/on/slot/buildConfig 语法
  - [DSL 方法与 JSON 字段对应关系](#dsl-方法与-json-字段对应关系)
- [三、nodeName 命名规则](#三nodename-命名规则重要) — 页面内唯一、命名规范建议、nodeName 与 label 的区别
- [四、nodeType 取值规则](#四nodetype-取值规则) — NORMAL_MODULE / HANDLER_MODULE / LIST_CONTAINER
- [五、props 类型写法](#五props-类型写法) — 基本类型、object 内联/objectWithSub 嵌套、静态值
- [六、style 样式写法](#六style-样式写法) — 具名样式 key、常见样式 key 列表
- [七、propConfig 双向绑定配置](#七propconfig-双向绑定配置) — updateBy/isRequestArg/lock
- [八、xIf 展示条件规则](#八xif-展示条件规则) — Boolean 表达式、简单/多条件/复杂逻辑
- [九、事件（on）配置规则](#九事件on配置规则) — 基本事件、透传参数、附加入参、同一事件多次触发
- [十、slot 插槽规则](#十slot-插槽规则) — renderTop/renderContent/renderBottom 等常见插槽名
- [十一、buildConfig 配置规则](#十一buildconfig-配置规则) — 默认 null、lazyLoad 懒加载
- [十二、LIST_CONTAINER 列表节点](#十二list_container-列表节点) — items + iterateKey 配置
- [十三、struct 整体布局规范](#十三struct-整体布局规范) — 推荐页面结构模式、logics/弹窗/全局组件放置规则
- [十四、表达式（DataExpression）规则](#十四表达式dataexpression规则) — Groovy 双花括号语法、数据路径前缀、写法规则
- [十五、注意事项与常见错误](#十五注意事项与常见错误) — 7 条关键注意点

## 一、PageNode 结构总览

`struct` 是 `PageNode[]` 数组，每个节点描述一个组件实例。通过 `slots` 嵌套子节点形成组件树。

```typescript
interface PageNode {
  nodeId?: string;                              // 后端存储用，前端不用
  nodeType: 'NORMAL_MODULE' | 'HANDLER_MODULE' | 'LIST_CONTAINER';
  materialId: string;                           // 物料 ID（componentsMap 的 key）
  materialType?: 'lowCode' | 'proCode';
  resource: PageNodeResource;                   // 组件配置（props/styles/events/advanced）
  slots?: { [slotName: string]: PageNode[] };  // 插槽子节点
}

interface PageNodeResource {
  nodeName: string;         // 节点唯一标识（页面内唯一）
  label: string;            // 节点显示名称
  props?: { [key: string]: DataExpression };
  styles?: { [key: string]: DataExpression };
  propConfig?: { [key: string]: PropConfig };
  advanced?: PageNodeAdvanced;
  events?: { emit?: { [eventName: string]: PageNodeEventEmit[] } };
  buildConfig: null;        // 标准字段，固定为 null
}
```

---

## 二、Groovy DSL 语法（struct.groovy）

struct.groovy 使用 Groovy DSL 描述组件树，与 JSON 协议一一对应。

### 基本节点语法

```groovy
node('NodeName', 'materialId') {
  label '节点显示名称'
  xIf {{ /* Boolean 表达式 */ }}

  props {
    string('propKey') {{ /* 表达式 */ }}
    number('propKey') {{ /* 表达式 */ }}
    bool('propKey') {{ /* 表达式 */ }}
    array('propKey') {{ /* 表达式 */ }}
    object('propKey') {{ /* 表达式 */ }}
  }

  style('styleName') {
    string('backgroundColor') {{ '#FFFFFF' }}
    number('marginBottom') {{ 10 }}
  }

  propConfig('propKey') {
    updateBy 'onEventName'
    isRequestArg true
  }

  on('onEventName') {
    callMethod('TargetNodeName', 'methodName')
    transparentArg('from', 'to')
    props {
      string('key') {{ 'value' }}
    }
  }

  buildConfig {
    lazyLoad true
    prefetch true
    splitFile true
  }

  slot('slotName') {
    node('ChildNode', 'materialId') {
    }
  }
}
```

> 字段说明：`xIf` 控制节点是否展示；`propConfig.updateBy` 为双向绑定事件名，`isRequestArg` 表示 update/submit 时是否传给后端；`transparentArg` 为透传参数映射；`on` 块中的 `props` 为附加入参（可选）；`buildConfig` 中 `lazyLoad` 懒加载、`prefetch` 预请求、`splitFile` 拆分文件

### DSL 方法与 JSON 字段对应关系

| Groovy DSL                      | JSON 协议字段                        |
| ------------------------------- | ------------------------------------ |
| `node('Name', 'id') { }`        | `nodeName` + `materialId`            |
| `label '...'`                   | `resource.label`                     |
| `xIf {{ expr }}`                | `resource.advanced.displayRule`      |
| `props { string/number/... }`   | `resource.props`                     |
| `style('name') { ... }`         | `resource.styles`                    |
| `propConfig('key') { ... }`     | `resource.propConfig`                |
| `on('event') { ... }`           | `resource.events.emit[eventName][]`  |
| `callMethod('node', 'method')`  | `notifyNodeName` + `notifyEventName` |
| `transparentArg('from', 'to')`  | `transparentArg[].from` + `.to`      |
| `buildConfig { lazyLoad true }` | `resource.buildConfig` (非 null 时)  |
| `slot('name') { ... }`          | `slots[slotName][]`                  |

---

## 三、nodeName 命名规则（重要）

### nodeName 必须页面内唯一

**错误信息**：`nodeName：LeezCard页面内不唯一`

**问题原因**：在 `node('NodeName', 'materialId')` 语法中：

- **第一个参数（nodeName）**：节点的唯一标识名称，必须在**整个页面内唯一**
- **第二个参数（materialId）**：物料 ID（componentsMap 的 key），同一物料的多个实例共用同一个 ID

**错误写法**：多个相同类型组件使用了相同的 nodeName

> ❌ 错误：三个节点都叫同一个名字

```groovy
node('LeezCard', '37') { label '商品信息卡片' }
node('LeezCard', '37') { label '用户信息卡片' }
node('LeezCard', '37') { label '底部提交栏' }
```

**正确写法**：每个节点使用唯一的业务名称作为 nodeName

> ✅ 正确：每个节点有唯一的 nodeName，materialId 可以相同

```groovy
node('DealInfoCard', '37') { label '商品信息卡片' }
node('UserInfoCard', '37') { label '用户信息卡片' }
node('SubmitBarCard', '37') { label '底部提交栏' }
```

### 命名规范建议

| 组件类型 | nodeName 命名建议 | 示例                                     |
| -------- | ----------------- | ---------------------------------------- |
| 文本组件 | 功能 + Text       | `DealNameText`, `PriceText`, `PhoneText` |
| 卡片组件 | 功能 + Card       | `DealInfoCard`, `UserInfoCard`           |
| 按钮组件 | 功能 + Button     | `SubmitButton`, `CancelButton`           |
| 布局组件 | 功能描述          | `MainLayout`, `TopBar`, `BottomBar`      |
| 逻辑组件 | 功能 + Logic      | `LifecycleLogic`, `PageLogic`            |

### nodeName 与 label 的区别

| 属性                            | 用途                                   | 唯一性要求         |
| ------------------------------- | -------------------------------------- | ------------------ |
| `nodeName`（node 第一个参数）   | 节点的程序标识，用于事件通信、方法调用 | **必须页面内唯一** |
| `label`                         | 节点的显示名称，便于开发者识别         | 建议唯一，用于调试 |
| `materialId`（node 第二个参数） | 物料 ID，映射到 componentsMap          | 同一物料实例共用   |

> `nodeName`（第一参数）是唯一标识，调用方法时使用；`label` 是显示名称，便于识别

```groovy
node('DealNameText', '38') {
  label '商品名称'
  props {
    string('text') {{ DATA_SOURCE?.data?.dealName ?: '' }}
  }
}
```

> 通过 `nodeName` 调用其他节点的方法，使用 `nodeName` 而非 `label`

```groovy
on('onChange') {
  callMethod('DealNameText', 'updateValue')
}
```

---

## 四、nodeType 取值规则

| 值               | 说明                        | 用于   |
| ---------------- | --------------------------- | ------ |
| `NORMAL_MODULE`  | 普通 UI 组件（最常用）      | struct |
| `HANDLER_MODULE` | 事件处理/逻辑组件           | logics |
| `LIST_CONTAINER` | 列表容器（items + iterate） | struct |

- **struct** 中的节点通常是 `NORMAL_MODULE`
- **logics** 中的节点通常是 `HANDLER_MODULE`（如生命周期、导航 API 等）

---

## 五、props 类型写法

### 基本类型

```groovy
props {
  string('title') {{ DATA_SOURCE?.data?.title ?: '' }}
  number('count') {{ DATA_SOURCE?.data?.count ?: 0 }}
  bool('isShow') {{ !!DATA_SOURCE?.data?.visible }}
  array('list') {{ DATA_SOURCE?.data?.itemList ?: [] }}
  object('info') {{ DATA_SOURCE?.data?.userInfo }}
}
```

### object 类型（内联构建）

```groovy
object('params') {{
  [
    orderId: DATA_SOURCE?.data?.orderId,
    poiId: CONST.baseInfo.poiId ?: '-999',
    bizType: CONST.baseInfo.bizType,
  ]
}}
```

### object 类型（使用 objectWithSub，嵌套结构）

```groovy
objectWithSub('lx') {
  objectWithSub('submitOrder') {
    object('valLab') {{
      return [
        goods_id: CONST?.goodsID ?: '-999',
      ]
    }}
  }
}
```

### 静态值写法

```groovy
string('type') {{ 'title3' }}       // 字符串常量用单引号
number('gap') {{ 0 }}               // 数字直接写
bool('hidden') {{ false }}          // 布尔值直接写
```

---

## 六、style 样式写法

`style` 对应 JSON 中的 `resource.styles`，通常使用具名样式 key：

```groovy
style('containerStyle') {
  number('marginBottom') {{ 10 }}
  number('paddingTop') {{ 12 }}
  string('backgroundColor') {{ '#F9F9F9' }}
}

style('style') {
  string('backgroundColor') {{ '#FFFFFF' }}
}

style('scrollStyle') {
  number('paddingLeft') {{ 8 }}
  number('paddingRight') {{ 8 }}
}
```

常见样式 key：`style`、`containerStyle`、`wrapCardStyle`、`scrollStyle`、`contentStyle`、`bottomSafeAreaStyle`

---

## 七、propConfig 双向绑定配置

```groovy
propConfig('value') {
  updateBy 'onChange'       // 触发双向更新的事件名
  isRequestArg true         // update/submit 时是否将该字段传给后端
  lock false                // 加锁：update/submit 执行中不触发（默认 false)
}
```

| 字段           | 说明                                                | 默认值 |
| -------------- | --------------------------------------------------- | ------ |
| `isRequestArg` | update/submit 时是否将该 prop 传给后端作为请求参数  | false  |
| `updateBy`     | 双向绑定：当指定事件触发时，自动更新该 prop 的值    | —      |
| `lock`         | 加锁：当 update/submit 正在执行时，该事件触发不生效 | false  |

---

## 八、xIf 展示条件规则

`xIf` 对应 `resource.advanced.displayRule`，值为 Boolean 类型的 Groovy 表达式：

简单条件：

```groovy
xIf {{ !CONST.isError }}
xIf {{ !!DATA_SOURCE?.data?.invoiceVO }}
```

多条件：

```groovy
xIf {{ CONST.isSuperGroupScene && !!DATA_SOURCE?.data?.bookInfoVO }}
```

复杂逻辑（需要 return）：

```groovy
xIf {{
  def payType = DATA_SOURCE.data.priceVO?.payType
  def payAmount = DATA_SOURCE.data.priceVO?.totalPayAmount
  return payType != 2 && !!payAmount && (payAmount as Double) > 0
}}
```

---

## 九、事件（on）配置规则

### 基本事件

```groovy
on('onEventName') {
  callMethod('TargetNodeName', 'targetMethodName')
}
```

### 透传参数（transparentArg）

透传参数将事件回调携带的参数映射到目标方法的入参：

```groovy
on('onScrollTo') {
  callMethod('LayoutTopBottom', 'scrollOffsetY')
  transparentArg('y', 'y')
}

on('onUpdateRoomNum') {
  callMethod('LifecycleLogic', 'update')
  transparentArg('value', 'payload.roomNum')
  transparentArg('refreshPromotion', 'payload.refreshPromotion')
}
```

> `transparentArg` 第一个参数为来源（事件参数路径），第二个参数为目标（方法参数名）

不透传任何参数（空透传）：

```groovy
on('onCountDownEnd') {
  callMethod('LifecycleLogic', 'update')
  transparentArg('', '')
}
```

> **重要**：`transparentArg('', '')` 表示不透传任何参数，是明确声明"不透传"，**不配置 transparentArg** 字段则表示"不透传"（等效）。

### 附加入参（props）

事件触发时携带的额外参数（静态值）：

```groovy
on('onCancelRuleClickHandler') {
  callMethod('HfeHotelSubmitRoomDetail', 'onOpenModal')
  props {
    string('source') {{ 'cancelServices' }}
  }
  transparentArg('', '')
}
```

### 同一事件多次触发

同一 `on` 事件可以配置多个响应，按顺序触发：

```groovy
on('onKeyBoardShow') {
  callMethod('GuestCard', 'onKeyBoardShow')
  transparentArg('', '')
}
on('onKeyBoardShow') {
  callMethod('BottomBar', 'onKeyBoardShow')
}
```

---

## 十、slot 插槽规则

slots 用于嵌套子节点，常见插槽名：

| 插槽名          | 用途     |
| --------------- | -------- |
| `renderTop`     | 顶部区域 |
| `renderContent` | 内容区域 |
| `renderBottom`  | 底部区域 |
| `renderHeader`  | 头部     |
| `renderFooter`  | 尾部     |
| `renderModules` | 模块列表 |
| `default`       | 默认插槽 |

```groovy
node('LayoutTopBottom', '7') {
  label '页面布局（上中下）'
  slot('renderTop') {
    node('NavBar', '12') {
      label '导航栏'
    }
  }
  slot('renderContent') {
    node('ContentCard', '25') {
      label '内容卡片'
    }
  }
  slot('renderBottom') {
    node('BottomBar', '798') {
      label '底部提单栏'
    }
  }
}
```

---

## 十一、buildConfig 配置规则

`buildConfig` 在 JSON 协议中为 `null`（所有节点均存在此字段）。在 Groovy DSL 中：

> 默认不写 `buildConfig`，JSON 输出为 `null`；需要懒加载时才显式声明

```groovy
node('NavBar', '12') {
  label '导航栏'
}

node('InsuranceTying', '704') {
  label '保险搭售'
  buildConfig {
    lazyLoad true
  }
}
```

> **规则**：非首屏、交互后才展示、或较重的组件，建议设置 `lazyLoad true`。

---

## 十二、LIST_CONTAINER 列表节点

列表节点需要配置 `items`（数据源）和 `iterateKey`（唯一 key），通过 `advanced` 配置：

```json
{
  "nodeType": "LIST_CONTAINER",
  "materialId": "xxx",
  "resource": {
    "nodeName": "OrderList",
    "label": "订单列表",
    "advanced": {
      "items": {
        "dataType": "List",
        "__resolveType__": "BACK_END",
        "data": "DATA_SOURCE.data?.orderList"
      },
      "iterateKey": {
        "dataType": "String",
        "__resolveType__": "BACK_END",
        "data": "item.orderId"
      }
    }
  }
}
```

---

## 十三、struct 整体布局规范

典型的页面结构（推荐模式）：

```groovy
node('CommonParams', '757') {
  label '通用参数'
}

node('LayoutTopBottom', '7') {
  label '页面布局（上中下）'
  xIf {{ !CONST.isError }}
  slot('renderTop') {
    node('NavBar', '12') { label '导航栏' }
  }
  slot('renderContent') {
    node('ContentCard', '25') { ... }
    node('PromotionCard', '30') { ... }
  }
  slot('renderBottom') {
    node('SubmitBar', '50') { label '提交栏' }
  }
}

node('LifecycleLogic', '830') {
  label '页面生命周期逻辑'
}

node('DetailModal', '805') {
  label '详情弹窗'
}
```

> **重要规则**：
>
> - **logics（逻辑组件）** 有两种放法，区别如下：
>   - **放在 `struct` 中**（作为独立节点，不在任何插槽内）：nodeType 为 `NORMAL_MODULE`，适合需要与其他 struct 节点保持相对位置关系、或需要在渲染树中占位的逻辑组件（如弹窗触发器）
>   - **放在 `logics` 数组中**：nodeType 为 `HANDLER_MODULE`，适合纯逻辑处理、无需在渲染树中占位的组件（如全局事件监听、数据处理器）
>   - 两种写法功能等价，区别仅在于组织方式；**推荐优先放在 `logics` 数组中**，使 struct 结构更清晰
> - **弹窗/全局组件** 通常放在布局组件之外（平级节点）
> - 组件书写顺序从上到下对应视觉层级从上到下

---

## 十四、表达式（DataExpression）规则

> ⚠️ **重要**：表达式是 **Groovy** 语法（后端执行），不是 JavaScript！

### Groovy DSL 双花括号语法

在 struct.groovy 中，表达式使用 `{{ }}` 双花括号包裹：

```groovy
string('title') {{ DATA_SOURCE?.data?.title ?: '' }}
bool('isShow') {{ !!DATA_SOURCE?.data?.visible }}
```

### 常用数据路径前缀

| 前缀                            | 含义                     |
| ------------------------------- | ------------------------ |
| `DATA_SOURCE?.data?.xxx`        | 数据源返回的 data 字段   |
| `DATA_SOURCE.code`              | 数据源返回的 code 字段   |
| `PAGE_QUERY?.xxx`               | 页面 URL 参数            |
| `CONST.xxx`                     | constData 中定义的常量   |
| `COMMON_PARAMS.systemInfo?.xxx` | 通参中的环境信息         |
| `COMMON_PARAMS.userInfo?.xxx`   | 通参中的用户信息         |
| `COMMON_PARAMS.location?.xxx`   | 通参中的定位信息         |
| `PROPS.xxx`                     | 节点自身 propConfig 的值 |

### 表达式写法规则

| 场景               | 写法              | 示例                                        |
| ------------------ | ----------------- | ------------------------------------------- |
| 字符串字面量       | 单引号包裹        | `{{ 'hello' }}`                             |
| 数字字面量         | 直接写            | `{{ 10 }}`                                  |
| null 兜底（Elvis） | `?:` 运算符       | `{{ DATA_SOURCE?.data?.title ?: '' }}`      |
| 存在性判断         | `!!` 双感叹号     | `{{ !!DATA_SOURCE?.data?.list }}`           |
| 列表判断           | `.size() > 0`     | `{{ DATA_SOURCE?.data?.list?.size() > 0 }}` |
| 取反条件           | `!expr`           | `{{ !CONST.isError }}`                      |
| 比较判断           | `!= / == / > / <` | `{{ DATA_SOURCE.code != 0 }}`               |
| 多行复杂表达式     | 使用 return       | `{{ def x = ...; return x > 0 }}`           |

---

## 十五、注意事项与常见错误

1. **nodeName 重复**：同一页面内所有 node 的第一个参数必须唯一，否则会报错。
2. **materialId 不能随意编造**：必须与 `componentsMap` 中的 key 一一对应，且只能来自平台真实物料 ID。
3. **constData 不可用于 reqProps**：`CONST.xxx` 只能在 struct 的表达式中使用，不能用于数据源的请求入参（reqProps）。
4. **logics 中的节点 nodeType 为 HANDLER_MODULE**：逻辑组件放在 `logics` 数组中，其 nodeType 是 `HANDLER_MODULE`，不是 `NORMAL_MODULE`。
5. **样式字段通过 styles 而非 props 定义**：DUO 2.0 协议中，样式字段单独放在 `styles` 对象中，便于运行时动态化处理。
6. **同事件多监听按声明顺序触发**：同一事件名（如 `on('onChange')`）可声明多次，按声明顺序依次触发。
7. **buildConfig 标准字段固定为 null**：所有节点的 `resource` 中均需包含 `buildConfig: null`，如需懒加载才设置 `{ lazyLoad: true }`。
