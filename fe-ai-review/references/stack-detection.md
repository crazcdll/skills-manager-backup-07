# 前端技术栈识别

> 独立判定资产：输入一批文件路径 / 依赖 / 内容特征，输出命中的技术栈集合（可多个）。不依赖调用方是谁、识别结果拿去做什么。

## 判定原则

1. **多信号加权**，优先级从高到低：`package.json` 依赖 → 目录结构特征 → 文件路径/后缀 → 文件内容 import 特征。级别越高越可信；只有拿不到高优先级信号时（比如只有 diff 文件、没有完整仓库），才退化到路径或内容特征。
2. **允许多技术栈同时命中**，不做"选一个"的仲裁。常见组合：
   - DUO 项目本身即 DUO + Max（DUO 仓库的 `material/` 下是 Max 源码物料）
   - Max 组件跑在 MRN 容器内（跨端引用场景）
   - 一码多端仓库同时含 MRN 包与小程序包
3. **信号不足以判定任何技术栈时**，如实返回"未识别"，不要猜测。

## 判定信号总表

| 技术栈 | package.json 依赖 | 目录/文件结构特征 | 路径/后缀特征 | 内容 import 特征 |
|---|---|---|---|---|
| **DUO** | — | 见下方「DUO 专项」 | `.groovy` 后缀 | `include 'nodes/*.groovy'` |
| **MRN** | `@mrn/react-native`、`@mrn/*` 系列包 | — | 路径含 `@mrn/` | `from '@mrn/react-native'`、`from '@mrn/react-navigation'` |
| **Max** | `@max-components`、`@leez-components`、`@hfe/max-*` 系列包 | — | 路径含 `max-components` / `leez-components` | `from '@max-components'`、`from '@leez-components'` |
| **小程序** | 微信/支付宝/抖音小程序相关包（各端不同，需项目自查） | 根目录含 `app.json`（含 `pages` 字段）+ `app.js`/`app.ts` | `pages/` 目录；文件后缀 `.wxml` `.wxss` `.axml` `.acss` `.ttml` `.ttss` | — |

路径/后缀、内容 import 特征置信度低于依赖和目录结构，仅当后两者信息缺失时才作为判定依据。

## DUO 专项：新旧仓库结构

DUO 项目新老两种结构目前并存（[组件页面合并仓库](https://km.sankuai.com/collabpage/2758155555)），先判定结构版本再定位协议/物料文件。

### 结构版本判定

| 结构版本 | 判定特征（命中任一即可） |
|---|---|
| **新结构**（合并后） | 项目根存在 `protocol/` 目录，或存在 `duo.config.js`（含 `duo-builder/duo.config.js`） |
| **老结构**（合并前，仍大量存量存在） | 页面目录直接平铺 `struct.groovy` + `dataSourceMap.groovy` + `componentsMap.json` 等协议文件，无 `protocol/` 目录 |

官方迁移方案即以"是否存在 `protocol` 目录，或者 `duo.config.js`"作为新旧目录的兼容检测逻辑，可直接复用。

### 新结构目录

仓库只需要关注 `protocol/`（协议）与 `material/`（组件/物料）两块；`src/**` 是 `duo-builder` 出码产物，全部忽略，不参与判定。

```
{page-repo}/
├── protocol/                  # 页面协议文件（对应老结构的根目录内容）
│   ├── componentsMap.json
│   ├── dependencies.json
│   ├── ohDependencies.json    # 鸿蒙依赖（可选）
│   ├── pageBuildConfig.json
│   ├── dataSourceMap.groovy
│   ├── constData.groovy
│   ├── struct.groovy
│   ├── logics.groovy
│   ├── scripts/                # 构建/MRN 配置（可选）
│   └── nodes/{nodeName}.groovy # 拆分节点（可选）
├── material/                  # 物料源码（monorepo），命中 Max（或 MRN，视 duoComponentMix 而定）
│   ├── packages/{name}/
│   │   ├── src/
│   │   ├── description.json
│   │   └── package.json
│   └── package.json
├── src/                       # duo-builder 出码产物，忽略
└── duo-builder/
    ├── package.json
    └── duo.config.js
```

路径判定：

- 路径落在 `protocol/**` → 命中 DUO
- 路径落在 `material/packages/**/src/**` → 命中 DUO + Max/MRN
- 路径落在 `src/**` → 忽略

### 老结构目录

无 `protocol/` 前缀，协议文件直接位于页面目录根：`struct.groovy` / `dataSourceMap.groovy` / `constData.groovy` / `logics.groovy` / `componentsMap.json` / `pageBuildConfig.json` / `dependencies.json` / `scripts/` / `nodes/`，判定方式同新结构 `protocol/` 内文件，仅路径前缀不同。
