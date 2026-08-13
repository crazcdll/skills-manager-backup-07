---
name: ai-pr-code-review
description: "前后端全栈代码审查一站式 Skill，支持单仓库和多仓库联合 CR。三层上下文感知 + 四层审查模型（P0零容忍/P1稳定性/P2规范/P3性能）+ Cross-Repo 跨仓库检查层（接口兼容/数据流/分布式事务/配置一致/上线顺序/灰度安全/监控/幂等）。全链路：生成学城文档 → 
评论到 
PR → 大象推送 → 登记多维表格，I/O 操作均重试4次失败通知提交人。触发：用户提到 review PR、代码审查、CR、帮我看下这个 PR，或提供 dev.sankuai.com PR 链接（单个或多个）。⚠️ 推荐使用 GLM5.2 及以上模型以获得最佳检出率。支持识别纯前端改动并自动委托 fe-ai-review 进行前端专项审查。"

metadata:
  skillhub.creator: "mengmuzi"
  skillhub.updater: "mengmuzi"
  skillhub.version: "V146"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "5205"
  skillhub.high_sensitive: "false"
---

# ✅ AI-PR-Code-Review — 线上正式版

> ---
> 📌 **【版本声明】这是线上正式版本，已发布到 Skillhub（skill_id=5205）。**
> - **不要在此做实验性修改**，改动前先同步到 Skillhub
> - 本地实验/集成开发请用：`~/.openclaw/workspace/skills/ai-cr-forlocal/`
> ---

# PR Code Review 自动化（单仓库 + 多仓库）

> 🚨 **执行强制要求（违反则本次 CR 无效）**：
> 1. **每个 Step 开始和结束必须在对话中输出进度**，格式见"过程可见性规范"，禁止静默执行
> 2. 格式：`▶️ Step N：xxx 开始...` → 执行 → `✅ Step N：xxx 完成 — 关键结果`
> 3. 用户反馈"没有进度输出"说明违反了本规则，必须在下次执行时严格遵守
> 4. **🚫🚫 禁止在任何 Step 完成后设置等待点**：每个 Step 完成后必须立即无条件执行下一个 Step，**尤其是 Step 4 完成后必须直接跑 Step 5/6 → 7 → 8 → 9**，绝对禁止输出「是否继续？」「等待用户确认」「回复后继续」等任何中断性语句。即使对话 compact/重开，新会话必须无条件跑完剩余 Step，违反本条 = CR 无效。

## 使用说明

### 触发场景

- **PR 链接**（必须，1 个或多个）：`dev.sankuai.com/code/repo-detail/{org}/{repo}/pr/{id}/diff`
- **ONES 需求 ID**（可选，多仓库推荐）、**学城目录**（可选）、**大象群聊**（可选）、**@人员**（可选）

> **如涉及对前端代码做审查，请展开 `fe-ai-review` Skill，阅读规则并执行前端专有审查流程。**

### ⚠️ 推荐模型

| 场景 | 推荐 | 说明 |
|------|------|------|
| 正式需求 CR / 多仓库联合 CR | **GLM5.2**（强烈推荐） | P0/P1 检出率最高；跨仓库关联推断需要大 context + 强语义理解；SKILL 指令遵从度最佳 |
| 简单改动（文件数 < 10，无跨仓库） | 轻量模型 | 速度快，适合轻量 CR |

> ⚠️ **使用弱模型（非 GLM5.2）时**：Layer 2 反查步骤可能被跳过，跨仓库依赖分析可能漏报，P0/P1 检出率下降明显。多仓库 CR **强制推荐 GLM5.2**。

### 单/多仓库自动判断

比较所有 PR URL 中的 `{org}/{repo}`：
- **相同或只有 1 个 PR** → 单仓库流程，跳过 Step 5 Cross-Repo 层
- **不同** → 多仓库流程，**两阶段串行**：阶段一逐仓完整 CR（每个 PR 独立跑 Step 3~4，禁止合并稀释），阶段二基于阶段一结论做跨仓 CX 检查（Step 5）

> ⚠️ **禁止合并稀释**：多 PR 同时跑时模型注意力被稀释，导致单仓检出率下降。必须串行，每个 PR 生成独立问题清单。

### 全链路重试规则（通用）

所有 I/O 操作（学城文档、PR 评论、多维表格）均遵循：**最多重试 4 次，每次间隔 2~3s，全部失败则输出到对话并大象通知 PR 提交人，不阻塞后续步骤。**

---

## 执行流程概览

```
Step 0：环境自检 + 强制安装（每次执行前自动运行）
Step 1 + Step 2：【并行执行】Step 1（ONES需求上下文）与 Step 2（PR元信息提取）相互独立，必须在同一轮 tool call 中同时发出
  ├── Step 1：ONES 需求上下文（有 ONES ID 时执行，无则跳过）
  └── Step 2：PR 元信息 + 仓库归属 + 单/多仓库判断 + 分批判断 + 超大PR检测
  └── 2F：识别纯前端改动 → 执行 fe-ai-review（Step 6~11 继续复用主流程）
Step 1+2 完成后，进入 Step 3（依赖 Step 2 的文件列表）

【单仓库】直接执行 Step 3~11
【多仓库】两阶段串行：
  ┌─── 阶段一：逐仓完整 CR（对每个 PR 独立完整执行）
  │    Step 3：三层上下文感知（每仓库独立，不缩减）（纯前端改动时跳过）
  │      ├── 3A. Layer 1 — 代码结构（文件分级读取 + 高危变更触发器）
  │      ├── 3B. Layer 2 — 变更影响（$REPO_SEARCH 全仓库反查，强制执行）
  │      └── 3C. Layer 3 — 业务语义（PR 描述 + ONES 需求 + 领域知识库 + COE 规则库）
  │    Step 4：四层审查（每仓库独立，完整跑，不因多仓库而缩减）（纯前端改动时跳过）
  │      ├── 4B. P0 零容忍异常 🔴 → 4C. P1 稳定性与安全 🟠
  │      ├── 4D. P2 规范与架构 🟡 → 4E. P3 性能与现代化 🔵
  │      ├── 4G. 业务逻辑审查 🔍（基于 SDD + 需求 + 上下文）
  │      └── 4H. Review 结论（四选一）
  │    ↑ 以上对每个 PR 循环执行，生成独立问题清单
  └─── 阶段二：跨仓 CX 检查（基于阶段一的接口契约变更清单）
       Step 5：Cross-Repo 跨仓库检查 Cross-Repo-01~08（专注跨仓边界，不重复单仓问题）

Step 6 + Step 7：创建学城 CR 文档 & 评论到 PR（并行执行，失败降级串行；Step 8 等 Step 6 完成后取文档 URL）
Step 8 + Step 9：大象群聊推送 & 记录持久化（并行执行，失败降级串行）
Step 10：采纳率回收（第二轮 CR 自动触发）
Step 11：验证（全链路状态播报）
```

---

## 过程可见性规范（强制执行）

> **每个 Step 开始前和结束后必须输出状态，禁止静默执行。**

### 播报格式

```
▶️ Step N：{步骤名} 开始...
✅ Step N：{步骤名} 完成 — {关键结果摘要}
❌ Step N：{步骤名} 失败 — {错误原因} | 降级处理：{降级策略}
⚠️ Step N：{步骤名} 跳过 — {跳过原因}
```

### 各步骤播报要求

| Step | 开始播报 | 完成播报内容 | 失败处理 |
|------|---------|------------|---------|
| Step 0 | ▶️ 环境自检开始 | ✅ 环境就绪，共安装/验证 N 个依赖 | ❌ 列出缺失项，中止或询问继续 |
| Step 1+2 | ▶️ Step 1+2 并行开始（ONES上下文 + PR元信息） | ✅ Step 1：已加载需求：{标题}（或跳过）；Step 2：PR #{id}，{提交人}，{文件数}个文件，{单/多}仓库 | Step 1 失败跳过；Step 2 失败中止 |
| Step 2F | ▶️ 识别纯前端改动 | ✅ 纯前端改动：已展开阅读 fe-ai-review 的审查流程 / 非前端：继续主流程 | ⚠️ fe-ai-review 不可用，中止并告知 |
| Step 3 | ▶️ 三层上下文感知（Layer 1/2/3） | ✅ Layer 1 读取 N 个文件，Layer 2 反查 N 个引用，Layer 3 加载 {知识库内容概要} | ❌/⚠️ Layer 2 降级时必须告知 |
| Step 4 | ▶️ 四层审查开始 | ✅ 审查完成：P0={n}，P1={n}，P2={n}，P3={n}，结论：{四选一} | — |
| Step 5 | ▶️ Cross-Repo 跨仓检查 | ✅ CX 检查完成：{通过N项/发现M项问题} | ⚠️ 单仓库跳过 |
| Step 6 | ▶️ 创建学城 CR 文档 | ✅ 学城文档已创建：{url} | ❌ 降级输出到对话，不阻塞后续 |
| Step 7 | ▶️ 评论到 PR | ✅ 已发 P0/P1 行内评论 N 条 + 全局摘要 1 条 | ❌ 重试4次仍失败，大象通知提交人 |
| Step 8+9 | ▶️ 大象推送 & 多维表格（并行） | ✅ 已推送到全局群 + 多维表格已追加 1 行 | 任一失败降级串行；仍失败则通知提交人 |
| Step 10 | ▶️ 采纳率回收 | ✅ 采纳率：{n}%，误报率：{n}% | ⚠️ 无历史 CR，跳过 |
| Step 11 | ▶️ 全链路验证 | 见 Step 11 完成报告模板 | — |

> ⚠️ **AI 执行约束**：以上播报为强制要求，不得省略。步骤失败时必须明确说明失败原因和降级策略，不允许静默跳过。

---

## Step 0：环境自检 + 强制安装 + 团队配置加载（一键脚本）

**每次执行 skill 前必须先跑此步。** 整个 Step 0 已封装为 `scripts/env-check.sh`，**只需一次 exec 调用**。

