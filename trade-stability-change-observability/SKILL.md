---
name: trade-stability-change-observability
description: 交易前端变更上线观测助手。用户希望准备或开始上线观测、查看或恢复当前观测，或明确要求停止观测时使用；已有观测任务时，“变更/灰度/发布完成”等完成态表达也表示结束观测。支持发版巡检、帮忙盯上线，以及提供 MRN/H5_DUO Raptor 链接后持续观察。面向已明确为 MRN bundleVersion 或 H5_DUO webVersion 的目标，编排 Baseline、Raptor 全版本与目标版本双查询、1024 Agent sleep-loop 周期播报、跨响应停止和中断恢复；不是一次性异常查询或 HTML 报告工具。

metadata:
  skillhub.creator: "duyifan10"
  skillhub.updater: "lidingcheng"
  skillhub.version: "V29"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "3394"
  skillhub.high_sensitive: "false"
---

# 交易前端变更上线观测

为一次上线变更维护完整 Observation 生命周期，在 1024 Agent 中通过短 `sleep` 循环持续执行 Raptor 巡检并向群内独立播报。当前支持 MRN 与 H5_DUO。

## 边界

- 仅支持已确认项目类型且具有对应版本标识的目标：MRN 使用非空 `bundleVersion`；H5_DUO 使用非空、非 `all` 的 `webVersion`。
- 无法确认项目类型，或缺少对应版本标识时，不创建 Observation；直接说明当前支持边界。不要猜测，也不设计额外的自动识别流程。
- 每群只允许一个非终态 Observation。已有任务时拒绝新建，并展示当前 Observation ID 与 Lifecycle State。
- 本 Skill 负责 Observation 生命周期、Raptor 双查询编排、判定和消息语义。
- 面向用户的准备说明、Round 播报、告警与总结中，MRN 版本标识统一称为 `bundleVersion`；`TAG4` 仅作为 Raptor 查询参数名或 URL 键使用，不出现在对外业务表述中。
- 调用 `infra-raptor` Skill/`raptorfe` 获取事实；不要复制其鉴权、项目检索或通用接口适配实现。

## 运行依赖

- **必读** `references/runtime-sleep-loop.md`：1024 Agent 平台运行时约束（sleep 超时上限、状态路径为何固定用 `shared/`、`send_dx_message_tool` 与 AI 会话回复的区别、并发响应行为）。
- 读取 `references/state-schema.md`，按其命令使用 `scripts/observation_state.py` 管理状态。
- 在准备 Baseline 或执行 Round 前读取 `references/raptor-observation.md`。
- 每轮全版本逐条目环比使用 `scripts/cluster_diff.py`；它是无状态纯计算工具，不读写 `current_observation.json`，只做涨幅比较，不做业务判定。
- 每次 60s 小循环未到 `next_round_at` 的唤醒使用 `scripts/fast_check.py` 做快速核检；它只读状态、内部自行调用 `raptorfe`（30 秒超时），不产出 severity。
- 状态路径为 `/efs/data/tenants/{paas}/shared/observation_{dxGroupId}/current_observation.json`。
- 以上三个脚本按本文和 `references/*.md` 给出的命令、参数与返回结构调用即可，正常执行不需要阅读脚本源码；仅当返回结果与预期不符、需要排查数据异常或脚本报错原因时，才打开对应 `.py` 文件深入查看。

设置：

```bash
SKILL_ROOT=<本 Skill 根目录>
STATE="python3 ${SKILL_ROOT}/scripts/observation_state.py --paas <paas> --group-id <dxGroupId>"
```

命令只是示例入口；用户自然语言表达同一意图时同样处理，不要求固定口令。

## 上下文压缩恢复

若当前原始输入含“任务交接摘要”等上下文压缩或模型切换提示，说明此前完整对话可能已被摘要替代；**不得只凭摘要中“跑 Round、查 Raptor、写状态”等任务级描述继续执行。** 先重新阅读 `SKILL.md` 和 `references/runtime-sleep-loop.md`，再执行一次完整 `$STATE read`，从持久状态确认自身角色、目标、`lifecycle_state`、`observation_id`、`loop_id`、`active_round`、已完成轮数、Stop Request 与下一步时间；随后按本 Skill 的按需加载规则补读当前动作需要的 `references/raptor-observation.md`、`references/state-schema.md`，再继续执行。面向用户的下一次回复以“【会话压缩】已自动恢复”说明已恢复上下文；sleep-loop 不为此单独发送空消息。

