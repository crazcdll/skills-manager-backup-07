# DUO 协议统一语言

## DUO 协议文件结构（子文件）

| 文件 | 扩展名 | 说明 | 生成顺序 |
|------|-------|------|---------|
| pageBuildConfig | .json | 页面静态配置：baseUrl、pageUrl、pageQuery、commonParams | 1 |
| dataSourceMap | .groovy | 数据源配置：reqProps、currentData、bizRespStatus/submitBizRespStatus | 2 |
| constData | .groovy | 页面常量：可在 struct 中复用，MUST_NOT 用于 reqProps | 3 |
| struct | .groovy | 组件树结构：node/props/style/events/slot/xIf | 4 |
| logics | .groovy | 页面逻辑：生命周期回调（preview/update/submit）、事件链路 | 5 |
| dependencies | .json | 依赖声明：proCode 物料的 npm 包列表 | 6 |
| componentsMap | .json | 物料注册表：materialId → npm/id/version/web | 6 |
| ohDependencies | .json | 鸿蒙专属依赖声明（可选） | 6 |
| scripts/buildCustom | .js | 构建定制脚本（可选） | 7 |
| scripts/mrnConfigCustom | .js | MRN 配置（可选） | 7 |
| scripts/firstScreenModulePaths | .json | 首屏模块路径（可选） | 7 |
| nodes/{NodeName} | .groovy | 节点独立拆分（可选，仅当 `buildConfig { splitFile true }` 时） | 8 |

## 核心名词

| 名词 | 定义 | 示例 |
|------|------|------|
| materialId | 物料在 DUO 平台的全局唯一标识（componentsMap 的 key） | `"37"` = @max/leez-card |
| id | 物料在 Yooz 平台发布的版本 id（componentsMap 的 value） | `"135"` = @max/leez-card@2.3.39 |
| nodeName | 节点在页面内的唯一标识（MUST 页面内唯一） | `DealInfoCard` |
| label | 节点的显示名称 | `'商品信息卡片'` |
| nodeType | 节点类型 | `NORMAL_MODULE`（UI）、`HANDLER_MODULE`（逻辑）、`LIST_CONTAINER`（列表） |
| slot | 插槽，用于嵌套子节点 | renderTop/renderContent/renderBottom |
| xIf | 展示条件（Boolean Groovy 表达式） | `xIf {{ !!DATA_SOURCE?.data?.list }}` |
| propConfig | 双向绑定配置 | `propConfig('value') { updateBy 'onChange'; isRequestArg true }` |
| Groovy 表达式 | 数据绑定（`{{ }}` 双花括号包裹，Groovy 2.4.17 执行） | `{{ DATA_SOURCE?.data?.title ?: '' }}` |

## 表达式变量速查

| 变量 | 含义 | 使用场景 | 限制 |
|------|------|---------|------|
| `PAGE_QUERY` | 页面 URL 参数 | 通用 | — |
| `COMMON_PARAMS` | 公共参数（用户/定位/系统/缓存） | 通用 | — |
| `DATA_SOURCE` | 数据源返回结果 | 组件 props | MUST_NOT 用于入参 |
| `CONST` | constData 中定义的常量 | struct 表达式 | CONST 间不可互引；MUST_NOT 用于 reqProps |
| `PREV_DATA` | 上次数据源结果 | 入参配置 | 只能在 reqProps 中使用 |
| `NODE.xxx.props` | 节点保存的状态 | 入参配置 | 建议只在入参中使用 |
| `PAYLOAD` | update 携带数据 | 入参配置 | 只在当次 update 生效 |
