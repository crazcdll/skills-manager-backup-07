# duo-builder 页面代码生成工具

> 本文档介绍 `duo-builder` 的设计目标、核心流程、配置项及常见扩展点，面向需要维护或定制出码流程的开发者。
> `duo-builder` 是 `duo-core` 仓库中的一个 package，仓库地址：`ssh://git@git.sankuai.com/nibfe/duo-core.git`
> 文档中所有路径均相对于页面工程根目录（即包含 `duo.config.js` 的目录）。

---

## 设计目标

`duo-builder` 是 DUO **页面代码生成工具**，负责将 DUO 页面协议转换为可运行的页面工程代码。它不是物料包构建工具，不负责打包 MRN bundle 或 Web UMD bundle，也不负责将物料发布到 yooz 平台。

它的核心职责是：

1. **拉取页面协议**：从 DUO 服务端拉取 `PageProtocol`，或使用本地传入的草稿协议
2. **拉取物料发布协议**：从 Yooz 平台拉取页面实际使用的物料发布信息
3. **生成页面工程代码**：将协议渲染为多端（MRN / Web / 小程序 / 鸿蒙）可运行的页面工程
4. **生成预请求配置**：生成 PN 预请求 JSON 和 MRN 预请求 JSON
5. **生成 lowCode 物料代码**：调用 `@yooz/lowcode-code-generator` 将 lowCode 物料 DSL 出码为真实组件/逻辑代码
6. **同步依赖锁文件**：从 Yooz S3 接口同步 `yarn.lock` / `oh-yarn.lock`，并自动安装依赖
7. **本地联调服务**：`dev` 模式下启动 WebSocket 服务，接收 DUO 配置平台实时下发的协议，支持热更新出码

---

## 两个命令

### generate（一次性出码）

```bash
duo-builder generate
```

读取本地 `duo.config.js`，拉取协议和物料，生成完整页面工程代码后退出。适用于 CI 流水线或手动触发出码。输出目录默认为 `./.duo-tmp/preview-{protocol.pageId}`（`protocol.pageId` 为协议中的页面 ID）。

### dev（联调模式）

```bash
duo-builder dev
```

启动本地联调服务，不直接出码。它会：

- 启动 WebSocket 服务（`socket.io`），等待 DUO 配置平台连接并下发页面配置
- 启动本地 Unix Socket 服务（`/tmp/duo.sock`），与 `duo-cli` 通信，支持源码组件调试
- 每次收到平台下发的配置后，触发一次出码，并在输出目录自动执行 `yarn start:main` 启动预览

`dev` 模式会复用上一次的协议/物料/meta，跳过重复安装依赖，并强制跳过 lint，以加速热更新出码。

---

## 完整出码流程

```
generate / dev 收到配置
  Step 1: 读取并合并配置（duo.config.js + 环境变量 + 平台下发 payload）
  Step 2: 加载页面协议
    -> 优先使用 config.draftProtocol（本地/平台传入的草稿协议字符串）
    -> 否则请求 DUO 服务端接口：POST /pageProtocol/queryPageProtocol
  Step 3: 校验协议版本
    -> duoVersion !== '2' 时，降级走 @meishi/duo-builder-v1 旧版逻辑
  Step 4: 初始化 meta（解析依赖、输出路径、MRN bundle 信息、预请求开关等）
  Step 5: 处理源码组件调试（dev 模式下复制并 watch 源码组件到输出目录）
  Step 6: 加载物料发布协议
    -> 从协议 componentsMap 中提取 usedMaterialIdSet（实际使用的物料）
    -> 请求 Yooz 接口：GET /api/public/material/publish/query
    -> 将 configSchema 解析为 config，并按 type 分类（NORMAL_MODULE / HANDLER_MODULE）
  Step 7: 初始化物料分类（视图物料 / 逻辑物料 / 内置物料）
  Step 8: 生成预请求数据（PN 预请求 JSON、MRN 预请求 JSON）
  Step 9: 并行生成以下内容：
    -> 渲染模板工程（template/ + generator/ -> outputFolder）
    -> 生成三端 materialMap（mrn / web / weapp）
    -> 生成 baseParams.ts / customHttpConfig.ts / onRequest.ts / useStaticNodes.ts
    -> 生成 PN 预请求配置文件
    -> 生成 MRN 预请求配置文件
    -> 生成 lowCode 视图物料代码（src/page/yoozComponents/）
    -> 生成 lowCode 逻辑物料代码（src/page/yoozLogics/）
  Step 10: 同步 yarn.lock / oh-yarn.lock（从 Yooz S3 接口拉取）
  Step 11: 安装依赖（yarn install 或鸿蒙 oh-better-install）
  Step 12: 更新 lock 文件（将安装后的 lock 文件回写到 Yooz S3）
  Step 13: prettier + lint（dev 模式下跳过）
  Step 14: （dev 模式）在 outputFolder 执行 yarn start:main 启动预览
```