## 每次响应的第一步

先读取当前群状态，再进行意图路由：

```bash
$STATE read --compact
```

控制与意图路由只读精简状态，避免每分钟重复载入历史 `rounds_summary`；compact 已包含 `target` 和 `initiator_mis`，足够支持每轮播报文案和 `warning` @ Initiator。仅在查看状态、判断连续查询失败或生成最终总结时执行完整的 `$STATE read`。状态不存在是正常情况。不要依赖会话记忆判断是否已有任务，也不要用 `.mutex` 是否存在表示循环所有权。

按用户原话识别意图（示例用于理解语义，不是固定口令）：

1. 准备上线：用户表达准备上线、帮忙盯上线；
2. 开始放量：用户表达开始放量、开始灰度；
3. 结束/取消观测：用户明确要求停止、取消或收尾观测；当前存在非终态 Observation 时，用户表达变更、灰度或发布已完成，也执行结束观测；
4. 查看状态/帮助：用户询问现在怎么样、查看状态；
5. 恢复观测：用户表达恢复观测、继续盯；
6. 补充信息：其余与当前 Observation 有关的消息。

**活跃循环路由（优先于开始、恢复和补充信息的处理）**：若当前为 `OBSERVING`，且 `runtime.heartbeat_at` 距现在小于 2 分钟，说明已有活跃主循环持有本次观测。新响应不得进入或另起 `sleep-loop`、不得写入 heartbeat，也无需执行 Round、Raptor 查询、`start-round`、`finish-round` 或独立播报。执行一次完整的 `$STATE read`，简要回复当前观测摘要（已完成轮数、最近一轮结论、下轮预计时间）；随后退出。按上面的路由识别为结束观测的消息，跳过活跃循环限制，直接执行结束流程；识别为查看状态的消息仍按既有流程处理。若心跳超过 15 分钟，按“恢复观测”条件和流程处理；介于 2 至 15 分钟时，不抢占循环，不另起主循环，可回复观测仍在进行且等待既有循环继续。

> 群内任意新消息都会触发一个独立的新 AI 响应，与既有响应并行、互不感知，因此靠心跳新鲜度而非会话记忆判断所有权，详见 `references/runtime-sleep-loop.md`《并发响应行为》。

## 准备上线

### 1. 归一化目标

从当前消息和用户显式提供的上下文提取：

- 经 `infra-raptor` 实时确认的 `projectId`；用户只提供项目名时，先在 Raptor 项目检索中选择名称完全一致的结果取得 ID，不使用历史上下文、缓存或名称猜测；
- 明确的 `project_type=MRN` 与非空 `bundleVersion`，或明确的 `project_type=H5_DUO` 与有效的 `webVersion`；
- 发起 @ Robot 的用户 MIS：从消息触发上下文取得，不要求用户在正文提供；
- 可选观测时长：建议用户在准备阶段说明，例如“观测 4 小时”或“帮我盯到下午 6 点”。未提供时默认观测 2 小时；
- 其它需要特殊关注的事项（如有）。

用户表达“准备上线”“准备观测”等准备意图时，可结合当前消息、近期群聊历史和入群 Trigger 已提取的信息，复用项目、类型、`bundleVersion` / `webVersion` 与观测时长。信息唯一且完整时，实时校验 `projectId` 后直接创建 `PREPARING` 并采集 Baseline；准备播报中展示复用的目标和时长。存在多个候选、信息缺失或矛盾时追问，不猜测、不创建 Observation。

消息历史仅用于补充目标参数；“开始放量”“停止/取消”“恢复”等状态操作仍必须由当前消息触发。

任一核心条件缺失时，不创建 Observation。说明仅支持已确认项目类型且具有对应版本标识的目标，并列出缺失信息。

### 2. 创建 PREPARING 状态

```bash
$STATE init \
  --initiator-mis <发起上线 @ Robot 用户的 MIS> \
  --max-duration-minutes <观测时长对应分钟数，未提供时省略> \
  --target-json '<项目类型对应的 target JSON，示例见下>'
```

