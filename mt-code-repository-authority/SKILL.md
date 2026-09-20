---
name: mt-code-repository-authority
description: "执行平台签发的仓库地址来源扫描、负责人识别或组织核验任务，通过固定 Runner 读取学城、查询 Yuntu 组织链并逐项直回调平台。仅接受 CatX 挂载的版本化任务，不用于人工查人、任意组织搜索、订阅或 Git 写入。"
skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - Metrics

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V6"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "141227"
  skillhub.high_sensitive: "false"
---

# 仓库负责人组织权威解析

## 作用和边界

本 Skill 只执行平台生成并挂载到当前 CatX Session 的版本化任务。入口由平台消息中的 Schema 和
固定命令决定，不改写任务内容或自行添加人员。仓库识别使用 `repository-authority-task/v1`，
组织核验使用 `organization-refresh-task/v1`，两者的回调和数据库状态独立。

仓库识别通过固定 Runner 完成以下确定性流程。单仓任务继续使用
`repository-authority-task/v1`；`authority_shard` 继续使用
`repository-authority-task/v2`（执行合同 `mt-code-repository-authority/v3`）；`source_scan` 使用
`repository-authority-task/v3`（执行合同 `mt-code-repository-authority/v4`）：

1. 校验 task 原始字节 Hash、Schema、身份、仓库 canonical 字段、deadline 和 callback capability。
2. 在 Session 私有目录安装并验证锁定的 `@ee/yuntu-cli@1.0.15`。
3. 使用 `code-cli repo -R <canonical-key> view --json` 读取仓库负责人。
4. 使用 `mtsso-skills-official` 换取 audience 为 `Metrics` 的当前用户票据。
5. 只通过 `YUNTU_ACCESS_TOKEN` 向 Yuntu 子进程临时注入票据，并以 JSON 模式读取负责人组织链。
6. Yuntu 成功后再次读取同一 canonical 仓库，确认负责人 MIS 和默认分支没有在查询窗口内变化。
7. 将 `confirmed`、`unresolved` 或 `failed` 结构化结果直接回调平台。

数据库 job/attempt 是业务状态权威。Agent 回复、Session 状态、工具事件、安装日志、stdout 和结果文件都
不能推进平台状态。Runner 不查询或接收目标组织、规则领域和展示名称，避免把用户期待答案传给解析过程。

仓库负责人识别当前由共享 CatX 账号 `zhangce07` 执行；各看板用户无需单独绑定。Vault/credential 均未配置时使用
CatX 原生 SSO，Edge 创建 Session 时省略 `vault_ids`；两项均配置时，Edge 在派发前校验官方凭据状态
及 owner 并挂载共享 Vault。仅配一项、格式错误或显式凭据未就绪时停止派发，不自动降级。
`task.actor.mis` 保留真实任务发起人，当前用户票据指 CatX 运行环境的执行身份，不从 task 或浏览器构造票据。
Code 和 Metrics 所需权限由共享账号在官方系统取得；配置完整或网关占位符不表示真实授权有效。
Code/Yuntu 认证失败按既有合同回调，管理员恢复共享账号的 CatX 授权后才能重新发起，Runner 不自行改换账号或重试。
本 Skill 显式换取的 `Metrics` 票据仅供 Yuntu；`code-cli` 使用其自身认证机制。
验收必须在同一 Session 分别确认 Code 仓库读取、Metrics 换票和 Yuntu 查询成功，不能互相替代。

本 Skill 不执行仓库关联、组织认领、订阅、Git clone/commit/push、浏览器查询、`yuntu sso login` 或
任意员工搜索。组织核验只查询平台已冻结的 MIS 列表，不接受对话中补充的账号。IAM empId 增强已保留
仓库识别合同字段，当前版本固定为 `not_requested`，不阻断 Yuntu 组织确认。

## 固定执行入口

平台消息必须提供任务挂载路径、上传前计算的 task artifact Hash 和结果路径。
对于 `repository-authority-task/v1`，立即且只执行一次：

```shell
node <skill_dir>/scripts/run-repository-authority.mjs \
  --task /mnt/session/uploads/repository-authority-task.json \
  --task-artifact-hash '<sha256:64hex>' \
  --output /mnt/session/outputs/repository-authority-result.json
```

对于 `organization-refresh-task/v1`（执行合同 `mt-code-repository-authority/v2`），只执行对应入口：

```shell
node <skill_dir>/scripts/run-organization-refresh.mjs \
  --task /mnt/session/uploads/organization-refresh-task.json \
  --task-artifact-hash '<sha256:64hex>' \
  --output /mnt/session/outputs/organization-refresh-result.json
```

对于平台签发的 `repository-authority-task/v2`（仅 `authority_shard`）或
`repository-authority-task/v3`（仅 `source_scan`），立即且只执行一次：

```shell
node <skill_dir>/scripts/run-repository-authority-v3.mjs \
  --task /mnt/session/uploads/repository-authority-task.json \
  --task-artifact-hash '<sha256:64hex>' \
  --output /mnt/session/outputs/repository-authority-result.json
```

