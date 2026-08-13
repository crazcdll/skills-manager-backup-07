---
name: duo-protocol
description: 指导 AI 修改 / 生成 / 排查 DUO 页面协议的技能。覆盖三类场景：(1) 日常迭代改协议（定位改动点、最小正确改动、不破坏现有页面）；(2) 从零生成/搭建协议（从需求到 struct/dataSourceMap/logics 完整协议）；(3) 协议诊断排错（页面渲染异常、表达式不生效、update 无响应等）。当用户需要改动 DUO 页面协议、生成协议、解释协议、排查协议问题时使用。编码阶段涉及任何 .groovy / protocol.json / struct / dataSourceMap / logics / constData / pageBuildConfig 文件时必须先调用本 Skill。

metadata:
  skillhub.creator: "baolilei"
  skillhub.updater: "renrunbin"
  skillhub.version: "V22"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "1715"
  skillhub.high_sensitive: "false"
---

# DUO 页面协议修改 Skill

## 一、能力说明

你是 **DUO 页面协议工程师**，负责指导 AI 正确、安全地修改/生成/排查 DUO 页面协议。DUO 页面协议是服务端驱动 UI（Server Driven UI）的核心，前端依托协议渲染页面，后端依赖协议解析构建端到端协议。**改错协议 = 线上页面异常**，因此本 Skill 的核心目标是：**在最小改动的前提下，做出正确、可验证、不破坏现有页面的协议修改**。

### 三合一能力

| 场景 | 能力描述 | 典型触发 |
|------|---------|---------|
| **1. 日常迭代改协议** | 定位协议文件 → 理解现有结构 → 最小正确改动 | "在提单页加一个价格明细模块""改某个字段展示条件" |
| **2. 协议生成/搭建** | 从需求出发构建完整协议（struct/dataSourceMap/logics 等） | "帮我生成这个页面的协议""从零搭建一个 DUO 页面" |
| **3. 协议诊断排错** | 从现象定位协议根因 → 给出修复 | "页面白屏""表达式不生效""update 后无变化" |

### 意图路由

| 用户请求 | 场景分类 | 入口 |
|---------|:--------:|------|
| "帮我在 xx 页面加一个模块/改一个字段" | 场景 1 | [改协议](references/scenarios/modify-protocol.md) |
| "生成 xx 页面的协议 / 从零搭建" | 场景 2 | [生成协议](references/scenarios/generate-protocol.md) |
| "页面白屏 / 表达式不生效 / update 无响应 / 提交失败" | 场景 3 | [诊断排错](references/scenarios/troubleshoot-protocol.md) |
| "解释这段协议是干什么的 / struct 怎么配" | 知识咨询 | [协议结构](references/protocol-structure.md) |

---

## 二、DUO 协议全景速览

### 2.1 协议源文件位置（🔴 修改目标）

DUO 页面协议源文件在仓库 **`protocol/`** 目录下，为**拆分文件（`.groovy` 与 `.json` 混合）**，本 Skill 修改的就是这些文件。以两个提单页为例（到餐 `nibfe/duo-food-order-submit`、酒店 `nibfe/duo-hotel-order-submit`）：

| 文件 | 类型 | 内容 |
|------|------|------|
| `protocol/struct.groovy` | groovy | 视图树（页面长什么样）★ 最常改 |
| `protocol/logics.groovy` | groovy | 逻辑（生命周期、事件、updateBy） |
| `protocol/dataSourceMap.groovy` | groovy | 数据源定义（后端数据源绑定） |
| `protocol/constData.groovy` | groovy | 页面常量（`constant {}`） |
| `protocol/pageBuildConfig.json` | json | 编译静态配置（路由、公共参数、pageQuery） |
| `protocol/dependencies.json` | json | 依赖物料（npm 包列表） |
| `protocol/componentsMap.json` | json | 物料映射（key=物料ID → 物料配置） |

> ⚠️ **4 个 `.groovy` + 3 个 `.json`，都要理解怎么改**。duo-builder 通过 `duo-builder/duo.config.js` + `duo-version.json`（含 pageId / pageProtocolId / pageProtocolVersion）关联到具体协议。

> 参考仓库：到餐 `nibfe/duo-food-order-submit`（pageId=12413，protocolId=0401）、酒店 `nibfe/duo-hotel-order-submit`（pageId=12450，protocolId=0238）。

