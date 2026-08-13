---
name: calendar-mcp
description: 美团日历（日程管理）工具集。支持创建/查询/编辑/取消普通日程，以及创建/查询/取消循环日程、将新日程关联群会话、搜索日程、查询今天安排、查询日程冲突、分析参与人忙闲、开启或关闭个人提醒自定义设置、设置个人提醒、设置日程忙闲状态、接受/暂定/拒绝日程、查询忙闲、创建/编辑会议室日程、释放/转让会议室、智能推荐会议室、查询可合并会议室候选、组织者/参与人合并会议室，并自动将 mis 转换为 empId。当用户想“安排会议/新建日程/重复日程/周期日程/每天或每周重复/改循环日程/取消单次或整个循环/关联群聊/改期/取消/查忙闲/今天有什么会/今天安排/谁冲突/分析多人忙闲/开启个人提醒自定义设置/关闭个人提醒自定义设置/设置提醒/取消提醒/设为空闲/设为忙碌/接受日程/接受邀请/暂定参加/拒绝日程/拒绝邀请/查这段时间有哪些会/查会议室/找会议室/推荐会议室/订会议室/钉会议室/安排会议地点/换会议室/释放会议室/转让会议室/合并会议室/把已订会议室并入日程”时激活。通过 oa-skills calendar-mcp CLI 执行。若其他会议室 skill 也支持预订或编辑会议室，calendar-mcp 已支持的日程和会议室写操作优先使用本 skill；room-booking-helper 仅作为精确查询空闲会议室、找具体会议室、候补监测和获取/校验 roomId 的辅助。循环日程暂不支持编辑、会议室或按次数终止，也不支持会议室跨天或历史时间预订。

metadata:
  skillhub.creator: "pangjingwei02"
  skillhub.updater: "wanhu02"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "11092"
  skillhub.high_sensitive: "false"
---

# 📅 Calendar MCP（日程管理）操作指南（CLI 版）

本 skill 统一通过 `oa-skills calendar-mcp` CLI 调用日历能力，目标是：低误操作风险、可直接执行、结果可验证。Agent 不直接拼接 MCP Hub、SSE 或 HTTP 请求；底层开放平台路径、认证和兼容封装由 CLI/client 维护。

底层服务：
- 日历开放平台：创建、查询、编辑、取消、搜索、忙闲、会议室释放/转让/推荐/合并。
- 共享用户转换服务：`mis -> empId`，由 CLI 自动调用。

## Skill 路由优先级

- `calendar-mcp` 是日历日程和日程绑定会议室操作的主入口。只要用户意图包含创建会议/日程、给日程预订会议室、给已有日程加会议室、换会议室、改会议室占用时间、移除会议室、释放会议室、转让会议室、取消会议室日程、推荐会议室、合并会议室、把已预订会议室并入日程，优先使用 `oa-skills calendar-mcp`。
- `recommendMeetingRooms` 是 `calendar-mcp` 内置的会议室推荐入口。用户说“推荐一个会议室”“帮我找合适会议室”“按人数/大厦/楼层推荐会议室”时，优先使用它做只读推荐；后续要创建或添加会议室时，再使用推荐结果里的 `roomId`。
- `skills-administrative room-booking-helper` 只作为精确会议室查询和候补监测辅助使用：查指定楼宇/楼层/设备/培训室的空闲会议室、按关键词找具体会议室、确认会议室楼宇/楼层/容量/设备、获取或校验 `roomId`；query 无结果且用户明确同意创建候补监测任务时，使用它的 `monitor`。
- 即使 `room-booking-helper` 也支持 `book` 预订能力，默认不要用它完成 `calendar-mcp` 已支持的创建/编辑/释放/转让流程，避免同一会议室资源出现两个写入口。
- `room-booking-helper book` 也是创建带会议室日程的写入口，和 `calendar-mcp createSchedule --roomId` 语义重叠；只有用户明确指定“使用会议室官方 skill / room-booking-helper / skills-administrative 预订”，或 `calendar-mcp` 当前能力无法覆盖且用户确认转交时，才考虑 `room-booking-helper book`；否则按本 skill 的 `createSchedule --roomId` / `updateSchedule --meetingRoomOperateType` 流程处理。

## 前置检查：确保 CLI 与本 Skill 兼容

每次 skill 激活后、认证或业务调用前，先执行结构化能力探测。仅检查 `command -v` 或 `--version` 不足以证明当前全局 CLI 支持本文件所列命令。

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

探测失败时只允许升级一次并复探测。能力探测发生在业务调用之前，所以升级后执行的是本次计划中的首次业务调用；任何可能已经进入认证或远端接口的写操作都不得自动重放。

精确会议室查询、找具体会议室和候补监测依赖 `skills-administrative room-booking-helper`。只有需要调用 `room-booking-helper query/find-room/monitor` 时，才检查 `@cap/skills-administrative` 是否为最新正式版本；版本不一致或未安装时才升级：

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

## 核心约束

- 所有调用必须通过 `oa-skills calendar-mcp ...` 执行；不要在回复里拼接长段 SSE / curl。
- 底层日历接口的参与人相关字段实际要求 `empId`，但 `calendar-mcp` CLI 对外支持传 `mis` 或纯数字 `empId`：
  - `createSchedule --attendees`
  - `searchSchedule --attendees`
  - `listBusyPeriod --users`
  - `analyzeParticipantBusyPeriod --users`
  - `updateSchedule --addAttendees / --removeAttendees`
  - `transferMeetingRoom --receiver`
  上述参数传入 `mis` 时，CLI 会先自动转换为 `empId` 再调用对应后端能力。纯数字输入会同时校验 `empId` 与数字 MIS 命名空间，不能未经验证直接透传；两者命中不同用户时必须停止，并按错误提示用 `empId:<数字>` 或 `mis:<数字>` 明确身份类型。
- 时间参数统一使用 `--startTime / --endTime / --minTime / --maxTime`，对大模型和示例一律传日期时间字符串：
  - `2026-04-07`
  - `2026-04-07 10:00`
  - `2026-04-07 10:00:00`
  CLI / client 会严格校验日期并转换为毫秒时间戳，不会把 `2026-02-30` 自动滚到下个月。无偏移时间默认按 `Asia/Shanghai` 解释，不再依赖运行机器时区；内部仍兼容 10 位秒级和 13 位毫秒级时间戳，以及旧参数名 `--startMs / --endMs / --minMs / --maxMs`，但对大模型不要这样传。
