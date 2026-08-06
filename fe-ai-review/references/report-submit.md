# CR 看板上报

Step 8 执行的上报动作：把本次 CR 结果写入 [AI CR 看板](https://aicr.mynocode.host)。

> 接口文档：https://aicr.mynocode.host/#/api-doc

- **默认启用**：Step 6 报告产出后，尽量作为后台 subagent 静默执行，不打断主会话
- **跳过**：用户说「不要上报」「不上报看板」时跳过
- **失败**：在会话末尾静默附加一行提示，不阻塞

## 字段来源

### 必填

| 字段 | 来源 |
|---|---|
| `operator` | 上下文中如有 misId 则直接使用；尝试 `git config user.email` 取 `@` 前缀；失败则用 `git config user.name`；仍失败留空 |
| `repo` | `git remote get-url origin` 末段路径，去掉 `.git` 后缀 |
| `branch` | `git branch --show-current` |
| `review_mode` | 路由时已知：`local` 或 `pr-only` |
| `tech_stack` | 技术栈识别结果，多值英文逗号拼接如 `"max,mrn"`；识别不出填 `"others"` |
| `review_depth` | 用户说"快速过一遍" → `quick`；其余 → `deep` |
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
| `change_summary` | 报告变更摘要要点，转为 `string[]`，建议 `"类型: 描述"` 格式。第一条放最能代表本次变更意图的摘要，其余按重要性递减，chore/纯技术类放最后 |
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

无问题时传空结构：

```json
{ "p0": [], "p1": [], "p2p3": [], "openQuestions": [] }
```

有发现项时每条格式（`confidence` P2-P3 可选；`code_context` 可选，P0/P1 优先填，截取 1~3 行关键变更；`rule_ids` 可选，0~n 个，见下方说明）：

```json
{
  "p0": [{
    "level": "P0", "type": "空值未处理",
    "path": "src/pages/checkout/index.jsx:L45",
    "reason": "order.items 在接口异常时可能为 null",
    "suggestion": "增加空值保护：(order.items ?? []).map(...)",
    "confidence": "高",
    "rule_ids": ["R29"],
    "code_context": {
      "lang": "jsx",
      "before": "const items = order.items.map((x) => <Item key={x.id} data={x} />);",
      "after": "const items = (order.items ?? []).map((x) => <Item key={x.id} data={x} />);"
    }
  }],
  "p1": [], "p2p3": [],
  "openQuestions": ["handleRetry 最大重试次数是否与后端约定一致？"]
}
```

`rule_ids`：命中的规则库条目编号数组，取自 `general-rules.md`（`R01`~）/ `trade-rules.md`（`T01`~）/ `stack/*.md`（`MRN01`~、`MAX01`~、`DUO01`~ 等）已有编号，不新建编号体系。一条问题可命中 0 个（纯上下文/业务逻辑判断，没有对应规则）到多个规则；无命中时省略该字段或传空数组，不得编造编号。

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

脚本读完文件后会自动删除 `/tmp/` 下的临时文件，无需手动清理。

上报成功时，从脚本输出中提取 id，在会话末尾附加一行报告地址：

```
📊 CR 报告已上报：https://aicr.mynocode.host/#/reports/{id}
```

失败时附加：

```
⚠️ CR 看板上报失败：<错误原因>（不影响本地报告）
```
