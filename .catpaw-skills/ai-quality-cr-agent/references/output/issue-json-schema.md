# 统一 Issue JSON 格式(Step 4-A + Step 4-B + Step 4-C + Step 4-D + Step 4-Merge 共用)

> 🚨 **强制**:所有审查来源（Step 4-A/B/C/D、合并和前端委托）的每一条问题都必须以本格式写入临时 JSON 文件。所有报告文档 / PR 评论 / 大象推送文案均由 `scripts/publish_results.py` 从 JSON 自动拼装。

## 1. 文件命名与存放

| 来源 | 文件路径 | 说明 |
|------|---------|------|
| Step 4-A 四层审查 | `/tmp/cr_issues_{prId}_step4a.json` | 主 Agent 把 P0/P1/P2/P3 全部 findings 写入此文件 |
| Step 4-B 子 Agent | `/tmp/cr_issues_{prId}_step4b.json` | 主 Agent 汇总已启动的子 Agent 结果写入此文件 |
| Step 4-C 自定义规则 | `/tmp/cr_issues_{prId}_step4c.json` | 子 Agent 检出自定义规则违规写入此文件 |
| Step 4-D 业务逻辑审查 | `/tmp/cr_issues_{prId}_step4d.json` | 子 Agent 检出业务逻辑问题写入此文件 |
| Step 4-Merge 合并后 | `/tmp/cr_issues_{prId}_step4.json` | 主 Agent 合并去重后产出统一 JSON,Step 7 唯一 issues 输入 |
| 前端委托 | `/tmp/cr_issues_{prId}_step4.json` | 将 fe-ai-review 的发现转换为统一格式；混合审查时与后端发现一起合并 |

每个文件内容为一个 **JSON 数组**,元素为本 schema 定义的 issue 对象。无问题时写 `[]`。

### 1.1. 序列化和公共校验门禁（强制）

使用 `json.dump(issues, file, ensure_ascii=False, allow_nan=False)` 或 `JSON.stringify(issues)` 序列化内存中的对象，禁止用字符串拼接或手工插值构造 JSON。描述和建议可以保留真实代码中的双引号、反引号、反斜杠和换行，由序列化器负责转义。Markdown 反引号不能替代 JSON 转义，禁止通过改写代码或删除双引号绕过校验。

每个阶段写完 issues 文件后，以及调用发布器前，必须执行公共门禁：

```bash
python3 "${SKILL_DIR}/scripts/issue_io.py" "/tmp/cr_issues_${PR_ID}_step4.json"
```

门禁同时检查 JSON 语法、数组结构、每条对象的必填字段和类型、严重级别、来源与规则前缀、行号/行类型、P0/P1 触达证据和待确认字段。`python3 -m json.tool` 只能检查语法，不能代替此门禁。门禁失败必须定位并重新序列化文件，校验通过后才能发布；禁止删除报错的问题、跳过损坏文件、替换成 `[]` 或报告“通过”。发布器公共入口会再次执行同一校验，前端委托也必须经过。

- 显式 `[]` 是合法的无发现结果；输入路径缺失、不可读文件、坏 JSON、重复 JSON 字段、非数组、非对象或任一不合规 issue 都使整个批次失败。
- `severity` 必须是单个 `P0` / `P1` / `P2` / `P3` / `confirm`。`P2-P3`、范围、自由文本等必须由上游根据证据逐条定级或拆分为独立发现，禁止猜测级别或静默丢弃。
- 校验器规范化级别大小写、行类型大小写及规则编号首尾空白，不修补错误 JSON，不凭空补充问题证据。

## 2. Issue 对象字段

