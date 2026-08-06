# Max 审查规则

> 框架背景、生态与代码示例见 [`../context/max-context.md`](../context/max-context.md)。
> `base` 层已覆盖通用与交易基础规则；本文件只补充 Max 特有 API、跨容器差异和高频坑。
>
> 更新时间：2026.5.29

## 审查范围

- 重点关注 Max 特有 API、跨端组件和与 React/MRN 的差异
- 忽略生成的文件、锁文件、配置文件和非代码资源

## 审查规则条目（结构化）

> **等级说明**：**高**为建议阻塞合并或必须修复；**中**为建议优化或需在 PR 中说明依据；**中，参考 Lint** 为静态工具可辅助发现，AI 仅在项目无 Lint 配置或规则明显缺失时作为兜底报告。

### MAX01 组件选型优先级（Leez → MBC → 自定义）

- **等级**：中
- **描述**：Max 跨端项目应优先使用团队标准组件体系，避免重复造轮子或与设计规范不一致。
- **规则**：
  - 新代码中需要通用 UI 能力时，优先检索 **Leez**（`leez-components` 等）是否有现成组件
  - Leez 无法满足时再选用 **MBC**（如 `@mrn/mbc-components`）
  - 仅在前两者均无法满足时实现自定义组件；若本次 Diff 引入可替代 Leez/MBC 的大段自定义 UI，需在 PR 中说明选型依据
- **正例**：
```typescript
import { Button, Input } from 'leez-components'
// Leez 无合适组件时再：
import { Image } from '@mrn/mbc-components'
```
- **反例**：
```typescript
// 已有 Leez Button 仍手写一套同规格按钮组件并大范围使用
```

### MAX02 跨端差异：能力降级与检测方式

- **等级**：高
- **描述**：不同容器能力不一致时，必须有降级或分支处理；优先按「能力是否可用」判断，避免仅按平台写死分支导致维护成本过高。
- **规则**：
  - 使用某端特有 API 前，确认其他端是否有等价能力或兜底路径
  - 条件分支应能说明「为何该端需要特殊逻辑」；若仅平台判断，需评估是否可用统一能力检测替代
- **正例**：
```typescript
import { isMiniProgram, isWeb, isMRN } from '@mrn/mrn-utils'
if (isMiniProgram()) {
  // 小程序侧无某 API 时的兜底
} else {
  // 通用路径
}
```
- **反例**：
```typescript
// 调用某 API 无任何 try/catch、能力判断或文档约定的降级，导致非目标端直接异常
```

### MAX03 Hooks 依赖数组完整

- **等级**：中，参考 Lint
- **描述**：`useEffect` / `useMemo` / `useCallback` 依赖遗漏会导致陈旧闭包、重复请求或状态不同步。
- **规则**：
  - 依赖数组需包含闭包内使用的所有外部可变值；若刻意省略，须用注释写明依据（如仅挂载执行一次且已与评审对齐 ESLint 例外）
- **反例**：
```typescript
useEffect(() => {
  fetchList(filters)
}, []) // filters 变化从不重新请求
```

### MAX04 Props 与嵌套数据访问的空值防御

- **等级**：高
- **描述**：重点关注跨端 props 和接口数据的深层访问、默认值与渲染分支是否稳健。
- **规则**：
  - 对对象、数组的链式访问需具备空值防御，可使用 `?.`、入口守卫、提前返回等方式，并结合 `??` / `||` 提供合理默认（空数组、空对象等）
  - 复杂 props 建议在解构或入口处统一兜底，避免深层访问散落在渲染逻辑中
- **正例**：
```typescript
const list = props.data?.items ?? []
return list.map((item) => item?.name ?? '')
```
- **反例**：
```typescript
props.data.items.map(...) // data 或 items 可能为 undefined
```

### MAX05 网络请求：统一封装、加载态、错误与卸载取消

- **等级**：高
- **描述**：请求需走统一封装，并处理加载、错误和页面离开后的更新，避免白屏与内存泄漏。
- **规则**：
  - 使用团队约定的请求方法（如 `@mrn/mrn-request` 的 `request` 或项目封装），避免散落裸 `fetch`
  - 请求过程维护 loading / error 状态；组件卸载时应取消未完成的请求或忽略回调中的 setState
- **反例**：
```typescript
fetch('/api/x').then((r) => r.json()).then(setData) // 无 loading、无错误处理、无取消
```

