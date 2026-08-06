---
name: trade-stability-change-query
description: 交易前端变更查询专家。作为稳定性全流程第二步，在问题时间点前后查询所有相关变更，为止损和排查提供依据。
  支持两类变更查询：MCM 前端代码发布（必查）、Diva Bundle 发布（必查）。
  核心能力：并行查询 MCM + Diva → 判断变更相关度（高/中/低）→ 给出止损建议 → 输出最可疑变更。
  输入：业务线、Bundle名、问题时间（来自第一步信息提取结果）。
  输出：变更扫描结果（各系统变更列表、相关度评级、止损建议、最可疑变更）。
  注意：MCM 查询的是前端团队的代码发布变更，查到变更后在报告中体现变更信息即可，无需执行后端回滚操作。
  触发词：查变更、变更查询、查发布记录、MCM查询、Diva查询。
skill-dependencies:
  mtsso-skills-official:
    app_access_token_placeholder: ${app_access_token}
    user_access_token_placeholder: ${user_access_token}
    audience:
      - "60921859"
    prompt: 本技能所需的token 占位符，请参考mtsso-skills-official的相关说明进行获取和注入
---

# 变更查询规则
## 前置输入

> 🚨 **强制依赖**：本 skill 必须在 [trade-stability-information-fetch](../trade-stability-information-fetch/SKILL.md) **完成并输出结果后**才能执行。
> - 若当前上下文中**已有**第一步信息提取结果 → 直接读取字段，进入变更查询
> - 若当前上下文中**没有**第一步信息提取结果 → **必须先执行信息提取**，获得结果后再继续

本 skill 作为全流程第二步执行，输入来自**第一步信息提取结果**，直接读取以下字段：

| 字段 | 用途 |
|------|------|
| 业务线 | 判断变更相关度时的业务范围 |
| Bundle / 页面 | Diva 查询的目标 bundle 名；MCM 过滤相关变更的关键词 |
| 问题时间 | 变更时间窗口的基准点（问题时间前 24 小时） |
| Appkey | MCM 查询结果中过滤相关服务变更的依据 |

> ⚠️ **执行原则**：MCM 和 Diva 必须**并行**发起，不得串行等待。两路都完成后再做综合判断，结果统一在最后输出。

> 🚧 **Horn 配置变更查询和 AB 实验变更查询暂不执行**，如需查询请手动访问 [Horn 配置平台](aHR0cHM6Ly9ob3JuLnNhbmt1YWkuY29tL3dvcmtzcGFjZQ==) 和 [Arena AB实验平台](aHR0cHM6Ly9hcmVuYS5zYW5rdWFpLmNvbQ==)。

---

## 🚨 强制约束（违反即视为流程错误）

1. **MCM 和 Diva 两路查询必须全部完成**，才能输出第二步结果。任何一路失败必须立即走兜底方案，**不得以「CLI 失效」「token 过期」为由跳过**。
2. **第二步结果必须完整输出**（按文末格式），才能进入第三步。禁止在输出前执行任何第三步/第四步的操作（包括查 UUID、查日志等）。
3. **Diva fetch 失败时**，必须立即切换 CLI 兜底，完成查询后补入结果，不得标注「未查询成功」后跳过。
4. **MCM 认证失败时**，必须执行 `mcm login --mis {mis_id}` 完成认证后重试，不得跳过。
5. **严禁在本步骤分析代码**：第二步只负责「找到哪个版本上线了 + 确认发布时间」，**不得**打开 commitUrl、访问 PR 页面、查看 diff、分析任何代码改动内容。commitUrl 仅作为字段记录在输出中，供第四步使用。代码分析属于**第四步**排查根因的职责。

---

开始执行第一步前，先执行以下命令，记录开始时间startTime
```bash
startTime "+%Y-%m-%d %H:%M:%S"
```

## 第一步、【必查】MCM 前端代码发布


**查询对象**：前端团队的代码发布变更（查到变更后在报告中体现变更信息即可，无需执行后端回滚操作）

**查询方式**：使用 `mcm-cli` 命令行工具查询变更日历。

### 环境检查（首次使用前执行一次）

```bash
# 检查是否已安装
mcm --version 2>/dev/null || echo "missing"

# 若 missing，安装最新版
npm install -g @dp/mcm-cli@latest --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t

# 检查认证状态
mcm whoami
```

- `mcm whoami` 返回正常用户信息 → 直接查询
- 返回未认证 / 401 → **必须**执行 `mcm login --mis {mis_id}`（需在大象 App 确认授权），认证成功后重试，**不得跳过**

### 查询命令

```bash
mcm plan calendar \
  --org 88888-153262-114609-114621-40010700 \
  --start "{问题时间前 24 小时，格式: yyyy-MM-dd HH:mm:ss}" \
  --end   "{问题时间，格式: yyyy-MM-dd HH:mm:ss}"
```

**示例**（问题时间为 2026-04-24 13:44）：

```bash
mcm plan calendar \
  --org 88888-153262-114609-114621-40010700 \
  --start "2026-04-23 13:44:00" \
  --end   "2026-04-24 13:44:00"
```

