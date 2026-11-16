---
name: ai-quality-evalset-builder
description: AI-CR 评测集自动化圈选工具。完整支持 L1 评测集生产流水线：①从多维表格拉取全量真实 PR 反馈 ②按四维打分粗筛出候选样本 ③产出「人工标注指引文档」写入学城（严格对齐精筛版格式）④接收木子标注完的精选评测集文档 ⑤按标准格式（input.json + ground_truth.json）导出写入 Git 仓库，供 ai-cr-evaluator 离线评测 pipeline 使用。另支持独立的外部评测集（Martian Benchmark）桥接通道：从开源 benchmark 仓库提取 Java 子集，转换为标准格式写入 Git，与内部评测集完全隔离。触发词：评测集、圈选评测集、筛选评测样本、构建评测集、eval dataset、L1 回溯、evalset、产出标注指引、生成评测文档、导出评测集、写入git、生成json格式、martian、外部评测集、benchmark、bridge。

metadata:
  skillhub.creator: "mengmuzi"
  skillhub.updater: "mengmuzi"
  skillhub.version: "V4"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "61455"
  skillhub.high_sensitive: "false"
---

# AI-CR 评测集生产流水线（ai-quality-evalset-builder）

## 概述

**全流程四个阶段，第三阶段需要人工介入：**

```
[阶段一] 拉取 + 粗筛          → candidates.json（带分数）
     ↓
[阶段二] 产出「标注指引文档」   → 学城文档（格式对齐精筛版）
     ↓
[阶段三] 🧑 木子人工标注        ← 离线，标注完后给 contentId
     ↓
[阶段四] 接收 + 导出写入 Git   → eval/cases/EVAL-NNN/{input,ground_truth}.json
```

---

## 前置依赖检查

```bash
which oa-skills   # citadel + citadel-database
which code-cli    # Code 平台 PR 评论拉取
python3 --version # >= 3.8
```

依赖缺失时重新读取对应 SKILL.md 并安装。

---

## 阶段一：拉取 + 粗筛

### Step 1：从多维表格拉取全量 CR 记录

调用 citadel-database 读取 AI-CR 记录表（全量，不限时间）：

```bash
oa-skills citadel-database query \
  --content-id 2751017775 \
  --table-id 2751197605 \
  --page-size 500
```

**提取字段：**

| 字段 | 说明 |
|------|------|
| 日期 | PR merge 日期 |
| PR链接 | dev.sankuai.com PR URL |
| 仓库名 | repo slug（`org/repo` 格式） |
| 标题 | PR 标题 |
| 提交人 | submitter mis |
| 组织 | 四级部门 |
| Review结论 | ✅/💚/🟠/🔴 |
| P0数/P1数/P2数 | 各级检出数 |
| 学城文档URL | AI-CR 详情文档链接 |
| 备注 | 自由文本 |

保存为 `~/.openclaw/workspace/eval-dataset/raw_records.json`。

---

### Step 2：粗筛 + 四维打分

运行 `scripts/harvest.py`：

```bash
python3 scripts/harvest.py \
  --input ~/.openclaw/workspace/eval-dataset/raw_records.json \
  --output ~/.openclaw/workspace/eval-dataset/candidates.json
```

**硬过滤（不满足直接排除）：**
- PR 链接包含 `dev.sankuai.com`（有效链接）
- P0+P1+P2 检出总数 ≥ 1（有检出项才有标注价值）
- 有学城 CR 文档 URL（需要解析检出详情）
- 同一 PR URL 去重（保留最高分）

⚠️ **不全量过滤**：打分低的也保留，只是排序靠后（用于补充稀缺类别覆盖）。

**四维打分公式：**

```
Score = 0.30×S_severity + 0.30×S_rarity + 0.25×S_context + 0.15×S_diversity

S_severity：P0×10 + P1×6 + P2×3 + P3×1，归一化到 0~100
S_rarity：样本含最稀缺类别的稀缺度×100
          C5(安全)=97.5 > C3(资源)=96.3 > C6(性能)=87.5 > C2(并发)=85 > C1=50 > C4=40 > C7=20
S_context：L1 only=20，has L2=60，has L3=100
           （判断标准：L3=有ONES需求或跨仓库引用；L2=有同仓库反查；L1=只看diff）
S_diversity：仓库频次惩罚
             独占=100，2次=80，3次=50，4次=30，≥5次=10
```

