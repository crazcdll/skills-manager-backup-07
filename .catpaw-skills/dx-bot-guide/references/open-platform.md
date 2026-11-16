# 开放平台扩展：18 项命令

## 共用规则与模式

- 下表标为“写”的命令默认 **dry-run**，先检查并预览；确认后加 `--force` 才执行。查询默认执行；显式 `--dry-run` 可只校验，且优先于 `--force`。
- 新增 `msg as-user …` / `group as-user …` 必须显式提供已取得、对目标接口有效的用户 token：`--user-token` 或 `DX_BOT_USER_TOKEN`。只透传，不自动获取、转换或退回机器人身份；下文示例假定已设置该环境变量。
- 上述新增用户态命令支持 **token-only Direct**，不需要 bot `client_id` / `client_secret`。优先级：① `--mode` 或其环境变量 `DX_BOT_MODE` 是入口 mode override，Clap 让 `--mode` 优先于环境变量；`--mode proxy` 或 `DX_BOT_MODE=proxy` 均可主动覆盖 `direct.local_only=true`。② 无入口 override 时，local-only 优先于配置 mode：`direct.local_only=true` 固定 Direct，抑制 `config.mode = "proxy"`。③ 再以 `config.mode` fallback：配置 mode 为 proxy 时走 Proxy，否则（包括默认 auto）走 Direct。`--client-id` 不覆盖这些用户态命令由 `--mode` / `DX_BOT_MODE` 指定的入口 mode，也不切换用户身份。旧命令模式规则不变。
- 表情配置查询是应用态，不需要用户 token。Direct 的机器人合并消息经 `cli-proxy`，`direct.local_only=true` 时拒绝；其他新增 Direct 操作走官方 HTTP。Proxy 请求发往 `/auto/api/cli/v1`，应用态使用**共享服务 bot，而非 profile bot**；仅机器人 `msg merge get` 在 Proxy 固定返回业务码 403，需改用 Direct 与应用凭证，用户态 `msg as-user merge` 不受此限制。
- 普通对象 ID 为正 signed i64（≤`9223372036854775807`），不要混用 GID、UID、empId、botId。JSON ID 推荐十进制字符串。CLI 外层业务对象可保留 Rust 精确 i64 数字；仅 **Proxy 或 Direct 机器人合并消息经 `cli-proxy` 跨 TS** 的请求使用 `proxy_safe_payload`，把 unsafe integer（绝对值 >`9007199254740991`）转成 string。Direct 官方 HTTP 保留精确 numeric，不自动字符串化。多语言消息体内的 JSON 字符串不由该转换重写，其中超大 long 必须显式写十进制字符串。历史游标与群空间 ID 的例外见下文。
- JSON 文件不做额外 CLI 转义；`--request-file` 只含业务字段，不带 token/req/request 封套。文件参数接受 `-` 表示 stdin，一次最多一个文件参数读取 stdin。
- `tool-cli` 后端的 Gateway SDK 已升级并固定为精确版本 `@thrift-api/dxenterprise-open-gateway@1.2.12-SNAPSHOT`（不使用 `^` / `~`）；现有 18 项操作仍为机器人合并消息走新版 Thrift、其余 16 项走官方 HTTP，**不自动重试**，也不自动遍历成员或历史消息分页。SDK 的其他能力不代表已全部接入 REST / CLI；版本差异与迁移见 `tool-cli` 仓库的 `docs/gateway-sdk-upgrade.md`。
- CLI 复用缓存的开放平台 HTTP client，强制 HTTP/1；HTTP 不跟随 redirect、超时 10 秒。Rust CLI 与 TS 后端在流式读取 HTTP 响应体时均有 **8 MiB（8388608 字节）**上限。超限或读取失败不自动重试/拆页，分页查询请减小 `--limit` 后请求较小页面。Thrift/RPC 由 SDK 预先缓冲，**RPC 缓冲不受该 HTTP 上限保护**；后续 CLI 读取 HTTP 封套仍受上限，不保证 RPC 全链路内存有界。

### Proxy 应用态的调用人授权

以下是 `/auto/api/cli/v1` 与 `/cli/api/v1` 别名共用的业务 policy，不改变既有入口认证或 SSO 流程。stderr warning 只提示共享服务 bot 身份，**不能代替服务端 authorization**。

