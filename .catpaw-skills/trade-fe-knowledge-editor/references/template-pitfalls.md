# 模板：spec/pitfalls/&lt;group&gt;.md（可选）

> 技术栈专属踩坑建议走 `spec/pitfalls/{mrn,max,duo,miniprogram}.md`。
> 业务组专属踩坑（跨技术栈）才落到 `spec/pitfalls/<group>.md`。

## Frontmatter

```yaml
---
category: pitfall
description: <group> 研发组业务场景专属踩坑记录--现象、根因、解决方案、关联 PR。
domain: <group>
related:
  - ./coding.md
  - ../coding-standards/<group>.md
tags:
  - 踩坑
  - <group>
  - 现象
  - 根因
  - 解决方案
last_updated: <YYYY-MM-DD>
---
```

## 每条踩坑的统一格式

```markdown
## <简明标题>

**现象**：
<!-- 问题表现、报错信息 -->

**根因**：
<!-- 根本原因分析 -->

**解决方案**：
\`\`\`typescript
// 错误写法
...

// 正确写法
...
\`\`\`

**参考**：
- PR: <url>
- 相关文档: <path>
```
