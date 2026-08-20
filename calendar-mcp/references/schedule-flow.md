# 日程高级操作与个人状态流程

本文件只处理关联群聊、编辑、取消、个人提醒、忙闲状态和参与反馈。普通创建、搜索和详情直接按 `SKILL.md` 的高频快速路径执行，不读取本文件。出现安装、兼容、认证或写结果未知时再读取 [runtime-and-safety.md](runtime-and-safety.md)；涉及循环、会议时间或会议室时读取对应 reference。

## 从快速路径升级

普通创建出现下列任一条件时停止快速路径并升级：

- 关联既有群会话：继续本文件的“关联群会话”。
- 循环意图：读取 [recurrence-pattern.md](recurrence-pattern.md)。
- 会议室意图：读取 [meeting-rooms.md](meeting-rooms.md)，不能用 `--location` 模拟预订。
- 用户要求避冲突、查询参与人是否有空或推荐时间：读取 [meeting-time-and-timezone.md](meeting-time-and-timezone.md)。

若已经执行冲突检查：无冲突时按原计划创建；有冲突时展示结果并让用户选择继续或调整，不能自行创建或改时间。用户原话已明确“即使冲突也创建”时可继续，但回复要说明检测到冲突。

## 关联群会话

- 仅新建日程支持 `--chatId <群会话ID> --chatType groupchat`，两个参数必须同传；操作人必须是目标群成员。
- 该能力只建立既有 `calendar_view` 关联，不发送分享卡片，不支持单聊，也不能分享已有日程。
- 用户显式要求“关联群/关联群聊”时，执行前提示“关联群是单向操作”，不要求二次确认。
- 用户在创建请求中直接指定当前群会话或提供 `chatId` 时，会话就是创建参数，不额外提示。

## 编辑普通日程

所有编辑先定位唯一日程并调用 `querySchedule --raw`。若详情表明是循环日程，立即按循环编辑禁止规则停止；若编辑涉及会议室资源，读取 [meeting-rooms.md](meeting-rooms.md)。

时间更新必须构造完整的新范围：

- “改到 15:00”或只给新开始时间：保持原时长，开始与结束一起平移。
- “推迟/提前 N 分钟”：开始和结束同时移动。
- “延长/缩短 N 分钟”：开始不变，只调整结束。
- 用户明确给出新开始和结束：使用用户值。
- 多人日程改期前使用 `analyzeParticipantBusyPeriod --currentScheduleId <id>` 排除自身；发现冲突后让用户选择继续或另选时间。

字段规则：

- `updateSchedule` 至少包含一个真实更新字段。
- `--location` / `--memo` 不传表示不更新；明确清空时使用 `--clearLocation` / `--clearMemo`，不要用空字符串。
- `updateSchedule` 不支持 `--attendees`；增加/移除参与人使用 `--addAttendees` / `--removeAttendees`。
- 普通编辑标题、备注、普通地点、参与人时，不传 `--roomId` 或 `--meetingRoomOperateType`。
- 已绑定会议室但只改标题、备注、参与人等不影响会议室占用的字段，仍走普通编辑；改时间、换房或移除会议室转入会议室流程。

## 取消与角色语义

用户没提供 ID 时先搜索并查询详情。目标唯一且动词与作用域明确时可直接执行：

- 组织者“取消整个日程/会议”：`deleteSchedule`。
- 当前参与人“我不参加/拒绝邀请/退出”：`updateAttendeeFeedback --feedbackStatus DECLINE`，不能删除整场。
- “取消这条提醒”：`saveMyReminder --mode NONE`，不能关闭全局提醒设置。
- “取消会议室”：必须按删除整个会议室日程、提前释放、仅移除会议室三种动作分流，见 [meeting-rooms.md](meeting-rooms.md)。
- “取消这个会”但无法从详情确定是删除整场还是仅拒绝参加时，只追问这一项，不能猜测破坏性操作。
- 循环日程必须区分当前实例与整个系列，见 [recurrence-pattern.md](recurrence-pattern.md)。

## 个人提醒

- 开关当前认证用户的个人提醒自定义设置：`updatePersonalReminderSetting --enabled true|false`。
- 设置当前用户单条提醒：`saveMyReminder --scheduleId <id> --mode CUSTOM --minutes "<一个或多个逗号分隔的正整数>"`，例如 `"15"` 或 `"15,60"`。
- 取消当前用户单条提醒：`saveMyReminder --scheduleId <id> --mode NONE`。
- 全局开关与单条提醒不能互相替代。设置单条提醒时不得静默修改全局开关；只有服务端明确返回全局开关未开启，才询问是否开启，用户同意后最多开启并重试一次。
- 用户未给提前分钟数时询问，不套用魔法值。每个正数表示开始前多少分钟，只使用用户明确给出的提醒点，不自行添加负数协议值。
- 当前只有写入能力；详情没有明确返回当前配置时，不能回答“当前提醒是什么”。成功后只说明当前用户提醒已更新，不说影响所有参会人。

## 当前用户忙闲状态

- 修改前先 `querySchedule`。默认输出中的“忙闲状态”是当前值，`canSetFreeBusyStatus` 决定是否可设置；明确不可设置时停止，未知时不声称已确认权限，以写接口实际结果为准。
- 只修改当前用户自己的状态用 `updateFreeBusyStatus --scheduleId <id> --freeBusyStatus BUSY|FREE`。
- 创建或编辑日程同时指定状态时，可在 `createSchedule/updateSchedule` 上加 `--freeBusyStatus BUSY|FREE`。
- 只改状态时优先 `updateFreeBusyStatus`，避免普通编辑副作用。它不修改全体参会人、反馈状态或日程内容。

## 参与人反馈

- “接受/确认参加”映射 `ACCEPT`，“暂定/可能参加”映射 `TENTATIVE`，“拒绝/不参加”映射 `DECLINE`。
- 使用 `updateAttendeeFeedback --scheduleId <id> --feedbackStatus <状态>`；只能修改当前认证用户，不能构造 `operator` 或替别人操作。
- 反馈与 `BUSY/FREE` 是独立能力，不能互相替代。
- 用户只问当前反馈或有哪些待响应日程时不要调用写接口。用户明确要反馈、目标唯一后才能执行；候选不唯一时先选择。
- 成功后只说明当前用户参与状态已更新，不声称替所有参与人操作或改变忙闲状态。
