# 目标文件矩阵

> 本文件是本 skill 阶段 0 / 1 / 2 的**路由表**。`<group> ∈ {food, gc, ticket, hotel, platform}`。
>
> **v1.1 核心原则**：用户显式指定范围 → **范围锁定模式**（scoped），仅处理范围内文件；未指定范围 → 默认 `scope=[overview]` 并单独一行提示用户可扩展；显式说"全量" → 进入全量模式。详见下方「范围锁定模式」章节。
>
> **v1.2 新增**：双模式路由（local / auto）。local 模式保留 v1.1 行为；auto 模式自动完成拉 master → 切分支 → 写盘 → 校验 → commit → push → pr_create 的完整闭环。详见下方「模式路由」章节。

---

## 模式路由（v1.2 新增）

### 关键词表（prompt → mode）

| 关键词（命中任一即 auto） | 说明 |
|--------------------------|------|
| `自动更新` / `自动化` / `自动化提 PR` | 显式声明自动模式 |
| `远程更新` / `远程` | 工作区在远程/临时目录，走 clone 分支 |
| `提 PR` / `提交 PR` / `帮我更新并提 PR` / `走自动流程` | 终点是 PR，必然走 auto |
| `mode: auto` / `--mode=auto` | 结构化显式参数 |

命中关键词 → **auto**。未命中且当前工作目录不在 trade-fe-rule 仓库 → **auto**（强制兜底，走 clone）。其余 → **local**（默认）。

### 模式 × 范围 的四种组合

| 组合 | 典型 prompt | 工作流差异 |
|------|-----------|-----------|
| **local + scoped** | "仅更新 food page-index" | v1.1 原生路径；无 git 操作；用户在本地 working tree 看到改动 |
| **local + full** | "全量更新 ticket 前端知识库" | v1.1 原生路径；触碰全部 13 个目标文件 |
| **auto + scoped** | "自动更新 gc glossary、business-rules 并提 PR" | 阶段 0 workspace 校验 → sync master → 切分支 → 写盘（仅 scope）→ validate --scope → commit（仅 scope 文件）→ push → pr_create |
| **auto + full** | "自动化提交 ticket 的 full 前端知识库 PR" | 同上，但 commit/PR 涵盖全部目标文件；validate 用 `--scope all` 显式留痕 |

### auto 模式关键步骤的路由表

| 步骤 | 对应脚本函数 | 失败行为 |
|------|-------------|---------|
| workspace 校验/切换 | `auto-pr.sh ensure_workspace <auto\|local>` | local 硬停；auto 自动 clone 到 `<clone_root>/trade-fe-rule-{ts}`，`<clone_root>` 由 `_resolve_clone_root` 按 6 级优先级动态选择（`$TRADE_FE_CLONE_ROOT` / `$CATPAW_WORKSPACE_ROOT` / `$WORKSPACE_FOLDER` / `$PWD` 向上继承 / `$HOME/projects` / `mktemp -d`） |
| sync master | `auto-pr.sh sync_master` | 非 ff-only 失败退出 13，由用户手动处理 |
| 解析 MIS | `auto-pr.sh resolve_mis` | 取不到则打印空串，不阻断 |
| 生成分支名 | `auto-pr.sh compute_branch <mis?>` | 纯字符串计算 |
| 切新分支（含脏检测+同名 `-rN` 后缀） | `auto-pr.sh safe_checkout_new <base_branch>` | 脏工作区退 14；同名 20 次仍冲突退 15 |
| 范围内 git add + commit | `auto-pr.sh commit_scoped <group> <kinds> <mis> <msg_file> <files...>` | staged 空退 16 |
| push | `auto-pr.sh push_current_branch` | 失败退 17，保留本地 commit |
| pr_create | `auto-pr.sh pr_create_wrapper <group> <kinds> <mis> <branch> <title_file> <desc_file>` | API 失败退 18，自动打印 fallback URL |
| validate 摘要 | `node validate.js <group> --scope <kinds> --pr-summary` | errors=0 退 0；否则退 1（auto 流程中断） |

## 命名同义词映射（严格）

| 用户说 | 映射到 |
|--------|--------|
| 服务零售 / 服务零售 GC / GC 组 / 次卡 / 预约 / 美甲 / 洗车 | `gc` |
| 到餐 / 美食 / 团购 / 买单 / 餐饮 / 购物车 | `food` |
| 门票 / 景点 / 游玩 / 度假 / 跟团 / 电子票 | `ticket` |
| 酒店 / 酒旅 / 价格日历 / 入住 | `hotel` |
| 平台 / DUO / 组件库 / 低代码 / 跨组通用 | `platform` |

若用户表述不在上表内（如"外卖""闪购""酒店房券"），**必须追问澄清**，不得默认选择。

---

## 文件清单（默认按优先级顺序执行）

| 优先级 | 文件路径 | 存在判定 | 默认模板 |
|--------|----------|---------|---------|
| P0 | `context-docs/overviews/<group>.md` | 必须存在 | `template-overview.md` |
| P1 | `context-docs/glossary/<group>.md` | 推荐存在 | `template-glossary.md` |
| P1 | `spec/coding-standards/<group>.md` | 推荐存在 | `template-coding-standards.md` |
| P2 | `context-docs/business-rules/<group>.md` | 按需 | `template-business-rules.md` |
| P2 | `context-docs/service-maps/<group>.md` | 按需 | `template-service-maps.md` |
| P2 | `context-docs/design-patterns/<group>.md` | 按需 | `template-design-patterns.md` |
| P3 | `spec/domain-models/<group>/entities.md` | 按需 | `template-domain-entities.md` |
| P3 | `spec/domain-models/<group>/enums.md` | 按需 | `template-domain-enums.md` |
| P3 | `spec/domain-models/<group>/state-machines.md` | 按需 | `template-domain-state-machines.md` |
| P3 | `spec/adr/<group>.md` | 按需 | `template-adr.md` |
| P4 | `spec/pitfalls/<group>.md` | 可选 | `template-pitfalls.md` |
| P4 | `spec/nfr/<group>.md` | 可选 | `template-nfr.md` |
| P4 | `context-docs/page-assets/<group>/page-index.md` | 可选 | `template-page-index.md`（**仅此一个 page-assets 文件纳入**） |

