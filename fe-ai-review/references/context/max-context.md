# Max (美团到店跨端框架) 指引

## 1. Max 基础介绍

### 1.1 框架介绍

- **定义**：Max 是美团到店跨端解决方案
- **支持容器**：MRN、Web 应用、微信小程序
- **语法标准**：基于 React 标准，支持 Hooks、Context 等 80%+ React API

### 1.2 生态体系

- **Max App**：配套研发框架，支持 TypeScript、Scss 等工程能力
- **MBC**：跨端基础组件集
- **MSI**：跨端标准 API
- **Leez**：到店设计规范组件库
- **Leez 动效库**：到店设计规范动效

---

## 2.组件规范

### 2.1 组件优先级

- 🥇 **第一选择 — Leez 组件**：到店设计规范组件，优先使用
- 🥈 **第二选择 — MBC 组件**：跨端基础组件，Leez 没有满足功能要求时使用
- 🥉 **第三选择 — 自定义组件**：前两者都无法满足时的兜底方案

```typescript
// 正确示例：优先使用 Leez 组件
import { Button, Input } from 'leez-components'

// MBC 组件使用场景：Leez 没有符合功能要求的组件时
import { Image, Video } from '@mrn/mbc-components'
```

- **组件选型**：先查 Leez 组件库，再查 MBC，最后考虑自定义
- **组件替换**：现有自定义组件如果 Leez/MBC 有替代品，建议迁移

---

## 3. 跨端兼容性

### 3.1 API 兼容性

- **React Hooks**：支持 useState、useEffect、useContext 等 80%+ API
- **生命周期**：使用 useEffect 替代类组件生命周期
- **状态管理**：支持 React Context

### 3.2 平台差异处理

```typescript
// 条件渲染处理平台差异
import { isMiniProgram, isWeb, isMRN } from '@mrn/mrn-utils'

// 平台特定逻辑
if (isMiniProgram()) {
    // 微信小程序特定逻辑
} else if (isWeb()) {
    // Web 特定逻辑
}
```

- **API 降级**：不支持的 API 需提供降级方案
- **样式差异**：注意不同容器的样式渲染差异
- **能力检测**：使用能力检测而非平台检测

---

## 4. 数据与状态

### 4.1 状态管理

- **Hooks 依赖**：useEffect/useMemo/useCallback 依赖数组需完整
- **状态持久化**：需考虑页面生命周期和状态恢复
- **全局状态**：跨页面状态使用 Context 或状态管理库

### 4.2 Props 传递

- **可选链**：复杂对象属性必须使用可选链
- **默认值**：为复杂 props 提供默认值
- **类型定义**：优先使用 TypeScript 类型定义

---

## 5. 网络请求

### 5.1 请求封装

```typescript
// Max 项目通常有统一请求封装
import { request } from '@mrn/mrn-request'

const response = await request({
    url: '/api/xxx',
    method: 'GET'
})
```

- **错误处理**：需处理网络异常、接口报错
- **加载状态**：请求需更新加载状态
- **取消场景**：页面卸载时取消进行中请求

### 5.2 响应处理

```typescript
// 空数据防御
const list = response?.data?.list || []

// 类型安全
interface ApiResponse<T> {
    code: number
    data: T
    msg?: string
}
```

---

## 6. 性能与可维护性

- **长列表**：使用虚拟列表组件，避免 ScrollView 加载大量数据
- **图片优化**：使用懒加载和适当的图片尺寸
- **组件拆分**：避免过大的单文件组件，保持组件单一职责
- **代码复用**：跨端代码优先抽取到共享模块

---

## 7. 样式规范

### 7.1 样式方案

- **CSS-in-JS**：推荐使用，样式作用域天然隔离
- **Scss**：Max App 支持，需配置
- **内联样式**：简单样式或动态样式

### 7.2 响应式设计

```typescript
// 使用相对单位
<View style={{ width: '100%' }}>

// 或使用样式常量
import { px } from '@mrn/mrn-utils'
<View style={{ width: px(750) }}>
```

- **尺寸单位**：使用相对单位或工具函数转换
- **字体大小**：考虑不同设备的可读性
