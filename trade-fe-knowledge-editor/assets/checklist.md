# Pre-Delivery Checklist（交付前自检）

> 交付给用户前，逐项在脑中（或以文本形式）打勾。任一项未完成即**不得声明"已完成"**。

## 基础

- [ ] 识别的 `<group>` 是合法值（`food/gc/ticket/hotel/platform`）
- [ ] **模式**（mode）已明文标注（`local` / `auto`），与用户 prompt 关键词一致；`auto` 模式已对用户正确提示（会自动拉 master / 切分支 / 提 PR）
- [ ] **工作区校验已通过**：git remote origin 命中 `nibfe/trade-fe-rule` **且** 向上查找存在 `AGENTS.md + context-docs/ + spec/`
  - local 模式：不合法即硬失败；**未**做任何兜底
  - auto 模式：不合法 → 已执行 `git clone … <clone_root>/trade-fe-rule-{ts}` 并 cd 进入（`<clone_root>` 由 `_resolve_clone_root` 动态决定：`$TRADE_FE_CLONE_ROOT` / `$CATPAW_WORKSPACE_ROOT` / `$WORKSPACE_FOLDER` / `$PWD` 继承 / `$HOME/projects` / `mktemp -d`）
- [ ] 意图范围（scope）已明文标注，与用户语义严格一致（单 kind / 多 kind / all）
- [ ] 所有被修改文件都在 `<group>` 作用域内（未触及其他组 / meta / 根 AGENTS.md；`page-assets/<group>/` 仅允许动 `page-index.md`）

## Confirmation Gate

- [ ] 已向用户展示变更计划表（每个文件一行：现状、建议动作、风险）
- [ ] **范围锁定模式**下，变更计划表表头已标注 `范围: <kind list>`，且表中不包含范围外文件
- [ ] 已收到用户明确确认（"确认/同意/go/执行"之一），或用户对每个文件逐项给出了 ✓/✗/✎ 决议
- [ ] **未经确认的写入 = 0 次**

## 内容质量

- [ ] 每个被创建/修改的文件 frontmatter 至少包含 `category` / `description` / `domain`
- [ ] `tags` 字段 ≥ 5 个且与业务/技术相关
- [ ] `last_updated` 刷新为今天（YYYY-MM-DD）
- [ ] 新增章节均留有 `<!-- TODO: ... -->` 占位或由用户提供实内容，**未编造业务术语/状态码/阈值**
- [ ] 相对路径链接（related / [x](./y.md)）指向的文件实际存在
- [ ] 未修改用户已有段落内容（除非用户明确要求改写）

## 校验

- [ ] 当前工作目录在 `trade-fe-rule` 仓库内（local 即用户仓库；auto 即 `workspace_dir`，允许为 `<clone_root>/trade-fe-rule-{ts}`，`<clone_root>` 由 `_resolve_clone_root` 动态决定），且已执行校验脚本：
  - 全量模式：`node <path-to-skill>/scripts/validate.js <group>`
  - 范围锁定模式：`node <path-to-skill>/scripts/validate.js <group> --scope <kind list>`（--scope 值严格 = 阶段 1 识别结果）
  - **auto 模式强制带 --scope**（无论 scope=all 还是具体 kinds），以便日志留痕；拼 PR description 时额外运行 `--pr-summary` 采集 Markdown 摘要
- [ ] 输出中 `errors=0`（**auto 模式下 errors>0 必须中止所有后续 git 写操作**）
- [ ] 所有 `warnings` 要么已修复，要么在交付摘要中明确列出留待用户决策；**范围锁定模式**下仅针对范围内文件的 warnings 处理

## [auto-only] 自动模式 git / PR 闭环

> 仅当 mode=auto 时核此章节；local 模式跳过。

