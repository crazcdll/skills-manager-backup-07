# 前端技术栈识别

> 独立判定资产：输入一批文件路径 / 依赖 / 内容特征，输出命中的技术栈集合（可多个）。不依赖调用方是谁、识别结果拿去做什么。

## 判定原则

1. 按下表特征识别本次变更所属模块，结合依赖、构建配置、目录结构和实际 import 确认；路径、后缀和仓库名称仅作线索。
2. **允许多技术栈同时命中**，保留各栈证据；单值登记使用下方「专项技术栈优先」规则。常见组合：
   - DUO 项目本身即 DUO + Max（DUO 仓库的 `material/` 下是 Max 源码物料）
   - Max 组件跑在 MRN 容器内（跨端引用场景）
   - 一码多端仓库同时含 MRN 包与小程序包
3. **信号不足以判定任何技术栈时**，如实返回"未识别"，不要猜测。

## 变更归属与交接

- 先定位本轮变更所属 package / workspace，再读取对应依赖、构建配置和入口。根 package 的依赖不能替代其它模块的证据；仅依赖升级也按对应 package 的实际用途判断。
- 路径、后缀和仓库名称只提供候选信号。JS/TS 需区分浏览器、小程序和 Node 服务端；MRN 桥接的 Objective-C、Swift、Android、ArkTS 实现按原生模块处理。Flutter 需同时核对所属模块的 Flutter SDK 声明与 Dart 实现，不能仅凭 Dart 后缀判定。
- 受委托时将非前端范围及证据交回主 Agent，不能宣称已按 Web/MRN 专项覆盖。独立审查时明确专项覆盖边界。
- 返回技术栈集合、各栈对应的变更模块与证据文件、未识别部分。按「专项技术栈优先」规则向上层交付单值登记；完整集合与各模块审查范围一并保留。
- React、Vue 等框架依据本模块依赖、入口和实际 import 区分；没有框架证据时保持未识别，不默认 React。

## 专项技术栈优先（单值登记）

受上层委托需要单值登记时，已确认的技术栈仅涉及 DUO、Max、MRN、React，则按 `DUO > Max > MRN > React` 取最高项。只比较有模块证据的栈，保留完整集合及审查覆盖；相关测试、构建工具仍需覆盖，不因使用 Node 就视为 Node 服务端。

涉及小程序、Java、Node 服务端、原生、Flutter 等其它栈时，由主 Agent 按本次实质变更确定主导栈；证据不足或无法确定则登记 `unknown`，继续核对未归属文件。

独立运行的看板按 [上报约定](report-submit.md) 保留多值，未识别填 `others`。

## 判定信号总表

| 技术栈 | package.json 依赖 | 目录/文件结构特征 | 路径/后缀特征 | 内容 import 特征 |
|---|---|---|---|---|
| **DUO** | — | 见下方「DUO 专项」 | `.groovy` 后缀 | `include 'nodes/*.groovy'` |
| **MRN** | `@mrn/react-native`、`@mrn/*` 系列包 | — | 路径含 `@mrn/` | `from '@mrn/react-native'`、`from '@mrn/react-navigation'` |
| **Max** | `@max/max`、`@max-components`、`@leez-components`、`@hfe/max-*`；`@leez/*` 需结合 Max 构建入口与实际 import 确认，单个工具依赖不足以定栈 | — | 路径含 `max-components` / `leez-components` | `from '@max/max'`、`from '@max-components'`、`from '@leez-components'` |
| **小程序** | 微信/支付宝/抖音小程序相关包（各端不同，需项目自查） | 根目录含 `app.json`（含 `pages` 字段）+ `app.js`/`app.ts` | `pages/` 目录；文件后缀 `.wxml` `.wxss` `.axml` `.acss` `.ttml` `.ttss` | — |

## DUO 专项：新旧仓库结构

DUO 项目新老两种结构目前并存（[组件页面合并仓库](https://km.sankuai.com/collabpage/2758155555)），先判定结构版本再定位协议/物料文件。

### 结构版本判定

| 结构版本 | 判定特征（命中任一即可） |
|---|---|
| **新结构**（合并后） | 项目根存在 `protocol/` 目录，或存在 `duo.config.js`（含 `duo-builder/duo.config.js`） |
| **老结构**（合并前，仍大量存量存在） | 页面目录直接平铺 `struct.groovy` + `dataSourceMap.groovy` + `componentsMap.json` 等协议文件，无 `protocol/` 目录 |

官方迁移方案即以"是否存在 `protocol` 目录，或者 `duo.config.js`"作为新旧目录的兼容检测逻辑，可直接复用。

### 新结构目录

确认是 DUO 页面仓库且构建配置证明 `src/**` 为 `duo-builder` 出码产物后，聚焦 `protocol/`（协议）与 `material/`（组件/物料），忽略对应生成目录。其它 workspace 的同名目录仍按各自用途判断。

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

以下路径规则仅应用于已确认的 DUO 页面模块：

- 路径落在 `protocol/**` → 命中 DUO
- 路径落在 `material/packages/**/src/**` → 命中 DUO + Max/MRN
- 路径落在 `src/**` → 忽略

### 老结构目录

无 `protocol/` 前缀，协议文件直接位于页面目录根：`struct.groovy` / `dataSourceMap.groovy` / `constData.groovy` / `logics.groovy` / `componentsMap.json` / `pageBuildConfig.json` / `dependencies.json` / `scripts/` / `nodes/`，判定方式同新结构 `protocol/` 内文件，仅路径前缀不同。
