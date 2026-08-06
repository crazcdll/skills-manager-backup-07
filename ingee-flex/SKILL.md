---
name: ingee-flex
description: 执行视觉与图片分析、视觉稿数据获取与组件检索，生成学城 `FLEX_DESIGN_DOC` 子文档。涵盖视觉稿图片 + 视觉稿 DSL 数据 + 框架分析 + 组件映射（完整综合层）。触发词："flex"、"视觉分析"、"分析视觉稿"、"生成flex-design"。

metadata:
  skillhub.creator: "wb_wangjing63"
  skillhub.updater: "hejun10"
  skillhub.version: "V27"
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
| Ingee 视觉稿链接 / 物料截图 | string | ✅ | 视觉输入来源；二者至少提供其一 |
| `KM_ROOT_ID` | string | ✅ | 学城根文档 ID |
| `KM_FEATURE_ID` | string | ✅ | 学城功能子文档 ID，`FLEX_DESIGN_DOC` 将挂在其下 |
| `KM_SPEC_ID` | string | ❌ | 学城 `spec需求分析` 子文档 ID；提供时作为视觉输入补充 |
| `task_id` | string | ❌ | 任务唯一标识；由上游 Skill（如 max-material-dev）调用时透传，独立调用时自行生成（12 位 [a-z0-9] 随机字符串） |

### 输出

| 产物 | 说明 |
|------|------|
| 学城 `FLEX_DESIGN_DOC` 子文档 | 视觉稿结构化分析结果（`KM_FLEX_ID`），含视觉稿图片、整体框架、子模块详细数据、组件统计 |
| `task_id` | 透传给调用方（独立调用时输出本次生成的 `task_id`，供后续阶段使用） |

---

## Introduction 介绍

视觉分析与组件映射 → 学城 `FLEX_DESIGN_DOC` 子文档。在方案设计阶段前完成视觉与组件分析准备，将视觉稿图片、DSL 数据、图片结构分析与 Max/Leez 组件检索结果融合，严格按模板输出到学城 `FLEX_DESIGN_DOC` 子文档（挂在 `KM_FEATURE_ID` 下），供后续 plan/design 阶段作为视觉输入。

## Function 功能

- **初始化与模板加载**：解析学城关键变量（`KM_ROOT_ID`、`KM_FEATURE_ID`、`KM_SPEC_ID`），加载 [assets/flex-design-template.md](assets/flex-design-template.md) 作为输出模板
- **视觉输入收集**：聚合用户输入的图片/视觉稿链接、学城 `SPEC_DOC` 子文档中的视觉要求、会话内已存在的截图与结构化数据，按优先级解决冲突
- **视觉稿 DSL 获取**：通过 `duo ingee-fetch` CLI 拉取 Ingee 视觉稿 DSL JSON 数据
- **图片结构分析**：对物料截图或视觉稿返回的 `imageUrl` 执行结构化分析，识别模块层级
- **组件检索**：从 Max/Leez 组件库检索可用组件（通过 `duo component-list -t \"leez,max\"` 查询组件列表，通过 `duo component-read-detail -p \"<pkg>\"` 获取组件详情）
- **三方融合生成终稿**：图片分析 + DSL JSON + 组件检索结果融合，严格按模板逐模块补全所有字段
- **学城写入**：在学城 `KM_FEATURE_ID` 下创建标题为 `FLEX_DESIGN_DOC` 的子文档，返回 `KM_FLEX_ID`（每次都创建新文档，不读取也不覆盖已有文档）

## When to Use 使用场景

**需要将视觉稿/物料截图转化为结构化 flex-design 学城文档**时使用：

- 用户提供 Ingee 视觉稿链接（ingee.meituan.com），要求生成 flex-design
- 用户提供物料截图并要求进行视觉结构分析与组件映射
- 在 max-material-dev 完整开发流程中被调用，完成视觉稿数据分析阶段

示例："flex"、"视觉分析"、"分析视觉稿"、"生成 flex-design"、"帮我分析这个 Ingee 视觉稿"

## When NOT to Use 不使用场景

以下场景**不触发**此 Skill：

- **无视觉输入**：既无视觉稿链接也无物料截图
- **纯文本需求澄清**：只讨论需求文字/业务逻辑，不涉及视觉结构分析
- **非视觉稿数据分析**：只需要读写学城文档、只做组件检索而无需生成 flex-design
- **非 Max/Leez 体系**：通用 React/Vue 组件视觉分析，与 Max/Leez 组件库无关

## Scope 能力边界

- Ingee 视觉稿 DSL 数据获取
- 物料图片/截图结构化分析
- Max/Leez 组件检索与映射
- flex-design 学城子文档的生成与写入
- 不负责 spec/design/tasks/implement 阶段产物，也不执行代码开发与测试

## Rule 执行约定

