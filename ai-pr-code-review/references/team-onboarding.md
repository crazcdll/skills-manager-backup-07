# 团队接入指南

> 其他团队接入只需三步，无需修改 Skill 本身。

## Step 1：创建团队配置文件

在团队 workspace 根目录创建 `.cr-config.yaml`：

```yaml
# .cr-config.yaml — AI Code Review 团队配置
# 放在 ~/.openclaw/workspace/.cr-config.yaml

team:
  name: "你的团队名称"                      # 仅用于标识，不影响逻辑

citadel:
  parent_id: 2749896619                    # 学城 CR 文档父节点 ID（改成你们团队的目录）

table:
  table_id: 2751197605                     # 多维表格 ID（改成你们团队的表格）

knowledge:
  domain_knowledge: references/domain-knowledge.md  # 领域知识库路径（相对或绝对路径）

notify:
  notify_mis: [your_mis, teammate_mis]     # CR 结果大象推送给谁（可选）
```

## Step 2：创建团队领域知识库

参考 `references/domain-knowledge.md` 模板，在配置的路径下创建你们团队的知识库：

```markdown
# 团队领域知识库

## ID 体系
- ...（团队核心 ID 类型及混用风险）

## 业务核心概念
- ...

## 团队特有 P0/P1 规则
- ...（从历史 COE 提炼）

## CR 触发映射
- ...（特定字段/类名出现时，触发哪些额外检查）
```

> 💡 知识库质量 = CR 检出质量。建议从历史 COE 复盘文档中提炼，投入越多误报越少。

## 可选：MDP-Context 仓库自动接入

如果你的仓库使用 **MDP-Context 框架**（特征：根目录有 `.mdp/` 目录），**无需任何额外配置**，CR Skill 会在 Step 3C 自动探测并读取：

| 目录 | 内容 | 是否自动读取 |
|------|------|------------|
| `.mdp/context/` | 业务上下文文档 | ✅ 全部读取 |
| `.mdp/rules/team/` | 团队级编码规范 | ✅ 全部读取 |
| `.mdp/rules/project/` | 项目级规范 | ✅ 全部读取 |
| `.mdp/rules/company/` | 公司级通用规范 | ⏭ 跳过（Skill 已内置） |

> 💡 spec 文档内容权威性高于通用规则，会优先用于业务语义理解和 P0/P1 判断。

**触发条件**：目标仓库根目录有 `.mdp/` 目录，无需在 `.cr-config.yaml` 中配置任何字段。

---

## Step 3：创建多维表格

在学城创建一张多维表格，字段顺序（含类型）：

| 列名 | 类型 |
|------|------|
| CR日期 | 日期（毫秒时间戳） |
| PR链接 | 文本 |
| 仓库 | 文本 |
| PR标题 | 文本 |
| 提交人 | 文本 |
| 组织架构 | 文本 |
| CR结论 | 单选（✅通过/💚通过有建议/🟠需修复/🔴需重新设计） |
| P0数量 | 数字 |
| P1数量 | 数字 |
| CR文档链接 | 文本 |
| 备注 | 文本 |

表格创建后将 `table_id` 填入 `.cr-config.yaml`。
