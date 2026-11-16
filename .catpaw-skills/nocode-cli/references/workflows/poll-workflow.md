# create & send 命令 — Agent 实时进度推送详细流程

> send 的 poll 流程与 create 一致，差异：send 的 done 不含 `screenshotUrl`，send 完成后需用 `nocode screenshot` 补截图。

## Poll 循环示意图

```
用户 ──"帮我创建一个TODO应用"──→ NoCode Agent
  │
  ├─ exec(background=true): nocode create "TODO应用" → pid
  │
  ├─ [poll 第1轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":1,"message":"正在创建应用并发起 AI 生成..."}
  │   └─ 立即推送用户："⏳ 正在创建应用并发起 AI 生成..."
  │
  ├─ [poll 第2轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":2,"message":"AI 正在生成页面..."}
  │   ├─ 读到: {"type":"ai_text","delta":"好的，我来帮你..."}（忽略）
  │   └─ 立即推送用户："⏳ AI 正在生成页面..."
  │
  ├─ [poll 第3~N轮, timeout=15s]  ← AI 生成中，持续 poll
  │   └─ 读到 ai_text 事件（忽略，继续 poll）
  │
  ├─ [可能出现: question 事件]  ← NoCode Agent 提问，需要回答
  │   ├─ 读到: {"type":"question","eventId":"...","chatId":"...","conversationId":"...","title":"...","questions":[...],"answer_hint":{"command":"nocode answer ...","actions":[...]}}
  │   ├─ 展示 title + questions[].prompt + answer_hint.actions 给用户，等待用户选择
  │   ├─ 用户选择后执行: nocode answer <chatId> <eventId> <conversationId> + 对应 args
  │   └─ 继续 poll 原始命令输出（可能还有更多 question）
  │
  ├─ [poll 第N+1轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":3,"message":"等待渲染就绪..."}
  │   └─ 立即推送用户："⏳ 等待渲染就绪..."
  │
  ├─ [poll 第N+2轮, timeout=15s]
  │   ├─ 读到: {"type":"progress","step":4,"message":"正在截图预览..."}
  │   └─ 立即推送用户："⏳ 正在截图预览..."
  │
  └─ [poll 最后一轮]
      ├─ 读到: {"type":"done","status":"success","chatId":"abc-123","chatUrl":"https://...","screenshotUrl":"https://s3-xxx/..."}
      ├─ 立即推送用户："✅ 创建完成！"
      ├─ 立即推送用户："🔗 [abc-123](https://nocode.sankuai.com/...)"
      └─ 展示截图（如有 screenshotUrl，不展示 renderUrl）
```

## NDJSON 示例输出

每行一个 JSON：

```
{"type":"progress","step":1,"total":4,"message":"正在创建应用并发起 AI 生成..."}
{"type":"progress","step":2,"total":4,"message":"AI 正在生成页面..."}
{"type":"ai_text","delta":"好的，我来帮你创建一个 TODO 应用。\n\n"}
{"type":"ai_text","delta":"首先，我们需要..."}
{"type":"tool_call","toolName":"create_file"}
{"type":"question","eventId":"evt-001","chatId":"abc-123","conversationId":"conv-001","title":"SQL 执行确认","questions":[{"id":"sql_confirm_1","prompt":"即将执行以下 SQL：CREATE TABLE notes ...","input_type":"choice","options":[{"id":"确认执行","label":"确认执行"}],"allow_multiple":false,"tags":["sql_execute_confirm"]}],"answer_hint":{"command":"nocode answer abc-123 evt-001 conv-001","actions":[{"label":"确认执行","args":"--text '确认执行'"},{"label":"取消执行","args":"--cancel"}]}}
{"type":"progress","step":3,"total":4,"message":"等待渲染就绪..."}
{"type":"progress","step":3,"total":4,"message":"渲染就绪","data":{"renderUrl":"https://sandbox-xxx.sankuai.com/..."}}
{"type":"progress","step":4,"total":4,"message":"正在截图预览..."}
{"type":"done","status":"success","chatId":"abc-123","chatUrl":"https://...","renderUrl":"https://...","screenshotUrl":"https://s3-xxx/abc-123.png","aiResponse":"完整AI响应文本...","totalDuration":48000}
```

> ⚠️ 以上为 **create** 命令的 done 事件示例。**send** 命令的 done 事件不含 `screenshotUrl`，需用 `nocode screenshot` 补截图。
