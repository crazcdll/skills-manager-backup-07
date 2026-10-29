# Observation 状态契约

本文是 `scripts/observation_state.py` 的运行契约。状态只保存流程控制与轻量摘要，不保存 Raptor 原始分页响应。

## 存储位置

每个大象群只有一个当前状态文件：

```text
/efs/data/tenants/{paas}/shared/observation_{group_id}/current_observation.json
```

同目录的 `.mutex` 是一次短写事务的互斥目录，不代表循环所有权。脚本采用持锁重读、临时文件和 `os.replace` 原子替换；超过 30 秒的互斥可按陈旧状态清理。

本地验证可通过全局参数 `--state-dir` 覆盖目录。

## 顶层结构

```json
{
  "observation_id": "obs_20260723_ab12cd34",
  "lifecycle_state": "OBSERVING",
  "initiator_mis": "zhangsan",
  "group_id": "70407074830",
  "created_at": "2026-07-23T10:00:00+08:00",
  "updated_at": "2026-07-23T10:27:00+08:00",
  "target": {
    "project_id": 34765,
    "project_name": "some_mrn_bundle",
    "project_type": "MRN",
    "bundle_name": "some_mrn_bundle",
    "bundle_version": "0.78.0",
    "log_type": "JS_ERROR"
  },
  "baseline": {
    "window_start": "2026-07-23T09:40:00+08:00",
    "window_end": "2026-07-23T09:50:00+08:00",
    "collected_at": "2026-07-23T10:00:00+08:00",
    "all_versions": {
      "clusters": 10,
      "count": 32,
      "rows": [
        {"main": "TypeError: example", "LEVEL": "ERROR", "COUNT": 2, "USER_COUNT": 2, "STATUS": 0}
      ]
    }
  },
  "rollout_started_at": "2026-07-23T10:03:27+08:00",
  "observation_started_at": "2026-07-23T10:04:00+08:00",
  "runtime": {
    "loop_id": "loop_ab12cd34",
    "heartbeat_at": "2026-07-23T10:27:00+08:00",
    "interval_minutes": 10,
    "data_lag_minutes": 2,
    "max_duration_minutes": 120,
    "ends_at": "2026-07-23T13:03:27+08:00",
    "next_window_start": "2026-07-23T10:14:00+08:00",
    "next_round_at": "2026-07-23T10:26:00+08:00"
  },
  "control": {
    "stop_requested_at": null,
    "stop_requested_by": null
  },
  "active_round": null,
  "rounds_summary": [],
  "fast_alert_seen": ["TypeError: example"]
}
```

## 核心约束

- 同群只允许一个非终态 Observation；当前终态为 `COMPLETED`。`init` 也允许覆盖旧版遗留的 `FAILED`，但不再创建该状态。
- 目标必须明确为 `MRN` 且包含非空 `bundle_version`，或明确为 `H5_DUO` 且包含有效的 `web_version`。H5_DUO 不使用 `bundle_version`。
- Baseline 成功后由 `PREPARING` 进入 `READY`。
- `start-observing` 保存真实 `rollout_started_at`，并将 `observation_started_at` 向上对齐至整分钟；若已经整分则不变。循环 `heartbeat_at` 与 `ends_at` 从命令实际执行时间计算，避免历史放量时间导致循环出生即陈旧或立即到期。`runtime.next_window_start` 取对齐后的放量时间与当前可查询整分钟（`floor(now-lag)`）中较晚者；`--at` 回补超过一个 `interval` 时不会逐轮追补历史 Window。
- `runtime.loop_id` 表示循环所有权。循环内写操作同时校验 `observation_id` 和 `loop_id`。
- `request-stop` 幂等保留第一次请求。`PREPARING`/`READY` 取消会直接完成；最大时长到期使用 `stop_requested_by="system:max_duration"`。`OBSERVING` 阶段若 `active_round` 心跳已超过 `HEARTBEAT_STALE_MINUTES`（15 分钟，判定为旧循环中断遗留），`request-stop` 会一并清空该 `active_round` 并直接完成，不等待其正常收尾，也不对中断期间到停止时刻这段窗口做补偿查询。该 Gap 不持久化；调用方仅在同一次停止响应仍持有调用前旧状态时尽力披露。心跳未陈旧的 `active_round` 不受影响，仍需 `finish-round` 后才能 `complete`。
- `start-round` 不接受调用方传入的 window；它在同一互斥事务内确认尚无 Stop Request 且 `active_round` 为空后，自行用 `runtime.next_window_start` 与 `interval_minutes` 推导 window 并写入 `active_round`；Stop Request 不取消已开始的 Round。`active_round` 除 `window_start`/`window_end`（ISO 格式）外，同时包含 `window_start_ms`/`window_end_ms`（对应的毫秒时间戳，用法见 `references/raptor-observation.md`《Window 映射》）。
- `finish-round` 可在已有 Stop Request 时完成当前 Round，并只追加轻量摘要。
- `resume` 只接受心跳已陈旧的 `OBSERVING` 状态。它清除中断遗留的 `active_round`、生成新 `loop_id`，并将 `runtime.next_window_start` 推进到当前可查询整分钟。调用方提示用户此前存在未观测 Gap，但不补查；之后只执行标准长度的正常 Round。
- `complete` 只能在 `active_round` 为空且已有 Stop Request 时执行；`request-stop` 已直接转入 `COMPLETED` 时无需再次调用。
- `fast_alert_seen` 是 fast-check（见 `references/raptor-observation.md`《fast-check：60s 小循环快速核检》）已播报过的异常名集合，用于跨小循环、跨响应去重；只通过 `record-fast-alert` 追加，`init` 时为空数组，整个观测周期内只增不减，直到 `complete`。