| 操作 | 已登录操作人的授权要求 |
| --- | --- |
| `SpaceList`、`BotReactionAdd/Delete` | 目标群成员 |
| `SpaceAdd/Delete` | 群主或管理员，沿用原 CLI 创建者例外 |
| `ReactionConfig` | 有可识别的 SSO 操作人 |
| `MergeSend` | 来源、目标分别核验：GROUP_CHAT 为群成员；PUB_CHAT 的 chatId 仅允许操作人自己的大象 UID |
| `MergeGet` | 固定 403：仅凭 msgId 无法验证源会话 scope，改用 Direct 与应用凭证 |
| `SendMultilingual` | UAC 必须配置 canonical 资源 `/auto/api/cli/v1/xm/msg/multilingual` 并对操作人授权；未配置、未授权或校验异常均 fail closed，返回 403 |

缺失操作人身份为 401，权限不足或授权校验异常为 403。多语言 `/cli/api/v1` 别名仍校验同一 canonical UAC 资源，path/query 不能改变资源。`/cli-proxy` **不套用共享 bot policy**，由上游校验 caller token 权限。

### 身份头与封套速查

CLI 自动构造 transport，JSON 文件不含以下身份头或封套。手工调用时后端入口均为 **POST + 裸业务对象 `B`**，其中 `/cli-proxy` 只提供 `MergeGet` / `MergeSend` 两项：

| 入口 | 应用态 | 用户态 |
| --- | --- | --- |
| `/auto/api/cli/v1` | 既有入口认证 + 上述业务 policy；共享服务 bot | 既有入口认证 + `X-Dx-User-Token` |
| `/auto/api/cli-proxy/v1` | 仅 `MergeGet` / `MergeSend`：`Authorization: Bearer <应用token>` + 必填 `X-Bot-AppId` | 不提供用户态操作 |

| 操作 | CLI / 后端自动构造的上游封套 |
| --- | --- |
| 机器人合并消息 | Thrift `accessToken` + `req=B` |
| 多语言、用户历史、用户合并查询、用户群角色 | HTTP `{ "req": B }` |
| 表情配置 | HTTP `{}` |
| 其余 HTTP 操作 | HTTP `{ "request": B }` |

完整路由清单在 `tool-cli` 仓库的 `docs/cli-proxy-api.md`；本参考不依赖跨仓库本地链接。

## 命令速查

### 消息：应用态 6 项、用户态 4 项

| 命令 | 参数与行为 |
| --- | --- |
| `msg merge get` | `--request-file FILE`：`mergeCondition` 查询链；仅 Direct，Proxy 固定 403 |
| `msg merge send`（写） | `--from-chat-id`、`--from-chat-type`、`--msg-ids`、`--to-chat-id`、`--to-chat-type` |
| `msg multilingual`（写） | `--emp-ids` 非空逗号列表、`--body-file FILE`；可选 `--type`（默认 text）、`--extension-file FILE` |
| `msg reaction add`（写） | `--message-id`、`--chat-id`、`--code`；机器人只支持 `groupChat` |
| `msg reaction delete`（写） | `--message-id`、`--chat-id`；不传 code |
| `msg reaction config` | 无业务参数，应用态查询可用 code/type/i18nName |
| `msg as-user history` | `--gid`、`--start-time`；可选 `--end-time`、`--limit`（默认 50，1–100）、`--last-mid`、`--channel`、`--sid` |
| `msg as-user merge` | `--request-file FILE`：`mergeInfoList`，不是 mergeCondition |
| `msg as-user reaction-add`（写） | `--message-id`、`--chat-id`、`--code`；可选 `--chat-type chat/groupChat` |
| `msg as-user reaction-delete`（写） | `--message-id`、`--chat-id`；可选 `--chat-type chat/groupChat`；不传 code |

表态 `--chat-type` 默认 `groupChat`；`chatId` 单聊用对端 UID、群聊用 GID，不是 empId。`--message-id` 别名 `--msg-id`，`--chat-id` 别名 `--gid`。HTTP 表态不接受 `sendNotice`，添加与删除参数不可混用。

### 群空间：3 项应用态操作