### MAX06 接口响应空数据与结构防御

- **等级**：高
- **描述**：接口字段缺失或 `data` 为空时，渲染逻辑不得抛错。
- **规则**：
  - 列表类数据使用 `response?.data?.list ?? []` 等模式
  - 类型定义与运行时防御一致，避免仅 TS 层面假设非空
- **正例**：
```typescript
const list = response?.data?.list ?? []
```
- **反例**：
```typescript
const list = response.data.list // 未校验 data/list
```

### MAX07 长列表：禁止用 ScrollView 承载大数据量

- **等级**：高
- **描述**：ScrollView 一次性渲染全部子节点会导致卡顿与内存压力，跨端一致适用。
- **规则**：
  - 长列表应使用虚拟列表方案或列表组件（按容器选型），避免在 ScrollView 内 `map` 成百上千项
- **反例**：
```tsx
<ScrollView>
  {hugeList.map((item) => <Row key={item.id} {...item} />)}
</ScrollView>
```

### MAX08 样式与尺寸：跨端单位与适配

- **等级**：中
- **描述**：不同容器对样式支持不同，需避免写死仅适用于单端的魔法数。
- **规则**：
  - 宽度等布局优先相对单位（如 `100%`）或团队约定的 `px` 等工具（如 `@mrn/mrn-utils` 的 `px`）
  - 字体与间距需考虑多端可读性；若使用平台特有样式属性，需确认其他端是否有等价表现或降级
- **正例**：
```tsx
import { px } from '@mrn/mrn-utils'
<View style={{ width: '100%', paddingHorizontal: px(24) }} />
```

### MAX09 在 MRN 容器中使用 Max 能力的导入路径

- **等级**：高
- **描述**：MRN 项目中直接使用 Max API、环境判断或 Leez / Max 能力时，若未走 MRN 对应产物路径，可能出现能力判断失真或端差异异常。
- **规则**：
  - 在 MRN 容器中使用 Max 能力时，确认依赖是否提供 `lib/mrn` 等 MRN 专用入口，并按规范引入
  - 环境判断、桥接能力、跨端 API 不应默认使用 Web / 通用产物
- **正例**：
```typescript
import '@max/meituan-uni-env/lib/mrn'
import '@max/some-api/lib/mrn'
```
- **反例**：
```typescript
import { isMRN } from '@max/meituan-uni-env'
```

### MAX10 一码多端场景的小程序限制与样式差异

- **等级**：高
- **描述**：Max 一码多端不代表各端能力完全一致；小程序容器对 HOC、样式属性和层级表现存在额外限制。
- **规则**：
  - 涉及小程序侧渲染时，避免依赖小程序不支持或不稳定的 HOC 用法
  - `position: fixed`、`z-index`、字体和层叠上下文等样式能力需确认在目标端的实际表现
  - 仅在单端验证通过的交互和样式，不应默认视作多端可用
- **正例**：
```typescript
const useStickyFooter = isMiniProgram() ? false : true
```
- **反例**：
```typescript
export default withSomething(FunctionalCard) // 小程序侧未验证 HOC 兼容性
```

### MAX11 Leez 与混排文本组件的容器兼容性

- **等级**：中
- **描述**：Leez 组件、混排文本和 InlineView 在不同容器下存在细粒度差异，需确认组件组合方式、稳定 key 和事件名是否匹配目标端。
- **规则**：
  - `LeezInlineView` 等依赖内部 diff 的组件，在内容重排或节点切换场景下应保证稳定 key
  - 混排文本场景若要求 `MRNTitleText` 嵌套，需确认外层容器也满足对应约束
  - 点评等场景下若组件仅接受 `onClick`，不要只传 `onPress`
- **正例**：
```tsx
<LeezInlineView key={inlineKey} onClick={handleClick} onPress={handleClick}>
  {content}
</LeezInlineView>
```
- **反例**：
```tsx
<LeezInlineView>
  <MaxText onPress={handleClick}>{text}</MaxText>
</LeezInlineView>
```

### MAX12 安卓端样式与网络请求特殊行为

- **等级**：中
- **描述**：部分样式和网络行为在安卓端与 iOS / Web 不一致，需警惕"其他端正常、安卓端失效"。
- **规则**：
  - 安卓端如依赖阴影颜色能力，需确认是否需要 `@mrn/react-native-shadow-view` 等替代方案
  - 原生网络请求在安卓端对 POST body、更底层桥接实现等约束可能更严格，不能默认沿用 iOS 兜底行为
