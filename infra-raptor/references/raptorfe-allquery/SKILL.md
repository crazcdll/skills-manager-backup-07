---
name: infra-raptorfe-allquery
display_name: Raptor大前端全量指标查询
description: 通过自然语言描述查询 Raptor 大前端相关的各类指标数据，支持 Crash（崩溃率/ANR/Foom/watchdog/捕获异常）、Raptor大前端指标（RCF/R分数/C分数/F分数/MSC容器/Metrics/babel自定义/大前端自定义）、老Raptor指标（移动端端到端/移动端自定义/web端/小程序端）三大分类。自动识别指标类型，选择对应CLI命令查询，支持按时间、版本、组件、项目等多维度筛选。触发词：查Crash率、查ANR、查RCF指标、查R分数、查C分数、查F分数、查秒开率、查端到端耗时、查自定义指标、查大前端指标、查Raptor指标、查小程序指标、查web端指标、mobile.outlink、bizpay、指标查询、Raptor数据
tags: 终端基础技术,Raptor,大前端,Crash,性能指标
version: 0.6.7
created: 2026-03-23

metadata:
  skillhub.creator: "zhangxinyue27"
  skillhub.updater: "zhangxinyue27"
  skillhub.version: "V5"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "12902"
---

# Raptor 大前端全量指标查询

## 功能概述

通过自然语言描述，查询 Raptor 大前端相关的各类指标数据。Skill 自动识别指标分类，选择对应的 CLI 命令完成查询，无需用户关心底层接口细节。

底层工具：**`raptorfe`（`@mtfe/raptorfe-cli`）**，SSO 全自动鉴权，首次触发大象推送确认一次后缓存 2.5 小时，无需手动传 `--cookie`。

## ⚠️ 鉴权说明（AI 必读，不可跳过）

**CLI 内置完整 SSO 鉴权流程，Agent 无需任何额外操作，更不能向用户索要 Cookie。**

### 鉴权流程（全自动）

1. CLI 启动时自动读取本地缓存（`~/.config/raptor-cli/token-cache.json`）
2. 缓存有效（2.5h 内）→ 直接复用，无需任何操作
3. 缓存缺失/过期 → 自动调用 `sso-auth-cli`，触发 **CIBA 授权**：
   - 大象 App 会收到一条授权推送（类似"有新登录请求"）
   - 用户在大象 App **点击确认**后，CLI 自动拿到 token 并缓存
4. HTTP 请求返回 401 → 自动清除缓存并重新走步骤 3

### Agent 正确处理方式

| 场景 | 正确做法 | ❌ 错误做法 |
|------|---------|-----------|
| 正常执行，无任何鉴权输出 | 直接等待结果 | — |
| stderr 出现"大象推送"提示 | 告知用户：**"CLI 正在等待大象 App 授权，请在大象 App 里点击确认"**，然后继续等待（最多 2 分钟） | ~~向用户索要 Cookie~~ |
| 收到 401 响应 | CLI 会自动重试，Agent 等待即可 | ~~向用户索要 Cookie~~ |
| sso-auth-cli 超时失败 | 报错提示：「SSO 鉴权超时，请确认是否在大象 App 点击了授权确认，或检查内网连通性」 | ~~向用户索要 Cookie~~ |

> **核心原则：CLI 自己会解决鉴权，Agent 的职责是执行命令并等待结果。遇到鉴权相关输出时，引导用户去大象 App 操作，而不是让用户手动复制 Cookie。**
> 
> ⚠️ **命令执行后可能沉默 10～30 秒（正在调用 sso-auth-cli 获取 token），这是正常现象，不是卡死。在 sso-auth-cli 缓存过期时，还需要等用户在大象 App 点击确认（最多 2 分钟）。全程 Agent 只需等待，不要中断命令、不要催用户提供 Cookie。**

## 安装 CLI

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

```bash
# 1. 安装 raptorfe CLI
npm install -g @mtfe/raptorfe-cli@beta --registry http://r.npm.sankuai.com

# 2. 预装 sso-auth-cli（⚠️ 必须，否则鉴权会失败）
npm install -g @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
```

> `@beta` tag 始终指向最新版，无需写死版本号。

> ⚠️ **sso-auth-cli 必须预先全局安装**。CLI 内部通过 `npx` 动态调用 `sso-auth-cli`，若 `r.npm.sankuai.com` 拉包失败（网络问题、npm 源未配置），鉴权会直接报错。预装后 npx 会优先使用本地已安装版本，不再依赖网络。

## 顶层命令结构

```
raptorfe [options] [command]

Commands:
  mobile      移动端端到端监控
  metric      移动端自定义指标
  hijack      劫持报表
  domain      域名监控
  crash       Crash 稳定性监控
  web         web 端性能/异常/资源/PV/自定义指标
  mp          小程序性能/异常/请求/PV/自定义指标
  perf        Perf 指标查询

Global Options:
  --cookie <string>   手动传入 Cookie（自动鉴权失败时备用）
  -t, --timeout <ms>   请求超时毫秒数，默认 30000
  -o, --output <format>  输出格式：json（单行）| pretty（缩进，默认 TTY）
  --raw               输出原始 JSON（已废弃，等同于 --output json）
  --dry-run           模拟执行不发请求
  --verbose           输出调试信息到 stderr
```

## 指标三大分类

| 分类 | CLI 模块 | 覆盖指标 |
|------|---------|---------|
| 老 Raptor | `mobile` / `metric` / `web` / `mp` / `hijack` / `domain` | 移动端端到端、自定义指标、web、小程序、劫持、域名 |
| Perf | `perf metric` | RCF/R/C/F 分数、秒开率、白屏率、负体验、MSC 容器、babel 自定义 |
| Crash/质量 | `crash` | Crash 率、ANR、Foom、watchdog、稳定性 |

## ⚠️ 时间格式（各模块不统一，易出错）

