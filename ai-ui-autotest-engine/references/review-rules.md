# AI 审校规则（flow-convert 输出后必做）

**审校顺序**：R-STR → R-ACT → R-AST → R-SEM → R-PAR → R-CFL。P0 不修流程必败，P1 大概率执行异常。

---

## R-STR 结构完整性

- **R-STR-001 [P0] sid 规范**：UI 用 S1/S2，API 用 A1/A2，Track 用 T1/T2，编号连续不重复
- **R-STR-002 [P0] 必填字段**：
  - ui → action + desc + step-type + asserts
  - api → api_assert（含 path + 可选 expected_fields；字段语义/匹配机制见 SKILL.md §三「api_assert 语义规范」）
  - track → track_assert（含 match + 可选 expected_fields）
  - step-type=assert → asserts 至少 1 项
  - kind=visual → expect 非空（多验收点用 targets 拆开）
  - tap/input-text → action_anchor；tap-text/scroll-until/open-url → action_arg
  - 打开新页面/弹窗/动态区域加载 → page_ready: true
- **R-STR-003 [P0] kind 互斥**：asserts 的 `kind` 只能是 text / visual；api/track 是步骤类型（配 `api_assert`/`track_assert`），不写进 asserts
- **R-STR-004 [P1] asserts 取值合法**：`kind` ∈ text / visual；`match` ∈ present / gone（仅 kind=text）
- **R-STR-005 [P1] asserts 限制**：interaction 步骤最多 1 项轻量文本断言，深层内容拆到独立 assert 步骤

## R-ACT Action 映射

- **R-ACT-001 [P0] action 映射正确**：按 SKILL.md §4 映射表对照；滑动/长按等复杂操作降级 tap + visual 断言
- **R-ACT-002 [P1] asserts 场景匹配**：打开新页面/弹窗只需 present 文本断言 + page_ready: true；`kind: "visual"` 只用于视图树无法表达的纯视觉判断（布局/动画/样式）
- **R-ACT-003 [P0] 视觉断言目标完整**：`kind: "visual"` 必须有 expect；有硬性验收点（位数/数值/状态）必须用 targets 逐项列出
- **R-ACT-004 [P1] 开看关拆分**：弹窗类拆三段，「看」独立为 step-type=assert
- **R-ACT-005 [P2] wait 条件合理**：页面稳定等待统一用 `page_ready: true`
- **R-ACT-006 [P0] action_arg 用页面完整节点文案**：`tap-text` / `scroll-until` 只做精确匹配，禁止写复合文案的子串（页面是「已优惠¥219」就不能写「已优惠」），否则执行期必然落入 resolve_text_not_found hook
  - Flow 原文就是子串时：改用完整文案并标 `"inferred": true`
  - 断言侧不受此限：单条 expect 允许子串 / 形态差异（候选唯一时引擎直接判 pass/semantic）
  - 文案口径差异只记备注：`log-record --desc "..." --note "..."`（不带判定开关）

## R-AST 断言校验

- **R-AST-001 [P0] 断言完整性**：Flow 的全部校验点在 asserts 中都有对应
- **R-AST-002 [P1] 归类正确**：kind/match 与 Flow 意图一致；interaction 步骤只放轻量标志
- **R-AST-003 [P1] 置信度处理**：high 直接使用；low/fuzzy 改用 `kind: "visual"`
- **R-AST-006 [P1] 抽象描述降级**：expect 含「展示/显示/正常/应该」等语义化描述，或无精确匹配可能 → 改用 `kind: "visual"`
- **R-AST-004 [P2] gone 断言合理**：验证确实应消失的内容，不是正常页面内容
- **R-AST-005 [P1] 多条断言拆步**：interaction 超过 1 项文本断言 → 拆出独立 assert 步骤

## R-SEM 语义一致性

- **R-SEM-001 [P0] 忠实于 Flow**：action_arg / asserts 必须在 Flow 原文有依据，禁止编造
- **R-SEM-002 [P0] api_assert 不补前缀**：path 只保留 Flow 原文值，不补 https://
- **R-SEM-003 [P0] 子场景全覆盖**：Flow 有 N 个场景，steps 就覆盖 N 个
- **R-SEM-004 [P2] desc 语义化**：建议用「开/看/关」前缀
- **R-SEM-005 [P1] 模糊推定**：Flow 含 `pending`/`待审校`/`以实际为准` 时推定最合理文案并标 `"inferred": true`，asserts 走 `kind: "visual"`

## R-PAR 参数完整性

- **R-PAR-001 [P0] 运行时参数补填**：tap/input-text 必须配 action_anchor
- **R-PAR-002 [P0] 占位符完整**：Flow 的 {xxx} 在 steps-input 中全部用到
- **R-PAR-003 [P1] 日期用 {T+N:format}**：禁止硬编码日期，如 `{T+10:%Y-%m-%d}`（不指定 format 时默认 `%Y-%m-%d`）
- **R-PAR-004 [P0] device/env 对齐**：把 `flow-convert` 的默认 device（type/platform/app）与 env 修正为 device-required / env-required 的实际结果
- **R-PAR-005 [P0] 真实值覆盖**：account/password 和 params 从 Flow「测试数据参考」提取真实值，经 `save-answers` 持久化到 env_answers.json
- **R-PAR-006 [P0] 匹配标识必填**：`api_assert.path` 与 `track_assert.match` 为空会被 flow-init 硬拒（空 path 匹配任意请求、空 match 必然匹配不到）
- **R-PAR-007 [P1] 埋点匹配标识选择**：`track_assert.match` 优先用 `val_bid`（事件 ID，精确且唯一，命中即 PASS）。Flow 只给组件级 cid（如 `c_hotel_xxx`）时，同一 cid 下会同时存在 PV / MV / MC 等多个事件，引擎会转 PENDING 交 AI 用 `assert-fields --picked` 消歧；建议补 `expected_fields` 锁定事件类型（如 `{"nm":"PV"}`）以减少歧义、提升确定性

## R-CFL 冲突检测

- **R-CFL-001 [P0] landing_scheme 不重复**：首步不得是 open-url 等于 landing_scheme（C2 已自动跳转），发现即删该步骤
- **R-CFL-002 [P0] tap 不用坐标**：tap/input-text 必须用 action_anchor 锚点文案，禁止写坐标

---

## 审校结果记录

审校完成后输出：

```
审校结果：
  P0 通过/未通过 | 修复 N 项
  P1 通过/未通过 | 修复 N 项
  结论：可以执行 flow-init / 需修复后重审
```
