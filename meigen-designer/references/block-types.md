# RenderBlock 输出结构说明

V3 设计师 agent 的轮询结果由 `RenderBlock` 组成，`poll.py` 以 JSON Lines 格式输出，每行一个 JSON 对象，通过 `type` 字段区分。

> 源码定义：`infra-solution-design-gateway/.../dialogue3/domain/model/content/RenderBlock.java`
> 前端渲染：`infra-ai-design-platform-web/.../creativeAssistant/v3/components/chat/answerCard.vue`

---

## Block 处理分类

| 分类 | Block Type | 处理方式 |
|------|-----------|---------|
| **保留处理** | Text | 输出文本内容 |
| **保留处理** | ImageList | 遍历 content[] 输出每张图片 |
| **保留处理** | Video | 输出视频；RUNNING+空url 指示后台轮询 |
| **保留处理** | TextQuestion | 展示追问标题+选项文本 |
| **保留处理** | ImageQuestion | 展示图片选项标题+URL |
| **处理** | Image | ImageList 子块提取 url/status；独立出现时同样处理 |
| **丢弃** | Card | 子 block 独立出现，直接跳过 |
| **丢弃** | Tool | V3 永远不产出，防御性跳过 |
| **丢弃** | ArticleList / ArticleItem | 搜索参考是 agent 中间过程，跳过 |
| **V4 不处理** | TextQuestionInput / TextQuestionUrl | V4 专用 |

---

## 流程控制信号（非 block）

### message_start

```json
{ "type": "message_start", "_action": "display", "messageId": 790, "role": "assistant" }
```

含义：新 assistant 消息开始。记录 messageId。

### message_status

```json
{ "type": "message_status", "_action": "notify_done", "messageId": 790, "status": 1, "statusText": "DONE" }
```

| status | statusText | 含义 |
|--------|-----------|------|
| 1 | DONE | 完成 |
| 2 | ABORTED | 已中止 |
| 3 | FAILED | 失败 |

收到终态 status 后，流程结束。

### queue

```json
{ "type": "queue", "_action": "notify_queue", "messageId": 790, "position": 3 }
```

含义：消息正在排队。告知用户排队位置。

---

## 保留处理的 Block 类型

### 1. Text — 文本内容

