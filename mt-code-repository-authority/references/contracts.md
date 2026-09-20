# Repository authority Runner contracts

## 固定版本

- 仓库识别执行合同：`mt-code-repository-authority/v1`（保持原合同）
- 组织核验执行合同：`mt-code-repository-authority/v2`（独立入口，见下文）
- 批量来源扫描/分片执行合同：`mt-code-repository-authority/v3`（兼容上述入口，见下文）
- task：`repository-authority-task/v1`
- result：`repository-authority-runner-result/v1`
- callback receipt：`repository-authority-callback-receipt/v1`
- Yuntu：`@ee/yuntu-cli@1.0.15`
- MTSSO audience：`Metrics`

task 只包含 `job_id`、`attempt_id`、`runner_invocation_id`、`request_hash`、可信 actor、canonical 仓库、
deadline 和 callback。完整 task artifact Hash 由 Edge 对上传字节计算，通过 Runner 的
`--task-artifact-hash` 参数传入，避免 JSON 自包含 Hash 的循环定义。task 禁止包含目标组织、展示名称或规则领域。

## Result

result 顶层固定 12 个字段：

```json
{
  "schema_version": "repository-authority-runner-result/v1",
  "attempt_id": "uuid",
  "runner_invocation_id": "uuid",
  "request_hash": "sha256:...",
  "task_artifact_hash": "sha256:...",
  "execution_status": "succeeded",
  "resolution_status": "confirmed",
  "repository": {
    "canonical_key": "namespace/repository",
    "default_branch": "master"
  },
  "owner": {
    "mis": "owner-mis",
    "display_name": "负责人",
    "iam_emp_id": null,
    "identity_enrichment_status": "not_requested"
  },
  "organization": {
    "source_system": "yuntu_org",
    "source_organization_id": "123",
    "display_name": "组织",
    "full_path": "根组织/子组织/组织",
    "chain": [
      { "source_organization_id": "1", "display_name": "根组织" },
      { "source_organization_id": "2", "display_name": "子组织" },
      { "source_organization_id": "123", "display_name": "组织" }
    ]
  },
  "evidence": {
    "skill_contract_version": "mt-code-repository-authority/v1",
    "ee_code_cli_version": "0.1.27",
    "yuntu_cli_version": "1.0.15",
    "account_mapping_contract_version": null,
    "verified_at": "ISO-8601",
    "timings_ms": {
      "runtime_install_ms": 1000,
      "repository_lookup_ms": 100,
      "metrics_token_exchange_ms": 100,
      "yuntu_lookup_ms": 100,
      "identity_enrichment_ms": null,
      "total_ms": 1300
    }
  },
  "error": null
}
```

状态组合只有三种：

| execution_status | resolution_status | owner | organization | error | 含义 |
| --- | --- | --- | --- | --- | --- |
| `succeeded` | `confirmed` | 完整 | 完整 | `null` | 负责人和组织链通过校验 |
| `succeeded` | `unresolved` | `null` 或完整 | `null` | 稳定错误 | 来源没有可确认的负责人/组织 |
| `failed` | `null` | `null` | `null` | 稳定错误 | 安装、认证、CLI、网络或合同执行失败 |

`identity_enrichment_status` 预留 `not_requested | resolved | unavailable`。当前 Runner 只产生
`not_requested + iam_emp_id=null`；未来 `resolved` 必须有 IAM empId，`unavailable` 仍不阻断组织确认。

`timings_ms` 未执行的阶段为 `null`，已执行阶段和 `total_ms` 是非负整数。`verified_at` 是观测时间；数据库
接收时间才是平台权威时间。Edge/RPC 必须从 `organization.chain` 重建层级，不能从 `full_path` 拆分身份。
单级组织名称不得包含作为路径分隔符的 `/`；在设计转义协议前必须失败关闭。

Yuntu 结果通过后，Runner 必须再次读取同一 canonical 仓库。owner MIS 变化返回 succeeded/unresolved 的
`repository_owner_changed`；默认分支变化返回 `repository_state_changed`。第二次读取耗时累加到既有
`repository_lookup_ms`，不新增跨层 timing 字段。

## Callback

- URL：`/functions/v1/rule-observability/internal/repository-authority/attempts/{attempt_id}/result`
- Bearer：attempt 级短期 capability，只在数据库保存 SHA-256。
- Idempotency-Key：`{attempt_id}:{runner_invocation_id}`。
- callback body 使用递归 key-sort 的 canonical JSON，`result_hash` 对同一 canonical 字节计算 SHA-256；不得
  使用 JavaScript 对象插入顺序作为跨语言 Hash 输入。
- 同 body 重放返回 `duplicate`；不同 body 或旧 attempt 返回冲突。
- receipt 精确字段：`schema_version,status,attempt_id,runner_invocation_id,result_hash`。
- Runner 只认可 `accepted | duplicate`；HTTP 2xx 本身不表示完成。

## 稳定错误分类

错误只跨层传递 `phase`、`error_code`、`retriable`，不得携带 stdout、stderr、Token、员工原始响应或堆栈。

