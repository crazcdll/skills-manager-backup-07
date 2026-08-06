# MRN 审查规则

> 版本、模块引用与 API 示例见 [`../context/mrn-context.md`](../context/mrn-context.md)。
> `base` 层已覆盖通用与交易基础规则；本文件只补充 MRN 特有 API、容器差异和高频坑。
>
> 更新时间：2026.5.29

## 审查范围

- 重点关注 MRN 特有 API 和与标准 React Native 的差异
- 忽略生成的文件、锁文件、配置文件和非代码资源

## 审查规则

> **等级说明**：**高**为建议阻塞合并或必须修复；**中**为建议优化或需在 PR 中说明依据；**中，参考 Lint** 为静态工具可辅助发现，AI 仅在项目无 Lint 配置或规则明显缺失时作为兜底报告。

### MRN01 React Native 组件从 `@mrn/react-native` 引用

- **等级**：中，参考 Lint
- **描述**：MRN 运行时与官方 `react-native` 包不一致，直接引用官方包可能导致类型、原生模块或打包错误。
- **规则**：
  - 所有 RN 内置组件与 API 均从 `@mrn/react-native` 引入，禁止从 `react-native` 直接 import（除非项目明确配置 alias 且与规范一致）
- **正例**：
```typescript
import { View, Text, Image } from '@mrn/react-native'
```
- **反例**：
```typescript
import { View } from 'react-native'
```

### MRN02 导航使用 `@mrn/react-navigation` 2.x API

- **等级**：中，参考 Lint
- **描述**：MRN 固定使用 React Navigation 2.x，与 5.x/6.x API 不兼容，误用会导致导航失败或类型错误。
- **规则**：
  - 导航相关 import 必须来自 `@mrn/react-navigation`
  - 使用 2.x 文档中的 API（如 `NavigationActions`、`dispatch`、`goBack`），不得混用新版 `createNativeStackNavigator` 等写法
- **正例**：
```typescript
import { NavigationActions } from '@mrn/react-navigation'
```
- **反例**：
```typescript
import { useNavigation } from '@react-navigation/native' // 与 MRN 2.x 栈不一致时
```

### MRN03 页面关闭与关页后状态更新

- **等级**：高
- **描述**：误关页面或在页面已销毁后更新状态会导致崩溃或告警。
- **规则**：
  - 关闭当前容器应使用 `pageRouterClose`（`@mrn/mrn-utils`），且关闭时机应对应明确用户意图，避免在不确定的异步回调中自动关页
  - 关页或组件卸载后，不得再执行 `setState` / 未守卫的 store 更新
- **正例**：
```typescript
import { pageRouterClose } from '@mrn/mrn-utils'
// 用户点击确认后
pageRouterClose()
```
- **反例**：
```typescript
setTimeout(() => pageRouterClose(), 0) // 无产品语义、易被其他逻辑触发
// 关页后仍在 request 回调里 setState
```

### MRN04 `openUrl` 跳转：协议、白名单、参数与回调安全

- **等级**：高
- **描述**：错误 URL、未申请白名单的外链或卸载后回调更新 UI 都可能引发线上问题。
- **规则**：
  - 跳转链接须为约定的 MRN 协议（如 `imeituan://`）或合法 H5 URL
  - 跳转外链（尤其非美团域名）前，确认是否已申请白名单或存在明确平台兜底
  - `openUrl` 的 `then`/回调中更新组件状态时，需判断组件仍挂载（或取消/忽略）
  - 复杂参数优先序列化传递，避免传递无法序列化的对象
- **正例**：
```typescript
import { openUrl } from '@mrn/mrn-utils'
openUrl(url).then((data) => {
  if (!mountedRef.current) return
  // 安全更新
})
```
- **反例**：
```typescript
openUrl('http://') // 非约定或非法地址
openUrl(url).then(() => setState(...)) // 无卸载判断
```

### MRN05 MSI 异步回调：权限、取消与卸载安全

