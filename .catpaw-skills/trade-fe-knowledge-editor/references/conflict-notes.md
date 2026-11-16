# 学城 wiki vs 仓库现状：冲突备忘

> 来源：学城《AI Coding Friendly 团队知识库》(km/2753716010) vs `trade-fe-rule` 仓库现状 + `meta/doc-template.md` / `meta/update-guide.md`。
> **本 skill 所有模板与校验规则以仓库现状为准**，不盲从 wiki。

## 冲突点 1：业务组命名

| wiki | 仓库 | 采纳 |
|------|------|------|
| 门票 / 酒旅 / 到餐 / 服务零售 (4 组) | food / gc / ticket / hotel / platform (5 组) | ✅ 仓库 |

**理由**：仓库新增 `platform`（DUO/组件库/跨组通用），wiki 写作时未覆盖。本 skill 使用 5 组命名。

## 冲突点 2：AI 入口目录

| wiki | 仓库 | 采纳 |
|------|------|------|
| `agents/global/AGENTS.md` + `agents/{biz}-fe/AGENTS.md` | 根 `AGENTS.md`（单文件路由全部 5 组） | ✅ 仓库 |

**理由**：仓库选择"单入口路由"策略，避免每组维护独立 AGENTS.md。本 skill **不创建** `agents/` 目录。

## 冲突点 3：Frontmatter 字段

| wiki | 仓库 | 采纳 |
|------|------|------|
| `title / type / domain / feature / tags / priority / last_updated` | `category / description / domain / related / see-also / archived` | ✅ 仓库为主 + 补 `tags / last_updated`（用户 Q-metadata 决议 C） |

**理由**：仓库已有大量文档使用现状字段；破坏性改造成本高。`tags / last_updated` 非冲突项，可增量补齐以提升召回。

- `title` → 改用 Markdown H1 自描述（H1 必填）
- `type` → 与 `category` 语义重叠，不引入
- `feature` → 与 `tags` 合并
- `priority` → 本 skill 在执行计划表中呈现，不落盘

## 冲突点 4：文档大小上限

| wiki | 仓库 | skill 采纳 |
|------|------|----------|
| ≤ 500 行 | ≤ 500 行 (update-guide.md) | ⚠️ **已在 skill 层面取消**：`validate.js` 不再针对行数产出 error / warning，拆分由作者按可读性自行决策；`meta/update-guide.md` 作为知识库建议保留，不做硬阻断。 |

## 冲突点 5：有效内容行占比

| wiki | 仓库 | 采纳 |
|------|------|------|
| > 60% | 未显式规定 | ✅ 采纳 wiki 规则作为 WARN 级校验 |

## 冲突点 6：CI 检查项

| wiki 提出 | 本 skill 的 validate.js 是否落地 |
|----------|--------------------------------|
| 文件命名规范（含业务域关键词） | ✅ 已实现 |
| Metadata 完整性 | ✅ 已实现 |
| 术语一致性（与 glossary 对比） | ⚠️ 仅 WARN（不做硬阻塞，避免打断用户） |
| 文件 ≤ 500 行 | ✖️ 已废弃（skill 层面移除行数检查，由作者自行权衡拆分） |
| 有效内容行占比 > 60% | ⚠️ 仅 WARN |
| 强制注入文件存在性（AGENTS.md） | ✅ 已实现（检查仓库根 AGENTS.md 存在） |

## 冲突点 7：business-flows 文件命名

| wiki 暗示 | 仓库现状 | 采纳 |
|----------|---------|------|
| `business-flows/{biz}-flow.md` | `business-flows/<group>-<flow>.md`（如 `gc-core-flow.md` / `food-coupon-flow.md`） | ✅ 仓库（更细粒度） |

## 非冲突的复用项（直接继承 wiki 设计）

- **强制注入 + 精确匹配 + Metadata 过滤** 三层召回保障机制
- **spec/（硬约束）vs context-docs/（软上下文）** 双轨分离
- 核心度量指标：上下文命中率 / 规则覆盖率 / AI 代码合规率（本 skill 不实现度量，但交付清单引用）
- 领域模型三件套：`entities.md` / `enums.md` / `state-machines.md`