> **设计思路**：缓存 + 并行 + 合并
> - 首次执行：完整检测（0A~0D）→ 写缓存（~15-60s）
> - 后续执行：读缓存 + 校验关键文件 → 直接输出（~0.2s）
> - `--force`：强制重建缓存

### 执行方式（AI 只需执行以下两行）

```bash
# 一键自检（含 0A mtskills + 0B Skill 并行安装 + 0C 路径定位 + 0D 配置加载）
SKILL_DIR=$(dirname "$(mtskills path ai-pr-code-review 2>/dev/null)" 2>/dev/null || echo "$HOME/.openclaw/workspace/.claude/skills/ai-pr-code-review")
bash "$SKILL_DIR/scripts/env-check.sh"
source /tmp/cr-env.env
```

### 脚本自动完成的事项

| 子步骤 | 内容 | 优化点 |
|--------|------|--------|
| 0A | mtskills CLI 检测 + 安装 | 已装则跳过 |
| 0B | 5 个 Skill 依赖检测 | **只安装缺失项，并行安装**（非全量串行） |
| 0C | code-cli / repo-search 路径定位 | **首次 find → 写缓存，后续直接读**（~0.1s） |
| 0D | cr-config.yaml 配置加载 | **纯 bash grep**（不启动 Python 解释器） |

### 输出的环境变量（source 后可直接使用）

| 变量 | 说明 |
|------|------|
| `$SKILL_DIR` | ai-pr-code-review Skill 根目录 |
| `$CODE_CLI` / `$CODE_CLI_PATH` | code-cli 完整命令 / 路径 |
| `$REPO_SEARCH` / `$REPO_SEARCH_PATH` | repo-search 完整命令 / 路径 |
| `$REPO_SEARCH_AVAILABLE` | true/false |
| `$GITNEXUS_AVAILABLE` | true/false |
| `$TABLE_ID` | 多维表格 ID（default fallback） |
| `$CITADEL_PARENT_ID` | 学城文档父目录 ID |
| `$TEAM_CHAT_GROUP_ID` | 团队大象群 ID |
| `$DOMAIN_KNOWLEDGE_PATH` | 领域知识库绝对路径 |
| `$GET_ORG_INFO_PATH` | get_org_info.py 路径 |
| `$CR_COMMENT_SH` | cr-comment.sh 路径 |
| `$NOTIFY_PY` | notify.py 路径 |

### 缓存机制

- 缓存文件：`/tmp/cr-env.env`（环境变量）+ `/tmp/cr-env-ready`（时间戳）
- 命中条件：两个文件存在 + `CODE_CLI_PATH` 和 `REPO_SEARCH_PATH` 指向的文件仍存在
- 失效场景：Skill 被重装/删除、沙箱重启（/tmp 清空）、手动传 `--force`
- **无需手动管理缓存**：脚本自动检测失效并重建

### 降级规则

| 状态 | AI 行为 |
|------|--------|
| `REPO_SEARCH_AVAILABLE=false` | 告知 Layer 2 降级影响，询问是否继续；禁止静默跳过 |

### 接口动态覆盖（Step 2 时执行）

Step 0 加载的是 default 配置。**Step 2 调用 `get_org_info.py` 后**，接口返回的 `chatGroupId` / `tableId` / `citadelParentId` 非空时覆盖对应变量：

```bash
_ORG_JSON=$(python3 "$GET_ORG_INFO_PATH" "{submitter_mis}" 2>/dev/null)
# 提取并覆盖（非空时）
_API_TABLE_ID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tableId',''))" 2>/dev/null || echo "")
[[ -n "$_API_TABLE_ID" ]] && TABLE_ID="$_API_TABLE_ID"
# ... 同理覆盖 CITADEL_PARENT_ID、TEAM_CHAT_GROUP_ID
```

**用户手动覆盖**（优先级最高）：
- 使用者在触发时提供学城目录 ID → 解析出 contentId → 赋值 `$CITADEL_PARENT_ID`，覆盖接口值
- 不提供 → 使用接口值或 default

> **⚠️ AI 执行规则（严禁违反）**：
> 1. **必须实际执行 env-check.sh 并 source 结果**，禁止把变量当文本字面量使用
> 2. **PR 行内评论必须用 `$CODE_CLI comment-add --url ... --file ... --line ... --line-type ADDED`**，禁止用 `code-cli pr comment`（该命令只支持全局评论）
> 3. `REPO_SEARCH_AVAILABLE=false` 时，**必须告知用户影响并等确认**，禁止静默降级

> **按需安装**：`fe-ai-review`（skill_id: 39902）不在 Step 0 预装，仅在 Step 2F 识别纯前

---

## Step 1：ONES 需求上下文

> ⚡ **并行执行**：Step 1 与 Step 2 相互独立，必须在同一轮 tool call 中同时发出，不要等 Step 1 完成再执行 Step 2。
> 无 ONES ID 时，Step 1 立即跳过，不等待用户提供。

有 ONES ID → 调用 `ee-ones` 拉取标题、验收条件，注入 Step 4 Cross-Repo 合规性检查。无则跳过。

---

## Step 2：PR 元信息提取

### 2A. 输入类型判断（PR 链接 vs 分支名）

| 用户输入 | 处理方式 |
|---------|---------|
| `dev.sankuai.com/.../pr/{id}/diff` PR 链接 | 标准 PR 流程（见 2B） |
| `{org}/{repo}` + 分支名（如 `feature/xxx`） | **分支级 diff 流程（见 2C）**，用于无 PR 的服务 |
| 多仓库混合（部分有 PR、部分只有分支） | 有 PR 的走 2B，无 PR 的走 2C，统一进入后续 Step 3~4 |

### 2B. PR 链接入口（标准流程）

1. **用 code-cli 拉取 PR 元信息和文件列表**（优先，不用浏览器）：
   ```bash
   # 获取 PR 基本信息（标题、提交人、源/目标分支）
   $CODE_CLI pr-info --url "{PR_URL}" 2>&1

   # 获取变更文件列表
   $CODE_CLI pr-diff --url "{PR_URL}" --name-only 2>&1
   ```
   从 `pr-info` 提取：标题、提交人 mis、源分支、目标分支；从 `--name-only` 统计文件数。

   > ⚠️ **截断检测**：`code-cli pr-diff --name-only` 输出的文件数若**恰好等于 500**，说明 Code 平台触发了截断限制（`This pull request is too large to render. Showing the first 500 files.`），**必须进入 2D 超大 PR 模式**拉取完整列表，禁止用截断列表继续 CR。

2. **提交人姓名 + 组织架构**（必须，用于 Step 8 推送和 Step 9 记录持久化）：
   ```bash
   # ⚠️ 必须调用固化脚本，禁止自己写 curl+python 解析（解析逻辑不稳定，历史上多次出现"未知组织"问题）
   # $GET_ORG_INFO_PATH 由 Step 0 env-check.sh 输出，source 后可直接用
   _ORG_JSON=$(python3 "$GET_ORG_INFO_PATH" "{submitter_mis}" 2>/dev/null)
   _AUTH_NAME=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('authorName','{submitter_mis}'))" 2>/dev/null || echo "{submitter_mis}")
   _ORG_ID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('orgId',''))" 2>/dev/null || echo "")
   # 接口同时返回团队配置，提取并覆盖 default（非空时覆盖）
   _API_CHAT_GROUP_ID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chatGroupId',''))" 2>/dev/null || echo "")
   _API_TABLE_ID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tableId',''))" 2>/dev/null || echo "")
   _API_CITADEL_PARENT_ID=$(echo "$_ORG_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('citadelParentId',''))" 2>/dev/null || echo "")
   ```
   将 `_AUTH_NAME` 保存为 `{authorName}`，`_ORG_ID` 保存为 `{orgId}`。

   **团队配置覆盖**（接口值非空时覆盖 Step 0D 的 default）：
   - `_API_TABLE_ID` 非空 → `$TABLE_ID = _API_TABLE_ID`
   - `_API_CITADEL_PARENT_ID` 非空 → `$CITADEL_PARENT_ID = _API_CITADEL_PARENT_ID`
   - `_API_CHAT_GROUP_ID` 非空 → `$TEAM_CHAT_GROUP_ID = _API_CHAT_GROUP_ID`

   - **多维表格"组织架构"列**：直接填 `{orgId}`（纯数字，如 `103461`），**禁止填组织架构名称**
   - **⚠️ 强制校验**：若 `{orgId}` 为空，兜底填空字符串（**严禁填入 mis 号或推测的部门名**）
   > 大象推送中提交人统一格式：`{authorName}（{submitter_mis}）`，如 `曾建涛（zengjiantao）`

3. **分批判断**（满足任一 → 分批）：文件数 > 30 / 高危层文件 > 15 / 高危触发器 > 3

### 2D. 超大 PR 模式（文件数 = 500，触发截断检测后执行）

> **触发条件**：Step 2B 检测到文件数恰好为 500（Code 平台截断）。
> **详细流程见**：[references/super-large-pr-guide.md](references/super-large-pr-guide.md)

**执行摘要**（完整实现见上方文档）：

1. **2D-1 拉完整列表**：用 MCode API `/code/api/1.0/projects/{org}/repos/{repo}/pull-requests/{prId}/changes` 分页拉取，直到 `isLastPage=true`；Cookie 失败时降级并告知漏报风险
2. **2D-2 三层分层**：P0 核心层全量精读（无上限）→ P1 接口层软上限 200（超出按 Enum>DTO>Config>Client 优先级截断）→ P2 边缘层直接跳过
3. **2D-3 衔接**：超大 PR 模式下必然分批（Batch1 P0高危层 → Batch2 P0其他+P1接口 → Batch3 P1配置 → Batch4 汇总）；单批超时不阻塞，主 Agent 基于已完成批次输出结论

