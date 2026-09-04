---
name: ai-ready-repo
description: 评估代码仓库的 AI-Ready 程度，生成详细评估报告与改进建议
version: 3.7.0
author: maoyue05

metadata:
  skillhub.creator: "maoyue05"
  skillhub.updater: "maoyue05"
  skillhub.version: "V33"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "9802"
  skillhub.high_sensitive: "false"
---

# AI-Ready 评估工具

对代码仓库的 AI 协作就绪度进行系统性评估，生成量化报告与分级改进建议。

## 触发条件

用户说出以下任意一句话时激活：
- "评估 AI-Ready"
- "AI-Ready 评估"
- "生成 AI-Ready 报告"
- "检查项目的 AI 友好度"
- "AI 协作评估"
- "评估远程仓库 AI-Ready"
- "扫描远程仓库"
- 用户提供 `https://dev.sankuai.com/code/repo-detail/*` 格式的链接时，自动激活**远程模式**

---

## 六层认知模型

评分体系基于以下六层认知模型设计。每一层回答 AI 协作中的一个核心问题，层层递进，缺失任何一层都会导致 AI 协作在对应环节失效。

```
┌─────────────────────────────────────────────────────────────┐
│  L1  仓库定位                                                │
│      AI 在整个系统中是什么角色？边界在哪？怎么导航到对的文档？  │
│      缺失后果：AI 在错误仓库改代码，或做出跨边界的设计         │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  L2  仓库结构                                                │
│      架构长什么样？模块怎么分工？依赖关系是什么？              │
│      缺失后果：AI 无法精准定位修改范围，改 A 坏 B             │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  L3  代码细节                                                │
│      代码能被理解、安全修改、正确扩展吗？                      │
│      缺失后果：AI 靠猜名字推逻辑，产生幻觉；改动引发连锁破坏   │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  L4  开发执行                                                │
│      怎么开发新需求？业务知识、开发规范、AI 协作方式           │
│      缺失后果：AI 遗漏隐含规则，违反禁止行为，找不到协作路径   │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  L5  测试验证                                                │
│      AI 改完能自证正确性？（测试 + CI 质量门禁）              │
│      缺失后果：AI 无法自验证，形成严重的人工 Review 瓶颈       │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  L6  反馈回路                                                │
│      经验能沉淀回来，仓库不随迭代退化？                        │
│      缺失后果：AI-Ready 变成一次性改造，每次都要重新教 AI      │
└─────────────────────────────────────────────────────────────┘
```

> **L5 vs L6**：L5 是单次任务的完成质量（每次改完能否自动验证）；L6 是仓库的持续进化能力（AI-Ready 程度能否保持甚至提升）。

---

## 评分维度总览

评估采用 **11 个维度**加权打分，总分 100 分。

**权重按仓库类型分档（weight profile）**：权重的唯一真相源是 [references/weight-profiles.json](references/weight-profiles.json)，交互式流程（本文件第三步）与 CLI（`scripts/score_commit.py`）均以该文件为准，**禁止在别处另行硬编码权重**。下表的「后端权重」即 `backend` 档（`unknown` 回退此档）；「前端权重」即 `frontend` 档（适用 `frontend` / `frontend-mono` / `nodejs`）。

| # | 维度 | 后端权重 | 前端权重 | 认知层 | 详细标准 |
|---|------|---------|---------|--------|---------|
| 1 | **仓库定位准确性** | **6%** | **6.7%** | L1 | [→ references/dim1a-repo-positioning.md](references/dim1a-repo-positioning.md) |
| 2 | **仓库导航完整性** | **6%** | **6.7%** | L1 | [→ references/dim1b-repo-navigation.md](references/dim1b-repo-navigation.md) |
| 3 | **架构文档完整性** | **12%** | **13.4%** | L2 | [→ references/dim2-architecture-docs.md](references/dim2-architecture-docs.md) |
| 4 | **代码可读性** | **8%** | **8.9%** | L3 | [→ references/dim3-code-readability.md](references/dim3-code-readability.md) |
| 5 | **代码可维护性** | **7%** | **7.8%** | L3 | [→ references/dim4-maintainability.md](references/dim4-maintainability.md) |
| 6 | **代码可扩展性** | **5%** | **5.6%** | L3 | [→ references/dim5-extensibility.md](references/dim5-extensibility.md) |
| 7 | **业务领域建模** | **14%** | **15.5%** | L4 | [→ references/dim6-domain-modeling.md](references/dim6-domain-modeling.md) |
| 8 | **编码规范遵守度** | **12%** | **13.4%** | L4 | [→ references/dim7-coding-standards.md](references/dim7-coding-standards.md) |
| 9 | **AI 协作友好度** | **8%** | **8.9%** | L4 | [→ references/dim8-ai-collaboration.md](references/dim8-ai-collaboration.md) |
| 10 | **测试验证** | **12%** | **2%** | L5 | [→ references/dim9-testing.md](references/dim9-testing.md) |
| 11 | **反馈回路** | **10%** | **11.1%** | L6 | [→ references/dim10-feedback-loop.md](references/dim10-feedback-loop.md) |

