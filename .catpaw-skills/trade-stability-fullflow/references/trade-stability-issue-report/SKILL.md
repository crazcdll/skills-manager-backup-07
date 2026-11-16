---
name: trade-stability-issue-report
description: 交易前端稳定性处置数据上报专家。作为稳定性全流程第六步，将状态文件中 S1-S5 的结构化数据直接调用 scripts/report_final.py 幂等上报稳定性平台数据库（内网授权域名，令牌走本地配置/环境变量，不入仓库）；不组装、不上报 Markdown 报告全文，完整处置报告由 NoCode 搭建的报告详情页基于数据库字段渲染（https://api-guidance-portal.mynocode.host/flbyw9_8182b99#/investigation/{issue_id}）。上报成功后脚本自动完成 S6 状态归档并推进到 S7_DONE。对用户的对话输出精简为【问题总结】+ 报告详情链接。输入：状态文件中 S1-S5 的对齐字段。输出：数据库上报（结构化字段 + 状态快照）+ 自动状态归档 + 用户侧（问题总结 + 报告详情链接）。触发词：上报报告、处置报告、数据上报、生成报告链接、复盘报告。
---

# 处置数据上报

> **执行顺序**：① 前置校验 → ② 上报 S1-S5 数据到数据库（获得 issue_id → 报告详情链接）→ ③ 向用户输出【问题总结】+ 报告详情链接
>
> ⚠️ 本步骤**不生成 Markdown 完整报告**（不组装三章节、不落盘 `reports/<issue_id>.md`），也不手动执行 `state-manager.sh done S6_REPORT`；完整处置报告由 NoCode 搭建的报告详情页基于数据库上报的数据自动渲染。

---

## ① 前置输入校验

本 skill 作为全流程第六步执行，**必须**在 S1-S5 全部完成且输出结果已确认后方可执行。

> 🚨 **禁止在缺少前五步输出时上报。** 如果前五步的任何一步没有输出结果，**不得自行编造或推断**，必须先回到对应步骤执行完成后再上报。

### 依赖检查

执行上报前，**必须**先执行 `./scripts/state-manager.sh read <issue_id>` 读取状态文件，逐项确认以下输入。

> ⚠️ **输入唯一来源**：S1-S5 各步骤的对齐字段（output 中与子 Skill 报告表格 1:1 对齐的字段，定义见 [state-management.md](../../state-management.md)）。**不得凭会话记忆重组、改写或概括详细结果。**

| 输入项 | 来源（状态文件） | 必须非空 | 缺失时处理 |
|--------|------------------|---------|----------|
| 信号类型、业务线、Bundle/页面 | `S1_INFO_FETCH.output` | ✅ | 回退到 S1 执行 |
| 变更扫描结果 | `S2_CHANGE_QUERY.output` | ✅ | 回退到 S2 执行 |
| 止损操作记录 | `S3_CHANGE_STOP.output` | ✅（含跳过场景） | 回退到 S3 执行 |
| 排查结论 | `S4_DIAGNOSIS.output` | ✅ | 回退到 S4 执行 |
| 修复方案 | `S5_REMEDIATION.output` | ✅ | 回退到 S5 执行 |

**对齐字段缺失时的补救**：某步骤 `output` 缺失对齐字段（旧状态文件 / 子 Skill 未按字段对齐原则写入）时，不得编造，按以下顺序处理：
1. 会话上下文中存在该步骤已输出的完整结果 → 从中提取对应字段值，通过 `update` + patch 文件补写入状态文件，然后继续；
2. 会话上下文也无法找到 → 提示用户「第 X 步输出缺失」，回退到该步骤重新执行后再上报。

> ⚠️ **状态管理守卫**：`state-manager.sh read <issue_id>` 显示 S1-S5 必须全部为 `completed`，才能执行 S6。如果 Agent 未走状态管理直接到达此步，**必须**先提示用户执行 `init` + 补全 S1-S5 的状态记录。

---

## ② 上报 S1-S5 数据到数据库

### 执行流程

> 🚨 **前置校验通过后必须立即执行上报命令，不可跳过。** 上报 = 数据提交数据库 + S6 自动归档，是一个原子操作。

