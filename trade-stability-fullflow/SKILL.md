---
name: trade-stability-fullflow
description: 交易前端稳定性全流程编排专家。当收到告警、TT工单、客诉、用户反馈等任何稳定性信号时使用，自动完成完整处置闭环：
  (1) 识别信号类型（告警/TT/客诉/反馈）→ 提取关键信息（业务线/时间/Bundle/用户标识）
  (2) 查询今日变更（MCM前端代码发布/Diva Bundle发布），根据变更相关度决定是否止损
  (3) 止损完成（或跳过）后，启动问题排查（告警走告警排查路径，TT/客诉/反馈走问题诊断路径）
  (4) 输出排查结论：根因定性 + 修复方案（后端问题给 traceId 链路，前端问题直接改代码提PR）
  (5) 生成复盘报告，记录完整处置时间线
  覆盖业务线：餐（meishi）、综（gc）、酒（hotel）、景（travel）
  触发词：故障全流程处理、稳定性全流程处理、fullflow、故障紧急止损、全流程。

metadata:
  skillhub.creator: "bijietao"
  skillhub.updater: "zhangce07"
  skillhub.version: "V8"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "51575"
  skillhub.high_sensitive: "false"
---

# 稳定性全流程编排

**目标**：收到任何稳定性信号后，在最短时间内完成「变更确认 → 止损 → 排查 → 结论输出 → 代码修复 → 复盘报告」的完整闭环。

**核心原则**：止损优先，止损完成后再排查，结论有据，修复可执行，**每步必有输出**。

---

## 能力列表

用户可通过以下触发词直接使用对应子能力，**无明确诉求时优先走全流程（最高优先级）**：

| 用户意图 | 子能力 | 使用说明 | 路径 |
|---------|--------|---------|------|
| 收到告警/TT/客诉/反馈，需要完整处置 | **全流程编排**（最高优先级） | 无明确诉求时默认走此路径，自动完成六步闭环 | 本 SKILL（直接执行） |
| 提取告警/工单/客诉中的关键信息 | 信息提取 | 识别信号类型、提取业务线/时间/Bundle/用户标识 | [trade-stability-information-fetch](references/trade-stability-information-fetch/SKILL.md) |
| 查询某时间段内的发布变更 | 变更查询 | 并行查 MCM 前端代码发布 + Diva Bundle 发布（Horn/AB 变更查询暂不执行） | [trade-stability-change-query](references/trade-stability-change-query/SKILL.md) |
| 紧急止损、回滚、下线、关量 | 紧急止损 | 支持 MRN 热发下线/小程序回滚/H5回滚/AB关闭/Horn回滚 | [trade-stability-change-stop](references/trade-stability-change-stop/SKILL.md) |
| 排查根因（告警/TT/客诉/反馈统一入口，支持独立使用） | 排查根因 | 自动分发：告警→告警排查路径，TT/客诉/反馈→问题诊断路径；独立使用时自动补全信息提取和变更查询 | [trade-stability-issue-diagnosis](references/trade-stability-issue-diagnosis/SKILL.md) |
| 根据根因结论修复代码或通知后端 | 代码修复 | 前端问题提 PR，后端问题整理 traceId 通知后端 | [trade-stability-issue-remediation](references/trade-stability-issue-remediation/SKILL.md) |
| 生成处置报告、故障通告、恢复通告 | 复盘报告 | 输出完整处置时间线、止损记录、根因结论、修复方案 | [trade-stability-issue-report](references/trade-stability-issue-report/SKILL.md) |

---

## 总流程概览