MRN 目标：

```bash
--target-json '{"project_id":34765,"project_name":"...","project_type":"MRN","bundle_name":"...","bundle_version":"0.78.0","log_type":"JS_ERROR"}'
```

H5_DUO 目标：

```bash
--target-json '{"project_id":34867,"project_name":"...","project_type":"H5_DUO","web_version":"0160:0001","log_type":"JS_ERROR"}'
```

如果脚本返回已有活跃 Observation，直接拒绝新建，不排队、不覆盖。

### 3. 采集 Baseline

选择最近一个已经结束、并预留约 2 分钟入库时间的整分钟标准 Window。默认 Window 长度 10 分钟。

Baseline 只查项目全版本（`webVersion=all`，不带目标 `bundleVersion` 过滤或其他 Tag）。按 `references/raptor-observation.md` 遍历分页，过滤 `STATUS in [3, 4, 5]` 与 `CATEGORY=resourceError` 后生成轻量摘要，`all_versions.rows[]` 与正常 Round 同构，作为首个 Round 的环比基准之一（首个 Round 的 `cluster_diff.py --previous-rows-json` 仍取 `rounds_summary` 最后一项而非 Baseline；Baseline 主要用于展示和 Agent 的整体判断参考）。

失败后重试 1 次。仍失败时：

- 保持 `PREPARING`；
- 停止自动重试；
- @ Initiator 说明失败原因；
- 提示可“重试准备”或“取消观测”；
- 不产生 Round Severity。

收到“重试准备”后，不重复执行 `init`；沿用当前 `PREPARING` Observation 重新采集 Baseline，成功后执行 `set-baseline`。

成功后：

```bash
$STATE set-baseline \
  --observation-id <observation_id> \
  --baseline-json '<baseline-json>'
```

向群内展示：项目、目标版本过滤（MRN bundleVersion 或 H5_DUO webVersion）、Baseline Window 和摘要、默认间隔、约 2 分钟入库延迟、观测时长（用户指定或默认 2 小时）和预计结束时间。提示用户放量后告知。Baseline 一旦成功就固定，不因等待时间过长而静默重采。

## 开始放量

只有当前状态为 `READY` 时执行。“开始放量”同时表示用户隐式确认准备阶段展示的目标和参数。

```bash
$STATE start-observing --observation-id <observation_id> --at <真实放量时间ISO>
```

脚本会：

- 保存真实 `rollout_started_at`；
- 将 `observation_started_at` 向上对齐整分钟；
- 生成 `loop_id`；
- 从当前可查询整分钟与对齐后的放量时间取较晚者作为 `next_window_start`，并计算首轮查询时间和最大结束时间；
- 进入 `OBSERVING`。

若传入的 `--at` 是回补的历史时间（超过一个 `interval`），首轮 Window 不会从这个历史时刻开始逐轮追补，而是直接从当前可查询整分钟开始；回复中需标明“`rollout_started_at` 到首轮 Window 起点之间不被观测且不补查”。

立即回复已开始观测，并说明首轮 Window；预计首次播报时间取脚本返回的 `runtime.next_round_at`。随后进入主循环。

## sleep-loop 主循环

循环归当前 `observation_id + loop_id` 所有。每次只串行执行一次 `sleep`，唤醒后重新读取状态；不要并行发起多个 sleep。**单次 sleep 默认 60 秒，最长不超过 120 秒**——无论距 `next_round_at` 还有多久，都不用一次长 sleep 直接等到点；长 sleep 会连带跳过 heartbeat 刷新、fast-check 核检和 Stop Request 检查。

**是否到点看 `next_round_at` 绝对时间戳，不数 sleep 次数**：fast-check 最坏耗时 30 秒，加上 Agent 推理和消息发送，单次唤醒实际间隔会在 60 秒基础上有数十秒浮动；只要判断逻辑始终是 `now >= runtime.next_round_at`，这种浮动只影响触发时刻的微小滞后，不会累积成"数错次数"导致的系统性偏差。不要改用固定次数计数判断是否到点。

每次唤醒依次执行：

