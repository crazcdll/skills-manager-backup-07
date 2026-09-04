# 维度 9：测试验证（后端 12% / 前端 2%，L5）

**核心原则**：考察"AI 改完能否自证正确性"，不只是测试文件是否存在。
CI/流水线质量门禁是自动化验证的核心，缺失会形成严重的人工 Review 瓶颈。

> **权重按仓库类型分档**：本维度权重在 [weight-profiles.json](weight-profiles.json) 中按 REPO_TYPE 区分——后端 12%、前端（frontend / frontend-mono / nodejs）2%。前端因 UI 测试 ROI 低、单测普遍缺失而**在权重层降权**（不在本文件的评分细则中放水），故本文件的 0–100 原始分评分标准对所有技术栈一视同仁，前后端的差异只体现在最终加权时的权重大小上。

## 评估标准（通用）

- [ ] **测试框架已接入且可运行**：有测试配置，能实际执行
- [ ] **核心业务逻辑有测试覆盖**：不只是工具类，核心业务路径有测试
- [ ] **测试覆盖率有统计**：能看到覆盖率数据，有量化指标（工具不限）
- [ ] **本地可一键自验证**：有标准化测试命令（`npm test` / `mvn test` / `make test`），AI 改完可独立运行验证
- [ ] **覆盖率阈值有配置**：有量化门禁（不限工具，JaCoCo / Istanbul / c8 / Vitest coverage 均可）
- [ ] **CI/流水线中有测试门禁**：无论使用何种 CI 平台（GitHub Actions / Jenkins / 内部流水线），测试失败会阻塞合并
- [ ] **测试命名描述性强**：测试意图清晰（`should_return_empty_when_no_items` 而非 `test1`）
- [ ] **边界条件与异常场景有覆盖**：空值、异常返回、边界输入有测试用例

## 评分细则（通用）

| 分段 | 描述 |
|------|------|
| 90–100 | 测试框架完整接入，核心逻辑覆盖率达标，CI/流水线有门禁，覆盖率阈值已配置，本地可一键自验证，测试命名规范，边界场景覆盖 |
| 75–89 | 测试框架接入，覆盖率基本达标，CI/流水线有测试步骤，本地可运行 |
| 60–74 | 测试框架接入，有测试文件，但覆盖率偏低，无 CI 门禁或无覆盖率阈值配置 |
| 30–59 | 仅有少量测试文件，覆盖率极低，无 CI 集成 |
| <30 | 无任何测试文件，或测试框架未安装，或本地无法运行测试 |

## 技术栈执行指南

> 根据 REPO_TYPE 选择对应列的检查命令执行。

| 检查项 | backend（Java/Maven） | frontend/frontend-mono（TS/JS） |
|--------|----------------------|--------------------------------|
| 测试框架检测 | `find . -type f -path "*/src/test/java/*" -name "*.java" \| wc -l` | `grep '"vitest"\|"jest"' package.json 2>/dev/null; find . -name "vitest.config.*" -o -name "jest.config.*" 2>/dev/null \| grep -v "node_modules"` |
| 测试/源文件比 | `test_count=$(find . -type f -path "*/src/test/java/*" -name "*.java" \| wc -l); src_count=$(find . -type f -path "*/src/main/java/*" -name "*.java" \| wc -l); echo "测试/源文件比: $test_count / $src_count"` | `test_count=$(find . \( -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" -o -name "*.spec.tsx" \) -not -path "*/node_modules/*" 2>/dev/null \| wc -l); src_count=$(find . \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" -not -path "*/dist/*" -not -name "*.d.ts" 2>/dev/null \| grep -v "test\|spec" \| wc -l); echo "测试文件: $test_count \| 源码文件: $src_count"` |
| 本地自验证命令 | `grep -E '"test"\|"verify"\|"surefire"' pom.xml 2>/dev/null \| head -5; ls Makefile 2>/dev/null && grep -n "test" Makefile \| head -5` | `grep '"test"' package.json 2>/dev/null; grep '"test:unit"\|"test:coverage"' package.json 2>/dev/null` |
| 覆盖率工具配置 | `grep -rE "jacoco\|cobertura\|coverage\|报告" pom.xml 2>/dev/null \| head -5; find . -name "jacoco*.xml" -not -path "*/target/*" 2>/dev/null \| head -3` | `grep -rn "coverage\|istanbul\|c8\|--coverage" package.json vitest.config.* jest.config.* 2>/dev/null \| grep -v "node_modules" \| head -10` |
| 覆盖率阈值配置 | `grep -A5 -B2 "limit\|minimum\|threshold\|覆盖率" pom.xml 2>/dev/null \| head -20` | `grep -A3 "thresholds\|branches\|lines\|statements\|functions" vitest.config.* jest.config.* 2>/dev/null \| head -20` |
| CI/流水线测试门禁 | `ls .github/workflows/ Jenkinsfile Makefile ci.yml .ci/ 2>/dev/null; grep -rn "test\|surefire\|verify" .github/workflows/ Jenkinsfile 2>/dev/null \| head -5` | `ls .github/workflows/ Jenkinsfile Makefile ci.yml .ci/ 2>/dev/null; grep -rn "test\|vitest\|jest" .github/workflows/ Jenkinsfile 2>/dev/null \| head -10` |
| 测试命名抽样 | `find . -path "*/src/test/java/*" -name "*.java" 2>/dev/null \| head -3 \| while read f; do echo "--- $f ---"; grep -n "@Test\|should_\|when_\|given_" "$f" \| head -10; done` | `find . \( -name "*.test.ts" -o -name "*.spec.ts" \) -not -path "*/node_modules/*" 2>/dev/null \| head -3 \| while read f; do echo "--- $f ---"; grep -n "it(\|test(\|describe(" "$f" \| head -10; done` |
| 各模块测试分布（前端专用） | 无 | `for dir in packages/*/ shared-lib/ src/; do if [ -d "$dir" ]; then cnt=$(find "$dir" \( -name "*.test.*" -o -name "*.spec.*" \) -not -path "*/node_modules/*" 2>/dev/null \| wc -l); echo "$cnt 个测试文件: $dir"; fi; done` |

## 结构性差异说明

- **后端**：覆盖率工具不限（JaCoCo / Cobertura / Jacoco-Maven-Plugin 均可），整体行覆盖率阈值 ≥ 80%；关键考察点是阈值是否在构建配置中**强制执行**（构建失败而非仅报告）
- **前端**：分层阈值——
  - 工具函数/纯逻辑（`utils/`、`shared-lib/`）：≥ 80%（等效于后端单元测试，ROI 最高）
  - 核心 Hook（`hooks/`）：≥ 60%
  - 关键组件（表单、列表、弹窗等交互密集组件）：有测试用例即可，不要求覆盖率
  - E2E 流程：加分项，不强制
- **原因**：前端 UI 组件测试的 ROI 远低于纯逻辑测试，强制 80% 整体覆盖率会导致大量低价值的 UI 快照测试，反而降低测试质量
- **CI 平台无关性**：美团内部使用内部 CI/CD 平台（非 GitHub Actions），评分时以"测试失败是否阻塞合并"为判断依据，而非检查特定 CI 配置文件是否存在
