---
name: meigen-designer
description: 美境 AI 设计师。凡是涉及视觉创作的需求，优先使用此 skill，包括但不限于：文生图、图生图、图片编辑、海报设计、Banner 制作、IP 形象设计（美团袋鼠/小象等）、LOGO 设计、ICON 设计、插画、表情包、包装设计、VI 设计、文创礼品、套图生成、文生视频、图生视频等。用户说"帮我画""生成一张""做个海报""设计个 logo""给图片加效果""让图动起来"等，都应使用此 skill。

metadata:
  skillhub.creator: "zhuxiangyu04"
  skillhub.updater: "chenshengtao"
  skillhub.version: "V19"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "5315"
  skillhub.high_sensitive: "false"
---

# 美境 - AI 设计师（V3）

美境是一个 AI 设计平台，支持文生图、图生图、图片编辑、IP 设计、视频生成等全链路视觉创作能力。

## 文件存储

- `~/.meigen-cli/meigen-designer/session_id` — 会话 ID（服务端返回，跨调用持久化，用于上下文关联）

目录不存在时自动创建。与 meigen-cli 的 `~/.meigen-cli/token/` 同级。

---

## 环境准备

**在执行任何操作前，按顺序完成以下准备：**

### 1. 检查 meigen-cli

执行 `meigen --version`，确认版本号 **>= 1.4.9**。

- **未安装**（命令不存在）：询问用户是否安装 meigen-cli，用户同意后执行 `npm install -g @meigen/meigen-cli@latest --registry=http://r.npm.sankuai.com`
- **版本过低**：执行 `npm install -g @meigen/meigen-cli@latest --registry=http://r.npm.sankuai.com`升级版本

### 2. 同步 Skill 版本

先获取 `<dirname>`——即存放各个 skill 子目录的那个**上级目录**：

```bash
DIRNAME="$(cd "$(dirname "<this-skill-md>")/.." && pwd)"
```

然后执行同步：

```bash
meigen sync "$DIRNAME" meigen-designer
```

状态信息输出到 **stderr**，根据**退出码**判断结果：退出码 0 = 成功，1 = 同步失败，2 = 前置检查失败。

| 退出码 | stderr 关键词 | 含义 | 后续动作 |
|-------|-------------|------|---------|
| 0 | `已是最新` | 本地已是最新版本 | 继续下一步 |
| 0 | `已更新` | 已自动更新到最新版本 | 继续下一步 |
| 0 | `已安装` | skill 首次注册安装成功 | 继续下一步 |
| 2 | `未检测到 mtskills` | 缺少 mtskills 依赖 | 询问用户是否安装：`npm install -g @mtfe/mtskills --registry=http://r.npm.sankuai.com`，用户同意后执行安装，再**重新执行** `meigen sync` |
| 1 | `失败` / `更新失败` | 同步异常 | 告知用户错误信息，跳过同步继续后续步骤 |

### 3. 确认脚本目录

```bash
SCRIPT_DIR="$(cd "$(dirname "<this-skill-md>")" && pwd)/scripts"
```
---

## 工作流程

生成流程分为两步，第一步为提交任务，第二步为轮询结果，不可遗漏。

提醒用户"首次生图可能需要登录认证授权，请留意大象消息"后，执行以下步骤

### STEP 1. 提交任务

⚠️ **调用范式（强制）**：`generate.py` 以 **JSON Lines** 输出到 stdout（与 poll.py 协议统一），stderr 仅供人类排查。**必须流式执行**——直接运行脚本，**不要**用 `$()` 捕获（`$()` 会缓冲到结束才返回，进度无法实时透传）。逐行读 stdout，每行解析为 JSON，按 `_action` 字段分发：

```bash
# 流式执行，stdout 逐行实时返回。每行一个 JSON，按 _action 分发处理。
python3 "$SCRIPT_DIR/generate.py" "<组装后的prompt>" 2>&1
```

- **禁止**用 `RESULT=$(...)`：`$()` 缓冲到脚本退出，`_action=display` 的进度无法实时透传给用户，失去 JSON Lines 的实时性。
- **禁止**用 `... && echo`：失败时（退出码 1）`&&` 短路，后续命令不执行。
- stdout 每行都是合法 JSON，逐行 `json.loads`，按 `_action` 分发（见下）。

`generate.py` 只接收**组装好的 prompt 字符串**——宿主 agent 负责检测用户描述中的 URL/本地路径并原位替换占位符，防止位置丢失。保持用户原始输入的结构和语序不变，仅做以下替换：

#### Prompt 组装规则

1. **图片/视频 URL**：在原位替换为 `[@image:#N]` 或 `[@video:#N]` 占位符，末尾追加引用行 `For Image #N: URL: xxx`
2. **文件 URL**（pdf/word/excel）：从 prompt 中移除，通过 `--file` 参数传入
3. **本地文件路径**：先上传获取远程 URL，再按类型走规则 1 或 2

