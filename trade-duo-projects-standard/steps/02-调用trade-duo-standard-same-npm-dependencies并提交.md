# Step 02：调用 trade-duo-standard-same-npm-dependencies 并提交（commit message 含明细）

## 输入

沿用 Step 01 的输出（至少需要 `localDir`，以及 `ohDependenciesPatchedToEmptyArray` 等标记）。

## 目标

1. 在目标 DUO 仓库中执行 `trade-duo-standard-same-npm-dependencies` 全流程完成三端一致性改造
2. 在目标仓库创建 1 个 commit
3. commit message 固定标题为：
   - `使用 trade-duo-standard-same-npm-dependencies 进行 npm 包三端一致性改造`
4. commit message 必须包含本次改造的关键结果明细（文件 + 依赖变化）

## 执行步骤

### 1) 进入目标仓库并确认状态

```bash
cd "<localDir>"
git status --porcelain
```

若存在未提交改动（不应发生，除非 Step 01 补齐 `ohDependencies.json`），允许继续，但要把该信息纳入 commit message 明细中。

### 2) 调用 `trade-duo-standard-same-npm-dependencies` skill 完整流程

在 **目标仓库根目录**执行 `trade-duo-standard-same-npm-dependencies`：

- 必须严格复用该 skill 的步骤（01-06），包含必要的双检与重复依赖检测。
- **可选加速**：若需用脚本生成清单 diff 与 `result/trade-packages-changelist.md`，可使用仓库内 **`trade-duo-projects-standard/scripts/apply-standard.mjs`**（须先 `npm install`，详见 `SKILL.md`「可选：apply-standard.mjs」）；脚本产出仍须与学城/k-hub 结论及步骤 4 降级校验一致，不得绕过 `trade-duo-standard-same-npm-dependencies` 的规则。
- 过程中产生的中间产物若写入 **工作区**（如宿主仓库的 `.temp/trade-duo-standard-same-npm-dependencies/`），可保留不提交；**仅提交 DUO 目标仓库内**应改动的清单文件。

**标准版本与学城（与 `trade-duo-standard-same-npm-dependencies` 一致）**：

