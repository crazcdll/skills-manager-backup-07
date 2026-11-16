---
name: raptor-query-cli
description: "美团 Raptor 监控平台 CLI 工具。当用户提供 raptor.mws.sankuai.com 的 URL、或提到 Raptor 查询、监控指标、QPS、TP99、成功率、报错分析、慢SQL、慢接口、transaction、business、topology、host-metrics、logview、主机指标、业务指标、服务健康检查、traceId链路追踪、RPC调用分析、接口级拓扑、接口上下游依赖、离线统计时使用。"
version: "1.12.0"
appkey: com.sankuai.mcpappkey.raptor

tags: ["MWS云管", "raptor", "可观测"]
space: "mws"
logo: "mws-official"

metadata:
  skillhub.creator: "zhaojunfeng03"
  skillhub.updater: "wumingyan04"
  skillhub.version: "V38"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "4657"
  skillhub.high_sensitive: "false"
---

## [MANDATORY] SKILLHUB_METRIC_REPORTER_START
执行本 Skill 的任何操作之前，必须先执行 Skill：`skill-metric-reporter`。
按照 `skill-metric-reporter` 的要求完成 `skill_start` 上报后，再去继续本 Skill 正文。
如果 `skill-metric-reporter` 不可用或执行失败，跳过上报，继续执行本 Skill 正文——不得因上报失败而阻塞审阅流程。
本 Skill 全部操作完成后，同样按照 `skill-metric-reporter` 的要求完成 `skill_end` 上报。
## [MANDATORY] SKILLHUB_METRIC_REPORTER_END

# raptor-query-cli (v1.12.0)

美团 Raptor 监控平台 CLI 工具

> **IRON LAW**：只读工具，禁止修改任何 Raptor 配置或数据；所有命令仅执行查询。

## 适用场景

- 查询生产服务的 QPS、TP99、成功率等性能指标
- 排查报错、异常、慢接口、慢 SQL 问题
- 查看接口/服务上下游拓扑、主机指标、业务打点
- 通过 traceId 分析调用链、定位性能瓶颈
- 用户提供 `raptor.mws.sankuai.com` URL 需要解析查询
- 查询 Appkey 离线请求量统计与排行

> ⚠️ **本工具仅连接生产环境**。Test 环境用 `raptor-query-test`（skill #11902），Keeta 环境用 `raptor-query-keeta`（skill #13937）。

## 如何调用

`raptor-prod` 与本 SKILL.md 位于同一目录，未注册到系统 PATH，需通过路径调用。

**执行步骤：**

1. 根据本 SKILL.md 的文件路径，去掉文件名即得到 skill 目录，`raptor-prod` 就在该目录下
2. 首次使用前，对上一步定位到的 `raptor-prod` 文件执行 `chmod +x` 确保可执行权限（zip 安装方式可能丢失权限）
3. 直接用完整路径执行，脚本内部已处理工作目录，无需 `cd`

## Token 配置

默认使用 MWS 共享 Token，开箱即用。高并发或遇到限流时换个人Token：

```bash
export RAPTOR_API_TOKEN=your_token_here   # 优先级高于默认
```

