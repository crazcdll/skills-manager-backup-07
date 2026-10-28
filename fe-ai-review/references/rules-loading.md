# 规则加载

在本地模式或 PR-only 模式的 Step 2 读取本文件。

## 首次调用

1. 有匹配业务仓库时，将其作为规则工作目录；没有时，创建独立规则临时目录，无需 `git init`，以 PR、已有 remote 或上游已确认的 `{org}/{repo}` 标识仓库。记录规则输出目录，后续读取其中的 `.mdp/rules/`；业务代码拉取失败不跳过规则同步。
2. 先通过宿主的 Skill 加载入口加载 `mt-code-standards-setup`，读取其 `SKILL.md`，使用加载结果返回的安装目录替换 `<setup_skill_dir>`。Runner 是该目录下的 `scripts/sync-effective-rules-with-sso.mjs`，不属于 `fe-ai-review`。加载失败、未返回可定位的安装目录或 Runner 不存在时，记录依赖缺失并进入失败处理，不去 FE 目录或猜测的兄弟目录尝试。
3. 首次调用就传入 `--repository`、`--output-dir`、`--domain frontend`、`--stage cr` 和已知宿主的 `--execution-agent`。子 Agent 沿用宿主标识，不填 Agent 名或 Skill 名：

| 执行环境 | 标识 |
|---|---|
| 1024 / CatPaw Studio（包括其中的子 Agent） | `agent_1024` |
| CatPaw IDE / CatDesk | `catpaw` / `catdesk` |
| Claude Code / Codex | `claude` / `codex` |
| CatX / 独立 sandbox | `catx` / `sandbox` |

下方命令适用于 1024 / CatPaw Studio（含子 Agent）；其它已知宿主只替换 `agent_1024` 为上表中的标识。仅确实无法确认宿主时省略 `--execution-agent`，交由 Runner 识别。先替换全部占位符再执行，保存完整 stdout、stderr 和退出码，勿直接管道到 `tail`：

```bash
RULE_RUN_LOG=$(mktemp -d "${TMPDIR:-/tmp}/fe-rule-sync.XXXXXX") || exit 1
RULE_RUN_PHASE=preflight
if [ ! -f "<setup_skill_dir>/scripts/sync-effective-rules-with-sso.mjs" ]; then
  : > "$RULE_RUN_LOG/stdout.json"
  printf '%s\n' 'setup_runner_missing: mt-code-standards-setup Runner 不存在，未发起规则调用' > "$RULE_RUN_LOG/stderr.log"
  RULE_RUN_EXIT=127
else
  RULE_RUN_PHASE=runner
  if node "<setup_skill_dir>/scripts/sync-effective-rules-with-sso.mjs" \
    --repository "<org/repo>" \
    --output-dir "<规则输出目录>" \
    --domain frontend \
    --stage cr \
    --execution-agent agent_1024 \
    > "$RULE_RUN_LOG/stdout.json" 2> "$RULE_RUN_LOG/stderr.log"; then
    RULE_RUN_EXIT=0
  else
    RULE_RUN_EXIT=$?
  fi
fi
printf '%s\n' "$RULE_RUN_PHASE" > "$RULE_RUN_LOG/phase"
printf '%s\n' "$RULE_RUN_EXIT" > "$RULE_RUN_LOG/exit-code"
printf 'Rule sync phase=%s; exit=%s; logs=%s\n' "$RULE_RUN_PHASE" "$RULE_RUN_EXIT" "$RULE_RUN_LOG"
```

默认使用依赖的匿名 public 统一入口，不加 `--bootstrap`，不自行请求规则平台或切换身份。Runner 负责认证、下载、包完整性验证和原子安装；FE 按下节核对本次交付并读取正文。

## 成功回执与本地校验

