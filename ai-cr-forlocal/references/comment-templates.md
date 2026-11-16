# Comment Templates — AI-CR forLocal

> 仅保留 CatPaw IDE 报告模板。不包含 PR 评论模板和大象群聊模板。

## CatPaw IDE Markdown 报告模板

```markdown
# AI-CR 本地审查报告

| 项目 | 内容 |
|------|------|
| 仓库 | {repo} |
| 分支 | {branch} |
| 审查时间 | {cr_at} |
| Skill | ai-cr-forlocal |
| 结论 | {conclusion} |
| 汇总 | P0={p0} P1={p1} P2={p2} P3={p3} |

{km_url 如果有则输出}

---

### P0 — 零容忍异常 🔴

**🔴 [P0-01] [{ruleId}] {anomalyType} — {summary}**
- **文件**：`{file}` L{line}
- **问题代码**：
```java
{code}
```
- **检出原因**：{description}
- **触达分析**：{reach_analysis}
- **线上场景**：{online_scenario}
- **影响范围**：{impact_scope}
- **修复建议**：
```java
{suggestion}
```

### P1 — 稳定性风险 🟠

**🟠 [P1-01] [{ruleId}] {anomalyType} — {summary}**
- **文件**：`{file}` L{line}
- **问题代码**：
```java
{code}
```
- **检出原因**：{description}
- **触达分析**：{reach_analysis}
- **线上场景**：{online_scenario}
- **影响范围**：{impact_scope}
- **修复建议**：
```java
{suggestion}
```

### P2 — 代码规范 🟡

**🟡 [P2-01] [{ruleId}] {summary}**
- **文件**：`{file}` L{line}
- **问题描述**：{description}
- **检出原因**：{risk}
- **规范要求**：{ruleName}
- **修复建议**：{suggestion}

### P3 — 优化建议 🔵

**🔵 [P3-01] {summary}**
- **文件**：`{file}` L{line}
- **建议**：{suggestion}

---

> 本报告由 ai-cr-forlocal 自动生成
```

### 格式说明

- 某级别无 issue 时该小节整体省略（不写「未发现」）
- 所有级别均无 issue 时写「本次审查未发现问题。」
- P0/P1 用完整七字段格式（文件/问题代码/检出原因/触达分析/线上场景/影响范围/修复建议）
- P2 用五字段格式（文件/问题描述/检出原因/规范要求/修复建议）
- P3 用两字段格式（文件/建议）

## 学城 CR 文档结构模板

> ⚠️ 以下为学城文档的固定结构，由 publish_results_local.py 自动拼装。

```markdown
# {repoName}/{branch} 本地 CR — {YYYY-MM-DD HH:mm}

## 一、CR 概述

| 项目 | 内容 |
|------|------|
| 仓库 | {repoName} |
| 操作者 | {operatorMis} |
| 分支 | {branch} |
| 审查时间 | {cr_at} |
| 审查范围 | 🟦 全量 |
| Skill 版本 | ai-cr-forlocal |

## 二、变更综述

{本次变更整体做了什么，1-2 句话概括}

## 三、Review 发现

### 规则命中摘要

- P0 零容忍：命中 {p0_count} 条
- P1 稳定性：命中 {p1_count} 条
- P2 规范：命中 {p2_count} 条
- P3 性能：命中 {p3_count} 条

{按 P0→P1→P2→P3 分组展示}

## 四、总体评价

**Review 结论**：{conclusion}
**发现汇总**：P0: {x} | P1: {x} | P2: {x} | P3: {x}

## 五、人工复审要点

{需要人工验证的事项}

## 六、附录

- Skill: ai-cr-forlocal
- 审查模式: 本地分支模式（forLocal）
```
