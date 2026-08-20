# Calendar MCP CLI 常用命令

本文件只提供复杂命令的补充示例，不定义路由或场景安全规则。普通创建、搜索和详情按 `SKILL.md` 高频快速路径直接执行；其他操作先读对应场景 reference。只有安装、兼容、认证或写结果未知时才读 [runtime-and-safety.md](runtime-and-safety.md)。命令与参数的最终契约以当前仓库 CLI 实现和 `oa-skills calendar-mcp --help` 为准。

所有命令格式：

```bash
oa-skills calendar-mcp <command> [options]
```

通用选项包括 `--mis <mis>`、`--raw`、`--clear-cache`、`--env <test|st|product>` 和 `--swimlane <lane>`。普通业务调用不要自行添加环境或泳道参数；只有用户或联调上下文明确指定时才使用。

## 诊断与身份转换

```bash
# 查看帮助、兼容能力和底层工具清单
oa-skills calendar-mcp --help
oa-skills calendar-mcp capabilities --raw
oa-skills calendar-mcp listTools

# MIS 转 EmpID；JSON 与 CSV 二选一
oa-skills calendar-mcp resolveEmpIdsByMis --misList '["<mis1>","<mis2>"]'
oa-skills calendar-mcp resolveEmpIdsByMis --misCsv "<mis1>,<mis2>"
```

## 创建、搜索、详情、编辑和取消

```bash
# 创建普通日程；省略 attendees 时默认当前认证用户
oa-skills calendar-mcp createSchedule \
  --title "项目周会" \
  --attendees "<mis1>,<mis2>" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00"

# 创建时设置当前用户忙闲
oa-skills calendar-mcp createSchedule \
  --title "项目周会" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00" \
  --freeBusyStatus BUSY

# 创建并关联群会话；两个参数必须同传
oa-skills calendar-mcp createSchedule \
  --title "群项目会" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00" \
  --chatId "<群会话ID>" \
  --chatType groupchat

# 搜索；description/location/organizer 均为可选筛选项
oa-skills calendar-mcp searchSchedule \
  --attendees "<mis1>,<mis2>" \
  --startTime "2026-04-07 00:00" \
  --endTime "2026-04-07 23:59:59" \
  --title "周会" \
  --description "项目" \
  --location "望京" \
  --organizer "<组织者empId>" \
  --pageIndex 1 \
  --pageSize 20

# 详情与普通编辑
oa-skills calendar-mcp querySchedule --scheduleId "<日程ID>"
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --title "新标题"
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --startTime "2026-04-07 11:00" --endTime "2026-04-07 12:00"
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --addAttendees "<mis1>,<mis2>"
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --removeAttendees "<mis3>"
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --clearLocation --clearMemo

# 取消普通日程
oa-skills calendar-mcp deleteSchedule --scheduleId "<日程ID>"
```

循环创建、查询与取消命令以 [recurrence-pattern.md](recurrence-pattern.md) 为准。

## 冲突、忙闲和时区

```bash
oa-skills calendar-mcp getScheduleDetailConflicts --scheduleId "<日程ID>" --timeZone "Asia/Shanghai"

oa-skills calendar-mcp analyzeParticipantBusyPeriod \
  --users "<mis1>,<mis2>" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00"

# 编辑前排除当前日程自身
oa-skills calendar-mcp analyzeParticipantBusyPeriod \
  --users "<mis1>,<mis2>" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00" \
  --currentScheduleId "<日程ID>"

oa-skills calendar-mcp queryParticipantTimeZone --users "<mis1>,<mis2>"

oa-skills calendar-mcp listBusyPeriod \
  --users "<mis1>,<mis2>" \
  --minTime "2026-04-07 09:00" \
  --maxTime "2026-04-07 18:00"
```

## 个人提醒、忙闲和反馈

```bash
oa-skills calendar-mcp saveMyReminder --scheduleId "<日程ID>" --mode CUSTOM --minutes "15"
oa-skills calendar-mcp saveMyReminder --scheduleId "<日程ID>" --mode NONE

oa-skills calendar-mcp updatePersonalReminderSetting --enabled true
oa-skills calendar-mcp updatePersonalReminderSetting --enabled false

oa-skills calendar-mcp updateFreeBusyStatus --scheduleId "<日程ID>" --freeBusyStatus FREE

oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "<日程ID>" --feedbackStatus ACCEPT
oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "<日程ID>" --feedbackStatus TENTATIVE
oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "<日程ID>" --feedbackStatus DECLINE
```

## 会议室

```bash
# 推荐候选（只读）
oa-skills calendar-mcp recommendMeetingRooms \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00" \
  --attendeeCount 5 \
  --buildingHint "望京A座" \
  --floorHint "10F"

# 创建会议室日程
oa-skills calendar-mcp createSchedule \
  --title "项目周会" \
  --startTime "2026-04-07 10:00" \
  --endTime "2026-04-07 11:00" \
  --roomId 573

# 添加、换房、只改占用时间、移除会议室
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --meetingRoomOperateType 1 --roomId 573
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --meetingRoomOperateType 2 --roomId 574
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --startTime "2026-04-07 11:00" --endTime "2026-04-07 12:00" --meetingRoomOperateType 2
oa-skills calendar-mcp updateSchedule --scheduleId "<日程ID>" --meetingRoomOperateType 3

# 释放与转让；memo 可选，转让续链使用 raw
oa-skills calendar-mcp releaseMeetingRoom --scheduleId "<日程ID>" --memo "提前释放"
oa-skills calendar-mcp transferMeetingRoom --scheduleId "<日程ID>" --receiver "<接收人mis>" --memo "转让会议室" --raw

# 合并先查询真实候选
oa-skills calendar-mcp queryMergeCandidates --scheduleId "<日程ID>"
oa-skills calendar-mcp mergeMeetingRoom --scheduleId "<日程ID>" --roomEventId "<会议室事件ID>"
oa-skills calendar-mcp mergeMeetingRoomByAttendee --scheduleId "<日程ID>" --roomEventId "<会议室事件ID>"
```

精确会议室查询的辅助命令与安全分流见 [meeting-rooms.md](meeting-rooms.md)。
