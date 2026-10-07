# 鉴权参考

用于 AI 判断 mtcli 调用失败是否和鉴权有关，以及应该如何恢复。

## SSO 鉴权

### 线上登录

查看当前状态：

```bash
mtcli auth sso whoami
```

登录：

```bash
mtcli auth sso login [--mis <mis>]
```

`auth sso login` 默认先从本机 MTLS AppKey 证书解析 MIS；`--mis` 只是在证书不可用时的 fallback，不强制覆盖证书身份。

退出：

```bash
mtcli auth sso logout
```

### 线下登录

当目标接口使用 SSO，且业务目标环境是精确的 `test`、`dev`、`test-keeta` 或 `dev-keeta` 时，mtcli 将该调用视为线下目标环境调用。

```bash
# 查看线下状态
mtcli --mtcli-target-env test auth sso whoami

# 线下登录
mtcli --mtcli-target-env test auth sso login [--mis <mis>]

# 只为 test schema discovery 准备线下登录态
mtcli --mtcli-schema-env test auth sso login [--mis <mis>]
```

### MOA local exchange 优先级

MOA local exchange 是 mtcli 自动尝试的登录来源，不是 `auth sso login` 子命令。

- 线上业务接口 SSO：先用已缓存目标 `ssoid`；没有缓存时，尝试 MOA local exchange（单 audience 直接传 audience，多 audience 以 audience set 传入）；MOA 不可用时，再用 `auth sso login` 保存的线上 access token 做 Token Exchange。
- 多 audience 线上 SSO：缓存、MOA 和 Token Exchange 都按规范化后的 audience set 处理。
- MOA 返回待用户授权时，提示用户完成授权后重试；不要立刻改走 `auth sso login`。
- 线下业务接口 SSO：使用线下 `ssoid` 缓存或线下登录 access token；线下缺失时可尝试线上登录缓存 fallback；不使用 MOA。
- 线上 schema/service/tool discovery：已缓存 discovery `ssoid` > MOA local exchange > 线上登录缓存 Token Exchange > 不带 cookie 继续请求。
- 线下 discovery：使用线下 discovery `ssoid` 或线下登录缓存；不使用 MOA。
- MWS 鉴权：已缓存 portal `ssoid` > MOA local exchange > 线上登录缓存 Token Exchange。

通用规则：

- 业务目标接口鉴权使用 target env：`--mtcli-target-env test/dev/test-keeta/dev-keeta` 使用线下登录缓存；`prod`、`staging`、空目标环境、`prod-keeta`、`staging-keeta` 使用线上 SSO 链路。
- schema/service/tool 元数据拉取鉴权使用 schema env：`--mtcli-schema-env` 优先；未传时沿用 `--mtcli-target-env`；显式 `MT_REMOTE_URL` / `MT_REMOTE_BASE` 指向标准 test/dev discovery host 时也按线下 discovery SSO 处理。
- `auth sso login/logout/whoami` 是登录缓存管理命令，优先按 `--mtcli-target-env` 判断线上/线下；未传 target env 时可用 `--mtcli-schema-env` 兜底，方便只处理 discovery 登录态。
- 线下目标接口优先读取线下登录缓存，并用线下 access token 为目标服务 audience 换取 ssoid。
- 线下登录缓存缺失时，mtcli 会尝试使用线上登录缓存兜底，为同一个目标服务 audience 做 Token Exchange；成功后把 ssoid 写入线上凭证缓存。
- 线下目标接口鉴权不会使用 MOA local exchange；看到 `SSO offline ... online fallback` 表示正在使用线上登录缓存兜底，不表示线下登录成功。

典型组合：

- `--mtcli-schema-env prod --mtcli-target-env test`：线上 schema discovery + 线下业务目标 SSO。
- `--mtcli-schema-env test --mtcli-target-env prod`：线下 schema discovery + 线上业务目标 SSO。

规则：

- 不要假设用户已登录；真实调用失败时先查状态。
- 登录态缓存在本地，后续请求自动复用。
- 某些服务需要特定 audience/client_id；优先从 schema/method contract 中确认。

## Audience

解析目标 URL 对应 audience：

```bash
mtcli auth sso audience --url <url>
```

只有当 schema、错误信息或调试输出指向 audience 问题时才需要单独查。

## Access 鉴权

查看机器证书身份：

```bash
mtcli auth access whoami
```

规则：

- access 类鉴权通常依赖运行环境注入的机器身份。
- 如果没有机器证书，AI 不应尝试绕过鉴权。
- 返回 no cert identity detected 时，说明当前环境不能调用该类接口。

## None/无鉴权

schema 显示无鉴权时仍要 dry-run 检查 URL 和参数。无鉴权不等于无副作用。

## HTML 登录页

现象：HTTP 200 但响应是 HTML 登录页。

处理：

- 不要把它当业务成功。
- 说明该服务路径可能只接受浏览器 session/cookie。
- mtcli 可能无法直接调用该路径，除非服务 schema 或 mtcli 支持相应 cookie/session 机制。

## 鉴权排查顺序

1. 看 schema 的 `authType` 或 tools contract 的 `effectiveAuth.type`。
2. 查登录状态。
3. dry-run 或 verbose 确认最终 URL 和鉴权信息是否发送。
4. 读取错误 envelope 里的 recovery。
5. 若仍失败，按权限不足或服务不支持当前鉴权形态报告。
