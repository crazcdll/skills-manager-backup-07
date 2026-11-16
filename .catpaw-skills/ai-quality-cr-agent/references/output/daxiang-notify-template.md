# 大象群聊推送模板（Step 8）

> ⚠️ 消息**必须以 `【AI-CR Agent】` 开头**，否则拒绝发送。

**无 P0/P1 时（清爽版）：**
```
【AI-CR Agent】{org}/{repo} #{id} {title}
{conclusion_emoji}{conclusion_text}  P0={p0} P1={p1} P2={p2} P3={p3}
提交人：{authorName}（{submitter_mis}）  触发人：{triggerName}（{triggerMis}）
范围: {scope_label_compact}

📄 {kmUrl}
🔗 {prUrl}
```

**有 P0/P1 时（带关键问题）：**
```
【AI-CR Agent】{org}/{repo} #{id} {title}
{conclusion_emoji}{conclusion_text}  P0={p0} P1={p1} P2={p2} P3={p3}
提交人：{authorName}（{submitter_mis}）  触发人：{triggerName}（{triggerMis}）
范围: {scope_label_compact}

⚠️ 关键问题：
{top_issues_text}
📄 {kmUrl}
🔗 {prUrl}
```

**实例（全量 CR）：**
```
【AI-CR Agent】mtec/inf-cr-agent #1024 支持增量 CR
🟠需修复  P0=0 P1=2 P2=3 P3=1
提交人：张三（zhangsan）  触发人：李四（lisi）
范围: 🟦全量

⚠️ 关键问题：
• P1-1 并发写 HashMap 存在数据覆盖风险
• P1-2 外部调用未设超时时间
📄 https://km.sankuai.com/collabpage/xxxxxxxxx
🔗 https://dev.sankuai.com/code/repo-detail/mtec/inf-cr-agent/pr/1024
```

**实例（增量 CR）：**
```
【AI-CR Agent】mtec/inf-cr-agent #1024 支持增量 CR
💚通过有建议  P0=0 P1=1 P2=0 P3=0
提交人：张三（zhangsan）  触发人：李四（lisi）
范围: 🟩增量(5个新commit)

⚠️ 关键问题：
• P1-1 新增缓存未设过期时间
📄 https://km.sankuai.com/collabpage/xxxxxxxxx
🔗 https://dev.sankuai.com/code/repo-detail/mtec/inf-cr-agent/pr/1024
```

> 说明：
> - `{conclusion_emoji}` + `{conclusion_text}`：✅通过 / 💚通过有建议 / 🟠需修复 / 🔴需重新设计
> - `范围: {scope_label_compact}`：位置固定在**「提交人/触发人」行之后、空行之前**（对应 `publish_results.py` 中 `lines = [header, stats, people, scope, ""]`）。注意冒号是**英文 `:` 加空格**，与上方「提交人：」的中文冒号不一致，这是代码实际行为，勿自行“修正”。
> - **本处用 compact 紧凑格式**（`scope_label(args, compact=True)`），与 PR 全局评论 / 学城文档的完整格式**不同** —— 无空格、用半角括号、**不展示 base/target commit hash**：
>
>   | 场景 | 大象推送（compact） | 对比：PR 评论 / 学城（非 compact） |
>   |------|------------------|--------------------------------|
>   | 全量 CR | `🟦全量` | `🟦 全量` |
>   | 增量 CR | `🟩增量(5个新commit)` | `🟩 增量（从 \`7394fa3d\` → \`57c84425\`，5 个新 commit）` |
>   | 增量但 commit_count 为空 | `🟩增量` | `🟩 增量（从 \`7394fa3d\` → \`57c84425\`）` |
>
> - 该行**始终输出**，全量 CR 也不省略；大象推送**不包含**基准 commit 行（那一行只在 PR 全局评论末尾）
> - `{top_issues_text}`：每个 P0/P1 各占一行，格式 `• P1-01 问题标题`；无 P0/P1 则整段省略（不写"未发现 P0/P1"）
> - `{triggerName}（{triggerMis}）`：triggerMis 从当前 session 操作者 mis 获取，triggerName 通过 `code_cli.py user-info {triggerMis}` 获取；**禁止硬编码、禁止省略触发人**
> - 多仓库联合 CR：每个 PR 各列一行 🔗 链接，结论取最高级别
> - **@ 策略**：全局群一律纯文本不 @（群广播模式）；团队群真实 **@ 模板 people 行人员（提交人 + 触发人）**——发送时对应行的 `{authorName}`/`{triggerName}` 替换为 `[@{姓名}|mtdaxiang://www.meituan.com/profile?uid={uid}&isAt=true]` 并携带 `extension.at`（uid 为大象 uid，非 mis；同一人双行都高亮，at 数组去重）。某人 mis 查不到 uid 时该人保持纯文本，其余照常 @，推送不中断。协议细节见 [daxiang-notify-api.md](daxiang-notify-api.md)
> - **禁止**出现"涉及文件 N 个"等元数据行
