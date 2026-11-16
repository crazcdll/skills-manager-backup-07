# DUO 代码仓库地图

> 快速定位：当你需要深入代码时，先看这里找到对应仓库和路径，再去读代码。
> 所有路径均相对于各仓库根目录（克隆后的本地路径因人而异）。
> 如需克隆，仓库地址见下方「仓库清单」。

---

## 仓库清单


| 仓库名                           | Git 地址                                                           | 职责简述                                        |
| ---------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------- |
| `duo-core`                       | `ssh://git@git.sankuai.com/nibfe/duo-core.git`                     | 前端核心（引擎/协议/Groovy/构建工具），Monorepo |
| `duo-backend-sdk`                | `ssh://git@git.sankuai.com/hui/duo-backend-sdk.git`                | Java 后端 SDK（协议解析/Groovy 执行）           |
| `duo-canvas`                     | `ssh://git@git.sankuai.com/nibfe/duo-canvas.git`                   | 搭建平台可视化画布                              |
| `duo-cli`                        | `ssh://git@git.sankuai.com/nibfe/duo-cli.git`                      | 开发者工具链（`duo` 命令）                      |
| `duo-page`                       | `ssh://git@git.sankuai.com/dfe/duo-page.git`                       | 页面构建模板，调试页面壳                        |
| `yooz-materials`                 | `ssh://git@git.sankuai.com/meis/yooz-materials.git`                | 到餐业务物料库（100+ 包）                       |
| `yooz-atomic-material`           | `ssh://git@git.sankuai.com/meis/yooz-atomic-material.git`          | 原子 UI 组件库（40+ 包）                        |
| `biz-cross-transaction-material` | `ssh://git@git.sankuai.com/dfe/biz-cross-transaction-material.git` | 跨业务通用物料（35 包）                         |

---

## 仓库全景与职责分工

```
duo-cli                        ← 开发者工具链（创建/发布/文档生成）
    ↓ 调用
duo-core/packages/duo-builder  ← 构建工具（dev/generate 命令）
    ↓ 依赖
duo-core/packages/duo-protocol ← 协议类型定义（核心数据结构）
    ↓ 被依赖
duo-core/packages/duo-engine   ← 运行时引擎（渲染/生命周期/事件）
    ↓ 运行时加载
yooz-atomic-material           ← 原子 UI 组件（Max/MRN/Web 跨端）
biz-cross-transaction-material ← 跨业务通用物料（布局/事件/工具）
yooz-materials                 ← 到餐业务物料（提单/订单/支付等）
    ↓ 打包进
duo-page                       ← 最终页面 bundle（通过 duo-builder 构建）
    ↓ 服务端解析
duo-backend-sdk                ← Java 后端 SDK（协议解析/Groovy 执行）
    ↓ 调试预览
duo-canvas                     ← 搭建平台画布（可视化编辑器）
```

---

## 功能 → 实际路径速查


