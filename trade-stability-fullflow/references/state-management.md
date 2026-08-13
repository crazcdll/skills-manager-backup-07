# 基于 JSON 文件的状态管理

> **本文件是状态管理的完整参考文档。主 SKILL.md 中仅保留铁律和状态一览表的摘要，详细规则、脚本用法、示例均在此文件中。**

---

## 状态文件结构

每个问题的状态文件位于 `states/{issue_id}.json`，模板为 `scripts/state-template.json`，结构如下：

```json
{
  "issue_id": "问题唯一标识",
  "created_at": "创建时间",
  "updated_at": "最后更新时间",
  "current_state": "当前状态，如 S1_INFO_FETCH",
  "signal_raw": "原始信号文本",
  "steps": {
    "S1_INFO_FETCH": {
      "status": "pending | running | completed | skipped",
      "started_at": "开始时间",
      "completed_at": "完成时间",
      "guard_passed": false,
      "output": { ... }
    },
    "S2_CHANGE_QUERY": { ... },
    "S3_CHANGE_STOP": { ... },
    "S4_DIAGNOSIS": { ... },
    "S5_REMEDIATION": { ... },
    "S6_REPORT": { ... }
  }
}
```

### 各步骤 output 字段定义

#### S1_INFO_FETCH.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `signal_type` | string | 信号类型：告警 / TT工单 / 客诉 / 用户反馈 |
| `business_line` | string | 业务线：餐 / 综 / 酒 / 景 |
| `bundle_name` | string | Bundle 名（如 `rn_meishi_group_order_detail`） |
| `page_name` | string | 页面名称 |
| `problem_time` | string | 问题发生时间（YYYY-MM-DD HH:mm） |
| `user_identifier` | string | 用户标识（userId / 手机号 / 订单号 / traceId） |
| `tech_stack` | string | 技术栈（DUO / MRN / MAX / 小程序 / H5 / i版） |
| `project_id` | string | Raptor 项目 ID |
| `ssh_url` | string | 仓库 SSH 链接 |
| `raptor_link` | string | Raptor 前端异常直链 |
| `diva_link` | string | Diva Bundle 发布直链 |
| `appkey` | string | 后端日志 Appkey（多个用 / 分隔） |

#### S2_CHANGE_QUERY.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `changes` | array | 变更列表（每项含系统、变更内容、发布时间、发布人、相关度） |
| `stop_loss_advice` | string | 止损建议：🔴 立即止损 / 🟡 评估后止损 / 🟢 暂不止损 |
| `most_suspicious_change` | string | 最可疑变更信息 |
| `commit_url` | string | commit 链接（仅记录，第四步使用） |

`sub_tracks` 字段记录 MCM 和 Diva 两路的独立状态：

```json
"sub_tracks": {
  "mcm": { "status": "pending", "result": null },
  "diva": { "status": "pending", "result": null }
}
```

#### S3_CHANGE_STOP.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `stop_loss_type` | string | 止损类型：MRN热发下线 / Horn回滚 / H5回滚 / AB实验关闭 / 小程序下线 / 跳过 |
| `stop_loss_target` | string | 止损对象（bundle名 / HornKey / 实验名） |
| `suspect_version` | string | 可疑版本号 |
| `rollback_target` | string | 回滚目标版本号 |
| `operation_status` | string | 操作状态：⏳ 等待确认 / ✅ 已完成 / 🟢 跳过 |
| `notify_record` | string | 通知责任方记录 |

`decision` 字段记录止损决策：`execute`（执行止损）或 `skipped`（跳过止损）。

#### S4_DIAGNOSIS.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `conclusion_validity` | string | 结论定性：✅有效 / ❌无效 / ⚠️待确认 |
| `root_cause_type` | string | 根因类型：变更引入 / 代码Bug / 依赖异常 / 无法定位 |
| `root_cause_detail` | string | 根因说明（含代码路径/接口/配置Key） |
| `related_change` | string | 关联变更（版本号+发布时间 或 无关联变更） |
| `fix_direction` | string | 修复方向（前端代码路径 或 后端traceId） |
| `code_location` | string | 代码定位（文件路径:行号 或 未定位） |
| `responsible_person` | string | 负责人 mis_id |

