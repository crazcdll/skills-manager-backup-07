---
name: trade-stability-change-query
description: 交易前端变更查询专家。作为稳定性全流程第二步，在问题时间点前后查询所有相关变更，为止损和排查提供依据。
  支持两类变更查询：MCM 前端代码发布（必查）、Diva Bundle 发布（必查）。
  核心能力：并行查询 MCM + Diva → 判断变更相关度（高/中/低）→ 给出止损建议 → 输出最可疑变更。
  输入：业务线、Bundle名、问题时间（来自第一步信息提取结果）。
  输出：变更扫描结果（各系统变更列表、相关度评级、止损建议、最可疑变更）。
  触发词：查变更、变更查询、查发布记录、MCM查询、Diva查询。
---

# 变更查询

## 前置输入

来自第一步信息提取结果：

| 字段 | 用途 |
|------|------|
| 业务线 | 变更相关度判断 |
| Bundle / 页面 | Diva 查询目标 bundle；MCM 过滤关键词 |
| 问题时间 | 变更时间窗口基准（前 24 小时） |
| Appkey | MCM 过滤相关服务变更 |

> 🚧 Horn 配置变更和 AB 实验变更暂不执行，如需请手动查询。

---

## 强制约束

1. **MCM 和 Diva 两路必须全部完成**才能输出结果。任何一路失败必须重试，不得跳过。
2. **输出前禁止执行任何第三步/第四步操作**（包括查 UUID、查日志等）。
3. **严禁分析代码**：本步只负责「找到哪个版本上线了 + 确认发布时间」。commitUrl 仅记录，供第四步使用。

---

## 执行

MCM 和 Diva 必须**并行**发起，不得串行等待。两路完成后统一输出。

```bash
startTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $startTime
```

### MCM 前端代码发布

```bash
mcm plan calendar \
  --org 88888-153262-114609-114621-40010700 \
  --start "{问题时间前24小时 yyyy-MM-dd HH:mm:ss}" \
  --end   "{问题时间 yyyy-MM-dd HH:mm:ss}"
```

> 时间格式必须为 `yyyy-MM-dd HH:mm:ss`。

返回关键字段：

| 字段 | 说明 |
|------|------|
| `planName` / `name` | 变更计划名称 |
| `appKey` | 变更涉及的服务 Appkey |
| `creator` / `operator` | 发布人 mis_id |
| `planStartTime` / `startTime` | 变更开始时间 |
| `planEndTime` / `endTime` | 变更结束时间 |
| `status` | 计划状态（RUNNING / DONE / WAIT_RUNNING 等） |

---

### Diva Bundle 发布

```bash
diva bundle tasks --name {bundle_name} --days 2 --env prod -o json 2>/dev/null
```

> `--days 2` 覆盖问题时间前 48 小时；`--env prod` 查生产环境。如需查测试环境用 `--env test`。

返回 JSON 数组，每条记录是一个发布任务。关键字段：

| 字段 | 说明 |
|------|------|
| `bundleName` | Bundle 名称 |
| `bundleVersion` | 发布版本号 |
| `taskType` | 任务类型：`PHASED_PUBLISH`（分阶段发布）/ `INSTANT_PUBLISH`（即时发布）/ `UPLOAD_BUNDLE`（上传打包） |
| `bizType` | 业务类型：`PUBLISH` / `UPLOAD_BUNDLE` |
| `platform` | 平台：`Android` / `iOS` / `HarmonyOS` |
| `app` | App：`group`（美团）/ `Nova`（点评）等 |
| `env` | 环境：`prod` / `test` |
| `createTime` | 任务创建时间（ISO 8601，UTC） |
| `updateTime` | 任务最后更新时间（分阶段发布每阶段推进会更新） |
| `expectPublishTime` | 预期发布时间（分阶段发布的计划开始时间） |
| `operateTimestamp` | 操作时间戳（毫秒，最后一次状态变更时间） |
| `operator` / `operatorData.misId` | 发布人 MIS / 姓名 |
| `taskStatus` | 任务状态：`1` = 成功完成 |
| `approvalStatus` | 审批状态：`3` = 已审批（prod）/ `5` = 免审批（test） |
| `publishTaskId` | 关联的发布任务 ID |

**过滤规则**：

1. 排除 `taskType = UPLOAD_BUNDLE`（仅打包上传，未发布到线上）。
2. 按 `updateTime` 降序排列，取最近一条作为判断基准。
3. 若同一版本多平台多 App 发布，合并为一条记录（版本号相同算一次变更）。

