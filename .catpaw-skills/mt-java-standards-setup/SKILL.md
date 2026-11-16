---
name: mt-java-standards-setup
description: "业研 Java 编码规范接入工具 Skill。用于把业研 L1 编码规范接入到具体业务仓库：把精简版规则拉取到业务仓库 .mdp/rules/company/java/，并把规范索引条目合并进 .mdp/rules/AGENTS.md（不是覆盖，是合并），同时在根目录 AGENTS.md / CLAUDE.md 中融合一段规范遵循指引。当仓库负责人希望让本仓库支持 Claude Code / Codex / Cursor 等非 CatPaw 工具的规范遵循，或希望关掉 CatPaw 云端下发改用本地规则时，使用本 Skill。本 Skill 不审查代码、不注入生码规则，只做接入与更新。编码规范本身见 mt-java-coding-standards（CR Skill，全量规则源 rules-for-CR/）与本 Skill 的 references/rules-for-design-and-coding/（精简规则源）。"

metadata:
  skillhub.creator: "xiejian07"
  skillhub.updater: "xiejian07"
  skillhub.version: "V5"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "108658"
  skillhub.high_sensitive: "false"
---

# 业研 Java 编码规范接入工具

## 角色定位

本 Skill 是**接入工具**，帮仓库负责人把业研 L1 编码规范接入到具体业务仓库，让该仓库的 Claude Code / Codex / Cursor 用户（以及关掉云端下发后的 CatPaw 用户）能按规范编码。

接入完成后，本 Skill 不参与日常编码与 CR——编码靠 AGENTS.md/CLAUDE.md 指针 + `.mdp/rules/AGENTS.md` 索引 + 本地规则文件，CR 靠 `mt-java-coding-standards` Skill。

## 何时使用

仓库负责人在以下场景触发本 Skill：
- 团队里有人用 Claude Code / Codex / Cursor 写代码，需要这些工具也遵循业研规范
- 想关掉 CatPaw 云端 Rules 下发，改用仓库内本地规则

不需要本 Skill：团队只用 CatPaw 且接受云端下发（默认已生效）；做代码评审（用 CR Skill）。

## 接入后业务仓库的变化

```
业务仓库/
├── AGENTS.md                    ← 融合一段规范遵循指引（指向 .mdp/rules/AGENTS.md）
├── CLAUDE.md                    ← 只写 @AGENTS.md（import 语法，复用 AGENTS.md 内容）
└── .mdp/
    └── rules/
        ├── AGENTS.md            ← 合并业研规范条目（公司级分组）
        ├── company/
        │   └── java/            ← 业研精简规则文件（29个）
        ├── team/                ← L2 团队规范（团队自维护，本 Skill 不动）
        └── project/             ← L3 项目规范（owner 自维护，本 Skill 不动）
```

规则源在本 Skill 的 `references/rules-for-design-and-coding/`（精简版，29 文件，存于中心仓库 `mt-java-coding-standards` 的 `mt-java-standards-setup/` 目录下）。

> 路径 A（仓库已接入 MDP Rules，`.mdp/` 已存在）在已有体系上叠加 `company/java/` 规则文件与 L1 索引条目；路径 B（`.mdp/` 不存在）从零搭出上图 `.mdp/rules/` 三层骨架再落规则文件。两条路径最终都到达上图结构。

## 接入步骤（首次）

按以下步骤执行，**每步根据业务仓库现状判断处理，不要机械执行**。

### 1. 确认环境

- 当前目录是业务仓库根（有 `.git`）
- 能访问内网（拉规则走 git SSH）

### 2. 判断接入路径

检查业务仓库根目录是否存在 `.mdp/` 目录，决定走哪条路径：

| 业务仓库现状 | 接入路径 |
|--------------|----------|
| `.mdp/` 目录**已存在**（仓库已接入 MDP Rules 体系） | **路径 A** |
| `.mdp/` 目录**不存在** | **路径 B** |

> MDP Rules 是一套独立的规范体系（仓库 `git@git.sankuai.com:hbar/mdp-rule.git`），已接入 MDP Rules 的仓库本地有 `.mdp/` 目录。路径 A 要在已有体系上叠加业研 Java 规范，路径 B 要从零搭建 `.mdp/rules/` 骨架。

下面按判断结果执行对应路径的步骤（路径 A 走 3A/4A/5A，路径 B 走 3B/4B），两条路径都最终汇入步骤 6（融合根目录指针）与步骤 7（提示 commit）。

