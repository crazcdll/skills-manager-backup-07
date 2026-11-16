# 维度 1b：仓库导航完整性（6%，L1）

**核心原则**：AI 知道仓库是什么之后，还要知道"怎么找到正确的文档和规则"。
导航入口文件是路由起点，骨架存在仅得基础分，路由有效性才是高分段。
**可发现性要求**：关键文档必须在从导航入口出发的 ≤2 跳内可达；跳数越深，导航质量越低。

## 评估标准（通用）

- [ ] **导航入口文件存在**——基础分（30 分）
- [ ] **意图识别表完整**：触发词 → 强制动作，覆盖主要开发场景
- [ ] **文档路由规则有效**：任务类型 → 对应文档路径，无死链
- [ ] **路由覆盖完整性**：必须覆盖四类目标——架构文档、领域/业务文档、编码规范、测试指南；缺少任意一类视为路由不完整
- [ ] **跳数深度合格**：从导航入口出发，到达任意关键文档的跳数 ≤2；存在需 3–4 跳才能到达的关键文档则扣分
- [ ] **无死链**：导航入口及其直接引用的所有文档中，不存在引用了实际不存在文件的链接

## 跳数定义

- **跳数 = 0**：信息直接写在导航入口文件中
- **跳数 = 1**：从导航入口有直接链接，一次点击可达
- **跳数 = 2**：从导航入口链接的文档中再有一次链接，两次点击可达
- **跳数 > 2**：需要多次跳转，AI 在有限上下文窗口内较难自动追踪

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 导航入口路由完整有效，四类文档（架构/领域/规范/测试）均在 ≤2 跳内可达，无死链，AI 可自动定位 |
| 75–89 | 导航入口存在，四类文档基本覆盖，但存在 1–2 个跳数为 3 的文档，或有少量死链（≤2 处） |
| 60–74 | 导航入口路由存在但覆盖不全（缺少 1–2 类目标），或关键文档需 3–4 跳才能到达 |
| 30–59 | 仅有导航入口骨架，无有效路由规则，或存在大量死链（>3 处） |
| <30 | 无任何导航入口文件，无任何导航信息 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 导航入口文件 | `ls AGENTS.md 2>/dev/null && echo "存在" \|\| echo "不存在"` | `ls AGENTS.md .cursorrules .catpaw/rules/ .github/copilot-instructions.md 2>/dev/null` |
| 架构文档路由 | `grep -E "arch\|architecture\|架构\|OVERVIEW\|\.mdp" AGENTS.md 2>/dev/null \| head -3` | `grep -E "arch\|architecture\|架构\|README\|docs/" AGENTS.md .cursorrules 2>/dev/null \| head -3` |
| 领域文档路由 | `grep -E "domain\|领域\|业务\|business" AGENTS.md 2>/dev/null \| head -3` | `grep -E "domain\|领域\|业务\|business" AGENTS.md .cursorrules 2>/dev/null \| head -3` |
| 编码规范路由 | `grep -E "standard\|规范\|convention\|coding\|rules" AGENTS.md 2>/dev/null \| head -3` | `grep -E "standard\|规范\|convention\|coding\|rules\|cursorrules" AGENTS.md .cursorrules 2>/dev/null \| head -3` |
| 测试指南路由 | `grep -E "test\|测试\|testing" AGENTS.md 2>/dev/null \| head -3` | `grep -E "test\|测试\|testing\|vitest\|jest" AGENTS.md .cursorrules 2>/dev/null \| head -3` |
| 死链检测 | `grep -oE '\[[^\]]+\]\([^)]+\.md\)' AGENTS.md 2>/dev/null \| grep -oE '\([^)]+\)' \| tr -d '()' \| while read path; do [ -f "$path" ] && echo "✅ 可达: $path" \|\| echo "❌ 死链: $path"; done` | `for f in AGENTS.md .cursorrules; do [ -f "$f" ] && grep -oE '\[[^\]]+\]\([^)]+\.md\)' "$f" 2>/dev/null \| grep -oE '\([^)]+\)' \| tr -d '()' \| while read path; do [ -f "$path" ] && echo "✅ 可达: $path" \|\| echo "❌ 死链: $path"; done; done` |
| 跳数=1 的文档 | `grep -oE '\[[^\]]+\]\([^)]+\.md\)' AGENTS.md 2>/dev/null \| grep -oE '\([^)]+\)' \| tr -d '()' \| while read path; do [ -f "$path" ] && echo "$path"; done` | `for f in AGENTS.md .cursorrules; do [ -f "$f" ] && grep -oE '\[[^\]]+\]\([^)]+\.md\)' "$f" 2>/dev/null \| grep -oE '\([^)]+\)' \| tr -d '()' \| while read path; do [ -f "$path" ] && echo "$path"; done; done` |
| 文档元数据（后端专用） | `total=$(find .mdp/ -name "*.md" -type f 2>/dev/null \| wc -l); with_fm=$(grep -rl "^---" .mdp/ 2>/dev/null \| wc -l); echo "元数据覆盖率: $with_fm / $total"` | 无（前端不使用 YAML Front Matter 标准） |