## 命令

所有命令都输出 JSON。失败时输出 `{"ok": false, "error": ...}` 并返回非零退出码。`finish-round` 因摘要关键字段缺失而被拒绝时，额外返回 `important_prompt`，提示调用方检查上下文压缩/任务交接后的 Skill 记忆并按 `SKILL.md`《上下文压缩恢复》处理。

```text
read [--compact]  # 状态不存在时成功返回 state=null；compact 省略 `baseline`/`rounds_summary` 等历史摘要，保留 `target`/`initiator_mis`
init --initiator-mis MIS --target-json JSON [--interval-minutes N] [--data-lag-minutes N] [--max-duration-minutes N]
set-baseline --observation-id ID --baseline-json JSON
start-observing --observation-id ID [--at ISO_TIME]
heartbeat --observation-id ID --loop-id ID
start-round --observation-id ID --loop-id ID  # window 由脚本用 next_window_start + interval_minutes 推导，不接受调用方传入
finish-round --observation-id ID --loop-id ID --summary-json JSON
record-fast-alert --observation-id ID --loop-id ID --cluster-names-json JSON  # JSON 为非空字符串数组，合并进 fast_alert_seen 并去重，返回 compact 状态
request-stop --observation-id ID --requested-by MIS_OR_SYSTEM [--at ISO_TIME]
resume --observation-id ID [--at ISO_TIME]
complete --observation-id ID
```

全局路径参数：

```text
--state-dir PATH
```

或：

```text
--paas PAAS --group-id GROUP_ID
```

`init --target-json` 中，MRN 目标使用 `project_type="MRN"` 与 `bundle_version`；H5_DUO 目标使用 `project_type="H5_DUO"` 与 `web_version`。两类目标都要求 `project_id` 或 `project_name`，其余状态与摘要契约相同。

`init` 可选参数默认值：`--interval-minutes 10`、`--data-lag-minutes 2`、`--max-duration-minutes 120`（2 小时）；均要求正数（`data-lag-minutes` 允许为 0）。调用方从用户自然语言中识别观测时长后，换算为分钟传入 `--max-duration-minutes`；用户未指定时省略该参数并使用默认值。`start-observing --at` 表示真实放量时间，仅用于记录和 `observation_started_at` 对齐；循环心跳和最大时长从命令执行时刻开始，首轮 Round 游标（`next_window_start`）取对齐放量时间与当前可查询整分钟中较晚者，避免回补历史时逐轮追补。`request-stop --at`、`resume --at` 缺省时使用调用时的当前时间。

## Round 摘要边界

`finish-round --summary-json` 至少包含：

- `severity`: `ok | notice | warning`
- `evidence`: 数组
- `reason`: 非空字符串
- `confidence`: 0 到 1
- `all_versions`: 聚合摘要，且必须包含过滤后的逐条目 `rows[]`（`main`/`LEVEL`/`COUNT`/`USER_COUNT`/`STATUS`），供下一轮 `cluster_diff.py` 环比使用；`baseline.all_versions` 同样需要该字段
- `target_version`: 聚合摘要，不需要逐条目 `rows[]`
- `source_available`（可选，默认 `true`）：本轮数据源是否可用；Agent 可读取上一轮摘要判断是否连续失败。

`all_versions` 与 `target_version` 都必须包含聚合字段 `clusters`、`count`、`user_count`、`levels`、`official_new_errors`、`official_new_error_count`、`filter_verification`；`all_versions` 还必须包含 `rows`。缺少任一字段时，`finish-round` 拒绝写入并返回 `important_prompt`；这是关键字段存在性校验，不校验字段值类型、聚合计算或业务判定。

脚本补入当前 `active_round` 的 `round`、Window 和 `ran_at`。调用方仍不得放入 Raptor 原始分页响应或未过滤字段；`all_versions.rows[]` 是过滤后的轻量逐条目快照，不是原始响应。`rounds_summary` 每轮完整保存该快照，不做历史裁剪或截断。Raptor 业务硬规则（含全版本逐条目环比命中后的 severity 下限）由 Skill 判定，状态脚本只校验基础摘要结构，不调用 `cluster_diff.py`，也不解释 `rows[]` 内容。
