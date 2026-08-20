# 运行前检查与全局安全规则

本文件只处理 `calendar-mcp` 的安装/兼容异常、认证、复杂身份与时间问题，以及写操作结果未知。普通创建、搜索和详情直接按 `SKILL.md` 的高频快速路径执行，不读取本文件，也不预先运行 `capabilities`。

## CLI 兼容诊断与修复

CLI 自身通过共享 runner 执行版本检查和参数校验。只有出现 CLI 缺失、未知命令/参数、能力不兼容，或升级后需要复核时，才执行以下完整探测；不要让普通业务请求承担这项检查。

```bash
CALENDAR_REGISTRY="https://r.npm.sankuai.com"
probe_calendar_cli() {
  NO_CHECK_VERSION=true oa-skills calendar-mcp capabilities --raw 2>/dev/null | node -e '
    const fs = require("fs");
    const payload = JSON.parse(fs.readFileSync(0, "utf8"));
    const required = [
      "status.strict",
      "raw.requiredPayload",
      "writes.noReplay",
      "time.strictIana",
      "search.pagination",
      "busy.verifiedPayload",
      "identity.numericValidated",
      "update.completeTimeRange",
      "reminder.positiveMinutes",
      "conflicts.timeZone",
      "busyAnalysis.currentScheduleId",
      "participantTimeZone.statusComplete",
      "reminder.personal",
      "freeBusy.canSet",
      "feedback.attendee",
      "meetingRoom.transfer.handoverEventId",
      "meetingRoom.recommend",
      "meetingRoom.merge",
      "schedule.recurrence",
      "schedule.recurrence.editBlocked",
      "schedule.groupchatAssociation"
    ];
    if (payload.schemaVersion !== 1 || required.some((key) => payload.features?.[key] !== true)) {
      process.exit(1);
    }
  '
}

if ! command -v oa-skills >/dev/null 2>&1; then
  npm install -g @it/oa-skills@latest --registry="$CALENDAR_REGISTRY"
fi

if ! probe_calendar_cli; then
  npm install -g @it/oa-skills@latest --registry="$CALENDAR_REGISTRY"
  hash -r 2>/dev/null || true
fi

if ! probe_calendar_cli; then
  echo "calendar-mcp CLI 能力仍与当前 Skill 不兼容，请停止业务调用并报告安装问题。" >&2
  exit 1
fi
```

探测失败时只允许升级一次并复探测。未知命令或本地参数错误发生在业务写入前时，可以修复 CLI 后重新构造调用；任何已经可能进入认证或远端接口的写操作都不得因为升级、认证、网络或超时错误而自动重放。

`capabilities` 只证明本地 CLI 支持参数，不证明目标环境已经发布对应 OpenService SDK、服务端和 DX Open schema。若目标环境返回未知字段、未知方法或契约未部署错误，立即停止；不能删掉参数后退化执行。

## 辅助会议室 CLI 检查

只有需要 `room-booking-helper query/find-room/monitor` 时，才检查 `@cap/skills-administrative` 是否为最新正式版本；不要让普通日程请求承担这项检查。

```bash
LOCAL=$(npm list -g @cap/skills-administrative --depth=0 2>/dev/null | grep '@cap/skills-administrative' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*'); \
REMOTE=$(npm view @cap/skills-administrative dist-tags.latest --registry=https://r.npm.sankuai.com 2>/dev/null); \
if [ -z "$REMOTE" ] && [ -z "$LOCAL" ]; then \
  echo "无法查询 room-booking-helper 最新版本，且本地未安装；停止辅助查询。" >&2; exit 1; \
elif [ -z "$REMOTE" ]; then \
  echo "无法查询最新版本，继续使用本地 $LOCAL，不执行盲目升级。"; \
elif [ "$LOCAL" != "$REMOTE" ]; then \
  echo "版本不一致（本地: ${LOCAL:-未安装}, 远端: $REMOTE），开始升级..."; \
  npm install -g @cap/skills-administrative@latest --registry=https://r.npm.sankuai.com; \
else \
  echo "已是最新版本 $REMOTE，无需升级。"; \
fi
```

如果 `skills-administrative` 不存在，或 `room-booking-helper query --help` 无法确认参数与返回结构，停止辅助查询；不要猜测 `roomId` 或绕过查询直接写入。

## 认证与身份

