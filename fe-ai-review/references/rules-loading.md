# 规则加载

在本地模式或 PR-only 模式的 Step 2 读取本文件。

## 同步与读取

1. 确认审查对象对应的本地 Git 仓库；PR-only 使用已校验的本地 checkout。
2. 读取 `mt-code-standards-setup`，再运行它的官方 Runner：

```bash
node <skill_dir>/scripts/sync-effective-rules-with-sso.mjs \
  --repo-root "<repo_root>" \
  --execution-agent "<当前执行环境>"
```

3. 退出码为 `0`，且 receipt 的 `schema_version` 为 `mt-effective-rule-bundle-install/v1`、状态为 `installed` 或 `not_modified` 时，读取 L1/L2。
4. 无论 Runner 结果如何，读取 `.mdp/rules/project/**/*.md` 中存在的 L3 项目规则。
5. Runner 失败时，读取 [`rules/fallback-rules.md`](rules/fallback-rules.md)，继续使用 L3 和 fallback 规则审查；在 `rule_bundle.fallback.active` 标记 `true`。

Runner 负责认证、下载、校验和原子写入。不要自行请求规则平台。

## 规则范围

- **L1**：manifest `managed_files` 中的 `company/*.md`。
- **L2**：manifest `managed_files` 中的 `team/<规则集 ID>/*.md`。
- **L3**：`.mdp/rules/project/**/*.md`。`project/` 下的首级目录作为 `rule_set_id`。
- 审查范围排除 `.mdp/rules/**`，规则文件不属于业务变更。

先读每份规则的标题、适用范围和目录；再结合 diff、技术栈和调用链补读相关章节。

## 统一规则标识

两个看板共用 `rule_sources`。每个命中规则记录：

- `source_type`：`platform`、`project` 或 `fallback`
- `scope_level`：`L1`、`L2`、`L3` 或 `FALLBACK`
- `rule_set_id`
- `rule_version`
- `file`、`title`、`section`
- `upstream_rule_id`：平台提供时填写

`rule_version` 取值：L1/L2 使用 `release_id`；L3 使用规则文件 `shasum -a 256` 的结果；fallback 使用 `fallback-rules.md` 顶部声明的版本。

上报脚本按上述字段生成并校验 `rule_id`。两个看板都使用这个 `rule_id` 和完整的 `rule_sources`，不各自转换规则 ID。

报告正文使用：

```text
【规则：<source_type>/<scope_level> / <rule_set_id>@<rule_version> / <file>#<title>】
```

上报 CR 看板前读取 [`report-submit.md`](report-submit.md)。质量门禁接口提供前，只上报现有看板；接口提供后复用同一份标准化 payload 发起第二个请求。