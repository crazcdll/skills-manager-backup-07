# C · DUO 引擎工作原理

> 覆盖范围：前端 duo-engine 的渲染流程、生命周期、props.__duo__ 注入；后端 DUO SDK 的解析流程和 StageEnum 六阶段。

---

## 1. 前端引擎（duo-engine）

### 1.1 引擎入口

前端引擎以 React 组件形式提供，核心 props 如下：

```typescript
interface DuoEngineProps {
  componentMap: Record<string, any>;   // 视图物料 map（materialId → 组件）
  logicMap: Record<string, any>;       // 逻辑物料 map（materialId → 组件）
  buildInMap: Record<string, string>;  // 内置物料（static/pageContainer/lifeCycle）
  pageQuery: { [key: string]: string }; // 页面跳链参数
  commonParamsManagerRef: { current: CommonParamsManager }; // 通参管理器
  requestInfo: DuoEngineRequestInfo;   // 接口基本信息（baseURL/pageId 等）
  prefetchRequestMap: Record<string, Record<string, DuoEnginePrefetch>>; // 预请求
  onLifecycle?: DuoOnLifecycle;        // 生命周期回调
}
```

### 1.2 渲染流程

```
mount
  ↓
收集 commonParams（异步，可能有桥耗时）
  ↓
发起 preview 请求（携带 pageQuery + commonParams）
  ↓
收到 RenderResponseData
  ↓
按 struct 树递归渲染：
  对每个 RenderNode：
    1. 从 nodeDataMap 取出 RenderNodeData
    2. 用 materialId 从 componentMap/logicMap 找到组件
    3. 将 props/styles 传入组件
    4. 注入 props.__duo__（引擎能力句柄）
    5. 递归渲染 slots 子节点
  ↓
页面就绪（ready=true）
```

### 1.3 生命周期

DUO 引擎有四个核心生命周期，对应四种接口：

| 生命周期 | 触发时机 | 说明 |
|----------|----------|------|
| **preview** | 页面首次加载 | 获取初始渲染数据，`isFirstRequest=true` |
| **update** | 用户交互触发 | 局部刷新，携带 `payload` 和 `updatePropMap` |
| **submit** | 表单提交 | 触发业务写操作，返回 `SubmitResponseData` |
| **check** | 前端校验 | 不触发写操作，用于表单校验，返回 `CheckResponseData` |

生命周期选项（以 update 为例）：

```typescript
interface UpdateOptions {
  payload?: any;          // 携带的临时数据
  debounceDelay?: number; // 防抖延迟（输入框场景）
  lock?: boolean;         // 有其他请求时取消本次
  addLock?: boolean;      // 本请求进行中时限制其他请求（默认 true）
  isShowLoading?: boolean;
  showLoadingDelay?: number;    // 延迟显示 loading（update 默认 400ms，preview/submit 默认不延迟）
  loadingMinDuration?: number;  // loading 最短显示时长（默认 200ms）
}
```

生命周期回调：

```typescript
interface LifecycleCallbacks {
  onResponse?: (data, ctx) => void;  // 收到响应时（成功或失败都触发）
  onSuccess?: (data?) => void;       // 业务成功
  onFail?: (data?) => void;          // 业务失败（bizRespStatus.isError=true）
  onEngineFail?: (data?) => void;    // 引擎层失败（网络错误等）
  onCancel?: (cancelReasonType) => void; // 请求被取消
}
```

取消原因类型（`CancelReasonType`）：
- `DebouncePending`：被防抖取消（后一次请求覆盖前一次）
- `Locked`：被锁取消（其他请求进行中）
- `Invalid`：请求已失效（数据竞态，被更新的请求覆盖）
- `PageClosed`：页面关闭时取消

### 1.4 props.__duo__ 注入

引擎自动向每个物料组件注入 `props.__duo__`：

```typescript
interface DuoInjectHandler {
  emit: (key: string, opts: any, ...rest: any[]) => void;
  // key: 'preview' | 'update' | 'submit' | 'check'
  // 触发对应生命周期

  renderNode: (node: RenderNode) => any;
  // 渲染子节点（用于 pageContainer 渲染 children）

  getPageQuery: () => PageQuery | undefined;
  getCommonParams: () => CommonParams | undefined;       // 同步获取（可能为空）
  getCommonParamsAsync: () => Promise<CommonParams>;     // 异步获取（推荐）
  getRequestInfo: () => DuoEngineRequestInfo | undefined;
  getPerformanceStat: () => DuoPerformanceStat | undefined;

  // 缓存和 Tab 场景
  getNodeKey: (node: RenderNode) => string;
  getNodeData: (node: RenderNode) => RenderNodeData | undefined;
  getPageState: () => DuoPageState & { updatePropMap };
  setPageState: (state) => void;
  forceRender: () => void;
  dangerouslyRefreshCommonParams: (params: RefreshCommonParamsType) => void;
}
```

**注意**：组件强依赖 `props.__duo__` 后就只能在 DUO 页面中使用，无法独立复用。

`getPageState()` 状态判断：
- `ready=false`：加载中
- `ready=true`：加载完成
- `isError=true`：接口返回业务异常

### 1.5 性能打点

```typescript
interface DuoPerformanceStat {
  pageStartTime: number;    // 页面入口执行第一行 JS 的时间
  previewStartTime: number; // 开始发出 preview 请求的时间（差值主要是桥耗时）
  previewEndTime: number;   // preview 接口结束时间（差值是接口耗时）
}
```