**四选标记加分（Step 3 拉取评论后叠加）：**
- 有 `✅已采纳` 标记 → +50（TP 有明确确认）
- 有 `❌误报` 标记 → +25（FP 样本价值高）
- 有 `⚠️规则太严` → confidence = 0.4（边缘样本，单独标记）
- 无标记 → confidence = 0.5（ai_detected 基线）

---

### Step 3：拉取 PR 评论中的四选标记

对 Step 2 过滤后的候选，逐条拉取 Code 平台评论：

```bash
code-cli pr-comments --repo <repo> --pr-id <pr_id>
```

解析 AI-CR bot 发出的四选标记，叠加到打分上（见 Step 2 加分规则）。
更新后的候选列表覆盖写回 `candidates.json`。

---

### Step 4：解析学城 CR 文档，提取检出项

对 Score ≥ 40 的候选（或 Score < 40 但属于稀缺类别 C3/C5 的），读取学城 CR 文档：

```bash
oa-skills citadel getSimpleMarkdown --contentId <cr_doc_contentId>
```

**每个检出项提取：**

| 字段 | 来源 |
|------|------|
| `file` | 代码块路径或文档标题 |
| `severity` | P0/P1/P2/P3 |
| `defect_class` | 基于关键词自动分类（C1~C7，规则见下） |
| `context_layer` | 根据文档是否包含跨仓库反查内容推断（L1/L2/L3） |
| `description` | 检出项正文，截断到 200 字 |
| `key_concepts` | 自动提取（Java类名+方法名+异常名+中文关键词，取前5个） |
| `line_range` | 从代码块行号推断，无法确定则 null |

**缺陷类别自动分类规则（关键词匹配）：**

| 代码 | 类别 | 匹配关键词 |
|------|------|-----------|
| C1 | 逻辑缺陷 | NPE、空指针、逻辑反转、中间态、边界、硬编码、死代码 |
| C2 | 并发安全 | 并发、线程安全、竞态、锁、volatile、double-check、同步 |
| C3 | 资源泄露 | 资源未释放、连接泄露、内存泄露、默认true、默认false、开关 |
| C4 | 异常处理 | 吞异常、事务回滚、浮点精度、catch Exception、资损 |
| C5 | 安全漏洞 | 越权、SQL注入、权限校验、敏感数据、XSS、SSRF |
| C6 | 性能风险 | N+1、全表扫描、无限流、无分页、批量、大 key |
| C7 | 规范问题 | 拼写、测试缺失、注释不符、幂等、日志 |

单个 PR 最多取 5 个检出项（防止大 PR 主导）。

---

## 阶段二：产出标注指引文档

### Step 5：生成候选评测集文档（写入学城）

**文档格式严格对齐「精筛版」参考文档（contentId=2761845502）**。

文档标题格式：`评测集圈选报告及数据集明细 YYYY-MM-DD（粗筛版，待标注）`

文档写入学城：

```bash
oa-skills citadel createDocument \
  --title "评测集圈选报告及数据集明细 $(date +%Y-%m-%d)（粗筛版，待标注）" \
  --parent-id <父文档 contentId>
```

**文档内容结构（完全对齐 2761845502 格式）：**

#### 5.1 文档头部

```
# 评测集圈选报告及数据集明细 YYYY-MM-DD（粗筛版，待标注）

## 圈选说明

- **数据来源**：AI-CR 多维表格（tableId=2751197605）全量记录，共 NNN 条
- **粗筛时间**：YYYY-MM-DD
- **候选总数**：NNN 条（Score ≥ 40 或属于 C3/C5 稀缺类别）
- **覆盖仓库**：NNN 个
- **标注说明**：请在每条样本的「人工标注」列填写 ✅（确认）或 ❌（误报）；
               如需调整 verdict 或 findings，直接修改对应行；
               标注完成后将本文档 contentId 告知 MUZI。
```

#### 5.2 总览汇总表

与精筛版格式完全一致的表格：

