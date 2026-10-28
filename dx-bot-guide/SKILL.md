---
name: dx-bot-guide
description: "大象机器人 CLI 工具（dx-bot-cli）。用于通过命令行发送大象消息（单聊/群聊/Markdown/@人/@all/@机器人/图片/文件/图文/卡片等多类型消息，支持动态消息与自定义 extension）、管理群组、查询用户身份、查看历史消息、撤回消息、总结群聊消息。当用户需要操作大象机器人时使用。"

metadata:
  skillhub.creator: "rancheng02"
  skillhub.updater: "rancheng02"
  skillhub.version: "V7"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "75893"
  skillhub.high_sensitive: "false"
---

# dx-bot-cli 操作指南

大象 Bot 命令行工具，一行命令完成消息发送、群管理、用户查询等操作。

## 快速开始

```bash
# 确认安装
dx-bot-cli --version

# 未安装时
curl -fsSL https://sre.sankuai.com/tool/dx-bot-cli/install | sh        # macOS/Linux
irm https://sre.sankuai.com/tool/dx-bot-cli/install | iex              # Windows

# 确认鉴权状态
dx-bot-cli auth status
dx-bot-cli config show
```

## 运行模式

| 模式           | 场景                        | 凭证                      |
| -------------- | --------------------------- | ------------------------- |
| `direct`       | 有 Bot 凭证，功能完整       | client_id + client_secret |
| `proxy`        | 无凭证，通过代理            | `sso-auth-cli` 鉴权       |
| `auto`（默认） | 有凭证走 direct，否则 proxy | —                         |

> 消息能力：全部消息类型（text/Markdown/@人/@all、图片、文件、图文等所有 `--type`）两种模式均支持，proxy 经后端转发；图片支持 URL 或本地文件（自动上传）。

## 核心原则

1. **风险操作自动 dry-run**：不加 `--force` 时仅打印参数预览不落地，加 `--force` 才真正执行
2. **参数不确定时**：先跑 `dx-bot-cli <cmd> --help` 确认
3. **出错时加 -v 调试**：`-v` info / `-vv` debug / `-vvv` trace（含完整 HTTP）

---

## 消息发送

### 单聊

```bash
# 纯文本
dx-bot-cli msg send-chat --to <mis> --text "消息内容" --force

# Markdown（多行用 \n，会自动还原为换行）
dx-bot-cli msg send-chat --to <mis> --markdown "**加粗** 正文\n第二行" --force

# 多人
dx-bot-cli msg send-chat --to <mis1>,<mis2>,<mis3> --text "通知" --force

# 从文件读取收件人
dx-bot-cli msg send-chat --to-file ./receivers.txt --text "批量通知" --force

# 管道输入
echo "构建结果: SUCCESS" | dx-bot-cli msg send-chat --to <mis> --stdin --force
```

### 群聊

```bash
# 纯文本
dx-bot-cli msg send-group --gid <群ID> --text "群通知" --force

# @指定人（纯文本模式，写 @mis 即可）
dx-bot-cli msg send-group --gid <群ID> --text "请 @<mis> 处理" --force

# @所有人
dx-bot-cli msg send-group --gid <群ID> --text "紧急 @all" --force

# Markdown + @人（直接写 @mis，自动转 [@显示名:uid]）
dx-bot-cli msg send-group --gid <群ID> --markdown "请 @<mis> 确认" --force

# Markdown + @所有人
dx-bot-cli msg send-group --gid <群ID> --markdown "紧急 @all" --force
```

### @ 格式规则（重要）

两种模式均可直接写 `@<mis>` / `@all` / `@所有人`，CLI 自动解析并补全 UID：

| 模式         | 写法                               | 说明                       |
| ------------ | ---------------------------------- | -------------------------- |
| 两种均可     | `@<mis>`                           | 自动转富文本/短语法        |
| 两种均可     | `@all` 或 `@所有人`                | @全员                      |
| `--markdown` | `[@显示名:<uid>]` / `[@所有人:-1]` | 原生短语法，已查 UID 时可用 |

> `@mis` 后需跟空格或标点才能识别（如 `请 @zhangsan 处理` ✓，`请@zhangsan处理` ✗）

### 多行内容与转义

内联 `--text` / `--markdown` 参数会自动还原转义序列：`\n`（换行）、`\r\n`（换行）、`\t`（制表符）、`\\`（反斜杠），全角 `＼n` / `＼t` 同样生效。