---

## 2. 后端 DUO SDK

### 2.1 解析流程

后端 SDK 收到前端请求后，按以下流程处理：

```
AbstractUnifiedController.handleRequest()
  ↓
UnifiedProtocolParserV2.parse()
  ↓
按 StageEnum 顺序执行 6 个阶段
  ↓
返回 RenderResponseData
```

### 2.2 StageEnum 六阶段

| 阶段 | 枚举值 | 说明 |
|------|--------|------|
| 1 | `INIT` | 初始化：加载 PageProtocol，校验请求参数 |
| 2 | `COMMON_PARAMS` | 收集通参：解析 commonParams，准备 Groovy 执行上下文 |
| 3 | `DATA_SOURCE` | 执行数据源：运行 reqProps Groovy 表达式，调用业务接口，运行 currentData 表达式 |
| 4 | `STRUCT` | 构建节点树：运行 struct.groovy，生成 RenderNode 树（含 xIf/xFor 展开） |
| 5 | `NODE_DATA` | 计算节点数据：对每个 RenderNode 运行 props/styles/events Groovy 表达式，生成 RenderNodeData |
| 6 | `RESPONSE` | 组装响应：将 RenderNode 树 + nodeDataMap 打包为 RenderResponseData 返回 |

各阶段关键说明：

**INIT**：加载 PageProtocol（从数据库或缓存），校验 pageId、生命周期类型（preview/update/submit/check）、pageQuery 必填项。

**COMMON_PARAMS**：解析 `commonParams`（systemInfo、userInfo、cityInfo、location 等），构建 Groovy 执行上下文，注入 `COMMON_PARAMS`、`PAGE_QUERY` 变量。

**DATA_SOURCE**：
1. 执行 `dataSourceMap.groovy` 中的 `requestProps` 块，生成业务接口入参
2. 调用业务接口（HTTP），拿到原始响应
3. 执行 `currentData` 块，从响应中提取并转换数据，注入 `DATA_SOURCE`、`PREV_DATA` 变量
4. 执行 `bizRespStatus` 块，判断业务是否成功

**STRUCT**：执行 `struct.groovy`，递归展开节点树。`xIf` 表达式为 false 的节点被剪枝，`xFor` 节点按列表展开，注入 `FOR` 变量。

**NODE_DATA**：对每个保留节点，执行 `nodes/<NodeName>.groovy`（或内联 props 块），计算 props/styles/events 的最终值，注入 `NODE`（已计算节点的 props 快照）变量。

**RESPONSE**：将 RenderNode 树（仅结构，不含数据）和 nodeDataMap（nodeId → RenderNodeData）分离打包，压缩字段名（`props→p`、`styles→s` 等），返回给前端。

### 2.3 Groovy 上下文变量速查

| 变量 | 类型 | 可用阶段 | 说明 |
|------|------|----------|------|
| `PAGE_QUERY` | Map | 全部 | 跳链参数 |
| `COMMON_PARAMS` | Map | DATA_SOURCE 起 | 通参（systemInfo/userInfo/cityInfo/location 等） |
| `DATA_SOURCE` | Map | NODE_DATA 起 | 业务接口原始响应 |
| `PREV_DATA` | Map | NODE_DATA 起 | currentData 计算结果（上一次快照） |
| `CONST` | Map | NODE_DATA 起 | constData.groovy 计算结果 |
| `NODE` | Map | NODE_DATA 中 | 已计算节点的 props（按 nodeName 索引） |
| `PAYLOAD` | Map | update/submit/check | 前端 emit 携带的 payload |
| `FOR` | Map | xFor 节点内 | 当前循环项（`FOR.item`、`FOR.index`） |

### 2.4 协议文件分工

| 文件 | 执行阶段 | 职责 |
|------|----------|------|
| `constData.groovy` | NODE_DATA 前 | 定义页面级常量（lx 埋点参数、枚举值等） |
| `dataSourceMap.groovy` | DATA_SOURCE | 定义数据源请求参数和响应映射 |
| `struct.groovy` | STRUCT | 定义节点树结构（含 xIf/xFor） |
| `nodes/<Name>.groovy` | NODE_DATA | 定义单个节点的 props/styles/events |
| `logics.groovy` | NODE_DATA | 定义逻辑节点（lifeCycle/事件处理） |

---

## 3. 前后端协作要点

**数据流向**：前端 pageQuery + commonParams → 后端 6 阶段处理 → RenderResponseData → 前端渲染

**updatePropMap**：update/submit/check 请求时，前端将 `propConfig.isRequestArg=true` 的 prop 当前值收集为 `updatePropMap`，随请求发给后端，后端在 DATA_SOURCE 阶段可通过 `NODE.<nodeName>.props.<propName>` 读取。

**PREV_DATA vs DATA_SOURCE**：`DATA_SOURCE` 是接口原始响应，`PREV_DATA` 是上一次 `currentData` 计算后的快照。update 时两者都有；preview 时 `PREV_DATA` 为空。

**节点树压缩**：RenderResponseData 中字段名被压缩（`props→p`、`styles→s`、`propConfig→pc` 等），前端引擎负责解压，开发者在 Groovy 中无需关心。

**错误处理**：`bizRespStatus.isError=true` 时，后端仍返回完整 RenderResponseData（除非配置了 `errorNoReturnStruct true`），前端引擎触发 `onFail` 回调，组件通过 `getPageState().isError` 感知。
