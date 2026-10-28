# CR 看板上报

本文件仅用于 `fe-ai-review` 独立运行。受 `ai-quality-cr-agent` 委托时，交付标准化结果，由上层统一组装和上报，不执行本文件的发布动作。

独立运行且报告产出后读取本文件，上报审查结论和发现项到 CR 看板。

- 需要本次规则上下文：平台 receipt、仓库本地 L3 实际规则清单（含 `.mdp/rules/project/**/*.md`、`.fed/` 目录规则及由适用入口文件发现的规则）以及 fallback 状态；入口文件本身只作为发现来源或直接约束记录。
- 用户说「不要上报」时跳过。
- 上报失败时在会话末尾提示，不阻塞审查结论。

质量门禁接口提供前，只调用现有看板。后续质量门禁看板复用同一份标准化 payload，不再转换规则 ID。

## 字段来源

### 必填

| 字段 | 来源 |
|---|---|
| `operator` | 上下文中如有 misId 则直接使用；尝试 `git config user.email` 取 `@` 前缀；失败则用 `git config user.name`；仍失败留空 |
| `repo` | `git remote get-url origin` 末段路径，去掉 `.git` 后缀 |
| `branch` | `git branch --show-current` |
| `review_mode` | 路由时已知：`local` 或 `pr-only` |
| `tech_stack` | 技术栈识别结果，多值英文逗号拼接如 `"max,mrn"`；识别不出填 `"others"` |
| `review_depth` | 用户说“快速过一遍”时填 `quick`；其余填 `deep` |
| `conclusion` | 见枚举映射 |
| `launch_risk` | 见枚举映射 |
| `p0_count` / `p1_count` / `p2p3_count` | 报告问题统计 |
| `one_liner` | 报告审查结论提炼，20 字以内 |
| `findings` | **必填**，无问题也要传空结构，见格式说明 |

### 可选

| 字段 | 来源 |
|---|---|
| `pr_id` | PR URL `pr/{id}` 中提取（仅 pr-only 模式） |
| `diff_range` | local 模式的 diff range，如 `origin/master...feature/xxx` |
| `change_summary` | 报告变更摘要要点，转为 `string[]` |
| `dep_changes` | package.json 有版本变化时填写，见格式说明 |
| `client` | 当前运行环境。如 `catpaw`、`catdesk`、`claudecode`、`cursor`、`clawagent`、`openclaw` 等 |

## 枚举映射

| 报告「审查结论」 | `conclusion` |
|---|---|
| ✅ 可合并 | `approve` |
| ✅ 可合并（有优化建议） | `approve_with_suggestion` |
| ⚠️ 修复后可合并 | `fix_then_merge` |
| ❌ 不建议合并 | `block` |

| 报告「上线风险」 | `launch_risk` |
|---|---|
| 🟩 安全 | `safe` |
| 🟨 低风险 | `low` |
| 🟧 中风险 | `medium` |
| 🟥 高风险 | `high` |

## 字段格式

### `findings`（必填）

`rule_bundle` 是两个看板共用的规则上下文：

```json
{
  "p0": [],
  "p1": [],
  "p2p3": [],
  "openQuestions": [],
  "rule_bundle": {
    "schema_version": "cr-rule-source/v1",
    "source": "mt-code-standards-setup",
    "snapshot_id": "<receipt.snapshot_id>",
    "standard_domain": "frontend",
    "release_refs": [
      {"rule_set_id": "frontend-l1", "release_id": "frontend-l1@2026.09", "scope_level": "L1"}
    ],
    "project_rules": [
      {"rule_set_id": "order-detail", "file": "project/order-detail/ab.md", "rule_version": "<sha256>"}
    ],
    "fallback": {"active": false, "rule_set_id": "fe-ai-review-fallback", "rule_version": "v2"}
  }
}
```

按 [`rules-loading.md`](rules-loading.md) 完成 receipt、manifest 与本地文件校验后，使用本次快照和完整 `release_refs`，`fallback.active` 填 `false`。`repository_not_registered` 或 `no_effective_l2` 的 `l1_only` 成功，以及 `not_modified` 成功，均适用此规则。

最终 Runner 失败、依赖缺失、receipt 无效或本地校验失败时：`source` 填 `fallback`，`snapshot_id` 填 `null`，`release_refs` 填空数组，`fallback.active` 填 `true`。已实际读取的 L3 规则仍列入 `project_rules`。快照表示安装来源，不代表其中全部正文均已读取；实际读取文件及章节记录随准备信息保留，`rule_sources` 只填写已读且命中的规则，不增加上报字段。

