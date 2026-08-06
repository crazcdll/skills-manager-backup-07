# DUO 框架代码审查规范

> 适用于 DUO 低代码配置平台项目，涵盖 Groovy DSL、页面配置文件、Max 源码物料等。
> DUO 项目核心文件：`struct.groovy`、`dataSourceMap.groovy`、`constData.groovy`、`logics.groovy`、`componentsMap.json`、`pageBuildConfig.json`
>
> **校准说明**：与 **DUO 官方/团队维护的协议与开发文档**（`duo-knowledge` skill，包含协议体系、Groovy 表达式、构建与排障等）对齐，不绑定某一本地目录或 skill 打包结构。若与具体**业务接口成功码、返回字段名**或线上行为冲突，以接口文档与线上为准。
>
> 更新时间：2026.5.29

---

## 目录

- [协议契约与变量边界](#协议契约与变量边界)
- [一、DUO 项目结构规范](#一duo-项目结构规范)
- [二、Groovy DSL 编码规范](#二groovy-dsl-编码规范)
- [三、struct.groovy 页面结构规范](#三structgroovy-页面结构规范)
- [四、dataSourceMap.groovy 数据源规范](#四datasourcemapgroovy-数据源规范)
- [五、constData.groovy 常量定义规范](#五constdatagroovy-常量定义规范)
- [六、logics.groovy 生命周期与事件规范](#六logicsgroovy-生命周期与事件规范)
- [七、性能与安全规范](#七性能与安全规范)
- [八、Max 源码物料规范](#八max-源码物料规范)
- [九、平台踩坑与跨端差异](#九平台踩坑与跨端差异)

---

## 协议契约与变量边界

> **审阅前必读**：本节是 **PageProtocol / 端到端协议**层面的**语义与硬约束**（背景 + 必查边界），用于对齐引擎/协议行为；**不是**代码风格或「推荐写法」清单——后者见 **D01 起**各条及正/反例。

### 协议语义与审查前提
- **等级**：高（违反易导致逻辑错误或与引擎行为不一致）
- **描述**：核对 **官方协议说明与表达式文档**中的下列变量边界（段首已说明：本条属**契约与语义**，非风格建议）。
- **PAYLOAD**
  - 用于 **update / submit / check** 等场景由前端 `emit` 传入的**临时数据**；**preview 时为空**。
  - 部分**协议变量表**只写「PAYLOAD 仅用于 update 入参」；**引擎侧** submit/check 也可能携带 payload，**以当前引擎与业务接口约定为准**。
  - **禁止**在首屏 preview 的 `requestProps` 中单独依赖 `PAYLOAD` 且无 `PAGE_QUERY` / `PREV_DATA` 兜底。
  - **submit** 时不要指望 `PAYLOAD` 携带此前多轮 update 的累计状态，持久业务态应从 **PREV_DATA**（及 currentData 映射）读取。
- **PREV_DATA**
  - 来自 `currentData` 映射结果；在 **requestProps** 中 preview 时通常为空，update 时为上一轮快照。
  - **应跨请求保持的业务快照**（写入 `currentData`、作为稳定出参）须用 **PREV_DATA**，勿用 **NODE** 当作持久真相源（NODE 反映当次请求内已算节点状态）。
- **NODE**
  - 在 **NODE_DATA** 阶段（含 `struct.groovy` / `nodes/*.groovy` 中的 props）以及数据源 **`requestProps`** 中，可按 **nodeName** 读取已计算节点的 `NODE.<nodeName>.props`；**只能引用 struct 中排在前面的已计算节点**。
  - 与 **PREV_DATA** 分工：同一次请求内的跨节点串联用 **NODE**；跨请求稳定数据用 **PREV_DATA** / `DATA_SOURCE.data`。
- **PROPS**
  - **当前节点**在勾选「保存状态」后，可在表达式中使用 **`PROPS.xxx`**（与读取**其他节点**的 `NODE.xxx.props` 不同）；配置与语义以协议说明为准。
- **DATA_SOURCE（多数据源）**
  - 页面存在多个数据源时，`DATA_SOURCE` 可表示**当前正在计算的数据源**；读**其他数据源**结果须遵守协议中对变量/阶段的约定。
- **布尔表达式**
  - 协议中的 `displayRule`、`emitCondition`、生命周期里的 `condition` 等，结果须为 **boolean**；建议 `!!expr`，并注意 **字符串 `"true"` / 空字符串** 与 Groovy Truth 导致的误判（条件渲染类问题可对照团队 **渲染/展示** 排障说明）。
- **static / pageContainer**
  - **static**：非必要禁止使用；须为视图树**顶层**，数据不参与主数据流。
  - **pageContainer**：全页**仅一个**，须为顶层；用于承载 loading/error 等（`props.children`）。
- **术语**：搭建协议 JSON 里数据源入参常写作 **`reqProps`**，Groovy 源文件中对应块名为 **`requestProps`**，含义相同。

---

## 一、DUO 项目结构规范

### D01 项目目录结构完整性
- **等级**：高
- **描述**：DUO 页面项目必须包含完整的核心文件
- **必需文件**：`struct.groovy`（页面结构）、`dataSourceMap.groovy`（数据源映射）、`componentsMap.json`（组件映射）、`pageBuildConfig.json`（构建配置）
- **可选文件**：`constData.groovy`（常量定义）、`logics.groovy`（逻辑处理）、`scripts/`（脚本目录）、`dependencies.json`（依赖配置）
- **协议 JSON 还可能包含**：`duoVersion`、`ohDependencies`（鸿蒙依赖）等字段，以搭建协议说明为准；**并非**所有页面目录都拆成独立 `.json` 文件名，以实际出码/仓库为准。
- **真实项目结构示例**（以 `order-submit/booking` 为例）：
```
order-submit/booking/
├── scripts/                    # 脚本目录
├── componentsMap.json          # 组件映射
├── constData.groovy            # 常量定义（环境参数、埋点、业务常量）
├── dataSourceMap.groovy        # 数据源映射（接口入参、响应映射、异常处理）
├── dependencies.json           # 依赖配置
├── logics.groovy               # 生命周期事件与埋点逻辑
├── pageBuildConfig.json        # 构建配置
└── struct.groovy               # 页面组件树结构
```
- **关注点**：缺少核心文件会导致页面无法正常构建和渲染

### D02 文件职责单一
- **等级**：高
- **描述**：每个 groovy 文件应职责单一
- **职责划分**：
  - `struct.groovy`：只定义组件树结构、组件 props 映射、渲染条件
  - `dataSourceMap.groovy`：只定义数据源 ID、请求入参（Groovy 中为 `requestProps` 块；JSON 协议字段常写作 `reqProps`）、响应数据映射（currentData）、异常处理（bizRespStatus）
  - `constData.groovy`：只定义常量（环境参数、埋点配置、业务常量）
  - `logics.groovy`：只定义生命周期回调（**preview / update / submit / check** 等对应的 `onResponse` / `onSuccess` / `onFail` / `onCancel` / `onEngineFail`）和事件处理
- **反例**：在 struct.groovy 中直接写复杂的数据转换逻辑，应提取到 constData.groovy 中

---

## 二、Groovy DSL 编码规范

### D03 使用 def 声明变量
- **等级**：高
- **描述**：DUO Groovy 中使用 `def` 声明变量，不要使用 `var` 或类型声明
- **正例**（来自真实项目）：
```groovy
def query = PAGE_QUERY
def fingerprint = COMMON_PARAMS.fingerprint?.fingerprint ?: query.fingerprint ?: ''
def promoProps = NODE?.PromodeskModule?.props ?: [:]
def quantityStepperProps = NODE?.QuantityStepperModule?.props ?: [:]
```
- **反例**：`var userName = 'test'`、`String userName = 'test'`
- **原因**：DUO 的 groovy 版本为 2.4.17，`var` 需要 Java 10+，类型声明在 DUO 前端解析中可能不支持

### D04 使用安全导航操作符
- **等级**：高
- **描述**：访问可能为 null 的对象属性时，必须使用安全导航操作符 `?.`，且需要链式使用
- **正例**（来自真实项目）：
```groovy
// 多层安全导航
def chosenDateInfo = timeSelectProps?.chosenDateInfo ?: [:]
def tradeChosenDateInfo = tradeTimeSelectProps?.selectedData ?: null
def cardInfo = cardProps?.cardInfoVO ?: [:]

// NODE 访问必须使用 ?.
def promoProps = NODE?.PromodeskModule?.props ?: [:]
def seatTypeModuleProps = NODE?.SeatType?.props ?: [:]

// DATA_SOURCE 访问
DATA_SOURCE.data?.promoDeskVO ?: [:]
DATA_SOURCE.data?.poolInfoData?.backRoomType ?: 0
DATA_SOURCE.data?.douHuABTestDTO?.douHuTestList
```
- **反例**：`DATA_SOURCE.data.extraData.submitButtonText`（data 为 null 时会报错）
- **特别注意**：`a?.b.c` 当 a 为 null 时 groovy 会报错，应写成 `a?.b?.c`

### D05 使用兜底运算符
- **等级**：高
- **描述**：对可能为空的值使用 `?:` 兜底运算符提供默认值
- **正例**（来自真实项目）：
```groovy
// 多级兜底
def fingerprint = COMMON_PARAMS.fingerprint?.fingerprint ?: query.fingerprint ?: ''
def productId = query?.productId ?: query?.productid  // 兼容大小写
def purchaseDate = chosenDateInfo?.purchaseDate ?: query?.purchaseDate ?: query?.purchasedate

// Map 兜底为空 Map
def promoProps = NODE?.PromodeskModule?.props ?: [:]
def cardProps = NODE?.VipCardModule?.props ?: [:]

// 数值兜底
def quantity = PAYLOAD?.QUANTITY ?: quantityStepperModuleProps?.quantity ?: 1
def backRoomType = DATA_SOURCE.data?.poolInfoData?.backRoomType ?: 0
```
- **注意**：Groovy 的 `?:` 等同于 `a ? a : b`，遵循 Groovy Truth 规则（空字符串、空列表、0 都视为 false）

### D06 禁止使用不支持的语法
- **等级**：高
- **描述**：DUO Groovy 有语法限制，以下语法不支持或不建议使用
- **禁止使用**：
  - `===` / `!==`（需要 Groovy 3.0.0，后端不支持）
  - `?=` 兜底赋值（需要 Groovy 3.0.0）
  - `a?[b]` 安全下标（需要 Groovy 3.0.0，使用 `a?.getAt(b)` 替代）
  - `**` 指数操作符（groovy 和 js 行为不一致）
  - 正则表达式操作符 `=~`、`==~`
  - `try-catch-finally`
  - `while`、`do-while` 循环
  - `switch-case`
  - 位操作符
  - 字符串插值 `"${expr}"`（会绑定上下文，不建议使用）
- **安全下标正例**：
```groovy
// 使用 getAt 替代安全下标
def tempObj = PREV_DATA?.skuMMFirstInflateCouponMap?.getAt(couponMapKey)
```

### D07 注意 Groovy 与 JavaScript 的差异
- **等级**：高
- **描述**：Groovy 和 JavaScript 在语义上有关键差异，审查时需特别注意
- **关键差异**：
  - `==` 在 Groovy 中使用 `equals` 比较（深度相等），在 JS 中是宽松比较
  - Groovy Truth 与 JS Falsy 不完全对齐：Groovy 中空列表 `[]`、空 Map `[:]` 视为 false，JS 中不是
  - `&&`、`||` 在 Groovy 中结果一定是 boolean，JS 中返回操作数本身
  - 不要在二元操作符前换行：`1\n+2` 在 JS 中是 `1+2`，在 Groovy 中是两行代码 `1; +2`
- **真实项目中的正确用法**：
```groovy
// 使用 !! 转换为 boolean
condition {{ !!DATA_SOURCE.data?.douHuABTestDTO?.douHuTestList }}

// 使用三元运算符而非 ||
def source = CONST?.isBookAfterGroup ? 'orderdetail' : lx?.page_source
```

### D08 闭包语法规范
- **等级**：中
- **描述**：Groovy 闭包使用 `{ params -> body }` 语法
- **正例**（来自真实项目）：
```groovy
// collect 闭包
def newAbTest = abTest?.collect { item ->
    item?.moduleAbInfo4Front
}

// find 闭包
def selectedcouponPackage = mmPreviewData?.couponPackageList?.find { it.selectStatus == true }

// count 闭包
promosnapShot?.promoSnapshotList?.count { it -> it.promoType == cardInfo?.cardOperatePromoDetailType }
```

### D09 Map 和 List 字面量规范
- **等级**：中
- **描述**：Groovy 中 Map 使用 `[key: value]` 语法，List 使用 `[item1, item2]` 语法
- **正例**（来自真实项目）：
```groovy
// Map 字面量
def dateInfo = [
  purchaseDate: chosenDateInfo?.purchaseDate ?: query?.purchaseDate,
  arriveTime: chosenDateInfo?.arriveTime ?: query?.arriveTime,
  leaveTime: chosenDateInfo?.leaveTime ?: query?.leaveTime,
]

// Spread 操作符合并 Map
def result = [
  *:CONST.envParam,
  *:CONST.baseParam,
  cx: fingerprint,
  productId: query?.productId ?: query?.productid,
]

// 条件性 spread
def promoExtMapObj = [
  *: query.scene ? [offlinechannel: query.scene] : [:],
  *: query.eventpromochannel ? [eventpromochannel: query.eventpromochannel] : [:],
  *: CONST?.trafficFlag ? [trafficFlag: CONST.trafficFlag] : [:],
]
```
- **反例**：
```groovy
def config = [return: 'test'] // 关键词不可作为 map 属性名
```

### D10 避免复杂表达式
- **等级**：中
- **描述**：DUO 表达式应保持简洁，复杂逻辑应拆分到 constData 或 logics 中
- **正例**：在 constData.groovy 中定义复杂计算，在组件 props 中引用 `CONST.xxx`
- **反例**：在组件 props 表达式中编写超过 3 行的复杂逻辑
- **真实项目中的良好实践**：
```groovy
// constData.groovy 中定义常量（顶层关键字以当前仓库为准；部分文档/项目写作 constant { }，语义一致）
constData {
  object('envParam') {{ [platform: COMMON_PARAMS?.platform ?: 'other'] }}
  object('baseParam') {{ [shopId: PAGE_QUERY?.shopid, spuId: PAGE_QUERY?.spuid] }}
  object('lx') {{ [channel: 'gc_booking', cid: 'c_gc_xxx'] }}
}

// struct.groovy 中引用常量
props {
  string('channelName') {{ CONST.lx.channel }}
  string('cid') {{ CONST.lx.cid }}
}
```

---

## 三、struct.groovy 页面结构规范

### D11 组件节点声明规范
- **等级**：高
- **描述**：组件节点使用 `node('组件名', '节点ID')` 声明，必须包含 `label` 描述
- **正例**（来自真实项目）：
```groovy
node('BookingTimeselectYoozMoudle', '100') {
  label '时间选择'
  props {
    object('dateInfo') {{ DATA_SOURCE.data?.dateInfo ?: [:] }}
    object('sessionInfo') {{ DATA_SOURCE.data?.sessionInfo ?: [:] }}
  }
}

node('QuantityStepperModule', '3') {
  label '人数选择'
  props {
    number('quantity') {{ DATA_SOURCE.data?.quantity ?: 1 }}
    object('quantityInfo') {{ DATA_SOURCE.data?.quantityInfo ?: [:] }}
  }
}
```
- **关注点**：
  - 节点 ID 必须唯一
  - label 应清晰描述组件业务含义
  - 组件名应与 componentsMap.json 中的映射一致
  - 协议中的 **`nodeType`**（如 `NORMAL_MODULE`、`HANDLER_MODULE`、`LIST_CONTAINER`）须与物料/协议一致；**`LIST_CONTAINER` + `xFor` / `FOR`** 的约定见 **D14**

### D12 组件 Props 类型声明
- **等级**：高
- **描述**：props 中的类型声明必须与实际数据类型匹配
- **支持的类型**：`string`、`number`、`bool`、`object`、`array`
- **正例**（来自真实项目）：
```groovy
props {
  // 字符串类型
  string('channelName') {{ CONST.lx.channel }}
  string('cid') {{ CONST.lx.cid }}
  
  // 数值类型
  number('quantity') {{ DATA_SOURCE.data?.quantity ?: 1 }}
  
  // 布尔类型
  bool('isPreview') {{ COMMON_PARAMS?.isPreview }}
  // 以下为示例：isError 语义须与本数据源约定的成功码一致（常见 code==0 或 code==200，禁止照搬）
  bool('isError') {{ DATA_SOURCE?.code != 200 }}
  
  // 对象类型
  object('dateInfo') {{ DATA_SOURCE.data?.dateInfo ?: [:] }}
  object('cardInfo') {{ DATA_SOURCE.data?.cardInfoVO ?: [:] }}
  
  // 数组 / 列表（可用 array，或与项目约定一致时用 object 包 List）
  array('promoList') {{ DATA_SOURCE.data?.promoInfoList ?: [] }}
}
```
- **反例**：用 `string` 声明一个对象类型的值

### D13 渲染条件表达式
- **等级**：高
- **描述**：组件的渲染条件使用 `condition` 或 `visible` 控制；struct 中协议字段 **`xIf` / `displayRule`** 同理，表达式须能稳定得到 boolean（避免把非 boolean 当条件导致误剪枝）
- **正例**（来自真实项目）：
```groovy
on('preview.onSuccess') {
  callMethod('MeishiCommonEventLx1', 'lxTrackModuleView')
  condition {{ !!DATA_SOURCE.data?.douHuABTestDTO?.douHuTestList }}
  props { ... }
}
```
- **关注点**：条件表达式是否覆盖所有场景、是否存在永远为 true/false 的条件；**字符串/空串与 Groovy Truth** 是否与产品预期一致

### D14 组件嵌套、列表与 xFor / FOR
- **等级**：中
- **描述**：struct 侧**树形结构**与**列表渲染**两类关注点；后者与团队演进策略相关。

**嵌套层级**

- struct.groovy 中的组件树**不宜过深**，建议不超过 **5 层**嵌套，以免影响性能与可读性。

**`xFor` / `FOR` 与 `LIST_CONTAINER`（不推荐）**

- **团队约定**：**不推荐**在协议里**新引入或扩大**使用 **`xFor` / `FOR`** 以及依赖其的 **`LIST_CONTAINER`** 循环展开（协议与旧版文档中可能仍有示例，属历史能力）。
- **推荐替代**：**新需求**优先使用**单个 proCode 物料**，通过 **数组/列表类 props** 在组件内渲染列表，便于维护与多端一致。
- **存量与 CR**：仅维护存量时若仍含 `xFor`/`FOR`，改动须评估副作用；**若本次 diff 新增或明显依赖上述能力**，须在审查说明中交代**业务必要性**与**维护/性能**风险。

### D15 组件节点命名规范
- **等级**：高
- **描述**：组件节点名称应清晰表达业务含义，使用 PascalCase
- **正例**：`BookingTimeSelectModule`、`QuantityStepperModule`、`PromodeskModule`、`OrderPayModule`
- **反例**：`comp1`、`div2`、`xxx`

---

## 四、dataSourceMap.groovy 数据源规范

### D16 数据源结构完整性
- **等级**：高
- **描述**：dataSourceMap.groovy 必须包含完整的数据源配置结构
- **标准结构**（来自真实项目）：
```groovy
dataSource {
  dataSourceId '16'          // 数据源 ID

  requestProps {             // 请求入参定义
    object('preOrderRequest') {{ ... }}    // preview 接口入参
    object('submitOrderRequest') {{ ... }} // submit 接口入参
  }

  currentData {              // 响应数据映射（存储到 PREV_DATA）
    object('preDataPromoDeskVO') {{ DATA_SOURCE.data?.promoDeskVO ?: [:] }}
    number('backRoomType') {{ DATA_SOURCE.data?.poolInfoData?.backRoomType ?: 0 }}
    string('shopIdEncrypt') {{ DATA_SOURCE.data?.shopIdStrEncrypt ?: DATA_SOURCE.data?.shopIdEncrypt }}
  }

  bizRespStatus {            // preview/update 异常处理（成功码须与接口约定一致，见 D20）
    bool('isError') {{ DATA_SOURCE?.code != 200 }}
    string('errorMsg') {{ DATA_SOURCE?.msg }}
    object('extra') {{ ... }}
    errorToast true
    errorNoReturnStruct true
  }

  submitBizRespStatus {      // submit 异常处理
    bool('isError') {{ DATA_SOURCE?.code != 200 }}
    string('errorMsg') {{ DATA_SOURCE?.msg }}
    object('extra') {{ ... }}
    errorToast true
  }
}
```

### D17 requestProps 入参完整性
- **等级**：高
- **描述**：preview/update/submit 三个接口的入参模型需完整配置
- **关键审查点**（来自真实项目）：
```groovy
object('preOrderRequest') {{
  def query = PAGE_QUERY
  // 1. 必须包含环境参数
  [
    *:CONST.envParam,
    *:CONST.baseParam,
    
    // 2. 必须包含业务核心参数
    productId: query?.productId ?: query?.productid,
    quantity: PAYLOAD?.QUANTITY ?: quantityStepperModuleProps?.quantity ?: 1,
    
    // 3. 时间参数需完整
    *: dateInfo,
    
    // 4. 优惠台参数需正确序列化
    promoDeskJson: DF.toJsonString([...]),
    
    // 5. 算价 Diff 参数
    stage: COMMON_PARAMS?.DIFF_STAGE ? 1 : 2,
    diffJson: COMMON_PARAMS?.DIFF_JSON ?: null,
    traceId: COMMON_PARAMS?.MASTER_TRACEID,
  ]
}}
```
- **关注点**：
  - 是否遗漏必要的入参字段
  - 入参类型是否与后端约定一致
  - 是否正确使用 `DF.toJsonString()` 序列化复杂对象
  - 是否兼容了参数名大小写（如 `productId` / `productid`）

### D18 PAYLOAD 数据处理
- **等级**：高
- **描述**：update 时通过 PAYLOAD 传递用户操作数据，需正确处理；并满足 **D00** 中对 preview/submit 的边界（preview 勿单独依赖 PAYLOAD；submit 累计态走 PREV_DATA）
- **正例**（来自真实项目）：
```groovy
// 根据 PAYLOAD 判断操作来源
def operatorModule = PAYLOAD?.operatorModule

// PAYLOAD 更新时间信息
def payloadDate = PAYLOAD?.dateInfo
if (payloadDate) {
  dateInfo = [
    purchaseDate: payloadDate.purchaseDate,
    arriveTime: payloadDate?.arriveTime,
    leaveTime: payloadDate?.leaveTime,
    productItemId: payloadDate?.skuId,
  ]
}

// 区分场景类型
sceneType: COMMON_PARAMS?.isUpdate ? 1 : 0,
```
- **关注点**：
  - PAYLOAD 字段是否有安全导航
  - 是否正确区分 preview 和 update 场景
  - PAYLOAD 数据优先级是否正确（PAYLOAD > 组件 props > 默认值）

### D19 currentData 响应映射
- **等级**：高
- **描述**：currentData 将接口响应数据存储到 PREV_DATA，供后续 update/submit 使用
- **正例**（来自真实项目）：
```groovy
currentData {
  object('preDataPromoDeskVO') {{ DATA_SOURCE.data?.promoDeskVO ?: [:] }}
  number('backRoomType') {{ DATA_SOURCE.data?.poolInfoData?.backRoomType ?: 0 }}
  string('shopIdEncrypt') {{ DATA_SOURCE.data?.shopIdStrEncrypt ?: DATA_SOURCE.data?.shopIdEncrypt }}
  string('preOrderExtParams') {{ DATA_SOURCE.data?.preOrderExtParams ?: '' }}
  object('skuMMFirstInflateCouponMap') {{ DATA_SOURCE.data?.skuMMFirstInflateCouponMap ?: [:] }}
  string('promotionPosition') {{ DATA_SOURCE.data?.promotionPosition }}
  number('purchaseDate') {{ DATA_SOURCE.data?.purchaseDate }}
  number('arriveTime') {{ DATA_SOURCE.data?.arriveDate }}
  number('leaveTime') {{ DATA_SOURCE.data?.leaveDate }}
}
```
- **关注点**：
  - 类型声明是否与实际数据类型匹配
  - 是否提供了合理的默认值
  - 字段路径是否正确（注意 `arriveDate` vs `arriveTime` 等命名差异）

### D20 bizRespStatus 异常处理
- **等级**：高
- **描述**：异常处理配置必须完整，包含错误判断、错误信息、上报信息
- **成功码约定**：`isError` 必须与**当前数据源接口**约定一致。实务中常见 **`code == 0`** 或 **`code == 200`**，禁止在未读接口契约时照搬其他页面的魔数。
- **类型陷阱**：若 `code` 可能为**字符串**（如 `"0"`），直接与数字比较会误判；宜使用 `DF.toNumber(DATA_SOURCE?.code) != 0` 或与 **`'0'` / `'200'`** 等**显式字符串比较**（详见团队 **数据源 / bizRespStatus** 排障说明）。
- **正例**（来自真实项目）：
```groovy
bizRespStatus {
  bool('isError') {{ DATA_SOURCE?.code != 200 }}
  string('errorMsg') {{ DATA_SOURCE?.msg }}
  object('extra') {{
    def cusInfo = CONST.raptorCustomInfo
    
    if (DATA_SOURCE?.code != 200 || DATA_SOURCE?.data == null) {
      return [
        reportMsg: (cusInfo.pageScene ?: '') + (COMMON_PARAMS.isUpdate ? ' Update-' : ' Preview-') + DATA_SOURCE?.code + '：' + (DATA_SOURCE?.msg ?: DATA_SOURCE?.message ?: DATA_SOURCE?.userMessage ?: ''),
        reportTags: [
          *: cusInfo,
          code: DATA_SOURCE?.code,
          category: 'ajaxError',
          level: 'error'
        ]
      ]
    }
    return [reportTags: cusInfo]
  }}
  errorToast true
  errorNoReturnStruct true
}
```
- **关注点**：
  - `isError` 判断条件是否正确，且与接口 **code 类型与成功值**一致
  - 错误信息是否包含多种可能的字段（msg / message / userMessage）
  - 是否配置了 Raptor 上报信息
  - `errorToast` 是否开启
  - preview 场景是否配置了 `errorNoReturnStruct true`（异常时不返回结构体）
  - 若存在 **check** 数据源，是否按需配置 **`checkBizRespStatus`**（与 `submitBizRespStatus` 分工一致）

### D21 submit 入参与 preview 入参的差异
- **等级**：高
- **描述**：submit 入参通常比 preview 入参多出支付、用户信息等字段，需确保完整
- **关注点**（来自真实项目）：
```groovy
object('submitOrderRequest') {{
  [
    // submit 特有字段
    encryptedPromoString: promoProps?.prePromoDeskVO?.promoCipher ?: '',
    promoJson: promoProps?.prePromoDeskVO?.promoJson ?: '',
    mobile: leadsProps?.userMobile,
    bookName: bookInfoProps?.name ?: '',
    gender: bookInfoProps?.gender ?: 0,
    orderRemark: NODE?.BookingRemarkModule?.props?.remarkContent ?: '',
    oneClickPayStatus: (payTypeProps?.payTypeInfo?.productScene == 2) ? 1 : 0,
    
    // 小程序参数
    *:miniProgramParams,
    
    // UTM 信息
    *:CONST.utmInfo,
  ]
}}
```

---

## 五、constData.groovy 常量定义规范

### D22 常量分类组织
- **等级**：中
- **描述**：constData.groovy 中的常量应按业务含义分类组织
- **推荐分类**（来自真实项目）：
```groovy
constData {
  // 1. 环境参数
  object('envParam') {{ [platform: COMMON_PARAMS?.platform ?: 'other'] }}
  
  // 2. 基础业务参数
  object('baseParam') {{ [shopId: PAGE_QUERY?.shopid, spuId: PAGE_QUERY?.spuid] }}
  
  // 3. 客户端类型
  string('clientType') {{ 
    def systemInfo = COMMON_PARAMS.systemInfo ?: [:]
    systemInfo?.IS_DP ? 'dp' : (systemInfo?.IS_MT ? 'mt' : 'other')
  }}
  
  // 4. 埋点配置
  object('lx') {{
    def query = PAGE_QUERY
    [
      channel: 'gc_booking',
      cid: 'c_gc_xxx',
      poi_id: query?.shopid,
      product_id: query?.productid,
    ]
  }}
  
  // 5. 业务模式常量
  object('bookingMode') {{ [PIN: 1, BAO: 2] }}
  
  // 6. Raptor 上报配置
  object('raptorCustomInfo') {{ [pageScene: 'booking', ...] }}
  
  // 7. 推广位置
  object('promotionPosition') {{ [submitPage: 'submit_page'] }}
}
```

### D23 常量引用安全性
- **等级**：高
- **描述**：引用 `COMMON_PARAMS`、`PAGE_QUERY`、`SYSTEM_INFO` 等全局变量时必须做空值保护
- **正例**：
```groovy
def systemInfo = COMMON_PARAMS.systemInfo ?: [:]
def envInWeb = systemInfo?.envInWeb ?: [:]
def query = PAGE_QUERY  // PAGE_QUERY 本身不会为 null，但其属性可能为 null
```
- **反例**：
```groovy
def platform = COMMON_PARAMS.systemInfo.platform  // systemInfo 可能为 null
```

### D24 避免在 constData 中引用动态数据
- **等级**：高
- **描述**：`constData.groovy` 在 **NODE_DATA 阶段早期**计算并注入 **CONST**（早于逐节点 props 中对 `DATA_SOURCE` 等的依赖），**不参与**数据源 HTTP 往返；不得引用随请求变化的 **`DATA_SOURCE`、`NODE`、`PAYLOAD`、`PREV_DATA`**（与后端阶段约定一致）。
- **可引用**：`PAGE_QUERY`、`COMMON_PARAMS`、`SYSTEM_INFO`
- **不可引用**：`DATA_SOURCE`、`NODE`、`PAYLOAD`、`PREV_DATA`
- **协议 JSON 注意**：搭建导出的 **JSON** 中若将 `constData` 内联为表达式片段，其求值时机与 **`.groovy` 源文件**不完全相同；若线上协议中 `constData` 表达式引用 `DATA_SOURCE` 等且运行正常，**勿仅凭本条机械判错**，应结合引擎阶段与接口约定判断；**Groovy 源文件**仍应遵守上表。

---

## 六、logics.groovy 生命周期与事件规范

### D25 生命周期回调结构
- **等级**：高
- **描述**：logics.groovy 使用 `node` + `on` 结构定义生命周期回调
- **标准结构**（来自真实项目）：
```groovy
node('MeishiCommonDuoLifecycle1', '13') {
  label '内置物料-页面生命周期'
  
  // preview 响应回调 - 用于埋点
  on('preview.onResponse') {
    callMethod('MeishiCommonEventLx1', 'lxTrackMPT')
    props {
      string('channelName') {{ CONST.lx.channel }}
      string('cid') {{ CONST.lx.cid }}
      object('param') {{
        def lx = CONST.lx
        [
          poi_id: lx.poi_id,
          cat_id: lx.cat_id,
          custom: [
            product_id: lx.product_id,
            sku_id: lx.sku_id,
          ]
        ]
      }}
    }
  }
  
  // preview 成功回调 - 用于 AB 实验上报
  on('preview.onSuccess') {
    callMethod('MeishiCommonEventLx1', 'lxTrackModuleView')
    condition {{ !!DATA_SOURCE.data?.douHuABTestDTO?.douHuTestList }}
    props { ... }
  }
}
```
- **支持的生命周期事件**（`{生命周期}.{事件}`；与 duo-engine 约定一致）：
  - `preview` / `update` / `submit` / `check` 均可有：`onResponse`、`onSuccess`、`onFail`、`onCancel`、`onEngineFail`（**引擎/网络层失败**等与业务 `onFail` 区分）
  - 示例：`preview.onResponse`、`update.onSuccess`、`submit.onFail`、`preview.onEngineFail`、`check.onSuccess` 等

### D26 callMethod 调用规范
- **等级**：高
- **描述**：`callMethod` 用于在生命周期回调中调用其他组件的方法
- **正例**（来自真实项目）：
```groovy
on('preview.onResponse') {
  callMethod('MeishiCommonEventLx1', 'lxTrackMPT')  // 调用埋点组件的方法
  props { ... }  // 传递参数
}
```
- **关注点**：
  - 被调用的组件名必须在 logics.groovy 中有对应的 `node` 声明
  - 方法名必须是目标组件支持的方法

### D27 辅助节点声明
- **等级**：中
- **描述**：logics.groovy 中需要声明被 callMethod 引用的辅助组件节点
- **正例**（来自真实项目）：
```groovy
// 埋点组件
node('MeishiCommonEventLx1', '16') {
  label '数据埋点'
}

// 导航 API
node('MeishiCommonEventNav1', '90') {
  label '导航API'
}

// Raptor 上报
node('MeishiUtilAutoReporterInstance1', '91') {
  label 'raptor上报'
}
```
- **关注点**：节点 ID 不能与 struct.groovy 中的节点 ID 冲突

### D28 condition 条件使用
- **等级**：高
- **描述**：生命周期回调中的 `condition` 用于控制是否执行该回调
- **正例**：
```groovy
on('preview.onSuccess') {
  callMethod('MeishiCommonEventLx1', 'lxTrackModuleView')
  condition {{ !!DATA_SOURCE.data?.douHuABTestDTO?.douHuTestList }}
  props { ... }
}
```
- **关注点**：condition 表达式必须返回 boolean 值，使用 `!!` 确保转换

---

## 七、性能与安全规范

### D29 避免不必要的 update 调用
- **等级**：高
- **描述**：update 会触发全页面刷新（重新请求接口），应避免频繁或不必要的 update 调用
- **关注点**：
  - 是否在循环中触发 update
  - 是否可以使用 debounce 减少调用频率
  - 纯展示变更是否可以通过前端状态管理而非 update 实现

### D30 requestProps 中避免冗余计算
- **等级**：中
- **描述**：requestProps 中的表达式在每次 preview/update 时都会执行，应避免重复计算
- **正例**：将复杂计算提取为变量
```groovy
object('preOrderRequest') {{
  def query = PAGE_QUERY
  def promoProps = NODE?.PromodeskModule?.props ?: [:]
  // 提取复杂计算
  def isBao = CONST?.hasTopTabs ? userChoiceIsBaoMode : (PREV_DATA?.backRoomType == 2)
  
  [
    bookAll: isBao,
    // ...
  ]
}}
```
- **反例**：在多个字段中重复计算相同的值

### D31 DF.toJsonString 使用规范
- **等级**：高
- **描述**：复杂对象传给后端时需使用 `DF.toJsonString()` 序列化
- **正例**（来自真实项目）：
```groovy
promoDeskJson: DF.toJsonString([
  *:promoExtMap,
  *: [
    *: finallyPromosnapShot,
    operatorPromoType: operatorPromoType,
  ],
  otherUserOperateType: otherUserOperateType
]),
bizdata: DF.toJsonString([
  *: (query?.promotionchannel ? [promotionChannel: query?.promotionchannel] : [:])
]),
```
- **关注点**：确保传给 `DF.toJsonString` 的是 Map 或 List，不是 null

### D32 敏感数据处理
- **等级**：高
- **描述**：DUO 页面中涉及的用户敏感数据（手机号、身份证等）必须脱敏展示
- **关注点**：Groovy 表达式中是否对敏感字段做了掩码处理

### D33 预请求数据合理使用
- **等级**：中
- **描述**：页面配置中勾选的系统环境参数（位置、用户信息等）会打包到 bundle 中，不需要的信息不应勾选
- **关注点**：是否勾选了不必要的系统参数，影响秒开性能

---

## 八、Max 源码物料规范

### D34 物料 Props 类型定义
- **等级**：高
- **描述**：Max 源码物料必须完整定义 Props 类型，包括 `__duo__` 透传参数
- **正例**：
```typescript
interface IProps {
  title?: string;
  onPress?: () => void;
  __duo__?: any; // DUO 框架透传参数
}
```

### D35 物料生命周期适配
- **等级**：高
- **描述**：源码物料需要适配 DUO 的 preview/update/submit/check 生命周期；触发展开时应使用引擎注入的 **`props.__duo__.emit('update' | 'submit' | …)`**，或在团队统一封装包（如 `@meishi/common-duo-lifecycle`）中转发到 `emit`。
- **正例**：
```typescript
// 推荐：直接使用引擎 API（具体类型以 @meishi/duo-protocol 为准）
props.__duo__?.emit('update', {
  payload: { selectedId: id },
  debounceDelay: 300,
});

// 或团队封装的 lifecycle 包（若页面已依赖）
import { update } from '@meishi/common-duo-lifecycle';
update({ __duo__: props.__duo__, PAYLOAD: { selectedId: id } });
```
- **关注点**：是否经 `__duo__` 触发请求而非绕过引擎句柄私自请求主接口；防抖/锁是否与业务匹配

### D36 物料样式规范
- **等级**：中
- **描述**：物料样式应使用 Max 标准的样式方案，支持多端适配（MRN/Web）
- **关注点**：是否使用了仅在某一端生效的样式属性、是否做了多端兼容

### D37 物料复用性
- **等级**：中
- **描述**：物料应设计为可复用的，通过 props 接口灵活配置，避免硬编码业务逻辑
- **关注点**：是否将业务特定逻辑硬编码在物料内部、props 接口是否足够灵活；**列表类 UI** 是否优先在**物料内**用数组 props 渲染（与 **D14** 中「不推荐 `xFor`/`FOR`」方向一致）

### D38 物料描述协议完整性
- **等级**：高
- **描述**：物料的 `description.json`（物料描述协议）中 props/slots/events 必须与实现一致；推荐使用 **`@meishi/duo-cli` 的 `duo doc-gen`**，并用 JSDoc `@label` 等保证搭建面板可读（详见 **DUO 物料发布与描述协议** 的团队文档或 CLI 说明）。
- **关注点**：props 定义是否与实际组件入参一致、**emit/on** 与 `callMethod` 目标方法是否齐全、**buildIn**（static/pageContainer）是否在协议中显式声明

### D39 组件依赖版本管理
- **等级**：高
- **描述**：dependencies.json 中的组件依赖版本应明确指定，避免使用 `latest` 或过于宽泛的版本范围
- **关注点**：依赖版本是否锁定、是否存在已知安全漏洞的版本

---

## 九、平台踩坑与跨端差异

### D40 NODE 使用边界
- **等级**：高
- **描述**：`NODE.<nodeName>.props` 存在使用限制，违反会导致取值不一致或为空。
- **规则**：
  - **禁止**在组件 A 的入参中使用组件 B 的 `NODE.B.props`（应使用 `PREV_DATA` 或 `DATA_SOURCE.data` 中转）
  - NODE 只能引用 struct 中**排在当前节点之前**的已计算节点
  - A 组件双向绑定更新 props 后，若没有立即触发 update，B 组件入参中**无法获取到** A 组件的最新 NODE.props
  - NODE 用于给**入参**使用，**出参不可以使用** NODE
- **正例**：
```groovy
// 通过 PREV_DATA 跨节点传递数据
currentData {
  object('timeSelectData') {{ NODE?.TimeSelectModule?.props?.selectedData ?: [:] }}
}
// 其他组件从 PREV_DATA 读取
object('dateInfo') {{ PREV_DATA?.timeSelectData ?: [:] }}
```
- **反例**：
```groovy
// 在 B 组件入参中直接引用 A 组件的 NODE（可能取不到最新值）
object('dateInfo') {{ NODE?.TimeSelectModule?.props?.selectedData }}
```

### D41 设备唯一标识（uuid）跨端取值差异
- **等级**：高
- **描述**：DUO 公参 `uuid` 在不同端取值不一致。美团侧为 mtuuid，点评侧可能为 mtuuid/dpid/空。使用 PN 预请求 + 同步桥时，preview 与 update 中 uuid 可能不一致。
- **规则**：
  - **推荐使用 `uuidV2` 字段**：美团 App = mtuuid，点评 App = dpid，小程序 = openId
  - 需要 mtuuid 时使用 `mtuuid` 字段（点评/小程序可能为空）
  - 禁止直接使用 `uuid` 字段作为设备唯一标识传给后端（取值不确定）
  - 前后端共识：美团用 uuid，点评用 dpId，小程序用 openId
- **正例**：
```groovy
def deviceId = COMMON_PARAMS?.uuidV2 ?: ''
```
- **反例**：
```groovy
def deviceId = COMMON_PARAMS?.uuid  // 点评侧取值不定
```

### D42 COMMON_PARAMS 布尔字段安卓预请求为 string
- **等级**：高
- **描述**：`COMMON_PARAMS.systemInfo?.isMRN` 等布尔字段，在安卓端预请求解析后可能变为字符串 `"true"`/`"false"`，直接判断会导致逻辑错误。
- **规则**：
  - 使用 `COMMON_PARAMS.systemInfo` 中的布尔字段时，统一使用 `!!` 双重否定转换
  - 不依赖 `=== true` 或 `== true` 判断
- **正例**：
```groovy
def isMRN = !!COMMON_PARAMS.systemInfo?.isMRN
```
- **反例**：
```groovy
def isMRN = COMMON_PARAMS.systemInfo?.isMRN == true  // 安卓预请求下为 "true"（字符串），判断失败
```

### D43 依赖升级导致多版本原生组件冲突
- **等级**：高
- **描述**：DUO 项目依赖升级后可能导致 `node_modules` 中安装多个版本的原生组件（如 `@mrn/mrn-text`），多处调用 `requireNativeComponent` 注册同名 native 模块导致启动失败。
- **规则**：
  - 升级依赖后，检查 lockfile 是否出现原生组件的多版本
  - 出现多版本时，在 `package.json` 中通过 `resolutions`（yarn）或 `overrides`（npm）锁定单一版本
  - 注意清理 `.duo-tmp/preview-*/node_modules`，否则旧缓存可能仍存在多版本
- **正例**：
```json
{
  "resolutions": {
    "@mrn/mrn-text": "x.y.z"
  }
}
```

### D44 Groovy 字符串转数字必须判空
- **等级**：中
- **描述**：Groovy 中对 null 或非数字字符串调用 `toInteger()` / `Integer.parseInt()` 会抛异常，导致页面报错。
- **规则**：
  - 字符串转数字前必须判空
  - 非数字字符串场景需额外兜底
- **正例**：
```groovy
def countStr = DATA_SOURCE.data?.count
def count = countStr ? countStr.toInteger() : 0
```
- **反例**：
```groovy
def count = DATA_SOURCE.data?.count.toInteger()  // count 为 null 时报错
```
