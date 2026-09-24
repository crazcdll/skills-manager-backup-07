---
name: trade-fe-stability-kb
version: "1.4.0"
author: "交易前端稳定性小组"
triggers:
  - "知识库"
  - "资产查询"
  - "查页面参数"
  - "查询参数"
  - "怎么查"
  - "排查流程"
  - "排查SOP"
  - "踩坑经验"
  - "稳定性知识"
  - "更新知识库"
  - "新增资产"
  - "补全知识库"
  - "修正知识库"
  - "过期处理"
  - "录入"
description: 交易前端稳定性知识库（trade-fe-stability-knowledge）的查询与更新执行器。查询模式：按 AGENTS.md 路由精确加载资产映射/工具手册/排查SOP/经验沉淀并返回带溯源的答案；更新模式：按 _kb-template.md 模板修改知识库文件并通过 PR 合入（by PR，人工合入）。

metadata:
  skillhub.creator: "duyifan10"
  skillhub.updater: "duyifan10"
  skillhub.version: "V3"
  skillhub.source: "ssh://git@git.sankuai.com/nibfe/trade-ai-skills.git"
  skillhub.skill_id: "132756"
---

# trade-fe-stability-kb —— 稳定性知识库查询与更新执行器

## 定位

本 skill 是交易前端稳定性知识库的**唯一读写入口**。消费链路：

```
人提问 → 调 skill → skill 操作知识库文件（AGENTS.md 路由 → 目标文件）→ 返回给人
```

- 知识库定位：交易前端稳定性知识的管理中心（资产映射 / 工具手册 / 排查 SOP / 经验沉淀）
- 纯 AI 间接消费：人不直接编辑，更新亦通过本 skill 完成
- 本 skill 只做两件事：**查询** 与 **更新（by PR）**；不编排排查流程、不查线上数据
- 查询参数（projectId / AppKey / Bundle 等）由用户或其他 skill 提供，本 skill 不自建查数命令

## 环境

| 项 | 约定 |
|---|---|
| 知识库仓库 | 固定目录 `~/.trade-fe-stability-knowledge`（远程 `ssh://git@git.sankuai.com/nibfe/trade-fe-stability-knowledge.git`） |
| 权威分支 | `master` |
| 路由依据 | 知识库 `AGENTS.md`（唯一路由入口，禁止枚举目录） |
| 模板规范 | 知识库 `_kb-template.md`（frontmatter + 五类模板，更新流程唯一依据） |

## 公共前置：知识库同步（每次必执行）

```bash
# 1. 固定目录，不存在则自动 clone，存在则拉取最新
KB_DIR="$HOME/.trade-fe-stability-knowledge"
KB_REMOTE="ssh://git@git.sankuai.com/nibfe/trade-fe-stability-knowledge.git"

if [ ! -d "$KB_DIR/.git" ]; then
  git clone "$KB_REMOTE" "$KB_DIR"          # 首次使用自动拉取
else
  git -C "$KB_DIR" fetch origin --quiet
fi

# 2. 检查工作区状态（更新模式硬性要求干净；查询模式仅提示）
git -C "$KB_DIR" status --short
```

- **clone/fetch 失败**（SSH Key 未配置 / 不在内网 / 网络异常）→ 输出诊断提示后停止，不得继续：

```
❌ 知识库同步失败，请检查：
1. SSH Key 是否已配置：ssh -T git@git.sankuai.com
2. 是否处于美团内网环境
3. 手动验证：git clone ssh://git@git.sankuai.com/nibfe/trade-fe-stability-knowledge.git ~/.trade-fe-stability-knowledge
```

- 更新模式：本地存在未提交改动或当前不在 `master` → **暂停**，向用户确认「继续当前分支走规范流程 / 放弃改动重新开始」
- 查询模式：检出本地落后 `master` 时提示「本地知识库可能不是最新，如需最新内容请在 knowledge 仓库 `git checkout master && git pull`」

## 意图识别：查询 or 更新（P1–P5，自上而下命中即停）