`diagnosis_path` 字段记录排查路径：`A`（告警排查）或 `B`（问题诊断）或 `A+B`（并行）。

#### S5_REMEDIATION.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `fix_type` | string | 修复类型：前端代码修复 / 后端问题 / 变更引入 / 根因待确认 |
| `fix_branch` | string | 修复分支名（前端修复时填写） |
| `root_cause_code` | string | 根因代码位置（仓库+文件+行号） |
| `pr_url` | string | PR 链接（前端修复时填写） |
| `trace_id` | string | 后端链路 ID（后端问题时填写） |
| `notify_target` | string | 通知目标（mis_id） |

`remediation_type` 字段同 `fix_type`。

#### S6_REPORT.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_generated` | bool | 报告是否已生成 |
| `memory_written` | bool | 记忆是否已写入 |
| `feedback` | string | 用户反馈：有效 / 无效 / 未评价 |

---

## 状态定义与流转

```
S0_INIT → S1_INFO_FETCH → S2_CHANGE_QUERY → S3_CHANGE_STOP
                                                  │
                                          ┌───────┴───────┐
                                          │               │
                                   🔴/🟡 执行止损      🟢 跳过止损
                                   S3 completed        S3 completed
                                   output=止损结果     output=跳过原因
                                          │               │
                                          └───────┬───────┘
                                                  ↓
                                          S4_DIAGNOSIS → S5_REMEDIATION → S6_REPORT → S7_DONE
```

### 守卫条件一览

| 状态 | 守卫条件（满足后 `guard_passed=true`） |
|------|--------------------------------------|
| `S1_INFO_FETCH` | output 中 `signal_type`、`business_line`、`bundle_name`、`problem_time` 非空 |
| `S2_CHANGE_QUERY` | sub_tracks.mcm 和 sub_tracks.diva 均为 completed，output 中 `stop_loss_advice` 非空 |
| `S3_CHANGE_STOP` | status 为 completed（含 🟢 跳过情况） |
| `S4_DIAGNOSIS` | output 中 `conclusion_validity`、`root_cause_type`、`root_cause_detail`、`fix_direction` 非空 |
| `S5_REMEDIATION` | output 中 `fix_type` 非空（前端PR / 后端traceId / 止损确认 / 待确认） |
| `S6_REPORT` | output 中 `report_generated`=true（反馈收集必须执行，但用户未回复时记为「未评价」，不阻塞 S6 完成） |

---

## 状态管理脚本

所有状态操作通过 `scripts/state-manager.sh` 完成（兼容 macOS bash 3.x，依赖 python3）：

```bash
# 初始化问题状态文件（全流程模式）
./scripts/state-manager.sh init <issue_id> [signal_raw]

# 初始化问题状态文件（独立模式，前序步骤自动 skipped）
./scripts/state-manager.sh init <issue_id> [signal_raw] <enter_step>
# 示例: 直接从 S4 排查根因开始
./scripts/state-manager.sh init issue-001 "用户反馈" S4_DIAGNOSIS

# 进入下一步（三合一：read + advance + running）
./scripts/state-manager.sh step <issue_id> [step_name]

# 完成步骤（二合一：completed + advance，可选写 output）
./scripts/state-manager.sh done <issue_id> <step_name> [json_patch_file]

# 读取状态（查看当前进度 + 各步骤执行情况）
./scripts/state-manager.sh read <issue_id>

# 手动更新步骤状态（高级用法）
./scripts/state-manager.sh update <issue_id> <step_name> <status> [json_patch_file]

# 手动推进到下一个未完成步骤（高级用法）
./scripts/state-manager.sh advance <issue_id>

# 列出所有问题
./scripts/state-manager.sh list
```

> 💡 **推荐使用 `step` + `done` 两个便捷命令**，每步只需 2 条命令即可完成状态流转。`read`/`update`/`advance` 为手动模式，适用于调试和恢复场景。

### 命令详解

#### init（初始化）

```bash
./scripts/state-manager.sh init alert-meishi-20260810-001 "Raptor告警: JS异常 P1"
```

从 `scripts/state-template.json` 复制一份到 `states/{issue_id}.json`，填入 `issue_id`、`created_at`、`signal_raw`。若文件已存在则提示并显示当前状态。

