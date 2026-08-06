# MCM AI 命令完整参考

## 全局选项

| 选项 | 说明 |
|------|------|
| `--version` | 显示版本号 |
| `--help` | 显示帮助信息 |

---

## 快速速查表

### 流式问答（主要命令）
```bash
mcm ai "<question>" [options]
```
- 实时流式输出 AI 回复
- 支持多轮对话（自动保持 sessionId）
- 最常用的命令方式

**选项**:
- `-s, --session-id <id>` - 指定会话 ID（可选，自动创建）
- `-p, --plan-id <id>` - 指定变更计划 ID（可选）
- `-b, --git-base-branch <branch>` - Git 基础分支（可选，默认 main）
- `--byAgent <id>` - 标识触发来源的 Agent（常见值：`CatClaw`、`CatDesk`、`CatPaw`）
- `--debug` - 打印服务端原始 SSE 数据（**仅故障排查时使用**，正常情况无需开启）

**示例**:
```bash
# 基础用法
mcm ai "创建变更计划，部署订单服务"

# 带计划 ID
mcm ai "执行计划第 1 步" --plan-id 12345

# 指定会话，继续之前的对话
mcm ai "接下来呢？" -s 027755fc-fbe6-4524-9280-c41dfa62fed9

# 以 Agent 身份调用（--byAgent 在 <question> 之后）
mcm ai "创建变更计划" --byAgent CatClaw
mcm ai "执行计划第 1 步" --byAgent CatDesk
```

---

### 同步问答
```bash
mcm ai sync "<question>" [options]
```
- 等待完整 JSON 结果返回（不流式）
- 用于脚本集成和需要结构化数据的场景
- 选项同流式问答

---

### 查询活跃会话
```bash
mcm ai sessions [--format <format>]
```
- 查询所有 24 小时内的活跃会话
- 用于了解现有会话并选择要继续的会话 ID

**选项**:
- `--format <format>` - 输出格式：`table`（默认，表格格式）或 `json`（JSON 格式，便于脚本处理）

**示例**:
```bash
# 表格形式（默认，可读性强）
mcm ai sessions

# JSON 形式（便于脚本处理）
mcm ai sessions --format json

# 管道处理示例
mcm ai sessions --format json | jq '.[] | select(.planId == "12345")'

# 输出示例（表格形式）:
# ┌─────────────────────────────────────┬─────────┬─────────────────────────┬────────────────────────┐
# │ 会话 ID                             │ 计划 ID │ 首次提问                │ 创建时间               │
# ├─────────────────────────────────────┼─────────┼─────────────────────────┼────────────────────────┤
# │ 027755fc-fbe6-4524-9280-c41dfa62fed9 │ 12345   │ 创建变更计划            │ 2026-05-19 14:30:00    │
# │ 827755fc-fbe6-4524-9280-c41dfa62fed0 │ 12346   │ 查询计划进度            │ 2026-05-19 13:15:00    │
# └─────────────────────────────────────┴─────────┴─────────────────────────┴────────────────────────┘
```

---

## 会话管理命令

### 停止会话
```bash
mcm ai stop <sessionId>
```
- 立即中止 AI 推理
- 场景：对话出错需要中止、释放资源

**示例**:
```bash
mcm ai stop 027755fc-fbe6-4524-9280-c41dfa62fed9
```

### 重连会话
```bash
mcm ai reconnect <sessionId>
```
- 重连**当前轮次**的 SSE 连接，回放本轮历史消息
- 仅用于本轮推理过程中发生网络中断的场景
- ⚠️ 若本轮 AI 已正常回复结束，调用后会返回空内容，这是正常行为，不代表会话失效
- sessionId 在本轮结束后依然有效，可继续用于下一轮对话：`mcm ai "继续" -s <sessionId>`

**选项**:
- `--debug` - 打印服务端原始 SSE 数据（**仅故障排查时使用**，正常情况无需开启）

**示例**:
```bash
# 推理过程中网络断了，重新连接回放本轮历史
mcm ai reconnect 027755fc-fbe6-4524-9280-c41dfa62fed9
# 自动输出：
# [历史] 用户问题 1
# [历史] AI 回复 1
# [新内容] 继续推理...

# 本轮结束后继续多轮对话
mcm ai "下一步怎么做？" -s 027755fc-fbe6-4524-9280-c41dfa62fed9
```

---

## 交互问答命令

