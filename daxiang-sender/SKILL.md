---
name: daxiang-sender
description: 通过大象开放平台 API 发送消息（个人/群组）。支持文本、Markdown、链接、文件、图片、名片、群名片、引用回复、模板、富文本等消息类型，支持 @某人（uid 或 mis 自动转换）、@所有人、@机器人，支持动态消息。自动处理 Token 获取和 mis→uid 转换。适用于"发送大象消息""给某人发大象""发群消息""@某人""@所有人""@机器人"等场景。

metadata:
  skillhub.creator: "suhao20"
  skillhub.updater: "wuqiqi05"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "1695"
  skillhub.high_sensitive: "false"
---

# Daxiang Sender

通过大象开放平台 API 发送消息的 Python skill。

## 特性

- ✅ 自动获取和缓存 accessToken（无需手动管理）
- ✅ 支持 mis 号自动转换为 uid（`--to` 和 `--at` 均支持）
- ✅ 支持文本、Markdown、链接（link）、多图文（multilink）消息
- ✅ 支持文件（file）、图片（image）消息快捷参数
- ✅ 支持名片（vcard）、群名片（gvcard）消息
- ✅ 支持引用回复（quote）消息
- ✅ 支持模板消息（custom）+ extension.custom 按钮扩展
- ✅ 支持通用/富文本消息（general），明文 JSON 自动 Base64 编码
- ✅ 支持个人消息和群组消息
- ✅ 支持 @某人（uid 或 mis 均可）、@所有人、@机器人
- ✅ 支持动态消息（`--dynamic`，后续可更新/撤回）
- ✅ 查询机器人所在群列表（`list-groups` 子命令）

## 前置条件