| 列名 | 说明 |
|------|------|
| # | 序号（EVAL-NNN） |
| 仓库 | org/repo |
| PR | PR#编号（可点击） |
| 标题 | PR 标题（截断50字） |
| 结论 | 🟠需修复 等 |
| P0/P1/P2 | 各级检出数 |
| Score | 四维打分 |
| Confidence | 初始置信度 |
| 人工标注 | **空列，木子填写 ✅/❌/修改** |
| 备注 | 自动分析备注 |

#### 5.3 每条样本的详情 Section

严格对齐精筛版的 `##### EVAL-NNN: <标题> (PR#NNN)` 格式：

```markdown
##### EVAL-001: <PR标题> (PR#NNN)

**仓库**: `org/repo`
**PR 链接**: [PR#NNN](https://dev.sankuai.com/...)
**CR 文档**: [学城链接](https://km.sankuai.com/...)
**提交人**: mis
**merge 时间**: YYYY-MM-DD
**Score**: XX（四维：severity=XX rarity=XX context=XX diversity=XX）
**Confidence**: 0.7（ai_detected，待标注）

| # | Severity | Defect Class | Context Layer | Expected Finding | 人工标注 |
|---|----------|--------------|---------------|-----------------|---------|
| 1 | P1 | C1 | L1 | `GuaranteeService.java` — getPlanId() 返回 String 传非数字会 NPE | 待标注 |
| 2 | P2 | C4 | L1 | `OrderDTO.java` — catch Exception 吞掉了业务异常 | 待标注 |

> **标注说明**：
> - 人工标注列：✅ = 确认是真实问题 / ❌ = 误报
> - 如 verdict 有误请直接修改
> - 如 findings 描述不准确请直接编辑
```

**输出统计：**
生成文档后打印：
```
✅ 标注指引文档已写入学城
   contentId: XXXXXXXXXX
   链接: https://km.sankuai.com/collabpage/XXXXXXXXXX
   候选样本数: NNN
   覆盖 C1~C7: C1(N) C2(N) C3(N) C4(N) C5(N) C6(N) C7(N)
   覆盖仓库数: NNN
   
请木子完成人工标注后，将 contentId 告知 MUZI。
```

---

## 阶段三：人工标注（离线）

此阶段由木子独立完成，MUZI 等待。

木子完成标注后，向 MUZI 提供：**学城文档 contentId**（即精选评测集文档）。

---

## 阶段四：接收精选评测集 → 导出写入 Git

### Step 6：读取标注完的学城文档

收到木子提供的 contentId 后，读取文档：

```bash
oa-skills citadel getSimpleMarkdown --contentId <标注后的contentId>
```

解析逻辑：
- 读取总览表，筛出人工标注列 = `✅` 的行
- 对每行进入对应 EVAL 详情 Section，读取 findings 表格
- 根据标注结果更新 confidence：
  - 全部 finding 都有 `✅` → `human_verified`，confidence = 0.9
  - 有 `❌` → 标记为 FP 样本，`gt_source = fp_verified`，confidence = 0.95
  - 仍有「待标注」→ `ai_detected`，confidence = 0.7（部分标注）
- 读取修改后的 verdict（以文档为准，AI 推断值仅做 fallback）

---

### Step 7：标准化格式导出写入 Git

将解析结果写入 Git 仓库标准目录结构。

**触发条件：** 用户说"导出到 git"、"写入仓库"、"生成 JSON"

#### 7.1 数据来源优先级

1. **Step 6 读取的标注文档**（优先，有人工确认）
2. **本地 samples.json**（Step 2 输出，仅做 fallback）
3. **直接指定 contentId**：`--km-doc <contentId>`（支持任意格式对齐的学城文档）

#### 7.2 仓库目录结构

```
mcp/ai-cr/
└── eval/
    ├── cases/
    │   ├── EVAL-001/
    │   │   ├── input.json          # PR 元信息（diff 固定 null）
    │   │   └── ground_truth.json   # GT findings + key_concepts
    │   ├── EVAL-002/
    │   │   ├── input.json
    │   │   └── ground_truth.json
    │   └── ...
    ├── schema/
    │   ├── input.schema.json
    │   └── ground_truth.schema.json
    ├── results/                    # CI 跑完后自动写入，不手动维护
    └── README.md
```