```json
{
  "severity": "P0",
  "ruleId": "CR:NullPointerException",
  "anomalyType": "空指针异常",
  "summary": "RPC 返回值未判空直接拆箱,可能导致 NPE",
  "file": "src/main/java/com/example/PriceService.java",
  "line": 42,
  "lineType": "ADDED",
  "description": "priceService.getPrice() 返回 Integer,调用点直接赋值给 int 拆箱;getPrice 在券后价为空时返回 null,拆箱触发 NPE。调用链上无 try-catch 保护。",
  "risk": "券后价为空的订单请求会触发 500 错误,影响交易下单链路,日均约 X 单受影响。",
  "suggestion": "赋值前判空并给默认值:\n```java\nInteger price = priceService.getPrice();\nint finalPrice = price != null ? price : 0;\n```",
  "code": "Integer price = priceService.getPrice();\nint finalPrice = price;  // 拆箱 NPE",
  "source": "step4a",
  "ruleName": "",
  "ruleFile": "",
  "reach_analysis": "getPrice() 被 OrderService.createOrder 调用,券后价为空时触发 NPE,无 try-catch 保护",
  "online_scenario": "用户下单时使用优惠券,券后价计算返回 null,日均约 X 单受影响",
  "impact_scope": "交易下单链路全量受影响,涉及订单创建、支付、履约"
}
```

### 待确认问题示例

```json
{
  "severity": "confirm",
  "ruleId": "CR:UncertainException",
  "anomalyType": "待确认",
  "summary": "RPC 调用是否已有外层异常兜底",
  "file": "src/main/java/com/example/OrderService.java",
  "line": 88,
  "lineType": "ADDED",
  "description": "createOrder 方法调用 priceService.getPrice(),但无法确定所有调用路径是否有外层异常兜底。",
  "risk": "若外层无保护,则可能导致下单接口 500。",
  "suggestion": "请人工确认调用链上下游异常处理策略。",
  "source": "step4a",
  "ruleName": "",
  "ruleFile": "",
  "confirm_reason": "无法确定该 RPC 是否在所有调用路径都有外层 try-catch 保护",
  "possible_risk": "若外层无保护,则会导致 500 错误影响下单",
  "confirm_suggestion": "请确认 OrderService.createOrder 外层是否有异常兜底逻辑"
}
```

