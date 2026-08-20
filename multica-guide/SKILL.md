---
name: multica-guide
description: >
  Multica AI-SDLC 一站式副驾驶：部署引导 + L2 skill 定制 + 运行时进度监控 + 卡点诊断 + 操作引导 + 工作流答疑。
  触发场景：说「部署 multica」「我想接入 multica」「定制 skill」「进度到哪了」「监控下」「卡住了」「下一步干啥」
  「XX 是什么」「Pipeline 和 Lite 区别」「Lite 前端和后端区别」「R-Gate 是啥」时激活。

metadata:
  skillhub.creator: "qiuchenjie"
  skillhub.updater: "hejun10"
  skillhub.version: "V4"
  skillhub.source: "ssh://git@git.sankuai.com/mcp/general-ai-marketplace.git"
  skillhub.skill_id: "119642"
---

# multica-guide — Multica AI-SDLC 一站式副驾驶

> **定位**：Multica AI-SDLC 平台的用户入口。**部署 → 定制 → 运维 → 答疑一条龙**，用户不用记 CLI 参数、不用翻文档，问我就行。
>
> **覆盖三条主线**：Pipeline 完整版（5 Squad + PMO + 15+ agent）+ Lite 后端版（1 Squad + 7 agent）+ Lite 前端版（1 Squad + 7 agent，`sdlc-lite-fe-pmo` 兼任调度中心，入口 `setup-lite-fe.sh`）。术语与最新 R-Gate 语义对齐 2026-07-26 起的双版本模型，前端版架构对齐 2026-07-29 设计（已落地）。

---

## Step 0：意图识别（先分类再走路径）

| 用户说的 | 走哪条路 |
|---|---|
| 「我想部署 / 接入 multica」「setup 一下」「怎么开始」| → **路径 A：部署引导** |
| 「定制 skill」「用我团队的编码规范」「同名 override / role-map」| → **路径 B：L2 定制引导** |
| 「进度」「到哪了」「现在怎样」| → **路径 C：进度快照** |
| 「监控」「盯着」「有没有动静」| → **路径 D：实时监控** |
| 「卡住了」「没动静」「为什么」「rerun 报错」| → **路径 E：卡点诊断** |
| 「下一步」「该干啥」「我要做什么」「回什么词」| → **路径 F：操作引导** |
| 「XX 是什么」「Pipeline 和 Lite 区别」「Lite 前端和后端区别」「R5 R6 是啥」| → **路径 G：工作流问答** |

---

## 路径 A：部署引导（一站式 hand-hold）

**目标**：把没接触过 Multica 的用户从"什么都没有"带到"跑起来的 workspace"。

### A.1 拉最新仓库代码

**先做这一步**：A.2 的决策树、A.3 的 env 模板都来自本仓库文件，本地仓库不存在或落后于 master 会导致依据过期，所以必须在做任何决策前先拉到最新。

```bash
REPO_LOCAL="$HOME/code/general-ai-marketplace"
if [ -d "$REPO_LOCAL/.git" ]; then
  cd "$REPO_LOCAL" && git fetch origin && git checkout master && git pull origin master
  echo "✅ 已更新到最新 master：$(git rev-parse --short HEAD)"
else
  mkdir -p "$HOME/code" && cd "$HOME/code"
  git clone ssh://git.sankuai.com/mcp/general-ai-marketplace.git
  cd general-ai-marketplace && git checkout master
  echo "✅ 已 clone 并切到 master"
fi
```

**判断规则**：
- 存在但脏 → 提示用户 `git status` 看有没有本地未提交改动，让用户决定 stash/丢弃再 pull
- clone 失败 → 检查 SSH key（`ssh -T git@git.sankuai.com`）+ workspace 网络权限

### A.2 决策：Pipeline / Lite 后端 / Lite 前端？

三选一决策树（详细决策树见 [`multica/docs/lite-guide.md`](../../../../multica/docs/lite-guide.md) §1.4，A.1 已保证读到的是最新版）：

| 场景 | 推荐版本 | 原因 |
|------|---------|------|
| 纯后端 / 单团队 / 1-3 仓 / 图快 | **Lite 后端版** | 1 Squad、7 agent、端到端 15-30 min |
| 纯前端 / 单团队 / 1-3 仓 / 图快 | **Lite 前端版** | 1 Squad、7 agent、整合 fe-rd-workflow |
| 前后端联合 / 3+ 仓 / 跨团队 / 需泳道部署 + 集成测试 | **Pipeline** | 5 Squad、15+ agent、双层 R-Gate |

**快速判断**：
- 需要**前后端联合编排**？→ **Pipeline**
- 涉及 **3+ 仓 / 跨团队协同**？→ **Pipeline**
- 需要**泳道部署 + 集成测试**？→ **Pipeline**
- 单团队 / 1-3 仓 / **纯后端** / 图快？→ **Lite 后端版**
- 单团队 / 1-3 仓 / **纯前端**（物料组件 / DUO 协议 / 页面开发）/ 图快？→ **Lite 前端版**

**默认建议**：
- 后端新手接入选 **Lite 后端版**
- 前端新手接入选 **Lite 前端版**
- 验证跑通后再评估要不要 Pipeline

**用完这一步告诉用户你选了哪个版本**，然后走 A.3。

### A.3 引导用户填 env（完全 hand-hold，Claude 逐项问）

**核心 env 项**（用户必须填的）：

1. **`WORKSPACE_ID`** — Multica 工作区 UUID
   - 怎么查：让用户执行 `multica workspace list --output json | jq -r '.[] | "\(.name)\t\(.id)"'` → 挑目标 workspace 复制 UUID
   - 或者去 Multica web UI 的 URL 里看：`https://mlt.sankuai.com/<workspace-slug>/...` 里的 slug 转换成 UUID（`multica workspace get --slug <slug>`）

2. **`KM_ROOT_PARENT_ID`** — 学城（KM）文档根节点 ID
   - 怎么查：进目标学城空间根目录 → 右键复制节点 ID
   - 例：`2769064456`

3. **`TEAM`** — 产物仓子目录名（`general-workspace` 仓下）
   - 常见值：`trade-general`（默认）、`trade-food-tp` 等
   - 团队自选，同 workspace 内多个团队用不同 TEAM 隔离

