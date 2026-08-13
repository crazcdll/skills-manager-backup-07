# `recurrencePattern` 循环规则

本文件是 `calendar-mcp` 创建循环日程时 `recurrencePattern` 字段组合、枚举和值示例的详细事实源。操作作用域、查询前置和写操作安全边界仍以 `../SKILL.md` 为准。

## 调用约束

- `--recurrencePattern` 接受一个用单引号包裹的 JSON 对象，至少包含 `type` 和 `interval`。
- 创建循环日程时，`--recurrencePattern` 与 `--recurrenceDeadline` 必须同时传入。
- `recurrenceDeadline` 不能早于日程开始日期，最晚为开始日期两年后。对 Agent 和示例使用日期时间字符串；需要指定时区时同时传 `--timeZone <IANA时区>`。
- 当前只支持按截止时间结束循环，不支持 `numberOfOccurrences`；不要传入该字段，也不要把“重复 N 次”静默改成截止日期。
- 当前禁止编辑循环日程，包括单个 occurrence/exception 和整个序列。不要生成任何带循环参数的 `updateSchedule` 命令，也不要退化成普通 selective 更新。
- 只传目标 `type` 所需的字段。不要为兼容或占位传 `null`、空数组及其他类型专用字段。

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

创建成功后保存返回的 master `scheduleId`，供后续查询或按明确范围取消使用。循环日程编辑当前不可用。
