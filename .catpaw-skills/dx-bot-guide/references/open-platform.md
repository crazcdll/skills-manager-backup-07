# 开放平台扩展（18 项）

## 共用规则

- 标「写」的命令默认 dry-run；确认后加 `--force`。显式 `--dry-run` 优先于 `--force`。
- `msg as-user …` / `group as-user …` 必须自带有效用户 token：`--user-token` 或 `DX_BOT_USER_TOKEN`。CLI 只透传，不获取、不换票、不回退机器人身份。
- 用户态命令支持 token-only direct（无需 bot 凭证）。模式优先级：有入口 `--mode` / `DX_BOT_MODE` 就听它（`--mode` 优先）；没有时 `direct.local_only=true` 压过 `config.mode`（配置的 proxy 被抑制）；再否则用 `config.mode`。`--mode proxy` / `DX_BOT_MODE=proxy` 都能覆盖 local-only。`--client-id` 不改变入口 mode，也不切换用户身份。
- 表情配置查询是应用态，无需用户 token。Direct 机器人合并消息走 `cli-proxy`，`local_only=true` 时拒绝；其余 Direct 走官方 HTTP。Proxy 请求打 `/auto/api/cli/v1`，应用态用**共享服务 bot，不是 profile bot**。
- ID：普通对象为正 signed i64，GID/UID/empId/botId 不可混用，JSON 里推荐十进制字符串。Proxy 或 Direct 机器人合并消息经 `cli-proxy` 跨 TS 时用 `proxy_safe_payload`（绝对值 >9007199254740991 转 string）；Direct 官方 HTTP 保留精确 numeric。
- JSON 文件不做 CLI 转义；`--request-file` 只含业务字段，不带 token/req/request 封套。文件参数接受 `-`（stdin），一次最多一个。
- 网关 SDK 固定 `@thrift-api/dxenterprise-open-gateway@1.2.12-SNAPSHOT`（不用 `^`/`~`）。不自动重试，不自动翻成员/历史分页。
- HTTP client 强制 HTTP/1、不跟随 redirect、超时 10s；响应体按流式读取上限 **8 MiB**（Rust 与 TS 后端相同），超限不重试、不拆页，减小 `--limit`。Thrift/RPC 由 SDK 预缓冲，不受该 HTTP 上限保护，但 CLI 读 HTTP 封套仍受限。

## Proxy 应用态授权

- `SpaceList` / `BotReactionAdd/Delete`：目标群成员
- `SpaceAdd/Delete`：群主或管理员（沿用创建者例外）
- `ReactionConfig`：有可识别 SSO 操作人
- `MergeSend`：GROUP_CHAT 需群成员；PUB_CHAT 只允许操作人自己的 UID
- `MergeGet`：固定 403，改用 Direct + 应用凭证
- `SendMultilingual`：UAC 需授权 canonical 资源，否则 403

缺操作人身份 401，权限不足或校验异常 403。stderr 的共享 bot 身份提示不代替服务端 authorization。`/cli-proxy` 不套共享 bot policy，由上游校验 caller token；`/cli/api/v1` 别名仍校验同一 canonical UAC 资源，path/query 改不了资源。

路由清单见 `tool-cli` 仓库 `docs/cli-proxy-api.md`。

## 请求封套

后端入口均为 **POST + 裸业务对象 `B`**；`/cli-proxy` 只有 `MergeGet` / `MergeSend`。

- `/auto/api/cli/v1`：应用态 = 入口认证 + 业务 policy、共享服务 bot；用户态 = 入口认证 + `X-Dx-User-Token`
- `/auto/api/cli-proxy/v1`：仅 merge 两项，`Authorization: Bearer <应用token>` + `X-Bot-AppId`；无用户态

- 机器人合并消息：Thrift `accessToken` + `req=B`
- 多语言、用户历史、用户合并查询、用户群角色：`{ "req": B }`
- 表情配置：`{}`
- 其余 HTTP：`{ "request": B }`

## 命令

