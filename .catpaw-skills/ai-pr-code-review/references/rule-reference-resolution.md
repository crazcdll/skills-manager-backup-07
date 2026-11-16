# 规则引用解析 (Reference Resolution)

> 适用于加载 `.mdp/rules/team/`、`.mdp/rules/project/`、`.catpaw/rules/` 目录下自定义规则的 Step。

## 背景

各团队知识库目录路径不同（如 `.knowledge/product/rules/`、`docs/team-rules/` 等），要求所有团队在 `.mdp/rules/` 下重复维护一份规则不现实。

规则引用解析机制允许各团队在 `.mdp/rules/` 下放一个**索引文件**，指向各自知识库目录中的规则文件，Skill 读到索引文件后自动解析路径并读取目标文件内容，合并注入 Layer 3。

## 判定索引文件的规则

读取 `.mdp/rules/team/` 或 `.mdp/rules/project/` 下的 `.md` 文件后，判断是否为索引文件：

1. 文件正文行数 ≤ 50 行
2. 非空行中 ≥ 80% 以 `- ` 开头或匹配路径模式（含 `/` 且以 `.md` 结尾）
3. 无完整的段落式规则描述（排除 H1/H2/H3 标题 + 正文段落的传统规则文件）

**是索引文件** → 解析路径，逐个读取目标文件内容，合并注入
**不是索引文件** → 按原逻辑作为规则文件直接注入

## 索引文件示例

`.mdp/rules/team/index.md`:

```markdown
# 规则索引

- .knowledge/product/rules/tenant_cr_rule.md
- .knowledge/product/rules/sku_cr_rule.md
- .knowledge/product/rules/common_cr_rule.md
- ../shared/rules/logging_rule.md
```

## 解析逻辑

1. 逐行扫描索引文件内容
2. 提取以 `- ` 开头的路径，或纯路径行（含 `/` 且以 `.md` 结尾）
3. 对每个路径：
   - 本地 CR（forlocal）：直接 `cat "$LOCAL_REPO_PATH/$path"` 读取
   - 远程 CR：调 `repo_search` 或 `read file` API 读取
4. 将所有目标文件内容合并，每个文件前加 `## 文件名` 作为分隔标题
5. 与非索引文件的内容一起合并写入规则缓存文件

## 注意事项

- 索引文件中的路径为**仓库内相对路径**（相对于仓库根目录）
- 支持子目录路径（如 `.knowledge/product/rules/xxx.md`）
- 不支持绝对路径和仓库外路径（安全限制）
- 目标文件不存在时静默跳过，不阻断流程
- 索引文件自身不作为规则内容注入（只做路径指引）