- `createSchedule`、`querySchedule`、`updateSchedule`、`searchSchedule`、`listBusyPeriod`、`recommendMeetingRooms`、`getScheduleDetailConflicts` 和 `analyzeParticipantBusyPeriod` 支持可选 `--timeZone <IANA时区>`；用户明确指定时区或跨时区基准明确时传入，例如 `America/New_York`。也可直接使用带 `Z` / `±HH:mm` 的时间。DST 中不存在或有歧义的墙上时间会失败，此时要求用户补充 UTC 偏移，不要猜测。
- 单独的 `YYYY-MM-DD` 表示所选时区当天 `00:00:00`，不等于全天日程。本 CLI 暂无全天日程标志；创建日程时仍应得到明确开始时间。
- 用户只提供开始时间、未提供结束时间或时长时，所有创建、预订、推荐会议室或查询空闲时间段的流程都默认补齐为 60 分钟，即 `endTime = startTime + 60 分钟`。不要默认 30 分钟；只有用户明确给出结束时间或时长时，才按用户指定值执行。
- “明早/上午/下午”等日期分段不足以创建、预订或查询精确空闲时段，应补问具体开始时间；但用于定位既有日程时，可搜索该自然日并按实际候选时间筛选，不要臆造分段边界。候选不唯一时再让用户选择。
- 日程搜索的底层 `attendUser` 为 empId long 数组；CLI 对外的 `--attendees` 可省略，省略时默认当前认证用户，并负责生成 `tid`（UUID）。
- 日程搜索支持分页：`--pageIndex` 从 1 开始计数，`--pageSize` 是每页条数且最大为 100。CLI 会转换为底层 `offset/limit`；未传分页参数时查询第 1 页、默认 50 条。
- `listTodaySchedule` 开放能力已移除。查询今天安排使用 `searchSchedule`，传入当前用户和当天时间窗口。
- 查询日程冲突使用 `getScheduleDetailConflicts --scheduleId <id> [--timeZone <IANA时区>]`，只展示服务端返回的 `conflictUsers`。`--raw` 只用于排障或内部续链，不允许在输出中拼接 CLI 推断出的用户字段。
- 创建或编辑前分析多人忙闲优先使用 `analyzeParticipantBusyPeriod --users ... --startTime ... --endTime ... [--timeZone <IANA时区>]`；编辑已有日程时传 `--currentScheduleId` 排除当前日程自身。
- 设置当前用户自己的个人提醒使用 `saveMyReminder --scheduleId <id> --mode CUSTOM --minutes "15"` 或 `--mode NONE`。正数表示开始前多少分钟；不要自行添加负数等服务端约定值。`--eventId` 只是兼容别名，对用户统一称为日程 ID；个人提醒只影响当前用户，不影响全体参会人。
- 开启或关闭当前用户的个人提醒自定义设置使用 `updatePersonalReminderSetting --enabled true|false`。该开关只作用于当前认证用户，不接受 `operator`；设置单条提醒时不得静默修改全局开关。
- 单独设置当前用户在某条日程上的忙闲状态使用 `updateFreeBusyStatus --scheduleId <id> --freeBusyStatus BUSY|FREE`。创建或编辑日程时顺带设置忙闲，使用 `createSchedule/updateSchedule --freeBusyStatus BUSY|FREE`；不传则不覆盖服务端默认或既有值。
- 当前用户接受、暂定或拒绝某条日程使用 `updateAttendeeFeedback --scheduleId <id> --feedbackStatus ACCEPT|TENTATIVE|DECLINE`。该命令只能修改当前认证用户自己的参与人反馈，不能替其他参与人操作，也不会修改 `BUSY/FREE`。
- 用户没提供 `scheduleId` 但要改/取消/看详情：应先用 `searchSchedule` 搜索候选，再内部继续调用（不要向用户索要 `scheduleId`）。
- 默认回复只给用户关心结果（中文摘要），不贴原始 RPC；仅在排障、内部续链或用户明确要求时用 `--raw`。`--raw` 是 CLI 解析并规范化后的服务响应，不保证与 HTTP 字节流逐字一致。
- 写操作遇到认证、网络或超时错误时，CLI 不会自动重放。此类失败可能处于“结果未知”状态：先用查询能力核对目标状态，再由用户决定是否重试；不能直接重复创建、更新、删除、释放、转让或合并。
- 创建日程或预订会议室日程时，用户可只提供时间和会议室意图；标题和参会人按以下规则补齐后再调用 CLI：
  - 用户未提供标题时，默认使用 `会议`；如果上下文能生成更准确的简短标题，也可使用上下文标题，不要为标题追问。
  - 用户未提供参会人时，默认参会人为当前认证用户本人。身份来自显式 `--mis`、`MAAS_USER_ID` 或 CLI 默认用户配置；不要把姓名、示例值或 `SSO_USER_ID` 猜成 MIS。CLI 可直接省略 `--attendees` 并使用认证身份。
  - 如果无法确定当前认证用户 MIS，才要求用户补充参会人 MIS；不要把姓名当作 MIS。
  - `--startTime`、`--endTime` 是创建日程的必要时间参数；如果用户只提供开始时间，按默认 60 分钟补齐结束时间。
  - `--location` 和 `--memo` 都是可选参数。用户没有提供地点或备注时，不要追问，也不要臆造默认值；直接不传即可。
