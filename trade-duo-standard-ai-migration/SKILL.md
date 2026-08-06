---
name: trade-duo-standard-ai-migration
description:
  交易 DUO 框架标准化 AI 迁移：在 hotel-debt 平台以「创建迁移计划 → 执行任务 →
  检查状态」三步调用 MPT Open API，将 DUO 工程接入 KNB→MSI / MRNUtils→MSI 等场景化
  代码迁移。当用户说「创建迁移计划」「跑迁移任务」「执行迁移」「DUO 标准化迁移」
  「mpt 迁移」「hotel-debt 迁移」「KNB 迁移」「MSI 迁移」「调迁移接口」等触发。
  第一步（POST /v1/plans）收集必填参数创建计划；第二步（POST /v1/tasks）用 planId +
  同一 triggerMisid 触发任务；第三步（GET /v1/tasks/{taskId}/detail）查状态，确
  认 running / pending 后给出平台链接。comment 可自定义，不填则默认「<gitRepoSSHUrl>，
  <今天日期> AI 标准化迁移」。任一步失败会原样返回 statusCode / statusText /
  errorMessage 并附排查建议。
---

# 交易 DUO 框架标准化 AI 迁移

本 Skill 面向**交易 DUO 框架**下的仓库，通过 **hotel-debt / MPT** 将标准化改造与 AI 迁移能力串成一键流程。

1. **第一步**：用户给出最少必填信息 → 调用 `/v1/plans` 创建迁移计划。
2. **第二步**：用第一步返回的 `planId` + 同一个 `triggerMisid`，调用 `/v1/tasks` 触发任务执行。
3. **第三步**：用第二步返回的 `taskId`，调用 `/v1/tasks/{taskId}/detail` 查询任务状态，确认任务已进入 `running` / `pending` 后给出平台链接。

每一步只有上一步成功时才进入；任一步失败都会把接口原始错误返回给用户，并附上排查建议。

---

## ⚠️ 前置检查

**触发此 Skill 前，请确保：**

**`hfestash` 用户对目标 Git 仓库有修改权限**（commit、push 权限），否则会在第一步创建计划或后续推送分支时因权限不足而失败。

如果用户权限不足，请：
1. 联系仓库管理员或项目负责人授予 `hfestash` 的 commit 和 push 权限
2. 或者在 hotel-debt 平台使用具有仓库权限的其他 MIS ID 作为 `triggerMisid`

---

## 快速使用

Skill **同时支持三种输入方式**（A / B / C），用户用谁都行。Skill 会根据消息形态自动判断走哪条路，**不需要让用户事先选 ABC**：

```
收到用户消息
  ├─ 包含 ≥1 个 `key=value`（A 特征）            → 走【方式 A】解析
  ├─ 包含「字段名: 值」的模板行（B 特征）      → 走【方式 B】解析
  └─ 只有自然语言（例如「帮我建个迁移计划」） → 走【方式 C】逐项追问
```

