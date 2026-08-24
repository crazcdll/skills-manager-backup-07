---
name: infra-codebase
description: "使用 infra-codebase CLI 查询已索引 APP 和代码仓库。适用于查询 APP 在 Android、iOS、HarmonyOS 下的版本、组件依赖与跨组件源码关系，以及单仓内的符号上下文、调用链、实现逻辑和影响面。"

metadata:
  skillhub.creator: "yangshunyu"
  skillhub.updater: "yangshunyu"
  skillhub.version: "V17"
  skillhub.source: "ssh://git@git.sankuai.com/met/gitnexus-common.git"
  skillhub.skill_id: "80891"
  skillhub.high_sensitive: "false"
---

# Infra Codebase 查询技能

使用 `infra-codebase` CLI 查询已索引的客户端代码知识库。查询前先保证全局 CLI 是最新版本，并按用户或仓库约定设置 `INFRA_CODEBASE_BASEURL` 和 `INFRA_CODEBASE_TOKEN`。

```bash
LATEST=$(npm view @mtfe/infra-codebase-cli version --registry=http://r.npm.sankuai.com 2>/dev/null)
INSTALLED=$(infra-codebase --version 2>/dev/null)
if [ "$INSTALLED" != "$LATEST" ]; then
  npm i -g @mtfe/infra-codebase-cli --registry=http://r.npm.sankuai.com
fi
```

## 查询入口

查询从 APP 版本能力开始：先执行 `infra-codebase capabilities`，确定已索引 APP、平台及其最新可查询版本，后续命令只使用能力入口或下钻结果返回的精确值。

```bash
infra-codebase capabilities
infra-codebase capabilities --app-name <appName>
infra-codebase capabilities --platform <android|ios|harmonyos>
```

- 首次执行不加过滤，使用返回的完整 Profile 知识识别用户所指 APP；优先按 `appName`、`displayName`、`aliases` 匹配，英文按大小写无关比较，`description` 只用于多个候选之间消歧，不作为弱匹配命中依据。
- 完全没有出现任何 APP 信号的具体查询默认选择返回的 `defaultAppName`（当前为 `meituan`），并在回答中说明。用户明确给出的名称未知或同时命中多个 APP 时，不得回退默认值，应列出候选并要求确认。
- 能力发现类问题不默认选择单一 App，直接汇总清单。
- 查询最新版本时直接使用目标 APP 的 `latest`。最新 APP 版本以 full-code 登记的 `versionSortKey DESC, id DESC` 为准；`depsVersion` 只在这个精确 APP 版本已有依赖数据时出现，`fullCodeVersion` 与 `fullCodeGroupKey` 指向同一版本。字段缺失表示该版本没有对应能力。
- 用户指定历史版本、比较版本或询问支持范围时，才调用 `catalog versions`：

```bash
infra-codebase catalog versions --app-name <appName> [--platform <platform>] [--app-version <version>] [--capability deps|full-code|all] [--limit 20] [--cursor <cursor>]
```

- 精确版本先加 `--app-version` 查询。结果为空时，再去掉该参数读取同 APP、平台、能力的候选，并按原规则向后选择前两段版本号相同（不跨 `major.minor`）的最近可用版本。只有用户明确要求完整历史时使用 `--all`。
- 具体查询任务缺平台时，查询目标 App 在相关能力下已有数据的所有平台最新版本，并在回答中分平台说明。
- `catalog versions` 的 `page.hasMore=true` 时使用 `nextCursor` 继续一页；`repoPage` 按分页提示继续。`deps members` 不分页，按下述筛选规则控制返回量。只有用户明确要求全部拉完时才扩大范围。
- 最终回答注明实际使用的 `appName`、`platform`、`appVersion` 或 `fullCodeGroupKey`；未读完分页结果时说明 `hasMore`。

兼容与排障时仍可使用旧链路，旧 CLI 和旧 Skill 的字段、分页及命令语义保持不变；新版正常查询不要优先走它：

