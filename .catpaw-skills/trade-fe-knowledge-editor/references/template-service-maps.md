# 模板：context-docs/service-maps/&lt;group&gt;.md

## Frontmatter

```yaml
---
category: service-map
description: <group> 研发组前后端工程全景--核心仓库、Bundle/AppKey、后端服务依赖、接口映射、部署信息。
domain: <group>
related:
  - ../overviews/<group>.md
  - ../page-assets/<group>/page-index.md
tags:
  - 服务地图
  - 仓库
  - 后端服务
  - 接口
  - <group>
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 服务地图`
2. `## 前端工程清单`（表格：工程名 / Code 地址 / AppKey / 技术栈 / 负责人）
3. `## 核心页面`（表格：页面 / Bundle / 仓库 / 日均 PV / 监控链接）
4. `## 后端服务依赖`（表格：服务名 / AppKey / 职责 / 接口前缀 / 负责人）
5. `## 接口映射速查`（前端调用 → mapi 前缀 → 后端服务）
6. `## 依赖关系图`（可选 Mermaid）
7. `## 运维部署`（发布平台 / 灰度策略 / 回滚方式 / 下游通知）
