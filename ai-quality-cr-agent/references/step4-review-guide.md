# Step 4-Review 详细指南:P0/P1 二次复审

> 本文件是 SKILL.md Step 4-Review 的详细参考文档。SKILL.md 中只保留流程骨架,具体 prompt 模板、字段映射、边界情况在此文档中维护。

## 1. 子 Agent Task Prompt 模板

使用 `sessions_spawn` 启动子 Agent:

```
sessions_spawn(
  model="{REVIEW_MODEL}",  # 默认 "default"(同主流程模型),可在配置中覆盖
  task="你是 AI Code Review 的二次复审 Agent。请对以下 P0/P1 issue 进行独立复审。

输入文件:
- /tmp/cr_review_input_{prId}.json — 待复审的 P0/P1 issue 列表(仅含 file/line/ruleId/summary/severity)
- /tmp/pr_diff.txt — 全量 diff

复审规则:
1. 对每条 issue,读取 diff 中对应文件的代码,独立判断问题是否成立
2. 不参考任何已有的 description/risk/suggestion——你只看代码本身
3. 对每条 issue 给出 verdict(五选一):
   - CONFIRM:代码证据确凿,级别正确
   - ESCALATE:实际比标记的更严重(如 P1 实际应为 P0),给出目标 severity
   - DOWNGRADE:证据不足或已有保护,应降级(如 P0 应为 P2),给出目标 severity
   - DISMISS:误报,代码本身没有问题
   - OPEN_QUESTION:无法确定,需要人工确认。触发条件:
     a) 代码上下文不全,需要看完整文件才能判断
     b) 依赖外部状态(限流开关/降级配置/运行时参数)
     c) 业务语义模糊,技术上有风险但业务可能已有约定规避
     d) 级别存疑(确认有问题但不确定是 P0/P1/P2)
     e) 子 Agent 超时/异常未能完成分析

输出格式(JSON 数组,写入 /tmp/cr_review_verdict_{prId}.json):
[
  {
    \"ruleId\": \"CR:xxx\",
    \"file\": \"src/xxx.java\",
    \"line\": 42,
    \"verdict\": \"CONFIRM|ESCALATE|DOWNGRADE|DISMISS|OPEN_QUESTION\",
    \"targetSeverity\": \"P0|P1|P2|P3\",  // 仅 ESCALATE/DOWNGRADE 时填,其他为 null
    \"reason\": \"复审理由(≥2 句话)\",
    \"question\": \"\",  // 仅 OPEN_QUESTION 时填,说明存疑原因
    \"suggestedActions\": []  // 仅 OPEN_QUESTION 时填,人工确认方向
  }
]

⚠️ 重要:
- 宁可标 OPEN_QUESTION 也不要强行判断不确定的问题
- DISMISS 必须非常确定是误报(如:该行是注释、是测试代码、是 import 语句等)
- ESCALATE/DOWNGRADE 必须给出明确的 targetSeverity"
)
```

> ⚠️ **模型选择**:`REVIEW_MODEL` 变量在 Step 0C 配置,默认值 `default`(同主流程模型)。可在 `.cr-config.yaml` 或环境变量中覆盖为其他模型(如 `kubeplex-maas-saferoom/catclaw-proxy-model`)。使用不同模型可带来模型多样性,降低单一模型的系统性偏差。

## 1b. BL 类(source=step4d)证据核验规则(2026-10-29 起)

**原则:没有清晰证据的 BL 发现不得出现在 P0/P1。** BL 的证据链是结论的根基,与 CR/MT/CU 类不同,BL 复审不是「盲审重判」而是「核验证据」。

### 1b-1. q1 机械核验(主 Agent 在构造复审输入前执行)

对每条 BL P0/P1:
1. 从 `description` 提取「依据来源」行的 SDD 引用文本(逐字;多行多条全部提取)
2. 执行 SKILL.md Step 4-Review 执行步骤 1b 的固定模板 python3 命令:短引用(<15 字符)拒 + 归一化子串命中 + **逐行**匹配块占比≥0.8(防跨条目拼接/尾部夹带,证据必须命中单一 SDD 条目)
3. 引用归一化后不足 15 字符 → 视同 `NOT_FOUND`(防短句碰巧命中)
4. SDD 文件 `/tmp/cr_sdd_{prId}.md` 缺失/为空 → 该 PR 全部 BL P0/P1 直接降 `P2`,记 `bl_gate_reason: "sdd_missing"`

**处置(机器判定优先于模型判断,q1 不通过的条目不进子 Agent 复审,不消耗复审额度)**:

| q1 结果 | 处置 |
|---|---|
| `NOT_FOUND`(引用不命中/无 SDD 类引用/提取失败/引用过短) | 直接转 `severity=confirm`,补齐三字段:`confirm_reason`(注明「SDD 引用未在落盘中核验到原文」)/`possible_risk`(原 risk)/`confirm_suggestion`(建议人工核对 SDD 后定级),`preReviewSeverity` 记原级,`reviewVerdict: "BL_Q1_GATE"` |
| `FOUND` | 进入复审,构造 `bl_evidence_review` 块 |

### 1b-2. BL 复审输入构造

`cr_review_input_{prId}.json` 中 BL 类条目在 5 字段外追加:

```json
"bl_evidence_review": {
  "description_full": "(4-D 完整证据链四段式原文)",
  "q1": {"sdd_found": true, "ratio": 0.95},
  "sdd_file": "/tmp/cr_sdd_{prId}.md",
  "diff_file": "$CR_DIFF_FILE"
}
```

### 1b-3. BL 复审子 Agent prompt 追加段(仅当输入含 bl_evidence_review 块时追加到 task 模板后)

```
【BL 类 issue 复审规则(含 bl_evidence_review 字段的条目适用)】

你的任务不是重新发现业务问题,而是核验已有证据链:

Q2 预期推导成立性:
- description_full 中的引用,放回 sdd_file / diff_file 的完整上下文后,
  「预期行为→实际实现→差异」的推导是否仍然成立
- 重点核查三类断章取义:
  a) 引用点上游/调用方已有防御分支、兑底逻辑、开关包裹(如 @ConditionalOnProperty、降级开关、上游 null 检查)
  b) 引用点位于死代码、未启用路径、或被新 diff 即将删除的逻辑
  c) 跨方法/跨类拼接引用,语义被扭曲
Q3 差异事实性:
- issue 声称的「本次变更导致 XX 业务影响」,因果链是否与 diff_file 中该文件的实际 hunk 一致
- diff 里没有的变更不许出现在因果链里(凭空因果 = 失败)

判定约束:
- q1.sdd_found=false 的条目已被机械核验判定可疑,你的 CONFIRM 必须基于
  你自己在源文件中找到的替代证据,不得依赖 description 的叙述
- DOWNGRADE/DISMISS 必须给出具体反证:文件+行号+代码原文片段,
  并填入 refutation 字段;无具体反证的「证据不足」改用 OPEN_QUESTION
- 你可以读 sdd_file 和 diff_file(只读),禁止拉取仓库代码、禁止访问 ONES、禁止读 /tmp 之外的任何文件
- 你无法完成核验的条目,输出 OPEN_QUESTION,不要强行 CONFIRM

BL 条目输出额外字段:
  "q2_verdict": "PASS|FAIL|SKIP",
  "q3_verdict": "PASS|FAIL|SKIP",
  "refutation": "文件:行号 + 反证代码/文本(DOWNGRADE/DISMISS 时必填)"
```

### 1b-4. BL verdict 处理增强(叠加到第 2 节处理表)

| Verdict | BL 附加处理 |
|---|---|
| **CONFIRM** | q2/q3 任一 FAIL 却 CONFIRM → 审计记 `review_flag: "confirm_despite_refutation"` |
| **ESCALATE** | BL 类禁止 ESCALATE(升级=提高置信主张,必须先过清晰证据线);遇到一律按 CONFIRM 处理并记 `review_flag: "escalate_blocked_bl"` |
| **DOWNGRADE/DISMISS** | 无 refutation 具体反证 → 按 OPEN_QUESTION 处理(转 confirm),不执行降级/删除 |
| **OPEN_QUESTION** | 照常转 confirm;confirm_reason 优先引用 q2/q3 失败原因 |
| **BL_Q1_GATE**(主 Agent 侧) | 见 1b-1,不进子 Agent |

### 1b-5. BL 兑底矩阵(与第 4 节边界情况叠加,按类区分)

| 异常 | CR/MT/CU/L2/FE | BL(source=step4d) |
|---|---|---|
| 子 Agent 超时/失败 | 默认 CONFIRM(不变) | **转 confirm** + `confirm_reason: "BL 复审未完成,证据未核验"` + possible_risk/confirm_suggestion 照补 |
| 格式异常/无 verdict | 默认 CONFIRM(不变) | **转 confirm**(同上) |
| BL P0+P1 >5 条 | — | 审计标 `bl_budget_flag: true`,播报加注「BL 数量超预算,关注批量话术模式」 |

### 1b-6. 审计文件增强