```bash
infra-codebase capabilities list
infra-codebase capabilities versions --app-name <appName> [--platform <platform>] --capability deps|full-code|all
```

只有用户明确提出按业务域（Scope）查询时，才读取 [Scope 单仓发现](references/scope-single-repo-discovery.md)，由 Scope 当前状态或命名版本定位成员单仓；未提及时不启用 Scope。

## 能力选择

| 问题中的信号 | 可用能力 | 最适合证明什么 |
|---|---|---|
| App 版本、组件上下游、跨版本差异 | `deps` | 版本清单和组件级依赖 |
| 跨组件调用方、组件未知、App 内源码影响面 | `full-code` | 指定 App 快照内的跨组件关系与源码 |
| 已知单仓符号、调用链、实现和影响面 | `repo lookup/context/impact` | 符号消歧与图关系 |
| 模糊业务概念或尚无精确锚点 | `repo query` | 发现候选执行流、符号和文件 |
| 已知文件路径、需要完整上下文 | `repo read` | 精确文件内容或指定行区间 |
| 需要文件盘点、路径模式或搜索范围 | `repo files` | 已索引文件集合；不是 read 的固定前置步骤 |
| 常规能力无法表达的只读结构问题 | `repo cypher` | 面向图 Schema 的专家查询 |

此表提供选择信号，不是固定流水线。根据已有线索从信息量高、成本低的能力开始，可以跳过任何不需要的步骤，也可以组合语义、文本和关系查询。

- 已有输出足以支持结论时停止，不要为了换一种工具重复读取同一事实。`context --content`、`repo read`、full-code 源码和只读 Cypher 都可以提供源码证据。
- `repo files` 只在确实需要盘点文件或探索路径时使用；已知路径可以直接 read。
- 不要先枚举全仓文件再逐个 `read`，也不要用 `repo cypher` 或 full-code Cypher 扫描 `File.content` 来重建已收缩的全仓文本能力；这些入口用于精确文件、符号关系和有界结构查询。
- `repo read` 能证明指定文件中的源码文本，不能单独证明调用关系。回答“谁调用、如何流转、影响谁”时，按证据缺口补 `context`、`impact` 或 full-code 关系查询。
- `repo query` 可用于低成本发现候选；仅知道文本锚点但没有文件或符号定位时，先用小 `limit` 召回候选，再通过 `read` 或 `context --content` 核验。语义查询空结果不是全仓字面量不存在的证明。
- 做“没有调用方”“仅此一处”等负面断言时，必须说明检索边界，并使用覆盖该边界的 full-code 关系查询；当前面向 AI 的单仓入口无法穷举证明任意文本在全仓不存在。
- APP 和平台一旦按用户信号或默认规则确定，不要仅因其他 APP 出现同名关键词就扩大查询；只有用户要求跨 APP、能力盘点，或目标平台在当前 APP 无数据时才扩展范围。
- 问组件上下游依赖时使用 `deps show`；`repo impact` 表达的是符号级影响，不能替代组件级依赖。
- 仅支持 `android`、`ios`、`harmonyos`；其他平台直接说明暂不支持。
- 某一路能力无数据，只说明该能力当前无数据，不否定其他能力。

## deps：版本组件与依赖

```bash
# 最新版本直接取 capabilities.latest[].depsVersion；历史版本才执行：
infra-codebase catalog versions --app-name <appName> [--platform <platform>] [--app-version <appVersion>] --capability deps
infra-codebase deps members <platform> <appVersion> --app-name <appName> --q <keyword>
infra-codebase deps show <platform> <appVersion> <repoId> --app-name <appName>
infra-codebase deps diff <platform> <fromAppVersion> <toAppVersion> [repoId] --app-name <appName>
```

