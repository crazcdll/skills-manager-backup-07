# Changelog — uuid-error-query

## v0.3.0 (2026-06-09)

- 修正 crash/anr/watchdog 查询逻辑（修复次数被严重统计偏小，实测某设备真实 21 次被错报成 1 次）：
  - **明确 Crash/ANR 上报时间 ≠ 发生时间**（崩溃后下次启动 APP 才上报），查询窗口应按「上报/落库时间」（接口默认索引时间，对应 `mt_datetime`），用**一个 7 天整段区间一次查满**（`--size 200 --excludes log -t 120000`），`data[]` 数组长度即真实总次数
  - **废弃 v0.2.0 引入的「逐天循环」逻辑**：上一版强制按 `crashTime` 逐天拆分查询，而 `crashTime` 在部分设备上为空/脏数据（恒为 `1970-01-01 08:00:00`），导致逐天过滤大量漏数据
  - **时间线排序口径（按类型区分发生时间字段）**：实测发现 **watchdog 有可靠的 `foomTime`（真实发生时间，且与上报时间仅差几秒，几乎实时上报）**，故 watchdog 排时间线优先用 `foomTime`；**crash/anr 才走 `crashTime` 脏数据回退逻辑**（crashTime 优先，脏数据时回退）；任一发生时间字段取到离谱值（`1970`/空/明显超出查询窗口）时统一回退到 `mt_datetime` 并标注「(上报)」；查询窗口一律按上报时间（`mt_datetime`），与排序口径分离，不再混用
  - 补充返回字段时间含义说明：区分 `crashTime`（crash/anr 发生时间）、`foomTime`（watchdog 发生时间，可靠）与 `mt_datetime`/`uploadTime`/`ts`（上报时间）
- 修正业务 JS 异常（MRN）被错报成个位数的首要根因：`get-summary-table` 走 `--project-id -1 --fe-type MRN` 跨项目查询很重，**默认 30s 必超时**，必须传 `-t 120000`；⚠️超时（`TIMEOUT`）绝不能当成「无数据/0 条」；明确 JS 异常总次数 = `data.table.rows[]` 里所有聚类 `COUNT` 之和（实测 17 聚类合计 123 次，最大单聚类 82 次而非总数），字段名为大写 `COUNT`/`main`/`CATEGORY`/`USER_COUNT`
- **依据 KM 需求文档（collabpage/2767631414）+ raptorfe CLI 内置「MRN 跨项目查询」官方示例，校正 JS 异常命令的两个致命点**（之前命令实跑返回 `table.total=0` 被误判为查不到，数据是 LLM 凑的）：
  - **`-t` 必须放全局位置**（`raptorfe -t 120000 web error get-summary-table ...`）：`web error` 子命令本身**没有** `--timeout`，旧文档里写在子命令上的 `--timeout 60000` 无效；`get-error-detail` 同理
  - **`--sort-field DATE` 不可省**：实测漏掉它 `get-summary-table` 会返回 `table.total=0`（看似查不到），加上后正常返回 17 个聚类；`--union-id` 接收的就是 64 位 uuid/deviceId（CLI 示例 + KM 文档一致确认）
  - 实跑核对该设备（美团iOS，6/2~6/9）：JS 异常 17 聚类合计 **123 次**，其中「下单任务按钮配置下发不符合预期」单聚类 **82 次**（即用户在页面看到的 82，是单聚类数而非设备总数）

## v0.2.0 (2026-06-09)

- 修复 crash/anr/watchdog 等稳定性异常次数被严重统计偏小的问题：强制真正逐天循环查询、`--size` 调大到 100、按「每天 data 数组长度之和」累加计数，禁止只查一天或只取首条
- 修复业务 JS 异常（MRN）数据不准与漏查：明确为**必查项**（iOS 也不可跳过）；`get-summary-table` 强制传 `--limit 200 --page-size 200` 拉全聚类；修正返回解析路径为 `data.table.rows[]`（`get-error-detail` 为 `data.result.table.rows[]`）；明确 JS 异常总次数 = 所有聚类 COUNT 之和
- 新增完整的 Raptor 页面链接拼接规则：稳定性异常按 KM 规范拼 `crash?project=&type=&filter=[{k,v}]`（含 URL 编码注意点），业务 JS 异常拼 `mrn-dashboard/.../js-detail?userId=<uuid>`，要求报告里每类异常都附带拼好的真实链接
- 报告模板升级：总览表新增「Raptor 链接」列，业务 JS 异常补充逐聚类清单与合计行

## v0.1.0 (2026-06-08)

- 初始版本
- 支持按 uuid（deviceId）检索最近 7 天的全类型异常日志，逐类拉详情后按时间线汇总成报告
- 稳定性指标：crash / anr / watchdog / catchexception（仅 Android）/ lag_log，通过 `raptorfe crash detail list` + `crash detail get`，`--eq "deviceId,<uuid>"` 逐天查询
- 业务 JS 异常：MRN 容器，通过 `raptorfe web error get-summary-table / get-error-detail / get-log-detail`，`--union-id` + `--fe-type MRN --project-id -1` 跨项目检索
- 覆盖美团/外卖/点评，Android/iOS/HarmonyOS
- 内置 APP 中文名 → project 映射，未命中时通过 `raptorfe perf app list` 动态查询
- 明确约束：最多查 7 天且需标注范围、按天拆分查询、APP 未知先问、不做 ID 互转（与万能钥匙能力区分）