> **为什么前端测试维度降权？** 前端 UI 组件测试的 ROI 远低于后端单元测试，绝大多数前端仓库缺少系统化单测，若按后端 12% 同口径计会系统性拉低前端得分。故前端 `dim9` 降权至 2%（**降权而非归零**——仅保留对"有 Vitest/Jest + 覆盖率门禁"等优秀前端测试投入的微弱区分度），腾出的 10% 按比例（×98/88）摊回其余 10 个维度（dim6 吸收取整余量）。两档权重之和均严格 = 100%，满分仍为 100。

### 按认知层分布

| 认知层 | 维度 | 后端合计 | 前端合计 |
|--------|------|---------|---------|
| L1 仓库定位 | 仓库定位准确性 + 仓库导航完整性 | 12% | 13.4% |
| L2 仓库结构 | 架构文档完整性 | 12% | 13.4% |
| L3 代码细节 | 代码可读性 + 代码可维护性 + 代码可扩展性 | 20% | 22.3% |
| L4 开发执行 | 业务领域建模 + 编码规范遵守度 + AI 协作友好度 | 34% | 37.8% |
| L5 测试验证 | 测试验证 | 12% | 2% |
| L6 反馈回路 | 反馈回路 | 10% | 11.1% |

**等级划分**：
- **90–100**：优秀 ⭐⭐⭐⭐⭐ — 高度 AI-Ready，AI 自主完成大部分任务
- **75–89**：良好 ⭐⭐⭐⭐ — 基本 AI-Ready，部分场景需人工辅助
- **50–74**：及格 ⭐⭐⭐ — 需要改造，AI 频繁出错
- **<50**：不及格 ⭐⭐ — 未就绪，AI 基本无法独立工作

---

## 执行流程

### 第零步：环境依赖预检查

读取 [references/step0-precheck.md](references/step0-precheck.md) 并执行依赖检查。

**模式判断**（预检查完成后）：
- 若用户提供了 `https://dev.sankuai.com/code/repo-detail/*` 链接 → 读取 [references/step7-remote-mode.md](references/step7-remote-mode.md) 执行**远程模式**，完成后跳至第七步
- 否则 → 继续**本地模式**（当前工作目录），执行第一步至第七步

---

### 第一步：识别仓库形态 + 收集项目基线信息 + AI 冷启动路径追踪

#### 1.0 REPO_SHAPE 与子仓库边界识别

先使用确定性脚本识别当前仓库是否为 mono-repo：

```bash
python3 "$SKILL_ROOT/scripts/monorepo.py" discover --root .
```

脚本只接受构建清单显式声明的成员，按以下优先级选择权威清单：
`pnpm-workspace.yaml#packages`、`package.json#workspaces`、Maven `pom.xml#modules`、
Gradle `settings.gradle(.kts)#include`。不扫描未声明目录，不把根目录计为成员。

- `is_monorepo=false`：根目录作为单仓，继续执行 1.1 至第七步。
- `is_monorepo=true`：将 `members` 中每个一级成员作为独立单仓，分别执行 1.1 至第五步；
  每个成员独立识别 `REPO_TYPE`、选择权重档案并完成 11 维评分。成员可沿父仓导航读取共享
  治理文档，但不得递归拆分成员内部的 workspace，也不得对 mono-repo 根目录评分。

清单包含越界路径、声明目录不存在、工作区模式无匹配或成员为空时，停止评估并报告清单错误，
不得回退为根目录单仓评分。

#### 1.1 REPO_TYPE 自动检测

**首先执行以下命令识别仓库类型**，后续所有步骤将基于此结果选择对应的评估路径：

```bash
# REPO_TYPE 自动检测
if [ -f "pom.xml" ] || (ls build.gradle 2>/dev/null && find . -name "*.java" -maxdepth 5 | head -1 | grep -q .); then
  REPO_TYPE="backend"
elif [ -f "pnpm-workspace.yaml" ] || ([ -f "package.json" ] && python3 -c "import json; d=json.load(open('package.json')); exit(0 if 'workspaces' in d else 1)" 2>/dev/null); then
  REPO_TYPE="frontend-mono"
elif [ -f "package.json" ] && grep -qE '"react"|"vue"|"next"|"nuxt"|"vite"' package.json 2>/dev/null; then
  REPO_TYPE="frontend"
elif [ -f "package.json" ]; then
  REPO_TYPE="nodejs"
else
  REPO_TYPE="unknown"  # 回退到后端标准
fi
echo "检测到 REPO_TYPE: $REPO_TYPE"
```

#### 1.2 项目规模统计

根据 REPO_TYPE 执行对应统计：

**backend**：
```bash
find . -name "*.java" -type f | wc -l  # Java 文件数
find . -name "*.xml" -type f | wc -l   # XML 文件数
find . -name "*.java" -type f -exec wc -l {} + | tail -1  # 代码总行数
du -sh .  # 项目体积
```

**frontend / frontend-mono / nodejs**：
```bash
find . \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" -not -path "*/dist/*" | wc -l  # TS 文件数
find . -name "*.tsx" -not -path "*/node_modules/*" -not -path "*/dist/*" | wc -l  # 组件文件数
find . \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) -not -path "*/node_modules/*" -exec wc -l {} + | tail -1  # 代码总行数
du -sh . --exclude=node_modules  # 项目体积
```