- 更新日程时，`--location` 和 `--memo` 是可选更新字段，不传表示不更新。明确要求清空时使用 `--clearLocation` / `--clearMemo`，不要依赖空字符串或把“清空”误解为“不更新”。
- 创建循环日程前，必须先读取 [references/recurrence-pattern.md](references/recurrence-pattern.md)，按其中的字段组合、枚举和值域构造完整 `recurrencePattern`；不要只根据开始日期猜测缺失字段，也不要向规则中加入未使用字段。
- 创建循环日程时必须同时传 `--recurrencePattern '<JSON>'` 与 `--recurrenceDeadline <时间>`。循环规则至少包含 `type` 和对应类型范围内的正整数 `interval`，当前明确不支持 `numberOfOccurrences`；完整参数说明和六类示例只以 [references/recurrence-pattern.md](references/recurrence-pattern.md) 为准。
- 创建成功返回的 `scheduleId` 是循环 master eventId。`querySchedule --raw` 回显 `detail.recurrenceScheduleId`、`detail.recurrencePattern`、`detail.recurrenceDeadline`；普通日程这些字段为空。
- `searchSchedule` 暂不返回循环日程的 master、循环规则或截止时间，也不保证在一次查询中展开整个系列。它只用于按标题、参与人和时间定位候选 `eventId`；判断普通/循环日程以及核对取消范围前，必须继续调用 `querySchedule --scheduleId <eventId> --raw`，并以 `detail.recurrenceScheduleId`、`detail.recurrencePattern`、`detail.recurrenceDeadline` 为准。不要根据搜索结果条数推断系列实例总数。
- `capabilities` 只证明本地 CLI 已支持这些参数，不证明目标环境已发布对应 OpenService SDK、服务端和 DX Open schema。若目标环境返回未知字段、未知方法或契约未部署错误，立即停止并报告环境未就绪；不能去掉循环参数后退化成普通单次日程。
- 当前禁止编辑循环日程，包括修改单次 occurrence/exception 和整个系列。用户提出改时间、标题、参与人、地点、规则、截止日期或“从下次开始改”时，明确说明暂不支持，不调用 `updateSchedule`，也不能退化成普通 selective 更新。可继续帮助查询或按用户明确范围取消循环日程。
- 循环日程取消同样先核对实例与 master：
  - 取消当前实例：`deleteSchedule --scheduleId <实例ID> --operationScope CURRENT`。
  - 取消整个序列：`deleteSchedule --scheduleId <实例ID> --operationScope SERIES --recurrenceScheduleId <master ID>`。`SERIES` 会影响整个序列，必须明确用户要取消整组，不能根据“取消这个会”自行推断。
- 新建日程时可用 `--chatId <群会话ID> --chatType groupchat` 建立群会话关联；两个参数必须同传，操作人必须是目标群成员。该能力只建立既有 `calendar_view` 关联，不发送日程分享卡片，不支持单聊，也不能用于分享已有日程。
- 用户显式要求“关联群/关联群聊”时，执行前提示“关联群是单向操作”；该提示不要求用户二次确认。用户在创建日程时直接指定群会话（包括提供 `chatId` 或要求在当前群会话中创建）时，将会话视为创建参数，不作该提示。
- `--roomId` 和 `--location` 是两个不同字段：`--roomId` 用于预订/占用会议室资源；`--location` 只是用户自填的普通地点展示信息，不会预订会议室。用户明确要“订会议室/钉会议室/预订会议室”时，必须通过会议室查询拿到 `roomId` 后传 `--roomId`，默认不要传 `--location`，也不要把会议室名称、楼宇或楼层写进 `--location` 来代替会议室预订。
- 会议室能力分流：
  - 普通日程创建：不调用会议室查询 CLI，不传 `--roomId`。
  - 推荐会议室：优先使用 `recommendMeetingRooms`，这是只读能力，不会创建或占用会议室。
  - 精确查询会议室：按具体楼宇、楼层、设备、培训室或会议室名称查空闲时，使用 `room-booking-helper query/find-room`。
  - 创建会议室日程：先获得可用会议室 `roomId`，再使用 `createSchedule --roomId`；不要为了展示会议室而额外传 `--location`。
  - 添加/换房/改会议室占用时间/移除会议室：先查日程详情并按 `detail.roomDetail` 分流，再使用 `updateSchedule --meetingRoomOperateType`。
  - 释放/转让会议室：先查日程详情确认是会议室日程，再使用 `releaseMeetingRoom` / `transferMeetingRoom`。
  - 合并会议室：先 `queryMergeCandidates` 获取候选，再按身份使用 `mergeMeetingRoom` 或 `mergeMeetingRoomByAttendee`。
- 循环日程不支持会议室或视频会议操作；不能把循环需求退化成只创建一次，也不能把 `roomId` 与循环创建/更新参数同时发送。
- 会议室名称、楼宇、楼层、容量等条件不能直接当 `roomId` 使用；当用户没有给明确数字 `roomId` 时，可先用 `recommendMeetingRooms` 推荐候选，或用 `skills-administrative room-booking-helper query` 精确查询目标时间段的空闲会议室并取得 `roomId`。查询不到可用会议室时，直接告知不可用，不要继续调用写接口。
- 如果当前环境没有 `skills-administrative` 命令，或 `room-booking-helper query --help` 无法确认参数和返回结构，应停止并说明无法按会议室名称自动查询空闲会议室；不要猜测 `roomId`，也不要绕过会议室查询直接写入。
- 用户只说“钉会议室”但缺少开始时间、目标对象或会议室条件时，先补齐必要信息；如果已给开始时间但未给结束时间或时长，按默认 60 分钟补齐后再调用会议室查询或写接口。
- 普通编辑不进入会议室分支：只改标题、备注、参与人、普通地点等，不调用会议室查询 CLI，不传 `--roomId` / `--meetingRoomOperateType`。
- 编辑日程时间时，如果可能是会议室日程，必须先 `querySchedule --raw` 判断 `detail.roomDetail`；普通日程按普通改期，会议室日程按会议室占用时间修改处理。
- 所有会议室编辑、释放、转让前必须先 `querySchedule --raw`，用 `detail.roomDetail != null` 判断是否为会议室日程：
  - `roomDetail == null`：普通日程。
  - `roomDetail != null`：会议室日程。
- 释放/转让是有副作用的写操作，必须先明确目标日程。如果用户没提供 `scheduleId`，先用 `searchSchedule` 定位候选；候选不唯一时必须让用户确认具体日程。
- 转让会议室的连续流程必须用 `transferMeetingRoom ... --raw` 获取结构化结果。仅当 `status.code` 为 `0` 且 `handoverEventId` 为非空字符串时，才把当前内部 `scheduleId` 原子替换为该 ID；旧 ID 随即视为失效。业务失败或成功响应缺少 `handoverEventId` 时立即停止，不能继续使用旧 ID，也不能猜测新 ID。面向用户回复时不要展示内部 ID，只说明已转让给接收人。
- `updateSchedule` 不支持 `--attendees`。编辑参与人时只能使用：
  - `--addAttendees "mis1,mis2"`
  - `--removeAttendees "mis3,mis4"`
