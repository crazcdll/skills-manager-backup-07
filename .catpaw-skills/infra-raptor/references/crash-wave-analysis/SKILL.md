---
name: crash-wave-analysis
version: "1.0.0"
description: >
  稳定性指标（Crash / ANR / FOOM）多维度波动分析，定位问题根因。
  支持两种触发方式：①用户明确说"分析"最近 N 天 Crash/ANR/FOOM 趋势/波动；②用户发送 Raptor 页面链接并提出分析诉求（自动解析 URL 参数后重新查询）。
  按版本分布→时间趋势→组件分布→栈顶聚类→设备型号→前后台→多维交叉→根因定位的完整 SOP 流程逐步分析，最终可选调用 infra-app-stability 进行深度堆栈分析。
  覆盖美团/外卖/点评，Android/iOS/HarmonyOS。
  触发词：分析Crash波动、分析ANR趋势、分析FOOM、稳定性指标分析、崩溃率波动分析、崩溃趋势分析、稳定性波动、crash分析、anr分析、foom分析、crash趋势分析、crash波动、ANR波动、FOOM波动。
  注意：如果用户只是简单查询数据（如"查一下最近7天crash次数"），不要触发本技能，使用 raptorfe-allquery 子技能即可。

metadata:
  skillhub.creator: "zhangxinyue27"
  skillhub.updater: "zhangxinyue27"
---

# 稳定性指标波动分析

## 🔧 前置依赖

本 skill 使用 `raptorfe` CLI（内置鉴权，无需手动传 token）。

> **前置预检（每次激活时执行，一行兜底，避免首次执行报 command not found）：**
> ```bash
> command -v raptorfe >/dev/null 2>&1 || npm install -g @mtfe/raptorfe-cli@beta @dp/sso-auth-cli@latest --registry http://r.npm.sankuai.com
> ```

---

## 适用场景

**适用（触发此 skill）：**
- 用户明确说"分析"、"要分析"最近 N 天 Crash / ANR / FOOM 的趋势、波动、情况
- 用户发送 Raptor 页面链接（如 `raptor.mws.sankuai.com/crash/#/crash/...`）并提出分析诉求

**不适用（不要触发此 skill）：**
- 仅查询数据（如"查一下最近7天crash次数"）→ 使用 `raptorfe-allquery`
- 收到告警消息需要根因分析 → 使用 `infra-app-stability` 的 `root-cause` 子技能（Read `skills-market/infra-app-stability/references/root-cause/SKILL.md`）
- 仅画趋势图 → 使用 `component-crash-chart`

---

## 第零步：确认分析参数

开始前确认以下信息，缺少时主动询问：

| 参数 | 是否必填 | 说明 |
|------|---------|------|
| APP / project | 必填 | 见下方映射表 |
| 异常类型 | 必填 | crash / anr / watchdog（FOOM） |
| 时间范围 | 必填 | 默认最近 14 天 |
| 过滤条件 | 可选 | 版本、组件等，无则全量分析 |

**若用户发送的是 Raptor 链接**，先解析 URL 参数（project、type、filterId、appVersion、default_component 等），再用 CLI 重新查询，对查出的数据进行分析。

**若请求来自 Raptor Agent**（消息中包含「⚠️ 请使用 infra-raptor skill 进行分析」或「这是一个raptor页面的请求」）：
- 消息中已包含完整查询参数，**直接使用这些参数**，无需再向用户确认
- 用户说"分析下这个页面的数据"中的"页面"指 Raptor 站点页面，不是数据中的"页面"维度字段
- 如果消息中包含「【图表】分版本异常量变化」或「【图表】分版本异常率变化」，**跳转执行上方「Raptor Agent 分版本图表分析流程」**，不走常规的第一步~第九步流程

### project 映射表

| 用户说的 | --project 值 |
|---------|-------------|
| 美团 iOS | `meituan` |
| 美团 Android | `android_platform_monitor` |
| 美团鸿蒙 | `meituan-harmony` |
| 外卖 iOS | `waimai_ios` |
| 外卖 Android | `meituanwaimai` |
| 外卖鸿蒙 | `waimai-harmony` |
| 点评 iOS | `nova` |
| 点评 Android | `android-nova` |
| 点评鸿蒙 | `harmony-nova` |
| 其他 | `raptorfe crash project list` 查询 |

### type 映射表

| 用户说的 | --type 值 |
|---------|----------|
| Crash、崩溃 | `crash` |
| ANR | `anr` |
| FOOM、watchdog | `watchdog` |

