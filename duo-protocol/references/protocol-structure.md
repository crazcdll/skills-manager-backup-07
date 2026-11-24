# DUO 页面协议完整结构指南

## 一、协议源文件位置

DUO 页面协议的源文件在仓库 **`protocol/`** 目录下，为**拆分文件（`.groovy` 与 `.json` 混合）**：

```
protocol/
├── struct.groovy          # 视图树（页面长什么样）★ 最常改
├── logics.groovy          # 逻辑（生命周期、事件、updateBy）
├── dataSourceMap.groovy   # 数据源定义
├── constData.groovy       # 页面常量（constant {}）
├── pageBuildConfig.json   # 编译静态配置（路由、pageQuery、公共参数）—— json 非 groovy！
├── dependencies.json      # 依赖物料（数组）—— json
└── componentsMap.json     # 物料映射（key=物料ID）—— json
```

> **4 个 `.groovy` + 3 个 `.json`，都要理解怎么改。** duo-builder 通过 `duo-builder/duo.config.js` + `duo-version.json`（pageId/protocolId/protocolVersion）关联具体协议。

> ⚠️ 仓库 README 提到的"出码后代码"指 `src/` 编译产物，与 `protocol/` 源文件不同，别混淆。
> 参考：到餐 `nibfe/duo-food-order-submit`（pageId=12413，protocolId=0401）、酒店 `nibfe/duo-hotel-order-submit`（pageId=12450，protocolId=0238）。两个仓库该目录文件结构一致。

## 二、顶层字段（protocol.json 维度）

DUO 页面协议（Page Protocol）整体描述页面的搭建配置：

| 字段 | 类型 | 说明 |
|------|------|------|
| `pageId` | string | 页面全局唯一 id（如到餐 12413、酒店 12450） |
| `pageProtocolId` | string | 协议 id（如酒店 0238、到餐 0401） |
| `pageProtocolVersion` | string | 版本号（稳定版 `0003` / 快照版 `0003-SNAPSHOT-0001`） |
| `pageBuildConfig` | - | 编译静态配置 |
| `dataSourceMap` | - | 数据源定义 |
| `constData` | - | 页面常量 |
| `struct` | PageNode[] | 视图树 |
| `logics` | PageNode[] | 逻辑列表 |
| `dependencies` | PageDependency[] | 依赖物料 npm（name/version/type） |
| `componentsMap` | { [materialId]: MaterialResourceConfig } | 物料接口配置映射 |

## 三、struct 节点真实语法

```groovy
node('BottomBar', '798') {
  label '酒店提单-底部提单栏'      // 中文描述
  xIf {{ COMMON_PARAMS.systemInfo.isMRN }}   // 条件渲染
  props {                        // ① 类型化字段声明（props 内只能放字段声明）
    bool('isOversea') {{ CONST.baseInfo?.isOversea }}
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    string('currencySymbol') {{ '¥' }}
    object('commonParams') {{ [ fingerprint: COMMON_PARAMS.fingerprint.fingerprint ] }}
    array('priceItemList') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
  }                              // ← props 必须在这里闭合
  propConfig('totalPayAmount') {  // ② 字段配置：与 props 同级，禁止写进 props
    updateBy 'onChangePrice'
    isRequestArg true
    lock false
  }
  on('onKeyBoardShow') {          // ③ 事件
    callMethod('GuestCard', 'onKeyBoardShow')
  }
}
```

### 节点级声明（🔴 块层级铁律）

`node` 内所有声明**平级、互不嵌套**，共 13 种：