---

## 输入与输出

### 输入

- `duo.config.js`：本地配置文件（见下方配置项说明）
- 环境变量：可覆盖 `duo.config.js` 中的配置
- DUO 服务端：页面协议（`PageProtocol`）
- Yooz 平台：物料发布协议（`Material[]`）
- Yooz S3：`yarn.lock` / `oh-yarn.lock`

### 输出

生成到 `config.outputFolder`（默认 `./.duo-tmp/preview-{protocol.pageId}`），产物结构如下：

```
{outputFolder}/
  package.json                        # 根据协议依赖生成
  oh-package.json                     # 鸿蒙依赖配置
  src/
    index.tsx                         # 页面入口
    app.json                          # 应用配置
    page/
      materialMap.mrn.tsx             # MRN 端物料映射
      materialMap.web.tsx             # Web 端物料映射
      materialMap.weapp.tsx           # 小程序端物料映射
      baseParams.ts                   # 运行时 storage 参数获取
      customHttpConfig.ts             # 自定义请求 headers/params
      onRequest.ts                    # 请求前处理逻辑
      useStaticNodes.ts               # 静态节点运行时代码
      yoozComponents/                 # lowCode 视图物料出码（仅 devMode=lowCode 的物料）
        {ComponentFolder}/
          ...                         # @yooz/lowcode-code-generator 生成的组件代码
      yoozLogics/                     # lowCode 逻辑物料出码
        helper.ts                     # 逻辑编排上下文辅助文件
        {LogicFolder}/
          logic.ts                    # 逻辑编排代码
  pn/                                 # PN 预请求配置（如开启 usePn）
    pn_preview.json
    mrn_prefetch_preview.json
```

---

## 配置项（duo.config.js）

```javascript
// duo.config.js
module.exports = {
  // 页面 ID（必填）
  pageId: 'your-page-id',

  // 协议 ID（必填）
  pageProtocolId: 'your-protocol-id',

  // 协议版本（必填）
  pageProtocolVersion: 'your-protocol-version',

  // 草稿协议字符串（可选）。传入后跳过远程拉取，直接使用此协议
  // 通常由 DUO 配置平台在 dev 模式下传入，用于调试未保存的协议
  draftProtocol: undefined,

  // Mock ID（可选）。用于指定 mock 数据
  mockId: undefined,

  // 代码输出目录（可选，默认 ./.duo-tmp/preview-{protocol.pageId}）
  outputFolder: './.duo-tmp/preview-your-page-id',

  // 拉取协议的环境（可选，默认 prod）
  // 可选值：prod | test | 泳道名
  _devEnv: 'prod',

  // 是否开启 h5guard URL 验签（可选，默认 true）
  h5guard: true,

  // 开启 h5guard header 验签的域名列表（可选）
  h5guardDomains: [],

  // 是否开启预请求（可选，默认 false；优先级高于协议配置）
  usePn: false,

  // 是否是测试包（可选，默认 false）
  isDevBundle: false,

  // Web 端是否包含 AppMock 配置入口（可选，默认 false）
  webAppmockConfig: false,

  // lowCode 物料调试 DSL 映射（可选）
  // key 为 materialId，value 为调试用的 DSL 字符串
  yoozComponentDebugMap: {},

  // --- 以下为调试开关，通常不需要手动配置 ---

  // 跳过安装依赖（默认 false）
  _devSkipInstallDeps: false,

  // 跳过 lint（默认 false）
  _devSkipLint: false,

  // 出码后是否自动执行 yarn start:main（默认 true，仅 dev 模式）
  _devYarnStart: true,

  // 是否强制重启预览进程（默认 false，仅 dev 模式）
  _devRestart: false,
};
```

### 环境变量

所有配置项均可通过环境变量覆盖，变量名规则为 `DUO_` 前缀加大写字段名：

