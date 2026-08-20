---
name: calendar-mcp
description: 美团日历（日程管理）工具集。当用户要安排会议、新建/查询/搜索/改期/取消普通日程，创建、识别或按当前实例/整个系列取消重复/周期日程，关联群聊，查看今天安排、冲突、忙闲或参与人时区，推荐会议时间，设置提醒、忙闲状态、接受/暂定/拒绝邀请，或查询/找/订/钉/换/释放/转让/合并会议室时使用。统一通过 oa-skills calendar-mcp CLI 执行；calendar-mcp 是日程和会议室写操作主入口，room-booking-helper 仅辅助精确查询、找具体会议室、候补监测和校验 roomId。循环日程暂不支持编辑、会议室或按次数终止，会议室不支持跨天或历史时间预订。

metadata:
  skillhub.creator: "pangjingwei02"
  skillhub.updater: "wanhu02"
  skillhub.version: "V7"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "11092"
  skillhub.high_sensitive: "false"
---

# Calendar MCP（日程管理）

本 Skill 把用户意图翻译为 `oa-skills calendar-mcp` CLI 调用。Agent 不直接拼接 MCP Hub、SSE、HTTP 或 Thrift 请求；认证、开放平台路径、响应拆包和 `mis -> empId` 转换由 CLI/client 负责。

## 执行路由

先判断是否命中下述高频快速路径。命中时直接按本文件执行，不读取 reference，也不预先执行 `capabilities`；CLI 自身负责版本检查和参数校验。只有触发升级条件时才读取对应场景文档。

### 高频快速路径

以下三类请求可直接执行：

1. **创建普通单次日程**：用户没有要求循环、会议室、关联群聊、查询冲突、推荐时间或跨时区换算。
2. **搜索已有日程**：用户查询今天、接下来或指定时间范围的安排，不要求判断真实忙闲。
3. **查看普通日程详情**：已有唯一 `scheduleId`；没有 ID 时先快速搜索，候选唯一后再查询。

普通创建规则：

- `--startTime` 必须明确；只有开始时间时默认 60 分钟。标题缺失时使用上下文可确定的简短标题，否则使用 `会议`。
- `--attendees` 只使用用户明确给出的 MIS/empId；未提供时省略并默认当前认证用户。`--location`、`--memo` 未提供时不追问、不传值。
- 用户已经给出明确时间并要求创建时，即使有多位参与人也直接创建；只有用户要求“避开冲突、看看大家是否有空、推荐时间”时才升级到忙闲分析。

```bash
oa-skills calendar-mcp createSchedule \
  --title "项目周会" \
  --attendees "<mis1>,<mis2>" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00"
```

搜索与详情规则：

- “今天有什么安排”使用 `searchSchedule` 查询当前时区当天 `00:00:00` 到 `23:59:59`；“接下来有什么会”从当前时刻查到用户指定范围，未指定时查到当天 `23:59:59`。
- 搜索省略 `--attendees` 时默认当前认证用户；默认第 1 页、50 条，`--pageSize` 最大 100。返回还有下一页时继续翻页，或明确结果尚未穷尽。
- 搜索结果只代表当前用户有权限看到的匹配日程，不能用日程数量推断忙闲。
- `searchSchedule` 只负责定位候选；普通详情使用 `querySchedule`，写前判断、循环属性或会议室类型使用 `querySchedule --raw`。

```bash
oa-skills calendar-mcp searchSchedule \
  --startTime "2026-04-07 00:00" \
  --endTime "2026-04-07 23:59:59"

oa-skills calendar-mcp querySchedule --scheduleId "<日程ID>"
```

### 升级读取路由

| 触发条件 | 读取 |
| --- | --- |
| CLI 缺失、未知命令/参数、版本或能力不兼容、认证异常、写结果未知 | [runtime-and-safety.md](references/runtime-and-safety.md) |
| 编辑、取消、关联群聊、个人提醒、忙闲状态、接受/暂定/拒绝 | [schedule-flow.md](references/schedule-flow.md) |
| 循环日程创建、识别或按当前实例/整个系列取消 | [recurrence-pattern.md](references/recurrence-pattern.md) |
| 冲突判断、多人忙闲、参与人时区、候选会议时间 | [meeting-time-and-timezone.md](references/meeting-time-and-timezone.md) |
| 查询、推荐、预订、添加、换房、改占用时间、移除、释放、转让或合并会议室 | [meeting-rooms.md](references/meeting-rooms.md) |
| 复杂命令需要更多参数示例 | [cli-cheatsheet.md](references/cli-cheatsheet.md)；参数事实以当前 CLI 实现和 `oa-skills calendar-mcp --help` 为准 |

复合意图按步骤读取需要的文档并串行执行。例如“找三个人都有空的时间并订会议室”先读会议时间规则，用户选定时间后再读会议室规则；不要提前查询或占用会议室。

## 路由优先级

