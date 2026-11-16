# B · DUO 协议体系

> 覆盖范围：PageProtocol（搭建协议）和 RenderResponseData（端到端协议）的完整字段说明、关键约束和常见误用。

---

## 1. 两层协议

DUO 有两层协议，职责不同：

**PageProtocol（搭建协议）** 是配置平台生成、存储在 Git 仓库中的静态 JSON，描述页面的完整配置意图。后端 SDK 读取它来执行 Groovy 和调用业务接口。

**RenderResponseData（端到端协议）** 是后端每次请求返回的动态数据，描述当前请求下页面应该渲染什么。前端引擎消费它来渲染组件树。

---

## 2. PageProtocol 字段速查

```typescript
interface PageProtocol {
  duoVersion: '2';              // 协议版本标识，旧版本此字段为空
  pageId: string;               // 页面全局唯一 ID（如 "food-order-submit"）
  pageProtocolId: string;       // 协议 ID，一个页面可有多个协议
  pageProtocolVersion: string;  // 协议版本号
  pageBuildConfig: PageBuildConfig;       // 编译时静态配置
  dependencies: PageDependency[];         // npm 依赖锁定列表
  ohDependencies?: PageDependency[];      // 鸿蒙端依赖锁定
  componentsMap: { [materialId: string]: MaterialResourceConfig }; // 物料映射表
  dynamicDataConfig: {
    dataSourceMap: { [key: string]: DataSourceConfig }; // 数据源配置
    constData?: { [key: string]: DataExpression };      // 常量（CONST.xxx）
  };
  struct?: PageNode[];   // 视图树
  logics?: PageNode[];   // 逻辑节点列表
}
```

### 2.1 pageBuildConfig

编译时静态配置，包含：

- `pageQuery`：页面跳链参数
- `commonParams`：需要收集的系统环境参数（不需要的不勾选，提升秒开）
- 接口前缀（preview/update/submit 的 URL 前缀）
- `modulesLoadConfig`：模块加载配置（内联引用、RAM bundle 等）

### 2.2 componentsMap

物料映射表，key 是 `materialId`，value 是 `MaterialResourceConfig`：

```typescript
interface MaterialResourceConfig {
  id: string;
  materialType: 'lowCode' | 'proCode';  // lowCode=Yooz 物料，proCode=源码 npm 包
  type: 'logic' | 'component';          // logic=逻辑节点，component=视图节点
  npm?: string;          // proCode 的 npm 包名
  npmVersion?: string;
  web?: string[];        // Web 端 CDN 地址
}
```

### 2.3 dataSourceMap

数据源配置，每个 key 对应一个业务接口：

```typescript
interface DataSourceConfig {
  currentData: { [key: string]: DataExpression }; // 入参中可能会使用上次的数据源结果，需要在这里定义。
  reqProps: { [key: string]: DataExpression };     // 数据源请求入参。只有后端关心，前端不需要解析
  bizRespStatus?: DataSourceConfigBizRespStatus;   // preview/update 数据源响应的业务状态
  submitBizRespStatus?: DataSourceConfigSubmitBizRespStatus; // submit 数据源响应的业务状态
  checkBizRespStatus?: DataSourceConfigCheckBizRespStatus;   // check 数据源响应的业务状态
}
```

`bizRespStatus.isError` 是 Groovy 表达式，返回 true 时引擎展示错误态。

### 2.4 PageNode（节点）

视图树和逻辑列表中的节点结构：

```typescript
interface PageNode {
  nodeType: 'NORMAL_MODULE' | 'HANDLER_MODULE' | 'LIST_CONTAINER';
  materialId: string;
  materialType?: 'lowCode' | 'proCode';
  resource: PageNodeResource;
  slots?: { [slotName: string]: PageNode[] }; // 子节点（插槽）
}

interface PageNodeResource {
  nodeName: string;       // 节点名，页面内唯一，用于事件通讯
  label: string;
  props?: { [key: string]: DataExpression };   // 属性（Groovy 表达式）
  styles?: { [key: string]: DataExpression };  // 样式（Groovy 表达式）
  propConfig?: { [key: string]: PropConfig };  // 属性配置（双向绑定等）
  advanced?: PageNodeAdvanced;                 // 高级配置
  events?: {
    emit?: { [emitEventName: string]: PageNodeEventEmit[] };
  };
}
```

**PropConfig** 控制属性的运行时行为：

```typescript
interface PropConfig {
  isRequestArg?: boolean; // 是否在 update/submit 时发给后端
  updateBy?: string;      // 双向绑定：触发哪个事件时更新此属性
  lock?: boolean;         // 双向绑定加锁：请求进行中时不触发更新
}
```

**PageNodeAdvanced** 高级配置：

```typescript
interface PageNodeAdvanced {
  displayRule?: DataExpression; // 显示规则（Groovy 表达式，返回 boolean）
  iterateKey?: DataExpression;  // 列表项唯一 key
  items?: DataExpression;       // 列表数据源
}
```

**PageNodeEventEmit** 事件配置：

