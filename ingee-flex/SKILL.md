---
name: ingee-flex
description: 执行视觉与图片分析、视觉稿数据获取与组件检索，生成学城 `FLEX_DESIGN_DOC` 子文档。涵盖视觉稿图片 + 视觉稿 DSL 数据 + 框架分析 + 组件映射（完整综合层）。触发词："flex"、"视觉分析"、"分析视觉稿"、"生成flex-design"。

metadata:
  skillhub.creator: "wb_wangjing63"
  skillhub.updater: "hejun10"
  skillhub.version: "V28"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "28269"
  skillhub.high_sensitive: "false"
---

# Ingee Flex

## 变量名称声明

引用代号是文档正文中的**内部简写**，对应学城子文档的真实标题：

| 引用代号（正文内部使用） | 学城子文档真实标题（对外输出时使用） |
|---|---|
| `SPEC_DOC` | `spec需求分析` |
| `FLEX_DESIGN_DOC` | `flex-design视觉分析` |

> ⚠️ **强制规则**：以下场景**必须**使用真实标题，使用代号视为错误输出：
> 1. **创建学城子文档**：`citadel createPage` 的 `title` 参数必须填真实标题，例如 `title: "flex-design视觉分析"`，而非 `title: "FLEX_DESIGN_DOC"`
> 2. **向用户汇报进度**：说「已完成 **flex-design视觉分析** 文档」，而非「已完成 **FLEX_DESIGN_DOC** 文档」
> 3. **引导用户查看**：说「请查看学城 **flex-design视觉分析** 子文档」，而非「请查看学城 **FLEX_DESIGN_DOC** 子文档」

## 输入 / 输出

### 输入

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 视觉稿链接（Ingee / imd）/ 物料截图 | string | ✅ | 视觉输入来源；二者至少提供其一。视觉稿链接按域名区分来源：`ingee.meituan.com` → Ingee 视觉稿，`imd.sankuai.com` → imd（MasterGo）视觉稿 |
| `KM_ROOT_ID` | string | ❌ | 学城根文档 ID；上游传入则使用、作为学城写入位置的上下文；不传入且 `KM_FEATURE_ID` 也未传入时不写入学城，直接输出结果 |
| `KM_FEATURE_ID` | string | ❌ | 学城功能子文档 ID，传入时 `FLEX_DESIGN_DOC` 将挂在其下并写入学城；**未传入时不执行学城写入**，直接将生成的 flex-design 内容作为对话回复输出给用户 |
| `KM_SPEC_ID` | string | ❌ | 学城 `spec需求分析` 子文档 ID；提供时作为视觉输入补充 |
| `task_id` | string | ❌ | 任务唯一标识；由上游 Skill（如 max-material-dev）调用时透传，独立调用时自行生成（12 位 [a-z0-9] 随机字符串） |

> **KM_FEATURE_ID 是写入学城的开关**：传入 `KM_FEATURE_ID` 时按原流程在其下创建 `FLEX_DESIGN_DOC` 子文档；未传入时跳过学城写入步骤，直接将按模板生成的完整 flex-design 内容输出到对话中。`KM_ROOT_ID` 仅在需要写入学城且需要定位根文档上下文时使用，单独传入 `KM_ROOT_ID` 而无 `KM_FEATURE_ID` 时仍不写入学城。

### 输出

| 产物 | 说明 |
|------|------|
| 学城 `FLEX_DESIGN_DOC` 子文档（仅传入 `KM_FEATURE_ID` 时） | 视觉稿结构化分析结果（`KM_FLEX_ID`），含视觉稿图片、整体框架、子模块详细数据、组件统计 |
| 对话直接输出的 flex-design 内容（仅未传入 `KM_FEATURE_ID` 时） | 与学城文档完全一致的结构化 Markdown 内容（视觉稿图片、整体框架、子模块详细数据、组件统计），直接在回复中展示给用户 |
| `task_id` | 透传给调用方（独立调用时输出本次生成的 `task_id`，供后续阶段使用） |

---

## Introduction 介绍

视觉分析与组件映射 → 结构化 flex-design 内容。在方案设计阶段前完成视觉与组件分析准备，将视觉稿图片、DSL 数据、图片结构分析与 Max/Leez 组件检索结果融合，严格按模板生成。**传入 `KM_FEATURE_ID`** 时写入学城 `FLEX_DESIGN_DOC` 子文档（挂在 `KM_FEATURE_ID` 下），供后续 plan/design 阶段作为视觉输入；**未传入** 时跳过学城写入，直接将同样内容作为对话回复输出。视觉稿支持 **Ingee**（`ingee.meituan.com`）与 **imd/MasterGo**（`imd.sankuai.com`）两种来源，仅视觉稿数据获取方式不同，其余处理链路完全一致。

## Function 功能

