---
name: room-booking-helper
description: "美团会议室预订助手。支持：查询空闲会议室（按建筑/楼层/容量/设备筛选）、按 room-id预订会议室（含参会人）、创建候补监测任务（query无结果时）、按关键词搜索会议室信息。取消会议室时，提示用户通过大象日历 Skill（calendar-mcp）操作，未安装时引导至安装页面。触发词：订会议室、预约会议室、查会议室、搜会议室、找会议室、帮我订个会议室、安排会议地点、有没有空会议室、哪个会议室有空、有电视机的会议室、有Zoom的会议室、取消会议室。不用于：修改/转让预订、查看预订记录、发会议邀请、日历编辑、周期性预订（每天/每周）、跨天预订。"

metadata:
  skillhub.creator: "wangjun137"
  skillhub.updater: "wangjun137"
  skillhub.version: "V8"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "2577"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

如遇 skill 问题，提 [TT](https://tt.sankuai.com/public/create?cid=17&tid=1615&iid=47000) 反馈。

# 美团会议室预订助手

## 前置步骤

每次处理请求前执行，避免相对日期推算错误：

```bash
date "+今天是 %Y年%m月%d日，星期%u，当前时间 %H:%M"
```

- **相对日期**（明天/这周六/下周五）：先用 `date` 确认今天星期数，再推算目标日期，**验证推算日期的 `%u` 值与目标星期一致**才能使用
- **未指定时间**：取下一个整点或半点，时长默认 1 小时（如 7:40 → 8:00-9:00）
- **日期窗口**：普通会议室 ≤ 8 天，培训会议室 ≤ 30 天；超出范围先提示再拒绝


## 前置检查：确保 CLI 最新

**重要！！！ 每次 skill 激活时执行以下命令，对比cli本地版本与远端最新正式版本，仅在不一致时升级，否则新命令可能不存在，导致运行失败**

```bash
LOCAL=$(npm list -g @cap/skills-administrative --depth=0 2>/dev/null | grep '@cap/skills-administrative' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*'); \
REMOTE=$(npm view @cap/skills-administrative dist-tags.latest --registry=http://r.npm.sankuai.com 2>/dev/null); \
if [ "$LOCAL" != "$REMOTE" ]; then \
  echo "版本不一致（本地: ${LOCAL:-未安装}, 远端: $REMOTE），开始升级..."; \
  npm install -g @cap/skills-administrative@latest --registry=http://r.npm.sankuai.com; \
else \
  echo "已是最新版本 $REMOTE，无需升级。"; \
fi
```

---

## 核心限制

| 限制 | 说明 |
|---|---|
| 预订窗口 | 普通会议室 8 天，培训会议室 30 天 |
| 单次时长 | 普通会议室 5 分钟～4 小时，培训会议室无上限 |
| 时间精度 | 5 分钟倍数，自动对齐 |
| 并发上限 | 同账号同一时刻最多 2 间，每天每间最多 3 次 |
| 不支持 | 跨天预订、历史时间预订、周期性预订 |
| 禁止轮询抢订 | 会触发限流并拉入黑名单 |
| **预订流程** | **`book` 有不可逆副作用，只执行一次。意图为"帮我查"时只展示列表不预订；意图为"帮我订"时先 `query`，有用户偏好（容量/设备/楼层）则选最匹配的，否则取第一个，直接调用 `book --room-id` 无需再次确认** |
| **监测任务** | **`monitor` 用于 query 无结果时。时长须 15-120 分钟，相同大厦+时段不可重复创建** |

---

## 五种用法

### 1. 查询空闲会议室

```bash
skills-administrative room-booking-helper query \
  [--city <城市>] --building <建筑> \
  --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> \
  [--capacity <人数>] [--floors <楼层>...] [--equips <条件>...] [--training]
```

- `--city` 省略时跨所有城市搜索，建筑名有歧义时填写
- `--equips` 模糊匹配，支持：`Zoom`、`仅投屏`、`电视机`、`投影仪`、`触屏一体机`、`自然采光`、`自控空调`、`可开窗户`、`书写板`
- `--training`：培训会议室标记，解除 4 小时时长上限

```bash
skills-administrative room-booking-helper query \
  --building 互联D2 --date 2026-04-10 --start 12:00 --end 13:00

skills-administrative room-booking-helper query \
  --city 北京 --building 恒电 --date 2026-04-10 --start 10:00 --end 11:00 \
  --capacity 10 --equips Zoom 可开窗户
```

**无结果时**：询问用户是否创建监测任务，不要自作主张换时间段。

---

### 2. 预订会议室

```bash
skills-administrative room-booking-helper book \
  --room-id <ID> --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> \
  [--attendees <mis>...] [--title <标题>] [--training]
```

- `--room-id`：来自 `query` 结果的 `id` 字段
- `--title`：日程标题（可选，默认为 `"<mis>的会议"`，培训室为 `"<mis>的培训"`）
- `--training`：培训会议室标记，解除 4 小时时长上限

```bash
skills-administrative room-booking-helper book \
  --room-id 11486 --date 2026-04-10 --start 12:00 --end 13:00 --attendees zhangsan lisi
```

成功判断：退出码 0 且输出含"✅ 预订成功"。展示会议室名称、日期时间、楼层、容量、设备、功能、配套设施、地图，不展示 scheduleId。

---

### 3. 创建候补监测任务

```bash
skills-administrative room-booking-helper monitor \
  --building <建筑> \
  --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> \
  [--min-capacity <人数>] [--floors <楼层>...] [--equips <设备>...]
```

时长须 15-120 分钟；`--equips` 仅支持：`Zoom`、`无线投屏`、`投影`/`投影仪`、`电视`/`电视机`。

---

### 4. 按关键词搜索会议室

```bash
skills-administrative room-booking-helper find-room --keyword <关键词> [--raw]
```

适用于已知具体会议室名称（如"青田厅"）。建筑名查询用 `query --building`。

---

### 5. 取消会议室

本 skill 不直接处理取消逻辑，通过 **`calendar-mcp` Skill** 完成。

**未安装时**，前往 Friday 平台安装（skill id: 11092）：
https://friday.sankuai.com/skills/skill-detail?activeTab=overview&activeTestTab=cases&from=/skills-market?keyword=%25E6%2597%25A5%25E5%258E%2586%26page=1&id=11092

#### 步骤一：搜索日程定位 scheduleId

按以下优先级逐步尝试，找到后即止：

**优先：精确时间 + 标题同时匹配**（上下文中有预订时间时，标题默认为 `"<mis>的会议"`）

```bash
oa-skills calendar-mcp searchSchedule \
  --attendees "<用户mis>" \
  --title "<mis>的会议" \
  --startTime "<预订日期> <开始时间>" \
  --endTime "<预订日期> <结束时间>" \
  --force-ciba --raw
```

**兜底：全天范围搜索**（第一步查不到时）

```bash
oa-skills calendar-mcp searchSchedule \
  --attendees "<用户mis>" \
  --startTime "<预订日期> 00:00" \
  --endTime "<预订日期> 23:59:59" \
  --force-ciba --raw
```

**匹配逻辑**：从结果中找 `conference` 字段包含目标会议室名称的条目（如 `"北京/恒电大厦B座-2层 - 厦门厅"`）。

#### 步骤二：删除日程

```bash
oa-skills calendar-mcp deleteSchedule \
  --scheduleId "<步骤一匹配到的 eventId>"
```

---

## 认证

CLI 自动处理：CatPaw Desk → CIBA（首次需大象 App 确认）→ 缓存 cookie。

```bash
skills-administrative room-booking-helper --clear-cache   # 清除缓存重新认证
skills-administrative room-booking-helper book --force-ciba ...  # 强制 CIBA
```

---

## 故障排除

| 错误 | 解决 |
|---|---|
| `401` / `未登录` | `--clear-cache` 后重试，或加 `--force-ciba` |
| `未找到城市/建筑` | 换更具体名称；南京等归属大区，调整 `--city` 为大区名 |
| `过去时间不可预订` | 先跑 `date` 确认当前日期 |
| `日期超出预订窗口` | 普通 ≤ 8 天，培训 ≤ 30 天；超出改更近日期或加 `--training` |

完整踩坑见 [references/faq.md](references/faq.md)
