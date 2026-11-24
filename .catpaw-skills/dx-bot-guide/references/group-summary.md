# 群聊消息总结

## 触发

「帮我总结下群消息」「群消息总结」「总结一下群聊」「群聊总结」。

## 必要信息

- `gid`：群数字 ID（没有先用 `group search --name <群名>` 或 `group list-joined` 定位）
- 时间范围：默认 24 小时

缺参数就问用户，别猜。

## 约束

1. 机器人必须在群内。
2. 时间范围 ≤14 天；超过不要直接拉，先和用户确认缩短（接口不保证完整性）。
3. 非群主受群配置「机器人可查看历史消息时间」限制。

## 流程

### 1. 拉消息

```bash
dx-bot-cli --json msg history-group --gid <GID> --start 24h --page-size 100
```

- `--start` 支持 `1h`/`24h`/`7d` 或毫秒，最早 3 年前
- `data.has_more=true` 时把 `data.page_token` 传给 `--page-token` 续取，直到 false
- 禁止 `head` 截断 JSON

### 2. 解析 `data.msgs`

- `msg_id`：消息 ID
- `from_uid` / `from_pub_id`：发送者；人 `from_pub_id=0`，机器人 `from_uid=0`
- `cts`：Unix 毫秒
- `msg_type`：1 文本 / 4 图片 / 6 图文 / 7 多图文 / 8 文件 / 13 模板 / 17 富文本
- `message`：消息体 JSON，文本取 `message.text`
- `is_cancel`：true 跳过

类型处理：1 取 `text`；4 标 `[图片]`；6 取 `title`/`link`；8 标 `[文件]` 取 `name`；13 取 `contentTitle`/`content`；17 尽量提取文本。

发送者：`from_pub_id != 0` → `[机器人]`；否则 uid，未知显示 `用户{uid}`，可 `user lookup --uid` 批量换姓名。

时间统一东八区：

```bash
jq -r '.data.msgs[] | "\((.cts/1000+28800)|strftime("%m-%d %H:%M"))"'
```

### 3. 总结

- 按话题/时间段分组，emoji + 标题
- 关键信息：谁说了什么、结论、待办
- @、决策、待办单独高亮
- 过滤水聊表情，人名用真实姓名，不加原文没有的内容
- >100 条按主要话题归类

### 4. 返回

**只发单聊给请求者本人，严禁发群**（群发会泄露群内对话）。

```bash
dx-bot-cli --force msg send-chat --to <请求者mis> --text "<总结>"
```

多行用 `\n`；含字面量反斜杠改 `--stdin` 或 `--no-unescape`。

## 错误处理

- `70003`：bot 不在群；`group list-joined` 核对 gid，提示先拉机器人入群
- `70005`：权限不足，可能需群主配置
- `40001`：参数错：单聊 `--uid` 传了数字（改 MIS）/ 时间戳格式 / `--start` 超 3 年

消息为空：告知该时段无消息（新群只有建群后的消息）。
