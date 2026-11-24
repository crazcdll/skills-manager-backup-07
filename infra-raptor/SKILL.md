---
name: infra-raptor
display_name: Raptor大前端Skill合集
description: 'Raptor大前端技能合集，支持：①自然语言查询大前端指标（Crash/ANR率、RCF分数、性能指标、移动端/Web/小程序自定义指标等）；②Crash/ANR/FOOM告警深度分析（多维度分布、DAU偏差、5条以上堆栈深度分析、根因推断）；③大前端性能告警自动分析（多维下钻、趋势对比图）；④Crash组件趋势图（小时级/N天/多版本/同比）；⑤自定义监控大盘创建（自然语言描述指标或粘贴Raptor链接，自动完成大盘/Tab/图表配置；支持 0-7 全部图表类型、参考线、环比、维度对比、灰度大盘配置、跨Tab复制，以及老Raptor大盘一键导入）；⑥RCF指标波动分析（R/C/F子指标贡献度计算、多维度下钻、根因定位）；⑦自定义大盘巡检（发送大盘链接自动读取所有图表、批量查询最近7天数据、异常检测、生成数据报告、异常指标多维下钻）；⑧按uuid（deviceId）查异常日志（输入设备uuid+排查诉求，检索该设备最近7天的崩溃/ANR/异常退出/捕获异常/卡顿/业务JS异常并按时间线汇总成报告，注意区别于uuid↔userid等ID互转/万能钥匙能力）。覆盖美团/外卖/点评，Android/iOS/HarmonyOS。直接转发任意告警消息即可自动分析。支持境内与境外双环境：用户提到海外/境外环境，或使用 raptor.mws.keetapp.com 域名时，自动将 CLI 命令字切换为 raptorfeov。触发词：导入旧大盘、老大盘导入、迁移老大盘、灰度大盘配置、灰度配置、复制Tab配置、图表参考线、环比配置。'
tags: 终端基础技术,Raptor,大前端,Crash,性能指标,告警,前端开发,境外
version: 0.11.0
created: 2026-03-27
updated: 2026-11-20

metadata:
  skillhub.creator: "xuzhen"
  skillhub.updater: "huangwenqing05"
  skillhub.version: "V51"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "18310"
  skillhub.high_sensitive: "false"
---

# Raptor 大前端监控

## Goal

Raptor 大前端监控域的统一入口，根据用户意图路由到对应子能力。

## 环境识别：境内 / 境外（必读）

Raptor 提供境内、境外两套访问入口，**接口、子命令与参数完全一致，只有 CLI 命令字与页面域名不同**。每次任务开始前先判定环境，判定结果在本次会话内保持，不得中途混用。

| 环境 | CLI 命令字 | 页面域名 | 说明 |
|---|---|---|---|
| 境内（默认） | `raptorfe` | `raptor.mws.sankuai.com`（Perf 页面 `perf.sankuai.com`） | 未命中境外条件时一律使用 |
| 境外（Overseas） | `raptorfeov` | `raptor.mws.keetapp.com`（如 `https://raptor.mws.keetapp.com/home`；Perf 接口同在该域名下） | 海外 / 境外网络访问入口 |

### 判定为境外的条件（命中任一即切境外）

1. 用户明确提到「海外环境 / 境外环境 / overseas / 出海 / keetapp」
2. 用户提供的 Raptor 链接域名为 `raptor.mws.keetapp.com`（如 `https://raptor.mws.keetapp.com/home`）
3. 请求来自境外站点的 Raptor Agent（来源特征文本见下节，链接域名为 keetapp）
4. 用户在本会话中已指定过境外环境，后续追问沿用

反之，用户明确说「境内」，或未出现任何境外信号时，使用默认境内环境，不要自作主张切换。

### 判定为境外后的执行规则

1. **命令字替换**：本文件及所有子技能中的 `raptorfe` 示例命令，统一替换为 `raptorfeov`；模块、子命令、参数、时间格式完全不变。
   - 例：`raptorfe crash timeseries get ...` → `raptorfeov crash timeseries get ...`