| 当你需要…                                | 去哪个仓库 / 哪个路径                                                           |
| ------------------------------------------- | --------------------------------------------------------------------------------- |
| 理解页面生命周期（preview/update/submit） | `duo-core` → `packages/duo-engine/src/page/pageLifecycle/index.ts`             |
| 理解组件如何被渲染                        | `duo-core` → `packages/duo-engine/src/page/RenderTreeNode/index.tsx`           |
| 理解渲染树遍历逻辑                        | `duo-core` → `packages/duo-engine/src/page/RenderTree.tsx`                     |
| 理解节点 props 如何计算（表达式求值）     | `duo-core` → `packages/duo-engine/src/page/RenderTreeNode/useNodeProps.ts`     |
| 理解事件系统（emit/useOn）                | `duo-core` → `packages/duo-engine/src/page/eventBus.ts` + `src/utils/event.ts` |
| 理解逻辑模块事件分发                      | `duo-core` → `packages/duo-engine/src/page/handleLogic.ts`                     |
| 理解全局状态/数据管理                     | `duo-core` → `packages/duo-engine/src/page/globalData.ts`                      |
| 理解 HTTP 数据源请求                      | `duo-core` → `packages/duo-engine/src/datasource/index.ts`                     |
| 理解 Groovy 解析与执行                    | `duo-core` → `packages/groovy-lite/src/evaluator/index.ts`                     |
| 理解 Groovy → JS 转换                    | `duo-core` → `packages/duo-expression-transform/src/duoPropsToJs/index.ts`     |
| 理解协议 ↔ Groovy 互转                   | `duo-core` → `packages/duo-protocol-transform/src/transformer.ts`              |
| 理解物料类型定义                          | `duo-core` → `packages/duo-protocol/src/material.ts`                           |
| 理解物料注册（构建时）                    | `duo-core` → `packages/duo-builder/src/services/initMaterials.ts`              |
| 理解生命周期协议类型                      | `duo-core` → `packages/duo-protocol/src/lifecycle.ts`                          |
| 理解 DF.xxx 内置函数                      | `duo-core` → `packages/groovy-runtime/src/functions/`                          |
| 理解监控/错误上报                         | `duo-core` → `packages/duo-owl/src/`                                           |
| 理解后端协议解析流水线                    | `duo-backend-sdk` → `data-engine/src/.../parse/stage/`（18 个 stage）          |
| 理解后端 Groovy 变量注入                  | `duo-backend-sdk` → `data-engine/src/.../groovy/DUOBinding.java`               |
| 新建物料包                                | `duo-cli` → `src/commands/component/new/`                                      |
| 发布物料到 yooz                           | `duo-cli` → `src/commands/component/yooz/yoozPublishProcode/`                  |
| 生成组件文档                              | `duo-cli` → `src/commands/docgen/`                                             |
| 查看原子 UI 组件实现                      | `yooz-atomic-material` → `packages/max-*/` 或 `packages/common-*/`             |
| 查看业务物料实现                          | `yooz-materials` → `packages/group-submit-*/` 等                               |
| 查看跨业务通用物料                        | `biz-cross-transaction-material` → `packages/common-event-*/` 等               |

---

## 各仓库详细结构

### duo-core（Monorepo，核心）

**Git：** `ssh://git@git.sankuai.com/nibfe/duo-core.git`
**npm 包名前缀：** `@meishi/`

