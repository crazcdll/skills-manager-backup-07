# calendar-mcp Skill 优化方案

日期：2026-07-08

## 背景

当前应用链路为：

```text
skill -> oa-skills calendar-mcp CLI -> 办公开放平台 -> ScheduleOpenService
```

因此 skill 的职责不是直接理解或调用后端接口，而是把用户自然语言意图稳定地翻译成 CLI 命令。所有真实能力、认证、开放平台 path、响应拆包和人员 ID 转换都由 CLI 负责。

当前 `SKILL.md` 已覆盖大量日程和会议室规则，但随着 `ScheduleOpenService` 增加 AI 场景能力，继续把所有细节堆在入口文件里会降低可维护性。优化重点是：入口文件保持短而硬，复杂规则拆到 references；同时在新增 CLI 能力落地后，让 skill 能正确分流今日上下文、冲突分析、个人提醒和忙闲状态。

## 优化目标

1. 保持唯一执行入口：skill 只能调用 `oa-skills calendar-mcp ...`，不拼接 HTTP、SSE、Thrift 请求。
2. 入口文件只保留触发、硬约束、风险规则和常用命令索引。
3. 长规则拆分到 references，按场景渐进读取，降低误用概率。
4. 不把后端未返回的数据说成已支持；冲突用户信息的目标是由服务端接口层直接返回，未落地前只展示冲突人 MIS。
5. 写操作必须明确目标、确认副作用，并在可行时回读验证。

## 建议目录结构

```text
skills/calendar-mcp/
  SKILL.md
  references/
    core-flow.md
    schedule-open-capabilities.md
    meeting-room-flow.md
    safety-and-verification.md
```

| 文件 | 内容 |
| --- | --- |
| `SKILL.md` | frontmatter、触发词、唯一入口、CLI 可用性检查、最常用命令索引、必须停止的风险规则 |
| `references/core-flow.md` | 普通日程创建、查询、编辑、取消、搜索、忙闲的通用流程 |
| `references/schedule-open-capabilities.md` | 今日上下文、冲突分析、多人忙闲、个人提醒、用户忙闲状态等新增开放能力分流 |
| `references/meeting-room-flow.md` | 会议室推荐、精确查询、创建、添加、换房、释放、转让、合并 |
| `references/safety-and-verification.md` | 写操作确认、相对日期、回读验证、错误处理、`raw` 使用规范 |

拆分原则：
- `SKILL.md` 不超过高频决策所需长度。
- 每个 reference 只服务一个场景，不做跨文件重复。
- reference 中的命令必须和 CLI `--help`、测试和真实实现一致。
- 未落地 CLI 命令只能写在方案或待办中，不能写成当前可执行步骤。

## 触发和 frontmatter 调整

当 CLI 新能力落地后，frontmatter 的 description 建议补充这些意图：

```text
查看今天安排、判断日程冲突、检查谁冲突、
分析多人忙闲、创建前查冲突、设置日程为空闲/忙碌、
设置个人提醒、取消个人提醒
```

仍需保留：
- 创建、查询、编辑、取消日程。
- 搜索日程和查询忙闲。
- 会议室推荐、创建、编辑、释放、转让和合并。
- `room-booking-helper` 仅作为精确会议室查询、找具体会议室、候补监测和校验 `roomId` 的辅助。

## 能力分流

| 用户意图 | 首选 CLI 命令 | 说明 |
| --- | --- | --- |
| “今天有什么安排” | `searchSchedule` | `listTodaySchedule` 开放能力已移除，使用当前用户和当天窗口查询 |
| “看这个日程详情” | `querySchedule` | 用于详情、写前判断、回读验证 |
| “这条会谁冲突” | `getScheduleDetailConflicts` | 服务端扩展后直接返回冲突用户信息；未扩展时只返回冲突人 MIS |
| “这些人这段时间忙不忙” | `analyzeParticipantBusyPeriod` | 多人忙闲分析首选；编辑时传 `currentScheduleId` 排除自身 |
| “把这条日程设为空闲/忙碌” | `updateFreeBusyStatus` | 单独修改当前用户自己的忙闲，不走普通编辑 |
| “创建时设为空闲/忙碌” | `createSchedule --freeBusyStatus` | 仅影响组织者自己的忙闲 |
| “编辑时顺便改忙闲” | `updateSchedule --freeBusyStatus` | 非纯忙闲变更时使用 |
| “开始前 15 分钟提醒/不提醒” | `saveMyReminder --scheduleId` | 当前只有写入能力，不回答当前提醒配置 |
| “查候选会议室” | `recommendMeetingRooms` 或 `room-booking-helper query` | 推荐走 CLI，精确楼宇/设备查询用辅助 skill |
| “订会议室/给日程加会议室” | `createSchedule --roomId` 或 `updateSchedule --meetingRoomOperateType` | 必须先拿到明确可用 `roomId` |

## 新增开放能力的 skill 规则

### 今日上下文

用户问今天安排、接下来有什么会、今天是否有空时：
1. `listTodaySchedule` 对应的开放平台能力已移除，不得调用。
2. 使用 `searchSchedule` 查询当前用户当天窗口。
3. 输出只总结用户可见日程，不说成“对方全部日程”。

