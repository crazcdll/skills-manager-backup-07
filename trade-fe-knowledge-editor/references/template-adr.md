# 模板：spec/adr/&lt;group&gt;.md

> ADR 可按单组聚合在一个 `<group>.md` 中（每个 ADR 是一个 H2 块），也可拆分为 `spec/adr/<group>/ADR-00N-xxx.md`。本 skill 默认聚合模式，作者可按 ADR 数量和可读性自行决定何时拆分为子文件。

## Frontmatter

```yaml
---
constraint: hard
category: adr
description: <group> 研发组架构决策记录汇总--技术选型、架构升级、接口协议等重大决策。
domain: <group>
related:
  - ../coding-standards/<group>.md
tags:
  - ADR
  - 架构决策
  - 技术选型
  - <group>
  - 方案
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 架构决策记录（ADR）`
2. `## 索引`（表格：编号 / 标题 / 状态 / 日期）
3. `## ADR-001：<标题>`（单条 ADR）
   - H3：状态（已采纳 / 废弃 / 讨论中）
   - H3：背景
   - H3：决策
   - H3：后果
   - H3：备选方案
4. `## ADR-002：...`

## 单条 ADR 最小内容

```markdown
## ADR-00N：<标题>

**状态**：已采纳 | 已废弃 | 讨论中
**日期**：YYYY-MM-DD
**决策者**：<mis-id>

### 背景
<!-- 为什么需要做这个决策 -->

### 决策
<!-- 我们决定... -->

### 后果
**正面**：
- ...
**负面/权衡**：
- ...

### 备选方案
<!-- 考虑过但未采纳的方案 -->
```
