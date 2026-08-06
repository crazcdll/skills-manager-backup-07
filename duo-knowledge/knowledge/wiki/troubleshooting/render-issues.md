# T1 · 渲染异常排查

> 覆盖范围：页面白屏、节点不渲染、样式错乱、事件不触发等前端渲染层问题的定位与修复。

---

## 快速定位流程

```
页面异常
  1. 看 getPageState()：ready? isError? errorMsg?
  2. 是引擎错误（isEngineError）还是业务错误（bizRespStatus.isError）？
  3. 打开 AppMock 查看接口响应：有 struct？有 nodeDataMap？
  4. 检查 Groovy 表达式：xIf 是否误剪枝？props 是否返回 null？
  5. 检查物料注册：componentMap/logicMap 中是否有对应 materialId？
```

---

## 1. 页面白屏 / 整页不渲染

### 1.1 引擎错误（isEngineError）

**现象**：页面显示"网络加载失败，请稍后重试~"，或 `getPageState().isError=true` 且 `errorMsg` 是引擎兜底文案。

**触发条件**（源码 `pageLifecycle/index.ts`）：

```typescript
const isEngineError = !resp || !!resp.error || !data;
```

即：接口无响应、`resp.error` 字段有值、或 `resp.data` 为空。

**排查步骤**：

1. **检查网络**：AppMock 或抓包工具查看 `duo_csdk_v` 接口是否有响应，HTTP 状态码是否 200。
2. **检查 pageId / baseUrl**：`duo.config.js` 中的 `pageId` 和 `baseUrl` 是否正确，是否指向了错误环境。
3. **检查后端日志**：后端 DUO SDK 是否抛出异常（StageEnum 任意阶段的未捕获异常都会导致 `resp.error` 有值）。
4. **检查 Groovy 语法**：`struct.groovy` 或 `constData.groovy` 中是否有语法错误，导致后端解析失败。

### 1.2 业务错误且无节点树

**现象**：`bizRespStatus.isError=true` 且 `struct` 为空数组。

**原因**：`dataSourceMap.groovy` 中配置了 `errorNoReturnStruct true`，接口返回错误码时后端不返回节点树。

**修复**：检查业务接口是否真的返回了错误，或调整 `bizRespStatus` 的判断逻辑。

### 1.3 物料 JS 加载失败（Web 端）

**现象**：Web 端白屏，控制台报 `Cannot read properties of undefined`，或 `componentMap` 中某个 key 对应的值是 `undefined`。

**原因**：`dependencies.json` 中的 S3 URL 不可访问，或 UMD bundle 加载失败。

**排查**：检查 Network 面板中 S3 URL 的请求状态，确认 `web-bundle/index.js` 是否可访问。

---

## 2. 部分节点不渲染

### 2.1 xIf 误剪枝

**现象**：某个模块在预期应该显示时不出现。

**排查**：在 AppMock 中查看接口响应的 `struct` 字段，确认该节点是否在树中。如果不在，说明 `xIf` 表达式返回了 `false`。

**常见原因**：

```groovy
// 问题：DATA_SOURCE.data?.showModule 可能是字符串 "true" 而非 boolean
xIf {{ DATA_SOURCE.data?.showModule }}

// 修复：显式转换
xIf {{ DATA_SOURCE.data?.showModule == true }}
```

```groovy
// 问题：空字符串在 Groovy 中是 falsy
xIf {{ DATA_SOURCE.data?.title }}  // title 为 "" 时节点被剪枝

// 修复：明确判断 null
xIf {{ DATA_SOURCE.data?.title != null }}
```

### 2.2 materialId 未注册

**现象**：节点在 `struct` 中存在，但页面上不渲染，控制台无报错。

**原因**：`componentMap` 或 `logicMap` 中没有该节点对应的 `materialId`。

**修复**：在 `componentsMap.json` 中添加物料映射，并重新执行 `yarn generate`。

### 2.3 xFor 数据源为空

**现象**：列表容器（LIST_CONTAINER）不渲染任何子节点。

