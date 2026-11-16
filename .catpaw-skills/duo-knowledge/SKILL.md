---
name: duo-knowledge
description: DUO 低代码平台知识库。处理任何 DUO 相关任务时使用——包括协议生成、Groovy 表达式编写、物料开发、页面构建/发布、白屏/数据异常排查、理解 duo-engine/duo-builder/duo-protocol 实现原理。

metadata:
  skillhub.creator: "liuxin62"
  skillhub.updater: "liuxin62"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "39709"
  skillhub.high_sensitive: "false"
---

# DUO Knowledge Base

## 知识库位置

知识库打包在本 SKILL 的 `knowledge/` 子目录下：

```
knowledge/
  AGENTS.md          ← 入口导航（任务类型 → 读哪个文件）
  wiki/              ← 编译后的结构化知识（主要读这里）
  context/           ← 代码仓库地图（需要深入代码时读）
  raw/               ← 原始学城文档索引（wiki 不够用时查链接）
```

## 使用流程

**第一步：必读两个文件**（任何 DUO 任务都要先读）

- `wiki/concepts/duo-overview.md` — DUO 整体架构
- `wiki/concepts/duo-protocol.md` — 协议结构速查

**第二步：按任务类型读对应文件**

| 任务 | 读取文件 |
|------|---------|
| 生成/调试协议 | `wiki/howto/protocol-generation.md` |
| 开发新页面 | `wiki/howto/development-workflow.md` |
| 开发物料组件 | `wiki/howto/material-development.md` |
| 写 Groovy 表达式 | `wiki/howto/groovy-expressions.md` |
| 构建/发布 | `wiki/howto/build-and-deploy.md` |
| 排查白屏/渲染异常 | `wiki/troubleshooting/render-issues.md` |
| 排查数据不更新 | `wiki/troubleshooting/data-issues.md` |
| 排查构建/出码问题 | `wiki/troubleshooting/build-issues.md` |
| 理解引擎/协议实现 | `wiki/concepts/duo-engine.md` |
| 理解物料协议 | `wiki/concepts/duo-material.md` |
| 理解 duo-builder | `wiki/context/duo-builder.md` |
| 需要看具体代码 | `context/repo-map.md` |

**第三步：wiki 不够用时**

查 `raw/index.md`，里面有 50+ 篇学城文档的链接和关键章节说明，直接读原始文档。

## 知识沉淀

任务完成后，如果发现 wiki 里没有记录的错误解法、字段行为与描述不符、或新的最佳实践，通过 catdesk-office SKILL 发送到「DUO 知识库维护群」：

```
【DUO 知识沉淀】
场景：（一句话）
发现：（具体内容）
建议归档：（wiki/ 下哪个文件）
置信度：高 / 中 / 低
```

任务结束时在对话末尾输出：
> 任务已完成。如果本次过程中有值得记录的新发现，可以说「记录到知识库」，我会帮你整理并发送到维护群。
