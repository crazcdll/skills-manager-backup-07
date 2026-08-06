# T2 · 数据异常排查

> 覆盖范围：数据不更新、PAYLOAD/PREV_DATA 取值错误、currentData 映射异常、bizRespStatus 判断失效等数据层问题。

---

## 快速定位流程

```
数据异常
  ↓
1. 确认生命周期：是 preview 还是 update/submit？
  ↓
2. AppMock 查看 bizReq（接口入参）是否符合预期
  ↓
3. AppMock 查看 bizRes（接口出参）是否正确
  ↓
4. 检查 currentData 映射：PREV_DATA 是否正确提取了数据
  ↓
5. 检查节点 props：DATA_SOURCE / PREV_DATA / CONST 取值路径是否正确
```

---

## 1. 数据不更新（update 后页面无变化）

### 1.1 isRequestArg 未配置

**现象**：用户操作后触发 update，但后端收到的入参中缺少前端状态字段，导致响应数据不变。

**原因**：`propConfig.isRequestArg` 未设置为 `true`，该 prop 的当前值不会随 update 请求发给后端。

```groovy
// ❌ 问题：count 变化后不会发给后端
node('StepperModule1', '5') {
  props {
    number('count') {{ PREV_DATA?.quantity ?: 1 }}
  }
  propConfig('count') {
    updateBy 'onChange'
    // 缺少 isRequestArg true
  }
}

// ✅ 修复
propConfig('count') {
  updateBy 'onChange'
  isRequestArg true
}
```

**验证**：AppMock 查看 `bizReq` 中的 `nodeDataMap` 字段，确认对应节点的 props 是否包含该字段。

### 1.2 update 时 setPageState 未调用

**现象**：update 请求成功（`onSuccess` 触发），但页面 UI 没有刷新。

**原因**（源码 `pageLifecycle/index.ts`）：update 时只有 `isError=false` 才会调用 `setPageState` 更新渲染树：
```typescript
if (!isError) {
  setPageState({ ready: true, isError, errorMsg, data });
} else if (errorMsg && errorToast) {
  Toast.open({ content: errorMsg, closeAll: true });
}
```

如果 `bizRespStatus.isError=true`，页面不会重新渲染（这是设计行为，避免错误态覆盖正常态）。

**排查**：检查 `bizRespStatus.isError` 的判断逻辑是否误判为 true。

### 1.3 请求被取消（onCancel 触发）

**现象**：操作后无响应，`onCancel` 回调被触发，`cancelReasonType` 为 `Locked` 或 `DebouncePending`。

**原因**：
- `Locked`：其他请求正在进行中，且配置了 `lock: true`
- `DebouncePending`：防抖期间被新的请求覆盖
- `Invalid`：先发出的请求比后发出的响应更晚，被丢弃

**这通常是正常行为**。如果不期望被取消，检查 `lock` 和 `debounceDelay` 配置。

---

## 2. PAYLOAD 取值错误

### 2.1 preview 时使用 PAYLOAD

**现象**：preview 时接口入参中某个字段为空或默认值，但预期应该有值。

**原因**：`requestProps` 中直接使用了 `PAYLOAD.xxx`，但 preview 时 `PAYLOAD` 为空对象 `{}`。

```groovy
// ❌ 问题：preview 时 PAYLOAD.skuId 为 null
object('productParam') {{
  [skuId: PAYLOAD.skuId]
}}

// ✅ 修复：preview 时从 PAGE_QUERY 取初始值
object('productParam') {{
  def skuId = PAYLOAD.skuId ?: PREV_DATA?.productInfoVO?.skuId ?: PAGE_QUERY.skuid
  [skuId: skuId]
}}
```

### 2.2 submit 时 PAYLOAD 已清空

**现象**：submit 时接口入参中缺少 update 阶段积累的状态。

**原因**：submit 时 `PAYLOAD` 只包含 submit 触发时传入的 payload，不包含之前 update 积累的状态。应从 `PREV_DATA` 读取。

```groovy
// ❌ 问题：submit 时 PAYLOAD.selectedSkuId 可能为空
object('submitParam') {{
  [skuId: PAYLOAD.selectedSkuId]
}}

// ✅ 修复：submit 时从 PREV_DATA 读取稳定状态
object('submitParam') {{
  if (COMMON_PARAMS.isSubmit) {
    return [skuId: PREV_DATA?.productInfoVO?.skuId]
  }
  [skuId: PAYLOAD.selectedSkuId ?: PREV_DATA?.productInfoVO?.skuId]
}}
```

---

## 3. PREV_DATA 取值错误

### 3.1 preview 时 PREV_DATA 为空

**现象**：preview 时某个字段取值为 null，但 `currentData` 中明明有映射。

**原因**：preview 时 `PREV_DATA` 是空对象 `{}`，`currentData` 的结果要等本次 preview 响应后才写入 `PREV_DATA`，供下次 update 使用。

