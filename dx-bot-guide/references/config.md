# 配置

## Profile

一个 profile = 一套 Bot 凭证：`client_id` + `client_secret`（必填）+ 可选 `bot_uid`（pubId）。

- 选择顺序：`--profile` > `DX_BOT_PROFILE` > `default_profile` > `default`
- 单 bot 只建 `default`，日常不传 `--profile`；多 bot 建多个 profile 按需切换
- proxy 不读 profile 的 client 凭证（走 SSO），只用其中的 `bot_uid`（群权限预检）

```bash
dx-bot-cli config set-profile --name default --client-id <id> --client-secret <secret>
dx-bot-cli config set-profile --name bot-b --client-id <id-b> --client-secret <secret-b>
dx-bot-cli config set-default bot-b
dx-bot-cli --profile bot-b msg send-chat --to <mis> --text "hi" --force
DX_BOT_PROFILE=bot-b dx-bot-cli group list-joined
```

## 命令

```bash
dx-bot-cli config init                # 初始化（输出完整路径；已存在会报错并带路径）
dx-bot-cli config show                # 生效配置（已合并环境变量；client_secret 默认脱敏）
dx-bot-cli config show --reveal-secrets  # 需要核对 secret 明文时（别贴到工单 / 聊天）
dx-bot-cli config list                # profile 列表（★ 默认；client_id 只显示前 8 位）
dx-bot-cli config set-default <name>  # 设默认（支持 alias；不存在只告警）
dx-bot-cli config set-profile --name <n> --client-id <id> --client-secret <secret> [--bot-uid <pubId>]
```

## bot_uid（pubId）：非必须

direct 只有 `client_id` + `client_secret` 必填。pubId 只在 3 处用到：

- `group create --group-mode B`：**必需**，机器人写入 `botAdmins`，必须是 pubId
- `group add-bot`：可选，`--bot-id` 省略则自动解析
- `dismiss` / `transfer` / `set-admin`：可选，仅本地权限预检；拿不到就跳过，服务端仍判

不需要：所有 `msg`、`card`、`group info` / `members` / `search` / `list-joined` / `update` / `set-notice` / `remove-members` / `remove-bot`、`group create` 模式 A。

解析顺序：

1. `--bot-uid <uid>`（等价环境变量 `DX_BOT_UID`）
2. 显式 `--profile` 指向的 profile 的 `bot_uid`
3. proxy 模式额外读 `[profiles.proxy]` 的 `bot_uid`
4. `default_profile` 指向的 profile 的 `bot_uid`
5. 沙箱降级：`agent_info` 文件里的 `AGENT_DX_BOT_ID`（仅当本次 direct 凭证也来自同一份 `agent_info` 时生效）
6. 自动查询（仅 `group create --group-mode B` 和 `group add-bot` 会走到）：`sso-auth-cli` 取 dxopen Cookie → `GET https://dxopen.sankuai.com/man/application/info?applicationKey=<client_id>` → `data.pubId`（需该应用管理权限，否则 403）

注意：

- pubId 是纯数字 uid（如 `139054973106`），不是 client_id / appKey，也不是 `@机器人` 用的字符串 ID（如 `2731102912X00Y14`）。
- 不配只影响上述 3 处，不影响发消息。

## 沙箱降级凭证（agent_info）

平台沙箱（e2b / sandbox-ide / 普通容器）会预置机器人凭证文件，CLI 在没有 profile / 环境变量凭证时自动读取，**无需任何配置**：

- 路径（按序尝试）：`/root/.openclaw/sso/agent_info`、`/root/sso/agent_info`
- 格式：`{"AGENT_SSO_CLIENT_ID":"…","AGENT_SSO_CLIENT_SECRET":"…","AGENT_DX_BOT_ID":"…"}`（其余字段忽略）
- 优先级最低：`config show` 的 TOML 里看不到它，`config save` 也不会把它写进配置文件
- 判断是否命中：`config show` 末尾（stderr）会打印 `凭证来源: agent_info <路径> (client_id: …)` + `direct 可用`；`auth status` 也会提示已有 direct 凭证、无需 SSO
- 直接读不到且疑似权限不足时，会用 `sudo -n cat` 兜一次；仍失败则静默跳过
- `DX_BOT_AGENT_INFO_PATH=<路径>` 可覆盖默认路径（测试 / 非 root 环境）

## 鉴权

```bash
dx-bot-cli auth status
dx-bot-cli auth token
dx-bot-cli auth clear
```

依赖 `sso-auth-cli`；装不了时加 `--force-oidc` 走内嵌流程。

## 优先级

CLI 参数 > 环境变量 > 配置文件 > 内置默认值

## 环境变量

`DX_BOT_MODE`、`DX_BOT_CLIENT_ID`、`DX_BOT_CLIENT_SECRET`、`DX_BOT_PROFILE`、`DX_BOT_UID`（可选）、`DX_BOT_CONFIG`、`DX_BOT_PROXY_PREFIX`、`DX_BOT_SSO_TARGET`、`DX_BOT_API_ENDPOINT`、`DX_BOT_SSO_ENDPOINT`、`DX_BOT_SCOPE`、`DX_BOT_INSECURE_SKIP_TLS_VERIFY`、`DX_BOT_AGENT_INFO_PATH`（沙箱降级凭证路径）。

## 文件位置

- macOS：`~/Library/Application Support/dx-bot-cli/config.toml`
- Linux：`~/.config/dx-bot-cli/config.toml`
- Windows：`%APPDATA%\dx-bot-cli\config.toml`

`--config <PATH>` / `DX_BOT_CONFIG` 可覆盖。Unix 权限 `0600`，内含明文 secret。

## 文件结构

```toml
mode = "auto"

[profiles.default]
client_id = "<id>"
client_secret = "<secret>"
# bot_uid = 139054973106   # 可选

[profiles.another-bot]
client_id = "<id2>"
client_secret = "<secret2>"
```

## profile 维护

- 覆盖：`config set-profile` 覆盖 `client_id` / `client_secret`；未传 `--bot-uid` 保留原值，**也不会自动查询补全**（自动查询只发生在运行时）
- 删除：无 `config delete`，手工编辑 TOML 删 `[profiles.<name>]` 整段，`config list` 复核
- alias：TOML 里手写 `alias = ["a", "b"]`，`--profile` / `set-default` 支持；`set-profile` 保留原值

## 获取凭证

```bash
COOKIE=$(sso-auth-cli "https://dxopen.sankuai.com/man/application/info?applicationKey=<clientID>" --cookie 2>/dev/null | tail -1)
curl -s -b "$COOKIE" "https://dxopen.sankuai.com/man/application/info?applicationKey=<clientID>"
```

返回 `clientKey`（client_id）、`clientSecret`、`pubId`。无管理权限返回 `{"code":403,"message":"权限不足"}`，改从大象客户端看发送方或找应用负责人要 pubId。
