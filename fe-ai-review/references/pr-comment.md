# PR 评论落地工具

`fe-ai-review` 的可选后置动作：把本地 CR 产出的发现项提交到 PR（单条行内评论 + 合并全局摘要）。

## 何时执行

满足以下任一条件即触发（**默认启用**，2-B 策略）：

- 用户提供了 `dev.sankuai.com/code/repo-detail/{org}/{repo}/pr/{id}` 链接
- 用户明确说「发到 PR」「评论到 PR」「提交到 PR」等

若用户明确说「只看本地」「不用发 PR」「只出报告」，则跳过本流程。

## 前置条件

1. 主流程已产出 P0/P1/P2-P3 / Open Questions 四组发现项（Step 6 已完成）
   - 本地模式：还需通过 Step 0.c 仓库一致性校验
   - PR-only 模式：天然有 PR 链接，无需额外校验
2. 脚本目录 `scripts/pr-comment/` 下的 `cr-comment.sh` 和 `code_cli.py` 可用
3. MCode 已登录（Cookie 有效）。脚本按以下顺序取 Cookie：
   - CLI `--cookie` 参数
   - 环境变量 `CODE_COOKIE`
   - CatClaw 沙箱 SSO 无感登录（`mtsso-moa-local-exchange`，缓存 30min）
   - 临时文件 `$CODE_COOKIE_FILE`（默认 `/tmp/code_cookies.txt`）
   - 持久化文件 `~/.openclaw/mcode_cookie.txt`
   - Chrome CDP（`http://localhost:9222`）

## 评论策略（2-B）

| 级别 | 评论形式 | 原因 |
|------|---------|------|
| **P0** 🔴 | 行内评论（逐条，锚定 ADDED 行） | 阻塞合并，必须让作者看到具体行 |
| **P1** 🟠 | 行内评论（逐条，锚定 ADDED 行） | 高风险，上下文强绑定 |
| **P2** 🟡 | 行内评论（逐条，锚定 ADDED 行） | 2-B 策略：P2 也是具体代码位置的建议，行内更有价值 |
| **P3** 🔵 | 合并为一条全局摘要 | 风格/性能优化，避免行内刷屏 |
| **Open Questions** | 并入全局摘要 | 需要作者回复的疑问集中一处 |

> 只有「可合并为一类」的纯格式/风格问题才在行内写成一条合并评论，不逐行展开。

## 执行步骤

### Step A：鉴权预检

```bash
SCRIPT_DIR="<skill 根目录>/scripts/pr-comment"   # fe-ai-review/scripts/pr-comment 的绝对路径
python3 "$SCRIPT_DIR/code_cli.py" user-info
```

返回 `{"name": "...", "mis": "..."}` 即 OK；若报 Cookie 错误，按「前置条件」中的 Cookie 获取链修复。

### Step B：发送 P0/P1/P2 行内评论（逐条）

对每条 P0/P1/P2 发现项执行：

```bash
bash "$SCRIPT_DIR/cr-comment.sh" inline \
  --url "<PR_URL>" \
  --file-keyword "<文件名关键词，如 UserService.ts>" \
  --line <行号> \
  --line-type ADDED \
  --text "<评论正文>"
```

要点：
- **必须用 `--file-keyword`**（文件名关键词），脚本会从 `pr-changes` 解析完整路径。禁止传 `--file` 拼完整路径（容易错）。
- 关键词匹配到 0 个或多个文件，脚本会报错并列出候选；换更精确的关键词重试。
- `--line-type` 固定 `ADDED`（锚定到新增行）；如要锚定 CONTEXT 行可改 `CONTEXT`。禁止锚定 `REMOVED`。
- 脚本内置 4 次重试（间隔 2s）；仍失败 → 在会话输出错误，不阻塞后续。

评论正文模板（与 SKILL.md 报告风格保持一致）：

```
🔴 [P0] <一句话标题>
- 原因：<为什么是问题>
- 位置：<file>:<line>
- 建议：<具体修复，给代码示例更好>
```

```
🟠 [P1] <一句话标题>
- 原因 / 位置 / 建议
```

```
🟡 [P2] <一句话标题>
- 位置：<file>:<line>
- 建议：<具体优化>
```

### Step C：发送全局摘要（P3 + Open Questions + 整体结论）

```bash
bash "$SCRIPT_DIR/cr-comment.sh" global \
  --url "<PR_URL>" \
  --text "<摘要正文>"
```

摘要模板：

```
🤖 AI Code Review 摘要

📊 结论：<✅通过 / 💚通过有建议 / 🟠需修复 / 🔴需重新设计>
📈 统计：P0=<n> P1=<n> P2=<n> P3=<n>

---

🔵 P3 性能/现代化建议（<n> 条）
1. <file>:<line> — <建议>
2. ...

---

❓ Open Questions（<n> 条）
1. <待作者确认的问题>
2. ...
```

### Step D：验证

```bash
bash "$SCRIPT_DIR/cr-comment.sh" verify --url "<PR_URL>"
```

检查点：
- 行内评论的 `file` 字段非 null（null 表示锚定失败，发成了全局评论 → **必须修正后重发**）
- 评论数与预期一致

### Step E：会话回显

在对话中汇报：

```
📣 已同步到 PR：
- 行内评论：<n> 条（P0=<a> P1=<b> P2=<c>）
- 全局摘要：<✅/❌>
- 失败项：<如有，列出文件名+原因>
```

## 失败兜底

| 场景 | 处理 |
|------|------|
| 鉴权失败（Step A） | 提示用户配置 Cookie，不继续发评论 |
| 行内评论路径解析失败 | 脚本自动报错退出，换关键词重试或回退为全局评论 |
| 单条行内评论 4 次重试仍失败 | 跳过该条，继续下一条，最后在会话汇总失败清单 |
| 全局摘要 4 次重试仍失败 | 在会话输出完整摘要文本，让用户手动贴到 PR |
| `verify` 发现 file=null | 按提示修正 `--file-keyword` 后重发该条 |

**原则**：任何失败都不阻塞主 CR 报告的产出。

## 与 CR 主流程的关系

- 本流程对应 Step 7（两个 mode 共用的可选后置动作），不改变 Step 0~6 的审查流程
- 仅复用主流程已产出的 `P0 / P1 / P2-P3 / Open Questions` 四组发现项，不做二次审查
- 报告仍按 `references/tpl-report.md` 输出；PR 评论只是把报告内容"搬运"到 PR
- PR-only 模式下，行内评论可能因 `fromHash` 解析受限退化为全局评论（`verify` 输出 `file: null`），评论内容仍完整可见，**不视为发送失败**——如需精确锚定，请走本地模式

## 参数速查

| 子命令 | 用途 | 必填参数 |
|--------|------|---------|
| `inline` | 行内评论 | `--url --file-keyword --line --text` |
| `global` | 全局评论 | `--url --text` |
| `verify` | 列出当前 PR 所有评论 | `--url` |
| `list-paths` | 列出 PR 全部变更文件路径 | `--url` |
| `delete` | 删除指定评论 | `--url --comment-id` |