- **初始化与模板加载**：解析学城关键变量（`KM_ROOT_ID`、`KM_FEATURE_ID` 均为选填，`KM_SPEC_ID`），并根据 `KM_FEATURE_ID` 是否传入确定后续是"写入学城"还是"直接对话输出"，加载 [assets/flex-design-template.md](assets/flex-design-template.md) 作为输出模板
- **视觉输入收集**：聚合用户输入的图片/视觉稿链接、学城 `SPEC_DOC` 子文档中的视觉要求、会话内已存在的截图与结构化数据，按优先级解决冲突
- **视觉稿来源识别与 DSL 获取**：根据视觉稿链接域名分流——`ingee.meituan.com` 通过 `duo ingee-fetch` CLI 拉取 DSL JSON 数据；`imd.sankuai.com` 通过 MasterGo MCP（优先）或 Chrome CDP（降级）获取节点 DSL 数据与截图
- **图片结构分析**：对物料截图或视觉稿返回的 `imageUrl`/导出截图执行结构化分析，识别模块层级
- **组件检索**：从 Max/Leez 组件库检索可用组件（通过 `duo component-list -t \"leez,max\"` 查询组件列表，通过 `duo component-read-detail -p \"<pkg>\"` 获取组件详情）
- **三方融合生成终稿**：图片分析 + DSL JSON + 组件检索结果融合，严格按模板逐模块补全所有字段
- **学城写入（条件执行）**：**传入 `KM_FEATURE_ID`** 时，在学城 `KM_FEATURE_ID` 下创建标题为 `FLEX_DESIGN_DOC` 的子文档，返回 `KM_FLEX_ID`（每次都创建新文档，不读取也不覆盖已有文档）；**未传入 `KM_FEATURE_ID`** 时跳过此步，直接将生成的完整 flex-design 内容作为对话回复输出

## When to Use 使用场景

**需要将视觉稿/物料截图转化为结构化 flex-design 内容**（写入学城或直接对话输出）时使用：

- 用户提供 Ingee 视觉稿链接（`ingee.meituan.com`），要求生成 flex-design
- 用户提供 imd/MasterGo 视觉稿链接（`imd.sankuai.com`），要求生成 flex-design
- 用户提供物料截图并要求进行视觉结构分析与组件映射
- 在 max-material-dev 完整开发流程中被调用，完成视觉稿数据分析阶段（通常会传入 `KM_FEATURE_ID` 写入学城）
- 用户仅想快速获得结构化视觉分析结果，无需写入学城（不传入 `KM_FEATURE_ID`）

示例："flex"、"视觉分析"、"分析视觉稿"、"生成 flex-design"、"帮我分析这个 Ingee 视觉稿"、"帮我分析这个 imd 视觉稿"

## When NOT to Use 不使用场景

以下场景**不触发**此 Skill：

- **无视觉输入**：既无视觉稿链接也无物料截图
- **纯文本需求澄清**：只讨论需求文字/业务逻辑，不涉及视觉结构分析
- **非视觉稿数据分析**：只需要读写学城文档、只做组件检索而无需生成 flex-design
- **非 Max/Leez 体系**：通用 React/Vue 组件视觉分析，与 Max/Leez 组件库无关

## Scope 能力边界

- Ingee 视觉稿 DSL 数据获取
- imd（MasterGo）视觉稿 DSL 数据与节点截图获取
- 物料图片/截图结构化分析
- Max/Leez 组件检索与映射
- flex-design 内容的生成，以及根据 `KM_FEATURE_ID` 是否传入选择写入学城子文档或直接对话输出
- 不负责 spec/design/tasks/implement 阶段产物，也不执行代码开发与测试

## Rule 执行约定

以下步骤 3、4、6、7 均涉及 rule，统一遵循以下优先级：

1. **有 rule 文件** → 读取并严格遵循该 rule 执行
2. **有用户输入的 rule** → 参考用户输入的 rule 执行
3. **均无** → 基于通用认知执行，结果标注

## MainStep 核心流程

流程共分两条分支，**依据视觉稿链接域名判断走哪条分支**：`ingee.meituan.com` → Ingee 分支（含环境检查步骤），`imd.sankuai.com` → imd 分支（无环境检查步骤）。仅"环境检查"与"链接前置校验 + 获取视觉稿 DSL 数据"两步不同，其余步骤两分支完全一致。若用户仅提供物料截图（无视觉稿链接），按 Ingee 分支执行但跳过第 0 步、第 4 步的链接校验与 DSL 获取动作。

