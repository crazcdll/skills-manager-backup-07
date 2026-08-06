# 模板：context-docs/business-rules/&lt;group&gt;.md

## Frontmatter

```yaml
---
category: business-rule
description: <group> 研发组业务规则--退款计算、预约限制、优惠规则、阈值与边界条件，供 AI 生成业务判断逻辑。
domain: <group>
related:
  - ../overviews/<group>.md
  - ../../spec/domain-models/<group>/state-machines.md
tags:
  - 业务规则
  - 退款
  - 阈值
  - 状态流转
  - <group>
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节（按组裁剪）

1. `# <业务组中文名> 业务规则`
2. `## 退款规则`（细分：申请条件 / 计算公式 / 审批流程 / 状态流转 / 异常处理）
3. `## 核销规则`（券码 / 核销码 / 自助核销 / 多次核销）
4. `## 预约规则`（提前量 / 修改次数 / 自动取消）
5. `## 优惠与营销规则`（限购 / 组合使用 / 抵扣优先级）
6. `## 库存/预订规则`
7. `## 关键阈值速查表`

## 占位骨架

```markdown
---
category: business-rule
description: <group> 研发组业务规则。
domain: <group>
related:
  - ../overviews/<group>.md
tags:
  - 业务规则
  - 退款
  - 阈值
  - 状态流转
  - <group>
last_updated: <YYYY-MM-DD>
---

# <业务组中文名> 业务规则

## 退款规则

### 申请条件

- <!-- TODO: 什么状态下可申请 -->

### 计算公式

```
<!-- TODO: 退款金额 = ... -->
```

### 审批流程

<!-- TODO -->

### 状态流转

详见 [spec/domain-models/<group>/state-machines.md](../../spec/domain-models/<group>/state-machines.md)。

## 核销规则

- <!-- TODO -->

## 预约规则

- **提前量**：<!-- TODO -->
- **修改次数**：<!-- TODO -->
- **自动取消**：<!-- TODO -->

## 关键阈值速查表

| 规则域 | 关键阈值 |
|--------|---------|
| <!-- TODO --> | <!-- TODO --> |
```
