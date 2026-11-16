# Frontmatter 字段规范

> 本 skill 强制执行的 YAML frontmatter 规范。字段闭环枚举**必须**从 `meta/doc-template.md` 取值，不得自创。

## 字段清单

```yaml
---
category: <闭环枚举>       # MUST
description: <一句话>      # MUST, ≤ 120 字
domain: <闭环枚举>         # MUST
related:                   # OPTIONAL, 相对路径数组
  - ./foo.md
see-also:                  # OPTIONAL, 外部 URL 数组
  - https://km.sankuai.com/collabpage/xxxxx
tags:                      # MUST（本 skill 强制补齐）
  - <业务动作词>
  - <知识类型词>
  - <技术栈词>
last_updated: YYYY-MM-DD   # MUST（本 skill 强制补齐）
archived: false            # OPTIONAL
constraint: soft | hard    # OPTIONAL（overview 类用 soft，spec 类可标 hard）
---
```

## category 闭环枚举（**以仓库实际落盘值为准**）

仓库 `trade-fe-rule` 中 .md 文件真实使用的 category 值（grep 统计得出）：

`adr` / `business-flow` / `business-rule` / `coding-conventions` / `design-pattern` / `domain-model` / `glossary` / `meta` / `nfr` / `onboarding` / `overview` / `page-asset` / `pitfall` / `process` / `service-map`

> 说明：`meta/doc-template.md` 规定的"官方"值（`process/coding/architecture/ops/pitfall/glossary/service-map/onboarding/meta`）与实际落盘值存在**扩展偏移**（仓库使用了 `coding-conventions` 而非 `coding`，`business-rule` 而非新增值，等等）。
> **本 skill 以实际落盘值为准**，避免破坏性改写现有文档。若将来统一，需同步本清单 + `validate.js` + 所有模板文件的 `category` 字段。

## domain 闭环枚举

`mrn` / `max` / `miniprogram` / `h5` / `duo` / `general` / `ci-cd` / `monitoring` / `knowledge-management` / `food` / `gc` / `ticket` / `hotel` / `platform`

> `food/gc/ticket/hotel/platform` 是业务组 domain，overview 类首选；技术栈 domain（mrn/max/...）用于 pitfalls/coding-standards。

## tags 生成规则（本 skill 的自动化部分）

目标：≥ 5 个，单词 2-8 字符，**不重复于 category/domain**。按优先级取：

1. **业务动作**（取自对应 glossary）：退款/核销/预约/提单/订详/购物车/买单...
2. **知识类型**：状态机/枚举/实体/ADR/踩坑/规范/流程...
3. **技术栈**：MRN/DUO/MAX/小程序/H5...
4. **关键页面/场景**：订详页/提单页/退款申请页...
5. **业务核心名词**：次卡/套餐/团购/预付/景+X/低碳...

**禁止**：
- `tags` 中出现 `meituan` / `美团` / `knowledge-base` 这类无检索价值的词
- 同义词重复（既有"退款"又有"refund"，保留中文）
- 超过 12 个（失去区分度）

## 自动补齐策略

- 文件已有 `tags` 且数量 ≥ 5 → 保留不改
- 文件已有 `tags` 但数量 < 5 → 追加至 5 个，保留已有
- 文件无 `tags` → 从该文件正文提取 H2/H3 标题、代码块类名、表格首列取前 5-8 个
- `last_updated`：每次改动写入今天日期 YYYY-MM-DD（UTC+8）
- `related` / `see-also`：仅在用户明确提供时添加，不臆造

## 一致性校验（由 validate.js 执行）

- `category` ∈ 枚举 → ERROR if 不在
- `domain` ∈ 枚举 → ERROR if 不在
- `description` 存在且 ≤ 120 字 → ERROR if 缺失，WARN if 超长
- `tags` ≥ 5 个 → WARN if 不足（给提示但不阻塞）
- `last_updated` 为合法日期 → ERROR if 格式不对
- `related` 中的相对路径实际存在 → WARN if 文件不存在