#### 1.3 文档体系识别

- 检查导航入口文件是否存在（AGENTS.md / .cursorrules / .catpaw/rules/）
- 统计文档文件数量与类型
- **检查文档是否为空模板**（仅有骨架无实质内容）

#### 1.4 AI 冷启动路径追踪（Cold Start Path Trace）

在进入 11 维度评分之前，**必须先沿以下路径逐步追踪**，记录每一跳的可达性和信息完整度。路径中每一个断链都将直接扣减对应维度的分数。

**后端路径**（REPO_TYPE = backend）：
```
Step 0: AGENTS.md / CLAUDE.md（入口）
  → 检查：entry 文件是否存在；是否包含"这是什么"的描述；是否有指向架构文档的路由

Step 1: 架构文档（README / .mdp/OVERVIEW.md / *-architecture.md）
  → 检查：路由是否能从 Step 0 直达；文档内容是否覆盖模块分工和关键路径

Step 2: 领域/业务文档（domain docs、业务规则、禁止行为、编码规范）
  → 检查：路由是否能从 Step 1 直达；内容是否有实质性领域知识

Step 3: 具体代码（核心 Service / DAO 的方法签名 + Javadoc）
  → AI 仅凭签名和注释（不读实现体），能否理解方法意图、参数含义、失败条件？
```

**前端路径**（REPO_TYPE = frontend / frontend-mono / nodejs）：
```
Step 0: AGENTS.md / .cursorrules / .catpaw/rules/ / .github/copilot-instructions.md（入口）
  → 检查：导航入口文件是否存在；是否包含"这是什么仓库"的描述；是否有指向架构文档的路由

Step 1: 架构文档（README / docs/ 目录下的架构文档）
  → 检查：路由是否能从 Step 0 直达；文档内容是否覆盖目录结构、模块划分、子应用关系

Step 2: 业务/规范文档（.cursorrules / .catpaw/rules/ 内容）
  → 检查：路由是否能从 Step 1 直达；内容是否有实质性领域知识、禁止行为、编码规范

Step 3: 核心 Hook/组件的 TypeScript 签名 + JSDoc
  → AI 仅凭签名和类型（不读实现体），能否理解意图、参数含义、返回值？
```

**评分映射**（追踪结果作为后续各维度的扣分依据）：

| 信息在哪一步可达 | 可发现性评级 |
|----------------|-------------|
| Step 0–1（从入口直达） | 高（满分） |
| Step 2–3（需进入领域/代码层） | 中（扣 20–40%） |
| 需要全仓库 grep 才能找到 | 低（扣 60%） |
| 完全无法找到 | 0 分 |

```bash
# 后端 Step 0：检查 entry 文件存在性及路由指向
ls AGENTS.md CLAUDE.md 2>/dev/null
grep -E "架构|architecture|OVERVIEW|README|\.mdp" AGENTS.md 2>/dev/null | head -10

# 前端 Step 0：检查导航入口文件
ls AGENTS.md .cursorrules .catpaw/rules/ .github/copilot-instructions.md 2>/dev/null

# Step 1：检查架构文档可达性（从 entry 引用的路径是否真实存在）
grep -oE '\[[^\]]+\]\([^)]+\.md\)' AGENTS.md 2>/dev/null | grep -oE '\([^)]+\)' | tr -d '()' \
  | while read path; do [ -f "$path" ] && echo "✅ 可达: $path" || echo "❌ 断链: $path"; done

# 后端 Step 3：抽样核心 Service 方法签名（仅签名与注释，不读方法体）
find . -path "*/service/*Service.java" -not -path "*/test/*" 2>/dev/null | head -3 \
  | while read f; do
    echo "=== $f ==="; grep -n "public\|/\*\*\|@param\|@return\|@throws" "$f" | head -30
  done

# 前端 Step 3：抽样核心 Hook 签名（仅签名与类型，不读实现体）
find . \( -path "*/hooks/use*.ts" -o -path "*/hooks/use*.tsx" \) -not -path "*/node_modules/*" 2>/dev/null | head -3 \
  | while read f; do
    echo "=== $f ==="; grep -n "export\|interface \|type \|: \|/\*\*\|@param\|@returns" "$f" | head -20
  done
```

### 第二步：十一维度逐项评估

对每个维度，读取对应 `references/dim*.md` 文件获取完整评估标准、评分细则和检查命令，逐项执行评估。

**执行规则**：每个 dim 文件的评估标准和评分细则适用于所有技术栈。在"技术栈执行指南"表格中，根据第一步识别的 `REPO_TYPE` 选择对应列的检查命令执行。若存在"结构性差异说明"区块，评分时以该区块为准。

评估 **dim1b（仓库导航完整性）** 和 **dim3（代码可读性）** 时，将冷启动路径追踪结果作为首要依据。

mono-repo 必须对 `members` 中的每个成员完整执行本步骤并分别保留 11 维原始分、加权分、
评级、优势、问题和建议；禁止抽样成员或用根目录扫描结果代替成员评分。

