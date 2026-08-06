# 工具清单

本文件列出 DUO 酒店提单页需求开发工作流中用到的工具，以及每个工具适合的场景。

## 内部知识与文档

| 工具 | Node | 用途 | 备注 |
|---|---:|---|---|
| `citadel` Skill | 24 | 读取学城 PRD、技术方案和引用文档 | MIS 从个人全局指令或环境变量读取；优先读取线上最新内容 |
| `oa-skills citadel` CLI | 24 | 将学城文档下载为 markdown 文件 | 适合生成方案、递归下载文档快照 |
| `duo-protocol` Skill | 24 | 理解 DUO 协议、Groovy、struct、dataSource、logics | 改协议前优先参考 |
| `skillhub` / `mtskills` | 24 | 读取、安装或更新内部 Skills | 用 Node 24，不用项目 Node 16 |

## UI 设计稿

| 工具 | 用途 | 输出 |
|---|---|---|
| `explore-design-tree-ingee` | 获取 Ingee 画板或图层数据 | `preview.png`、语义 JSON、图层 JSON |
| `ingee-flex` | 更细致地分析设计稿并生成 FLEX 设计文档 | DSL、视觉分析、图片信息 |
| `duo ingee-fetch` | 拉取指定画板节点 DSL 或裁切图 | 本地 JSON / 图片 |

建议：设计稿下载结果放到忽略目录 `.temp`；正式文档只记录结论和最终链接。

## AppMock

| 工具 / 路线 | 用途 | 备注 |
|---|---|---|
| `appmock-all` Skill | 理解和管理 AppMock 配置 | 使用前先读 Skill 文档 |
| `ciba-request.mjs` | 直连 `/appmockapi/` 接口 | 可能受 Node、SSO、MOA、CIBA 状态影响 |
| 浏览器已登录路线 | 兜底读取 AppMock 原始 JSON | 打开 `/appmockapi/mock/getMockConfigByMockId?mockId=<id>` |
| `data.response` 解析 | 提取业务 mock 响应体 | 通常是 JSON 字符串，需要二次解析 |

关键区分：

- `bizReq`：DUO 组装出的后端请求。
- `bizRes`：业务后端响应结构。
- `data`：DUO 转换后的页面 / 组件数据。

## 仓库与代码

| 工具 | 用途 |
|---|---|
| `rg`、`rg --files` | 快速搜索文件和符号 |
| `sed`、`nl`、`git show`、`git diff` | 读取聚焦上下文和历史变更 |
| `apply_patch` | 在工作区内做手工文件编辑 |
| `git diff --check` | 检查空白、冲突标记等问题 |
| `trade-commit-message` Skill | 基于暂存区 diff 生成中文 Conventional Commit 并执行 `git commit`；提交正文必须写明 `变更文件：` 和 `变更内容：` |
| Node JSON 解析 | 校验改动过的 JSON 文件 |
| 定向 eslint / typecheck | 校验改动过的 TS/TSX 文件 |

## 代码审查

| 工具 | 用途 | 备注 |
|---|---|---|
| `trade-code-reviewer` | 交易前端、DUO、MRN/MAX、Groovy 协议和物料综合审查 | 当前 DUO 提单页需求优先推荐 |
| `hotel-frontend-code-review` | 酒店前端本地 Git diff 审查，输出 PR 自查报告 | 适合本地扫当前分支改动 |
| Superpowers `requesting-code-review` | 用独立 reviewer 视角审查阶段成果 | 需要用户授权并行/子 Agent 时使用 |
| `branch-spell-check` | 检查英文拼写、大小写和术语 | PR 前辅助检查，不替代业务审查 |

## 运行与验证

| 命令区域 | Node | 用途 |
|---|---:|---|
| `duo-builder/yarn dev` | 16 | 默认本地 DUO 调试 |
| `duo-builder/yarn dev:web` | 16 | Web 调试 |
| `duo-builder/yarn dev:mrn` | 16 | MRN 调试 |
| DUO 平台 URL | 无 | 真机或平台联调验证 |

如果没有手机或 DUO 平台可用，最终回复要明确说明 MRN 端上验证仍待补齐。

## 文档与记录

| 文件区域 | 用途 |
|---|---|
| 个人全局指令，例如 `~/.codex/AGENTS.md` | 个人 MIS、个人偏好等不应进 Git 的身份信息 |
| 根 `AGENTS.md` | 全局硬规则、目录路由和项目地图 |
| 目录级 `AGENTS.md` | `protocol`、`material`、`docs`、`duo-builder` 的局部操作规则 |
| `docs/<需求目录>/agent-reference.md` | 长项目事实、链接、当前需求细节和低频参考 |
| `docs/<需求目录>/voice-prompt/*.md` | 用户语音输入的人工归档，收工或关键节点批量补齐 |
| `docs/<需求目录>/superpowers/plans/*.md` | 开发方案 |
| `docs/<需求目录>/superpowers/specs/*.md` | Superpowers brainstorming / 设计规格 |
| `docs/<需求目录>/progress/*progress.md` | 开发、联调、测试、Bug 修复进度 |
| `docs/<需求目录>/progress/*ai-tools.md` | AI 工具清单 |
| `docs/<需求目录>/progress/*token-usage.md` | Token、缓存 token、缓存命中率和费用统计 |
| `docs/<需求目录>/progress/*turn-log-events.jsonl` / `*turn-log.jsonl` | Codex hooks 每轮追加的原始 prompt、回复和耗时 |
| `docs/<需求目录>/progress/*turn-log.md` | 收工时由 `python .codex/hooks/turn_time_logger.py DailySummary` 生成的摘要版总结 |
| `docs/<需求目录>/progress/*turn-log-full.md` | 收工时由 `DailySummary` 生成的完整输入/输出版总结 |

## Token 和费用统计

| 来源 | 用途 |
|---|---|
| `~/.codex/sessions/**/*.jsonl` | 当前需求主线程 `total_token_usage`，可拆 cache input、uncached input 和 output |
| `~/.codex/session_index.jsonl` | 确认线程 ID、会话信息和 session JSONL 路径 |
| `docs/<需求目录>/progress/*turn-log*` | 统计阶段耗时时优先使用的每轮记录 |

记录两个口径：

- 需求主线程增量：当前累计 Token 减去基线。
- 费用估算：按当前需求主线程的 cache input、uncached input 和 output 拆分估算，不使用本机 CodexBar 全量作为本需求口径。
- 缓存命中率：`cache input token / input total token`。
