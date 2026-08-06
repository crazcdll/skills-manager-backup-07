# 更新流程详细指引

> 本文件由 SKILL.md 在公共前置（`cd ~/.trade-fe-kb`）**之前**读取，CWD 此时尚未改变。
> - KB 根目录：`~/.trade-fe-kb/`（公共前置后的 CWD）
> - **`SKILL_DIR`**：harness 注入的 `Base directory for this skill:` 绝对路径，**与 CWD 无关**，脚本路径均用此变量拼接，禁止猜测。
> - 更新流程无需用户中途确认，MR 评审即为合规审核入口。

---

## Step 1：识别输入类型

| 用户输入形态 | 模式 |
|------------|------|
| **一句话 / 意图描述**（如"在 food 踩坑里加一条关于 XXX 的记录"） | **意图模式**：AI 读模板后辅助生成完整文档内容 |
| **原始素材**（学城文档、代码片段、日志、截图说明、设计稿描述等，无固定结构） | **提炼模式**：AI 从素材中提取关键信息，按模板整理成 KB 文档 |
| **完整 Markdown 文档**（含 `---` frontmatter 开头和正文） | **直接模式**：用户已写好，直接进入 Step 3 |

> **意图模式**和**提炼模式**的后续步骤相同（均走 Step 2），区别仅在于内容来源：前者由 AI 根据意图自行生成，后者以用户提供的素材为准，AI 不补充素材中没有的信息。

---

## Step 2（意图模式）：读模板 → AI 生成内容

### 2.1 判断文档类型

| 用户意图描述 | 文档类型 | 模板文件 |
|------------|---------|--------|
| 新增/解释业务术语、状态码、缩写 | glossary | `~/.trade-fe-kb/_governance/templates/glossary.tpl.md` |
| 新增业务规则、计算公式、展示逻辑 | business-rules | `~/.trade-fe-kb/_governance/templates/business-rules.tpl.md` |
| 记录踩坑、Bug 复盘、异常处理经验 | pitfall | `~/.trade-fe-kb/_governance/templates/pitfall.tpl.md` |
| 新增实体/接口类型定义、枚举定义 | domain-model | `~/.trade-fe-kb/_governance/templates/entity.tpl.md` |
| 技术选型决策、架构决策记录 | adr | `~/.trade-fe-kb/_governance/templates/adr.tpl.md` |

若无法判断，询问用户：「这条内容属于哪种类型？①业务术语 ②业务规则 ③踩坑记录 ④实体定义 ⑤架构决策」

### 2.2 读取模板并生成内容

```
Read ~/.trade-fe-kb/_governance/doc-template.md          ← frontmatter 字段规范（唯一权威来源）
Read ~/.trade-fe-kb/_governance/templates/<type>.tpl.md  ← 对应类型模板
```

若目标文件已存在，先 Read 以参考现有内容风格和已有条目格式。

**frontmatter 必填字段以 `doc-template.md` 中的定义为准**，不在本文件重复定义。生成内容时严格对照该文件中的字段列表、枚举值和格式要求填写。

---

## Step 3：确定目标文件路径

| 内容类型 | 业务组专属路径（相对 KB 根） | 跨业务通用路径 |
|---------|------------------------|-------------|
| 术语/状态码 | `biz/<group>/L1-domain/glossary.md` | `biz/general/L1-domain/glossary.md` |
| 业务规则 | `biz/<group>/L2-spec/business-rules.md` | — |
| 踩坑记录 | `biz/<group>/L2-spec/pitfalls.md` | `L0-rules/pitfalls.md` |
| 实体/类型定义 | `biz/<group>/L2-spec/domain-models/entities.md` | — |
| 枚举定义 | `biz/<group>/L2-spec/domain-models/enums.md` | — |
| 架构决策（ADR） | `biz/<group>/L2-spec/adr.md` | `L0-rules/tech-stack.md` |
| 平台技术规范 | — | `L2-tech/<platform>.md`（如 mrn.md） |

写文件时使用绝对路径：`~/.trade-fe-kb/<相对路径>`。

- 文件**不存在**：创建新文件（含完整 frontmatter + 正文）；**必须先确认父目录存在**，否则 Write 工具会失败：
  ```bash
  mkdir -p ~/.trade-fe-kb/<父目录路径>
  # 例：mkdir -p ~/.trade-fe-kb/biz/food/L2-spec/domain-models
  ```