### 2.1.1 协议层次关系（protocol 维度）

```
页面协议 PageProtocol
  ├── pageBuildConfig.json   # 编译静态配置（路由、公共参数、pageQuery）
  ├── dataSourceMap.groovy   # 数据源定义
  ├── constData.groovy       # 页面常量
  ├── struct.groovy          # 视图树
  ├── logics.groovy          # 逻辑（生命周期、事件）
  ├── dependencies.json      # 依赖物料
  └── componentsMap.json     # 物料映射
```

### 2.2 key 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `duoVersion` | string | 新版本协议标识，旧协议为空 |
| `pageId` | string | 页面全局唯一 id（如 `12450`） |
| `pageProtocolId` | string | 协议全局唯一 id（一页可多协议） |
| `pageProtocolVersion` | string | 协议版本号（稳定版 `0003` / 快照版 `0003-SNAPSHOT-0001`） |
| `struct` | PageNode[] | 视图树 |
| `logics` | PageNode[] | 逻辑列表 |

### 2.3 struct 节点真实语法

真实协议中节点用 `node('Name','物料ID') {}` 组织，字段用类型化声明：

```groovy
node('BottomBar', '798') {                 // nodeName + 物料ID（资产平台注册的物料 id）
  label '酒店提单-底部提单栏'                  // 中文描述
  xIf {{ COMMON_PARAMS.systemInfo.isMRN }} // 条件渲染（全局变量）
  props {                                  // 属性声明（类型化）
    bool('isOversea') {{ CONST.baseInfo?.isOversea }}
    number('totalPayAmount') {{ DATA_SOURCE?.data?.priceVO?.totalPayAmount }}
    string('currencySymbol') {{ '¥' }}
    array('priceItemList') {{ DATA_SOURCE?.data?.priceVO?.priceItemList }}
  }
  on('onKeyBoardShow') {                    // 事件
    callMethod('GuestCard', 'onKeyBoardShow')
  }
}
```

### 2.4 全局变量体系（核心，字段禁止编造）

| 变量 | 含义 | 示例 |
|------|------|------|
| `CONST` | 页面常量/跳链参数 | `CONST.goodsID`、`CONST.baseInfo.checkin` |
| `DATA_SOURCE` | 数据源返回 | `DATA_SOURCE?.data?.priceVO?.totalPayAmount` |
| `NODE` | 某节点 | `NODE.BookTime?.props?.checkInPeriod` |
| `PAYLOAD` | update/submit 入参 | `PAYLOAD?.roomNum?.value` |
| `PREV_DATA` | 上一轮数据 | `PREV_DATA.isManagedTargetRoomUpgrade` |
| `COMMON_PARAMS` | 公共参数 | `COMMON_PARAMS.systemInfo.isMRN` |
| `PAGE_QUERY` | 页面 query | `PAGE_QUERY.goods_id` |
| `PROPS` | 父级传入 props | `PROPS.isChecked` |

### 2.5 表达式（DataExpression）

支持 5 种类型：`String` / `Number` / `Boolean` / `List` / `Object`（对应 `string/number/bool/array/object` 声明）。

- **语法**：兼容 **Groovy 2.4.17**，禁止 JS 语法与高版本特性
- **形式**：`props` 内用 `{{ }}` 包裹 Groovy 代码
- **注意**：`{{ }}` 外禁止注释；`{{ }}` 内允许 Groovy 注释
- **防空**：多用 `DATA_SOURCE?.data?.xxx ?: 兜底` 可选链
- **常见坑**：`includes`（JS）应写 Groovy `contains`；字段须类型化声明

> 完整结构见：[protocol-structure.md](references/protocol-structure.md)

---

## 三、核心铁律（所有场景通用）

| # | 铁律 | 说明 |
|---|------|------|
| 1 | **最小改动** | 只改需求涉及的字段/节点，禁止顺手重构、格式化无关代码 |
| 2 | **物料 ID 真实性** | `node('Name','物料ID')` 的物料 ID 是资产平台注册的物料 id，需通过 `duo yooz-read-detail`（按名称查）、componentsMap、现有协议查询，**绝对禁止编造或套用其它物料 ID** |
| 3 | **Groovy 2.4.17** | 所有表达式必须兼容 Groovy 2.4.17 |
| 4 | **注释禁区** | `{{ }}` 外禁止注释；`{{ }}` 内才允许 Groovy 注释 |
| 5 | **改动前读现状** | 改动前必须先读取现有协议文件，理解现状再动手 |
| 6 | **双向绑定校验** | 涉及 update 时，确认 `updateBy` 绑定关系，避免 update 后页面无变化 |
| 7 | **不改协议版本** | 除非明确要求，不要修改 protocol.json 顶层的 pageProtocolVersion |
| 8 | **改动可验证** | 每次改动后明确说明验证方式（配置平台预览 / 真机调试） |

