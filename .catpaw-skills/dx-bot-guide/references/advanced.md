# 高级用法

## 消息体字段（--type）

全部类型 direct / proxy 均支持（proxy 后端校验 msgType 白名单）。body 必须 JSON 对象 ≤32KB，不支持 `--markdown` 与 @。calendar/emotion/dynamic 已废弃。

- image：`thumbnail` / `normal` / `original`（`--body` 可传 URL 或本地路径，自动上传并补全三字段）
- file：`id` / `url` / `name` / `format` / `size`
- link：`title` / `image` / `content` / `link`
- multilink：`num` / `content`
- audio：`codec` / `duration` / `stamp` / `url`（仅 amr，群聊不支持）
- video：`videoUrl` / `screenshotUrl` / `width` / `height` / `duration`
- gps：`name` / `latitude` / `longitude`
- vcard：`uid` / `type`
- gvcard：`guid`
- newemotion：`id` / `params` / `category` / `packageId` / `type`
- event：`type` / `text`
- custom：`templateName` / `contentTitle` / `content` / `linkName` / `link`
- general：`data` / `type` / `summary`（富文本 type=100）
- quote：`quotedMsgId` / `replyMsg`

字段详情：km.sankuai.com/collabpage/2648372848

## upload-image

返回永久 CDN URL（file.sankuai.com），非风险操作。

```bash
dx-bot-cli msg upload-image ./panel.png
dx-bot-cli msg upload-image ./cover.jpg --creator <mis>
dx-bot-cli --json msg upload-image ./qr.png
```

- png/jpg/jpeg/gif/webp/bmp，≤10MB
- >1MB 压缩为 JPEG（质量 85→40，再缩尺寸）；gif 跳过；失败回退原图，`-v` 可见
- 用途：image 消息、link 封面、卡片 `cover_img`
- `--type image --body <本地路径>` 发送时自动上传，无需先手动传

## 卡片更新

```bash
dx-bot-cli card update-chat --msg-id <msgId> --uids <uid1>,<uid2> \
  --template-id <tplId> --template-args '{"key":"value"}' --force

dx-bot-cli card update-group --gid <群ID> --msg-id <msgId> \
  --template-id <tplId> --template-args '{"key":"value"}' --force
```

`--request-id` 新式排他卡片：内联 `--text` / `--markdown` / `--abstract` 自动还原 `\n` `\t` `\\`；字面量反斜杠加 `--no-unescape`，或改用 `--text-file` / `--markdown-file` / `--stdin-*`。

## card query

以机器人身份查用户实际看到的最新卡片（`POST /card/user/queryByBot`），只读。

```bash
# 单聊（direct）
dx-bot-cli --mode direct card query --to <mis|empId> --msg-id <msgId> \
  --biz-id <bizId> --task-id <taskId> --dynamic-type <dynamicType>

# 群聊（direct）
dx-bot-cli --mode direct card query --chat-type GROUP_CHAT --gid <群ID> \
  --to <非机器人成员的mis|empId> --msg-id <msgId> \
  --biz-id <bizId> --task-id <taskId> --dynamic-type <dynamicType>

# proxy（--to 被忽略）
dx-bot-cli --mode proxy card query --msg-id <msgId> \
  --biz-id <bizId> --task-id <taskId> --dynamic-type <dynamicType>
```

- `--to` 仅 direct 用（MIS 或 empId）
- `--biz-id` / `--task-id` / `--dynamic-type` 取自消息体 `extension.businessInfo`
- `--msg-id` 可逗号分隔批量，共用三个业务字段
- `--chat-type` 默认 `PUB_CHAT`，简写 `pub`/`chat`/`group`；群聊必须 `--gid`（proxy 还要求你在群内）
- 限制：流式卡片发送后 ≥1 分钟、转发卡片 ≥3 秒；最多 3 年前；不支持 PULL 卡片与 `body.type=11`；5 QPS
- `--json` 输出 `{code, message, data.contentMap}`

## 操作日志

写入 `~/.local/share/dx-bot-cli/logs/`。

```bash
dx-bot-cli log list                       # 最近 7 天
dx-bot-cli log list --days 30 --cmd send
dx-bot-cli log search --msg-id <msgId>
dx-bot-cli log search --gid <群ID>
dx-bot-cli log search --text "关键词"
dx-bot-cli log path
dx-bot-cli log clean
```

## 权限诊断（仅 direct）

`diag scopes` 不可用（依赖的 dxopen 管理后台 client 未开放，**勿申请 IAM 权限**）。改用浏览器打开
`https://dxopen.sankuai.com/app/manage/auth?appkey=<机器人clientId>`。

```bash
dx-bot-cli diag token-exchange --target <service> --src mtsso   # 鉴权链路测试，可用
```

## 排障

- 凭证错误：`config show` 核对 client_id（secret 默认脱敏，核对明文用 `config show --reveal-secrets`）
- 缺 sso-auth-cli：`curl -fsSL https://sre.sankuai.com/tool/sso-auth-cli/install | sh`
- 操作没生效：是否 dry-run，补 `--force`
- 权限不足：`diag scopes` 不可用；浏览器查 dxopen 授权页
- 网络/API 异常：`-vvv` 看完整 HTTP
- JSON `Unexpected end of input`：自己用 `head` 截断了 JSON，去掉管道
- `code=40001`：单聊 `--uid` 传了数字（改 MIS）、`--start` 超 3 年、时间戳格式错
- `code=70003`：bot 未入群或 gid 错，`group list-joined` 核对

`--json` 顶层 `code` 只有 `0` / `500`，业务码在 `message` 的 `(code=xxxxx)`。

## 分页

单页上限 100（越界自动收敛并告警）。`data.page_token` 是整数游标，`data.has_more=false` 停止；`page_token=null` 表示无下一页。

- 非 JSON：首行 `共 N 条消息（hasMore: …）`，末行 `下一页 pageToken: <数字>`
- 旧版 ≤0.4.5 的 `page_token` 恒为 `null`，可 `-vvv` 从 `cli-proxy 响应` 取 `"pageToken"` 兜底，建议升级
- 大群直接 `--page-size 100` 翻到底，比切碎时间窗省事

## 30002「标准开放能力权限校验失败」

多为限流误报（app+path 维度 1 秒 5 次），**与 Bot 权限无关**。限流窗口内也可能是 `{"code":10003,"msg":"服务限流"}`，HTTP 200 / 403 都会出现。

- 先重试；`group list-joined` 大群翻页时降并发或加 `--limit` 分批
- 新版 CLI 已内置退避重试，限流时不会拿其他凭证的结果冒充
- 排除限流后仍持续报错，才查授权页

## 退出码

`0` 成功 · `1` 用法错误 · `2` 认证失败 · `3` API/网络错误 · `4` 权限不足