### 第三步：计算综合分

**严格按以下步骤逐项计算，禁止跳步或估算。**

#### 3.1 选择权重档案（按 REPO_TYPE）

权重不再写死，而是根据第一步识别的 `REPO_TYPE` 从 [references/weight-profiles.json](references/weight-profiles.json) 中选择对应档案：

```bash
# 读取权重档案（profile 名 = repo_type_to_profile[REPO_TYPE]，其中 frontend/frontend-mono/nodejs → frontend；backend/unknown → backend）
python3 -c "
import json, sys
cfg = json.load(open('$SKILL_ROOT/references/weight-profiles.json'))
rt = '$REPO_TYPE'
prof = cfg['repo_type_to_profile'].get(rt, 'backend')
w = cfg['profiles'][prof]['weights']
print(f'使用权重档案: {prof}')
for k in ['dim1a','dim1b','dim2','dim3','dim4','dim5','dim6','dim7','dim8','dim9','dim10']:
    print(f'  {k}: {w[k]}%')
assert abs(sum(w.values()) - 100) < 1e-6, '权重之和必须=100'
"
```

> `$SKILL_ROOT` 为本 skill 根目录（交互式流程中即包含本 `SKILL.md` 的目录，可用 `references/weight-profiles.json` 相对路径访问；CLI 子 agent 通过 `--add-dir` 注入，路径已写入 prompt）。若无法运行 Python，则直接采用下方两档权重常量。

**后端档（backend，`unknown` 回退此档）**：
dim1a=6, dim1b=6, dim2=12, dim3=8, dim4=7, dim5=5, dim6=14, dim7=12, dim8=8, dim9=12, dim10=10

**前端档（frontend / frontend-mono / nodejs）**：
dim1a=6.7, dim1b=6.7, dim2=13.4, dim3=8.9, dim4=7.8, dim5=5.6, dim6=15.5, dim7=13.4, dim8=8.9, **dim9=2**, dim10=11.1

#### 3.2 逐项加权累加

将每个维度的原始分（0–100）乘以**所选档案**的对应权重（百分比 ÷ 100），得到该维度的加权分，然后逐项累加：

```
设各维度原始分为 S(dim1a)…S(dim10)（均为 0–100 的整数），W(x) 为所选档案中维度 x 的权重百分比：

  D(x) = S(x) × W(x) / 100      （对 11 个维度逐一计算）

  综合分 = ΣD(x)
```

**输出时必须展示完整计算过程**，格式如下（禁止省略任何一行，`{W..}` 取自所选档案）：

```
使用权重档案：{profile}（REPO_TYPE = {REPO_TYPE}）

D1a  = {S_dim1a}  × {W_dim1a}%  = {D1a}
D1b  = {S_dim1b}  × {W_dim1b}%  = {D1b}
D2   = {S_dim2}   × {W_dim2}%   = {D2}
D3   = {S_dim3}   × {W_dim3}%   = {D3}
D4   = {S_dim4}   × {W_dim4}%   = {D4}
D5   = {S_dim5}   × {W_dim5}%   = {D5}
D6   = {S_dim6}   × {W_dim6}%   = {D6}
D7   = {S_dim7}   × {W_dim7}%   = {D7}
D8   = {S_dim8}   × {W_dim8}%   = {D8}
D9   = {S_dim9}   × {W_dim9}%   = {D9}
D10  = {S_dim10}  × {W_dim10}%  = {D10}
─────────────────────────────
综合分 = D1a + D1b + D2 + D3 + D4 + D5 + D6 + D7 + D8 + D9 + D10
       = {score}
```

**自验证**：所选档案 11 个权重之和必须 = 100（后端 6+6+12+8+7+5+14+12+8+12+10=100；前端 6.7+6.7+13.4+8.9+7.8+5.6+15.5+13.4+8.9+2+11.1=100）。若综合分超出 [0, 100] 范围，说明计算有误，须重新逐项核查。

#### 3.3 mono-repo 等权聚合

当 `REPO_SHAPE=mono-repo` 时，先完成全部 `N` 个成员的 3.1 和 3.2，再计算父仓分数：

```
mono-repo 综合分 = (成员1综合分 + 成员2综合分 + ... + 成员N综合分) / N
```

- 所有成员权重相等，不按代码量、目录深度或技术栈加权；结果四舍五入保留一位小数。
- mono-repo 评级按聚合后的综合分套用统一等级划分。
- 每个维度可等权计算成员原始分均值用于横向观察，但**不得**用维度均值重新推导父仓综合分；
  不同成员可能采用不同权重档案，父仓唯一有效总分是成员综合分的平均值。
- 任一成员为 `parse_error` / `schema_error` / `error` 或缺少有效分数时，整体返回
  `member_error`，列出失败成员，不得对成功子集计算部分平均分。

### 第四步：生成改进建议

按优先级分三档：
- **高优先级（必须改进）**：维度分 < 70 → 输出问题描述、影响分析、改进步骤、预期收益、工作量估算
- **中优先级（建议改进）**：维度分 70–85 → 输出改进建议
- **低优先级（可选优化）**：维度分 85–90 → 输出优化建议

### 第五步：生成改进路线图