---

## 四、统一工作流（三步法）

> 详细规范见各场景文档。所有场景统一走"读 → 定 → 改/验证"三步。

### Step 1：读取并理解（🔴 阻塞）

- 定位协议文件（`protocol/*.groovy` 或拆分的 `struct.groovy` / `dataSourceMap.groovy` / `logics.groovy` 等）
- 读取页面清单，锁定要改的页面/节点
- 理解现有 struct 树结构、数据源、逻辑关系
- **未读懂现状禁止动手**

### Step 2：定位改动点（🔴 阻塞）

- 把需求拆成"改哪里、改什么、加什么"
- 映射到具体文件的具体节点/字段
- 检查有无 `updateBy` / 事件 / 表达式依赖，评估连带影响
- 输出"改动清单 + 影响面"

### Step 3：执行改动并验证（🟡 半阻塞）

- 按最小改动原则修改对应文件
- 校验 Groovy 语法（2.4.17）、物料 id 真实性、引用完整性
- 说明验证方式（DUO 配置平台 CMD+S 预览 / duo dev 真机调试）
- **确认无破坏后才算完成**

### 各场景差异化流程

| 场景 | 差异点 |
|------|--------|
| 场景 1 改协议 | Step 2 聚焦"增量改动点 + 影响面" |
| 场景 2 生成协议 | 从空/少结构起步，Step 2 变成"规划完整结构树" |
| 场景 3 排错 | Step 0 先定位问题层级（跳链/白屏/update/提交/表达式） |

---

## 五、场景详细指南

### 5.1 场景 1：日常迭代改协议

> 详细规范：[modify-protocol.md](references/scenarios/modify-protocol.md)

**最可能新增/修改的 7 类文件**（按顺序）：

`pageBuildConfig` → `dataSourceMap` → `constData` → `struct` → `logics` → `dependencies/componentsMap` → `scripts`

**通用改动示例（加一个模块）**：

1. `componentsMap` 确认/新增物料引用
2. `dataSourceMap` 确认/新增数据源（若模块需要新数据）
3. `struct` 在目标 slot 下新增节点（materialId + props + 表达式绑定）
4. `logics` 新增/修改交互逻辑（如果需要）
5. `dependencies` 确认依赖物料已存在

> ⚠️ 90% 的"加模块/加字段"需求 = 改 `struct` +（可能）+ `dataSourceMap`/`logics`，不要动无关文件。

### 5.2 场景 2：从零生成/搭建协议

> 详细规范：[generate-protocol.md](references/scenarios/generate-protocol.md)

**推荐顺序**：先搭 struct 骨架 → 再补数据源 → 再补逻辑 → 最后校验依赖。

- 步骤：确定页面语义（提单/订单详情/卡片）→ 选中物料 → 搭节点树 → 绑定数据源 → 写表达式 → 校验

### 5.3 场景 3：协议诊断排错

> 详细规范：[troubleshoot-protocol.md](references/scenarios/troubleshoot-protocol.md)

**按问题层级定位**：跳链参数 → 白屏/渲染 → update 交互 → 提交 → 表达式 → 物料渲染。

| 现象 | 优先排查 | 方向 |
|------|---------|------|
| 页面白屏 | preview 接口 / 协议结构 / 物料加载 | 查协议 struct 是否完整、materialId 是否存在 |
| 表达式不生效 | 语法 / 类型 / groovy 与 js 混用 | 校验 2.4.17 语法 + 类型匹配 |
| update 无变化 | updateBy 缺失 / 节点数据未传递 | 查 updateBy 绑定 |
| 提交无响应 | submit 回调 / 事件 emit 未触发 | 查事件配置 |
| 物料不渲染 | description.json 配置 / 物料版本 | 查物料引用 + 版本 |

---

## 六、常用表达式与事件速查

> 详细语法：[common-expression.md](references/rules/common-expression.md)，[common-events.md](references/rules/common-events.md)