---

### 路径 A：业务仓库已接入 MDP Rules（`.mdp/` 已存在）

#### 3A. 拉取 mdp-rule master 同步 .mdp/

业务仓库已接入 MDP Rules，`.mdp/` 体系已存在。先把 `mdp-rule` 远程 **master** 分支的最新内容同步到本地 `.mdp/`，确保 MDP Rules 体系本身是最新版，再叠加业研 Java 规则。

用 sparse checkout 只拉 `mdp-rule` 仓库的 `.mdp/` 子目录（避免 clone 整个仓库）：

```bash
TMP_RULE="$(mktemp -d)"
git clone --depth 1 --filter=blob:none --sparse git@git.sankuai.com:hbar/mdp-rule.git "$TMP_RULE"
git -C "$TMP_RULE" sparse-checkout set .mdp
```

把拉到的 `.mdp/` 与本地现有 `.mdp/` 做差异比对，**逐文件决定如何合并**，不要无脑覆盖：

- **本地没有、远程新增的文件**：直接拷贝进来
- **本地有、远程也有的文件**：逐文件 diff，内容一致则跳过；内容不一致即冲突，**停下询问负责人**如何合并（见下方冲突处理）
- **本地有、远程已删除的文件**：可能本地有自定义，**停下询问负责人**是否删除

> mdp-rule 是 MDP Rules 体系的源仓库。本 Skill 维护者也是 mdp-rule 维护者，因此路径 A 主动同步 mdp-rule master，保证业务仓库的 MDP Rules 基线最新。同步只取 master 分支。

**冲突处理（关键）：** 同步过程中遇到任何本地与远程内容不一致的文件，**不要自动覆盖、不要自动跳过**。把冲突文件的本地版本与 mdp-rule master 版本并列展示给负责人，说明差异点，询问采用哪一方或如何合并。常见判断：

- 远程是 MDP Rules 体系升级（如新增分组、修正笔误）→ 倾向采用远程
- 本地是仓库自定义（如团队在 L2 加了条目）→ 倾向保留本地
- 两者都有改动 → 由负责人定夺，本 Skill 不替决策

冲突全部解决后，清理临时目录：

```bash
rm -rf "$TMP_RULE"
```

#### 4A. 拉取业研精简规则进 .mdp/rules/company/java/

`.mdp/` 已同步到最新 MDP Rules 基线。本步骤把业研 Java 精简规则文件落入 `company/java/`（业研规范属于 L1 公司级，落在 `company/java/` 下，与 MDP Rules 体系分层一致）。

**先清空旧规范：** `company/java/` 下若已有旧版业研规范或历史文件，落入前先全部删除，避免新旧规范并存造成歧义。业研规范以中心仓库精简版为准，本地不应保留旧版。

用 git sparse checkout 只拉中心仓库的精简规则子目录（避免 clone 整个仓库）：

```bash
# 先清空 company/java/ 下所有现有文件（旧规范),保留目录本身
mkdir -p .mdp/rules/company/java
find .mdp/rules/company/java -mindepth 1 -delete

# 拉业研精简规则并落入
TMP_DIR="$(mktemp -d)"
git clone --depth 1 --filter=blob:none --sparse git@git.sankuai.com:hbar/mt-java-coding-standards.git "$TMP_DIR"
git -C "$TMP_DIR" sparse-checkout set mt-java-standards-setup/references/rules-for-design-and-coding
cp -R "$TMP_DIR/mt-java-standards-setup/references/rules-for-design-and-coding/." .mdp/rules/company/java/
rm -rf "$TMP_DIR"
```

拉取后确认 `.mdp/rules/company/java/` 下有 29 个 `.md` 文件，且无残留旧文件。

#### 5A. 合并规范索引条目进 .mdp/rules/AGENTS.md

业务仓库的 `.mdp/rules/AGENTS.md` 是 MDP Context 体系的规范总索引，按三个层级分组，优先级为 **L3 项目级 > L2 团队级 > L1 公司级**：

- `## L3 项目级规范`：由项目 owner 维护，覆盖同名的团队级和公司级规范
- `## L2 团队级规范`：由团队维护，覆盖同名的公司级规范
- `## L1 公司级规范`：业研统一维护，优先级最低

本步骤**只操作 L1 公司级分组**，把业研规范条目合并进去。

> 注意：步骤 3A 同步 mdp-rule 后，`.mdp/rules/AGENTS.md` 可能已被 MDP Rules 体系更新过。本步骤在最新版本基础上，只往 `## L1 公司级规范` 分组合并业研 Java 条目，不碰 L2/L3。

