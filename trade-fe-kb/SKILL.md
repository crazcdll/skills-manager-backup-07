---
name: trade-fe-kb
description: 交易前端知识库（trade-fe-rule）查询与更新工具。查询时遵循 AGENTS.md 路由规则从 KB 仓库读取内容进行 AI 问答；更新时辅助生成规范文档、创建分支并提交 GitLab MR。当用户提到「查知识库」「KB里有没有」「更新知识库」「往KB加一条规则」「录入踩坑」「查团队规范」「GC/food/hotel/ticket/platform 业务相关规范」时激活。

metadata:
  skillhub.creator: "changsusheng"
  skillhub.updater: "changsusheng"
  skillhub.version: "V16"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "91576"
  skillhub.high_sensitive: "false"
---

# trade-kb — 交易前端知识库查询与更新

## 激活条件

当用户出现以下任一情形时激活本 Skill：

- 显式调用：`/trade-kb`、`/trade-kb query <问题>`、`/trade-kb update`
- 自然语言触发：
  - **查询类**：「查一下知识库」「KB 里有没有关于 XXX 的内容」「GC 业务里 XXX 是什么」「food 的踩坑有哪些」「帮我查团队规范」「XXX 怎么写」「XXX 是啥」
  - **更新类**：「往知识库里加一条」「更新知识库」「把这条踩坑录入 KB」「修改 KB 里的 XXX」「知识库里新增一个规则」

激活后，**立即进入本 Skill 定义的流程，不使用训练知识直接回答**。

---

## 固定配置

| 项 | 值 |
|---|---|
| 本地 KB 目录 | `~/.trade-fe-kb` |
| 远程仓库 | `ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git` |
| 主分支 | `release/main` |
| Code 平台 API | `http://git.sankuai.com/rest/api/2.0/` |
| 项目 / 仓库 | `project=nibfe`，`repo=trade-fe-rule` |
| 固定 Reviewer | `changsusheng`、`hfe_stash`、`it_catpaw` |

---

## 第一步：公共前置 — 本地 KB 同步（每次必执行）

```bash
KB_DIR=~/.trade-fe-kb
if [ ! -d "$KB_DIR/.git" ]; then
  git clone ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git "$KB_DIR"
fi
cd "$KB_DIR" && git fetch origin && git checkout release/main && git pull origin release/main
```

若命令失败，输出以下诊断提示后停止：

```
❌ 知识库同步失败，请检查：
1. SSH Key 是否已配置：ssh -T git@git.sankuai.com
2. 是否处于美团内网环境
3. 手动验证：git clone ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git ~/.trade-fe-kb
```

---

## 第二步：意图识别

**优先级规则（自上而下，命中即停）：**

| 优先级 | 判断条件 | 操作 |
|--------|---------|------|
| P1 | `/trade-kb query` 或 `/trade-kb update` 显式指定 | → 按指定执行，不再判断 |
| P2 | **同时**包含查询信号词和写入信号词，**或**含双义词（见下方说明） | → **必须追问**：「你是要查询 XXX 的内容，还是要更新这部分文档？」 |
| P3 | 仅含写入信号词（加、新增、录入、补充、追加、写入、记录），**且不含双义词** | → **更新（update）** |
| P4 | 仅含查询信号词（什么、怎么、为什么、有没有、如何、是啥、哪些、查一下），**且不含双义词** | → **查询（query）** |
| P5 | 均未命中 | → 追问：「请问是要**查询**知识库内容，还是**更新**知识库文档？」 |

> **双义词（单独出现时必须触发 P2 追问，不得直接路由）**：
> - **「更新」**：可以是"把这条更新进去"（写入）也可以是"这个规则是怎么更新的"（查询）
> - **「修改」**：可以是"帮我修改这条规则"（写入）也可以是"这个字段怎么修改"（查询）
> - **「改」**：同上
>
> **P2 歧义示例**（必须追问，不得猜测）：
> - "帮我更新知识库里 XXX 是什么的说明" —— "更新"（双义）+ "是什么"（查询词）
> - "查一下 XXX 有没有，如果没有帮我加一条" —— 查询+更新复合意图
> - "知识库里 XXX 目前是怎么定义的，我想补充一下" —— "怎么"（查询词）+ "补充"（写入词）
> - "XXX 规则需要修改一下" —— "修改"单独出现，无法判断是要查现状还是要写入变更

---

## 查询流程

**详细步骤见** `<SKILL_DIR>/references/query-workflow.md`（`SKILL_DIR` 来自 `Base directory for this skill:` 注入值）

核心约束（**不可省略任何一条**）：

1. 必须先 `Read ~/.trade-fe-kb/AGENTS.md` — 路由唯一依据，不可跳过
2. 按 AGENTS.md 中意图识别规则确定业务组和加载层级
3. Read 对应业务组 `_index.md`，跟随 `related:` 字段递归加载（最多 2 层）
4. 遵守四条硬约束：禁止枚举 biz、禁止跨组、跟随 related、禁用训练知识
5. 答案必须引用具体文件路径 + 行号，不能凭空断言

---

## 更新流程

> ⛔ **强制前置：在执行任何操作前，必须先完整读取流程文档。**
> 禁止在读完文档前进行任何文件写入、git 操作或脚本调用。

**Step 1（必须，在公共前置 cd 之前执行）**：

从上下文中找到 harness 注入的这一行，取其值作为 `SKILL_DIR`：
```
Base directory for this skill: /actual/absolute/path/to/trade-fe-kb
```

然后用该绝对路径读取流程文档：
```
Read {SKILL_DIR}/references/update-workflow.md
```

> ⚠️ **必须在 `cd ~/.trade-fe-kb`（公共前置）之前完成这一步**。
> 公共前置执行后 CWD 变为 `~/.trade-fe-kb`，届时任何相对路径都会在 KB 目录下解析，找不到 skill 文件。
> `SKILL_DIR` 是 harness 注入的绝对路径，与 CWD 无关，任何时候都可以用。

**Step 2**：执行公共前置（KB 同步），然后检查工作区状态：
```bash
cd ~/.trade-fe-kb && git status --short && git rev-parse --abbrev-ref HEAD
```
- 若已在非 `release/main` 分支或有未提交改动 → **暂停**，询问用户：
  「检测到已有进行中的改动，请确认：① 继续当前分支走规范流程，② 放弃当前改动重新开始？」
- 工作区干净且在 `release/main` → 按 `update-workflow.md` 步骤继续

---

## 重要原则

- 禁止跳过「公共前置」直接读本地旧文件
- 查询的意图识别规则**以 `AGENTS.md` 为准**，本文件不重复定义
- 更新的文档模板**以 `_governance/` 目录为准**，本 Skill 不内嵌模板内容
- PR 认证由 `scripts/_code_.sh` 中的 hfe_stash 服务账号负责，无需用户提供 Token