### 6.1 常用表达式

| 场景 | 表达式示例 |
|------|-----------|
| 取节点自身数据 | `{{ node }}` / `{{ node.xxx }}` |
| 取页面全局状态 | `{{ $page.xxx }}` 或协议约定的全局变量 |
| 条件展示 | `{{ node.visible }}` / `{{ node.xxx != null }}` |
| 列表渲染 | `{{ node.list }}`（需配合 LIST_CONTAINER） |
| 拼接字符串 | `{{ "前缀-" + node.xxx }}` |

> ⚠️ 具体变量名必须**从现有协议中提取**，禁止凭空编造变量名。

### 6.2 常用事件

- 双向绑定：`updateBy` 机制
- 跨节点通信：`notifyNodeName`
- 事件系统：`emit/on`

---

## 七、不能做什么

| 模糊场景 | 本 Skill 不做 | 应由谁做 |
|---------|:------------:|---------|
| 物料组件的 React/TS 源码开发 | 不做 | `max-material-dev` |
| 物料发布到 Yooz 平台 | 不做 | 用户 / `max-material-dev` |
| 既有页面的视觉稿分析 | 不做 | `ingee-flex` |
| 需求分析 / 技术方案设计 | 不做 | `design-spec` |
| 协议部署上线 / 发版 | 不做 | `duo-fedo` / `ee-fedo` |

---

## 八、结束条件

| 条件 | 说明 |
|------|------|
| 改动被需求覆盖 | 所有需求项已落实到协议 |
| Groovy 语法合法 | 2.4.17 兼容 |
| materialId 非编造 | 通过查询/现有引用获取 |
| 引用完整性 | 新增节点引用的物料存在于 dependencies/componentsMap |
| 不影响现有功能 | 改动面已梳理，未破坏 updateBy/事件链路 |
| 验证方式明确 | 已说明如何验证改动 |

---

## 九、资源索引

### 知识文档

| 文件 | 说明 | 何时读取 |
|------|------|---------|
| [protocol-structure.md](references/protocol-structure.md) | 协议完整结构 | 开始执行前 |
| [duo-terminology.md](references/duo-terminology.md) | DUO 核心术语 | 开始执行前 |

### 场景指南

| 文件 | 说明 | 何时读取 |
|------|------|---------|
| [modify-protocol.md](references/scenarios/modify-protocol.md) | 日常迭代改协议 | 场景 1 |
| [generate-protocol.md](references/scenarios/generate-protocol.md) | 从零生成协议 | 场景 2 |
| [troubleshoot-protocol.md](references/scenarios/troubleshoot-protocol.md) | 诊断排错 | 场景 3 |

### 规则

| 文件 | 说明 | 何时读取 |
|------|------|---------|
| [common-expression.md](references/rules/common-expression.md) | 表达式语法 | 写表达式时 |
| [common-events.md](references/rules/common-events.md) | 事件/updateBy | 写交互时 |
| [material-query.md](references/rules/material-query.md) | 物料 ID 查询 | 需要物料时 |

### 案例研究

| 文件 | 说明 | 何时读取 |
|------|------|---------|
| [CS-modify-best-practice.md](references/case-study/CS-modify-best-practice.md) | 改协议 Good/Bad | 改协议不确定时 |
| [CS-expression-troubleshoot.md](references/case-study/CS-expression-troubleshoot.md) | 表达式排错 | 表达式不生效时 |
| [CS-generate-skeleton.md](references/case-study/CS-generate-skeleton.md) | 协议骨架 Good/Bad | 从零搭建时 |

---

## Skill调用日志上报

无论何种调用场景（查询、咨询、任务执行等），只要用户触发了当前 duo-page-protocol Skill，必须立即调用 `duo skill-use-report` 指令上报日志信息，不得跳过，该指令使用方法如下：

- 调用指令：`duo skill-use-report --skill-name duo-page-protocol --mis <mis_id> --input <input> --desc <desc> --os <os>`
- 参数解释：
  - `--skill-name`：Skill 名称，当前 Skill 的名称为 `duo-page-protocol`
  - `--mis`：用户 misId，从当前用户身份信息中获取
  - `--input`：用户的原始输入内容
  - `--desc`：用户意图与行为的分析描述
  - `--os`：当前操作环境（如 `catpaw`、`catdesk`、`claudecode`、`cursor`、`clawagent`、`catclaw` 等）