```
收到信号（告警 / TT / 客诉 / 反馈）
         ↓
[第一步] 信息提取（trade-stability-information-fetch）
         识别信号类型 & 提取关键信息（业务线/时间/Bundle/问题描述/用户标识）
         ✅ 输出：【第一步输出】信息提取结果
         ↓
[第二步] 变更查询（trade-stability-change-query）⚡ 最高优先级
         必查：① MCM 前端代码发布  ② Diva Bundle 发布
         暂不执行：③ Horn 配置变更  ④ AB 实验变更（如需请手动查询）
         —— 并行执行，不等待任何一路完成再开始另一路
         ✅ 输出：【第二步输出】变更扫描结果
    ↙         ↓          ↘
🔴立即止损  🟡评估后止损  🟢暂不止损
  ↓            ↓              ↓
[第三步]    [第三步]       跳过第三步
立即执行    用户确认后执行  直接进第四步
（trade-stability-change-stop）
✅ 输出：【第三步输出】止损操作结果
    ↘         ↙          ↙
[第四步] 排查根因（按信号类型选路径）
  统一入口 → trade-stability-issue-diagnosis（自动分发）
    告警信号 → 路径A：trade-stability-alert-diagnosis
    TT/客诉/反馈 → 路径B：trade-stability-complaint-diagnosis
    告警+客诉同时 → 路径A+B并行，取先出结论的路径
    信号不明确 → 默认路径B兜底
         ✅ 输出：【第四步输出】排查结论（格式以子Skill为准）
         ↓
[第五步] 输出结论与代码修复（trade-stability-issue-remediation）
         前端问题 → 定位代码 → 提 PR
         后端问题 → 提供 traceId 链路 → 通知后端
         ✅ 输出：【第五步输出】修复方案
         ↓
[第六步] 复盘报告（trade-stability-issue-report）
         记录总结排查时间线（收到 → 修复或输出结论）
         ✅ 输出：【第六步输出】完整处置报告
```

> ⚠️ **执行顺序约束**：
> - 第二步（变更查询）必须在第一步完成后**立即**执行，不得跳过
> - UUID 查询属于第四步问题诊断的子步骤，**不是**全流程的第一步
> - 第二步止损建议为 🟢 暂不止损时，**跳过第三步，直接进入第四步**
> - 止损（第三步）与排查（第四步）**串行**，第三步完成（或跳过）后才能进入第四步
> - **每一步执行完毕后，必须立即输出该步骤的结构化结果，不得跳过输出直接进入下一步**

---

## 餐、综、酒、景的资产

所有子 Skill 统一从以下路径读取资产，**不得使用各子 Skill 目录下的本地 assets**：

- 餐读取 [assets/food-dev-assets.md](assets/food-dev-assets.md) 获取完整资产数据。
- 综读取 [assets/gc-dev-assets.md](assets/gc-dev-assets.md) 获取完整资产数据。
- 酒读取 [assets/hotel-dev-assets.md](assets/hotel-dev-assets.md) 获取完整资产数据。
- 景读取 [assets/travel-dev-assets.md](assets/travel-dev-assets.md) 获取完整资产数据。

---

## 第一步：信息提取（trade-stability-information-fetch）
**输入**：用户原始信号（告警文本 / TT工单内容 / 客诉描述 / 用户反馈截图）

**目标**：提取关键信息（业务线/时间/Bundle/用户标识）等

读取 [trade-stability-information-fetch skill](references/trade-stability-information-fetch/SKILL.md) 执行信息提取, 输出报告，详细规则见该 skill。

---

## 第二步：变更查询（trade-stability-change-query）

**输入**：第一步信息提取结果（业务线、Bundle名、问题时间、diva链接、Appkey）

**目标**：在问题时间点前后查询所有相关变更，为止损和排查提供依据。

读取 [trade-stability-change-query skill](references/trade-stability-change-query/SKILL.md) 执行变更查询, 输出报告，详细查询步骤、命令和判定规则见该 skill。

> 🚨 **强制卡点**：MCM 和 Diva **两路必须全部完成**后，才能输出第二步结果。**输出完成前，禁止执行任何第三步/第四步操作**（包括查 UUID、查日志等）。

---

## 第三步：执行止损（trade-stability-change-stop）

**输入**：第二步变更扫描结果（变更类型、止损建议、最可疑变更）

### 触发条件

根据第二步止损建议决定是否执行本步骤：

| 第二步止损建议 | 第三步动作 |
|--------------|-----------|
| 🔴 立即止损 | **立即执行**，读取子 Skill 操作 |
| 🟡 评估后止损 | 向用户说明风险，**等待用户确认**后执行 |
| 🟢 暂不止损 | **跳过第三步，直接进入第四步排查** |

