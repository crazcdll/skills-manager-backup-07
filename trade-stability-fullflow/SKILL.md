---
name: trade-stability-fullflow
description: 交易前端稳定性全流程编排专家。当收到告警、TT工单、反馈（客诉/用户反馈等）等任何稳定性信号时使用，自动完成完整处置闭环：
  (1) 信息提取：识别信号类型（告警/TT/反馈）→ 提取关键信息（业务线/时间/Bundle/用户标识）
  (2) 变更查询：查询今日变更（MCM前端代码发布/Diva Bundle发布），根据变更相关度决定是否止损
  (3) 紧急止损：执行或跳过止损（🔴/🟡执行 🟢跳过）
  (4) 排查根因：告警走告警排查路径，TT/反馈走问题诊断路径 → 输出根因定性
  (5) 代码修复：前端问题直接改代码提PR，后端问题给 traceId 链路通知后端
  (6) 复盘报告：将 S1-S5 的结构化数据直接调用 scripts/report_final.py 幂等上报稳定性平台数据库（内网授权域名 database.sankuai.com，令牌通过本地配置文件 scripts/report_config.json 或环境变量注入，不入仓库），上报成功后脚本自动完成 S6 状态归档并推进到 S7_DONE；不生成 Markdown 报告全文，完整处置报告由 NoCode 搭建的报告详情页基于数据库字段渲染；对用户仅输出【问题总结】+ 报告详情链接（https://api-guidance-portal.mynocode.host/flbyw9_8182b99#/investigation/{issue_id}）
  覆盖业务线：餐（meishi）、综（gc）、酒（hotel）、景（travel）
  信号类型分为三类：告警 / TT工单 / 反馈（用户投诉、客诉、C端反馈、产研反馈、测试反馈、用户反馈等统一归为「反馈」）。
  触发词：故障全流程处理、稳定性全流程处理、fullflow、故障紧急止损、全流程、告警、TT工单、反馈、客诉、用户反馈。

metadata:
  skillhub.creator: "bijietao"
  skillhub.updater: "bijietao"
  skillhub.version: "V18"
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
# 1. 初始化（收到问题时执行一次；issue_id 传 auto 自动按规则生成）
./scripts/state-manager.sh init auto "信号描述"
# 生成规则: {信号前缀}-{业务线}-{YYYYMMDD}-{HHmm}-{唯一识别符}，精确到分钟
#   信号前缀: alert(告警)/tt(TT工单)/fb(反馈)  业务线: meishi/gc/hotel/travel
#   唯一识别符: TT号（TT信号天然幂等）/ 4位随机短码；示例: alert-meishi-20260918-1430-ps5b
# 同一问题重复提问: 自动按信号指纹（TT号/Bundle名/订单号/文本哈希）去重，
#   命中未完成问题 → 续办不建单；命中已完成问题 → 提示报告链接；确认新问题 → FORCE_NEW=1

# 2. 每步重复（S1→S5 共 5 次；S6 由上报脚本自动完成，见下）：
./scripts/state-manager.sh step <issue_id>            # 进入下一步（自动 read+advance+running）
# ...读取子 Skill 并执行，产出结果...
./scripts/state-manager.sh done <issue_id> <step_name> # 完成步骤（自动 completed+advance+写 output）

# 3. S6 复盘报告特殊：step 进入后执行上报命令，
#    report_final.py 上报成功后自动完成 S6 归档并推进 S7_DONE，无需手动 done
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
| `S6_REPORT` | report_uploaded=true（数据库上报成功后由 report_final.py 自动标记完成并推进 S7_DONE） |

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

# 5. mtskills + trade-fe-stability-kb skill（S1/S4 资产查询用）
mtskills --version 2>/dev/null && echo "✅ mtskills ok" || {
  echo "⚠️ mtskills missing, installing..."
  npm install -g @mtfe/mtskills --registry=aHR0cDovL3IubnBtLnNhbmt1YWkuY29t
}
mtskills list 2>/dev/null | grep -q "trade-fe-stability-kb" && echo "✅ kb skill ok" || mtskills i trade-fe-stability-kb