- `calendar-mcp` 是日历日程和日程绑定会议室操作的主入口。创建/编辑/取消日程，以及预订、添加、换房、移除、释放、转让或合并会议室，默认都走本 Skill。
- 用户说“推荐会议室”“按人数/大厦/楼层找合适会议室”时，优先使用只读 `recommendMeetingRooms`；用户明确给出楼宇、楼层、设备、培训室或会议室名称时，使用 `skills-administrative room-booking-helper query/find-room` 精确查询。
- `room-booking-helper book` 与 `createSchedule --roomId` 是重叠写入口。仅当用户明确指定使用会议室官方 Skill，或本 Skill 无法覆盖且用户确认转交时才使用；默认禁止用它绕开 `calendar-mcp`。
- `room-booking-helper monitor` 会创建候补监测任务。只有查询无结果且用户明确同意监测条件后才能执行。

## 全局硬约束

- 所有日历业务调用必须使用 `oa-skills calendar-mcp <command>`；不要直接调用底层服务。
- 每个串行步骤只调用一个 CLI 方法。CLI 调用之间没有隐式状态，后续命令必须显式携带当前对话中唯一确认的人员、时间、`scheduleId`、`roomId` 或其他结果字段。
- 写操作必须有唯一目标和完整必要参数。候选不唯一时先让用户选择，不能批量猜测。
- 写操作遇到认证、网络或超时错误时不得自动重放。结果可能为未知；先查询权威状态，再由用户决定是否重试。
- 用户没有 `scheduleId` 但要查看、编辑或取消日程时，先用 `searchSchedule` 找候选；不要要求用户理解或提供内部 ID。
- `searchSchedule` 是候选搜索，不是详情事实源。涉及编辑、取消范围、循环属性或会议室类型时必须继续调用 `querySchedule --raw`。
- 用户明确给出时区时传 IANA 时区；无偏移日期时间默认按 `Asia/Shanghai` 解释。不得猜测 DST 歧义时间或隐藏的参与人时区。
- 创建、推荐会议室或查询精确空闲时段时，只有开始时间而没有结束时间/时长，默认补为 60 分钟；编辑已有日程只给新开始时间时保持原时长，不能套用 60 分钟。
- 用户只给姓名而无法从当前上下文唯一确定 MIS 时，要求补充 MIS；不要把姓名、示例值或 `SSO_USER_ID` 猜成身份。
- 默认只给中文摘要，不贴原始 RPC 或内部 ID。`--raw` 仅用于排障、字段续链或用户明确要求。

## 其他命令索引

| 用户意图 | 首选命令 |
| --- | --- |
| 编辑普通日程 | `updateSchedule` |
| 取消组织者创建的日程 | `deleteSchedule` |
| 查看已有日程冲突参与人 | `getScheduleDetailConflicts` |
| 分析多人忙闲或推荐时间 | `analyzeParticipantBusyPeriod` |
| 查询参与人时区 | `queryParticipantTimeZone` |
| 查询底层忙碌区间 | `listBusyPeriod` |
| 设置/取消个人提醒 | `saveMyReminder` |
| 开关个人提醒自定义设置 | `updatePersonalReminderSetting` |
| 设置当前用户忙闲状态 | `updateFreeBusyStatus` |
| 接受、暂定或拒绝邀请 | `updateAttendeeFeedback` |
| 推荐会议室 | `recommendMeetingRooms` |
| 释放/转让会议室 | `releaseMeetingRoom` / `transferMeetingRoom` |
| 查询/执行会议室合并 | `queryMergeCandidates` 后按身份使用 `mergeMeetingRoom` / `mergeMeetingRoomByAttendee` |

## 必须停止的场景

- CLI 能力探测升级一次后仍不兼容，或目标环境返回未知字段、未知方法、契约未部署错误。
- 人员、日程、取消范围、会议室或写操作目标无法唯一确定。
- 循环日程编辑、循环会议室、循环视频会议、`FOLLOWING`、按次数终止或其他当前未支持能力；不能静默退化成单次普通日程。
- 会议室名称/条件无法解析为真实可用 `roomId`，或无法确认新增会议室占用区间空闲。
- 忙闲/时区批量响应缺行、重复、身份未知或结构异常。缺失证据是“无法确认”，不是空闲。
- 写操作结果未知且尚未通过查询完成状态核对。

## 输出规则

- 默认隐藏 `scheduleId`、`roomId`、`roomEventId`、`handoverEventId` 等续链字段；只有用户明确要求时展示。
- 只陈述服务端返回或按文档规则明确推算的结果。会议时间候选必须标注“根据本次忙闲区间推算，尚未创建或占用资源”。
- 业务失败必须透传原因；未完成回读时不能声称写入已验证。
- 释放成功回复“会议室释放成功”；转让成功回复“会议室转让成功，已转让给：<receiver>”，不要展示内部新日程 ID。