- **等级**：高
- **描述**：MSI 为原生异步能力，用户取消、权限拒绝与组件卸载均需处理。
- **规则**：
  - `success`/`fail`/`complete` 回调中更新 UI 前，确认组件仍挂载（类组件可用挂载标记，函数组件用 ref / AbortController 等约定）
  - 定位、相册等需处理权限拒绝；ActionSheet、选图等需处理用户取消，避免当作错误路径误关页面
- **正例**：
```typescript
msi.showActionSheet({
  itemList: ['A', 'B'],
  success: (e) => {
    if (!mountedRef.current) return
    setSelected(e.tapIndex)
  },
})
```
- **反例**：
```typescript
success: (e) => setState({ x: e }) // 无挂载判断，卸载后可能崩溃
```

### MRN06 导航参数：可序列化与空值安全访问

- **等级**：高
- **描述**：导航参数会经序列化传递，非法类型或缺省访问会导致异常。
- **规则**：
  - `params` 中禁止传递函数、类实例等不可序列化数据
  - 读取参数需做空值防御（如 `route.params?.key` 或等价守卫），并提供默认
- **正例**：
```typescript
const userId = route.params?.userId ?? ''
```
- **反例**：
```typescript
NavigationActions.navigate({ routeName: 'X', params: { onOk: () => {} } })
const id = route.params.userId // params 可能为 undefined
```

### MRN07 禁止 render 阶段 setState；异步与竞态

- **等级**：高
- **描述**：在 render 中触发 setState 会造成死循环或异常；重复请求与竞态会导致错误数据展示。
- **规则**：
  - 绝不在 `render` 或其同步调用链中调用 `setState`
  - 异步结果返回前若依赖已变化（如路由、筛选条件），应丢弃过期响应或使用请求序号 / AbortController
- **反例**：
```typescript
render() {
  if (this.state.loading) {
    this.setState({ loading: false }) // 禁止在 render 中 setState
  }
  return null
}
```

### MRN08 网络请求：统一封装、加载错误、卸载取消

- **等级**：高
- **描述**：请求需走统一封装，并处理页面离开后的取消或卸载动作。
- **规则**：
  - 使用 `postRequest` / `getRequest` 等统一方法，完整处理网络错误与业务 `code`
  - 页面离开时取消请求或忽略回调中的状态更新
- **反例**：
```typescript
// 无 loading、无错误提示、无取消
yield call(postRequest, config)
```

### MRN09 长列表与图片：FlatList/SectionList 与占位

- **等级**：高
- **描述**：ScrollView + 大列表会卡顿；图片无占位影响体验。
- **规则**：
  - 长列表使用 `FlatList` 或 `SectionList`，避免 ScrollView 嵌套大量子项
  - `Image` 在可行时使用 `defaultSource` 等占位策略
- **反例**：
```typescript
<ScrollView>
  {items.map((i) => <Row key={i.id} />)}
</ScrollView>
```

### MRN10 全局共享内存、缓存与事件监听清理

- **等级**：高
- **描述**：MRN 页面销毁后不会自动清理共享内存、缓存和全局监听；缺少清理容易产生脏数据和重复触发。
- **规则**：
  - 写入 `globalSharedMemory`、`cacheList` 或模块级缓存时，需在页面退出或组件卸载时显式清理
  - `DeviceEventEmitter.addListener`、原生事件订阅、定时器等资源必须在 cleanup / `componentWillUnmount` 中释放
- **正例**：
```typescript
useEffect(() => {
  const subscription = DeviceEventEmitter.addListener('refresh', handleRefresh)
  globalSharedMemory.orderDraft = draft
  return () => {
    subscription.remove()
    delete globalSharedMemory.orderDraft
    cacheList.delete(pageKey)
  }
}, [draft, pageKey])
```
- **反例**：
```typescript
componentDidMount() {
  DeviceEventEmitter.addListener('refresh', this.handleRefresh)
  globalSharedMemory.orderDraft = this.state.draft
}
```

