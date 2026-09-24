# 基于 JSON 文件的状态管理

> **本文件是状态管理的完整参考文档。主 SKILL.md 中仅保留铁律和状态一览表的摘要，详细规则、脚本用法、示例均在此文件中。**

---

## 状态文件结构

每个问题的状态文件位于 `states/{issue_id}.json`，模板为 `scripts/state-template.json`，结构如下：

### issue_id 生成规则（统一命名）

**格式**：`{信号前缀}-{业务线}-{YYYYMMDD}-{HHmm}-{唯一识别符}`，时间精确到分钟。

| 段 | 取值 | 说明 |
|----|------|------|
| 信号前缀 | `alert` / `tt` / `fb` | 告警 / TT工单 / 反馈（对应三类信号） |
| 业务线 | `meishi` / `gc` / `hotel` / `travel` / `unk` | 餐 / 综 / 酒 / 景 / 无法识别 |
| 日期时间 | `YYYYMMDD-HHmm` | 流程初始化时间，精确到分钟 |
| 唯一识别符 | TT 工单号（TT 信号，天然幂等）/ 4 位随机短码（其他信号） | 保证全局唯一；冲突时自动追加随机短码兑底 |

**示例**：`alert-meishi-20260918-1430-ps5b`、`tt-gc-20260918-1535-2514932343`、`fb-hotel-20260918-0912-x7q2`

**推荐用法**：`init` 时 issue_id 传 `auto`，脚本根据信号描述自动识别信号前缀和业务线并按上述规则生成：

```bash
./scripts/state-manager.sh init auto "Raptor告警: rn_meishi_group_order_detail JS异常 P1"
# 🆔 已自动生成 issue_id: alert-meishi-20260918-1430-ps5b
```

> 💡 `issue_id` 是数据库幂等去重键和报告详情链接路由，必须唯一；手动指定时也应遵循上述统一格式，避免同一问题重复处理产生多条记录。

### 同一问题重复提问的处理（信号指纹去重）

**问题**：同一个问题在不同时间被提问两次（如同一 TT 工单隔天又来一次、同一告警被重复推送），如果每次都建单会产生重复状态文件和重复数据库记录。

**机制**：`init auto` 时脚本自动计算**信号指纹**并写入状态文件 `signal_fingerprint` 字段，建单前先比对已存在的状态文件：

| 指纹优先级 | 规则 | 示例 |
|-----------|------|------|
| 1. TT 工单号 | 信号中含 `TT#?数字` | `tt:2514932343` |
| 2. Bundle 名 | 信号中含 `rn_xxx` 模式 | `bundle:rn_meishi_group_order_detail` |
| 3. 订单号 | 信号中含 `订单号:数字` | `order:5035048852842134300` |
| 4. 文本哈希 | 去空白/数字后 md5 前 8 位（兑底） | `hash:1a2b3c4d` |

**处理规则**：

- **指纹命中 + 原问题未完成**（current_state ≠ S7_DONE）→ **不重复建单**，输出原 issue_id 和 current_state，从原状态继续处理（`step <issue_id>`）
- **指纹命中 + 原问题已处理完成**（S7_DONE）→ 提示已处理完成，报告详情见原状态文件 S6 output.detail_url；确认为新发生的问题时用 `FORCE_NEW=1` 强制新建
- **确认是新问题**：`FORCE_NEW=1 ./scripts/state-manager.sh init auto "..."`
- 手动指定 issue_id 时不做指纹去重（由文件存在性检查兑底）

**结构**：

