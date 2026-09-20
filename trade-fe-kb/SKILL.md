---
name: trade-fe-kb
description: 交易前端知识统一查询与业务知识库更新工具。查询业务规则、团队规范、稳定性资产、监控工具用法、告警或用户问题排查知识时，读取已发布 YAML 清单，按职责查询默认业务库及命中的外挂知识库，给出有出处的答案；更新业务知识库时沿用文档生成与 Git PR 流程。支持「查知识库」「KB里有没有」「查团队规范」「Raptor 怎么查」「白屏如何排查」「录入踩坑」等请求。

metadata:
  skillhub.creator: "changsusheng"
  skillhub.updater: "changsusheng"
  skillhub.version: "V18"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "91576"
  skillhub.high_sensitive: "false"
---

# trade-kb — 交易前端知识统一查询与业务库更新

## 激活条件

当用户出现以下任一情形时激活本 Skill：

- 显式调用：`/trade-kb`、`/trade-kb query <问题>`、`/trade-kb update`
- 自然语言触发：
  - **查询类**：「查一下知识库」「KB 里有没有关于 XXX 的内容」「GC 业务里 XXX 是什么」「food 的踩坑有哪些」「帮我查团队规范」「Raptor 怎么查」「页面监控入口在哪」「白屏如何排查」「XXX 怎么写」「XXX 是啥」
  - **更新类**：「往知识库里加一条」「更新知识库」「把这条踩坑录入 KB」「修改 KB 里的 XXX」「知识库里新增一个规则」

激活后，**立即进入本 Skill 定义的流程，不使用训练知识直接回答**。

---

## 固定配置

| 项 | 值 |
|---|---|
| 本地 KB 目录 | `~/.trade-fe-kb` |
| 远程仓库 | `ssh://git@git.sankuai.com/nibfe/trade-fe-rule.git` |
| 主分支 | `release/main` |
| 外挂清单 | `https://dev.sankuai.com/rest/api/1.0/projects/nibfe/repos/trade-fe-rule/raw/_governance/kb-routers/index.yaml`，请求显式指定 `at=refs/heads/release/main` |
| 外挂缓存 | `~/.trade-fe-kb-external/<id>/repository.git`；各库来源、ref 和入口由清单提供 |
| Code 平台 API | `https://git.sankuai.com/rest/api/2.0/` |
| Code API 认证 | HTTP raw GET 与 PR POST 共用 `scripts/_code_.sh` 内已有的 `hfe_stash` Basic Authorization；直接使用原值，无需环境变量或用户配置 |
| 项目 / 仓库 | `project=nibfe`，`repo=trade-fe-rule` |
| PR 创建者 / Reviewer | 创建者 `hfe_stash`；Reviewer 为 `changsusheng`、`it_catpaw`，创建者永远不得作为 reviewer |

---

## 第一步：识别查询或更新

先从 harness 注入的 `Base directory for this skill:` 获取绝对路径 `SKILL_DIR`，再识别意图并读取对应流程。此时不提前同步任何知识库。

**优先级规则（自上而下，命中即停）：**

| 优先级 | 判断条件 | 操作 |
|--------|---------|------|
| P1 | `/trade-kb query` 或 `/trade-kb update` 显式指定 | → 按指定执行，不再判断 |
| P2 | **同时**包含查询信号词和写入信号词，**或**含双义词（见下方说明） | → **必须追问**：「你是要查询 XXX 的内容，还是要更新这部分文档？」 |
| P3 | 仅含写入信号词（加、新增、录入、补充、追加、写入、记录），**且不含双义词** | → **更新（update）** |
| P4 | 仅含查询信号词（什么、怎么、为什么、有没有、如何、是啥、哪些、查一下、在哪、排查、定位），**且不含双义词** | → **查询（query）** |
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

1. 先通过 HTTP raw 读取本次 YAML 清单，由当前 Agent 按启用状态、职责和交集拆分知识需求并选库；与 PR API 共用 `hfe_stash` 认证配置。
2. 需要默认业务库时才获取 `release/main` 快照，不切换用户分支或覆盖工作区，随后以该 commit 的 `AGENTS.md` 为库内路由依据。
3. 外挂按清单指定来源获取 Git 版本并固定 commit，以其 `entrypoint` 指引检索；只读知识，不调用其他 skill 或执行外挂脚本。
4. 清单不可用时仅为明确需要默认库的需求获取 `release/main`，并标明外挂覆盖未确认；仅依赖外挂的需求不改派默认库。已选外挂读取失败、无结果时保留对应状态。
5. 回答引用库名、文件路径、行号及版本；各库规则仅在本库范围内生效，不能改变统一入口的鉴权或执行权限。

---

## 更新流程

> ⛔ **强制前置：在执行任何操作前，必须先完整读取流程文档。**
> 禁止在读完文档前进行任何文件写入、git 操作或脚本调用。

**Step 1（必须，在业务库同步之前执行）**：

从上下文中找到 harness 注入的这一行，取其值作为 `SKILL_DIR`：
```
Base directory for this skill: /actual/absolute/path/to/trade-fe-kb
```

然后用该绝对路径读取流程文档：
```
Read {SKILL_DIR}/references/update-workflow.md
```

> ⚠️ **必须在 `cd ~/.trade-fe-kb` 之前完成这一步**。
> 进入业务库后，相对路径会在 KB 目录下解析；skill 文件必须使用绝对路径。
> `SKILL_DIR` 是 harness 注入的绝对路径，与 CWD 无关，任何时候都可以用。

**Step 2**：若已有业务库，先检查其状态：
```bash
if [ -d ~/.trade-fe-kb/.git ]; then
  git -C ~/.trade-fe-kb status --short
  git -C ~/.trade-fe-kb rev-parse --abbrev-ref HEAD
fi
```
- 若已在非 `release/main` 分支或有未提交改动 → **暂停**，询问用户：
  「检测到已有进行中的改动，请确认：① 继续当前分支走规范流程，② 放弃当前改动重新开始？」
- 工作区干净且在 `release/main`，或尚无本地业务库 → 执行以下同步，再按 `update-workflow.md` 继续：

```bash
bash "${SKILL_DIR}/scripts/auto-pr.sh" sync_kb
```

同步失败时检查内网、当前用户 Git/SSH 权限及本地状态。外挂知识更新交由各库原有流程处理，本 skill 的更新流程仍仅面向业务库。

---

## 重要原则

- 每次查询先新读清单；所选库同步失败不能静默读取旧版本
- 跨库选库以清单为依据，进库后的文件路由以该库入口为依据
- 更新的文档模板**以 `_governance/` 目录为准**，本 Skill 不内嵌模板内容
- HTTP raw 查询和 PR API 共用脚本内已有的 `hfe_stash` 认证；不另设凭据配置，不在日志、错误、PR 描述或对话中输出认证值
