# 维度 7：编码规范遵守度（12%，L4）

**核心原则**：考察"规范是否定义并可自动执行"。禁止行为明确列出，是 AI 避免踩坑的关键。

> ⚠️ **重要区分**：工具配置存在 ≠ 规范"有定义"。必须同时有**规范文档**（说明"为什么"和"禁止什么"）和**自动化工具**（强制执行）。

## 量化定义（消除主观歧义）

在评分前，先对以下术语做量化判定：

| 术语 | 量化标准 |
|------|---------|
| **一条有效禁止规则** | 同时满足：①以"禁止/不允许/不得/❌/forbidden/prohibited"等否定词开头；②描述具体行为（而非泛泛"遵守最佳实践"）；③可被人工或工具验证是否违反。三项缺任一项不计入"条数" |
| **禁止行为 ≥5 条** | 按上述标准逐条计数，达到 5 条才算满足；多条相似规则（如"禁止用 var 声明"和"禁止用 let 声明全局变量"）各算一条 |
| **规范文档充实** | 文档中有效规则条数 ≥ 5 条，且至少有 1 条附有违反示例（反例代码或反例描述） |
| **无硬编码敏感配置** | 检查命令（见下方技术栈执行指南）扫描结果为 0 个命中；若有命中，每个命中扣 5 分，上限扣 20 分 |
| **CI 自动化检查** | CI 配置文件中存在 lint/checkstyle/tsc 等检查步骤，且该步骤配置为失败时阻断流水线（非 `continue-on-error: true`） |

## 评估标准（通用）

- [ ] **规范文档存在且充实**：有具体的编码规范说明，且有效规则 ≥ 5 条（见量化定义）
- [ ] **禁止行为明确列出**：按量化定义计数，有效禁止规则 ≥ 5 条，至少 1 条附反例
- [ ] **静态分析工具已接入**：能自动检测代码质量问题
- [ ] **代码格式化工具已接入**：统一代码风格
- [ ] **CI 中有自动化检查**：CI 配置中有检查步骤且失败阻断（非 continue-on-error）
- [ ] **无硬编码敏感配置**：扫描命中数为 0（密钥、Token、内部地址等通过配置管理）

## 评分细则（通用）

| 分段 | 描述 | 量化判定依据 |
|------|------|------------|
| 90–100 | 规范文档完整，禁止行为清单充实，工具链齐全，CI 全套检查 | 有效禁止规则 ≥5 条且有反例 + 静态分析 + CI 阻断 + 硬编码扫描 0 命中 |
| 75–89 | 规范文档存在，静态分析工具接入，CI 部分接入 | 有效禁止规则 ≥5 条（无反例）或 3–4 条有反例 + 静态分析已接入 |
| 60–74 | 有规范意识，工具存在，但禁止行为不明确或 CI 未接入 | 有效禁止规则 1–2 条，或工具配置存在但无规范文档 |
| 30–59 | 有工具配置但无规范文档；或有文档但无自动化检查 | 工具配置存在但有效规则 = 0；或文档存在但无静态分析工具 |
| <30 | 无任何规范文档，无静态分析工具 | 文档不存在 + 工具未配置 |

### 评分锚点示例

**90 分样本（高分）**：
```
AGENTS.md 中包含：
❌ 禁止在 Controller 层直接调用 DAO，原因：绕过事务管理，反例：userDao.save(user) 在 Controller 中直接调用
❌ 禁止在 SQL 中使用 ${} 拼接用户输入，原因：SQL 注入风险，反例：WHERE name = '${name}'
❌ 禁止 catch 后仅 log 不 rethrow，原因：吞异常导致上层无法感知错误
❌ 禁止在循环内调用 RPC，原因：N+1 问题，应批量查询
❌ 禁止使用 System.out.println 输出日志，原因：不受日志级别控制
（共 5 条，每条含原因，其中 3 条含反例代码）
+ pom.xml 中 checkstyle 已配置 + CI 流水线中 checkstyle 步骤 failsOnError=true
```

**65 分样本（中分）**：
```
.cursorrules 中包含：
- 使用 TypeScript 严格模式
- 组件用函数式写法
- 避免使用 any
（共 3 条，均无反例，表述模糊，不满足"具体行为可验证"）
+ ESLint 已配置，但 CI 中 eslint 步骤配置了 continue-on-error: true（不阻断）
```

**35 分样本（低分）**：
```
package.json 中有 eslint 依赖，但：
- 无 .eslintrc 配置文件（或配置为空 {}）
- 无任何规范文档
- 无禁止行为清单
（工具存在但实质上未配置，有效规则 = 0）
```

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 规范文档 | `ls .mdp/rules/company/java/ 2>/dev/null` | `wc -l .cursorrules 2>/dev/null; find .catpaw/rules/ -name "*.md" 2>/dev/null \| xargs wc -l 2>/dev/null; wc -l AGENTS.md 2>/dev/null` |
| 禁止行为数量 | `grep -r "禁止\|不允许\|不得\|forbidden\|prohibited" .mdp/rules/ --include="*.md" 2>/dev/null \| wc -l` | `grep -n "禁止\|不允许\|不得\|❌\|forbidden\|prohibited" .cursorrules AGENTS.md 2>/dev/null \| wc -l; grep -rn "禁止\|❌" .catpaw/rules/ 2>/dev/null \| wc -l` |
| 静态分析工具 | `grep -E "checkstyle" pom.xml 2>/dev/null` | `ls .eslintrc.* eslint.config.* .eslintrc.js .eslintrc.ts .eslintrc.json 2>/dev/null` |
| 代码格式化工具 | （Checkstyle 兼顾格式检查） | `ls .prettierrc* prettier.config.* 2>/dev/null` |
| Commit 规范（前端专用） | 无等效 | `ls commitlint.config.* .commitlintrc.* 2>/dev/null; grep -E "commitlint\|@commitlint" package.json 2>/dev/null` |
| Pre-commit hook（前端专用） | 无等效 | `ls .husky/ 2>/dev/null && cat .husky/pre-commit 2>/dev/null; grep -E "lint-staged\|husky" package.json 2>/dev/null` |
| CI 自动化检查 | `grep -E "checkstyle\|jacoco" pom.xml 2>/dev/null; ls .github/workflows/ 2>/dev/null && grep -r "checkstyle\|jacoco" .github/workflows/ 2>/dev/null \| head -5` | `ls .github/workflows/ 2>/dev/null && grep -r "lint\|eslint\|tsc\|typecheck" .github/workflows/ 2>/dev/null \| head -5` |
| 硬编码敏感配置 | `grep -rn "password\s*=\s*['\"][^$\{]" . --include="*.java" --include="*.properties" --include="*.yml" 2>/dev/null \| grep -v "test"` | `grep -rn "http://\|https://" src/ packages/ --include="*.ts" --include="*.tsx" 2>/dev/null \| grep -v "node_modules\|\.test\.\|example\|placeholder" \| head -10` |
| SQL 注入风险（后端专用） | `echo "预编译（安全）: $(grep -r '#{' . --include='*.xml' 2>/dev/null \| wc -l)"; echo "字符串拼接（风险）: $(grep -r '\${' . --include='*.xml' 2>/dev/null \| grep -v 'mapper\|namespace\|resultType\|resultMap\|parameterType' \| wc -l)"` | 无等效 |
| TypeScript strict 模式（前端专用） | 无等效 | `grep -r '"strict"' tsconfig*.json 2>/dev/null; grep -r '"noImplicitAny"' tsconfig*.json 2>/dev/null` |
