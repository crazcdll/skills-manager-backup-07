---
name: component-crash-chart
version: "2.1.0"
description: >
  生成组件 Crash / ANR 趋势图（折线图 + 柱状图），自动查询 Perf MCP 数据并附带分析结论。支持小时级、N天趋势、多版本对比、小时级同比四种模式；覆盖美团/点评/外卖，Android/iOS/HarmonyOS。
  触发词：组件crash图、babel crash图、dsp crash图、pike crash图、logan crash图、raptor crash图、sniffer crash图、horn crash图、SAKHorn crash、iOS crash、Android crash、鸿蒙crash、HarmonyOS crash、点评crash、DP crash、外卖crash、crash折线图、crash小时级、7天crash、15天crash、30天crash、crash趋势、多版本对比、版本crash对比、发版时间线、同比、环比、修复效果观测、N天同比。
  ANR触发词：anr图、ANR图、raptor anr图、anr趋势、ANR趋势、anr小时级、anr折线图。

metadata:
  skillhub.creator: "nieyunlong"
  skillhub.updater: "nieyunlong"
  skillhub.version: "V10"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "5381"
---

# 通用多平台组件 Crash / ANR 趋势图

## 🔧 前置依赖

本 skill 使用 `raptorfe` CLI（内置鉴权，无需 mcporter，无需 token 申请）。

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

**错误处理：**
- raptorfe 未找到 → `npm install -g @mtfe/raptorfe-cli --registry https://r.npm.sankuai.com/`
- S3 上传失败 → 回复图片本地路径，提示用户手动下载

---

## 📢 用户话术速查（直接这样说就行）

### 小时级（当天）
```
dsp crash 图
鸿蒙 pike crash 图
Android babel crash 小时图
iOS horn crash 图
点评 android dsp crash 图
点评鸿蒙 pike crash 图
外卖鸿蒙 crash 图
外卖 android babel crash 图
外卖 iOS horn crash 图
```

### N天趋势（带发版时间线）
```
pike crash 7天图
鸿蒙 pike crash 15天图
pike crash 30天图
android dsp crash 7天图
```

### 多版本对比
```
pike crash 版本对比 auto              ← 自动 top5 版本
pike crash 版本对比 12.53.402,12.53.202
android dsp crash 版本对比 auto
```

### 分钟级（排查短时突刺）
```
鸿蒙 pike crash 分钟图
android dsp crash 分钟图
```

### 小时级同比（观测修复效果）
```
pike crash 同比昨天
鸿蒙 pike crash 4天同比              ← 今天 + 前3天叠加
android babel crash 3天同比
pike crash 同比 2026-03-10,2026-03-11    ← 指定对比日期
```

### 修复效果自动观测（定时推送）
```
上线了，帮我盯 android babel crash，2小时后推结果
帮我 N 小时后推一次 android babel crash 修复效果
```
→ Agent 创建 cron，N 小时后自动生成图 + 推送大象

> **平台规则：**
> - 不说平台默认**美团**
> - 说「点评」或「DP」→ 切换点评
> - 说「外卖」→ 切换外卖（project: meituanwaimai / waimai_ios / waimai-harmony）
> - Android/iOS/鸿蒙需要指明，默认 Android

---

## ⚙️ Agent 执行指引

### 第一步：识别用户意图 → 选模式

| 用户说 | 模式 | 关键参数 |
|---|---|---|
| `xxx crash 图` / `xxx crash 小时图` | **小时级**（默认） | 无额外参数（自动带昨天对比线） |
| `xxx crash 分钟图` / `xxx crash 分钟级` | **分钟级** | `--minute` |
| `xxx crash N天图` / `7天趋势` | **N天趋势** | `--range Nd` |
| `xxx crash 版本对比` / `版本对比 auto` | **多版本对比** | `--versions auto` 或 `--versions v1,v2` |
| `xxx crash 同比` / `N天同比` / `修复效果观测` | **小时级同比** | `--compare-days (N-1)` |
| `N小时后推结果` / `定时盯着 crash` | **修复效果定时推送** | 创建 cron + `watch.py --notify <misid>` |

> ⚠️ **同比天数换算**："4天同比" = 今天 + 前3天 → `--compare-days 3`（N天同比 → compare-days = N-1）
> ⚠️ **小时图默认行为**：小时图自动带昨天对比线，无需额外说「同比」。若想指定多天，用「N天同比」。

### 第二步：识别平台 → 选 group

**默认美团**，说"点评"/"DP"切换点评。

| 用户说 | group 值 |
|---|---|
| dsp / DSP | `android:dsp` |
| babel | `android:babel` |
| raptor / basemonitor | `android:raptor` |
| pike（Android） | `android:pike` |
| logan | `android:logan` |
| horn（Android） / horn全系列 | `android:horn` |
| sniffer | `android:sniffer` |
| iOS horn / SAKHorn | `ios:horn` |
| **鸿蒙 pike** / HarmonyOS pike | `harmony:pike` |
| 鸿蒙 horn | `harmony:horn` |
| 点评 + android + 上述任意 | `dp-android:xxx` |
| 点评 iOS horn | `dp-ios:horn` |
| 点评鸿蒙 pike | `dp-harmony:pike` |
| 点评鸿蒙 horn | `dp-harmony:horn` |
| 外卖 android babel | `wm-android:babel` |
| 外卖 iOS horn / SAKHorn | `wm-ios:horn` |
| 外卖鸿蒙 crash / core | `wm-harmony:core` |
| 外卖鸿蒙 pike | `wm-harmony:pike` |

### 第三步：提取日期

