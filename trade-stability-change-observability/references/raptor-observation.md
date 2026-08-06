# Raptor 观测契约（MRN MVP）

本文定义变更观测 Skill 如何消费 `infra-raptor` Skill/`raptorfe` CLI。鉴权、项目检索、接口适配和通用排障仍以 `infra-raptor` 为权威来源，不在此复制实现。

## 适用边界

MVP 只接受已明确为 MRN 且有非空 `bundleVersion` 的目标。`TAG4` 在本流程中只表示 MRN `bundleVersion`，不能泛化为所有 Web 项目的版本过滤。

可接受输入包括：

- 包含 `projectId` 和 `TAG4` 的 Raptor 异常页链接，并有上下文明确这是 MRN；
- `projectId + bundleVersion + MRN`；
- `bundle 名称 + bundleVersion + MRN`，通过 `infra-raptor` 查询项目 ID。

无法确认 MRN 或缺少 `bundleVersion` 时不创建 Observation，直接说明 MVP 支持边界。

## 查询命令

使用 `infra-raptor` 指引中的 Web 异常列表能力：

```bash
raptorfe -t 120000 web error get-summary-table \
  --project-id <projectId> \
  --start-long <windowStartMs> \
  --end-long <windowEndMsMinusOne> \
  --web-version all \
  --sort-field DATE \
  --page-size 200 --limit 200 --offset <offset> \
  --time-size MINUTE
```

目标 bundleVersion 查询只增加：

```bash
--query-param '{"TAG4":["<bundleVersion>"]}'
```

`TAG4` 必须是非空字符串数组。字符串或数字形式可能被接口静默忽略。`get-trend`、`get-groups` 不能作为目标 bundleVersion 异常列表证据。

## Window 映射

领域 Window 始终是 `[window_start, window_end)`。`MINUTE` 查询会纳入 `end-long` 所在分钟桶，因此物理参数必须为：

```text
start-long = window_start_ms
end-long   = window_end_ms - 1
```

正常 Window 的起止必须是整分钟。不要把逻辑 `window_end_ms` 原样传给 CLI，否则相邻 Window 会重复边界分钟。`start-round` 返回的 `active_round.window_start_ms`/`window_end_ms` 已按此公式换算和减 1，可直接传参，不需要再次换算或加减。

## 每轮双查询

对相同 Window 执行两次查询，除 `queryParam.TAG4` 外参数保持一致：

1. **全版本查询**：不传 `TAG4`，用于与 Baseline 和上一 Round 同口径比较；
2. **目标查询**：传 `TAG4=[bundleVersion]`，用于观察目标 MRN bundleVersion 范围内的异常。

Baseline 只执行全版本查询，不使用 `TAG4`。

## 分页与字段

- `--limit 200` 是单次返回上限，不代表只查第一页；从 `offset=0` 开始按实际返回条数递增 offset，直至覆盖 `data.total`；不要使用可能为 0 的 `data.table.total`；10 分钟 Window 常规下带量不会超过一页，最多翻 3 页仍未覆盖 `data.total` 时，停止翻页并在摘要中注明数据不完整；
- 聚类行位于 `data.table.rows[]`；
- 关键字段：`main`（异常名）、`LEVEL`、`COUNT`、`USER_COUNT`、`STATUS`、`CATEGORY`；
- `data.newErrors[]` 是跨分页分布的异常名字符串数组；遍历所有页后合并去重；
- 将 `newErrors` 名称与同次查询的 `rows[].main` 关联，才能取得等级和计数。

`newErrors` 指 Raptor 权威的最近一周首现异常；不要与 `cluster_diff.py` 的 `new_appeared`（比较基准是上一 Round，非近一周滚动窗口）混称"首现"。

## 查询结果主条目环比&过滤

全版本和目标查询的 `rows[]` 在生成摘要前都必须排除 `STATUS in [3, 4, 5]`（3=已解决，4=完全忽略，5=暂时忽略）。目标查询中被该状态过滤掉的行不进入 `target_version` 摘要，也不触发 `newErrors` 硬规则。

全版本 `rows[]` 在写入 `all_versions.rows[]`、参与逐条目环比（见《判定规则》）前，还必须排除 `CATEGORY=resourceError`（静态资源加载失败，非业务逻辑异常）。目标版本不做逐条目环比。

目标 bundleVersion 查询处于放量灰度期间，`COUNT`/`USER_COUNT` 会随灰度比例自然增长，目前暂不做归一化比较，因此不对目标查询结果做逐条目环比；目标版本的异常判定仍使用过滤后的官方 `newErrors` 硬规则与 Agent 综合判断。

## 轻量摘要

不要将 Raptor 原始分页响应或未过滤字段写入 Observation 状态；但全版本摘要需要保留**过滤后的逐条目行**，供下一轮环比使用。每次查询归一化为：

```json
{
  "clusters": 3,
  "count": 8,
  "user_count": 5,
  "levels": {"ERROR": 2, "WARN": 1, "INFO": 0},
  "official_new_errors": ["TypeError: example"],
  "official_new_error_count": 1,
  "filter_verification": "verified_by_difference",
  "rows": [
    {"main": "TypeError: example", "LEVEL": "ERROR", "COUNT": 2, "USER_COUNT": 2, "STATUS": 0}
  ]
}
```

