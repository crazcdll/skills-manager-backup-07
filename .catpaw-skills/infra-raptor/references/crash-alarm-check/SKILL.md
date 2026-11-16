---
name: crash-alarm-check
version: "5.0.0"
description: >
  【已迁移·转发壳】Crash / ANR / FOOM / Watchdog 告警排查与根因分析。
  本子能力的分析逻辑已统一迁移至 infra-app-stability 技能的 root-cause 子技能，
  本文件仅保留为转发壳，收到告警后一律转发至 root-cause 执行。
  覆盖美团/点评/外卖，Android/iOS/鸿蒙。
  触发词：crash告警、crash新增异常、P1 crash、P2 crash、P3 crash、分析crash告警、
  crash告警排查、新增Crash、crash详情分析、帮我看下这个告警、crash数量异常、crash激增、
  anr告警、ANR告警、anr分析、ANR排查、anr激增、anr异常、anr堆栈、P3 anr、P2 anr、
  foom告警、FOOM告警、foom分析、FOOM分析、watchdog告警、watchdog分析、内存告警、低内存崩溃

metadata:
  skillhub.creator: "nieyunlong"
  skillhub.updater: "zhangxinyue27"
  skillhub.version: "V9"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "6278"
---

# Crash / ANR / FOOM / Watchdog 告警排查（已迁移）

> ⚠️ **本子能力已迁移。** Crash/ANR/FOOM/Watchdog 告警的根因分析逻辑已统一收敛至
> **`infra-app-stability` 技能的 `root-cause` 子技能**。
> 本文件仅作为转发壳保留，不再包含分析流程。

## 为什么迁移

`root-cause` 完整覆盖了本技能原有的全部能力（告警解析 → 聚类列表 → 趋势分析 → 维度分布 + DAU 偏差 → 堆栈深度分析 ≥5 条 → 输出报告），并额外提供两项本技能不具备的能力：

- **数据波动前置判断** — 分析前先识别基线为 0、聚类分散、低版本存量、短时窗口小样本、历史波动区间内等伪告警场景，避免无效深度分析
- **变更关联定位** — 通过 crash-change-locator Mode A，用聚类 UUID + 时间窗口关联 Diva / Horn / Native 变更，输出带置信度的变更归因

## 执行动作（唯一）

当本子能力被路由命中时，**不要在此处执行任何分析**，直接执行以下转发：

1. **Read skill 文件**：`skills-market/infra-app-stability/references/root-cause/SKILL.md`
   （若路径不存在，回退尝试仓库布局 `skills-market/infra-app-stability/skill/references/root-cause/SKILL.md`）
2. **按 root-cause 的模式 A（告警消息/聚类标识）流程执行**完整分析
3. 将用户原始告警消息原文透传给 root-cause，由其自行解析以下参数：
   - `[P\d]` → 告警等级（P1/P2/P3/P4）
   - `[crash]` / `[anr]` / `[foom]` / `[watchdog]` → 告警类型
   - `GroupBy：message=` 后的值 → 崩溃聚类标识（堆栈 hash）
   - `统计开始时间：` / `统计结束时间：` → 告警统计周期
   - `[[聚类列表|URL]]` 中的 URL → project / type / filter 参数

> 💡 转发时无需向用户二次确认，也无需重复回述告警内容——root-cause 会自行完成参数回述与路由说明。

## 边界说明

以下场景**不属于**本转发壳，请按原路由处理：

| 场景 | 正确路由 |
|---|---|
| 用户主动描述「分析 Crash/ANR/FOOM 趋势波动」，无告警文本 | `crash-wave-analysis` |
| 用户发送 `raptor.mws.sankuai.com/crash/...` 链接 + 分析诉求 | `crash-wave-analysis` |
| 消息含「⚠️ 请使用 infra-raptor skill」或「这是一个raptor页面的请求」（Raptor Agent 来源） | `crash-wave-analysis` |
| 仅统计崩溃率/崩溃量趋势图 | `component-crash-chart` |
| 含 `[前端异常]` 标签的 Web 端告警 | `owl-web-error-analysis` |
