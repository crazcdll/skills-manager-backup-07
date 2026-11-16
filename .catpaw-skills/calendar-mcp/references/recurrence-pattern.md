# `recurrencePattern` 循环规则

本文件是 `calendar-mcp` 循环日程创建、识别、编辑、取消作用域，以及 `recurrencePattern` 字段组合、枚举和值示例的唯一事实源。创建日程的通用字段、搜索定位和全局硬约束沿用 [SKILL.md](../SKILL.md)；只有出现 CLI 安装、兼容、认证或写结果未知时，才读取 [runtime-and-safety.md](runtime-and-safety.md)。

## 调用约束

- `--recurrencePattern` 接受一个用单引号包裹的 JSON 对象，至少包含 `type` 和 `interval`。
- 创建循环日程时，`--recurrencePattern` 与 `--recurrenceDeadline` 必须同时传入。
- `recurrenceDeadline` 不能早于日程开始时间，最晚为开始时间两年后。对 Agent 和示例使用日期时间字符串；需要指定时区时同时传 `--timeZone <IANA时区>`。
- 当前只支持按截止时间结束循环，不支持 `numberOfOccurrences`；不要传入该字段，也不要把“重复 N 次”静默改成截止日期。
- 编辑循环日程必须使用 `updateRecurrenceSchedule` 并显式指定作用范围；普通 `updateSchedule` 仍不能编辑循环日程。
- 只传目标 `type` 所需的字段。不要为兼容或占位传 `null`、空数组及其他类型专用字段。
- 循环日程不能修改会议室或视频会议，不能进行会议室合并；取消循环日程只支持 `CURRENT` / `SERIES`，编辑另支持 `FOLLOWING`。不能把循环意图退化成单次日程。

## 创建、查询与写入续链

- 创建成功返回的 `scheduleId` 是循环 master eventId。保存它供后续查询或按明确范围取消。
- `searchSchedule` 只用于按标题、参与人和时间定位候选 `eventId`，不承诺返回 master、循环规则、截止时间，也不保证一次搜索展开整个系列。不能根据搜索结果条数推断实例总数。
- 判断普通/循环日程或核对编辑/取消范围前，必须继续调用 `querySchedule --scheduleId <eventId> --raw`；以 `detail.recurrenceScheduleId`、`detail.recurrencePattern`、`detail.recurrenceDeadline` 为准。普通日程这些字段为空。编辑所需的 `scheduleId` 必须是带时间戳后缀的实例 ID；详情若只有 master ID，先搜索并定位目标场次。
- 取消当前实例：`deleteSchedule --scheduleId <实例ID> --operationScope CURRENT`。
- 取消整个系列：`deleteSchedule --scheduleId <实例ID> --operationScope SERIES --recurrenceScheduleId <master ID>`。
- `SERIES` 会影响整个系列。必须明确用户要取消整组，不能根据“取消这个会”自行推断；实例 ID 和 master ID 不能混用。
- 编辑当前实例用 `updateRecurrenceSchedule --operationScope CURRENT`；编辑整个系列用 `SERIES`；编辑当前实例及后续用 `FOLLOWING`。必须由用户意图明确确定范围，不能自行推断。三种范围都要同时提供实例 ID 和匹配的 master ID。
- 编辑前用 `querySchedule --raw` 核对目标实例和主日程的 `detail.roomDetail`。若任一处有关联会议室，或已知同系列其他实例、例外实例有关联会议室，停止所有编辑，包括只改标题、备注等普通属性。仅查询目标实例和主日程无法证明其他例外实例没有会议室；已知存在时不能继续写入，未知情况需要服务端另行兜底。
- `capabilities` 只证明本地 CLI 支持参数。目标环境返回未知字段、未知方法或契约未部署错误时立即停止，不能移除循环参数后创建单次日程。

## 编辑循环日程