**分阶段发布时间判断**：

| taskType | 时间基准 | 说明 |
|----------|---------|------|
| `INSTANT_PUBLISH` | `createTime` | 即时发布，创建即全量生效 |
| `PHASED_PUBLISH` | `updateTime` | 分阶段发布，`updateTime` 为最近一个阶段完成时间；`expectPublishTime` 为首阶段开始时间 |

**关键判断**：

| updateTime 距问题时间 | 动作 |
|---|---|
| **> 48 小时** | 判定无近期 Diva 变更，跳至输出 |
| **≤ 48 小时** | 提取 `bundleVersion`、`operator`、`createTime`、`updateTime`，计算时间差用于相关性判断 |

**获取 commit 信息（止损必备）**：

`diva bundle tasks` 返回的 JSON 不含 commit 信息，需额外执行 `diva bundle versions` 获取：

```bash
diva bundle versions {bundle_name} 2>/dev/null
```

返回格式化文本（非 JSON），每条版本记录包含：
- 版本号、在线状态（🟢在线 / ⚪未在线）
- 打包时间、发布时间、上线时间
- 发布类型（分阶段发布 / 立即发布）
- 各平台发布状态和发布人
- **commit 链接**（格式：`https://dev.sankuai.com/code/repo-detail/{repo}/commit/{hash}`）

**操作要点**：
1. 从 `diva bundle versions` 输出中找到 `diva bundle tasks` 确认的 `bundleVersion`，记录其 **commit 链接**（供第四步代码分析使用）。
2. 找到该版本的**上一在线版本**（即回滚目标），记录其版本号和 commit 链接（供第三步止损使用）。
3. 若该版本未在线（⚪），说明还在灰度中，止损方式为「取消灰度」而非「回滚」。

> ⚠️ CLI 认证失败时按错误提示修复后重试，不得跳过 Diva 查询。
> ⚠️ 若 `--env prod` 无结果但 `--env test` 有结果，说明仍在测试环境发布未上生产，记录但相关度降一级。

---

## 变更相关性判断矩阵

**时间差基准**：Diva 用 `updateTime`（分阶段发布取最近阶段完成时间），MCM 用 `planEndTime`。

| 变更时间差 | 相关度 | 处置建议 |
|-----------|--------|---------|
| < 6 小时 | 高（同 Bundle 变更 或 MCM 同功能变更） | 🔴 立即止损 |
| < 6 小时 | 低（无 Bundle 变更 且 MCM 不同功能） | 🟡 评估后决定 |
| 6h ~ 24h | 高（同 Bundle 变更 或 MCM 同功能变更） | 🟡 评估后止损 |
| 6h ~ 24h | 低（无 Bundle 变更 且 MCM 不同功能） | 🟢 暂不止损 |
| > 24 小时 | — | 🟢 无近期变更 |

> **分阶段发布**：`taskType = PHASED_PUBLISH` 且 `expectPublishTime` 距问题 < 6 小时，按 < 6 小时判定（首阶段已影响部分用户）。

---

## 输出

```bash
endTime=$(date "+%Y-%m-%d %H:%M:%S") && echo $endTime
```

✅ **第二步：变更查询报告**（完成时间：{endTime}  耗时：{约 X 分钟}）

| 系统 | 变更内容 | 发布时间 | 发布人 | 相关度 |
|------|---------|---------|-------|-------|
| MCM | {变更名称 / 未发现} | {planEndTime} | {mis_id} | 高/中/低/无 |
| Diva | {bundle名 版本号 / 未发现} | {updateTime（taskType）} | {mis_id} | 高/中/低/无 |

> Diva 发布时间格式：`2026-08-10T15:00:07（PHASED_PUBLISH）` 或 `2026-08-11T07:43:48（INSTANT_PUBLISH）`。
> 若为分阶段发布且 `expectPublishTime` 早于 `updateTime`，附加说明：`首阶段 12:32 / 最近阶段 15:00`。

> 🔴 高相关度变更在行末追加 `← 🔴 高度可疑，距问题时间仅 {X} 分钟`。

**止损建议**：🔴 立即止损 / 🟡 评估后止损 / 🟢 暂不止损

**最可疑变更**：{变更信息 或「无变更」}

**commitUrl（备查）**：{可疑版本 commit 链接 或「无」}（⚠️ 仅记录，第四步使用）

**回滚目标版本**：{上一在线版本号}（commit: {链接}）— 供第三步止损使用

➡️ 进入第三步：{执行止损 / 跳过止损，直接排查}
