# MRN (Meituan React Native) 指引

## 1. MRN 基础

### 1.1 版本与文档

- **React Native 版本**：MRN 基于官方 React Native **0.63** 版本
- **文档查询**：查询文档时请使用 https://reactnative-archive-august-2023.netlify.app/docs/0.63/getting-started
- **组件引用**：使用 React Native 组件时，请从 `@mrn/react-native` 中引用

### 1.2 常用模块引用

- **React Native 组件**（`@mrn/react-native`）：标准 RN 组件
- **React Navigation**（`@mrn/react-navigation`）：MRN 项目使用 **2.x** 版本
- **工具库**（`@mrn/mrn-utils`）：页面路由、通用方法
- **MSI**（`@mtfe/msi-mrn`）：客户端原生能力

---

## 2. 页面与导航

### 2.1 页面关闭

```typescript
// 关闭当前容器
import { pageRouterClose } from '@mrn/mrn-utils'

pageRouterClose()
```

- **关闭时机**：确认页面关闭是用户主动行为，避免在异步回调中误关闭
- **回调处理**：关闭页面后确保不执行后续 setState

---

### 2.2 页面跳转

```typescript
// 打开新容器/mrn/webview/native 页面
import { openUrl } from '@mrn/mrn-utils'

// 不带回调
openUrl(url)

// 带回调
openUrl(url).then((data) => {
    console.warn(data)
})
```

- **URL 格式**：确认使用的是 MRN 协议（`imeituan://`）或 H5 URL
- **回调安全**：组件卸载后需防止调用已卸载组件的 setState
- **参数传递**：复杂参数建议 JSON 序列化后传递

---

## 3. 客户端原生能力 (MSI)

### 3.1 常见 MSI API

- **`msi.showActionSheet`**：显示操作菜单；回调中需处理用户取消情况
- **`msi.getLocation`**：获取定位；需处理权限拒绝场景
- **`msi.uploadImage`**：图片上传；需处理选择取消

### 3.2 回调安全

```typescript
// 错误 - 组件卸载后可能崩溃
msi.showActionSheet({
    itemList: ['选项1', '选项2'],
    success: (e) => {
        this.setState({ selected: e.tapIndex }) // 组件可能已卸载
    }
})

// 正确 - 需在调用前判断组件状态
msi.showActionSheet({
    itemList: ['选项1', '选项2'],
    success: (e) => {
        if (!this._isMounted) return
        this.setState({ selected: e.tapIndex })
    }
})
```

---

## 4. React Navigation (MRN 2.x)

路由使用不同项目可能有差异，这里仅介绍常用模式。以项目中实际使用为准。

### 4.1 版本差异

- **版本**：MRN 使用 **2.x** 版本，不同于主流 5.x/6.x
- **API 差异**：部分 API 可能在 2.x 与新版不兼容
- **文档参考**：查询文档请使用 https://reactnavigation.org/docs/2.x/getting-started
- **引用方式**：从 `@mrn/react-navigation` 引用

### 4.2 常见导航模式

```typescript
// 2.x 常用 API
import { NavigationActions } from '@mrn/react-navigation'

// 导航到页面
const navigateAction = NavigationActions.navigate({
    routeName: 'Profile',
    params: { userId: '123' }
})
this.props.navigation.dispatch(navigateAction)

// 返回
this.props.navigation.goBack()
```

- **参数类型**：避免在导航参数中传递函数/类实例等不可序列化值
- **参数守卫**：使用 `route.params?.x` 访问，防御 params 为 undefined

---

## 5. 数据与状态

### 5.1 Props 传递

- **可选链**：从父组件接收的复杂对象必须使用可选链：`props.data?.list?.map()`
- **默认值**：为复杂 props 提供默认值或空值守卫
- **buildIn 组件**：注意 `buildIn: "static"` 组件的 props 可能为空

### 5.2 状态更新

- **渲染期间更新**：绝不在 render 方法中调用 setState
- **异步安全**：异步回调中需判断组件是否已卸载
- **竞态条件**：避免在未完成时发起重复请求

---

## 6. 网络请求

### 6.1 请求封装

```typescript
// MRN 项目通常有统一请求封装，这里仅举例
import { postRequest, getRequest } from '@mtfe/mrn-request'

const response = yield call(postRequest, requestConfig)
```

- **错误处理**：需处理网络异常、接口报错
- **加载状态**：请求发起和结束需更新加载状态
- **取消场景**：页面卸载时需取消进行中的请求

### 6.2 响应处理

```typescript
// 常见响应结构
interface Response<T> {
    code: number
    data: T
    msg?: string
}

// 空数据防御
const list = response?.data?.list || []
```

---

## 7. 性能与可维护性

- **长列表**：使用 FlatList 或 SectionList，避免 ScrollView 加载大量数据
- **图片优化**：使用 `defaultSource` 提供占位图
- **布局稳定性**：条件渲染可能导致布局抖动
- **组件拆分**：避免过大的单文件组件