**分层结果播报格式**：
```
🔀 超大 PR 模式：共 {N} 个文件
   ✅ P0 核心层：{p0} 个文件（全量精读）
   📋 P1 接口层：{p1_read} 个文件（扫描）{p1_truncated > 0 ? "，另有 {p1_truncated} 个超出软上限跳过" : ""}
   ⏭ P2 边缘层：{p2} 个文件（已跳过，含 {test_count} 个测试文件）
   {p1_truncated > 0 ? "⚠️ 建议将 PR 拆分为多个小 PR 以获得完整 CR 覆盖" : ""}
```

### 2C. 分支级 diff 入口（无 PR 时使用）

> **场景**：多仓库 CR 中某个服务未创建 PR，但有开发分支。

优先用 `code-cli files list {org}/{repo} --branch {branch}` 拿文件列表，`code-cli diff {org}/{repo} --from master --to {branch}` 拿 diff；不支持时用 `$REPO_SEARCH`（即 `python3 repo_search.py`）搜索关键类名兜底。

- 变更文件列表/diff → 等同于 PR 入口，进入分批判断和三层上下文感知
- **学城文档标注「分支 CR（无 PR）」，Step 7 PR 评论跳过**，其余流程相同
- 若后续创建 PR，可复用本次结论并补充评论

**分批流程：** Batch1 高危层 → Batch2 业务层 → Batch3 配置层 → Batch4 汇总去重。上下文连续不重置。

---

### 2F. 纯前端改动识别与委托

审视 Step 2B/2C 获取的变更文件列表，综合路径、扩展名、目录结构等信息自行判断本次改动的性质：

- **纯前端改动** → 展开阅读 `fe-ai-review` Skill 进行审查，跳过本 Skill 的 Step 3/4；前端审查的步骤、覆盖面必须完全符合 `fe-ai-review`（含其 SKILL 与既定执行流程），不使用本 Skill 后端「四层审查」替代或删减。审查完成后以 `fe-ai-review` 的报告作为结论源进入 Step 6/7/8/9。
- **非纯前端改动**（含后端文件） → 保持原主流程，进入 Step 3

> 当前仅支持纯前端改动经由 `fe-ai-review` 处理，暂不支持前后端混合改动的拆分合并。混合场景先按主流程走后端审查，前端部分本轮不覆盖。

**委托方式（必须与 `fe-ai-review` 对齐）**：优先启动独立 subagent，仅载入并执行 `fe-ai-review`；若当前环境不支持 subagent，则在主 Agent 上下文内串行：先按需加载 `fe-ai-review` 的规则与步骤说明，再按其流程完成前端专项审查，严格禁止「摘要式评审」简化其完整流程。

执行时，以自然语言描述范围即可，例如：

````
请对 PR {PR_URL} 的前端变更执行代码审查，聚焦以下文件：{前端文件列表}

补充信息：
- PR 提交人：{submitter_mis}
- `$REPO_SEARCH` 可用（$REPO_SEARCH_AVAILABLE={true/false}），可用时**必须**使用全仓库搜索做影响分析。调用方式：`$REPO_SEARCH -r {org}/{repo} -k "关键词" --ext .java --json`
- 审查完成后将 Markdown 报告落盘，并在返回消息中带回 P0/P1/P2/P3 计数与结论。
````

> 与上文「上下文节约」的关系：节省的是本 Skill 在对话中的逐条复述，不是 `fe-ai-review` 的工作量。Markdown 报告、issue 粒度与必选输出仍须 `fe-ai-review` 逐项满足。

`fe-ai-review` 返回后，主流程以其报告为单一结论源，继续进入 Step 6（学城）、Step 7（PR 评论）、Step 8（大象推送）、Step 9（记录持久化）。下游步骤读取前端报告中的 P0/P1/P2/P3 计数、结论、issue 列表即可，无需额外合并逻辑。

**失败处理**：`fe-ai-review` 不可用或执行失败时，向用户明确告知"前端改动本轮未审查"，终止流程；不要把纯前端改动丢给后端审查链路。

**播报**：
- `▶️ Step 2F：识别纯前端改动...`
- `✅ Step 2F：纯前端改动，已按 fe-ai-review 约定完成前端审查（委托）；跳过 Step 3/4`
- `✅ Step 2F：非前端改动，继续主流程`
- `⚠️ Step 2F：fe-ai-review 不可用，前端改动本轮未审查`

---

## Step 3：三层上下文感知

> **纯前端路径**：若 Step 2F 已委托 `fe-ai-review`，跳过整个 Step 3。

**核心原则：bug 藏在「变化 × 存量语义」的交集里，光看 diff 不够。**

### 3A. Layer 1 — 代码结构

文件分级读取策略：

| 架构层 | 识别特征 | 读取策略 |
|--------|---------|---------|
| 数据流转/校验层 | Converter/Assembler/Checker/Validator/Filter | **读完整文件** |
| 业务/基础设施层 | Service/Manager/Dao/Repository/Client | **读变更方法完整方法体** |
| 接口定义/配置层 | DTO/Request/Response/Enum/Config/XML | **读 diff，扫触发器** |

**高危变更触发器（命中任一 → 强制扩展读取）：**
- DTO/Request 新增字段 → grep 全仓库消费方
- 常量/枚举值被修改 → grep 全仓库引用方
- 方法签名变更（参数类型/数量/顺序） → grep 全仓库调用方
- XML 新增 bean/consumer/producer → 读完整 XML，反查 Java 类
- interface 新增方法 → grep 所有实现类

### 3B. Layer 2 — 变更影响（**强制执行，不可跳过**）

**核心思路：diff 只告诉你"改了什么"，Layer 2 要告诉你"改了之后，谁受影响"。**

两个方向，哪个被 diff 触发就执行哪个（可同时触发）：

---

**3B-1「我新增了东西，谁在消费我？」— 适用场景举例**

- 新增枚举值（如 `ProductFilterTypeEnum.TECHNICIAN_XXX`）→ 哪些 switch/if 没有覆盖这个新值？
- 新增 DTO 字段（如 `filteredProductIds`）→ 哪些 Converter/序列化逻辑会读这个字段？
- 新增接口方法 / 公共方法 → 现有实现类是否都已同步？

**操作（合并搜索，减少文件遍历次数）**：

1. 先从 diff 中 **收集所有触发器关键词**（新增的字段名/枚举名/方法名/类名）
2. 用 `--regex` 将多个关键词合并为一次搜索（避免每个关键词重复遍历全仓库文件）：

```bash
# ✅ 正确方式：合并关键词，一次搜索
$REPO_SEARCH -r {org}/{repo} \
  -k "ProductFilterTypeEnum|filteredProductIds|getSkuList" \
  --regex --ext .java --json

# 加 --path 限定源码目录（提速，大仓库推荐）
$REPO_SEARCH -r {org}/{repo} \
  -k "ProductFilterTypeEnum|filteredProductIds|getSkuList" \
  --regex --ext .java --path {repo-name}/src/main/java --json

# ❌ 禁止：每个关键词单独搜一次（N 个关键词 = N 次全仓库遍历，慢 N 倍）
# $REPO_SEARCH -r {org}/{repo} -k "ProductFilterTypeEnum" --ext .java --json
# $REPO_SEARCH -r {org}/{repo} -k "filteredProductIds" --ext .java --json
# $REPO_SEARCH -r {org}/{repo} -k "getSkuList" --ext .java --json
```

3. 从返回结果的 `hit.text` 中识别命中的是哪个关键词，**按触发器分组**分析消费方兼容性
4. 结果中每个命中文件，精准读 1~3 个相关方法，判断「消费方是否兼容新增内容」。**发现不兼容 → 直接升级 P1。**

> **为什么合并？** `$REPO_SEARCH`（repo_search.py）每次搜索都要遍历仓库所有 .java 文件（~3-5s/次）。
> 10 个关键词单独搜 = 10 次遍历 = 30-50s；合并为 1 次 regex = 3-5s。

**Layer 2 搜索约束（三档策略：正常 → 软警告 → 硬截断）：**

| 触发器关键词数 | 策略 | 行为 |
|---------------|------|------|
| ≤ 30 个 | ✅ 正常执行 | 合并 regex 搜索，无额外标注 |
| 31-50 个 | ⚠️ 软警告 | 全部执行不截断，CR 结论 + 大象推送 + PR 评论加拆分建议（具体文案见 comment-templates.md `{layer2_warning}` 软警告模板） |
| > 50 个 | 🔴 硬截断 | 只搜前 30 个（P0 > P1 > P2 优先级截断），CR 结论 + 大象推送 + PR 评论加截断警告 + 拆分建议（具体文案见 comment-templates.md `{layer2_warning}` 硬截断模板） |

| 约束 | 限制 | 说明 |
|------|------|------|
| 搜索调用次数 | ≤ 12 次 exec | 合并后单仓库 1-2 次，多仓库（3 仓库 × 2-3 次）≈ 6-9 次；超 12 次按触发器优先级截断 |
| 单次 regex 关键词数 | ≤ 10 个 | 超 10 个分批（每批 ≤ 10），避免 regex 过长超时 |

**Layer 2 失败处理（严格执行，禁止静默跳过）：**

| 情况 | 处理 |
|------|------|
| `$REPO_SEARCH` 可用（`REPO_SEARCH_AVAILABLE=true`） | 正常搜索，**必须有 exec 调用 `$REPO_SEARCH` 的记录** |
| 搜索超时（>15s 无响应） | 重试 1 次，仍失败进入降级 |
| `$REPO_SEARCH` 不可用 / 重试失败 | CR 结论加 ⚠️ 标注："Layer 2 变更影响分析未完成（搜索工具不可用），以下问题可能漏检：新增字段的消费方兼容性/新增调用的异常处理" |
| 搜索返回空结果 | 正常现象（没人引用），不需要降级标注 |

---

**3B-2「我新调用了别人，被调用方的行为是什么？」— 适用场景举例**