**排查**：检查 `xFor` 表达式的数据源是否为空数组或 null：

```groovy
// struct.groovy 中
xFor {{ CONST.list }}  // CONST.list 为 [] 时不渲染任何子节点
```

---

## 3. 样式异常

### 3.1 styles 表达式返回 null

**现象**：组件样式丢失，或样式不符合预期。

**原因**：`style` 块中的表达式返回了 `null`，引擎会忽略该样式字段。

```groovy
// 问题：DATA_SOURCE.data?.bgColor 可能为 null
style('style') {
  string('backgroundColor') {{ DATA_SOURCE.data?.bgColor }}
}

// 修复：提供默认值
style('style') {
  string('backgroundColor') {{ DATA_SOURCE.data?.bgColor ?: '#FFFFFF' }}
}
```

### 3.2 MRN 与 Web 样式差异

**现象**：MRN 端样式正常，Web 端样式错乱（或反之）。

**常见差异**：
- MRN 中 `flexDirection` 默认值是 `column`，Web 中是 `row`
- MRN 中数值单位是 dp（无需写 `px`），Web 中需要 `px`
- MRN 中 `position: 'absolute'` 需要父容器有 `position: 'relative'`，Web 中默认行为不同

---

## 4. 事件不触发

### 4.1 callMethod 目标节点不存在

**现象**：点击按钮后无响应，控制台无报错。

**原因**：`on` 块中 `callMethod` 的目标 `nodeName` 在当前渲染树中不存在（可能被 `xIf` 剪枝）。

**排查**：确认目标节点在当前状态下是否在 `struct` 中，以及 `nodeName` 拼写是否正确。

### 4.2 事件被锁

**现象**：快速点击时，第二次点击无响应。

**原因**：`propConfig` 中配置了 `lock: true`，或 `emit` 时传入了 `lock: true`，请求进行中时事件被锁。这是正常行为，如果需要允许并发，去掉 `lock: true` 配置。

### 4.3 透传参数映射错误

**现象**：事件触发后，后端收到的 `PAYLOAD` 中缺少预期字段。

**排查**：检查 `transparentArg` 的 `from`/`to` 映射是否正确：

```groovy
on('onChange') {
  callMethod('Lifecycle1', 'update')
  // from: 事件回调参数的字段名
  // to: 映射到 PAYLOAD 中的字段名
  transparentArg('value', 'payload.newValue')
}
```

---

## 5. 表达式执行错误

**现象**：页面渲染但某些 props 值异常（为 null 或默认值），Raptor 上报 `expressionErrorList` 有记录。

**原因**：Groovy 表达式执行时抛出异常，引擎会捕获并记录到 `warnInfo.expressionErrorList`，该字段的 props 会被置为 null。

**排查**：AppMock 查看接口响应中的 `warnInfo.expressionErrorList` 字段，包含 `errorReason`（错误原因）、`field`（哪个 prop）、`expression`（表达式内容）。

**常见原因**：

```groovy
// NullPointerException：没有用 ?. 安全访问
string('title') {{ DATA_SOURCE.data.shopInfo.name }}
// 修复
string('title') {{ DATA_SOURCE.data?.shopInfo?.name }}
```

```groovy
// GroovyCastException：类型不匹配
number('price') {{ DATA_SOURCE.data?.price }}  // price 是字符串 "9.9"
// 修复
number('price') {{ DF.toNumber(DATA_SOURCE.data?.price) }}
```

---

## 附：常用调试方法

```typescript
// 在组件内获取页面状态
const pageState = props.__duo__?.getPageState();
console.log('ready:', pageState?.ready);
console.log('isError:', pageState?.isError);
console.log('errorMsg:', pageState?.errorMsg);

// 获取性能数据
const perf = props.__duo__?.getPerformanceStat();
console.log('桥耗时(ms):', perf?.previewStartTime - perf?.pageStartTime);
console.log('接口耗时(ms):', perf?.previewEndTime - perf?.previewStartTime);
```