4. **`DEFAULT_MEMBERS`**（可选，runtime pool 成员）
   - 让用户跑 `multica runtime list --output json | jq -r '.[] | select(.provider == "claude" and .status == "online") | "\(.id)  # \(.name)"'` 挑要用的 runtime UUID

5. **`KNOWLEDGE_SKILL`** — 团队自建知识库 skill 名字（chain-analysis-agent 消费）
   - **是什么**：团队自建、上线到 workspace 的知识库检索 skill（不是 git 仓地址、不是入口文件——那些由 skill 内部维护）
   - **怎么查团队有没有**：`multica --workspace-id <WORKSPACE_ID> skill list --output json | jq -r '.[] | .name' | grep -iE "knowledge|kb"`
   - **常见值**：到综团队默认 `trade-knowledge-base`；餐团队 `foodtrade-knowledge`；其他团队用自己的
   - **没有知识库怎么办**：留空 `KNOWLEDGE_SKILL=""` —— chain-analysis 只靠 crkg/CRG/grep，跳过团队背景检索
   - **⚠️ 不能填别团队的知识库 skill 名**：静默拉别团队的知识库，结论有依据但依据是错的，比无知识库更危险；setup/deploy 会校验 skill 在本 workspace 存在，不存在直接报错

**⚠️ Lite 前端版额外前置条件**：前端外部 Skill 必须先导入 workspace

Lite 前端版依赖多个外部 Skill（来自 Friday SkillHub），通过 `sdlc-lite-fe.env` 中的 `FRIDAY_SKILLS_MOUNTS` 声明，由 `setup-sdlc-lite-fe.sh` 自动拉取并挂载：

| 外部 Skill | 挂载到 | 用途 |
|------------|--------|------|
| `arch-design` | sdlc-lite-fe-design-agent | 架构分析（仓/页面/组件拓扑） |
| `design-spec` | sdlc-lite-fe-design-agent | 需求规格 + 技术方案 + 开发任务 |
| `max-material-dev` | sdlc-lite-fe-coding-agent | Max/Leez 物料组件开发与发布 |
| `duo-protocol` | sdlc-lite-fe-coding-agent | DUO 协议开发 |
| `ee-ones` | sdlc-lite-fe-coding-agent | ONES 分支关联（配合 dlc-branch） |
| `ingee-flex` | sdlc-lite-fe-coding-agent | 视觉稿分析 |
| `citadel` / `citadel-database` | 全部 agent | 学城文档读写 |
| `mtsso-skills-official` | 全部 agent | SSO 鉴权 |
| `ai-app-flow` / `hotel-ui-autotest` | sdlc-lite-fe-autotest-agent | 自动化测试用例 + 执行 |
| `ee-fedo` | sdlc-lite-fe-deploy-agent | CI/CD 部署 |

部署前先确认 `mtskills` 已安装（`npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com`），且运行 deploy 的 MIS 有对应 Skill 的 Friday 下载权。任一 Skill 拉取失败直接 `exit 1`。

**hand-hold 交互模板**（Claude 按顺序问，每个问题给出获取方式）：

```
📋 Multica 部署配置（{{Pipeline / Lite 后端 / Lite 前端}}）

我要问你几个 workspace 相关参数，逐项给你查询命令：

1) WORKSPACE_ID：<Multica 工作区 UUID>
   查询命令：multica workspace list --output json | jq -r '.[] | "\(.name)\t\(.id)"'
   请提供：____________________

2) KM_ROOT_PARENT_ID：<学城文档根节点 ID>
   位置：学城目标空间根目录 → 右键复制节点 ID
   请提供：____________________

3) TEAM 名（产物仓子目录）：
   默认 trade-general；如果你团队有独立 TEAM 名请说
   请提供：____________________

4) 首个 runtime 成员 UUID（可选）：
   查询命令：multica runtime list --output json | jq -r '.[] | select(.provider == "claude" and .status == "online") | "\(.id)  # \(.name)"'
   请提供：____________________

5) KNOWLEDGE_SKILL：<团队自建知识库 skill 名字，如 foodtrade-knowledge / trade-knowledge-base>
   查询命令：multica --workspace-id <上面 WORKSPACE_ID> skill list --output json | jq -r '.[] | .name' | grep -iE "knowledge|kb"
   ⚠️ 只能填本 workspace 已上线的 skill 名（setup/deploy 会校验，不存在直接报错）；无知识库就留空
   请提供：____________________

{{若选了 Lite 前端版，额外确认：}}
5) mtskills CLI 是否已安装？（前端版外部 Skill 通过 mtskills 自动拉取）
   确认命令：which mtskills || echo "未安装"
   安装命令：npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com
```

用户回答后 Claude 自动写文件：

```bash
# Lite 后端版
TEAM_ENV_FILE="$REPO_LOCAL/multica/sdlc-lite-<team>.env"
cp "$REPO_LOCAL/multica/sdlc-lite.env" "$TEAM_ENV_FILE"

# Lite 前端版
TEAM_ENV_FILE="$REPO_LOCAL/multica/sdlc-lite-fe-<team>.env"
cp "$REPO_LOCAL/multica/sdlc-lite-fe.env" "$TEAM_ENV_FILE"

# Pipeline
TEAM_ENV_FILE="$REPO_LOCAL/multica/sdlc-pipeline-<team>.env"
cp "$REPO_LOCAL/multica/sdlc-pipeline.env" "$TEAM_ENV_FILE"

# sed 覆盖用户提供的值
sed -i.bak "s|^WORKSPACE_ID=.*|WORKSPACE_ID=\"$USER_WORKSPACE_ID\"|" "$TEAM_ENV_FILE"
sed -i.bak "s|^KM_ROOT_PARENT_ID=.*|KM_ROOT_PARENT_ID=\"$USER_KM_ROOT\"|" "$TEAM_ENV_FILE"
sed -i.bak "s|^TEAM=.*|TEAM=\"$USER_TEAM\"|" "$TEAM_ENV_FILE"
sed -i.bak "s|^KNOWLEDGE_SKILL=.*|KNOWLEDGE_SKILL=\"$USER_KNOWLEDGE_SKILL\"|" "$TEAM_ENV_FILE"
rm "$TEAM_ENV_FILE.bak"
```

