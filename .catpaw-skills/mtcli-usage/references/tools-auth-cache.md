# Tools、鉴权与缓存参考

用于 tools 模式、SSO 登录状态、缓存修复和调用排查。

## Tools 模式

查看一个服务的 tool contract：

```bash
mtcli tools describe <service>
```

列出 tools 使用轻量摘要接口，不拉取参数 schema、response schema 或 API detail。优先用服务名缩小远端范围；`--filter` 主要缩小返回结果，不要把它当作等价的远端窄查询：

```bash
mtcli tools list --service <service>
mtcli tools list --filter <keyword>
```

只有用户明确需要全量目录时才用：

```bash
mtcli tools list
```

执行 tool：

```bash
mtcli tools call <service_resource_method> --params '<json-object>'
```

带 body 的 tool：

```bash
mtcli tools call <service_resource_method> --params '<json-object>' --json '<json-object>'
```

安全预览：

```bash
mtcli tools call <service_resource_method> --params '<json-object>' --json '<json-object>' --dry-run
```

规则：

- `tools list` 只返回 name、description、service、resource、method、httpMethod、effectiveAuthType；调用前仍需 `tools describe <service>` 或 `schema` 看完整参数和响应结构。
- tool name 由 service/resource/method 组成，形态是 `<service_resource_method>`。
- tools call 不生成业务独立 flag。
- path/query/header 放 `--params`。
- request body 放 `--json`。
- tools call 的真实响应是 JSON envelope；dry-run 响应是请求计划。

## 鉴权

查看当前登录状态：

```bash
mtcli auth sso whoami
```

登录：

```bash
mtcli auth sso login [--mis <mis>]
```

退出登录：

```bash
mtcli auth sso logout
```

需要鉴权处理的信号：

- schema 或 method contract 显示需要 SSO/access 等鉴权。
- 真实请求返回 401/403/auth required。
- 返回 HTML 登录页。
- 错误 envelope 中包含 recovery。

## 缓存

查看缓存状态：

```bash
mtcli cache list
```

查看远端发现配置：

```bash
mtcli cache config
```

刷新单个服务：

```bash
mtcli cache refresh --service <service>
```

绕过缓存执行一次命令：

```bash
mtcli --no-cache <service> ...
```

缓存选择规则：

- 只有一个服务可疑时，只刷新该服务。
- `cache refresh` 不支持全量刷新；裸 `mtcli cache refresh` 会直接报错且不会请求后端。
- `tools list` 和 `generate-skills` 已走轻量摘要路径；但无服务范围时仍会覆盖很多服务，优先使用 `--service`。`--filter` 可减少返回结果，但不保证减少远端扫描。
- help/schema 与预期不一致时，优先单服务 refresh。
