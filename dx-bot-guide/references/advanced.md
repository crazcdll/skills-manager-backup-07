# 高级用法

## 多类型消息体（--type）

`msg send-chat` / `msg send-group` 支持 `--type` + `--body`/`--body-file`/`--stdin` 发送富媒体消息（仅 direct 模式）：

| type | body 关键字段 | 备注 |
|------|--------------|------|
| image | thumbnail/normal/original | `--body` 可直接传图片 URL，自动补全三字段 |
| file | id/url/name/format/size | 文件消息 |
| link | title/image/content/link | 图文摘要 |
| multilink | num/content | 多图文 |
| audio | codec/duration/stamp/url | 仅 amr，群聊不支持 |
| video | videoUrl/screenshotUrl/width/height/duration | |
| gps | name/latitude/longitude | 位置 |
| vcard | uid/type | 名片 |
| gvcard | guid | 群名片 |
| newemotion | id/params/category/packageId/type | 表情 V2 |
| event | type/text | 事件 |
| custom | templateName/contentTitle/content/linkName/link | 模版消息 |
| general | data/type/summary | 富文本 type=100 |
| quote | quotedMsgId/replyMsg | 引用回复 |

规则：body 必须为 JSON 对象且 ≤32KB；不支持 `--markdown` 与 @；calendar/emotion/dynamic 已废弃。字段详情见学城《消息类型与消息体字段》（km.sankuai.com/collabpage/2648372848）。

## 卡片消息更新

```bash
# 更新单聊卡片（默认 dry-run，需 --force）
dx-bot-cli card update-chat \
  --msg-id <msgId> --uids <uid1>,<uid2> \
  --template-id <tplId> --template-args '{"key":"value"}' --force

# 更新群聊卡片
dx-bot-cli card update-group \
  --gid <群ID> --msg-id <msgId> \
  --template-id <tplId> --template-args '{"key":"value"}' --force
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