| 环境变量 | 对应配置项 | 说明 |
|----------|-----------|------|
| `DUO_PAGE_ID` | `pageId` | 页面 ID |
| `DUO_PAGE_PROTOCOL_ID` | `pageProtocolId` | 协议 ID |
| `DUO_PAGE_PROTOCOL_VERSION` | `pageProtocolVersion` | 协议版本 |
| `DUO_OUTPUT_FOLDER` | `outputFolder` | 输出目录 |
| `DUO_PROTOCOL_ENV` | `_devEnv` | 拉取协议的环境 |
| `DUO_USE_PN` | `usePn` | 是否开启预请求 |
| `DUO_H5GUARD` | `h5guard` | 是否开启 h5guard |
| `DUO_H5GUARD_DOMAINS` | `h5guardDomains` | h5guard 域名（逗号分隔） |
| `DUO_DEVBUNDLE` | `isDevBundle` | 是否是测试包 |
| `DUO_WEB_APPMOCK_CONFIG` | `webAppmockConfig` | Web 端 AppMock 入口 |
| `DUO__DEV_SKIP_INSTALL_DEPS` | `_devSkipInstallDeps` | 跳过安装依赖 |
| `DUO__DEV_SKIP_LINT` | `_devSkipLint` | 跳过 lint |
| `DUO__DEV_YARN_START` | `_devYarnStart` | 出码后是否启动预览 |

---

## generator/ 目录说明

`generator/` 目录下的文件不是最终输出文件，而是"模板渲染器"，每个文件负责生成输出工程中某个目标文件的内容：

- `generator/package.json.ts`：根据协议依赖更新 `package.json`，融合 Max Horn 配置
- `generator/oh-package.json.ts`：生成鸿蒙 `oh-package.json`
- `generator/src/app.json.ts`：根据协议依赖推导 `leez-icon` 版本，渲染 `app.json`
- `generator/src/index.tsx.ts`：根据协议是否有 static/pageContainer 节点注入入口变量
- `generator/src/page/baseParams.ts.ts`：根据协议 storage 配置生成运行时参数获取函数
- `generator/src/page/customHttpConfig.ts.ts`：根据协议 `customHttpConfig.items` 生成请求 headers/params
- `generator/src/page/onRequest.ts.ts`：根据 `pnMatch` 和 `customHttpConfig` 生成请求前处理逻辑
- `generator/src/page/useStaticNodes.ts.ts`：将 static 节点、页面容器节点转为运行时代码，并做展示条件 tree shaking
- `generator/src/page/materialMapGenerator.ts`：生成三端物料映射，处理 lowCode 导入路径、ErrorBoundary 包装、MRN lazy load 等
- `generator/pn/pn_preview.json.ts`：生成通用 PN 预请求 JSON
- `generator/pn/mrn_prefetch_preview.json.ts`：生成 MRN 专用预请求 JSON（含 MSI/KNB hook、query match、commonParams）

---

## 与物料构建的关系

`duo-builder` 和物料构建是两个完全独立的流程：

- **物料构建**：由物料仓库（如 `yooz-materials`、`biz-cross-transaction-material`）自己的构建脚本完成，产物发布到 Yooz 平台
- **duo-builder**：消费 Yooz 平台上已发布的物料协议，生成页面工程代码

`duo-builder` 不负责打包物料，也不负责将物料发布到 Yooz。它只是在出码时，从 Yooz 拉取物料的发布协议（`configSchema`、`dsl` 等），用于生成 `materialMap` 和 lowCode 物料代码。

---

## 常见问题

### Q：generate 命令执行后，输出目录在哪里？

默认输出到 `./.duo-tmp/preview-{protocol.pageId}`（`protocol.pageId` 为协议中的页面 ID），可通过 `duo.config.js` 的 `outputFolder` 或环境变量 `DUO_OUTPUT_FOLDER` 修改。

### Q：dev 模式下如何触发重新出码？

`dev` 模式不读取本地 `duo.config.js` 中的协议配置，而是等待 DUO 配置平台通过 WebSocket 下发配置。在 DUO 配置平台上点击"预览"或"保存"时，平台会向本地 `duo-builder dev` 服务推送最新配置，触发重新出码。

### Q：如何调试 lowCode 物料？

在 `duo.config.js` 中配置 `yoozComponentDebugMap`，key 为 `materialId`，value 为本地调试用的 DSL 字符串。`duo-builder` 会优先使用此 DSL 而不是 Yooz 平台上的发布版本。

### Q：出码后依赖安装很慢，如何跳过？

设置 `_devSkipInstallDeps: true` 或环境变量 `DUO__DEV_SKIP_INSTALL_DEPS=true`，跳过依赖安装步骤。注意：首次出码或依赖变更时不能跳过，否则页面无法运行。

### Q：协议版本 duoVersion 不是 2 时会怎样？

`duo-builder` 会自动降级，调用 `@meishi/duo-builder-v1` 的旧版生成逻辑，兼容旧版协议。
