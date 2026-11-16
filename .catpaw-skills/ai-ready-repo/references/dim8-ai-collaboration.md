# 维度 8：AI 协作友好度（8%，L4）

**核心原则**：考察"执行有效性"——AI 知道用哪类文档做什么事，有先例可复用，不确定时有路径可循，且有工具能力扩展（MCP Server）。

## 评估标准（通用）

- [ ] **AI 任务入口清晰**：AI 知道从哪里开始、用什么文档做什么事
- [ ] **工作流文档存在且完整**：有具体的编码/开发工作流说明（非空模板）
- [ ] **有历史需求案例沉淀**：PRD → 方案设计 → 代码的完整映射案例，供 AI 参考
- [ ] **非标需求有明确处理路径**：AI 知道"不确定时找谁"或如何上报
- [ ] **规则优先级机制存在**：当规则冲突时，AI 知道哪个优先
- [ ] **MCP Server 已配置**（加分项）：有 `.vscode/mcp.json` 或 `.mcp.json` 或 `AGENTS.md` 中有 MCP 工具说明，AI 可通过工具调用扩展能力（参考 agentrc Level 4：AI Tooling）

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 任务入口清晰，工作流完整，有案例沉淀，非标路径明确，规则优先级有说明；有 MCP Server 配置可进一步加分 |
| 75–89 | 工作流存在，任务入口基本清晰，但缺案例沉淀或非标路径 |
| 60–74 | 有基础 AI 协作支持，但缺乏系统性 |
| <60 | 无 AI 协作基础设施 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| AI 任务入口 | `ls .mdp/workflows/mdp-coding.md 2>/dev/null; wc -l .mdp/workflows/mdp-coding.md 2>/dev/null` | `wc -l AGENTS.md .cursorrules 2>/dev/null; ls .catpaw/rules/ 2>/dev/null` |
| 工作流文档完整性 | `wc -l .mdp/workflows/mdp-coding.md 2>/dev/null; grep -c "##\|步骤\|Step" .mdp/workflows/mdp-coding.md 2>/dev/null` | `grep -c "##\|步骤\|workflow\|流程" AGENTS.md .cursorrules 2>/dev/null` |
| 历史案例沉淀 | `find .mdp/context/ -name "*spec*" -o -name "*案例*" 2>/dev/null; find .mdp/ -name "*spec*" 2>/dev/null \| wc -l` | `find docs/specs/ .catpaw/specs/ -name "*.md" 2>/dev/null; find docs/ -name "*spec*" -o -name "*案例*" 2>/dev/null \| wc -l` |
| 非标处理路径 | `grep -r "不确定\|升级\|找谁\|escalate\|上报" .mdp/ --include="*.md" 2>/dev/null \| wc -l` | `grep -rn "不确定\|升级\|找谁\|escalate\|上报" AGENTS.md .cursorrules .catpaw/rules/ 2>/dev/null \| wc -l` |
| 规则优先级 | `grep -r "优先级\|priority\|项目级\|团队级\|公司级" .mdp/ --include="*.md" 2>/dev/null \| wc -l` | `grep -rn "优先级\|priority\|覆盖\|override" AGENTS.md .cursorrules 2>/dev/null \| wc -l` |
| MCP Server 配置 | `ls .vscode/mcp.json .mcp.json 2>/dev/null; grep -rn "mcp\|MCP" AGENTS.md .mdp/ --include="*.md" 2>/dev/null \| head -5` | `ls .vscode/mcp.json .mcp.json 2>/dev/null; grep -rn "mcp\|MCP" AGENTS.md .cursorrules .catpaw/rules/ 2>/dev/null \| head -5` |
