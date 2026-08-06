# 交易前端 CR 增量规则

> 交易前端增量规则（通用规则已合并入 general-rules，本文件保留交易领域特有规则），共 8 条。
> 适用文件类型：`*.js, *.jsx, *.ts, *.tsx, *.vue`
> 更新时间：2026.4.23
>
> **等级说明**：
> - **高**：线上发生时必定造成白屏等严重后果。建议阻塞合并、必须修复。对应 P0
> - **中**：线上发生时有可能影响用户，或导致代码质量严重劣化。建议优化或要求用户说明依据，否则不予放行。对应 P1-P2
> - **低**：对代码质量或长期维护带来一定负面影响。预期优先由 Lint 工具发现，AI 仅在项目无 Lint 配置或 Lint 规则明显缺失时作为兜底报告，不作为主要输出重点。对应 P2-P3

---

## 目录

- [一、逻辑正确性](#一逻辑正确性)
- [二、React/Hooks 规范](#二reacthooks-规范)
- [三、联调与上线](#三联调与上线)
- [四、上下游影响与交付](#四上下游影响与交付)

---

## 一、逻辑正确性

### T02 金额、时间与本地化处理
- **等级**：中
- **描述**：金额、时间和本地化相关逻辑应避免隐式假设，优先使用最小单位整数、明确时区语义，并关注本地化排序和大小写处理差异。
- **关注点**：
  - 金额计算是否直接使用浮点数参与业务逻辑
  - 时间解析是否依赖不稳定的字符串格式或设备本地时区
  - 服务端时间、客户端时间、展示时间是否语义一致
  - 排序、大小写比较是否受本地化差异影响
- **正例**：
```ts
const totalAmountInCent = unitPriceInCent * count;
const displayTime = dayjs.utc(serverTime).local().format('YYYY-MM-DD HH:mm:ss');
```
- **反例**：
```ts
const totalAmount = 19.9 * count;
const displayTime = new Date('2026-04-15 12:00:00');
```

### T03 路由、跳链与 Query 参数类型归一
- **等级**：高
- **描述**：路由参数、跳链参数、URL Query、容器透传参数在跨页面和跨端传递过程中经常发生类型丢失，审查时应重点关注字符串化后的布尔值、数字和枚举是否被显式归一。
- **关注点**：
  - 上游传递的 `boolean`、`number`、枚举值在下游读取后，是否仍按原始类型参与判断
  - 是否直接拿 `'true'`、`'false'`、`'0'`、`'1'` 等字符串与布尔值或数字比较
  - 透明页、弹窗页、埋点透传等特殊参数是否有明确的取值约束
- **正例**：
```ts
const fromOffline = query?.fromOffline === 'true';
const pageSize = Number(query?.pageSize ?? 20);
const isTransparent = query?.mrn_transparent === 'true';
```
- **反例**：
```ts
if (query.fromOffline === true) {
  // Query 中的值实际是字符串，条件永远不成立
}
```

### T04 数值计算、序列化与存储前校验
- **等级**：高
- **描述**：金额、数量、坐标、分页等数值在计算、序列化、缓存和请求传输前应校验 `NaN` / `Infinity` / 非法字符串，避免静默变成 `null` 或触发后续逻辑异常。
- **关注点**：
  - `Number()`、算术运算、坐标转换、金额换算后是否可能得到 `NaN` / `Infinity`
  - 写入 storage、JSON、埋点、接口请求前是否做 `isNaN` / `isFinite` 校验
  - 默认值逻辑是否把非法数值继续透传到下游
- **正例**：
```ts
const lng = Number(query?.lng);
const safeLng = Number.isFinite(lng) ? lng : undefined;
const payload = Number.isFinite(totalAmount) ? { totalAmount } : {};
```
- **反例**：
```ts
const totalAmount = Number(query.amount) * count;
localStorage.setItem('draft', JSON.stringify({ totalAmount })); // totalAmount 可能是 NaN
```

---

## 二、React/Hooks 规范

> 下列以 React Hooks / JSX 为主表述；如涉及 Vue 等栈请按组合式 API、生命周期钩子的等价语义对照。

### T05 全局状态与缓存需有明确生命周期
- **等级**：中
- **描述**：跨页面共享状态、模块级缓存、本地缓存和容器缓存都应有明确归属、失效策略和清理时机，避免脏数据长期残留。
- **关注点**：
  - 是否把临时态长期挂在全局对象、模块变量或容器缓存中
  - 页面退出、组件销毁、用户切换后是否需要清理缓存
  - 缓存是否有过期策略、容量约束和敏感信息保护
  - 是否依赖隐式状态透传导致行为不可预测
- **正例**：
```ts
cache.set(cacheKey, data, { ttl: 5 * 60 * 1000 });
return () => {
  cache.delete(pageKey);
};
```
- **反例**：
```ts
globalState.tempDraft = draft;
localStorage.setItem('draft', JSON.stringify(draft));
```

### T06 长列表与大资源场景的渲染成本控制
- **等级**：中
- **描述**：长列表、大图和高频更新场景容易造成卡顿、白屏或状态错位，审查时应关注渲染量、稳定 key 和资源尺寸是否受控。
- **关注点**：
  - 长列表是否一次性渲染全部节点，缺少分页、虚拟化或增量渲染
  - 列表 key 是否稳定，数据重排时是否可能导致状态错位
  - 图片、富媒体或大对象是否明显超出展示尺寸或首屏承载能力
  - 高频更新场景是否把不参与渲染的数据也推入渲染层
- **正例**：
```ts
const visibleList = list.slice(0, pageSize);
return visibleList.map((item) => <Row key={item.id} item={item} />);
```
- **反例**：
```ts
return hugeList.map((item, index) => <Row key={index} item={item} />);
```

---

## 三、联调与上线

### T07 请求参数体积与传输方式
- **等级**：中
- **描述**：大型 Query、超长 URL、过大的请求体或请求头在真实链路中可能触发 413/414/431 等问题，审查时应关注参数组织方式是否稳定可控。
- **关注点**：
  - 是否把大量业务参数、列表数据或 JSON 字符串直接拼进 URL / 跳链
  - GET 请求参数是否可能超过网关或容器限制
  - Header / Cookie / Body 是否可能膨胀到异常体积
  - 大对象是否应改为 POST body、缓存引用或短链标识传递
- **正例**：
```ts
await request({
  url: '/api/order/confirm',
  method: 'POST',
  data: { skuIds, selectedCoupons },
});
```
- **反例**：
```ts
location.href = `/confirm?payload=${encodeURIComponent(JSON.stringify(hugePayload))}`;
```

---

## 四、上下游影响与交付

### T08 上下游影响与回归风险
- **等级**：高
- **描述**：修改公共代码、导出接口、类型定义、共享组件或底层逻辑时，必须评估上下游影响范围，确认使用方是否需要同步变更、是否需要回归关联功能。
- **关注点**：
  - 导出函数、组件、类型、常量的签名变更是否影响现有调用方
  - 公共组件 props 变更（新增必填、删除、类型变化）是否已通知使用方
  - 类型定义修改是否需要同步更新下游的类型收窄或类型守卫
  - 底层工具函数、请求封装、状态管理逻辑变更是否需要回归依赖模块
  - 是否需要在 PR 描述或工作项中标注影响范围和回归建议
- **正例**：
```ts
// 新增可选参数，保持向后兼容
function fetchUser(id: string, options?: { includeDeleted?: boolean }) {}

// PR 描述中标注影响范围
// > 影响范围：UserCard、UserList、ProfilePage
// > 回归建议：验证用户头像、昵称展示正常
```
- **反例**：
```ts
// 删除参数但未通知使用方
function fetchUser(id: string) {} // 旧版有 options 参数
// 使用方 fetchUser(id, options) 调用将静默失败或抛异常
```

### T09 API 契约一致性
- **等级**：中
- **描述**：前端请求调用应与后端接口文档或类型定义保持一致，避免字段名、类型、必填性、枚举值等不匹配。
- **关注点**：
  - 请求参数字段名、类型是否与接口定义一致
  - 响应数据字段访问是否与接口返回结构一致
  - 枚举值、状态码是否与后端定义对齐
  - 可选字段是否在类型定义中正确标记，避免遗漏空值处理
  - 接口版本升级后是否同步更新前端调用
- **正例**：
```ts
// 类型定义与接口文档一致
interface OrderDetailResponse {
  code: number;
  data: {
    orderId: string;
    status: 'pending' | 'paid' | 'cancelled';
    amount: number;
  };
}
```
- **反例**：
```ts
// 字段名与接口不一致
const orderId = response.data.order_id; // 接口返回的是 orderId
// 枚举值未对齐
if (status === 'PENDING') {} // 后端实际返回 'pending'
```