**这一步要判断，不是覆盖：**

- **先读现有 `.mdp/rules/AGENTS.md`**（路径 A 下文件已存在），理解已有的三层分组结构和各层条目
- **只操作 `## L1 公司级规范` 分组**：不碰 L2/L3 的任何内容，即使 L2/L3 里有与业研规范同名的条目也不动——同名时 L2/L3 优先级更高，业研 L1 条目仍然写入，但运行时会被高优先级层级覆盖
- **若已有 L1 公司级 Java 相关条目**：对比业研最新条目，补充缺失的、更新过时的，不重复添加已有的
- **若无 L1 公司级 Java 条目**：在 `## L1 公司级规范` 下新增 Java 相关分组，按索引模板插入

**确保文件顶部有 front matter + 自更新 section**：路径 A 下 `.mdp/rules/AGENTS.md` 已存在。读文件顶部，若已有 front matter（含 `setup-skill`/`version`/`last-synced`/`update-interval-days` 字段）和「规范自更新」section，保留并将 `last-synced` 更新为当天日期、`version` 更新为本次执行读到的 `.claude/skills/mt-java-standards-setup/SKILL.md` 的 `metadata.skillhub.version` 值；若文件顶部无 front matter 与自更新 section，按「索引模板」中「.mdp/rules/AGENTS.md 完整框架」顶部的 front matter + 自更新 section 在文件最顶部插入（不覆盖现有索引内容）。

**确保「规范查阅流程」段为最新版**：查阅策略主内容（委派子 Agent、清单契约、校验与回查）收口在该段。若已有该段则整段替换为「索引模板」中的最新版，若无则在「优先级」说明后插入——策略随 Skill 迭代，以此保证已接入仓库拿到最新策略。

执行完跳到 **步骤 6**。

---

### 路径 B：业务仓库未接入 MDP Rules（`.mdp/` 不存在）

#### 3B. 创建 .mdp/rules/ 骨架并落规则文件

从零搭建 `.mdp/rules/` 三层目录骨架，并把业研精简规则文件落进 `company/java/`。

```bash
# 创建三层规范目录骨架
mkdir -p .mdp/rules/company/java
mkdir -p .mdp/rules/team
mkdir -p .mdp/rules/project

# team/ 与 project/ 放 .gitkeep 占位，让空骨架目录能被 git 跟踪
touch .mdp/rules/team/.gitkeep .mdp/rules/project/.gitkeep

# 清空 company/java/ 下可能存在的旧规范文件（防御性:目录可能被手动建过)
find .mdp/rules/company/java -mindepth 1 -delete

# 用 sparse checkout 拉中心仓库的精简规则子目录（避免 clone 整个仓库）
TMP_DIR="$(mktemp -d)"
git clone --depth 1 --filter=blob:none --sparse git@git.sankuai.com:hbar/mt-java-coding-standards.git "$TMP_DIR"
git -C "$TMP_DIR" sparse-checkout set mt-java-standards-setup/references/rules-for-design-and-coding
cp -R "$TMP_DIR/mt-java-standards-setup/references/rules-for-design-and-coding/." .mdp/rules/company/java/
rm -rf "$TMP_DIR"
```

拉取后确认 `.mdp/rules/company/java/` 下有 29 个 `.md` 文件、无残留旧文件。`team/` 与 `project/` 只放 `.gitkeep` 占位（git 不跟踪空目录，占位文件让骨架目录能进版本库），目录内容留给团队和 owner 后续自维护，本 Skill 不写入规范文件。

#### 4B. 新建 .mdp/rules/AGENTS.md 三层索引

路径 B 下文件不存在，直接新建，写入完整结构：顶部为 front matter + 「规范自更新」section，其下为三层分组结构（L2/L3 留占位），并在 `## L1 公司级规范` 下插入业研 Java 条目。完整内容见**索引模板**中的「.mdp/rules/AGENTS.md 完整框架」。front matter 的 `version` 取值：执行 setup 时读 `.claude/skills/mt-java-standards-setup/SKILL.md` front matter 中 `metadata.skillhub.version` 的值填入（如 V2、V3）；`last-synced` 填入当天日期。

执行完跳到 **步骤 6**。

---

### 6. 清理旧索引并融合指针进根目录 AGENTS.md / CLAUDE.md