> ⚠️ 时间格式必须为 `yyyy-MM-dd HH:mm:ss`，不支持 ISO 8601 格式。

**返回结果关键字段**：

| 字段 | 说明 |
|------|------|
| `planName` / `name` | 变更计划名称 |
| `appKey` | 变更涉及的服务 Appkey |
| `creator` / `operator` | 发布人 mis_id |
| `planStartTime` / `startTime` | 变更开始时间 |
| `planEndTime` / `endTime` | 变更结束时间 |
| `status` | 计划状态（RUNNING / DONE / WAIT_RUNNING 等） |
| `planId` / `id` | 变更计划 ID，可用于 `mcm plan detail <id>` 查详情 |

**兜底方式**（mcm-cli 不可用时，用浏览器打开）：

```
aHR0cHM6Ly9tY20ubXdzLnNhbmt1YWkuY29tLyMvcGxhbi1jYWxlbmRhcj9zdGF0dXNMaXN0PSZyaXNrTGV2ZWxMaXN0PSVFOSVBQiU5OCVFOSVBMyU4RSVFOSU5OSVBOSwlRTQlQkQlOEUlRTklQTMlOEUlRTklOTklQTkmY2hhbmdlTW9kZT0mb3JnUGF0aD04ODg4OC0xNTMyNjItMTE0NjA5LTExNDYyMS00MDAxMDcwMCZwbGFuU3RhcnRUaW1lR3RlPXvlvIDlp4vml7bpl7R9JnBsYW5TdGFydFRpbWVMdGU9e+e7k+adn+aXtumXtH0=
```

时间格式：`YYYY-MM-DD HH:mm:ss`

---

## 第二步、【必查】Diva MRN Bundle 发布

**查询对象**：前端 MRN Bundle 发布记录

> ✅ **优先方案**：先用 `navigate` 跳到 Diva 域建立 SSO 上下文，再用 `evaluate` 调用相对路径 API（自动携带 Cookie）。**无需 CLI token，无需手动登录。**

### Step 0：导航到 Diva 域（每次查询前必须执行）

```bash
catdesk browser-action '{"action":"navigate","url":"aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29t"}'
```

> ⚠️ 必须等 navigate 返回 `success: true` 后，再执行后续 evaluate 命令。否则 Cookie 未就绪，API 会返回 HTML 登录页。

### Step 1：获取版本列表，判断问题时间前 24 小时内是否有上线版本

```bash
catdesk browser-action '{"action":"evaluate","script":"fetch(atob(\"L2FwaS9idW5kbGUvbGlzdFZlcnNpb24=\")+\"?bundleName={bundleName}&env=prod&keyword=&pageIndex=1&pageSize=20\").then(r=>r.json()).then(d=>JSON.stringify(d))"}'
```

**返回结果关键字段**（`data.list[]` 数组，按 `latestUpdateTime` 降序排列）：

| 字段 | 说明 |
|------|------|
| `version` | 版本号（如 `0.51.0`） |
| `latestUpdateTime` | **全量完成时间**（ISO 8601，UTC），直接用于与问题时间对比 |
| `packUser` | 打包人 mis_id |
| `packUserInfo.name` | 打包人姓名 |
| `ruleList[].platform` | 平台（Android / iOS / HarmonyOS） |
| `ruleList[].bundleVersionStatus` | 版本状态（5=在线，其他=非在线） |
| `commitUrl` | **commit 链接**（指向 dev.sankuai.com 代码仓库的具体 commit） |
| `commentText` | commit 信息（含 branch / sprint / task / fedo 链接等） |
| `mrnBaseType` | MRN 架构版本（3.x 旧架构 / 5.x+ 新架构） |

**筛选逻辑**：直接取列表第一条（最新版本），检查其 `latestUpdateTime` 是否在问题时间前 24 小时内，且至少一个平台 `bundleVersionStatus=5`（在线）。

> 🛑 **强制卡点（必须严格执行，不得绕过）**：
>
> - 若最新版本的 `latestUpdateTime` 距问题时间 **> 24 小时** → **立即判定为「无近期 Diva 变更」，直接跳至输出阶段**。**严禁继续执行 Step 2**，无论任何理由（包括「确认一下」「保险起见」等），均不得调用分阶段发布接口。
> - 若最新版本的 `latestUpdateTime` 距问题时间 **≤ 24 小时** → **必须**继续执行 Step 2，获取分阶段发布开始时间，以该时间作为最终判断基准。

### Step 2：获取目标版本的分阶段发布开始时间（⚠️ 仅当 latestUpdateTime ≤ 24 小时时才可执行，否则严禁调用）

> `latestUpdateTime` 是全量完成时间，分阶段发布**开始**时间需通过任务接口单独获取，作为与问题时间对比的实际基准。

**2a. 获取该版本的 PHASED_PUBLISH 任务列表**