读取退出码及完整 stdout/stderr。仅 Runner 退出码为 `0` 且以下检查全部通过，才接受为平台规则交付成功；旧文件存在或日志最后出现成功字样均不能替代校验。`installed` 和 `not_modified` 执行相同检查，后者仍需重新读取本地正文。

1. stdout 是完整 JSON receipt，`schema_version=mt-rule-bundle-install/v1`，`status=installed|not_modified`，`standard_domain=frontend`，`stage=cr`；`request_id`、`pull_id` 和 `snapshot_id` 非空，`release_refs`、`managed_files` 是非空数组。核对 `target.canonical_key` 与本次仓库一致，`execution_agent` 与调用宿主一致。保留本次请求编号，不要求它们与历史安装时相同。
2. 在 `<规则输出目录>/.mdp/rules/` 内按 receipt 的 `bundle_kind` 选择 manifest，并检查另一份不存在：

   | `bundle_kind` | manifest | `schema_version` |
   |---|---|---|
   | `effective` | `.mt-effective-rule-bundle.json` | `mt-effective-rule-bundle-manifest/v8` |
   | `l1` | `.mt-l1-bootstrap.json` | `mt-l1-bootstrap-manifest/v5` |

   缺失、两份并存、类型不符均为本地校验失败。不要仅凭 `delivery_mode=l1_only` 选择 manifest：`effective` 也可只含 L1。
3. 比对 receipt 与 manifest 的 `snapshot_id`、`standard_domain`、`stage`、完整 `release_refs` 和 `managed_files`，数组按集合比对并拒绝重复项。manifest 的 `resolution` 中 `bundle_kind`、`delivery_mode`、`selection_reason` 和仓库身份须与 receipt 一致。Release 至少有 L1；`l1_only` 无 L2，`l1_l2` 同时有 L1/L2，`bundle_kind=l1` 只能是 `l1_only`。用 `managed_file_releases` 将每个文件绑定到 `release_refs` 中的 `rule_set_id` / `release_id`，不用目录名推导 Release。
4. 逐个检查 `managed_files` 指向规则根目录内的普通文件，无越界路径或符号链接；实读字节的 SHA-256 和大小分别与 manifest 的 `managed_file_hashes`、`managed_file_sizes` 一致。receipt 不含逐文件 Hash，以已匹配快照的 manifest 为准。核对 `managed_agents_indexes` 清单及其文件的 `managed_agents_index_hashes`、`managed_agents_index_sizes`；缺少索引时保留 Runner 的 `agents_index_warnings`，不编造索引或因此判定 fallback。

`repository_not_registered + l1_only` 和 `no_effective_l2 + l1_only` 都是正常成功。只要本次 L1 交付和本地校验成功，就使用平台规则并令 `rule_bundle.fallback.active=false`，不因无 L2、未登记或 manifest 名称含 bootstrap 而读取 fallback。

## 失败与诊断证据

仅在最终 Runner 失败（包括依赖缺失而未能调用）、receipt 无效或本地校验失败时，读取 [`rules/fallback-rules.md`](rules/fallback-rules.md)，继续使用可读 L3 和 fallback 审查，令 `rule_bundle.fallback.active=true`；本次无效平台包不作为已加载规则。

- `setup_runner_missing` 是依赖安装问题；`MODULE_NOT_FOUND`、漏传领域引起的 `domain_required` 等是客户端路径或参数错误，不归因服务端。若发生纠正后的再次调用，每次证据分别保存；最终成功须清除 fallback，但不能把该次运行记为“首次调用成功”。不要将自我纠错重试作为正常加载流程。
- 服务端真实失败保留具体 code/message、issues 和请求编号，不统一改写为 `public_rule_bundle_unavailable`。认证、限流或服务故障不自动切换身份、bootstrap 或反复重试；错误码本身不足以推断仓库登记、权限或发布状态。
- 规则证据目录保留：依赖安装目录及版本、实际命令和宿主、仓库、输出目录、时间、调用序号、phase、完整 stdout、stderr、exit code，以及原始 receipt、manifest、managed files 清单和实际正文读取记录。成功时同时保留实际受管规则与索引内容，便于复核 Hash；清理临时规则目录前先归档这些证据。
- 从 receipt 或错误响应记录 `request_id` / `pull_id`。失败时字段未返回则明确记为不可用，不编造编号；预检未执行 Runner 时，`127` 是本地预检码，Runner 退出码及 receipt 均记为未产生。现存 manifest 只能作为现场证据，不冒充本次成功回执。