### 字段说明（11 个基础必填字段，其他字段按来源和 severity 条件必填）

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `severity` | ✅ | 最终严重级别：`P0` / `P1` / `P2` / `P3` / `confirm`。Step 4-B 子 Agent 按信号路由表 `默认 P 级别` 列定级。Step 4-D 子 Agent 按证据链置信度定级。`confirm` 表示待确认问题，不参与 P0-P3 编号 | `P0` |
| `ruleId` | ✅ | 规则编号,**必须与 checklist / 规则库中的规则条目精确对应**；L3 规则文件没有定义 ID 时允许使用约定的 `FE:L3_custom` 兜底。Step 4-A 用 `CR:`;Step 4-B 用规则文件中的 `MT:`（如 `MT:java-l1:JAVA-05.N001`）;Step 4-C 用仓库规则中的 `CU:`;Step 4-D 用 `BL:`。前端委托结果由主 Agent 转换阶段加 `FE:`，脚本幂等兜底：平台 `fe-l1:` / `fe-l2:` 命名空间先去掉，普通规则使用真实编号，L3 规则优先使用规则文件 ID（`FE:L3_<id>`）；纯上下文判断没有规则编号时允许空字符串 `""`。字段本身不可缺失。合并规则使用 ` + ` 连接，至少一个前缀必须与 `source` 对应 | `CR:NullPointerException` / `FE:ASYNC-001` / `FE:L3_order-detail` |
| `anomalyType` | ✅ | 异常类型 / 规则类别。P0/P1 填异常类型(`空指针异常`、`并发问题`);P2/P3 填规则类别(`命名规范`、`日志规范`);`confirm` 填 `待确认` | `空指针异常` |
| `summary` | ✅ | 一句话概括(标题),≤30 字,不带规则编号前缀 | `RPC 返回值未判空直接拆箱` |
| `file` | ✅ | 文件完整路径(diff 中的新文件路径) | `src/main/java/.../PriceService.java` |
| `line` | ✅ | 大于 0 的整数，禁止字符串、布尔值或 0；`ADDED` 对应新文件行号 dstN，`REMOVED` 对应旧文件行号 srcN | `42` |
| `lineType` | ✅ | `ADDED` / `REMOVED`,用于 PR 行内评论锚定。Git diff 中"修改一行"= REMOVED+ADDED 一对,服务端 segment 枚举无 `MODIFIED`,**禁止填 `MODIFIED`**(会触发 `illegal segment type` 报错);指向改后新行用 `ADDED`(line 填新文件行号 dstN),指向被删老行用 `REMOVED`(line 填老文件行号 srcN) | `ADDED` |
| `description` | ✅ | 问题描述:命中了什么规则、为什么违反、判定依据(≥2 句话,禁止"可能""建议确认"等模糊措辞) | - |
| `risk` | ✅ | 风险/后果:什么场景触发、影响什么业务、影响范围(≥1 句话实质内容) | - |
| `suggestion` | ✅ | 修复建议:**必须包含具体修复代码示例**,禁止只写"建议修改""请优化" | - |
| `code` | 选填 | 问题代码片段(3-5 行含上下文),用于文档展示;无则省略 | - |
| `source` | ✅ | 来源标记:`step4a` / `step4b` / `step4c` / `step4d` / `fe-ai-review`。**仅内部用于校验和统计,不出现在最终报告中** | `step4a` |
| `ruleName` | step4b/step4c 必填 | 规则名称(Step 4-B 子 Agent 填(仅启动的子 Agent),Step 4-C 子 Agent 填,Step 4-A 留空) | `并发处理规范-R03` |
| `ruleFile` | step4b/step4c 必填 | 规则来源文件名(Step 4-B 子 Agent 填,Step 4-C 子 Agent 填) | `JAVA-04-并发处理规范.md` |
| `rule_sources` | FE 必填 | 原样保留全部命中来源；纯上下文填 `[]`。每项必填 `source_type`、`scope_level`、`file`；平台/fallback 必须保留 `upstream_rule_id`，L3 无明确 ID 时允许省略 | `[{"source_type":"project","scope_level":"L3","file":".fed/order.md","upstream_rule_id":"ORDER-API-01"}]` |
| `reach_analysis` | P0/P1 必填 | 触达分析:调用链与触发条件,说明问题如何触达线上逻辑 | `getPrice() 被 OrderService.createOrder 调用,券后价为空时触发 NPE,无 try-catch 保护` |
| `online_scenario` | P0/P1 必填 | 线上场景:实际业务场景描述 | `用户下单时使用优惠券,券后价计算返回 null,日均约 X 单受影响` |
| `impact_scope` | P0/P1 必填 | 影响范围:波及面评估 | `交易下单链路全量受影响,涉及订单创建、支付、履约` |
| `confirm_reason` | confirm 必填 | 不确定原因:为什么 AI 无法判定此问题 | `无法确定该 RPC 是否在所有调用路径都有外层 try-catch 保护` |
| `possible_risk` | confirm 必填 | 可能的风险:如果确实是问题的后果 | `若外层无保护,则会导致 500 错误影响下单` |
| `confirm_suggestion` | confirm 必填 | 确认建议:人工确认方向 | `请确认 OrderService.createOrder 外层是否有异常兜底逻辑` |
| `mergedRuleIds` | 合并时选填 | 当多条 CR:/MT: 规则合并为一条 issue 时,记录所有被合并的规则编号 | `["CR:NP-01", "MT:java-l1:JAVA-05.N002"]` |
| `reviewVerdict` | Step 4-Review 选填 | 二次复审结论:`CONFIRM` / `ESCALATE` / `DOWNGRADE` / `DISMISS` / `OPEN_QUESTION`。仅 P0/P1 issue 经复审后存在此字段。`OPEN_QUESTION` 时 severity 同步改为 `confirm` | `CONFIRM` |
| `reviewNote` | Step 4-Review 选填 | 复审理由,≥2 句话 | `外层已有 try-catch 保护,触达路径被阻断` |
| `preReviewSeverity` | Step 4-Review 选填 | 复审前的原始 severity(仅 ESCALATE/DOWNGRADE/OPEN_QUESTION 时存在) | `P0` |

