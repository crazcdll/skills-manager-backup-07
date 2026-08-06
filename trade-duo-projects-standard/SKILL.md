---
name: trade-duo-projects-standard
description: DUO 项目标准化：Step1 通过 ee-mep（mep code，需 Node 18+ 或安装 @ee/mep-cli）拉取指定分支并校验清单；Step2 调用 trade-duo-standard-same-npm-dependencies（学城优先，k-hub/降级时需 commit 说明）完成三端一致性改造并生成含明细的 commit。
---

# DUO 项目标准化（依赖三端一致性改造 + 自动提交）

面向 **DUO 类型项目**的标准化流程：Step 1 基于 `ee-mep`（`mep code`）先获取仓库关键元信息（用于确认仓库可访问/分支存在等）并拉取用户指定分支代码，完成清单文件校验；Step 2 复用 `trade-duo-standard-same-npm-dependencies` 对依赖做三端一致性改造，最后在目标仓库生成一个带**变更明细**的提交。

## 使用方式（用户输入）

用户执行该 skill 时，需要提供两个参数：

1. **DUO 配置仓库**：例如 `ssh://git@git.sankuai.com/nibfe/duo-hotel-order-submit.git`
2. **开发分支**：例如 `feature/fedo-367821`

## 环境与前置条件（Agent 执行前自检）