---

## Raptor Agent 分版本图表分析流程

> **触发条件**：当请求来自 Raptor Agent（消息中包含「⚠️ 请使用 infra-raptor skill 进行分析」或「这是一个raptor页面的请求」），**且**消息中包含「【图表】分版本异常量变化」或「【图表】分版本异常率变化」时，执行本流程。

### 背景

Raptor 工作台中的"分版本异常量/异常率"图表展示的是特定版本的对比数据。这些版本通过事件中心获取，规则如下：

1. **最新全量版本**：事件中心时间线中最新的一条 `APP_PUBLISH_FULL` 事件对应的版本号
2. **最新灰度版本**：在最新全量发布时间**之前**最近的一条 `APP_PUBLISH_GRAY` 事件对应的版本号
3. **次新全量版本**：时间线中倒数第二条 `APP_PUBLISH_FULL` 事件对应的版本号
4. **次新灰度版本**：在次新全量发布时间**之前**最近的一条 `APP_PUBLISH_GRAY` 事件对应的版本号

### 执行步骤

#### Step 1: 获取发版事件（优先 `crash events list`）

直接通过 `raptorfe crash events list` 获取发版事件，无需额外 CLI 或鉴权：

```bash
raptorfe crash events list --project <project> \
  --start "<90天前>" --end "<当前时间>" \
  --type "应用全量发版,应用独立灰度发版"
```

> 💡 该命令直接从 Raptor 后端获取发版事件，使用与 raptorfe 相同的鉴权，不依赖 eventcenter CLI。

#### Step 2: 从发版事件中提取4个目标版本

从返回结果中按以下逻辑提取4个版本：

1. 按时间倒序排列所有事件
2. 找到第一条「应用全量发版」→ **最新全量版本**，记录其发布时间 T1
3. 找到时间早于 T1 的第一条「应用独立灰度发版」→ **最新灰度版本**
4. 找到第二条「应用全量发版」→ **次新全量版本**，记录其发布时间 T2
5. 找到时间早于 T2 的第一条「应用独立灰度发版」→ **次新灰度版本**

**提取版本号方法**：从事件的 `title` 字段中提取版本号（格式通常为 `<版本号> 全量发版` 或 `<版本号>灰度发布上线`），取 title 中的第一个数字版本串（如 `12.58.401`）。

> ⚠️ 如果某个版本找不到（如灰度版本不存在），跳过该版本，用找到的版本继续分析。

#### Step 2 Fallback: `crash events list` 返回为空时

如果 `crash events list` 返回空数据（部分项目可能未接入发版事件上报），使用以下替代方案：

**方案 A：直接用 `timeseries-by-version`（推荐）**

不传 appVersion filter 时自动返回 Top 活跃版本数据，从返回结果的 key 中提取版本号：

```bash
raptorfe crash timeseries-by-version get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>"
# 返回结果的 data.data 中的 key 即为 Top 版本号（如 "12.58.401"、"12.59.200" 等）
```

**方案 B：用 `field-suggestions` 获取版本枚举**

```bash
raptorfe crash field-suggestions get \
  --project <project> --type <type> --field appVersion \
  --start "<start>" --end "<end>"
# 返回该时间范围内有数据的所有版本号列表，取前几个即为活跃版本
```

> 💡 替代方案无法区分"全量版本"和"灰度版本"，但能获取到当前活跃的 Top 版本，满足分版本对比分析的需求。

#### Step 3: 用获取到的版本号查询 Crash 数据

根据图表类型选择对应命令：

**分版本异常量变化：**
```bash
raptorfe crash timeseries get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --interval day \
  --filter "appVersion:<版本1>,<版本2>,<版本3>,<版本4>"
```

**分版本异常率变化：**
```bash
raptorfe crash ratio-by-version get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>"
```

> 注意：`ratio-by-version` 命令会返回所有版本数据，结果中只需关注上面获取到的4个版本。如果需要精确过滤，可以使用 `ratio get` 配合 `--filter "appVersion:<版本>"` 逐个版本查询。

#### Step 4: 分析并输出结论

对比4个版本的异常量/异常率趋势，重点分析：
- 最新全量版本 vs 次新全量版本的对比
- 灰度版本的异常表现是否正常
- 是否有版本引入了新的异常

---

## 执行流程

每个维度查询完成后**立即展示结果并给出初步判断**，不要等所有维度都查完再输出。

### 第一步：时间趋势分析

**目的：** 识别异常波动的具体时间点，判断是否与版本发布相关。