- 当前只支持 `mis -> empId` 转换，不支持“姓名 -> mis”自动转换；如果用户只提供人员姓名，除非能从当前上下文唯一确定对应 `mis`，否则必须要求用户补充 `mis`。
- 示例命令中的人员参数都只是占位符；不要把文档里的示例 MIS 当作默认参会人、查询对象或转让接收人。创建日程的 `--attendees` 可在用户未提供参会人时默认使用当前认证用户本人；除此之外，`--attendees`、`--addAttendees`、`--removeAttendees`、`--users`、`--receiver` 只能来自用户明确输入、当前对话上下文唯一确认的信息。缺少必要人员信息且不能按当前用户默认规则补齐时，先追问。
- `calendar-mcp` CLI 调用之间没有隐式状态，`listBusyPeriod --users` 不会自动成为后续 `createSchedule --attendees`。但在同一个“查忙闲并创建会议”的连续意图中，如果刚刚查询的 `--users` 是当前对话唯一确认的会议参与人，后续创建必须显式沿用这组用户作为 `createSchedule --attendees`；如果只是独立查询忙闲或参与人不唯一，必须先追问确认。
- 若一句话中包含多个动作，例如“先查忙闲再建会”“先搜这周的会再取消其中一条”，要拆成串行步骤执行；每一步只调用一个 CLI 方法。
- 查询其他人的日程时，不要表述成“对方全部日程”；应理解为“你当前有权限看到的、与输入条件匹配的日程/交集日程”。
- 删除或更新日程后，优先用 `querySchedule --raw` 或再次按 `scheduleId` 验证；`searchSchedule` 的检索结果可能有短暂延迟，不要用刚删除后的一次搜索结果直接判定删除失败。
- 涉及会议室查询或预订时，先执行 `date "+今天是 %Y年%m月%d日，星期%u，当前时间 %H:%M"`，再推算“明天/这周六/下周五”等相对日期；推算后必须验证星期一致。
- 会议室时间限制：普通会议室预订窗口不超过 8 天，培训会议室不超过 30 天；普通会议室单次时长 5 分钟到 4 小时；时间粒度为 5 分钟倍数；不支持历史时间、跨天预订、周期性预订；禁止轮询抢订。
- `room-booking-helper query` 返回的会议室 `id` 就是后续传给 `calendar-mcp` 的 `roomId`。不要臆造字段名；如果输出里无法确认 `id` / `roomId`，停止并说明无法继续写入。
- `room-booking-helper book` 不作为 `calendar-mcp` 默认创建会议室日程流程的一部分；默认仍使用 `createSchedule --roomId`，避免双入口创建日程。

## 认证

认证由 CLI 自动处理，根据运行环境选择合适的策略，优先 SSO 无感登录。Token 自动缓存。

常见自查：
- 认证失败/过期：`oa-skills calendar-mcp --clear-cache` 后重试
- mis 无法解析：需要用户提供正确 mis（不支持"姓名 → mis"自动识别）

## CLI 使用

所有命令格式：`oa-skills calendar-mcp <method> [options]`