- 新增 RPC/Pigeon 调用（新增 `@Reference` 注入或新增调用语句）→ 被调用接口在不同入参下返回什么？
- 新增对外部 Wrapper/Client 的方法调用 → 该方法的异常行为、null 返回、超时表现是什么？

> **触发条件**：diff 中出现新增的外部服务调用（新注入依赖 或 新增调用语句）

**禁止猜测被调用接口的语义**，必须实际读取：
1. 用 `$REPO_SEARCH`（即 `python3 repo_search.py`，或 dev.sankuai.com 搜索框）找到被调用接口的实现
2. 读接口定义：方法签名 + JavaDoc + 返回值 DTO 的字段注释
3. 确认在当前入参组合下的实际行为（尤其是空值/异常路径）
4. 重点检查：返回值字段的语义（特别是携带多种 ID 的字段，要确认装的是哪种 ID）

**多仓库时**：字段名从 diff 动态提取，跨仓库反查（同样优先合并关键词）：
```bash
# 同仓库内多个被调用方，合并搜索
$REPO_SEARCH -r {org}/{repo-B} -k "{fieldName1}|{fieldName2}" --regex --ext .java --json

# 跨文件类型搜索（Java + XML 不能合并，分开搜）
$REPO_SEARCH -r {org}/{repo-B} -k "{topicName}" --ext .xml --json
```

### 3C. Layer 3 — 业务语义

加载顺序（**三层叠加注入，编号越大越贴近当前仓库实际，优先用于业务语义判断**）：

1. **Skill 内置通用规则**（所有团队共享）：
   - `references/zero-tolerance-checklist.md` — P0 零容忍
   - `references/stability-security-checklist.md` — P1 稳定性
   - `references/coe-rules.md` — 历史 COE 提炼规则

2. **团队领域知识库**（Step 0 从 `.cr-config.yaml` 加载路径，默认 `references/domain-knowledge.md`）：
   ```bash
   # $DOMAIN_KNOWLEDGE_PATH 由 Step 0 设置
   # 支持绝对路径（/path/to/team-knowledge.md）或相对 skill 目录的相对路径
   cat "$DOMAIN_KNOWLEDGE_PATH" 2>/dev/null || echo "（未找到领域知识库，跳过）"
   ```
   内容：ID 体系、业务核心概念、双平台规范、团队特有 P0/P1 规则、命名规范

3. **仓库级 spec 文档**（双源合并，权威性最高，与前两层叠加注入，不覆盖通用 P0/P1 规则）：

   > **spec 文件两种来源都要读，合并去重后注入 Layer 3。有任一来源有内容即可；两处都没有才跳过，完全不影响原流程。**

   **来源 A — master 分支存量 spec**（仓库长期维护的领域文档）：
   ```bash
   # ✅ 一次搜索拿全量 .md，本地过滤 spec 目录（替代旧版 6 次 --list-files 调用）
   $REPO_SEARCH -r {org}/{repo} -k "^#" --regex --ext .md --json 2>/dev/null
   ```
   从返回结果中按路径前缀过滤 spec 目录（以下 6 个前缀任一命中即保留）：
   - `specs/`、`.mdp/context/`、`.mdp/rules/team/`、`.mdp/rules/project/`
   - `docs/superpowers/specs/`、`docs/superpowers/plans/`

   命中的文件 → 逐文件读取内容（`$REPO_SEARCH` 或 code-cli file get）
   无命中 → 该来源为空，与来源 B 合并后继续

   **来源 B — PR feature 分支新增 spec**（本次需求新增/更新的规范文档，与来源 A 并行执行）：
   ```bash
   # 从 Step 2 的 PR diff 文件列表中过滤，路径模式：
   #   specs/**/*.md  /  .mdp/context/*.md  /  .mdp/rules/team/*.md  /  .mdp/rules/project/*.md
   #   docs/superpowers/specs/**/*.md  /  docs/superpowers/plans/**/*.md
   # 命中的文件从 diff 内容提取（-行或+行，取有实质内容的一侧）：
   $CODE_CLI pr diff {prId} -R {org}/{repo} --color never 2>&1 > /tmp/pr_diff.txt
   python3 -c "
   import sys
   content = open('/tmp/pr_diff.txt').read()
   target = '{filename}'
   idx = content.find(f'diff --git a/{target}')
   if idx < 0: sys.exit(0)
   next_idx = content.find('\ndiff --git', idx+10)
   chunk = content[idx:next_idx] if next_idx > 0 else content[idx:]
   lines = [l[1:] for l in chunk.split('\n') if l.startswith(('-','+')) and not l.startswith(('---','+++'))]
   print('\n'.join(lines))
   "
   # 无命中 → 跳过
   ```

   **合并与优先级**（两来源都读完后）：
   - 同名文件以来源 B（PR 新增）为准（代表最新设计意图）
   - 不同文件合并叠加

   **优先读取顺序**（文件多时按此顺序，时间有限可截断后面的）：
   1. `specs/*/spec.md` / `specs/*/design.md` — 需求规范 + 技术方案（最高价值）
   2. `.mdp/context/*.md` — 领域知识、业务概念、状态机
   3. `.mdp/rules/team/*.md`、`.mdp/rules/project/*.md` — 团队/项目规则
   4. `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` — Superpowers 设计文档
   5. `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md` — Superpowers 实现计划

   **直接跳过**（纯工具脚手架，与业务语义完全无关）：`.mdp/workflows/`、`.claude/`、`.specify/`

   **`.mdp/rules/company/`**：仓库级 Java 编码规范，**可选读取**。Skill 已内置通用 P0/P1 规则，这里的内容多为代码风格/写法规范（并发、异常、日志等），不影响业务语义判断。若时间充裕（文件数 ≤ 5）可读取，用于补充 P2/P3 判断依据；文件多时优先跳过，不影响主要检出率。

   **注入用途**：校验实现与 design.md 一致性 / 用验收条件验证 P0/P1 合理性 / 用 domain.md 设计决策避免误报

   > 💡 **MDP-Context 接入**：根目录有 `.mdp/` 的仓库自动识别，无需在 `.cr-config.yaml` 配置。

4. **ONES 验收条件**（有 ONES ID 时从 Step 1 注入）

> 💡 **团队扩展点**：各团队只需维护自己的领域知识库（第2层），在 `.cr-config.yaml` 中配置路径即可，无需修改 Skill 本身。使用 MDP-Context 的仓库第3层自动生效，两者可同时使用。

---

### Step 3D：SDD 产物校验（Spec-Code Alignment Check）

> **前提**：**始终执行**。有 spec 文件时做完备性 + 文码一致性检查；无 spec 文件时输出「本次变更未采用 SDD」。
> **纯前端路径**：若 Step 2F 已委托 `fe-ai-review`，跳过整个 Step 3D。
> **零额外 IO**：spec 文件已在 3C 加载，本步骤纯内存分析。
> **核心原则**：客观列出差异事实，不预设谁对谁错，由 Reviewer 自行判断。

#### 3D-1. 完备性检查

从 `changed_files` 推断涉及的功能模块，逐模块检查是否有对应 spec 文件：

- ✅ **完备**：有对应 spec 文件且覆盖本次变更涉及的核心设计点
- ⚠️ **简略**：有 spec 但缺少关键信息（需列出缺少哪些内容，如：缺少异常处理策略、缺少数据模型说明、缺少接口定义）
- ❌ **缺失**：涉及业务逻辑变更但无任何对应 spec 文件（`specs/`、`.mdp/context/`、`docs/superpowers/specs/` 均无，建议定为 **P2**）

**特殊情况**：变更仅涉及配置文件（.yml/.properties/.xml）、测试代码、纯重构（rename/move 无逻辑变更）→ 仍输出 SDD 结果，`has_spec: false` + `completeness: MISSING` + 备注「纯配置/测试/重构变更，无业务 spec 要求」

#### 3D-2. 文码一致性检查

将 3C 加载的 spec 内容与 diff 代码做双向比对，**仅在完备性为「完备」或「简略」时执行**：

- **正向**（spec → 代码）：spec 描述的关键设计决策（接口定义、数据模型、处理流程、异常策略、技术选型），代码实现是否符合
- **反向**（代码 → spec）：代码中新增的关键实现（新增 public 方法、新增异常分支、新增业务规则、新增外部依赖），spec 中是否有对应描述

定级：逻辑性不一致（方案/流程不同，可能误导后置环节）→ **P1**；新增关键逻辑未覆盖 → **P2**；命名/格式微差 → 忽略

#### 3D 结论（注入 Step 4 上下文，并作为文档 SDD 章节数据源）

```
[SDD_CHECK_RESULT]
has_spec: true | false
completeness: COMPLETE | PARTIAL(缺少: {异常处理策略/数据模型/接口定义等}) | MISSING
alignment_rate: {X}%  # 仅 has_spec=true 时输出
alignment_issues:     # 仅 has_spec=true 时输出，无问题则为空列表
  - [P1/P2] {spec文件} L{行号}：spec 描述「{spec描述}」，代码实现「{代码实现}」
suggestions:          # 仅 has_spec=true 时输出，简短1-2条
  - {待更新/待优化建议}
skipped: false | true（原因：仓库无 spec 目录 / 纯配置变更 / 纯前端）
[/SDD_CHECK_RESULT]
```

**空结果标准化模板（`has_spec=false` 时强制使用，禁止自由发挥）：**

```
[SDD_CHECK_RESULT]
has_spec: false
completeness: MISSING
skipped: false
note: 本次变更未采用 SDD，仓库中未检索到 spec 文件（specs/、.mdp/context/、docs/superpowers/specs/ 均无命中）
[/SDD_CHECK_RESULT]
```

**纯配置/测试/重构变更标准化模板：**

```
[SDD_CHECK_RESULT]
has_spec: false
completeness: MISSING
skipped: false
note: 纯配置/测试/重构变更，无业务 spec 要求
[/SDD_CHECK_RESULT]
```