2. **不混用**：同一分析任务只用一个命令字；不要同时调用境内与境外命令再拼接结论，避免把境内数据当成境外数据。
3. **链接同步换域名**：回复中给出的 Raptor 页面链接、万能钥匙引导链接一律用 `raptor.mws.keetapp.com`，不要给 `raptor.mws.sankuai.com` 链接。
4. **鉴权无差异**：`raptorfeov` 与 `raptorfe` 共用同一套 SSO 自动鉴权（首次触发大象 CIBA 授权确认，之后复用缓存），无需用户提供 Cookie；境外登录态过期时页面会 302 跳 `mws.keetapp.com/login`，CLI 会自动重新鉴权。
5. **安装要求**：`raptorfeov` 由同一个 npm 包 `@mtfe/raptorfe-cli` 提供（需 ≥ 1.0.25 版本），装了 `raptorfe` 即已具备，缺命令时按子技能中的安装命令补齐后重试。
6. **环境自检**：执行 `raptorfeov doctor check`，其 `data.environment` 应为 `overseas`；若为 `domestic` 说明命令字用错。
7. **报告标注**：境外环境的分析结果需在抬头或数据说明处标注「境外环境（raptor.mws.keetapp.com）」，避免与境内数据混淆。
8. **失败处理**：境外链路较慢且存在波动，查询超时**或 4xx/5xx 失败**时，如实说明失败原因与已知限制，不改写查询参数、不凭空编造数据、不机械套用 `--timeout` 重试。
9. **能力边界**：境外命令入口未提供 `alert` 系列命令（告警创建 / 更新 / 启停等），配置告警请引导用户在 Raptor 境外站点 Web 界面操作；数据查询类命令（mobile / metric / crash / web / mp / perf / dashboard）均可正常使用。
10. **境外 crash 全 0 判定**：境外站点主体服务出海业务（如 keetapp 项目），境内业务项目（如 meituan / waimai-wxapp / shangou-wxapp）在境外站点**无 crash 数据，返回全 0 属已知现象**（2026-11-19 实测）。境外 crash 查询返回全 0 时，先通过 `raptorfeov mobile project list` 或与用户确认该业务是否为出海项目，再下结论；**不得直接报「崩溃清零 / 无 crash」**。
11. **crash ratio get 境外当前不可用（2026-11-19 实测）**：境外 `crash ratio get` 稳定超时或 HTTP 400（境内同参数正常）。需要量级时改用 `crash timeseries get`；崩溃率需另行计算或引导用户走境外 Web 页面。此为服务端现状，修复后需回改本条，不要当成永久结论。
12. **间歇超时**：境外链路同一命令一次成功、一次超时属正常网络状况，可等价重试一次；仍失败则如实说明网络问题，不要改写查询参数、不要编造数据。

---

## CLI 版本要求（大盘三期能力，必读）

自定义大盘三期能力（图表类型 0-7、参考线、环比、维度对比、灰度配置、Tab 级筛选器、跨 Tab 复制、老大盘导入、图表分析上下文 `chart context`）要求：

```
raptorfe --version ≥ 2.0.3
```

**版本检查**（semver 比较）：`raptorfe --version`，输出小于 `2.0.3` 即不满足。

**升级命令**：

```bash
npm install -g @mtfe/raptorfe-cli --registry=http://r.npm.sankuai.com
```

**错误引导**：旧版本调用三期新命令（如 `dashboard chart context`、`dashboard gray-config`、`dashboard import`）会报 `unknown command` / `unknown option` 类错误。遇到此类错误先执行版本检查，按上方命令升级后重试，不要改用浏览器接口绕过。

三期能力编排细则见 [references/raptorfe-dashboard-create/SKILL.md](references/raptorfe-dashboard-create/SKILL.md) 与 [references/dashboard-patrol/SKILL.md](references/dashboard-patrol/SKILL.md)。

---

## 能力列表