```bash
# 查看帮助
oa-skills calendar-mcp --help

# mis -> empId
oa-skills calendar-mcp resolveEmpIdsByMis --misCsv "<用户mis1>,<用户mis2>"

# 创建日程（CLI 接受 mis 或 empId，内部自动转换为底层接口需要的 empId；location/memo 可选）
oa-skills calendar-mcp createSchedule --title "项目周会" --attendees "<参会人mis1>,<参会人mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --location "A3-09木星"

# 创建每日循环日程（创建成功返回 master eventId；其他规则见 references/recurrence-pattern.md）
oa-skills calendar-mcp createSchedule --title "项目晨会" --attendees "<参会人mis1>,<参会人mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 09:30" --recurrencePattern '{"type":"DAILY","interval":1}' --recurrenceDeadline "2026-04-03 23:59:59"

# 创建日程并关联群会话（只建立关联，不发送分享卡片）
oa-skills calendar-mcp createSchedule --title "群项目会" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --chatId "<群会话ID>" --chatType groupchat

# 查询空闲会议室 / 获取 roomId（query 结果的 id 用作 calendar-mcp 的 roomId）
skills-administrative room-booking-helper query \
  --building 互联D2 --date 2026-03-03 --start 09:00 --end 10:00

skills-administrative room-booking-helper query \
  --city 北京 --building 恒电 --date 2026-03-03 --start 09:00 --end 10:00 \
  --capacity 10 --equips Zoom 可开窗户

# 已知具体会议室名时，先查会议室信息，再用 query 校验目标时间是否空闲
skills-administrative room-booking-helper find-room --keyword 青田厅 --raw

# 创建会议室日程（先通过会议室查询或推荐拿 roomId；只额外传 roomId）
oa-skills calendar-mcp createSchedule --title "项目周会" --attendees "<参会人mis1>,<参会人mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --roomId 573

# 搜索日程（CLI 接受 mis 或 empId，内部自动转换为底层接口需要的 empId；pageIndex 从 1 开始）
oa-skills calendar-mcp searchSchedule --attendees "<查询对象mis1>,<查询对象mis2>" --startTime "2026-03-03 00:00" --endTime "2026-03-03 23:59:59" --title "周会" --pageIndex 1 --pageSize 20

# 查忙闲（CLI 接受 mis 或 empId，内部自动转换为底层接口需要的 empId）
oa-skills calendar-mcp listBusyPeriod --users "<用户mis1>,<用户mis2>" --minTime "2026-03-03 09:00" --maxTime "2026-03-03 18:00"

# 查询某条日程的冲突参与人
oa-skills calendar-mcp getScheduleDetailConflicts --scheduleId "schedule-id"
oa-skills calendar-mcp getScheduleDetailConflicts --scheduleId "schedule-id" --timeZone "Asia/Shanghai"

# 分析参与人忙闲，编辑已有日程时传 currentScheduleId 排除自身
oa-skills calendar-mcp analyzeParticipantBusyPeriod --users "<用户mis1>,<用户mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00"
oa-skills calendar-mcp analyzeParticipantBusyPeriod --users "<用户mis1>,<用户mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --currentScheduleId "schedule-id" --timeZone "Asia/Shanghai"

# 设置 / 取消当前用户自己的个人提醒
oa-skills calendar-mcp saveMyReminder --scheduleId "schedule-id" --mode CUSTOM --minutes "15"
oa-skills calendar-mcp saveMyReminder --scheduleId "schedule-id" --mode NONE

# 开启 / 关闭当前用户的个人提醒自定义设置
oa-skills calendar-mcp updatePersonalReminderSetting --enabled true
oa-skills calendar-mcp updatePersonalReminderSetting --enabled false

# 设置当前用户在该日程中的忙闲状态
oa-skills calendar-mcp querySchedule --scheduleId "schedule-id"
oa-skills calendar-mcp updateFreeBusyStatus --scheduleId "schedule-id" --freeBusyStatus FREE
oa-skills calendar-mcp createSchedule --title "项目周会" --attendees "<参会人mis1>,<参会人mis2>" --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --freeBusyStatus BUSY
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --freeBusyStatus FREE

# 接受、暂定或拒绝当前用户参与的日程
oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "schedule-id" --feedbackStatus ACCEPT
oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "schedule-id" --feedbackStatus TENTATIVE
oa-skills calendar-mcp updateAttendeeFeedback --scheduleId "schedule-id" --feedbackStatus DECLINE

# 查详情 / 改期 / 取消（内部优先用搜索结果的 scheduleId，不对外展示）
oa-skills calendar-mcp querySchedule --scheduleId "schedule-id"
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --title "改期" --startTime "2026-03-03 11:00" --endTime "2026-03-03 12:00"
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --addAttendees "<新增参会人mis1>,<新增参会人mis2>"
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --removeAttendees "<移除参会人mis>"
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --clearLocation --clearMemo
oa-skills calendar-mcp deleteSchedule --scheduleId "schedule-id"

# 循环日程当前禁止编辑；不要为 CURRENT 或 SERIES 生成 updateSchedule 命令

# 取消循环当前实例 / 整个序列
oa-skills calendar-mcp deleteSchedule --scheduleId "<当前实例ID>" --operationScope CURRENT
oa-skills calendar-mcp deleteSchedule --scheduleId "<当前实例ID>" --operationScope SERIES --recurrenceScheduleId "<循环master ID>"

# 编辑会议室（先 querySchedule --raw 判断 roomDetail；meetingRoomOperateType: 1=ADD, 2=UPDATE, 3=REMOVE）
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --meetingRoomOperateType 1 --roomId 573
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --meetingRoomOperateType 2 --roomId 574
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --startTime "2026-03-03 11:00" --endTime "2026-03-03 12:00" --meetingRoomOperateType 2
oa-skills calendar-mcp updateSchedule --scheduleId "schedule-id" --meetingRoomOperateType 3

# 释放 / 转让会议室
oa-skills calendar-mcp releaseMeetingRoom --scheduleId "schedule-id"
oa-skills calendar-mcp transferMeetingRoom --scheduleId "schedule-id" --receiver "<接收人mis>" --raw

# 查询可合并的会议室候选（查看当前日程可以合并哪些已预订的会议室）
oa-skills calendar-mcp queryMergeCandidates --scheduleId "schedule-id"

# 智能推荐会议室（根据时间、人数、大厦/楼层偏好推荐空闲会议室）
oa-skills calendar-mcp recommendMeetingRooms --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00"
oa-skills calendar-mcp recommendMeetingRooms --startTime "2026-03-03 09:00" --endTime "2026-03-03 10:00" --attendeeCount 5 --buildingHint "望京A座" --floorHint "10F"

# 组织者合并会议室（roomEventId 从 queryMergeCandidates 获取）
oa-skills calendar-mcp mergeMeetingRoom --scheduleId "schedule-id" --roomEventId "room-event-id"

# 参与人合并会议室（roomEventId 从 queryMergeCandidates 获取）
oa-skills calendar-mcp mergeMeetingRoomByAttendee --scheduleId "schedule-id" --roomEventId "room-event-id"

```

注意：
- 示例只展示常见调用形态；参数必填、时间格式、`mis -> empId` 转换、`--location` / `--memo` 可选规则以“核心约束”为准。
- 普通日程和会议室日程的创建、编辑、合并分流规则以“执行策略”为准；不要把示例里的 `--roomId`、`meetingRoomOperateType` 或会议室名称当作默认值。
- 所有命令都通过 `oa-skills calendar-mcp` 执行；不要根据底层接口形态自行拼接请求。

## 执行策略

### 今日安排和冲突分析

今日上下文：
- 用户问“今天有什么安排”时，使用 `searchSchedule` 查询当前用户的当天时间窗口；省略 `--attendees` 即默认本人。
- 用户问“接下来有什么会”时，开始时间取当前时刻，而不是当天零点；结束时间取用户给定范围或当天结束。
- 用户问“今天是否有空/这段时间我忙不忙”时，使用 `listBusyPeriod` 查询当前用户，而不是根据搜索到的日程数量推断忙闲；省略 `--users` 即默认本人。
- 搜索结果只摘要标题、时间、地点和组织者；只有接口明确返回忙闲字段时才能展示忙闲状态。

已有日程冲突：
- 用户没给 `scheduleId` 时，先用 `searchSchedule` 定位候选；候选不唯一时先让用户选择。
- 唯一目标确定后调用 `getScheduleDetailConflicts --scheduleId <id>`。
- 用户明确指定时区，或跨时区场景已能唯一确定基准时区时，追加 `--timeZone <IANA时区>`；否则省略该参数。
- 展示时只使用服务端返回的 `conflictUsers`，不要兼容已删除字段，也不要伪造姓名或用户对象。
- 用户明确要求 raw 时可以加 `--raw`；结果是 CLI 规范化后的服务字段，不能混入 CLI 推断字段，也不要声称它是逐字节 HTTP 原文。

创建或编辑前多人忙闲：
- 用户要求“看看这些人这段时间忙不忙”“创建前查冲突”时，优先调用 `analyzeParticipantBusyPeriod`。
- `--users` 可传 MIS 或数字 empId；CLI 会转换和去重。
- 编辑已有日程时必须带 `--currentScheduleId`，避免把当前日程算作自身冲突。
- 用户明确指定时区，或跨时区场景已能唯一确定基准时区时，追加 `--timeZone <IANA时区>`；否则省略该参数。
- 该命令返回忙碌区间，不等同于自动推荐会议时间；如果上层基于结果推算空档，需要明确说明是推算。

### 个人提醒、忙闲和参与人反馈