**HARD-GATE**：**不要覆盖官方的 `sdlc-lite.env` / `sdlc-lite-fe.env` / `sdlc-pipeline.env`**（那是模板，是版本控制里的）。永远复制成 `sdlc-<lite|lite-fe|pipeline>-<team>.env`。

### A.4 跑 setup

```bash
# Lite 后端版
bash "$REPO_LOCAL/multica/setup-lite.sh" --env "$TEAM_ENV_FILE"

# Lite 前端版
bash "$REPO_LOCAL/multica/setup-lite-fe.sh" --env "$TEAM_ENV_FILE"

# Pipeline
bash "$REPO_LOCAL/multica/setup.sh" --env "$TEAM_ENV_FILE"
```

**Lite 前端版特有的额外检查**（setup 完成后必须确认）：

```bash
# 确认外部 Skill 已挂载到 sdlc-lite-fe-* agent
for skill in arch-design design-spec max-material-dev duo-protocol ee-ones citadel ee-fedo; do
  echo "=== $skill ==="
  multica --workspace-id "$WORKSPACE_ID" skill list --output json | \
    jq -r --arg s "$skill" '.[] | select(.name | test($s; "i")) | "\(.name) (id=\(.id))"'
done
```

若关键 Skill 输出为空，说明 `FRIDAY_SKILLS_MOUNTS` 拉取失败，检查 mtskills 安装状态和 Friday 下载权限后重跑 `setup-lite-fe.sh`。

**中途报错主动接管**（常见 4 个错）：

| 错误 | 原因 | Claude 主动执行的修复 |
|---|---|---|
| `agent sdlc-*-agent 不存在` | Agent 尚未创建 | 提示：属正常首次部署，setup 会自动创建；若报错说 create 失败，检查 workspace 权限（`multica auth status`） |
| `skill xxx 不存在` | SKILL_DIRS 白名单里的 skill 未上传 | 让 setup 继续跑，Phase 2 会自动 create；若 Phase 2 之后仍缺，跑 `bash deploy-lite.sh --only <skill>` 或 `deploy-pipeline.sh` |
| `SKILL_ROLE_MAP 校验失败：impl 未上线` | 用户在 env 里加了 map 但 impl skill 还没 create | 提示：**先按方式 B 上线 impl**（见路径 B.3），再重跑 setup |
| `mtskills: command not found`（Lite 前端版） | mtskills 未安装，无法拉取外部 Skill | `npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com` 后重跑 setup |
| `Friday 下载失败 403`（Lite 前端版） | 运行 deploy 的 MIS 无对应 Skill 的 Friday 下载权 | 联系对应 Skill 作者（如 arch-design / max-material-dev 作者）申请授权后重跑 |

### A.5 部署后自查清单

setup 成功后 Claude 自动跑一遍自查，确认部署健康：

```bash
# 1. 7 (Lite 后端/前端) / 15+ (Pipeline) 个 agent 都在
multica agent list --output json | jq -r '.[] | .name' | grep '^sdlc-'
# Lite 后端期望：sdlc-lite-dispatcher / chain-analysis / design / contract / coding / review / knowledge
# Lite 前端期望：sdlc-lite-fe-pmo / fe-review-agent / fe-requirement-agent / fe-design-agent / fe-coding-agent / fe-autotest-agent / fe-deploy-agent
# Pipeline 期望：sdlc-tech-design / sdlc-coding / sdlc-test-prep / sdlc-integration-test / sdlc-ai-pmo（等）

# 2. squad 存在
multica squad list --output json | jq -r '.[] | .name'
# Lite 后端期望：sdlc-lite-backend
# Lite 前端期望：sdlc-lite-fe
# Pipeline 期望：sdlc-tech-design / sdlc-coding / sdlc-test-prep / sdlc-integration-test / sdlc-ai-pmo（等）

# 3. runtime pool 已挂
bash "$REPO_LOCAL/multica/set-runtime-pool.sh" --env "$TEAM_ENV_FILE" --dry-run

# 4. agent env 里 KM_ROOT_PARENT_ID 已注入
multica agent list --output json | jq -r '.[] | select(.name | startswith("sdlc-")) | .id' | head -1 | \
  xargs -I{} multica agent get {} --output json | jq -r '.custom_env.KM_ROOT_PARENT_ID // "未注入"'

# 5.（仅 Lite 前端版）前端外部 Skill 已挂载
for skill in arch-design design-spec max-material-dev duo-protocol ee-ones citadel ee-fedo; do
  echo "=== $skill ==="
  multica --workspace-id "$WORKSPACE_ID" skill list --output json | \
    jq -r --arg s "$skill" '.[] | select(.name | test($s; "i")) | .name'
done
```

自查通过 → 走 A.6 把本次 env 配置提交归档，归档完成后再收尾。

### A.6 把 env 提 PR 合回主干

团队专属的 `<team>.env` 是这个 workspace 部署配置的唯一存证，只留在本地磁盘上没有意义（换机器/其他同事排障都找不到），必须进版本库：

```bash
cd "$REPO_LOCAL"
BRANCH="feat/multica-env-<team>"
git checkout -b "$BRANCH"
git add "multica/$(basename "$TEAM_ENV_FILE")"
git commit -m "feat(multica): 添加 <team> $(basename "$TEAM_ENV_FILE")（<team> workspace {{Lite/Pipeline}} 部署配置）"
git push origin "$BRANCH"
```

推完分支后，去内部代码平台（git.sankuai.com 上 `mcp/general-ai-marketplace` 仓库页面）对这个分支发起合并请求（PR/MR），目标分支 `master`，走 review 后合入。**不要直接 push master**——这是团队 workspace 配置的唯一存证，需要走正常代码评审留痕。

**HARD-GATE**：这一步只提交 env 文件本身，不要把 `setup.sh` 产生的其它临时文件/`.bak` 备份一起带上；提交前用 `git status` 确认 diff 只有目标 env 文件一项。

PR 创建/合入后，告知用户"部署完成，可以创建第一个需求 Issue 了"，给出 workspace URL + 创建 Issue 的 CLI 命令。

---

## 路径 B：L2 skill 定制引导