```json
{
  "issue_id": "问题唯一标识",
  "created_at": "创建时间",
  "updated_at": "最后更新时间",
  "current_state": "当前状态，如 S1_INFO_FETCH",
  "signal_raw": "原始信号文本",
  "signal_fingerprint": "信号指纹（去重识别，格式见 issue_id 生成规则）",
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

> 🔗 **字段对齐原则**：各步骤 output 字段与对应子 Skill（第一步~第五步）报告表格字段 **1:1 对齐**。写入 patch 时应包含报告表格中的全部对齐字段（无值时填「无」或「—」），第六步将 S1-S5 的这些对齐字段直接上报稳定性平台数据库（不生成 Markdown 报告全文，完整报告由 NoCode 报告详情页基于数据库字段渲染，对话中向用户仅输出【问题总结】+ 报告详情链接）。

> ⚠️ **写入规则**：每个子 Skill 输出报告后，必须将报告表格的全部字段值写入 patch 文件，执行 `done <issue_id> <step> /tmp/<step>_output.json` 完成持久化。注意：patch 文件会**整体替换**该步骤的 output，必须一次性包含全部对齐字段，不得分次写入。

#### S1_INFO_FETCH.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `signal_type` | string | 信号类型（三类）：告警 / TT工单 / 反馈 |
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
| `rollback_target` | string | 回滚目标版本号（含 commit 链接，供第三步止损使用） |

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
| `stop_loss_page` | string | 止损页面链接（执行止损时填写） |
| `stop_loss_note` | string | 止损操作摘要（执行止损时填写） |
| `skip_reason` | string | 跳过原因：无可疑变更 / 变更时间差 > 6h / 相关度低 / 用户确认跳过（🟢跳过时填写） |
| `change_conclusion_ref` | string | 第二步变更扫描结论引用（🟢跳过时填写） |
| `notify_record` | string | 通知责任方记录 |

`decision` 字段记录止损决策：`execute`（执行止损）或 `skipped`（跳过止损）。

#### S4_DIAGNOSIS.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `conclusion_validity` | string | 结论定性：✅有效 / ❌无效 / ⚠️待确认 |
| `alert_type` | string | 告警类型：48h首现 / JS异常 / CIA / 成功率 / 其他（路径A） |
| `alert_time` | string | 告警时间 YYYY-MM-DD HH:mm（路径A） |
| `alert_content` | string | 告警内容摘要（路径A） |
| `alert_params` | string | 告警链接参数：projectId、告警窗口、webVersion（路径A） |
| `exception_type` | string | 异常类型：TypeError / API异常 / script加载失败 等（路径A） |
| `impact_scope` | string | 影响范围：用户数 / 设备数 / 请求量 / 影响页面 |
| `stack_detail` | string | 堆栈详情：sourcemap 还原后的代码位置或错误内容摘要（路径A） |
| `exception_summary` | string | 异常明细汇总：Top 5 异常名称/类型/级别/COUNT/用户数/容器/堆栈摘要/traceId（路径A） |
| `frontend_error` | string | 前端异常描述（Raptor 或「无记录」）（路径B） |
| `backend_log` | string | 后端日志关键错误信息 + traceId（或「无记录」）（路径B） |
| `root_cause_type` | string | 根因类型：变更引入 / 代码Bug / 依赖异常 / 无法定位 |
| `root_cause_detail` | string | 根因说明（含代码路径/接口/配置Key） |
| `related_change` | string | 关联变更（版本号+发布时间 或 无关联变更） |
| `change_diff` | string | 关联变更内容摘要：相关文件、代码位置、变更摘要和关联证据（路径B） |
| `fix_direction` | string | 修复方向（前端代码路径 或 后端traceId） |
| `suggestion` | string | 建议处理：立即回滚 / 通知负责人修复 / 升级依赖 / 进一步排查（路径A） |
| `code_location` | string | 代码定位（文件路径:行号 或 未定位） |
| `responsible_person` | string | 负责人 mis_id |

`diagnosis_path` 字段记录排查路径：`A`（告警排查）或 `B`（问题诊断）或 `A+B`（并行）。

#### S5_REMEDIATION.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `fix_type` | string | 修复类型：前端代码修复 / 后端问题 / 变更引入 / 根因待确认 |
| `fix_branch` | string | 修复分支名（前端修复时填写） |
| `root_cause_code` | string | 根因代码位置（仓库+文件+行号） |
| `problem_desc` | string | 问题描述：代码逻辑问题说明（前端修复时填写） |
| `fix_solution` | string | 具体修复方案内容（前端修复时填写） |
| `fix_diff` | string | 修复代码 diff（前端修复时填写） |
| `pr_url` | string | PR 链接（前端修复时填写） |
| `api_path` | string | 异常接口路径（后端问题时填写） |
| `downstream_appkey` | string | 下游服务 Appkey（后端问题时填写） |
| `trace_id` | string | 后端链路 ID（后端问题时填写） |
| `error_info` | string | 错误码/错误描述（后端问题时填写） |
| `follow_up` | string | 后续跟进事项（变更引入时填写，如通知发布人修复后重新发布） |
| `checked_scope` | string | 已排查范围（根因待确认时填写） |
| `current_status` | string | 当前问题状态：持续/已恢复（根因待确认时填写） |
| `next_step` | string | 下一步方向（根因待确认时填写） |
| `need_escalation` | string | 是否需要升级：是/否（根因待确认时填写） |
| `notify_target` | string | 通知目标（mis_id） |

`remediation_type` 字段同 `fix_type`。

#### S6_REPORT.output

| 字段 | 类型 | 说明 |
|------|------|------|
| `report_uploaded` | bool | 数据是否已上报数据库（上报成功后由 report_final.py 自动写入） |
| `detail_url` | string | 报告详情链接（NoCode 报告页，上报成功后由 report_final.py 自动写入） |

> 💡 S6 不走 `step` → `done` 手动归档：进入 S6 后直接执行上报命令，`report_final.py` 上报成功后自动将 S6_REPORT 标记为 completed（写入上述 output 字段）并推进 S7_DONE。S6 不生成 Markdown 报告全文，完整报告由 NoCode 报告详情页基于数据库上报的字段渲染。

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
| `S6_REPORT` | output 中 `report_uploaded`=true（数据库上报成功后由 report_final.py 自动标记完成并推进 S7_DONE） |

---

## 状态管理脚本

所有状态操作通过 `scripts/state-manager.sh` 完成（兼容 macOS bash 3.x，依赖 python3）：

```bash
# 初始化问题状态文件（推荐：issue_id 传 auto 自动按规则生成）
./scripts/state-manager.sh init auto "Raptor告警: rn_meishi_group_order_detail JS异常 P1"

