# 模板：spec/coding-standards/&lt;group&gt;.md

## Frontmatter

```yaml
---
constraint: hard
category: coding-conventions
description: <group> 研发组编码规范--命名/组件/状态管理/请求封装/DUO 约定，生成代码时必须遵守。
domain: <group>
related:
  - ./general.md
  - ../pitfalls/<tech>.md
tags:
  - 编码规范
  - 命名
  - 组件
  - <tech-stack>
  - CR
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 编码规范`
2. `## 命名规范`
   - H3：文件命名（组件/工具/页面/类型）
   - H3：变量/常量命名
   - H3：包命名（DUO 场景 `@{ns}/{biz}-{mod}`）
3. `## 组件规范`
   - H3：MDS 组件库约定（禁用 antd/element-ui）
   - H3：DUO 组件三段式（preview/update/submit）
4. `## 状态管理规范`（Zustand / Redux 取舍）
5. `## 请求封装规范`（useRequest / fetch 禁令）
6. `## 端环境判断规范`（`'' | 'true'` 坑点）
7. `## CR Checklist`（提单前自检）
8. `## 违规示例（反例）`
