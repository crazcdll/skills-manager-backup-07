---
name: dx-bot-guide
description: "大象机器人 CLI 工具（dx-bot-cli）。用于通过命令行发送大象消息（单聊/群聊/Markdown/@人/@all/@机器人/图片/文件/图文/卡片等多类型消息，支持动态消息与自定义 extension）、管理群组、查询用户身份、查看历史消息、查询卡片最新内容、撤回消息、总结群聊消息。当用户需要操作大象机器人时使用。"

metadata:
  skillhub.creator: "rancheng02"
  skillhub.updater: "rancheng02"
  skillhub.version: "V11"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "75893"
  skillhub.high_sensitive: "false"
---

# dx-bot-cli

## 快速开始

```bash
dx-bot-cli --version
curl -fsSL https://sre.sankuai.com/tool/dx-bot-cli/install | sh   # macOS/Linux
irm https://sre.sankuai.com/tool/dx-bot-cli/install | iex         # Windows

# 判断 direct 是否可用：config show 末尾会打印「凭证来源」与「direct 可用」
dx-bot-cli config show
# 只有提示「未找到 bot 凭证」时才走 proxy，需要 SSO
dx-bot-cli auth status
```

> `config show` 的 TOML 走 stdout（`client_secret` 默认脱敏，需明文核对时加 `--reveal-secrets`），凭证判定走 stderr（可安全 `| toml`）。提示里出现 `direct 可用` 就不要再碰 SSO；`agent_info` 有值同样算 direct 可用，即使 TOML 里看不到 client_id。详见 [references/config.md](references/config.md)。
>
> 配置路径：macOS `~/Library/Application Support/dx-bot-cli/config.toml`，Linux `~/.config/dx-bot-cli/config.toml`。`config show` 不打印路径，`config init` 会。

## 模式与凭证

- `direct`（**首选**）：有 `client_id` + `client_secret`，直连开放平台，全功能
- `proxy`（兜底）：无凭证时代理转发，`sso-auth-cli` 鉴权
- `auto`（默认）：有凭证走 direct，否则 proxy；**能 direct 就不要手动选 proxy**

- 凭证按 profile 存：`config set-profile --name <n> --client-id … --client-secret …`；`--profile <n>` 或 `DX_BOT_PROFILE` 选用，默认 `default`。多 bot = 多个 profile。
- `--bot-uid`（pubId）**非必须**，只有 3 处用到：`group create --group-mode B`（必需）、`group add-bot`（可省略）、`dismiss`/`transfer`/`set-admin` 本地预检（可省略，缺省跳过）。发消息、查历史、群查询都不需要。详见 [references/config.md](references/config.md)。
- 消息全部 `--type` 与 `card query` 两种模式都支持；proxy 的 `card query` 忽略 `--to`，群聊要求你在群内。

## 硬规则

1. 写操作默认 dry-run，加 `--force` 才执行。
2. 参数不确定先跑 `<cmd> --help`。
3. 调试 `-v` / `-vv` / `-vvv`（trace 含完整 HTTP）。
4. 禁止 `head` / `head -c` 截断 JSON，按 `--page-size` 或 `jq` 控体积。
5. 全局参数放子命令前后均可。
6. **direct 优先**：有 bot 凭证就直连，别用 proxy/SSO；`auth status` 只在 direct 不可用时才需要。

## 开放平台扩展（18 项）

详见 [references/open-platform.md](references/open-platform.md)。要点：

- 写命令默认 dry-run，`--force` 执行，显式 `--dry-run` 优先。
- `msg as-user …` / `group as-user …` 必须自带有效用户 token（`--user-token` / `DX_BOT_USER_TOKEN`），支持 token-only direct（无 bot 凭证）。
- 模式优先级：有入口 `--mode` / `DX_BOT_MODE` 就听它（`--mode` 优先）；没有时 `direct.local_only=true` 压过 `config.mode`；再否则用 `config.mode`。两个入口 proxy 都能覆盖 local-only。
- Proxy 应用态用共享服务 bot（非 profile bot），须业务授权；机器人 `msg merge get` 在 proxy 固定 403，改用 direct。
- 多语言 `text` 上限 6000 **UTF-8 字节**。输出 ID 接受 `number|string`。

## 消息发送