| 模块 | 时间参数 | 格式 |
|------|---------|------|
| `mobile` / `web` / `mp` / `hijack` / `domain` | `--start-time` / `--end-time` | **毫秒时间戳 或 日期字符串**（如 `"2026-03-28"` / `"2026-03-28 10:00:00"`） |
| `crash` | `--start` / `--end` | `"YYYY-MM-DD HH:MM:SS"` |
| `perf get-trend`（DAY 粒度） | `--start-time` / `--end-time` | `"YYYY-MM-DD"` |
| `perf get-trend`（分钟/小时粒度） | `--start-time` / `--end-time` | `"YYYY-MM-DD HH:MM:SS"` |
| `web` / `mp` custom-metric、`metric` 自定义指标 | `--start-str` / `--end-str` | `"YYYY-MM-DD HH:mm"` |

---

## 执行流程

### Step 1：解析用户意图

**关键字 → CLI 模块映射（先按此表判断）：**

| 用户关键字 | 对应 CLI 模块 |
|-----------|-------------|
| 移动端端到端 | `mobile` |
| 移动端自定义指标、Cat 上报 | `metric` |
| web 端 | `web` |
| 小程序端 | `mp` |
| 体验优化、RCF、秒开率2.0、babel 自定义指标、Perf 系统指标 | `perf` |
| 版本覆盖率、版本占比、某版本以上覆盖率、某版本量级/去重数、机型/机型分级(高中低端)占比、网络类型/厂商/系统版本等任意维度占比、lingxi.pv 用户数占比/去重数 | `perf`（用 `device-info-v3` + `distribution` 命令，见 Step 2.5 专门章节；lingxi.pv 见其专章；**必须遵守各章「去重数表述与输出规范」并执行输出前自检**）。**用户提到 DAU 时：第一句必须明确告知"Raptor 没有 DAU 指标，不支持 DAU 查询"，可用设备去重数统计但不等于 DAU 口径、有差异只可参考占比（见各章合规规则与反例）** |
| Crash、ANR、崩溃率、稳定性 | `crash` |

**指标命名规律辅助判断：**

- 驼峰命名（如 `MRNPageLoadSuccess`）→ 优先老 Raptor，appId=10000
- 含点号多段命名（如 `bizpay.sdk.load`）→ 优先老 Raptor
- `mobile.` / `web.` / `metricx.` / `ffp_` / `ppf_` / `feedback_` 前缀 → Perf
- 无法判断时走 Step 2 ⑥ 兜底

**引导话术（找不到指标时）：**

> "请您尽可能描述指标来自哪个上报 SDK 或模块。比如 Cat 上报的移动端自定义指标、Babel 上报的自定义指标。"

### Step 1.5：APP 字段映射

| APP | Crash (`--project`) | Perf (`--appkey` / `--project-name`) | 老Raptor 移动端 (`--app-id`) |
|-----|--------------------|------------------------------------|---------------------------|
| 美团 iOS | meituan | PERF / meituan | 10 |
| 美团 Android | android_platform_monitor | PERF / android_platform_monitor | 10 |
| 美团 HarmonyOS | meituan-harmony | PERF / meituan-harmony | 10 |
| 点评 iOS | nova | — / nova | 1 |
| 点评 Android | android-nova | — / android-nova | 1 |
| 点评 HarmonyOS | harmony-nova | — / harmony-nova | 1 |
| 外卖 iOS | waimai_ios | — / waimai_ios | 11 |
| 外卖 Android | meituanwaimai | — / meituanwaimai | 11 |
| 外卖 HarmonyOS | waimai-harmony | — / waimai-harmony | 11 |
| 容器监控（虚拟APP） | — | — | 10000 |

> 容器监控（appId=10000）：专门存放 MRN、Picasso、babel、pike 等容器的自定义指标，不对应真实 App。

### Step 2：指标分类判断

优先级从高到低，按顺序匹配，命中即停。

**① Crash（最高优先级）**

- 关键词：Crash 率、崩溃率、ANR 率、Foom、watchdog、稳定性趋势 → `raptorfe crash`
- 关键词：crash 详情、堆栈、UUID → `raptorfe crash detail get`

**② ID 查询 / 万能钥匙（不支持，直接拒绝）**

- 关键词：uuid/dpid/userid/unionid/oneid 互转、查设备信息、万能钥匙、masterkey、查用户 ID、ID 转换
- **一律拒绝，不执行任何命令**，回复：