| 用户意图 | 子能力 | 使用说明 | 路径 |
|---|---|---|---|
| 查询 Crash 率/ANR/Foom/watchdog、RCF/R/C/F 分数、MSC 容器、Metrics、移动端端到端/自定义/web/小程序等各类 Raptor 大前端指标 | Raptor 大前端全量指标查询 | 直接提问，例如：「查一下美团 Android 最近 7 天的 Crash 率」 | [references/raptorfe-allquery/SKILL.md] |
| 分析大前端监控告警、定位指标波动根因、多维下钻、输出趋势对比报告 | 大前端告警自动分析 | 转发大前端监控 PERF 告警消息给 🦞 自动分析 | [references/raptorperf-alert-analyzer/SKILL.md] |
| 收到 Crash/ANR/FOOM/Watchdog **告警推送消息**（含告警标题、聚类信息等格式化告警文本），分析 crash 堆栈、定位根因、给出修复建议。**注意：若用户是主动发送 Raptor 链接或主动描述分析诉求，不走本路由** | Crash 告警分析（已统一迁移至 infra-app-stability/root-cause） | 转发 Crash/ANR/FOOM 告警消息给 🦞 自动分析 | [skills-market/infra-app-stability/references/root-cause/SKILL.md] |
| 查看组件 Crash 趋势图、小时级/N天趋势/多版本对比/同比观测 | Crash 组件波动分析看板 | 直接提问，例如：「画一下 logan 组件最近 7 天的 Crash 趋势图」 | [references/component-crash-chart/SKILL.md] |
| 创建自定义监控大盘、新建大盘、创建大前端大盘，支持自然语言描述指标或粘贴 Raptor 页面链接自动解析；配置大盘灰度观测、跨 Tab 复制图表/筛选器配置 | Raptor 自定义大盘创建 | 直接描述要监控的指标，或粘贴 Raptor 页面链接，例如：「创建一个美团 iOS WaimaiAddress 组件 Crash 率的大盘」 | [references/raptorfe-dashboard-create/SKILL.md] |
| 导入老 Raptor 大盘、迁移旧大盘到自定义大盘平台（用户提供老大盘 ID，如 dashboardId=116218） | 老 Raptor 大盘导入（CLI） | 提供老大盘 ID，例如：「帮我导入老 Raptor 大盘 116218」 | [references/raptorfe-dashboard-create/SKILL.md]（方式三） |
| 用户**主动**分析最近 N 天 Crash / ANR / FOOM 的趋势波动（非告警推送触发），或用户**发送 Raptor 页面链接**（如 `raptor.mws.sankuai.com/crash/...`）并提出分析诉求，按版本/时间/组件/聚类/设备/前后台等多维度逐步分析，输出根因报告 | 稳定性指标波动分析 | 直接描述分析诉求，例如：「分析一下美团 iOS 最近 14 天的 Crash 波动」，或粘贴 Raptor crash 页面链接 | [references/crash-wave-analysis/SKILL.md] |
| 用户**主动**分析 RCF / R / C / F 分数的波动、劣化、下降（非告警推送触发），或用户**发送 Raptor 性能大盘链接**（如 `raptor.mws.sankuai.com/ffp/...`）并提出分析诉求，按子指标贡献度→维度下钻→多维交叉逐步分析，输出根因报告 | RCF 指标波动分析 | 直接描述分析诉求，例如：「分析一下美团 iOS 最近 7 天的 C 分数波动」，或粘贴 Raptor 性能大盘链接 | [references/rcf-raptor-anylisize/SKILL.md] |
| 用户发送 Raptor **自定义大盘链接**（URL 含 `dashboardId=`），要求巡检/分析/查看大盘数据，自动读取所有 Tab 和图表配置，批量查询最近 7 天天粒度数据，逐图表异常检测，生成数据报告，对异常指标进行多维度下钻分析 | 自定义大盘巡检 | 发送自定义大盘链接，例如：「帮我巡检一下这个大盘」、「这个大盘最近有没有异常」 | [references/dashboard-patrol/SKILL.md] |
| 用户**主动**分析通用类指标波动根因（移动端端到端/自定义指标/Perf 指标/Web 端/小程序），按版本/平台/网络/地区等多维度下钻，不含 RCF 和 Crash/ANR/FOOM | 通用指标下钻分析 | 直接描述分析诉求，例如：「分析 banma_all 项目 xxx 接口最近 7 天网络成功率波动」、「分析外卖 Android fnr-ad-entrance 自定义指标最近 14 天趋势」 | [references/general-metric-analysis/SKILL.md] |
| 用户**主动**分析 Web 端（OWL）JS 异常 / 资源异常 / Promise 异常的波动（非告警推送触发），或用户**发送 Raptor Web 端异常页面链接**（如 `raptor.mws.sankuai.com/frontend/error/...`）并提出分析诉求，或**转发含 [前端异常] 标签的告警消息**，按聚类/页面/容器/OS 等多维度逐步分析，输出根因报告和堆栈分析 | OWL Web 端异常波动分析 | 直接描述分析诉求，例如：「分析一下 goodsmarket 项目最近 7 天 JS 错误波动」，或粘贴 Raptor Web 端异常页面链接，或转发前端异常告警消息 | [references/owl-web-error-analysis/SKILL.md] |
| 用户输入一个 **uuid（设备标识 deviceId，通常 64 位十六进制）** 并提出查询/排查异常诉求，检索该设备最近 7 天内发生过的所有异常（崩溃/ANR/异常退出/捕获异常/卡顿/业务 JS 异常），逐类拉日志详情并按时间线汇总成「用户异常画像」报告。**注意：这是按 uuid 查异常日志，不是 uuid↔userid 等 ID 互转** | UUID 查询异常日志 | 直接输入 uuid + 排查诉求，例如：「帮我查一下这个 uuid `0000...5406` 最近发生过哪些异常」 | [references/uuid-error-query/SKILL.md] |