> **链接前置校验（MUST，两分支通用原则）**：拿到视觉稿链接后，必须先校验链接格式是否合法，校验通过后才可进入 DSL 数据获取；**任一校验不通过，立即停止执行，不得调用任何获取工具，直接向用户汇报链接错误**，不得凭空猜测缺失或错误的参数。
> - **Ingee 链接**：必须匹配 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 格式，且 `artboard_id` 必须存在，具体规则见 [references/ingee-design-fetch.md](references/ingee-design-fetch.md)「前置校验规则」
> - **imd 链接**：必须能从链接中解析出 `fileId`、`pageId`、`layerId` 三个参数，缺一不可，具体规则见 [references/imd-design-fetch.md](references/imd-design-fetch.md)「前置校验规则」
> - **多视觉稿容器链接（MUST，单独识别）**：除上述格式校验外，还需识别“看似合法但实际指向多张视觉稿的容器型链接”，无法确定具体分析哪一张，均视为校验不通过，立即停止并向用户提问：
>   - **Ingee 项目链接**：路径为 `#/detail/<project_id>/default`（如 `https://ingee.meituan.com/#/detail/258568/default`），而非 `#/artboard/<artboard_id>/pos_n`，该链接指向包含多张视觉稿的项目，详见 [references/ingee-design-fetch.md](references/ingee-design-fetch.md)「项目级链接识别」
>   - **imd 文件/页面级链接**：仅能解析出 `fileId`、`pageId`，缺少 `layerId`，该链接指向包含多张视觉稿的整套设计文件，详见 [references/imd-design-fetch.md](references/imd-design-fetch.md)「文件级/页面级链接识别」

另外，**第 8 步“写入学城”仅在传入 `KM_FEATURE_ID` 时执行**：传入则按原流程在其下创建 `FLEX_DESIGN_DOC` 子文档；未传入则跳过学城写入动作，直接将按模板生成的完整 flex-design 内容作为对话回复输出，第 9 步报告输出相应调整为输出内容本身而非学城链接。此分叉对 Ingee/imd 两分支均适用。

### Ingee 分支（视觉稿链接为 ingee.meituan.com）

```
用户输入：Ingee 视觉稿链接 / 物料截图 / 视觉要求描述
    ↓
[第 0 步] 环境检查（duo-cli）：执行 `duo --version` 确认 @meishi/duo-cli 已安装且版本 ≥ `0.4.63`，根据输出结果进行以下处理：
      - 未安装：自动执行 `npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com` 安装，完成后确认版本 ≥ `0.4.63`
      - 版本低于 `0.4.63`：自动执行同一指令更新，完成后确认版本 ≥ `0.4.63`
      - 已安装且版本满足：无需操作，直接进入下一步
    ↓
[第 1 步] Skill 调用日志上报（START）：
      - 确认 task_id：上游透传则直接使用；未提供则自行生成 12 位 [a-z0-9] 随机字符串作为本次 task_id
      - 流程启动时立即上报 `FLEX_DESIGN_START`，`duration` 传 `0`，具体上报规则参见本文"Skill 调用日志上报"章节
    ↓
[第 2 步] 初始化：解析 KM_ROOT_ID / KM_FEATURE_ID（均为选填，未传入则记录为“无需写入学城”）/ KM_SPEC_ID，加载 flex-design-template.md
    ↓
[第 3 步] 收集视觉输入：用户输入 + 学城 `SPEC_DOC` + 会话上下文
    ↓
[第 4 步] 链接前置校验 + 获取视觉稿 DSL 数据 → 读取 references/ingee-design-fetch.md
· 4.1 **前置校验（MUST）**：校验链接是否匹配 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 格式，且 `artboard_id` 非空；**同时识别是否为 `#/detail/<project_id>/default` 的项目级链接**（包含多张视觉稿，无法确定具体分析对象）；以上任一条件不满足，立即停止执行，向用户汇报/提问具体的链接错误原因，不得继续后续步骤
· 4.2 校验通过后，通过 `duo ingee-fetch` CLI 拉取 DSL JSON
    ↓
[第 5 步] 图片结构分析 → 读取 references/image-analysis.md，并分析图片的结构信息。
    ↓
[第 6 步] 生成初稿：视觉稿图片 + 整体框架 + 子模块骨架（含嵌套），读取文件 references/design-data-analytics.md，确定组件的整体框架、布局信息。
    ↓
[第 7 步] 组件检索 → 读取 references/material-retrieval.md，对视觉稿数据进行分析，识别出需要使用组件库中的哪些组件完成当前组件开发。
      「必须先通过 duo component-read-detail 查询组件完整 Props/API，不得凭空猜测任何参数」
    ↓