`mode=authority_shard` 时，一个 Session 最多包含 10 个仓库，Runner 固定使用两个 worker，
每个仓库使用独立 attempt capability 回调；单项失败不阻断其余项。`mode=source_scan` 时，
Runner 只接受 task 中平台核验的 `actor.mis`，以该 MIS 和 `sso-ciba` 发起当前用户的大象授权，
再只读调用 `oa-skills citadel getSimpleMarkdown`，并通过
`getDocumentJson` 和 `citadel-database listTables/getTableMeta` 枚举多维表及全部列，固定页面读取器
调用同一官方包的单页客户端接口逐页读取，不使用会隐藏分页错误的 CLI 全量缓存结果。
每个 attempt 使用权限为 `0700` 的私有认证缓存目录，受控子进程移除继承的 `SSO_CIBA_TOKEN` 并关闭
OIDC fallback；同一 attempt 的多次文档/表格读取复用该缓存，结束时由最外层 Runner 清理，不跨 attempt 复用。
运行环境必须提供 Node.js 24 与 `oa-skills`，且官方客户端支持 `queryTableDataSinglePage`。
旧结果合同只提取完整 MCode HTTPS/SSH 地址。新版
`repository-association-source-scan-result/v2` 提取地址原文并保留来源位置，覆盖 `sankuai.com`
根域或子域的 HTTP(S)、`ssh://git@host/path` 和 `git@host:path`；不在 Runner 内合并仓库身份，
不调用 Code/Yuntu，也不创建逐仓任务。参数和片段交由平台统一去除，线下 VIP、未知主机及大小写路径
也由平台统一判定，Runner 不按同路径猜测等价仓库。普通来源读取中断可保留已完成结果并返回
`partially_scanned`；本人拒绝/未完成认证、认证超时或文档 ACL 失败必须立即停止后续读取并返回
`failed`，不得继续触发授权或伪造全量完成。source scan 的 `actor.execution_mis` 与结果
`execution_mis` 都必须等于 `actor.mis`；MIS 只是 CIBA 发起参数，不能单独作为已认证主体证据，
最终授权仍由官方 CIBA/学城响应决定。

组织核验每个 Session 最多 10 人，顺序调用 Yuntu 的 `user org <mis>` 并逐项回调，不调用 Code。
单人查询失败会回传该项失败并继续其他项；认证失败不会切换账号。`dry_run` 与 `apply` 的区别由平台
数据库执行，Runner 两种模式都只读取来源并回调。输出文件仅包含本地回执，不能用它修改数据库状态。
平台收到回调后仍需汇总和核对同轮组织链；`result_status=observed` 不表示组织关系已应用。

不要读取 task 后自行重写参数，不要复制 Runner 内部命令，不要手工安装 Yuntu，不要在失败后改用
`drill-org-lookup`、`org-http`、浏览器或说明文本解析。命令非零退出时也不要重跑；平台依据数据库 deadline
和 append-only attempt 提供重试。

单仓 Runner 的成功 stdout 只是 `repository-authority-local-receipt/v1` 本地传输回执（批量为 v2）。真正完成必须是受限 Edge
callback 返回 `repository-authority-callback-receipt/v1` 的 `accepted` 或 `duplicate`，并由平台重新读取
数据库 job 状态。

学城扫描按 deadline 有界执行并预留回调时间；超时保留已发现结果并报告部分读取。来源结果分段回调，
不限制总仓库数量，每段核对 shard/generation/chunk 和 canonical Hash；不同结果不能伪装成幂等重放。
新版结果固定分为 `candidates,invalid_items,read_errors`：候选项和无效项均含 `raw_value` 与
`source_locations`，读取错误含 `source,error_code,retriable`。Runner 仅按地址形状提取，候选是否合法由
Edge 唯一 normalizer 判定；`invalid_items` 只承载过长等提取层错误。无效地址本身不表示学城读取不完整；
只有 `read_errors` 会把扫描降级为 `partially_scanned` 或 `failed`。用户确认前 Runner 没有绑定能力。

组织核验必须收到 `organization-refresh-callback-receipt/v1`，并同时校验 attempt、invocation、Hash
及 `result_status`。回调可在原 deadline 内有限重送相同结果；不得重新查询并修改已经提交的结果。
平台根据数据库 run/item/attempt 状态提供重试，旧批次不能覆盖较新的核验事实。

## 安全规则

- 用户票据必须来自官方 `mtsso-moa-local-exchange --audience Metrics`。`exit=42` 和官方权限错误禁止重试。
- CatX 网关的 `AT_FOR_GW_BASE64_...` 是合法票据占位符，不得把它误判成非 JWT。
- 票据不能进入 task、CLI 参数、结果文件、callback body、日志或回复；只进入单次 Yuntu 子进程环境。
- callback token 只用于 task 指定的 HTTPS host、attempt 路径和 Idempotency-Key，不得发送到其他地址。
- `code-cli` 和 Yuntu 均由 Node `execFile` 参数数组调用，不经过 shell；`~namespace/repository` 不得展开。
- Yuntu stdout 必须整体是 UTF-8 JSON。不得从前后夹杂的解释、Markdown 或日志中截取 JSON。
- 组织 `fullPath` 只用于交叉校验和展示；身份与层级以逐项配对的 `orgIdPath`/名称 chain 为准。
- `/` 是组织路径分隔符，叶子名称和 chain 的单级组织名称中不得包含 `/`，当前不定义转义协议。

跨层 Schema、状态含义和稳定错误码见 [references/contracts.md](references/contracts.md)。只有排障合同或修改
Runner 时才需要读取该文件；普通执行只运行上面的固定命令。
