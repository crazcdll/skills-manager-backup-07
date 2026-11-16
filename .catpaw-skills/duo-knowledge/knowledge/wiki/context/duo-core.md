# duo-core 仓库结构与核心模块

> 本文档面向需要深入理解 DUO 前端引擎实现的开发者，介绍 `duo-core` 仓库的整体结构、核心模块职责及关键数据流。
> **仓库地址：** `ssh://git@git.sankuai.com/nibfe/duo-core.git`
> 文档中所有路径均相对于该仓库根目录。

---

## 仓库概览

`duo-core` 是 DUO 低代码平台的前端核心仓库，包含以下主要 package：

```
packages/
  duo-engine/              # 运行时引擎（@meishi/duo-engine）
  duo-protocol/            # 协议类型定义（@meishi/duo-protocol）
  duo-protocol-transform/  # 协议 ↔ Groovy 互转（@meishi/duo-protocol-transform）
  duo-expression-transform/ # 表达式转换（@meishi/duo-expression-transform）
  duo-builder/             # 构建工具 CLI（@meishi/duo-builder）
  groovy-lite/             # 前端 Groovy 解析器（@meishi/groovy-lite）
  groovy-runtime/          # Groovy 运行时函数库（DF.xxx 实现）
  duo-owl/                 # 监控/错误上报
  duo-debug-panel/         # 调试面板（AppMock/锁版本）
  duo-loader/              # 物料加载器
```

> 完整的各 package 目录结构见 `context/repo-map.md`。

---

## duo-engine：前端渲染引擎

### 职责

`duo-engine` 负责将后端返回的 `PageProtocol`（JSON 协议）渲染为可交互的 UI，是 DUO 的核心运行时。

### 目录结构（`packages/duo-engine/src/`）

```
packages/duo-engine/src/
  index.tsx                        # 引擎入口，导出 DuoPage 组件
  types.ts                         # GlobalData / DuoPageState 等核心类型
  page/
    index.tsx                      # 页面主组件
    RenderTree.tsx                 # 渲染树（遍历 nodes 递归渲染）
    RenderTreeNode/
      index.tsx                    # 单节点渲染器（核心）
      helper.tsx
      useNodeProps.ts              # 节点 props 计算（表达式求值入口）
    pageLifecycle/
      index.ts                     # 生命周期主入口（isEngineError 判断逻辑在此）
      prefetchRequest.ts
      requestNodeDataMap.ts
      handlePreviewCallback.ts
      report.ts                    # 性能上报
      types.ts
    eventBus.ts                    # 事件系统（emit / useOn）
    handleLogic.ts                 # 逻辑模块事件监听与分发
    globalData.ts                  # 全局状态管理（GlobalDataMap）
    hooks/
      validate.ts
      validateQuery.ts
  datasource/
    index.ts                       # DataSource 类（HTTP 请求封装）
    handleMinifyHttpResponse.ts
  utils/
    event.ts                       # createEvent 事件工厂
    getset.ts                      # 深路径 get/set
    monitor.ts                     # 监控上报工具
```

### 关键数据流

```
App 启动
  -> pageLifecycle.init()
     -> 加载 componentMap / logicMap（物料注册表）
     -> 调用后端接口（duo_csdk_v）
     -> 解析响应：isEngineError 判断
        -> 是引擎错误：显示错误兜底页，终止
        -> 否：继续
     -> 解析 bizRespStatus：业务错误判断
     -> 执行 struct Groovy 表达式，生成节点树
     -> 执行各节点 props Groovy 表达式
     -> 渲染节点树
     -> 触发 onPageReady 生命周期
```

### isEngineError 判断逻辑

```typescript
// packages/duo-engine/src/page/pageLifecycle/index.ts
const isEngineError = !resp || !!resp.error || !data;
```

三种情况触发引擎错误：
1. `resp` 为 null/undefined（网络请求失败）
2. `resp.error` 有值（后端 SDK 抛出未捕获异常）
3. `resp.data` 为 null/undefined（接口返回了响应但 data 字段为空）

### bizRespStatus 判断逻辑

```typescript
// packages/duo-engine/src/page/pageLifecycle/handlePreviewCallback.ts
const bizRespStatus = data.bizRespStatus;
const isBusinessError = bizRespStatus?.isError === true;
```