```bash
# 整体崩溃数量时序（按天）
raptorfe crash timeseries get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --interval day

# 整体崩溃率时序
raptorfe crash ratio get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>"
```

**分析要点：** 标记异常率明显上升的时间点；结合第二步的版本分布数据，判断波动是否与特定版本相关。

---

### 第二步：版本分布分析

**目的：** 判断异常是否集中在某个或某几个版本。

```bash
# 按版本分组的崩溃数量时序（不传 appVersion filter 时自动返回 Top 版本数据）
raptorfe crash timeseries-by-version get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>"

# 按版本分组的崩溃率时序
raptorfe crash ratio-by-version get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>"
```

> 💡 `timeseries-by-version` 和 `ratio-by-version` 不传 `--filter "appVersion:..."` 时，后端自动返回 Top 活跃版本的数据，无需事先知道版本号。

**分析要点：** 识别异常率突增的版本，重点关注；结合第一步时间趋势，判断突增版本的发布时间。

---

### 第三步：组件分布分析

**目的：** 定位异常是否集中在某个组件或模块。

```bash
# 崩溃原因排行（按 message 聚合，识别高发组件）
raptorfe crash reason-ranking get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --filter "appVersion:<突增版本>"

# 查指定组件的崩溃时序（对高发组件逐一分析）
raptorfe crash timeseries get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --interval day \
  --filter "default_component:<组件名>"
```

**分析要点：** 识别 Top 高发组件；判断是否为新引入问题（结合版本信息）。

---

### 第四步：栈顶聚类分析

**目的：** 进一步定位具体的崩溃/ANR 发生点，提取高频栈顶。

> ⚠️ `crash` 和 `anr` 类型的聚类查询，时间跨度不能超过 1 天（24 小时）。`watchdog`（FOOM）无此限制。

```bash
# 查崩溃聚类列表（crash/anr 限 1 天范围）
raptorfe crash cluster list \
  --project <project> --type <type> \
  --start "<突增当天 00:00:00>" --end "<突增当天 23:59:59>" \
  --filter "appVersion:<突增版本>" \
  --page-size 20

# FOOM（watchdog）支持更长时间范围
raptorfe crash cluster list \
  --project <project> --type watchdog \
  --start "<start>" --end "<end>" \
  --page-size 20
```

**分析要点：** 列出 Top 聚类（按 count 排序），提取高频 message；分析高频栈顶是否为新出现（结合 firstTS 判断）。

---

### 第五步：设备型号分布分析

**目的：** 判断异常是否集中在特定设备型号。

> ⚠️ `device-model get` 必须传 `--start` 和 `--end`，否则后端会返回错误。

```bash
raptorfe crash device-model get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --filter "appVersion:<突增版本>"
```

**分析要点：** 判断是否集中在特定机型，辅助定位硬件相关问题。

---

### 第六步：前后台分布分析

**目的：** 判断异常发生时 App 处于前台还是后台。

> 💡 `records list` 的 `--start/--end` 是可选的（不传默认最近 7 天），但建议明确传入以聚焦分析时间范围。

```bash
# 查崩溃记录（含前后台字段）
raptorfe crash records list \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --eq "appVersion,<突增版本>" \
  --size 50 --excludes log
```

**分析要点：** 统计前台、后台异常的次数和占比；结合业务场景排查。

---

### 第七步：多维交叉分析

**目的：** 通过多维度交叉定位更细粒度的问题。

```bash
# 某版本 + 某组件的崩溃时序
raptorfe crash timeseries get \
  --project <project> --type <type> \
  --start "<start>" --end "<end>" \
  --interval day \
  --filter "appVersion:<突增版本>" \
  --filter "default_component:<高发组件>"

# 某版本 + 某组件的聚类列表
raptorfe crash cluster list \
  --project <project> --type <type> \
  --start "<突增当天 00:00:00>" --end "<突增当天 23:59:59>" \
  --filter "appVersion:<突增版本>" \
  --filter "default_component:<高发组件>" \
  --page-size 20
```

**分析要点：** 结合版本、组件、设备等多维度，分析是否有共同特征；缩小问题范围，为根因定位提供依据。

---

### 第八步：根因定位与输出结论

汇总上述各维度分析结果，按以下模板输出分析报告：

