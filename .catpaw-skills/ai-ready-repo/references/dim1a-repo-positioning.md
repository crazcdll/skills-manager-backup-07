# 维度 1a：仓库定位准确性（6%，L1）

**核心原则**：AI 首先要知道"这个仓库是什么、解决什么问题、边界在哪"。
业务边界不清晰，AI 就会在错误范围内设计方案；拓扑关系缺失，AI 就会做出跨边界的改动。

## 评估标准（通用）

- [ ] **业务域定位**：明确该仓库负责的业务领域/产品功能边界（做什么 / 不做什么）
- [ ] **系统/应用拓扑关系**：与其他仓库/服务/子应用的上下游关系显性化
- [ ] **服务/应用画像**：技术栈声明、核心依赖、关键约束等基础信息有明确记录
- [ ] **关键约束声明**：禁止使用哪些库/工具、强制技术决策、SLA 等

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 四项全部清晰：边界声明明确、拓扑关系可视化（有图或列表）、画像完整、约束已列出 |
| 75–89 | 三项清晰，第四项缺失或描述笼统 |
| 60–74 | 仅有业务功能描述，无边界声明，无拓扑，无画像 |
| 30–59 | 仅有 README 简介，内容笼统，无法帮助 AI 判断改动范围 |
| <30 | 无任何定位信息，或文档为空模板 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 业务边界描述 | `grep -rE "做什么\|不做什么\|业务边界\|负责\|scope\|boundary" AGENTS.md README.md .mdp/ 2>/dev/null \| head -10` | `grep -rE "做什么\|不做什么\|业务边界\|负责\|页面\|功能\|scope\|boundary" AGENTS.md README.md 2>/dev/null \| head -10` |
| 拓扑/依赖关系 | `grep -rE "上游\|下游\|调用方\|依赖\|topology\|upstream\|downstream" AGENTS.md README.md .mdp/ 2>/dev/null \| head -10` | `grep -rE "子应用\|微前端\|shared-lib\|packages\|依赖\|upstream" AGENTS.md README.md 2>/dev/null \| head -10` |
| 服务/应用画像 | `grep -rE "AppKey\|appkey\|SLA\|调用方\|依赖服务\|服务画像" AGENTS.md README.md .mdp/ 2>/dev/null \| head -10` | `grep -rE "React\|Vue\|TypeScript\|pnpm\|技术栈\|框架\|组件库" AGENTS.md README.md .cursorrules 2>/dev/null \| head -10` |
| 关键约束声明 | `grep -rE "禁止\|不允许\|不得\|forbidden" .mdp/rules/ 2>/dev/null \| wc -l` | `grep -rE "禁止\|不允许\|不得\|❌\|forbidden" .cursorrules .catpaw/rules/ AGENTS.md 2>/dev/null \| wc -l` |
| 子项目结构（MonoRepo） | 无 | `[ -f "pnpm-workspace.yaml" ] && cat pnpm-workspace.yaml; ls packages/ 2>/dev/null \| head -20` |