```bash
# 单聊
dx-bot-cli msg send-chat --to <mis> --text "内容" --force
dx-bot-cli msg send-chat --to <mis> --markdown "**加粗**\n第二行" --force
dx-bot-cli msg send-chat --to <mis1>,<mis2> --text "通知" --force
dx-bot-cli msg send-chat --to-file ./receivers.txt --text "通知" --force
echo "结果" | dx-bot-cli msg send-chat --to <mis> --stdin --force

# 群聊
dx-bot-cli msg send-group --gid <群ID> --text "请 @<mis> 处理" --force
dx-bot-cli msg send-group --gid <群ID> --text "紧急 @all" --force
dx-bot-cli msg send-group --gid <群ID> --markdown "请 @<mis> 确认" --force
```

### @ 规则

- 直接写 `@<mis>` / `@all` / `@所有人`，CLI 自动查 UID，两种模式均可。
- 原生短语法 `[@显示名:<uid>]` / `[@所有人:-1]` 仅 `--markdown`。
- `@` 前不能紧跟字母/数字；`@mis` 后需空格或标点（`请@zhangsan处理` ✗）。MIS 支持字母、数字、下划线、英文点。
- 邮箱不会被识别为 mention。

### 转义

- 内联 `--text` / `--markdown` 还原 `\n` `\r\n` `\t` `\\`（全角 `＼n` / `＼t` 同样生效）；`--no-unescape` 关闭。
- 不处理转义：`--stdin*`、`--text-file`、`--markdown-file`、`--body`、`--tmpl-file`。
- 未知转义与末尾孤立反斜杠原样保留。
- `--no-unescape` 适用：`msg send-chat` / `send-group`、`card send-*` / `update-*`（含 `--abstract`）、`group set-notice`。

### 多类型消息

```bash
dx-bot-cli msg send-group --gid <群ID> --type image --body https://img.meituan.net/x.jpg --force
dx-bot-cli msg send-group --gid <群ID> --type image --body ./panel.png --force        # 自动上传
dx-bot-cli msg send-group --gid <群ID> --type link \
  --body '{"title":"上线","content":"已部署","link":"https://km.sankuai.com/..."}' --force
dx-bot-cli msg send-chat --to <mis> --type file --body-file body.json --force
```

- `--type`：image/file/link/multilink/audio/video/gps/vcard/gvcard/newemotion/event/custom/general/quote（默认 text）。
- 非 text：内容用 `--body` / `--body-file` / `--stdin`，须 JSON 对象 ≤32KB；不支持 `--markdown` 与 @。
- 字段明细 → [references/advanced.md](references/advanced.md)。

### 文件 / extension / 动态消息

```bash
dx-bot-cli msg send-group --gid <群ID> --type file --file ./report.xlsx --force   # 自动上传
dx-bot-cli msg upload-file ./report.xlsx                                          # 只上传

dx-bot-cli msg send-group --gid <群ID> --type custom \
  --body '{"templateName":"审批","contentTitle":"报销","content":"请处理"}' \
  --extension '{"custom":{"version":1,"type":1,"buttons":[{"button":"通过","action":"mtdaxiang://approve","type":"PRIMARY"}]}}' \
  --force

# @机器人
dx-bot-cli msg send-group --gid <群ID> --text "[@机器人名|mtdaxiang://www.meituan.com/pub/profile?pubid=<BOTID>&isAt=true] 触发" \
  --extension '{"botAt":[<BOTID>]}' --force

dx-bot-cli msg send-group --gid <群ID> --text "处理中..." --dynamic --force
```

- `--extension`：合并进 `sendMsgInfo.extension`，同名 key 覆盖。
- `--dynamic`：`isDynamicMsg=true`，可后续更新/撤回。

### 图片上传

```bash
dx-bot-cli msg upload-image ./panel.png
dx-bot-cli msg upload-image ./cover.jpg --creator <mis>
dx-bot-cli --json msg upload-image ./qr.png
```

- png/jpg/jpeg/gif/webp/bmp，≤10MB；>1MB 自动压缩为 JPEG（gif 除外）。永久 CDN URL。
- 非风险操作，无需 `--force`。

### 撤回

```bash
dx-bot-cli msg recall-chat --to <mis> --msg-id <msgId>
dx-bot-cli msg recall-group --gid <群ID> --msg-id <msgId>
# 不知道 msgId 先查
dx-bot-cli --json msg history-group --gid <群ID> --start 24h | jq '.data.msgs[] | {msg_id, cts, message}'
```

## 用户查询

- `mis`：账号名（邮箱前缀），发消息、@人用
- `empId`：IAM 数字 ID，可互查 mis/uid
- `uid`：大象数字 ID

```bash
dx-bot-cli user lookup --mis <mis>                    # 单个详情 / 多个映射表
dx-bot-cli user lookup --uid <uid1>,<uid2>            # UID → MIS
dx-bot-cli user lookup --emp-id <empId1>,<empId2>     # empId → MIS/UID
dx-bot-cli user lookup --mis-file ./mis-list.txt
```