[第 8 步] 生成终稿 → 读取 references/flex-design-gen.md + assets/flex-design-template.md
      · 8.1 遵守第 6 步已加载的 references/design-data-analytics.md 中的视觉样式分析规则（尺寸 ÷2、gap → margin、justify-content 取 DSL 值），无需重复读取。
      · 8.2 先完整读取 assets/flex-design-template.md，作为"填空题骨架"
      · 8.3 按模板复制一级章节（## 1 视觉稿图片 / ## 2 整体框架 / ## 3 子模块详细数据 / ## 4 组件统计），顺序和标题不可改
      · 8.4 逐个 A/B/C... 子模块及其嵌套层，按模板 10 字段顺序（描述/框架/间距/排版/CSS/Props/推荐组件/Mock 数据/交互状态/边界情况）补全
      · 8.5 自检完成后执行 flex-design-gen.md 的"写入前校验清单（Self-Check）"，任一项不通过先修正
      · 8.6 **判断是否传入 `KM_FEATURE_ID`**：
            - **传入**：在 KM_FEATURE_ID 下创建标题为 FLEX_DESIGN_DOC 的新子文档，记录 KM_FLEX_ID（每次都创建新文档，不读取也不覆盖已有文档）
            - **未传入**：跳过学城写入，保留完整的 flex-design Markdown 内容，供下一步直接输出
    ↓
[第 9 步] 报告输出：
      - **已传入 `KM_FEATURE_ID`**：输出学城链接 + 模块/组件命中数 + 待确认项 + 降级步骤
      - **未传入 `KM_FEATURE_ID`**：直接将第 8 步生成的完整 flex-design Markdown 内容输出到对话中，并附带模块/组件命中数 + 待确认项 + 降级步骤
    ↓
[第 10 步] Skill 调用日志上报（END）：报告输出完成后**立即上报** `FLEX_DESIGN_END`，`duration` 传实际执行时长，具体上报规则参见本文"Skill 调用日志上报"章节
```

### imd 分支（视觉稿链接为 imd.sankuai.com）

```
用户输入：imd（MasterGo）视觉稿链接 / 物料截图 / 视觉要求描述
    ↓
[第 1 步] Skill 调用日志上报（START）：
      - 确认 task_id：上游透传则直接使用；未提供则自行生成 12 位 [a-z0-9] 随机字符串作为本次 task_id
      - 流程启动时立即上报 `FLEX_DESIGN_START`，`duration` 传 `0`，具体上报规则参见本文"Skill 调用日志上报"章节
    ↓
[第 2 步] 初始化：解析 KM_ROOT_ID / KM_FEATURE_ID（均为选填，未传入则记录为“无需写入学城”）/ KM_SPEC_ID，加载 flex-design-template.md
    ↓
[第 3 步] 收集视觉输入：用户输入 + 学城 `SPEC_DOC` + 会话上下文
    ↓
[第 4 步] 链接前置校验 + 获取视觉稿 DSL 数据 → 读取 references/imd-design-fetch.md
· 4.1 **前置校验（MUST）**：从链接中解析 `fileId`、`pageId`、`layerId` 三个参数；**若仅能解析出 `fileId`+`pageId`、缺少 `layerId`，识别为文件/页面级链接**（包含多张视觉稿，无法确定具体分析页面）；任一参数缺失、为空或解析失败，立即停止执行，向用户汇报/提问具体缺失的参数，不得继续后续步骤
· 4.2 校验通过后，优先通过 MasterGo MCP（`getDsl`）获取；未配置或调用失败时自动降级为 Chrome CDP 提取节点 DSL 数据与 PNG 截图。**imd/MasterGo 读取总尝试次数最多 3 次**（MCP 与 CDP 的所有调用合计计数）；任一次成功即继续后续步骤，连续/累计第 3 次失败后立即停止，不得再读取、切换路线、重新解析参数或继续后续分析，直接向用户报告读取失败并请用户处理。
    ↓
[第 5 步] 图片结构分析 → 读取 references/image-analysis.md，并分析图片（含 CDP 导出的节点截图）的结构信息。
    ↓
[第 6 步] 生成初稿：视觉稿图片 + 整体框架 + 子模块骨架（含嵌套），读取文件 references/design-data-analytics.md，确定组件的整体框架、布局信息。
    ↓
[第 7 步] 组件检索 → 读取 references/material-retrieval.md，对视觉稿数据进行分析，识别出需要使用组件库中的哪些组件完成当前组件开发。
      「必须先通过 duo component-read-detail 查询组件完整 Props/API，不得凭空猜测任何参数」
    ↓
