# AI 审校规则（flow-convert 输出后必做）

审校不是"看一眼觉得没问题"，是按规则逐项检查。P0 不修则流程必败，P1 大概率执行异常。

**审校顺序**：R-STR → R-ACT → R-AST → R-SEM → R-PAR → R-CFL

---

## R-STR 结构完整性（5 条）

- **R-STR-001 [P0] sid 规范**：UI 用 S1/S2，API 用 A1/A2，Track 用 T1/T2，编号连续不重复
- **R-STR-002 [P0] 必填字段**：
  - ui → action + desc + step-type + asserts
  - api → api_assert（含 path + 可选 expected_fields）
  - track → track_assert（含 match + 可选 expected_fields）
  - step-type=assert → asserts 至少 1 项
  - 含 kind: "visual" → expect 非空（多验收点用 targets 拆开）
  - tap/input-text → action_anchor；tap-text/scroll-until/open-url → action_arg
  - 打开新页面/弹窗/动态区域加载 → page_ready: true
- **R-STR-003 [P0] kind 互斥**：`kind` 只能是 text / visual，`match` 仅 kind=text 适用；api/track 是步骤类型（配 `api_assert`/`track_assert`），不写在 asserts 里
- **R-STR-004 [P1] asserts 取值合法**：`kind` ∈ text, visual；`match` ∈ present, gone（仅 kind=text）
- **R-STR-005 [P1] asserts 限制**：interaction 步骤最多 1 项轻量文本断言，深层内容拆到独立 assert 步骤

## R-ACT Action 映射（5 条）

- **R-ACT-001 [P0] action 映射正确**：按映射表对照（见 SKILL.md §4），复杂操作（滑动/长按）降级 tap + visual 断言
- **R-ACT-002 [P1] asserts 场景匹配**：引擎收集数据 + AI hook 判定架构下，present 断言引擎构建结构化元素索引给 AI 做语义匹配。打开新页面/弹窗只需 present 文本断言 + page_ready: true。`kind: "visual"` 仅用于纯视觉判断（布局/动画/样式），视图树无法表达的内容
- **R-ACT-003 [P0] 视觉断言目标完整**：kind: "visual" 必须有 `expect`（目标短句）；有硬性验收点（位数/数值/状态等）时必须用 `targets` 逐项列出，判定时逐项给出 result
- **R-ACT-004 [P1] 开看关拆分**：弹窗类必须拆为三段，看步骤独立为 step-type=assert
- **R-ACT-005 [P2] wait 条件合理**：不再使用 wait_text 字段，统一用 page_ready: true 处理页面稳定等待
- **R-ACT-006 [P0] action_arg 必须是页面完整节点文案**：`tap-text` / `scroll-until` 只做精确匹配（L0/L1），`action_arg` 禁止写复合文案的子串（页面是「已优惠¥219」就不能写「已优惠」），否则执行期必然落入 resolve_text_not_found hook 需人工兜底。
  - Flow 原文就是子串时：改为完整文案并标 `"inferred": true`，或在步骤 desc 说明口径
  - 断言侧不受此限：单条 `expect` 允许子串 / 形态差异。引擎在精确匹配失败后会做**唯一子串**判定，候选文案形态唯一时直接判 `pass / semantic`（无需 AI hook）；形态不唯一才交 AI。含 `match: "gone"` 的断言反向适用：只要文本仍以精确或子串形态残留，就不会判「已消失」。
  - 文案口径差异（Flow 目标文案与页面真实节点文案不一致）只记备注：`log-record --desc "..." --note "..."`（不带判定开关），不判失败也不额外记一条 PASS。

## R-AST 断言校验（5 条）

- **R-AST-001 [P0] 断言完整性**：catalog 全部断言在 steps 的 asserts 中都有对应
- **R-AST-002 [P1] 归类正确**：kind/match 与 Flow 意图一致；interaction 步骤的 asserts 只放轻量标志
- **R-AST-003 [P1] 置信度处理**：high 直接使用，low/fuzzy 改用 `kind: "visual"`
- **R-AST-006 [P1] 抽象描述降级**：asserts 中 kind=text 的 expect 如果包含"展示""显示""正常""应该"等语义化描述词，或无精确匹配可能的自然语言描述，应改用 kind: "visual"
- **R-AST-004 [P2] gone 断言合理**：验证确实应消失的内容，不是正常页面内容
- **R-AST-005 [P1] 多条断言拆步**：interaction 超过 1 项文本断言 → 拆出独立 assert 步骤

