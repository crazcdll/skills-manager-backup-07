# DUO Knowledge Base — Agent 使用指南

## 第一步：必读

进入任何 DUO 相关任务前，先读以下两个文件：

- `wiki/concepts/duo-overview.md`（DUO 整体架构，必读）
- `wiki/concepts/duo-protocol.md`（协议结构速查，必读）

## 按任务类型读取


| 任务类型           | 读取文件                                |
| -------------------- | ----------------------------------------- |
| 生成/调试协议      | `wiki/howto/protocol-generation.md`     |
| 开发新页面         | `wiki/howto/development-workflow.md`    |
| 开发物料组件       | `wiki/howto/material-development.md`    |
| 写 Groovy 表达式   | `wiki/howto/groovy-expressions.md`      |
| 构建/发布          | `wiki/howto/build-and-deploy.md`        |
| 排查白屏/渲染异常  | `wiki/troubleshooting/render-issues.md` |
| 排查数据不更新     | `wiki/troubleshooting/data-issues.md`   |
| 排查构建/发布问题  | `wiki/troubleshooting/build-issues.md`  |
| 需要看具体代码实现 | `context/repo-map.md`                   |

## wiki/ 不够用时

去 `raw/index.md` 找原始学城文档链接，直接读原始文档获取更完整的信息。

## 知识沉淀规则

完成任务后，如果满足以下任一条件，执行沉淀动作：

1. 遇到 wiki/ 里没有记录的错误及解法
2. 发现某个字段/API 的实际行为与 wiki/ 描述不符
3. 完成了一个新的开发模式或最佳实践

**沉淀动作**：调用 catdesk-office SKILL，发送消息到「DUO 知识库维护群」，消息格式严格如下：

```
【DUO 知识沉淀】
场景：（什么任务触发了这个发现，一句话）
发现：（具体知识内容，尽量精确）
建议归档：（wiki/ 下的哪个文件）
置信度：高 / 中 / 低
```

> 置信度「低」的内容仍然发送，由维护者判断是否归档。

任务完成后，在对话末尾输出以下提示：

```
任务已完成。如果本次过程中有值得记录的新发现，可以说「记录到知识库」，我会帮你整理并发送到维护群。
```