| 优先级 | 判断条件 | 操作 |
|---|---|---|
| P1 | 用户显式指定（如「查询」「更新」或命令式） | 按指定执行，不再判断 |
| P2 | 同时含查询信号词与写入信号词，**或**含双义词 | **必须追问**：「你是要查询 XXX，还是要更新这段内容？」 |
| P3 | 仅含写入信号词，且不含双义词 | **更新模式** |
| P4 | 仅含查询信号词，且不含双义词 | **查询模式** |
| P5 | 均未命中 | 追问：「请问是**查询**知识库内容，还是**更新**知识库文档？」 |

**信号词**：

- 查询词：什么、怎么、为什么、有没有、如何、是啥、哪些、查一下、查、找
- 写入词：加、新增、录入、补充、追加、写入、记录、补全、修正

> **双义词（单独出现时必须触发 P2 追问，不得直接路由）**：
> - 「更新」：写入变更 or 查询现状
> - 「修改」：帮我改这条 or 这个字段怎么改
> - 「改」：同上
>
> 示例："帮我更新知识库里 XXX 的说明" → 追问是查询现状还是写入变更；"查一下 XXX 有没有，没有就加一条" → 查询+更新复合意图，追问确认。

## 查询模式（摘要）

详见 `references/query.md`，要点：

1. 公共前置就绪检查
2. 读 `~/.trade-fe-stability-knowledge/AGENTS.md` 确定路由
3. 按意图匹配加载场景包（资产 1 文件 / 排查 2 文件 / 工具 1 文件 / 经验 1 文件）
4. 精确读取：assets 用 Grep 精确匹配 `asset_id`/`bundle`/`project_id`/`keywords`，**禁止整读**；guides/playbooks/pitfalls 直接 Read
5. 输出答案：**结论先行**、引用带 `文件:行号`；过期条目标注并带 `owner`；未命中走未命中模板，禁止编造

## 更新模式（摘要，by PR）

详见 `references/update.md`，要点：

1. 定位目标文件与条目（按 `asset_id`/`bundle`/标题精确匹配；无则走新增）
2. 按 `_kb-template.md` 生成变更内容（内容以用户输入为准：素材不补充、完整内容直接入库），同步刷新 `expires_at`/`verified_at`
3. 公共前置：`checkout master` + `pull`，新建 `feature/kb-update-<简述>` 分支
4. 修改文件：新增用模板；修改仅动目标条目块
5. `git commit` + `git push` + 开 PR → 输出 PR 链接，**人工合入**后通知用户

## 硬约束（⚠️ CRITICAL）

1. **白名单目录**：只操作知识库仓库的 `AGENTS.md`、`_kb-template.md`、`assets/`、`guides/`、`playbooks/`、`pitfalls/`；不碰其他任何文件
2. **更新走 PR**：更新必须走 feature 分支 + PR，禁止直接推 master；**禁止在更新模式流程之外直接修改本地知识库文件**；PR 由人工合入，合入前不回写
3. **禁止跨线**：业务线资产（food/gc/hotel/travel）只查/只改对应文件；未命中时不得跨文件猜测资产归属
4. **禁止编造参数**：`projectId`、仓库 SSH、`AppKey`、Topic 必须来自资产文件、堆栈、PR 或用户输入；未命中时记录缺失信息
5. **命令从 guides 读取**：任何平台查询命令先精确读取对应 `guides/<tool>.md`，按其命令与参数执行
6. **引用带行号**：引用资产、指南、SOP 内容时标注 `文件:行号`
7. **过期标注**：`expires_at` 早于当前日期的条目，输出时标注「可能已过期，请人工核实」，并带 `owner`
8. **兜底红线**：检测到更新意图但流程不明确时，先向用户确认，不得自行决定修改方式；绝不在未读 `references/update.md` 的情况下执行任何文件写入或 git 操作

## Reference 文件

| 文件 | 用途 |
|---|---|
| `references/query.md` | 查询模式：路由规则、加载场景包、精确读取规则、输出格式、未命中处理 |
| `references/update.md` | 更新模式：内容来源原则、定位→生成→分支→落库→PR 流程、过期刷新、模板要点速查 |