#### 7.3 input.json 格式

```json
{
  "$schema": "../../schema/input.schema.json",
  "eval_id": "EVAL-001",
  "title": "价保-手动删除保障书接口",
  "repo": "nib/nib-price-operation",
  "pr_number": 172,
  "pr_url": "https://dev.sankuai.com/code/repo-detail/nib/nib-price-operation/pr/172/diff",
  "cr_doc_url": "https://km.sankuai.com/collabpage/2750768387",
  "diff": null
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `eval_id` | string | ✅ | 唯一标识，格式 `EVAL-NNN`（三位补零） |
| `title` | string | ✅ | PR 标题 |
| `repo` | string | ✅ | 仓库路径，`{org}/{repo}` |
| `pr_number` | integer | ✅ | PR 编号（纯数字） |
| `pr_url` | string | ✅ | 完整 PR URL |
| `cr_doc_url` | string\|null | ⬜ | 对应的学城 CR 文档 URL |
| `diff` | null | ⬜ | **固定 null**，评测时动态从 Code 平台拉取 |

#### 7.4 ground_truth.json 格式

```json
{
  "$schema": "../../schema/ground_truth.schema.json",
  "eval_id": "EVAL-001",
  "verdict": "🟠需修复",
  "gt_source": "human_verified",
  "annotator": "mengmuzi",
  "annotated_at": "2026-05-13",
  "confidence": 0.9,
  "findings": [
    {
      "id": "F001",
      "severity": "P0",
      "defect_class": "C1",
      "context_layer": "L1",
      "file": "GuaranteeDeleteResultDTO.java",
      "line_range": null,
      "description": "getPlanId() 返回 String，传入非数字字符串抛 NumberFormatException；null 时 NPE。notEmpty 只保证非空。",
      "key_concepts": ["getPlanId", "NumberFormatException", "notEmpty", "NPE"]
    }
  ],
  "expected_absent": []
}
```

**findings 关键字段：**

| 字段 | 说明 |
|------|------|
| `severity` | P0/P1/P2/P3 |
| `defect_class` | C1~C7（见缺陷分类表） |
| `context_layer` | L1/L2/L3 |
| `key_concepts` | **语义比对锚点**，2~6个；AI命中 ≥2 个 = TP |
| `expected_absent` | 已知 clean 点；AI 误报这些 = FP |

**confidence 对照：**

| gt_source | confidence | 含义 |
|-----------|-----------|------|
| `human_verified` | 0.9 | 木子确认为真实问题 |
| `fp_verified` | 0.95 | 木子确认为误报（FP 样本） |
| `ai_detected` | 0.7 | 仅 AI 检出，未人工确认 |
| `coe_regression` | 1.0 | 来自 COE 历史故障，100% 确定 |

#### 7.5 执行命令（在 CatDesk 中运行）

**仓库信息：**
- 本地路径：`/Users/mengmuzi/IdeaProjects/ai-cr`
- 远程地址：`ssh://git@git.sankuai.com/mcp/ai-cr.git`
- 主分支：`master`

```bash
cd /Users/mengmuzi/IdeaProjects/ai-cr

# 切出新分支（每次写入评测集切独立分支）
git checkout master && git pull
git checkout -b feat/evalset-l1-$(date +%Y%m%d)

# 从标注后的学城文档导出
python3 ~/.openclaw/workspace/skills/ai-quality-evalset-builder/scripts/export_to_git.py \
  --km-doc <标注后的contentId> \
  --output-dir eval/cases \
  --create-schema \
  --create-readme

# 验证生成的文件
ls eval/cases/ | head -20
cat eval/cases/EVAL-001/input.json
cat eval/cases/EVAL-001/ground_truth.json

# 提交推送
git add eval/
git commit -m "feat(eval): add L1 evalset EVAL-001~NNN [$(date +%Y-%m-%d)] human_verified"
git push -u origin feat/evalset-l1-$(date +%Y%m%d)

# 在 Code 平台提 PR：https://dev.sankuai.com/code/repo-detail/mcp/ai-cr/pr/create
```

---

## 缺陷分类表

