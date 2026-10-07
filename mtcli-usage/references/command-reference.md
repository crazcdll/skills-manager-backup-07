# 命令与 Flag 参考

用于回答 mtcli 支持什么命令、某个 flag 怎么用、或 AI 需要选择入口时。

## 全局 Flags

| Flag | 作用 |
|---|---|
| `--output text|json` | 输出格式 |
| `--verbose`, `-v` | 调试输出，通常包含最终 URL、headers、鉴权信息和状态 |
| `--mtcli-target-env <env>` | 业务目标环境覆盖。执行请求时精确匹配 `serviceConfig[env]`，影响目标地址、目标鉴权和目标 SSO；未传 `--mtcli-schema-env` 时也作为 schema discovery 环境 |
| `--mtcli-schema-env <env>` | schema/config discovery 环境覆盖。只影响远程 schema 拉取地址和 discovery SSO；优先级高于 `--mtcli-target-env` |
| `--no-cache` | 本次绕过 schema 缓存 |

调试鉴权、请求问题或查看某次命令的调用日志时，优先在原命令上加 `-v` 或 `--verbose`，并保留原来的 `--mtcli-schema-env` / `--mtcli-target-env`；先确认请求 URL、token/cookie/header 是否按预期发送。

## 顶层命令

| 命令模板 | 目的 | 注意 |
|---|---|---|
| `mtcli services` | 列服务 | 通常比全量 schema 扫描轻 |
| `mtcli schema <service[.resource[.method]]>` | 查看 schema | 复杂结构加 `--resolve-refs` |
| `mtcli auth ...` | 鉴权管理 | 见 auth 参考 |
| `mtcli cache ...` | 缓存查看/刷新 | 优先单服务刷新 |
| `mtcli tools ...` | AI 友好的发现和执行 | `tools list` 是轻量摘要；优先加 `--service` 或 `--filter` |
| `mtcli generate-skills` | 生成服务技能 | 走轻量摘要路径；无 `--filter` 时覆盖面仍大 |
| `mtcli version` | 查看版本 | 轻量 |
| `mtcli <service> <resource> <method>` | 执行动态 API 方法 | 先检查 schema |

## services

```bash
mtcli services
mtcli services --output json
```

## schema

```bash
mtcli schema <service>
mtcli schema <service>.<resource>
mtcli schema <service>.<resource>.<method>
mtcli schema <service>.<resource>.<method> --resolve-refs
```

## 动态服务命令

形态：

```bash
mtcli <service> <resource> <method>
```

常见 method flags：

| Flag | 作用 |
|---|---|
| `--params '<json-object>'` | path/query/header 参数 JSON |
| `--headers '<json-object>'` | header 参数 JSON，优先于 `--params` 中的同名 header |
| `--json '<json-object>'` | request body JSON |
| `--dry-run` | 打印请求计划，不发送 |
| `--format json|yaml|table` | 响应展示格式 |
| `--fmt json|yaml|table` | `--format` 的兼容别名 |
| `--timeout <seconds>` | 请求超时覆盖 |

规则：

- schema 可能为 path/query/header 标量参数生成业务独立 flag。
- body 参数走 `--json`。
- 复杂 object/array path/query/header 参数走 `--params`。
- `--params` 存在时，它是 path/query/header 的权威来源，不与业务独立 flag 合并。
- `--headers` 存在时，其中指定的 header 参数会覆盖 `--params` 中的同名参数（`--headers` 优先级最高）。
- `--help` 适合查看动态命令形态和简要参数提示；body 复杂字段的完整 description 用 `mtcli schema <service>.<resource>.<method> --resolve-refs` 查看。

模板：

```bash
mtcli <service> <resource> <method> --<param> <value> --dry-run
mtcli <service> <resource> <method> --params '<json-object>'
mtcli <service> <resource> <method> --params '<json-object>' --json '<json-object>'
mtcli <service> <resource> <method> --params '<json-object>' --headers '<json-object>'
mtcli <service> <resource> <method> --params '<json-object>' --headers '<json-object>' --json '<json-object>'
mtcli <service> <resource> <method> --mtcli-schema-env prod --mtcli-target-env test --params '<json-object>' --dry-run
```

## tools

```bash
mtcli tools list --service <service>
mtcli tools list --filter <keyword>
mtcli tools describe <service>
mtcli tools call <service_resource_method> --params '<json-object>'
mtcli tools call <service_resource_method> --params '<json-object>' --json '<json-object>'
mtcli tools call <service_resource_method> --params '<json-object>' --dry-run
mtcli tools call <service_resource_method> --timeout <seconds>
```

tools call 规则：

- 不使用业务独立 flag。
- path/query/header 放 `--params`。
- body 放 `--json`。
- `tools list` 只返回轻量摘要，不包含完整 input/output schema。优先用 `--service` 限定服务；`--filter` 只保证缩小返回结果，不保证减少远端扫描成本。
- 真实响应是 JSON envelope。
- dry-run 输出请求计划。

## generate-skills

```bash
mtcli generate-skills --filter <service-or-keyword>
```

规则：

- 当前实现走轻量 service index + tools summary，不拉取全量 API detail。
- 没有明确要生成所有服务时，优先加 `--filter`。

## cache

```bash
mtcli cache list
mtcli cache clear
mtcli cache clear --type <type>
mtcli cache refresh --service <service>
mtcli cache config
mtcli cache config --output json
```

缓存规则：

- `cache refresh --service <service>` 优先。
- 全量 `cache refresh` 已禁用；不要推荐或执行。裸 `mtcli cache refresh` 会直接报错，不会请求后端。
- `tools list`、`generate-skills` 只有全局需求时使用。

## auth

```bash
mtcli auth sso whoami
mtcli auth sso login [--mis <mis>]
mtcli auth sso logout
mtcli auth sso audience --url <url>
mtcli auth access whoami
```

## 响应判断

| 现象 | 处理 |
|---|---|
| 2xx 且业务字段成功 | 可视为成功 |
| 401/403 | 先查鉴权和权限 |
| 404 | 可能是资源不存在、路径过期或 schema 过期 |
| HTML 登录页 | 可能需要浏览器 session/cookie，mtcli 不一定支持 |
| timeout/network error | dry-run/verbose 确认 URL，再考虑 timeout |

## 性能判断

| 命令类型 | 成本 |
|---|---|
| `services`、单服务 help、单方法 schema | 较低 |
| 单服务 cache refresh | 中等 |
| `tools list --service` | 较低到中等，适合限定服务发现 tool 名称 |
| `tools list --filter` | 较低到中等，适合减少返回结果；不保证降低远端扫描成本 |
| 裸 `tools list`、裸 `generate-skills` | 较高，避免默认使用 |