以下步骤 3、4、6、7 均涉及 rule，统一遵循以下优先级：

1. **有 rule 文件** → 读取并严格遵循该 rule 执行
2. **有用户输入的 rule** → 参考用户输入的 rule 执行
3. **均无** → 基于通用认知执行，结果标注

## MainStep 核心流程

```
用户输入：视觉稿链接 / 物料截图 / 视觉要求描述
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
[第 2 步] 初始化：解析 KM_ROOT_ID / KM_FEATURE_ID / KM_SPEC_ID，加载 flex-design-template.md
    ↓
[第 3 步] 收集视觉输入：用户输入 + 学城 `SPEC_DOC` + 会话上下文
    ↓
[第 4 步] 获取视觉稿 DSL 数据 → 读取 references/ingee-design-fetch.md
    ↓
[第 5 步] 图片结构分析 → 读取 references/image-analysis.md，并分析图片的结构信息。
    ↓
[第 6 步] 生成初稿：视觉稿图片 + 整体框架 + 子模块骨架（含嵌套），读取文件 references/ingee-data-analytics.md，确定组件的整体框架、布局信息。
    ↓
[第 7 步] 组件检索 → 读取 references/material-retrieval.md，对视觉稿数据进行分析，识别出需要使用组件库中的哪些组件完成当前组件开发。
      「必须先通过 duo component-read-detail 查询组件完整 Props/API，不得凭空猜测任何参数」
    ↓
[第 8 步] 生成终稿并写入学城 → 读取 references/flex-design-gen.md + assets/flex-design-template.md
      · 8.1 遵守第 6 步已加载的 references/ingee-data-analytics.md 中的视觉样式分析规则（尺寸 ÷2、gap → margin、justify-content 取 DSL 值），无需重复读取。
      · 8.2 先完整读取 assets/flex-design-template.md，作为"填空题骨架"
      · 8.3 按模板复制一级章节（## 1 视觉稿图片 / ## 2 整体框架 / ## 3 子模块详细数据 / ## 4 组件统计），顺序和标题不可改
      · 8.4 逐个 A/B/C... 子模块及其嵌套层，按模板 10 字段顺序（描述/框架/间距/排版/CSS/Props/推荐组件/Mock 数据/交互状态/边界情况）补全
      · 8.5 写入前执行 flex-design-gen.md 的"写入前校验清单（Self-Check）"，任一项不通过先修正不得写入
      · 8.6 在 KM_FEATURE_ID 下创建标题为 FLEX_DESIGN_DOC 的新子文档，记录 KM_FLEX_ID（每次都创建新文档，不读取也不覆盖已有文档）
    ↓
[第 9 步] 报告输出：学城链接 + 模块/组件命中数 + 待确认项 + 降级步骤
    ↓
[第 10 步] Skill 调用日志上报（END）：报告输出完成后**立即上报** `FLEX_DESIGN_END`，`duration` 传实际执行时长，具体上报规则参见本文"Skill 调用日志上报"章节
```

## 各阶段的输入、输出与停止条件

| 阶段 | 输入 | 输出 | 停止条件 | 依赖 |
| --- | --- | --- | --- | --- |
| 环境检查 | — | `duo --version` 输出正常 | duo-cli 已安装且版本 ≥ `0.4.63`；未安装自动安装 | `@meishi/duo-cli` |
| 初始化 | 用户输入、学城 `KM_ROOT_ID` | `KM_FEATURE_ID`、`KM_SPEC_ID`、已加载模板 | 关键变量全部确认，模板加载成功 | [assets/flex-design-template.md](assets/flex-design-template.md) |
| 收集视觉输入 | 用户输入、学城 `KM_SPEC_ID`、会话上下文 | 视觉输入集合（链接/截图/结构化数据） | 视觉输入齐备或确认无可用输入 | — |
| 获取视觉稿数据 | 视觉稿链接 | 视觉稿 DSL JSON | DSL 数据获取成功且可解析 | [references/ingee-design-fetch.md](references/ingee-design-fetch.md) |
| 图片结构分析 | 物料截图 / `imageUrl` | 结构化分析结果（模块层级、分区） | 所有可识别模块层级输出完毕 | [references/image-analysis.md](references/image-analysis.md) |
| 生成初稿 | DSL JSON + 图片分析 | 视觉稿图片 + 整体框架 + 子模块骨架 | 所有子模块（含嵌套）占位完整 | [references/ingee-data-analytics.md](references/ingee-data-analytics.md) |
| 组件检索 | 子模块骨架、需求要点 | 匹配的 Max/Leez 组件列表与 API 信息 | 子模块均完成组件匹配或标注 `待确认` | [references/material-retrieval.md](references/material-retrieval.md) |
| 生成终稿并写入学城 | 图片分析 + DSL JSON + 组件检索结果 | 学城 `FLEX_DESIGN_DOC` 子文档（`KM_FLEX_ID`） | 学城子文档创建成功 | [references/flex-design-gen.md](references/flex-design-gen.md)、[assets/flex-design-template.md](assets/flex-design-template.md) |
| 报告输出 | 写入结果 | 学城链接 + 统计信息 + 待确认项 | 报告完整输出 | — |