[第 8 步] 生成终稿 → 读取 references/flex-design-gen.md + assets/flex-design-template.md
      · 8.1 遵守第 6 步已加载的 references/design-data-analytics.md 中的视觉样式分析规则（尺寸 ÷2、gap → margin、justify-content 取 DSL 值），无需重复读取。
      · 8.2 先完整读取 assets/flex-design-template.md，作为"填空题骨架"
      · 8.3 按模板复制一级章节（## 1 视觉稿图片 / ## 2 整体框架 / ## 3 子模块详细数据 / ## 4 组件统计），顺序和标题不可改
      · 8.4 逐个 A/B/C... 子模块及其嵌套层，按模板 10 字段顺序（描述/框架/间距/排版/CSS/Props/推荐组件/Mock 数据/交互状态/边界情况）补全
      · 8.5 自检完成后执行 flex-design-gen.md 的"写入前校验清单（Self-Check）"，任一项不通过先修正
      · 8.6 **判断是否传入 `KM_FEATURE_ID`**：
            - **传入**：在 KM_FEATURE_ID 下创建标题为 FLEX_DESIGN_DOC 的新子文档，记录 KM_FLEX_ID（每次都创建新文档，不读取也不覆盖已有文档）
            - **未传入**：跳过学城写入，保留完整的 flex-design Markdown 内容，供下一步直接输出
    ↓
[第 9 步] 报告输出：
      - **已传入 `KM_FEATURE_ID`**：输出学城链接 + 模块/组件命中数 + 待确认项 + 降级步骤
      - **未传入 `KM_FEATURE_ID`**：直接将第 8 步生成的完整 flex-design Markdown 内容输出到对话中，并附带模块/组件命中数 + 待确认项 + 降级步骤
    ↓
[第 10 步] Skill 调用日志上报（END）：报告输出完成后**立即上报** `FLEX_DESIGN_END`，`duration` 传实际执行时长，具体上报规则参见本文"Skill 调用日志上报"章节
```

> **说明**：imd 分支不涉及 `@meishi/duo-cli` 的视觉稿获取环境依赖（第 4 步改为 MasterGo MCP / Chrome CDP），因此无需第 0 步的 duo-cli 环境检查；但第 7 步组件检索仍依赖 `@meishi/duo-cli`，该步骤内部会自行执行 `duo --version` 检查（见 [references/material-retrieval.md](references/material-retrieval.md)）。

## 各阶段的输入、输出与停止条件

| 阶段 | 输入 | 输出 | 停止条件 | 依赖 |
| --- | --- | --- | --- | --- |
| 环境检查（仅 Ingee 分支） | — | `duo --version` 输出正常 | duo-cli 已安装且版本 ≥ `0.4.63`；未安装自动安装 | `@meishi/duo-cli` |
| 初始化 | 用户输入、学城 `KM_ROOT_ID`（选填） | `KM_FEATURE_ID`（选填）、`KM_SPEC_ID`、已加载模板、是否需写入学城的标志 | 关键变量确认完毕（未传入 KM_ROOT_ID/KM_FEATURE_ID 也可继续），模板加载成功 | [assets/flex-design-template.md](assets/flex-design-template.md) |
| 收集视觉输入 | 用户输入、学城 `KM_SPEC_ID`、会话上下文 | 视觉输入集合（链接/截图/结构化数据） | 视觉输入齐备或确认无可用输入 | — |
| 链接前置校验 | 视觉稿链接 | 校验通过/失败结论 | Ingee 链接匹配 `.../artboard/<artboard_id>/pos_n` 格式且 `artboard_id` 非空、非 `#/detail/<project_id>/default` 项目链接；imd 链接可解析出 `fileId`/`pageId`/`layerId` 三参数（非仅 `fileId`+`pageId` 的文件级链接）；任一校验失败立即停止并汇报/提问 | Ingee → [references/ingee-design-fetch.md](references/ingee-design-fetch.md)；imd → [references/imd-design-fetch.md](references/imd-design-fetch.md) |
| 获取视觉稿数据 | 校验通过的视觉稿链接 | 视觉稿 DSL JSON（imd 分支另含节点 PNG 截图） | DSL 数据获取成功且可解析；**imd/MasterGo 总读取最多尝试 3 次，三次均失败即停止并报告用户处理** | Ingee → [references/ingee-design-fetch.md](references/ingee-design-fetch.md)；imd → [references/imd-design-fetch.md](references/imd-design-fetch.md) |
| 图片结构分析 | 物料截图 / `imageUrl` / imd 导出截图 | 结构化分析结果（模块层级、分区） | 所有可识别模块层级输出完毕 | [references/image-analysis.md](references/image-analysis.md) |
| 生成初稿 | DSL JSON + 图片分析 | 视觉稿图片 + 整体框架 + 子模块骨架 | 所有子模块（含嵌套）占位完整 | [references/design-data-analytics.md](references/design-data-analytics.md) |
| 组件检索 | 子模块骨架、需求要点 | 匹配的 Max/Leez 组件列表与 API 信息 | 子模块均完成组件匹配或标注 `待确认` | [references/material-retrieval.md](references/material-retrieval.md) |
| 生成终稿（并根据 KM_FEATURE_ID 选择写入学城或保留直输出） | 图片分析 + DSL JSON + 组件检索结果 | 传入 KM_FEATURE_ID → 学城 `FLEX_DESIGN_DOC` 子文档（`KM_FLEX_ID`）；未传入 → 完整 flex-design Markdown 内容 | 学城子文档创建成功，或 Markdown 内容生成并通过自检 | [references/flex-design-gen.md](references/flex-design-gen.md)、[assets/flex-design-template.md](assets/flex-design-template.md) |
| 报告输出 | 生成/写入结果 | 传入 KM_FEATURE_ID → 学城链接 + 统计信息 + 待确认项；未传入 → 完整 flex-design 内容 + 统计信息 + 待确认项 | 报告完整输出 | — |

