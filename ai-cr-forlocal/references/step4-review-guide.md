# Step 4-Review：P0/P1 二次复审 + 漏报扫描指南（forlocal：错报过滤 + 检出宽度并重）

> **定位（与 ai-quality-cr-agent 的差异）**：
> - agent 版（公众号场景）：复审只做降误报，DISMISS 无门槛直接删除
> - forlocal 版（本地场景）：**错报过滤与检出宽度并重**——
>   1. 高置信误报要过滤（有明确代码证据才 dismiss，减少 confirm 噪音）
>   2. 拿不准的不硬删（转 confirm 留人工，宁可人工筛不愿漏）
>   3. 反向扫描漏报（检出全貌），疑似漏报转 confirm
>   4. 所有 dismiss 可追溯（审计记录 + 文档附录），人工可翻案

## 触发条件
合并去重后（Step 4-Merge 之后）：
- P0 + P1 ≥ 3 → 触发二次复审
- P0 + P1 ≤ 2 → **跳过机器复审**，报告标注「未机器复审（P0/P1≤2），建议人工复核该 N 条」，直接进 Step 5
  （4-D 证据链定级门槛已保证小额高置信；复审边际价值低——实测小额 P1 复审结论几乎不改变）

## 复审双重目标
1. **错报过滤**：已检出的 P0/P1 中，高置信误报剔除（须证据），低置信存疑标记（不剔除）
2. **检出宽度**：反向扫描漏报——高风险信号是否全部被四路审查覆盖，未覆盖文件是否存在明显遗漏

## 执行方式（预处理注入 + 规模分流）

**第 0 步·预处理（主 Agent 执行，子 Agent 零 diff 读取）**：

```bash
python3 "$SKILL_ROOT/scripts/prep_review_input.py" --repo "$REPO_NAME"   --repo-path "$REPO_PATH"   --diff /tmp/local_cr_diff.txt --issues /tmp/cr_issues_${REPO_NAME}_step4.json   --signals /tmp/cr_signals_${REPO_NAME}.md --skill-root "$SKILL_ROOT"
```

产出四个文件：
- `/tmp/cr_review_input_{repo}.json` — 第一轮输入：每条 P0/P1 的 5 字段 + **预切好的 ±30 行代码上下文**（context 字段）
- `/tmp/cr_review_miss_{repo}.json` — 第二轮输入：未覆盖文件的 diff hunks（每文件截 120 行）
- `/tmp/cr_review_rules_{repo}.md` — 涉及规则文件合集（distinct ruleId 去重，去前缀匹配 checklists/）
- `/tmp/cr_review_meta_{repo}.json` — 分流判定：`mode=small|large` + large 时的按文件分片方案（k≤4）

**规模分流**：
- `small`（P0+P1 ≤ 8 且文件 ≤ 3）→ spawn 1 个子 Agent 串行两轮（输入/规则/未覆盖全量注入）
- `large` → 第一轮按 file 分片 spawn ≤4 个子 Agent 并行（同文件 issue 同片）；第二轮漏报扫描独立子 Agent **同时 spawn**（输入互不依赖）；主 Agent yield 汇合统一后处理，漏报与 dismiss 的 file+line 重叠项丢弃
- 所有复审子 Agent `runTimeoutSeconds=1200`（V118 统一）；spawn 时 `attachments` 注入：该片 input JSON 分片 + 规则合集 + （仅漏报 Agent）未覆盖 hunks

### 第一轮：P0/P1 准确性验证（错报过滤）

#### 子 Agent 输入（每条 P0/P1 issue 给 5 字段 + context，已由预处理注入）：
- file: 文件路径
- line: 行号
- ruleId: 规则 ID
- severity: P0 或 P1
- summary: 一句话摘要（不给完整的 description/risk/suggestion）
- context: 该行 ±30 行 diff 上下文（预处理已切好，**子 Agent 不再读 diff 文件**）

#### 子 Agent 任务（零仓库读取 + 三态判定）：
1. **只看注入**：context（diff ±30 行，文件不在 diff 时已由预处理预读仓库源码注入）+ 规则合集。**禁止读取任何仓库文件/diff 文件**——上下文不足以判定时直接给 `to_human`，不追代码（复审是「拿现成证据做判定」，不是二次审查；追代码验证是 4-D 的职责，复审追代码会与 4-D 重复劳动）
2. 规则文件已在 attachments 注入（`/tmp/cr_review_rules_{repo}.md` 合集），不重复读取
3. verdict 文件用文件写入工具一次性直写（禁止 `echo`/`tee`/`mv`/`python -c` 校验等终端命令——CatPaw 中会触发用户审批中断流程）
4. 独立判断（不看原 issue 的 description/risk/suggestion，避免锚定效应），verdict 三种：
   - ✅ **confirmed**：问题确实存在。原 severity 基本合理（确有升降级必要可标 confirmed 并在 reason 附注建议级别，不再单列 escalate/downgrade）
   - ❌ **dismissed**：**高置信误报**——必须满足证据门槛（见下），severity 转为 `dismissed`（保留记录，可追溯，不进主 findings）
   - ❓ **to_human**：上下文不足或拿不准（含原 suspect/open_question 场景）→ severity 转 `confirm` 留人工判断

#### DISMISS 证据门槛（强制，缺一不可）：
1. reason 中必须引用**具体代码证据**（如 "diff L42 已有 null check" / "该 catch 块内有 log.error 且向上抛出" / "该字段仅在测试代码使用"）
2. 证据类型限定三种之一：
   - **已有防护**：代码中存在有效防护措施（null 检查/幂等/重试/兜底）
   - **规则不适用**：规则明确的排除场景（如规则只管线上代码，该处是测试代码）
   - **路径不可达**：该代码路径在线上不可达（配置恒为 false / 死代码）