| 代码 | 类别 | 典型关键词 |
|------|------|-----------|
| C1 | 逻辑缺陷 | NPE、逻辑反转、空指针、边界条件、中间态 |
| C2 | 并发安全 | 并发修改、线程安全、竞态条件、double-check |
| C3 | 资源泄露 | 资源未释放、连接泄露、内存泄露、默认值开关 |
| C4 | 异常处理 | catch Exception、吞异常、事务回滚、浮点精度 |
| C5 | 安全漏洞 | SQL注入、越权访问、权限校验、敏感数据 |
| C6 | 性能风险 | N+1查询、全表扫描、无限流控制、无分页保护 |
| C7 | 规范问题 | 拼写错误、测试缺失、注释不符、幂等缺失 |

---

## 子命令速查

| 用户说 | 执行范围 | 说明 |
|--------|---------|------|
| `全量跑` / `粗筛` / `生成标注文档` | 阶段一 + 阶段二（Step 1~5） | 首次构建，产出学城标注指引文档 |
| `增量更新` | Step 1~5，只处理新增记录 | 周度增量更新候选集 |
| `接收标注` / `木子给了 contentId` | 阶段四 Step 6 | 读取标注结果，准备导出 |
| `导出到 git` / `写入仓库` | 阶段四 Step 7 | 生成 JSON 写入 Git 仓库 |
| `覆盖检查` | 只分析 candidates.json 覆盖矩阵 | 检查 C1~C7 / L1~L3 均衡度 |
| `单 PR 验证 <url>` | Step 3~4 单条 | 手动加入候选 |

---

## 关键约束

1. **只选 merged PR**：未合并不纳入
2. **同一 PR URL 去重**：保留最高分
3. **不全量过滤**：Score 低的样本也保留，用于补充稀缺类别（C3/C5）覆盖
4. **单 PR 最多 5 个检出项**：防止大 PR 主导
5. **diff 不存 Git 仓库**：input.json 的 diff 字段固定 null，评测时动态拉取
6. **标注文档格式对齐 contentId=2761845502**：总览表结构 + EVAL Section 格式必须严格一致

---

## 本地文件结构

```
~/.openclaw/workspace/eval-dataset/
├── raw_records.json      # Step 1 全量 CR 记录
├── candidates.json       # Step 2~3 过滤打分后候选
└── run-log.md            # 执行统计日志
```

---
---

# 外部评测集通道：Martian Benchmark Bridge（独立路径）

> ⚠️ **完全独立**：本通道与上述阶段一~四的内部评测集流水线互不影响。
> 使用独立前缀 `EVAL-MRT-`，独立脚本 `bridge_martian.py`，独立子命令触发。

## 概述