## ErrorHanding 错误处理

0. **`@meishi/duo-cli` 未安装或版本低于 `0.4.63`**（在第 0 步中自动处理）：

- 按以下情况自动处理：
  - **未安装**：自动执行安装指令，安装完成后继续流程
  - **版本低于 `0.4.63`**：自动执行更新指令，更新完成后继续流程
  ```bash
  npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com
  ```
  > `@meishi/duo-cli` 最低版本要求：`0.4.63`
- 执行 `duo --version` 验证版本 ≥ `0.4.63` 后自动继续，无需等待用户重新输入

1. **Ingee 视觉稿读取错误**

- 尝试调整参数（`-b` 视觉稿 ID、`-n` 图层节点 ID），重新读取视觉稿数据
- 连续 3 次仍失败，停止并与用户确认提供的 Ingee 视觉稿链接是否正确、是否有访问权限

2. **可恢复异常**（记录后继续）：

- 图片结构分析单模块识别失败
- 组件检索单个子模块无命中
- 学城子文档读取失败但可回退到用户输入

*每阶段最多重试 3 次，仍失败则在对应位置标注 `待确认` 并继续，报告中集中列出*

3. **不可恢复异常**（中断并通知用户）：

- `@meishi/duo-cli` 未安装，无法执行任何 duo 命令
- 学城 `FLEX_DESIGN_DOC` 子文档写入失败
- 模板文件 [assets/flex-design-template.md](assets/flex-design-template.md) 缺失或无法加载

*遇到不可恢复异常立即停止，输出已完成阶段、失败原因和建议操作，等待用户处理*

## References 目录索引

| 阶段 | 读取文件 | 说明 |
|------|---------|------|
| 视觉稿数据获取 | [references/ingee-design-fetch.md](references/ingee-design-fetch.md) | 解析视觉稿链接、调用 `duo ingee-fetch` 拉取 DSL JSON 的参数规范与用法 |
| 图片结构分析 | [references/image-analysis.md](references/image-analysis.md) | 物料截图 / `imageUrl` 的结构化分析规则，识别整体框架与子模块层级 |
| 组件检索 | [references/material-retrieval.md](references/material-retrieval.md) | Max/Leez 组件库检索策略、优先级与命中判定规则 |
| 终稿生成 | [references/flex-design-gen.md](references/flex-design-gen.md) | 三方融合逻辑与字段清单；强制按模板输出 |
| 输出模板 | [assets/flex-design-template.md](assets/flex-design-template.md) | FLEX_DESIGN_DOC 学城子文档的结构与格式（章节、表格、代码块） |
| 输出模板 | [references/ingee-data-analytics.md](references/ingee-data-analytics.md) | ingee 视觉稿分析规则 |


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
| `FLEX_DESIGN_END` | 当前阶段的输入信息 | `"视觉稿分析完成"` | `{"flex_design_doc_url": "<FLEX_DESIGN_DOC 学城链接>", "ingee_url": "<Ingee 视觉稿链接>", "start": <阶段开始时间戳ms>, "end": <阶段结束时间戳ms>}` |

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

- **严格遵守模板**：第 7 步终稿必须严格遵守 [assets/flex-design-template.md](assets/flex-design-template.md) 的章节顺序、标题层级、表格表头与列顺序、字段命名、代码块语言标识、占位符位置；不得新增、删除、合并或重排模板中的任何章节/字段，模板未覆盖的额外内容只能追加到对应章节末尾。
- **不得凭空猜测**：不得仅凭视觉稿链接猜测结构，必须通过工具获取真实 DSL 数据；DSL 与图片冲突时以 DSL 为准。
- **嵌套全量补全**：每个子模块的所有嵌套层级（A-1、B-1-a 等）都须逐项补全字段，不可只写名称或骨架占位。
- **Rule 优先级**：rule 文件存在时必须严格遵循，缺失时降级执行并在报告中标注受影响的步骤。
- **每次生成新文档**：无论是首次还是迭代，都直接在 `KM_FEATURE_ID` 下创建新的 `FLEX_DESIGN_DOC` 子文档，不读取也不对比已有文档，不进行增量更新。
- **单任务范围**：仅处理用户本次输入的单个功能视觉稿，不自动扩展到其他功能或关联需求。

以上是 flex 视觉分析的流程说明，实际执行中需要根据用户输入动态调整。遇到不确定的信息（视觉稿链接、节点 ID、组件选择等）必须和用户确认，一定不要凭空想象或根据其他经验猜测。
