# 规则加载策略

审查规则按可信度和适用范围依次加载。附加能力模块仍固定读取本 Skill 自带文件，不参与同步。

## 1. 当前组织 / 仓库有效规则（首选）

宿主存在 `RULE_OBSERVABILITY_USER_TOKEN` 时，先识别技术栈，再执行：

```bash
node <skill_dir>/scripts/resolve-effective-rules.mjs \
  --scope <auto|organization|repository> \
  --stage cr \
  --domain frontend \
  --tech-stacks <react,vue,mrn,general> \
  --format markdown \
  --output <skill_dir>/.rules-cache/effective-rules.md
```

- `auto`：本地仓库或 PR 仓库与当前组织登记仓库精确匹配时走 `repository`；否则走
  `organization`。
- `repository`：服务端按 `repository_direct > organization_direct > organization_inherited`
  选择已发布 L1/L2。
- `organization`：只读取当前组织直接/继承订阅，不混入任何仓库直订阅；L1 使用仓库受管文件
  或签名包兜底。
- 当前组织来自服务端核验用户会话，输出 `org_name_path`；不得用 Git/PR 作者或手工 MIS 代替。
- 用户会话只从环境读取，禁止写入命令、日志、报告和缓存。默认无浏览器 fallback。

成功后读取 `.rules-cache/effective-rules.md`。本地模式还要追加读取业务仓库
`.mdp/rules/project/fe/*.md` 中的 L3；服务端快照不包含 L3。

准备信息必须说明：规则作用域、当前组织路径、可选仓库身份、规则数、releaseRefs，以及是否发生
降级。不得只写“已加载远程规则”。

## 2. 业务仓库 `.mdp` 回退

首选链路因缺少可信会话、组织未解析、仓库未登记或网关不可用而失败时，本地模式按顺序读取：

1. `.mdp/rules/company/fe/*.md`
2. `.mdp/rules/team/fe/*.md`
3. `.mdp/rules/project/fe/*.md`

只读受版本管理文件，忽略 source manifest。必须提示：

```text
ℹ️ 当前组织/仓库订阅未刷新，本次使用仓库内 .mdp 规则。
```

PR-only 没有本地仓库时跳过本层。

## 3. 旧远程规则源回退

前两层都没有可用规则时，清理 `<skill_dir>/.rules-cache/legacy/` 后执行：

```bash
git clone --depth 1 -b feature/rules-init \
  ssh://git@git.sankuai.com/mcp/ai-cr.git \
  <skill_dir>/.rules-cache/legacy
```

成功时读取 `.rules-cache/legacy/rules/frontend/`；失败时进入签名包兜底。旧远程源不含当前组织/
仓库订阅语义，准备信息必须明确标记 `legacy_remote_fallback`。

## 4. 签名包兜底

最终读取本 Skill 的 `references/rules/`：

- `base/general-rules.md`
- `base/trade-rules.md`
- 按技术栈选择 `stack/mrn-rules.md`、`stack/max-rules.md`、
  `stack/miniprogram-rules.md`、`stack/duo-rules.md`

并提示：

```text
ℹ️ 规则网关、仓库 .mdp 和旧远程规则均不可用，本次使用签名包兜底规则（可能非最新版本）。
```

## 5. 附加能力模块

以下流程说明固定读取本 Skill，不走任何远程同步：

- `references/rules/base/dep-upgrade-rules.md`
- `references/rules/base/msi-api-review-rules.md`

## 6. 安全与停止条件

- 401/403、身份未验证、组织不明确时失败关闭；不打开浏览器，不读取 Cookie。
- `repository` 模式仓库未登记时不得静默降为其他仓库；只有 `auto` 才允许降为组织作用域。
- 网络失败只触发一次分层回退，不高频重试。
- 缓存不得包含 token；每次审查开始前清理旧的有效快照文件。
