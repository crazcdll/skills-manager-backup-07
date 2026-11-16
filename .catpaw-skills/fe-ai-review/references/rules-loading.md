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

L3 获取按以下步骤处理：

1. 读取上述入口中的约束正文；README、AGENTS 中的封装约定、禁止项等也可构成 L3，不能仅按文件名归为项目介绍。
2. 沿入口明确声明的编码规范、工程规范或 CR 规则路径和链接继续读取正文；外部文档使用对应的只读工具。权限不足、文件不存在或工具不可用时保留入口和具体原因，不记为无规则。
3. 根据规则声明的模块范围及本次变更的调用影响判断适用性。模块未直接出现在变更清单中，不足以单独判定不适用；也不把模块专属规则扩展为全仓规范。
4. 在准备信息中逐项记录已发现入口的来源、适用范围和获取状态：已读取且适用、已读取但不适用（附理由）、读取受阻、待判断或待读取。适用规则沿用下方正文读取记录；尚未取得正文时不填写内容 Hash。
5. 进入审查前核对入口清单；有未处理入口或正文读取受阻时，记录 L3 覆盖缺口并随结果交付。只有相关入口检查完成且没有适用约束时，才可记录“未发现适用 L3”。

先读取受管索引、规则标题、适用范围和目录，再根据 diff、技术栈与调用链实际读取适用规则章节。索引缺失时从 `managed_files` 逐份读取标题和范围以定位正文。列出文件、计算 Hash 或读取 receipt/manifest 不算读取规则正文。

保存实际读取文件列表，每项记录规则层级、文件路径、入口来源、适用范围、已读章节或行范围和内容 Hash；区分只读索引/标题与已读正文。适用章节未读完时记录覆盖缺口，不宣称规则加载完成，也不因这一覆盖缺口自动读取 fallback。

以校验后的 receipt/manifest 填写 `rule_bundle` 的快照与 Release，以实际读取记录填写 `project_rules` 及命中项的 `rule_sources`；未读正文的规则不能记为已使用或命中。完整读取记录随准备信息交付上层并用于验收，不把安装文件清单当成阅读清单，也不扩展上报接口。上报字段见 [`report-submit.md`](report-submit.md)。业务变更审查排除 `.mdp/rules/**` 与 `.fed/**`。

## CR 前规则检查

开始代码审查前，在准备信息中记录以下检查结果及对应证据路径：
- **仓库与范围**：实际读取的仓库路径和 commit 与审查目标一致；PR 审查未取得匹配仓库时，核对是否按模式流程尝试 clone / fetch，并记录结果；失败允许降级继续，未尝试则说明用户仅远程要求或具体环境阻塞。记录远程读取策略，规则目录不能充当业务仓库。
- **平台规则**：记录真实 Runner 路径、完整输出、退出码及本节要求的校验结果；成功时列出已读适用正文，失败时记录原因和实际读取的 fallback。尚未执行、只有文件清单或没有正文读取证据，均不能记为加载完成。
- **L3**：核对已检查的根目录与相关模块入口、规范链接及逐项获取状态；复核 README 中是否有被误归为背景的约束。适用但未读、链接未处理或适用性未判断时先补齐；实际尝试后因权限或工具受阻的，明确记录缺口后降级继续，不能记为无 L3。
- **继续条件**：可完成的获取和正文读取已完成，剩余受阻项已有原因与影响范围，才进入代码审查。结论区分“已完成”和“带缺口继续”；审查中发现新的适用规则入口时补读并更新记录。检查结果随独立输出或上层交接保留，规则命中数量不能代替读取检查。

## 规则优先级与覆盖

**适用规则的优先级为 L3 > L2 > L1，L3 最高。** 对同一代码、同一约束存在冲突或明确例外时，以已读取且适用的高层级规则为准；不得依据已被覆盖的低层级要求报错。互不冲突的规则共同生效，高层级未规定的事项继续使用低层级规则。

覆盖仅限规则声明的适用范围和冲突条款，不因存在一条 L3 就跳过全部 L1/L2。审查及复查均记录冲突双方的来源、最终采用的规则及理由，发现项引用实际生效的规则。已知高层级入口但正文未读到时，记录覆盖缺口；受该缺口影响、无法确定规则是否生效的候选项不直接按低层级规则定性；满足 [定级与证据判断](severity.md) 准入条件时列为待确认，单纯的规则读取缺口只记入覆盖自评。

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
