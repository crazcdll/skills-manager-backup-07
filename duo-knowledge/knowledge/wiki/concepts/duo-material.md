# D · DUO 物料体系

> 覆盖范围：物料的分类与类型、MaterialConfig 协议结构、物料与节点的关系、proCode vs lowCode 开发模式、物料注册与使用。

---

## 1. 物料是什么

物料（Material）是 DUO 页面的最小可复用单元，对应一个 React 组件（视图物料）或一段逻辑（逻辑物料）。页面协议中的每个节点（PageNode）都通过 `materialId` 引用一个物料。

物料在 yooz 平台（`yooz.sankuai.com/client-platform/material/component`）统一管理，每个物料有唯一的 `materialId`，并通过 npm 包发布到前端工程。

---

## 2. 物料分类

### 2.1 按功能分类


| 类型       | MaterialType     | 说明                                 |
| ------------ | ------------------ | -------------------------------------- |
| 普通模块   | `NORMAL_MODULE`  | 标准视图组件，渲染 UI                |
| 处理器模块 | `HANDLER_MODULE` | 逻辑组件，不渲染 UI，处理事件/副作用 |
| 列表容器   | `LIST_CONTAINER` | 循环渲染子节点，对应`xFor`           |

### 2.2 按开发模式分类


| 模式       | devMode   | 说明                                                               |
| ------------ | ----------- | -------------------------------------------------------------------- |
| 源码物料   | `proCode` | 标准 React 组件，通过 npm 包引入，有`npm`/`npmVersion`/`urls` 字段 |
| 低代码物料 | `lowCode` | 在搭建平台上用拖拽方式组合而成，有`dsl` 字段                       |

初期页面使用比较多，现在已不再新增lowCode类型物料，现在业务开发中绝大多数使用 **proCode** 模式。

### 2.3 内置特殊物料（buildIn）


| buildIn 值      | 说明                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------ |
| `lifeCycle`     | 页面生命周期物料，监听 preview/update/submit/check 的 onResponse/onSuccess/onFail 等事件 |
| `pageContainer` | 页面容器物料，负责渲染 children slot（整个页面的根节点）                                 |
| `static`        | 静态物料，不参与数据驱动渲染                                                             |

---

## 3. MaterialConfig 协议结构

`MaterialConfig` 是物料的配置描述，存储在 yooz 平台，前端工程通过 `configSchema` 字段（JSON 字符串）获取。

```typescript
interface MaterialConfig {
  materialOrigin?: 'MCP';       // 来源标记
  buildIn?: 'lifeCycle' | 'pageContainer' | 'static'; // 内置物料标记
  type: MaterialType;           // 'NORMAL_MODULE' | 'HANDLER_MODULE' | 'LIST_CONTAINER'

  // 物料的 props 定义
  props?: (FieldConfig & { name: string; updateBy?: string })[];

  // 高级配置（nodeSchema）
  nodeSchema?: (FieldConfig & { name: string })[];

  // 插槽定义
  slots?: MaterialConfigSlot[];

  // 事件定义
  events?: {
    emit?: MaterialConfigEmit[];  // 物料发出的事件（callback）
    on?: MaterialConfigOn[];      // 物料接收的事件（method）
  };
}
```

### 3.1 props 定义

每个 prop 对应一个 `FieldConfig`，描述该 prop 的类型、默认值、是否必填等。`updateBy` 字段用于双向绑定：当物料触发 `updateBy` 指定的事件时，引擎自动更新该 prop 的值。

```typescript
// 示例：count prop 绑定 onChange 事件
{
  name: 'count',
  type: 'number',
  updateBy: 'onChange'
}
```

对应协议中的 `propConfig`：

```groovy
propConfig('count') {
  updateBy 'onChange'
  isRequestArg true   // update 时将 count 的当前值发给后端
  lock true           // 请求进行中时不触发双向绑定
}
```

### 3.2 slots 定义

插槽允许父节点向子节点传递渲染内容。

```typescript
interface MaterialConfigSlot {
  name: string;    // 插槽名，如 'children'、'renderTop'、'renderBottom'
  label?: string;
  desc?: string;
}
```

在 struct.groovy 中使用：

```groovy
node('MeishiCommonLayoutTopBottom1', '7') {
  slot('renderTop') {
    node('NavBar1', '1') { ... }
  }
  slot('renderContent') {
    node('ContentModule1', '2') { ... }
  }
  slot('renderBottom') {
    node('BottomBar1', '3') { ... }
  }
}
```

