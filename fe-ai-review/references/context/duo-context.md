# DUO 上下文

识别到 DUO 技术栈时读取，作为框架背景，不作为编码规则来源。

## 协议与文件职责

DUO 是服务端驱动 UI 的方案：页面协议描述视图、数据和交互，物料组件负责具体渲染与行为。审查时区分 `protocol/` 协议源文件、出码产物和运行时接口返回的协议。

| 文件 | 职责 |
|---|---|
| `struct.groovy` | 视图树、节点属性和条件展示 |
| `logics.groovy` | 生命周期、事件和交互逻辑 |
| `dataSourceMap.groovy` / `constData.groovy` | 数据源绑定 / 页面常量 |
| `pageBuildConfig.json` | 路由、跳链参数和公共参数配置 |
| `componentsMap.json` / `dependencies.json` | 物料映射 / 物料依赖与版本 |

`node('节点名', '物料ID')` 的第二个参数对应 `componentsMap` 的 key，不是条目中的发布版本 `id`。核对节点引用时，同时查看物料映射、依赖版本及实际物料接口；逻辑节点和静态节点不渲染 UI。

## 表达式与数据来源

协议表达式使用 `{{ }}` 包裹，兼容 Groovy 2.4.17；不要套用 JavaScript 语义。属性通过 `string` / `number` / `bool` / `array` / `object` 声明类型，核对表达式返回值与物料属性契约。

- `CONST` / `PAGE_QUERY` / `COMMON_PARAMS`：页面常量、跳链参数和公共参数。
- `DATA_SOURCE` / `PREV_DATA`：数据源返回和上一轮数据。
- `NODE` / `PROPS`：节点数据和父级传入属性。
- `PAYLOAD`：update / submit 入参。

具体字段和可空性以现有协议、数据源及调用方为准。

## 生命周期与交互

`preview` 在打开页面时生成端到端协议；`update` 根据交互重新计算并返回协议；`submit` 返回数据源结果，由前端执行提交回调。

涉及更新或跨节点交互时，串联检查事件 `emit/on`、`updateBy` 绑定、`callMethod` / `notifyNodeName` 的目标及传参。判断页面是否刷新，需要核对实际响应与前端消费逻辑。

## 审查易误判点

1. **开发 Mock 与正式出码**：`duo-version.json` 的 `mockId` 用于 `duo-builder dev`，正式 `generate` 出码不固化该值；线上调试 Mock 另由调试开关和本地存储控制。仅修改配置或本地 dev 产物含 Mock 不作为线上缺陷，需有实际发布链路消费 Mock 产物等证据。