- 认证由 CLI 根据运行环境自动选择，优先 SSO 无感登录并缓存 Token。认证失败或过期时可执行 `oa-skills calendar-mcp --clear-cache` 后重试认证；不能借此重放结果未知的业务写操作。
- 参与人相关参数支持 MIS 或纯数字 `empId`：`createSchedule --attendees`、`searchSchedule --attendees`、`listBusyPeriod --users`、`analyzeParticipantBusyPeriod --users`、`queryParticipantTimeZone --users`、`updateSchedule --addAttendees/--removeAttendees`、`transferMeetingRoom --receiver`。
- MIS 由 CLI 转换为底层需要的 `empId`。纯数字输入会同时校验 `empId` 与数字 MIS 命名空间；两者命中不同用户时停止，并按错误提示使用 `empId:<数字>` 或 `mis:<数字>` 明确类型。
- 当前不支持“姓名 -> MIS”。只有姓名且上下文不能唯一确认 MIS 时，要求用户补充；不要使用文档示例值、姓名或 `SSO_USER_ID` 猜测。
- `--attendees`、`--addAttendees`、`--removeAttendees`、`--users`、`--receiver` 只能来自用户明确输入或当前对话唯一确认的信息。只有创建日程未提供参与人时，才允许省略 `--attendees` 并使用当前认证用户。

## 时间解释

- 面向 Agent 使用 `--startTime/--endTime/--minTime/--maxTime` 和日期时间字符串，例如 `2026-04-07 10:00`。CLI 严格校验日期，不会把 `2026-02-30` 滚到下个月。
- 无偏移时间默认按 `Asia/Shanghai` 解释。用户明确指定时区或跨时区基准唯一确定时，`createSchedule`、`querySchedule`、`updateSchedule`、`searchSchedule`、`listBusyPeriod`、`recommendMeetingRooms`、`getScheduleDetailConflicts` 和 `analyzeParticipantBusyPeriod` 可传 `--timeZone <IANA时区>`；也可直接使用带 `Z` / `±HH:mm` 的时间。
- DST 中不存在或有歧义的墙上时间会失败，要求用户补充 UTC 偏移，不要猜测。单独 `YYYY-MM-DD` 表示所选时区当天零点，不是全天日程；当前 CLI 没有全天标志。
- 创建日程、推荐会议室、预订会议室或查询精确空闲时段时，只有开始时间而没有结束时间/时长，默认 60 分钟。用户只给“明早/上午/下午”等不精确范围时，创建或精确查询必须补问具体开始时间；若只是定位已有日程，可搜索对应自然日并按真实候选时间筛选。
- 相对日期涉及会议室查询或预订时，先执行 `date "+今天是 %Y年%m月%d日，星期%u，当前时间 %H:%M"`，再推算“明天/这周六/下周五”，并校验日期与星期一致。
- 内部仍兼容旧时间戳和旧参数名，但面向大模型不要生成 `--startMs/--endMs/--minMs/--maxMs`。

## 串行状态与写操作

- 一句话包含多个动作时拆成串行步骤，每一步只调用一个 CLI 方法。CLI 调用之间没有隐式状态；后续命令必须显式传递已确认的参与人和内部 ID。
- 写操作遇到认证、网络或超时错误时不自动重放。先用查询能力核对权威状态；无法核对时结论是“结果未知”，由用户决定是否重试。
- 用户没有 `scheduleId` 时，先 `searchSchedule`。候选不唯一时让用户选择；唯一后再 `querySchedule --raw` 或执行对应写操作。
- 删除或更新后优先使用 `querySchedule --raw` 或按 `scheduleId` 回读。搜索索引可能短暂延迟，不要用删除后的一次搜索结果判定失败。
- 查询其他人的日程只能表述为“当前用户有权限看到的匹配日程”，不能说成对方全部日程。
- `--raw` 是 CLI 解析并规范化后的服务响应，不保证与 HTTP 字节流逐字一致。

## 输出

- 默认输出中文摘要，不贴原始 RPC、JSON 或内部续链 ID。
- 只有排障、验证字段、内部续链或用户明确要求时使用 `--raw`。
- CLI 输出的 `scheduleId`、`roomEventId`、`handoverEventId` 只供内部串行操作；默认不面向用户展示。
- 缺失、重复、结构异常或未覆盖的数据都是“无法确认”，不能当作空闲、成功或无错误。
