# 版本依赖图谱

某 App 版本内所有组件的列表及上下游依赖关系，数据来自外挂导入（非实时构建）。

---

## 1. 列出所有版本

先用能力清单拿到可用 `platform / appVersion / appName / groupKey`，后续命令都引用这些字段。

- 首选 `infra-codebase capabilities list`，需要版本明细时用 `capabilities versions` 按 App/平台下钻。
- 直接使用 `deps versions` 只作为旧 CLI fallback 或用户明确要求 raw list 时使用。
- 如果用户给了具体任务但没说 App，从能力清单结果中选 `appName=meituan` 的最高 `appVersion`。

```bash
infra-codebase capabilities versions --app-name <app-name> [--platform <android|ios|harmonyos>] --capability deps
# 返回：platform, appVersion, appName, groupKey
```

---

## 2. 列出版本内组件

`platform`、`resolved-version`、`resolved-app-name` 必须来自能力清单、`capabilities versions` 结果或用户明确指定值。CLI 对旧用法会尝试推断并在 stderr 提示迁移，但 Skill 不应依赖该兼容路径。

```bash
infra-codebase deps members <platform> <resolved-version> --app-name <resolved-app-name> --q <keyword>
infra-codebase deps members <platform> <resolved-version> --app-name <resolved-app-name>                 # 全量（不传 --type）
infra-codebase deps members <platform> <resolved-version> --app-name <resolved-app-name> --type pending  # 前 20 个三方/无源码候选
infra-codebase deps members <platform> <resolved-version> --app-name <resolved-app-name> --type indexed  # 前 20 个已索引候选
# 示例（已从用户输入或发现结果解析出 appName=meituan）
infra-codebase deps members android 12.57.203 --app-name meituan --type pending
```

输出含 `summary`（total / indexed / external / pendingIndex）、`memberResult` 和 `members[]`：

- 不传 `--q` 且不传 `--type`（或 `--type all`）：不分页，返回全量成员；每条仅含 `repoId`、`componentVersion`、`indexed`、`indexStatus`。
- 存在 `--q` 或非 `all` 的 `--type`：按稳定顺序返回前 20 条详细成员；详细记录额外包含 `commitSha`、`registryName`、`snapshotId`、`skipReason`。
- `memberResult.total` 是筛选后的总命中数，`returned` 是本次返回数，`truncated=true` 表示需要继续收窄筛选条件；不存在下一页。

| 字段 | 说明 |
|---|---|
| `repoId` | 组件标识（maven 坐标 / pod 名）|
| `componentVersion` | 该版本内此组件的版本号 |
| `indexStatus` | `exact` / `external` / `pending` |
| `skipReason` | 有值时表示显式不可索引原因，如 `hpx_no_record` / `system_lib` |

`indexStatus` 含义：
- `exact` — 已索引，可做单仓符号分析（`infra-codebase repo` 命令组）
- `external` — 已显式标记为第三方、系统库或其他不可索引组件，弱关注
- `pending` — 依赖清单中存在，但当前没有可查源码；对用户统一归类为“三方/无源码”

若 `summary.pendingIndex > 0`，告知用户这些组件属于“三方/无源码”，不能做 `repo` 单仓源码查询；只回答版本依赖关系。

查具体组件时不要先拉全量组件列表；用 `--q <keyword>` 定位候选。若 `memberResult.truncated=true` 且前 20 条不足以判断，继续收窄关键词或叠加 `--type`，不要尝试翻页。

---

## 3. 查组件上下游依赖

`platform`、`resolved-version`、`app-name-or-meituan` 必须来自能力清单、`deps versions` 结果或用户明确指定值。用户给了具体任务但没说 App 时，先从清单中选择 `meituan`，再传入对应版本。

```bash
infra-codebase deps show <platform> <resolved-version> <repoId> --app-name <app-name-or-meituan>
# 示例：infra-codebase deps show android 12.57.203 com.meituan.android.common:horn --app-name meituan
```

输出两节：
- `← 上游（谁依赖它）` — `dependents`，含 `repoId` + `version`
- `→ 下游（它依赖谁）` — `dependencies`，含 `repoId` + `version`

**禁止用 `infra-codebase repo impact` 替代 `deps show`。** impact 是单仓符号级分析，deps show 是组件级依赖关系，语义完全不同。

---

## 4. 组件版本跨版本对比

比较两个 App 版本的组件清单与组件版本时使用 `deps diff`。比较逻辑由服务端完成，CLI 只发起一次请求。

```bash
# 指定组件：返回 same、status、beforeVersion、afterVersion
infra-codebase deps diff android 12.57.203 12.57.402 com.meituan.android.common:horn --app-name meituan

# 全量：只返回 changed / added / removed 组件，summary 中保留 unchanged 数量
infra-codebase deps diff android 12.57.203 12.57.402 --app-name meituan
```

- `changed`：两个 App 版本都包含该 `repoId`，但组件版本号不同。
- `added`：只在对比后的 App 版本中存在。
- `removed`：只在对比前的 App 版本中存在。
- `unchanged`：两个 App 版本中的组件版本号完全相同；仅在指定组件结果或 summary 中出现。
- `missing`：指定的 `repoId` 在两个 App 版本中都不存在，此时 `same=null`。

组件版本号只做字符串精确比较，不推断版本语义顺序。

---

## 5. 上下游关系跨版本对比

对同一 `repoId` 用两个不同版本各调用一次 `deps show`，对比 dependencies / dependents 列表差异。

```bash
infra-codebase deps show android 12.57.203 com.meituan.android.common:horn --app-name meituan
infra-codebase deps show android 12.57.402 com.meituan.android.common:horn --app-name meituan
```

---

## 6. 组合查询（单仓 + 依赖图谱）

1. 通过 `deps show` 找到上下游组件 repoId
2. 用 `infra-codebase repo find <repoId关键词>` 查确认组件已索引
3. 切换到单仓能力；写 Cypher 前用 `infra-codebase schema repo` 查看 CLI 内置 schema