**独立模式**：如果传入了第三个参数 `enter_step`（如 `S4_DIAGNOSIS`），则将该步骤之前的所有步骤自动标记为 `skipped`（含 `guard_passed=true`），`current_state` 直接设为该步骤。适用于用户直接使用某个子能力而非全流程的场景。

#### step（进入步骤，推荐使用）

```bash
# 自动找到下一个未完成步骤并进入
./scripts/state-manager.sh step alert-meishi-20260810-001

# 指定步骤名进入（用于恢复场景）
./scripts/state-manager.sh step alert-meishi-20260810-001 S2_CHANGE_QUERY
```

等价于 `read`（找到下一步） + `advance`（推进状态） + `update running`（标记为执行中）三条命令。自动找到第一个未完成的步骤，推进状态并标记为 running。

#### done（完成步骤，推荐使用）

```bash
# 基本用法：标记完成并自动推进
./scripts/state-manager.sh done alert-meishi-20260810-001 S1_INFO_FETCH

# 带 patch 文件：完成的同时写入 output
echo '{"signal_type":"告警","business_line":"餐","bundle_name":"rn_meishi_xxx","problem_time":"2026-08-10 15:00"}' > /tmp/patch.json
./scripts/state-manager.sh done alert-meishi-20260810-001 S1_INFO_FETCH /tmp/patch.json
```

等价于 `update completed`（标记完成 + 记录时间 + 设 guard_passed） + `advance`（推进到下一步）两条命令。如果有 patch 文件，同时将 output 写入 JSON。

#### read（查看状态）

```bash
./scripts/state-manager.sh read alert-meishi-20260810-001
```

输出当前状态 + 各步骤执行情况表（状态/守卫通过/完成时间）+ 下一步待执行步骤及其子 Skill 路径。

#### update（手动更新）

```bash
# 基本用法
./scripts/state-manager.sh update <issue_id> S1_INFO_FETCH running
./scripts/state-manager.sh update <issue_id> S1_INFO_FETCH completed

# 带 patch 文件（将 output 字段写入 JSON）
echo '{"signal_type":"告警","business_line":"餐","bundle_name":"rn_meishi_xxx","problem_time":"2026-08-10 15:00"}' > /tmp/patch.json
./scripts/state-manager.sh update <issue_id> S1_INFO_FETCH completed /tmp/patch.json
```

`status` 取值：`pending` → `running` → `completed`（或 `skipped`）。
设置 `running` 时记录 `started_at`；设置 `completed` 时记录 `completed_at` 并设 `guard_passed=true`。
patch 文件是一个 JSON 对象，会整体替换该步骤的 `output` 字段。

#### advance（手动推进）

```bash
./scripts/state-manager.sh advance <issue_id>
```

找到第一个 `status` 不为 `completed` 且不为 `skipped` 的步骤，将 `current_state` 设为该步骤名。若全部完成或跳过，设为 `S7_DONE`。

#### list

```bash
./scripts/state-manager.sh list
```

列出 `states/` 目录下所有问题的 `issue_id`、`current_state`、`updated_at`。

---

## 每一步的标准执行流程

> **每一步执行时，严格按照以下 3 个子步骤操作，不得跳过。**

```bash
# ── 子步骤 1：进入步骤（自动 read + advance + running） ──
./scripts/state-manager.sh step <issue_id>

# ── 子步骤 2：读取子 Skill 并执行（产出输出结果） ──
# 读取对应子 Skill 的 SKILL.md，按其流程执行
# 执行完毕后将输出结果构造为 patch 文件

# ── 子步骤 3：完成步骤（自动 completed + advance + 写 output） ──
./scripts/state-manager.sh done <issue_id> <step_name> [json_patch_file]
```

> 💡 与旧版 5 子步骤的对应关系：旧版 `read` + `advance` + `update running` 三步合并为 `step`；旧版 `update completed` + `advance` 两步合并为 `done`。操作更简，但状态记录同样完整。

---

## 完整示例：一次全流程执行