- **正例**：
```typescript
const requestBody = method === 'POST' ? data ?? {} : undefined
```
- **反例**：
```typescript
request({
  method: 'POST',
  data: undefined,
})
```

### MAX13 Max 组件开发不支持 `export * from` 写法

- **等级**：高
- **描述**：Max 项目中开发组件时，不支持 `export * from './index'` 的写法，会导致代码不生效，maxAPI 报混编相关错误。
- **规则**：
  - 禁止使用 `export * from '...'` 写法
  - 需先通过 `import` 导入后再具名 `export`，或使用具名 re-export
  - 合并仓库后尤其需要注意——原 npm 包构建已自动处理，合并后需手动规避
- **正例**：
```typescript
import { someUtil } from './utils'
export { someUtil }
// 或具名 re-export
export { someUtil } from './utils'
```
- **反例**：
```typescript
export * from './index' // Max 组件开发中不生效
```

### MAX14 style 数组写法需用 flattenStyle 拍平

- **等级**：高
- **描述**：Max 合并仓库后，`style={[]}` 数组形式的写法会导致样式未能正确应用，表现为组件样式异常。
- **规则**：
  - 遇到数组形式的 `style` 时，使用 `flattenStyle` 方法将样式拍平后再传递
  - 合并仓库场景下尤其注意——原 npm 包构建已自动处理，合并后需手动处理
- **正例**：
```typescript
import { flattenStyle } from '@mrn/react-native'
<View style={flattenStyle([styles.container, customStyle])} />
```
- **反例**：
```typescript
<View style={[styles.container, customStyle]} />
// 合并仓库后样式可能不生效
```

### MAX15 Leez 组件与 Leez Theme 版本必须匹配

- **等级**：中
- **描述**：Leez 组件库高版本可能直接使用了 Leez Theme 新增字段（如 `neutralColor.textColor`），若项目中 Theme 版本低于组件版本，会导致运行时访问 undefined 属性而白屏。本地运行即可发现，CR 重点关注 package.json 中版本锁定是否一致（提交者本地可能恰好 theme 版本对，但 clean install 后崩溃）。
- **规则**：
  - 升级 Leez 组件时，确认 `@leez/theme` 版本是否满足组件要求
  - 审查 `package.json` 中 Leez 相关包版本是否对齐
- **正例**：
```json
{
  "@leez/leez-button": "2.6.x",
  "@leez/theme": "2.6.x"  // 版本对齐
}
```
- **反例**：
```json
{
  "@leez/leez-button": "2.6.x",
  "@leez/theme": "2.5.x"  // 版本不匹配，button 使用了 2.6 新增的 theme token
}
```

### MAX16 setRemConfig 全局缩放必须在样式引入之前执行

- **等级**：中
- **描述**：通过 `setRemConfig` 开启全局缩放时，如果样式配置在 `setRemConfig` 之前已被 import 加载，缩放配置不会生效。
- **规则**：
  - 确保 `setRemConfig` 在应用入口最先执行，早于任何组件/样式的 import
  - 样式引入推荐使用动态 import 或按推荐方式延后加载

### MAX17 TextInput 与 TopView/slideModal 共用时的光标异常

- **等级**：中
- **描述**：`TextInput` 在 `TopView` 或 `slideModal` 中使用时，在非首/末位置添加删除字符时光标定位会错乱（前移一位）。View 或原生 Modal 中无此问题。
- **规则**：
  - 在 TopView/slideModal 内的 `TextInput`，使用 `defaultValue` 替代 `value`（受控模式）来绕过该问题
  - 如必须使用受控模式，需测试光标行为

### MAX18 KNB 与 Max Storage 互通配置

- **等级**：中
- **描述**：Max API 与 KNB 的缓存数据可以互通，但需要双方按约定配置 `level` 和 `shareConfig`，否则读取不到对方写入的数据。
- **规则**：
  - Max API 读取 KNB 设置的缓存：KNB.setStorage 时需设置 `level: 1`；Max getStorage 时设置 `_meituan.shareConfig.shared: true`
  - KNB 读取 Max API 设置的缓存：Max setStorage 时设置 `level: 0` + `_meituan.shareConfig.shared: true`
  - API 版本要求：`@max/meituan-uni-storage@1.1.1` 及以上

### MAX19 跳链拼接需使用 queryStringify 防止 undefined

