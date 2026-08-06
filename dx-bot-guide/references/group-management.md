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
dx-bot-cli group list-joined
dx-bot-cli group list-joined --cursor <token> --page-size 50
```

## 公告与更新

```bash
dx-bot-cli group set-notice --gid <群ID> --text "公告内容"
dx-bot-cli group get-notice --gid <群ID>
dx-bot-cli group update --gid <群ID> --name "新群名" --info "新简介"
```

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

## 拉 Bot 入群

```bash
dx-bot-cli group add-bot --gid <群ID> --app-key <应用appkey> --force
```

## Proxy 模式限制

以下命令仅 Direct 模式支持：`dismiss`、`transfer`、`set-admin`、`set-notice`、`update`、`set-config`
