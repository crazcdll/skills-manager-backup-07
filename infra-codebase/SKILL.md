---
name: infra-codebase
description: "使用 infra-codebase CLI 查询已索引的美团客户端代码知识库（Android、iOS、HarmonyOS）。用于回答组件依赖、跨组件源码关系、单仓符号上下文、调用链、实现逻辑和影响面问题。"

metadata:
  skillhub.creator: "yangshunyu"
  skillhub.updater: "yangshunyu"
  skillhub.version: "V16"
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

先用精简能力入口一次确定 APP 身份和各平台最新查询定位字段，后续命令只使用入口或下钻结果返回的精确值。

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

## 路由

| 用户目标 | 首选能力 | 查询路径 |
|---|---|---|
| App 版本组件、上下游依赖、跨版本差异 | `deps` | `capabilities`（历史版本再用 `catalog versions`）→ `deps members` → `deps show` |
| App 全量源码、跨组件符号、组件未知 | `full-code` | `capabilities`（历史版本再用 `catalog versions`）→ `schema full-code` → `full-code query` |
| 单组件内实现、调用方、执行流、影响面 | `repo` | `repo find` → `repo lookup` → `repo context` / `repo impact` |
| 同时涉及版本和源码细节 | 组合 | 先用 `deps` 或 `full-code` 定位范围，再用 `repo` 深挖 |

- 问组件上下游依赖时用 `deps show`，不要用 `repo impact` 代替组件级依赖。
- 问已知组件内的实现、入口、调用关系时直接用 `repo`。
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
infra-codebase repo overview '<repo>'
infra-codebase repo lookup '<repo>' <SymbolName> [--kind Class|Method|Function]
infra-codebase repo context '<repo>' <SymbolName> [--uid <uid>] [--content]
infra-codebase repo impact '<repo>' <SymbolName> [--direction up|down] [--depth N] [--uid <uid>]
infra-codebase repo query '<repo>' '<text>' [--limit N] [--content]
infra-codebase schema repo
infra-codebase repo cypher '<repo>' '<cypher with LIMIT>'
```

- `<repo>` 是统一快照选择器：使用 `<repoId>` 时，先检查美团各平台最大 APP 版本依赖清单中的组件版本是否已有可查询的精确 alias/snapshot；存在才使用该精确组件快照，不存在（包括组件不在清单中，或清单版本尚未索引）则回退到 `gitnexus_component_aliases.id DESC` 的最新登记快照。组件版本字符串不参与排序。使用 `<repoId>@<componentVersion>` 精确查询指定组件版本。
- 用户或 `deps members` / `deps show` 已给出 `componentVersion` 时，必须使用 `<repoId>@<componentVersion>`，不得退回裸 `repoId`。App 版本和组件版本不是同一个概念，不要用 `appVersion` 猜测 `componentVersion`。
- 没有任何组件版本上下文时，使用裸 `<repoId>` 查询上述默认快照。默认 `repo find` 按 `repoId` 去重并返回 alias 最大 `id` 对应的版本，不表示语义上的最大 `componentVersion`。
- 需要指定版本、比较版本或确认可用版本时，使用 `repo find --include-versions`，再从结果中选择精确的 `repoId` 和 `componentVersion`。不要把 `snapshotId`、`commitSha` 或 App 版本拼进 `<repo>`。
- 指定的组件版本不存在或匹配不唯一时，不要静默改查最新版本；返回 `repo find --include-versions` 的候选快照和建议的 `<repoId>@<componentVersion>` 命令。
- 最终回答注明实际使用的 `repoId`、`componentVersion`、`commitSha` 和 `snapshotId`；裸 `repoId` 查询也要根据 `repo find` 结果说明实际命中的最新快照。
- 对 `init`、`start`、`Manager`、`Center`、`ABTest` 等高频名称，先 `lookup` 消歧，再带 `--uid` 查 `context` 或 `impact`。
- `context` 返回歧义候选时，选定 `uid` 重查。
- 需要源码证据时优先 `context --content`；如果内容被截断或需要完整文件，再读 `schema repo` 后用只读 Cypher 查询 `File.content`。
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

- CLI 返回 `[]` 时，只说明当前查询条件无数据。
- 图查询执行环境错误（如 `lbug-executor not available`）不等同于未索引；说明服务状态，并改用 `deps`、`repo find`、`repo context` 等可用路径兜底。
