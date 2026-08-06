# DUO 协议业务规则总览

> ⚠️ 以下规则是强约束条件，MUST 严格遵守。

## 规则索引

| 编号 | 规则名称 | 核心约束 | 触发场景 |
|:---:|---------|---------|---------|
| P-1 | 输入来源唯一性 | 唯一输入 = spec/plan/tasks | Step 1 读取输入时 |
| P-2 | Groovy 2.4.17 合法性 | 表达式兼容 2.4.17 语法 | 编写数据绑定表达式时 |
| P-3 | DUO Groovy DSL 语法规则 | `{{ }}` 外禁止注释；DSL 语法约束 | 编写任何 .groovy / .json 文件时 |
| P-4 | 物料 ID 真实性 | materialId 必须可追溯来源 | Step 3.6 写入 componentsMap 时 |
| P-4.5 | 本地物料发布先置 | 本地物料必须先发布到 Yooz 再改协议 | 本次改动包含本地物料升级/新增时 |
| P-5 | 依赖与路径规则 | proCode 必须声明 + 路径区分类型 | 新增/修改物料依赖时 |
| P-6 | 数据源规则 | 变量作用域隔离（reqProps 限制） | 编写 dataSourceMap 时 |
| P-7 | 组件树结构规则 | nodeName 唯一 + 层级正确 + 书写顺序 | 编写 struct.groovy 时 |
| P-8 | nodeName 命名规范 | 统一命名约定 | 为节点命名时 |
| P-9 | 执行纪律规则 | 逐页→逐文件→逐项，禁止偷跑 | 整个协议生成流程 |
| P-10 | 常见遗漏防线 | 5 类高频遗漏场景的防御 | 每个步骤完成后回查时 |

---

## P-1：输入来源唯一性

**核心约束**：唯一合法输入源是 spec.md / plan.md / tasks.md。

**MUST**：
- 从这三个文件提取改动清单和需求点

**MUST_NOT**：
- 自行阅读学城文档、PRD 或其他外部文档作为输入
- 阅读 `{work_root}/.duo/{需求英文名}/docs` 下的中间产物 md 文件

---

## P-2：Groovy 2.4.17 合法性

**核心约束**：所有数据绑定表达式必须兼容 Groovy 2.4.17 运行时。

**MUST**：
- 字符串字面量使用外双内单：`"data": "'字符串值'"`
- 空值兜底使用 `?:` Elvis 运算符：`{{ DATA_SOURCE?.title ?: '' }}`
- 使用 `?.` 安全访问，每级属性都必须加

**MUST_NOT**：
- `===`（用 `==`）、`var`（用 `def`）、`**` 幂运算符
- 箭头函数 `=>`、模板字符串、解构赋值等 JS 语法

**参考**：case-study/CS-groovy-syntax.md（由 SKILL.md 资源索引统一引用）

---

## P-3：DUO Groovy DSL 语法规则

> 🔴 **核心铁律**：`{{ }}` 内是 Groovy 脚本代码，支持 `//` 注释。`{{ }}` 外是 DUO DSL 语法层，不支持任何注释，写了会报 `Unexpected char "/"`。此规则无例外。

### 注释规则（最高优先级）

- `{{ }}` 内部：允许 `//` 单行注释和 `/* */` 块注释
- `{{ }}` 外部：禁止任何注释

### DSL 语法对照表

| # | MUST_NOT（禁止写法） | MUST（正确写法） | 报错信息 |
|---|---------------------|-----------------|---------|
| 1 | `{{ }}` 外使用 `//` 或 `/* */` | 注释只写在 `{{ }}` 内 | `Unexpected char "/"` |
| 2 | `styles { object('style') }` | `style('styleName')` | `Unexpected token "}"` |
| 3 | `advanced { bool('displayRule') }` | `xIf {{ expr }}` | `Unexpected token "}"` |
| 4 | `events { emit { ... } }` JSON 数组 | `on('eventName') { callMethod() }` | `Unexpected token "["` |
| 5 | `constData.groovy` 中用 `constData` | 使用 `constant` 关键字 | `Unknown identifier` |
| 6 | `submitBizRespStatus` 中用 `errorNoReturnStruct` | 该关键字只在 `bizRespStatus` 中有效 | `Unknown identifier` |
| 7 | `string('flex') {{ '1' }}` | `number('flex') {{ 1 }}` | 样式值类型不匹配 |
| 8 | `{{ #FFFFFF }}` | `string('backgroundColor') {{ '#FFFFFF' }}` | 颜色值缺引号 |
| 9 | CSS 简写 `{{ '10px 20px' }}` | 拆分为单独属性 | DUO 基于 RN 不支持 CSS 简写 |
| 10 | `display`/`float`/`position:absolute` | 使用 flex 布局替代 | RN 不支持该属性 |
| 11 | `lock(false)` 显式声明 | lock 默认 false，无需声明 | 冗余代码 |

---

## P-4：物料 ID 真实性

**核心约束**：所有物料 ID 必须有可追溯的数据来源，绝对禁止编造。

**MUST**：
1. 通过 CLI/MCP 查询获取（优先 CLI → 降级 MCP → 降级 materials.json → 标记不可用）
2. 写入 componentsMap 时，每个 materialId 的来源必须在 Agent 输出中以表格说明（禁止在 .json 文件中写 `//` 注释）
3. 物料版本 ID 与版本号必须匹配

**MUST_NOT**：
- 自行编造任何 materialId 或 id
- 从旧协议复制 ID 但未验证
- 从非 CLI / 非 MCP / 非 materials.json 的来源获取 ID

