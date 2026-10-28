# 群管理完整命令

## 创建群

```bash
dx-bot-cli group create \
  --name "群名称" \
  --members <mis1>,<mis2> \
  --owner <mis> \
  --admins <mis> \
  --info "群简介" \
  --group-mode A \
  --force
```

- `--group-mode A`（默认）：Bot 为群主，指定用户为管理员
- `--group-mode B`：指定用户为群主，Bot 为管理员
- `--members-file <PATH>`：从文件读取成员列表

## 解散群

```bash
dx-bot-cli group dismiss --gid <群ID> --force
```

## 成员管理

```bash
dx-bot-cli group add-members --gid <群ID> --members <mis1>,<mis2> --force
dx-bot-cli group remove-members --gid <群ID> --members <mis> --force
dx-bot-cli group transfer --gid <群ID> --to <mis> --force

# 管理员
dx-bot-cli group set-admin --gid <群ID> --user <mis> --enable
dx-bot-cli group set-admin --gid <群ID> --user <mis> --disable
```

## 群信息

```bash
dx-bot-cli group info --gid <群ID>
dx-bot-cli group members --gid <群ID>
dx-bot-cli group search --name "关键词"

# 查询机器人所在群（默认自动翻页拉全量）
dx-bot-cli group list-joined

# 手动翻页：--limit 控制总量，到量即停并输出 next_cursor
dx-bot-cli group list-joined --limit 20
# → 结果已达 --limit 上限，使用 `--cursor <next_cursor>` 继续获取下一批
dx-bot-cli group list-joined --limit 20 --cursor <next_cursor>

# 调整单次 API 请求的页大小（默认 20，上限 50）
dx-bot-cli group list-joined --page-size 50
```

> `--limit`：结果总条数上限（须 >0，省略 = 全量）；截断时输出续取游标，配合 `--cursor`
> 构成手动翻页。`--json` 模式下 `next_cursor` / `has_more` 字段可用于程序化分页。
> direct / proxy 两种模式默认均为**自动翻页拉全量**，`--limit` / `--cursor` 语义一致。

## 公告与更新

```bash
# 公告支持多行：\n 会自动还原为换行
dx-bot-cli group set-notice --gid <群ID> --text "值班表\n周一: alice\n周二: bob"

# 需要字面量反斜杠时加 --no-unescape
dx-bot-cli group set-notice --gid <群ID> --text "C:\temp" --no-unescape

dx-bot-cli group get-notice --gid <群ID>
dx-bot-cli group update --gid <群ID> --name "新群名" --info "新简介"
```

> `set-notice` 为非风险操作（直接执行），需预览时显式加 `--dry-run`。内联 `--text` 默认还原转义，字面量反斜杠用 `--no-unescape`。

## 群配置

```bash
dx-bot-cli group set-config \
  --gid <群ID> \
  --mute true \
  --audit true \
  --allow-add-members false \
  --allow-at-all false \
  --allow-share false \
  --history-visibility week   # none / day / week / all
```

## Bot 入群/退群

```bash
dx-bot-cli group add-bot --gid <群ID> --app-key <应用appkey> --force
dx-bot-cli group remove-bot --gid <群ID> --force
```

## 模式支持

上述所有群管理命令 direct / proxy 模式均支持。
