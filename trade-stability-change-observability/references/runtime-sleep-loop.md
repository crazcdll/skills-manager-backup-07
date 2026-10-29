# 1024 Agent 运行时约束（sleep-loop 与播报）

本文是 1024 Agent 平台侧的运行时约束，供 sleep-loop 主循环、状态存储和消息播报使用；不定义 Observation 生命周期、Baseline/Round/Window、Raptor 查询或判定规则，这些内容以 `SKILL.md`、`raptor-observation.md`、`state-schema.md` 为准。

## sleep 超时

单次 `sleep` 存在平台侧阻塞上限：

| sleep 时长 | timeout 参数 | 结果 |
|:---:|:---:|:---:|
| 60s | 70,000ms | 稳定通过 |
| 300s（5min） | 310,000ms | 通过 |
| 600s（10min） | 被杀（SIGKILL，退出码 137） |

单次阻塞上限在 5～10 分钟之间。sleep-loop 每次只串行执行一次 `sleep 60`，不合并成更长的单次 sleep。

## 状态存储路径

只有 `shared/` 路径同时满足跨 bash 调用持久、跨用户共享：

| 路径 | 跨调用持久 | 跨用户共享 | bash 可操作 |
|------|:---:|:---:|:---:|
| `/tmp/` | 否 | — | 是 |
| `users/{mis}/` | 是 | 否 | 是 |
| `groups/{dxGroupId}/` | 否 | — | 否（bash 无权限） |
| `shared/` | 是 | 是 | 是 |

`shared/` 路径始终跨用户共享，不受沙箱执行身份配置（`globalEmpMis`/`groupEmpMisMapping`/对话用户 MIS）影响——群内任意成员触发的响应都能读写同一份状态。这是本 Skill 状态路径固定为 `/efs/data/tenants/{paas}/shared/observation_{dxGroupId}/current_observation.json` 的原因。

## 消息投递

- `send_dx_message_tool` 每次调用生成独立新消息，不受 AI 会话生命周期约束；AI 会话回复是同一条卡片覆盖式更新。sleep-loop 播报必须用前者，逐轮结论需要各自独立可见，不能被覆盖。
- `messageContent` 中单个实际换行 `\n` 不会稳定渲染为大象消息的可见分段；标题、摘要字段、异常区块等相邻逻辑块之间必须使用实际的 `\n\n`（一个空行）。Markdown 无序列表也可分行，但不能替代逻辑块间的空行。
- `send_dx_message_tool` 发送的消息不会出现在 `dx_get_group_history_messages` 的查询结果里；该工具只能看到用户消息和 AI 会话回复。**不要用消息历史判断某一轮是否已经播报过**——去重必须依赖状态字段（如 `fast_alert_seen`、`rounds_summary`），消息历史不是可靠依据。

## 并发响应行为

群内任意新消息都会触发一个独立的新 AI 响应，无论是否已有响应在执行中；两个响应并行运行、互不感知，新响应无法感知旧循环是否仍在 sleep 或查询。这是《每次响应的第一步》"活跃循环路由"一节靠 `runtime.heartbeat_at` 新鲜度而非会话记忆判断所有权的原因。

## 已知限制

- sleep 期间用户消息无法打断 bash 阻塞，终止请求存在最多一个 sleep 周期（约 60 秒）的确认延迟；
- 极端并发下（两个响应同时检查状态）仍可能出现短暂竞态，本 Skill 通过 `.mutex` 互斥目录和 `loop_id` 校验收敛，不追求生产级分布式一致性；
- `dx-bot-cli` 在沙箱下不可用（`flock` 限制），一律使用 `send_dx_message_tool`；
- 每轮实际间隔会因 Agent 推理和消息发送耗时产生 +10~20s 的累积偏差；判断是否到点应始终用 `next_round_at` 绝对时间戳比较，不受此偏差影响（见 `SKILL.md`《sleep-loop 主循环》）。