```
<duo-core 根目录>/packages/
├── duo-engine/                    # 运行时引擎（@meishi/duo-engine v2.1.37）
│   └── src/
│       ├── index.tsx              # 引擎入口，导出 DuoPage 组件
│       ├── types.ts               # GlobalData / DuoPageState 等核心类型
│       ├── page/
│       │   ├── index.tsx          # 页面主组件（Home）
│       │   ├── RenderTree.tsx     # 渲染树（遍历 nodes 递归渲染）
│       │   ├── RenderTreeNode/
│       │   │   ├── index.tsx      # 单节点渲染器（核心）
│       │   │   ├── helper.tsx     # 节点渲染辅助
│       │   │   └── useNodeProps.ts # 节点 props 计算（表达式求值）
│       │   ├── pageLifecycle/
│       │   │   ├── index.ts       # 生命周期管理（preview/update/submit）
│       │   │   ├── prefetchRequest.ts
│       │   │   ├── requestNodeDataMap.ts
│       │   │   ├── handlePreviewCallback.ts
│       │   │   ├── report.ts      # 性能上报
│       │   │   └── types.ts
│       │   ├── eventBus.ts        # 事件系统（emit/useOn）
│       │   ├── handleLogic.ts     # 逻辑模块事件监听与分发
│       │   ├── globalData.ts      # 全局状态管理（GlobalDataMap）
│       │   └── hooks/
│       │       ├── validate.ts
│       │       └── validateQuery.ts
│       ├── datasource/
│       │   ├── index.ts           # DataSource 类（HTTP 请求封装）
│       │   └── handleMinifyHttpResponse.ts
│       └── utils/
│           ├── event.ts           # createEvent 事件工厂
│           ├── getset.ts          # 深路径 get/set
│           └── monitor.ts         # 监控上报工具
│
├── duo-protocol/                  # 协议类型定义（@meishi/duo-protocol v2.0.45）
│   └── src/
│       ├── lifecycle.ts           # 生命周期事件类型（preview/update/submit/check）
│       ├── material.ts            # 物料类型（Material/MaterialConfig）
│       ├── datasource.ts          # 数据源类型
│       ├── fieldConfig.ts         # 字段配置类型
│       ├── page/
│       │   ├── index.ts           # 页面协议类型
│       │   ├── pageNode.ts        # 页面节点类型（RenderNode）
│       │   ├── dataSourceConfig.ts
│       │   ├── dataExpression.ts  # 数据表达式类型
│       │   └── pageBuildConfig.ts
│       └── render/
│           ├── index.ts           # 渲染请求/响应类型
│           ├── renderNodeData.ts  # 节点数据类型
│           └── commonParams.ts
│
├── duo-protocol-transform/        # 协议 ↔ Groovy 互转（@meishi/duo-protocol-transform v1.2.3）
│   └── src/
│       ├── transformer.ts         # 转换主入口
│       ├── from/                  # Groovy → 协议（反向解析）
│       │   ├── structFromGroovy.ts
│       │   ├── constFromGroovy.ts
│       │   └── dataSourceMapFromGroovy.ts
│       ├── to/                    # 协议 → Groovy（正向生成）
│       │   ├── structToGroovy.ts
│       │   ├── constToGroovy.ts
│       │   └── dataSourceMapToGroovy.ts
│       └── groovy/                # Groovy 词法/语法解析
│           ├── tokenize.ts / parse.ts
│           ├── evaluate.ts
│           └── fromGroovy.ts
│
├── duo-expression-transform/      # 表达式转换（@meishi/duo-expression-transform v1.0.4）
│   └── src/
│       ├── duoPropsToJs/index.ts  # Groovy 表达式 → JS 代码
│       ├── dataSourceToJs/index.ts # 数据源表达式 → JS
│       ├── dataSourceToPn/        # 数据源表达式 → PN（预请求格式）
│       │   ├── index.ts
│       │   ├── jsToPn/            # JS AST → PN 格式
│       │   └── optimizeAst/       # AST 优化（死代码消除）
│       └── utils/
│           ├── getVarsGroovy.ts   # 提取 Groovy 变量
│           └── getVarsJs.ts
│
├── groovy-lite/                   # 前端 Groovy 解析器（@meishi/groovy-lite v1.1.6）
│   └── src/
│       ├── groovyLite.ts          # 解析器主入口
│       ├── tokenizer/index.ts     # 词法分析
│       ├── parser/index.ts        # 语法分析（生成 AST）
│       ├── evaluator/index.ts     # AST 求值执行
│       ├── jsTransformer/index.ts # Groovy AST → JS AST 转换
│       └── traverse/index.ts     # AST 遍历工具
│
├── groovy-runtime/                # Groovy 运行时函数库（@meishi/groovy-runtime）
│   └── src/
│       ├── index.ts               # 运行时函数注册
│       └── functions/             # DF.xxx 内置函数实现
│           ├── DF.ts / list.ts / map.ts
│           ├── string.ts / number.ts / Math.ts
│           └── set.ts
│
├── duo-builder/                   # 构建工具 CLI（@meishi/duo-builder v3.1.93）
│   └── src/
│       ├── main.ts                # CLI 主入口
│       ├── commands/
│       │   ├── dev/index.ts       # dev 命令（本地调试）
│       │   └── generate/index.ts  # generate 命令（出码）
│       ├── services/
│       │   ├── loadProtocol.ts    # 拉取协议
│       │   ├── loadMaterials.ts   # 加载物料
│       │   ├── initMaterials.ts   # 物料分类（视图/逻辑/内置）
│       │   ├── yoozComponent.ts   # YOOZ 组件处理
│       │   └── yoozLogic.ts       # YOOZ 逻辑处理
│       └── generator/src/page/
│           ├── materialMap.mrn.tsx.ts   # MRN 物料注册表生成
│           ├── materialMap.weapp.tsx.ts # 小程序物料注册表生成
│           └── materialMap.web.tsx.ts   # Web 物料注册表生成
│
├── duo-owl/                       # 监控/错误上报（@meishi/duo-owl）
│   └── src/
│       ├── owl/owl.ts             # OWL 监控核心
│       ├── error/manager.ts       # 错误管理
│       ├── metric/manager.ts      # 指标管理
│       └── owlConfig/             # 多端配置（mrn/weapp/web）
│
├── duo-debug-panel/               # 调试面板（AppMock/锁版本）
├── duo-loader/                    # 物料加载器
└── mrn-oh-better-cli/             # MRN 鸿蒙 CLI 工具
```