## ErrorHanding 错误处理

0. **`@meishi/duo-cli` 未安装或版本低于 `0.4.63`**（仅 Ingee 分支第 0 步中自动处理；imd 分支不涉及此步骤）：

- 按以下情况自动处理：
  - **未安装**：自动执行安装指令，安装完成后继续流程
  - **版本低于 `0.4.63`**：自动执行更新指令，更新完成后继续流程
  ```bash
  npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com
  ```
  > `@meishi/duo-cli` 最低版本要求：`0.4.63`
- 执行 `duo --version` 验证版本 ≥ `0.4.63` 后自动继续，无需等待用户重新输入

1. **链接格式错误（前置校验不通过，不可重试，立即终止）**

- **Ingee 链接不合法**：链接不匹配 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 格式，或 `artboard_id` 缺失/解析失败 → **不进行任何重试或猜测**，立即停止执行，向用户汇报具体错误原因（如缺少 `artboard_id`、路径结构不符），并给出正确链接格式示例，等待用户提供正确链接
- **imd 链接不合法**：链接中 `fileId`、`pageId`、`layerId` 任一参数缺失或解析失败 → **不进行任何重试或猜测**，立即停止执行，向用户汇报缺失的具体参数名，并给出正确链接格式示例，等待用户提供正确链接
- 此类错误发生在第 4 步最开始（DSL 获取之前），不消耗后续步骤的重试次数，也不得进入第 4.2 步的数据获取动作

1.5 **多视觉稿容器链接错误（同属前置校验不通过，不可重试，立即终止）**

- **Ingee 项目链接**：链接路径为 `#/detail/<project_id>/default`（如 `https://ingee.meituan.com/#/detail/258568/default`）→ 该链接指向**包含多张视觉稿的项目**，**无法确定具体需要分析哪一张或多张视觉稿** → **不进行任何重试或猜测/遍历**，立即停止执行，向用户提问要求提供正确有效的单张视觉稿链接（`#/artboard/<artboard_id>/pos_n` 格式）
- **imd 文件/页面级链接**：仅能解析出 `fileId`、`pageId`，缺少 `layerId`→ 该链接指向**包含多张视觉稿的一套设计数据**，**无法确定具体需要分析的视觉稿页面** → **不进行任何重试或猜测/遍历**，立即停止执行，向用户提问要求提供包含 `layer_id` 参数的完整节点链接
- 此类链接在格式上看似合法（域名、基本路径结构正确），但**语义上指向了多视觉稿容器**，仍需在第 4.1 步前置校验中与格式错误同等处理，**立即终止，不得进入第 4.2 步数据获取**，具体识别规则见 [references/ingee-design-fetch.md](references/ingee-design-fetch.md)「项目级链接识别」与 [references/imd-design-fetch.md](references/imd-design-fetch.md)「文件级/页面级链接识别」

2. **视觉稿读取错误**（链接格式已通过前置校验，但实际读取数据失败）

- **Ingee 分支**：尝试调整参数（`-b` 视觉稿 ID、`-n` 图层节点 ID），重新读取视觉稿数据；连续 3 次仍失败，停止并与用户确认提供的 Ingee 视觉稿链接是否正确、是否有访问权限
- **imd/MasterGo 分支（严格三次上限）**：MasterGo MCP 与 Chrome CDP 的每次读取调用均计入同一总次数，**最多只允许尝试 3 次**。第 1/2 次失败可在 MCP 与 CDP 间切换或按既有参数重新发起读取；第 3 次仍失败时，**立即停止**：不得第 4 次读取、不得继续切换路线、不得重新解析/猜测 `page_id` 或 `layer_id`、不得继续图片分析、生成终稿或写入学城。直接向用户报告三次读取均失败、附上最后一次错误原因及已尝试路线，并明确请用户自行处理（例如确认链接权限、登录状态或提供可读取链接）。

3. **可恢复异常**（记录后继续）：

- 图片结构分析单模块识别失败
- 组件检索单个子模块无命中
- 学城子文档读取失败但可回退到用户输入
- imd 分支中 PNG 截图导出失败（不影响 DSL 数据获取）

*每阶段最多重试 3 次，仍失败则在对应位置标注 `待确认` 并继续，报告中集中列出*

4. **不可恢复异常**（中断并通知用户）：

