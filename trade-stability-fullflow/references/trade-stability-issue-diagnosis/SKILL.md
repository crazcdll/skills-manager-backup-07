---
name: trade-stability-issue-diagnosis
description: 交易前端稳定性告警、客诉等问题排查与定位专家。支持两种使用模式：
  (1) 独立模式：直接接收告警/TT工单/客诉/用户反馈原始信号，自动完成信息提取 → 变更查询 → 分发排查的完整闭环；
  (2) 全流程模式：作为稳定性全流程第四步「排查根因」统一入口，接收第一步和第二步已有结果后直接分发排查。
  根据信号类型自动分发到对应子流程：
  - 告警信号（Raptor / CIA / 成功率 / 48h首现）→ 路径 A：trade-stability-alert-diagnosis
  - TT工单 / 客诉 / 用户反馈 → 路径 B：trade-stability-complaint-diagnosis
  - 告警 + 客诉同时存在 → 路径 A + B 并行，两路均完成后综合输出
  - 信号类型不明确 → 默认路径 B 兜底
  覆盖业务线：餐（meishi）、综（gc）、酒（hotel）、景（travel）。
  触发词：排查根因、问题排查、问题定位、告警排查、问题诊断、issue diagnosis、交易问题、线上问题、帮我排查、帮我定位。
skill-dependencies:
  mtsso-skills-official:
    app_access_token_placeholder: ${app_access_token}
    user_access_token_placeholder: ${user_access_token}
    audience:
      - "60921859"
    prompt: 本技能所需的token 占位符，请参考mtsso-skills-official的相关说明进行获取和注入
---

# 交易前端稳定性问题排查与定位

**定位**：交易前端稳定性问题排查的统一入口，既可独立使用，也可作为全流程第四步被调用。

**核心职责**：根据信号类型选择正确的排查路径，完成根因定位并输出结构化结论。

---

## 执行模式判断（首先执行此步骤）

**在开始任何排查前，先判断当前上下文中是否已有前序步骤的结果：**

```
当前上下文中是否已有「第一步：信息提取结果」AND「第二步：变更扫描结果」？
  ├─ 是（两步均完成）→ 跳过「前置步骤」，直接进入「路径分发」
  └─ 否（任意一步缺失）→ 进入「独立模式」，从缺失的步骤开始执行
```

---

## 【独立模式】前置步骤

> 仅在上下文中**缺少**第一步或第二步结果时执行对应步骤。若两步均已完成，直接跳到「路径分发」。

### 前置步骤 1：信息提取

读取并执行 [trade-stability-information-fetch/SKILL.md](../trade-stability-information-fetch/SKILL.md) 完成信息提取。

核心任务：
- 识别信号类型（告警 / TT工单 / 客诉 / 用户反馈）
- 匹配业务线（餐 / 综 / 酒 / 景）
- 提取：页面名称、技术栈、bundle名、仓库链接、diva发布链接、projectId、前端raptor异常链接、后端日志 topic（可能有多个）

> ✅ 完成后输出「第一步：信息提取结果」，再继续前置步骤 2。

---

### 前置步骤 2：变更查询

读取并执行 [trade-stability-change-query/SKILL.md](../trade-stability-change-query/SKILL.md) 完成变更查询。

核心任务：
- 并行查询 MCM 代码发布 + Diva Bundle 发布
- 判断变更相关度（高 / 中 / 低）
- 给出止损建议（🔴 立即止损 / 🟡 评估后止损 / 🟢 暂不止损）

> ✅ 完成后输出「第二步：变更扫描结果」，再进入路径分发。

> ⚠️ **独立模式下的止损处理**：若变更扫描结果为 🔴 立即止损，**立即告知用户并给出止损操作建议**（参考 [trade-stability-change-stop/SKILL.md](../trade-stability-change-stop/SKILL.md)），等待用户确认止损完成后，再进入路径分发执行排查。

---

## 路径分发

> 前置步骤完成（或已有前序结果）后，根据信号类型选择排查路径。

### 输入确认

