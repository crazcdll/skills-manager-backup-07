# 群管理

## 创建

```bash
dx-bot-cli group create --name "群名" --members <mis1>,<mis2> --owner <mis> \
  --admins <mis> --info "简介" --group-mode A --force
```

- `--group-mode A`（默认）：Bot 群主，指定用户管理员
- `--group-mode B`：指定用户群主，Bot 管理员；必须 `--owner`，且需 pubId 写入 `botAdmins`
- `--members-file <PATH>`：从文件读成员
- `--bot-admins <pubId,...>`：额外机器人管理员，填 pubId

> 模式 A 不需要 bot-uid；模式 B 需要（`--bot-uid` / `DX_BOT_UID` / profile `bot_uid` / 自动查询任一）。

## 解散 / 转让

```bash
dx-bot-cli group dismiss --gid <群ID> --force
dx-bot-cli group transfer --gid <群ID> --to <mis> --force
```

> 都要求 bot 是群主。配了 bot-uid 会在本地预检并给可读报错；没配则跳过预检，由服务端判定。

## 成员与管理员

```bash
dx-bot-cli group add-members --gid <群ID> --members <mis1>,<mis2> --force
dx-bot-cli group remove-members --gid <群ID> --members <mis> --force
dx-bot-cli group set-admin --gid <群ID> --user <mis> --enable
dx-bot-cli group set-admin --gid <群ID> --user <mis> --disable
```

> `set-admin` 非风险操作，无需 `--force`；bot-uid 可选，仅影响预检。

## 查询

```bash
dx-bot-cli group info --gid <群ID>
dx-bot-cli group members --gid <群ID>
dx-bot-cli group search --name "关键词"

dx-bot-cli group list-joined                       # 自动翻页拉全量
dx-bot-cli group list-joined --limit 20            # 截断，输出 next_cursor
dx-bot-cli group list-joined --limit 20 --cursor <next_cursor>
dx-bot-cli group list-joined --page-size 50        # 单次请求页大小，默认 20，上限 50
```

- `--limit`：结果总条数上限（>0，省略=全量），截断时给续取游标
- `--json` 下 `next_cursor` / `has_more` 可用于程序化分页
- direct / proxy 语义一致

## 公告与更新

```bash
dx-bot-cli group set-notice --gid <群ID> --text "值班表\n周一: alice"
dx-bot-cli group set-notice --gid <群ID> --text "C:\temp" --no-unescape
dx-bot-cli group get-notice --gid <群ID>
dx-bot-cli group update --gid <群ID> --name "新群名" --info "新简介"
```

> `set-notice` 非风险，直接执行；预览加 `--dry-run`。内联 `--text` 自动还原转义，字面量反斜杠用 `--no-unescape`。

## 群配置

```bash
dx-bot-cli group set-config --gid <群ID> \
  --mute true --audit true --allow-add-members false \
  --allow-at-all false --allow-share false \
  --history-visibility week      # none / day / week / all
```

## Bot 入群 / 退群

```bash
# direct：以当前 SSO 用户身份拉机器人入群
dx-bot-cli --mode direct --profile default group add-bot --gid <群ID> --force
dx-bot-cli --mode direct group add-bot --gid <群ID> --bot-id <pubId> --force
# proxy：只需 gid
dx-bot-cli --mode proxy group add-bot --gid <群ID> --force

dx-bot-cli group remove-bot --gid <群ID> --force
```

- `--bot-id` 是机器人 pubId（非 appKey），可省略自动解析
- `--user-token` 可省略，默认取 sso-auth-cli 缓存的用户票据
- “已在当前群组中” = 机器人已在群内，无需重复添加
- 移除时若提示机器人是群主，先 `group transfer`

## 模式支持

全部命令 direct / proxy 均支持。与 bot-uid 相关的只有 `create --group-mode B`（必需）、`add-bot`（可省）、`dismiss`/`transfer`/`set-admin`（可省，仅预检）。