# 初始化问题状态文件（手动指定 issue_id，需遵循统一命名规则）
./scripts/state-manager.sh init <issue_id> [signal_raw]

# 初始化问题状态文件（独立模式，前序步骤自动 skipped）
./scripts/state-manager.sh init <issue_id> [signal_raw] <enter_step>
# 示例: 直接从 S4 排查根因开始
./scripts/state-manager.sh init issue-001 "反馈" S4_DIAGNOSIS

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
./scripts/state-manager.sh init auto "Raptor告警: JS异常 P1"
# → issue_id 自动生成，如 alert-meishi-20260810-1500
```

从 `scripts/state-template.json` 复制一份到 `states/{issue_id}.json`，填入 `issue_id`、`created_at`、`signal_raw`。若 issue_id 传 `auto`，先按「issue_id 生成规则」自动生成（信号前缀和业务线从 signal_raw 关键词识别，无法识别时分别为 `fb` 和 `unk`）。若文件已存在则提示并显示当前状态。

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

输出当前状态 + 各步骤执行情况表（状态/守卫通过/开始时间）+ 下一步待执行步骤及其子 Skill 路径。

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
>
> ⚠️ **S6 例外**：S6 不执行子步骤 3 的 `done`，而是执行上报命令 `python3 scripts/report_final.py states/<issue_id>.json`；脚本上报成功后自动完成 S6 归档并推进 S7_DONE。

---

## 完整示例：一次全流程执行

```bash
# 1. 收到告警信号，初始化状态文件（issue_id 自动生成）
./scripts/state-manager.sh init auto "Raptor告警: rn_meishi_group_order_detail JS异常 P1"
# 从输出中提取生成的 issue_id（形如 alert-meishi-20260918-1430）
issue_id="alert-meishi-20260918-1430"

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

# 7. 进入 S6，执行 issue-report 子 Skill（不生成报告全文、不手动归档）
./scripts/state-manager.sh step "$issue_id"
# ...将 S1-S5 结构化数据直接幂等上报稳定性平台数据库（内网授权域名；上报令牌走本地 scripts/report_config.json，不入仓库）...
# 令牌/上报人优先级：环境变量 TRADE_STABILITY_REPORT_TOKEN > scripts/report_config.json（MIS 自动识别本地登录配置）
python3 scripts/report_final.py "states/$issue_id.json"
# 输出: [report-upload] success issue_id=<issue_id> reporter=<mis>（重复执行按 issue_id 合并，不产生重复记录）
#       [report-upload] detail_url=https://api-guidance-portal.mynocode.host/flbyw9_8182b99#/investigation/<issue_id> ← 向用户输出的报告详情链接
#       [report-upload] S6_REPORT 已自动完成，状态推进到 S7_DONE（无需手动执行 done）
```

---

## 状态管理运行规则

**规则 1：状态文件优先于上下文（强制）**
> 每一步开始前，**必须**先执行 `step` 命令。即使上下文中有记忆，也以 JSON 文件中的 `current_state` 为准。
> 如果 `read` 显示有未完成的步骤，**从该步骤继续执行**，不得从头开始。
> **不允许跳过状态管理。** 每个问题从 `init` 开始，S1→S5 每步必须 `step` → `done`，不得跳过；S6 例外：`report_final.py` 在数据库上报成功后自动完成 S6 归档并推进 S7_DONE，无需手动执行 `done`。

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