| 声明 | 写法 | 落 JSON | 说明 |
|------|------|---------|------|
| `label` | `label '底部提单栏'` | `resource.label` | 中文描述 |
| `nodeId` | `nodeId 'existing-id'` | `nodeId` | 可选的后端存储标识，沿用现有协议格式 |
| `nodeType` | `nodeType 'NORMAL_MODULE'` | `nodeType` | 仅 3 个值，见 §四 |
| `materialType` | `materialType 'proCode'` | `materialType` | `proCode` / `lowCode` |
| `key` | `key {{ item.orderId }}` | `advanced.iterateKey` | LIST_CONTAINER 子项唯一 key |
| `xIf` | `xIf {{ !CONST.isError }}` | `advanced.displayRule` | 条件渲染 |
| `xFor` | `xFor {{ DATA_SOURCE?.data?.list }}` | `advanced.items` | 列表数据源 |
| `props` | `props { ... }` | `resource.props` | 类型化字段声明 |
| `propConfig` | `propConfig('field') { ... }` | `resource.propConfig` | 字段级配置 |
| `style` | `style('containerStyle') { ... }` | `resource.styles[name]` | 具名样式 |
| `on` | `on('event') { ... }` | `resource.events.emit[event][]` | 事件 |
| `buildConfig` | `buildConfig { lazyLoad true }` | `resource.buildConfig` | 惰加载 / 预请求 / 拆包 |
| `slot` | `slot('renderContent') { node(...) { } }` | `slots[slotName][]` | 插槽子节点 |

1. `propConfig` 必须与 `props` **同级**。写进 `props { }` 里会被当成一个「名为 propConfig 的字段」，**协议解析失败**（预览报错 / 白屏），`updateBy` / `isRequestArg` / `lock` 全部失效。
2. `updateBy` 只能写在 `propConfig { }` 内，不能裸写在 `node` 或 `props { }` 里。
3. 字段声明（`bool/number/string/object/array/objectWithSub`）只能写在 `props { }` 内；`transparentArg` 属于事件作用域，不在 `props` 里。

> ⚠️ 这类错误 **Groovy 语法是合法的**（括号配平、缩进正常），语法校验 / ESLint 一律抓不到，只能靠块层级核对。

真实线上案例（`nibfe/hotel-inb-orderfill` 的 `HotelInbOrderfillGuestInfo`）：

```groovy
// ❌ 错误：propConfig 被嵌进 props
props {
  string('email') {{ ... }}
  propConfig('email') { updateBy 'onChangeEmail' }
}

// ✅ 正确：props 先闭合，propConfig 与 props 同级
props {
  string('email') {{ ... }}
}
propConfig('email') { updateBy 'onChangeEmail' }
```

### 插槽与惰加载（真实写法）

```groovy
node('LayoutTopBottom', '7') {
  label '页面布局（上中下）'
  slot('renderTop') {                       // 插槽：子节点只能写在 slot 里，不能直接写在 node 下
    node('NavBar', '1523') { label '导航' }
  }
  slot('renderContent') {
    node('OrderList', '2xxx') {
      label '订单列表'
      nodeType 'LIST_CONTAINER'
      xFor {{ DATA_SOURCE?.data?.orderList }}   // 列表数据源
      key {{ item.orderId }}                     // 子项唯一 key，列表必填
      props {
        string('title') {{ item.title }}
      }
    }
  }
  slot('renderBottom') {
    node('BottomBar', '798') { label '底部提单栏' }
  }
  buildConfig {                             // 按需配置；不写时通常省略该字段
    lazyLoad true
  }
}
```

> - 对声明了插槽的容器物料（如 `LayoutTopBottom`），子节点应按物料 schema 放入对应 `slot('插槽名')`，常见插槽名：`renderTop` / `renderContent` / `renderBottom`；是否允许其他挂载方式由物料协议决定。
> - 大页面拆分：`include('nodes/XxxNode.groovy')` 与 `node(...)` **平级**（顶层 struct 或 slot 内），对应 `buildConfig { splitFile true }`。
> - `buildConfig` 的可选值：`lazyLoad`（惰加载）/ `prefetch`（按数据源 ID 配置 JS/PN 预请求）/ `splitFile`（拆文件）。不配置时通常不输出 `buildConfig`，不要强制补 `null`。
>
> `prefetch` 不是布尔值，而是按数据源 ID 配置：
> ```groovy
> buildConfig {
>   prefetch {
>     submitData {
>       jsEnabled true
>       pnEnabled true
>     }
>   }
> }
> ```


### 字段声明类型

| 类型 | 用法 |
|------|------|
| `bool('xx')` | 布尔 |
| `number('xx')` | 数字 |
| `string('xx')` | 字符串 |
| `object('xx')` | 对象（整体返回一个 Map） |
| `array('xx')` | 数组 |
| `objectWithSub('xx') { }` | 带具名子字段的对象（子字段可被单独引用） |

`object` vs `objectWithSub`：