## 规则范围与正文读取

以验证通过的 `managed_files` 为平台规则文件清单，路径相对于 `<规则输出目录>/.mdp/rules/`，不按旧目录结构或目录名猜文件：

- **L1**：`company/fe/<规则集名称>/**/*.md`。
- **L2**：`team/fe/<规则集名称>/**/*.md`。
- **L3**：仓库本地的 `.mdp/rules/project/`、`.fed/` 中明确表达审查约束的文档，以及 `AGENTS.md`、`README` 等入口直接定义或指向的规则。L3 不由平台下发，普通项目介绍、配置和模板不自动作为规则。

无论 Runner 结果如何，有业务仓库时检索上述 L3，并检查仓库根目录、变更相关模块及附近目录的 `AGENTS.md`、`README` 或 `README.md`，只沿其中声明的审查规范、CR 约定或规则入口继续读取。无业务仓库时，可从目标 commit 的远程文件补读明确可定位的入口和 L3；无法获取则记录 L3 未读取，不影响已同步的 L1/L2。

先读取受管索引、规则标题、适用范围和目录，再根据 diff、技术栈与调用链实际读取适用规则章节。索引缺失时从 `managed_files` 逐份读取标题和范围以定位正文。列出文件、计算 Hash 或读取 receipt/manifest 不算读取规则正文。

保存实际读取文件列表，每项记录规则层级、文件路径、入口来源、适用范围、已读章节或行范围和内容 Hash；区分只读索引/标题与已读正文。适用章节未读完时记录覆盖缺口，不宣称规则加载完成，也不因这一覆盖缺口自动读取 fallback。

以校验后的 receipt/manifest 填写 `rule_bundle` 的快照与 Release，以实际读取记录填写 `project_rules` 及命中项的 `rule_sources`；未读正文的规则不能记为已使用或命中。完整读取记录随准备信息交付上层并用于验收，不把安装文件清单当成阅读清单，也不扩展上报接口。上报字段见 [`report-submit.md`](report-submit.md)。业务变更审查排除 `.mdp/rules/**` 与 `.fed/**`。

## 统一规则标识

两个看板共用 `rule_sources`。每个命中规则记录：

- `source_type`：`platform`、`project` 或 `fallback`
- `scope_level`：`L1`、`L2`、`L3` 或 `FALLBACK`
- `rule_set_id`
- `rule_version`
- `file`、`title`、`section`
- `upstream_rule_id`：平台规则保留完整 UID（如 `fe-l1:ASYNC-001`）；L3 取命中条目明确声明的 `id` / `ruleId` 或标题编号，没有则留空；fallback 取标题编号（如 `FB01`）。不从路径或正文猜造编号。

`rule_version` 取值：L1/L2 使用 `release_id`；L3 使用规则文件 `shasum -a 256` 的结果；fallback 使用 `fallback-rules.md` 顶部声明的版本。

上报脚本按来源字段生成 `cr-rule/v1/<sha256>`，作为 `rule_sources[].rule_id`。该来源标识与报告展示编号分开；委托交接时原样保留全部 `rule_sources`。

报告正文使用：

```text
【规则：<source_type>/<scope_level> / <rule_set_id>@<rule_version> / <file>#<title>】
```

上报 CR 看板前读取 [`report-submit.md`](report-submit.md)。质量门禁接口提供前，只上报现有看板；接口提供后复用同一份标准化 payload 发起第二个请求。