### MRN11 跳链 Query 参数类型归一与透明页参数约束

- **等级**：高
- **描述**：MRN 跳链 Query 参数经常在字符串化后丢失类型；透明页等特殊参数若传值不规范，可能导致关页、回参或容器行为异常。
- **规则**：
  - 跳链参数中的布尔值、数字、枚举值在下游读取时需显式做类型转换
  - `mrn_transparent` 等容器关键参数需遵循既有约束，不要把 `1/0`、`'1'/'0'` 当作布尔值等价使用
- **正例**：
```typescript
const isTransparent = query?.mrn_transparent === 'true'
const pageIndex = Number(query?.pageIndex ?? 0)
```
- **反例**：
```typescript
const isTransparent = query?.mrn_transparent === 1
const pageIndex = query?.pageIndex + 1
```

### MRN12 地图、定位与原生能力的多端差异确认

- **等级**：中
- **描述**：地图定位、坐标转换和原生能力在不同端和容器下存在额外前置条件，需确认坐标系和端差异兜底。
- **规则**：
  - 涉及地图、定位时，确认坐标系（如 `GCJ02` / `WGS84`）是否统一；`KNB.getLocation` 默认类型美团/点评 App 均为 GCJ02
  - 涉及相机、定位、支付等原生能力时，需评估 iOS / Android / HarmonyOS 的兼容差异
  - 明确指定经纬度类型，避免 GCJ02 和 WGS84 混用（两者第三位小数不同，约 100m 误差）
- **正例**：
```typescript
const targetLocation = convertWGS84ToGCJ02(rawLocation)
KNB.getLocation({ type: 'gcj02' }) // 显式指定类型
```
- **反例**：
```typescript
mapView.moveTo(userLocation) // 未确认坐标系
KNB.getLocation({}) // 依赖默认值，不同端可能不一致
```

### MRN13 安卓端 request body 禁止多维嵌套数组

- **等级**：高
- **描述**：安卓端 MRN 底层网络库对 POST body 中的多维数组存在 bug，会导致数据丢失或格式错误。
- **规则**：
  - POST body 中**禁止**出现二维及以上嵌套数组
  - 多维数组需打平为一维，或增加对象嵌套层级
- **正例**：
```typescript
// 将多维数组通过对象嵌套绕开
const body = [
  { guestList: [{ name: '张三' }, { name: '李四' }] },
  { guestList: [{ name: '王五' }] },
]
```
- **反例**：
```typescript
// 安卓端会丢失数据
const body = [
  [{ name: '张三' }, { name: '李四' }],
  [{ name: '王五' }],
]
```

### MRN14 安卓端预请求参数整数精度问题

- **等级**：高
- **描述**：安卓端 MRN 预请求场景下，整数类型参数会出现精度丢失；如果预请求与代码请求参数不一致，会导致发出第二个请求（预请求命中失败）。
- **规则**：
  - 预请求接口的 number 类型参数，与后端约定直接使用 string 类型
  - 代码中将整数参数 `+ ''` 转为字符串传递
- **正例**：
```typescript
const params = { poiId: String(poiId), count: String(count) }
```
- **反例**：
```typescript
const params = { poiId: 123456, count: 10 } // 安卓预请求可能精度丢失
```

### MRN15 点评 iOS 透明容器关页需用 KNB.closePage

- **等级**：高
- **描述**：点评 iOS 的 MRN 透明容器存在页面堆栈 bug：在 KNB 容器中打开透明容器后使用 `navigateBack` 会白屏或异常关页。多个透明容器叠加时 `KNB.closePage` 可能同时关闭多层。
- **规则**：
  - 点评 iOS 透明容器场景中，关页**必须使用** `@mrn/mrn-knb` 的 `KNB.closePage`，不能使用 Max `navigateBack`
  - 关页前应判断页面堆栈（使用 `@max/meituan-uni-getPages`），避免将整个 MRN 堆栈关闭
  - 多个透明容器叠加场景需特别测试关页行为