根目录 AGENTS.md 只插入一小段带标题的规范遵循指引（短指针，指向 `.mdp/rules/AGENTS.md`），轻量、不污染现有内容——查阅策略主内容（委派子 Agent、清单契约、校验与回查）收口在 `.mdp/rules/AGENTS.md` 的「规范查阅流程」段，根目录不承载；CLAUDE.md 只写 `@AGENTS.md`（Claude Code 的 import 语法，复用 AGENTS.md 内容，避免重复维护）。同时清理 mdp-rule 旧体系遗留在根 AGENTS.md 里的旧规范索引。

**这一步要判断，不是覆盖：**

- **先读现有文件**（若存在），理解现有结构
- **删除 mdp-rule 旧规范索引**：若根 AGENTS.md 中有 mdp-rule 旧体系留下的规范索引内容（如直接列出的规则条目、指向旧路径的规范段落、与 `.mdp/rules/AGENTS.md` 重复或冲突的规范索引），整段删除——规范索引已统一收口到 `.mdp/rules/AGENTS.md`，根目录只保留规范遵循指引段，不再承载索引内容。删除前向负责人展示将删除的段落，确认无误后再删。CLAUDE.md 同理清理旧索引段落
- **AGENTS.md 找合适位置插入指引**：基于对现有内容的理解判断最合适的位置——若有"编码规范"相关节插入其下，若有其他工具索引跟着放，若结构不明显放在文件末尾。不要机械追加，让插入后读起来自然
- **若 AGENTS.md 已有指向 `.mdp/rules/AGENTS.md` 的指引**：替换为最新版指引（旧版可能是单行指针），仍需检查并删除旧索引段落
- **若 AGENTS.md 文件不存在**：直接新建，只写这一段
- **CLAUDE.md 只加一行 `@AGENTS.md`**：CLAUDE.md 用 Claude Code 的 import 语法复用 AGENTS.md 内容，不重复写指引正文。分情况处理：
  - **文件不存在**：新建，只写 `@AGENTS.md`
  - **文件已存在、且无旧规范指引段**：在文件**开头**插入一行 `@AGENTS.md`（import 语法会把它导入的内容当作紧跟在该行的下文展开），其余已有内容一律不动
  - **文件已存在、且含旧规范指引段**（如过去复制进去的「方案设计与编码规范遵循」整段正文）：把该旧指引段整段删除，在文件开头插入 `@AGENTS.md`；其余与规范无关的内容不动
  - CLAUDE.md 中与规范无关的内容始终不动

AGENTS.md 插入内容：
```
## 方案设计与编码规范遵循

【严格遵循】方案设计和编码阶段需要遵循规范：先读 `.mdp/rules/AGENTS.md`，按其中「规范查阅流程」匹配本任务命中的规范并查阅后编码（含编码后的回溯要求）。
```

CLAUDE.md 内容（仅一行，使用 Claude Code import 语法复用 AGENTS.md）：
```
@AGENTS.md
```

### 7. 提示 commit

接入完成后，检查 `.gitignore` 规则；若 `.mdp/` 被忽略，直接调整对应忽略规则，确保 `.mdp/` 目录下所有文件均可提交到 Git。**不要自动 commit**。列出改动文件，提示负责人 review 后手动 commit：

```
git add .mdp/rules/company/java/ .mdp/rules/AGENTS.md .mdp/rules/team/ .mdp/rules/project/ AGENTS.md CLAUDE.md
git commit -m "chore: 接入业研 Java 编码规范（L1）"
```

### 8. 提示可选：关闭 CatPaw 云端下发