| phase | 典型 error_code | retriable |
| --- | --- | --- |
| `task_validation` | `task_invalid`、`task_hash_mismatch` | false |
| `runtime_install` | `runtime_install_timeout`、`runtime_install_failed` | 仅临时网络错误 |
| `repository_lookup` | `repository_owner_not_found` | false，属于 unresolved |
| `repository_lookup` | `repository_owner_changed`、`repository_state_changed` | false，属于 unresolved |
| `repository_lookup` | `repository_lookup_failed` | 按超时/网络分类 |
| `metrics_token_exchange` | `metrics_user_authorization_required` | false |
| `yuntu_lookup` | `organization_not_found` | false，属于 unresolved |
| `yuntu_lookup` | `organization_identity_mismatch`、`organization_path_invalid` | false |
| `callback` | `callback_timeout`、`callback_network_error` | true |
| `callback` | `callback_unauthorized`、`callback_conflict` | false |

Agent 回复和本地文件不参与错误状态判断。Runner 无法送达 callback 时，数据库 finalizer 按 deadline 将 attempt
关闭为超时；诊断结果文件写入失败也不得阻止 callback。不得读取 CatX Session 的自然语言结束语补写结果。

## 组织核验合同

这是独立入口 `scripts/run-organization-refresh.mjs`，不改变仓库识别 v1 的字段或行为。

| 层级 | Schema | 关键字段 |
| --- | --- | --- |
| 挂载任务 | `organization-refresh-task/v1` | `skill_contract_version=mt-code-repository-authority/v2`、`run_id`、`generation`、`mode`、`actor`、`execution`、`items` |
| 单人结果 | `organization-refresh-item-result/v1` | run/generation/item/attempt/invocation/MIS/request Hash、执行状态、组织链、核验时间、版本、错误 |
| 回调回执 | `organization-refresh-callback-receipt/v1` | `status`、`result_status`、`attempt_id`、`runner_invocation_id`、`result_hash` |
| 本地回执 | `organization-refresh-local-receipt/v1` | run/generation、逐项传输状态，不包含 Token 或原始员工响应 |

`items` 最多 10 项，每项固定为 `item_id,attempt_id,runner_invocation_id,principal_mis,request_hash,callback`。
人员、item、attempt 和 invocation 在同一任务中唯一。`actor` 是 `{mis,source:"verified-edge"}`；
`execution` 是 `{deadline,expected_result_schema:"organization-refresh-item-result/v1"}`。
artifact Hash 校验原始 UTF-8 字节；task 不得超过 64 KiB，接收时剩余有效期最多 25 分钟。

每个 item 使用自己的 capability，地址固定为：

```text
https://db0y7dgg85gphojyva.database.sankuai.com/functions/v1/rule-observability/internal/organization-refresh/attempts/{attempt_id}/result
```

callback 不接受重定向或其他主机，Idempotency-Key 固定为 `{attempt_id}:{runner_invocation_id}`。
对同一 canonical 结果最多发送三次，只有网络错误、408/425/429/5xx 可以重送；原查询不重跑。
每次发送同时受请求总时限和任务 deadline 限制。回执必须匹配原身份和结果 Hash；成功查询只接受
`result_status=observed`，失败查询只接受 `failed`。`accepted/duplicate` 均不代表数据库已应用关系变更。

成功项的 `organization` 固定为 `source_organization_id,display_name,full_path,chain`，每级 chain
仅含 `source_organization_id,display_name`。失败项组织为 `null`，错误仅含 `phase,error_code,retriable`。
共享运行环境或换票失败时仍逐项报告失败；单项无组织、返回其他 MIS 或查询失败不得推断为离职或无人组织。
来源没有提供修订号，`verified_at` 仅记录采样时间，平台应通过 run generation、当前 attempt 和同轮链一致性
控制应用顺序，不能按回调到达时间覆盖关系。

部署需要分别更新 Friday 的 `mt-code-repository-authority` 和 CatX 实际安装的技能包。Skill 包包含两个
Runner，但仓库识别继续使用 v1 执行合同；v2 表示新增组织核验能力，不表示 Friday 安装版本号。
先部署数据库迁移与具备新入口的技能包，再启用 Edge 组织核验；初次启用保持 `dry_run`，真实无人值守
Metrics 换票和来源权限需另行验证。本机模拟测试不等于已部署定时任务。

## 批量仓库任务合同

入口 `scripts/run-repository-authority-v3.mjs` 按 mode 接受两个不混用的合同：
`authority_shard` 保留 `repository-authority-task/v2` + `mt-code-repository-authority/v3`；
`source_scan` 仅接受 `repository-authority-task/v3` + `mt-code-repository-authority/v4`。
这些版本均不代表 Friday 的安装版本号。
顶层字段固定为 `schema_version,skill_contract_version,mode,shard_id,generation,actor,execution,payload`。
authority shard 的 `actor.execution_mis="zhangce07"`；source scan 的
`actor.execution_mis=actor.mis`，且 `actor.source="verified-edge"`。旧 v2/v3 的 source scan 任务拒绝执行，
避免把共享读取身份静默重解释为个人授权。
所有任务仍校验原始字节 Hash、允许的回调 host/path、最多 64 KiB 和最多 15 分钟有效期。