- 可更新标题 `--title`、普通地点 `--location` / `--clearLocation`、备注 `--memo` / `--clearMemo`、参与人增减 `--addAttendees` / `--removeAttendees`、当前用户忙闲状态 `--freeBusyStatus BUSY|FREE`、时间，以及循环规则和截止时间。至少传一个实际更新字段。参与人传 MIS 或 empId；同一人同时增加和移除时，服务端按移除优先处理。`FOLLOWING` 新系列中的原 `DECLINE` 参与人默认不重新邀请，只有明确再次添加才进入新系列。
- 时间变更必须把 `--startTime`、`--endTime`、`--isAllDay true|false` 三者一起传入；只给新开始时间时先从详情得到原时长，算出新结束时间。`isAllDay` 以详情或用户明确要求为准，不能省略或默认 `false`。CLI 接受秒级时间，不要求整分钟。跨时区可加 `--timeZone`。
- 全天编辑时，`--endTime` 应落在**最后一个要包含的日期内**；服务端按该日期计算到次日零点。单日全天用同一天的 `00:00` 和 `23:59:59`，不要把次日 `00:00` 当作结束输入，否则会多包含一天。写后回读核对实际日期范围。
- 以下全天示例按 `Asia/Shanghai` 解释。服务端当前按运行时区截取全天日期；跨时区全天修改不能只靠 `--timeZone` 推断日期范围，无法核对服务端口径时停止。
- 循环规则与截止时间必须同时传 `--recurrencePattern`、`--recurrenceDeadline`，只允许 `SERIES` 或 `FOLLOWING`；`CURRENT` 不能改规则。规则 JSON 不接受 `type=NONE` 或 `numberOfOccurrences`。截止时间须符合新序列起点起两年内等规则。
- 用户只改规则或只改截止时间时，先用 `querySchedule --raw` 读取并核对目标系列当前的完整规则和截止时间；另一项沿用查询到的原值后一起提交。详情缺失或无法确定原值时停止，不用示例值补齐。
- 不支持 `--roomId`、`--meetingRoom`、`--meetingRoomOperateType`、`--videoMeeting`、`--noticeType`、`--noticeRule`、`--optionalAttendees`、`--externalAttendees`、`--attendeeAbilitySet`、`--operator`、`--chatId`、`--chatType`。已有会议室的循环日程按上面的预检规则停止编辑，不尝试用普通字段更新绕过。
- `SERIES` 的结构变更、`FOLLOWING` 拆分会影响已有例外实例；写前说明作用范围，成功后查询目标场次和其他相关场次核对。`FOLLOWING` 返回新 master ID，应保存用于后续查询；若成功响应缺少新 ID 或网络结果未知，先查询核实，不得直接重试。

```bash
# 只改当前一场的标题
oa-skills calendar-mcp updateRecurrenceSchedule \
  --scheduleId "<实例ID>" --recurrenceScheduleId "<master ID>" \
  --operationScope CURRENT --title "临时议题"

# 将当前一场改成 2026-11-03 的单日全天；endTime 是最后一天内的时间
oa-skills calendar-mcp updateRecurrenceSchedule \
  --scheduleId "<实例ID>" --recurrenceScheduleId "<master ID>" \
  --operationScope CURRENT \
  --startTime "2026-11-03 00:00" --endTime "2026-11-03 23:59:59" --isAllDay true

# 从当前场次开始修改后续系列的时间和规则
oa-skills calendar-mcp updateRecurrenceSchedule \
  --scheduleId "<实例ID>" --recurrenceScheduleId "<master ID>" \
  --operationScope FOLLOWING \
  --startTime "2026-10-21 10:00" --endTime "2026-10-21 10:30" --isAllDay false \
  --recurrencePattern '{"type":"WEEKLY","interval":1,"daysOfTheWeek":["WE"]}' \
  --recurrenceDeadline "2026-12-31 23:59:59"
```

## 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 循环类型，枚举见下文。`NONE` 不是开放接口支持的循环类型。 |
| `interval` | positive integer | 循环间隔，单位由 `type` 决定，并受各类型最大值限制。 |
| `daysOfTheWeek` | string[] | 周几或相对日期类别。`WEEKLY` 可传多个具体星期；相对月/年规则只传一个值。 |
| `dayOfTheWeekIndex` | string | 月内第几个或最后一个目标日，仅用于相对月/年规则。 |
| `month` | integer | 月份，范围 `1..12`，仅用于年度规则。 |
| `dayOfMonth` | integer | 月内日期，范围 `1..31`，仅用于绝对月/年规则。 |

## `type` 与字段组合

