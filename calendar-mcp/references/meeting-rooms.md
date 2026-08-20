# 会议室查询与写操作

本文件是会议室推荐、精确查询、创建、添加、换房、改占用时间、移除、释放、转让和合并的场景事实源。创建日程的通用字段与默认值沿用 [SKILL.md](../SKILL.md) 的普通创建规则和全局硬约束；编辑、取消或个人状态操作再读取 [schedule-flow.md](schedule-flow.md)。只有出现 CLI 安装、兼容、认证或写结果未知时，才读取 [runtime-and-safety.md](runtime-and-safety.md)。

## 入口和资源语义

- `calendar-mcp` 是日程绑定会议室写操作的主入口。`room-booking-helper` 只辅助精确查询、找具体会议室、候补监测和获取/校验 `roomId`。
- `recommendMeetingRooms` 是内置只读推荐入口，适合按时间、人数、大厦和楼层偏好推荐候选。
- `--roomId` 用于预订/占用真实会议室资源；`--location` 只是普通地点展示，不会预订。不能把会议室名称、楼宇或楼层写进 `--location` 模拟占用。
- 会议室名称、楼宇、楼层、容量和设备条件都不能直接当 `roomId`。只使用推荐或查询结果中确认的真实 `roomId`；`room-booking-helper query` 返回的 `id` 就是后续 `calendar-mcp` 的 `roomId`。
- `room-booking-helper book` 是重叠写入口，默认禁止使用。仅当用户明确指定该 Skill，或 `calendar-mcp` 无法覆盖且用户确认转交时才考虑。
- 循环日程不支持会议室、视频会议或会议室合并；不能退化成单次操作。

## 时间限制

- 日期和开始时间是查询、推荐和预订的必要信息；只给开始时间时按全局规则补 60 分钟。
- 普通会议室预订窗口不超过 8 天，培训会议室不超过 30 天。
- 普通会议室单次时长 5 分钟到 4 小时，时间粒度为 5 分钟倍数。
- 不支持历史时间、跨天或周期性预订，禁止轮询抢订。
- 相对日期先执行 `date "+今天是 %Y年%m月%d日，星期%u，当前时间 %H:%M"` 获取本机日期，再推算“明天/这周六/下周五”并校验日期与星期一致。

## 只查或推荐会议室

用户只问“有没有空会议室/推荐一个/找有 Zoom 的/某会议室在哪”，未表达创建或预订动作时，只执行只读步骤：

- 泛化推荐：`recommendMeetingRooms --startTime <start> --endTime <end> [--attendeeCount N] [--buildingHint <building>] [--floorHint <floor>]`。
- 明确楼宇、楼层、设备、培训室等筛选：`skills-administrative room-booking-helper query`。
- 已知具体会议室名：先 `find-room --keyword <关键词> --raw` 确认信息，再用 `query` 校验目标时段。

常用精确查询形态：

```bash
skills-administrative room-booking-helper find-room --keyword "<会议室关键词>" --raw

skills-administrative room-booking-helper query \
  --city "<城市>" \
  --building "<楼宇>" \
  --date "2026-04-07" \
  --start "10:00" \
  --end "11:00" \
  --capacity 10 \
  --equips Zoom
```

建筑、城市、楼层、人数和设备都是可选偏好；用户没提就不要逐项追问，只有条件无法执行、结果过多或用户要求精确筛选时再补必要项。

只展示会议室名称、日期时间、楼层、容量、设备、地图等用户关心的信息，不调用 `createSchedule`、`updateSchedule` 或 `room-booking-helper book`。推荐结果中的 `roomId` 只有在用户随后明确要创建或添加会议室时才能用于写接口。

查询为空时直接说明当前条件无可用会议室，不自动换时间。可以询问是否调整条件，或是否创建 `room-booking-helper monitor` 候补监测；`monitor` 是新副作用，必须明确复述监测条件并取得用户同意后才能执行。执行前先用当前 `room-booking-helper monitor --help` 核对参数，不根据查询命令猜测监测参数。

## 创建会议室日程

- 先在目标时段确认会议室可用并取得唯一真实 `roomId`，再使用 `createSchedule --roomId`；标题、参与人和完整时间按 [SKILL.md](../SKILL.md) 的普通创建规则补齐。
- 用户只给会议室名称或筛选条件时，先推荐或精确查询目标时间段，拿到真实可用 `roomId`。具体会议室名先 `find-room`，再 `query` 校验空闲。
- 预订场景只额外传 `--roomId`，默认不传 `--location`。
- 查询为空时不调用写接口，不自动改时间；候选多条且无法唯一匹配时先让用户选择。
- 用户只有“钉会议室”意图但缺少开始时间、目标对象或会议室条件时补齐必要信息；查询意图不能自动升级成预订意图。
- 用户要求避开参与人冲突时，可在会议室查询前读取 [meeting-time-and-timezone.md](meeting-time-and-timezone.md)；会议室自身空闲仍以会议室查询和后端写结果为准。

## 编辑分流

普通标题、备注、参与人或普通地点编辑不进入会议室分支。只有以下意图进入会议室编辑：