```groovy
props {
  object('params') {{ [ orderId: DATA_SOURCE?.data?.orderId ] }}   // 只整体使用
  objectWithSub('lx') {                                            // 子字段需单独引用（如 CONST.lx.cid）
    string('cid') {{ 'c_0evvuz5' }}
    object('valLab') {{ [ deal_id: PAGE_QUERY.dealid ?: '-999' ] }}
  }
}
```

> - `objectWithSub` 是 **props 内的声明符**（与 `string/number` 同级），最终生成 `Object` 类型的 `sub` 层级；具体访问前缀以所在上下文为准。
> - 协议转 Groovy 时，空 `sub` 可能被格式化为 `object`；Groovy 转协议时空的 `objectWithSub` 仍会保留为 Object + 空 `sub`，因此不要依赖空块表达特殊语义。

### 全局变量体系（核心）

| 变量 | 含义 |
|------|------|
| `CONST` | 页面初始化常量/跳链参数（CONST.goodsID、CONST.baseInfo.checkin） |
| `DATA_SOURCE` | 数据源返回（DATA_SOURCE.data.priceVO.totalPayAmount） |
| `NODE` | 某节点属性（**仅入参场景**，如 `NODE.GuestCard?.props?.email`） |
| `PAYLOAD` | update/submit 入参（PAYLOAD?.roomNum?.value） |
| `PREV_DATA` | 上一轮数据 |
| `COMMON_PARAMS` | 公共参数（location/city/systemInfo/fingerprint） |
| `PAGE_QUERY` | 页面 query |
| `PROPS` | **自身节点**属性（配合 `propConfig` 双向绑定使用） |

> ⚠️ **使用限制**（放错位置语法不报错，运行时才炸）：
> - `PREV_DATA`、`PAYLOAD`、`NODE.xxx.props` **只能用于 dataSourceMap 的入参**（`requestProps`），不能出现在 struct 的 `props` 表达式里
> - `DATA_SOURCE` 反过来：**不能用于数据源入参**，入参要用 `PREV_DATA`
> - `CONST` 之间不能互相引用；`PAYLOAD` 只在当次 update 生效、不可复用
> - `SYSTEM_INFO`（后端侧）：`realRemoteIp` / `user-agent` / utm 等，只在后端可用

## 四、节点类型

| 类型 | 用途 |
|------|------|
| `NORMAL_MODULE` | 普通渲染模块 |
| `HANDLER_MODULE` | 只执行逻辑、不渲染 UI |
| `LIST_CONTAINER` | 列表容器 |

> `nodeType` 只有上面 3 个值。`STATIC`/`static` **不是 nodeType**，而是物料属性 `MaterialConfig.buildIn='static'`（编译时静态处理、不进渲染树）；DSL 里用 `nodeType '...'` 声明 nodeType，两者不要混。

### static/逻辑节点区分

- `CommonParams` / `MeishiCommonDuoParams`：静态公共参数节点
- `LifecycleLogicStatic` / `LifecycleLogic` / `Logic` / `Static`：生命周期/逻辑节点
- 这些节点**不渲染 UI**，不要把渲染表达式放这里

## 五、逻辑列表 logics 真实语法

```groovy
node('MeishiCommonDuoLifecycle1', '13') {
  label '内置物料-页面生命周期'
  on('preview.onResponse') {
    callMethod('Static', 'onPreviewResponse')
    condition {{ !!COMMON_PARAMS.systemInfo.isMRN }}
  }
  on('submit.onFail') {
    callMethod('SubmitRisk', 'onRiskDialogShow')
    transparentArg('item', 'item')
  }
}
```

### 常见生命周期事件

| 事件 | 说明 |
|------|------|
| `preview.onResponse` / `preview.onSuccess` / `preview.onEngineFail` | preview 各阶段 |
| `submit.onFail` / `submit.onSuccess` | submit 结果 |
| `updateBy` | ⚠️ 不是 lifecycle 事件，只能写在 `propConfig('field') { }` 块内（见 §三） |
| `on('onKeyBoardShow')` 等 | 交互事件 |

## 六、json 类文件修改指南

`protocol/` 下 3 个 `.json` 文件也是协议内容，同样要理解怎么改：

### 6.1 pageBuildConfig.json（编译静态配置）