个人提醒：
- 开启当前用户的个人提醒自定义设置：`updatePersonalReminderSetting --enabled true`。
- 关闭当前用户的个人提醒自定义设置：`updatePersonalReminderSetting --enabled false`。
- 设置当前用户提醒：`saveMyReminder --scheduleId <id> --mode CUSTOM --minutes "15"`，表示开始前 15 分钟。
- 取消当前用户提醒：`saveMyReminder --scheduleId <id> --mode NONE`。
- `updatePersonalReminderSetting` 只修改当前认证用户的全局开关；`saveMyReminder` 只修改指定日程的当前用户提醒，两者不能互相替代。
- “取消这条日程的提醒”只调用 `saveMyReminder --mode NONE`；只有用户明确说“关闭个人提醒自定义设置/关闭所有自定义提醒”时才调用全局开关。
- 当前没有读取全局提醒开关的能力。设置单条提醒时先直接调用 `saveMyReminder`；只有服务端明确返回“全局开关未开启”后，才询问用户是否开启。用户同意后最多开启并重试一次，不能静默修改全局设置。
- `--minutes` 默认只使用用户明确给出的“开始前 N 分钟”正整数；用户未给提前量时应询问，不要套用 `15,-540` 等魔法值。
- 对用户统一使用 `scheduleId` / 日程 ID 说法；只有兼容旧上下文时才接受 `--eventId` 别名。
- 当前只有写入能力；除非详情接口明确返回当前用户提醒配置，不要回答“当前提醒是什么”。

忙闲状态：
- 修改前先调用 `querySchedule --scheduleId <id>`；默认输出中的“忙闲状态”是当前值，“忙闲可设置”来自服务端 `canSetFreeBusyStatus`。结果为“不可设置”时停止写入并说明原因；结果为“未知”时不要声称已确认权限，以实际写接口结果为准。
- 只改当前用户自己在某条日程上的忙闲，使用 `updateFreeBusyStatus --scheduleId <id> --freeBusyStatus BUSY|FREE`。
- 该操作不代表修改全体参会人的忙闲，不修改反馈状态，也不等同于普通日程编辑。
- 创建或编辑日程时用户同时要求设为空闲/忙碌，可在 `createSchedule` 或 `updateSchedule` 上加 `--freeBusyStatus BUSY|FREE`。
- 只改忙闲状态时优先用 `updateFreeBusyStatus`，避免走普通 `updateSchedule` 引入额外编辑副作用。

参与人反馈：
- 用户明确表达“接受/确认参加”时使用 `ACCEPT`，“暂定/可能参加”时使用 `TENTATIVE`，“拒绝/不参加”时使用 `DECLINE`。
- 命令为 `updateAttendeeFeedback --scheduleId <id> --feedbackStatus ACCEPT|TENTATIVE|DECLINE`，只修改当前认证用户自己的反馈状态；不要提供或构造 `operator` 参数，开放平台会绑定当前用户身份。
- 参与人反馈与忙闲状态是两套独立能力：接受、暂定或拒绝日程不能用 `updateFreeBusyStatus`；设置 `BUSY/FREE` 也不能代替接受或拒绝邀请。
- 这是有副作用的写操作。用户只问“我是否接受了”“有哪些待响应日程”时不要调用；只有用户明确要求接受、暂定或拒绝目标日程时才执行。
- 用户没提供 `scheduleId` 时，先用 `searchSchedule` 定位目标；候选不唯一时让用户选择，不能批量猜测。唯一目标和反馈意图明确后可直接执行。
- 成功后仅说明当前用户的参与状态已更新，不要表述成替所有参与人接受或拒绝，也不要声称改变了日程忙闲状态。

### 创建：按风险分流

以下场景，创建前优先执行 `analyzeParticipantBusyPeriod`；如果该接口不可用或需要底层忙闲列表，再使用 `listBusyPeriod`：
- 多人会议
- 用户明确要求避冲突 / 找都空的时间
- 需要向用户推荐候选时间

以下场景可跳过忙闲检查：
- 单人提醒
- 用户明确要求“直接创建，不用查忙闲”

冲突检查后的唯一动作规则：
- 没有冲突：按原计划创建。
- 发现冲突：展示冲突参与人或忙碌区间，询问用户“仍按原时间创建”还是“调整时间”；不得自行创建，也不得自行改到另一个时间。
- 用户原话已经明确“即使冲突也创建/直接创建”时，可继续创建，但回复中应说明检测到冲突。
- 只有用户明确要求“推荐都空的时间”时，才根据忙闲结果推算候选空档；推算结果必须标注为候选，不能自动写入。

### 只查会议室：不创建日程

适用场景：
- 用户问“有没有空会议室”“哪个会议室有空”“推荐一个会议室”“找个有 Zoom 的会议室”“青田厅在哪”
- 用户明确说“帮我查会议室”，未表达创建日程或预订动作

执行规则：
- 日期和开始时间是查询必需信息；如果用户已给开始时间但未给结束时间或时长，按默认 60 分钟补齐结束时间。建筑、城市、楼层、人数和设备都是可选偏好：用户没提就不要逐项追问，只有当前结果过多、条件无法执行或用户要求精确筛选时再补问必要项。
- 用户说“推荐一个会议室”“帮我找合适会议室”“按人数/大厦/楼层推荐”时，优先用 `recommendMeetingRooms --startTime <start> --endTime <end> [--attendeeCount N] [--buildingHint <building>] [--floorHint <floor>]`。这是只读能力；推荐结果里的 `roomId` 只能在用户明确要创建/添加会议室后用于写接口。
- 用户给出明确楼宇/楼层/设备/培训室筛选，或要校验具体会议室是否空闲时，用 `skills-administrative room-booking-helper query`；已知具体会议室名时，先用 `find-room --keyword <关键词> --raw` 确认会议室信息，再用 `query` 校验目标时间是否空闲。
- 只展示查询或推荐结果，不调用 `createSchedule` / `updateSchedule` / `room-booking-helper book`。
- 查询结果应展示会议室名称、日期时间、楼层、容量、设备、地图等用户关心信息；默认不展示 `scheduleId`。
- query 无结果时，告诉用户当前条件无空闲会议室，不要自作主张换时间段；可询问是否调整查询条件，或是否通过 `skills-administrative room-booking-helper monitor` 创建候补监测任务。`monitor` 是新的副作用，必须用户明确同意后才执行。