```
S1-S5 前置校验通过
  │
  └─ 立即执行「上报命令」：
       python3 scripts/report_final.py states/<issue_id>.json
       脚本校验（S1-S5 completed）→ 组装 payload（结构化对齐字段
       + 完整状态快照 raw_state + report_url）→ 幂等上报数据库
       → 自动完成 S6 归档并推进 S7_DONE。
       成功后按 ③ 向用户输出精简结果。
```

> ⚠️ **如果 Agent 跳过数据库上报直接结束，视为执行失败。**

### 上报命令（令牌走本地配置文件，不入仓库）

```bash
python3 scripts/report_final.py "states/<issue_id>.json"
# 成功输出: [report-upload] success issue_id=<issue_id> reporter=<mis>
#           [report-upload] detail_url=.../investigation/<issue_id>（③ 的报告详情链接）
#           [report-upload] S6_REPORT 已自动完成，状态推进到 S7_DONE
```

上报令牌不硬编码、不入仓库，解析优先级（高 → 低）：
1. 环境变量 `TRADE_STABILITY_REPORT_TOKEN` / `USER_MIS` / `USER_NAME`
2. `scripts/report_config.json`（本地配置：`supabase_anon_key` / `user_mis` / `user_name`，已加入 .gitignore，不入仓库；`supabase_anon_key` 为平台前端公开分发的匿名密钥，非机密凭证）
3. 上报人 MIS 自动从本地登录配置识别（`~/.openclaw/openclaw.json` 等）

上报目标为美团内网授权域名（`*.database.sankuai.com`）的稳定性平台数据库，不向任何外部域名传输数据。

网络/服务异常时脚本自动重试 3 次（指数退避），无需手动重跑。

### 上报前置条件（脚本自身也会校验）

S1-S5 均为 `completed`，且以下枚举字段合法（脚本会先自动归一化常见别名，仍无法识别则拒绝上报）：

| 字段 | 仅允许取值 | 自动归一化的常见别名 |
|------|-----------|---------------------|
| `signal_type` | 告警 / TT工单 / 反馈 | 监控告警、Raptor告警、alert、TT、工单、客诉、投诉、用户反馈 等（均自动归一到三类枚举） |
| `business_line` | 餐 / 综 / 酒 / 景 | meishi、food、餐饮、到餐、gc、综合、hotel、酒店、travel、门票、旅游 等 |

任一条件不满足时脚本拒绝上报并以非零码退出（报错会列出允许取值），此时修正 S1 字段后重试。归一化后的枚举值会随 payload 与 raw_state 上报，并写回状态文件。

### 脚本行为说明

- **幂等上报**：以 `issue_id` 冲突合并（`Prefer: resolution=merge-duplicates`），重复执行不会产生重复记录，可安全重试。
- **上报内容**：结构化对齐字段（信号/业务线/Bundle/问题时间/根因定性/止损状态/修复方式/负责人等）+ 完整状态快照 `raw_state`（含 S1-S5 全部 output 与时间戳、S6 完成后的终态）+ 报告详情链接 `report_url`。
- **报告渲染**：NoCode 搭建的报告详情页（`detail_url`）基于数据库上报的字段自动渲染完整处置报告，无需上传 Markdown 报告全文。
- **S6 自动归档**：上报成功后脚本自动将 S6_REPORT 标记为 completed（`report_uploaded=true`、`detail_url` 写入 output）并把 `current_state` 推进到 S7_DONE，**无需也不得再手动执行 `state-manager.sh done S6_REPORT`**。
- **校验失败**：禁止绕过，回退补全后重新执行。

### 失败处理

| 场景 | 处理 |
|------|------|
| 缺少上报凭证 | 按报错提示配置环境变量 `TRADE_STABILITY_REPORT_TOKEN` 或 `scripts/report_config.json` 的 `supabase_anon_key` 后重试 |
| 401/42501 RLS 策略拦截 | 属平台侧表策略问题，联系平台管理员放行写入策略后重试 |
| 网络/服务异常 | 脚本自动重试 3 次；仍失败则提示用户稍后重跑上报命令（幂等，可安全重试） |
| 校验类报错（S1-S5 未完成） | 禁止绕过，回退补全后重新执行 |
| 枚举字段非法（signal_type / business_line 不在允许取值内） | 回退到 S1 修正字段后重试；常见别名（如 meishi、TT、客诉）脚本会自动归一，无需人工干预 |

