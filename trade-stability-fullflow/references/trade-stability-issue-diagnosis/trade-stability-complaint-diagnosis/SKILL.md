---
name: trade-stability-complaint-diagnosis
description: 交易前端问题诊断专家。作为稳定性全流程第四步「问题诊断路径（路径 B）」的子流程，由 trade-stability-issue-diagnosis 分发调用。适用于 TT工单、客诉、用户反馈等信号。
  覆盖业务线：餐（meishi）、综（gc）、酒（hotel）、景（travel），支持美团/点评 APP、美小/点小程序、H5/i版全端。
  排查流程：读取前序步骤结果 → 匹配页面 → 查日志 → 结合第二步变更分析 → 输出结构化结论。
  技术栈覆盖：DUO、MRN、MAX、小程序、H5；支持 iOS / Android / Harmony。
  用户标识自适应：userId 或手机号走 UUID 查询路径（前端异常 + 后端日志双线并行）；traceId / 订单号 / openId 直接定位后端链路；无标识时直接读取第二步变更结论。
  查询能力：万能钥匙查 UUID、Raptor 前端异常、Logan 端侧日志回捞、后端日志（topic）、git diff 代码分析。
  输入：第一步信息提取结果 + 第二步变更扫描结果。
  输出：结构化排查结论（结论定性、根因日志、关联变更版本、修复建议、负责人）。
  触发词：交易问题排查、线上问题、TT工单、用户反馈、餐综酒景、提单异常、提单失败、支付失败、支付异常、退款问题、页面白屏、功能不可用、userId排查、traceId排查、订单号排查、查UUID、查日志、前端异常排查、bundle问题。
skill-dependencies:
  mtsso-skills-official:
    app_access_token_placeholder: ${app_access_token}
    user_access_token_placeholder: ${user_access_token}
    audience:
      - "60921859"
    prompt: 本技能所需的token 占位符，请参考mtsso-skills-official的相关说明进行获取和注入
---

# 交易前端问题诊断

**定位**：作为全流程第四步「问题诊断路径（路径 B）」子流程，由 [trade-stability-issue-diagnosis](../SKILL.md) 分发调用。适用于 TT 工单、客诉、用户反馈等信号。

**排查流程**：读取前序步骤结果 → 匹配页面 → 查日志 → 结合第二步变更分析 → 输出结论

---

## 前置输入（来自 trade-stability-issue-diagnosis 分发）

> 🚨 **强制依赖**：本 skill 由 [trade-stability-issue-diagnosis](../SKILL.md) 分发调用，必须在第一步和第二步**均完成并输出结果后**才能执行。**所有输入字段必须从前序步骤输出中读取，严禁 AI 自行推断或向用户重复询问已有信息。**

| 输入项 | 必须来自 | 说明 | ⚠️ 强制要求 |
|--------|----------|------|------------|
| 业务线 | **第一步·信息提取结果** | 餐 / 综 / 酒 / 景 | 不得重新询问 |
| 用户标识 | **第一步·信息提取结果** | userId / 手机号 / traceId / 订单号（至少一个） | 无标识时直接读取第二步变更结论 |
| 问题描述 | **第一步·信息提取结果** | 文字描述或截图 | 不得重新询问 |
| 问题时间 | **第一步·信息提取结果** | 格式 YYYY-MM-DD HH:mm | 不得重新询问 |
| 变更扫描结果 | **第二步·变更查询结果** | MCM/Diva 变更列表、相关度、止损建议、最可疑变更 | **发布记录查询直接读取此结果，不再重复查询 Diva** |

---

## 环境检查

> ⚠️ 排查流程中会自动校验并安装/更新 CLI，通常无需手动执行以下命令。仅在自动安装失败时参考。

```bash
# 确保 mtskills 可用
mtskills --version 2>/dev/null || npm i -g @mtfe/mtskills --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
```

各 CLI 工具的详细安装步骤，参见对应排查流程文档中的「环境检查」章节。

---

## 排查流程

> 开始排查前，必须先执行以下命令记录开始时间：
> ```bash
> startTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $startTime
> ```

### 第一步：匹配问题页面

根据**第一步信息提取结果**中的截图或描述，在研发资产映射表中匹配对应页面。

统一从 trade-stability-fullflow/assets/ 读取：