会议室日程：
- 用户明确给出 `roomId` 时，可使用 `createSchedule --roomId` 创建会议室日程。
- 用户只给会议室名称、楼宇、楼层、容量等条件时，先用 `recommendMeetingRooms` 或 `skills-administrative room-booking-helper query` 获得目标时间段可用会议室并取得 `roomId`；不要猜测 `roomId`。如果用户给的是具体会议室名，可先用 `find-room` 确认建筑/楼层/容量，再用 `query` 校验目标时间空闲。
- 会议室预订场景默认只传 `--roomId`，不传 `--location`；不要把会议室名称或楼宇信息作为普通地点写入 `location` 来模拟会议室。
- 用户只说“钉会议室”时，先补齐开始时间、目标对象和会议室条件；如果已给开始时间但未给结束时间或时长，按默认 60 分钟补齐结束时间。缺少开始时间时不能查会议室，也不能创建/更新。
- 查询结果为空时，直接告诉用户目标会议室或目标时间不可用，不调用 `calendar-mcp` 写接口，不要自动改时间段；可询问是否调整条件。
- 查询结果多条且无法唯一匹配时，先让用户选择具体会议室。
- 创建会议室日程前如用户要求避开冲突，仍可先查参与人忙闲；会议室自身空闲用 `room-booking-helper query` 前置确认，后端写接口返回的业务失败也必须透传。
- 如果用户有容量/设备/楼层偏好，优先选择最匹配的推荐或 query 结果；没有偏好时可推荐第一条候选，但在真正写入 `createSchedule --roomId` 前应确认用户意图是“订/创建”，不是“查询”。

### 编辑：先分流普通编辑和会议室编辑

所有改期先定位唯一日程并调用 `querySchedule --raw` 读取原 `startTime/endTime`，再计算完整的新时间范围：
- “改到 15:00”或只给新开始时间：保持原时长，开始和结束一起平移；不能沿用旧结束时间，也不能套创建时的默认 60 分钟。
- “推迟/提前 N 分钟”：开始和结束同时移动 N 分钟。
- “延长/缩短 N 分钟”：开始不变，只调整结束时间。
- 用户明确给出新开始和新结束：按用户值执行。
- 多人日程改期前使用 `analyzeParticipantBusyPeriod`，并传 `--currentScheduleId` 排除日程自身。发现冲突后展示并询问是否仍改期或另选时间，不得自行决定。
- 调用 `updateSchedule` 时必须至少包含一个真实更新字段；清空地点/备注分别使用 `--clearLocation` / `--clearMemo`。

普通编辑保持普通 `updateSchedule` 流程，不触发会议室查询：
- 改标题、备注、普通地点、参与人：不传 `--roomId` / `--meetingRoomOperateType`。
- 普通日程改时间且用户没有会议室资源意图：按普通改期处理。
- 已经是会议室日程但只改标题、备注、参与人等不影响会议室占用的字段：按普通编辑处理，不传 `meetingRoomOperateType`。

以下场景才进入会议室编辑分支：
- 给普通日程添加会议室。
- 把已有会议室日程换到另一个会议室。
- 修改已有会议室日程的会议室占用时间。
- 移除会议室但保留日程。

会议室编辑前置：
- 如果用户没有 `scheduleId`，先用 `searchSchedule` 搜索候选；候选不唯一时让用户确认。
- 拿到唯一 `scheduleId` 后，先 `querySchedule --raw`。
- 用 `detail.roomDetail != null` 判断原日程类型。

会议室编辑决策：
- 普通日程添加会议室：原日程 `roomDetail == null`，先用 `skills-administrative room-booking-helper query` 查目标时间可用会议室，拿到 `roomId` 后执行 `updateSchedule --meetingRoomOperateType 1 --roomId <id>`。
- 会议室日程换房：原日程 `roomDetail != null`，先查目标会议室在目标时间是否空闲，拿到 `roomId` 后执行 `updateSchedule --meetingRoomOperateType 2 --roomId <newRoomId>`。
- 会议室日程只改时间：原日程 `roomDetail != null`，必须先按“已订会议室日程改时间”规则判断是否需要查新增占用区间；只有缩短时间或新增占用区间确认空闲后，才能执行 `updateSchedule --startTime <newStart> --endTime <newEnd> --meetingRoomOperateType 2`，不传 `--roomId`。
- 会议室日程移除会议室：原日程 `roomDetail != null`，执行 `updateSchedule --meetingRoomOperateType 3`，不传 `--roomId`。
- 普通日程不能执行换房、只改会议室占用时间或移除会议室；应直接说明当前日程没有绑定会议室。

已订会议室日程改时间：
- 先从 `querySchedule --raw` 的原日程详情读取 `oldStart`、`oldEnd` 和当前会议室信息，计算完整的 `newStart/newEnd`，并验证 `newStart < newEnd`。
- 只检查“新占用减去旧占用”的非空区间：左侧新增段为 `[newStart, min(newEnd, oldStart))`（仅当 `newStart < oldStart`），右侧新增段为 `[max(newStart, oldEnd), newEnd)`（仅当 `newEnd > oldEnd`）。这同样覆盖缩短、扩展、平移、部分重叠和完全不重叠场景。
- 新区间完全位于旧区间内时没有新增占用，可直接走 `meetingRoomOperateType=2` 更新；否则逐段确认当前同一会议室空闲，所有新增段都可用后才能更新。
- 查询新增占用区间时，使用 `detail.roomDetail` 中能唯一识别当前会议室的真实字段；如果查询结果不能确认是同一会议室，或不能排除其他占用，视为不可确认并停止写入。
- 任一新增占用区间不可用或不可确认时，不调用更新接口，直接说明具体冲突区间或无法确认可用。

### 取消语义：先区分作用域

- “取消整个日程/取消会议”：先查询详情判断当前用户角色；组织者取消整场使用 `deleteSchedule`。
- “我不参加/拒绝邀请/从这个会退出”：使用 `updateAttendeeFeedback --feedbackStatus DECLINE`，不能删除整场日程。
- “取消这条提醒”：使用 `saveMyReminder --mode NONE`，不能关闭全局提醒设置。
- “取消会议室”：继续按“删除整个会议室日程 / 提前释放 / 仅移除会议室”三种动作分流。
- 目标唯一、用户动词和作用域明确时可直接执行；“取消这个会”但无法从详情确定用户要删除整场还是仅拒绝参加时，只追问这一个作用域问题，不能猜测执行破坏性操作。

