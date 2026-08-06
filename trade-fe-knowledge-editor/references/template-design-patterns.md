# 模板：context-docs/design-patterns/&lt;group&gt;.md

## Frontmatter

```yaml
---
category: design-pattern
description: <group> 研发组设计模式与最佳实践--可复用的组件/Hook/状态管理/接口封装模板，附正反例代码。
domain: <group>
related:
  - ../overviews/<group>.md
  - ../../spec/coding-standards/<group>.md
tags:
  - 设计模式
  - 最佳实践
  - 代码模板
  - <group>
  - 组件
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 设计模式与最佳实践`
2. `## 策略模式（Strategy Pattern）`（业务变体枚举场景）
3. `## 懒加载（Lazy Loading）`（预约/长列表/大弹窗）
4. `## 乐观更新（Optimistic Update）`（次卡核销等）
5. `## 反模式（Anti-Pattern）`
6. `## 代码模板索引`

## 每条模式的统一格式

```markdown
### 模式名（英文/中文）

**适用场景**：<什么情况下用>
**核心思想**：<一句话解释>
**正例**：
\`\`\`tsx
// 示例代码
\`\`\`
**反例**：
\`\`\`tsx
// 反面教材
\`\`\`
**参考**：<仓库路径或 PR 链接>
```
