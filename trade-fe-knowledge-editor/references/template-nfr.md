# 模板：spec/nfr/&lt;group&gt;.md（可选）

> 通用 NFR 在 `spec/nfr/general.md`。组级 NFR 仅在**该组有额外硬约束**时新建。

## Frontmatter

```yaml
---
category: nfr
description: <group> 研发组非功能需求清单--性能/稳定性/监控/灰度/回滚的组级特殊要求。
domain: <group>
related:
  - ./general.md
  - ../../context-docs/service-maps/<group>.md
tags:
  - NFR
  - 性能
  - 监控
  - 灰度
  - <group>
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 非功能需求`
2. `## 性能基线`（FCP / LCP / TTI 等组级阈值）
3. `## 稳定性要求`（JS 错误率 / 接口成功率）
4. `## 监控告警`（必接大盘、关键指标、告警阈值）
5. `## 灰度策略`（流量比例 / 观察时长）
6. `## 回滚预案`