### 消息：应用态 6 + 用户态 4

- `msg merge get`：`--request-file FILE`（`mergeCondition`）；仅 Direct，proxy 固定 403
- `msg merge send`（写）：`--from-chat-id` `--from-chat-type` `--msg-ids` `--to-chat-id` `--to-chat-type`
- `msg multilingual`（写）：`--emp-ids`（非空逗号列表）、`--body-file`；可选 `--type`(默认 text)、`--extension-file`
- `msg reaction add`（写）：`--message-id` `--chat-id` `--code`；机器人仅 `groupChat`
- `msg reaction delete`（写）：`--message-id` `--chat-id`；不传 code
- `msg reaction config`：无业务参数；应用态可查 `code` / `type` / `i18nName`
- `msg as-user history`：`--gid` `--start-time`；可选 `--end-time` `--limit`(默认50,1–100) `--last-mid` `--channel` `--sid`
- `msg as-user merge`：`--request-file FILE`（`mergeInfoList`，不是 mergeCondition）
- `msg as-user reaction-add`（写）：`--message-id` `--chat-id` `--code`；可选 `--chat-type chat|groupChat`
- `msg as-user reaction-delete`（写）：`--message-id` `--chat-id`；可选 `--chat-type`；不传 code

- 表态 `--chat-type` 默认 `groupChat`；`chatId` 单聊用对端 UID、群聊用 GID，不是 empId。
- 别名：`--message-id`=`--msg-id`，`--chat-id`=`--gid`。
- HTTP 表态不接受 `sendNotice`；add/delete 参数不可混用。
- `msg merge get` 的 proxy 403 只针对机器人态；用户态 `msg as-user merge` 不受限。

### 群空间：3 项应用态

- `group space list`：`--conversation-id`；可选 `--source-type` `--include-hidden`(默认 false)
- `group space add`（写）：`--conversation-id` `--source-type` `--url`；可选 `--title` `--sync-children`(false) `--create-space-if-absent`(true)
- `group space delete`（写）：`--conversation-id`；`--link-id` / `--url` 至少一个，都传时 linkId 优先

- `--conversation-id`（别名 `--gid`）为正十进制字符串，≤128 位，自动带 `conversationType=group`。
- sourceType：citadel/ones/raptor/link/notebook。URL 仅 HTTP(S) ≤2048，title ≤512，linkId ≤128。
- 布尔显式 true/false；`createSpaceIfAbsent=false` 不自动建空间。

### 用户群：5 项，均需用户 token

- `group as-user create`（写）：必填 `--category`；可选 `--name` `--desc` `--admin-emp-ids` `--member-emp-ids`
- `group as-user add-members`（写）：`--gid` `--invitee-emp-ids`
- `group as-user members`：`--gid`；`--offset`(0) `--limit`(100)；offset>0 必须 `--version`
- `group as-user roles`：`--gid` `--member-ids` `--member-category HUMAN|ROBOT`（empId / botId）
- `group as-user info`：`--gid`

- 管理员/成员均用 empId；category 用业务确认的整数，无默认值。
- 成员页不传当前用户 empId（上游注入）；保留 hasNext/version/memberList，调用方显式翻页。
- 群设置继续用 `group set-config` / `group update`。

## 合并消息

机器人（`merge-bot.json`，查询链从外到内，首项只能 GROUP_CHAT/PUB_CHAT，后续可 CHAT）：

```json
{"mergeCondition":[{"msgId":"123456789012345678","chatType":"GROUP_CHAT"}]}
```

用户（`merge-user.json`，CHAT/GROUP_CHAT/PUB_CHAT）：

```json
{"mergeInfoList":[{"msgId":"123456789012345678","chatType":"CHAT"}]}
```

```bash
dx-bot-cli --mode direct msg merge get --request-file merge-bot.json --json   # local_only 不能为 true
dx-bot-cli msg as-user merge --request-file merge-user.json --json
dx-bot-cli msg merge send --from-chat-id 123456 --from-chat-type GROUP_CHAT \
  --msg-ids 123456789012345678,123456789012345679 \
  --to-chat-id 234567 --to-chat-type GROUP_CHAT --force --json
```