申请方式见 [Token 管理 Wiki](https://km.sankuai.com/collabpage/2712642356)

## 命令列表

所有命令均支持 `--json` 输出原始数据。

| 命令 | 别名 | 说明 |
|------|------|------|
| `types` | | 获取类型列表（推荐第一步，`-s` 可省略，默认 1h） |
| `names` | | 获取名称列表（`-s` 可省略，默认 1h） |
| `transaction` | `tx` | 查询 Transaction 指标（QPS/TP99/成功率） |
| `event` | `ev` | 查询 Event 指标 |
| `problem` | `pb` | 查询 Problem 指标（异常/报错统计） |
| `logview` | `lv` | 获取 Logview IDs |
| `logview-detail` | `ld` | 查询 Logview 详情（`--url` 支持直接粘贴 raptor 页面 URL） |
| `ips` | | 获取 IP 列表 |
| `hosts` | | 获取主机列表 |
| `sets` | | 查询机器分组列表（set/灰度分组/机房/region/custom）；`--group <分组名>` 列出该分组下机器 |
| `host-metrics` | `hm` | 查询主机指标时序 / 列出自定义指标（`--list`） |
| `business` | `bk`/`biz` | 业务指标查询 |
| `topology` | `topo` | 获取上下游拓扑 |
| `topo-api` | `topoapi` | 接口级拓扑（1跳，不递归） |
| `methods` | `method` | 查询指定 appkey 下的接口/方法列表（支持按日期、set 过滤） |
| `rpc` | | 查询上/下游 RPC 调用统计 |
| `trace` | `tr` | 按 traceId 查看调用链路（全量或按 appkey 精准过滤） |
| `offline-stat` | `ofs` | 离线统计（event/transaction/problem 三种维度），Appkey 请求量/成功率排行 |

## 核心参数（transaction / event / problem）

| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `-a, --appkey` | ✅ | | 服务名 |
| `-t, --type` | ✅ | | 类型（URL/System/SQL/error/long-sql） |
| `-n, --name` | | All | 接口名称 |
| `-i, --ip` | | All | IP / set名，**支持逗号分隔多个**（如 `10.1.1.1,10.1.1.2`），默认 All |
| `-s, --start` | | 5m | 时间范围（5m/1h/1d），支持绝对时间 `2026-04-06 13:57:00` 或紧凑格式 `20260406135700` |
| `-e, --end` | | now | 结束时间（绝对时间，配合 `-s` 绝对时间使用）；host-metrics 因 `-e` 为 `--endpoints`，用 `--end` |
| `-q, --query-type` | | auto | 聚合粒度：second/minute/hour/day/week/month；默认 auto 按时间跨度自动选择 |

**event 额外参数：** `--trend`（多 type/name 时逐一输出时序趋势）；`-q day/week/month` 可获取整体聚合值（非算术均值）

**host-metrics 额外参数：** 详见 [references/params-host-metrics.md](references/params-host-metrics.md)

**business 额外参数：** 详见 [references/params-business.md](references/params-business.md)

**rpc 额外参数：** 详见 [references/params-rpc.md](references/params-rpc.md)

**trace 额外参数：** 详见 [references/workflow-trace.md](references/workflow-trace.md)

**methods 额外参数：** `--start-date`（起始日期，yyyy-MM-dd）、`--set`（set 信息）、`--json`。详见 [references/params-methods.md](references/params-methods.md)

**topology 额外参数：** `-d up|down|all`（默认 all）`-l`（条数，默认 20）`--sort count|tp99|fail`

**topo-api 额外参数：** `-m`（接口名，必填）`-d up|down|all`（默认 all）`--timeout`（超时秒数，默认 30）

**logview 额外参数：** `--data-type`（problem/event/transaction）`-l`（条数，默认 10）`-i`（IP）

**logview-detail 额外参数：** `--url`（Raptor 页面 URL，自动提取参数）`--metric-type`（类型过滤）`-d`（最大展示层级，默认 10）

**names 额外参数：** `--data-type`（默认 transaction，可切 event/problem 查对应 names）

**offline-stat 额外参数：** 低频命令，详见 [references/params-offline-stat.md](references/params-offline-stat.md)

## 推荐工作流程

### 服务健康全景
```
raptor-prod types -a <appkey>          → 了解服务上报了哪些类型
raptor-prod tx -a <appkey> -t URL      → QPS/TP99/成功率
raptor-prod pb -a <appkey> -t error    → 报错统计
raptor-prod topo -a <appkey>           → 上下游依赖
```
> 💡 `types`/`names` 默认查最近 1h，低频服务可能无数据。若返回为空，用 `-s 24h` 或 `-s 7d` 扩大时间窗口重试。

指标参考：URL TP99 < 100ms 正常；成功率 < 99.9% 需关注

### 异常排查（Problem → Logview → 堆栈）
```
raptor-prod pb -a <appkey> -t error                 → 报错统计
raptor-prod lv -a <appkey> -t error                 → 获取 Logview IDs
raptor-prod ld --url "<raptor.mws.sankuai.com URL>" → 查详细堆栈
```

### 接口性能分析 & 链路追踪

接口慢 → `tx` 看 TP99 → `methods` 查服务接口列表 → `rpc` 看下游耗时 → `topoapi` 看上下游依赖 → `trace` 定位具体 span

详细参数与示例见 [references/workflow-trace.md](references/workflow-trace.md)

**常见 Type 速查：** 详见 [references/common-types.md](references/common-types.md)

## Anti-Pattern

- ❌ 不要在没有 `-a appkey` 的情况下猜测服务名，直接报错让用户提供
- ❌ 不要把 Test/Keeta 环境数据当生产数据解读，环境不匹配直接提示换 skill
- ❌ 不要把 `--json` 输出当最终答案展示给用户，应解析后输出可读结论
- ❌ 限流失败后不要立即重试；等 10–15s 再试，或按提示执行 `export RAPTOR_API_TOKEN=xxx`

## Changelog

- v1.12.0 (2026-09-04): 适配 Raptor MCP 工具升级：trace 全量查询由 `traceid_without_innner` 切换为 `get_tracedetail_by_traceid`，按 appkey 查询由 `get_trace_info_by_traceid_and_appkey` 切换为 `get_by_traceid_and_appkey`；修复 SSE 解析固定按消息序号取响应的问题，改为按 JSON-RPC id 匹配。接口级拓扑由 `topology_api_onestep` 切换为 `get_method_topology_onestep`；新增 `methods`/`method` 命令，支持通过 `get_methods_by_appkey` 查询服务接口列表。

[历史版本](references/changelog.md)