分三阶段（高/中/低优先级），每阶段包含：预计周期、预计投入、预期收益。

### 第六步：生成评估报告（并保存）

**报告的标题规范、内容结构、学城存放位置统一定义在
[references/step6-report-template.md](references/step6-report-template.md)，
生成报告前必须先读取该文件并严格套用，禁止自由发挥。**

要点速览（完整规范见上述文件）：

`<YYYY-MM-DD> | <仓库名> | AI-Ready 评估报告 | #N | <综合得分>分`
（如 `2026-07-31 | deal-shelf | AI-Ready 评估报告 | 78.5分`）；**分数固定在末尾**，
  同仓库同日重复评估追加 `| #2`/`| #3`；版本号与评估次数不进标题。
  学城目录按**标题字典序**展示（非创建时间），故默认把日期放前面让目录按日期聚合；
  若想让同仓库历次评估相邻，用 `--order repo`（或 `AI_READY_TITLE_ORDER=repo`）
  切成 `deal-shelf | AI-Ready 评估报告 | 2026-07-31 | 78.5分`，两种形态可混存
- **结构**：固定六个一级章节——一、评估概要 / 二、得分总览 / 三、各维度详情 /
  四、总结 / 五、改进路线图 / 六、附录；章节名与顺序不得增删改
- **mono-repo 报告**：标题与概要使用父仓平均分；得分总览必须先列出全部成员分数，
  各维度详情按成员分别展开，不得只展示父仓维度均值
- **位置**：按月归档到 `【YYYY-MM】AI-Ready-Repo 打分` 目录，**禁止硬编码 parentId**

**输出报告前，询问用户保存方式**（使用 AskUserQuestion 工具）：

> "评估完成（综合分：{score}/100，{level}）。请选择报告保存方式：
> 1. 保存到学城按月归档目录（【{YYYY-MM}】AI-Ready-Repo 打分）— 需要 citadel skill 已安装
> 2. 保存为本地文件 AI-READY-REPO-REPORT.md
> 3. 跳过保存"

**保存逻辑：**

**选项 1：保存到学城（按月归档）**

```bash
# 1. 检测 citadel 是否可用
CITADEL_AVAILABLE=false
for dir in "$HOME/.claude/skills" "$HOME/.catpaw/skills/skills-market" "$HOME/.openclaw/workspace/.claude/skills"; do
  [ -d "$dir/citadel" ] && CITADEL_AVAILABLE=true && break
done

if [ "$CITADEL_AVAILABLE" != "true" ]; then
  echo "❌ citadel 未安装，无法保存到学城，流程停止。"
  echo "   安装命令：npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com"
  echo "   安装完成后重新运行评估。"
  exit 1
fi

# 2. 将完整报告内容写入临时文件（严格套用 step6-report-template.md 的结构）
REPORT_TMP="/tmp/ai-ready-report-$(date +%s).md"
# （将完整报告内容写入 $REPORT_TMP）

# 3. 解析当月归档目录（不存在则自动创建；满 480 篇自动开下一卷）
#    stdout 只输出纯 contentId，日志走 stderr，可安全用于 $(...)
PARENT_ID=$(python3 "$SKILL_ROOT/scripts/km_report_dir.py" resolve --quiet)

# 4. 生成规范标题（自动格式化分数 + 处理同仓库同日重复评估的 #N 后缀）
#    --score 传第三步算出的综合分，脚本会取一位小数并去尾零
TITLE=$(python3 "$SKILL_ROOT/scripts/km_report_dir.py" title \
          --repo-name "$REPO_NAME" --score "$TOTAL_SCORE" --parent-id "$PARENT_ID")
# → 2026-07-31 | deal-shelf | AI-Ready 评估报告 | 78.5分

# 5. 创建学城文档
oa-skills citadel createDocument --title "$TITLE" --file "$REPORT_TMP" --parentId "$PARENT_ID"
# 成功后获取返回的文档链接（格式：https://km.sankuai.com/collabpage/{pageId}）
KM_URL="<返回的学城文档链接>"
echo "✅ 报告已归档到【$(date +%Y-%m)】目录：$KM_URL"
```

> **禁止硬编码 `--parentId`**。学城单个父目录的子文档数存在硬上限（实测 500，
> 超出后 `createDocument` 返回 `code=708` 直接失败）。必须通过 `resolve`
> 动态获取当月目录，脚本会自动处理目录创建与满卷时的分卷。

**若 `resolve` 报错「归档根目录已达上限」**：说明根目录下仍有历史报告平铺占位，
需先做一次性归位（属于写操作，**先 dry-run 并经用户确认后**再执行）：

```bash
python3 "$SKILL_ROOT/scripts/km_report_dir.py" migrate            # 预演
python3 "$SKILL_ROOT/scripts/km_report_dir.py" migrate --execute  # 确认后执行
```

**选项 2：保存为本地文件**

将完整报告内容写入 `AI-READY-REPO-REPORT.md`（当前工作目录），`KM_URL=""`。
内容结构同样遵循 [references/step6-report-template.md](references/step6-report-template.md)。

**选项 3：跳过保存**

不保存任何文件，`KM_URL=""`。

