# 配置管理

## 命令

```bash
dx-bot-cli config init                # 初始化配置文件
dx-bot-cli config show                # 查看生效配置
dx-bot-cli config list                # 列出所有 profile
dx-bot-cli config set-default <name>  # 设置默认 profile

# 写入 profile（--bot-uid 可选）
dx-bot-cli config set-profile \
  --name default \
  --client-id <client-id> \
  --client-secret <client-secret> \
  --bot-uid <pubId>
```

## 鉴权

```bash
dx-bot-cli auth status      # 查看鉴权状态
dx-bot-cli auth token       # 获取当前 token
dx-bot-cli auth clear       # 清除缓存
```

鉴权依赖 `sso-auth-cli` 工具处理，未安装时按提示安装即可。若环境无法安装 `sso-auth-cli`，可加 `--force-oidc` 使用内嵌鉴权流程。

## 配置优先级

CLI 参数 > 环境变量 > 配置文件 > 内置默认值

## 环境变量

| 变量 | 说明 |
|------|------|
| `DX_BOT_MODE` | `auto` / `direct` / `proxy` |
| `DX_BOT_CLIENT_ID` | Bot client_id |
| `DX_BOT_CLIENT_SECRET` | Bot client_secret |
| `DX_BOT_PROFILE` | 使用的 profile 名称 |
| `DX_BOT_UID` | Bot UID (pubId) |
| `DX_BOT_CONFIG` | 配置文件路径 |

## 配置文件模板

路径：`~/.config/dx-bot-cli/config.toml`

```toml
mode = "auto"

[profiles.default]
client_id = "<your-client-id>"
client_secret = "<your-client-secret>"
bot_uid = 123456789  # 可选，即 pubId

[profiles.another-bot]
client_id = "<another-client-id>"
client_secret = "<another-client-secret>"
```

切换 profile：`dx-bot-cli --profile another-bot <command>`

## 获取 Bot 凭证

**方式一：通过接口查询（推荐，需对应用有管理权限）**

```bash
# 使用 sso-auth-cli 鉴权后请求应用信息接口
COOKIE=$(sso-auth-cli "https://dxopen.sankuai.com/man/application/info?applicationKey=<clientID>" --cookie 2>/dev/null | tail -1)
curl -s -b "$COOKIE" "https://dxopen.sankuai.com/man/application/info?applicationKey=<clientID>"
```

返回中包含 `clientKey`（client_id）、`clientSecret`、`pubId`（bot-uid）。

**方式二：手动查看**

访问大象开放平台（dxopen.sankuai.com）应用管理页，找到目标应用查看详情。

**配置凭证：**

```bash
dx-bot-cli config set-profile --name default \
  --client-id <clientKey> --client-secret <clientSecret> --bot-uid <pubId>
```

> `--bot-uid` 可选，不传时保留已有值或由 CLI 自动查询。