### 3.3 events 定义

**emit**（物料发出的事件）：物料通过 callback prop 向外发出事件，协议中用 `on` 块监听。

```typescript
interface MaterialConfigEmit {
  name: string;       // 事件名，如 'onChange'、'onRefresh'
  label?: string;
  props?: FieldConfig[];  // 事件回调参数
  update?: string;    // 双向绑定语法糖：触发时更新哪个 prop
}
```

**on**（物料接收的事件）：物料暴露的方法，可被其他节点通过 `callMethod` 调用。

```typescript
interface MaterialConfigOn {
  name: string;       // 方法名，如 'update'、'scrollHandler'
  label?: string;
  props?: (FieldConfig & { name: string })[];  // 方法入参
}
```

---

## 4. 节点与物料的关系

页面协议中的 `PageNode` 通过 `materialId` 引用物料，`nodeName` 是节点在页面内的唯一标识：

```typescript
interface PageNode {
  nodeType: 'NORMAL_MODULE' | 'HANDLER_MODULE' | 'LIST_CONTAINER';
  materialId: string;          // 引用哪个物料（yooz 平台的物料 ID）
  materialType?: 'lowCode' | 'proCode';
  resource: PageNodeResource;  // 节点配置（nodeName、props、events 等）
  slots?: { [slotName: string]: PageNode[] };
}
```

同一个物料可以在页面中被多次使用，每次使用对应一个不同的节点（不同 `nodeName`）。

---

## 5. 物料在前端工程中的注册

前端页面入口需要将物料 map 传给 DUO 引擎：

```typescript
// componentMap: 视图物料（NORMAL_MODULE / LIST_CONTAINER）
// logicMap: 逻辑物料（HANDLER_MODULE）
<DuoEngine
  componentMap={{
    'meishi-common-layout-top-bottom': MeishiCommonLayoutTopBottom,
    'meishi-biz-order-detail-feedback': MeishiBizOrderDetailFeedback,
    // ...
  }}
  logicMap={{
    'meishi-common-duo-lifecycle': MeishiCommonDuoLifecycle,
    // ...
  }}
  buildInMap={{
    static: 'static',
    pageContainer: 'meishi-common-layout-top-bottom',
    lifeCycle: 'meishi-common-duo-lifecycle',
  }}
  // ...其他 props
/>
```

`materialId` 与 componentMap 的 key 对应关系由 yooz 平台的 npm 包名决定，通常是 kebab-case 格式。

---

## 6. proCode 物料开发规范

### 6.1 组件接收的 props

proCode 物料组件接收两类 props：

1. **业务 props**：由协议中的 `props` 块计算得出，对应 `MaterialConfig.props` 中定义的字段
2. **`props.__duo__`**：引擎注入的能力句柄（详见 C · DUO 引擎工作原理）

```typescript
interface MyMaterialProps {
  // 业务 props（由 MaterialConfig.props 定义）
  title: string;
  count: number;
  onChange?: (count: number) => void;  // emit 事件

  // 引擎注入
  __duo__?: DuoInjectHandler;
}
```

### 6.2 触发生命周期

物料通过 `props.__duo__.emit` 触发引擎生命周期：

```typescript
// 触发 update
props.__duo__?.emit('update', {
  payload: { quantity: newCount },
  debounceDelay: 300,
});

// 触发 submit
props.__duo__?.emit('submit', {
  payload: { orderId: '123' },
  onSuccess: (data) => { /* 提交成功 */ },
  onFail: (data) => { /* 提交失败 */ },
});
```

### 6.3 注意事项

组件强依赖 `props.__duo__` 后就只能在 DUO 页面中使用，无法独立复用。如果组件需要在非 DUO 场景复用，应将 `__duo__` 相关逻辑封装在上层，或通过 props 透传回调。

---

## 7. 物料类型速查


| materialId 命名规范           | 示例                               | 说明             |
| ------------------------------- | ------------------------------------ | ------------------ |
| `<业务前缀>-<功能描述>`       | `meishi-common-layout-top-bottom`  | 通用布局物料     |
| `meishi-biz-<功能>`           | `meishi-biz-order-detail-feedback` | 业务物料         |
| `meishi-common-duo-lifecycle` | —                                 | 内置生命周期物料 |
| `meishi-common-event-lx`      | —                                 | 埋点事件物料     |

物料 ID 在 yooz 平台查询，`materialInfo.materialId` 字段即为注册到 componentMap/logicMap 的 key。