- 查不到的行显示 `-`；`--json` 输出结构化结果。
- 只有 empId 时：先 `user lookup --emp-id` 换 mis，再发消息。

## 群管理（常用）

```bash
dx-bot-cli group info --gid <群ID>
dx-bot-cli group members --gid <群ID>
dx-bot-cli group search --name "关键词"
dx-bot-cli group list-joined                          # 默认拉全量
dx-bot-cli group list-joined --limit 20               # 截断并给 next_cursor
dx-bot-cli group list-joined --limit 20 --cursor <next_cursor>
dx-bot-cli group add-members --gid <群ID> --members <mis1>,<mis2> --force
```

> 创建/解散/转让/公告/配置 → [references/group-management.md](references/group-management.md)

## 历史消息

```bash
dx-bot-cli --json msg history-group --gid <群ID> --start 7d --page-size 100
dx-bot-cli --json msg history-chat --uid <mis> --start 24h --page-size 100
```

- `--start`：毫秒或 `1h`/`24h`/`7d`，必填，最早 3 年前（传 `0` 报错）。
- `--end`：毫秒或 `now`，默认 `now`。
- `--page-size`：1~100，默认 50，越界自动收敛并告警。
- `--page-token`：传上一页 `data.page_token`，取更早消息。
- 单聊 `--uid` **只接受 MIS**，数字 UID 报 `(code=40001)`。

### 分页

- `data.page_token`（整数）+ `data.has_more`；`has_more=false` 停止。
- 非 JSON：首行 `共 N 条消息（hasMore: …）`，末行 `下一页 pageToken: <数字>`。
- 自动翻页：

```bash
token=""; while :; do
  out=$(dx-bot-cli --json msg history-group --gid <群ID> --start 7d --page-size 100 ${token:+--page-token $token})
  echo "$out" | jq -r '.data.msgs[] | "\(.cts) \(.msg_id)"'
  token=$(echo "$out" | jq -r '.data.page_token // empty')
  [ "$(echo "$out" | jq -r '.data.has_more')" = "true" ] && [ -n "$token" ] || break
done
```

### 错误码

- `40001`：请求参数错误 → 单聊 `--uid` 传了数字（改 MIS）；`--start` 超 3 年
- `70003`：机器人不在该群 → gid 写错或未入群，`group list-joined` 核对
- `30002`：标准开放能力权限校验失败 → 多为限流误报，重试；见 advanced.md

- `--json` 顶层 `code` 只有 `0` / `500`，真实业务码在 `message` 里的 `(code=xxxxx)`。
- JSON 字段 snake_case：`msg_id` / `msg_type` / `from_uid` / `from_pub_id` / `is_cancel`。

### cts 时区

`cts` 是 Unix 毫秒。`jq` 的 `strftime` 按 UTC（少 8 小时），`strflocaltime` 依赖机器时区。固定 `+28800`：

```bash
jq -r '.data.msgs[] | "\((.cts/1000+28800)|strftime("%m-%d %H:%M"))"'   # ✅ 东八区
```

CLI 非 `--json` 输出已按东八区格式化。

## 全局参数

- `--mode direct|proxy`：强制模式
- `--json`：JSON 输出
- `-v` / `-vv` / `-vvv`：调试级别
- `--force`：风险操作实际执行
- `--bot-uid <UID>`：可选 pubId；仅模式 B 建群、`add-bot`、权限预检用；否则读 profile → 沙箱预置凭证 → 自动查询 → 跳过
- `--profile <NAME>`：选 profile；不传用 `default_profile`（默认 `default`）
- `--config <PATH>`：配置文件路径

## 风险操作（自动 dry-run）

`msg send-chat` / `send-group`、`card send-*` / `update-*`、`group create` / `dismiss` / `transfer` / `add-members` / `remove-members` / `add-bot` / `remove-bot`。

非风险：`set-notice` / `update` / `set-config` / `set-admin`、消息撤回、所有查询（含 `card query`）。开放平台写操作见 [references/open-platform.md](references/open-platform.md)。

## 参考文档

- [references/config.md](references/config.md)：profile、环境变量、bot_uid/pubId
- [references/group-management.md](references/group-management.md)：群管理完整命令
- [references/group-summary.md](references/group-summary.md)：群聊总结流程
- [references/open-platform.md](references/open-platform.md)：开放平台 18 项
- [references/advanced.md](references/advanced.md)：消息体字段、卡片、日志、排障