---

### duo-backend-sdk（Maven 多模块，Java）

**Git：** `ssh://git@git.sankuai.com/hui/duo-backend-sdk.git`

```
<duo-backend-sdk 根目录>/
├── data-engine/                   # 核心引擎模块
│   └── src/main/java/com/sankuai/duo/backend/sdk/
│       ├── UnifiedController.java         # 统一控制器（核心入口）
│       ├── UnifiedControllerV2.java
│       ├── UnifiedProtocolParser.java     # 协议解析器
│       ├── UnifiedProtocolParserV2.java
│       ├── DUOProcessContext.java         # 请求上下文
│       ├── ExpressionDataResolver.java    # 表达式数据解析
│       ├── groovy/
│       │   └── DUOBinding.java            # Groovy 绑定（变量注入）
│       ├── parse/stage/                   # 协议解析各阶段（18 个 stage）
│       ├── protocol/                      # 协议模型（PageProtocol/PageNode）
│       ├── response/                      # 响应模型（RenderNode/NodeData）
│       └── util/
└── data-management/               # 协议版本管理模块
    └── src/main/java/.../management/utils/
        ├── ProtocolConverter.java
        └── ProtocolVersionConverter.java
```

---

### duo-canvas（MRN 应用，可视化画布）

**Git：** `ssh://git@git.sankuai.com/nibfe/duo-canvas.git`

```
<duo-canvas 根目录>/canvas/src/
├── index.tsx                      # 画布入口
├── init.ts                        # 初始化
├── app_mrn.tsx / app.ts           # MRN 应用入口
└── Home/
    ├── index.tsx                  # DUO 1.0 画布主页面
    ├── duo.tsx                    # DUO 渲染集成
    ├── hooks.ts / service.tsx
    ├── component/render/
    │   ├── Render.tsx
    │   └── ErrorCom.tsx
    └── Duo2/                      # DUO 2.0 画布
        ├── index.tsx
        ├── hooks.ts / service.tsx
        └── component/render/
            ├── Render.tsx
            └── ErrorCom.tsx
```

---

### duo-cli（开发者工具链，`duo` 命令）

**Git：** `ssh://git@git.sankuai.com/nibfe/duo-cli.git`
**npm 包名：** `@meishi/duo-cli` v0.4.46

```
<duo-cli 根目录>/src/
├── index.ts                       # CLI 入口（commander 注册）
├── commands/
│   ├── component/
│   │   ├── new/                   # duo new-pkg（新建物料包）
│   │   ├── publish/               # duo publish-pkg（发布物料）
│   │   └── yooz/
│   │       ├── login/             # YOOZ SSO 登录
│   │       ├── publishJsBundle/   # 发布 JS Bundle
│   │       ├── yoozPublishProcode/ # ProCode 物料发布（v1/v2/v3）
│   │       ├── workflow/          # 发布工作流
│   │       └── utils/
│   │           ├── atomicMaterial/ # 原子物料 CRUD
│   │           └── buildUmd/      # UMD 构建
│   ├── docgen/                    # duo doc-gen（组件文档生成）
│   │   ├── parser/                # 源码解析
│   │   └── typedocParser/         # TypeDoc 解析
│   └── project/
│       ├── init/                  # duo init（初始化项目）
│       ├── start/                 # duo start（启动开发）
│       ├── preview/               # duo preview
│       └── copyAndWatch/          # 文件监听复制
├── lingyu/                        # 灵玉平台 API（物料注册/空间管理）
│   ├── createComponent.ts
│   ├── updateComponent.ts
│   └── ...
└── utils/
```

