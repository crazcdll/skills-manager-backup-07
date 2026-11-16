---
name: mtcli-usage
description: "当用户希望 AI 使用、解释或排查 mtcli 本身时使用：发现内部 API 服务、查看 service/resource/method schema、规划或执行 mtcli 调用、使用 tools call、处理 mtcli 鉴权/缓存/调试、解释 --params/--json/--dry-run/--no-cache/--mtcli-target-env/--mtcli-schema-env 等语义。用户询问 mtcli 怎么用、命令为什么失败、unknown flag/缺必填 flag、auth sso、MOA、schema 环境、target 环境、cache refresh、调用日志、verbose 排查时也使用。触发词：mtcli、tools call、schema、服务列表、查看接口参数、调用内部接口、dry-run、cache refresh、auth sso、鉴权、缓存、报错排查、调用日志。跳过：修改 mtcli 源码、Go 实现、npm 打包、发布二进制、或非 mtcli 的 API 客户端。"
version: 1.0.17
appkey: com.sankuai.raptor.iconfont.websdk
tags: mtcli,api,tool,meituan
visibility: private

metadata:
  skillhub.creator: "wangtianyi18"
  skillhub.updater: "wangtianyi18"
  skillhub.version: "V28"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "37285"
  skillhub.high_sensitive: "false"
---

# mtcli Agent 使用指南

**IRON LAW: 先查 schema/contract；未知或可能有副作用的调用只做 dry-run；不要猜 service、resource、method、参数或鉴权。**

这个 skill 的目标是让 AI 会使用 `mtcli`，不是给用户写 README。只保留会改变执行决策的规则，命令细节放到 references。

对用户解释或展示命令时，默认使用占位符，不主动暴露真实服务名、方法名、账号、appkey、URL、业务参数值或具体内部接口示例。只有当用户已经提供了具体值，才可以在回答和命令里使用这些值。

统一占位符：

- `<service>`、`<resource>`、`<method>`
- `<service>.<resource>.<method>`
- `<service_resource_method>`
- `<param>`、`<value>`、`<json-object>`、`<mis>`、`<env>`

## 核心原则

- 先检查，再调用。不要猜 service、resource、method、必填参数、鉴权方式或 body 结构。
- 使用最窄的发现路径。优先服务索引、单服务 schema 和 `tools list --service <service>`；`tools list --filter <keyword>` 主要缩小返回结果，不保证降低远端扫描成本。
- 未确认的 method 一律按可能有副作用处理。
- 不确定调用形态或可能有副作用时，先 dry-run。
- tools 模式不使用业务独立 flag：path/query/header 放 `--params`，body 放 `--json`。
- 动态命令中 `--params` 是 path/query/header 的批量入口，`--headers` 可专门覆盖 header 参数；`--json` 是 request body 入口。
- 每次使用本 skill 先检查全局 npm 包版本；如果未安装或落后于已发布版本，主动升级后再继续。
- 查询 CLI 自报版本优先用 `mtcli --version`；该 flag 从 mtcli `1.1.2` 起可用，旧版本若报 `unknown flag: --version`，再退回 `mtcli version`。
- `tools list` 只返回轻量摘要，不含参数/响应 schema；需要调用前仍要用 `tools describe <service>` 或 `schema <service>.<resource>.<method>` 检查详情。
- `cache refresh` 全量刷新已禁用；只能用 `cache refresh --service <service>`。
- 区分两类环境：`--mtcli-schema-env` 控制 schema/config discovery 和 discovery SSO；`--mtcli-target-env` 控制业务目标 `serviceConfig[env]`、目标鉴权和目标 SSO。
- 未传 `--mtcli-schema-env` 时，schema discovery 沿用 `--mtcli-target-env`；显式 `MT_REMOTE_URL` / `MT_REMOTE_BASE` 的优先级更高。
- SSO 鉴权按用途分环境：元数据拉取用 schema env；真实业务接口用 target env。`test`、`dev`、`test-keeta`、`dev-keeta` 走线下 SSO；`prod`、`staging`、空值、`prod-keeta`、`staging-keeta` 走线上链路。
- 线上 SSO 优先级：已缓存目标 `ssoid` > MOA local exchange（支持单 audience 和多 audience set）> `auth sso login` 缓存的线上 access token 做 Token Exchange。线下 SSO 和线下 discovery 不使用 MOA。
- 用户要查看某次命令的调用日志或排查一次具体调用时，优先在原命令上加 `-v` 或 `--verbose`，并保留原来的 schema/target 环境参数。

## 反模式

- 不要把 dry-run 输出描述成远端 API 调用成功。
- 不要推荐裸 `cache refresh`、裸 `tools list` 或无范围的 `generate-skills`，除非用户明确要全量。
- 不要把 `tools list --filter` 当作等价的远端窄查询；要降低范围优先用 `--service`。
- 不要把 body 字段拆成业务独立 flag；body 只走 `--json`。
- 不要为 tools call 生成业务独立 flag；只用 `--params` 和可选 `--json`。
- 不要为了排查引入额外 flag；调用日志优先用 `-v` / `--verbose`。

## 路由表