```typescript
interface PageNodeEventEmit {
  notifyNodeName: string;       // 通知哪个节点
  notifyEventName: string;      // 调用该节点的哪个方法
  emitCondition?: DataExpression; // 触发条件（Groovy 表达式）
  lock?: boolean;               // 请求进行中时不触发
  props?: { [key: string]: DataExpression }; // 调用时的入参
  transparentArg?: PageNodeEventEmitTransparentArg[]; // 透传参数映射
}
```

---

## 3. RenderResponseData 字段速查

```typescript
interface RenderResponseData {
  pageId: string;
  pageProtocolId: string;
  pageProtocolVersion: string;
  bizRespStatus?: BizRespStatus; // 业务状态（isError/errorMsg/errorToast）
  currentData: { [key: string]: any }; // 数据源出参（PREV_DATA 的来源）
  struct: RenderNode[];          // 视图树（渲染用）
  logics: RenderNode[];          // 逻辑节点列表
  nodeDataMap: { [nodeName: string]: RenderNodeData }; // 节点数据
}

interface RenderNode {
  nodeName: string;
  iterateKey?: string;
  slots?: { [slotName: string]: RenderNode[] };
}

interface RenderNodeData {
  materialId: string;
  materialType?: 'lowCode' | 'proCode';
  props?: { [key: string]: any };   // 计算后的属性值
  styles?: { [key: string]: any };  // 计算后的样式值
  propConfig?: { [key: string]: RenderNodePropConfig };
  events?: {
    emit?: { [emitEventName: string]: RenderNodeEventEmit[] };
  };
}
```

---

## 4. 请求入参（RenderRequest）

```typescript
interface RenderRequest {
  pageId: string;
  pageProtocolId: string;
  pageQuery?: { [key: string]: string };  // 页面跳链参数
  commonParams: CommonParams;             // 系统环境参数
  prevData: { [key: string]: any };       // 上次数据源结果
  nodeDataMap: {                          // 当前节点 props 状态
    [nodeName: string]: { props: { [key: string]: any } }
  };
  updatePropMap: {                        // 本次变更的字段
    [nodeName: string]: { [propName: string]: boolean }
  };
  payload: any;                           // 本次携带的临时数据
}
```

---

## 5. 表达式变量速查

在 Groovy 表达式中可用的内置变量：


| 变量                | 可用场景    | 说明                                           |
| --------------------- | ------------- | ------------------------------------------------ |
| `PAGE_QUERY.xxx`    | 所有        | 页面跳链参数                                   |
| `COMMON_PARAMS.xxx` | 所有        | 系统环境参数（用户/设备/位置等）               |
| `CONST.xxx`         | 所有        | 常量，来自`dynamicDataConfig.constData`        |
| `PREV_DATA.xxx`     | 出参        | 上次接口返回数据，推荐在出参中使用             |
| `NODE.X.props.xxx`  | 入参        | 其他节点当前 props 值，**仅接口入参使用**          |
| `PROPS.xxx`         | 入参/出参   | 节点保存的状态，需勾选"保存状态"               |
| `PAYLOAD.xxx`       | update 入参 | 本次 update 携带的临时数据，**仅 update 场景** |
| `DATA_SOURCE.xxx`   | 入参        | 其他数据源的出参                               |

---

## 6. 关键约束

**PAYLOAD 使用约束：**

- 仅在需要后端校验的 update 场景使用
- preview 时 PAYLOAD 为空，submit 时可能已清空
- 必须提供 PREV_DATA 兜底，不能单独依赖 PAYLOAD

**NODE.X.PROPS 使用约束：**

- 仅在入参时使用，出参必须用 PREV_DATA
- 读取的是当前渲染帧的前端状态，不稳定

**displayRule 约束：**

- 表达式结果必须是 boolean，建议用 `!!` 强制转换
- 例：`!!PREV_DATA?.showButton`

**static 节点约束：**

- 必须是视图树顶层节点，不能嵌套
- 数据在页面生命周期内不会更新
- 非必要禁止使用

**pageContainer 约束：**

- 一个页面只能有一个
- 必须是视图树顶层节点
- DUO 会注入 `props.children`（loading/error 视图）

---

## 7. 常见误用

**误用 1：在 preview 中使用 PAYLOAD**

```groovy
// ❌ preview 时 PAYLOAD 为空
def count = PAYLOAD.quantity

// ✅ 正确：提供兜底
def count = PAYLOAD.quantity ?: PREV_DATA?.quantity ?: 1
```

**误用 2：出参使用 NODE.X.PROPS**

```groovy
// ❌ 出参不稳定
{ productList: NODE.ProductListModule?.props?.items }

// ✅ 出参用 PREV_DATA
{ productList: PREV_DATA?.productList }
```

**误用 3：displayRule 返回非 boolean**

```groovy
// ❌ 可能返回 null/undefined
PREV_DATA?.showButton

// ✅ 强制转 boolean
!!PREV_DATA?.showButton
```

**误用 4：emitCondition 返回非 boolean**

```groovy
// ❌
PREV_DATA?.count

// ✅
(PREV_DATA?.count ?: 0) > 0
```