---

## CLI 程序化调用（commit 评分）

除了让 Agent 进入交互式评估流程，本 Skill 还提供一个**脚本入口**，
用于对**指定 (repo, commit)** 做一次性的 11 维量化评分（不写报告、不上报、不交互）。

典型场景：评测集自动化（如 `ai-ready-caseset-builder` 的精筛阶段），
需要对每个 PR 的 `base_commit` 拿一份 AI-Ready 分。

### 入口

```bash
python3 scripts/score_commit.py \
  --repo ssh://git@git.dianpingoa.com/<group>/<repo>.git \
  --commit <hash7+> \
  --out /tmp/scoring.json \
  [--workdir ~/.cache/ai-ready-repo] \
  [--timeout 1500] \
  [--dump-raw-dir /tmp/raw]
```

### 工作机制

1. 浅克隆：`scripts/clone_at_commit.py` 三策略退化（指定 commit fetch → clone+fetch → 全克隆），
   24h 内同 (repo, commit) 复用本地目录
2. 形态识别：`scripts/monorepo.py` 读取构建清单；单仓进入根目录评分，mono-repo 只取清单
   声明的一级成员
3. 评分：单仓启动一个评分 Agent；mono-repo 为每个成员分别启动评分 Agent，成员内部不再递归拆分
4. 输出：单仓保持 v1.0；mono-repo 输出 v1.1，保留成员完整结果并给出等权平均分

### 输出 Schema

```json
{
  "_status": "ok",
  "version": "1.0",
  "repo": "...",
  "commit": "<full hash>",
  "repo_type": "backend|frontend|frontend-mono|nodejs|unknown",
  "score": 71.4,
  "level": "优秀|良好|及格|不及格",
  "dim_scores": { "dim1a": 75, "dim1b": 60, "...": "..." },
  "dim_notes":  { "dim1a": "...", "...": "..." },
  "highlights": ["..."],
  "main_gaps":  ["..."],
  "elapsed_ms": 160000
}
```

`_status` 为 `clone_error` / `parse_error` / `schema_error` / `member_error` / `error` 时表示中间环节失败，
此时 `_error` 字段含人可读原因，`_raw_text_path` 指向子 agent 原始输出便于排查。

mono-repo 成功时 `repo_type="mono-repo"`、`version="1.1"`，并新增：

```json
{
  "manifest": "pnpm-workspace.yaml",
  "member_count": 2,
  "score": 80.0,
  "members": [
    {"path": "apps/web", "repo_type": "frontend", "score": 70.0, "dim_scores": {}},
    {"path": "services/api", "repo_type": "backend", "score": 90.0, "dim_scores": {}}
  ]
}
```

顶层 `dim_scores` 是各成员原始维度分的等权均值，仅用于观察；顶层 `score` 始终直接取
成员综合分平均值。任一成员失败时 `_status="member_error"`，输出 `members` 诊断信息且不输出
不完整的 `score`。

### 与交互式流程的关系

| 维度 | 交互式（Agent 触发） | CLI（score_commit.py） |
|------|--------------------|----------------------|
| 触发方 | 人/Agent 在 IDE 内说"评估 AI-Ready" | 脚本/批处理（如 caseset-builder） |
| 工作目录 | 当前目录或远程仓库 | 自动浅克隆指定 commit |
| 第零步预检查 | ✅ | ❌（CLI 跳过） |
| 第七步上报回调 | ✅ | ❌（CLI 跳过） |
| 报告生成（学城/本地 md） | ✅（按月归档 + 统一模板） | ❌（CLI 只产 JSON） |
| 11 维评分 | ✅ | ✅（同一份维度 references） |

> 两条路径**共用** `references/dim*.md` 与 SKILL.md 第一/二/三步定义，
> 评分口径完全一致；CLI 只是把"消费方"从人换成了机器。

---

## 评估原则

1. **客观评估**：基于实际扫描结果打分，不做主观假设
2. **量化优先**：尽量使用量化指标（文件数、行数、覆盖率比例）
3. **区分骨架与内容**：空模板文件、仅有 `init` 初始化后的骨架文档，不得在业务领域建模维度获得高分
4. **认知层视角**：改进建议须说明对应哪层认知失效，帮助用户理解优先级的本质原因
5. **可执行建议**：改进建议须具体可执行，附示例和模板
6. **预期收益**：每条改进建议须标注预期分数提升
7. **工作量估算**：每条改进建议须标注时间和人力估算
8. **渐进可发现性优先**：每个维度的评分应以"AI 冷启动路径能在几跳内找到该信息"作为首要参考，而非单纯以信息是否存在于仓库中为依据。需要全仓库 grep 才能发现的信息，等同于对 AI 不可见。
9. **等效性原则**：前端工具与后端工具在评估中具有等效地位——ESLint ≈ Checkstyle；Vitest/Jest ≈ JUnit/JaCoCo；TypeScript Props 类型 ≈ Javadoc；`.cursorrules`/`.catpaw/rules/` ≈ 编码规范文档；Hook ≈ Service 层；`package.json` ≈ `pom.xml`。评分时以"功能等效"为判断依据，不因使用前端工具而扣分。