## R-SEM 语义一致性（5 条）

- **R-SEM-001 [P0] 忠实于 Flow**：action_arg/asserts 必须在 Flow 原文有依据，禁止编造。注：含 `pending`/`待审校`/`以实际为准` 时推定 + `"inferred": true` 不违规
- **R-SEM-002 [P0] api_assert 不补前缀**：path 只保留 Flow 原文值，不补 https:// 前缀
- **R-SEM-003 [P0] 子场景全覆盖**：Flow 有 N 个场景，steps 就覆盖 N 个
- **R-SEM-004 [P2] desc 语义化**：建议用「开/看/关」前缀，如"看：断言订单详情页"
- **R-SEM-005 [P1] 模糊推定**：Flow 含模糊标记时推定最合理文案，标注 `"inferred": true`，asserts 走 `kind: "visual"`

## R-PAR 参数完整性（5 条）

- **R-PAR-001 [P0] 运行时参数补填**：tap/input-text 必须配 action_anchor
- **R-PAR-002 [P0] 占位符完整**：Flow 的 {xxx} 在 steps-input 中全部用到
- **R-PAR-003 [P1] 日期用 {T+N:format}**：禁止硬编码日期。必须用 `{T+N:format}` 动态日期占位符（如 `{T+10:%Y-%m-%d}` 表示 10 天后 YYYY-MM-DD、`{T+4:%Y%m%d}` 表示 4 天后 yyyyMMdd）。不指定 format 时默认 `%Y-%m-%d`，各页面团队应保证格式与页面期望一致
- **R-PAR-004 [P0] device/env 对齐**：`flow-convert` 生成的是默认值，AI 必须根据 device-required/env-required 的咨询结果修正 device 类型/platform/app 和 env 配置
- **R-PAR-005 [P0] 真实值覆盖**：account/password 和 params 必须从 Flow「测试数据参考」提取真实值，通过 `save-answers` 持久化到 env_answers.json

## R-CFL 冲突检测（2 条）

- **R-CFL-001 [P0] landing_scheme 不重复**：第一条 step 禁止 open-url 等于 landing_scheme（引擎 C2 阶段已通过 landing_scheme 自动跳转，steps 中无需重复）。如发现第一步是 open-url 且与 landing_scheme 相同，直接删除该步骤
- **R-CFL-002 [P0] tap 不用坐标**：tap/input-text 必须用 `action_anchor` 锚点文案，禁止直接写坐标

---

## 审校结果记录

审校完成后输出：

```
审校结果：
  P0 通过/未通过 | 修复 N 项
  P1 通过/未通过 | 修复 N 项
  结论：可以执行 flow-init / 需修复后重审
```

## 常见 P0 违规速查

| 现象 | 规则 |
|------|------|
| sid 跳号/重复 | R-STR-001 |
| 必填字段缺失（缺 action_anchor 等） | R-STR-002 |
| kind 混入禁止字段 / 把 api·track 写成 assert 的 kind | R-STR-003 |
| action_arg 写了复合文案的子串（如「已优惠」，页面为「已优惠¥219」） | R-ACT-006 |
| asserts 中 text 断言 ≥2 项（interaction 步骤） | R-STR-005 |
| action 与 Flow 不匹配 | R-ACT-001 |
| visual 断言缺 expect | R-ACT-003 |
| 断言未覆盖 Flow 全部校验项 | R-AST-001 |
| 编造 Flow 原文没有的内容（pending/待审校推定不违规） | R-SEM-001 |
| api_assert 补全了前缀 | R-SEM-002 |
| 遗漏子场景 | R-SEM-003 |
| landing_scheme 重复导航 | R-CFL-001 |
| tap 缺 action_anchor | R-CFL-002 |
| device/env 未对齐（默认值未修正） | R-PAR-004 |
| 占位符遗漏 | R-PAR-002 |
| params 未从测试数据参考填充 | R-PAR-005 |