**触发**：用户说「定制 coding 流程」「用我团队的规范」「同名 override」「role-map」等。

### B.1 判断是否需要定制

问用户：
1. 你想定制的是 **产出流程**（overview 章节 / design 接口格式 / plans 拆 Task 方式 / 单测断言库 / mock 手法等）？→ 走 L2 skill 定制（本节）
2. 还是想定制 **调度流转 / R-Gate 语义 / metadata schema**？→ **不允许**，见 [`multica/CLAUDE.md`](../../../../multica/CLAUDE.md) 铁律 3（Agent 指令零业务定制，跨 agent 契约官方定死）

只有 4 个 L2 slot 可定制：`chain-analysis-strategy` / `design-strategy` / `contract-strategy` / `coding-strategy`。

### B.2 方式 A：同名 override（简单，团队 skill 与官方同名）

场景：团队只想覆盖一个 slot、不介意 skill 叫官方名字。

```bash
# ① 用官方约定名把定制内容上线到 workspace（首次 create，后续改用 update）
multica --workspace-id "$WORKSPACE_ID" skill create \
  --name coding-strategy \
  --content-file ./team-coding-strategy.md

# ② 编辑本 workspace 的 <team>.env，把它加进 SKILL_PROTECT
echo 'SKILL_PROTECT=(coding-strategy)' >> "$TEAM_ENV_FILE"

# ③ 跑 setup
bash "$REPO_LOCAL/multica/setup-lite.sh" --env "$TEAM_ENV_FILE"
```

**HARD-GATE**：**顺序不能颠倒**——必须先 ① 上线到 workspace，再 ③ deploy。跳过 ① 只加 SKILL_PROTECT 是伪成功（deploy 打印"跳过 coding-strategy"但线上仍是官方原版）。详细事故背景见 [`pipeline-guide.md`](../../../../multica/docs/pipeline-guide.md) §7.2。

### B.3 方式 B：role→impl 映射（团队保留自家 skill 名字，2026-07-26 起支持）

场景：团队 skill 想叫 `foodtrade-coding-strategy`（保留自家身份，方便复用/识别）。

```bash
# ① 用团队自家名字把定制内容上线到 workspace
multica --workspace-id "$WORKSPACE_ID" skill create \
  --name foodtrade-coding-strategy \
  --content-file ./team-coding-strategy.md

# ② 编辑本 workspace 的 <team>.env，加 SKILL_ROLE_MAP（**不用手动加 SKILL_PROTECT**，setup 会自动加）
cat >> "$TEAM_ENV_FILE" <<EOF
SKILL_ROLE_MAP=(
  coding-strategy=foodtrade-coding-strategy
)
EOF

# ③ 跑 setup
bash "$REPO_LOCAL/multica/setup-lite.sh" --env "$TEAM_ENV_FILE"
```

setup 自动做 4 件事（详见 [`pipeline-guide.md`](../../../../multica/docs/pipeline-guide.md) §7.4）：
1. 校验 `foodtrade-coding-strategy` 已上线到 workspace（未上线报错停止）
2. 自动追加进 `SKILL_PROTECT`
3. 挂载 skill 到 `sdlc-*-coding-agent` 时用 impl 名字
4. Agent env 注入 `SKILL_CODING_STRATEGY=foodtrade-coding-strategy`

**HARD-GATE 同方式 A**：impl 必须先上线（步骤 ①），未上线 setup 报错停止，**不代为上传**。

### B.4 混用与回退

- **混用**：4 个 L2 slot 各选各自方式。比如 `design-strategy` 用方式 A（同名 override）、`coding-strategy` 用方式 B（role-map）——OK。
- **回退到官方**：删掉 `SKILL_PROTECT` / `SKILL_ROLE_MAP` 里的条目 → 重跑 setup → 官方版重新覆盖。

### B.5 常见坑

| 现象 | 根因 | 修复 |
|---|---|---|
| setup 报「SKILL_ROLE_MAP 校验失败：impl 未上线」 | 忘了先跑 `multica skill create` | 按 B.3 ① 上线 impl 再重跑 setup |
| deploy 打印「跳过 xxx」但线上仍是官方版 | 方式 A 顺序颠倒（先 SKILL_PROTECT 后上线，导致 skill 从未上线） | 补跑 `multica skill create` 后再 deploy |
| agent 挂载的 skill 是官方名字，不是团队 impl 名字 | 方式 B env 里 map 没生效 | 检查 `<team>.env` 是否 `SKILL_ROLE_MAP=(...)`（大写、`=` 无空格）；重跑 setup |

---

## 路径 C：进度快照

### C.1 先探测本 workspace 是 Pipeline 还是 Lite

```bash
# 从最近的父 Issue metadata 判断版本
multica issue list --limit 20 --output json | \
  jq -r '.issues[] | select(.parent_issue_id == null) | .metadata.version // "unknown"' | \
  sort | uniq -c | sort -rn | head -3
```

若最常见值：
- `lite` → 走 C.2 Lite 后端版分支
- `lite-frontend` → 走 C.2b Lite 前端版分支
- `pipeline` / `unknown` → 走 C.3 Pipeline 分支

### C.2 Lite 后端版进度快照

```bash
# 拉 Lite 父 Issue + 全部子 Issue
PARENT_ID="<用户提供或从 issue list 挑活跃的>"
multica issue get $PARENT_ID --output json | jq '{title, status, phase: .metadata.phase, workspace_dir: .metadata.workspace_dir}'
multica issue list --limit 200 --output json | \
  jq -r --arg pid "$PARENT_ID" '.issues[] | select(.parent_issue_id == $pid) | "\(.status)\t\(.updated_at[0:19])\t\(.title[0:70])"' | sort -k2
```

**Lite 后端版 R-Gate 顺序**（2026-07-26 起，per-repo 语义）：

```
R0 chain-analysis → R1 overview → R2 design → R3 plans →
├─ R3.5 testcases → R4 yaml-skeletons
└─ R-code（本仓所有 Task 完成一次评审）→ R-code-tail（per-repo 全量自审）
→ R7 全量验证 → 知识官复盘 → 关闭
```

### C.2b Lite 前端版进度快照