- 餐读取 [assets/food-dev-assets.md](../../assets/food-dev-assets.md) 获取完整映射数据。
- 综读取 [assets/gc-dev-assets.md](../../assets/gc-dev-assets.md) 获取完整映射数据。
- 酒读取 [assets/hotel-dev-assets.md](../../assets/hotel-dev-assets.md) 获取完整映射数据。
- 景读取 [assets/travel-dev-assets.md](../../assets/travel-dev-assets.md) 获取完整映射数据。

**匹配策略**：
1. 优先根据截图特征（标题、按钮、布局）匹配
2. 其次根据关键词匹配（提单→团购提单，支付结果→支付结果页，订单详情→订单详情页，退款→申请退款）
3. 注意区分技术栈版本（DUO/MRN/MAX/小程序/H5），根据客户端信息判断
4. 无法确定时，列出候选页面让用户确认

**获取信息**：页面名称、技术栈、bundle名、仓库链接、diva发布链接、projectId、前端raptor异常链接、后端日志 topic（可能有多个）

---

### 【子步骤输出】UUID 查询结果（如有）

完成 UUID 查询后，输出：

```
用户信息：userId={xxx}  UUID={xxx}（美团App）/ UUID={xxx}（点评App）
```

---

### 第二步：查询日志 / 代码分析

> 💡 本步中的「第二步变更扫描结果」指的是 **trade-stability-change-query** 前置步骤的输出，并非本 Skill 内部命名的第二步。不要混淆。

**首先按以下决策树确定执行路径，再进入对应流程：**

```
有用户标识（userId / 手机号 / traceId / 订单号 / dealID / openID）？
  ├─ 是
  │    第二步变更扫描有 Diva 变更？
  │    ├─ 是 → 线路 A（日志查询）+ 线路 B（变更代码分析）并行
  │    └─ 否 → 线路 A（日志查询）
  │              ↓ 日志无结论，问题判断与前端代码相关？
  │              ├─ 是 → 追加线路 C（clone master 代码分析）
  │              └─ 否 → 进入第三步汇总分析
  └─ 否（无任何用户标识）
       第二步变更扫描有 Diva 变更？
       ├─ 是 → 直接线路 B（变更代码分析），跳过线路 A
       └─ 否
            问题描述判断与前端代码相关（页面渲染/交互/功能缺失等）？
            ├─ 是 → 直接线路 C（clone master 代码分析）
            └─ 否 → 直接进入第三步汇总分析（无法定位）
```

> ⚠️ 有用户标识时，线路 A 与线路 B **必须并行启动**，任意一路得出明确结论即可停止等待，直接进入第三步。

**「问题与前端代码相关」判断标准**（符合任一条即为相关）：
- 问题描述涉及页面功能缺失、交互异常、UI 渲染错误（如「没有下拉刷新」「按钮消失」「页面空白」）
- 第二步变更扫描虽无 Diva 变更，但问题已持续较久（可能是旧版 master 代码本身存在问题）
- 问题无后端接口报错嫌疑（纯前端交互/展示问题）

---

**移动端 APP（美团 APP / 点评 APP / DUO 转 H5 / MAX 转 H5）**：