---

### duo-page（页面 bundle 模板）

**Git：** `ssh://git@git.sankuai.com/dfe/duo-page.git`

```
<duo-page 根目录>/
└── page-latest/
    ├── duo.config.js              # DUO 构建配置
    ├── package.json               # 依赖（含 @meishi/duo-builder）
    └── scripts/                   # 构建脚本
```

**关键环境变量：**


| 变量                        | 说明                         |
| ----------------------------- | ------------------------------ |
| `DUO_PAGE_ID`               | 页面 ID                      |
| `DUO_PAGE_PROTOCOL_ID`      | 协议 ID                      |
| `DUO_PAGE_PROTOCOL_VERSION` | 协议版本                     |
| `DUO_PROTOCOL_ENV`          | 协议环境（prod/test/泳道名） |

---

### yooz-materials（到餐业务物料库，100+ 包）

**Git：** `ssh://git@git.sankuai.com/meis/yooz-materials.git`

```
<yooz-materials 根目录>/packages/
├── group-submit-*/        # 团购提单（底部栏/数据容器/商品/风控等）
├── group-order-detail-*/  # 团购订单详情
├── food-*/                # 外卖（购物车/拼团/群订单）
├── gc-*/                  # 综合频道
├── pay-result-*/          # 支付结果页
├── order-detail-*/        # 订单详情
├── biz-*/                 # 通用业务组件（地址选择/富文本等）
├── common-duo-lifecycle/  # DUO 生命周期物料
├── common-duo-build-in-lifecycle/ # DUO 内置生命周期
└── util-*/                # 工具包（上报/图片/键盘/存储等）
```

---

### yooz-atomic-material（原子 UI 组件库，40+ 包）

**Git：** `ssh://git@git.sankuai.com/meis/yooz-atomic-material.git`

```
<yooz-atomic-material 根目录>/packages/
├── max-*/                 # Max 跨端基础组件（button/text/view/image/scrollView/recyclerview 等）
├── leez-*/                # Leez 组件封装（blur-view 等）
└── common-*/              # 通用业务原子组件
    ├── common-rich-text/  # 富文本（MRN/Web 双实现）
    ├── common-count-down/ # 倒计时
    ├── common-bubble-tip/ # 气泡提示
    ├── common-phone-verify/ # 手机验证（mrn/weapp/web 三端）
    └── common-text-ellipsis/ # 文本省略（三端）
```

---

### biz-cross-transaction-material（跨业务通用物料，35 包）

**Git：** `ssh://git@git.sankuai.com/dfe/biz-cross-transaction-material.git`

```
<biz-cross-transaction-material 根目录>/packages/
├── common-layout-*/       # 布局物料（左右/上下/滑动布局）
├── common-ele-*/          # 元素物料（标题/列表/分割线/时间轴）
├── common-event-*/        # 事件物料
│   ├── common-event-nav/  # 导航跳转
│   ├── common-event-pay/  # 支付
│   ├── common-event-lx/   # 埋点
│   ├── common-event-location/ # 定位
│   └── common-event-utils/ # 事件工具
├── common-duo-lifecycle/  # DUO 生命周期物料
├── common-duo-build-in-lifecycle/ # DUO 内置生命周期
├── common-duo-params/     # DUO 参数物料
├── common-custom-view/    # 自定义视图
├── common-phone-modal/    # 手机号弹窗
└── util-*/                # 工具包
    ├── util-auto-reporter/        # 自动上报
    ├── util-auto-reporter-request/ # 请求上报（mrn/web/weapp 三端）
    ├── util-storage/              # 存储（三端）
    ├── util-location/             # 定位（三端）
    ├── util-msi-api/              # MSI API 封装（三端）
    ├── util-lx/                   # 埋点工具
    ├── util-loganrtl/             # Logan 日志（三端）
    └── util-modal-wrap/           # 弹窗包装器
```
