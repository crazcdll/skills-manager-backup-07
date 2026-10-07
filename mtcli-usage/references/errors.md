# 系统级输入错误排查

用于排查 mtcli 在业务接口请求发出前失败的情况。业务接口自身的响应错误不在本文件范围内。

## 判断边界

把以下错误视为 mtcli 系统级输入错误：

- Cobra 本地解析错误：`unknown flag: ...`、缺少必填 flag、参数类型不合法。
- 动态命令/schema 解析错误：service/resource/method 找不到，schema 路径不匹配。
- mtcli 自身 flag 的输入错误：`--params`、`--headers`、`--json` 不是合法 JSON。
- 鉴权准备失败：本地登录态、证书身份、SSO token exchange 或 MOA 授权未完成。
- 缓存命令输入错误：全量刷新、未知缓存类型、缺少 `--service`。

真实 HTTP 请求已经发出后的业务状态码、业务 code/message、业务字段校验失败，不按本文件排查。

## Cobra 解析错误

现象包括：

```text
unknown flag: ...
required flag(s) "url" not set
required flag(s) "auth-req-id" not set
```

处理流程：

1. 如果只是当前命令确实缺少必填 flag，先运行对应 `--help`，按 help 补齐，例如 `--url`、`--auth-req-id`。
2. 如果用户认为该 CLI 或 flag 本应存在，确认当前 schema 拉取环境是线上还是线下：显式 `--mtcli-schema-env` 优先，未传时沿用 `--mtcli-target-env`；必要时用 `mtcli cache config` 查看 discovery 配置。
3. 让用户到对应环境检查是否已经创建该 CLI：线上 schema 就查线上，线下 schema 就查线下。
4. 如果是私有 CLI，让用户检查是否在对应环境完成登录，再重新拉取 schema 或重新执行。

这类错误发生在本地解析阶段，通常还没有业务 HTTP 请求。不要直接归因于接口权限或业务入参。

## 常见系统级提示

| 提示形态 | 排查方式 |
|---|---|
| `unknown command` / service/resource/method 找不到 | 重新做服务发现或 schema 检查；不要发明名称。 |
| `unknown flag: --version` | 本机 mtcli 旧版；先退回 `mtcli version`，再按版本检查流程升级。 |
| `invalid JSON` / `failed to parse --params` / `failed to parse --json` | 修正 JSON；保留 schema 中的 key 大小写；body 用 `--json`，path/query/header 用 `--params` 或 `--headers`。 |
| 缺少 path/query/header/body 业务参数 | 查 method schema，按参数位置放入正确通道；body 不拆成业务独立 flag。 |
| schema 来源或目标地址不符合预期 | 区分 `--mtcli-schema-env` 和 `--mtcli-target-env`；用 dry-run 查看目标 URL。 |
| schema 明显过期 | 只执行 `mtcli cache refresh --service <service>`；不要执行裸 `mtcli cache refresh`。 |
| cache 提示未知类型或缺少 service | 用 `mtcli cache list` / `mtcli cache config` 查看现状；刷新时补 `--service <service>`。 |
| 鉴权准备失败或提示 recovery | 查 `auth sso whoami`、schema `authType` 或 tools `effectiveAuth.type`；按提示登录对应线上/线下环境。 |
| MOA 提示待授权 | 让用户完成 MOA 授权后重试；不要立刻改走 `auth sso login`。 |

## 调用日志

用户需要查看某次命令的调用日志时，在原命令上加 `-v` 或 `--verbose`：

```bash
mtcli -v <service> <resource> <method> --params '<json-object>' --dry-run
```

保留原来的 `--mtcli-schema-env` / `--mtcli-target-env`，否则日志里的 discovery 环境、目标 URL 和鉴权链路会变。