### 提交回答
```bash
mcm ai answer <sessionId> -e <eventId> -r '<json>'
```
- 提交用户对 AI 问题的回答
- `<sessionId>` - 会话 ID
- `-e, --event-id <eventId>` - 事件 ID（来自 AI 的 ask_question 事件，必填）
- `-r, --result <json>` - 回答内容（有效的 JSON 字符串，必填）

**典型流程**:
1. AI 发出 ask_question 事件，包含 eventId
2. 用户通过此命令提交回答
3. 使用 `mcm ai resume` 继续执行

**示例**:
```bash
# 响应 AI 的问题（有选项时 content 填选项的 id，无选项时填自定义文本）
mcm ai answer 027755fc-fbe6-4524-9280-c41dfa62fed9 -e evt_abc123 \
  -r '{"answers":[{"id":"source_info","content":"feature"}]}'

# 多个问题同时回答
mcm ai answer 027755fc-fbe6-4524-9280-c41dfa62fed9 -e evt_abc123 \
  -r '{"answers":[{"id":"change_desc","content":"feature"},{"id":"deploy_time","content":"19"}]}'

# 输出：
# ✓ 回答已提交
# {...response...}
```

### 恢复执行
```bash
mcm ai resume <sessionId>
```
- 所有交互问题回答完成后，恢复 Agent 执行
- 必须在所有 `ask_question` 事件都通过 `answer` 回答后调用

**示例**:
```bash
# 所有问题回答完成后，继续
mcm ai resume 027755fc-fbe6-4524-9280-c41dfa62fed9
# 输出：
# ✓ Agent 已恢复执行
```

---

## 完整交互示例

### 场景：创建变更计划（需要用户交互）

```bash
# 第 1 步：发起对话（会自动保存 sessionId）
mcm ai "创建变更计划，部署新的支付服务"
# 输出示例：
# 🤖 MCM AI 助手
# 了解。为了制定更合理的计划，我需要了解几个信息...
# 📋 Ask Question Event: evt_001
#    计划类型是什么？

# 第 2 步：查看当前会话 ID
sessionId=$(mcm ai sessions --format json | jq -r '.[0].sessionId')

# 第 3 步：提交第一个回答
mcm ai answer $sessionId -e evt_001 \
  -r '{"answers":[{"questionId":"q1","selectedOptionIds":["STANDARD"],"skipped":false}]}'

# 第 4 步：恢复执行（继续推理）
mcm ai resume $sessionId

# 第 5 步：提交第二个回答
mcm ai answer $sessionId -e evt_002 \
  -r '{"answers":[{"questionId":"q2","textAnswer":"pay-service,order-service","skipped":false}]}'

# 第 6 步：再次恢复执行
mcm ai resume $sessionId
# 输出示例：
# ✓ Agent 已恢复执行
# 🤖 MCM AI 助手
# 基于以上信息，我为你生成了如下计划：
# 1. 灰度验证（10%）
# 2. 全量推送
# 3. 后检查
# ✅ 计划已生成，ID: 12345
```

---

## 全局参数说明

### sessionId - 会话标识符
- **格式**: UUID，如 `027755fc-fbe6-4524-9280-c41dfa62fed9`
- **用途**: 维持对话上下文，用于多轮对话续接
- **生命周期**: 24 小时，自动过期
- **自动创建**: 不传 sessionId 时，mcm-cli 会自动创建或使用本地最新会话
- **用途**：在 `stop/reconnect/answer/resume` 中使用

### <question> - 用户问题（位置参数）
- **格式**: 自然语言字符串，最大 5000 字符
- **示例**: `"创建变更计划"`, `"变更后流量下降了，怎么办？"`
- **知识库增强**: 自动通过 MCM 知识库增强语义理解

### --plan-id - 变更计划 ID（可选）
- **格式**: 整数，如 `12345`
- **用途**: 指定操作的变更计划，执行变更计划步骤时必须提供
- **场景**: 执行变更步骤、针对特定计划提问、查询计划进度
- **示例**: `--plan-id 12345`

### --session-id (-s) - 会话 ID（可选）
- **格式**: UUID 或自动生成的会话ID
- **用途**: 继续之前的对话，保持上下文
- **示例**: `-s 027755fc-fbe6-4524-9280-c41dfa62fed9`

### --git-base-branch (-b) - Git 基础分支（可选）
- **默认**: `main`
- **用途**: PR 分析时的对比基准分支
- **示例**: `-b develop`

### --result - 回答内容（answer 命令必填）
- **格式**: 有效的 JSON 字符串
- **用途**: 提交用户对 AI 问题的回答
- **示例**: `--result '{"choice":"option-a","confirmed":true}'`