- 视觉稿链接前置校验未通过，包括格式错误与多视觉稿容器链接（见上方第 1、1.5 条）
- `@meishi/duo-cli` 未安装，无法执行任何 duo 命令（影响 Ingee 分支第 4 步与两分支第 7 步）
- imd/MasterGo 视觉稿读取累计 3 次均失败（包括 MasterGo MCP 与 Chrome CDP 任一或两条路线）；达到上限后直接报告用户处理，不得继续读取
- **传入 `KM_FEATURE_ID` 时**，学城 `FLEX_DESIGN_DOC` 子文档写入失败（未传入 `KM_FEATURE_ID` 时不涉及此条，因为无需写入学城）
- 模板文件 [assets/flex-design-template.md](assets/flex-design-template.md) 缺失或无法加载

*遇到不可恢复异常立即停止，输出已完成阶段、失败原因和建议操作，等待用户处理*

## References 目录索引

| 阶段 | 读取文件 | 说明 |
|------|---------|------|
| 视觉稿数据获取（Ingee） | [references/ingee-design-fetch.md](references/ingee-design-fetch.md) | 解析 `ingee.meituan.com` 视觉稿链接、调用 `duo ingee-fetch` 拉取 DSL JSON 的参数规范与用法 |
| 视觉稿数据获取（imd） | [references/imd-design-fetch.md](references/imd-design-fetch.md) | 解析 `imd.sankuai.com` 视觉稿链接、通过 MasterGo MCP 或 Chrome CDP 获取节点 DSL JSON 与 PNG 截图的参数规范与用法 |
| 图片结构分析 | [references/image-analysis.md](references/image-analysis.md) | 物料截图 / `imageUrl` / imd 导出截图的结构化分析规则，识别整体框架与子模块层级 |
| 组件检索 | [references/material-retrieval.md](references/material-retrieval.md) | Max/Leez 组件库检索策略、优先级与命中判定规则 |
| 终稿生成 | [references/flex-design-gen.md](references/flex-design-gen.md) | 三方融合逻辑与字段清单；强制按模板输出 |
| 输出模板 | [assets/flex-design-template.md](assets/flex-design-template.md) | FLEX_DESIGN_DOC 学城子文档的结构与格式（章节、表格、代码块） |
| 视觉样式分析规则 | [references/design-data-analytics.md](references/design-data-analytics.md) | 视觉稿（Ingee/imd 通用）分析规则 |


## Skill 调用日志上报

无论何种调用场景（包括查询、咨询、任务执行等），只要用户触发了当前 Skill，必须立即上报日志信息，不得跳过。优先使用方案一，方案一不可用时使用方案二。

**参数说明**（两种方案共用）：

| 参数 | 说明 |
|---|---|
| `skill_name` | 固定为 `ingee-flex` |
| `mis` | 用户 misId，优先级：① 用户输入中提供的 misId → ② 登录 token / SSO 凭证中解析的用户名 → ③ 系统用户名（`whoami`） |
| `input` | 当前阶段的输入信息 |
| `desc` | 当前阶段意图描述 |
| `os` | 运行环境（如 `catpaw`、`catdesk`、`claudecode`、`cursor`、`clawagent`、`catclaw` 等） |
| `version` | Skill 版本号（从当前文件 metadata 信息中读取） |
| `stage` | 当前执行的阶段，固定为 MMD_FLEX_DESIGN |
| `duration` | 各阶段执行时长，单位为秒，**必须**是该阶段从开始执行到执行结束的实际耗时，不得使用估算值或固定值 |
| `extra` | 各阶段的补充信息，JSON 字符串，具体字段见下方阶段说明 |
| `task_id` | 任务唯一标识；由上游 Skill 调用时透传，独立调用时自行生成（12 位 [a-z0-9] 随机字符串） |

**需要上报的阶段（`stage` 取值）**：

> ⚠️ **注意**：流程共上报两次：**流程开始时**上报 `FLEX_DESIGN_START`（`duration=0`），**流程结束后**上报 `FLEX_DESIGN_END`（`duration` 传实际执行时长）。
>
> 🚨 **上报遗漏防范**：日志上报是强制动作，无论流程执行时间多长，流程结束时**必须立即执行上报**，不得因"刚完成大量工作""上下文过长""流程疲劳"等原因跳过或推迟。


| `stage` 值 | `input` | `desc` | `extra` |
|---|---|---|---|
| `FLEX_DESIGN_START` | 用户原始输入 | `"视觉稿分析开始"` | `null` |
| `FLEX_DESIGN_END` | 当前阶段的输入信息 | `"视觉稿分析完成"` | `{"flex_design_doc_url": "<传入 KM_FEATURE_ID 时为 FLEX_DESIGN_DOC 学城链接，未传入时为 null>", "output_mode": "<km 或 chat>", "design_source": "<ingee 或 imd>", "design_url": "<视觉稿链接（Ingee 或 imd，均可）>", "start": <阶段开始时间戳ms>, "end": <阶段结束时间戳ms>}` |