1. 读取 `current_observation.json`；
2. 校验 Lifecycle State 仍为 `OBSERVING`；
3. 校验 `observation_id` 与 `loop_id` 仍匹配；不匹配时旧循环静默退出；
4. 写入 heartbeat（**每次唤醒都执行，不属于第 7/8 步的互斥范围**）：

```bash
$STATE heartbeat --observation-id <observation_id> --loop-id <loop_id>
```
5. 若当前时间达到 `runtime.ends_at` 且尚无 Stop Request，以 `requested_by=system:max_duration` 请求停止；
6. 若已有 Stop Request：
   - 有 `active_round`：允许它完成；
   - 无 `active_round`：发送总结、完成状态并退出；
7. 未到 `next_round_at`：执行一次 fast-check（见下），再串行 `sleep`（默认 60 秒，最长不超过 120 秒）；
8. 到时：跳过 fast-check，直接尝试 `start-round`；只有脚本成功写入 `active_round` 后才查询数据。

不要先查询 Raptor 再登记 Round。fast-check 与正常 Round 互斥，同一次唤醒只做其中一个；heartbeat 不参与这个互斥，第 4 步始终执行。

### fast-check（每次未到点的唤醒都做）

按 `references/raptor-observation.md`《fast-check：60s 小循环快速核检》执行：

```bash
python3 ${SKILL_ROOT}/scripts/fast_check.py --paas <paas> --group-id <dxGroupId>
```

`alerts` 非空时，先调用状态命令登记，再立即用 `send_dx_message_tool` 发送独立群消息并 @ Initiator：

```bash
$STATE record-fast-alert --observation-id <observation_id> --loop-id <loop_id> \
  --cluster-names-json '<本次 alerts[].cluster 组成的 JSON 数组>'
```

```text
【变更观测 · 快速预警】目标版本范围内出现官方近一周首现异常，请关注：

- [ERROR] TypeError: xxx  12 次 / 8 人

- [WARN]  SomeWarn        3 次 / 2 人
```

fast-check 播报与正常 Round 播报相互独立，不共用轮次编号，也不等待下一次正常 Round。fast-check 失败（超时、报错）时静默跳过，不重试、不告警，直接进入下一步 `next_round_at` 判断；正常 Round 会覆盖同一异常。

## 执行正常 Round

正常运行期间 Window 连续且不重叠；首次从 `observation_started_at` 开始，恢复后从脚本返回的 `runtime.next_window_start` 重新起算。逻辑区间为 `[window_start, window_end)`；CLI 查询边界的换算已由 `start-round` 完成（见下）。

### 1. 登记 Round

```bash
$STATE start-round \
  --observation-id <observation_id> \
  --loop-id <loop_id>
```

Window 由脚本内部根据 `runtime.next_window_start` 和 `interval_minutes` 自行推导并返回。若返回 Stop Request、循环所有权失效或已有 Round，不执行查询，按最新状态处理。

### 2. 执行 Raptor 双查询

`raptorfe` 的 `--start-long`/`--end-long` 直接使用 `active_round.window_start_ms`/`window_end_ms`；**不要**自行换算或加减，容易算错引发 Raptor 报错。

依据 `references/raptor-observation.md`：

- 全版本：固定 `webVersion=all`，不带目标版本过滤或其他 Tag；
- 目标版本：MRN 使用 `bundleVersion` 过滤（请求参数为 `queryParam.TAG4=["<bundleVersion>"]`），并保持 `webVersion=all`；H5_DUO 使用 `webVersion=<webVersion>`，不带其他 Tag；
- 两次查询的其他参数完全一致；
- 遍历全部分页，读取 `data.total`、`data.table.rows[]` 和跨页 `data.newErrors[]`；
- 全版本和目标查询的 `rows[]` 都按 `references/raptor-observation.md`《查询结果主条目环比&过滤》排除 `STATUS in [3, 4, 5]` 后生成摘要；目标侧被过滤的异常不触发 `newErrors` 硬规则；
- 全版本 `rows[]` 还须排除 `CATEGORY=resourceError` 后写入摘要的 `all_versions.rows[]`，供 `cluster_diff.py` 使用；
- 只形成轻量摘要，不把 Raptor 原始分页响应写入状态。