> ⚠️ **`has_spec=false` 时**：不输出 alignment_issues / alignment_rate / suggestions。文档 SDD 章节直接写 `note` 字段内容。
> ⚠️ **`skipped=true` 时**：仅纯前端路径跳过（`fe-ai-review`），其余场景必输出 SDD 结果。

---

## Step 4：四层审查

> **纯前端路径**：若 Step 2F 已委托 `fe-ai-review`，跳过整个 Step 4。

**核心问题：变更改变了什么语义，会不会破坏存量假设。**

**4A. mt-java 规则信号检测与按需加载**

> 多仓库时每个 PR 独立执行 4A（信号检测基于各自仓库的 diff）。

从 Step 2 获取的 diff 文件列表和 diff 内容中，提取触发信号：

1. **文件类型扫描**：遍历变更文件列表
   - 包含 *.java → 激活 SIG-JAVA
   - 包含 *Mapper.xml 或 *.sql → 激活 SIG-SQL
   - 包含 pom.xml → 激活 SIG-POM
   - 包含 *.thrift / *.proto → 激活 SIG-THRIFT
   - 包含 *Test.java → 激活 SIG-TEST

2. **diff 内容关键词扫描**：按 `references/mt-java-signal-router.md` 中的触发信号定义逐个检查
   - SIG-CONCUR: synchronized/Lock/Thread/Executor/ThreadPool/CompletableFuture/volatile/Atomic
   - SIG-RPC: @ThriftClient/@OCTO/HttpClient/RestTemplate/Feign
   - SIG-CACHE: Squirrel/Cellar/Redis/cache/Cache
   - SIG-MQ: Mafka/Producer/Consumer/Message/MQ
   - SIG-EXCEPTION: try/catch/throw/Exception/NPE
   - SIG-LOG: log./logger./XMDFileAppender/scribeAppender
   - SIG-SECURITY: password/token/secret/encrypt/decrypt/serialize/exec/parse/XML/redirect/cookie/upload/SSRF/XSS
   - SIG-CONFIG: @LionValue/Lion/config/开关/degrade
   - SIG-ES: Eagle/Elasticsearch/Bulk
   - SIG-HBASE: HBase/HTable/Scan/Put/Get/RowKey
   - SIG-DDL: CREATE TABLE/ALTER TABLE/ADD INDEX/DROP INDEX

3. **按路由表加载命中的规则文件并与 CR: 规则同等审查**：读取 `references/mt-java-signal-router.md`，按信号→规则文件路由表加载对应的精要版规则文件（`references/mt-java/` 目录下）。
   - `_always/` 下的文件在 SIG-JAVA 触发时始终加载
   - 其他目录按信号匹配加载
   - 规则编号统一带 `MT:` 前缀（如 `MT:N001`、`MT:HA-J001`），与 CR checklist 规则的 `CR:` 前缀区分
   - **⚠️ CR: 前缀补全规则**：CR checklist 源文件中的规则 ID 可能没有 `CR:` 前缀（如 `STYLE-02`、`SOLID-01`），输出时必须统一补上 `CR:` 前缀（如 `[CR:STYLE-02]`、`[CR:SOLID-01]`）。所有 P0~P3 问题输出中的规则编号必须带前缀，MT: 或 CR:，不允许出现无前缀的裸规则 ID。
   - **⚠️ 逻辑 Bug 标注规则**：AI 在审查中自主发现的代码逻辑错误（非空指针/异常处理/规范/性能类问题，而是取值错误、条件判断反转、数据类型误用等），标注为 `[CR:LOGIC]`，归入对应 P 层级（通常为 P0 或 P1）。
   - **⚠️ 核心要求：MT: 规则与 CR: 规则同等对待，不是"加载了就行"**。加载后必须逐条审查，对每条 MT: 规则检查代码是否命中，产出与 CR: 规则完全相同的审查结论（命中/未命中/不适用）。MT: 规则报出的问题在输出中使用 `[{规则缩写}]` 拼接，格式与 CR: 规则一致，例如：
     - P0：`**🔴 [P0-01] [MT:HA-J001] Executors禁用 — ...**`
     - P1：`**🟠 [P1-01] [MT:HA-F001] RPC失败设计缺失 — ...**`
     - P2：`**🟡 [P2-01] [MT:N001] 常量定义规范 — ...**`
     - P3：`**🔵 [P3-01] [MT:DB-04] 索引优化建议 — ...**`
   - 审查结果必须包含在最终报告中，不能只记录"加载了哪些规则文件"而不输出逐条检查结论

4. **日志输出与文档摘要**：
   - **过程日志**（对话中输出）：记录激活了哪些信号、加载了哪些规则文件，以及命中的 MT: 规则
     - 信号加载格式：`[MT-JAVA-SIGNALS] activated: SIG-JAVA, SIG-SQL, SIG-CONCUR | loaded: java-01-constants, java-02-oop-core, java-05-exception-core, db-01-orm, db-02-sql-dev, ha-04-storage-ha, java-04-concurrency, ha-07-threadpool`
     - 命中规则格式：`[MT-RULES-HIT] MT:N002 → P0-01 | MT:HA-F001 → P1-02 | ...`（只列命中的，不列未命中/不适用）
   - **学城文档摘要**（写入「四、Review 发现 → 规则命中摘要」子段落）：用综述文字说明规则命中情况及命中分布。格式：激活信号 + 总命中数（CR: X 条 + MT: Y 条）+ 按 P 层级分布（P0/P1/P2/P3 各命中几条+命中规则编号列表，**同一问题同时命中 CR: 和 MT: 的，两个编号都列出**）+ 逻辑 Bug 检出数（独立于 P0-P3 的额外维度，体现 AI 自主发现的逻辑错误数量）+ CR/MT 分别命中几条。检出细节不在此重复，统一在 P0~P3 各层级列表中体现

5. **⚠️ 防误报与去重**：mt-java 规则报出的 P0/P1 必须同样通过三要素/报出门槛校验（代码证据确凿 + 触达路径可达 + 线上影响明确），不满足的降级为 P2/P3。与现有 `CR:` 规则**完全重叠**时（同一代码行+同一问题本质），**合并为一条 issue，标题同时标注两个规则编号**，格式为 `[CR:xxx] + [MT:yyy]`，不重复报两条。示例：`🔴 [P0-01] [CR:NP-01] + [MT:N002] 主流程中断 — ...`。**部分重叠时**（如同为 NPE 但 MT: 规则覆盖了 CR: 未覆盖的细分场景，如并发集合操作、包装类拆箱），两个规则各自报各自覆盖的部分，不互相吞掉。**仅命中 MT: 规则而无对应 CR: 规则**时，标题只标 `[MT:xxx]`。**仅命中 CR: 规则而无对应 MT: 规则**时，标题只标 `[CR:xxx]`。

**4B. 前置确认**：`$REPO_SEARCH` 是否实际调用过（上下文中必须有 exec `$REPO_SEARCH` 的输出记录）？所有触发器是否已反查？消费方是否兼容？任意不兼容 → 升级 P1。**如果 `REPO_SEARCH_AVAILABLE=true` 但未找到任何 `$REPO_SEARCH` 调用记录 → 必须回到 Step 3B 补执行，禁止跳过。**

**4C. P0 零容忍** 🔴（必须逐条扫描，不能跳过）
> ⚠️ **硬门禁：在执行 P0 审查前，必须先 read_file `references/zero-tolerance-checklist.md`。未读取该文件直接审查 = P0 漏报。**
>
> ⚠️ **同时审查 4A 加载的 MT: 规则中标注为 P0 层级的条目**（具体编号见 `mt-java-signal-router.md` 路由表「注入层级」列的 P0 条目），与上述 CR: 规则逐条并行检查，命中的问题用 `[MT:xxx]` 缩写输出，格式与 CR: 规则一致。

> 🚨 **P0 报出三要素（内部校验，不输出到文档）**：
> 每条疑似 P0 在内部必须同时满足以下三个条件，**不满足的直接按实际级别归类，不出现在 P0 中，也不标注"降级"字样**：
> 1. **代码证据确凿**：能指出 diff 中的具体行号和代码片段，不是"可能存在"
> 2. **触达路径可达**：异常输入/null 值能从实际调用链到达该代码点（外层有 try-catch 保护则触达被阻断）
> 3. **线上影响明确**：能说清楚"什么场景下、什么数据会触发、影响什么业务功能、影响范围多大"
>
> **内部分级（用户不可见，只看到最终级别）**：
> - 三要素全满足 → 报 P0
> - 任一要素不满足 → **直接归为 P2 或 P3**（不归 P1）
> - 防御性编程建议（"建议加深度限制"）→ 归为 P2/P3
>
> ⚠️ **禁止在输出文档中出现"降级"、"从 P0 降为"等字眼。三要素是内部判定逻辑，对用户透明——用户看到的每个级别就是最终结论。**

> 🚨 **P0/P1 输出格式（强制，每条必须包含以下全部字段，不可省略）**：
> ```
> **🔴 [P0-xx] {异常类型} — {一句话概括}**
> 
> - **文件**：{完整文件路径} L{起始行号}-L{结束行号}
> - **问题代码**：
>   ```java
>   {粘贴完整的问题代码片段，不要只贴一行，要包含足够上下文}
>   ```
> - **检出原因**：{为什么这是一个 P0/P1 问题？命中了哪条规则？与哪条零容忍/稳定性条目对应？为什么不是 P2？用 2-3 句话说清楚判定依据。}
> - **触达分析**：{完整调用链分析——这个方法被谁调用？入参从哪来（RPC/MQ/HTTP/配置/用户输入）？中间经过哪些转换？到达问题代码点时数据是什么状态？外层有无 try-catch？如果有，catch 了什么、处理了什么？}
> - **线上场景**：{具体业务场景描述——什么用户操作/什么定时任务/什么消息会触发这条代码路径？触发时数据长什么样？在什么条件下会出异常？发生概率是高（每天都可能）/中（特定数据才触发）/低（极端边界情况）？}
> - **影响范围**：{触发后的完整影响链——哪个接口/功能受影响？是单次请求失败还是批量失败？是否会导致上游重试风暴？有无降级兜底？对用户体验的具体影响是什么（页面报错/数据不一致/功能不可用）？影响面：单个用户/单个商户/全量？}
> - **修复建议**：
>   ```java
>   {给出具体的修复代码片段，不要只说"加 try-catch"或"加判空"。
>    展示修复后的完整代码，包含异常处理、日志、兜底逻辑。}
>   ```
>   {如有多种修复方案，列出推荐方案和备选方案，说明各自优劣。}
> ```
>
> ⚠️ P0/P1 的每个字段都必须有实质内容（≥2 句话），禁止用"可能""建议确认"等模糊措辞敷衍。如果某个字段写不出实质内容，说明证据不足，应归为 P2/P3。