---

## 版本历史

- v1.0.0（2026-03-19）：初始版本
- v1.1.0（2026-03-25）：迁移至 MDP-Context 标准；调整权重
- v1.2.0（2026-03-25）：全面切换为中文；引入"骨架与内容"区分原则
- v1.3.0（2026-03-25）：引入六层认知模型（L1-L6）；重构维度体系
- v1.4.0（2026-03-26）：主体精简，评分细则和检查命令迁移至 references/ 子目录
- v1.5.0（2026-03-30）：L1 拆分为两个独立维度——仓库定位准确性（dim1a）和仓库导航完整性（dim1b），各 6%，总维度数升至 11
- v1.6.0（2026-03-31）：引入 AI 冷启动路径追踪（Cold Start Path Trace）作为第一步前置评估；dim1b 新增跳数深度与死链检测；dim3 以本地可理解性测试（LCT）替代 grep 覆盖率评分；新增评估原则第 8 条：渐进可发现性优先
- v1.6.1（2026-03-31）：修复综合分计算幻觉问题——改为强制展示 11 个中间值（D1–D11）并逐项累加，禁止跳步估算，新增权重自验证规则
- v1.7.0（2026-03-31）：新增第七步评分数据回收上报，上报逻辑定义于 references/step7-score-callback.md；支持通过环境变量 AI_READY_MIS_ID / AI_READY_CALLBACK_URL 配置
- v2.0.0（2026-03-31）：大版本迭代——新增第零步依赖预检查（references/step0-precheck.md）；新增远程仓库模式，支持 dev.sankuai.com 链接通过 code-repo-search 拉取评估（references/step7-remote-mode.md）；第七步改为交互式鉴权上报，通过 meituan-sso 获取 token 填入 callback_token；新增远程模式触发条件
- v2.0.1（2026-03-31）：第七步改为必须执行（不可跳过），默认上报数据，仅用户明确回复 n 时跳过
- v2.1.0（2026-03-31）：第七步上报改用 Supabase REST API（JWT + anon key），移除 mtsso-skills-official 依赖；step0-precheck.md 同步移除 mtsso 检测项
- v2.2.0（2026-03-31）：调整上报策略
- v2.3.0（2026-03-31）：step0-precheck 新增 playwright/chromium 检测和 citadel 强制安装引导；第六步报告保存改为三选一（学城/本地/跳过），优先通过 citadel 保存到学城；上报 payload 新增 km_url 字段
- v2.4.0（2026-04-01）：修复三处上报 bug——①step0-precheck playwright 检测命令从 `import playwright` 改为 `from playwright.sync_api import sync_playwright`，修复已安装时误报未安装的问题；②step7 第一步依赖检测从 mt-sso-requests 改为 playwright（与实际执行一致）；③step7 新增强制约束：第一步至第四步必须在同一个 Bash 工具调用中完成，禁止分块执行，避免变量丢失导致重复弹出浏览器登录
- v2.5.0（2026-04-01）：step0-precheck 新增独立安装引导脚本 `scripts/install_deps.py`，检测到依赖缺失时交互式引导用户确认安装（支持 Y/n 确认、安装后重新检测、非 TTY 环境自动跳过），替代原来仅打印提示的行为；脚本支持独立运行和单项指定，适配任意 agent 和用户直接调用
- v3.0.0（2026-04-02）：(鸣谢dingxiaoxue02同学) 新增多端支持，采用"单一评分框架 + 技术栈感知执行层"架构；第一步新增 REPO_TYPE 自动检测（backend/frontend/frontend-mono/nodejs/unknown）；新增前端冷启动路径追踪；11 个 dim 文件全部改造为"通用评估标准 + 技术栈执行指南表格 + 结构性差异说明（按需）"结构，替代双分支设计；新增评估原则第 9 条：等效性原则；第七步上报新增 repo_type 字段；报告模板新增仓库类型字段
- v3.1.0（2026-04-12）：重构维度9（测试验证）——移除 JaCoCo/GitHub Actions 硬依赖，聚焦单测覆盖率、CI/流水线质量门禁、本地一键自验证能力，补充覆盖率阈值配置检查，CI 平台无关性说明（适配美团内部流水线）；维度8（AI 协作友好度）新增 MCP Server 集成检查项（参考 agentrc Level 4 AI Tooling）；同步更新 ai-ready-fordlc
- v3.2.0（2026-04-17）：为高方差维度引入量化锚点——dim6（业务领域建模）新增"充实/内容极少/隐含规则已显性化"量化定义表格及高/中/低三档评分锚点示例；dim7（编码规范遵守度）新增"一条有效禁止规则"三项判断标准及锚点示例；dim3（代码可读性）LCT 新增后端 Java + 前端 TS 高/中/低分典型样本，替代纯主观判断；同步更新 ai-ready-fordlc
- v3.3.0（2026-05-19）：新增 CLI 程序化调用入口 `scripts/score_commit.py`（commit 评分）——浅克隆指定 (repo, commit) + 起 `mc --code -p --output-format json --json-schema` 子 agent + structured_output 强约束 JSON 输出；与交互式流程共用 references/dim*.md，评分口径一致；新增 `scripts/clone_at_commit.py` 三策略退化（指定 commit fetch → clone+fetch → 全克隆）+ 24h 缓存复用；服务于 ai-ready-caseset-builder 精筛阶段对 PR.base_commit 的程序化评分需求
- v3.4.0（2026-06-25）：权重配置化 + 按仓库类型分档——解决前端仓库因普遍缺少单测被 dim9（测试验证，12%）系统性拉低分数的问题。新增 `references/weight-profiles.json` 作为权重唯一真相源（backend / frontend 两档，含 repo_type→profile 映射）；前端档 dim9 从 12% 降权至 2%（降权而非归零，仅保留对优秀前端测试投入的微弱区分度），腾出的 10% 按比例（×98/88）摊回其余 10 维，两档权重之和均严格 = 100；交互式 SKILL.md 第三步改为先按 REPO_TYPE 选档再逐项加权累加，CLI `score_commit.py` 同步从配置文件动态注入权重到子 agent prompt，两条路径口径一致
- v3.5.0（2026-07-29）：`score_commit.py` 默认评分模型由 `claude-sonnet-4-7` 改为国产模型候选链 `glm-5.2 → LongCat-2.0`，并新增**候选链自动回退**——解决部分 runtime（CatPaw / Multica 定制版）网关不支持 claude-* 系列、报 400「不支持的模型类型」导致整批仓库评分静默降级/跳过的问题。`--model` 现支持逗号分隔候选链（如 `glm-5.2,LongCat-2.0,claude-sonnet-4-7`），某候选遇「不支持/超时/400」自动切下一个，全部失败才判定评分失败；结果 JSON 新增 `_model` 字段记录实际生效模型；`--list-models` 标注默认候选链顺序
- v3.6.0（2026-07-31）：学城归档能力重构——解决归档根目录 `2756859002` 已打满学城子文档硬上限（实测 500，超出后 `createDocument` 返回 `code=708`，**新报告完全无法保存**）的线上故障。①归档结构由「一层平铺」改为「按月分目录」`【YYYY-MM】AI-Ready-Repo 打分`，单月满 480 篇自动开「· 卷2」，根目录每年仅新增 12~15 个节点、永不触顶；②新增 `scripts/km_report_dir.py`（`audit` 盘点容量与标题规范度 / `resolve` 解析并自动创建当月目录 / `title` 生成规范标题并处理同日重名 / `migrate` 把历史平铺文档按创建月份归位，默认 dry-run），stdout 仅输出纯数据、日志走 stderr，可直接用于 `$(...)`；③新增 `references/step6-report-template.md` 作为报告归档规范唯一真相源，统一标题格式 `<仓库名> AI-Ready 评估报告 YYYY-MM-DD[ #N] · <综合得分>分`（同日重复评估追加 `#N`；**综合分固定置于标题末尾**，最多一位小数并去尾零，可在目录列表直接横向对比得分；分数段整体可选以兼容已归档的无分数旧标题，同日去重只比对仓库名+日期而不看分数；版本号/评估次数仍禁止进标题），以及六个固定一级章节（概要/总览/详情/总结/路线图/附录），治理此前 500 篇中 83 篇标题不规范、格式各异无法机器解析的问题；**实测确认学城目录按标题字典序展示而非创建时间**，故排序完全由标题开头字段决定，`title` 因此支持 `--order repo|date` 双形态（环境变量 `AI_READY_TITLE_ORDER` 可设团队默认）：`date`（默认）把日期前置让目录按日期聚合，打开月度目录一眼看到最近评了哪些；`repo` 则让同仓库历次评估相邻便于看分数趋势（三个月真实数据中同仓库复评占比达 28%~37%）；两种形态字段一致、可混存同一目录，解析与同日去重均跨形态生效，切换无需改名历史文档；标题各段用 `|` 分隔，解析器同时兼容旧格式空格分隔；④SKILL.md 第六步与 step7-remote-mode.md 改为动态 `resolve` 获取 parentId，**禁止硬编码**；⑤健壮性：`migrate` 支持「引导式建目录」破解「根目录满→建不了目录→没法迁移」死锁（先在个人空间建目录、迁移腾位后自动 `moveDocument` 挂回），中断后重跑会复用遗留目录而非重复创建，SSO token 抖动/网络超时自动退避重试（3s→6s）；修复 citadel 写操作把结果输出到 stderr 导致新建目录 contentId 解析失败的问题。**已实机验证**：根目录 500→5（释放 495 容量），500 篇历史文档 100% 归位到 3 个月度目录（2026-05: 92 / 2026-06: 353 / 2026-07: 55），零失败，报告写入链路恢复正常
- v3.7.0（2026-09-01）：新增 mono-repo 分仓评分。通过 `scripts/monorepo.py` 从 pnpm/npm workspace、Maven modules 或 Gradle include 确定性发现一级成员；根目录不评分，每个成员独立执行 11 维评分并保留完整结果，父仓总分取全部成员综合分的等权平均值。任一成员失败时返回 `member_error`，禁止计算部分平均分；交互式报告与 `score_commit.py` v1.1 输出同步支持成员明细和父仓平均分。