- 给普通日程添加会议室。
- 把已有会议室日程换到另一个会议室。
- 修改已有会议室日程的会议室占用时间。
- 移除会议室但保留日程。

所有会议室编辑前：

1. 没有 `scheduleId` 时先搜索候选，候选不唯一时让用户选择。
2. 对唯一目标调用 `querySchedule --raw`。
3. 用 `detail.roomDetail != null` 判断类型：`null` 是普通日程，非空是会议室日程。

操作矩阵：

| 场景 | 前置 | 命令参数 |
| --- | --- | --- |
| 普通日程添加会议室 | `roomDetail == null`；查询目标时段并取得 `roomId` | `updateSchedule --meetingRoomOperateType 1 --roomId <id>` |
| 会议室日程换房 | `roomDetail != null`；新会议室目标时段可用 | `updateSchedule --meetingRoomOperateType 2 --roomId <newRoomId>` |
| 会议室日程只改占用时间 | `roomDetail != null`；新增占用区间全部确认空闲 | `updateSchedule --startTime <newStart> --endTime <newEnd> --meetingRoomOperateType 2`，不传 `roomId` |
| 移除会议室保留日程 | `roomDetail != null` | `updateSchedule --meetingRoomOperateType 3`，不传 `roomId` |

普通日程不能执行换房、只改会议室占用时间或移除会议室；直接说明当前日程没有绑定会议室。

## 已订会议室改时间

先从 `querySchedule --raw` 读取 `oldStart`、`oldEnd` 和当前会议室，按 [schedule-flow.md](schedule-flow.md) 计算完整 `newStart/newEnd` 并验证 `newStart < newEnd`。

只检查“新占用减去旧占用”的非空区间：

- 左侧新增段：`[newStart, min(newEnd, oldStart))`，仅当 `newStart < oldStart`。
- 右侧新增段：`[max(newStart, oldEnd), newEnd)`，仅当 `newEnd > oldEnd`。

新区间完全位于旧区间内时没有新增占用，可直接更新。否则逐段确认当前同一会议室空闲，所有新增段都可用才能写入。

查询新增段时必须使用 `detail.roomDetail` 中能唯一识别当前会议室的真实字段。若无法确认查询结果是同一会议室、无法排除其他占用，或任一新增段不可用，停止写入并说明具体冲突或无法确认的区间。

## 释放、转让、移除与删除

“取消会议室”必须先区分：

- 取消整个会议室日程：`deleteSchedule --scheduleId <id>`。
- 提前释放会议室：`releaseMeetingRoom --scheduleId <id> [--memo <说明>]`。
- 仅移除会议室但保留日程：`updateSchedule --meetingRoomOperateType 3`。
- 转让会议室：`transferMeetingRoom --scheduleId <id> --receiver <misOrEmpId> [--memo <说明>] --raw`。

释放或转让前必须目标唯一，并 `querySchedule --raw` 确认 `roomDetail != null`。普通日程不能调用释放/转让接口。

转让的结构化结果只在 `status.code == 0` 且 `handoverEventId` 是非空字符串时有效。此时把内部当前 `scheduleId` 原子替换为该 ID，旧 ID 立即失效。业务失败或成功响应缺少 ID 时停止；不能继续使用旧 ID或猜测新 ID。面向用户只说明接收人，不展示内部 ID。

## 会议室合并

先调用只读 `queryMergeCandidates --scheduleId <id>`。从真实候选中读取 `roomEventId`；不能构造它，也不能把 `roomId` 当作 `roomEventId`。

组织者候选要求：来源会议室日程和目标普通日程均由当前用户创建，时间完全相同；来源有会议室、目标没有会议室；两条日程都只保留创建人、没有其他参与人。对外说明该前置条件时保留“时间完全相同、只保留创建人、没有其他参与人”三项语义。

发现其他参与人时说明不满足条件。内部阻断记录使用固定句：`不得静默调用 updateSchedule --removeAttendees`；面向用户只说明不能为了制造候选自动或静默移除参与人，不展示内部命令。只有用户明确要求移除并确认影响后，才进入普通编辑流程。

- 候选为空：说明没有可合并候选，不继续写入。
- 候选多条：展示会议室名称、时间、位置等，让用户选择。
- 用户只说“看看能不能合并”：只查询候选。
- 候选唯一且用户明确合并：组织者用 `mergeMeetingRoom --scheduleId <id> --roomEventId <id>`；参与人用 `mergeMeetingRoomByAttendee ...`。
- 身份无法判断时确认是组织者合并还是参与人合并，不能猜。

## 输出与验证

- 推荐、精确查询和候选查询都是只读，不声称已经预订或占用。
- 会议室写入失败透传业务原因；认证、网络或超时失败按结果未知处理，禁止自动重放。
- 更新、释放、转让或合并后按唯一 ID 回读可验证状态；未回读时不要声称结果已验证。
- 默认隐藏 `roomId`、`roomEventId`、`handoverEventId`。释放成功回复“会议室释放成功”；转让成功回复“会议室转让成功，已转让给：<receiver>”。