| 命令 | 参数与行为 |
| --- | --- |
| `group space list` | `--conversation-id`；可选 `--source-type`、`--include-hidden`（默认 false） |
| `group space add`（写） | `--conversation-id`、`--source-type`、`--url`；可选 `--title`、`--sync-children`（默认 false）、`--create-space-if-absent`（默认 true） |
| `group space delete`（写） | `--conversation-id`；`--link-id` / `--url` 至少一个，都传时 linkId 优先 |

`--conversation-id`（别名 `--gid`）是最长 128 位的正十进制字符串，自动附加 conversationType=group。sourceType 支持 citadel/ones/raptor/link/notebook。URL 仅 HTTP/HTTPS、≤2048 字符，title≤512，linkId≤128。布尔选项显式接受 true/false，false 会保留；createSpaceIfAbsent=false 不会自动创建缺失空间。

### 用户群：5 项，均需显式用户 token

| 命令 | 参数与行为 |
| --- | --- |
| `group as-user create`（写） | 必填 `--category`；可选 `--name`、`--desc`、`--admin-emp-ids`、`--member-emp-ids` |
| `group as-user add-members`（写） | `--gid`、`--invitee-emp-ids`：被邀请人的 empId 逗号列表 |
| `group as-user members` | `--gid`；`--offset` 默认 0、`--limit` 默认 100；offset>0 必须提供上一页 `--version` |
| `group as-user roles` | `--gid`、`--member-ids` 逗号列表、`--member-category HUMAN/ROBOT`；分别使用 empId/botId |
| `group as-user info` | `--gid`：查群基础信息 |

建群管理员与成员列表均为 empId；category 必须用业务确认的整数，无猜测默认值。成员页不传当前用户 empId，由上游注入；保留 hasNext/version/memberList，调用方显式翻页。既有群设置继续用 `group set-config` / `group update`，不新增重复入口。

## 合并消息 JSON 与转发

保存为 `merge-bot.json`；机器人嵌套查询链按**外层到内层**排列。首项只能 GROUP_CHAT/PUB_CHAT，后续也支持 CHAT：

```json
{
  "mergeCondition": [
    { "msgId": "123456789012345678", "chatType": "GROUP_CHAT" },
    { "msgId": "123456789012345679", "chatType": "CHAT" }
  ]
}
```

用户查询保存为 `merge-user.json`，字段不同，chatType 支持 CHAT/GROUP_CHAT/PUB_CHAT：

```json
{"mergeInfoList":[{"msgId":"123456789012345678","chatType":"CHAT"}]}
```

```bash
# 需应用凭证，且 direct.local_only 不能为 true
dx-bot-cli --mode direct msg merge get --request-file merge-bot.json --json
dx-bot-cli msg as-user merge --request-file merge-user.json --json
dx-bot-cli msg merge send --from-chat-id 123456 --from-chat-type GROUP_CHAT \
  --msg-ids 123456789012345678,123456789012345679 \
  --to-chat-id 234567 --to-chat-type GROUP_CHAT --force --json
```

转发 `--msg-ids`（别名 `--from-msg-ids`）为 1–99 个既有消息 ID。来源和目标类型只支持 GROUP_CHAT/PUB_CHAT，chatId 分别为 GID/对端大象 UID，不能用 empId/MIS/botId 替代。

## 多语言消息 JSON

`multilingual.json` 只含语言 map，不是完整业务请求；收件人 `--emp-ids` 是非空 empId 列表，无文档规定的 100 人上限。语言支持 zh/en/zh-HK，至少一种；值可为对象或该对象的 JSON 字符串：

```json
{
  "zh": {"text":"## 发布通知\n服务：example-api\n[查看变更](https://example.com/changelog)"},
  "en": "{\"text\":\"## Release notice\\nService: example-api\"}",
  "zh-HK": {"text":"## 發佈通知\n服務：example-api"}
}
```

可选 `extension.json`：

```json
{"fileType":"markdown"}
```

```bash
# 先预览，确认后在同一命令添加 --force 实际发送
dx-bot-cli msg multilingual --emp-ids 23983167,12345678 --type text \
  --body-file multilingual.json --extension-file extension.json --json
```

