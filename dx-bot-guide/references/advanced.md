# 高级用法

## 多类型消息体（--type）

`msg send-chat` / `msg send-group` 支持 `--type` + `--body`/`--body-file`/`--stdin` 发送富媒体消息。

> 全部消息类型 direct/proxy 两种模式均支持（proxy 经后端转发，后端校验 msgType 白名单并透传 sendMsgInfo.type）。

| type | body 关键字段 | 备注 |
|------|--------------|------|
| image | thumbnail/normal/original | `--body` 可直接传图片 URL 或本地图片路径（自动上传为永久 CDN URL），自动补全三字段 |
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

## 图片上传（msg upload-image）

将本地图片上传到大象文件服务，返回永久 CDN URL（file.sankuai.com）。两种模式均支持，上传非风险操作、无需 `--force`。

```bash
# 上传并输出 CDN URL
dx-bot-cli msg upload-image ./screenshots/panel.png

# 自定义上传者标识
dx-bot-cli msg upload-image ./cover.jpg --creator rancheng02

# JSON 输出（便于脚本取用）
dx-bot-cli --json msg upload-image ./qr.png
```

- 支持格式：png/jpg/jpeg/gif/webp/bmp，单张 ≤10MB
- 超过 1MB 自动压缩为 JPEG（降质量 85→40，再逐次缩小尺寸），gif 动图跳过；压缩失败回退原图，仅 -v 时可见日志
- 返回的 URL 为永久链接，可直接用于：
  - 图片消息：`msg send-group --gid <群ID> --type image --body <URL>`
  - link 图文封面：`--type link --body '{...,"image":"<URL>"}'`
  - 卡片模板 cover_img 变量
- `--type image --body <本地路径>` 发送时会自动上传并替换为 CDN URL，无需先手动上传

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

> ⚠️ **`diag scopes` 暂时不可用**：该命令依赖的 dxopen 管理后台 client（`e85cbe6f99`）
> 暂不开放普通用户访问。**请勿为此申请 IAM 权限**（申请也不会生效）。
> 替代方案：请在浏览器自行打开
> `https://dxopen.sankuai.com/app/manage/auth?appkey=<机器人clientId>`
> 查看权限开通状态。

```bash
# ❌ 暂时不可用，执行会直接报错提示
# dx-bot-cli diag scopes
# dx-bot-cli diag scopes --app-key <appkey> --enabled-only

# 鉴权链路测试（仍可用）
dx-bot-cli diag token-exchange --target <service> --src mtsso
```

## 排障

| 问题 | 解决 |
|------|------|
| 凭证错误 | `dx-bot-cli config show` 确认 client_id/secret |
| 鉴权工具缺失 | 安装 `sso-auth-cli`：`curl -fsSL https://sre.sankuai.com/tool/sso-auth-cli/install \| sh` |
| 操作未生效 | 检查是否 dry-run 状态，加 `--force` |
| 权限不足 | `diag scopes` 暂不可用（勿申请权限）；浏览器打开 `https://dxopen.sankuai.com/app/manage/auth?appkey=<机器人clientId>` 查看 |
| 网络/API 错误 | 加 `-vvv` 查看完整 HTTP 交互 |

### 30002「标准开放能力权限校验失败」多为限流误报（重要）

连续快速查询（如机器人加了几百个群时 `group list-joined` 翻页）会触发服务端限流
（app+path 维度 1 秒 5 次），限流窗口内可能返回 `{"code":10003,"msg":"服务限流"}`，
也可能**误报** `{"code":30002,"msg":"标准开放能力权限校验失败"}`（HTTP 200 或 403 均可能）。

- **该错误绝大多数情况与 Bot 权限无关**，稍后重试即恢复，勿急着申请权限
- 新版 CLI 已内置保护：自动退避重试、限流时不冒充其他凭证结果、报错附诊断提示（旧版请升级）
- 仍遇到时：① 重试；② 降并发/加 `--limit` 分批查询；③ `-vvv` 看完整 HTTP 定位
- 排除限流后持续报错，才需要检查应用授权（浏览器打开
  `https://dxopen.sankuai.com/app/manage/auth?appkey=<机器人clientId>`）

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 用法错误 |
| 2 | 认证失败 |
| 3 | API/网络错误 |
| 4 | 权限不足 |