- 用户指定日期 → 用指定日期
- 未指定 → 用今天（`date` 命令获取当前日期）

### 第四步：执行命令

```bash
cd /root/.openclaw/skills/component-crash-chart

# 模式1：小时级（默认自动带昨天对比线，无需额外参数）
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group>

# 模式2：N天趋势（自动附带发版时间线）
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --range Nd

# 模式3：多版本对比
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --versions auto
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --versions 12.53.402,12.53.202

# 模式4：小时级同比（N天同比 → compare-days=N-1）
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --compare-days <N-1>
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --compare yesterday
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --compare 2026-03-10,2026-03-11

# 模式6：ANR 图（--type anr，其余参数与 crash 完全相同）
python3 scripts/generate_chart.py --date YYYY-MM-DD --group android:raptor --type anr
python3 scripts/generate_chart.py --date YYYY-MM-DD --group android:raptor --type anr --range 7d
# 注意：当天数据不完整时自动用昨日同时段做环比，而非全天对比

# 模式5：修复效果定时推送（--notify 自动上传S3+推大象）
# 手动触发（立即生成并推送）：
python3 scripts/generate_chart.py --date YYYY-MM-DD --group <group> --compare yesterday --notify <misid>
# cron 用入口（自动取今天日期）：
python3 scripts/watch.py --group <group> --notify <misid>
python3 scripts/watch.py --group <group> --notify <misid> --compare-days 3
```

**修复效果定时推送流程（用户说"N小时后推结果"）：**
1. Agent 用 `daxiang-scheduled-message` skill 创建定时任务
2. 定时任务内容：`cd <SKILL_DIR> && python3 scripts/watch.py --group <group> --notify <misid>（<SKILL_DIR> 替换为 skill 实际安装路径）`
3. N小时后自动执行：出图 → 上传S3 → 推送大象

### 第五步：上传 S3 + 单条消息回复（严格执行，不得拆分）

```bash
cd /mnt/openclaw/.openclaw/skills/s3plus-upload
python3 scripts/upload_to_s3plus.py --file <输出png路径> --env prod-corp --object-name <文件名>
```

> ⚠️ **强制规则（违反即错）：**
> - **禁止** 用 `media=<file>` 单独发图片消息
> - **禁止** 先发图、再发分析（两条消息）
> - **必须** 将 S3 URL 以 `![Crash 图](url)` 嵌入分析文字，**用 message tool 发一条纯文字消息**
> - 大象渲染 markdown 图片链接，效果等同于图片消息，且分析文字不会丢失

**⚠️ 每张图必须附带以下分析，缺一不可：**

| 分析项 | 说明 |
|---|---|
| **概况** | 今天 Total、对比昨天（或对比日）涨跌数量和百分比（↑/↓），并给出明确结论：**环比改善 / 环比恶化 / 基本持平**（±5% 内为持平） |
| **波动情况** | 峰值时间点 + 峰值数量；是否有集中突刺 or 分散持续；有无异常时段 |
| **建议** | 根据数据给出 1-3 条具体建议（继续观察 / 排查特定版本 / 排查特定时段 / 结合版本图等） |

**回复模板（大象单条消息，图片嵌入分析文字中）：**

> ⚠️ **大象不支持图片+文字合并发送**。正确做法：
> 1. 先上传图片到 S3，拿到 URL
> 2. 将 S3 URL 以 `![图片](url)` 格式嵌入文字消息，**一条消息**发出去
> 3. 禁止用 `media=` 单独发图，否则分析文字不会显示

```
{组件} Crash {模式}（{日期}）

![Crash 图](https://s3plus-bj02.vip.sankuai.com/supabase-bucket/{文件名}.png)

**概况：**
- 今天 Total：{n}，昨天：{m}，{↑/↓} {diff}（{pct}%）→ **环比{改善/恶化/持平}**
- [N天图额外写：均值 {x}/天，最高 {max}（{日期}），最低 {min}（{日期}）]

**波动情况：**
- 峰值：{时间} = {count} 次；{描述突刺/分散情况}
- {其他异常描述，如无则写"整体平稳"}

**建议：**
1. ...
2. ...
```

---

## 完整预设组件组

完整的 group 映射、包含组件、话术示例见 [references/presets.md](references/presets.md)。

## 输出说明

| 模式 | 输出内容 |
|---|---|
| 小时级 | 折线图 + 柱状图（含均线），标注每小时数值，**默认自动叠加昨天对比线** |
| 分钟级 | 折线图 + 柱状图，x轴每分钟一个点，每30分钟标一次时间，适合排查短时突刺 |
| N天趋势 | 日级折线 + 柱状 + 发版时间线虚线（top5版本首现日） |
| 多版本对比 | 多版本折线叠加 + 堆叠柱状 + 版本首现时间竖线 |
| 小时级同比 | 今日实线 + 前N天虚线参考，颜色区分每天 |

多组件时额外输出分组件折线+合计折线。所有图表标注 Total。

## ⚠️ 发送消息强制要求

**每次生成图表后，必须将图片 + 分析结论一起发送给用户，缺一不可。**

脚本 stdout 中 `=== 分析结论 ===` 段落的内容就是分析结论，必须原文（或适当精简后）随图一起发送，不能只发图片或只发数字摘要。

```
# 正确格式示例：
图片（Markdown 图片链接）
+ 分析结论文本（概况、时段分布、结论）
```

违反此要求 = 执行不完整。

## 扩展

- 列出全部预设：`python3 scripts/generate_chart.py --date today --list`
- 添加新组件：编辑 `scripts/generate_chart.py` 中 `PRESET_GROUPS`

