# A · DUO 整体概览

> DUO（Dynamic Unified Output）是美团交易前端的低代码页面引擎，通过"搭建协议驱动渲染"的方式，让页面逻辑和 UI 配置从代码中剥离，由配置平台管理，实现多端（Web/MRN/小程序）统一输出。

---

## 1. 核心定位

DUO 解决的核心问题是：**交易页面高度相似但定制需求多，纯手写代码维护成本高**。它的解法是：

- 页面结构（视图树 + 逻辑节点）由配置平台可视化搭建，存储为 JSON 协议
- 业务数据流（入参/出参/表达式）用 Groovy 脚本描述，在后端执行
- 前端引擎（duo-engine）解析协议，动态渲染物料组件
- 物料（Material）是可复用的 UI/逻辑单元，由前端 RD 开发并注册到平台

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    DUO 配置平台                          │
│  (duo.sankuai.com)  可视化搭建 → 生成 PageProtocol JSON │
└───────────────────────────┬─────────────────────────────┘
                            │ 存储到 Git 仓库
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 DUO SDK                          │
│  读取 PageProtocol → 执行 Groovy 表达式 → 返回渲染数据  │
└───────────────────────────┬─────────────────────────────┘
                            │ preview/update/submit 接口
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  前端 duo-engine                         │
│  解析 RenderResponseData → 渲染物料组件树               │
│  Web(H5) / MRN(React Native) / 小程序(Max)              │
└─────────────────────────────────────────────────────────┘
```

## 3. 核心概念速查


| 概念                     | 说明                                                                             |
| -------------------------- | ---------------------------------------------------------------------------------- |
| **PageProtocol**         | 页面搭建协议，JSON 格式，描述页面的完整配置（视图树、数据源、物料映射等）        |
| **Material（物料）**     | 可复用的 UI 组件或逻辑单元，分 lowCode（Yooz 搭建）和 proCode（源码 npm 包）两种 |
| **DataSource（数据源）** | 后端业务接口的抽象，配置入参 Groovy 表达式和出参业务状态判断                     |
| **preview**              | 页面首次加载时触发的接口，返回初始渲染数据                                       |
| **update**               | 用户交互触发的局部刷新接口，携带变更数据                                         |
| **submit**               | 表单提交接口，触发业务写操作                                                     |
| **check**                | 前端校验接口，不触发写操作，用于表单校验                                         |
| **Groovy 表达式**        | 在后端执行的数据处理脚本，用于入参构造、出参映射、显示规则等                     |
| **COMMON_PARAMS**        | 系统环境参数（用户信息、设备信息、位置等），由引擎在请求前收集                   |
| **PAGE_QUERY**           | 页面跳链参数，从 URL 或 MRN 路由参数中获取                                       |
| **PREV_DATA**            | 上一次接口返回的数据，在出参表达式中引用                                         |
| **PAYLOAD**              | update/submit 时携带的临时数据，仅在当次请求中有效                               |
| **PROPS**                | 节点保存的状态，需在配置平台勾选"保存状态"后才可用                               |
| **NODE.X.PROPS**         | 读取其他节点当前 props 值的语法，仅在接口入参时使用                                  |
| **CONST**                | 常量数据，在`dynamicDataConfig.constData` 中配置                                 |

## 4. 数据流全景

一次完整的 preview 请求数据流：

```
1. 前端引擎收集 pageQuery + commonParams
2. 发起 POST /preview，携带 RenderRequest
3. 后端 DUO SDK 读取 PageProtocol
4. 执行 DataSource.reqProps 中的 Groovy 表达式，构造业务接口入参
5. 调用业务接口，获取 bizRes
6. 执行 DataSource.currentData 中的 Groovy 表达式，映射出参
7. 执行各节点 props 表达式，计算节点属性值
8. 执行 displayRule 表达式，决定节点显示/隐藏
9. 返回 RenderResponseData（struct + logics + nodeDataMap）
10. 前端引擎按 struct 树递归渲染物料组件
```

update 流程与 preview 基本相同，区别在于携带了 `payload`（用户操作数据）和 `updatePropMap`（本次变更的字段）。

## 5. 多端产物

DUO 页面通过 duo-builder 构建，输出三种产物：

- **Web（H5）**：标准 React 应用，部署到 CDN，通过 KNB 容器加载
- **MRN**：React Native bundle，通过 MRN 容器加载，路径格式 `rn_{biz}_{name}&{component}`
- **小程序（Max）**：微信小程序产物，通过 `yarn start:wx` 或 `yarn dev:wx` 构建

三端共用同一套 PageProtocol 和物料代码（物料基于 Max 跨端框架开发），由 duo-builder 在构建时按目标平台差异化处理。

## 6. 仓库职责分工


| 仓库                             | 职责                                                                                                                                   |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `duo-core`                       | 核心包集合：duo-protocol（类型定义）、duo-engine（前端渲染引擎）、duo-builder（构建工具）、groovy-lite/groovy-runtime（Groovy 执行）等 |
| `duo-page`                       | 页面工程模板，每个 DUO 页面的代码存储在此仓库的子目录中                                                                                |
| `duo-backend-sdk`                | 后端 Java SDK，负责解析 PageProtocol、执行 Groovy、调用业务接口                                                                        |
| `yooz-materials`                 | lowCode 物料库，基于 Yooz 搭建平台开发                                                                                                 |
| `biz-cross-transaction-material` | 跨业务线通用物料，DUO 页面基础物料存储仓库                                                                                             |
| `duo_platform`                   | DUO 配置平台前端                                                                                                                       |

## 7. 关键约束

- 页面的 FEDO 项目必须建立在各自业务方向的研发组里，DUO 研发组仅供 平台 RD 测试
- 禁止往 `release` 和 `master` 分支直接 push 代码
- Web 部署必须使用 Talos 2.0 工作流
- 自测必须覆盖 Web 和 MRN 两种产物