```bash
catdesk browser-action '{"action":"evaluate","script":"fetch(atob(\"L2FwaS9wcGwvdGFzay9saXN0VmVyc2lvbkRldGFpbFRhc2tz\")+\"?bundleName={bundleName}&version={version}&env=prod\").then(r=>r.json()).then(d=>{const arr=d.data||d.list||d;const tasks=Array.isArray(arr)?arr:[];const phased=tasks.filter(t=>t.taskType==\"PHASED_PUBLISH\");return JSON.stringify(phased.map(t=>({id:t.id,platform:t.platform,app:t.app,createTime:t.createTime,taskStatus:t.taskStatus})))})"}'
```

**2b. 查发布任务详情，获取分阶段发布节点的 startTime**

```bash
# 对每个平台的 PHASED_PUBLISH 任务分别执行，{taskId} 取 2a 返回的 id 字段
catdesk browser-action '{"action":"evaluate","script":"fetch(atob(\"L2FwaS9wcGwvdGFzay9kZXRhaWw=\")+\"?id={taskId}\").then(r=>r.json()).then(d=>{const nodes=d.data.nodes;return JSON.stringify({taskStartTime:d.data.startTime,taskEndTime:d.data.endTime,nodes:nodes.map(n=>({name:n.nodeName,type:n.nodeType,start:n.startTime,end:n.endTime,status:n.nodeStatus}))})})"}'
```

**关键节点说明**（`nodes[]` 数组）：

| nodeType | nodeName | 说明 |
|----------|----------|---------|
| `SAVE_RULE` | 存储发布规则 | 任务提交时间 |
| `APPROVAL` | 审批 | 审批通过时间 |
| `WAITING` | 分阶段发布 | ⭐ **分阶段发布开始时间**（`startTime`），bundle 真正开始下发用户的时刻，**以此作为判断基准** |
| `PUBLISHING` | 发布完成 | 全量完成时间，对应 `latestUpdateTime` |

### Step 3：CLI 兜底方案（navigate + evaluate 均失败时使用）

```bash
# 懒更新 diva CLI
LOCAL=$(node -e "try{console.log(require('$(npm root -g)/@mtfe/infra-diva-cli/package.json').version)}catch(e){console.log('')}" 2>/dev/null)
REMOTE=$(npm view @mtfe/infra-diva-cli version --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t 2>/dev/null)
if [ "$LOCAL" != "$REMOTE" ]; then
  npm install -g @mtfe/infra-diva-cli@latest --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t --quiet
fi

# 查询 bundle 发布记录（必须用 --name 参数）
diva bundle get --name {bundleName}
```

> ⚠️ CLI 返回非 JSON 内容（token 失效、网络错误等）时，**必须**回到 navigate + evaluate 方案重试，**不得**以「CLI 失效」为由跳过。

---

## 第三步、变更相关性判断矩阵

> **判断基准选择**：
> - `latestUpdateTime` 距问题时间 **> 24 小时** → 🛑 **直接判定无近期变更 🟢，禁止查分阶段发布时间，直接进入输出**
> - `latestUpdateTime` 距问题时间 **≤ 24 小时** → 以**分阶段发布开始时间**（`WAITING` 节点 `startTime`）与问题时间的差值为准进行判断

| 变更时间差 | 变更内容相关度 | 处置建议 |
|-----------|--------------|---------|
| < 6 小时 | 高（同 Bundle / 同功能） | 🔴 立即止损，同步排查 |
| < 6 小时 | 低（不同功能） | 🟡 评估后决定，继续排查 |
| 6 小时 ~ 24 小时 | 高 | 🟡 评估后决定止损，加快排查 |
| 6 小时 ~ 24 小时 | 低 | 🟢 继续排查，暂不止损 |
| > 24 小时 | 任意 | 🟢 无近期变更，暂不止损 |

---

## 第四步、输出变更报告
> ⚠️ **必须在 MCM 和 Diva 两路均完成后才能输出。输出完成前，禁止执行任何后续步骤。**

输出报告前，先执行以下命令，获取结束endTime：

```bash
endTime "+%Y-%m-%d %H:%M:%S"
```
> 💡 **耗时计算**：endTime - startTime，精确到分钟，格式如「约 X 分钟」。

✅ **第二步：变更查询报告**（完成时间：{endTime 命令输出}  耗时：{约 X 分钟}）

| 系统 | 变更内容 | 发布时间 | 发布人 | 相关度 |
|------|---------|---------|-------|-------|
| MCM | {变更名称 / 未发现} | {时间} | {mis_id} | 高/中/低/无 |
| Diva | {bundle名 版本号 / 未发现} | {分阶段开始时间（若 ≤24h）/ 全量完成时间（若 >24h，标注「无近期变更」）} | {mis_id} | 高/中/低/无 |

> 🔴 **高相关度变更必须单独高亮**：若某行相关度为「高」，在该行末尾追加 `← 🔴 高度可疑，距问题时间仅 {X} 分钟`，并在表格下方单独列出。

**止损建议**：🔴 立即止损 / 🟡 评估后止损 / 🟢 暂不止损

**最可疑变更**：{排第一的变更信息，或「无变更」}

**commitUrl（备查）**：{commitUrl 链接，或「无」}（⚠️ 仅记录，第四步代码分析时使用，本步骤严禁打开或分析）


➡️ 进入第三步：{执行止损 / 跳过止损，直接排查}
---