| `type` | 语义与 `interval` 单位 | `interval` 范围 | 额外必填字段 |
| --- | --- | --- | --- |
| `DAILY` | 每 N 天 | `1..31` | 无 |
| `WEEKLY` | 每 N 周的指定星期 | `1..12` | `daysOfTheWeek`，至少一个具体星期 |
| `ABSOLUTE_MONTHLY` | 每 N 月的第几日 | `1..12` | `dayOfMonth` |
| `RELATIVE_MONTHLY` | 每 N 月的第几个或最后一个目标日 | `1..12` | `daysOfTheWeek`、`dayOfTheWeekIndex` |
| `ABSOLUTE_YEARLY` | 每 N 年的指定月日 | `1..2` | `month`、`dayOfMonth` |
| `RELATIVE_YEARLY` | 每 N 年指定月份的第几个或最后一个目标日 | `1..2` | `month`、`daysOfTheWeek`、`dayOfTheWeekIndex` |

`ABSOLUTE_YEARLY` 的 `month` 与 `dayOfMonth` 必须组成有效日期。`ABSOLUTE_MONTHLY` 使用 `29`、`30` 或 `31` 时，不要向用户承诺所有月份都会产生实例，以服务端实际展开结果为准。

## `daysOfTheWeek` 枚举

具体星期枚举：

| 值 | 含义 | 可用于 |
| --- | --- | --- |
| `MO` | 周一 | `WEEKLY`、相对月/年 |
| `TU` | 周二 | `WEEKLY`、相对月/年 |
| `WE` | 周三 | `WEEKLY`、相对月/年 |
| `TH` | 周四 | `WEEKLY`、相对月/年 |
| `FR` | 周五 | `WEEKLY`、相对月/年 |
| `SA` | 周六 | `WEEKLY`、相对月/年 |
| `SU` | 周日 | `WEEKLY`、相对月/年 |

相对月/年规则还支持以下类别值；不要在 `WEEKLY` 中使用：

| 值 | 含义 |
| --- | --- |
| `WEEKDAY` | 工作日，即周一至周五中的目标日 |
| `WEEKEND_DAY` | 周末日，即周六或周日中的目标日 |
| `DAY` | 自然日 |

`RELATIVE_MONTHLY` 和 `RELATIVE_YEARLY` 的 `daysOfTheWeek` 按单个相对目标表达，只传一个枚举值，例如 `["FR"]` 或 `["WEEKDAY"]`。

“每个工作日/工作日每天”是周循环快捷语义，映射为 `WEEKLY`、`interval: 1` 和 `["MO","TU","WE","TH","FR"]`；不能使用 `DAILY`。`WEEKDAY` 枚举只表示相对月/年规则中的目标日类别，不能用于 `WEEKLY`。

## `dayOfTheWeekIndex` 枚举

| 值 | 含义 |
| --- | --- |
| `FIRST` | 第一个 |
| `SECOND` | 第二个 |
| `THIRD` | 第三个 |
| `FOURTH` | 第四个 |
| `LAST` | 最后一个 |

## 六类规则示例

每天一次：

```json
{"type":"DAILY","interval":1}
```

每两周的周二、周四：

```json
{"type":"WEEKLY","interval":2,"daysOfTheWeek":["TU","TH"]}
```

每月 15 日：

```json
{"type":"ABSOLUTE_MONTHLY","interval":1,"dayOfMonth":15}
```

每月最后一个工作日：

```json
{"type":"RELATIVE_MONTHLY","interval":1,"daysOfTheWeek":["WEEKDAY"],"dayOfTheWeekIndex":"LAST"}
```

每年 12 月 31 日：

```json
{"type":"ABSOLUTE_YEARLY","interval":1,"month":12,"dayOfMonth":31}
```

每年 9 月第一个周一：

```json
{"type":"RELATIVE_YEARLY","interval":1,"month":9,"daysOfTheWeek":["MO"],"dayOfTheWeekIndex":"FIRST"}
```

完整的每周创建示例：

```bash
oa-skills calendar-mcp createSchedule \
  --title "项目例会" \
  --attendees "<参会人mis1>,<参会人mis2>" \
  --startTime "2026-09-01 10:00" \
  --endTime "2026-09-01 10:30" \
  --recurrencePattern '{"type":"WEEKLY","interval":1,"daysOfTheWeek":["TU","TH"]}' \
  --recurrenceDeadline "2026-12-31 23:59:59"
```

编辑前先按“编辑循环日程”核对目标、范围与字段；取消仍只允许明确的 `CURRENT` 或 `SERIES` 范围。
