# Scope 单仓发现

只在用户明确指定 Scope 时使用本参考。它只负责把 Scope 当前状态或命名快照中的成员解析为精确单仓入口；每个成员后续都是独立的 `repo` 查询，不把 Scope 当作跨仓图，也不参与 APP 选择。

## 发现 Scope 与状态

```bash
infra-codebase scope list --q <scope-keyword>
infra-codebase scope versions --scope-name <name> [--q <version-or-description>]
infra-codebase scope members --scope-name <name> [--version <version>] [--q <member-keyword>]
```

1. 用 `name`、`displayName`、`aliases` 和描述匹配用户明确给出的 Scope，后续固定使用唯一 `name`。
2. 用户没有指定版本、时间或历史语义时，省略 `--version`，直接读取 Scope 当前状态；不要先列举版本再猜测一个 Snapshot。
3. 用户指定命名版本、时间或描述时，先用 `scope versions` 定位唯一 version，再传给 `scope members --version`。无结果或存在歧义时停止，不得静默改用当前状态。
4. 用户已经给出成员名或仓库线索时，用 `--q` 收窄成员；需要在整个 Scope 中发现成员时，按 `memberPage.nextCommand` 继续必要分页。
5. 只下钻 `ready=true`、存在 `snapshotId` 且 `componentVersion` 合法的成员；其他成员单独报告状态，不使用最新 alias 或同名仓库补位。

## 选择独立单仓

把成员返回的 `member`、`description`、`aliasGroup`、`repoId`、`componentVersion`、`commitSha`、`snapshotId` 和 `repoCommand` 作为本轮精确上下文。

- 已明确成员时，优先直接执行其 `repoCommand`。
- Scope 成员可以是后端、Web 或移动端，`platform=generic` 不阻止 exact repo 下钻；Android、iOS、HarmonyOS 的平台限制只约束 APP 发现入口。
- 只有业务意图、接口、错误码或符号锚点时，先用成员 name、aliases、description、repoId 和平台筛选候选。
- 符号形态锚点用 `repo lookup` 廉价测试；业务意图用小 `limit` 的 `repo query` 测试。无法仅靠元数据收敛时，最多并发测试 4 个候选成员，命中足够证据后停止。
- 一个问题涉及多个成员时，对每个成员分别完成精确 alias 下钻；成员间只通过明确的路由、RPC/HTTP、bridge、schema、事件或配置协议连接证据，不因相似关键词推断调用链。
- Scope 成员均不命中时，说明 Scope 内检索边界和不可用成员；不得自动切换默认 APP、native 搜索或 Scope 外仓库。只有用户明确要求越过 Scope 后，才重新按主 Skill 的普通入口处理。

## 精确 Repo 下钻

自行构造命令时始终使用成员返回的精确组件 alias：

```bash
infra-codebase repo overview '<repoId>@<componentVersion>' --alias-group '<aliasGroup>'
infra-codebase repo lookup '<repoId>@<componentVersion>' '<symbol>' --alias-group '<aliasGroup>'
infra-codebase repo context '<repoId>@<componentVersion>' '<symbol>' --uid '<uid>' --content --alias-group '<aliasGroup>'
infra-codebase repo impact '<repoId>@<componentVersion>' '<symbol>' --uid '<uid>' --direction up --depth 3 --alias-group '<aliasGroup>'
infra-codebase repo query '<repoId>@<componentVersion>' '<intent>' --limit 5 --alias-group '<aliasGroup>'
infra-codebase repo files '<repoId>@<componentVersion>' --alias-group '<aliasGroup>' [--glob '<glob>']
infra-codebase repo read '<repoId>@<componentVersion>' '<filePath>' --alias-group '<aliasGroup>' [--start-line N] [--limit N]
infra-codebase repo cypher '<repoId>@<componentVersion>' '<readonly cypher with LIMIT>' --alias-group '<aliasGroup>'
```

- 不允许裸 `repoId` 或 `--snapshot-id` 下钻；Scope 成员必须显式传自己的 `aliasGroup`。
- 不使用 `repo find` 重新发现版本，也不把 APP 版本、commitSha 或 snapshotId 拼进 selector。
- 记录 repo 响应中的 `repoMeta.snapshotId` 和 `repoMeta.commitSha`。若与成员审计信息不一致，重新读取一次相同 Scope 状态；仍不一致时按并发变化或服务异常停止，不得回退其他版本。
- 对高频符号名先 `lookup` 消歧，再带 `uid` 查询 `context` 或 `impact`。已知路径直接 `read`；仅有业务意图时才用小范围 `query`。
- 语义查询空结果不能证明任意文本在单仓不存在；不得枚举全仓文件逐个读取，也不得用 repo Cypher 扫描 `File.content` 绕过边界。

## 输出与失败

- 注明实际 Scope `name`，以及使用“当前状态”还是命名 Snapshot version。
- 注明实际成员、`aliasGroup`、`repoId`、`componentVersion`、`commitSha` 和 `snapshotId`。
- 区分已核验证据、未验证候选、不可用成员和 Scope 外缺口。
- `scope list` 无结果时只说明未登记匹配 Scope；命名版本无结果时列出相近候选。两种情况都不得回退默认 APP。
- 精确 alias 查询失败时停止该成员下钻；CLI 空结果只表示当前条件无数据，图查询环境错误不等于未索引。
