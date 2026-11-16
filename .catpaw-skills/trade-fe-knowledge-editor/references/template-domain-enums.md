# 模板：spec/domain-models/&lt;group&gt;/enums.md

## Frontmatter

```yaml
---
constraint: hard
category: domain-model
description: <group> 研发组枚举定义汇总--订单状态/退款状态/核销状态/SKU 类型等。AI 生成代码必须引用枚举而非硬编码数字。
domain: <group>
related:
  - ./entities.md
  - ./state-machines.md
tags:
  - 枚举
  - 状态码
  - 领域模型
  - <group>
  - OrderStatus
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 枚举定义`
2. `## 订单状态（OrderStatus）`
3. `## 退款状态 / applyStatus`
4. `## 核销状态 / VoucherStatus`（按组）
5. `## SKU / 商品类型`
6. `## 支付类型 / PayType`
7. `## 工具函数`（`canRefund` / `canVerify` 等 AI 可直接引用的判定函数）

## 统一格式

```markdown
## <中文名>（<EnglishName>）

\`\`\`typescript
export enum <EnglishName> {
  PENDING = 1,  // 待支付（中文说明）
  PAID    = 2,  // 已支付
  // ...
}
\`\`\`

**业务含义**：
- `PENDING`：<补充说明>

**易错点**：
- <!-- 常见错用 -->
```

## 工具函数示例（推荐写法）

```typescript
export const canRefund = (status: OrderStatus): boolean =>
  [OrderStatus.PAID].includes(status);
```

## 禁止事项

- ❌ 硬编码 `status === 2`
- ❌ 魔法数字数组 `[1, 2, 5]`
- ❌ 字符串枚举值与数字枚举值混用