```bash
# 拉 Lite 前端父 Issue + 全部子 Issue
PARENT_ID="<用户提供或从 issue list 挑 version=lite-fe 的>"
multica issue get $PARENT_ID --output json | jq '{title, status, phase: .metadata.phase, workspace_dir: .metadata.workspace_dir, version: .metadata.version}'
multica issue list --limit 200 --output json | \
  jq -r --arg pid "$PARENT_ID" '.issues[] | select(.parent_issue_id == $pid) | "\(.status)\t\(.updated_at[0:19])\t\(.title[0:70])"' | sort -k2
```

**Lite 前端版 R-Gate 顺序**（R1~R8 线性流转，R4/R5 可并行）：

```
R1 需求SPEC → R2 架构+技术方案 → R3 开发任务(plan)
                                       ↓              ↘（并行）
                                  R4 编码实现        R5 测试准备
    （组件开发 × N仓并行 → 项目编码串行，dlc-branch 创建分支）
                                       ↓              ↙
                                  R6 测试执行 → R7 部署+集成验证 → R8 上线部署
```

**Lite 前端版产物路径**（`$WORKSPACE/frontend/`）：

| 文件 | Gate | 说明 |
|------|------|------|
| `spec.md` | R1 | 需求规格（requirement-agent 产出） |
| `arch-design.md` | R2 | 架构分析（design-agent，arch-design Skill） |
| `tech-design.md` | R2 | 前端技术方案（design-agent） |
| `dev-tasks.md` | R3 | 开发任务清单（物料/协议/业务三类） |
| `testplan/testcases.md` | R5 | 测试用例清单 |
| `testplan/testdata.md` | R5 | 测试数据构造清单 |
| `frontend/test-report.md` | R6 | 测试执行报告 |
| `deploy/delivery-report.md` | R7/R8 | 部署与交付报告 |

### C.3 Pipeline 进度快照

Pipeline 用父/子 Issue + Squad 分工模型，一个需求会有 PMO 派发的多个子 Issue（tech-design / coding / test-prep / integration-test），每个 Squad 内又有子子 Issue。

```bash
# 找到 PMO 入口 Issue（顶层）
multica issue list --limit 50 --output json | \
  jq -r '.issues[] | select(.assignee_type == "agent") | select(.metadata.phase != null) | "\(.status)\t\(.metadata.phase // "-")\t\(.title[0:70])\t\(.id[0:8])"'
```

**Pipeline R-Gate 顺序**（2026-07-26 起 R5/R6 语义颠倒对齐 Lite）：

```
R1 overview → R2 design → R3 plans → R3.5 testcases → R4 yaml-skeletons →
R5（per-repo sdlc-review-agent 评审）→ R6（per-repo ai-pr-code-review 自审）→
contract-test → R7 全量验证 → R8 上线部署
```

### C.4 输出模板

**必须在最后明确告诉用户"你现在需要做什么"**：

```
## 当前进度：<父 Issue 标题>

版本：{{Lite / Pipeline}}
整体位置：{{当前 phase}}

| Sub Issue | 内容 | 状态 |
|---|---|---|
| ... | ... | ✅/⏳/❌ |

**你现在需要做**：
- <具体动作 + 回什么词 + @谁>
```

---

## 路径 D：实时监控

用 Monitor 工具每 30 秒轮询关键 issue 状态，有变化时主动通知。

**监控逻辑**：
1. 找到所有 `in_progress` 或 `in_review` 的 sub-issue
2. 检查其 `issue runs` 最后 run 时间（超过 2 小时无新 run → 可能卡住）
3. 状态变化（`todo→in_progress`、`in_review→done`）时发通知
4. 评审员发出 `SDLC_VERDICT: PASS/FAIL` 时通知用户"该回复通过了"

**关键告警信号**：
- run STATUS = `failed` + error = `runtime went offline` → 提示用户 rerun
- review issue `done` 但父 Issue 无新评论 → 评审员可能没关 issue
- issue `in_review` 超过 4 小时无新评论 → 提示用户检查

**推荐用 `multica-lite-regression` skill 做自动化端到端回归**（`/multica-lite-regression`），它自动 poll + LGTM + 报告——避免人肉盯（详见 `multica/skills/lite-regression/SKILL.md`）。

---

## 路径 E：卡点诊断

**先拿数据，再判断根因**：

```bash
# 看 issue 最近的 run 记录
multica issue runs <issue-key>

# 看最新评论 + 时间
multica issue comment list <issue-key> --output json | \
  jq -r '.[-3:][] | "\(.created_at[0:19])  \(.content[0:100])"'
```

### 常见卡点和修复

| 现象 | 根因 | 修复 |
|---|---|---|
| run 显示 `runtime went offline` | agent 的 runtime 离线 | `multica agent update <id> --runtime-id <当前在线 runtime>` 然后 `multica issue rerun <key>` |
| review issue `done` 但流程没推进 | 评审员发了 PASS 但父 Issue 没收到唤醒 | 手动在父 Issue 评论 `通过` 或 `@dispatcher 请推进`，rerun 调度员 |
| issue `in_review` 超 4 小时无评论 | agent run 没触发或卡住 | `multica issue runs <key>` 看状态 → `multica issue rerun <key>` |
| env var 缺失导致 init 失败 | GIT_AUTHOR_NAME/EMAIL / KM_ROOT_PARENT_ID 等未配置 | `multica agent env set <id> --custom-env '{"KEY":"..."}'` |
| SKILL_ROLE_MAP 校验失败 | impl skill 未上线 | 见路径 B.5 |
| coding-agent 卡在 Task-N 生成 | 单 Task 生成时间长（正常 5-15 min） | 耐心等 15 min，超时后 `multica issue rerun` |
| plans 里 Task 拆得太多 → coding-agent 一次 run 跑不完 | context 撑爆 | agent 会自己 stop、下次唤醒续跑（第零步从 progress.md 恢复位置） |
| `SDLC_VERDICT: CLARIFICATION_NEEDED` — design-spec 缺失 | 前端外部 Skill 未导入 workspace | 从 Friday SkillHub 导入 `design-spec` → `multica skill create --name design-spec --content-file <path>` → 重跑 |
| material-agent 报 `duo-cli not found` | duo-cli 未安装（物料发布依赖） | `npm i -g @meishi/duo-cli --registry=http://r.npm.sankuai.com` → rerun |
| R-code 卡在物料→协议之间 | material-agent DONE 后调度员没派 protocol-agent | 手动在父 Issue 评论 `@dispatcher 物料已完成，请派 protocol-agent` |
| fe-ai-review 自审报 P0 不建议合并 | 代码有编译/运行时错误 | material/protocol-agent 修复 P0 后重跑 R-code-tail（≤2 轮），超限如实说明交调度员 |
| R6 duo-fedo CI/CD 构建失败 | 前端构建配置错误或依赖缺失 | 转 Blocked，@reporter 排查构建日志 → 修复后 rerun knowledge-agent |
| pmo 报 `version=lite，非 lite-fe` | Issue metadata version 写成了 `lite` 而非 `lite-fe` | `multica issue metadata set <id> --key version --value "lite-fe"` → rerun pmo |
| `dlc-branch Skill` 执行失败 | ones-cli 或 duo-cli 未安装，或 ONES 链接解析失败 | 检查 ones-cli（`ones -v`）/ duo-cli（`duo -V`）是否安装；检查 Issue metadata 中 ones_url 是否正确 |
| coding-agent 创建分支后 push 被 git hook 拦截 | ONES 关联未建立（dlc-branch Skill「ONES 创建分支（P0）」未完成） | 确认 dlc-branch Skill 执行时 ones_url 有效，ONES 分支关联幂等重试即可 |