- **正例**：
```typescript
import KNB from '@mrn/mrn-knb'
import { getPages } from '@max/meituan-uni-getPages'
// 判断堆栈后安全关页
KNB.closePage()
```
- **反例**：
```typescript
import { navigateBack } from '@max/meituan-uni-router'
navigateBack() // 点评 iOS 透明容器下会白屏
```

### MRN16 版控不可完全依赖 Diva

- **等级**：中
- **描述**：点评 Google Play 渠道的 version_code 与国内商店不一致，导致 Diva 始终下发最新 bundle，MRN 版控下界不生效。旧版 App 会拉到新 bundle，新端能力在旧容器中不存在会抛异常。
- **规则**：
  - 版控**不能只依赖 Diva 下界**，代码中需额外判断端版本或能力可用性
  - 使用新端能力时加 try-catch 或能力探测，防止低版本 App 加载到高版本 bundle 后崩溃
- **正例**：
```typescript
import { versionCompare } from './utils'
if (versionCompare(appVersion, '12.0.0') >= 0) {
  // 使用新能力
} else {
  // 降级
}
```

### MRN17 fontWeight 必须为字符串类型

- **等级**：中
- **描述**：MRN 旧架构开发模式下，安卓端 `fontWeight` 若为数字类型会直接红屏（`StyleSheet.create` + `Object.freeze` 导致类型转换失败）。
- **规则**：
  - `fontWeight` 统一使用字符串类型（如 `'700'`、`'bold'`），不使用数字
- **正例**：
```typescript
const styles = StyleSheet.create({
  title: { fontWeight: '700' },
})
```
- **反例**：
```typescript
const styles = StyleSheet.create({
  title: { fontWeight: 700 }, // 安卓开发模式红屏
})
```

### MRN18 非全面屏底部安全区域遮挡

- **等级**：中
- **描述**：使用绝对定位的底部栏在非全面屏设备上可能被系统导航栏遮挡。
- **规则**：
  - 底部固定元素优先使用 flex 布局而非绝对定位
  - 若必须绝对定位，需考虑 `getSafeAreaMarginBottom()` 等安全区域偏移
  - 测试需覆盖全面屏和非全面屏设备

### MRN19 浮层路由加 mrn_navSetBanned=true

- **等级**：中
- **描述**：先后打开两个浮层时，关闭上层浮层可能触发前页导航栏展示，导致底部浮层无法点击关闭按钮。
- **规则**：
  - 浮层路由参数中加上 `&mrn_navSetBanned=true`，防止关闭浮层时触发导航栏状态变更

### MRN20 MRN 页面预热时机

- **等级**：中
- **描述**：在页面一挂载时就给后续页面预热，会导致当前页面可用的 MRN 引擎被消耗，包加载耗时增加，C 指标下降。
- **规则**：
  - 页面预热不要在 `componentDidMount` / `useEffect([], [])` 中立即执行
  - 延迟 1~2 秒再调用下一个页面的预热，避免抢占当前页面的引擎资源

### MRN21 MRN 中打开网页链接需用 Linking.openURL

- **等级**：中
- **描述**：`@mrn/mrn-utils` 的 `openUrl` 底层是 `NativeModules.MRNPageRouter.openUrlWithResult`，适用于 bundle 间跳转，不能用于打开外部 HTTP 链接。
- **规则**：
  - 打开外部 HTTP/HTTPS 网页链接，使用 `@mrn/react-native` 的 `Linking.openURL`
  - `openUrl` 仅用于 `imeituan://` 等 MRN 协议跳转
- **正例**：
```typescript
import { Linking } from '@mrn/react-native'
Linking.openURL('https://example.com')
```
- **反例**：
```typescript
import { openUrl } from '@mrn/mrn-utils'
openUrl('https://example.com') // 无法正常打开网页
```