每个发现项填写全部命中的 `rule_sources`，纯上下文传 `[]`。脚本按来源、规则集、版本、文件和章节生成 `cr-rule/v1/<sha256>`，保留 `upstream_rule_id` 原值；不使用可读展示编号替换来源标识。

```json
{
  "level": "P0",
  "type": "空值未处理",
  "path": "src/pages/checkout/index.jsx:L45",
  "reason": "order.items 在接口异常时可能为 null",
  "suggestion": "增加空值保护：(order.items ?? []).map(...)",
  "confidence": "高",
  "rule_sources": [{
    "source_type": "platform",
    "scope_level": "L1",
    "rule_set_id": "frontend-l1",
    "rule_version": "frontend-l1@2026.09",
    "file": "company/fe/前端规范/ASYNC-异步与异常处理.md",
    "title": "异步与异常处理",
    "section": "空值与异常返回",
    "upstream_rule_id": "fe-l1:ASYNC-001"
  }]
}
```

L3 使用 `source_type: "project"`、`scope_level: "L3"` 和文件 SHA-256 作为 `rule_version`。`.mdp/rules/project/` 的首级目录作为 `rule_set_id`；`.fed/` 使用首级目录名，根目录规则使用 `fed`；由 `AGENTS.md`、`README` 等入口直接声明的可执行约束使用 `project-entry`，并保留入口文件路径。`upstream_rule_id` 的取法见 [`rules-loading.md`](rules-loading.md)。Fallback 使用 `source_type: "fallback"`、`scope_level: "FALLBACK"`、`rule_set_id: "fe-ai-review-fallback"`；`rule_version`、`file`、`title` 和 `section` 按 [`rules/fallback-rules.md`](rules/fallback-rules.md) 顶部约定填写。

### 待确认问题（Open Questions）

按 [定级与证据判断](severity.md) 筛选后上报，报告、评论与上报使用同一批待确认项。

- 现有 CR 看板沿用 `findings.openQuestions` 容器，无待确认项时传 `[]`。每条保留标题、真实位置、问题描述、不确定原因、条件成立时的风险和确认建议；不放入 `p0` / `p1` / `p2p3`，不增加这些级别的计数。
- 受 `ai-quality-cr-agent` 委托时，由上层按交接协议转换为 `severity=confirm`，沿用 `description`、`confirm_reason`、`possible_risk`、`confirm_suggestion` 字段并补齐通用必填字段。位置必须可核对，不以猜测补齐文件或行号。
- 两条通道保留相同事实与待确认条件；不把候选级别当成已确认级别，不把 `confirm` 与复审结论 `CONFIRM` 混用。现有看板容器不改名为 `confirm`。
- 结论按 [output.md](output.md) 映射；仅有待确认项时，`one_liner` 明确“无已确认缺陷，仍有待确认项”，避免把通过表述为风险已排除。覆盖缺口留在覆盖自评，不作为待确认项上报。

### `dep_changes`

```json
[
  { "name": "axios", "from": "1.4.0", "to": "1.6.8", "type": "patch", "notes": "修复 CSRF header 在重定向时丢失的问题；无 Breaking Change" },
  { "name": "@mtfe/mtd-react", "from": "3.5.2", "to": "3.6.0", "type": "minor", "notes": "Table 组件新增 virtual 属性" }
]
```

`type`：`major | minor | patch`；`notes` 可选，从依赖扫描结果提取，识别不到时省略。

## 执行

payload **必须通过临时文件传入**，直接传字符串会因代码片段中的引号、换行导致 shell 解析异常：

```bash
SKILL_DIR="<fe-ai-review skill 根目录>"
PAYLOAD_FILE=$(mktemp /tmp/cr_report_payload_XXXXXX.json)
cat > "$PAYLOAD_FILE" << 'ENDJSON'
{ ... }
ENDJSON
bash "$SKILL_DIR/scripts/report-submit.sh" "$PAYLOAD_FILE"
```

脚本会生成 `rule_id`、上报现有看板，并删除 `/tmp/` 下的 payload 文件。

上报成功时，从脚本输出中提取 id，在会话末尾附加一行报告地址：

```text
📊 CR 报告已上报：https://aicr.mynocode.host/#/reports/{id}
```

失败时附加：

```text
⚠️ CR 看板上报失败：<错误原因>（不影响本地报告）
```