#### 本地文件上传

用户描述中引用本地路径（如 `/path/to/file.png`、`~/Downloads/demo.mp4`）时，先上传：

```bash
python3 "$SCRIPT_DIR/upload-to-s3.py" <本地文件路径> 2>&1
```

stdout 输出远程 URL（失败 exit 非 0，停止并告知用户）。URL 有效期 24 小时。获取后按类型：图片/视频 → 规则 1（占位符 + 引用行），文档 → 规则 2（`--file`）。外部图片 URL（非 meituan 域名）需先下载到本地再上传转存。

#### 示例

用户：`~/Downloads/ref.png 参考这张图，帮我画一个海报`
1. 上传 `~/Downloads/ref.png` → `https://cdn.example.com/ref.png`
2. 图片类型 → 占位符替换

组装后 prompt：
```
[@image:#1] 参考这张图，帮我画一个海报
For Image #1: URL: https://cdn.example.com/ref.png
```

用户：`https://a.com/1.mp4 这个视频讲了什么？https://b.com/2.mp4 这个呢？`
组装后 prompt：
```
[@video:#1] 这个视频讲了什么？[@video:#2] 这个呢？
For Video #1: URL: https://a.com/1.mp4
For Video #2: URL: https://b.com/2.mp4
```

用户：`~/docs/spec.pdf 根据这个文档画流程图`
1. 上传 `~/docs/spec.pdf` → `https://cdn.example.com/spec.pdf`
2. 文档 → `--file` 参数，prompt 中移除文档路径

组装后 prompt：`根据这个文档画流程图`，并附带 `--file https://cdn.example.com/spec.pdf`

#### 调用

```bash
python3 "$SCRIPT_DIR/generate.py" "<组装后的prompt>" [--file <url>]... [--model <name>] [--config <json>] 2>&1
```

**提示词原则**：保留用户原始描述，不擅自改写、润色或添加描述。美境设计师本身会做 prompt 优化。
- 必须保留任务类型词（"图片""视频""海报""logo"等），决定走生图还是视频流程。
- 尺寸/比例描述（"1080x1920""16:9""竖版""4K"）原样保留，不得概括或省略。
- **禁止改写用户原文**——仅在 URL/本地路径出现处做占位符替换，其余文字不动。

参数说明：
- `<组装后的prompt>`：agent 按上述规则组装后的字符串
- mis_id 与 access_token 由脚本内部 `meigen status --json` 获取
- `--file <url>`：文件 URL（pdf/excel/word，可多次指定）
- `--model <name>`：指定模型（映射到 config.fastModel）。**仅当需要指定模型才传此参数**，不填时美境设计师自动指定最优模型。支持：
   - 生图：`gpt-image-2`、`gpt-image-1.5`、`gemini-3.1-flash-image-preview`（nano banana2）、`gemini-3-pro-image-preview`（nano banana pro）、`meituan-ip`（美团IP）
   - 视频：`doubao-seedance-2.0`
- `--config <json>`：额外配置，如 `--config '{"openSearch": true}'`

> 视频参考输入（参考视频 URL）走 prompt 占位符 `[@video:#N]`；视频**生成**任务的轮询用 poll.py 的 `--video` 标志（见 STEP 2），两者不同。

#### generate.py 输出格式

脚本以 **JSON Lines** 格式输出到 stdout，每行一个 JSON 对象，按 `_action` 字段分发（与 poll.py 同一套解析逻辑）。stderr 仅供人类排查，不作为 agent 信息源。

| `_action` | 含义 | 处理方式 |
|-----------|------|----------|
| `display` | 进度信息（创建会话/上传文件/发送任务等） | 将 content 字段实时透传给用户 |
| `submitted` | 提交成功（**终态信号**） | 从该行取 `sessionId`/`userMessageId`/`assistantMessageId`，进入第二步轮询。**收到后停止读取 stdout** |
| `failed` | 失败（**终态信号**，退出码 1） | 读 `msg` 提示用户并按错误处理章节处置。**收到后停止读取 stdout** |

典型输出时序（逐行到达）：
```
{"type":"progress","_action":"display","content":"🆕 创建新会话..."}
{"type":"progress","_action":"display","content":"✅ 会话已创建: 123456"}
{"type":"progress","_action":"display","content":"🚀 发送任务给设计师..."}
{"type":"progress","_action":"display","content":"📨 消息已发送 (userMessageId=789, assistantMessageId=790)"}
{"type":"submit_result","_action":"submitted","sessionId":123456,"userMessageId":789,"assistantMessageId":790,"status":"submitted"}
```

收到 `_action=submitted` 后，必须将 `userMessageId` 和 `assistantMessageId` 告知用户（如"任务已提交，消息ID: user=789, assistant=790"），便于用户报告问题时定位问题。