> ⚠️ 上报失败时状态文件保持 S6 running（脚本不会归档未上报成功的数据），数据库无记录；修复后重新执行上报命令即可，成功时一次性完成上报 + S6 归档。

---

## ③ 向用户输出精简结果

> 🚨 **数据库上报成功后执行本步骤，这是对用户的唯一对话输出。**

### 输出内容（仅限以下两部分）

1. **【问题总结】表格**：按下文模板从状态文件 S1-S5 对齐字段直接组装（字段、取值、顺序均不得改动），用于向用户概括本次处置。
2. **报告详情链接**：取上报命令成功输出的 `detail_url`（即 `https://api-guidance-portal.mynocode.host/flbyw9_8182b99#/investigation/{issue_id}`，`{issue_id}` 为实际问题 ID；完整报告由该 NoCode 页面基于数据库数据渲染）。

### 字段来源映射（问题总结 ← 状态文件对齐字段）

| 问题总结单元格 | 来源字段（状态文件） |
|---------------|---------------------|
| 问题标题 | S1 `business_line` + `page_name`/`bundle_name` + 问题简述（S4 `alert_content` 或信号摘要） |
| 信号类型 | S1 `signal_type` |
| 问题定性 | S4 `conclusion_validity`（✅有效→✅有效问题 / ❌无效→❌无效问题 / ⚠️待确认） |
| 根因类型 | S4 `root_cause_type` |
| 根因摘要 | S4 `root_cause_detail` |
| 影响范围 | S1 `business_line` + `bundle_name`/`page_name` + S4 `impact_scope` |
| 止损状态 | S3 `operation_status` + `stop_loss_type`（🟢跳过→「🟢 无需止损」，附 `skip_reason`） |
| 修复状态 | S5 `fix_type` + `pr_url` / `trace_id` / `notify_target` |
| 整体耗时 | S1 步骤 `started_at`（HH:MM）→ S5 步骤 `completed_at`（HH:MM），总耗时：completed_at- started_at，无法计算时填「—」 |
| 后续动作 | S5 `follow_up` / `next_step`，无则「无」 |

> 时间字段必须取自状态文件真实时间戳（`started_at` / `completed_at`），严禁估算或推断；缺失时填「—」。

### 用户侧输出模板

```markdown
## 【问题总结】

| 字段 | 内容 |
|------|------|
| 问题标题 | {业务线简称 + 页面名 + 问题简述，如「【点餐提单】JS 异常 P1 告警」} |
| 信号类型 | {告警 / TT工单 / 反馈（含客诉、用户反馈等）} |
| 问题定性 | ✅ 有效问题 / ❌ 无效问题（误报）/ ⚠️ 待进一步确认 |
| 根因类型 | 变更引入 / 代码 Bug / 依赖异常 / 后端异常 / 无法定位 |
| 根因摘要 | {一句话说明根因} |
| 影响范围 | {业务线} / {Bundle 或页面} / {影响描述} |
| 止损状态 | ✅ 已止损（{止损方式}）/ 🟢 无需止损 / ⏳ 待确认 |
| 修复状态 | ✅ 已修复（{PR 链接或后端通知记录}）/ ⏳ 修复中 / 🔍 待确认 |
| 整体耗时 | {第一步开始时间 HH:MM ~ 第五步完成时间 HH:MM} 总耗时：XXm|
| 后续动作 | {无 / PR 合入后验证 / 后端跟进 / 持续观测 / 其他明确待办} |

📄 **报告详情**：https://api-guidance-portal.mynocode.host/flbyw9_8182b99#/investigation/{issue_id}
```

### 强制约束

- ⚠️ **禁止**向用户输出前五步详细结果、处置时间线或其他长篇内容（完整报告已上报数据库，通过详情链接查看）。
- ⚠️ **禁止**在链接之后追加任何总结、概述、核心结论、要点回顾、反馈询问或收尾文字。
- ⚠️ 上报失败时：状态保持 S6 running，向用户输出【问题总结】并附注「数据库上报失败（原因），修复后将重新上报，成功后提供报告详情链接」；**不得输出报告详情链接**（数据库无记录，链接不可访问），待重跑上报命令成功后再补发链接。