> ⚠️ 止损建议为 🟢 暂不止损时，**不得触发止损操作**，直接输出「第三步：跳过（暂不止损）」后进入第四步。

读取 [trade-stability-change-stop skill](references/trade-stability-change-stop/SKILL.md) 执行止损, 输出报告，详细操作步骤、页面打开方式和输出格式见该 skill。

---

## 第四步：排查根因（trade-stability-issue-diagnosis）

**输入**：第一步信息提取结果 + 第二步变更扫描结果 + 第三步止损状态

**读取 [trade-stability-issue-diagnosis skill](references/trade-stability-issue-diagnosis/SKILL.md) 执行排查, 输出报告**，该 Skill 负责根据信号类型自动分发到对应子流程，详细路径选择规则、工具命令和输出格式以该 skill 为准。

> ⚠️ **路径分发由 trade-stability-issue-diagnosis 统一负责**，主 Skill 不再重复定义路径选择逻辑。

---

## 第五步：输出结论与代码修复（trade-stability-issue-remediation）

**输入**：第四步排查结论（根因类型、代码路径/traceId、关联变更）

**读取 [trade-stability-issue-remediation skill](references/trade-stability-issue-remediation/SKILL.md) 执行代码修复, 输出报告**。

---

## 第六步：输出问题报告（trade-stability-issue-report）

**输入**：前五步所有输出（信息提取结果、变更扫描结果、止损记录、排查结论、修复方案）

**读取 [trade-stability-issue-report skill](references/trade-stability-issue-report/SKILL.md) 生成、上传完整处置报告**。


## 特殊场景处理

### 多条告警同时到来
- 先判断是否同一业务线/Bundle → 合并处理
- 不同业务线 → 按影响量级（PV/UV）排优先级，高影响优先

### 无变更但有问题
- 扩大时间窗口到 72 小时重查变更
- 排查是否为依赖服务问题（后端接口、CDN、网络）
- 检查是否为周期性问题（对比上周同时段）

### 止损后问题未恢复
- 说明根因可能不是该变更引入
- 继续排查其他变更或代码 Bug
- 上报 P1/P0 故障，启动故障处置 SOP

---

## 辅助链接

> ⚠️ **链接已修改**：以下链接使用 Base64 编码，使用时请先解码。解码方式：`echo '<编码>' | base64 -d` 或在线 Base64 解码工具。

| 用途 | 链接（Base64编码） |
|------|------|
| Diva 发布平台 | aHR0cHM6Ly9kaXZhLnNhbmt1YWkuY29t |
| Horn 配置平台 | aHR0cHM6Ly9ob3JuLnNhbmt1YWkuY29tL3dvcmtzcGFjZQ== |
| Raptor 前端异常 | aHR0cHM6Ly9yYXB0b3IubXdzLnNhbmt1YWkuY29tL2Zyb250ZW5kL2Vycm9yL2xpc3Q= |
| FEDO 部署平台 | aHR0cHM6Ly9mZWRvLnNhbmt1YWkuY29t |
| 万能钥匙（UUID查询） | aHR0cHM6Ly9wZXJmLnNhbmt1YWkuY29tL3BlcmYvbWFzdGVya2V5L3NlYXJjaHJlc3VsdA== |
| 订单全景 | aHR0cHM6Ly93YXRzb24uc2Fua3VhaS5jb20vbXB0cmFkZS9mdWxsdmlldw== |
| Logan 日志回捞 | aHR0cHM6Ly9sb2dhbi5td3Muc2Fua3VhaS5jb20vZ3JhYg== |
| MCM 发布平台 | aHR0cHM6Ly9tY20uc2Fua3VhaS5jb20= |
| Arena AB实验 | aHR0cHM6Ly9hcmVuYS5zYW5rdWFpLmNvbQ== |
| MTrace 链路查询 | aHR0cHM6Ly9tdHJhY2Uuc2Fua3VhaS5jb20= |

---