**诊断完必须给出可执行的修复命令，不只是描述问题。**

---

## 路径 F：操作引导

根据当前 Gate，给出用户需要做的**具体操作**：

### Lite 后端版

| 当前 Gate | 你需要做 |
|---|---|
| R0 chain-analysis PASS | 去看 `chain-analysis.md`（学城 URL） → 在父 Issue 回复 `通过` |
| R1 overview PASS | 去学城看 overview → 在父 Issue 回复 `通过` |
| R2 design PASS | 去学城看 design → 在父 Issue 回复 `通过` |
| R3 plans PASS | 去 workspace 仓看 `backend/plans/*.md` → 在父 Issue 回复 `通过` |
| R3.5 testcases PASS | 去学城看 testcases → 回复 `通过` |
| R4 yaml-skeletons PASS | 去 workspace 仓看 `yaml-skeletons/*.yaml` → 回复 `通过` |
| R-code PASS（per-repo） | 去看开发员 push 的 PR + 单测覆盖情况 → 回复 `通过` |
| R-code-tail 完成 | 不需要人工——coding-agent 自跑，通过或达 2 轮自修上限自动推进 R7 |
| R7 PASS | 去看全量验证报告 → 回复 `通过` → 知识官复盘 → 关闭 |

### Lite 前端版

| 当前 Gate | 你需要做 |
|---|---|
| R1 需求SPEC PASS | 去学城看 spec 文档 → 在父 Issue 回复 `通过` |
| R2 架构+技术方案 PASS | 去学城看 arch-design + tech-design → 在父 Issue 回复 `通过` |
| R3 开发任务 PASS | 去学城看 dev-tasks → 在父 Issue 回复 `通过`。R3 通过后 pmo 并行创建 R4（编码）+ R5（测试准备）子 Issue |
| R4 编码实现 PASS | 去看物料组件源码 + DUO 协议 + 业务代码 diff → 在编码子 Issue 回复 `通过`。组件按仓库并行，各仓库子 Issue 全部 done 后进项目编码 |
| R5 测试准备 PASS | 去学城看 testcases + testdata → 在测试准备子 Issue 回复 `通过` |
| R6 测试执行 PASS | 去看 test-report.md + Flow 用例执行情况 → 在测试执行子 Issue 回复 `通过`（R4+R5 均完成后才创建） |
| R7 部署验证 PASS | 去看泳道部署结果 + 集成验证报告 → 在部署子 Issue 回复 `通过` |
| R8 上线部署 | 合并 PR + 生产发布，无需 AI 预审，人工确认即完成 → 回复 `通过` → 收尾 |

### Pipeline 版

| 当前 Gate | 你需要做 |
|---|---|
| R1/R2/R3 PASS | 去学城看对应文档 → 在对应子 Issue 回复 `通过` |
| R3.5/R4 有 ❌ must-fix | 不需要操作，leader 自动通知 agent 修改（新规则） |
| R4 通过，分配开发员 | 在编码入口 Issue 回复 `甲负责 <仓A> 乙负责 <仓B>` + @coding-leader |
| R5 PASS（per-repo 评审）| 去看代码 → 回复 `通过` |
| R6 完成 | 不需要人工——coding-agent 自跑 |
| Contract-test 完成 | 去看接口级单测报告 → 回复 `通过` |
| R7 PASS | 去看全量验证 → 回复 `通过` → 收尾 |

**格式**：永远在最后用「**你现在需要做**：」明确告诉用户。

**关键词严格性**：回复必须用 `通过`（中文两字，无标点无前缀），pmo/dispatcher 消费严格匹配。见 [`multica/references/lite/agents/dispatcher-agent.md`](../../../../multica/references/lite/agents/dispatcher-agent.md) 和 [`multica/references/lite-fe/squad.md`](../../../../multica/references/lite-fe/squad.md)「机读标记体系」段。

---

## 路径 G：工作流问答

### G.1 三版本速查

| 维度 | Pipeline 完整版 | Lite 后端版 | Lite 前端版 |
|---|---|---|---|
| **Squad 数量** | 5 + PMO | 1 | 1 |
| **Agent 数量** | 15+ | 7 | 7 |
| **R-Gate 数** | 8（R1/R2/R3/R3.5/R4/R5/R6/R7）| 8（R0/R1/R2/R3/R3.5/R4/R-code/R7） | 8（R1/R2/R3/R4/R5/R6/R7/R8） |
| **前端能力** | ✅ fe-design + fe-coding | ❌ | ✅ 物料/协议/业务/测试/部署全流程 |
| **集成测试** | ✅ | ❌ | ✅ autotest-agent 一体化 |
| **泳道部署** | ✅ | ❌ | ✅ deploy-agent（ee-fedo CI/CD） |
| **每 Gate 关卡** | 2 层（review-agent 预审 + 人工）| 1 层（评审员 AI + 人工 LGTM）| 1 层（review-agent AI + 人工 LGTM）|
| **version 字段** | `pipeline` | `lite` | `lite-fe` |
| **Squad 名** | sdlc-tech-design 等 5 个 | sdlc-lite-backend | sdlc-lite-fe |
| **入口脚本** | `setup.sh` | `setup-lite.sh` | `setup-lite-fe.sh` |
| **产物目录** | `$WORKSPACE/backend/` + `$WORKSPACE/frontend/` | `$WORKSPACE/backend/` | `$WORKSPACE/frontend/` |

