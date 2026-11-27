# 统一 Issue JSON 格式（Step 3 + Step 4 共用）

> 本文件定义 AI-CR forLocal (ai-cr-forlocal) 中 Step 3（SDD 校验）和 Step 4（4-A 主 Agent + 4-B/4-C/4-D 子 Agent）共用的 Issue JSON 格式。

## 文件路径约定

| 来源 | 文件路径 |
|------|---------|
| Step 4-A 主 Agent | `/tmp/cr_issues_{repo}_main.json` |
| Step 4-B 子 Agent（按组） | `/tmp/cr_issues_{repo}_step4b_{group}.json`（group = java / db-dep / ha / sec） |
| Step 3A SDD 校验 | `/tmp/cr_issues_{repo}_sdd.json` |
| Step 4-Merge 合并后 | `/tmp/cr_issues_{repo}_step4.json` |

## 脚本

发布脚本：`scripts/publish_results_local.py`

## Issue 对象字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| severity | string | ✅ | 严重级别：P0 / P1 / P2 / P3 / confirm（待人工确认：复审疑似误报/疑似漏报转此级，人工定夺）/ dismissed（复审高置信误报，附代码证据移除，进文档附录可追溯）|
| ruleId | string | ✅ | 规则编号。4-A/主 Agent：`CR:` 前缀（P0=`CR:NullPointerException`、P1=`CR:EH-01`、P3=`CR:DB-01`、COE=`CR:R1-1`、SDD=`CR:SDD-ALIGN`）；4-B：`MT:` 前缀照抄规则文件（`MT:java-l1:JAVA-02.N001`）；4-C CU 规则：`CU:TEAM-001`，L2 规则：`L2:{规则集ID}:{稳定标识}`（如 `L2:new-be-l2:FE-01.N001`，无稳定标识时用 `L2:{规则集ID}:{文件名去.md}` 占位）；4-D：`BL:FUNC-MISS`；前端 `source=fe_review` 保留子 Skill 的原始编号，由主 Agent 转换阶段归一化为 `FE:<id>`，脚本幂等兜底；命中 L3 时使用 `FE:L3_<id>`，无 ID 时使用 `FE:L3_custom`，纯上下文可为空。 |
| file | string | ✅ | 文件路径（相对路径或绝对路径） |
| line | int | ✅ | 行号 |
| code | string | P0/P1/P2 | 问题代码片段（3-5 行含上下文） |
| description | string | P0/P1/P2 | 检出原因 / 问题描述 |
| suggestion | string | ✅ | 修复建议（含代码示例） |
| source | string | ✅ | 来源标识：`main`（4-A 主 Agent）、`{group}`（4-B 如 java/db-dep/ha/sec）、`step4c`（4-C 自定义/L2规则，V117 恢复独立路）、`step4d`（4-D 业务逻辑）、`step4d_core`/`step4d_logic`（full 档拆分路）、`sdd`（3A SDD 校验）、`review`（4-Review 复审漏报）、`fe_review`（前端委托） |
| ruleName | string | 可选 | 规则名称（如"并发处理规约"） |
| ruleFile | string | 可选 | 完整规则文件路径（如 checklists/mt-java-coding-standards/JAVA-04-并发处理规范.md） |
| rule_sources | array | FE 必填 | 原样保留全部命中来源；纯上下文填 `[]`。每项必填 `source_type`、`scope_level`、`file`；平台/fallback 必须保留 `upstream_rule_id`，L3 无明确 ID 时允许省略 |
| anomalyType | string | ✅ | 异常类型：bug/risk/smell/style；4-C 额外允许：`custom`（自定义规范）/`team`（团队约定）——4-C 独立路补充枚举，merge 去重键兼容（同位置 4-A style 与 4-C custom 不合并，各自保留） |
| summary | string | ✅ | 一句话摘要（≤50字），用于快速浏览 |
| lineType | string | ✅ | 行号类型：added（新增行）/removed（删除行）/context（上下文行）|
| fix_type | string | P0/P1 | REPLACE（替换行）/ INSERT（插入）/ DELETE（删除）/ REFACTOR（重构，需说明范围）|
| fix_range | object | P0/P1 | {"startLine": N, "endLine": N}（相对于文件，基于 diff 中的 +/- 行号推算）|
| fix_code | string | P0/P1 | 完整可粘贴的修复代码，保持原有缩进风格；REFACTOR 类型可给出关键片段 + 改造说明 |
| fix_description | string | P0/P1 | 一句话：改了什么、为什么这样改（供人工确认用）|
| risk | string | P2 可选 | 风险/后果（P2 用作"检出原因"） |
| reach_analysis | string | P0/P1 可选 | 触达分析 |
| online_scenario | string | P0/P1 可选 | 线上场景 |
| impact_scope | string | P0/P1 可选 | 影响范围 |