- 文件**已存在**：在末尾追加新内容，保留原有 frontmatter（无需 mkdir）

---

## Step 4：创建分支

> `safe_checkout_new` 内部会校验当前分支必须是 `release/main`；SKILL.md 公共前置（`git checkout release/main && git pull`）已保证这一前提。若脚本报错"当前分支非 release/main"，说明公共前置未成功执行，应重新执行 SKILL.md 第一步。

```bash
# SKILL_DIR = harness 注入的 "Base directory for this skill:" 绝对路径
# 已在 SKILL.md 读取本文件前确认，此处直接使用
# 示例：SKILL_DIR=/Users/xxx/Mine/CatPaw-Works/.catpaw/skills/skills-market/trade-fe-kb
SCRIPTS="${SKILL_DIR}/scripts"
MIS=$(bash "${SCRIPTS}/auto-pr.sh" resolve_mis)
BRANCH=$(bash "${SCRIPTS}/auto-pr.sh" compute_branch "${MIS}" "<kebab-topic>")
bash "${SCRIPTS}/auto-pr.sh" safe_checkout_new "${BRANCH}"
```

> 分支格式：`feat/kb-<topic>-<5位随机串>`，唯一性由随机串保证，总长 ≤ 30 字符。

`<kebab-topic>`：内容简短概括，kebab-case 英文，**不超过 15 字符**。
示例：`food-refund`、`gc-coupon`、`mrn-scroll`

---

## Step 5：写文件 + commit + push

> ⚠️ **git push 的 remote 提示 URL 必须忽略**：push 完成后 remote 服务器会在 stderr 输出一条"建 PR"的跳转链接，该链接的 `targetBranch` 是仓库默认 HEAD（`master`），**不是我们的目标分支 `release/main`**。请只使用 Step 6 中脚本生成的 PR URL，忽略 remote hint。

Write 工具写入文件后（绝对路径），执行 commit 和 push：

```bash
# SCRIPTS 同 Step 4，来自 "Base directory for this skill:" 注入值
# <相对路径> 是相对于 KB 根目录（~/.trade-fe-kb/）的路径，脚本内部已 cd 到 KB 根
bash "${SKILL_DIR}/scripts/auto-pr.sh" commit_push \
  "docs: <一句话变更说明>" \
  <相对路径>
```

Commit message 规范：前缀固定 `docs:`，简述"加了什么"。
示例：`docs: gc 踩坑记录 - 次卡核销重复提交问题`

---

## Step 6：创建 PR

Reviewer 由脚本自动指定（`changsusheng`、`hfe_stash`、`it_catpaw`）：

```bash
# SCRIPTS 同 Step 4，来自 "Base directory for this skill:" 注入值
SCRIPTS="${SKILL_DIR}/scripts"

# DESC 必须是纯文字一句话，禁止包含 URL、Markdown 符号、路径斜杠、换行
# 格式：<业务组> <文件名（不含路径）> <做了什么>
DESC="<group> <文件名> <变更内容一句话>"

PR_URL=$(bash "${SCRIPTS}/auto-pr.sh" pr_create_wrapper \
  "${BRANCH}" \
  "docs: <变更摘要>" \
  "${DESC}")
echo "${PR_URL}"
```

DESC 示例：
```
gc page-index.md 删除页面索引顶部的数据来源信息
food business-rules.md 新增次卡核销幂等校验规则说明
```

脚本始终 exit 0（commit/push 已成功），通过 URL 格式区分两种结果：

| PR_URL 包含 | 含义 | 操作 |
|------------|------|------|
| `/pr/detail/<id>` | ✅ PR 自动创建成功 | 直接输出链接给用户 |
| `/pr/create?` | ⚠️ API 失败，已降级 | 提示用户在浏览器打开链接手动创建 PR |

```bash
if [[ "${PR_URL}" == *"/pr/create?"* ]]; then
  echo "⚠️ PR 自动创建失败，请在浏览器手动创建："
else
  echo "✅ PR 已创建："
fi
echo "${PR_URL}"
```

commit 和 push 均已完成，fallback 时代码不会丢失，仅需手动提 PR。