选哪个见路径 A.2 决策树。

### G.2 R-Gate 名词解释（2026-07-26 更新，2026-07-29 新增前端版）

| Gate | 说的是什么 |
|---|---|
| **R0** | 链路分析产出（chain-analysis.md + `doc_tree.repos[]`），Lite 后端/前端独有 gate |
| **R1** | overview（后端）/ demand-spec（前端）概设产出 + AI 评审 + 人工 LGTM |
| **R2** | design（后端）/ tech-design（前端）详设产出 + 评审 + LGTM |
| **R3** | plans（后端）/ dev-tasks（前端）执行计划产出 + 评审 + LGTM |
| **R3.5** | testcases 契约用例产出 + 评审 + LGTM（后端版独有，前端版无） |
| **R4** | yaml-skeletons CT 骨架产出 + 评审 + LGTM（后端版独有，前端版无） |
| **R5**（Pipeline）| per-repo 代码评审（`sdlc-review-agent` 评审 + LGTM）—— **本仓所有 Task 完成后一次评审整仓改动** |
| **R6**（Pipeline）| per-repo AI 自审（`ai-pr-code-review` 全量自审，≤ 2 轮自修）—— R5 通过后 coding-agent 自跑，不建 gate |
| **R-code**（Lite 后端/前端）| 对齐 Pipeline R5：per-repo 评审 + LGTM（后端 `sdlc-lite-review-agent`，前端 `sdlc-lite-fe-review-agent`） |
| **R-code-tail**（Lite 后端/前端）| 对齐 Pipeline R6：per-repo 全量自审（后端 `ai-pr-code-review`，前端 `fe-ai-review`） |
| **R6**（Lite 前端）| PR + CI/CD（委托 duo-fedo + ee-code）+ 评审 + LGTM —— 前端版独有 gate |
| **R7** | 全量验证 + 评审 + LGTM（后端 YamlScenarioRunner 跑 CT，前端交付报告） |

**⚠️ 2026-07-26 语义变更**：
- 老 R5 = per-Task 单测 AI 自审（DELETED），老 R6 = per-Task 实现评审（DELETED）
- 新 R5/R6 语义颠倒 + 挪到 per-repo，与 Lite R-code / R-code-tail 完全对齐

**⚠️ 2026-07-29/08-17 前端版（sdlc-lite-fe）差异**：
- 前端版 R-Gate 编号 R1~R8，与后端版 R0~R-code 不同
- 前端版无独立链路分析 Gate（arch-design 融入 R2 方案设计阶段）
- 前端版 R4 编码阶段：组件开发按物料仓库分组（一仓一子 Issue 可并行），全部仓库完成后进项目编码（DUO 协议→业务逻辑）
- 分支创建由 **dlc-branch Skill** 统一处理（识别 DUO 类型仓库 / 集成 ONES 关联），分支名仅进程内使用不写入 metadata
- 前端版 R5 = 测试准备（用例+数据+参数），可与 R4 并行创建
- 前端版 R6 = 测试执行（Flow 用例 + 执行 + 报告），依赖 R4+R5 均完成
- 前端版 R7/R8 = 部署验证 + 上线部署（deploy-agent + ee-fedo）

### G.3 常见问题

**Q：为什么需要我「通过」？调度员不能自己判断吗？**
调度员不读文档、不评价内容——R-Gate 的通过权永远在人手里。调度员只负责路由，你说"通过"才推进。

**Q：为什么 per-Task 不再走 R6 评审？**
`ai-pr-code-review` skill 慢，per-Task N 次会把等待时间放大 N 倍。改为 per-repo 一次评审整仓改动，还剩最后一次 R6/R-code-tail 自审做 zero-error 保底（≤ 2 轮自修）。

**Q：Lite 前端版和 Lite 后端版有什么区别？**
- **Agent 不同**：后端版 7 个 `sdlc-lite-*-agent`（含 dispatcher / chain-analysis / design / contract / coding / review / knowledge），前端版 7 个 `sdlc-lite-fe-*-agent`（pmo / requirement-agent / design-agent / coding-agent / autotest-agent / review-agent / deploy-agent）
- **R-Gate 编号不同**：前端版 R1~R8，后端版 R0~R-code；前端版无 R3.5/R4（无契约骨架阶段），但有 R5 测试准备、R6 测试执行、R7 部署验证、R8 上线部署
- **开发阶段不同**：后端版是多实例 TDD 循环（coding-agent，per-repo 并行），前端版是单 coding-agent 总协调（组件开发按仓库分组 → 项目编码，分支由 dlc-branch Skill 统一创建）
- **测试阶段不同**：后端版无独立测试 agent，前端版有 autotest-agent 一体化完成用例设计+数据准备+测试执行
- **部署阶段不同**：后端版无独立部署 agent，前端版有 deploy-agent（ee-fedo CI/CD + 泳道部署）
- **产物目录不同**：后端版 `$WORKSPACE/backend/`，前端版 `$WORKSPACE/frontend/` + `testplan/` + `deploy/`
- **version 字段不同**：后端版 `lite`，前端版 `lite-fe`

**Q：Lite 前端版和 Pipeline 前端支线有什么区别？**
- **编排复杂度**：Lite 前端版 1 Squad 7 agent（`sdlc-lite-fe` 单 Squad，pmo 兼任调度中心），Pipeline 5 Squad 15+ agent
- **关卡**：Lite 前端版单关卡（review-agent AI + 人工 LGTM），Pipeline 双层关卡（review-agent 预审 + 人工确认）
- **能力范围**：Lite 前端版覆盖需求→方案→编码→测试→部署全流程（R1~R8），Pipeline 支持前后端联合编排 + 集成测试 + 泳道部署
- **Squad 架构**：Lite 前端版无独立 Leader，pmo 直接派发子 Issue 给执行 Agent；Pipeline 每个 Squad 有独立 Leader 转发