若负责人希望所有工具统一走本地规则，可在 CatPaw 平台关闭本仓库的云端 Rules 下发。本 Skill 不代操作，只提示。操作步骤参考：[关闭 CatPaw 云端 Rules 下发](https://km.sankuai.com/collabpage/2730079987)。

## 更新流程（规则迭代后）

精简版规则随业研季度迭代，需让已接入的业务仓库跟进新版。**「更新」与「初始化」的关键差别**：更新不重跑建骨架、不重融合根目录 AGENTS.md/CLAUDE.md 指针，只刷新规范文件、`.mdp/rules/AGENTS.md` 的 L1 索引与「规范查阅流程」段、版本元信息（front matter）。更新同样先按**步骤 2** 判断路径。

更新流程要动四个方面，下面按路径分别说清：

1. **规范文件更新**：`.mdp/rules/company/java/` 下规则文件从旧版更新到新版——沿用初始化的覆盖式语义（清空 + 重新落入），不逐文件 diff；团队级 L2（`team/`）、项目级 L3（`project/`）一律不动
2. **`.mdp/rules/AGENTS.md` 索引更新**：只动 `## L1 公司级规范` 下的 Java 条目——补充新增条目、删除废弃条目、更新变更条目（路径/触发场景/名称随规则迭代而变）；L2/L3 分组不动。同时把「规范查阅流程」段整段替换为「索引模板」中的最新版（查阅策略随 Skill 迭代，以此下发到已接入仓库），并刷新文件顶部 front matter 的 `last-synced`（见下方步骤），`version` 在自更新流程里刷新
3. **根目录 AGENTS.md / CLAUDE.md**：**不需要动**。指针段是泛指「先读 `.mdp/rules/AGENTS.md`，按其中『规范查阅流程』查阅」，不引用具体条目与策略细节——规范条目迭代、查阅策略迭代都只落索引文件，根目录指针稳定不变
4. **mdp-rule 同步**（仅路径 A）：**不在每次更新时重跑**。步骤 3A 同步 mdp-rule master 只在「MDP Rules 体系本身升级」时才需要——即规则文件变更、`## L1 公司级规范` 条目调整这类业研 Java 规范迭代，不触发 mdp-rule 同步。仅当负责人确认 MDP Rules 基线有升级（如 mdp-rule master 有新提交、`.mdp/` 体系文件需跟进）时，才重跑步骤 3A，冲突同样停下询问负责人

### 路径 A（`.mdp/` 已存在）更新流程

1. **规范文件更新**：重跑**步骤 4A** 的 sparse checkout + 清空覆盖逻辑，把 `.mdp/rules/company/java/` 下 29 个规则文件更新到最新精简版（先 `find ... -delete` 清空再落入）。**不重跑 3A**（见上方第 4 点，除非 MDP Rules 体系本身升级）
2. **索引更新**：重跑**步骤 5A** 的合并逻辑——读现有 `.mdp/rules/AGENTS.md`，只对比 `## L1 公司级规范` 下 Java 条目：补充新增的、删除已废弃的、更新内容变更的（名称/触发场景/路径），不碰 L2/L3；同时把「规范查阅流程」段整段替换为「索引模板」中的最新版
3. **front matter 刷新**：更新文件顶部 front matter 的 `last-synced` 为当天日期（若文件顶部无 front matter，按含 front matter + 自更新 section 的完整框架补齐顶部）
4. 提示 commit

### 路径 B（`.mdp/` 不存在）更新流程

1. **规范文件更新**：重跑**步骤 3B** 的 sparse checkout + 清空覆盖逻辑，把 `.mdp/rules/company/java/` 下 29 个规则文件更新到最新精简版（骨架目录已存在，仍先 `find ... -delete` 清空旧文件再落入）
2. **索引更新**：重跑**步骤 4B** 的对比逻辑——只对比 `.mdp/rules/AGENTS.md` 的 `## L1 公司级规范` 下 Java 条目：补充新增的、删除已废弃的、更新内容变更的，不碰 L2/L3；同时把「规范查阅流程」段整段替换为「索引模板」中的最新版
3. **front matter 刷新**：更新文件顶部 front matter 的 `last-synced` 为当天日期（若文件顶部无 front matter，按含 front matter + 自更新 section 的完整框架补齐顶部）
4. 提示 commit

## 索引模板

### 根目录指针（AGENTS.md 融合内容）

```
## 方案设计与编码规范遵循

方案设计和编码阶段需要遵循规范：先读 `.mdp/rules/AGENTS.md`，按其中「规范查阅流程」匹配本任务命中的规范并查阅后编码（含编码后的回溯要求）。
```

### 根目录 CLAUDE.md 内容

```
@AGENTS.md
```

CLAUDE.md 只写 `@AGENTS.md`（Claude Code 的 import 语法），复用 AGENTS.md 的内容，避免两份文件重复维护。

### .mdp/rules/AGENTS.md 完整框架

**路径 B（文件不存在，步骤 4B）**：直接新建，写入下方完整结构——顶部为 front matter + 「规范自更新」section，其下为三层规范索引框架（L2/L3 留占位），并在 `## L1 公司级规范` 下插入末尾的 Java 条目。front matter 的 `version` 取值：执行 setup 时读 `.claude/skills/mt-java-standards-setup/SKILL.md` front matter 中 `metadata.skillhub.version` 的值填入（如 V2、V3）；`last-synced` 填入当天日期。

**路径 A（文件已存在，步骤 4A/5A）**：不使用本框架整体覆盖，只把 `## L1 公司级规范` 下的 Java 条目合并进现有文件的对应分组，不动 L2/L3 的任何内容。同时确保文件顶部存在 front matter + 「规范自更新」section（见下方框架顶部）——若已有 front matter 则保留并按需更新 `last-synced`、`version`，若无则在文件最顶部插入 front matter + 「规范自更新」section。再确保「规范查阅流程」段存在——若已有则替换为最新版，若无则在「优先级」说明后插入。下方框架仅供理解目标结构。

```markdown
---
setup-skill: mt-java-standards-setup
version: <执行时读 .claude/skills/mt-java-standards-setup/SKILL.md 的 metadata.skillhub.version 填入，如 V2、V3>
last-synced: <执行时填入当天日期，格式 YYYY-MM-DD>
update-interval-days: 7
---

# 规范文档索引

优先级：L3 项目级 > L2 团队级 > L1 公司级

同名规范存在于多个层级时，以最高优先级层级为准。

---

## 规范自更新（读取本文件时优先处理）

若「今天」距 front matter 中 `last-synced` 超过 `update-interval-days` 天，执行：

1. 确保 mtskills 可用：运行 `mtskills --version`，失败则安装：`npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com`
2. 拉取最新 skill：`mtskills pull mt-java-standards-setup`；若失败（skill 未安装）则改用 `mtskills i mt-java-standards-setup`
3. 读取 `.claude/skills/mt-java-standards-setup/SKILL.md` front matter 中 `metadata.skillhub.version` 的值
4. 与本文件 front matter 的 `version` 比对：
   - 相同 → 仅将 `last-synced` 更新为今天，跳过后续更新
   - 不同 → 按 `.claude/skills/mt-java-standards-setup/SKILL.md` 的「更新流程」执行，刷新 `.mdp/rules/` 下规则文件与本文件 L1 索引，并将 `version` 与 `last-synced` 都更新为最新值
5. 任一步失败则静默跳过，不阻塞当前任务

未超期则跳过本节，继续查阅下方规范索引。

---

## 规范查阅流程

**核心原则：精准召回、宁缺毋滥、按需注入。** 规则分阶段按需召回，优先保证核心规则的召回精度与遵守质量；允许漏召回——编码后回溯与 AI CR 阶段提供多层兜底。规则正文默认由子 Agent 读取，主上下文只保留规则清单：命中 ≥3 个规则文件时，禁止主 Agent 直接 Read 规则文件全文（规则正文量大，进主上下文会挤占整段会话）；命中 ≤2 个文件时主 Agent 可直接读全文（单文件约 100~250 行），信息零损失且比委派更省。

1. **方案定型后精准召回（主环节）**：先完成代码调研、确定实现方案（明确涉及的技术点：线程池/MQ/事务/锁/缓存等），再从下方索引表「触发场景」列匹配规范并查阅。**不要在任务最开始、方案未定前查规则**——此时相关性判断天然不准，容易全量滥召回、稀释对核心规则的遵守。
   - 委派子 Agent 时：**把需求与实现方案一并传给子 Agent**，子 Agent 读规则文件全文后自行判断相关性，**只返回与本任务相关的规则**；判定不相关的条目不返回（宁缺毋滥，由后续阶段兜底）。
   - 返回形态：以原文每个相关规则条目（`### 规则编号` 小节）为单位逐条列出：`规则编号 + [强制/推荐] + 核心约束（参数/阈值/公式照抄原文，不概括）+ 全部禁止项 + 原文正确写法示例（可只保留关键片段）`；示例必须摘自规则原文，不得自行推导；末尾附召回清单：`本文件共 N 条规则，召回 M 条：编号列表`。
   - 主 Agent 拿到清单先校验再编码：召回结果明显不合理（如强烈相关的并发/事务/异常规范一条未召回）则打回重抽；对拿不准的条目，按规则编号派子 Agent 回查该小节原文，禁止凭清单猜测。
   - 子 Agent 只返回规则内容本身，不要基于清单再做「针对本任务的编码要点提炼/方案建议」——那是主 Agent 的职责。
2. **编码中按需补查（JIT 注入）**：编码过程中涉及方案外的新领域（如临时引入缓存、MQ、新工具类、新外部调用），随时按同一方式补查对应规则文件：命中 ≤2 个文件主 Agent 直接读全文，≥3 个文件委派子 Agent（同样携带需求与方案背景）。
3. **编码后回溯（必做兜底）**：回到本索引表，逐条对照每条规范的「触发场景」列与你的代码，补齐前序阶段漏查的规范。前序阶段允许遗漏：回溯是第一层兜底，AI CR 阶段基于全量规则源独立检查是第二层兜底。
   - 回溯的「对照判断」由主 Agent 直接执行，不委派子 Agent：索引表已在主上下文，且主 Agent 掌握完整代码语境（含规则与项目惯例冲突时的取舍），委派反而需传输大 diff、损失语境。
   - 回溯命中的「规则正文补查」沿用同一委派阈值：≤2 个文件主 Agent 直接读全文，≥3 个文件委派子 Agent（携带需求与最终方案）。
   - 大 diff 场景（如重构涉及大量文件）可委派子 Agent 做触发场景初筛（输入：需求 + 改动文件清单 + 本索引表），主 Agent 复核其结论后再补查。

---

## L3 项目级规范（最高优先级）

> 由项目 owner 在 `.mdp/rules/project/` 下维护，覆盖同名的团队级和公司级规范。

_暂无项目级规范_

## L2 团队级规范

> 由团队在 `.mdp/rules/team/` 下维护，覆盖同名的公司级规范。

_暂无团队级规范_

## L1 公司级规范

> 由公司统一维护，适用于所有仓库，优先级最低。

[插入以下 Java 条目]
```

**以下为插入 `## L1 公司级规范` 下的 Java 条目：**

```markdown
**Java编码规范**

| 名称 | 触发场景 | 路径 |
|------|----------|------|
| `JAVA-01-常量定义规范` | 常量定义、枚举使用、魔法值治理 | `.mdp/rules/company/java/JAVA-01-常量定义规范.md` |
| `JAVA-02-OOP设计规约` | 类设计、访问控制、对象拷贝与内存泄漏预防 | `.mdp/rules/company/java/JAVA-02-OOP设计规约.md` |
| `JAVA-03-集合处理规范` | 集合初始化、比较器实现、数组转换 | `.mdp/rules/company/java/JAVA-03-集合处理规范.md` |
| `JAVA-04-并发处理规范` | 线程安全、线程池、锁与并发集合 | `.mdp/rules/company/java/JAVA-04-并发处理规范.md` |
| `JAVA-05-异常处理规范` | 异常分类、捕获处理、自定义异常与异常链 | `.mdp/rules/company/java/JAVA-05-异常处理规范.md` |
| `JAVA-06-日志记录规范` | 日志级别、日志内容、敏感信息处理 | `.mdp/rules/company/java/JAVA-06-日志记录规范.md` |
| `JAVA-07-单元测试编写规范` | 单元测试、Mock使用、测试方法设计 | `.mdp/rules/company/java/JAVA-07-单元测试编写规范.md` |
| `JAVA-08-接口设计规范` | 接口命名、参数返回、幂等与版本设计 | `.mdp/rules/company/java/JAVA-08-接口设计规范.md` |

**数据库规范**

| 名称 | 触发场景 | 路径 |
|------|----------|------|
| `DB-01-ORM规范` | ORM查询字段、类型安全结果集、DAO生成工具 | `.mdp/rules/company/java/DB-01-ORM规范.md` |
| `DB-02-MySQL-SQL开发规范` | SQL编写、DML约束、多表别名与批量操作 | `.mdp/rules/company/java/DB-02-MySQL-SQL开发规范.md` |
| `DB-03-MySQL-建表规范` | 建表设计、字段命名、类型选择、注释要求 | `.mdp/rules/company/java/DB-03-MySQL-建表规范.md` |
| `DB-04-MySQL-索引规范` | 索引设计、联合索引、分页与JOIN优化 | `.mdp/rules/company/java/DB-04-MySQL-索引规范.md` |

**安全规范**

| 名称 | 触发场景 | 路径 |
|------|----------|------|
| `SEC-01-注入安全规范` | SQL注入防护、HTTP安全头与Cookie安全、CSRF防护 | `.mdp/rules/company/java/SEC-01-注入安全规范.md` |
| `SEC-02-数据保护规范` | XSS防御、敏感信息脱敏、反序列化安全 | `.mdp/rules/company/java/SEC-02-数据保护规范.md` |
| `SEC-03-访问控制与网络安全规范` | 文件操作安全、路径遍历防护、SSRF防护、网络访问安全 | `.mdp/rules/company/java/SEC-03-访问控制与网络安全规范.md` |

**高可用规范**

| 名称 | 触发场景 | 路径 |
|------|----------|------|
| `HA-01-失败设计规范` | 超时、重试（指数退避）、熔断（Rhino）、降级、限流 | `.mdp/rules/company/java/HA-01-失败设计规范.md` |
| `HA-02-可观测性规范` | Raptor/Cat Metrics埋点、Mtrace链路、分级告警 | `.mdp/rules/company/java/HA-02-可观测性规范.md` |
| `HA-03-防御性编程规范` | 参数校验、空指针防御、异常链 | `.mdp/rules/company/java/HA-03-防御性编程规范.md` |
| `HA-04-存储高可用规范` | 事务安全（禁止事务内RPC）、MySQL查询性能、软删除 | `.mdp/rules/company/java/HA-04-存储高可用规范.md` |
| `HA-05-缓存高可用规范` | 缓存一致性、容量治理、穿透/击穿/雪崩防护 | `.mdp/rules/company/java/HA-05-缓存高可用规范.md` |
| `HA-06-消息队列高可用规范` | 发送结果检查、消费幂等、死信队列 | `.mdp/rules/company/java/HA-06-消息队列高可用规范.md` |
| `HA-07-JVM与线程池高可用规范` | ThreadLocal finally remove、TTL跨线程池传递、并发安全 | `.mdp/rules/company/java/HA-07-JVM与线程池高可用规范.md` |
| `HA-09-最终一致性规范` | 幂等设计、本地消息表、Saga/TCC、延迟双删 | `.mdp/rules/company/java/HA-09-最终一致性规范.md` |
| `HA-10-接口兼容性规范` | 接口版本管理、共存周期、灰度 | `.mdp/rules/company/java/HA-10-接口兼容性规范.md` |
| `HA-11-配置安全规范` | volatile+硬编码默认值、boolean开关、Lion降级链 | `.mdp/rules/company/java/HA-11-配置安全规范.md` |
| `HA-12-安全编码规范` | 接口认证拦截器(P0)、防水平越权(userId/tenantId入查询条件)、防垂直越权(后端独立权限校验) | `.mdp/rules/company/java/HA-12-安全编码规范.md` |
| `HA-13-搜索引擎高可用规范` | 禁止深分页、filter替代must、Bulk写入、Lion切流 | `.mdp/rules/company/java/HA-13-搜索引擎高可用规范.md` |
| `HA-14-HBase高可用规范` | RowKey Hash前缀散列、同步写入、禁止逐条flush | `.mdp/rules/company/java/HA-14-HBase高可用规范.md` |

**依赖规范**

| 名称 | 触发场景 | 路径 |
|------|----------|------|
| `DEP-01-依赖规范` | Maven依赖管理、版本冲突与SNAPSHOT管控 | `.mdp/rules/company/java/DEP-01-依赖规范.md` |
```

## 执行约束

- **不自动 commit**：所有写操作完成后提示负责人手动 commit
- **不碰 .catpaw/rules/**：那是仓库 L3，本 Skill 不动
- **只操作 L1 公司级条目**：`.mdp/rules/AGENTS.md` 中只操作 `## L1 公司级规范` 分组，L2 团队级和 L3 项目级的条目一律不动
- **路径 A 主动同步 mdp-rule master**：本 Skill 维护者也是 mdp-rule 维护者，路径 A 第一步拉 mdp-rule master 同步本地 `.mdp/`，保证 MDP Rules 基线最新；同步只取 master 分支
- **路径 A 冲突必须询问用户**：同步 mdp-rule 时遇到本地与远程内容不一致的文件，不自动覆盖、不自动跳过，并列展示差异由负责人定夺；业研 Java 条目合并进 L1 分组时同样只合并不覆盖
- **路径 B 只搭 company/java 骨架**：`team/`、`project/` 各放一个 `.gitkeep` 占位（让空目录能被 git 跟踪），本 Skill 不写入规范文件，留给团队和 owner 自维护
- **合并而非覆盖**：`.mdp/rules/AGENTS.md` 已有内容时合并，根目录 AGENTS.md 已有内容时融合
- **CLAUDE.md 只写 `@AGENTS.md`**：使用 Claude Code import 语法复用 AGENTS.md 内容，不重复写指引正文，避免两份文件不一致
- **在业务仓库根目录执行**：路径均以业务仓库根为基准