1. **`mep`（ee-mep / code-cli）**：需能在 PATH 中执行 `mep`。若 `command not found: mep`，可先安装：`npm install -g @ee/mep-cli --registry=http://r.npm.sankuai.com`，再重试 Step 1。
2. **Node.js 与 `mep code`**：`mep code repo settings` 依赖全局 `fetch`（**Node.js 18+**）。若报错 `ReferenceError: fetch is not defined`，请切换到 **Node.js 18 或更高版本**（如 `nvm use 18` / `nvm use 20`）后再执行 `mep`，**不要使用 Node 16 降级方案**。
3. **`trade-duo-standard-same-npm-dependencies` 与标准版本**：权威主线为学城 [标准化依赖版本](https://km.sankuai.com/collabpage/2747476284)；子流程依赖 **k-hub MCP** 与/或 **oa-skills citadel** 拉取学城正文。若 citadel 因未配置 **MIS** / SSO 无法拉取学城，允许按 `trade-duo-standard-same-npm-dependencies` 的降级策略仅用 k-hub 知识库继续，但须在 Step 2 的 **commit message「说明」**中注明「学城未直连，已用知识库/降级路径」，并提示人工与学城表复核。
4. **中间产物**：工作区 `.temp/trade-duo-projects-standard/`、`.temp/trade-duo-standard-same-npm-dependencies/` 等**不要提交到 DUO 目标仓库**；若执行了 `trade-duo-standard-same-npm-dependencies` 的步骤 06，可在目标仓库 `.gitignore` 中追加 `.temp/`（与清单类提交同一 commit 或按团队规范）。

## 结果输出目录（必须）

本 skill 在宿主工作区产生的**可交付记录**，一律写入：

**`.temp/trade-duo-projects-standard/result/`**

执行前先 `mkdir -p .temp/trade-duo-projects-standard/result`。至少包含：

| 阶段 | 建议文件名 | 内容 |
|------|------------|------|
| Step 1 | `step01.json` | 仓库 URL、分支、`localDir`、清单校验标记等（结构见 Step 01） |
| Step 1 | `mep-repo-settings.json` | `mep code repo settings --json` 的原始 JSON 输出（成功时） |
| Step 2 | `trade-packages-changelist.md` | 若执行了 `trade-duo-standard-same-npm-dependencies`，将其 `changelist.md`（或等价报告）**复制或汇总**到此路径 |
| Step 2 | `step02-summary.md` | 本次改造与提交的摘要：是否产生 commit、`git log -1` 一行、变更文件列表、学城/k-hub 降级说明（若有） |

对话中可再复述要点，但**不得省略**上述目录下的落盘文件（失败时可在 `result/` 写入 `error.txt` 或 `error-step01.txt` 记录原因）。

### 可选：`apply-standard.mjs` 是否要进仓库？

**建议保留。** 仓库内已提供 **`trade-duo-projects-standard/scripts/apply-standard.mjs`** 与 **`trade-duo-projects-standard/data/km-5241-raw.md`**（k-hub《整合版》表格快照），避免每次在 `.temp` 里临时生成脚本。注意：

- 脚本**不能替代** `trade-duo-standard-same-npm-dependencies` 的完整人工/k-hub/学城流程；仅当与 skill 规则一致、且已理解降级风险时作为**自动化辅助**。
- 标准版本以 **学城 2747476284** 为准；更新 `data/km-5241-raw.md` 时请与知识库/学城对齐。
- 依赖：在 `trade-duo-projects-standard/scripts/` 下执行 `npm install`（需 `semver`，`node_modules` 已 gitignore）。
- 运行示例（在 **trade-skills 根目录**）：  
  `node trade-duo-projects-standard/scripts/apply-standard.mjs --repo .temp/trade-duo-projects-standard/work/<克隆目录名>`  
  报告写入 **`.temp/trade-duo-projects-standard/result/`**（可用 `--result-dir` 覆盖）。

## 🚀 流程自动执行指南

总共需要执行 **2** 个步骤，请一次性无中断地完成全部节点；每个节点开始前需要查看对应的 step 文档（标注了 @stepName），然后立即执行该节点并继续下一步，直到所有节点完成。

执行过程中不得停下来等待用户确认或输入，除非节点文档明确要求澄清信息。

### 📝 步骤清单

#### 第 1 步：拉取仓库指定分支并校验清单文件

- **描述**：通过 `ee-mep`（`mep code`）获取仓库信息后 clone/checkout 用户提供的仓库与分支；检查 `componentsMap.json`、`dependencies.json`、`ohDependencies.json` 是否存在/有效（`ohDependencies.json` 允许缺省或为空，其余两个不允许）。
- **Step**：@trade-duo-projects-standard/steps/01-拉取并校验清单文件.md
- **后续步骤**：执行第 2 步（调用 `trade-duo-standard-same-npm-dependencies` 改造并提交）

#### 第 2 步：调用 trade-duo-standard-same-npm-dependencies 改造并生成 commit（含明细）

- **描述**：在目标仓库执行 `trade-duo-standard-same-npm-dependencies` 完整流程；改造完成后生成一个 commit，commit message 固定以「使用 trade-duo-standard-same-npm-dependencies 进行 npm 包三端一致性改造」开头，并在 message 中附带本次变更的关键结果明细（文件、包、版本变化、迁移等）；同时将 **`step02-summary.md`**、**`trade-packages-changelist.md`** 等写入 **`.temp/trade-duo-projects-standard/result/`**（详见 Step 02）。
- **Step**：@trade-duo-projects-standard/steps/02-调用trade-duo-standard-same-npm-dependencies并提交.md
- **后续步骤**：流程完成

## ⚠️ 执行规则（必须遵守）

1. **目标仓库与分支必须来自用户输入**：不得默认 main/master，也不得切换到其他分支。
2. **不得伪造文件或结果**：
   - `componentsMap.json`、`dependencies.json` 必须真实存在且为有效 JSON；否则立即失败并报告原因。
   - `ohDependencies.json` 可不存在或为空（`[]` / 空文件）；若不存在，为了后续改造可创建为空数组文件，但必须在输出中说明「原仓库缺省，本流程补齐空文件」。
3. **必须复用 `trade-duo-standard-same-npm-dependencies`**：第二步不得自行“手改版本”绕过该 skill。
4. **必须生成 commit**：改造完成后必须在目标仓库生成 1 个 commit（不 squash、不 amend）。
5. **commit message 必须包含明细**：除了固定标题，还必须写入改造结果摘要（详见 Step 2 的格式要求）。
6. **结果落盘**：Step 1 / Step 2 的全部约定输出必须写入 **`.temp/trade-duo-projects-standard/result/`**（见上文「结果输出目录」），不得仅口头输出而不写文件。

## 常见问题（排障摘要）

| 现象 | 处理 |
|------|------|
| `mep: command not found` | 安装 `@ee/mep-cli`（见上文），或确认 nvm/ PATH 包含全局 npm bin |
| `fetch is not defined`（执行 `mep code` 时） | 切换到 **Node.js 18+**（如 `nvm use 18`），勿使用 Node 16 |
| `citadel getMarkdown` 要求 MIS / SSO | 学城表未拉取时走 k-hub 降级，commit 中说明并请人工对照学城 |
| Step 2 无文件变更 | 不得空提交；报告「无需三端一致性改造」 |

