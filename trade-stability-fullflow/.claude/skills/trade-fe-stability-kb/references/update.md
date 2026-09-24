# 更新模式 —— 修改知识库（by PR）

## 触发与总原则

> ⛔ **强制前置（CRITICAL）**：进入本模式后，在执行任何文件写入或 git 操作之前，**必须先完整读取本文件**（以及知识库 `_kb-template.md` 模板依据）。禁止凭 SKILL.md 摘要或记忆直接动手；流程不明确时先向用户确认。

- 由 SKILL.md「意图识别」判定为更新意图后进入本模式
- 所有更新**必须**走 feature 分支 + PR，由人工合入；禁止直接提交 master，也禁止在流程之外直接修改本地知识库文件
- 变更内容以知识库 `_kb-template.md` 为**唯一模板依据**，不自行发明格式
- 更新只动目标条目块或目标文件，不波及无关内容；批量更新逐条列出清单
- **内容来源原则**：更新内容以用户输入为准——
  - 用户只给意图描述 → AI 按 `_kb-template.md` 模板生成；
  - 用户给原始素材（学城链接 / 代码片段 / 日志 / 截图说明等）→ AI 从素材中提取，**不补充素材中没有的信息**；
  - 用户已给出完整内容（含 frontmatter）→ 直接入库，不做二次改写

## 第 1 步：定位目标

- **资产**：用 Grep 精确匹配 `asset_id` / `bundle` / `project_id` / `keywords`，定位到条目：

```bash
grep -n "asset_id\|<关键词>" ~/.trade-fe-stability-knowledge/assets/<domain>-assets.md
```

- **指南 / SOP / 经验**：按标题 / 别名 / 信号类型定位文件与章节
- 命中 → 修改；未命中 → 走**新增**（选择对应模板，见「模板要点速查」）
- 定位不到且用户未给全信息 → 记录缺失，向用户确认，不猜测

## 第 2 步：生成变更内容

1. 对照 `_kb-template.md` 选择模板：`asset` / `guide` / `sop` / `pitfall` / `incident`
2. 校验 frontmatter 必填字段：`category` / `domain` / `constraint` / `owner` / `expires_at` / `tags` / `aliases`
3. 刷新时效字段：
   - `expires_at`：默认当前日期 +1 年（`YYYY-MM-DD`）；用户指定则从用户
   - `verified_at`：更新为当天
4. `asset_id` 命名：`<业务线>-<页面英文简称>`（如 `gc-group-order-submit`）
5. 内容规范自查：代码块标注语言、术语首现给出定义、叙述性文件 ≤500 行（assets 除外）、`{占位符}` 标注取值来源
6. `constraint: hard` 文件不允许「可跳过 / 视情况」等弱约束表述

> 修改既有条目时，保留原有字段与数据来源（`source`），只改目标字段；涉及参数变更必须同步更新 `source` 与 `verified_at`。

## 第 3 步：分支（先同步 master，再切新分支）

```bash
# 1. 回到权威分支并拉最新（公共前置已保证目录存在并 fetch）
cd ~/.trade-fe-stability-knowledge
git checkout master && git pull --ff-only origin master

# 2. 确认工作区干净（存在未提交改动则暂停并向用户确认）
git status --short

# 3. 新建 feature 分支
git checkout -b feature/kb-update-<简述>   # 如 feature/kb-update-gc-new-asset
```

## 第 4 步：落库

- **新增文件**：按模板写入 `assets/`、`guides/`、`playbooks/` 或 `pitfalls/incidents/`；文件不存在时先确认父目录存在，必要时 `mkdir -p`
- **修改条目**：仅替换目标条目 YAML block 或章节，不动其他内容
- 完成后 `git diff` 自查：变更范围符合预期、无无关改动

## 第 5 步：提交 PR

```bash
git add <变更文件>
git commit -m "kb: <变更类型> <简述>"        # 如 "kb: add gc-group-order-submit asset"
git push -u origin feature/kb-update-<简述>
```

推送成功后生成建 PR 链接（Code 平台，目标分支 master）：

```
https://git.sankuai.com/code/repo-detail/nibfe/trade-fe-stability-knowledge/pr/create?sourceBranch=feature/kb-update-<简述>&targetBranch=master
```

- 输出链接给用户（或由用户环境直接开 PR），PR 描述包含：变更文件 / 变更摘要 / 数据依据（来源链接或用户提供）/ 影响条目数
- 等待人工合入；**合入前不回写**任何内容；合入结果（merged/closed）需向用户反馈

## 过期刷新场景

用户提出「过期处理 / 保鲜 / 巡检」或定期维护时：

1. 扫描知识库全部文件 frontmatter，提取 `expires_at`：

```bash
# 扫描示例（assets/ 逐文件）
grep -n "expires_at\|^### \|^asset_id" ~/.trade-fe-stability-knowledge/assets/<domain>-assets.md
```

2. 分类：**已过期**（早于今天）/ **临期**（7 天内）
3. 输出清单（文件、条目、过期日期、owner），由用户逐条决定：刷新 / 删除 / 保留并标注
4. 按上述流程执行；删除条目需用户明确确认，PR 描述中说明删除原因

## 模板要点速查

| 模板 | 位置 | constraint | 说明 |
|---|---|---|---|
| asset | `assets/` | `reference` | 页面资产映射，参数来源；每条目一个 YAML block |
| guide | `guides/` | `hard` | 工具手册，命令必须可执行、参数标注来源 |
| sop | `playbooks/` | `hard` | 排查流程，每步给出输入与判定 |
| pitfall | `pitfalls/pitfalls.md` | `soft` | 踩坑记录，一句话标题 + 现象/根因/结论/日期 |
| incident | `pitfalls/incidents/<id>.md` | `soft` | 故障复盘，`<id>` = `YYYYMMDD-<业务线>-<简述>` |

## 安全边界

1. 只操作白名单目录：`AGENTS.md` / `_kb-template.md` / `assets/` / `guides/` / `playbooks/` / `pitfalls/`
2. 业务线资产只改对应文件，禁止跨线猜测归属
3. 参数（`projectId` / `AppKey` / Topic / 仓库 SSH）必须有来源；来源缺失时 PR 标注「待核实」
4. 更新须在知识库仓库新建分支（基于 `master`），禁止直接推 master；PR 由人工合入
5. 修改后如引用该条目的其他文件存在（如 SOP 引用 guide），检查链接是否仍有效