```json
{ "type": "Text", "_action": "display", "messageId": 790, "content": "正在为您设计...", "html": "" }
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 纯文本内容（设计师思考、回复、错误信息） |
| html | string | HTML 富文本（可选，通常为空） |

**处理方式**：将 `content` 文本直接发送给用户。用于展示设计师思考过程、回复内容、错误提示等。

---

### 2. ImageList — 多张图片（核心输出）

```json
{
  "type": "ImageList",
  "_action": "show_images",
  "messageId": 790,
  "title": "生成结果",
  "content": [
    { "type": "Image", "url": "https://...", "status": "FINISH", "prompt": "...", "model": "..." },
    { "type": "Image", "url": "https://...", "status": "FINISH", "prompt": "...", "model": "..." }
  ],
  "status": "FINISH"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| title | string | 列表标题 |
| content | Image[] | 图片列表（每项为 Image 子块） |
| status | string | 整体状态：RUNNING / FINISH / FAILED |

**Image 子块结构**：

| 字段 | 类型 | 说明 |
|------|------|------|
| url | string | 图片 URL（FINISH 时非空） |
| status | string | RUNNING / FINISH / FAILED / AUDIT_FAILED |
| prompt | string | 生成提示词 |
| model | string | 模型名 |

**处理方式**：
1. 遍历 `content[]` 中的每个 Image 子块
2. 对 `status=FINISH` 且 `url` 非空的图片，发送完整 URL（禁止截断，是否用 markdown 由宿主 agent 按自身渲染环境决定）
3. 对 `status=RUNNING` 的图片，可提示"图片生成中"
4. 对 `status=FAILED` 或 `AUDIT_FAILED` 的图片，提示生成失败

**block 更新**：当 ImageList 的 `status` 从 RUNNING 变为 FINISH 时，poll.py 会重新输出该 block 完整内容（附带 `blockIndex`），`_action` 保持 `show_images`，据此发送图片 URL 给用户。

---

### 3. Video — 视频

#### 视频生成中（RUNNING，url 为空）

```json
{
  "type": "Video",
  "_action": "wait_video",
  "messageId": 790,
  "url": "",
  "status": "RUNNING",
  "taskId": "abc123",
  "prompt": "...",
  "model": "..."
}
```

#### 视频已完成（FINISH，url 非空）

```json
{
  "type": "Video",
  "_action": "show_video",
  "messageId": 790,
  "blockIndex": 0,
  "url": "https://...",
  "status": "FINISH",
  "taskId": "abc123",
  "preview": "https://...",
  "duration": 5000,
  "ratio": "16:9",
  "resolution": "720p"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| url | string | 空=生成中，非空=完成 |
| status | string | RUNNING / FINISH / FAILED |
| taskId | string | 异步视频任务 ID |
| preview | string | 预览图 URL |
| duration | int | 时长（毫秒） |
| ratio | string | 宽高比如 "16:9" |
| resolution | string | 分辨率如 "720p" |
| blockIndex | int | 仅在 block 更新时附带，标识哪个 block 更新了 |

**处理方式**：
1. `status=RUNNING` 且 `url` 为空 → 告知用户"视频正在生成，可能需要数分钟"，在**后台**继续运行 poll.py
2. `status=FINISH` 且 `url` 非空 → 发送完整视频 URL（禁止截断），通知"视频已生成"
3. `status=FAILED` → 通知用户视频生成失败

**异步状态说明**：Video block 的 status 与 message status 由不同 Mafka 链路异步更新。典型时序：message.status=DONE 时 Video block 可能仍 RUNNING。poll.py 会继续轮询直到 Video 也终态。

**block 更新**：Video block 从 RUNNING 变为 FINISH 时，poll.py 重新输出该 block 完整内容（附带 `blockIndex`）作为新增输出，`_action` 保持 `show_video`，据此发送视频 URL 给用户，**不替换**之前的"视频生成中"消息。

---

### 4. TextQuestion — 文字追问

```json
{
  "type": "TextQuestion",
  "_action": "ask_user",
  "messageId": 790,
  "title": "请选择风格",
  "content": [
    { "type": "TextQuestionListItem", "index": 0, "title": "A. 赛博朋克", "prompt": "cyberpunk" },
    { "type": "TextQuestionListItem", "index": 1, "title": "B. 水墨风", "prompt": "ink" }
  ],
  "status": "PENDING"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| title | string | 问题标题 |
| content | TextQuestionListItem[] | 选项列表（已从 TextQuestionList 展平） |
| status | string | PENDING / SELECTED / DISMISSED |

**TextQuestionListItem 子块**：

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 选项序号 |
| title | string | 选项标题（**已自带 A/B/C 编号**，直接透传） |
| prompt | string | 选项对应的 prompt |

**处理方式**：
1. 仅在 `status=PENDING` 时展示追问
2. 将 `title` 和 `content[]` 中的选项文本直接透传给用户（选项已自带编号，无需添加）
3. 用户回复后，统一通过 `generate.py` send 提交（**不调用 replyQuestion**）

---

### 5. ImageQuestion — 图片追问

```json
{
  "type": "ImageQuestion",
  "_action": "ask_user",
  "messageId": 790,
  "content": [
    { "type": "ImageQuestionGridItem", "index": 0, "url": "https://...", "prompt": "..." },
    { "type": "ImageQuestionGridItem", "index": 1, "url": "https://...", "prompt": "..." }
  ],
  "status": "PENDING"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| content | ImageQuestionGridItem[] | 图片选项列表（已从 ImageQuestionGrid 展平） |
| status | string | PENDING / SELECTED / DISMISSED |

**ImageQuestionGridItem 子块**：

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 选项序号 |
| url | string | 选项图片 URL |
| prompt | string | 选项描述 |

**处理方式**：
1. 仅在 `status=PENDING` 时展示追问
2. 将每个选项以"编号 + 图片 URL"形式展示给用户
3. 用户回复后，统一通过 `generate.py` send 提交

---

### 6. Image — 单张图片

```json
{ "type": "Image", "_action": "show_images", "messageId": 790, "url": "https://...", "status": "FINISH", "prompt": "...", "model": "...", "size": "2048x2048" }
```

| 字段 | 类型 | 说明 |
|------|------|------|
| url | string | 图片 URL |
| status | string | RUNNING / FINISH / FAILED |
| size | string | 尺寸如 "2048x2048" |

**处理方式**：Image 通常作为 ImageList 的子块出现，遍历 ImageList 时直接提取 `url`/`status`。如果独立出现（顶层 content.blocks 中），同样发送完整 URL（禁止截断）。

---

## 丢弃的 Block 类型

### Card — 卡片容器

```json
{ "type": "Card", "messageId": 790, "title": "...", "blocks": [...], "status": "FINISH" }
```

**丢弃原因**：Card 是 Web 端的 UI 容器，其子 block（Text/ImageList/Video）会独立出现在 content.blocks 中，skill 直接丢弃 Card 不丢失信息。

### Tool — 工具调用

```json
{ "type": "Tool", "messageId": 790, "content": "搜索中..." }
```

**丢弃原因**：V3 AgentEventType 无 TOOL 事件，V3 通道永远不产出 Tool block。防御性跳过。

### ArticleList / ArticleItem — 搜索结果

```json
{ "type": "ArticleList", "messageId": 790, "title": "搜索结果", "content": "摘要...", "articles": [...], "status": "FINISH" }
```

**丢弃原因**：搜索参考是 agent 的中间过程信息，skill 场景下用户关注的是生成结果（图片/视频），搜索摘要不直接有用。

---

## 品牌水印字段（watermark）

品牌水印不单独输出事件，作为 `watermark` 字段附在生图 `notify_done` JSON Line 里（任务成功且有图片产出时）。视频场景已由 `wait_video` 引导前往 web 端，不输出水印。

```json
{ "type": "message_status", "_action": "notify_done", "messageId": 790, "status": 1, "statusText": "DONE", "watermark": "🎨 本图由 美境AI设计师 | [前往美境](https://aidesign.meituan.com/creativeAssistant/790)(https://aidesign.meituan.com/creativeAssistant/790)" }
```

| 字段 | 类型 | 说明 |
|------|------|------|
| watermark | string | 固定文案 `🎨 本图由 美境AI设计师 \| [前往美境](<web_url>)(<web_url>)`，web_url 为 `https://aidesign.meituan.com/creativeAssistant/<sessionId>` |

**处理方式**：宿主 agent 收到含 `watermark` 字段的 `notify_done` 时，将文案**直接原样发送给用户**，不可省略或吞掉。纯文本对话（无图片产出）不带此字段。

---

## BlockStatus 枚举

实现 `StatusAwareBlock` 的 block 使用：

| 值 | 含义 |
|----|------|
| RUNNING | 生成中 |
| FINISH | 完成 |
| FAILED | 失败 |
| STOPPED | 已停止（用户中止） |
| AUDIT_FAILED | 审核未通过 |

## QuestionStatus 枚举

追问 block 使用：

| 值 | 含义 |
|----|------|
| PENDING | 待回答 |
| SELECTED | 已选择 |
| DISMISSED | 已忽略 |