```
# 稳定性指标波动分析报告

## 基本信息
- APP：<APP名称>
- 异常类型：<Crash/ANR/FOOM>
- 分析时间范围：<start> ~ <end>

## 1. 时间趋势
- 整体趋势：<描述>
- 突增时间点：<具体日期>
- 与版本发布的关联：<是否与某版本发布时间吻合>

## 2. 版本分布
- 异常率最高版本：<版本号>（异常率 X%）
- 突增版本：<版本号>，发布时间：<日期>

## 3. 组件分布
- Top 高发组件：<组件名>（占比 X%）
- 新增高发组件：<组件名>（首次出现于 <版本>）

## 4. 栈顶聚类
- Top 聚类：<message>（出现 X 次，首次出现：<时间>）
- 高频栈顶分析：<是否为新问题>

## 5. 设备分布
- 主要影响机型：<机型>（占比 X%）

## 6. 前后台分布
- 前台占比：X%，后台占比：X%

## 7. 多维交叉
- 高风险组合：<版本 + 组件 / 版本 + 机型>
- 交叉分析结论：<说明>

## 8. 根因定位
**初步根因：**
<综合以上分析，初步判断根因为...>

**优化建议：**
1. <建议1>
2. <建议2>
3. <建议3>
```

---

### 第九步：深度日志分析（可选）

输出分析报告后，询问用户是否需要进行深度日志分析：

> "以上是多维度波动分析结果。如需进一步分析具体崩溃堆栈，我可以对至少 5 条日志进行深度堆栈分析。是否继续？"

如果用户确认继续：

1. 从聚类列表中获取 Top 聚类的 `firstTS` 和 `message`
2. 用 `raptorfe crash detail list` 批量获取某聚类下的事件记录（含 deviceId、UUID 等）
3. 用 `raptorfe crash detail get` 获取完整堆栈
4. 调用 `infra-app-stability` 技能对至少 5 条日志进行深度堆栈分析

```bash
# 批量获取某聚类下的事件记录（通过 message 过滤定位聚类）
raptorfe crash detail list \
  --project <project> \
  --start "<start>" --end "<end>" \
  --eq "message,<高频message>" \
  --size 10 --excludes log

# 获取单条崩溃详情（含完整堆栈）
raptorfe crash detail get \
  --id "<crash-uuid>" \
  --ts <firstTS> \
  --project <project>
```

> 💡 **`detail list` vs `records list` 区别**：
> - `detail list`：返回某聚类下的**单条原始事件记录**（含 deviceId、id/UUID、appVersion、crashTime），适合提取具体崩溃 UUID 后调用 `detail get` 查完整堆栈。
> - `records list`：返回按 message **聚合后的聚类数据**（含 count、影响版本等），适合查看聚类概览，不含单条记录的 UUID。

---

### 第十步：代码仓库检索（⚠️ 分析完成后必须执行本步骤判断，禁止跳过）

> 🔴🔴🔴 **强制执行规则**：第九步深度日志分析完成后（或用户拒绝深度日志分析时），**必须立即执行本步骤的场景判断逻辑**。不得以"分析已完成"、"结论已清晰"等理由跳过。未执行本步骤的分析报告视为不完整。

#### 触发场景判断

**场景一：主动触发（强制）**
当分析结论满足以下任一条件时，**直接调用** `infra-codebase` 技能，无需询问用户：
- 堆栈显示为 Native 层崩溃（如 C++/OC/Swift/Kotlin Native 代码）
- 崩溃点为业务自有代码（非系统框架、非三方库）
- 堆栈调用链涉及复杂业务逻辑，需要源码上下文才能理解触发路径
- 根因分析中存在"需要看实现逻辑"、"需确认调用关系"等待定结论

**场景二：询问触发（必做）**
当分析结论已经足够清晰（如系统 API 兼容性问题、明显的空指针、已知三方库 bug 等），**必须**在输出报告后询问用户：

> "以上分析已定位到初步根因。如需进一步查看相关源码实现、调用链或影响面，我可以通过代码仓库检索进行深度源码分析。是否需要？"

> 🔴 **注意**：场景二的询问是**必做动作**，不是可选项。即使根因已清晰，也必须询问用户是否需要源码分析。

#### 执行流程

1. **获取堆栈代码行**：从第九步的深度日志分析中（或重新拉取 1 条崩溃详情），提取崩溃点及关键调用链的代码行信息：

```bash
# 若尚未获取堆栈详情，先拉取 1 条崩溃日志
raptorfe crash detail get \
  --id "<crash-uuid>" \
  --ts <firstTS> \
  --project <project>
```

2. **构造 infra-codebase 调用 prompt**：基于分析结论和堆栈代码行，构造明确的检索请求。Read skill 文件 `skills-market/infra-codebase/SKILL.md` 并按其路由规则执行。