**4D. P1 稳定性与安全** 🟠（合并前必须修复）
> ⚠️ **硬门禁：在执行 P1 审查前，必须先 read_file `references/stability-security-checklist.md`。未读取该文件直接审查 = P1 漏报。**
>
> ⚠️ **同时审查 4A 加载的 MT: 规则中标注为 P1 层级的条目**（具体编号见 `mt-java-signal-router.md` 路由表「注入层级」列的 P1 条目），与上述 CR: 规则逐条并行检查，命中的问题用 `[MT:xxx]` 缩写输出，格式与 CR: 规则一致。

> 🚨 **P1 报出门槛（内部校验，不输出到文档）**：每条疑似 P1 在内部必须满足：
> 1. **diff 中有明确代码证据**（具体行号 + 代码片段），不是推测
> 2. **能说清线上影响场景**：什么请求/什么数据/什么时机会触发，不能是"理论上可能"
> 3. **排除已有保护**：确认调用链上没有 try-catch、降级、兜底等已有防护
>
> **不满足的直接归为 P2/P3 或不报，不在文档中提及判定过程。** 以下场景禁止报 P1：
> - "超时时间可能不够" — 无数据支撑的猜测 → 归为 P2/P3
> - "没有 failover" — 直连测试环境等非核心链路 → 归为 P2/P3
> - "没有重试" — 用户主动触发的同步操作 → 归为 P2/P3
> - "没有事务" — 跨 RPC + 乐观锁 + 逐步 catch 有意设计 → 不报
> - "catch(Exception) 范围过宽" — 已有 log.error + Cat 上报 → 归为 P2
>
> P1 输出格式同 P0（所有字段必须有实质内容）。

**4E. P2 规范与架构** 🟡（本 MR 修或跟进）
> ⚠️ **硬门禁：在执行 P2 审查前，必须先 read_file `references/coding-standards-checklist.md`。未读取该文件直接审查 = P2 漏报。**
>
> ⚠️ **同时审查 4A 加载的 MT: 规则中标注为 P2 层级的条目**（具体编号见 `mt-java-signal-router.md` 路由表「注入层级」列的 P2 条目），与上述 CR: 规则逐条并行检查，命中的问题用 `[MT:xxx]` 缩写输出，格式与 CR: 规则一致。
>
> **P2/P3 输出格式（精简，每条 2-3 行即可）**：
> ```
> **🟡 [P2-xx] {一句话概括}**
> {文件名} L{行号}：{问题描述 + 建议}，示例：`{修复代码片段}`
> ```

**4F. P3 性能与现代化** 🔵（可选）
> ⚠️ **硬门禁：在执行 P3 审查前，必须先 read_file `references/performance-checklist.md`。未读取该文件直接审查 = P3 漏报。**
>
> ⚠️ **同时审查 4A 加载的 MT: 规则中标注为 P3 层级的条目**（具体编号见 `mt-java-signal-router.md` 路由表「注入层级」列的 P3 条目），与上述 CR: 规则逐条并行检查，命中的问题用 `[MT:xxx]` 缩写输出，格式与 CR: 规则一致。
>
> ```
> **🔵 [P3-xx] {一句话概括}**
> {文件名} L{行号}：{建议内容}
> ```

**4G. 业务逻辑审查** 🔍（基于 SDD + 需求 + 上下文）

> ⚠️ 本步骤不是检查代码缺陷或编码规范，而是检查**业务逻辑正确性**。

**三个输入源：**
1. **SDD 产物**（Step 3D 产出）— 设计文档中的架构决策、接口定义、数据模型
2. **ONES 需求语义**（Step 1 产出）— 需求标题、描述、验收标准中的业务意图
3. **上下文逻辑**（Step 3 Layer 1/2/3）— 存量代码的业务流程、已有校验逻辑

**检出范围（严格限定，与其他层级不重叠）：**
- ✅ 功能遗漏：需求/SDD 要求了某个功能点，代码没有实现或实现不完整
- ✅ 逻辑偏离：SDD 设计的流程/策略是 A，代码实现的是 B
- ✅ 边界条件缺失：需求隐含的业务边界没有处理
- ✅ 业务规则冲突：新代码的业务规则和上下文中已有逻辑矛盾
- ❌ 不报代码缺陷（NPE/异常处理/资源泄露）→ 4C
- ❌ 不报编码规范（命名/常量/并发）→ 4E
- ❌ 不报性能问题 → 4F

**证据链要求（强制）：**
每条发现必须包含：
- 依据来源：[SDD/ONES需求/上下文代码] 中的具体内容
- 预期行为：根据依据，预期代码应 X
- 实际实现：代码实际实现了 Y
- 差异分析：为什么是业务逻辑问题，可能导致什么业务后果

**置信度与定级：**
- 三源一致 → P0/P1
- 两源一致 → P1/P2
- 仅单源推断 → 标 `confirm`（归入人工复审要点）
- 无依据 → 禁止输出

**输出格式：**
> 🔍 **[BL:FUNC-MISS] {一句话概括}**
> - **依据**：{SDD/ONES需求/上下文代码 中的具体引用}
> - **预期**：{根据依据预期行为}
> - **实际**：{代码实际实现}
> - **差异分析**：{业务后果}
> - **级别**：{P0/P1/P2/confirm}

**去重规则**：与 4C/4D/4E/4F 命中同一 file+line+同类问题时，保留 4C-4F 的 finding，丢弃本步骤的重复项。

> ⚠️ 如果本次变更无 SDD 产物，仍执行本步骤，但仅基于 ONES 需求 + 上下文逻辑，置信度相应降低。

**4H. Review 结论（四选一）：**

| 结论 | 判定条件 |
|------|---------|
| ✅ 通过 | P0=0 且 P1=0 且 P2≤3 |
| 💚 通过（有建议） | P0=0 且 P1=0 且 P2>3 |
| 🟠 需修复 | P0>0 或 P1>0 或 Cross-Repo 有 P1 问题 |
| 🔴 需重新设计 | 架构级问题 |

> 🚨🚨🚨 **Step 4 完成后的强制指令（本条优先级最高，覆盖所有其他行为）**：
> - **立即、无条件、不等待任何用户输入，直接执行 Step 5（多仓库）或 Step 6（单仓库）**
> - **严禁**输出以下任何内容：「是否继续？」「回复确认后继续」「请告知是否发布」「如需继续请回复」「等待你的指示」或任何形式的停顿提示
> - **严禁**在对话中等待用户回复后再继续。用户不需要也不应该触发后续步骤。
> - 违反本条 = 本次 CR 无效，必须重跑。

---

## Step 5：Cross-Repo 跨仓库检查（多仓库专属，单仓库跳过）

**核心问题：A 承诺给 B 什么，B 期望从 A 得到什么，这两件事有没有对齐。**

**5-PRE：接口契约变更清单**（从 diff 提取，禁止硬编码字段名）

| 信号类型 | 识别方式 | 用于 |
|---------|---------|------|
| HTTP 接口签名变更 | `@RequestMapping`/`@GetMapping` 方法变更 | Cross-Repo-01 |
| DTO/VO 新增/删除字段 | 接口定义层字段级变更 | Cross-Repo-01、02、06 |
| MQ 消息体结构变更 | Mafka topic 相关类变更 | Cross-Repo-02、08 |
| 枚举新增/删除值 | 枚举文件新增/删除 case | Cross-Repo-02 |
| Lion/配置 key 变更 | `.yml`/`.properties`/Lion 文件变更 | Cross-Repo-04 |
| 反序列化配置/新增 required 字段 | Jackson/Fastjson 配置或 `@NotNull` 变更 | Cross-Repo-06 |
| MQ/RPC 新增消费或调用路径 | 新增 Consumer 类或 RPC 调用 | Cross-Repo-08 |

**Cross-Repo-01 接口变更兼容性**：用 `$REPO_SEARCH -r {org}/{repo-B} -k "{actualMethodName}" --ext .java --json` 找调用方，检查参数/返回值适配，灰度向前兼容。未适配 → **P1**

**Cross-Repo-02 数据流完整性**（最高优先级）：
- RPC/DTO：`$REPO_SEARCH -r {org}/{repo-B} -k "{fieldName}" --ext .java --json` → 检查读取和 null 判断
- MQ：检查 filter 字段与 map 取值字段是否一致（filter X 但取 Y → 新增场景丢失数据）
- 枚举：检查 B 的 switch/if 有无 default 兜底
- 无法正确消费 → **P1**

**Cross-Repo-03 分布式事务边界**：构建失败场景矩阵，检查 B 失败时补偿机制（重试幂等？定时补偿？）。无补偿 → **P1**

**Cross-Repo-04 配置一致性**：`$REPO_SEARCH -r {org}/{repo-B} -k "{configKey}" --ext .yml,.properties,.xml --json` 检查两边 key 一致性和上线顺序。不一致 → **P1**

**Cross-Repo-05 上线顺序依赖（必查）：**

