---
name: trade-stability-fullflow
description: 交易前端稳定性全流程编排专家。当收到告警、TT工单、客诉、用户反馈等任何稳定性信号时使用，自动完成完整处置闭环：
  (1) 信息提取：识别信号类型（告警/TT/客诉/反馈）→ 提取关键信息（业务线/时间/Bundle/用户标识）
  (2) 变更查询：查询今日变更（MCM前端代码发布/Diva Bundle发布），根据变更相关度决定是否止损
  (3) 紧急止损：执行或跳过止损（🔴/🟡执行 🟢跳过）
  (4) 排查根因：告警走告警排查路径，TT/客诉/反馈走问题诊断路径 → 输出根因定性
  (5) 代码修复：前端问题直接改代码提PR，后端问题给 traceId 链路通知后端
  (6) 复盘报告：生成处置报告，收集反馈，写入记忆
  覆盖业务线：餐（meishi）、综（gc）、酒（hotel）、景（travel）
  触发词：故障全流程处理、稳定性全流程处理、fullflow、故障紧急止损、全流程。

metadata:
  skillhub.creator: "bijietao"
  skillhub.updater: "bijietao"
  skillhub.version: "V11"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "51575"
  skillhub.high_sensitive: "false"
---

# 稳定性全流程编排

止损优先，排查在后，每步必有输出。

---

## 环境检查（执行前必做）

收到信号后，**第一步操作前**执行一次，确保 CLI 工具可用：

```bash
# 1. MCM CLI（S2 变更查询用）
mcm --version 2>/dev/null || npm install -g @dp/mcm-cli@latest --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
mcm whoami 2>/dev/null || mcm login --mis {mis_id}

# 2. Diva CLI（S2 变更查询用）
diva --version 2>/dev/null || npm install -g @mtfe/infra-diva-cli@latest --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t

# 3. raptorfe CLI（S4 告警排查路径A用）
raptorfe --version 2>/dev/null || npm install -g @mtfe/raptorfe-cli@beta --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t

# 4. code-cli（S5 代码修复提PR用）
code-cli --version 2>/dev/null || npm install -g @ee/code-cli --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
code-cli auth status 2>/dev/null || code-cli auth login
```

> 仅检查实际需要用到的工具。全流程执行时全部检查；独立使用某子能力时按需检查。

---

## 🚦 状态管理（第一优先级）

每个问题独立维护 JSON 状态文件，每步操作前后必须读写。**不允许跳过状态管理。**

**核心原则**：状态文件是唯一事实来源。每个问题从 `init` 开始，每步必须 `step`（进入）→ 执行子 Skill → `done`（完成），不得跳过。

### 标准操作流程（每步只需 2 条命令）

```bash
# 1. 初始化（收到问题时执行一次）
./scripts/state-manager.sh init <issue_id> "信号描述"

# 2. 每步重复（S1→S6 共 6 次）：
./scripts/state-manager.sh step <issue_id>            # 进入下一步（自动 read+advance+running）
# ...读取子 Skill 并执行，产出结果...
./scripts/state-manager.sh done <issue_id> <step_name> # 完成步骤（自动 completed+advance+写 output）
```

> 💡 `step` 命令三合一（read + advance + running），`done` 命令二合一（completed + advance + 可选写 output）。每步只需 2 条命令，降低执行摩擦，但不可跳过。

| 状态 | 子 Skill | 守卫条件 |
|------|----------|---------|
| `S1_INFO_FETCH` | [information-fetch](references/trade-stability-information-fetch/SKILL.md) | signal_type、business_line、bundle_name、problem_time 非空 |
| `S2_CHANGE_QUERY` | [change-query](references/trade-stability-change-query/SKILL.md) | MCM 和 Diva 两路完成，stop_loss_advice 非空 |
| `S3_CHANGE_STOP` | [change-stop](references/trade-stability-change-stop/SKILL.md) | status=completed（含 🟢 跳过） |
| `S4_DIAGNOSIS` | [issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md) | conclusion_validity、root_cause_type、root_cause_detail、fix_direction 非空 |
| `S5_REMEDIATION` | [issue-remediation](references/trade-stability-issue-remediation/SKILL.md) | fix_type 非空 |
| `S6_REPORT` | [issue-report](references/trade-stability-issue-report/SKILL.md) | report_generated=true（反馈收集必须执行，但用户未回复时记为「未评价」不阻塞完成） |

`S0_INIT → S1 → S2 → S3 → S4 → S5 → S6 → S7_DONE`

> 📖 状态文件结构、脚本命令详解、完整示例、运行规则 → [references/state-management.md](references/state-management.md)

---

## 能力列表

| 意图 | 子能力 | 路径 |
|------|--------|------|
| 收到信号，需完整处置 | **全流程** | 本 SKILL |
| 提取关键信息 | 信息提取 | [information-fetch](references/trade-stability-information-fetch/SKILL.md) |
| 查发布变更 | 变更查询 | [change-query](references/trade-stability-change-query/SKILL.md) |
| 止损/回滚/下线 | 紧急止损 | [change-stop](references/trade-stability-change-stop/SKILL.md) |
| 排查根因 | 排查根因 | [issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md) |
| 修复代码/通知后端 | 代码修复 | [issue-remediation](references/trade-stability-issue-remediation/SKILL.md) |
| 生成处置报告 | 复盘报告 | [issue-report](references/trade-stability-issue-report/SKILL.md) |

---

## 总流程

```
信号 → S1信息提取 → S2变更查询 → S3止损(🔴/🟡执行 🟢跳过) → S4排查根因 → S5修复 → S6报告
```

约束：UUID 查询属 S4 子步骤；S2 两路全完成后才能进 S3；S3 完成或跳过后才能进 S4。

---

## 资产文件

| 业务线 | 路径 |
|--------|------|
| 餐 | [assets/food-dev-assets.md](assets/food-dev-assets.md) |
| 综 | [assets/gc-dev-assets.md](assets/gc-dev-assets.md) |
| 酒 | [assets/hotel-dev-assets.md](assets/hotel-dev-assets.md) |
| 景 | [assets/travel-dev-assets.md](assets/travel-dev-assets.md) |

---

## 各步骤

| 步骤 | 输入 | 执行 | 关键卡点 |
|------|------|------|---------|
| S1 信息提取 | 用户原始信号 | 读 [information-fetch](references/trade-stability-information-fetch/SKILL.md) | 业务线不明确时必须提问 |
| S2 变更查询 | S1 输出 | 读 [change-query](references/trade-stability-change-query/SKILL.md)，MCM+Diva 并行 | 两路全完成后才可输出；禁止分析代码 |
| S3 止损 | S2 止损建议 | 🔴立即 / 🟡确认后 / 🟢跳过 → 读 [change-stop](references/trade-stability-change-stop/SKILL.md) | 🟢 也需标记 completed |
| S4 排查根因 | S1+S2+S3 | 读 [issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md)，自动分发路径A/B | 路径选择后不得切换 |
| S5 代码修复 | S4 排查结论 | 读 [issue-remediation](references/trade-stability-issue-remediation/SKILL.md) | 前端提PR / 后端给traceId |
| S6 复盘报告 | S1-S5 全部输出 | 读 [issue-report](references/trade-stability-issue-report/SKILL.md) | S1-S5 必须全部 completed；报告后必须提问有效/无效；反馈收集必须执行但用户未回复时不阻塞完成 |

---

## 平台辅助链接

→ [references/platform-links.md](references/platform-links.md)