## 路由说明

根据用户描述的意图，找到上表中最匹配的子能力，读取对应路径的 SKILL.md，然后按该 SKILL.md 的指引执行具体操作。

子能力路径均相对于本文件所在目录（`skill/`）。

### Raptor Agent 来源识别（重要）

当用户消息中包含以下任一特征文本时，说明该请求来自 **Raptor 页面上的 AI 按钮**（Raptor Agent），而非用户在 CatDesk 中主动发起：

- `⚠️ 请使用 infra-raptor skill 进行分析，必须使用以下查询参数作为 CLI 调用的输入，不要自行解读数据或跳过 skill 调用。`
- `这是一个raptor页面的请求，请使用对应的skill`

> 境外站点的 Raptor Agent 使用相同来源文本，仅链接域名为 `raptor.mws.keetapp.com`；此时按「环境识别」章节切换为境外环境（`raptorfeov`）。

**识别为 Raptor Agent 来源后的行为差异：**

1. **语境理解**：用户说"分析下这个页面的数据"时，"页面"指的是 Raptor 站点上当前展示的图表/数据页面，**不是**数据中"页面"维度字段。应直接使用消息中附带的查询参数进行 CLI 调用并分析结果。
2. **参数优先**：Raptor Agent 传来的消息中通常附带了完整的查询参数（project、type、时间范围、过滤条件等），应**直接使用这些参数**调用 CLI，不需要再向用户确认。
3. **分版本图表特殊处理**：如果消息中包含「【图表】分版本异常量变化」或「【图表】分版本异常率变化」，需要先通过 `raptorfe crash events list` 获取发版事件确定版本号，再分版本查询数据。详见 `crash-wave-analysis` 子技能中的「Raptor Agent 分版本图表分析流程」章节。

### 路由消歧规则

以下场景容易混淆，优先按此规则判断：