转发 `--msg-ids`（别名 `--from-msg-ids`）1–99 个；来源/目标仅 GROUP_CHAT / PUB_CHAT，chatId 为 GID / 对端 UID，不能用 empId/MIS/botId。

## 多语言

`multilingual.json` 只含语言 map；`--emp-ids` 非空，无 100 人上限。语言 zh/en/zh-HK 至少一种，值为对象或其 JSON 字符串。

```json
{
  "zh": {"text":"## 发布通知\n服务：example-api"},
  "en": "{\"text\":\"## Release notice\"}"
}
```

可选 `extension.json`：`{"fileType":"markdown"}`

```bash
dx-bot-cli msg multilingual --emp-ids 23983167,12345678 --type text \
  --body-file multilingual.json --extension-file extension.json --json
```

限制：

- 校验全部 15 种 type 的最低必填字段：text/image/link/multilink/audio/video/file/gps/vcard/gvcard/newemotion/event/custom/general/quote
- 每种语言 body ≤32000 UTF-8 字节；body + extension 合计 ≤32767
- **text.text 1–6000 UTF-8 字节**（非字符数）；link.title 1–200 字节
- image 需 thumbnail/normal/original；link 需 title/image/link/content；quote.replyMsg 按 text/general 递归校验

## 示例

```bash
dx-bot-cli group space add --conversation-id 123456 --source-type link \
  --url https://example.com/project --title "项目入口" \
  --sync-children false --create-space-if-absent false --force --json
dx-bot-cli group as-user members --gid 123456 --offset 0 --limit 100 --json
dx-bot-cli group as-user members --gid 123456 --offset 100 --limit 100 --version previous-page-version --json
dx-bot-cli msg as-user history --gid 123456 --start-time 1792713600000 --limit 50 \
  --last-mid 123456789012345678 --channel 1213 --sid topic-example --json
dx-bot-cli msg reaction config --json
dx-bot-cli msg as-user reaction-delete --message-id 123456789012345678 \
  --chat-type chat --chat-id 7118603 --force --json
```

- 历史 startTime/endTime 为毫秒，startTime≥0 且 endTime 不早于它；lastMid 为完整 signed i64，channel 为 signed i32；1213 是话题会话约定，不是通用枚举；sid 可空（`--sid ''`）。
- 历史保留 msgList/hasNext，下一页显式传 last-mid。

## 响应与失败

- 非 JSON：成功时 stdout 输出 `ApiResponse.data`（完整上游响应）；失败时 stderr 输出完整 `ApiResponse` 并退出
- `--json`：成功/失败都 stdout 输出完整 `ApiResponse`，失败退出；诊断/警告走 stderr

- CLI 封套 `{code: 0, message, data}`；失败 code 非 0。后端封套 `{status, message, data}`，不能只看 HTTP 200。
- 群空间还需 `data.success=true` 且内层 `data.data.ok != false`。
- 多语言 failMap 非空、建群/邀请 failEmpIdList 非空 → `code=207` 且保留完整数据，只检查失败项，不整批重试。邀请 `joinGroupStatus=1` = 待审批。
- dry-run 标志是 `dry_run`：群操作为 `{dry_run, command, payload}`，消息为 `{dry_run, command, args}`（args 只是摘要）。后端无 dry-run 开关，直接 POST 写接口会实际执行；本地校验/传输失败不会伪造上游详情。
- 凭证与已知 secret 在错误/成功/dry-run 输出中会被脱敏；“完整”指业务结构完整，不是原样暴露凭证。

## 大整数

脚本接受 `number|string`：Direct 官方 HTTP 保留 number；proxy 会把 unsafe integer 转 string；机器人合并消息经 Thrift 通常为 string。精确 ID 用支持大整数的解析器，别先转 JS Number。