**Q：Lite 前端版的前端外部 Skill 是什么？为什么要通过 mtskills 安装？**
前端外部 Skill（arch-design / design-spec / max-material-dev / duo-protocol / ee-ones / ingee-flex / citadel / ee-fedo 等）来自 Friday SkillHub，不是本仓维护的。它们通过 `sdlc-lite-fe.env` 中的 `FRIDAY_SKILLS_MOUNTS` 声明，由 `setup-sdlc-lite-fe.sh` 在 Phase 2 自动通过 `mtskills i` 拉取 → 上传到 workspace → 挂给指定 agent。任一拉取/上传失败直接 `exit 1`，不静默跳过。

**Q：SKILL_ROLE_MAP 和 SKILL_PROTECT 什么关系？**
- SKILL_PROTECT：deploy 时跳过不覆盖的 skill 名单（"保护"作用）
- SKILL_ROLE_MAP：声明 role→impl 映射，setup 自动挂 impl + 注入 env + 追加 impl 进 SKILL_PROTECT（"映射 + 联动保护"）
- 方式 A（同名 override）用 SKILL_PROTECT；方式 B（自家名字）用 SKILL_ROLE_MAP。见路径 B。

**Q：Amendment 是什么？什么时候触发？**
当某个阶段的文档需要因架构变更而修改时触发（比如 Phase 2 发现 Phase 1 的设计有误）。触发后会并行创建"修改文档"和"评估影响"两个子 issue，你确认后继续。

**Q：为什么有时候流程会卡住很久？**
常见原因：
1. 评审员发完报告但没关 issue（流程靠 issue 关闭事件触发）
2. agent 的 runtime 离线（daemon 挂了或换机器了）
3. env var 缺失导致 dlc-init 失败
4. plans 拆 Task 太多，coding-agent 需要多次唤醒续跑（正常，不算卡住）

**Q：各 agent 是干什么的？**

**Pipeline / Lite 后端版**：
- **调度员 / PMO**：唯一的状态机 driver，不写代码不写文档，只做路由
- **链路分析师**：用 crkg 分析调用链，产 `chain-analysis.md` + `doc_tree.repos[]`
- **方案员**：产 overview / design / plans 三段（委托 L2 `design-strategy`）
- **契约员**：产 testcases + yaml-skeletons（委托 L2 `contract-strategy`）
- **开发员**（甲/乙/丙）：每人负责一个仓的 TDD 循环（委托 L2 `coding-strategy`）；本仓所有 Task 完成后交 R5/R-code 评审、通过后跑 R6/R-code-tail 自审
- **评审员**：AI 预审各 gate 产物（不替代人工 LGTM）
- **知识官**：产 retrospective.md + KM 复盘、关父 Issue

**Lite 前端版**（7 个 `sdlc-lite-fe-*-agent`，Squad 名 `sdlc-lite-fe`）：
- **sdlc-lite-fe-pmo**（调度员）：唯一入口，意图识别、创建子 Issue、阶段流转（R1~R8）、doc_tree 维护、收尾关闭；兼任 Squad 调度中心，无独立 Leader
- **sdlc-lite-fe-requirement-agent**（需求分析师）：PRD → 结构化需求 SPEC，PM 澄清循环 + AI 预审 + PM 确认（R1）
- **sdlc-lite-fe-design-agent**（方案设计师）：arch-design（架构分析）+ tech-design（技术方案）+ dev-tasks（任务拆分），委托 `arch-design` + `design-spec` Skill，产物写学城（R2/R3）
- **sdlc-lite-fe-coding-agent**（编码员）：编码总协调——按物料仓库分组组件任务→每仓创建一个组件开发子 Issue（max-material-dev，仓间并行）→创建项目编码子 Issue（DUO 协议→业务逻辑）；分支由 `dlc-branch` Skill 创建（R4）
- **sdlc-lite-fe-autotest-agent**（测试员）：测试准备（用例+数据+参数，R5）+ 测试执行（Flow 用例+执行+报告，R6）
- **sdlc-lite-fe-review-agent**（评审员）：全 gate AI 预审（R1~R7 全覆盖），PASS/FAIL + must-fix 分级
- **sdlc-lite-fe-deploy-agent**（部署员）：泳道部署 + 集成验证（R7）+ 合并 PR + 生产发布 + KB 沉淀（R8），委托 `ee-fedo`

---

## 使用规范

1. **始终查实际数据**：不要凭记忆回答进度，先调 `multica issue list`
2. **诊断必给命令**：卡点分析后必须给出可执行的修复命令
3. **引导必给用词**：告诉用户回复什么词（`通过` / `变更确认` 等），不要让用户猜
4. **部署 hand-hold 必逐项问**：不能一次性丢一堆参数让用户查；每项都给查询命令
5. **HARD-GATE 顺序不能颠倒**：方式 A/B 定制都必须先上线 skill 再 deploy；用户跳步就是伪成功
6. **术语与文档对齐**：R5/R6/R-code/R-code-tail 用 2026-07-26 起的新语义，别用老 DLC-Squad 时代的 R5=自审 R6=评审

---

## 参考文档

- **协议契约**：[`multica/references/06-metadata-schema.md`](../../../../multica/references/06-metadata-schema.md)（唯一真源）
- **Lite 后端版使用指南**：[`multica/docs/lite-guide.md`](../../../../multica/docs/lite-guide.md)
- **Lite 前端版使用指南**：[`multica/docs/lite-guide-frontentd.md`](../../../../multica/docs/lite-guide-frontentd.md)
- **Pipeline 使用指南**：[`multica/docs/pipeline-guide.md`](../../../../multica/docs/pipeline-guide.md)
- **CLAUDE.md 铁律**：[`multica/CLAUDE.md`](../../../../multica/CLAUDE.md)（尤其铁律 3/4 关于定制机制）
- **回归测试 skill**：`/multica-lite-regression`（端到端跑 Lite 流水线自动化验证）

