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
  props {                        // 类型化字段声明
    bool('isOversea') {{ CONST.baseInfo?.isOversea }}
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    string('currencySymbol') {{ '¥' }}
    object('commonParams') {{ [ fingerprint: COMMON_PARAMS.fingerprint.fingerprint ] }}
    array('priceItemList') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
  }
  on('onKeyBoardShow') {          // 事件
    callMethod('GuestCard', 'onKeyBoardShow')
  }
}
```

### 字段声明类型

| 类型 | 用法 |
|------|------|
| `bool('xx')` | 布尔 |
| `number('xx')` | 数字 |
| `string('xx')` | 字符串 |
| `object('xx')` | 对象 |
| `array('xx')` | 数组 |
| `transparentArg('xx','xx')` | 透传参数 |

### 全局变量体系（核心）

| 变量 | 含义 |
|------|------|
| `CONST` | 页面初始化常量/跳链参数（CONST.goodsID、CONST.baseInfo.checkin） |
| `DATA_SOURCE` | 数据源返回（DATA_SOURCE.data.priceVO.totalPayAmount） |
| `NODE` | 某个节点（NODE.BookTime?.props?.checkInPeriod） |
| `PAYLOAD` | update/submit 入参（PAYLOAD?.roomNum?.value） |
| `PREV_DATA` | 上一轮数据 |
| `COMMON_PARAMS` | 公共参数（location/city/systemInfo/fingerprint） |
| `PAGE_QUERY` | 页面 query |
| `PROPS` | 父级传入 props |

## 四、节点类型

| 类型 | 用途 |
|------|------|
| `NORMAL_MODULE` | 普通渲染模块 |
| `HANDLER_MODULE` | 只执行逻辑、不渲染 UI |
| `LIST_CONTAINER` | 列表容器 |
| `STATIC` | 编译时静态处理（`MaterialConfig.buildIn='static'`），只放逻辑不渲染 |

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
| `updateBy` | 双向绑定（如 `updateBy 'onChangeHourPeriod'`） |
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