**规律**：
- `requestProps` 中：preview 时 `PREV_DATA` 为空，update 时 `PREV_DATA` 是上次 `currentData` 的结果
- 节点 `props` 中：`PREV_DATA` 始终是本次请求 `currentData` 的结果（已计算完毕）

### 3.2 currentData 映射路径错误

**现象**：`PREV_DATA.xxx` 为 null，但接口响应中有该字段。

**排查**：AppMock 查看 `bizRes`（接口原始响应），对照 `currentData` 中的映射路径：

```groovy
// 接口响应：{ "data": { "productInfoVO": { "skuId": "123" } } }

currentData {
  // ❌ 路径错误：少了 .data
  object('productInfoVO') {{ DATA_SOURCE?.productInfoVO }}

  // ✅ 正确路径
  object('productInfoVO') {{ DATA_SOURCE.data?.productInfoVO }}
}
```

**注意**：`DATA_SOURCE` 是接口的完整响应对象（含 `code`、`data`、`message` 等），业务数据通常在 `DATA_SOURCE.data` 下。

### 3.3 出参误用 NODE.X.PROPS

**现象**：节点 props 中某个字段的值是前端状态而非服务端返回的稳定值，导致数据不一致。

**原因**：在出参（节点 props）中使用了 `NODE.X.PROPS`，而 `NODE.X.PROPS` 是前端当前渲染帧的状态，不稳定。

```groovy
// ❌ 问题：出参使用 NODE.X.PROPS，值不稳定
string('totalPrice') {{ NODE.StepperModule1?.props?.count * PREV_DATA?.productInfoVO?.price }}

// ✅ 修复：出参使用 PREV_DATA（服务端返回的稳定数据）
string('totalPrice') {{ PREV_DATA?.totalPrice }}
```

`NODE.X.PROPS` 只应用于 `requestProps`（入参），读取其他节点的当前状态传给后端。

---

## 4. bizRespStatus 判断异常

### 4.1 isError 误判

**现象**：接口正常返回数据，但页面显示错误态，或 `onFail` 被触发。

**排查**：检查 `bizRespStatus.isError` 的表达式：

```groovy
// ❌ 问题：code 为字符串 "0" 时，!= 0 为 true（Groovy 中字符串和数字比较）
bool('isError') {{ DATA_SOURCE?.code != 0 }}

// ✅ 修复：转换类型后比较
bool('isError') {{ DF.toNumber(DATA_SOURCE?.code) != 0 }}
// 或
bool('isError') {{ DATA_SOURCE?.code?.toString() != '0' }}
```

### 4.2 errorNoReturnStruct 导致页面空白

**现象**：接口返回错误码时，页面完全空白（不显示错误提示）。

**原因**：配置了 `errorNoReturnStruct true`，后端不返回节点树，但前端没有处理错误态 UI。

**修复**：在 `pageContainer` 物料中处理 `isError` 状态，或去掉 `errorNoReturnStruct true` 让后端返回错误态节点树。

---

## 5. 数据竞态问题

### 5.1 快速操作导致数据错乱

**现象**：快速连续操作后，页面显示的数据与最后一次操作不对应。

**原因**：多个 update 请求并发，先发出的请求比后发出的响应更晚返回。

**引擎处理**（源码 `pageLifecycle/index.ts`）：
```typescript
requestIdRef.current += 1;
const requestId = requestIdRef.current;
// ...
if (requestId !== requestIdRef.current) {
  callbacks.onCancel && callbacks.onCancel('Invalid');
  return;  // 丢弃已失效的响应
}
```

引擎已内置处理，`onCancel('Invalid')` 触发时说明该响应被正确丢弃，**这是正常行为**。

### 5.2 防抖配置不当

**现象**：输入框每次输入都触发 update，导致请求过于频繁。

**修复**：在 `emit` 时配置 `debounceDelay`：
```typescript
props.__duo__?.emit('update', {
  payload: { keyword: value },
  debounceDelay: 300,  // 300ms 防抖
});
```

或在 `on` 块中配置（通过 `propConfig.updateBy` 触发时）：
```groovy
propConfig('keyword') {
  updateBy 'onChange'
  isRequestArg true
}
// 在 emit 时由物料组件传入 debounceDelay
```

---

## 附：AppMock 查看数据的方法

连接 AppMock 后，DUO 端到端接口响应中包含：

| 字段 | 说明 |
|------|------|
| `bizReq` | 实际业务接口入参（`requestProps` 计算结果） |
| `bizRes` | 实际业务接口出参（原始响应） |
| `warnInfo.expressionErrorList` | Groovy 表达式执行错误列表 |
| `data.bizRespStatus` | 业务状态（isError/errorMsg） |
| `data.struct` | 节点树（xIf/xFor 展开后） |
| `data.nodeDataMap` | 各节点的 props/styles 计算结果 |

不连 AppMock 时，在 request header 中添加 `from-appmock: true` 也可以获取 `bizReq`/`bizRes`。