> 🔒 所有子 Agent 写 Issue/Verdict JSON 时，一律用文件写入工具一次性直写目标文件。禁止 `echo`/`tee`/`mv`/`python -c` 校验等终端命令——CatPaw 中子 Agent 终端命令会触发用户审批，中断并行流程。

前端编号按 ` + ` 分段；每段允许字母、数字及 `._:/-`。FE 编号以 `rule_sources` 为准，原 `ruleId` 仅保留非 FE 前缀；`mergedRuleIds` 如提供，按最终编号列表重建。发布脚本校验规则来源，失败时告警并保留问题及原始字段，不改变严重度。

## 去重规则

合并多个 Issue JSON 文件时，按 `ruleId + file + line` 三元组去重。

- 相同 ruleId + file + line → 保留第一条，丢弃后续重复项
- 不同 line 的相同 ruleId + file → 保留（同文件多行命中同一条规则是合理的）

## 4-C severity 定级（V117 独立路）

- **CU（仓库自定义规则）**：规则标注「P0」或「零容忍」→ P0；「建议」或「推荐」→ P2；未标注 → P3
- **L2（平台团队规则）**：「严重/高」→ P1；「中(建议修复)」→ P2；「低/提示」→ P3；未标注 → P3
- ruleId 前缀是采纳率分口径统计依据（CU 命中 vs L2 命中）；前端 FE 前缀只由本地主流程补齐

## 各级别必填字段

| severity | 必填字段 |
|----------|---------|
| P0 | severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType, fix_type, fix_range, fix_code, fix_description |
| P1 | severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType, fix_type, fix_range, fix_code, fix_description |
| P2 | severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType |
| P3 | severity, file, line, suggestion, source |

## 不包含的概念

本格式**不包含**以下概念：
- ❌ PR 评论（无 PR 交互）
- ❌ 大象群聊推送
- ❌ Step 4.5（已合并到 Step 4）
- ❌ prId（无 PR ID）

## 示例

```json
[
  {
    "severity": "P1",
    "ruleId": "RM-04",
    "ruleName": "线程池参数",
    "anomalyType": "risk",
    "summary": "线程池使用无界队列可能导致OOM",
    "lineType": "added",
    "file": "src/main/java/com/example/Service.java",
    "line": 42,
    "code": "new ThreadPoolExecutor(2, 2, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>())",
    "description": "LinkedBlockingQueue 无界队列，任务堆积会导致 OOM",
    "reach_analysis": "任务来源为外部请求，QPS 不可控",
    "online_scenario": "高峰期请求堆积 → OOM → 服务不可用",
    "impact_scope": "整个服务",
    "suggestion": "改用有界队列：new LinkedBlockingQueue<>(1000)",
    "fix_type": "REPLACE",
    "fix_range": {"startLine": 42, "endLine": 42},
    "fix_code": "new ThreadPoolExecutor(2, 2, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>(1000))",
    "fix_description": "无界队列改为有界队列，防止任务堆积 OOM",
    "source": "main"
  },
  {
    "severity": "P2",
    "ruleId": "NAME-04",
    "ruleName": "布尔变量命名",
    "anomalyType": "smell",
    "summary": "布尔is开头导致序列化字段名不一致",
    "lineType": "added",
    "file": "src/main/java/com/example/Model.java",
    "line": 15,
    "code": "private boolean isDeleted = false;",
    "description": "布尔变量以 is 开头，Jackson 序列化时会去掉 is 前缀",
    "risk": "前后端字段名不一致",
    "suggestion": "改为 private boolean deleted = false;",
    "source": "java"
  }
]
```