1. Python 3
2. `pip3 install requests PyJWT`
3. 在 [企平应用开放平台](https://open.sankuai.com/developer/app/list) 创建应用并获取 Client ID 和 Secret

## 脚本路径

```
~/.catpaw/skills/skills-market/daxiang-sender/scripts/send.py
```

所有示例中的 `{SKILL_DIR}` 均指该路径前缀：

```bash
SKILL_DIR=~/.catpaw/skills/skills-market/daxiang-sender
python3 $SKILL_DIR/scripts/send.py ...
```

## 凭证配置

凭证优先级：命令行参数 > 环境变量 > 配置文件。

### 方式 1：环境变量（推荐）

```bash
export DX_CLIENT_ID="你的ClientID"
export DX_CLIENT_SECRET="你的ClientSecret"
```

### 方式 2：配置文件 `~/.daxiang.json`

```json
{
  "clientId": "你的ClientID",
  "clientSecret": "你的ClientSecret"
}
```

### 方式 3：命令行参数

```bash
python3 $SKILL_DIR/scripts/send.py --client-id xxx --client-secret xxx ...
```

---

## 命令用法

### 子命令概览

```
send.py send          发送消息（个人或群组）
send.py list-groups   查询机器人所在的所有群
```

---

### 发送文本消息

```bash
# 私聊
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --text "Hello World"

# 群聊
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "Hello Group"

# 多个接收人（逗号分隔，支持 mis 号或 uid）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20,zhangsan \
  --text "Hello"
```

### 发送 Markdown 消息

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --text "**加粗** _斜体_ [链接](https://km.sankuai.com)" \
  --markdown
```

> ⚠️ **换行符说明**：shell 双引号中的 `\n` 是字面量，如需换行使用 `$'...'` 语法：
>
> ```bash
> python3 $SKILL_DIR/scripts/send.py send \
>   --group 69662141203 \
>   --text $'**标题**\n\n正文\n\n- 列表项 1\n- 列表项 2' \
>   --markdown
> ```

### 发送链接消息（图文卡片）

> ⚠️ `--image` 为**必填**字段，API 不接受空值。

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --link \
  --title "文章标题" \
  --content "文章描述" \
  --url "https://example.com" \
  --image "https://example.com/cover.jpg"
```

### 发送文件消息

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --file-url "https://example.com/report.xlsx" \
  --file-name "报告.xlsx" \
  --file-size 3296 \
  --file-format "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

> ⚠️ `--file-url` 不能包含中文字符和服务端口。`--file-format` 参考 MIME 规范，如 `application/pdf`、`text/plain`。

### 发送图片消息

```bash
# 简单模式（thumbnail/normal 自动与原图相同）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --image-url "https://example.com/photo.jpg"

# 完整模式（分别指定三个尺寸）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --image-url "https://example.com/photo_original.jpg" \
  --image-thumbnail "https://example.com/photo_thumb.jpg" \
  --image-normal "https://example.com/photo_normal.jpg"
```

### 发送名片消息

```bash
# 个人名片（type=1，默认）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --vcard-uid 2967510770

# Pub 名片（type=2）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --vcard-uid 137626262046 \
  --vcard-type 2
```

### 发送群名片消息

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --gvcard-gid 70473524669
```

### 发送引用回复消息

> 注意：一次调用只能回复一个会话中的一条消息，`--to` 只能传一个接收人。

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --quote-msg-id 1733383831204126722 \
  --reply-text "收到，已处理！"
```

### 发送模板消息（custom）

```bash
# 基础模板消息
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --custom-template "审批通知" \
  --custom-title "报销申请" \
  --custom-content "请及时处理报销申请" \
  --custom-link-name "查看详情" \
  --custom-link "https://oa.neixin.cn/approval/detail/123"

# 带操作按钮（extension.custom.buttons）
# 按钮格式：按钮文字|action_url[|PRIMARY|DANGER]
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --custom-template "审批通知" \
  --custom-title "报销申请" \
  --custom-content "请及时处理" \
  --custom-clink-name "审批详情" \
  --custom-clink-url "https://oa.neixin.cn/approval/detail/123" \
  --custom-button "通过|mtdaxiang://approve|PRIMARY" \
  --custom-button "驳回|mtdaxiang://reject|DANGER"
```

### 发送通用/富文本消息（general）

> `data` 字段必须是 **Base64 编码**的字符串。传入明文 JSON 时脚本会**自动 Base64 编码**。

```bash
# 传入明文 JSON（自动编码）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --general-data '{"nodes":[{"t":"text","c":"富文本内容"}]}' \
  --general-summary "消息摘要"

# 传入已编码的 Base64 字符串（直接使用）
python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --general-data "eyJub2RlcyI6W3sidCI6InRleHQiLCJjIjoiSGVsbG8ifV19"
```

### 发送自定义消息体（multilink 等高级类型）

```bash
cat > /tmp/msg.json << 'EOF'
{
  "num": 2,
  "content": "[{\"title\":\"标题1\",\"content\":\"描述1\",\"link\":\"https://example.com/1\",\"image\":\"https://example.com/1.jpg\"},{\"title\":\"标题2\",\"content\":\"描述2\",\"link\":\"https://example.com/2\",\"image\":\"https://example.com/2.jpg\"}]"
}
EOF

python3 $SKILL_DIR/scripts/send.py send \
  --to suhao20 \
  --body-file /tmp/msg.json \
  --msg-type multilink
```

`--body-file` 模式同样支持 `--at`、`--at-all`、`--bot-at`、`--markdown` 等 extension 参数。

### 发送动态消息

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "当前状态：处理中..." \
  --dynamic
```

---

## @ 提及功能

> @所有人 和 @机器人 仅在群消息中生效。

### @某人（支持 mis 或 uid）

```bash
# mis 号（推荐，自动转换）
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "请处理一下这个问题" \
  --at suhao20:苏灏

# uid
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "请处理一下这个问题" \
  --at 2967510770:苏灏

# @多人
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "请大家看一下" \
  --at suhao20:苏灏 \
  --at zhangsan:张三
```

### @所有人

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "大家注意，系统将于今晚维护" \
  --at-all
```

### @机器人

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "触发自动化任务" \
  --bot-at 137626262046:开放平台机器人
```

### 自定义@文本
> `--at`默认在`--text`的正文前添加"@某人"的高亮文本，无法指定高亮文本在消息中的位置。添加`--custom-at`，可以关闭自动添加，需要自行获取UID在text中自行构造高亮文本，格式为
`[@名称|mtdaxiang://www.meituan.com/profile?uid=UID&isAt=true]`。`--custom-at`需配合`--at`使用，仅在text中添加高亮文本，未使用`--at`的消息无高亮提醒。

```bash
python3 $SKILL_DIR/scripts/send.py send \
  --group 69662141203 \
  --text "请处理一下这个问题[@苏灏|mtdaxiang://www.meituan.com/profile?uid=2967510770&isAt=true]" \
  --at suhao20:苏灏 \
  --custom-at
```
---

## 查询机器人所在群

```bash
python3 $SKILL_DIR/scripts/send.py list-groups
python3 $SKILL_DIR/scripts/send.py list-groups --json
```

---

## 参数说明

### send 子命令

#### 凭证参数

| 参数 | 环境变量 | 说明 |
|------|----------|------|
| `--client-id` | `DX_CLIENT_ID` | 应用 Client ID |
| `--client-secret` | `DX_CLIENT_SECRET` | 应用 Client Secret |
| `--config` | - | 配置文件路径，默认 ~/.daxiang.json |

#### 目标参数（二选一）

| 参数 | 说明 |
|------|------|
| `--to`, `-u` | 接收用户（mis 号或 uid），多个用逗号分隔 |
| `--group`, `-g` | 群组 ID (gid) |

#### 消息类型参数（互斥，必选其一）

| 参数 | 消息类型 | 说明 |
|------|---------|------|
| `--text` | text | 文本消息内容 |
| `--link` | link | 链接卡片模式（需配合 `--title` `--url` `--image`） |
| `--file-url` | file | 文件消息：文件地址（不能含中文和端口） |
| `--image-url` | image | 图片消息：原图地址 |
| `--vcard-uid` | vcard | 名片消息：用户 uid 或公众号 pubId |
| `--gvcard-gid` | gvcard | 群名片消息：群 ID |
| `--quote-msg-id` | quote | 引用回复：被引用的消息 ID |
| `--general-data` | general | 富文本消息：内容（明文 JSON 自动 Base64 编码） |
| `--custom-template` | custom | 模板消息：模板名称 |
| `--body-file` | 自定义 | 自定义消息体 JSON 文件（需配合 `--msg-type`） |

#### 消息修饰参数

| 参数 | 说明 |
|------|------|
| `--markdown` | 以 Markdown 渲染文本（`--text` 模式） |
| `--dynamic` | 发送动态消息（isDynamicMsg=true） |

#### link 消息参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--title` | ✅ | 链接标题 |
| `--url` | ✅ | 链接地址 |
| `--image` | ✅ | 封面图 URL（API 必填） |
| `--content` | ❌ | 链接描述 |

#### file 消息参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--file-name` | ✅ | 文件名 |
| `--file-size` | ❌ | 文件大小（字节） |
| `--file-format` | ❌ | MIME 类型，默认 `application/octet-stream` |
| `--file-id` | ❌ | 文件 ID，默认空字符串 |

#### image 消息参数

| 参数 | 说明 |
|------|------|
| `--image-thumbnail` | 缩略图地址（不传则与 `--image-url` 相同） |
| `--image-normal` | 大图地址（不传则与 `--image-url` 相同） |

#### vcard 消息参数

| 参数 | 说明 |
|------|------|
| `--vcard-type` | 名片类型：1=个人名片（默认），2=Pub 名片 |

#### quote 引用回复参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--reply-text` | ✅ | 回复的文本内容 |

#### general 富文本消息参数

| 参数 | 说明 |
|------|------|
| `--general-type` | 消息子类型：100=富文本（默认），11=旧卡片（已停止接入） |
| `--general-summary` | 消息摘要（可选） |

#### custom 模板消息参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--custom-title` | ✅ | 模板标题（contentTitle） |
| `--custom-content` | ✅ | 模板内容（最多展示约 10 行） |
| `--custom-link-name` | ❌ | 底部链接名称 |
| `--custom-link` | ❌ | 底部链接地址 |
| `--custom-clink-name` | ❌ | extension.custom.clink 详情链接名称 |
| `--custom-clink-url` | ❌ | extension.custom.clink 详情链接地址 |
| `--custom-button` | ❌ | 操作按钮，格式：`文字\|action_url[\|PRIMARY\|DANGER]`，可多次使用 |

#### @ 提及参数

| 参数 | 格式 | 说明 |
|------|------|------|
| `--at` | `id:显示名称` | @某人，id 为 mis 号或 uid（自动识别），可多次使用 |
| `--at-all` | 无 | @所有人，仅群消息有效 |
| `--bot-at` | `机器人id:显示名称` | @机器人，id 为机器人 pubid，可多次使用 |
| `--custom-at` | 无 | 配合--at使用，自定义高亮@文本位置|

#### 其他参数

| 参数 | 说明 |
|------|------|
| `--msg-type` | 消息类型，配合 `--body-file` 使用，默认 text |
| `--test` | 使用测试环境 |
| `--debug` | 打印调试信息 |

---

## 消息类型支持

| 类型 | 支持 | 发送方式 |
|------|------|---------|
| text | ✅ | `--text` |
| text + markdown | ✅ | `--text --markdown` |
| link（图文卡片） | ✅ | `--link`（image 必填） |
| multilink（多图文） | ✅ | `--body-file --msg-type multilink` |
| file（文件） | ✅ | `--file-url` |
| image（图片） | ✅ | `--image-url` |
| vcard（名片） | ✅ | `--vcard-uid` |
| gvcard（群名片） | ✅ | `--gvcard-gid` |
| quote（引用回复） | ✅ | `--quote-msg-id --reply-text` |
| custom（模板消息） | ✅ | `--custom-template`（支持按钮扩展） |
| general（富文本，type=100） | ✅ | `--general-data`（自动 Base64 编码） |
| audio（语音） | ❌ | 仅支持 amr 格式，实用性低，暂不支持 |
| gps（位置） | ❌ | 实用性低，暂不支持 |
| newemotion（表情V2） | ❌ | 实用性低，暂不支持 |

---

## @ 提及实现原理

大象 @ 提及需要同时满足两个条件：

1. `extension` 中设置 `at`（用户 uid 列表，Long 类型）或 `botAt`（机器人 id 列表，Long 类型）
2. `body.text` 中包含对应的高亮文本片段

| 场景 | body.text 中的格式 |
|------|-------------------|
| @某人 | `[@名称\|mtdaxiang://www.meituan.com/profile?uid=UID&isAt=true]` |
| @所有人 | `[@所有人\|mtdaxiang://www.meituan.com/profile?uid=-1&isAt=true]` |
| @机器人 | `[@名称\|mtdaxiang://www.meituan.com/pub/profile?pubid=BOTID&isAt=true]` |

---

## API 信息

- **生产环境**: `https://xopen.sankuai.com`
- **测试环境**: `https://xopen.xm.test.sankuai.com`
- **Token 端点（生产）**: `https://ssosv.sankuai.com/sson/auth/oidc/v1/token`
- **Token 端点（测试）**: `https://ssosv.it.test.sankuai.com/sson/auth/oidc/v1/token`

限流：建议 QPS < 5，批量发送 receiverIds 最多 100 人。

---

## 参考文档

- 大象消息 API: https://km.sankuai.com/collabpage/1357048485
- 消息 extension 说明（@人/@机器人）: https://km.sankuai.com/collabpage/1401295987
- 消息类型与消息体字段: https://km.sankuai.com/collabpage/2648372848
- 以用户身份发送消息: https://km.sankuai.com/collabpage/2269540204
- Token 鉴权: https://km.sankuai.com/collabpage/2712835886
- 企平应用开放平台: https://open.sankuai.com/developer/app/list