**两次查询相互独立，必须在同一个工具调用块中并行发起**，不要等全版本查询（含其全部分页）完全结束再开始目标查询。这是 Round 从触发到播报之间延迟的最大可控变量：串行执行会让 Round 耗时接近两次查询之和，并行执行接近两者中较慢的一次。

**时间预算**：单次查询固定 `-t 120000`（2 分钟）超时，超时或失败重试 1 次，仍不成功则本轮对该查询按 `source_available=false` 降级，不再继续重试或等待。整个 Round（从 `start-round` 到 `finish-round`）应控制在 3 分钟内——宁可用不完整数据及时播报，也不要为等数据推迟播报。

单次数据源失败重试 1 次。仍失败时本轮使用 `source_available=false` 的轻量空摘要完成，Evidence 明确“数据不可用”。若上一轮摘要的 `source_available` 也为 `false`，本轮必须为 `warning`；状态脚本不额外维护失败计数。数据源失败不终止 Observation。

### 3. 计算全版本逐条目环比

双查询都成功（`source_available=true`）时，调用无状态计算工具比较本轮与上一轮全版本 `rows[]`：

```bash
python3 ${SKILL_ROOT}/scripts/cluster_diff.py \
  --current-rows-json '<本轮 all_versions.rows JSON>' \
  --previous-rows-json '<rounds_summary[-1].all_versions.rows JSON，无上一轮传 []>'
```

上一轮 rows 需从本响应第一步已读取的完整状态（或按需执行一次完整 `$STATE read`）中的 `rounds_summary` 数组最后一项取得；`cluster_diff.py` 本身不读状态。该脚本只返回命中事实列表，不产出 severity，具体阈值和 `hit_rule` 见 `references/raptor-observation.md`《全版本逐条目环比（cluster_diff.py）》。

### 4. 形成判定

每轮输出：

- `severity`: `ok | notice | warning`；
- `evidence`: 事实列表；
- `reason`: 从事实到结论的理由；
- `confidence`: 0 到 1。

先应用两条硬规则（性质不同，见 `references/raptor-observation.md` 《判定规则》）：

1. **强制值**：目标查询未违反全版本子集关系，且目标范围内存在未被 `STATUS in [3, 4, 5]` 过滤的 Raptor 官方 `data.newErrors[]` 标记 `ERROR`，本轮必须为 `warning`，不可降级；准确表述见该节，不要称“版本首现”。
2. **下限值**：`cluster_diff.py` 返回 `user_count_surge` 或 `count_surge` 时，本轮 severity 下限为 `notice`，不可判为 `ok`；是否升级为 `warning` 由 Agent 结合命中数量、涨幅幅度综合判断，不是自动升级。`new_appeared` 仅表示较上一正常 Round 新增，作为常规提示，不单独抬升 severity。

其他情况由 Agent 结合全版本 Baseline、上一正常 Round、目标异常分布和数据完整性综合判断。连续两轮数据源失败时，本轮以“数据不可用”为 Evidence 产出 `warning`，Observation 继续。

### 5. 完成 Round

```bash
$STATE finish-round \
  --observation-id <observation_id> \
  --loop-id <loop_id> \
  --summary-json '<compact-summary-json>'
```

`summary-json` 的 `all_versions` 必须包含过滤后的逐条目 `rows[]`，供下一轮 `cluster_diff.py` 取用；即使 Round 执行期间收到 Stop Request，也允许完成并保存本轮。脚本会拒绝缺少关键摘要字段的写入，并在错误响应中附 `important_prompt`。收到该字段时，先按《上下文压缩恢复》重新阅读 Skill、完整读取状态并按需补读摘要契约；若仍可靠保有本轮查询、过滤和判定事实，补全摘要后重试 `finish-round`；若已遗忘或无法确认这些事实，复用当前 `active_round` 的 Window 重新查询、过滤和判定后再提交，**不再调用 `start-round` 或创建新 Round**。

### 6. 独立播报

使用 `send_dx_message_tool` 每轮发送独立群消息，不用持续更新 AI 会话回复。以下格式只约束正常 Round；准备阶段与最终总结按各自流程播报，不受影响。