```json
{
  "baseUrl": "https://xxx.xxx.com/xxx",            // 真实业务前缀，勿照搬
  "pageUrl": {
    "mrn": "rn_xxx_xxx-orderfill-duo&main",        // 各端页面路由，按实际页面填
    "h5": "xxx-orderfill-duo"
  },
  "pageQuery": {
    "goods_id,goodsId": { "required": true, "pnMatch": true },
    "checkinDate,checkindate": { "required": false, "pnMatch": true }
  },
  "commonParams": {
    "usePn": false,
    "systemInfo": { "benchmarkLevel": false },
    "location": { "type": "GCJ02", "useSync": true, "useQuery": false },
    "userInfo": { "forceLogin": true },
    "city": { "useSync": false },
    "fingerprint": { "useQuery": true }
  }
}
```
- `baseUrl`：接口公共前缀
- `pageUrl`：各端页面路由（mrn / h5）
- `pageQuery`：页面跳链参数定义（key 用逗号列出别名，`required` 是否必传，`pnMatch` 是否参与预请求匹配）
- `commonParams`：公共参数开关（location/userInfo/city/fingerprint 等）

**改页面路由 / 跳链参数 / 公共参数开关时修改此文件。**

### 6.2 dependencies.json（依赖物料，数组）

```json
[
  { "name": "@meishi/common-layout-top-bottom", "version": "2.1.6", "type": "component", "url": "https://.../index.js" },
  { "name": "@meishi/common-duo-lifecycle", "version": "1.1.1", "type": "logic", "url": "https://.../index.js" },
  { "name": "@meishi/util-image", "version": "1.0.2", "type": "util", "url": "https://.../index.js", "isLocal": true }
]
```
- 每项：`name`（npm 包名）、`version`、`type`（component/logic/util）、`url`（产物 CDN）、`isLocal`（本地物料）
- **新增物料节点 → 需在此确认/追加对应依赖**

### 6.3 componentsMap.json（物料映射，key=物料ID）

```json
{
  "7":  { "id": "32660", "materialType": "proCode", "type": "component", "npm": "@meishi/common-layout-top-bottom", "npmVersion": "2.1.6", "web": ["https://.../index.js"] },
  "13": { "id": "19422", "materialType": "proCode", "type": "logic", "npm": "@meishi/common-duo-lifecycle", "npmVersion": "1.1.1", "web": ["https://.../index.js"] }
}
```
- **key 就是 `node('Name','物料ID')` 里的物料 ID**（如 7、13、38）
- 每项：`id`（发布版本 id）、`materialType`（proCode）、`type`（component/logic）、`npm` 包名、`npmVersion`、`web` CDN 数组
- **新增视图节点 → 使用的物料必须先出现在 componentsMap（有物料 ID 作 key）**

> ⚠️ 新增物料时，需同步确认 `componentsMap.json`（有物料 ID 作 key）和 `dependencies.json`（有依赖项）都覆盖，否则编译/渲染失败。物料 ID（key）可用 `duo yooz-read-detail` 查询真实验证。

## 七、交互机制

- **updateBy**：某节点变化触发另一节点重算。真实写法：`updateBy 'onChangeGuestInfo'`、`updateBy 'onChangeHourPeriod'`
- **callMethod**：跨节点调用：`callMethod('GuestCard', 'onKeyBoardShow')`
- **on(...)**：事件监听

## 八、关键提醒

1. **变量名禁止编造**：用 `CONST/DATA_SOURCE/NODE/PAYLOAD/PREV_DATA/COMMON_PARAMS/PAGE_QUERY/PROPS`，从现有协议确认
2. **Groovy 2.4.17**：不用 JS 语法（includes/map/filter/reduce）、不用高版本 Groovy
3. **字段用类型化声明**：`bool/number/string/object/array`
4. **第二个参数是物料 ID**：`node('Name','物料ID')`，物料 ID 是**资产平台注册的物料 id**（列表见下，可通过 `duo yooz-read-detail -n <包名>` 查询，或从 componentsMap、现有协议获取，禁止编造或套用其它物料）
5. **不覆盖已有字段**：增量改动
6. **新增物料**：在 componentsMap/dependencies 补引用
7. **materialId 实时查询**：参照真实节点与 package.json 物料，禁止编造