**调用 prompt 模板：**

```
请使用 infra-codebase 技能分析以下崩溃问题的源码：

【分析结论】
{第八步的根因定位结论，如：美团 iOS 12.58.401 版本 WaimaiAddress 组件在页面初始化时触发 NSInvalidArgumentException，崩溃点位于 -[WMAddressManager loadCacheWithCompletion:] 方法}

【关键堆栈】
{从崩溃详情中提取的关键调用链，包含类名、方法名、行号，如：
Frame 0: WaimaiAddress -[WMAddressManager loadCacheWithCompletion:] + 128 (WMAddressManager.m:67)
Frame 1: WaimaiAddress -[WMAddressViewController viewDidLoad] + 256 (WMAddressViewController.m:42)
Frame 2: UIKitCore -[UIViewController _sendViewDidLoadWithAppearanceProxyObjectTaggingEnabled] + 100}

【检索需求】
1. 查看 WMAddressManager loadCacheWithCompletion: 方法的完整实现
2. 分析该方法的调用方和被调用方
3. 评估该崩溃点的影响面（哪些页面/入口会触发此调用链）
```

3. **Read 并执行 infra-codebase 技能**：

```
Read skill 文件：skills-market/infra-codebase/SKILL.md
按 Step 1 路由规则判断使用哪种能力（单仓代码图谱 / 多仓 full-code / 关联 deps）
按 Step 2 确认数据存在并完成查询
```

#### 输出补充

代码仓库检索完成后，将源码分析结果作为补充追加到分析报告中：

```
## 9. 源码分析补充（via infra-codebase）

**崩溃点源码上下文：**
{源码片段及关键逻辑说明}

**调用链分析：**
{调用方/被调用方关系，触发路径}

**影响面评估：**
{哪些入口/页面会命中此崩溃路径}

**修复建议（基于源码）：**
{基于源码分析给出的具体修复方案}
```

---

## CLI 命令速查

### raptorfe crash 核心命令

| 命令 | 用途 |
|------|------|
| `raptorfe crash timeseries get` | 整体崩溃数量时序（支持 filters） |
| `raptorfe crash timeseries-by-version get` | 按版本分组的崩溃数量时序 |
| `raptorfe crash ratio get` | 整体崩溃率时序 |
| `raptorfe crash ratio-by-version get` | 按版本分组的崩溃率时序 |
| `raptorfe crash cluster list` | 崩溃聚类列表（crash/anr 限 1 天，watchdog 不限） |
| `raptorfe crash reason-ranking get` | 崩溃原因排行（按 message 聚合） |
| `raptorfe crash component list` | 获取组件名列表 |
| `raptorfe crash device-model get` | 设备型号分布 |
| `raptorfe crash records list` | 崩溃聚类记录列表（按 message 聚合） |
| `raptorfe crash detail list` | 批量查询某聚类下的原始事件记录（含 deviceId、UUID） |
| `raptorfe crash detail get` | 单条崩溃详情（含完整堆栈） |
| `raptorfe crash field-suggestions get` | 字段值枚举（如版本列表） |
| `raptorfe crash sum-avg get` | 崩溃汇总均值 |
| `raptorfe crash events list` | 发版事件查询（全量/灰度发布时间线） |
| `raptorfe crash project list` | 获取 Crash 项目列表 |

### --filter 支持的字段

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `appVersion` | 版本号 | `--filter "appVersion:12.54.401,12.54.210"` |
| `default_component` | 组件名 | `--filter "default_component:WaimaiAddress"` |
| `deviceLevel` | 设备等级 | `--filter "deviceLevel:HIGH"` |
| `message` | 崩溃 message | `--filter "message:NullPointerException"` |

### crash events list（发版事件查询）

```bash
# 查版本发布事件（全量 + 灰度）
raptorfe crash events list --project <project> \
  --start "<start>" --end "<end>" \
  --type "应用全量发版,应用独立灰度发版"
```

---

## 注意事项

- **分析顺序**：建议先做时间趋势分析，找到突增时间点，再针对突增时间点做版本、组件等维度的深入分析
- **版本过滤**：确定突增版本后，后续各维度分析都应加上 `--filter "appVersion:<突增版本>"` 聚焦问题版本
- **cluster list 时间限制**：`crash` 和 `anr` 类型时间跨度不能超过 1 天；`watchdog`（FOOM）无此限制
- **逐步输出**：每个维度查询完成后立即展示结果，不要等所有维度都查完再输出