CLI 将各语言对象序列化为上游需要的字符串；Rust 与 TS 按相同的最低必填字段及 UTF-8 字节限制校验全部 15 种 type：text/image/link/multilink/audio/video/file/gps/vcard/gvcard/newemotion/event/custom/general/quote，不是任意对象都可发送。每种语言消息体≤32000 UTF-8 字节，该消息体与 extension 合计≤32767 UTF-8 字节；**text.text 为 1–6000 UTF-8 字节，不是字符数**（如 2000 个常见三字节汉字或 1500 个四字节 emoji）。link.title 为 1–200 UTF-8 字节；image 需 thumbnail/normal/original，link 需 title/image/link/content，quote.replyMsg 按 text/general 递归校验。文件内容仅按标准 JSON 解析。

## 群空间、分页与表态示例

```bash
dx-bot-cli group space add --conversation-id 123456 --source-type link \
  --url https://example.com/project --title "项目入口" \
  --sync-children false --create-space-if-absent false --force --json
dx-bot-cli group as-user members --gid 123456 --offset 0 --limit 100 --json
# version 替换为真实上一页返回值
dx-bot-cli group as-user members --gid 123456 --offset 100 --limit 100 --version previous-page-version --json
dx-bot-cli msg as-user history --gid 123456 --start-time 1792713600000 --limit 50 \
  --last-mid 123456789012345678 --channel 1213 --sid topic-example --json
dx-bot-cli msg reaction config --json
dx-bot-cli msg as-user reaction-delete --message-id 123456789012345678 \
  --chat-type chat --chat-id 7118603 --force --json
```

历史 startTime/endTime 为毫秒时间戳，startTime≥0、endTime 不早于它。可选 lastMid 是完整 signed i64，channel 是完整 signed i32，均不额外要求正值；1213 是话题会话约定，不是通用 channel 枚举。sid 为可选字符串，允许空（`--sid ''`）。历史保留 msgList/hasNext，下一页显式传 last-mid。

## 响应与失败

新增消息与群操作共用公共脱敏：错误、成功输出和 dry-run 中的凭证字段及已知秘密值会被隐藏；“完整”表示业务结构完整，而非原样暴露凭证。

| 输出模式 | 成功 | API 失败（含部分失败） |
| --- | --- | --- |
| 非 JSON | stdout 只输出完整 `ApiResponse.data`（即含上游 status/data 的完整响应）；无 data 时打印成功标记 | stderr 输出完整 `ApiResponse`，失败退出 |
| `--json` | stdout 输出完整 `ApiResponse` | stdout 输出完整 `ApiResponse`，失败退出；诊断/警告仍走 stderr |

- CLI 成功封套为 `{code: 0, message, data: 完整上游响应}`，失败为非零 code；保留分页、审批、角色及嵌套业务/错误结构，不仅是列表。本地校验或传输失败没有上游响应时不会伪造详情。
- 后端封套为 `{status: 200, message, data: 完整上游响应}`，不能只看 HTTP 200；后端 status、CLI code 与上游 status.code 是不同层。
- 群空间除上游 status.code=0 外，还要求 data.success=true，且内层 data.data.ok 不能为 false。
- 多语言 failMap 非空，或建群/邀请 failEmpIdList 非空，返回 **code=207 并保留完整数据**；检查失败项，不要整批重试。邀请 joinGroupStatus=1 表示需审批，不等于已入群。
- JSON dry-run 标志统一为 **`dry_run`，不是 `dryRun`**：群操作为 `{dry_run: true, command, payload}`；消息操作为 `{dry_run: true, command, args}`，args 为摘要，不保证是完整请求体。后端没有 dry-run 开关，直接 POST 写接口会实际执行。

### 大整数响应：接受 `number|string`

不在输出阶段统一改写原类型，这是传输表示的兼容性契约：

| 路径 | 大整数表示 |
| --- | --- |
| Direct 官方 HTTP | 保留 Rust 精确 JSON number；上游本为 string 时仍保留 string |
| Proxy 官方 HTTP | TS 后端将 unsafe JSON integer 转为 string；安全整数仍可为 number，直接经 cli-proxy 转发 HTTP 也如此 |
| 机器人合并消息 | Direct / Proxy 均经 TS / Thrift，i64 通常为十进制 string，不强制全部字符串化 |

脚本应接受 **`number|string`**，需要文本可用 `tostring`；精确 ID 应使用支持大整数的 JSON 解析器，避免先强制转为 JS Number。不要将不同路径的 number/string 差异当作数据错误；请求的 `proxy_safe_payload` 不决定响应类型，也不作用于 Direct 官方 HTTP 精确 numeric 请求。