```bash
# 多行 Markdown：用 \n 换行
dx-bot-cli msg send-group --gid <群ID> --markdown "## 上线通知\n服务已部署\n- 影响范围: ..." --force

# 需要发送字面量反斜杠（如 Windows 路径）时，加 --no-unescape 关闭还原
dx-bot-cli msg send-group --gid <群ID> --text "C:\new\table" --no-unescape --force
```

- **不做转义处理的输入**：`--stdin` / `--stdin-text` / `--stdin-markdown`、`--text-file` / `--markdown-file`、`--body`（JSON）、`--tmpl-file`
- 未知转义（如 Markdown 的 `\*`）原样保留；末尾孤立反斜杠也保留
- `--no-unescape` 适用命令：`msg send-chat` / `send-group`、`card send-chat` / `send-group` / `update-chat` / `update-group`（含 `--abstract`）、`group set-notice`

### 多类型消息（图片/文件/图文等）

> 全部 `--type` 两种模式均支持（proxy 经后端转发）；非 text 类型不支持 `--markdown` 与 @，body 须为 JSON 对象（≤32KB）。

```bash
# 图片：--body 直接传图片 URL，自动补全三种尺寸
dx-bot-cli msg send-group --gid <群ID> --type image --body https://img.meituan.net/x.jpg --force

# 图片：--body 直接传本地路径，发送时自动上传为永久 CDN URL
dx-bot-cli msg send-group --gid <群ID> --type image --body ./screenshots/panel.png --force

# 图文 link：--body 传 JSON 消息体
dx-bot-cli msg send-group --gid <群ID> --type link \
  --body '{"title":"上线通知","content":"服务已部署","link":"https://km.sankuai.com/..."}' --force

# 消息体从文件读取
dx-bot-cli msg send-chat --to <mis> --type file --body-file body.json --force
```

- `--type`：image/file/link/multilink/audio/video/gps/vcard/gvcard/newemotion/event/custom/general/quote（默认 text）
- 非 text 类型：内容改用 `--body`/`--body-file`/`--stdin`，须为 JSON 对象（≤32KB）；不支持 `--markdown` 与 @
- 各类型 body 字段 → [references/advanced.md](references/advanced.md)

#### 本地文件自动上传（file 类型）

```bash
# --file 本地路径自动上传并构造 file 消息体（等价于先 upload-file 再发）
dx-bot-cli msg send-group --gid <群ID> --type file --file ./report.xlsx --force

# 或先手动上传，取回 fileId/url/name/size/format
dx-bot-cli msg upload-file ./report.xlsx
```

#### extension 与动态消息

```bash
# custom 模板消息带操作按钮（extension.custom.buttons）
dx-bot-cli msg send-group --gid <群ID> --type custom \
  --body '{"templateName":"审批通知","contentTitle":"报销申请","content":"请及时处理"}' \
  --extension '{"custom":{"version":1,"type":1,"buttons":[{"button":"通过","action":"mtdaxiang://approve","type":"PRIMARY"}]}}' \
  --force

# @机器人（extension.botAt + 正文高亮链接）
dx-bot-cli msg send-group --gid <群ID> --text "[@机器人名|mtdaxiang://www.meituan.com/pub/profile?pubid=<BOTID>&isAt=true] 触发自动化" \
  --extension '{"botAt":[<BOTID>]}' --force

# 动态消息（可后续更新/撤回）
dx-bot-cli msg send-group --gid <群ID> --text "处理中..." --dynamic --force
```

- `--extension`：额外 `sendMsgInfo.extension` JSON 对象，与自动生成的 @/markdown 扩展合并（同名 key 覆盖），用于 custom 按钮、botAt 等
- `--dynamic`：发送动态消息（`isDynamicMsg=true`）

### 图片上传（获取永久 CDN URL）

只需拿到图片 URL（不发送消息）时使用，两种模式均支持，非风险操作无需 `--force`：

```bash
# 上传本地图片，输出永久 CDN URL（file.sankuai.com）
dx-bot-cli msg upload-image ./screenshots/panel.png

# 自定义上传者标识 / JSON 输出
dx-bot-cli msg upload-image ./cover.jpg --creator <mis>
dx-bot-cli --json msg upload-image ./qr.png
```

- 支持 png/jpg/jpeg/gif/webp/bmp，单张 ≤10MB；超过 1MB 自动压缩为 JPEG（gif 动图除外）
- URL 为永久链接，可复用于图片消息、link 封面、卡片 cover_img 等场景
- 完整说明 → [references/advanced.md](references/advanced.md)

### 撤回

```bash
dx-bot-cli msg recall-chat --to <mis> --msg-id <msgId>
dx-bot-cli msg recall-group --gid <群ID> --msg-id <msgId>
```