**P0 必查，P1 推荐，P2-P4 按用户意图范围取用。**

---

## 意图范围 → scope 路由（v1.1 严格模式）

> 解析结果就是校验脚本 `--scope` 的值，**与阶段 1 识别结果一致**，不得擅自扩大。

| 用户意图关键词 | 解析为 scope |
|---------------|-------------|
| "更新 X 前端知识库"（无其他范围词） | `[overview]`（默认单范围，不扩散；另单独一行提示"可扩展到…"） |
| "全量更新 X" / "一次性完善 X" / "all" | `all`（进入全量模式，扫描全部文件） |
| "新增术语" / "glossary 补全" | `[glossary]` |
| "订单/退款/核销状态机" | `[domain-state-machines]` |
| "状态码" / "枚举" | `[domain-enums]` |
| "实体类型" / "entity" | `[domain-entities]` |
| "域模型" / "domain-models 全部" | `[domain-models]`（= entities + enums + state-machines） |
| "业务规则" / "退款规则" / "阈值" | `[business-rules]` |
| "编码规范" / "命名规范" / "组件规范" | `[coding-standards]` |
| "ADR" / "架构决策" / "技术选型" | `[adr]` |
| "踩坑" / "pitfall" | `[pitfalls]` |
| "服务地图" / "仓库拓扑" / "AppKey" | `[service-maps]` |
| "设计模式" / "最佳实践" | `[design-patterns]` |
| "NFR" / "非功能约束" | `[nfr]` |
| "页面索引" / "page-index" / "仓库映射" | `[page-index]` |
| 多 kind 并列（如"仅更新 glossary 和 business-rules"） | `[glossary, business-rules]` |

> **历史兼容提示**：v1.0 中"P0+P1 默认激活"已废弃。若用户仍希望默认激活 P0+P1，需显式说"全量更新"或主动"扩展到 glossary、coding-standards"，AI 不再擅自勾选。

---

## 范围锁定模式（scoped）铁律

进入范围锁定模式后，AI 必须严守：

1. **不读范围外文件**：阶段 2 扫描时只读 scope 命中的文件的 frontmatter/H2，不得以"交叉参考 / 保证术语一致"为由读取 `glossary/<group>.md` 等其他文件。
2. **不写范围外文件**：阶段 4 执行时，只允许操作 scope 命中的文件；其他文件即使格式不合规也不动。
3. **不提示范围外变更**：确认清单、变更计划表、Handoff Summary 中不得出现范围外文件名和建议。仅允许在交付摘要末尾用**一行**轻提示：
   > "如需扩展范围，请回复'扩展到 <kind>'"（不说明具体改什么）
4. **校验命令严格对齐 scope**：`node <path-to-skill>/scripts/validate.js <group> --scope <kind list>`，--scope 值 = 阶段 1 识别结果。
5. **范围只因用户明确扩展而扩大**：AI 不得在任何阶段"顺手"加 kind。用户回复"扩展到 glossary"后，scope 更新为 `[原 kind..., glossary]` 并走一轮新的阶段 3 确认。

### 范围锁定 Handoff Summary 示例

```markdown
## Handoff Summary
范围: page-index（严格锁定）

- [✓] context-docs/page-assets/food/page-index.md：补齐 tags、last_updated；补写"变更记录"尾条
validate: errors=0 warnings=1（tags<5，已补全）

（不提 overview / glossary / … 等其他文件的任何状态）
```

---

## business-flows 的特殊处理

`context-docs/business-flows/<group>-<flow>.md` 因 `<flow>` 不固定（下单/核销/退款/赠送/预约…），本 skill **不自动创建**。
遇到用户说"补充 GC 退款流程" → 追问 `<flow>` 命名（kebab-case），确认后使用 `template-business-flow.md`（若存在）或引导用户按 `meta/doc-template.md` 模板一自行新建。
本 skill 只对已存在的 flow 文件做 frontmatter / 章节校验，**不做内容注入**。

---

## page-assets 的处理策略（部分纳入）

`context-docs/page-assets/<group>/` 下文件分三类，本 skill 的处理方式不同：

| 文件模式 | 示例 | 本 skill 处理 |
|---------|------|--------------|
| **`<group>/page-index.md`** | `food/page-index.md` | ✅ **纳入**（P4）。使用 `template-page-index.md`（参考 `gc/page-index.md` 五维度设计）初始化或补齐。强制三大必有板块：**①页面索引表 / ③仓库索引 / ⑤变更记录**；推荐两大板块：**②按技术栈分类 / ④常用跳转链接模板**。**结构灵活**，维度 ① 可进一步按业务功能分区（food/ticket/hotel 常用）。 |
| `<group>/*-order-submit-modules.md` / `<group>/*-order-detail-modules.md` | `food-order-submit-modules.md` | ❌ **不纳入**。提单/订详页模块速查粒度过细，由人工/专项 skill 维护。 |
| `<group>/<specific-page>.md` | `combo-order-submit-page.md`、`duo-platform-guide.md`、`refund-apply-page.md` | ❌ **不纳入**。每个特殊页面结构各异，无通用模板。 |

**对不纳入的 page-assets 文件**：本 skill 的 `scripts/validate.js` 也 **不扫描**（只校验 `page-index.md`），避免误报。
