# 高级用法

## 卡片消息更新（仅 Proxy 模式）

```bash
# 更新单聊卡片
dx-bot-cli msg update-chat-card \
  --msg-id <msgId> --uids <uid1>,<uid2> \
  --template-id <tplId> --template-args '{"key":"value"}'

# 更新群聊卡片
dx-bot-cli msg update-group-card \
  --gid <群ID> --msg-id <msgId> \
  --template-id <tplId> --template-args '{"key":"value"}'
```

## 操作日志

所有写操作自动落盘到 `~/.local/share/dx-bot-cli/logs/`。

```bash
dx-bot-cli log list                          # 最近 7 天日志
dx-bot-cli log list --days 30 --cmd send     # 按命令过滤
dx-bot-cli log search --msg-id <msgId>       # 按消息 ID 查
dx-bot-cli log search --gid <群ID>           # 按群查
dx-bot-cli log search --text "关键词"        # 按内容查
dx-bot-cli log path                          # 日志目录路径
dx-bot-cli log clean                         # 清理过期日志
```

## 权限诊断（仅 Direct 模式）

```bash
# 查询 Bot 已开通的权限 scope
dx-bot-cli diag scopes
dx-bot-cli diag scopes --app-key <appkey> --enabled-only

# 鉴权链路测试
dx-bot-cli diag token-exchange --target <service> --src mtsso
```

## 排障

| 问题 | 解决 |
|------|------|
| 凭证错误 | `dx-bot-cli config show` 确认 client_id/secret |
| 鉴权工具缺失 | 安装 `sso-auth-cli`：`curl -fsSL https://sre.sankuai.com/tool/sso-auth-cli/install \| sh` |
| 操作未生效 | 检查是否 dry-run 状态，加 `--force` |
| 权限不足 | `dx-bot-cli diag scopes` 查看已开通权限 |
| 网络/API 错误 | 加 `-vvv` 查看完整 HTTP 交互 |

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 用法错误 |
| 2 | 认证失败 |
| 3 | API/网络错误 |
| 4 | 权限不足 |