将 [Martian Code Review Benchmark](https://github.com/withmartian/code-review-benchmark) 的 Java 子集（Keycloak 项目，10 条 PR）转换为 AI-CR 标准评测格式，写入 Git 仓库 `eval/cases/EVAL-MRT-*`。

**数据流：**
```
[GitHub] Martian Benchmark 仓库
     ↓ git clone
[本地] /tmp/martian-bench/offline/data/
     ↓ bridge_martian.py（筛选 Java + 转换格式 + 可选拉取 diff）
[Git 仓库] mcp/ai-cr/eval/cases/EVAL-MRT-001 ~ EVAL-MRT-010
```

## 前置依赖

```bash
git --version      # clone martian benchmark 仓库
python3 --version  # >= 3.8
# 可选：GitHub Personal Access Token（提升 diff 拉取 rate limit）
```

## 执行步骤

### Step M1：Clone Martian Benchmark 仓库

```bash
git clone https://github.com/withmartian/code-review-benchmark /tmp/martian-bench
```

### Step M2：运行 Bridge 脚本（只取 Java/Keycloak）

```bash
# 基础转换（diff 内嵌）
python3 scripts/bridge_martian.py \
  --input /tmp/martian-bench/offline/data \
  --output-dir <git-repo>/eval/cases \
  --language java \
  --fetch-diff \
  --github-token $GH_TOKEN

# 不拉取 diff（评测时 Evaluator 从 GitHub 实时拉）
python3 scripts/bridge_martian.py \
  --input /tmp/martian-bench/offline/data \
  --output-dir <git-repo>/eval/cases \
  --language java
```

**参数说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | 必填 | Martian benchmark 数据路径（文件或目录） |
| `--output-dir` | 必填 | 输出目录（通常为 `eval/cases/`） |
| `--language` | `java` | 筛选语言（java/python/go/typescript/ruby） |
| `--fetch-diff` | false | 从 GitHub API 预拉取 diff 写入 input.json |
| `--github-token` | 无 | GitHub PAT（避免 rate limit） |
| `--limit` | 无 | 最多转换 N 条 |
| `--start-index` | 1 | EVAL-MRT 起始编号 |
| `--dry-run` | false | 只打印不写文件 |

### Step M3：验证 + 提交到 Git

```bash
cd <git-repo>

# 验证生成的文件
ls eval/cases/EVAL-MRT-*/
cat eval/cases/EVAL-MRT-001/input.json | python3 -m json.tool
cat eval/cases/EVAL-MRT-001/ground_truth.json | python3 -m json.tool

# 提交
git checkout -b feat/evalset-martian-java-$(date +%Y%m%d)
git add eval/cases/EVAL-MRT-*
git commit -m "feat(eval): add Martian benchmark Java subset (Keycloak, 10 PRs)"
git push -u origin feat/evalset-martian-java-$(date +%Y%m%d)
```

## 格式说明

### input.json（Martian 专属字段）

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | `"external"` | 标识为外部数据集（Evaluator 据此走降级路径） |
| `dataset` | `"martian"` | 数据集名称 |
| `dataset_id` | string | Martian 原始 PR ID（如 `keycloak-12345`） |
| `language` | `"java"` | 编程语言 |
| `project` | `"keycloak"` | OSS 项目名 |
| `diff` | string\|null | 预拉取的 unified diff（或 null 由 Evaluator 运行时拉） |

### ground_truth.json

与内部评测集格式完全一致，额外字段：
- `martian_gt_id`：原始 GT comment ID，保留用于 debug

### Severity 映射

| Martian label | → AI-CR Severity |
|---------------|-----------------|
| bug / critical / high | P0 |
| medium / performance | P1 |
| low / maintainability / style | P2 |
| suggestion | P3 |

### Defect Class 映射

| Martian category | → AI-CR defect_class |
|------------------|---------------------|
| concurrency | C2 |
| resource_leak | C3 |
| exception_handling | C4 |
| security | C5 |
| performance | C6 |
| memory | C7 |
| logic / bug（默认） | C1 |

## Evaluator 兼容性

- Evaluator 看到 `source == "external"` + `dataset == "martian"` → 自动走降级路径
- 跳过：Step 1 ONES、Step 3 L2 反查（默认）、Step 3 L3 领域知识库、Step 5 CX
- 正常执行：Step 3 L1、**Step 4 四层审查（零改动）**、Step 6 语义匹配、Step 7 聚合
- 报告分区：Martian 通道独立统计，不影响内部集指标

## 与内部流水线的隔离保证

| 维度 | 内部流水线（阶段一~四） | Martian Bridge |
|------|----------------------|----------------|
| 前缀 | `EVAL-001` ~ `EVAL-NNN` | `EVAL-MRT-001` ~ `EVAL-MRT-NNN` |
| 脚本 | harvest.py / export_to_git.py | bridge_martian.py |
| 数据源 | 多维表格 + 学城标注文档 | GitHub Martian 仓库 |
| 触发词 | 粗筛 / 标注指引 / 导出 git | martian / 外部评测集 / benchmark |
| 人工标注 | 需要（阶段三） | 不需要（GT 来自 benchmark） |
| diff | null（运行时从内网拉） | 可内嵌（GitHub 预拉取） |

## 子命令速查（新增）

| 用户说 | 执行 | 说明 |
|--------|------|------|
| `跑 martian bridge` / `构建 martian 评测集` | Step M1~M3 | 全流程 |
| `只转换不拉 diff` | Step M2（不加 --fetch-diff） | 快速生成，diff 留空 |
| `dry run martian` | Step M2 + --dry-run | 预览不写入 |
| `只取 keycloak` / `只取 java` | Step M2 + --language java | 默认行为 |