| 用户意图 | 首选路径 | 参考 |
|---|---|---|
| 找服务或确认服务名 | 服务发现 | [references/discovery.md](references/discovery.md) |
| 查看服务/资源/方法结构 | schema 检查 | [references/discovery.md](references/discovery.md) |
| 规划或执行一个 API 调用 | 请求流程 | [references/request-flow.md](references/request-flow.md) |
| 让 AI 用结构化 tool contract 调用 | tools 模式 | [references/tools-auth-cache.md](references/tools-auth-cache.md) |
| 处理鉴权、缓存、调试问题 | auth/cache/debug | [references/tools-auth-cache.md](references/tools-auth-cache.md)、[references/auth.md](references/auth.md) |
| 回答命令和 flag 用法 | 命令模板 | [references/command-reference.md](references/command-reference.md) |
| 排查 CLI 本地解析/系统级输入错误 | 错误排查 | [references/errors.md](references/errors.md) |
| 判断服务可用性 | 实时状态策略 | [references/services.md](references/services.md) |

## 阶段 0：版本检查

入口条件：本 skill 被触发，且接下来需要运行或指导 `mtcli`。

1. 查询已发布的 npm 包版本。
2. 查询本机全局安装版本。
3. 查询 CLI 自报版本，优先 `mtcli --version`，旧版本回退到 `mtcli version`。
4. 如果未安装或版本落后，主动安装/升级到最新版本。
5. 如果 npm 包版本和 CLI 自报版本不一致，记录为发布包/二进制版本不一致；继续只读检查，不要因此执行高风险真实调用。
6. 升级失败时，向用户报告失败原因，并继续用现有版本做只读检查；不要在版本不确定时执行高风险真实调用。

模板：

```bash
LATEST=$(npm view @dp/mtcli version --registry http://r.npm.sankuai.com 2>/dev/null)
INSTALLED=$(npm list -g @dp/mtcli --depth=0 2>/dev/null | grep @dp/mtcli | sed 's/.*@//')
CLI_VERSION=$(mtcli --version 2>/dev/null || mtcli version 2>/dev/null || true)

if [ -z "$INSTALLED" ] || [ "$INSTALLED" != "$LATEST" ]; then
  npm i -g @dp/mtcli@$LATEST --registry http://r.npm.sankuai.com
fi
```

出口条件：mtcli 已是最新版本，或已明确记录无法升级的原因。

## 阶段 1：分类

入口条件：用户提到 mtcli，或要求通过 mtcli 调用/查看内部接口。

1. 判断任务类型：发现、schema 检查、dry-run、真实执行、tools 模式、鉴权、缓存修复、命令解释。
2. 判断操作安全性：只读、未知、或可能写入/发布/删除/修改。
3. 判断用户是否已经提供 service、resource、method、参数、schema 环境、目标环境和鉴权上下文。
4. 信息不足时先检查，不要猜。

出口条件：知道下一步应该走哪类 mtcli 命令，并知道是否需要安全门控。

## 阶段 2：检查

入口条件：目标接口、参数或鉴权要求不完整。

1. 只知道业务领域时，先发现服务。
2. 已知服务时，查看服务命令树、`tools list --service <service>` 或 tools 描述。
3. 已知方法时，查看 method schema；涉及 body 或复杂参数时解析 refs。
4. 本地解析报 `unknown flag: ...` 或缺必填 flag 时，先按 [references/errors.md](references/errors.md) 判断是命令输入问题还是 schema 环境/私有 CLI 问题。
5. schema 可疑过期时，只刷新目标服务缓存；不要运行裸 `mtcli cache refresh`。
6. 记录必填字段、参数位置、body 结构、鉴权类型、schema 来源环境、目标环境支持和响应结构。

出口条件：method、参数名、参数位置、body schema、鉴权方式和潜在副作用已确认。

## 阶段 3：规划

入口条件：目标 method 已确认。

1. 根据参数位置选择通道：
   - path/query/header：动态命令可用业务 flag、`--params` 或专门的 `--headers`
   - body：使用 `--json`
   - tools call：只用 `--params` 和可选 `--json`
2. 不确定或可能有副作用时，先 dry-run。
3. 可能修改远端状态时，除非用户已经明确要求执行，否则先说明副作用并等待确认。
4. 只有任务需要时才添加 timeout、schema 环境、目标环境、no-cache 或 verbose。

出口条件：已有 dry-run 计划，或已有用户批准的真实请求计划。

## 阶段 4：执行或回复

入口条件：已运行 dry-run/真实请求，或用户只要求命令指导。

1. dry-run 只说明请求计划，不宣称远端 API 成功。
2. 真实请求要说明是否成功、状态码、关键响应和恢复建议。
3. 鉴权失败时先检查登录状态、schema 的 `authType` 或 tools contract 的 `effectiveAuth.type`，以及错误里的 recovery。
4. schema/cache 问题优先做单服务缓存修复。
5. 给用户展示命令时使用占位符，除非值来自用户。

出口条件：用户能安全复用、替换占位符或继续下一步。

## 完成检查

- 命令路径匹配用户意图。
- 没有主动暴露真实服务/方法/账号/appkey/URL/业务值。
- 不确定执行前已经检查 schema。
- 可能有副作用的操作已 dry-run 或得到明确授权。
- `--params` 与 `--json` 按参数位置使用。
- 缓存刷新范围最小。
- 已区分 schema discovery 鉴权环境和业务目标接口鉴权环境。
- 排查调用日志时使用 `-v` / `--verbose`，并保留原 schema/target 环境参数。
- 最终说明区分了 dry-run、真实请求和命令指导。