- `authority_shard`：payload 是 1 至 10 个仓库。Session 内两个 worker；每仓独立
  `item_id,job_id,attempt_id,runner_invocation_id,request_hash,repository,callback`。查询/认证错误
  按仓回调，回调失败不阻断其他仓库，不自动重跑该仓库。evidence 执行版本必须是 v3；结果/回执
  继续使用现有单仓 Schema，并由数据库读取当前 attempt 判断成功。
- `source_scan`：payload 为 `run_id,scan_revision,citadel_url,callback`。固定只读调用 Citadel
  简化 Markdown（含普通表格）、底层 JSON 的内嵌表格引用及 Citadel Database 元数据，
  显式读取全部列，固定读取器调用官方 `XTableClient.queryTableDataSinglePage` 逐页查询。
  不消费 CLI 全量自动翻页的空 rows/缓存文件回执，以免遗漏数据或吞掉读取错误。
  运行环境必须安装 Node.js 24、`oa-skills`，且客户端提供上述单页能力；顺序读取加入短暂抖动。
  旧结果合同仅解析完整 MCode HTTPS/SSH 地址。新版结果合同提取地址原文，不把裸名、文档说明或
  嵌入指令作为执行请求，也不在 Runner 内解析仓库身份或调用 Code/Yuntu。
  使用平台核验的 `actor.mis` 和 `sso-ciba` 发起当前用户大象授权；attempt 内创建 `0700` 私有
  `AUTH_CACHE_FILE`，清除受控子进程继承的 `SSO_CIBA_TOKEN`、关闭 OIDC fallback，并在最外层 Runner
  的 `finally` 中清理。多次读取在同一 attempt 复用认证，不跨 attempt 复用。单次读取有超时/缓冲限制，
  扫描预留一分钟回调时间；普通中断可保留已发现地址并报告未读来源，不将 `partially_scanned` 宣称为全量成功。
  CIBA 等待/拒绝/失败/超时或文档 ACL 失败则立即停止后续文档和表格读取，结果为 `failed`，提示用户
  在大象完成确认或取得文档权限后新建 attempt。传入 MIS 不等同于已认证主体，授权事实仅来自官方响应。

历史来源结果 Schema `repository-authority-source-scan-result/v1` 曾包含
`run_id,shard_id,generation,scan_revision,execution_mis,scan_status,repositories,issues,chunk_index,is_final`。
该 v1 结果仅作为历史合同记录，新的 v3/v4 source scan task 不再接受。历史地址和错误结果曾按最多
500 项且约 240 KiB 分段，顺序提交，**总仓库数不设上限**。
回调 URL 固定为 `/functions/v1/rule-observability/internal/repository-association/runs/{run_id}/source-result`，
Bearer 是 shard/generation 级 capability，Idempotency-Key 为 `{shard_id}:{generation}`。
每个 chunk 的 canonical Hash 绑定数据库分段记录；同段同 Hash 返回 duplicate，不同 Hash 返回 409，
只有 final 段才能将扫描置为 ready/failed。重送最多三次，仅对传输临时错误进行。

来源回执 Schema `repository-authority-source-scan-callback-receipt/v1`；Runner 校验
`status,run_id,shard_id,generation,chunk_index,result_hash`，HTTP 2xx 自身不是成功凭据。
本地回执 `repository-authority-local-receipt/v2` 仅记录传输结果。平台必须重新读取数据库状态，
旧合同的部分读取必须由用户显式确认后才能开始负责人识别。旧合同最终关联在平台逐仓独立提交，
不创建新 Session。

简化绑定使用 `repository-authority-task/v3` 和 `mt-code-repository-authority/v4` 顶层合同，
通过 `execution.expected_result_schema=repository-association-source-scan-result/v2` 选择结果；旧任务版本
不再执行 source scan。结果中的 `execution_mis` 必须等于 `actor.mis`。v2 结果固定包含
`run_id,shard_id,generation,scan_revision,execution_mis,scan_status,chunk_index,is_final,candidates,invalid_items,read_errors`：

- `candidates[] = {raw_value,source_locations[]}`，按地址形状保留原文，由 Edge 使用唯一 normalizer 去参数、校验和解析 alias；
- `invalid_items[] = {raw_value,source_locations[],error_code}`，仅承载过长等提取层错误，不替代 Edge 地址校验，也不降低读取完整性；
- `read_errors[] = {source,error_code,retriable}`，决定 `partially_scanned/failed`，不能被成功候选掩盖。

三类记录合计每段最多 500 项且约 240 KiB，总数不设上限。v2 的 Idempotency-Key 固定为
`{shard_id}:{generation}:{chunk_index}`，回执为
`repository-association-source-scan-callback-receipt/v2`，继续严格核对全部身份和 canonical body Hash。
Runner 只读并分段回传，不能绑定仓库；用户确认后由平台直接批量绑定，不创建逐仓 authority task。