- 权威版本线以学城 [标准化依赖版本](https://km.sankuai.com/collabpage/2747476284) 为准；步骤 01 通常需 **k-hub MCP** 查询知识库，必要时用 **oa-skills citadel getMarkdown --contentId 2747476284** 拉取学城正文（需 MIS/SSO）。
- 若 **citadel 无法拉取学城**（未配置 MIS、401 等）：不得伪造学城表格内容；按 `trade-duo-standard-same-npm-dependencies` 的降级策略，可仅用 **k-hub** 等已获取的知识库文档执行改造，并在最终 **commit message 的「说明」**中写明：「学城未直连，标准版本以 k-hub/降级路径为准，请人工与学城 2747476284 复核」。
- 执行完 `trade-duo-standard-same-npm-dependencies` 的 **步骤 06** 时：若目标仓库 **`.gitignore` 尚未包含 `.temp/`**，可追加一行 `.temp/`（避免误将本地临时目录提交入库）；若本次修改了 `.gitignore`，须纳入 **同一 commit** 的变更说明（与清单改动一起描述）。

执行完成后，确保至少满足以下之一：
- `dependencies.json` / `componentsMap.json` 有预期变更（常见）
- 或者确认无需变更（此时不应创建空 commit；应停止并报告“无需改动”）

### 3) 汇总 diff，生成「变更明细」

将下列内容**落盘到** **`.temp/trade-duo-projects-standard/result/`**（与 Step 01 共用该目录）：

- **`trade-packages-changelist.md`**：若 `trade-duo-standard-same-npm-dependencies` 生成了 `.temp/trade-duo-standard-same-npm-dependencies/result/changelist.md`（或等价路径），**复制**到该文件名；若无单独文件，则将变更说明整理为该 Markdown。
- **`step02-summary.md`**：新建，至少包含：目标仓库路径、`git log -1 --oneline`、变更文件列表、依赖升级/迁移摘要、componentsMap 同步摘要、学城/k-hub 说明（若有）、是否写入 `block-commit.flag`（若有）。

要求对以下文件做变更提取（若文件存在且被修改）：

- `dependencies.json`
- `ohDependencies.json`
- `componentsMap.json`

生成明细的要求：

- **文件维度**：哪些文件变了（新增/修改）
- **依赖维度（dependencies/ohDependencies）**：
  - 新增了哪些包（name@version）
  - 删除了哪些包（name@version）
  - 升级/降级了哪些包（name: old → new）
  - 是否发生「三端兼容依赖从 ohDependencies 迁移到 dependencies」（列出包名）
- **componentsMap 维度（若存在）**：
  - `npmVersion` 变化的条目列表（name: old → new）
  - URL 中带版本号的资源是否随之更新（若可识别，按条目列出）

> 提示：明细允许用脚本或程序解析 JSON 前后差异；禁止仅用“更新了一些依赖”这类模糊描述。

### 4) 选择性 stage（只提交目标清单文件）

只 stage 与标准化直接相关的文件，通常为：

- `dependencies.json`
- `ohDependencies.json`（若存在/被创建/被修改）
- `componentsMap.json`
- **`.gitignore`**（仅当本流程按步骤 06 追加了 `.temp/` 等忽略规则时）

如果 `trade-duo-standard-same-npm-dependencies` 在工作区其他目录生成了临时文件或报告（如宿主侧的 `.temp/trade-duo-standard-same-npm-dependencies/`），**默认不提交**；确保 **不要** `git add` DUO 仓库外的路径。

```bash
git add dependencies.json componentsMap.json || true
git add ohDependencies.json || true
git add .gitignore 2>/dev/null || true
git status --porcelain
```

### 5) 创建 commit（message 含明细）

commit message 规范：

- 第一行固定：
  - `使用 trade-duo-standard-same-npm-dependencies 进行 npm 包三端一致性改造`
- 需要包含一个「结果明细」段落，建议格式：

```text
使用 trade-duo-standard-same-npm-dependencies 进行 npm 包三端一致性改造

变更文件：
- dependencies.json（modified）
- ohDependencies.json（created/modified/unchanged）
- componentsMap.json（modified）

依赖变更摘要：
- 新增：pkg-a@x.y.z, pkg-b@x.y.z
- 删除：pkg-c@x.y.z
- 升级：pkg-d 1.2.3 -> 2.0.0
- 降级：pkg-e 4.5.6 -> 4.5.0
- 迁移（oh -> deps）：pkg-f, pkg-g

componentsMap 同步：
- pkg-d npmVersion 1.2.3 -> 2.0.0（URL 已同步）
- pkg-e npmVersion 4.5.6 -> 4.5.0（URL 已同步/无 URL）

说明：
- Step01 补齐 ohDependencies.json 为空数组（如适用）
- 学城/k-hub：若未直连学城 2747476284，说明采用的降级来源并请人工复核
- .gitignore：若本提交包含追加 `.temp/`，在此说明
```

提交命令要求使用 heredoc（避免转义问题）：

```bash
git commit -m "$(cat <<'EOF'
使用 trade-duo-standard-same-npm-dependencies 进行 npm 包三端一致性改造

<按上述格式填入明细>

EOF
)"
```

### 6) 校验提交完成

```bash
git status --porcelain
git log -1 --oneline
```

将 `git log -1 --oneline` 与完整 `git log -1`（或 commit hash）**追加或合并**进 **`.temp/trade-duo-projects-standard/result/step02-summary.md`**，保证该文件为本次运行的最终摘要。

预期：
- 工作区清洁（除非有明确不提交的临时产物）
- HEAD 提交 message 符合标题 + 明细格式
- **`.temp/trade-duo-projects-standard/result/`** 下已具备 `step01.json`、`mep-repo-settings.json`（Step 1 成功时）、`step02-summary.md`、`trade-packages-changelist.md`（或说明为何为空）

## 失败处理

- 若 Step 02 执行后没有任何文件改动：不得创建空 commit；应退出并报告「已执行检查，目标仓库无需做三端一致性改造」；并在 **`result/step02-summary.md`** 中说明「无清单改动、未提交」。
- 若仅产生临时文件改动（如 `.temp/`）：不得提交临时文件；应清理或保留在工作区但不提交，并明确说明。