> 撤回需要显式 `--msg-id`。若只记得内容/时间，先用 `msg history-group` 查到目标消息的 `msgId`，再撤回：

```bash
# 1. 查最近消息，找到目标 msgId
dx-bot-cli --json msg history-group --gid <群ID> --start 24h | jq '.data.msgs[] | {msgId, cts, message}'

# 2. 按查到的 msgId 撤回
dx-bot-cli msg recall-group --gid <群ID> --msg-id <msgId>
```

---

## 用户查询

### 三种账号标识

| 标识   | 含义                       | 用途                         |
| ------ | -------------------------- | ---------------------------- |
| `mis`  | 账号名（邮箱前缀）          | 发消息、@人                  |
| `empId`| IAM 账号 ID（数字）         | 人员唯一标识，可互查 mis/uid |
| `uid`  | 大象通信 ID（数字）         | 发消息、@人等大象操作         |

### 查询命令

```bash
# MIS → UID（单个返回详情，多个返回映射表）
dx-bot-cli user lookup --mis <mis>
dx-bot-cli user lookup --mis <mis1>,<mis2>,<mis3>

# UID → MIS
dx-bot-cli user lookup --uid <uid1>,<uid2>

# empId → MIS/UID
dx-bot-cli user lookup --emp-id <empId1>,<empId2>

# 从文件批量查询
dx-bot-cli user lookup --mis-file ./mis-list.txt
```

输出说明：

- 单个 `--mis`：返回 MIS / UID / empId / 姓名详情
- `--uid`：返回 UID → MIS 映射表
- `--emp-id`：返回 empId → MIS、UID 映射表，查不到的 empId 对应行显示 `-`
- 加 `--json` 可获取结构化输出，便于脚本处理

### 常用工作流：empId 转发消息

用户只有 empId 时，先查 mis 再发消息：

```bash
# 1. empId → mis
dx-bot-cli user lookup --emp-id 23983167

# 2. 用查到的 mis 发消息
#    dx-bot-cli msg send-chat --to <查到的mis> --text "消息内容" --force
```

---

## 群管理（常用）

```bash
# 查询
dx-bot-cli group info --gid <群ID>
dx-bot-cli group members --gid <群ID>
dx-bot-cli group search --name "关键词"

# 机器人所在群（默认拉全量；--limit N 截断并输出 next_cursor，--cursor 续取手动翻页）
dx-bot-cli group list-joined
dx-bot-cli group list-joined --limit 20
dx-bot-cli group list-joined --limit 20 --cursor <next_cursor>

# 添加成员
dx-bot-cli group add-members --gid <群ID> --members <mis1>,<mis2> --force
```

> 完整群管理命令（创建/解散/转让/配置等）→ [references/group-management.md](references/group-management.md)

---

## 历史消息

```bash
# 群聊历史
dx-bot-cli msg history-group --gid <群ID> --start 7d
dx-bot-cli msg history-group --gid <群ID> --start 24h --page-size 100

# 单聊历史
dx-bot-cli msg history-chat --uid <mis> --start 24h
```

`--start` 支持：相对时间（`1h`/`24h`/`7d`）或毫秒时间戳。`--end` 默认 `now`。

---

## 全局参数

| 参数                   | 说明                                  |
| ---------------------- | ------------------------------------- |
| `--mode direct\|proxy` | 强制模式                              |
| `--json`               | JSON 输出                             |
| `-v / -vv / -vvv`      | 调试级别                              |
| `--force`              | 风险操作实际执行（默认自动 dry-run） |
| `--bot-uid <UID>`      | 指定 Bot UID                          |
| `--profile <NAME>`     | 指定配置 profile                      |

---

## 风险操作（自动 dry-run）

不加 `--force` 时仅打印参数预览，不真正执行：

- 所有消息发送：`msg send-chat` / `send-group`（不论人数、是否 @all）
- 卡片发送与更新：`card send-*` / `card update-*`
- 群管理：`group create` / `dismiss` / `transfer` / `add-members` / `remove-members` / `add-bot` / `remove-bot`

> `set-notice` / `update` / `set-config` / `set-admin`、消息撤回及各类查询非风险操作，无需 `--force`。

---

## 参考文档（按需查阅）

| 文档                                                             | 内容                               |
| ---------------------------------------------------------------- | ---------------------------------- |
| [references/config.md](references/config.md)                     | 配置管理、环境变量、多 Profile     |
| [references/group-management.md](references/group-management.md) | 群管理完整命令                     |
| [references/group-summary.md](references/group-summary.md)       | 群聊消息总结工作流                 |
| [references/advanced.md](references/advanced.md)                 | 卡片消息、操作日志、权限诊断、排障 |