| 场景 | 顺序 |
|------|------|
| A 新增接口，B 新增调用 | 先 A 后 B |
| A 删除接口，B 删除调用 | 先 B 后 A |
| A 修改接口（向前兼容） | 先 A 后 B |
| A 修改接口（不兼容） | 蓝绿/版本兼容 |
| A 新增枚举值，B 新增 case | 先 B（default 兜底）后 A |

**Cross-Repo-06 版本兼容性/灰度安全**：检查 B 的反序列化配置，未配置 `FAIL_ON_UNKNOWN_PROPERTIES=false` + A 新增字段 → **P1**

**Cross-Repo-07 监控覆盖度对齐**（P2）：检查 A/B 两侧 Cat.logEvent/Metrics 打点是否对称，key 是否一致。

**Cross-Repo-08 幂等性覆盖**：检查 B 的 `RECONSUME_LATER` 场景有无幂等保护（DB unique key / Redis setNX），A 的重试次数是否合理。无幂等 → **P1**

**Cross-Repo 层输出：** 逐项列出 Cross-Repo-01~08 结论（✅/🟠/不适用），注明上线顺序。

---

## Step 6：创建学城 CR 文档（**必须执行，无论 PR 大小，不可跳过**）

> **纯前端路径**：若 Step 2F 已委托 `fe-ai-review`，本步骤以 `fe-ai-review` 产出的 Markdown 报告为文档正文来源（其它写入流程、失败降级规则完全一致）。

> ⚡ **并行执行**：Step 6 与 Step 7 相互独立（Step 7 不依赖学城文档 URL），必须在同一轮 tool call 中同时发出。
> 若并行失败，降级为串行：先完成 Step 6，再执行 Step 7。
> Step 6 的文档 URL 在 Step 8 大象推送时使用（Step 8 必须等 Step 6 完成）。

> ⚠️ **硬门禁：在写任何输出前，必须先 read_file `references/citadel-write-guide.md`（命令规范、失败处理）和 `references/comment-templates.md`（文档内容格式模板）。未读取这两个文件直接写输出 = 格式一定不对。**

### 6a. 日期子目录（防止父目录子文档数量超限）

> 学城单个父目录下的二级子文档数量有限制，直接平铺会很快用满。因此在 `$CITADEL_PARENT_ID` 和 CR 文档之间插入一级**日期目录**。

1. 取当天日期字符串：`DATE_DIR=$(date +%Y-%m-%d)`
2. 调 `citadel getChildContent --contentId $CITADEL_PARENT_ID`，在返回的子文档列表中查找 title **完全等于** `$DATE_DIR` 的子文档
3. **找到** → 取其 contentId 作为 `$DATE_PARENT_ID`
4. **未找到** → 创建日期目录文档：
   ```bash
   citadel createDocument --title "$DATE_DIR" --content "" --parentId $CITADEL_PARENT_ID
   ```
   取返回的 contentId 作为 `$DATE_PARENT_ID`
5. 后续创建 CR 文档时，`parentId` 使用 `$DATE_PARENT_ID`（而非 `$CITADEL_PARENT_ID`）

> ⚠️ `$CITADEL_PARENT_ID` 的获取逻辑不变（优先 `get_org_info.py` 接口返回，fallback 到 `cr-config.yaml` default）。日期目录仅在其下加一层。

### 6b. 创建 CR 文档

1. 将 CR 内容写入 `/tmp/cr_review_{prId}.md`（**必须用 `--file`，禁止 `--content`**）

2. 调 `citadel createDocument` 创建文档，`parentId = $DATE_PARENT_ID`
3. 从 PR overview 提取 CatPaw 评论，写入「与 CatPaw 对比」章节（无则跳过）
4. 失败降级：输出到对话 + 大象通知提交人，**不阻塞 Step 7**

---

## Step 7：评论到 PR

> **纯前端路径**：若 Step 2F 已委托 `fe-ai-review`，PR 评论内容取自 `fe-ai-review` 的审查报告，评论格式和流程与后端审查一致。

> ⚡ **并行执行**：Step 7 与 Step 6 相互独立，必须在同一轮 tool call 中同时发出，不要等学城文档创建完再发 PR 评论。
> 若并行失败，降级为串行：先完成 Step 6，再执行 Step 7。

> ⚠️ **硬门禁：在写任何 PR 评论前，必须先 read_file `references/comment-templates.md` 中的「全局评论模板」和「行内评论模板」章节。未读取模板直接写评论 = 格式一定不对。**

**⚠️ 必须使用 `references/cr-comment.sh` 脚本发评论，禁止直接调用 `code-cli pr comment`（该命令只支持全局评论，无法发行内评论）。**

- **7-PRE**：验证鉴权可用
  ```bash
  python3 $CODE_CLI_PATH user-info
  ```

- **7A**：P0/P1 逐条行内评论，锚定代码行（只挂 ADDED/CONTEXT 行，不挂 REMOVED）。**包括 CR: 规则和 MT: 规则报出的所有 P0/P1，不做区分**

  > ✅ **使用 `--file-keyword` 传文件名，脚本自动从 `pr-changes` 解析完整路径，彻底避免路径拼错。**
  > 若关键词匹配到多个文件，脚本会报错并列出所有候选，换更精确的关键词重试即可。
  > 锚定失败（file 字段为 null）时脚本会报错并退出，**必须修正后重发，不可跳过**。

  ```bash
  bash "$CR_COMMENT_SH" inline \
    --url "{PR_URL}" \
    --file-keyword "{文件名，如 DealGroupExtendPriceProcessor.java}" \
    --line {行号} \
    --line-type ADDED \
    --text "{评论内容}"
  ```

- **7B**：P2/P3/Cross-Repo 发一条全局摘要评论。**包括 CR: 规则和 MT: 规则报出的所有 P2/P3，不做区分**
  ```bash
  bash "$CR_COMMENT_SH" global \
    --url "{PR_URL}" \
    --text "{全局摘要内容}"
  ```

- **7C**：验证，脚本已内置 `file` 字段非 null 校验；若提示 file 为 null **必须修正 --file 路径后重发，不可跳过**（file 为 null = 评论发成了全局评论，行内锚定失败）
  ```bash
  bash "$CR_COMMENT_SH" verify \
    --url "{PR_URL}"
  ```

失败重试 4 次（脚本内置），仍失败则大象通知提交人，不阻塞后续步骤。

---

## Step 8：大象群聊推送（双轨模式）

> ⚡ **并行执行**：Step 8 与 Step 9 相互独立，必须在同一轮 tool call 中同时发出，不要等 Step 8 完成再执行 Step 9。
> 若并行发出失败（任一步骤报错或无响应），立即降级为串行：先完成 Step 8，再执行 Step 9。

> ⚠️ **硬门禁：在写大象推送消息前，必须先 read_file `references/comment-templates.md` 中的「大象群聊推送模板」章节和 `references/daxiang-notify-api.md`（API 实现细节）。未读取模板直接写消息 = 格式一定不对。**

使用 AI-CR Claw bot 直接调用大象开放平台 API，不依赖 OpenClaw bot。

> ⚠️ **强制规则（违反则 CR 结果无效）**：
> - **禁止**使用 OpenClaw `message` tool 发送大象群消息（它用的是 OpenClaw bot，不在目标群里，必然报 `code=70003 机器人不在该群`）
> - **必须**使用 `daxiang-notify-api.md` 中的 Python 脚本，通过 AI-CR Claw bot 调用大象开放平台 API 发送；凭证（appId/appSecret/GID）已在 `daxiang-notify-api.md` 中配置，直接使用，**禁止替换**
> - 任何情况下都不允许降级为 `message` tool，失败只允许重试或输出到对话提示手动发送

**双轨推送：**
- **全局汇总群**（GID: 70457605151）：所有人 CR 完必推，无需配置
- **团队专属群**（自动）：由 `$TEAM_CHAT_GROUP_ID` 决定（Step 2 接口返回，或 fallback 到 default），非空则自动推送

### 8A. 获取团队群 ID

**优先级（从高到低）**：
1. `$TEAM_CHAT_GROUP_ID`（Step 2 接口返回的 `chatGroupId`，非空时已在 Step 2 覆盖）
2. `TOOLS.md` 中手动配置的群 ID（搜索 `ai-cr`，兼容旧配置）
3. 均为空 → 仅推全局群，不阻塞 Step 9

### 8B. 执行

1. 取 token（每次重新取，无需缓存）→ 详见 `daxiang-notify-api.md`
2. 填充消息文本 → 详见 `comment-templates.md` 大象群聊推送模板
   - `{triggerName}（{triggerMis}）`：格式与提交人一致（姓名+mis）。triggerMis 从当前 session USER.md 或 `code_cli.py user-info` 动态获取，triggerName 通过 `code_cli.py user-info {triggerMis}` 获取真实姓名，**禁止硬编码**
   - ⚠️ **触发人是必填项，禁止省略**；消息中必须包含"触发人：{triggerName}（{triggerMis}）"，让群里的人知道是谁发起的这次 CR
3. **🚨 发送前校验（强制，不可跳过）**：消息内容**必须以 `【AI-CR】` 开头**，否则**拒绝发送**并在对话中输出 `❌ 消息未发送：内容未以【AI-CR】开头，疑似非 CR 消息`。此规则适用于所有目标群（全局群 + 团队群），无例外。
4. 推全局汇总群（必推）
5. 若有团队群 ID → 再推团队群
6. 每次发送失败重试最多 4 次，仍失败则输出到对话提示手动发送，**不阻塞 Step 9**
7. **Step 8 执行后必须在对话中输出推送结果**（✅已推送 / ❌推送失败 / ❌消息被拦截），禁止静默跳过
8. **重跑保证**：每次完整执行 CR 流程，无论是否重跑，Step 8 **必须无条件执行**，不依赖上下文中是否有"已推送"记录。重跑 = 再推一次，这是预期行为。



---

## Step 9：记录持久化（DB + 多维表格降级）