建议结构：用轻量 Markdown 增强扫读：固定标签加粗，只有异常扩展区使用无序列表，避免 Markdown 表格、多余分割线和固定历史轮次表。标题中的中文状态固定映射：`ok` 为 `✅ 正常`，`notice` 为 `⚠️ 关注`，`warning` 为 `❌ 异常`。**`send_dx_message_tool.messageContent` 中单个换行不会稳定形成可见分段；每个逻辑块之间必须保留一个空行，即使用实际的 `\n\n`，不要只用 `\n`。** 每轮先输出标题和带 Raptor 访问链接的 Window：

```text
【变更观测 #Round<N>】✅ 正常

[<window_start> ~ <window_end> · <project>(<version>)](<raptor_url>)

**预计下轮**：<next_round_at>
```

`notice`、`warning` 时，时间窗口后先追加异常事实、分析或证据，并**必须**列出有效变化条目；再输出判定依据和预计下轮。异常扩展区与其他逻辑块之间也保留一个空行；`cluster_diff.py` 的每个 `hits[]` 参考以下格式逐条渲染：

```text
【变更观测 #Round<N>】⚠️ 关注

[<window_start> ~ <window_end> · <project>(<version>)](<raptor_url>)

**显著变化项**：

- [<level>] <cluster>：<count> 次 / <user_count> 人（<人数或次数> +<增量>，↑<涨幅>%）；<new_appeared 时标“较上一轮新增”>

**判定依据**：<reason>

**预计下轮**：<next_round_at>
```

- `user_count_surge` 展示“人数 +<增量>，↑<人数涨幅>%”；`count_surge` 展示“次数 +<增量>，↑<次数涨幅>%”；`new_appeared` 明确标“较上一轮新增”。不展示上轮完整次数和人数。目标范围官方近一周首现 ERROR、数据不可用等未包含在 `hits[]` 的判定依据，也以列表项追加在“显著变化项”下。`inconclusive` 或 `invalid_subset` 时追加过滤说明，前者不得声称异常为目标版本独有，后者不得使用目标版本证据触发专属结论。
- 构造 `<raptor_url>` 前，`projectId` 必须来自本次 Observation 初始化时经 Raptor 项目检索确认、并写入 `target.project_id` 的结果；不得从项目名、历史上下文或缓存推断。使用 Raptor 异常列表页：MRN 为 `https://raptor.mws.sankuai.com/frontend/error/list?type=datetimerange&start=<YYYYMMDDHHmmss>&end=<YYYYMMDDHHmmss>&projectId=<projectId>&webVersion=all&TAG4=<bundleVersion>`；H5_DUO 为 `https://raptor.mws.sankuai.com/frontend/error/list?type=datetimerange&start=<YYYYMMDDHHmmss>&end=<YYYYMMDDHHmmss>&projectId=<projectId>&webVersion=<webVersion>`。`start` 取 `active_round.window_start`；`end` 取逻辑上开区间 `active_round.window_end` 减 1 秒；时间按 Raptor 要求格式化为 `YYYYMMDDHHmmss`。只在输入链接中存在非空 `SEC_CATEGORY` 时保留它，其他 URL 参数均不透传。
- 未来启用 CIA、LogCenter 后，仍保持同一个标题、带访问链接的 Window 和异常扩展区；各数据源的异常事实与判定依据统一收敛在异常扩展区和“判定依据”中，总 `severity` 取各数据源结论中的最高级别。
- `warning`（`❌ 异常`）播报必须 @ Initiator；`ok` 和 `notice` 不用。
- 投递失败当次重试 1 次，仍失败则继续主循环。

## 结束或取消

用户表达明确停止、取消或收尾观测时，立即请求停止；当前存在非终态 Observation 时，表达变更、灰度或发布已完成也按此执行。用户不需要使用固定措辞。

命中后独立响应立即执行：

```bash
$STATE request-stop \
  --observation-id <observation_id> \
  --requested-by <requester-mis>
```

随后检查返回状态：若已 `COMPLETED`，或 `active_round` 为空，则当前响应直接发送总结并执行 `complete`；否则回复“已收到，将停止创建新 Round；当前执行中的 Round 会完成后收尾”。