### 搜索：用于先定位候选日程

适用场景：
- 用户只记得参与人、时间范围、标题关键词，想先列出候选日程
- 用户没有 `scheduleId`，但需要先搜索再决定查哪条详情、编辑或取消

约束：
- `searchSchedule` 是“按条件列出候选日程”，不是“按 ID 查详情”
- 循环日程的搜索结果当前只适合定位候选 `eventId`，不承诺返回循环 master/规则/截止时间，也不承诺展开全部 occurrence；需要识别循环属性或继续按 CURRENT/SERIES 取消时，必须对候选调用 `querySchedule --raw`
- 当查询对象包含其他用户时，搜索结果应理解为“当前你有权限看到的匹配日程”，不要表述成对方全部日程
- CLI 会区分“本页数量”和“总数”。只要提示还有下一页，就必须继续翻页或告诉用户结果未穷尽；不能把当前页唯一候选当成全量唯一候选后直接写入。

### 查询详情：内部依赖 `scheduleId`

适用场景：
- 用户要看某一条已知日程的详细信息

约束：
- 如果用户没有 `scheduleId`，先用 `searchSchedule` 找候选，再内部继续调用 `querySchedule`
- 不要向用户索要 `scheduleId`
- 对用户回复时默认不展示 `scheduleId`

### 会议室合并：先查候选再写入

适用场景：
- 用户说“合并会议室”“把这个会议室并到日程里”“把已订会议室并入会议”“把我订的会议室合到别人/主日程上”。
- 查询当前日程有哪些可合并的会议室候选：`queryMergeCandidates --scheduleId <id>`。
- 组织者执行合并：`mergeMeetingRoom --scheduleId <id> --roomEventId <roomEventId>`。
- 参与人执行合并：`mergeMeetingRoomByAttendee --scheduleId <id> --roomEventId <roomEventId>`。

执行规则：
- 如果用户没有 `scheduleId`，先用 `searchSchedule` 定位目标日程；候选不唯一时让用户确认。
- 合并前必须先调用 `queryMergeCandidates`，从返回结果中读取真实 `roomEventId`；不允许凭空构造 `roomEventId`，也不要把 `roomId` 当成 `roomEventId`。
- `queryMergeCandidates` 是只读操作，可直接调用。若候选为空，直接说明当前日程没有可合并的会议室候选，不继续写操作。
- 候选唯一且用户已明确要合并时，按身份选择命令：组织者身份用 `mergeMeetingRoom`，参与人身份用 `mergeMeetingRoomByAttendee`。身份不明确时，优先根据用户描述判断；仍无法判断时说明需要确认是组织者合并还是参与人合并。
- 候选多条时，展示会议室名称、时间、位置等信息，让用户选择具体候选后再合并。
- `mergeMeetingRoom` / `mergeMeetingRoomByAttendee` 是写操作；用户只说“看看能不能合并”时，只执行 `queryMergeCandidates`。
- 循环日程不支持合并会议室，直接说明暂不支持。

### 会议室编辑、释放和转让

适用场景：
- 给普通日程添加会议室：`updateSchedule --meetingRoomOperateType 1 --roomId <id>`
- 会议室日程换房：`updateSchedule --meetingRoomOperateType 2 --roomId <newRoomId>`
- 会议室日程只改占用时间：`updateSchedule --startTime <newStart> --endTime <newEnd> --meetingRoomOperateType 2`
- 会议室日程移除会议室：`updateSchedule --meetingRoomOperateType 3`
- 释放会议室：`releaseMeetingRoom --scheduleId <id>`
- 转让会议室：`transferMeetingRoom --scheduleId <id> --receiver <misOrEmpId>`
- 取消整个会议室日程：`deleteSchedule --scheduleId <id>`
- 智能推荐会议室：`recommendMeetingRooms --startTime <start> --endTime <end> [--attendeeCount N] [--buildingHint <building>] [--floorHint <floor>]`

约束：
- 编辑、释放、转让、推荐都通过 `oa-skills calendar-mcp` CLI 执行；不要根据底层接口形态自行拼请求。
- 转让会议室的 `receiver` 可传 MIS 或数字 empId，CLI 会转换成开放接口要求的 empId。
- 释放/转让前必须明确唯一目标日程并先 `querySchedule --raw`；只有 `detail.roomDetail != null` 才能调用释放/转让。普通日程不能调用释放/转让会议室接口。
- 转让后还要继续操作时，必须调用 `transferMeetingRoom ... --raw`。校验 `status.code == 0` 和非空 `handoverEventId` 后，将内部当前日程 ID 一次性替换为该值；缺失 ID 或业务失败就停止，不能继续使用旧 ID。默认用户可见回复只展示接收人。
- "取消会议室"必须先澄清：取消整个会议室日程用 `deleteSchedule`；提前释放会议室用 `releaseMeetingRoom`；仅移除会议室但保留日程用 `updateSchedule --meetingRoomOperateType 3`。不要一律映射成释放会议室。
- `recommendMeetingRooms` 是只读操作，推荐接口使用当前认证用户身份；推荐结果中的 `roomId` 可直接用于 `createSchedule --roomId` 或 `updateSchedule --meetingRoomOperateType 1 --roomId`。

### 忙闲查询：用于找空档，不代替日程详情

适用场景：
- 创建多人会议前检查冲突
- 用户问“这几个人什么时候都有空”
- 需要给出候选会议时间

命令选择：
- 面向参与人的创建/编辑前冲突分析，优先使用 `analyzeParticipantBusyPeriod`。
- 只需要底层忙碌时段列表，或兼容旧流程时，使用 `listBusyPeriod`。

不适用场景：
- 用户已经提供 `scheduleId`，想确认具体某个日程的内容
- 用户只是想查看某一条日程详情

## 输出规则

- 默认输出中文摘要；`--raw` 输出 CLI 规范化后的 JSON/文本，用于排障或内部字段续链
- CLI 自身可输出 `scheduleId`、`roomEventId`、`handoverEventId` 供内部串行操作；面向用户的最终回复默认隐藏这些 ID，只有用户明确要求时才展示
- 释放会议室成功时回复“会议室释放成功”；转让成功时回复“会议室转让成功，已转让给：<receiver>”，不要展示 `handoverEventId` 或新日程 ID。
