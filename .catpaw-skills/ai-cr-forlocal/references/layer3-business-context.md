# Layer 3 业务语义加载指南（Step 2C）

### 2C. Layer 3 — 业务语义

加载顺序（**三层叠加注入，编号越大越贴近当前仓库实际，优先用于业务语义判断**）：

1. **Skill 内置通用规则**（所有团队共享，**加载前必须显式检测文件存在性**）：
   ```bash
   # 使用 Step 0A 设置的 $SKILL_ROOT
   for ref in zero-tolerance-checklist.md stability-security-checklist.md coe-rules.md; do
     if [ -f "$SKILL_ROOT/references/$ref" ]; then
       cat "$SKILL_ROOT/references/$ref"
     else
       echo "⚠️ [3C] references/$ref 不存在，跳过（请检查 Skill 安装完整性）"
     fi
   done
   ```
   - `references/zero-tolerance-checklist.md` — P0 零容忍
   - `references/stability-security-checklist.md` — P1 稳定性
   - `references/coe-rules.md` — 历史 COE 提炼规则

2. **团队领域知识库**（Step 0 从 `cr-config.yaml` 加载路径，默认 `references/domain-knowledge.md`）：
   ```bash
   # $DOMAIN_KNOWLEDGE_PATH 由 Step 0 设置
   cat "$DOMAIN_KNOWLEDGE_PATH" 2>/dev/null || echo "（未找到领域知识库，跳过）"
   ```
   内容：ID 体系、业务核心概念、双平台规范、团队特有 P0/P1 规则、命名规范

3. **仓库级 spec 文档**（双源合并，权威性最高）：

   > **spec 文件两种来源都要读，合并去重后注入 Layer 3。**

   **来源 0 — FEATURE_SPEC 环境变量**（最高优先级，AI-SDLC 平台直接传入）：
   ```bash
   if [ -n "$FEATURE_SPEC" ] && [ -f "$FEATURE_SPEC" ]; then
     echo "=== FEATURE_SPEC: $FEATURE_SPEC ==="
     cat "$FEATURE_SPEC"
   else
     echo "（FEATURE_SPEC 未设置或文件不存在，跳过）"
   fi
   ```

   **来源 A — master 分支存量 spec**（本地文件系统）：
   ```bash
   find "$LOCAL_REPO_PATH/specs" -name "*.md" 2>/dev/null
   find "$LOCAL_REPO_PATH/.mdp/context" -name "*.md" 2>/dev/null
   find "$LOCAL_REPO_PATH/.mdp/rules/team" -name "*.md" 2>/dev/null
   find "$LOCAL_REPO_PATH/.mdp/rules/project" -name "*.md" 2>/dev/null
   find "$LOCAL_REPO_PATH/docs/superpowers/specs" -name "*.md" 2>/dev/null
   find "$LOCAL_REPO_PATH/docs/superpowers/plans" -name "*.md" 2>/dev/null
   # 有结果 → 逐文件 cat 读取；无结果 → 该来源为空
   ```

   **来源 B — feature 分支新增 spec**（从变更文件列表过滤）：
   ```bash
   grep -E '^(specs/|\.mdp/context/|\.mdp/rules/team/|\.mdp/rules/project/|docs/superpowers/specs/|docs/superpowers/plans/).*\.md$' \
     /tmp/local_cr_files.txt 2>/dev/null | while read -r filepath; do
     echo "=== $filepath ==="
     cat "$LOCAL_REPO_PATH/$filepath" 2>/dev/null
   done
   ```

   **合并与优先级**：同名文件以来源 B 为准（代表最新设计意图）；不同文件合并叠加。

   **🔗 规则引用解析（Reference Resolution)**:
   若 `.mdp/rules/team/` 或 `.mdp/rules/project/` 下的某个 `.md` 文件是索引文件（仅包含引用路径），则自动解析路径并读取目标文件内容合并注入 Layer 3。

   **优先读取顺序**：
   1. `specs/*/spec.md` / `specs/*/design.md` — 需求规范 + 技术方案（最高价值）
   2. `.mdp/context/*.md` — 领域知识、业务概念、状态机
   3. `.mdp/rules/team/*.md`、`.mdp/rules/project/*.md` — 团队/项目规则
   4. `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` — Superpowers 设计文档
   5. `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md` — Superpowers 实现计划

   > 💡 **MDP-Context 接入**：根目录有 `.mdp/` 的仓库自动识别，无需在 `cr-config.yaml` 配置。

   **来源 C — GitNexus 语义搜索（`$GITNEXUS_AVAILABLE=true` 时，补充发现）：**

   ```bash
   cd "$LOCAL_REPO_PATH"
   # 语义搜索仓库内散落的设计文档和领域知识
   gitnexus query "设计文档 技术方案 状态机 ID体系" --content -l 5 2>/dev/null
   ```

   不受目录约定限制，对没有 `specs/` 或 `.mdp/` 规范的旧仓库也能发现有价值的业务语义。
   与来源 A/B 合并去重后注入 Layer 3。GitNexus 不可用时跳过。

4. **ONES 验收条件**（有 ONES ID 时从 Step 1 注入）

5. **Whitebox 测试点**（`SPECS_DIR` 环境变量指定路径）：

   > **来源**：`whitebox-logic-review` Skill 根据产品需求逻辑生成的功能检查点，代码必须实现所有功能点。

   ```bash
   if [ -n "$SPECS_DIR" ] && [ -f "$SPECS_DIR/testpoints.json" ]; then
     echo "=== Whitebox 测试点: $SPECS_DIR/testpoints.json ==="
     cat "$SPECS_DIR/testpoints.json"
   else
     echo "（SPECS_DIR 未设置或 testpoints.json 不存在，跳过）"
   fi
   ```

   **用途**：在 Step 4-A P0 审查中，逐条验证代码是否实现了所有测试点。未实现的测试点 → **P0 issue**。

---
