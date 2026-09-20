# uuid-error-query — UUID 查询异常日志

用户给出一个 **uuid（设备标识 deviceId，通常 64 位十六进制）** 并提出查询/排查异常诉求时，检索该设备在**最近 7 天**内发生过的**所有类型异常**，逐类拉取日志详情，最后按时间线汇总成一份完整的「用户异常画像」报告。

---

## 能做什么

- 按 deviceId 逐天检索最近 7 天的稳定性异常：崩溃（crash）、ANR、异常退出（watchdog/FOOM）、捕获异常（catchexception，仅 Android）、卡顿（lag_log）
- 跨项目检索该设备的业务 JS 异常（MRN 容器，通过 `--union-id` + `--fe-type MRN --project-id -1`）
- 逐条拉取完整堆栈日志（iOS `iosLog` / Android `androidLog` / Web `stackInfo`）
- 把散落在崩溃、ANR、卡顿、JS 异常等多个系统里的问题，按发生时间倒序串成一份汇总报告 + 综合根因分析

## 触发示例

```
帮我查一下这个 uuid 0000...5406 最近发生过哪些异常
这个设备最近有没有崩溃？deviceId 是 xxxx
排查一下这个用户的异常，uuid: xxxx（美团iOS）
查一下这个 uuid 发生过什么问题
```

> 触发要点：用户给出 uuid（一般 64 位十六进制）**且**带明确的"查异常/排查异常"诉求。
> 若用户没说 APP，先提问让其提供 APP 名称（含平台，如「美团iOS」），拿到后再查。

## 与其他子技能 / 技能的区别（避免误路由）

| 用户意图 | 应走哪个技能 |
|---|---|
| 给 uuid（deviceId）+ **查/排查异常日志** | **本技能 uuid-error-query** |
| uuid / userid / dpid / unionid 之间 **ID 互转**，或提及"万能钥匙 / masterkey / 查设备信息" | **直接拒绝**，引导去 Raptor 万能钥匙页面 |
| 不带 uuid，分析某 APP 整体 Crash/ANR/FOOM 波动 | `crash-wave-analysis` |
| 不带 uuid，只查某指标的数量/率 | `raptorfe-allquery` |
| 收到告警消息要做根因分析 | `infra-app-stability` → `root-cause` |
| 分析 Web/OWL 端 JS 异常整体波动 | `owl-web-error-analysis` |

> 核心区分点：**有具体 uuid + 排查该设备异常诉求** 才走本技能；只要是 **ID 互转 / 万能钥匙** 一律拒绝，不要进入本技能的查询流程。

## 重要约束

- **最多查最近 7 天**，且最终报告必须写明查询的具体日期范围。
- **稳定性指标必须按天拆分查询**（每天一个 `00:00:00 ~ 23:59:59` 区间），不要一次查 7 天。
- **APP 未知必须先问**，不要默认猜测 project。
- **不做 ID 互转**：本技能只用 uuid（deviceId）检索异常日志。
- **隐私保护**：仅在用户有明确排查诉求时查询，不主动外泄设备/用户信息。

## 依赖

- `raptorfe` CLI：`npm install -g @mtfe/raptorfe-cli --registry https://r.npm.sankuai.com/`
- 鉴权全自动（内置 SSO），命令沉默 10～30s 属正常；遇大象 App 授权提示引导用户确认，不索要 Cookie。

## 涉及的底层命令

| 命令 | 用途 |
|---|---|
| `raptorfe perf app list` | APP 中文名 → project 映射 |
| `raptorfe crash detail list` | 按 deviceId 逐天查某类型事件列表（`--eq "deviceId,<uuid>"`） |
| `raptorfe crash detail get` | 拉单条稳定性事件完整堆栈 |
| `raptorfe web error get-summary-table` | 按 union-id 查 MRN 异常聚类列表 |
| `raptorfe web error get-error-detail` | 查某 MRN 异常明细（拿 errorLogId） |
| `raptorfe web error get-log-detail` | 查单条 MRN 异常完整堆栈 |

详细的查询流程、参数说明和报告模板见 [SKILL.md](./SKILL.md)。
