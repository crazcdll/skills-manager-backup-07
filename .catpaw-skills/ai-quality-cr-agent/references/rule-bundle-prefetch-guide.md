# 平台 L2 预取指南

执行步骤见 [SKILL.md 的 Step 2I](../SKILL.md#2i-规则包后台预取mt-code-standards-setupl2-团队规范正式链路)。

- 主流程按 `ORG/REPO` 调用 `mt-code-standards-setup` 公开的 `sync-effective-rules-with-sso.mjs`。Runner 在独立临时目录安装规则;业务仓无需 clone,鉴权沿用 Runner。
- `backend` 显式传后端领域;`mixed`、`general` 由平台按仓库登记领域返回规则。比如登记为 `frontend` 的 Android 仓库仍取登记领域的团队规则。纯前端由 FE 自己获取平台规则。
- 主流程只读取平台正式包的 `mt-rule-bundle-install/v1` 回执和对应的安装清单，按 `managed_files` 中的路径读取 L2 正文。正式包 L2 路径为 `team/fe/<规则集>/…` 或 `team/java/<规则集>/…`；规则集 ID 取自清单记录的归属，不从目录名推导 Release。
- L1 和 `AGENTS.md` 索引仅由 Runner 临时安装。主流程保留通过校验的 L2 正文;仓库自定义规则继续使用 Step 3C 的独立缓存。

| 状态 | 含义 | 退出码 |
|---|---|---|
| `loaded` | 本轮 L2 正文校验通过,可交给审查 | 0 |
| `no_team_rules` | 确认本轮没有生效的 L2,或仓库未登记 | 0 |
| `fetch_failed` | 依赖缺失、超时、拉取错误、权限不足或正文不完整 | 3 或 4 |
| `domain_unresolved` | 平台不能确定规则领域 | 5 |
| `not_started` / `running` | 尚未启动或进程执行中;收割未完成记覆盖缺口 | — |

输出位于各仓本轮的 `$CR_RUN_DIR/rule_bundle/`: `manifest.json` 记录状态、错误码、平台请求和快照标识(若有)。`loaded` 的 `rules_path` 指向 `l2_rules.md`,正文按 `## {规则集ID}/{文件名}` 分段;`files` 列出这些段落对应的 release。Step 4-C 使用该正文检查本轮变更,命中时沿用 `L2:{规则集ID}:{稳定编号}`。

排查时先核对本轮回执的仓库、领域、状态和正文,再用 `pull_id` 或 `request_id` 对平台拉取记录。平台返回 `l2_not_accessible` 或拉取失败时,继续检查已取得的仓库规则并记录缺口。`loaded` 只证明正文已交付;审查是否引用或命中规则,须看审查结果。