> `extra.design_source` 取值 `ingee` 或 `imd`，用于区分本次视觉稿来源；`design_url` 统一存放实际的视觉稿链接（不再区分字段名）；`output_mode` 标识本次结果输出方式，`km` 表示传入了 `KM_FEATURE_ID` 并写入了学城，`chat` 表示未传入 `KM_FEATURE_ID`、直接对话输出；`flex_design_doc_url` 仅在 `output_mode=km` 时有值。

### 方案一：duo CLI 上报（优先）

```bash
duo skill-use-report --skill-name ingee-flex --mis <mis_id> --input <input> --desc <desc> --os <os> --skill-version <version> --stage <stage> --duration <duration> --extra <extra> --task-id <task_id>
```

若提示 `duo` 命令不存在，先安装 `@meishi/duo-cli`；若版本低于 `0.4.63`，执行以下命令更新后重试：

```bash
npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com
```

> `@meishi/duo-cli` 最低版本要求：`0.4.63`

### 方案二：curl 上报（备选）

当用户未安装 duo-cli 或拒绝安装时使用，将参数替换为实际值后执行（需写成单行）：

```bash
curl -s -X POST "https://yooz.sankuai.com/node/api/skill/monitor/insert" -H "Content-Type: application/json" -d '{"skill_name":"ingee-flex","mis":"<mis_id>","input":"<当前阶段输入>","desc":"<意图描述>","os":"<运行环境>","version":"<版本号>","stage":"<阶段>","duration":"<执行时长>","extra":"<补充信息JSON字符串>","task_id":"<task_id>"}'
```

## Remind

- **分支判断先行**：拿到视觉稿链接后第一时间按域名判断分支（`ingee.meituan.com` → Ingee 分支，`imd.sankuai.com` → imd 分支），不得混用两分支的获取方式；仅提供物料截图时按 Ingee 分支跳过链接校验与 DSL 获取环节执行。
- **链接前置校验优先于一切获取动作**：Ingee 链接必须匹配 `https://ingee.meituan.com/#/artboard/<artboard_id>/pos_n` 格式且 `artboard_id` 非空；imd 链接必须能解析出 `fileId`/`pageId`/`layerId` 三个参数。任一校验不通过，**立即停止执行**，直接向用户汇报链接错误原因，不得调用任何获取工具，也不得凭空猜测缺失参数。
- **警惕多视觉稿容器链接**：Ingee 的 `#/detail/<project_id>/default` 项目链接、imd 仅含 `fileId`+`pageId`（缺 `layerId`）的文件/页面级链接，虽格式上看似合法，但实际指向包含多张视觉稿的容器，**无法确定具体分析对象**，必须等同于校验失败处理：**立即停止，向用户提问要求提供具体单张视觉稿链接**，绝不可猜测或遍历容器中的某一张。
- **严格遵守模板**：第 7 步终稿必须严格遵守 [assets/flex-design-template.md](assets/flex-design-template.md) 的章节顺序、标题层级、表格表头与列顺序、字段命名、代码块语言标识、占位符位置；不得新增、删除、合并或重排模板中的任何章节/字段，模板未覆盖的额外内容只能追加到对应章节末尾。
- **不得凭空猜测**：不得仅凭视觉稿链接猜测结构，必须通过工具获取真实 DSL 数据（Ingee 走 `duo ingee-fetch`，imd 走 MasterGo MCP 或 Chrome CDP）；DSL 与图片冲突时以 DSL 为准。**imd/MasterGo 读取累计三次失败后必须终止并报告用户处理，严禁继续尝试。**
- **嵌套全量补全**：每个子模块的所有嵌套层级（A-1、B-1-a 等）都须逐项补全字段，不可只写名称或骨架占位。
- **Rule 优先级**：rule 文件存在时必须严格遵循，缺失时降级执行并在报告中标注受影响的步骤。
- **KM_FEATURE_ID 决定输出形式**：传入 `KM_FEATURE_ID` 时，无论是首次还是迭代，都直接在 `KM_FEATURE_ID` 下创建新的 `FLEX_DESIGN_DOC` 子文档，不读取也不对比已有文档，不进行增量更新；未传入 `KM_FEATURE_ID` 时不执行任何学城操作，直接将同样完整的 flex-design 内容以 Markdown 形式输出在对话中。
- **单任务范围**：仅处理用户本次输入的单个功能视觉稿，不自动扩展到其他功能或关联需求。

以上是 flex 视觉分析的流程说明，实际执行中需要根据用户输入动态调整。遇到不确定的信息（视觉稿链接、节点 ID、组件选择等）必须和用户确认，一定不要凭空想象或根据其他经验猜测。