> 当前不支持 ID 查询功能，请前往 [Raptor 万能钥匙](https://raptor.mws.sankuai.com) 系统界面中查询。请注意用户隐私，非必要不查询。

**③ 老 Raptor 移动端端到端/自定义指标**

- 用户描述含：端到端、移动端端到端、移动端自定义指标
- 指标名含点号（如 `bizpay.sdk.load`）且不含 `mobile.` / `metricx.` 前缀
- 驼峰命名（如 `MRNPageLoadSuccess`）→ 优先查老 Raptor；查不到再去 Perf

**④ 老 Raptor web 端/小程序**

- 用户描述含：web 端指标、小程序指标
- 用户提供 `com.` 开头的项目名 → 强判老 Raptor

**⑤ Perf 平台**

- 关键词：RCF、R 分数、C 分数、F 分数、秒开率、白屏率、负体验占比、MSC 容器、大前端监控、Metrics、babel sdk、perf sdk
- 指标名以 `mobile.`、`web.`、`metricx.`、`ffp_`、`ppf_`、`feedback_` 开头
- 用户明确说是 Perf 平台

**⑥ 兜底策略**

1. 先搜 Perf：`raptorfe perf metric search --appkey PERF --match "指标名"`，找到则走 Perf 流程
2. 再查老 Raptor 移动端：`raptorfe metric list --app-id 10`
3. 仍不确定时询问 SDK：CAT/OWL → 老 Raptor；babel/perf SDK → Perf

### Step 2.5：核心系统指标速查表（全部为 Perf 模块）

#### ⚠️ 分数计算原理（必读，影响下钻方式）

RCF 分数**不是**直接对耗时/帧率原子指标做数学换算，而是 Raptor 后端在每条原始日志入库时，同步衍生出一个 `.score` 原子指标：

- 例：`ffp_native` 某条日志耗时 3421ms → 后端换算出分数 78 → 写入 `ffp_native.score`，value=78
- 最终展示的"C 分数"= `ffp_native.score` 的 SUM ÷ `ffp_native.score` 的 reckoncount（即加权均值）
- **`.score` 后缀指标对用户分析没有直接意义**，它只是算分的中间载体，不代表耗时也不代表达标率

**下钻时的正确主指标：**

| 分数类型 | 下钻时用的原子指标（`--metrics-name`） | 说明 |
|---------|--------------------------------------|------|
| C 分数（秒开） | `ffp_native` / `ffp_mrn` / `ffp_mmp` / `ffp_msc` / `ffp_knb` | 首屏耗时原子指标 |
| R 分数（交互响应） | `metricx.response.duration` | 交互响应耗时原子指标 |
| F 分数（滑动掉帧） | `mobile.fps.scroll.avg.v2.n` | 掉帧率原子指标 |

> **不要用 `.score` 指标做 `dimension-analyse` 的主指标**，应以上表中的原子指标为主，把分数复合指标放入 `--other-metrics`。

---

#### 秒开（C 指标）完整指标体系

| 技术栈 | 首屏耗时原子指标（atom） | 秒开率（composite） | 单栈 C 分数（composite） |
|--------|------------------------|--------------------|-----------------------|
| Native | `ffp_native` | `ffp_native.ratio` | `C分数-26年-Native` |
| MRN | `ffp_mrn` | `ffp_mrn.ratio` | `C分数-26年-MRN` |
| MMP | `ffp_mmp` | `ffp_mmp.ratio` | `C分数-26年-MMP` |
| MSC | `ffp_msc` | `ffp_msc.ratio` | `C分数-26年-MSC` |
| KNB | `ffp_knb` | `ffp_knb.ratio` | `C分数-26年-KNB` |
| **5栈汇总** | —（无单一原子指标） | — | `C分数-26年` |

> - 秒开率后缀是 `.ratio`（不是 `.tatio`）
> - C 分数指标命名规律：`C分数-26年-<技术栈>`，5 栈汇总为 `C分数-26年`，均为 composite
> - 中间指标 `ffp_native.score` 等 `.score` 后缀指标**不用于下钻**，仅供后端算分

**C 分数下钻示例（以 MRN 为例）：**

```bash
# 查 C分数-26年-MRN 的维度分布
# --metrics-name 传原子指标 ffp_mrn，--other-metrics 传复合指标 ID（先 search 获取）
raptorfe perf metric search --appkey PERF --match "C分数-26年-MRN"   # 获取 composite ID，如 c17949
raptorfe perf metric dimension-analyse \
  --metrics-name ffp_mrn --metrics-type atom \
  --other-metrics "c17949" \
  --tag-names "appVersion" \
  --agg DAY --start-time "2026-04-22" --end-time "2026-04-29"
```

---

#### 交互响应延迟（R 指标）完整指标体系

| 类型 | 指标名 | 备注 |
|------|--------|------|
| 原子指标（耗时） | `metricx.response.duration` | atom，下钻主指标 |
| R 分数（汇总） | `R分数-26年` | composite，各技术栈汇总 |

> R 分数**不按技术栈拆分为独立指标**，而是在同一个 `R分数-26年` 指标内，通过 `techStack` 维度字段区分，可选值如 `native`、`mrn`、`msc`、`knb`。

**R 分数下钻示例：**

```bash
# 查 R分数-26年 的技术栈分布
raptorfe perf metric search --appkey PERF --match "R分数-26年"   # 获取 composite ID
raptorfe perf metric dimension-analyse \
  --metrics-name metricx.response.duration --metrics-type atom \
  --other-metrics "<R分数-26年的composite ID>" \
  --tag-names "techStack,appVersion" \
  --agg DAY --start-time "2026-04-22" --end-time "2026-04-29"
```

---

#### 滑动掉帧（F 指标）完整指标体系

| 类型 | 指标名 | 备注 |
|------|--------|------|
| 原子指标（掉帧率） | `mobile.fps.scroll.avg.v2.n` | atom，下钻主指标 |
| F 分数（汇总） | `F分数-26年` | composite，各技术栈汇总 |

> F 分数同样**不按技术栈拆分为独立指标**，通过 `techStack` 维度字段区分，可选值如 `native`、`mrn`、`msc`、`knb`。

**F 分数下钻示例：**

```bash
# 查 F分数-26年 的技术栈分布
raptorfe perf metric search --appkey PERF --match "F分数-26年"   # 获取 composite ID
raptorfe perf metric dimension-analyse \
  --metrics-name mobile.fps.scroll.avg.v2.n --metrics-type atom \
  --other-metrics "<F分数-26年的composite ID>" \
  --tag-names "techStack,appVersion" \
  --agg DAY --start-time "2026-04-22" --end-time "2026-04-29"
```

---

#### 白屏率（全部为 Perf 模块）

| 类型 | 指标名 |
|------|-------|
| 汇总白屏率（5s+离开） | `ppf_WhitePage_alltype` |
| 5s 白屏率 | `ppf_WhitePage_on5s` |
| 离开白屏率 | `ppf_WhitePage` |

**白屏次数**（指标均为 `feedback_block`，区分筛选条件）

| 类型 | 指标 | 筛选条件 |
|------|------|---------|
| 5s 白屏次数 | `feedback_block` | isOn5s=1 且 isreal5swhite=1 |
| 离开白屏次数 | `feedback_block` | isOnLeave=1 且 isreal5swhite=1 |

#### 负体验占比（全部为 Perf 模块）

| 口径 | 指标名 | 分母说明 |
|------|-------|---------|
| 口径1 | `feedback_block.3s+.ratio` | 筛选条件下的用户 UV |
| 口径2 | `feedback_block.alluv.ratio` | 大盘 UV（仅受 APP/OS/版本控制） |

---

#### 版本覆盖率 / 任意维度占比查询（device-info-v3 + distribution 命令，必读）

当用户要查**某个版本以上的覆盖率**、**各版本占比**、**某个版本/机型/维度值的量级（去重数）**，或**任意硬件/环境维度的占比**（机型、机型分级、网络类型、厂商、系统版本等）时，统一使用 Perf 基础指标 `device-info-v3`，配合 **`raptorfe perf metric distribution`** 命令查询。

> 🔒 **去重数表述与输出规范（安全合规红线，输出前必须逐条自检）：** `device-info-v3` 的去重数（`distinct-count`）量级接近 DAU，但它**不是官方 DAU**，属于敏感口径。规则如下：
>
> 1. **用户提到「DAU」时，回复的第一句话必须明确告知：「Raptor 没有 DAU 指标，不支持 DAU 查询」**，然后说明：可以用技术指标的**设备去重数**做统计，但结果**不等于 DAU 口径、存在差异，只可参考占比**。不允许默默把去重数当 DAU 汇报，也不允许只字不提就照查；
> 2. **输出前自检（不通过必须改写后再输出）**：回复全文——包括标题、小标题、表格表头、行名、对比句、备注——**一个「DAU」字样都不能出现**，一律用「去重数 / 占比」表述；
> 3. **未获用户明确要求时，禁止输出任何去重数绝对值**：包括总量/总数，也包括分版本、分维度的去重数列。展示分布时表格**只保留占比列**；只有用户明确要「去重数/具体数值/绝对量级」时才给绝对值；
> 4. 一旦输出了任何去重数，必须同时附两句说明：①该数值为设备去重数，不严格等于官方 DAU 口径，仅供内部参考；②该数据仅限内部使用，**请勿对外泄露**。
>
> ❌ **反例（真实违规案例，禁止复现）：** 用户说“查一下鸿蒙 9月15 的 DAU，顺便拆各系统版本占比”，若回复标题写“9月15 DAU”、报出“总量约 971 万”、表格里列出各版本去重数列——即为违规。
> ✅ **正确示范：** 开头第一句“Raptor 没有 DAU 指标，不支持 DAU 查询；可以用设备去重数统计，但不等于 DAU 口径、有差异，只可参考占比”，随后只给各系统版本**占比**表格（无任何绝对值），结尾附“内部数据请勿对外泄露”。

`device-info-v3` 的机型、机型分级、网络等硬件/环境信息都是该指标的**维度 tag**，只要把对应 tag 作为 `--group-by` 传入，即可查到各维度值的去重数与占比（`percent`）。

> ⚠️ **务必用 `distribution` 命令，不要用 `dimension-analyse` 累加 distinctCount。** `dimension-analyse` 的 `distinctCount` 只对量级 Top N 个维度值返回（实测仅约 10 个），其余为空，累加求占比会因分母偏小而严重虚高（实测从真实 ~92% 误算成其他值）。`distribution` 命令对**每个**维度值都返回真实去重数，并自带全量 `totalValue` 作为分母、`percent` 作为占比。

**指标与字段信息：**

| 项 | 值 |
|----|----|
| 指标名称 | `device-info-v3` |
| 项目名（`--project-name`，顶层字段） | 见下方「APP → project-name 映射表」 |
| 分组维度（`--group-by`） | 任意维度 tag，默认 `appVersion`；常用：`device_marketing_name` 机型、`model` 机型分级、`network` 网络类型、`build_manu` 厂商、`osVersion` 系统版本 |
| 统计方法（`--methods`） | `distinct-count`（去重数；注意是**中划线**。回复用户时禁止称之为 DAU，见上方「去重数表述与输出规范」） |
| 返回结构 | `data.distribution.<维度值>.value` = 该维度值去重数；`.totalValue` = 全量总去重数（分母）；`.percent` = 该维度值占比；顶层 `data.queryDate` = 实际查询日期 |

**APP → `--project-name` 映射表（distribution 命令用）：**

| 用户说的 APP | `--project-name` 值 |
|-------------|--------------------|
| 美团 iOS | `meituan` |
| 美团 Android | `android_platform_monitor` |
| 美团鸿蒙 | `meituan-harmony` |
| 外卖 iOS | `waimai_ios` |
| 外卖 Android | `meituanwaimai` |
| 外卖鸿蒙 | `waimai-harmony` |
| 点评 iOS | `nova` |
| 点评 Android | `android-nova` |
| 点评鸿蒙 | `harmony-nova` |
| 其他未列出的 APP | 用 `raptorfe crash project list` 查询对应 project 值 |

> 🔀 **用户未指明 APP / 操作系统时，必须分开逐个查询。** 例如用户只说"美团"没说 iOS 还是 Android，就把美团 iOS、美团 Android（及鸿蒙）分别跑一遍 distribution，再分别汇报；只说"外卖"同理。不要擅自只查其中一个或合并成一个数。
>
> ⚠️ 若某 APP 返回 `totalValue` / `totalDistinctCount` 为 `0`（即无数据），说明该 APP 该指标在 Perf 侧无上报或项目名不同，先用 `raptorfe crash project list` 核对项目名，仍无果则告知用户该 APP 暂无 `device-info-v3` 数据，不要伪造占比。

> 📅 **查询时间（重要）：** 该接口**只能查单天**数据。`--start-time`/`--end-time` **不传则默认查前一天**，输出 `data.queryDate` 会标明实际日期，并在 `notes` 提示——回复用户时务必告知查的是哪一天。**不建议查当日**：当日为分钟粒度、查询性能很差；用户若坚持查当日，CLI 会在 `notes` 提示性能问题，需向用户说明。

**先查可用维度（可选）：** 不确定有哪些维度 tag / 维度值时：

```bash
# 查 device-info-v3 的所有可用维度 tag
raptorfe perf metric get-tags --appkey PERF --metrics-name device-info-v3
# 查某个维度的可选值，如机型分级
raptorfe perf metric get-tag-values --metrics-name device-info-v3 --tag model
```

**场景 1（强烈推荐）——一条命令直接算版本覆盖率：**

`distribution` 命令内置 `--coverage-gte <版本号>`，自动按版本号分段数字比较、累加 ≥ 该版本的去重数并除以 `totalValue`，直接输出覆盖率（不传时间即查前一天）：

```bash
# 美团 iOS：>= 12.49.400 的版本覆盖率（默认查前一天）
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name meituan \
  --coverage-gte 12.49.400

# 美团 Android：仅把 project-name 换成 android_platform_monitor
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name android_platform_monitor \
  --coverage-gte 12.49.400
```

返回（节选）：

```json
{"ok":true,"data":{"queryDate":"2026-06-11","coverageGte":"12.49.400","totalDistinctCount":58053527,"matchedDistinctCount":53774524,"coverage":0.9263,"coveragePercent":"92.63%","matchedVersionCount":58,"notes":["未指定时间，已默认查询前一天（2026-06-11）"]}}
```

直接读 `coveragePercent`（如 `92.63%`），并把 `queryDate` 告知用户。

**场景 2——机型分级 / 机型 / 网络等任意维度占比：**

把维度 tag 传给 `--group-by`，每个维度值直接读 `percent` 即可，无需手动累加：

```bash
# 机型分级占比（model：HIGH/MIDDLE/LOW/UN_KNOW）
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name meituan \
  --group-by model

# 机型占比（device_marketing_name）
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name android_platform_monitor \
  --group-by device_marketing_name

# 网络类型占比（network：WiFi/5G/4G/...）
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name meituan \
  --group-by network
```

返回 `data.distribution` 是「维度值 → 详情」的 map，每个维度值的 `percent` 即占比、`value`（= `valueMap.distinctCount`）即去重数、`totalValue` 即全量分母。**回复时默认只报 `percent` 占比**，去重数的给出条件与表述方式见上方「去重数表述与输出规范」。

**场景 3——查全量版本分布（看各版本占比）：**

```bash
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name meituan \
  --group-by appVersion
```

需要自己算「≥ 某版本」覆盖率时（一般用场景 1 即可）：把版本号 ≥ 目标版本的 `value` 累加 ÷ `totalValue`（**版本号要按 `.` 分段转数字比较，不能按字符串字典序**）。

**场景 4——单个版本/维度值量级（去重数）查询：** 用 `--filters` 锁定，`value` 即该维度值去重数。仅在用户**明确提出要看去重数/绝对量级**时使用本场景，且回复时必须遵守上方「去重数表述与输出规范」（称「去重数」、附口径说明、提醒不要对外泄露）：

```bash
raptorfe perf metric distribution \
  --metrics-name device-info-v3 --project-name meituan \
  --filters '{"appVersion":["12.49.400"]}'
```

> 数据源可能含极少量脏版本号（如 `99.99.99`），其去重数极小（个位数），对覆盖率结果无实质影响，可忽略。

#### lingxi.pv 去重数查询（lingxiPV 项目，必读合规规则）

Perf 项目 `lingxiPV` 下的 `lingxi.pv` 指标也带设备去重口径，其去重数（`distinct-count`）量级接近官方 DAU，但它是 **Raptor 自己的指标统计口径，不等于官方 DAU**。用户有时会直接点名查询该指标，必须严格遵守以下规则：

> 🔒 **lingxi.pv 合规规则（安全合规红线，输出前必须逐条自检）：**
>
> 1. **用户提到「DAU」时，回复的第一句话必须明确告知：「Raptor 没有 DAU 指标，不支持 DAU 查询」**，然后说明：可以用技术指标（如 `lingxi.pv`）的**设备去重数**做统计，但结果**不等于 DAU 口径、存在差异，只可参考占比**。不允许默默把去重数当 DAU 汇报；
> 2. **输出前自检（不通过必须改写后再输出）**：回复全文——包括标题、小标题、表格表头、行名、对比句、备注——**一个「DAU」字样都不能出现**，一律用「去重数 / 占比」表述；
> 3. **未获用户明确要求时，禁止输出任何去重数绝对值**：包括总量/总数，也包括分版本、分维度的去重数列。展示分布时表格**只保留占比列**；
> 4. 仅当用户**明确要求返回去重数**时才返回，且必须同时附两句：①该数值是 Raptor 自己的指标统计出的设备去重数，**不等于官方 DAU**，仅供内部参考；②该数据仅限内部使用，**请勿对外泄露**。
>
> ❌ **反例（真实违规案例，禁止复现）：** 用户说“查一下鸿蒙 9月15 的 DAU，顺便拆各系统版本占比”，若回复标题写“9月15 DAU”、报出“总量约 971 万”、表格里列出各版本去重数列——即为违规。
> ✅ **正确示范：** 开头第一句“Raptor 没有 DAU 指标，不支持 DAU 查询；可以用设备去重数统计，但不等于 DAU 口径、有差异，只可参考占比”，随后只给各系统版本**占比**表格（无任何绝对值），结尾附“内部数据请勿对外泄露”。

**查询方式：**

```bash
# 先确认指标与可用维度 tag（不确定项目名/指标名时先用 search 核对）
raptorfe perf metric get-tags --appkey PERF --metrics-name lingxi.pv
raptorfe perf metric search --appkey PERF --match "lingxi"

# 用户数占比：按维度分组查去重数占比（只回复 percent，不回复去重数）
raptorfe perf metric distribution \
  --metrics-name lingxi.pv --project-name lingxiPV \
  --group-by appVersion

# 仅用户明确要求去重数时才返回 value（distinct-count 去重数），并附合规提示
raptorfe perf metric distribution \
  --metrics-name lingxi.pv --project-name lingxiPV
```

返回结构与 `device-info-v3` 一致（`data.distribution.<维度值>.value / .percent / .totalValue`，单天数据、默认查前一天，`notes` 会标明实际日期）。若 `--project-name` 报错或无数据，用 `raptorfe crash project list` 核对项目名，仍无果则告知用户暂无数据，**不要伪造占比或去重数**。

---

> **Perf 指标命名规律总结：**
> - `<原子名>` → ATOM，首屏耗时/帧率等原始数据，下钻主指标
> - `<原子名>.ratio` → COMPOSITE，达标率（秒开率等）
> - `<原子名>.score` → ATOM（中间指标），后端算分用，**用户分析时无需关注**
> - `C分数-26年-<栈>` / `R分数-26年` / `F分数-26年` → COMPOSITE，最终展示的体验分数

### Step 2.8：Crash 查询维度字段

`--filter` 的 fieldName 直接透传给后端接口，支持接口所有维度字段。常用字段如下：

| 用户说的 | fieldName | 示例值 |
|---------|-----------|--------|
| 组件 / 涉及组件 | default_component | SAKAlita, MTVodReporter |
| 应用版本 | appVersion | 12.54.401 |
| 设备分级 | deviceLevel | HIGH / MEDIUM / LOW |
| 系统版本 | osVersion | 18.4.1 |
| BU（业务单元） | default_bu_chinese | 外卖业务, 到店业务 |
| BG（业务群组） | default_bg_chinese | 外卖, 到店 |
| MRN bundle | mrn | rn_meishi_food-poi |
| 前后台 | foreground | true / false |
| 频道 | optional_channel | - |
| 网络类型 | net | wifi, 4g |
| 设备型号 | deviceModel | iPhone15,3 |
| 崩溃 message | message | JavaScriptCore |

如需查看某字段的可选值，可用 `raptorfe crash field-suggestions get --field <fieldName> --project <project> --type <type>`。

用户提到的任何其他维度名称，只要合理，均可直接作为 fieldName 尝试传入（接口不识别的字段会被忽略，不会报错）。

⚠️ **严禁使用 matchPhrase 替代 --filter 来过滤组件/版本等字段**，matchPhrase 只用于堆栈关键词搜索。

---

## Step 3：CLI 命令详细参数

### Crash 模块

> ⚠️ **以下示例参数以 `raptorfe <cmd> --help` 为准，如遇 unknown option 先查 help。特别注意 `crash ratio get` 不支持 `--interval` 参数。**

```bash
# 项目列表
raptorfe crash project list

# Crash/ANR 时序（分钟/小时/天级）
raptorfe crash timeseries get \
  --project meituan --type crash \
  --start "2026-03-23 10:00:00" --end "2026-03-23 11:00:00" \
  --interval minute \
  --filter "default_component:MTVodReporter"   # 可多次指定

# 按 BG/BU 业务维度筛选（--filter 支持后端所有维度字段，直接透传）
raptorfe crash timeseries get \
  --project meituan --type anr \
  --start "2026-06-15 00:00:00" --end "2026-06-22 00:00:00" \
  --interval day \
  --filter "default_bg_chinese:外卖" \
  --filter "default_bu_chinese:外卖业务"

# 版本对比时序（不传 appVersion filter 时自动返回 Top 活跃版本）
raptorfe crash timeseries-by-version get \
  --project meituan --type crash \
  --start "2026-03-23 00:00:00" --end "2026-03-30 00:00:00"

# 崩溃率（跨度必须 > 1天，⚠️ ratio get 不支持 --interval 参数）
raptorfe crash ratio get \
  --project meituan --type crash \
  --start "2026-03-23 00:00:00" --end "2026-03-30 00:00:00"

# 版本崩溃率
raptorfe crash ratio-by-version get \
  --project meituan --type crash \
  --start "2026-03-23 00:00:00" --end "2026-03-30 00:00:00"

# 聚类概览
raptorfe crash static get --project meituan --type crash

# 聚类列表（⚠️ crash/anr 类型时间跨度不能超过 1 天，watchdog 无此限制）
raptorfe crash cluster list \
  --project meituan --type crash \
  --start "2026-03-23 00:00:00" --end "2026-03-23 23:59:59"

# Crash 详情（需要 uuid 和秒级时间戳）
raptorfe crash detail get \
  --id "GUID-B4A3556B-EDE8-4D81-A9FB-F151786762B9" \
  --ts 1774419797 --project meituan

# Crash 聚类记录列表（按 message 聚合，返回聚类概览）
raptorfe crash records list \
  --project meituan --type crash \
  --start "2026-03-23 00:00:00" --end "2026-03-24 00:00:00" \
  --size 20 \
  --eq "default_component,MTVodReporter"   # 多值用||分隔，可多次指定

# 批量查询某聚类下的原始事件记录（含 deviceId、UUID，用于后续 detail get）
raptorfe crash detail list \
  --project meituan \
  --start "2026-03-23 00:00:00" --end "2026-03-24 00:00:00" \
  --eq "message,<崩溃message>" \
  --size 10 --excludes log

# 发版事件列表（直接从 Raptor 后端获取，无需 eventcenter）
raptorfe crash events list --project meituan \
  --start "2026-04-01 00:00" --end "2026-04-24 23:59" \
  --type "应用全量发版,应用独立灰度发版"   # 可选，默认全量+补丁+灰度

# 其他
raptorfe crash reason-ranking get   # 崩溃原因排行
raptorfe crash device-model get     # 机型分布（⚠️ 必须传 --start/--end）
raptorfe crash component list       # 组件列表
raptorfe crash field-suggestions get  # 字段值枚举（如版本列表）
```

**--filter 与 --eq 格式区分：**
- `timeseries` / `ratio` 用 `--filter "fieldName:val1,val2"`
- `records list` 用 `--eq "fieldName,val1||val2"`

**输出格式**：查询 Crash 时同时输出率和次数，合并为一张表。

### Perf 模块

> ⚠️ **RCF总分/R分数/C分数/F分数等 composite 聚合指标已按全量口径计算，查询时不要传 `--filters app/os`，否则结果恒为 0。**

```bash
# 搜索指标获取数字 ID
raptorfe perf metric search --appkey PERF --match "ffp_native"

# 查询指标支持的维度 tag
raptorfe perf metric get-tags \
  --appkey PERF --metrics-name 9751 --metrics-type atom

# 查询指标时序（DAY 粒度）
raptorfe perf metric get-trend \
  --metrics-name 9751 \
  --start-time "2026-03-16" --end-time "2026-03-23" \
  --agg DAY --metrics-type composite --methods avg,totalCount

# 查询指标时序（分钟粒度）
raptorfe perf metric get-trend \
  --metrics-name 9751 \
  --start-time "2026-03-30 10:00:00" --end-time "2026-03-30 11:00:00" \
  --agg ONE_MINUTE --metrics-type atom --methods avg

# 维度下钻分析（atom 指标，不需要 --other-metrics）
raptorfe perf metric dimension-analyse \
  --metrics-name 9751 \
  --start-time "2026-03-16" --end-time "2026-03-23" \
  --tag-names "content_type_category,appVersion" \
  --agg DAY --metrics-type atom --methods avg --limit 20

# 维度下钻分析（同时查 atom + composite，⚠️ 必须以 atom 为主，composite 放 --other-metrics）
# 正确用法：--metrics-name 传原子指标（atom），--metrics-type atom
#           --other-metrics 传附加的复合指标 ID，逗号分隔（如 ffp_mrn.ratio,c17949）
# 例：查 ffp_mrn（atom）+ ffp_mrn.ratio（composite）+ C分数-26年-MRN（c17949，composite）
raptorfe perf metric dimension-analyse \
  --metrics-name ffp_mrn \
  --start-time "2026-04-26" --end-time "2026-04-28" \
  --tag-names "fetch_bridge_type" \
  --filters '{"app":["com.sankuai.meituan"]}' \
  --agg DAY --metrics-type atom --methods avg --limit 20 \
  --other-metrics "ffp_mrn.ratio,c17949"

# 获取 tag 的可选值
raptorfe perf metric get-tag-values \
  --project-name meituan --metrics-name 9751 --tag appVersion \
  --start-time "2026-03-16" --end-time "2026-03-23" --agg DAY

# 分布查询
raptorfe perf metric get-buckets \
  --project-name meituan --metrics-name 9751 \
  --start-time "2026-03-16" --end-time "2026-03-23" \
  --min 0 --max 5000 --bucket-num 10

# 查询复合指标的组成详情（公式、子指标原子 ID、预设 filters）
raptorfe perf metric get-compound-detail --appkey PERF --metric-ids c10295
# 支持批量：--metric-ids c10295,c17949

# APP/appkey 列表
raptorfe perf app list
raptorfe perf appkey get
```

> ⚠️ `--metrics-name` 是**数字 ID**（从 `search` 返回的 `id` 字段），不是指标名称字符串。

> ⚠️ **`dimension-analyse` 的 `--other-metrics` 用法：**
> - `--metrics-name` 必须传**原子指标**（atom，纯数字 ID 或指标名），`--metrics-type atom`
> - `--other-metrics` 传**附加的复合指标 ID 列表**（逗号分隔），如 `ffp_mrn.ratio,c17949`
> - 即：以 atom 为主驱动下钻，composite 作为附加一起聚合，**不能以 composite 为主**
> - 示例：查 C分数-26年-MRN（c17949）的维度分布 → `--metrics-name ffp_mrn --metrics-type atom --other-metrics c17949`

> ⚠️ **复合指标（c 前缀）下钻的完整流程：**
> 1. 复合指标不能直接做 `dimension-analyse`（会返回空数据）
> 2. 先用 `get-compound-detail` 查出底层原子指标 ID：
>    ```bash
>    raptorfe perf metric get-compound-detail --appkey PERF --metric-ids c10295
>    ```
>    返回中 `config.A.metricId` 就是原子指标数字 ID（如 98468）
> 3. 再用原子指标做下钻，把复合指标 ID 放入 `--other-metrics`：
>    ```bash
>    raptorfe perf metric dimension-analyse \
>      --metrics-name 98468 --metrics-type atom \
>      --other-metrics "c10295" \
>      --tag-names "appVersion" \
>      --agg DAY --start-time "2026-04-22" --end-time "2026-04-29"
>    ```
> 4. `get-compound-detail` 返回的 `isMerge` 字段：
>    - `"true"`：子指标共享 filters，取任一子指标的 metricId 做下钻即可
>    - `"false"`：子指标独立过滤，需要用 `--metrics-list` 参数传各子指标独立的 filters（高级查询模式）

### 老 Raptor 移动端自定义指标（metric 模块）

```bash
raptorfe metric list --app-id 10
raptorfe metric get-tags --app-id 10 --metric "bizpay.sdk.load"
raptorfe metric get-trend \
  --app-id 10 --metric "bizpay.sdk.load" \
  --start-str "2026-03-16 00:00" --end-str "2026-03-23 23:59"
```

### 老 Raptor 移动端端到端（mobile 模块）

```bash
raptorfe mobile project list
raptorfe mobile app list

# 获取项目下所有 API
raptorfe mobile api get-by-project --project-id 859

# API 趋势（时间支持毫秒时间戳或日期字符串）
raptorfe mobile api get-trend \
  --api-id 190 --project-id 859 \
  --start-time 1743436800000 --end-time 1743955200000 \
  --time-type day \
  --type netWorkSuccess \    # request | netWorkSuccess | businessSuccess | delay | summary
  --source 10                # App 过滤，美团主APP=10（不是 appId）

# API 延迟分布
raptorfe mobile api get-delay \
  --api-id 190 --project-id 859 \
  --start-time 1743436800000 --end-time 1743955200000 \
  --time-type day --type summary

# 请求分桶
raptorfe mobile api get-request-bucket \
  --api-id 190 --project-id 859 \
  --start-time 1743436800000 --end-time 1743955200000 \
  --time-type day --group-by-field source

# 内置枚举
raptorfe mobile const lookup
raptorfe mobile city get-provinces
```

### 老 Raptor web 端（web 模块）

```bash
# 项目查询
raptorfe web project search

# 性能趋势（时间支持毫秒时间戳或日期字符串）
raptorfe web speed get-trend \
  --project <项目名> --start-time <time> --end-time <time>
raptorfe web speed get-dimension-dist
raptorfe web speed get-pv
raptorfe web speed get-summary

# 异常
raptorfe web error get-trend
raptorfe web error get-groups
raptorfe web error get-log

# 请求
raptorfe web request get-trend
raptorfe web request get-distribution

# PV
raptorfe web pv get-trend

# 自定义指标（时间用 start-str/end-str）
raptorfe web custom-metric list
raptorfe web custom-metric get-trend \
  --project <项目名> --metric <指标名> \
  --start-str "2026-03-16 00:00" --end-str "2026-03-23 23:59"
```

### 老 Raptor 小程序（mp 模块）

```bash
raptorfe mp project list

# 性能趋势（时间支持毫秒时间戳或日期字符串）
raptorfe mp speed get-trend \
  --project <项目名> --start-time <time> --end-time <time>

# 请求
raptorfe mp request get-trend
raptorfe mp request get-sub-trend

# 异常
raptorfe mp error get-trend
raptorfe mp error get-summary

# PV
raptorfe mp pv get-trend

# 自定义指标（时间用 start-str/end-str）
raptorfe mp custom-metric list
raptorfe mp custom-metric get-trend \
  --project <项目名> --metric <指标名> \
  --start-str "2026-03-16 00:00" --end-str "2026-03-23 23:59"

# 维度枚举
raptorfe mp meta get-dimensions
raptorfe mp meta get-input-types
```

### 其他模块

```bash
# 劫持报表（时间支持毫秒时间戳或日期字符串）
raptorfe hijack const list
raptorfe hijack trend get --start-time <time> --end-time <time>
raptorfe hijack summary get --start-time <time> --end-time <time>

# 域名监控（时间支持毫秒时间戳或日期字符串）
raptorfe domain list
raptorfe domain trend get --start-time <time> --end-time <time>
raptorfe domain summary get --start-time <time> --end-time <time>
raptorfe domain cluster get
```

---

## Step 4：结果输出

> ⚠️ **大 JSON 处理提示（重要）**：`raptorfe --raw` 或 `raptorfe -o json` 返回的 JSON 可能较大，直接保留在上下文中会导致后续步骤 input 膨胀、cache 失效。建议在 bash 中用 `python -c` 或 `jq` 提取关键字段（如 `avg`、`value`、`dt`、`total`）后再回传给模型：
> ```bash
> # 示例：提取趋势数据中的日期和均值
> raptorfe perf metric get-trend --metrics-name 9751 --agg DAY ... -o json | \
>   python3 -c "import sys,json; [print(f\"{d['dt']}: {d['avg']}\") for d in json.load(sys.stdin)['data']['trend']]"
> ```

查询到数据后，以**表格 + 趋势分析**形式输出：

- 表格展示原始数据
- 对比同比 7 天前/1 小时前，标注明显异常
- Crash 同时输出率和次数合并为一张表

---

## 多轮交互示例

**示例1：Crash 率**
```
用户：查一下最近7天美团 Android 的 Crash 率
→ raptorfe crash ratio get --project android_platform_monitor --type crash \
    --start "2026-03-23 00:00:00" --end "2026-03-30 00:00:00"
```

**示例2：Native 秒开率**
```
用户：查美团最近7天 Native 秒开率
→ ffp_native.ratio，COMPOSITE
→ raptorfe perf metric search --appkey PERF --match "ffp_native.ratio"  # 获取 id
→ raptorfe perf metric get-trend --metrics-name <id> \
    --start-time "2026-03-23" --end-time "2026-03-30" \
    --agg DAY --metrics-type composite --methods avg
```

**示例3：5s 白屏率**
```
用户：查美团最近7天 5s 白屏率
→ ppf_WhitePage_on5s，COMPOSITE
→ raptorfe perf metric search --appkey PERF --match "ppf_WhitePage_on5s"
→ raptorfe perf metric get-trend --metrics-name <id> \
    --start-time "2026-03-23" --end-time "2026-03-30" \
    --agg DAY --metrics-type composite --methods avg
```

**示例4：带组件过滤的 Crash**
```
用户：查 MTVodReporter 组件最近7天 Crash 率
→ raptorfe crash ratio get --project meituan --type crash \
    --start "2026-03-23 00:00:00" --end "2026-03-30 00:00:00" \
    --filter "default_component:MTVodReporter"
```

**示例5：容器驼峰命名指标**
```
用户：查一下 MRNPageLoadSuccess 最近7天趋势
→ 驼峰 + MRN 前缀 → 老 Raptor 容器，appId=10000
→ raptorfe metric get-tags --app-id 10000 --metric "MRNPageLoadSuccess"
→ raptorfe metric get-trend --app-id 10000 --metric "MRNPageLoadSuccess" \
    --start-str "2026-03-23 00:00" --end-str "2026-03-30 23:59"
```

**示例6：ID 查询 / 万能钥匙 → 直接拒绝**
```
用户：帮我查一下 uuid 3BB59464-7482-4A1D-A223-CCA8A7039474 对应的 userid
→ 命中 ID 查询拒绝规则
→ 回复：「当前不支持 ID 查询功能，请前往 Raptor 万能钥匙（https://raptor.mws.sankuai.com）系统界面中查询。请注意用户隐私，非必要不查询。」
→ 不执行任何命令
```