读取 [references/app-client-investigation.md](references/app-client-investigation.md) 执行排查，按上方决策树选择线路：
- **线路 A**：userId 或手机号 → A1 查前端异常 → A2 查后端日志；traceId / 订单号 / dealID / openID → 直接 A2 查后端日志
- **线路 B**：仅有 Diva 变更时执行，完整步骤见公共文档 [code-analysis.md](../../../references/code-analysis.md)
- **线路 C**：无 Diva 变更、问题判断与代码相关时执行，完整步骤见 [references/app-client-investigation.md](references/app-client-investigation.md#线路-c)

**小程序（美小 / 点小）**：

读取 [references/miniapp-investigation.md](references/miniapp-investigation.md) 执行排查：
- 提供了 **userId / 手机号 / traceId / 订单号 / dealID / openID** → 线路 A（前端异常 + 后端日志），同时若有变更并行执行线路 B；日志无结论且问题与代码相关时追加线路 C
- **以上均未提供 + 有变更** → 直接线路 B 代码分析
- **以上均未提供 + 无变更 + 问题与代码相关** → 直接线路 C
- **以上均未提供 + 无变更 + 问题与代码无关** → 直接进入第三步汇总分析（无法定位）

**H5 / i 版**：

读取 [references/h5-client-investigation.md](references/h5-client-investigation.md) 执行排查：
- 提供了 **userId / 手机号 / traceId / 订单号 / dealID / openID** → 线路 A（后端日志），同时若有变更并行执行线路 B；日志无结论且问题与代码相关时追加线路 C
- **以上均未提供 + 有变更** → 直接线路 B 代码分析
- **以上均未提供 + 无变更 + 问题与代码相关** → 直接线路 C
- **以上均未提供 + 无变更 + 问题与代码无关** → 直接进入第三步汇总分析（无法定位）

---

### 第三步：汇总分析

> 💡 这里的「第二步变更扫描结果」同样指前置步骤 (trade-stability-change-query) 的输出。

结合日志查询结果与**第二步变更扫描结果**进行综合分析：

| 情况 | 处理方式 |
|------|---------|
| 日志有明确报错，且与第二步变更相关 | 变更引入，记录错误信息 + 关联变更版本，进入输出 |
| 日志有明确报错，与变更无关 | 代码Bug或依赖异常，记录错误信息，进入输出 |
| 日志无结论，第二步有高相关度变更 | 以变更为根因，进入输出 |
| 日志无结论，第二步无相关变更 | 无法定位，参考辅助工具扩大排查范围（见下方） |

**无法定位时**：读取 [references/useful-links.md](references/useful-links.md)，根据问题类型推荐对应工具链接供用户进一步排查：
- 订单相关问题 → 订单查询 / 订单全景
- 疑似风控拦截 → 风控查询 / 反扒查询
- 端侧日志缺失 → Logan 回捞 / 小程序实时日志
- 网关层问题 → 网关日志
- i版问题 → i版日志查询 / i版 raptor 前端错误

---

### 第四步：输出排查结论

严格按以下格式输出，**必须**使用表格格式，不得省略。**输出前，必须先执行以下命令获取结束时间并计算耗时**：

```bash
endTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $endTime
```

> ⚠️ 严禁使用估算时间，完成时间必须来自上方 `date` 命令的真实输出。
>
> 💡 **耗时计算**：用上方得到的 endTime 减去排查流程开始时记录的 startTime，精确到分钟，格式如「约 X 分钟」。

🔎 **第四步【路径B】：排查结论**（完成时间：{endTime}  耗时：{约 X 分钟}）

**结论定性**：✅ 有效问题 / ❌ 无效问题（误报）/ ⚠️ 待进一步确认

| 字段 | 内容 |
|------|------|
| 用户信息 | UUID={xxx} / userId={xxx}（来自第一步） |
| 问题时间 | YYYY-MM-DD HH:mm（来自第一步） |
| 问题页面 | {页面名} / {技术栈} / {bundle名} |
| 仓库地址 | {仓库链接} |
| 前端异常 | {Raptor异常描述 或「无记录」} |
| 后端日志 | {关键错误信息 + traceId 或「无记录」} |
| 根因类型 | 变更引入 / 代码Bug / 依赖异常 / 无法定位 |
| 根因说明 | {详细说明，包含代码路径/接口/配置Key} |
| 关联变更 | {版本号 + 发布时间（来自第二步）或「无关联变更」} |
| 变更内容 | {变更组件/代码描述（DUO 填组件名+版本，MRN/MAX 填变更文件+摘要）} |
| 修复方向 | 前端问题 → {代码路径 + 修复方案} / 后端问题 → traceId={xxx} |
| 负责人 | 餐/毕杰涛  综/徐俊  酒/鲍立磊  景/王松 |
| **耗时** | **约 {X} 分钟**（从开始问题诊断到完成结论输出） |

> ⚠️ 若无法定位根因，在「根因说明」中列出已排查范围，并在表格下方附上推荐的辅助工具链接（来自 useful-links.md）。

➡️ **进入第五步：{代码修复 / 后端通知}**

---

## 注意事项

- 移动端 APP 日志查询完成后，直接结合第二步变更扫描结果综合分析，**不再重复查询 Diva 发布记录**
- DUO 页面代码分析优先分析 componentsMap.json，MRN/MAX 页面直接 git diff 全量代码
- 所有仓库 clone 到 `/Users/All_deal_project/` 目录下
