# 模板：spec/domain-models/&lt;group&gt;/entities.md

## Frontmatter

```yaml
---
constraint: hard
category: domain-model
description: <group> 研发组领域实体 TypeScript 接口定义，AI 生成代码必须引用而非自行编造字段。
domain: <group>
related:
  - ./enums.md
  - ./state-machines.md
tags:
  - 领域模型
  - 实体
  - TypeScript
  - <group>
  - 接口
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节

1. `# <业务组中文名> 领域实体定义`
2. `## 订单（Order）`
3. `## 商品/SKU`
4. `## 券码 / 核销单`（按组）
5. `## 预约 / 预订`（按组）
6. `## 退款单（Refund）`

## 每个实体的统一格式

```markdown
## <实体名中文>（<EnglishName>）

<一句话说明>

\`\`\`typescript
export interface <EnglishName> {
  /** 字段中文描述 */
  fieldName: string;
  // ...
}
\`\`\`

**字段备注**：
- `fieldName`：<注意事项>
```

## 强约束

- **禁止**使用 `any`（除非字段就是 JSON 黑盒，需注释说明）
- **禁止**定义后与后端接口响应不一致的字段（以 Swagger/apic 为准）
- 字段命名**严格**与后端契约一致，不擅自 camelCase 重命名
