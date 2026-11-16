# 模板：spec/domain-models/&lt;group&gt;/state-machines.md

## Frontmatter

```yaml
---
constraint: hard
category: domain-model
description: <group> 研发组状态机定义--订单/退款/核销/预约状态转移规则、前端展示映射、轮询策略。
domain: <group>
related:
  - ./enums.md
  - ./entities.md
  - ../../context-docs/business-rules/<group>.md
tags:
  - 状态机
  - 状态转移
  - 轮询
  - <group>
  - 领域模型
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 状态机`
2. `## 订单状态机`
3. `## 退款状态机`（applyStatus 分段）
4. `## 核销状态机`（按组）
5. `## 预约状态机`（按组）
6. `## 前端展示规则`（状态 → UI 文案 / 颜色 / 可操作按钮）
7. `## 轮询策略`（哪些状态需要轮询，频率）

## 每个状态机的统一格式

```markdown
## <名称>状态机

### 状态转移图

\`\`\`mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> PAID: 用户支付
    PAID --> USED: 到店核销
    PAID --> REFUNDING: 申请退款
    REFUNDING --> REFUNDED: 审核通过
    REFUNDING --> PAID: 审核拒绝
\`\`\`

### 状态转移规则表

| 起始状态 | 目标状态 | 触发动作 | 后端服务 | 前端拦截 |
|---------|---------|---------|---------|---------|
| PENDING | PAID | 支付成功回调 | pay-service | — |

### 前端展示映射

| 状态 | 文案 | 颜色 | 可操作按钮 |
|------|------|------|-----------|
| PENDING | 待支付 | 橙色 | [去支付] [取消] |

### 轮询策略

- 进入 `REFUNDING` 后每 3s 轮询一次，最多 10 次
```