3. 只凭"感觉不对"、"理论上是误报"、"大概率没问题"→ 只能给 SUSPECT，禁止 DISMISS

### 第二轮：漏报扫描（检出宽度）

#### 子 Agent 输入（已由预处理注入，large 模式下独立 spawn 与第一轮并行）：
- 未覆盖文件 hunks：`/tmp/cr_review_miss_{repo}.json`（预处理已切好，**子 Agent 不再读 diff 文件**）
- 活跃信号清单：`/tmp/cr_signals_{repo}.md`（attachments 注入）
- 已检出 issue 清单摘要：主 Agent 在 task 中给 file+ruleId+severity 列表

#### 子 Agent 任务：
1. 逐个未覆盖文件的注入 hunks 扫描高风险模式：NPE 风险、资源未关闭、并发问题、SQL 拼接、硬编码、空 catch、事务边界
2. 对照 ACTIVE_SIGNALS：命中的信号类别是否都有对应 issue（如 SIG-SQL 命中但无任何 DB 类 issue → 疑似漏检）
4. 输出疑似漏报清单（`missed_candidates`），每条含：file、line、pattern、reason
5. **克制原则**：只报有明确代码证据的疑似漏报（pattern 命中 + 上下文可疑），不猜测、不遍历全部规则

#### 漏报结果处理：
- 疑似漏报 → 新增 issue，`severity=confirm`（不直接给高严重级，留人工判断）
- `source=review`，`ruleId` 按实际命中的规则填：主 Agent 审查范围（P0/P1/P3）命中用 `CR:` 前缀（如 `CR:NumberFormatException`、`CR:EH-01`、`CR:DB-01`）；4-B 规范范围命中用 `MT:` 前缀（如 `MT:java-l1:JAVA-05.N006`）
- description 前缀 `[复审漏报]`，说明复审来源

### 复审结果 JSON 格式：
```json
{
  "reviews": [
    {
      "original_severity": "P0",
      "ruleId": "HA-03",
      "file": "src/Main.java",
      "line": 42,
      "verdict": "confirmed|dismissed|to_human",
      "new_severity": "P0|P1|P2|dismissed|confirm|null",
      "reason": "复审理由（DISMISS 必须含具体代码证据）"
    }
  ],
  "missed_candidates": [
    {
      "file": "src/Other.java",
      "line": 88,
      "pattern": "empty-catch",
      "reason": "未覆盖文件中存在空 catch 且无日志",
      "ruleId": "CR:NumberFormatException"
    }
  ]
}
```

## 主 Agent 后处理
1. 读取 `/tmp/cr_review_verdict_{repo}.json`
2. 第一轮（错报过滤）按 verdict 处理 issue：
   - **CONFIRM**：保留原 issue 不变
   - **ESCALATE**：修改 severity 字段（如 P1→P0）
   - **DOWNGRADE**：修改 severity 字段（如 P0→P1 或 P1→P2）
   - **DISMISS**：severity 改为 `dismissed`，description 前缀 `[复审移除: {reason}]`——**不删除记录**，进文档附录可追溯
   - **SUSPECT**：转为 `severity=confirm`，description 前缀 `[复审疑似误报: {reason}]`
   - **to_human**：转为 `severity=confirm`，复用现有待确认问题机制（suspect/open_question 已合并入此态）
3. 第二轮（漏报扫描）：
   - `missed_candidates` 每条转为新 issue（`severity=confirm`，`source=review`，description 前缀 `[复审漏报]`）
   - 追加到 issues 列表
4. 更新 `/tmp/cr_issues_{repo}_step4.json`（合并后的统一 JSON）
5. 审计记录写入 `/tmp/cr_review_result_{repo}.json`（保留所有 verdict + reason + missed_candidates，用于追溯）
6. 重新计算 counts 和 conclusion（confirm / dismissed 均不计入 P0/P1 计数）

## 边界情况处理
- 子 Agent 超时/失败/格式异常 → 默认 CONFIRM（保留原 issue 不变），跳过漏报扫描
- 所有 P0/P1 被 DISMISS → 按 P2/P3 推导结论（dismissed 在附录可见，人工可翻案）
- to_human 全转 confirm → 按剩余 P2/P3 推导结论（confirm 区人工定夺）
- missed_candidates 为空 → 正常，说明覆盖良好，播报中注明「无疑似漏报」
- 漏报扫描不扩大化：子 Agent 上下文有限，只扫未覆盖文件的高风险模式，不做全量规则重审（那是四路审查的职责，复审只兜底）
- 复审是可选步骤：如果子 Agent 不可用（降级模式），主 Agent 自行复查 P0/P1 + 快速漏报扫描（只看未覆盖文件列表）
- 复审不阻塞：失败则保留原 issue 不变

## 播报格式
```
✅ Step 4-Review:复审完成 - 确认 {a} / 升级 {b} / 降级 {c} / 误报移除 {d}(附证据) / 疑似误报转confirm {e} / 存疑 {f} | 漏报扫描: 新增 {g} 条疑似漏报(转confirm) / 无疑似漏报 | step4.json 已更新 | 审计记录 /tmp/cr_review_result_{repo}.json
```

## 注意事项
- 复审子 Agent 不看原 issue 的 description/risk/suggestion，避免锚定效应
- 子 Agent 不读 diff 文件：上下文/hunks/规则合集由主 Agent 预处理后经 attachments 注入
- **平衡原则**：错报过滤（DISMISS 需硬证据）与检出宽度（漏报扫描）并重；DISMISS 的产出保留 dismissed 记录可追溯，SUSPECT/漏报一律转 confirm 不硬删
- 复审完成后立即进入 Step 5，不得停顿
