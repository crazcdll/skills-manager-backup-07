# Repository authority Runner contracts

## 固定版本

- Skill/Runner：`mt-code-repository-authority/v1`
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
