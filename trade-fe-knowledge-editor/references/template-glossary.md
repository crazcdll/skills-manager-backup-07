# 模板：context-docs/glossary/&lt;group&gt;.md

## Frontmatter

```yaml
---
category: glossary
description: <group> 研发组专属术语表，包含业务术语、易混词辨析、中英文映射，供 AI 解析业务上下文。
domain: <group>
related:
  - ../overviews/<group>.md
tags:
  - 术语
  - <group>
  - 业务词汇
  - 中英文映射
  - 易混词
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 术语表`
2. `## 业务术语`（表格：术语 / 定义 / 英文/代码标识 / 备注）
3. `## 易混词辨析`（对比：A vs B，说明差异）
4. `## 状态/枚举关键词映射`（指向 `spec/domain-models/<group>/enums.md`）
5. `## 缩写与代号`（表格：缩写 / 全称 / 场景）

## 占位骨架

```markdown
---
category: glossary
description: <group> 研发组专属术语表。
domain: <group>
related:
  - ../overviews/<group>.md
tags:
  - 术语
  - <group>
  - 业务词汇
  - 中英文映射
  - 易混词
last_updated: <YYYY-MM-DD>
---

# <业务组中文名> 术语表

## 业务术语

| 术语 | 定义 | 英文/代码标识 | 备注 |
|------|------|--------------|------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

## 易混词辨析

### <!-- TODO: 术语A --> vs <!-- TODO: 术语B -->

- **<术语A>**：<!-- TODO -->
- **<术语B>**：<!-- TODO -->
- **差异**：<!-- TODO -->

## 状态/枚举关键词映射

详见 [spec/domain-models/<group>/enums.md](../../spec/domain-models/<group>/enums.md)。

| 中文 | 枚举值 | 代码标识 |
|------|-------|---------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

## 缩写与代号

| 缩写 | 全称 | 场景 |
|------|------|------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |
```