除 `line`（整数）、`mergedRuleIds`（非空字符串数组）和 `rule_sources`（对象数组）外，表内字段均为字符串。必填文本不得为空或仅有空白，只有 `source=step4a` 或 `source=fe-ai-review` 的纯上下文 finding 的 `ruleId` 允许为空；FE 规则命中不得丢失 `rule_sources`。原生通用审查使用 `step4a`，无规则编号仍需完整代码证据、合法位置及相应级别的必填字段，P0/P1 照常复查。选填文本如出现也必须是字符串。`ruleName` / `ruleFile` 在 `step4b` / `step4c` 下不得为空。`mergedRuleIds` 非空时必须与 `ruleId` 中列出的编号一致。此结构校验不会验证外部规则库中是否真实存在规则，审查 Agent 仍须核对规则来源。

前端编号按 ` + ` 分段；每段允许字母、数字及 `._:/-`。FE 编号以 `rule_sources` 为准，原 `ruleId` 仅保留非 FE 前缀；`mergedRuleIds` 如提供，按最终编号列表重建，来源保留原值。发布时规则字段校验失败会告警并保留问题及原始字段，不改变严重度；校验 CLI 仍返回失败，便于修正输入。

## 3. Step 4-B 严重级别映射（强制）

Step 4-B 子 Agent 检出问题时，**严格按信号路由表(`references/signal-routing-table.md`)中对应信号的 `默认 P 级别` 列定级**：

| 信号路由表 `默认 P 级别` | severity 映射 |
|---------------------------|------------------|
| 纯 `P2`（如 SIG-CONSTANT、SIG-COLLECTION、SIG-OOP、SIG-TEST、SIG-DEPENDENCY） | 该信号下所有规则一律 `P2` |
| 含 P0 范围（如 `P0(强制)→P2`） | 逐条判断规则的实际线上影响，决定 `P0` 或 `P2` |
| `P0/P1`（如 SIG-SECURITY、SIG-NPE） | 按具体规则影响判断 `P0`、`P1` 或 `P2` |
| `P1→P2`（如 SIG-CACHE、SIG-RPC） | 逐条判断，决定 `P1` 或 `P2` |

> ⚠️ **禁止仅因规则正文出现「强制」「禁止」等措辞就一律判 P0**。必须以信号路由表的级别定义为准。

## 3.5. Step 4-C 严重级别映射（强制）

Step 4-C 子 Agent 读取自定义规则文件时，按规则文件中的严重级别标注映射 `severity`：

| 规则标注 | severity |
|---------|----------|
| P0 / 零容忍 | `P0` |
| 建议 / 推荐 | `P2` |
| 其它(未标注) | `P3` |

> ⚠️ 自定义规则不限制语言,不限于 Java。

## 3.6. Step 4-D 严重级别映射（强制）

Step 4-D 子 Agent 检出问题时，按证据链置信度定级：

| 依据组合 | 置信度 | severity |
|---------|--------|----------|
| SDD + 需求 + 上下文 三者一致指向问题 | 高 | `P0` / `P1` |
| 两个来源一致指向 | 中 | `P1` / `P2` |
| 仅单一来源推断 | 低 | `confirm`（人工复审） |
| 无依据 | — | 禁止输出 |

> ⚠️ **禁止输出无依据的推断**。每条 finding 必须包含明确的证据链（依据来源 + 预期行为 + 实际实现 + 差异分析）。

## 4. 文案模板(脚本自动拼装,禁止手写)

`publish_results.py` 读取上述 JSON 后,每条 issue 按以下模板拼装到学城文档「四、Review 发现」章节(按 severity 分组、组内编号;每条问题独立展示)。

**P0/P1 文案模板(含触达分析等七字段):**