`/tmp/cr_review_result_{prId}.json` 每条 BL 记录增加:`q1`(含 ratio)/`q2_verdict`/`q3_verdict`/`refutation`/`review_flag`/`bl_gate_reason`。这些字段是 BL 误报治理的度量原始数据源。

## 2. Verdict 处理表

子 Agent 返回后,主 Agent 读取 `/tmp/cr_review_verdict_{prId}.json`,对每条 P0/P1 issue 按 verdict 处理:

| Verdict | 处理方式 | step4.json 变更 |
|---------|---------|----------------|
| **CONFIRM** | 保留原样 | issue 新增 `reviewVerdict: "CONFIRM"` + `reviewNote` 字段 |
| **ESCALATE** | 提升严重度 | 修改 `severity` 为 targetSeverity,原值记入 `preReviewSeverity`,新增 `reviewVerdict: "ESCALATE"` + `reviewNote`(BL 类例外见 1b-4:禁止 ESCALATE,按 CONFIRM 处理) |
| **DOWNGRADE** | 降低严重度 | 修改 `severity` 为 targetSeverity,原值记入 `preReviewSeverity`,新增 `reviewVerdict: "DOWNGRADE"` + `reviewNote`(BL 类须附 refutation 反证,否则按 OPEN_QUESTION) |
| **DISMISS** | 从结果中删除 | **从 step4.json 中物理删除该 issue**,完整记录到审计文件(BL 类须附 refutation 反证,否则按 OPEN_QUESTION) |
| **OPEN_QUESTION** | 转为待确认问题 | `severity` 改为 `confirm`,原值记入 `preReviewSeverity`,新增 `reviewVerdict: "OPEN_QUESTION"` + `reviewNote` + `confirm_reason`(=复审存疑原因) + `possible_risk`(=原 issue 的 risk) + `confirm_suggestion`(=复审建议方向)。归入「🔎 待人工确认」展示路径,不参与 P0-P3 编号 |
| **BL_Q1_GATE** | (仅 BL 类,主 Agent 机械核验触发,不进子 Agent) | `severity` 改为 `confirm`,原值记入 `preReviewSeverity`,补齐三字段,见 1b-1 |

### 结论计数规则

`severity=confirm` 的 issue 不参与 P0-P3 编号（与现有 confirm 机制一致）。其余 issue 按 severity 计数推导结论(✅/💚/🟠/🔴)。

### OPEN_QUESTION → confirm 字段映射

| 复审输出字段 | 写入 step4.json 字段 | 说明 |
|-------------|---------------------|------|
| `question` | `confirm_reason` | 存疑原因 |
| 原 issue 的 `risk` | `possible_risk` | 原始风险描述 |
| `suggestedActions` 拼接 | `confirm_suggestion` | 建议确认方向,多条用 `;` 拼接 |

> 转为 confirm 后自动归入现有「🔎 待人工确认」展示路径（第四章 Review 发现的子节），无需单独输出文件。

## 3. 审计文件格式

将所有 verdict 记录(含被删除的 DISMISS issue 完整信息)写入 `/tmp/cr_review_result_{prId}.json`:

```json
[
  {
    "originalIssue": {
      "severity": "P0",
      "ruleId": "CR:P0-001",
      "file": "src/SkuService.java",
      "line": 42,
      "summary": "空指针风险:getSkuList()返回值未判空"
    },
    "verdict": "DOWNGRADE",
    "targetSeverity": "P2",
    "reason": "外层已有 Optional.ofNullable 包装,触达路径被阻断",
    "reviewer": "subagent",
    "timestamp": "2026-08-06T22:08:00+08:00"
  }
]
```

## 4. 边界情况

| 场景 | 处理 |
|------|------|
| 子 Agent 超时/失败 | CR/MT/CU/L2/FE 类默认 `CONFIRM`(宁可信其有);BL(source=step4d)类转 `confirm`(见 1b-5) |
| 子 Agent 返回格式异常 | 主 Agent 记录错误,该条 issue 默认 `CONFIRM`(BL 类转 confirm,见 1b-5) |
| 子 Agent 对某条 issue 未返回 verdict | 该条 issue 默认 `CONFIRM`(BL 类转 confirm) |
| 所有 P0/P1 都被 DISMISS | step4.json 只剩 P2/P3,结论变为 💚或✅ |
| 所有 P0/P1 都标 OPEN_QUESTION | P0/P1 计数为 0,全部转为 confirm,结论按 P2/P3 推导(可能是✅或💚);「待确认问题」子节列出所有存疑项 |
| 复审后仍有 P0(CONFIRM/ESCALATE) | 流程继续,结论 🟠/🔴,正常发布(BL 类的 ESCALATE 已被 1b-4 拦截) |