# 6. 稳定性知识库预检（trade-fe-stability-kb 公共前置，首次自动 clone）
KB_DIR="$HOME/.trade-fe-stability-knowledge"
[ -d "$KB_DIR/.git" ] && echo "✅ kb repo ok" || \
  git clone ssh://git@git.sankuai.com/nibfe/trade-fe-stability-knowledge.git "$KB_DIR"
```

> ⚠️ 知识库 clone/fetch 失败（SSH Key 未配置 / 不在内网）→ 按下方「资产查询」的诊断提示处理，不得继续执行依赖资产的步骤。

### 工具与步骤映射

| CLI 工具 | 使用步骤 | 用途 | 鉴权要求 |
|---------|---------|------|---------|
| `mcm` | S2 变更查询 | MCM 前端代码发布日历查询 | `mcm login` |
| `diva` | S2 变更查询 | Diva Bundle 发布记录查询 | S2 内部有 `sso-auth-cli` 鉴权预检 |
| `raptorfe` | S4 路径A 告警排查 | Raptor 异常汇总/明细/堆栈/sourcemap | 无需单独鉴权 |
| `code-cli` | S5 代码修复 | 创建分支/提 PR | `code-cli auth login` |
| `sso-auth-cli` | S2 Diva 鉴权 | CatPaw 沙箱中 Diva 透明代理 SSO 预热 | S2 内部自动执行 |
| `mtskills` + `trade-fe-stability-kb` | S1/S4 资产查询 | 稳定性知识库（资产映射）查询入口 | `mtskills i trade-fe-stability-kb` |
| 知识库仓库 `~/.trade-fe-stability-knowledge` | S1/S4 资产查询 | 资产映射数据的唯一来源 | 无需鉴权，SSH Key 需可访问 git.sankuai.com |

> 💡 `sso-auth-cli` 不在此处检查 — 由 S2 子 Skill 在 Diva 查询前自动执行鉴权预检。

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
| S4 排查根因 | S1+S2+S3 | [issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md) | 自动分发路径A(告警)/B(TT·反馈)；路径选择后不得切换；UUID 查询属 S4 子步骤 |
| S5 代码修复 | S4 排查结论 | [issue-remediation](references/trade-stability-issue-remediation/SKILL.md) | 前端提PR / 后端给traceId |
| S6 数据上报 | S1-S5 全部输出 | [issue-report](references/trade-stability-issue-report/SKILL.md) | S1-S5 必须全部 completed；S1-S5 结构化数据直接上报数据库（不生成报告全文），成功后自动完成 S6；NoCode 报告页基于数据库字段渲染完整报告，用户侧仅输出问题总结 + 详情链接 |

---

## 资产查询（trade-fe-stability-kb 知识库）

**餐/综/酒/景的研发资产（页面 → projectId / Bundle / 仓库 / 日志 AppKey / 各平台链接）统一通过 Skill [trade-fe-stability-kb](https://friday.sankuai.com/skills/skill-detail?activeTab=overview&activeTestTab=cases&id=132756) 查询，不再读取本仓库本地资产文件。**

| 业务线 | 知识库资产文件（`~/.trade-fe-stability-knowledge/`） |
|--------|---------|
| 餐 | `assets/food-assets.md` |
| 综 | `assets/gc-assets.md` |
| 酒 | `assets/hotel-assets.md` |
| 景 | `assets/travel-assets.md` |

**查询规则（各子 Skill 必须遵守）**：
1. 按 `trade-fe-stability-kb` 的查询模式执行：同步知识库 → 读 `AGENTS.md` 路由 → 按业务线 Grep 精确匹配 `asset_id`/`bundles`/`project_id`/`keywords` → 命中后读取该条目 YAML 块上下文
2. **禁止整读资产文件、禁止跨业务线文件猜测资产归属**
3. 未命中时按 `trade-fe-stability-kb` 未命中模板输出，不得编造参数

平台辅助链接：[references/platform-links.md](references/platform-links.md)