`bizRespStatus` 来自后端 `dataSourceMap.groovy` 中的配置，用于表达业务层面的错误（如商品已下架、无权限等）。与 `isEngineError` 的区别：

| 维度 | isEngineError | bizRespStatus.isError |
|------|--------------|----------------------|
| 触发层 | 引擎层（网络/SDK 异常） | 业务层（业务逻辑判断） |
| 是否有 struct | 否 | 可配置（errorNoReturnStruct） |
| 错误文案 | 引擎兜底文案 | 业务自定义文案 |

### expressionErrorList

当 Groovy 表达式执行时抛出异常，引擎不会崩溃，而是将错误记录到 `warnInfo.expressionErrorList`：

```typescript
// 来自 @meishi/duo-protocol ExpressionErrorInfo
interface ExpressionErrorInfo {
  field: string;        // 出错的 prop 字段名
  expression: string;  // 表达式内容
  errorReason: string; // 错误原因（如 NullPointerException）
}
```

出错的 prop 会被置为 null，其他 prop 正常渲染。可通过 AppMock 查看接口响应中的 `warnInfo` 字段排查。

### 事件系统

```typescript
// 触发事件（组件内）
props.__duo__?.emit('onChange', { value: newValue });

// 调用方法（Groovy on 块配置）
// struct.groovy 中：
on('onChange') {
  callMethod('Lifecycle1', 'update')
  transparentArg('value', 'payload.newValue')
}
```

`callMethod` 会通过 `eventBus` 找到目标逻辑节点，调用其 `update` 方法，并将 `transparentArg` 映射的参数注入到 `PAYLOAD` 中。

---

## duo-protocol-transform：协议转换工具

### 职责

将 Groovy 协议文件（`struct.groovy`、`constData.groovy` 等）转换为：
1. TypeScript 类型定义（供物料开发使用）
2. JSON Schema（供 yooz 平台配置使用）
3. 测试用 mock 数据

### 使用方式

`duo-protocol-transform` 的具体使用方式和转换规则超出前端源码可验证范围，以实际工具文档为准。

---

---

## 关键配置文件说明

### duo.config.js

`duo.config.js` 的完整配置项见 `context/duo-builder.md`。核心必填字段：

```javascript
module.exports = {
  pageId: 'your-page-id',
  pageProtocolId: 'your-protocol-id',
  pageProtocolVersion: 'your-protocol-version',
};
```

### dependencies.json

`dependencies.json` 是 `PageDependency[]` 数组，每项描述一个物料依赖：

```typescript
// 来自 @meishi/duo-protocol
interface PageDependency {
  name: string;     // npm 包名
  version: string;  // 版本号
  type: string;     // 依赖类型
  url?: string;     // Web 端 CDN URL（可选）
}
```

### componentsMap

`componentsMap` 是协议中 `materialId` 到物料资源配置的映射，value 类型为 `MaterialResourceConfig`：

```typescript
// 来自 @meishi/duo-protocol
interface MaterialResourceConfig {
  id: string;          // 物料发布 ID（Yooz 平台）
  materialType?: string;
  type?: string;
  npm?: string;        // npm 包名
  npmVersion?: string; // npm 版本号
  web?: string;        // Web 端 CDN URL
}
```

引擎通过 `materialId` 在 `componentMap`/`logicMap` 中找到对应的 React 组件。

---

## 性能数据采集

引擎内置性能打点，可通过 `getPerformanceStat()` 获取：

```typescript
// 来自 @meishi/duo-protocol DuoPerformanceStat
interface DuoPerformanceStat {
  pageStartTime: number;    // 页面入口执行第一行 JS 的时间
  previewStartTime: number; // 开始发出 preview 请求的时间（差值主要是桥耗时）
  previewEndTime: number;   // preview 接口结束时间（差值是接口耗时）
}

// 计算各阶段耗时
const stat = props.__duo__?.getPerformanceStat();
const bridgeTime = stat.previewStartTime - stat.pageStartTime;   // 桥耗时
const apiTime = stat.previewEndTime - stat.previewStartTime;     // 接口耗时
```