`official_new_errors` 仅保留同时属于 `data.newErrors[]`、未被 `STATUS in [3, 4, 5]` 过滤且 `LEVEL=ERROR` 的重点异常名称，`official_new_error_count` 为其数量。该业务字段由 Skill 生成和解释，状态脚本不执行 Raptor 硬规则校验。

`all_versions.rows[]` 是本轮全版本过滤后的逐条目快照（`main`/`LEVEL`/`COUNT`/`USER_COUNT`/`STATUS`），只在全版本摘要中出现；`target_version` 摘要使用同样排除 `STATUS in [3, 4, 5]` 的聚合口径，但不需要逐条目 `rows[]`。每轮完整保存进 `rounds_summary`，不做历史裁剪，供下一轮通过 `cluster_diff.py` 计算环比时取用（见下节）。

## 过滤可信度

目标查询应是同窗口全版本查询的子集：

- 目标聚类集合不得超出全版本聚类集合；
- 同名聚类的目标 `COUNT` 不得大于全版本 `COUNT`；
- 目标 `COUNT` 合计不得大于全版本合计。

根据结果设置：

- `verified_by_difference`：满足子集关系且两份结果存在差异；
- `inconclusive`：两份结果完全相同。格式正确的 TAG4 结果仍可使用，也允许硬规则生效，但播报必须说明“过滤效果未能通过结果差异验证”，且不能宣称异常为目标版本独有；
- `invalid_subset`：违反子集关系。目标证据不可信，不触发目标版本专属硬规则。

## 全版本逐条目环比（cluster_diff.py）

全版本逐条目环比由独立、无状态的 `scripts/cluster_diff.py` 计算，不读写 `current_observation.json`，只接受两组行数据并返回命中列表；业务判定（命中后如何映射到 severity）仍由 Skill/Agent 完成，脚本本身不产出 severity。

```bash
python3 ${SKILL_ROOT}/scripts/cluster_diff.py \
  --current-rows-json '<本轮全版本过滤后 rows JSON 数组>' \
  --previous-rows-json '<上一轮全版本 rows JSON 数组，无上一轮时传 []>'
```

调用方（Agent）自行从 `$STATE read` 的完整状态中取 `rounds_summary[-1].all_versions.rows` 作为 `--previous-rows-json`；首个 Round（`rounds_summary` 为空）传 `[]`。脚本内部按上一节的 STATUS/CATEGORY 规则再次防御性过滤，调用方仍应先过滤好再传入。

### `hit_rule` 的语义

`hit_rule` 是 `cluster_diff.py` 对**全版本、较上一正常 Round**的逐条目比较结果，不是 Raptor 官方 `data.newErrors[]`，也不表示近一周首现。脚本只返回事实；以下规则决定这些事实如何影响 Round severity：

| `hit_rule` | 命中条件 | 播报语义 | 对 severity 的作用 |
| --- | --- | --- | --- |
| `user_count_surge` | `ERROR` / `WARN` 同名异常在上轮存在，本轮 `USER_COUNT` 涨幅 ≥50% 且增加 ≥3 人 | 较上一轮受影响人数明显上涨 | 本轮至少 `notice` |
| `count_surge` | `INFO` 或其他非 `ERROR` / `WARN` 的同名异常在上轮存在，本轮 `COUNT` 涨幅 ≥200% 且增加 ≥5 次 | 较上一轮发生次数明显上涨 | 本轮至少 `notice` |
| `new_appeared` | 本轮出现 `ERROR`，上轮不存在同名异常 | 较上一轮环比新增 | 仅提示，不单独改变 severity |

`new_appeared` 无量级阈值，但仅用于提示“较上一轮新增”；**不要**称为“首现”。“近一周首现”只指 Raptor 官方 `data.newErrors[]`（过去 7 天滚动窗口内首次出现），见下方规则一。

返回 `{"ok": true, "hits": [...]}`；每个命中项包含 `cluster`/`level`/`count`/`user_count`/`prev_count`/`prev_user_count`/`hit_rule` 及对应的涨幅字段。`hits` 为空数组表示本轮全版本逐条目环比未命中。

## fast-check：60s 小循环快速核检

正常 Round 的双查询和判定链路耗时较长（预算 3 分钟），不适合每 60s 跑一次。`scripts/fast_check.py` 是独立的固定脚本，供 sleep-loop 每次小循环唤醒时做低延迟核检，只检查一件事：目标 MRN bundleVersion 范围内是否存在**新的**官方近一周首现异常，不限 `LEVEL`，1 例即告警。

```bash
python3 ${SKILL_ROOT}/scripts/fast_check.py --paas <paas> --group-id <dxGroupId>
```

行为边界：

