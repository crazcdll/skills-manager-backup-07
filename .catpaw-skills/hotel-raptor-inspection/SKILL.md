---
name: hotel-raptor-inspection
description: 酒店交易前端异常日报生成工具。自动拉取 Raptor 前端监控数据，生成包含环比分析、近一周首现异常、持续异常、暴涨异常、ERROR 堆栈分析、异常类型统计的 HTML 报告，所有异常名称可点击跳转 Raptor 详情页。当用户需要生成前端异常日报、查看异常环比变化、排查首现异常、生成 Raptor 异常报告时使用。触发词：异常日报、前端异常报告、生成报告、Raptor 日报、异常分析报告。

metadata:
  skillhub.creator: "lidingcheng"
  skillhub.updater: "lidingcheng"
  skillhub.version: "V4"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "5502"
---

# 酒店前端异常日报生成器

> **版本**：20260325 · 更新脚本时同步修改 `gen_error_report.py` 顶部的 `SKILL_VERSION`

---

## 快速开始

```bash
# 生成当前时间的报告（滚动 24h 窗口）
python3 scripts/gen_error_report.py <projectName>

# 指定基准时间（适合定时任务，每日固定时间出报告）
python3 scripts/gen_error_report.py <projectName> 2026-03-16T10:00:00
```

输出：`error_report_<project>_<YYYYMMDD_HHMM>.html`，保存在脚本同目录。

**首次使用前**：需配置 Raptor Cookie，详见 [references/setup.md](references/setup.md)。

---

## 报告内容

| 模块 | 说明 |
|------|------|
| 概览卡片 | 总异常次数（含环比）、影响用户数（含环比）、异常类型分布（JS/AJAX 数量） |
| 最近一周首现异常 | Raptor 官方标记的「较上周同期首现」异常，分页拉取全量后合并各页 newErrors |
| 环比暴涨异常 | 环比增幅 >100% 且次数超动态阈值的异常，按环比降序 Top 10 |
| 持续异常 | 两窗口均出现、次数超动态阈值的高频异常，按次数降序 Top 10 |
| ERROR 级别 JS 异常分析 | ERROR 级别异常的规则推断（风险等级、影响范围、处理建议） |
| AJAX 接口异常聚合 | 按接口路径聚合的 API 错误统计 |
| 完整异常列表 | 全量异常，支持按类型/级别/首现筛选，每页 100 条分页，点击跳转 Raptor 详情页 |

### 动态阈值说明

持续异常和暴涨异常的过滤阈值根据项目体量自动计算，避免固定值在不同项目间失效：

- **持续异常阈值** = `max(10次, 当前窗口总量 × 0.5%)`
- **暴涨异常阈值** = `max(5次, 当前窗口总量 × 0.1%)`

报告标题会实时显示本次实际使用的阈值，透明可追溯。

---

## 工作流程

### 1. 确认项目名

Raptor 项目名格式如 `rn_hotel_hotelchannel-orderfill-duo`，可从 Raptor 页面 URL 或项目列表获取。projectId 由脚本自动查询，无需手动填写。

### 2. 确认 Cookie 有效

```bash
cat /path/to/workspace/.raptor_cookie | head -c 50
```

若文件不存在或 Cookie 过期，参考 [references/setup.md](references/setup.md) 重新获取。

### 3. 运行脚本

```bash
python3 /path/to/skill/scripts/gen_error_report.py rn_hotel_hotelchannel-orderfill-duo
```

正常输出示例：

```
项目：rn_hotel_hotelchannel-orderfill-duo
当前窗口：2026-03-17 10:00:00 ~ 2026-03-18 10:00:00
对比窗口：2026-03-16 10:00:00 ~ 2026-03-17 10:00:00

  projectId=37345 (酒店新填单页)
[1/4] Raptor Web API：拉取当前窗口数据（含 TAG 过滤 + 官方首现）...
  当前窗口: 221 条（已过滤忽略 TAG），官方首现: 23 条
[2/4] 拉取对比窗口数据...
  对比窗口: 222 条
[3/4] 聚合汇总数据...
[3.5/4] 拉取 ERROR 级别堆栈（top 3）...
  获取到堆栈: 0 条
[4/4] 数据处理 & 生成报告...
  首现: （官方，23条）  高危: 10  暴涨: 9

✅ 报告已生成：error_report_rn_hotel_hotelchannel-orderfill-duo_20260318_1052.html
   数据模式：✓ Raptor Web API（官方 TAG + 官方首现）
```

> **注意**：堆栈拉取（`/cat/fe/log/list`）目前返回 404，获取到 0 条为正常现象，不影响报告其他内容。

### 4. 查看报告

用浏览器打开生成的 HTML 文件，或通过 `browser_action` 工具预览：

```
browser_action: navigate to file:///path/to/error_report_xxx.html
```

---

## 跳转链接格式

报告中每条异常名称均可点击，跳转到 Raptor 对应时间窗口的异常详情页：

```
https://raptor.mws.sankuai.com/frontend/error/detail
  ?type=datetimerange
  &start=YYYYMMDDHHmmss
  &end=YYYYMMDDHHmmss
  &projectId=<动态>
  &webVersion=all
  &projectName=<动态>
  &keyword=<url_encoded_name>
  &errorListCurrentPage=1
  &errorName=<url_encoded_name>
  &errorDetailCurrentPage=1
  &errorDetailCurrentPageSize=50
```

---

## 常见问题

**Cookie 失效（HTTP 302 / 401）**：重新从浏览器获取 Cookie，更新 `.raptor_cookie` 文件，参考 [references/setup.md](references/setup.md)。

**Cookie 不可用时降级**：自动切换到 MCP 模式，无 TAG 过滤，首现数据不可用（不做推断）。

**持续异常/暴涨异常条数为 0**：项目体量较小时动态阈值会降到绝对下限（10次/5次），若仍为 0 说明确实无符合条件的异常。

**调整交易链路关键词**：修改脚本顶部 `CRITICAL_KEYWORDS` 列表。

**调整动态阈值参数**：修改脚本顶部 `PERSISTENT_RATIO`、`PERSISTENT_ABS_MIN`、`SURGE_RATIO`、`SURGE_ABS_MIN` 等常量。

**多项目批量生成**：循环调用脚本即可，每个项目独立输出一个 HTML 文件。

---

## Agent 维护规范

> 本 skill 由 Agent（CatClaw）自动维护，每次修改脚本后**必须**执行以下步骤：

1. **更新版本号**：将 `scripts/gen_error_report.py` 顶部的 `SKILL_VERSION` 改为当天日期，格式 `YYYYMMDD`，例如 `"20260318"`。
2. **同步 SKILL.md**：将本文件顶部「版本」备注中的日期同步更新。
3. **不得遗漏**：即使只是小改动（注释、阈值调整等），也需要 bump 版本日期，确保报告底部版本号与实际脚本一致。