无论走哪种方式，最终都汇入同一套 [参数解析规则](#参数解析规则) 与接口调用流程；差别只在「怎么收参数」。

### 方式 A：一行（多行）`key=value`（最快）

适合有经验的用户，5 行以内搞定：

```
/trade-duo-standard-ai-migration
repo=ssh://git@git.sankuai.com/hfe/hotel-material.git
name=酒店-新提单-物料
projectType=mrn
mis=zhangce07
branch=feature/fedo-367824
```

- 触发词 `/trade-duo-standard-ai-migration` 可有可无；只要消息里**出现任意 `key=value` 形式**就视为方式 A。
- 5 项必填 key（`repo` / `name` / `projectType` / `mis` / `branch`）齐全 → **立即执行**，不再追问。
- **部分给出**（例如只给了 3 项）→ 已解析的保留，**缺失项降级到方式 C** 逐项追问（只问缺失的，不再重复问已填的）。

> **支持的 key 别名**（大小写不敏感、下划线/连字符都接受）：
> - `repo` / `git` / `gitRepoSSHUrl`
> - `name` / `planName`
> - `projectType` / `type`
> - `mis` / `triggerMisid` / `triggerMis`
> - `branch` / `gitSourceBranch` / `sourceBranch`
> - `targetPrefix` / `gitTargetBranchPrefix`（可选）
> - `scenes` / `useSceneIds`（可选，逗号分隔）
> - `entry` / `entryFilePath`（可选）
> - `rel` / `projectRelativePath`（可选）
> - `include` / `includeFiles`（可选，逗号或 `|` 分隔）
> - `exclude` / `excludeFiles`（可选，逗号或 `|` 分隔）
> - `node` / `useNodeVersion`（可选）
> - `install` / `installCommand`（可选）
> - `lint` / `lintCommand`（可选）
> - `start` / `startCommand`（可选）
> - `externalId`（可选）
>
> **第二步（执行任务）专用 key**（也可在同一条消息里跟第一步的 key 一起给）：
> - `comment` / `taskComment` / `note`（可选，未给会按默认模板自动生成）
> - `overrideSourceBranch` / `overrideBranch` / `overrideSource`（可选，不传则用计划配置的源分支）

### 方式 B：结构化模板（对新手友好）

当用户说「建迁移计划 / 跑迁移 / mpt 迁移」等但**没带任何 `key=value`**、也没给出足够信息时，**立即**输出下面这份模板让用户复制填写。

**⚠️ 输出模板时的绝对禁令**：
- 严禁自行改写字段名（不要把 `gitRepoSSHUrl` 改成 `repo`，不要把 `triggerMisid` 改成 `mis` 等）。
- 严禁修改默认值（`projectType` 默认值是 `mrn`，不要改成别的）。
- **每个字段必须单独占一行，严禁把两个或多个字段写在同一行**（这是最常见的错误）。
- 模板必须放在代码块（` ``` `）里输出，确保每行都有换行。

**输出给用户的模板如下（完整复制这个代码块，不要修改任何内容）**：

```
请把下面模板填完一次性发回来（必填 5 项；可选留空就用默认值）：

=== 必填 ===
gitRepoSSHUrl:       ssh://git@git.sankuai.com/xxx/xxx.git
name:                
projectType:         mrn
triggerMisid:        
gitSourceBranch:     

=== 可选（留空 = 用默认值） ===
gitTargetBranchPrefix:
useSceneIds:         10005
projectRelativePath: ./
entryFilePath:       packages/index.js
includeFiles:        packages/*/src/**
excludeFiles:        
installCommand:      pnpm install
lintCommand:         pnpm lint
startCommand:        npm start
useNodeVersion:      16
externalId:          
taskComment:         
overrideSourceBranch:
```

> 注：`projectType` 可选值为 `mrn | msc | web | machpro | mach | mtflexbox | other`；`useSceneIds` 多个用逗号分隔；`includeFiles` 多条用 `|` 分隔；`gitTargetBranchPrefix` 留空会自动生成 `mpt_migrated_YYYYMMDD_6位随机`。

**模板解析规则**：
- 形如 `字段名: 值` 的每一行都算有效输入，`值` 为空则视为「未提供」，走默认值或必填校验。
- `#` 后是注释，解析时忽略。
- 用户可以只回发填完的行，也可以原样把模板回发——都能正确解析。
- 用户若漏填必填项，Skill 只针对缺失项再抛一次精简模板（不要把填过的字段又问一遍）。

### 方式 C：自然语言 / 逐项追问（兜底）

当用户消息里**既没有 `key=value`也没有模板行**，只是丢了一句自然语言（如「帮我建个酒店物料的迁移计划」、「跑个 mpt 迁移」），或者从方式 A 降级进来时，走方式 C：**一次性用中文编号列表把缺失的必填项全问完**，不要一条一问。

示例话术（**5 项必填都缺**时）：

```
好的，我来帮你创建迁移计划。麻烦一次性告诉我下面 5 个信息（其余用默认值）：

1) gitRepoSSHUrl 仓库 SSH 地址（例：ssh://git@git.sankuai.com/xxx/xxx.git）
2) name 计划名称（例：酒店-新提单-物料）
3) projectType 项目类型（mrn | msc | web | machpro | mach | mtflexbox | other）
4) triggerMisid 触发人 MIS（例：zhangce07）
5) gitSourceBranch 源分支（例：feature/fedo-367824）

可选：gitTargetBranchPrefix（不填我自动生成）、useSceneIds（默认 10005）。
```

示例话术（**从 A 降级过来、只缺几项**时——已填的字段不要重复问）：

```
已收到：repo / projectType / mis。还差 2 项必填，麻烦补一下：

1) name 计划名称
2) gitSourceBranch 源分支
```

用户回复后仍然支持三种格式混填（`key=value` / 模板行 / 纯文本编号答案如「1) 酒店-新提单 2) feature/fedo-123」），均能正确解析。

### 三种方式可混用

- 用户用方式 A 给了一部分 `key=value`，又在下面粘了一段模板 → 以 `key=value` 为准，模板里与之重复的忽略。
- 用户填完模板后发回的内容里也允许掺杂 `key=value` 行 → 合并后统一按下文规则校验。
- C 的追问回复可以用编号列表、`key=value`、模板行任选一种；全部按「收到的参数透明合并」原则合起来校验。

---

## 参数解析规则

### 必填校验（5 项）

| 字段 | 说明 | 校验 |
|------|------|------|
| `gitRepoSSHUrl` | git SSH 地址 | 必须以 `ssh://git@` 开头且以 `.git` 结尾；否则提示用户更正 |
| `name` | 计划名称 | 非空字符串 |
| `projectType` | 项目类型 | 必须是 `mrn / msc / web / machpro / mach / mtflexbox / other` 之一（小写、去空格）；若用户传了 `MRN` 等大写自动转小写 |
| `triggerMisid` | 触发人 MIS | 非空字符串 |
| `gitSourceBranch` | 源分支 | 非空字符串 |

**任一必填项缺失或非法**：立即停止调用接口，向用户指出具体缺失/错误的字段并等待补齐。

### 自动生成：gitTargetBranchPrefix

用户未显式提供时，按以下规则**在 Skill 运行时本地生成**（不要让 AI 凭想象写值）：

```bash
# 生成示例：mpt_migrated_20260421_a3f91c
DATE=$(date +%Y%m%d)
RAND=$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 6)
echo "mpt_migrated_${DATE}_${RAND}"
```

> 6 位随机数规则：**小写字母 + 数字**混合、长度 6。纯数字也可接受，但统一用 [a-z0-9] 更稳妥。
> 日期用**当天 UTC+8 / 本地日期**均可，格式固定 `YYYYMMDD`。
>
> ⚠️ 不要用系统当前虚构日期硬编码，必须调用 `date +%Y%m%d` 实时获取。

### 可选字段默认值

| 字段 | 默认值 |
|------|--------|
| `useSceneIds` | `[10005]` |
| `projectRelativePath` | `./` |
| `entryFilePath` | `packages/index.js` |
| `includeFiles` | `["packages/*/src/**"]` |
| `excludeFiles` | 不传 |
| `installCommand` | `pnpm install` |
| `lintCommand` | `pnpm lint` |
| `startCommand` | `npm start` |
| `useNodeVersion` | `"16"` |
| `externalId` | 不传 |

> **只有用户显式给出时才覆盖默认值**；留空 / 未提及 = 用默认值。`includeFiles` / `excludeFiles` / `useSceneIds` 如果用户用逗号或 `|` 分隔，需要解析成数组。

---

## 第一步：创建迁移计划（POST /v1/plans）

### Endpoint

```
POST https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/plans
Headers:
  mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2
  Content-Type: application/json
```

> ⚠️ `mpt-token` 是固定的 Open API token（和 curl 示例一致），不需要替换。两步 API 共用同一个 token。

### Request Body（示例，按用户输入与默认值拼装）

```json
{
  "gitRepoSSHUrl": "ssh://git@git.sankuai.com/hfe/hotel-material.git",
  "name": "酒店-新提单-物料-from API",
  "projectType": "mrn",
  "triggerMisid": "zhangce07",
  "gitSourceBranch": "feature/fedo-367824",
  "gitTargetBranchPrefix": "mpt_migrated_20260421_a3f91c",
  "projectRelativePath": "./",
  "entryFilePath": "packages/index.js",
  "includeFiles": ["packages/*/src/**"],
  "installCommand": "pnpm install",
  "lintCommand": "pnpm lint",
  "startCommand": "npm start",
  "useNodeVersion": "16",
  "useSceneIds": [10005]
}
```

### 发起请求（推荐用 curl，所有字符串用单引号包裹）

为避免 JSON 转义踩坑，**先把 body 写入临时文件**再用 `curl -d @file` 发送：

```bash
BODY_FILE="/tmp/mpt-plan-$(date +%s).json"
cat > "$BODY_FILE" <<'EOF'
{
  "gitRepoSSHUrl": "…",
  "name": "…",
  "projectType": "mrn",
  "triggerMisid": "…",
  "gitSourceBranch": "…",
  "gitTargetBranchPrefix": "…",
  "projectRelativePath": "./",
  "entryFilePath": "packages/index.js",
  "includeFiles": ["packages/*/src/**"],
  "installCommand": "pnpm install",
  "lintCommand": "pnpm lint",
  "startCommand": "npm start",
  "useNodeVersion": "16",
  "useSceneIds": [10005]
}
EOF

curl -sS --location 'https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/plans' \
  --header 'mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2' \
  --header 'Content-Type: application/json' \
  --data-binary "@$BODY_FILE"
```

> - 用 `--data-binary @file` 而不是 `-d '...'`，避免 shell 里中文/斜杠/引号反复转义。
> - 用 `-sS` 静默但保留错误输出；需要排查时再加 `-v`。
> - 请求完成后可 `rm -f "$BODY_FILE"` 清理临时文件。

---

### 第一步返回处理

#### 成功返回（进入第二步）

成功时示例结构（按文档说明 `statusCode` 为状态码、`data` 为业务数据）：

```json
{
  "statusCode": 200,
  "statusText": "OK",
  "errorMessage": "",
  "data": {
    "planId": 10064
  }
}
```

判定成功：**`statusCode === 200`**（若后端返回 `code` 字段也可作为兼容判断）。

成功时向用户展示以下摘要，**然后立即进入第二步**（不要等用户再确认，除非用户明确说"只建计划不执行"）。以下是要展示给用户的内容（**直接输出纯文本，不要包裹在代码块里**）：

✅ 迁移计划创建成功

- 计划 ID：<data.planId>
- 计划名称：<name>
- 项目类型：<projectType>
- 源分支：<gitSourceBranch>
- 目标分支前缀：<gitTargetBranchPrefix>
- 使用场景：<useSceneIds>
- 触发人：<triggerMisid>

接下来自动执行第二步：触发任务执行……

> **必须**把 `data.planId` 持久化在会话上下文里（或临时文件 `/tmp/mpt-last-plan.json`），第二步要复用。

#### 失败返回（中止，不进入第二步）

```json
{
  "statusCode": 4xx/5xx,
  "statusText": "…",
  "errorMessage": "具体错误原因"
}
```

向用户展示（**不要进入第二步**）。以下是要展示给用户的内容（**直接输出纯文本，不要包裹在代码块里**）：

❌ 迁移计划创建失败，已中止，不会触发任务执行。

- statusCode: <statusCode>
- statusText: <statusText>
- errorMessage: <errorMessage>

可能原因分析（按 statusCode / errorMessage 选一条最贴合的回复）：
- gitRepoSSHUrl 格式不对（需 `ssh://git@…` 开头、`.git` 结尾）
- triggerMisid 不是该仓库 / hotel-debt 的管理员
- gitSourceBranch 在仓库里不存在或拼写错误
- projectType 不在 7 个枚举值内
- gitTargetBranchPrefix 已被占用，换一个前缀再试
- useSceneIds 里的场景 ID 不存在或不可用
- mpt-token 失效 / 平台临时不可用（5xx）

修正后可以重新发起 Skill。

#### 网络层异常

如果 curl 非 0 退出、或返回非 JSON：
- 打印 HTTP 状态、响应体（前 500 字）。
- 提示可能是内网代理、token 失效、服务端 5xx，建议重试或联系管理员。
- **不进入第二步**。

---

## 第二步：执行迁移任务（POST /v1/tasks）

**前置条件**：第一步 `statusCode === 200` 且拿到 `data.planId`。否则直接跳过第二步。

### Endpoint

```
POST https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/tasks
Headers:
  mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2
  Content-Type: application/json
```

### Request Body 字段来源

| 字段 | 类型 | 必填 | 本 Skill 的行为 |
|------|------|------|-----------------|
| `planId` | number | 是 | **从第一步返回的 `data.planId` 取**，不要让 AI 凭印象填写 |
| `triggerMisid` | string | 是 | **复用第一步用户输入的 `triggerMisid`**，两步必须一致（接口会校验该用户是计划管理员） |
| `comment` | string | 否（接口层） | **本 Skill 视为必须有值**：优先取用户输入；用户没给则按默认模板生成 |
| `overrideSourceBranch` | string | 否 | 用户显式给出时才透传（key 别名：`overrideBranch` / `overrideSource`）；不给则不传，沿用计划配置 |

### comment 字段的处理逻辑

**优先级**：

1. 用户**显式给出** `comment=...`（方式 A 的 key-value），或在方式 B/C 被追问时填写了 comment → 直接用用户原文。
2. 用户**未给出** → 用默认模板生成：

   ```
   <gitRepoSSHUrl>，<今天日期> AI 标准化迁移
   ```

   其中：
   - `<gitRepoSSHUrl>` 取第一步 body 里的原始值（例如 `ssh://git@git.sankuai.com/hfe/hotel-material.git`）
   - `<今天日期>` 用 `date '+%Y-%m-%d'` **实时生成**（例如 `2026-04-21`），**严禁**用 AI 对话上下文里猜的日期
   - 中间用**中文逗号「，」**分隔（与用户示例保持一致）

   **默认 comment 示例**：

   ```
   ssh://git@git.sankuai.com/hfe/hotel-material.git，2026-04-21 AI 标准化迁移
   ```

### 在进入第二步前，是否要让用户确认 comment？

- **默认直接用「用户输入 / 默认模板」的 comment 静默执行**，不打断流程。
- 仅当**用户明确说了「我要改 comment」「先让我看看备注」**等意图时，才展示默认 comment 并等待用户确认或给新值。

### Request Body 示例

用户未给 comment、用了默认模板的情况：

```json
{
  "comment": "ssh://git@git.sankuai.com/hfe/hotel-material.git，2026-04-21 AI 标准化迁移",
  "planId": 10064,
  "triggerMisid": "zhangce07"
}
```

用户显式给了 `comment` 和 `overrideSourceBranch` 的情况：

```json
{
  "comment": "执行迁移测试，修复已知问题",
  "overrideSourceBranch": "feature/mpt-debug",
  "planId": 10064,
  "triggerMisid": "zhangce07"
}
```

### 发起请求

同样用 `curl --data-binary @file` 规避转义：

```bash
TASK_BODY_FILE="/tmp/mpt-task-$(date +%s).json"
# 变量 PLAN_ID、TRIGGER_MIS、COMMENT、GIT_REPO 都来自第一步上下文
# COMMENT 未给时：COMMENT="${GIT_REPO}，$(date '+%Y-%m-%d') AI 标准化迁移"
cat > "$TASK_BODY_FILE" <<EOF
{
  "comment": "${COMMENT}",
  "planId": ${PLAN_ID},
  "triggerMisid": "${TRIGGER_MIS}"
}
EOF

curl -sS --location 'https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/tasks' \
  --header 'mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2' \
  --header 'Content-Type: application/json' \
  --data-binary "@$TASK_BODY_FILE"

rm -f "$TASK_BODY_FILE"
```

> 如果 `comment` 或 `gitRepoSSHUrl` 里含 `"`、`` ` ``、`$` 等 shell 特殊字符，改用 `python3 -c "import json; print(json.dumps({...}))" > file` 生成 body，避免 heredoc 变量插值被破坏。

### 第二步返回处理

#### 成功返回

```json
{
  "statusCode": 200,
  "statusText": "OK",
  "errorMessage": "",
  "data": {
    "planId": 10064,
    "taskId": 20231,
    "status": "PENDING"
  }
}
```

向用户展示摘要，**然后立即进入第三步**（不要等用户再确认）。以下是要展示给用户的内容（**直接输出纯文本，不要包裹在代码块里**）：

✅ 迁移任务已触发

- 计划 ID：<data.planId>
- 任务 ID：<data.taskId>
- 任务状态：<data.status>
- 备注：<comment>
- 触发人：<triggerMisid>

接下来自动执行第三步：检查任务执行状态……

> **必须**把 `data.taskId` 和 `data.planId` 保留在会话上下文中，第三步要复用。

#### 失败返回

```json
{
  "statusCode": 4xx/5xx,
  "statusText": "…",
  "errorMessage": "具体错误原因"
}
```

向用户展示（**不要重试第一步**——计划已经建好了，只重试第二步即可）。以下是要展示给用户的内容（**直接输出纯文本，不要包裹在代码块里**）：

❌ 迁移任务触发失败（计划已创建成功，可直接重试本步）

- 计划 ID：<planId>     ← 来自第一步，后续重试直接复用
- statusCode: <statusCode>
- statusText: <statusText>
- errorMessage: <errorMessage>

可能原因分析：
- triggerMisid 不是该计划的管理员（需和第一步一致）
- overrideSourceBranch 分支在仓库里不存在
- planId 已被归档 / 删除
- 平台限流或临时不可用（5xx，建议稍后重试）

可以直接用 planId=<planId> 重新触发第二步，不需要再建计划。

#### 网络层异常

- 打印 HTTP 状态、响应体前 500 字。
- 告知用户 `planId=<planId>` 可留存用于稍后重试。

---

## 第三步：检查任务执行状态（GET /v1/tasks/{taskId}/detail）

**前置条件**：第二步 `statusCode === 200` 且拿到 `data.taskId`。否则直接跳过第三步。

### Endpoint

```
GET https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/tasks/<taskId>/detail
Headers:
  mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2
  Content-Type: application/json
```

> URL 中的 `<taskId>` 替换为第二步返回的 `data.taskId`，**不允许硬编码**示例中的数字。

### 发起请求

```bash
# TASK_ID 来自第二步上下文的 data.taskId
curl -sS --location "https://infra.sankuai.com/api/mpt/open-api/hotel-debt/v1/tasks/${TASK_ID}/detail" \
  --header 'mpt-token: 4e3d347e846ec21sa6dsaa7fas9cw3s2' \
  --header 'Content-Type: application/json'
```

### 第三步返回处理

#### 成功返回

```json
{
  "statusCode": 200,
  "statusText": "OK",
  "errorMessage": "",
  "data": {
    "taskId": 10355,
    "planId": 10064,
    "planName": "酒店-新提单-物料-from API",
    "status": "running",
    "progress": 30,
    "operator": "zhangce07",
    "comment": "ssh://git@git.sankuai.com/hfe/hotel-material.git，2026-04-21 AI 标准化迁移",
    "targetBranch": "mpt_migrated_20260421_a3f91c_uuid123",
    "createdAt": "2026-04-21T10:00:00Z",
    "startedAt": "2026-04-21T10:00:05Z",
    "talosFlowGLogAdminPanelLink": "https://talos.sankuai.com/..."
  }
}
```

根据 `data.status` 的值，向用户展示不同提示：

##### status = `running`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

🚀 当前任务在执行中

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 计划名称：<data.planName>
- 任务状态：running（执行中）
- 执行进度：<data.progress>%
- 操作人：<data.operator>
- 目标分支：<data.targetBranch>
- 开始时间：<data.startedAt>

可以打开链接查看实时进度：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

📌 迁移执行中，请注意以下事项：

1. ⏱ 迁移时间因服务队列问题，可能在 10min ~ 2h 不等，请耐心等候。
2. 任务结束后，请仔细检查修改的 diff，并在**三端**（Android / iOS / H5）验证。
3. AI 迁移第一步会先进行 lint，如果结果不合适，可以让 AI 修复或手动回退。
4. 部分 KNB 桥（尤其是 `KNB.useXXX` 类桥）缺失迁移方案，需要人工介入，可在【酒旅标准化改造】大群沟通。

如遇到任务执行问题，请联系 zhangguanyu02 / hanyuhang；
Skill 使用问题，请联系 zhangce07。

> 链接中的 `<PLAN_ID>` 替换为**第一步返回的 `data.planId`**。

##### status = `pending`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

⏳ 当前任务等待执行，请稍后

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 计划名称：<data.planName>
- 任务状态：pending（排队等待中）
- 操作人：<data.operator>
- 创建时间：<data.createdAt>

可以打开链接查看最新状态：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

📌 任务已排队，请注意以下事项：

1. ⏱ 迁移时间因服务队列问题，可能在 10min ~ 2h 不等，请耐心等候。
2. 任务结束后，请仔细检查修改的 diff，并在**三端**（Android / iOS / H5）验证。
3. AI 迁移第一步会先进行 lint，如果结果不合适，可以让 AI 修复或手动回退。
4. 部分 KNB 桥（尤其是 `KNB.useXXX` 类桥）缺失迁移方案，需要人工介入，可在【酒旅标准化改造】大群沟通。

如遇到任务执行问题，请联系 zhangguanyu02 / hanyuhang；
Skill 使用问题，请联系 zhangce07。

##### status = `submitting`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

📤 当前任务正在提交中，请稍候

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 任务状态：submitting（提交中）

可以打开链接查看最新状态：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

📌 任务提交中，请注意以下事项：

1. ⏱ 迁移时间因服务队列问题，可能在 10min ~ 2h 不等，请耐心等候。
2. 任务结束后，请仔细检查修改的 diff，并在**三端**（Android / iOS / H5）验证。
3. AI 迁移第一步会先进行 lint，如果结果不合适，可以让 AI 修复或手动回退。
4. 部分 KNB 桥（尤其是 `KNB.useXXX` 类桥）缺失迁移方案，需要人工介入，可在【酒旅标准化改造】大群沟通。

如遇到任务执行问题，请联系 zhangguanyu02 / hanyuhang；
Skill 使用问题，请联系 zhangce07。

##### status = `success`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

✅ 迁移任务已完成

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 计划名称：<data.planName>
- 任务状态：success（成功）
- 完成时间：<data.completedAt>
- 目标分支：<data.targetBranch>

可以打开链接查看迁移报告：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

🎉 任务完成！请按以下步骤检查和验收：

1. 仔细检查目标分支（<data.targetBranch>）的修改 diff，确认变更符合预期。
2. 在**三端**（Android / iOS / H5）验证功能是否正常。
3. AI 迁移第一步会先进行 lint，如果结果不合适，可以让 AI 修复或手动回退。
4. 部分 KNB 桥（尤其是 `KNB.useXXX` 类桥）可能缺失迁移方案，需要人工介入，可在【酒旅标准化改造】大群沟通。

如遇到迁移质量问题，请联系 zhangguanyu02 / hanyuhang；
Skill 使用问题，请联系 zhangce07。

##### status = `failed`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

❌ 迁移任务执行失败

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 任务状态：failed
- 错误信息：<data.errorMessage>

可以打开链接查看详情：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

该计划已创建，可直接重试第二步（触发新任务），不需重建计划。

如问题持续，请联系 zhangguanyu02 / hanyuhang；Skill 使用问题请联系 zhangce07。

##### status = `cancelled`

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

🚫 迁移任务已被取消

- 任务 ID：<data.taskId>
- 计划 ID：<data.planId>
- 任务状态：cancelled

如需重新执行，可直接用 planId=<PLAN_ID> 重试第二步。
如有疑问，请联系 zhangguanyu02 / hanyuhang；Skill 使用问题请联系 zhangce07。

#### 失败返回（接口本身报错）

```json
{
  "statusCode": 4xx/5xx,
  "statusText": "…",
  "errorMessage": "具体错误原因"
}
```

向用户展示以下内容（**直接输出纯文本，不要包裹在代码块里**，链接末尾严禁出现反引号）：

⚠️ 查询任务状态失败（任务已触发，只是查询详情出错）

- 任务 ID：<taskId>
- 计划 ID：<planId>
- statusCode: <statusCode>
- statusText: <statusText>
- errorMessage: <errorMessage>

可能原因：
- taskId 不存在或被删除
- mpt-token 失效
- 平台临时不可用（5xx，建议稍后重试）

你可以手动打开链接查看任务状态：
https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>

#### 网络层异常

- 打印 HTTP 状态、响应体前 500 字。
- 告知用户任务已触发（第二步成功），只是状态查询失败，可手动打开平台链接查看。
- 给出平台链接 `https://infra.sankuai.com/migrate-platform/plans/<PLAN_ID>`。

---

## 完整执行流程

```
1. 收到用户消息 → 判断输入方式
   ├─ 消息里有任何 `key=value`        → 走【方式 A】解析
   │    ├─ 5 项必填齐全           → 进入 2
   │    └─ 缺失必填               → 降级到【方式 C】编号列表追问缺失项，补齐后合并进入 2
   ├─ 消息里有「字段名: 值」模板行 → 走【方式 B】解析
   │    ├─ 5 项必填齐全           → 进入 2
   │    └─ 缺失必填               → 降级到【方式 C】逐项追问缺失项，补齐后合并进入 2
   └─ 只有自然语言描述                 → 首次抛完整【方式 B】模板，若用户回复依然不完整则降级到【方式 C】逐项追问
2. 合并所有已收到的参数，校验 5 项必填 → 不合法就提示并停
3. 生成 gitTargetBranchPrefix（若用户没给）—— 用 `date +%Y%m%d` + 6 位随机

--- 第一步：创建计划 ---
4. 组装 /v1/plans 的 JSON body（仅包含用户给出 + 必要默认值），写入 `/tmp/mpt-plan-xxx.json`
5. curl 调用 /v1/plans
6. 解析返回：
   ├─ statusCode === 200 → 提取 `data.planId`，向用户输出「创建成功」摘要 → 进入 7（第二步）
   └─ 失败 / 网络异常 → 输出错误 + 分析，**终止流程**，不进入第二步

--- 第二步：执行任务（仅当第一步成功才执行）---
7. 确定 `comment`：
   ├─ 用户显式给了 `comment` → 用用户原文
   └─ 没给 → `comment = "${gitRepoSSHUrl}，$(date '+%Y-%m-%d') AI 标准化迁移"`
8. 组装 /v1/tasks 的 JSON body（`planId` 取第一步的 `data.planId`；`triggerMisid` 复用第一步的值；`overrideSourceBranch` 用户给才传），写入 `/tmp/mpt-task-xxx.json`
9. curl 调用 /v1/tasks
10. 解析返回：
    ├─ 成功 → 输出 `planId / taskId / status / comment / triggerMisid` 摘要 → 进入 11（第三步）
    └─ 失败 → 输出错误，提醒用户 planId 已存在可直接重试第二步，不需重建计划，**终止流程**

--- 第三步：检查任务状态（仅当第二步成功才执行）---
11. 用第二步返回的 `data.taskId` 拼接 URL：/v1/tasks/<taskId>/detail
12. curl GET 调用 /v1/tasks/<taskId>/detail
13. 解析返回：
    ├─ statusCode === 200 → 根据 `data.status` 给出不同提示：
    │    ├─ running  → 🚀 提示「任务执行中」+ 平台链接（planId）
    │    ├─ pending  → ⏳ 提示「任务等待执行」+ 平台链接（planId）
    │    ├─ submitting → 📤 提示「任务提交中」+ 平台链接
    │    ├─ success  → ✅ 提示「任务已完成」+ 平台链接
    │    ├─ failed   → ❌ 提示「任务失败」+ 错误信息 + 平台链接
    │    └─ cancelled → 🚫 提示「任务已取消」+ 平台链接
    └─ 失败 / 网络异常 → 提示查询失败，但任务已触发，给出平台链接供手动查看

--- 收尾 ---
14. 清理临时 body 文件（/tmp/mpt-plan-xxx.json、/tmp/mpt-task-xxx.json）
```

---

## 注意事项

- **严禁伪造返回值**：两步接口都必须真实发起 curl 请求，不能 AI 自行编造 statusCode / data / planId / taskId。
- **严禁跳过必填校验**：第一步 5 项任一缺失，立刻回退到参数收集阶段。
- **第一步失败绝不允许进入第二步**：必须 `statusCode === 200` 且 `data.planId` 有值才可以调用 /v1/tasks；失败时把错误原文返给用户并给出分析。
- **planId 只能从第一步响应里取**：不要使用文档示例里的 `10064` 或语上下文里出现过的任何数字硬编码。
- **triggerMisid 两步必须一致**：第二步直接复用第一步用户输入的 `triggerMisid`，不要再问用户。
- **comment 默认模板的日期**：**必须**用 `date '+%Y-%m-%d'` 实时生成，不要用对话上下文里的「今天」猜测；中间用「中文逗号」（，）分隔，不要用英文逗号。
- **gitTargetBranchPrefix 的日期部分**：**必须**用 shell `date` 命令实时生成，不要用对话上下文里看到的「当前日期」硬编码；如果在代码里写日期，要用 `$(date +%Y%m%d)` 形式。
- **mpt-token 保密**：不要把 token 打印到给用户的汇总信息里，只在实际 curl 调用时使用（两步共用同一个 token）。
- **projectType 仅接受 7 个合法值**：`mrn / msc / web / machpro / mach / mtflexbox / other`，用户输入大小写不敏感统一转小写。
- **useSceneIds 是数字数组**：解析用户输入时要 `parseInt`，不要传字符串（`["10005"]` 是错的，要 `[10005]`）。
- **includeFiles / excludeFiles 是字符串数组**：支持 glob pattern，原样保留用户给的 pattern。
- **仓库 SSH 地址示例**：`ssh://git@git.sankuai.com/<org>/<repo>.git`，常见错误是用 HTTP 或忘记 `.git` 后缀。
- **curl 用 `--data-binary @file` 传 body**：避免复杂 JSON 在命令行被 shell 破坏；调用完成删除临时文件（第一、二步各自有独立文件）。
- **第二步成功后必须自动进入第三步**：不要等用户确认，直接用 `data.taskId` 查询状态。
- **taskId 只能从第二步响应里取**：不要使用示例中的 `10355` 或上下文中任何数字硬编码。
- **第三步平台链接中的 planId 取第一步返回值**：链接格式固定为 `https://infra.sankuai.com/migrate-platform/plans/<planId>`，只需替换末尾数字。
- **展示给用户的消息严禁用代码块包裹**：所有「向用户展示」的内容必须直接输出纯文本，链接末尾绝对不能出现反引号 `` ` `` 或代码块结束符 ` ``` `；否则链接会被破坏无法点击。
- **第三步是 GET 请求**：不需要 body，taskId 直接放在 URL path 中。
- **第三步失败不影响已触发的任务**：任务已在第二步成功触发，第三步只是查状态，失败时告知用户手动打开平台链接即可。

---

## 字段对照表（接口文档原文映射）

### 第一步 /v1/plans 入参

| 入参字段 | 必填 | 本 Skill 的行为 |
|----------|------|-----------------|
| `gitRepoSSHUrl` | 是 | 用户必填 |
| `name` | 是 | 用户必填 |
| `projectType` | 是 | 用户必填，7 个枚举值 |
| `triggerMisid` | 是 | 用户必填（第二步复用） |
| `gitSourceBranch` | 否（接口层面） | **本 Skill 视为必填** |
| `gitTargetBranchPrefix` | 否 | 用户未填 → 自动生成 `mpt_migrated_YYYYMMDD_6位随机` |
| `useSceneIds` | 否 | 默认 `[10005]` |
| `projectRelativePath` | 否 | 默认 `./` |
| `entryFilePath` | 否 | 默认 `packages/index.js` |
| `includeFiles` | 否 | 默认 `["packages/*/src/**"]` |
| `excludeFiles` | 否 | 不传 |
| `installCommand` | 否 | 默认 `pnpm install` |
| `lintCommand` | 否 | 默认 `pnpm lint` |
| `startCommand` | 否 | 默认 `npm start` |
| `useNodeVersion` | 否 | 默认 `"16"` |
| `externalId` | 否 | 不传，用户显式给才透传 |

### 第一步 /v1/plans 返回

| 返回字段 | 说明 |
|----------|------|
| `statusCode` | 数字；200 = 成功 |
| `statusText` | 状态文本 |
| `errorMessage` | 错误信息（成功时通常为空） |
| `data.planId` | 成功时的计划 ID，**第二步必须使用此值** |

### 第二步 /v1/tasks 入参

| 入参字段 | 必填 | 本 Skill 的行为 |
|----------|------|-----------------|
| `planId` | 是 | 取第一步返回的 `data.planId`，**不允许硬编码** |
| `triggerMisid` | 是 | 复用第一步用户输入的 `triggerMisid`，不再问用户 |
| `comment` | 否（接口层面） | **本 Skill 总为其填值**：用户显式给就用用户原文；否则用 `${gitRepoSSHUrl}，${今天日期} AI 标准化迁移` |
| `overrideSourceBranch` | 否 | 用户显式给才透传；不给则不传，由后端用计划配置的源分支 |

### 第二步 /v1/tasks 返回

| 返回字段 | 说明 |
|----------|------|
| `statusCode` | 数字；200 = 成功 |
| `statusText` | 状态文本 |
| `errorMessage` | 错误信息（成功时通常为空） |
| `data.planId` | 计划 ID（和第一步应一致） |
| `data.taskId` | 本次触发的任务 ID，**第三步必须使用此值** |
| `data.status` | 任务状态（如 PENDING / RUNNING 等，以后端返回为准） |

### 第三步 /v1/tasks/{taskId}/detail 入参

| 入参字段 | 必填 | 本 Skill 的行为 |
|----------|------|------------------|
| `taskId`（URL path） | 是 | 取第二步返回的 `data.taskId`，拼入 URL path，**不允许硬编码** |

> 第三步是 GET 请求，没有 request body，只有 URL path 参数。

### 第三步 /v1/tasks/{taskId}/detail 返回

| 返回字段 | 说明 |
|----------|------|
| `statusCode` | 数字；200 = 成功 |
| `statusText` | 状态文本 |
| `errorMessage` | 错误信息（成功时通常为空） |
| `data.taskId` | 任务 ID |
| `data.planId` | 计划 ID |
| `data.planName` | 计划名称 |
| `data.status` | 任务状态：`pending` / `submitting` / `running` / `success` / `failed` / `cancelled` |
| `data.progress` | 执行进度百分比 0-100（可选） |
| `data.operator` | 操作人 MIS |
| `data.comment` | 执行备注 |
| `data.targetBranch` | 目标分支名（含 uniqueId） |
| `data.createdAt` | 创建时间 |
| `data.startedAt` | 开始执行时间（可选） |
| `data.completedAt` | 完成时间（可选） |
| `data.errorMessage` | 任务级错误信息（可选） |
| `data.flowId` | Pipeline flowId（可选） |
| `data.talosFlowGLogAdminPanelLink` | Talos 流水线日志页链接（可选） |
| `data.migrateReport` | 迁移报告（可选） |

---

## 示例会话

### 示例 1：三步都成功（未给 comment，走默认模板，状态为 running）

**用户：**

```
/trade-duo-standard-ai-migration
repo=ssh://git@git.sankuai.com/hfe/hotel-material.git
name=酒店-新提单-物料-from API
projectType=mrn
mis=zhangce07
branch=feature/fedo-367824
```

**Skill 执行：**

1. 5 项必填齐全 ✅；用户未给 `targetPrefix`、`comment`、`overrideSourceBranch`。
2. 生成 `gitTargetBranchPrefix`：`date +%Y%m%d` → `20260421`，随机 `a3f91c` → `mpt_migrated_20260421_a3f91c`。
3. 其它第一步字段用默认值，组装 body 写入 `/tmp/mpt-plan-xxx.json`，curl POST /v1/plans。
4. 第一步返回 `statusCode=200, data.planId=10064` → 向用户输出创建成功摘要（包含 `计划 ID: 10064`）。
5. 自动进入第二步：
   - `comment` 未给 → 运行 `date '+%Y-%m-%d'` 得到 `2026-04-21`，模板拼接为：
     `ssh://git@git.sankuai.com/hfe/hotel-material.git，2026-04-21 AI 标准化迁移`
   - `planId=10064`（第一步返回），`triggerMisid=zhangce07`（复用第一步）。
   - 写入 `/tmp/mpt-task-xxx.json`，curl POST /v1/tasks。
6. 第二步返回 `statusCode=200, data.taskId=20231, status=PENDING` → 输出任务触发成功摘要。
7. 自动进入第三步：
   - 用 `taskId=20231` 拼接 URL，curl GET /v1/tasks/20231/detail。
8. 第三步返回 `statusCode=200, data.status=running, data.progress=30` → 输出：
   ```
   🚀 当前任务在执行中
   - 任务 ID：20231
   - 计划 ID：10064
   - 任务状态：running（执行中）
   - 执行进度：30%
   可以打开链接查看实时进度：
   https://infra.sankuai.com/migrate-platform/plans/10064
   ```
9. 清理 `/tmp/mpt-plan-xxx.json` 和 `/tmp/mpt-task-xxx.json`。

### 示例 2：用户显式给了 comment 和 override 分支，状态为 pending

**用户：**

```
repo=ssh://git@git.sankuai.com/hfe/hotel-material.git
name=酒店-新提单-物料
projectType=mrn
mis=zhangce07
branch=feature/fedo-367824
comment=执行迁移测试，修复已知问题
overrideSourceBranch=feature/mpt-debug
```

**Skill 执行：**

- 第一步正常创建计划、拿到 `planId` 后，第二步 body 直接用用户原文 `comment`，并透传 `overrideSourceBranch=feature/mpt-debug`。
- 第二步成功拿到 `taskId=20232`，自动进入第三步查询状态。
- 第三步返回 `data.status=pending` → 输出：
  ```
  ⏳ 当前任务等待执行，请稍后
  - 任务 ID：20232
  - 计划 ID：10064
  - 任务状态：pending（排队等待中）
  可以打开链接查看最新状态：
  https://infra.sankuai.com/migrate-platform/plans/10064
  ```

### 示例 3：第一步失败（不进第二、三步）

第一步返回 `statusCode=400, errorMessage="gitSourceBranch not found"` → Skill 立即停止，输出错误 + 根因分析（「分支在仓库里不存在或拼写错误」），**不会**调用 /v1/tasks 和 /v1/tasks/{taskId}/detail。

### 示例 4：第一步成功、第二步失败（不进第三步）

第一步拿到 `planId=10064`，第二步返回 `statusCode=500` → Skill 保留 `planId=10064` 交给用户，提示「计划已建好，后续直接用 planId 重试第二步即可，不需重建」。不进入第三步。

### 示例 5：前两步成功、第三步查询失败

前两步成功拿到 `planId=10064`、`taskId=20231`，第三步 curl 查询 detail 返回 `statusCode=500` → Skill 提示「查询任务状态失败，但任务已在第二步成功触发」，给出平台链接 `https://infra.sankuai.com/migrate-platform/plans/10064` 供手动查看。