| 输入项 | 来源 | 说明 |
|--------|------|------|
| 信号类型 | 第一步·信息提取结果 | 告警 / TT工单 / 客诉 / 用户反馈 |
| 业务线 | 第一步·信息提取结果 | 餐 / 综 / 酒 / 景 |
| Bundle 名 / 页面名 | 第一步·信息提取结果 | 如 `rn_meishi_group_order_detail` |
| 告警时间 / 问题时间 | 第一步·信息提取结果 | YYYY-MM-DD HH:mm |
| 用户标识 | 第一步·信息提取结果 | userId / 手机号 / traceId / 订单号（可为空） |
| 变更扫描结果 | 第二步·变更查询结果 | MCM/Diva 变更列表、相关度、止损建议 |

### 分发规则

根据信号类型，**严格按下表选择排查路径**，选定后不得中途切换：

| 信号类型 | 排查路径 | 执行方式 |
|---------|---------|---------|
| 告警（Raptor / CIA / 成功率 / 48h首现） | **路径 A：告警排查** | 读取 [trade-stability-alert-diagnosis/SKILL.md](trade-stability-alert-diagnosis/SKILL.md) |
| TT 工单 / 客诉 / 用户反馈 | **路径 B：问题诊断** | 读取 [trade-stability-complaint-diagnosis/SKILL.md](trade-stability-complaint-diagnosis/SKILL.md) |
| 告警 + 同时有 TT / 客诉 | **路径 A + B 并行** | 同时读取两个子 Skill，两路均完成后综合输出 |
| 信号类型不明确 | **路径 B（兜底）** | 读取 [trade-stability-complaint-diagnosis/SKILL.md](trade-stability-complaint-diagnosis/SKILL.md) |

> ⚠️ **路径选择后不得中途切换**。若路径 A 排查中发现需要查用户日志，仍在路径 A 框架内完成，不切换到路径 B。

---

## 路径 A：告警排查

**适用信号**：Raptor 告警、CIA 告警、成功率告警、48小时首现异常、JS异常

**执行**：读取并严格遵循 [trade-stability-alert-diagnosis/SKILL.md](trade-stability-alert-diagnosis/SKILL.md) 中的完整排查流程。

排查重点：
- 识别告警类型（48h首现 / JS异常 / CIA / 成功率 / 其他）
- 告警有效性判断（有效 / 无效 / 待观察）
- 是否与第二步查到的变更相关（时间吻合 + 代码关联）
- 堆栈分析 + 代码定位（git diff）

**输出格式**：以 `trade-stability-alert-diagnosis` 子 Skill 定义的「🔔 第四步【路径A】：告警排查结论」为准。

---

## 路径 B：问题诊断

**适用信号**：TT 工单、客诉、用户反馈、功能异常反馈

**执行**：读取并严格遵循 [trade-stability-complaint-diagnosis/SKILL.md](trade-stability-complaint-diagnosis/SKILL.md) 中的完整排查流程。

排查重点：
- **UUID 查询**：通过 userId / 手机号查 UUID，再查 Raptor 前端异常 + Logan 端侧日志
- 前端日志（Raptor + Logan）+ 后端日志并行查询
- 结合第二步变更记录，判断问题是否由变更引入
- 后端问题 → 提供 traceId 链路 → 通知后端
- 前端问题 → 定位代码 → 提 PR

**输出格式**：以 `trade-stability-complaint-diagnosis` 子 Skill 定义的「🔎 第四步【路径B】：排查结论」为准。

---

## 输出要求

> ⚠️ **输出格式以子 Skill 为准**，本 Skill 不另行定义输出格式，避免与子 Skill 冲突。

完成排查后，**必须**确认以下关键字段已在子 Skill 输出中体现：

- 结论定性（有效 / 无效 / 待观察）
- 根因类型（变更引入 / 代码Bug / 依赖异常 / 无法定位）
- 根因说明（含代码路径 / 接口 / 配置Key）
- 关联变更（版本号 + 发布时间，或「无关联变更」）
- 修复方向（前端代码路径 或 后端 traceId）

**独立模式下**：输出完成后，询问用户是否需要继续执行代码修复（第五步）或生成处置报告（第六步）。

**全流程模式下**：输出完成后，向用户展示排查结论，并询问是否进入第五步（代码修复）；若根因为后端问题或无法定位，告知用户并等待确认是否需要生成处置报告（第六步）。