> **核心原则**：没有查询结果或备选作为依据的 materialId，一律视为编造，绝对禁止写入。

---

## P-4.5：本地物料发布先置

**核心约束**：本地改动的物料必须先发布到 Yooz 平台，再通过 CLI/MCP 拉取实时版本信息写入协议。严禁用本地版本号预占位。

> 历史踩坑（2026-04-17）：Agent 把本地 `0.3.0` 直接写入协议，该版本尚未发布到 Yooz，CDN url 404。

**正确的分段交付节奏**：
- 阶段 A（物料开发）：改 src → demo 验证 → UT → bump version → build
- 阶段 B（物料发布）：lerna publish → duo publish-pkg → 用户告知"已发布"
- 阶段 C（协议改动）：CLI/MCP 查询新版本 → 写入协议 → 回查

**执行态自检**（Step 3.6 写入前 MUST 回答）：
1. 涉及的物料包名列表？
2. 是否包含本地改过 src/ 的物料？
3. 如果是 → 已发布到 Yooz？
4. 如果已发布 → 最近一次查询时间 + latestVersion + latestId？
5. 如果未发布 → MUST 停止写入，交回给用户推进发布

> **核心原则**：协议文件永远只记录 Yooz 平台已存在的物料版本。本地开发中的版本号绝不允许泄漏到协议仓库。

---

## P-5：依赖与路径规则

**MUST**：
1. proCode 物料必须同时在 `dependencies.json` 和 `componentsMap.json` 中声明
2. logic 类型用 `/logic/` CDN 路径，component 类型用 `/material/` 路径
3. componentsMap 中每个 resource 条目必须包含 `"buildConfig": null`
4. logics.groovy 标配 `common-duo-lifecycle` + `common-event-nav`

**MUST_NOT**：
- lowCode 组件放入 dependencies
- 路径类型混用
- 遗漏 `buildConfig: null`

---

## P-6：数据源规则

**MUST**：
1. `PREV_DATA` 只能在 `reqProps` 中使用，且必须先在 `currentData` 中定义对应字段
2. `dataSourceMap` 有接口改动时，通常需配套修改 `logics.groovy`

**MUST_NOT（reqProps 入参三大禁区）**：
- reqProps 中使用 `DATA_SOURCE`（应用 `PREV_DATA` 替代）
- reqProps 中使用 `CONST`（常量仅用于 struct 渲染）
- CONST 间互相引用

**变量作用域速查**：

| 变量 | 可用位置 | 不可用位置 |
|------|---------|-----------|
| `DATA_SOURCE` | struct props、logics 回调 | reqProps 入参 |
| `CONST` | struct 表达式 | reqProps、CONST 间互引 |
| `PREV_DATA` | reqProps 入参 | struct、logics |
| `PAGE_QUERY` | 全局可用 | — |
| `COMMON_PARAMS` | 全局可用 | — |

---

## P-7：组件树结构规则

**MUST**：
1. nodeName 页面内唯一（同一物料可多次使用但 nodeName 不同）
2. logics 节点 nodeType 必须为 `HANDLER_MODULE`
3. 弹窗/全局组件外置（不嵌套在布局插槽内）
4. 书写顺序 = 视觉层级（从上到下）
5. lowCode「已支持」仍需检查是否需要新增 props/events/埋点配置
6. 样式归 `styles {}`，禁止混入 `props {}`

---

## P-8：nodeName 命名规范

| 组件类型 | 命名模式 | 示例 |
|---------|---------|------|
| 文本组件 | 功能 + Text | `DealNameText`、`PriceText` |
| 卡片组件 | 功能 + Card | `DealInfoCard`、`OrderCard` |
| 按钮组件 | 功能 + Button | `SubmitButton`、`CancelButton` |
| 布局组件 | 功能描述 | `MainLayout`、`TopBar` |
| 逻辑组件 | 功能 + Logic | `LifecycleLogic`、`SubmitLogic` |
| 列表组件 | 功能 + List | `GoodsList`、`CouponList` |
| 图片组件 | 功能 + Image | `CoverImage`、`QrCodeImg` |

- 大驼峰命名（PascalCase）
- 禁止 `Node1`、`View2` 等无意义命名

---

## P-9：执行纪律规则

**MUST**：
1. 严格按「逐页面 → 逐文件 → 逐组件」顺序执行
2. 每完成一条改动项立即标记
3. 所有文件完成后必须逐条对照需求清单
4. 多页面时必须对所有页面逐一执行
5. 拆分后必须逐文件检查一致性

**MUST_NOT**：
- 实现 spec.md 未描述的改动（防偷跑）
- 跳过回查步骤
- 存在待处理项时就认为完成

---

## P-10：常见遗漏防线

| # | 遗漏场景 | 后果 | 防御措施 |
|---|---------|------|---------|
| 1 | 多页面只处理了一个 | 部分线上功能缺失 | 先输出完整页面清单，逐页打勾 |
| 2 | lowCode「已支持」就不改 | 缺少新配置 | 仍需逐项检查 |
| 3 | 只改 dataSourceMap 不改 logics | 埋点/事件未同步 | 每次改完 dataSourceMap 配套检查 logics |
| 4 | 只关注新增改动项 | 已有配置被遗漏 | 同步检查已有配置是否受影响 |
| 5 | 目录不存在就静默跳过 | 页面协议完全缺失 | 必须向用户确认，禁止默认跳过 |