- `READY` 阶段取消会直接完成，并注明未开始放量；
- `OBSERVING` 阶段若 `active_round` 心跳未陈旧（未超过 15 分钟），不取消已开始 Round，等待其正常完成；
- `OBSERVING` 阶段若 `active_round` 心跳已陈旧（对应旧循环疑似中断遗留），`request-stop` 会直接清空该 `active_round` 并将 Observation 置为 `COMPLETED`，不等待其“完成”，也不补查中断期间的数据；
- 活跃主循环下一次唤醒读取 Stop Request 后停止创建新 Round；
- 当前停止响应或主循环发现无 active Round 时，发送总结并执行 `complete`（若 `request-stop` 已直接终结，则无需再调用 `complete`）。

达到最大观测时长时采用同一路径，`requested_by` 固定为 `system:max_duration`，总结注明自动结束。

## 查看状态

将状态翻译为用户可理解的摘要，不直接倾倒完整 JSON。至少展示：

- Observation ID 和 Lifecycle State；
- 目标项目与目标版本（MRN bundleVersion 或 H5_DUO webVersion）；
- Baseline 时间；
- 已完成轮数与最近一轮结论；
- 下轮预计时间或 Stop Request；
- 心跳是否超过 15 分钟。

## 恢复观测

只在以下条件都满足时恢复：

- 当前为 `OBSERVING`；
- heartbeat 超过 15 分钟；
- 没有 Stop Request；
- active Round 为空，或它属于心跳已陈旧的中断循环。

```bash
$STATE resume --observation-id <observation_id> --at <当前时间ISO>
```

脚本会清除中断遗留的 `active_round`、生成新 `loop_id`，并把 `runtime.next_window_start` 推进到“当前时间减数据入库延迟后向下对齐的整分钟”；旧循环随后因 `loop_id` 不匹配而失效。

恢复响应立即提示用户：从“最后完成 Window 的 `window_end`（若尚无完成轮次则取 `observation_started_at`）”到脚本返回的 `runtime.next_window_start` 之间没有观测数据，本次不补查。正常陈旧恢复场景会产生 Gap。

随后继续 `sleep` 主循环（默认 60 秒，最长不超过 120 秒），不立即查询历史区间。到新的 `runtime.next_round_at` 后，从 `next_window_start` 开始执行一个标准长度的正常 Round，之后按正常节奏连续推进。

## 完成

无 active Round 且 Stop Request 已生效后：

1. 汇总观测目标、实际时长、轮数和各 Severity 数量；
2. 列出重要 warning 和数据不可用情况；
3. 根据 `stop_requested_by` 区分人工停止与最大时长自动结束；
4. 发送独立总结消息；
5. 执行：

```bash
$STATE complete --observation-id <observation_id>
```

若状态文件损坏或任务上下文无法恢复，停止自动执行并向用户说明；不维护额外的 `FAILED` 状态。

## 禁止行为

- 不为未支持或项目类型不明确、缺少对应版本标识的目标创建 Observation；
- 不把 `bundleVersion` 对应的 `TAG4` 请求值直接作为字符串传给 `query-param`，必须使用字符串数组；H5_DUO 不传其他 Tag；
- 不把 `newErrors` 解释为首次出现于当前 bundleVersion；
- 不使用 `get-trend` / `get-groups` 证明 bundleVersion 过滤；
- `baseline-json`、`summary-json` 等 JSON 入参只放过滤后的轻量摘要；`all_versions.rows[]` 只放过滤后的轻量逐条目快照；
- 不用 Agent 心算比较本轮与上一轮全版本聚类的涨幅或集合差异；必须调用 `scripts/cluster_diff.py`；
- 不用 fast-check 替代正常 Round 的判定或双查询；fast-check 只触发独立播报，不产出 severity，不写 `rounds_summary`；
- 不在到达 `next_round_at` 的唤醒里额外执行 fast-check；两者互斥，同一次唤醒只做一个；
- 不直接编辑或删除 `current_observation.json`，所有状态变更必须经 `observation_state.py` 命令完成，避免绕过互斥与校验；
- 不用删除文件代替 Stop Request；
- 不让旧 `loop_id` 继续更新状态；
- 不生成 HTML/WebStatic 报告；
- 不依赖 `dev_docs/`、ADR 或仓库过程文档运行。