```bash
# 1. 收到告警信号，初始化状态文件
issue_id="alert-meishi-20260810-001"
./scripts/state-manager.sh init "$issue_id" "Raptor告警: rn_meishi_group_order_detail JS异常 P1"

# 2. 进入 S1，执行 information-fetch 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...读取 SKILL.md 并执行，产出信息提取结果...
# ...构造 patch 文件...
./scripts/state-manager.sh done "$issue_id" S1_INFO_FETCH /tmp/s1_patch.json

# 3. 进入 S2，执行 change-query 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...并行查 MCM + Diva，产出变更扫描结果...
# ...止损建议为 🟢 暂不止损...
./scripts/state-manager.sh done "$issue_id" S2_CHANGE_QUERY /tmp/s2_patch.json

# 4. 进入 S3，执行 change-stop 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...止损建议为 🟢，输出跳过止损报告...
./scripts/state-manager.sh done "$issue_id" S3_CHANGE_STOP /tmp/s3_patch.json

# 5. 进入 S4，执行 issue-diagnosis 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...按信号类型分发路径 A/B，产出排查结论...
./scripts/state-manager.sh done "$issue_id" S4_DIAGNOSIS /tmp/s4_patch.json

# 6. 进入 S5，执行 issue-remediation 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...产出修复方案（PR / traceId / 止损确认 / 待确认）...
./scripts/state-manager.sh done "$issue_id" S5_REMEDIATION /tmp/s5_patch.json

# 7. 进入 S6，执行 issue-report 子 Skill
./scripts/state-manager.sh step "$issue_id"
# ...生成完整处置报告 + 收集反馈 + 写入记忆...
./scripts/state-manager.sh done "$issue_id" S6_REPORT /tmp/s6_patch.json
# 输出: ✅ S6_REPORT 已完成。所有步骤已完成，状态推进到 S7_DONE
```

---

## 状态管理运行规则

**规则 1：状态文件优先于上下文（强制）**
> 每一步开始前，**必须**先执行 `step` 命令。即使上下文中有记忆，也以 JSON 文件中的 `current_state` 为准。
> 如果 `read` 显示有未完成的步骤，**从该步骤继续执行**，不得从头开始。
> **不允许跳过状态管理。** 每个问题从 `init` 开始，S1→S6 每步必须 `step` → `done`，不得跳过。

**规则 2：禁止跨状态操作**
> `current_state` 为 `S2_CHANGE_QUERY` 时，**严禁**执行 UUID 查询、日志查询等属于 `S4` 的操作。
> `current_state` 为 `S4_DIAGNOSIS` 时，**严禁**执行代码提交、PR 创建等属于 `S5` 的操作。

**规则 3：每步输出写入 JSON**
> 每步完成后，应将输出结果通过 patch 文件写入 JSON 的 `output` 字段。这样即使上下文丢失，后续步骤也能从 JSON 中读取前序步骤的结果。
> patch 文件是一个 JSON 对象，包含该步骤的 output 字段值。

**规则 4：🟢 暂不止损也是 completed**
> 第三步止损建议为 🟢 时，不需要执行止损操作，但**必须**将 `S3_CHANGE_STOP` 标记为 `completed`，并在 `output` 中记录 `decision: "skipped"` 和跳过原因。

**规则 5：异常不改变状态**
> 子 Skill 执行中遇到 CLI 失败、网络超时等异常，状态保持 `running`，在当前步骤内重试或兜底处理。
> 异常**不触发状态推进**，直到当前步骤的输出产物完成或明确判定无法完成时，才可向用户报告并等待决策。

**规则 6：独立子能力调用的状态入口**
> 当用户直接使用某个子能力（如「查变更」「排查根因」）而非全流程时：
> - 仍需初始化状态文件，使用 `init <issue_id> [signal_raw] <enter_step>`，前序步骤自动标记为 `skipped`。
> - `current_state` 直接设为对应步骤。
> - 子能力完成后，状态标记为 `completed` 并进入 `S7_DONE`。
> - 示例：`./scripts/state-manager.sh init issue-001 "查变更" S2_CHANGE_QUERY`

**规则 7：多问题并行**
> 每个问题有独立的 `issue_id` 和独立的 JSON 文件，互不干扰。
> `list` 命令可查看所有问题的状态概览。