| 用户行为 | 路由目标 |
|---------|---------|
| 消息含「⚠️ 请使用 infra-raptor skill」或「这是一个raptor页面的请求」+ Crash/ANR 相关参数 | `crash-wave-analysis`（Raptor Agent 来源，按消息中参数直接执行） |
| 转发/粘贴一段**格式化告警文本**（含告警标题、触发时间、聚类名等），或以 `[P\d][crash]`/`[anr]`/`[foom]`/`[watchdog]` 开头的告警消息 | **`infra-app-stability` → `root-cause`**（跨技能路由，见下方「Crash 告警统一路由」） |
| 发送 `raptor.mws.sankuai.com/crash/...` **链接** + 分析诉求 | `crash-wave-analysis` |
| 主动描述「分析 Crash/ANR/FOOM 趋势/波动」，无告警文本 | `crash-wave-analysis` |
| 发送 `raptor.mws.sankuai.com/ffp/...` 或性能大盘**链接** + 分析诉求 | `rcf-raptor-anylisize` |
| 主动描述「分析 RCF/R/C/F 分数波动/劣化」，无告警文本 | `rcf-raptor-anylisize` |
| 发送 `raptor.mws.sankuai.com` **链接** + 要求**新建大盘** | `raptorfe-dashboard-create` |
| 用户提到「导入老 Raptor 大盘 / 迁移旧大盘 / 老大盘转新平台」，或提供老大盘数字 ID（如 116218） | `raptorfe-dashboard-create`（方式三：`dashboard import`，必走 dry-run 预览） |
| 用户提到「配置灰度大盘 / 灰度筛选器 / 设置版本监控范围」，或要求把一个 Tab 的图表/筛选器复制到另一个 Tab | `raptorfe-dashboard-create`（gray-config / copy-config 章节） |
| 发送 `raptor.mws.sankuai.com/lowcode/custom/dashboard/detail?dashboardId=...` **自定义大盘链接** + 巡检/分析/查看数据诉求 | `dashboard-patrol` |
| 用户**主动**描述「分析端到端/自定义指标/Perf/Web/小程序指标波动」，无告警文本，且不是 RCF/Crash/ANR/FOOM/Web 异常 | `general-metric-analysis` |
| 转发/粘贴含 `[前端异常]` 标签的告警消息 | `owl-web-error-analysis` |
| 发送 `raptor.mws.sankuai.com/frontend/error/...` 链接 + 分析诉求 | `owl-web-error-analysis` |
| 主动描述「分析 Web/OWL 端 JS 异常/资源异常/Promise 异常波动」 | `owl-web-error-analysis` |
| 用户输入一个 **uuid（deviceId，通常 64 位十六进制）** + **查询/排查异常**诉求（如"这个 uuid 发生过哪些崩溃/异常"、"帮我查这个设备的异常"） | `uuid-error-query`（按 deviceId 检索最近 7 天全类型异常日志） |
| 用户要求 uuid/dpid/userid/unionid 等 ID **互转**（如 uuid 查 userid、userid 反查 uuid），或提及万能钥匙/masterkey/查设备信息 | 直接拒绝，回复「当前不支持 ID 查询功能，请前往 Raptor 万能钥匙（境内 https://raptor.mws.sankuai.com ／境外 https://raptor.mws.keetapp.com）系统界面中查询。请注意用户隐私，非必要不查询。」 |
| 用户提供 `raptor.mws.keetapp.com/...` **链接**（含 `/home`）+ 任意查询/分析诉求 | 按链接路径路由到对应子能力，但 CLI 一律使用 `raptorfeov`（见「环境识别：境内 / 境外」） |
| 用户明确提到「海外 / 境外 / overseas」+ 查询或分析诉求 | 同上按意图路由，CLI 一律使用 `raptorfeov` |

### Crash 告警统一路由（重要）

> 🚨 **Crash / ANR / FOOM / Watchdog 告警的根因分析已统一收敛至 `infra-app-stability` 技能的 `root-cause` 子技能。**
> 原 `crash-alarm-check` 子能力已改造为转发壳，不再包含分析逻辑。

**触发特征**（满足任一即视为告警消息）：

- 消息以 `[P\d][crash]` / `[P\d][anr]` / `[P\d][foom]` / `[P\d][watchdog]` 开头
- 消息含「策略名称」「GroupBy」「统计开始时间」「触发规则」「当前值」等告警字段
- 消息含 `[[聚类列表|URL]]` 形式的聚类跳转链接

**执行动作**：

1. Read skill 文件：`skills-market/infra-app-stability/references/root-cause/SKILL.md`（若不存在，回退尝试 `skills-market/infra-app-stability/skill/references/root-cause/SKILL.md`）
2. 按 root-cause 的**模式 A（告警消息/聚类标识）**流程执行完整分析
3. 将用户告警消息**原文透传**，由 root-cause 自行解析参数并完成参数回述与路由说明

**为什么统一**：root-cause 完整覆盖原 crash-alarm-check 的全部能力（告警解析 → 聚类列表 → 趋势分析 → 维度分布 + DAU 偏差 → 堆栈深度分析 ≥5 条 → 输出报告），并额外提供**数据波动前置判断**（过滤基线为 0 / 小样本 / 历史波动区间内的伪告警）和**变更关联定位**（crash-change-locator Mode A 关联 Diva/Horn/Native 变更，输出置信度）。

**不受影响的场景**（仍走原路由，不要误转发）：

- Raptor Agent 来源（消息含「⚠️ 请使用 infra-raptor skill」或「这是一个raptor页面的请求」）→ `crash-wave-analysis`
- 用户主动描述趋势波动分析、或发送 `raptor.mws.sankuai.com/crash/...` 链接 → `crash-wave-analysis`
- 含 `[前端异常]` 标签的 Web 端告警 → `owl-web-error-analysis`
- 大前端监控 PERF 告警 → `raptorperf-alert-analyzer`