> ⚡ **并行执行**：Step 9 与 Step 8 相互独立，必须在同一轮 tool call 中同时发出，不要等 Step 8 完成再执行 Step 9。
> 若并行发出失败（任一步骤报错或无响应），立即降级为串行：先完成 Step 8，再执行 Step 9。

调用 `$SKILL_ROOT/scripts/cr_record.py` 脚本完成记录持久化。**禁止 AI 手动拼 columnIds / data JSON / 时间戳**，必须通过脚本写入。脚本内部按优先级执行：

1. **路径 A（主）**：HTTP POST 到 DB（`33.18.123.212:8098/api/aicr/submit-task`），写入 `cr_task` 表
2. **路径 B（降级）**：DB 失败 → 自动降级到多维表格 `addData`（脚本内部处理 `getTableMeta`、时间戳计算、列 ID 映射、data 拼装、重试）
3. **全部失败**：输出错误信息，AI 通知提交人，不阻塞后续步骤

**AI 不需要接触 columnIds / data JSON / 时间戳计算**，这些全部由脚本内部处理。

### 执行命令

```bash
python3 "$SKILL_ROOT/scripts/cr_record.py" \
  --pr-url "{prUrl}" \
  --repo "{org}/{repo}" \
  --pr-title "{prTitle}" \
  --author-mis "{authorMis}" \
  --conclusion "{conclusion}" \
  --p0 {p0} --p1 {p1} --p2 {p2} --p3 {p3} \
  --doc-url "{docUrl}" \
  --operator-mis "{operatorMis}" \
  --source-branch "{sourceBranch}" \
  --target-branch "{targetBranch}" \
  {--is-sdd | --no-sdd} \
  --alignment "{alignment}" \
  --skill-version "ai-pr-code-review {{SKILL_VERSION}}" \
  --org-id "{orgId}" \
  --table-id "{tableId}" \
  --no-proxy
```

### 参数说明

| 参数 | 必填 | 来源 | 说明 |
|------|------|------|------|
| `--pr-url` | ✅ | 用户输入 | PR 链接 |
| `--repo` | ✅ | Step 2 从 pr_url 解析 | `org/repo` 格式 |
| `--pr-title` | ✅ | Step 2 `pr-info` | PR 标题 |
| `--author-mis` | ✅ | Step 2 `pr-info` | 提交人 MIS |
| `--conclusion` | ✅ | Step 4 | `✅通过` / `💚通过有建议` / `🟠需修复` / `🔴需重新设计` |
| `--p0` `--p1` `--p2` `--p3` | ✅ | Step 4 | 问题计数（整数） |
| `--doc-url` | ✅ | Step 6 | 学城文档 URL |
| `--operator-mis` | ✅ | 当前用户 | 操作人 MIS（用于多维表格 --mis） |
| `--source-branch` | ✅ | Step 2 `pr-info` | 源分支 |
| `--target-branch` | ✅ | Step 2 `pr-info` | 目标分支 |
| `--is-sdd` / `--no-sdd` | ✅ | Step 3D | 是否 SDD 流程 |
| `--alignment` | ✅ | Step 3D | 文码一致性率（无 spec 时填 `N/A`） |
| `--skill-version` | ✅ | 脚本自动读取 | `ai-pr-code-review {版本号}`（cr_record.py 自动从 SKILL.md frontmatter 读取 skillhub.version 并拼接，无需手动传版本号） |
| `--org-id` | ✅ | Step 2 `get_org_info.py` | 组织架构 orgId（纯数字） |
| `--table-id` | ✅ | Step 0/2 | 多维表格 ID（降级时使用） |
| `--no-proxy` | 推荐 | 固定 | 内网直连，不走代理 |
| `--remark` | 可选 | — | 备注（默认填 skill-version） |
| `--cr-report-file` | 可选 | — | CR 报告文件路径（DB 存储用） |
| `--dry-run` | 可选 | — | 只打印参数，不执行写入 |
| `--table-only` | 可选 | — | 跳过 DB，直接写多维表格 |

### 脚本输出与判断

| 输出 | 含义 | AI 动作 |
|------|------|--------|
| `✅ DB 写入成功，记录 ID: xxx` | DB 写入成功 | 记录 ID，继续下一步 |
| `✅ 多维表格写入成功（降级）` | DB 失败、多维表格成功 | 记录降级状态，继续下一步 |
| `✅ 多维表格写入成功（直写）` | `--table-only` 模式 | 记录，继续下一步 |
| `❌ 全部失败！` | DB + 多维表格均失败 | 通知提交人，不阻塞后续 |

### 硬性规则

- **🚨 必须使用脚本写入**：`cr_record.py` 是 Step 9 的唯一写入入口，严禁 AI 手动调 `getTableMeta` / `addData` / `exec` 算时间戳等操作。手动写入 = 字段格式不可控 = 数据污染。
- **Step 9 无条件执行**：每次完整执行 CR 流程都必须写入记录，不依赖上下文中是否有"已登记"记录。重跑 = 再追加一行，这是预期行为（效果回收必须完整）。
- **AI 只传业务参数**，不接触 columnIds / data JSON / 时间戳 / 结论映射，这些全部由脚本内部确定性处理。
- **脚本内重试 4 次**（DB 路径 + 多维表格路径各自独立重试），AI 不需要手动重试。
- **脚本失败时的处理**：输出 `❌ 全部失败！` → AI 在完成报告中标注失败，并通知提交人手动补录，不阻塞后续步骤。
- `references/table-write-guide.md` 保留为降级路径的参考文档，AI 不再需要手动读取它。

---

## Step 10：采纳率回收（第二轮 CR 自动触发）

> ⚠️ **硬门禁：在写采纳率章节前，必须先 read_file `references/comment-templates.md` 中的「采纳率章节模板」。未读取模板直接写 = 格式一定不对。**

检测到 PR 已有历史 CR 评论（含 `🤖 AI Code Review 结果`）时触发：
1. 扫描评论区，识别标记：✅已采纳 / ⚠️规则太严 / ⏭暂不修复 / ❌误报 / 无回复=未反馈
2. 未反馈 issue 检查对应代码行是否有变更 → 有则自动判定「已采纳」
3. 计算采纳率/有效率/误报率，追加「上轮 CR 采纳情况」章节到本轮文档

---

## Step 11：验证

报告各步骤状态：学城文档 URL 可访问 ✅/失败 ❌ | PR 评论已提交 | 大象消息已发送 | 多维表格已追加 | 采纳率已回收（如有）

> **纯前端路径**：Step 2F 委托过 `fe-ai-review` 时，本步骤的 P0/P1/P2/P3 计数、审查结论均直接取自 `fe-ai-review` 的返回结果。

**完成报告模板（强制格式）：**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI CR 完成报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 PR：{org}/{repo}#{prId}（{提交人}）
🔍 审查结论：{✅通过 / 💚通过有建议 / 🟠需修复 / 🔴需重新设计}
   P0={n} P1={n} P2={n} P3={n}

📄 学城文档：{url} {✅ / ❌未生成}
💬 PR 评论：行内 {n} 条 + 全局摘要 {✅ / ❌未发出}
📣 大象推送：{✅已推送 / ❌失败，请手动发送}
📊 记录持久化：{✅DB已写入 / ⚠️DB失败降级多维表格 / ✅多维表格已登记 / ❌失败}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 想让每次提 PR 自动触发 AI Code Review？
👉 接入自动 AICR，告别手动触发：
🔗 代码仓库对接自动AICR操作流程：https://km.sankuai.com/collabpage/2768389747
```

**Step 11 完成后自动执行中间文件清理：**

```bash
# 清理本次 CR 产生的所有中间文件（/tmp 下，机器重启也会自动清）
rm -f /tmp/cr_review_{prId}.md \
      /tmp/cr_files_{prId}.txt \
      /tmp/pr_diff.txt
```

> 清理失败不影响 CR 结果，静默跳过即可。

---

## 注意事项

- **P0/P1 必须逐条扫描，不能跳过**
- **在用户确认前不要自动修改代码，Review first**

---

## References

| 文件 | 内容 |
|------|------|
| [references/zero-tolerance-checklist.md](references/zero-tolerance-checklist.md) | P0 零容忍异常完整清单 + 代码示例 |
| [references/stability-security-checklist.md](references/stability-security-checklist.md) | P1 稳定性与安全：EH/RM/TP/CC/FT/SEC 共 29 条规则 |
| [references/coding-standards-checklist.md](references/coding-standards-checklist.md) | P2 规范与架构：14 大类 100+ 条规则，含美团中间件规范 |
| [references/performance-checklist.md](references/performance-checklist.md) | P3 性能与现代化：DB/CACHE/COLL/RPC/MEM/JDK 共 27 条规则 |
| [references/coe-rules.md](references/coe-rules.md) | 历史 COE 提炼的 6 大类 11 条规则，含触发关键词映射 |
| [references/domain-knowledge.md](references/domain-knowledge.md) | 领域知识：7 类 ID 体系、双平台规范、命名规范、CR 触发映射 |
| [references/comment-templates.md](references/comment-templates.md) | 行内评论、全局评论、大象推送、学城文档结构、采纳率章节模板 |
| [references/daxiang-notify-api.md](references/daxiang-notify-api.md) | 大象群推送 API 实现：token 获取（client_secret_jwt）、发送消息代码、常见错误 |
| [references/table-write-guide.md](references/table-write-guide.md) | 多维表格写入：addData 命令、结论强制映射表、日期时间戳规范、多仓库规则 |
| [references/citadel-write-guide.md](references/citadel-write-guide.md) | 学城文档创建：--file 写入命令、失败处理、CatPaw 对比章节 |
| [references/pr-comment-guide.md](references/pr-comment-guide.md) | PR 评论操作：行内评论命令参数、7A/7B/7C 流程、file 字段验证 |

---

## 团队接入指南

详见 [`references/team-onboarding.md`](references/team-onboarding.md)。