- **等级**：高
- **描述**：直接使用字符串模板拼接跳链参数时，当变量为 undefined，跳链上会出现 `xx=undefined`（字符串），后端解析时将其视为有效值，产生业务风险。
- **规则**：
  - 跳链参数拼接使用统一的 queryStringify 函数，自动过滤 null/undefined
  - 禁止直接模板字符串拼接未做空值检查的参数
- **正例**：
```typescript
function queryStringify(obj: Record<string, any>): string {
  return Object.entries(obj)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${v}`)
    .join('&')
}
const url = `imeituan://path?${queryStringify({ a: val1, b: val2 })}`
```
- **反例**：
```typescript
const url = `imeituan://path?a=${val1}&b=${val2}`
// val1 或 val2 为 undefined 时，url 中出现 "a=undefined"
```

### MAX20 `@max/max` 多处引入时 type 必须置于最前

- **等级**：高
- **描述**：Web 端通过源码引入多个 `@max/max` 导出时，`@max/max-import-create-element-loader` 会在最后一个 `@max/max` 引入后自动插入 `createElement`。若 `type` 导入排在 hooks 等具名导入之后（以下列形式），会导致 `createElement` 被插入到 `type` 之前，运行时报 `createElement is undefined`。
- **规则**：
  - `import type { ... } from '@max/max'` 必须放在所有 `import { ... } from '@max/max'` 的**最上面**
  - 或将 type 和值合并为一条 import
- **正例**：
```typescript
import type { ForwardedRef } from '@max/max';
import { forwardRef, useCallback, useState, useImperativeHandle, memo, useMemo } from '@max/max';
```
- **反例**：
```typescript
import { forwardRef, useCallback, useState, useImperativeHandle, memo, useMemo } from '@max/max';
import type { ForwardedRef } from '@max/max';
// → createElement 插入位置在 type import 之前，导致 undefined 报错
```

### MAX21 小数字 toString 科学计数法问题

- **等级**：高
- **描述**：JS 中小于 1e-7 的小数调用 `toString()` 会自动转为科学计数法（如 `0.0000001.toString()` → `'1e-7'`）；Groovy/Java 中阈值为 1e-4。涉及经纬度等高精度数值时，传给后端的字符串可能不是预期格式。
- **规则**：
  - 经纬度等高精度小数转字符串时，不能直接 `.toString()` / 模板字符串拼接
  - 使用 `toFixed(N)` 或 `BigDecimal.toPlainString()` 确保不出现科学计数法
- **正例**：
```typescript
// JS 侧
const lngStr = lng.toFixed(6)

// Groovy 侧（DUO requestProps 中）
def lng = COMMON_PARAMS.location?.lng
return (lng instanceof String) ? lng : lng?.toBigDecimal()?.toPlainString()
```
- **反例**：
```typescript
const lngStr = lng.toString() // 伦敦经度 0.0000001 → '1e-7'
const url = `?lng=${lng}` // 同上
```

### MAX22 MSI API 多端返回行为差异需同时处理 success 和 fail

- **等级**：高
- **描述**：MSI 是 Max 生态的跨端基础 API（类似 KNB 但统一性更好）。同一个 MSI 方法在不同端的回调行为可能不同。如 `MSI.getCityInfo`：不开定位时，安卓和鸿蒙在 success 中返回缓存/首页城市数据；iOS 在 fail 中返回失败信息。
- **规则**：
  - 调用 MSI API 时，**必须同时处理 success 和 fail 回调**，不能假设某一端一定走 success
  - 对于可能返回缓存数据的场景（如定位未开启时返回上次缓存），需评估缓存数据是否满足业务需求
  - 不同端的返回数据结构可能也有差异，做好字段防御
- **正例**：
```typescript
MSI.getCityInfo({
  success: (res) => {
    // 安卓/鸿蒙：未开定位也可能走 success，返回缓存数据
    const cityName = res?.cityName ?? ''
    updateCity(cityName)
  },
  fail: (err) => {
    // iOS：未开定位走 fail
    // 降级为默认城市或提示用户开启定位
    updateCity(DEFAULT_CITY)
  },
})
```
- **反例**：
```typescript
MSI.getCityInfo({
  success: (res) => {
    updateCity(res.cityName) // 只处理 success，iOS 未开定位时不触发
  },
  // 未处理 fail → iOS 场景下无任何响应
})
```
