---
name: dx-bot-guide
description: "大象机器人 CLI 工具（dx-bot-cli）。用于通过命令行发送大象消息（单聊/群聊/Markdown/@人/@all）、管理群组、查询用户身份、查看历史消息。当用户需要操作大象机器人时使用。"

metadata:
  skillhub.creator: "rancheng02"
  skillhub.updater: "rancheng02"
  skillhub.version: "V3"
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

| 模式 | 场景 | 凭证 |
|------|------|------|
| `direct` | 有 Bot 凭证，功能完整 | client_id + client_secret |
| `proxy` | 无凭证，通过代理 | `sso-auth-cli` 鉴权 |
| `auto`（默认） | 有凭证走 direct，否则 proxy | — |

## 核心原则

1. **先 dry-run 再执行**：风险操作默认 dry-run，加 `--force` 才真正执行
2. **参数不确定时**：先跑 `dx-bot-cli <cmd> --help` 确认
3. **出错时加 -v 调试**：`-v` info / `-vv` debug / `-vvv` trace（含完整 HTTP）

---

## 消息发送

### 单聊

```bash
# 纯文本（单人单聊无需 --force）
dx-bot-cli msg send-chat --to <mis> --text "消息内容"

# Markdown
dx-bot-cli msg send-chat --to <mis> --markdown "**加粗** 正文"

# 多人（>10 人为风险操作，需 --force）
dx-bot-cli msg send-chat --to <mis1>,<mis2>,<mis3> --text "通知"

# 从文件读取收件人
dx-bot-cli msg send-chat --to-file ./receivers.txt --text "批量通知" --force

# 管道输入
echo "构建结果: SUCCESS" | dx-bot-cli msg send-chat --to <mis> --stdin
```

### 群聊

```bash
# 纯文本
dx-bot-cli msg send-group --gid <群ID> --text "群通知" --force

# @指定人（纯文本模式，写 @mis 即可）
dx-bot-cli msg send-group --gid <群ID> --text "请 @<mis> 处理" --force

# @所有人
dx-bot-cli msg send-group --gid <群ID> --text "紧急 @all" --force

# Markdown + @人（需用 [@显示名:uid] 格式）
dx-bot-cli msg send-group --gid <群ID> --markdown "[@张三:<uid>] 请确认" --force

# Markdown + @所有人
dx-bot-cli msg send-group --gid <群ID> --markdown "[@所有人:-1] 全员通知" --force
```

### @ 格式规则（重要）

纯文本（`--text`）和 Markdown（`--markdown`）的 @ 格式**互斥**：

| 模式 | 写法 | 说明 |
|------|------|------|
| `--text` | `@<mis>` | CLI 自动解析为富文本 |
| `--markdown` | `[@显示名:<uid>]` | 需提前查 UID |
| `--text` | `@all` 或 `@所有人` | @全员 |
| `--markdown` | `[@所有人:-1]` | @全员 |

> - 不要在 `--markdown` 中写 `@mis`，不会生效。获取 UID：`dx-bot-cli user lookup --mis <mis>`
> - 纯文本模式中 `@mis` 后需跟空格或标点才能识别（如 `请 @zhangsan 处理` ✓，`请@zhangsan处理` ✗）

### 撤回

```bash
dx-bot-cli msg recall-chat --to <mis> --msg-id <msgId>
dx-bot-cli msg recall-group --gid <群ID> --msg-id <msgId>
```

---

## 用户查询

```bash
# MIS → UID（单个返回详情，多个返回映射表）
dx-bot-cli user lookup --mis <mis>
dx-bot-cli user lookup --mis <mis1>,<mis2>,<mis3>

# UID → MIS
dx-bot-cli user lookup --uid <uid1>,<uid2>

# 从文件批量查询
dx-bot-cli user lookup --mis-file ./mis-list.txt
```

---

## 群管理（常用）

```bash
# 查询
dx-bot-cli group info --gid <群ID>
dx-bot-cli group members --gid <群ID>
dx-bot-cli group search --name "关键词"
dx-bot-cli group list-joined

# 添加成员
dx-bot-cli group add-members --gid <群ID> --members <mis1>,<mis2> --force
```

> 完整群管理命令（创建/解散/转让/配置等）→ [references/group-management.md](references/group-management.md)

---

## 历史消息（仅 Direct 模式）

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

| 参数 | 说明 |
|------|------|
| `--mode direct\|proxy` | 强制模式 |
| `--json` | JSON 输出 |
| `-v / -vv / -vvv` | 调试级别 |
| `--dry-run` | 仅验证不执行 |
| `--force` | 跳过 dry-run 保护 |
| `--bot-uid <UID>` | 指定 Bot UID |
| `--profile <NAME>` | 指定配置 profile |

---

## 风险操作（默认 dry-run）

- `group create` / `dismiss` / `remove-members` / `transfer` / `add-bot`
- `msg send-chat` 批量（>10 人）
- `msg send-group` 含 @all

---

## 参考文档（按需查阅）

| 文档 | 内容 |
|------|------|
| [references/config.md](references/config.md) | 配置管理、环境变量、多 Profile |
| [references/group-management.md](references/group-management.md) | 群管理完整命令 |
| [references/advanced.md](references/advanced.md) | 卡片消息、操作日志、权限诊断、排障 |