- [ ] 已执行 `git fetch origin && git checkout master && git pull --ff-only`，master 为最新
- [ ] MIS 已按优先级解析（环境变量 → git config user.email → user.name → 宿主）；获取不到时分支名退化为无 mis 段，不阻断流程
- [ ] 分支名合规：`chore/update-knowledge-{mis?}-{yyyyMMddHHmmss}`；若同名冲突已自动追加 `-r2`/`-r3` … 后缀
- [ ] 切分支前 **已检测**当前 working tree 干净；脘则提示用户 `git stash` / 手动处理，**未**硬走
- [ ] `git add` **仅 scope 内文件**（严禁 `git add .` / 全量 add）
- [ ] 单个 commit，title 严格合模板：`chore(knowledge): 更新 <group> <kinds> [<mis?@yyyyMMdd>]`；body 包含 scope / 变更文件清单 / validate 汇总 / user prompt
- [ ] `git push origin HEAD` 已成功；失败时已输出恢复指引，未自动回滚
- [ ] PR 已通过 `auto-pr.sh pr_create_wrapper` 创建，PR URL 已给用户；若 API 失败已打印 fallback 手动提 PR URL（`…/pr/create?sourceBranch=…&targetBranch=master`）
- [ ] PR title 与 commit title 一致；PR description 严格四段式（变更范围 / 变更文件 / validate 校验结果 / 原始用户需求），user prompt 原封不动引用
- [ ] reviewers 留空，由仓库默认 reviewer 规则兜底，**未**自动 @ 任何人

## 反模式自查

- [ ] 未引入 wiki 提到但仓库未采纳的目录（如 `agents/global/`）
- [ ] 未自创 `category` / `domain` 新值（只用 `meta/doc-template.md` 已登记的）
- [ ] 未一次性修改超过一个 `<group>`
- [ ] 只动了 `context-docs/page-assets/<group>/page-index.md`，**未触碰**该目录下其他文件（`*-order-submit-modules.md` / `*-order-detail-modules.md` / 特殊页面 `*.md`）
- [ ] **范围锁定模式铁令自查**（scoped 模式必查）：
  - 未读范围外文件，未以"交叉参考"为由扩展读取
  - 未写范围外文件（即使发现其格式瑕疵也不动）
  - 确认清单 / 变更计划表 / Handoff Summary 中未出现范围外文件名和建议
  - 需要提示用户可扩展时，只在摘要末尾用**一行**："如需扩展范围，请回复'扩展到 <kind>'"，不泄露具体文件问题
- [ ] **[auto-only] 三关铁律自查**（auto 模式必查，IRON LAW 8）：
  - ① workspace 校验通过才进入主流程
  - ② Confirmation Gate 通过才写盘 / commit / push
  - ③ `validate.js --scope` errors=0 才 push / pr_create；**任一关未过→未继续 git 写操作**
- [ ] **[auto-only] git 行为自查**：
  - 未 `git add .` （仅 add scope 内文件）
  - 未在非 master 的分支上切新分支（阶段 0 已强制回 master）
  - 未在 PR description 中加入 user prompt 以外的 AI 自造话术
  - 未自动 merge / approve / decline PR（只负责 create，merge 等交付给用户/reviewer）

## 交付格式

- [ ] Handoff Summary 列出：
  - **模式标识**：开头一行 `模式: local / auto ｜ 组: <group> ｜ 范围: <scope>(锁定标记)`
  - **范围锁定模式**：开头第一行 `范围: <kind list>（严格锁定）`，摘要仅提范围内文件
  - 修改的文件清单（N 个）
  - 每个文件本次改动章节
  - 待用户补充的 TODO 占位数量
  - 校验结果 errors / warnings 数
  - **[auto-only] 额外字段**：`branch_name` / `commit_hash` / `PR URL` ；若 push/PR 失败→明标”❌ 待人工接管“ + 恢复指令

---

> ⛔ **任一 ❌ → 不得交付**。若因用户信息不足无法补齐，请回到阶段 1 追问。