### STEP 2. 轮询结果

```bash
python3 "$SCRIPT_DIR/poll.py" <sessionId> <assistantMessageId> [--video] 2>&1
```

- 生图/对话场景：不加 `--video`，超时 10 分钟，轮询到 message 终态退出
- 视频场景：加 `--video`，超时同为 10 分钟，**检测到 Video RUNNING 即终态退出**——poll.py 输出含 web 链接的 `wait_video` 后即退出，**不轮询视频生成结果**（视频耗时长，由用户去 web 端自查）

#### poll.py 输出格式

脚本以 **JSON Lines** 格式输出到 stdout，每行一个 JSON 对象，按 `_action` 分发（与 generate.py 同一套协议）。进度信息（等待创作/Token 重新认证等）也以 `_action=display` 的 JSON Line 输出，stderr 不再有进度日志。

**解析规则**：逐行读取 stdout，每行解析为 JSON，根据 `_action` 字段处理（`_action` 提供语义化处理提示，无需自行理解 block 结构）。各 type 的完整 JSON 结构和字段说明见 [references/block-types.md](references/block-types.md)。

⚠️ **URL 完整性约束（强制）**：输出给用户的任何 URL（图片 URL、视频 web 链接、水印文案中的 URL 等）**必须原样完整输出**——禁止丢弃 query 部分、用 `...` 省略中间段、重新编码转义、补全协议。默认输出纯文本 URL，不使用 markdown 语法（多数终端/聊天环境不渲染）。

#### `_action` 语义化标注

每个 JSON Line 包含 `_action` 字段，指示宿主 agent 应如何处理：

| `_action` | 含义 | 处理方式 |
|-----------|------|----------|
| `display` | 文本内容或进度信息（等待创作/Token 重新认证等） | 将 content 字段直接发送给用户 |
| `show_images` | 图片结果 | 逐张发送完整 URL（禁止截断），默认输出纯文本 URL，不使用 markdown 语法。仅当确认当前环境支持 markdown 渲染时才可使用 |
| `wait_video` | 视频开始生成（**视频场景终态信号**，含 web 链接 url） | 告知用户"视频生成耗时较长，请前往 web 端查看：[url]"。**此为终态信号，poll.py 随即退出，停止读取 stdout**——不等待视频生成结果 |
| `ask_user` | 追问选项 | 展示标题和选项，等待用户回复 |
| `notify_queue` | 排队中 | 告知用户排队位置 |
| `notify_done` | 任务完成 | 通知用户。若含 `watermark` 字段，原样发送给用户。**此为终态信号，poll.py 随即退出，停止读取 stdout** |
| `notify_failed` | 任务失败 | 通知用户。**终态信号，poll.py 随即退出** |
| `notify_timeout` | 轮询超时 | 通知用户，建议重试。**终态信号，poll.py 随即退出** |

#### 丢弃的 Block 类型（直接忽略，不处理）

| type | 丢弃原因 |
|------|---------|
| `Card` | 子 block 会独立输出，无需渲染容器 |
| `Tool` | V3 通道永远不产出 |
| `ArticleList` | 搜索参考是 agent 中间过程 |

**block 更新机制**（仅生图场景）：已输出过的 block 如果后续字段变化（如 ImageList status RUNNING→FINISH），poll.py 会重新输出该 block 的完整内容作为新增输出，附带 `blockIndex` 标识哪个 block 更新了，`_action` 为 `update`。应当据此组织新消息告知用户（如"图片已生成"），不替换之前已展示的旧消息。视频场景不适用：视频检测到 Video RUNNING 即终态退出，不追踪 Video 后续状态变化。

---

## 追问交互

设计师 agent 可能追问用户（选择风格、确认方案等）。追问通过 `TextQuestion` 和 `ImageQuestion` 类型的 JSON Line 输出。

### 处理流程

1. **识别追问**：stdout 输出 `type=TextQuestion` 或 `type=ImageQuestion`
2. **展示选项**：将选项通过 `message` 发送给用户
   - 文字追问：展示选项列表（选项已自带 A/B/C 编号，直接透传）
   - 图片追问：展示图片选项（编号 + 图片 URL）
3. **等待回复**：用户回复后，统一通过 send 接口提交
4. **继续轮询**：回复后继续轮询获取后续结果

### 回复追问

用户回复追问时，统一通过 generate.py send 提交（不调用 replyQuestion）：

```bash
# 流式执行，逐行按 _action 分发。_action=submitted 行取新的 assistantMessageId
python3 "$SCRIPT_DIR/generate.py" "<用户回复>" 2>&1
python3 "$SCRIPT_DIR/poll.py" <sessionId> <newAssistantMessageId> 2>&1
```