- `deps members` 不支持分页，也不接收 `--limit`：存在 `--q` 或非 `all` 的 `--type` 筛选时，按 `repoId ASC, id DESC` 返回前 20 条详细记录；`memberResult.truncated=true` 表示仍有更多匹配项，应继续收窄关键词或筛选条件，不能翻页。
- 不传 `--q` 且不传 `--type`（或显式 `--type all`）时，返回全量成员，但每条仅含 `repoId`、`componentVersion`、`indexed`、`indexStatus` 四个必要字段；该模式只用于全量盘点，不用于定位具体组件。
- 查具体组件前先用 `deps members ... --q <keyword>` 定位候选，再用精确 `repoId` 调 `deps show`。
- `indexStatus="pending"` 或 `indexed=false` 表示该组件在依赖清单中存在，但当前没有可查源码；对用户统一归类为“三方/无源码”，只能回答版本依赖信息，不能继续做 `repo` 单仓查询。
- `indexStatus="exact"` 且 `indexed=true` 表示可以继续做 `repo` 查询；使用该成员返回的 `<repoId>@<componentVersion>` 精确查询对应组件快照。
- 如果目标 App/平台没有 deps 版本，说明该平台版本依赖数据尚未导入。
- 比较两个 App 版本时直接使用 `deps diff`。传精确 `repoId` 时读取 `component.same` 和 `component.status`；不传时 `changes` 只包含变更组件，并用 `changed` / `added` / `removed` 区分版本变化、新增和移除。
- `deps diff` 以精确 `repoId` 为组件主键，`beforeVersion` / `afterVersion` 按字符串精确比较，不推断组件版本的语义顺序。指定组件在两个版本中都不存在时返回 `status="missing"`、`same=null`。

## full-code：App 全源码图

```bash
# 最新版本直接取 capabilities.latest[].fullCodeGroupKey；历史版本才执行：
infra-codebase catalog versions --app-name <appName> [--platform <platform>] [--app-version <appVersion>] --capability full-code
infra-codebase schema full-code <android|ios|harmonyos>
infra-codebase full-code query <groupKey> '<cypher with LIMIT>'
```

- `groupKey` 使用能力入口的 `fullCodeGroupKey` 或历史目录返回值，例如 `android:12.60.203:meituan`。
- 同一轮同一平台只读取一次 `schema full-code <platform>`，后续复用。
- Cypher 必须自行包含 `LIMIT`。
- 如果目标 App/平台没有 full-code 版本，说明该平台全源码尚未托管。

## repo：单仓代码图谱

```bash
infra-codebase repo find <keyword> --platform <android|ios|harmonyos> --limit 20
infra-codebase repo find <keyword> --platform <android|ios|harmonyos> --include-versions --limit 20
infra-codebase repo overview '<repoId>@<componentVersion>' [--alias-group <group>]
infra-codebase repo lookup '<repoId>@<componentVersion>' <SymbolName> [--kind Class|Method|Function] [--alias-group <group>]
infra-codebase repo context '<repoId>@<componentVersion>' <SymbolName> [--uid <uid>] [--content] [--alias-group <group>]
infra-codebase repo impact '<repoId>@<componentVersion>' <SymbolName> [--direction up|down] [--depth N] [--uid <uid>] [--alias-group <group>]
infra-codebase repo query '<repoId>@<componentVersion>' '<text>' [--limit N] [--content] [--alias-group <group>]
infra-codebase repo files '<repoId>@<componentVersion>' [--glob '<glob>'] [--limit 200] [--cursor <cursor>] [--alias-group <group>]
infra-codebase repo read '<repoId>@<componentVersion>' '<filePath>' [--start-line N] [--limit N] [--alias-group <group>]
infra-codebase schema repo
infra-codebase repo cypher '<repoId>@<componentVersion>' '<cypher with LIMIT>' [--alias-group <group>]
```