- 脚本内部自行调用 `raptorfe`（固定 `-t 30000`，30 秒超时），查询最近 5 分钟、目标 `TAG4` 的 `get-summary-table` 单页（`offset=0`，不翻页）；`newErrors` 判定不依赖 Window 长度，短窗口足够覆盖持续存在的首现异常，下次小循环还会再次核检；
- 只读 `current_observation.json` 取 `target` 和 `fast_alert_seen`，不读写其他状态字段；`lifecycle_state` 非 `OBSERVING` 时直接报错退出；
- 结果排除 `STATUS in [3, 4, 5]` 和 `CATEGORY=resourceError`，不按 `LEVEL` 过滤；
- 与 `fast_alert_seen` 做差集，只返回尚未告警过的异常名；命中过的异常不会在同一观测周期内重复触发小循环告警；
- 只返回待告警列表（`cluster`/`level`/`count`/`user_count`），不产出 severity，不判断是否升级为 warning——命中即由 Agent 播报并 @ Initiator，判断逻辑在 `SKILL.md` 维护。

成功时返回：

```json
{
  "ok": true,
  "observation_id": "obs_20260723_ab12cd34",
  "window_start": "2026-07-23T10:21:00+08:00",
  "window_end": "2026-07-23T10:26:00+08:00",
  "checked_new_error_names": ["TypeError: example"],
  "alerts": [
    {"cluster": "TypeError: example", "level": "ERROR", "count": 12, "user_count": 8}
  ]
}
```

`checked_new_error_names` 是本次窗口内命中官方 `newErrors` 的全部异常名（含已在 `fast_alert_seen` 中、本次不再告警的）；`alerts` 是与 `fast_alert_seen` 做差集后真正待播报的子集，按 `level`（ERROR > WARN > INFO）再按 `user_count` 降序排列。`alerts` 为空数组表示本次无需播报。

调用后若 `alerts` 非空，播报前先调用状态命令登记，避免下次小循环重复播报：

```bash
python3 ${SKILL_ROOT}/scripts/observation_state.py --paas <paas> --group-id <dxGroupId> \
  record-fast-alert --observation-id <observation_id> --loop-id <loop_id> \
  --cluster-names-json '<本次 alerts[].cluster 组成的 JSON 数组>'
```

30 秒超时到期或 `raptorfe`/脚本失败时，`fast_check.py` 以非零退出码返回 `{"ok": false, ...}`；调用方按《判定规则》以外的路径处理——不重试、不告警、不记入 heartbeat 异常，直接进入下一步是否到 `next_round_at` 的判断，等正常 Round 覆盖同一异常。

## 判定规则

按以下顺序判定，三类信号不可混称：

1. **官方近一周首现（强制 `warning`）**：过滤可信度不是 `invalid_subset`，且目标查询中存在同时属于 `data.newErrors[]`、未被 `STATUS in [3, 4, 5]` 过滤、`LEVEL=ERROR` 的异常时，本轮必须为 `warning`。`newErrors` 语义为过去 7 天滚动窗口内首次出现，准确播报为“目标 MRN bundleVersion 过滤范围内的官方近一周首现 ERROR”；禁止说成“版本首现”“首次出现于该版本”或“较上周同期首现”。
2. **较上一轮环比上涨（severity 下限 `notice`）**：`cluster_diff.py` 返回 `user_count_surge` 或 `count_surge` 时，本轮不可判为 `ok`。Agent 可结合命中数量、涨幅和级别分布升级为 `warning`，但不是自动升级。
3. **较上一轮新增（仅提示）**：`cluster_diff.py` 返回 `new_appeared` 时，列为“较上一轮新增”的事实，不单独改变 severity。

规则一命中时直接 `warning`。只命中规则二时，severity 在 `notice` 与 `warning` 之间由 Agent 判断。只命中规则三时，仍由 Agent 结合其他事实综合判断。

**fast-check 告警（触发规则，不是 severity 规则）**：

> `fast_check.py` 返回非空 `alerts` 时，Agent 必须先调用 `record-fast-alert` 登记，再立即独立播报并 @ Initiator，不等待、不合并进下一次正常 Round。

fast-check 告警只解决"小循环期间要不要立即喊人"，不产出、不影响、也不由规则一/规则二的 severity 判断；命中过的异常到了正常 Round 仍会按规则一重新判定一次（`fast_alert_seen` 只影响小循环是否重复播报，不影响 Round 内的 severity 计算）。

其他波动由 Agent 结合以下事实综合判断 `ok / notice / warning`：

- 全版本相对 Baseline；
- 全版本相对上一正常 Round（含上方 `cluster_diff.py` 的逐条目环比结果）；
- 目标 bundleVersion 的异常分布；
- 数据是否完整。

## URL 参数白名单

可消费：`projectId`、`start`、`end`、MRN `TAG4`、非空 `SEC_CATEGORY`。MVP 的 Baseline 和每轮双查询都固定 `webVersion=all`，URL 中的 `webVersion` 不进入 Observation 查询口径。

`metric`、`speedPoint`、`singleSpeedPoint`、`isPerfInMp`、`perfBundleId`、`webVersion`、空 `dyeingId`、`type=datetimerange` 属于性能配置、页面状态或非 MVP 过滤，不进入异常列表查询。`errorListCurrentPage` 仅可换算为 offset，不直接透传。