```
**🔴 [P0-01] [{ruleId}] {anomalyType} - {summary}**
- **文件**:`{file}` L{line}
- **问题代码**:
```java
{code}
```
- **检出原因**:{description}
- **触达分析**:{reach_analysis}
- **线上场景**:{online_scenario}
- **影响范围**:{impact_scope}
- **修复建议**:
```java
{suggestion}
```
```

**P2/P3 文案模板(简洁版):**

```
**🟡 [P2-01] [{ruleId}] {summary}**
- **文件**:`{file}` L{line}
- **问题描述**:{description}
- **检出原因**:{risk}
- **规范要求**:{ruleName}
- **修复建议**:{suggestion}
```

**待确认问题文案模板:**

```
**🔎 待人工确认 [Q-01] {summary}**
- **文件**:`{file}` L{line}
- **问题描述**:{description}
- **不确定原因**:{confirm_reason}
- **可能的风险**:{possible_risk}
- **请确认**:{confirm_suggestion}
```

- 报告中 **不区分 Step 4-A / Step 4-B 来源**,所有 issue 统一按 P0 → P1 → P2 → P3 → 待确认 顺序排列,组内编号 `[P0-1] [P0-2] [P1-1] ... [Q-1] ...`。
- `source` / `ruleName` / `ruleFile` 不出现在文案中(`ruleName`/`ruleFile` 仅在 PR 行内评论末尾追加可追溯信息时使用)。
- `severity=confirm` 的 issue 归入「🔎 待人工确认」小节,不参与 P0-P3 编号。
- P0/P1 的 `reach_analysis` / `online_scenario` / `impact_scope` 缺失或为空时，校验失败并阻止发布。`confirm` 的三个确认字段执行相同要求。
- 主流程或前端纯上下文判断的空 `ruleId` 仍独立展示，并计入“无规则标注”统计；前端命中 L3 规则但文件没有规则 ID 时使用 `FE:L3_custom`，不能因没有规则编号省略该问题。

## 5. 规则合并去重规则

当 Step 4-A 的 `CR:` 规则与 Step 4-B 的 `MT:` 规则、Step 4-C 的 `CU:` 规则、Step 4-D 的 `BL:` 规则存在重叠时,由 Step 4-Merge 按以下策略处理:

| 场景 | 处理方式 | ruleId 格式 |
|------|---------|------------|
| 完全重叠(同一代码行 + 同一问题本质) | 合并为一条 issue | `CR:xxx + MT:yyy + CU:zzz` |
| 部分重叠(同一异常类型但覆盖范围不同) | 各自独立报,不合并 | 各自原样 |
| 仅命中 CR: / MT: / CU: / BL: | 不合并 | 原样 |
| Step 4-D 与 4-A/4-B/4-C 命中同一 file+line+同类问题 | 位置和类别不足以证明重复；先核对触发条件、根因和影响。确为同一问题才合并，保留最高严重级别与完整证据 | 保留最终所选来源对应的真实规则编号 |

合并后的 issue:
- `ruleId` 字段:`CR:xxx + MT:yyy` 或 `CR:xxx + MT:yyy + CU:zzz`(加号连接,CR: 在前 MT: 在后 CU: 在最后)
- `mergedRuleIds` 字段:`["CR:xxx", "MT:yyy"]` 或 `["CR:xxx", "MT:yyy", "CU:zzz"]`(数组,方便统计)
- 语义合并必须基于同一根因、触发条件和影响，保留最高严重级别与对应的完整触达证据，不能按输入顺序保留第一条。
- 发布器只在规范化后除 `severity` 外**所有字段完全相同**时去重，并保留最高严重级别；同位置、同规则但描述/证据/风险不同的发现全部保留。空 `ruleId` 采用同一保守策略，禁止按 `file+line+ruleId` 碰撞合并。
- 统计时 `ruleId` 为 `CR:xxx + MT:yyy + CU:zzz` 的,CR: 和 MT: 和 CU: 各计一次命中
- Step 4-D 的 `BL:` 发现没有充分证据证明与其他发现重复时独立保留；合并不能使其更高严重级别或业务证据丢失。