- 所有 `overview/lookup/context/impact/query/files/read/cypher` 下钻都必须使用 `<repoId>@<componentVersion>`；裸 `repoId` 和 `--snapshot-id` 不再是公开查询入口。`aliasGroup` 默认 `native`。
- `componentVersion` 必须是非空字符串且不能包含 `@`。以 `@` 开头的 scoped repoId 仍然合法，例如 `@meituan/abtest@0.0.23`。
- App 版本和组件版本不是同一个概念，不要用 `appVersion` 猜测 `componentVersion`。没有组件版本上下文时，先用 `repo find --include-versions` 或 deps 定位精确版本，再下钻。
- `repo find` 是发现入口：默认按 `repoId` 去重并展示最近发布的 alias；组件版本字符串不参与排序，也不表示语义上的最大 `componentVersion`。查询命令不能直接复用裸 repoId。
- 不要把 `snapshotId`、`commitSha` 或 App 版本拼进 repo selector。
- 指定的组件版本不存在或匹配不唯一时，不要静默改查最新版本；返回 `repo find --include-versions` 的候选快照和建议的 `<repoId>@<componentVersion>` 命令。
- 最终回答注明实际使用的 `repoId`、`componentVersion`、`commitSha` 和 `snapshotId`；后两者来自查询结果，只用于事实审计。
- 对 `init`、`start`、`Manager`、`Center`、`ABTest` 等高频符号名，先用 `lookup` 消歧，再带 `--uid` 查 `context` 或 `impact`；只有业务概念而无精确符号时先用小 `limit` 的 `query` 收敛候选。
- `context` 返回歧义候选时，选定 `uid` 重查。
- `context --content` 与 `repo read` 都可能返回源码：前者围绕符号并附带关系，后者围绕文件和行区间。按问题选择一个即可，除非现有结果被截断或仍缺证据。
- `repo files` 的 `page.nextCommand` 非空时，仅在问题需要完整路径覆盖时继续；`repo read` 小文件整文件返回，大文件按 32 KiB/2000 行预算分页，并通过 `nextCommand` 继续读取。
- 版本已经由 deps 或精确 alias 锁定时，后续命令和分页命令沿用同一个 `<repoId>@<componentVersion>` 与 `aliasGroup`。
- 如果没有 repo 结果，说明该组件尚未索引，建议使用 `infra-codebase-index` 录入。

例如，从外卖 App 的 deps 结果拿到 `componentVersion=8.77.51-wm` 后，精确查询对应快照：

```bash
infra-codebase repo cypher 'com.sankuai.waimai:order-mt@8.77.51-wm' 'MATCH (n) RETURN count(n) LIMIT 1'
```

## 组合查询

- 未知组件的符号问题：`capabilities` → 选最新 `fullCodeGroupKey`（历史版本先用 `catalog versions`）→ `full-code query` 定位组件/符号 → `repo find` 或 `deps members --q <component-keyword> --type indexed` → 用 `<repoId>@<componentVersion>` 执行 `repo context`。
- 跨 App 影响面：先用一次 `capabilities` 匹配 APP/平台候选，再分别使用对应 `appName`、`appVersion`、`fullCodeGroupKey` 查询。
- 跨版本差异：先用 `catalog versions` 精确定位目标 App 的两个 deps 版本，再执行一次 `deps diff`；继续单仓查询时，分别使用差异结果中的 `<repoId>@<beforeVersion>` 与 `<repoId>@<afterVersion>`，不得让多个 App 版本共用裸 `repoId`。新增或移除组件只查询存在版本的一侧。

## 错误处理

- CLI exit 0 且返回空数组、空 `matches/items` 或 `total=0` 时，才说明当前查询条件无数据。
- CLI exit 1 且 `status=400` 是输入问题，修正 selector 或参数范围；`status=404` 是精确组件、符号或文件不存在；`status=422` 是已知执行失败或资源预算拒绝；`status=500` 才是未预期服务错误。不要把这些错误解释成零命中。
- 图查询执行环境错误（如 `lbug-executor not available`）不等同于未索引；说明服务状态，并改用 `deps`、`repo find` 等仍可用路径兜底。