> 由于 sessionId 持久化，在同一会话中 send 用户回复即可，设计师 agent 会理解上下文。无论用户是回答追问还是发起新请求，都走同一个 generate.py + poll.py 流程。

---

## 视频生成

视频生成通常需要 10-20 分钟，远超 skill 同步轮询窗口。因此 skill 在检测到视频**开始生成**时即输出 web 端链接，让用户自行前往查看结果，**不在 skill 内等待视频完成、不轮询视频生成结果**。

### 视频任务处理流程

当用户请求"让图动起来"等视频生成任务时，与生图调用方式**完全一致**，仅多传 `--video` 标志：

```bash
python3 "$SCRIPT_DIR/poll.py" "$SESSION_ID" "$ASSISTANT_MESSAGE_ID" --video 2>&1
```

逐行解析 stdout JSON Lines，按 `_action` 实时展示给用户。视频场景的典型输出时序：

1. **初始阶段**：Text 思考、追问等中间内容（`display`/`ask_user`），与生图一致
2. **视频开始生成（终态）**：poll.py 检测到 Video block status=RUNNING，输出 `wait_video` JSON Line（**含 web 链接 url**）：
   ```json
   {"type": "Video", "_action": "wait_video", "messageId": 790, "blockIndex": 0, "url": "https://aidesign.meituan.com/creativeAssistant/<sessionId>", "status": "RUNNING", "taskId": "abc123", ...}
   ```
   宿主 agent 告知用户："视频生成耗时较长（约 10-20 分钟），请前往 web 端查看结果：[url]"。**此为视频场景终态信号——收到后停止读取 stdout，结束本轮任务，不等待视频生成结果**。poll.py 执行 report 上报后退出。
3. **失败**：若视频任务在检测到 Video RUNNING 前就失败，收到 `notify_failed`，告知用户，poll.py 退出
4. **超时**：若较长时间未出现 Video RUNNING block，超过 10 分钟收到 `notify_timeout`，告知用户超时

---

## 会话管理

### 新对话/重置会话

用户说「新对话」「重置会话」「清除上下文」时：删除 `~/.meigen-cli/meigen-designer/session_id` 文件。

```bash
rm -f ~/.meigen-cli/meigen-designer/session_id
```

下次调用 `generate.py` 时会自动创建新会话。

⚠️ **禁止擅自重置会话**：除非用户明确说「新对话」「重置会话」「清除上下文」，否则**绝对不要**删除或修改 session_id 文件。话题变化、换一种生成内容、开始新任务等都不是重置会话的理由。同一会话支持任意次数、任意主题的生成请求。擅自重置会话会导致上下文丢失、进行中的任务中断。

### 取消任务

用户说「取消」「停止」「不要了」或类似表述时：通过 `generate.py --abort` 调用 `/message/abort` 接口。

```bash
SESSION_ID=$(cat ~/.meigen-cli/meigen-designer/session_id 2>/dev/null)
python3 "$SCRIPT_DIR/generate.py" --abort "$SESSION_ID" 2>&1
```

执行后告知用户"已发送取消请求"。

### 超时

轮询超过时限自动终止：生图/对话场景与视频场景均 10 分钟（视频检测到 Video RUNNING 即终态退出，通常远小于 10 分钟）。输出超时错误信息。

---

## 错误处理

脚本自身错误（认证失败/网络异常/接口业务码等）统一以退出码 1 退出，stdout 输出 JSON Line `{"status": "failed", "_action": "failed", "msg": "<错误原因>"}`。宿主 agent 收到 `_action=failed` 后停止读取 stdout，读 `msg` 提示用户并处置。

**认证机制**：
脚本执行过程中会尝试获取调用接口所需token，认证失败时 `msg` 信息中会有相关提示

**poll.py 的两种「失败」区分**：
- **任务终态失败**（退出码 0）：任务 FAILED/ABORTED/TIMEOUT，通过 `notify_failed`/`notify_timeout` JSON Line 标识，宿主按 `_action` 处理后停止读取。这是正常业务终态，非脚本异常。
- **脚本自身错误**（退出码 1）：输出 `_action=failed` JSON Line，读 `msg` 处理。

**升级指令处理**：若 `msg` 提示 skill 版本不可用问题且告诉了升级指令，按照升级指令执行；若仅提示需升级但未给指令，回退执行 `meigen sync "$DIRNAME" meigen-designer`。升级完成后重新发起原任务。

---

## 重置认证

用户说「重置美境认证」「重新登录」「清除认证」时：

```bash
meigen logout
```

告知用户已重置。如用户同时有生图请求，重新认证后继续执行。

---

## 自动上报

每次生图完成（无论成功或失败）后，`poll.py` 会在后台自动调用 `meigen report` 上报使用数据，无需手动操作。

---

## 品牌水印

品牌水印描述会作为 `watermark` 字段附在生图 `notify_done` JSON Line 里，**必须与生成结果一起输出**
