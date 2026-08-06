# 模板：context-docs/overviews/&lt;group&gt;.md

> 结构忠实于仓库现有成熟样本 `context-docs/overviews/gc.md`（15 段）。
> 本 skill 在阶段 4 对**缺失章节**做模板注入，保留用户已填内容不动。

---

## Frontmatter（必填）

```yaml
---
constraint: soft
category: overview
description: <group> 研发组 AI Coding 导航页--文件路由规则、强制约束/禁止项、上下文索引。业务形态全景对齐<后端团队名称>。
domain: <group>
related:
  - ./glossary/<group>.md
  - ./service-maps/<group>.md
  - ./business-rules/<group>.md
tags:
  - <business-action-1>
  - <business-action-2>
  - <tech-stack>
  - <key-page>
  - <domain-noun>
last_updated: <YYYY-MM-DD>
---
```

## 必备 H2 章节（按顺序；缺失则补占位）

1. `# <业务组中文名> — AI Coding 导航页`（H1）
2. `## 一句话定义`
3. `## 业务形态与产品功能全景`
   - H3：业务交易类型（表格）
   - H3：核心功能特性（多个 H4：打包能力 / 营销能力 / 服务体验 / 售后能力 / 买单能力 等，按组裁剪）
4. `## 文件路由规则`（表格：场景/关键词 → 文件 → 说明）
5. `## 强制约束（MUST — 每次生成代码必须遵守）`
   - H3：命名约束
   - H3：技术栈约束（按需）
6. `## 禁止项（MUST NOT — 违反将导致 CR 不通过）`
7. `## 关键业务规则速查`（指向 `business-rules/<group>.md`）
8. `## 文档分类速查`（强制约束 vs 上下文，便于 AI 区分）
9. `## 核心仓库`（表格：仓库名 / Code 地址 / 说明）
10. `## 维护约定`（事件 → 需要更新的文件）
11. `## 重点需求与业务方向`（可选）
12. `## 团队联系`

---

## 占位骨架（初始化新文件时使用）

```markdown
---
constraint: soft
category: overview
description: <group> 研发组 AI Coding 导航页--文件路由规则、强制约束/禁止项、上下文索引。
domain: <group>
related:
  - ./glossary/<group>.md
tags:
  - TODO
  - TODO
  - TODO
  - TODO
  - TODO
last_updated: <YYYY-MM-DD>
---

# <业务组中文名> — AI Coding 导航页

> 本文件是 <业务组中文名> 研发组的 AI Coding 入口文档。
> AI 工具（CatPaw / Cursor / Copilot）读取本文件即可定位所有相关上下文。

---

## 一句话定义

<!-- TODO: 一句话描述业务组定位，≤ 100 字 -->

---

## 业务形态与产品功能全景

### 业务交易类型

| 交易类型 | 说明 |
|---------|------|
| <!-- TODO --> | <!-- TODO --> |

### 核心功能特性

#### 打包能力

| 功能 | 说明 |
|------|------|
| <!-- TODO --> | <!-- TODO --> |

---

## 文件路由规则

| 场景 / 关键词 | 读取文件 | 说明 |
|---------------|---------|------|
| 生成 <group> 任何前端代码 | `spec/coding-standards/<group>.md` | **每次必须加载** |
| 不认识 <group> 业务术语 | `context-docs/glossary/<group>.md` | 专属术语定义 |
| 需要数据结构/类型定义 | `spec/domain-models/<group>/entities.md` | TypeScript 类型 |
| 涉及状态枚举/状态机 | `spec/domain-models/<group>/enums.md` + `state-machines.md` | 状态定义与流转 |
| 涉及核心流程 | `context-docs/business-flows/<group>-*.md` | 业务核心流程 |
| 涉及退款规则/阈值 | `context-docs/business-rules/<group>.md` | 业务规则 |
| 需要设计方案参考 | `context-docs/design-patterns/<group>.md` | 最佳实践 |
| 定位页面 / 仓库 | `context-docs/page-assets/<group>/page-index.md` | 页面索引 |
| 了解技术选型决策 | `spec/adr/<group>.md` | ADR |
| <group> 工程全景 / 服务地图 | `context-docs/service-maps/<group>.md` | 服务地图 |

---

## 强制约束（MUST — 每次生成代码必须遵守）

### 命名约束

- <!-- TODO: 列出组级命名约定 -->

### 技术栈约束

- <!-- TODO: 列出组级技术栈红线 -->

---

## 禁止项（MUST NOT — 违反将导致 CR 不通过）

- <!-- TODO: 至少 3 条禁止项 -->

---

## 关键业务规则速查

详见 [context-docs/business-rules/<group>.md](../business-rules/<group>.md)。

| 规则域 | 关键阈值 |
|--------|---------|
| <!-- TODO --> | <!-- TODO --> |

---

## 文档分类速查

| 类型 | 文件 | 消费方式 |
|------|------|---------|
| **强制约束** | `spec/coding-standards/<group>.md` | 生成代码时**始终加载** |
| **强制约束** | `context-docs/business-rules/<group>.md` | 涉及业务逻辑时**始终加载** |
| **上下文** | `context-docs/glossary/<group>.md` | 遇到不认识的术语时加载 |
| **上下文** | `spec/domain-models/<group>/entities.md` | 需要数据结构时加载 |
| **上下文** | `spec/domain-models/<group>/enums.md` | 涉及状态枚举时加载 |
| **上下文** | `spec/domain-models/<group>/state-machines.md` | 涉及状态流转时加载 |
| **上下文** | `context-docs/design-patterns/<group>.md` | 设计方案参考时加载 |
| **上下文** | `context-docs/page-assets/<group>/page-index.md` | 定位页面/仓库时加载 |
| **上下文** | `context-docs/service-maps/<group>.md` | 需要后端服务信息时加载 |

不要把上下文文件当成约束强制注入，会导致 token 浪费。

---

## 核心仓库

| 仓库名称 | Code 地址 | 说明 |
|----------|-----------|------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

详细页面清单见 [context-docs/page-assets/<group>/page-index.md](../page-assets/<group>/page-index.md)。

---

## 维护约定

| 事件 | 需要更新的文件 |
|------|---------------|
| 新增/下线仓库或页面 | `context-docs/page-assets/<group>/page-index.md` + `context-docs/service-maps/<group>.md` |
| 新增/修改编码规范 | `spec/coding-standards/<group>.md` + 本文件的约束摘要 |
| 新增业务术语或发现易混词 | `context-docs/glossary/<group>.md` |
| 领域模型字段/枚举变更 | `spec/domain-models/<group>/entities.md` + `enums.md` |
| 业务规则变更 | `context-docs/business-rules/<group>.md` + 本文件规则速查 |
| 重大技术选型决策 | `spec/adr/<group>.md` |
| 新增设计模式 / 最佳实践 | `context-docs/design-patterns/<group>.md` |

---

## 重点需求与业务方向（可选）

### 核心业务能力

| 业务方向 | 重点需求/能力 | 涉及页面 |
|----------|--------------|----------|
| <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

### 学城重点文档入口

- <!-- TODO: 学城 URL -->

## 团队联系

- **学城主目录**：<!-- TODO -->
- **FEDO 研发组**：<!-- TODO -->
```
