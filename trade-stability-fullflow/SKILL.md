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
  触发词：故障全流程处理、稳定性全流程处理、fullflow、故障紧急止损、全流程、告警、TT工单、客诉、用户反馈。

metadata:
  skillhub.creator: "bijietao"
  skillhub.updater: "bijietao"
  skillhub.version: "V13"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "51575"
  skillhub.high_sensitive: "false"
---

# 稳定性全流程编排

止损优先，排查在后，每步必有输出。

```
信号 → S1信息提取 → S2变更查询 → S3止损(🔴/🟡执行 🟢跳过) → S4排查根因 → S5修复 → S6报告
```

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

### 守卫条件

| 状态 | 守卫条件 |
|------|---------|
| `S1_INFO_FETCH` | signal_type、business_line、bundle_name、problem_time 非空 |
| `S2_CHANGE_QUERY` | MCM 和 Diva 两路完成，stop_loss_advice 非空 |
| `S3_CHANGE_STOP` | status=completed（含 🟢 跳过） |
| `S4_DIAGNOSIS` | conclusion_validity、root_cause_type、root_cause_detail、fix_direction 非空 |
| `S5_REMEDIATION` | fix_type 非空 |
| `S6_REPORT` | report_generated=true（反馈收集必须执行，但用户未回复时记为「未评价」不阻塞完成） |

`S0_INIT → S1 → S2 → S3 → S4 → S5 → S6 → S7_DONE`

> 📖 状态文件结构、脚本命令详解、完整示例、运行规则 → [references/state-management.md](references/state-management.md)

---

## 🔧 环境检查（执行前必做）

全流程启动前（`init` 之后、S1 之前），**必须**执行一次 CLI 工具可用性检查，确保后续步骤不会因工具缺失而中断。

> ⚠️ **检查原则**：安装检查只做一次，通过后子 Skill 内部不再重复安装检查（鉴权/登录检查除外）。若子 Skill 独立使用，仍需按子 Skill 内部的环境检查执行。

### 检查清单

```bash
# 1. MCM CLI（S2 变更查询用）
mcm --version 2>/dev/null && echo "✅ mcm ok" || {
  echo "⚠️ mcm missing, installing..."
  npm install -g @dp/mcm-cli@latest --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
}
mcm whoami 2>/dev/null || mcm login --mis {mis_id}

# 2. Diva CLI（S2 变更查询用）
diva --version 2>/dev/null && echo "✅ diva ok" || {
  echo "⚠️ diva missing, installing..."
  npm install -g @mtfe/infra-diva-cli@latest --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
}

# 3. raptorfe CLI（S4 告警排查路径A用）
raptorfe --version 2>/dev/null && echo "✅ raptorfe ok" || {
  echo "⚠️ raptorfe missing, installing..."
  npm install -g @mtfe/raptorfe-cli@beta --registry aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
}

# 4. code-cli（S5 代码修复提PR用）
code-cli --version 2>/dev/null && echo "✅ code-cli ok" || {
  echo "⚠️ code-cli missing, installing..."
  npm install -g @ee/code-cli --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
}
code-cli auth status 2>/dev/null || code-cli auth login
```

### 工具与步骤映射

| CLI 工具 | 使用步骤 | 用途 | 鉴权要求 |
|---------|---------|------|---------|
| `mcm` | S2 变更查询 | MCM 前端代码发布日历查询 | `mcm login` |
| `diva` | S2 变更查询 | Diva Bundle 发布记录查询 | S2 内部有 `sso-auth-cli` 鉴权预检 |
| `raptorfe` | S4 路径A 告警排查 | Raptor 异常汇总/明细/堆栈/sourcemap | 无需单独鉴权 |
| `code-cli` | S5 代码修复 | 创建分支/提 PR | `code-cli auth login` |
| `sso-auth-cli` | S2 Diva 鉴权 | CatPaw 沙箱中 Diva 透明代理 SSO 预热 | S2 内部自动执行 |

> 💡 `sso-auth-cli` 和 `mtskills` 不在此处检查 — `sso-auth-cli` 由 S2 子 Skill 在 Diva 查询前自动执行鉴权预检；`mtskills` 由 S4-B 子 Skill 按需检查。

### 检查结果处理

- **全部通过** → 继续进入 S1 信息提取
- **安装失败** → 停止流程，提示用户手动安装对应工具后重试
- **鉴权失败** → 提示用户完成登录/鉴权后重试；不得在鉴权未通过时继续执行

---

## 流程概览

| 步骤 | 输入 | 子 Skill | 关键卡点 |
|------|------|----------|---------|
| S1 信息提取 | 用户原始信号 | [information-fetch](references/trade-stability-information-fetch/SKILL.md) | 业务线不明确时必须提问 |
| S2 变更查询 | S1 输出 | [change-query](references/trade-stability-change-query/SKILL.md) | MCM+Diva 并行，两路全完成后才可输出；禁止分析代码 |
| S3 止损 | S2 止损建议 | [change-stop](references/trade-stability-change-stop/SKILL.md) | 🔴立即 / 🟡确认后 / 🟢跳过；🟢 也需标记 completed |
| S4 排查根因 | S1+S2+S3 | [issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md) | 自动分发路径A(告警)/B(客诉)；路径选择后不得切换；UUID 查询属 S4 子步骤 |
| S5 代码修复 | S4 排查结论 | [issue-remediation](references/trade-stability-issue-remediation/SKILL.md) | 前端提PR / 后端给traceId |
| S6 复盘报告 | S1-S5 全部输出 | [issue-report](references/trade-stability-issue-report/SKILL.md) | S1-S5 必须全部 completed；报告后必须提问有效/无效；反馈收集必须执行但用户未回复时不阻塞完成 |

---

## 资产文件与平台链接

| 业务线 | 资产路径 |
|--------|---------|
| 餐 | [assets/food-dev-assets.md](assets/food-dev-assets.md) |
| 综 | [assets/gc-dev-assets.md](assets/gc-dev-assets.md) |
| 酒 | [assets/hotel-dev-assets.md](assets/hotel-dev-assets.md) |
| 景 | [assets/travel-dev-assets.md](assets/travel-dev-assets.md) |

平台辅助链接：[references/platform-links.md](references/platform-links.md)