### 冲突分析

已有日程冲突：
1. 若用户没给 `scheduleId`，先 `searchSchedule` 找候选。
2. 候选唯一后调用 `getScheduleDetailConflicts`。
3. 服务端扩展后，优先使用响应里的冲突用户信息展示 `姓名(MIS)`。
4. 服务端未返回冲突用户信息时，只展示 `conflictMisList`，不要声称已经拿到用户名。
5. 参与人超过服务端限制时，透传“人数过多，无法分析”的业务结果，不继续拆分成多个请求伪造完整结论。

创建或编辑前冲突：
1. 用 `analyzeParticipantBusyPeriod` 查询参与人忙碌区间。
2. 编辑已有日程时必须传 `currentScheduleId`，避免把当前日程算成自身冲突。
3. 接口返回忙碌区间，不返回自动推荐空闲时间。若要推荐时间，skill 只能在结果基础上做上层计算，并清楚说明是推算。

### 个人提醒

用户要求设置或取消自己的提醒：
1. 必须有唯一 `scheduleId` 或 `eventId`；对用户统一称为日程 ID。
2. 优先调用 `saveMyReminder --scheduleId "<schedule-id-or-event-id>"`，不要要求用户理解 eventId 和 scheduleId 的区别。
3. `mode=CUSTOM` 时必须有提醒分钟数。
4. `mode=NONE` 表示不提醒。
5. 当前缺少独立读取当前个人提醒的开放接口，不能可靠回答“现在提醒是什么”。
6. 写入成功后只说明个人提醒已更新，不说影响所有参会人提醒。

### 忙闲状态

用户要求把某条日程设为空闲或忙碌：
1. 优先 `querySchedule` 确认目标唯一和 `canSetFreeBusyStatus`。
2. 若可设置，调用 `updateFreeBusyStatus --freeBusyStatus BUSY|FREE`。
3. 该操作只修改当前用户自己的忙闲，不修改反馈状态，不通知其他参与人。
4. 若用户在创建或编辑日程时同时指定忙闲，使用 `createSchedule --freeBusyStatus` 或 `updateSchedule --freeBusyStatus`。
5. 用户要求批量把多条日程设为空闲时，需要逐条执行并汇总结果；当前不设计批量写入口。

## 连续意图规则

CLI 调用之间没有隐式状态，skill 必须显式传参。

允许沿用上下文的场景：
- 用户说“先查 A/B 的忙闲，再给他们建会”，且 A/B 是当前对话唯一确认的参与人。
- 用户从搜索结果中明确选择某一条日程后，后续更新或删除可以沿用该 `scheduleId`。
- 用户要求“把刚才那条日程设为空闲”，且上一条日程结果唯一。

必须追问或重新查询的场景：
- 搜索候选多条，无法唯一确定目标。
- 人员只有姓名，没有 MIS，且上下文无法唯一确定 MIS。
- 会议室只有名称、楼宇或条件，没有明确可用 `roomId`。
- 用户要求写操作，但缺少时间、目标日程、接收人或提醒分钟数等必要信息。

## 安全和输出规范

写操作包括：
- 创建、编辑、取消日程。
- 设置忙闲状态。
- 设置或取消个人提醒。
- 创建、添加、替换、释放、转让、合并会议室。
- 创建会议室候补监测任务。

安全规则：
- 写操作前必须有唯一目标和完整必要参数。
- 删除、释放、转让、合并等高风险操作，候选不唯一时必须让用户确认。
- 相对日期必须先用本机 `date` 获取当前日期，再推算并校验星期。
- 默认输出中文摘要，不贴原始 JSON。
- 只有排障、验证字段或用户明确要求时使用 `--raw`。
- 业务失败必须透传原因，不把开放平台失败说成操作成功。

## 与 CLI 的同步要求

每次新增或修改 CLI 能力时，skill 必须同步检查：
- `SKILL.md` 的 description 是否覆盖新增触发词。
- reference 中的命令是否和 CLI `--help` 完全一致。
- 参数名是否仍是 CLI 对外参数，而不是后端 request 字段。
- 默认输出是否符合 skill 摘要规则。
- `--raw` 示例是否只用于排障和字段确认。
- 不存在把未实现 CLI 命令写成当前可用命令的描述。

建议维护顺序：
1. CLI 类型、client、handler、help、测试先落地。
2. 本 skill 再把“待落地”能力改成“可执行流程”。
3. 跑 `oa-skills calendar-mcp --help` 对齐命令文本。
4. 执行 skill package 校验，确认没有多余隐藏文件或未引用资源。

## 不纳入范围

- 不引入高风险运维类写能力。
- 不把 `room-booking-helper book` 作为默认会议室写入口。
- 不实现“姓名 -> MIS”自动识别。
- 在服务端 `conflictUsers` 等字段落地前，不声称冲突接口原生返回用户名。
- 不声称可以读取当前个人提醒配置，除非后端开放读取能力或详情字段明确提供。
- 不绕过 `oa-skills calendar-mcp` 直接访问办公开放平台或后端服务。