## 安装成功引导

**触发条件**：当用户说"安装成功了吗"、"skill 装好了吗"、"infra-raptor 怎么用"、"Raptor 怎么用"、"这个 skill 能干嘛"，或用户首次与本 skill 交互且没有明确的分析/查询意图时，主动发送以下安装成功欢迎消息。

**欢迎消息模板**（原文输出，不要改动格式）：

---
✅ **Raptor 大前端 Skill 已就绪！** `v0.11.0`

我能帮你做这几件事 👇

---

**🔔 告警分析（最常用）**
把大象收到的雷达告警消息**直接转发/粘贴**过来，我会自动分析：
- **Crash / ANR / FOOM 告警** → 解析堆栈、定位根因、给出修复建议
- **大前端监控 PERF 告警** → 多维下钻、趋势对比、输出分析报告

> 💡 无需任何额外说明，把告警消息完整复制发过来就行

---

**📊 查指标**
用自然语言直接问，例如：
- 「查一下美团 Android 今天的 Crash 率」
- 「美团 iOS Native技术栈最近 7 天 C 分数趋势」
- 「外卖 Android 12.10.203 版本的 ANR 率」
- 「查一下 privacy 项目下 privacy_** 指标最近 7 天的 TP90」
- 「waimai_boot_apis 项目 waimai_boot_apis 接口最近 7 天端到端网络成功率」

支持：Crash/ANR/FOOM/RCF/性能/自定义指标，覆盖美团/外卖/点评，Android/iOS/鸿蒙

> 🌏 支持境外环境：提到「海外/境外」或使用 `raptor.mws.keetapp.com` 域名时，自动改用境外 CLI（`raptorfeov`）

---

**📈 Crash 趋势图**
- 「画一下 logan 组件最近 7 天的 Crash 趋势」
- 「美团 iOS 多版本 Crash 对比图（12.48 vs 12.49）」

---

**📊 创建监控大盘**
用自然语言描述指标，或直接粘贴 Raptor 页面链接，一键生成大盘：
- 「创建一个美团 iOS WaimaiAddress 组件 Crash 率和 Crash 次数的大盘」
- 「帮我建个大盘，配置 ffp_native 首屏时长 TP90 趋势图」
- 「把这个老 Raptor 大盘 116218 导入成新大盘」
- 「给这个 Tab 配置灰度观测（只看最新版+次新版）」
- 直接粘贴 `raptor.mws.sankuai.com/crash/...` 等页面链接

---

**📉 RCF 指标波动分析**
主动分析 RCF / R / C / F 分数波动，定位根因：
- 「分析一下美团 iOS 最近 7 天的 C 分数波动」
- 「外卖 Android R 分数这周劣化了，帮我分析一下」
- 直接粘贴 `raptor.mws.sankuai.com/ffp/...` 等性能大盘链接

---

**🔍 通用指标下钻分析**
分析移动端端到端/自定义指标/Perf/Web/小程序指标波动，多维度下钻定位根因：
- 「分析美团 iOS 最近 7 天 xxx 接口网络成功率波动」
- 「分析外卖 Android fnr-ad-entrance 自定义指标最近 14 天趋势」
- 「分析 H5 项目 xxx 页面加载耗时 TP90 波动」

---

**🔎 UUID 异常排查**
给我一个设备 uuid（deviceId）+ APP，我会检索该设备最近 7 天的全类型异常（崩溃/ANR/异常退出/捕获异常/卡顿/业务 JS 异常），按时间线汇总成排查报告：
- 「帮我查一下这个 uuid `0000...5406` 最近发生过哪些异常（美团iOS）」
- 「排查一下这个设备的崩溃，deviceId 是 xxxx」

> ⚠️ 仅按 uuid 查异常日志，不做 uuid↔userid 等 ID 互转（ID 转换请用 Raptor 万能钥匙页面）

---

## 用户引导

当用户表达以下意图时，调用上方安装成功引导中的欢迎消息模板进行回复：
- 询问 skill 怎么用 / 能干什么
- 发来"你好"、"在吗"等打招呼消息但没有具体任务
- 表示不知道从哪里开始
