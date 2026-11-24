---
name: ai-auto-ui-test
version: 6.0.0
description: 自动化 UI 测试编排入口。单份用例委托下游 Skill 执行；多份用例按分片派发 N 个子 Agent 并行执行并汇总（一次任务一份报告）。触发词：UI 自动化测试、端到端测试、回归测试、测试用例生成、steps.json 用例、Flow 用例（历史叫法）、测试报告、批量测试、多 Agent、并行测试、ai-app-flow、ai-ui-autotest-engine。场景：需要生成测试用例时委托 ai-app-flow，需要执行测试时委托 ai-ui-autotest-engine（单份直接执行 / 多份走多 Agent 编排）。

metadata:
  skillhub.creator: "huangshuiqing"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V42"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "112900"
  skillhub.high_sensitive: "false"
---

## 前置

```bash
# 1. 全自动环境准备（自身更新 + 依赖 Skill 安装 + 运行时环境配置）
python3 scripts/env_setup.py

# 2. 使用上报
python3 scripts/report_usage.py --stage start --mis "<mis_id>" --input "<输入摘要>" --desc "<意图>"
```

## 目录约定（硬约定）

> 唯一产物根 = **机器顶层目录** `$AI_UITEST_HOME`（默认 `~/.local/share/ai-ui-autotest/`）；
> **Skill 安装目录与项目根都不存任何运行态或用例文件**（自动更新 / 多副本 / 换项目不会丢）。

```text
$AI_UITEST_HOME/
├── cases/                                          # 用例资产（长期维护，不参与自动清理）
│   ├── local/<biz>/<pageId>/<caseId>/steps.json    # 已完成转化、无平台审核记录（MMCD 等）
│   └── platform/<需求id-需求名>/<caseKey>/steps.json  # 平台审核通过用例的本地镜像（可刷新）
├── orchestration/<task_id>/                        # 编排产物：manifest.json / cases 快照 / shards/
└── engine/                                         # 引擎运行态 $STATE：run / reports / console / credentials / device-pool
```

| 类别 | 规范位置 |
|------|---------|
| **用例资产（长期）** | `$AI_UITEST_HOME/cases/{local,platform}/...`（一用例一 `steps.json`，`case_id` = 所在目录名） |
| **编排产物（任务级）** | `$AI_UITEST_HOME/orchestration/<task_id>/`（`manifest.json` + `cases/` 快照 + `shards/`） |
| **执行运行态** | `$STATE` = `$AI_UITEST_HOME/engine/{run,reports,console,device-pool,credentials}/`（可用 `AI_UITEST_STATE_HOME` 整体改写） |

- **两种用例来源，二选一（互斥）**：
  - `--from-platform <需求 id | 需求名>`：走 `GET /test-case-review/export`，**服务端只导出 `reviewStatus === approved`**；先刷 `cases/platform/` 本地镜像，再快照进 `orchestration/<task>/cases/`。
  - `--local-cases <目录>`：已完成转化、无平台审核记录的用例（如 MMCD），目录下每个 `steps.json` = 一个用例；未自带 `reviewStatus=approved` 时**必须显式 `--skip-review`**（写入 `manifest.review_bypass=true` 供审计）。
- **两层落盘**：源（`cases/`）与任务快照（`orchestration/<task>/cases/`）分离 —— 子 Agent 只读快照，运行期改源不影响本任务。
- **自动滚动保留（若启用）只作用于 `orchestration/` 的一级任务目录**；`cases/` 永不参与自动清理。
- **路径可覆盖**：`AI_UITEST_HOME=/path`（CI / 多账号 / 沙箱隔离），缺省 `~/.local/share/ai-ui-autotest/`。
- **清理**：`cases/` 用例资产不参与自动清理（由 `ai-app-flow` 的 `prune_cases.py` 按需求维度回收）；`orchestration/` 一级任务目录由 `plan` 在创建新任务前自动滚动保留（默认最近 5 个，`AI_UITEST_KEEP_ORCH_TASKS` 可调），引擎报告归档在 `flow-init` 前按 keep-latest-N 清理。

# 编排入口

本 Skill 是**编排层**，不做具体业务逻辑，也不含任何测试执行实现：

| 场景 | 委托 Skill | 说明 |
|------|-----------|------|
| 生成用例资产 | `ai-app-flow` | 产出 `steps.json` → 入库平台 → 渲染 `flow.md`（只读视图）；**入库且审核通过后才可执行** |
| 执行测试（单份） | `ai-ui-autotest-engine` | 端到端执行一份输入，产出报告 |
| 执行测试（多份） | `ai-ui-autotest-engine` × N | **本 Skill 拆分 + 派发 N 个子 Agent 并行**（需**用例 ≥ 3 且环境支持子 Agent**，否则退化为单份），见「多 Agent 编排」 |

## 执行规则

1. **全局依赖就绪**：进入执行前先运行 `python3 scripts/env_setup.py`，自动完成自身更新、依赖 Skill（`ai-app-flow`、`ai-ui-autotest-engine`）安装、运行时环境配置。
2. 委托前先读取并严格遵循下游 Skill 的 SKILL.md。
3. **执行前必预审核（本 Skill 负责串联）**：只能从平台取「审核通过」用例（`--from-platform`）。串联顺序固定为：
   ① 用例未入库 → 委托 `ai-app-flow` 生成 `steps.json` 并入库（`pending`）；
   ② 跑 `orchestrate.py review --from-platform <id|需求名>` 拿到**审核页链接 + 审核态**，把链接交给用户；
   ③ **停下等用户确认「已审核通过」**（退出码 2 = 一条都没通过，禁止继续；退出码 3 = 部分通过，需用户确认「只跑已通过用例」）；
   ④ 用户确认后才跑 `fetch` / `plan`，再交给 `ai-ui-autotest-engine` 执行。
   只要审核通过数 > 0 就可以执行（服务端只下发 approved）；只有 0 条通过才彻底阻断。
   用户给的是本地目录 / 本地 `steps.json` 时，引导其先由 `ai-app-flow` 入库并在平台审核通过，**禁止绕过平台直接跑本地文件**；
   也禁止代替用户审核（写入 `approved` 只能由用户在审核页操作）。
   用例已存在时不得重新生成，除非用户明确要求更新。
4. 不重写下游 Skill 的流程，下游 Skill 的输出即最终结果。
5. **执行方式分流**：
   - **前置**：需当前运行环境支持派发子 Agent（Task / subagent）。**不支持时一律走「单份执行」**（详见「多 Agent 编排 › 前置能力与不适用情形」）。
   - **用例数 < 3（1~2 个）**：**不使用子 Agent**，由当前 AI 在本地直接执行 `ai-ui-autotest-engine`；委托 `ai-app-flow` 后，`ec-toolkit`、`citadel` 等 CLI 也由当前 AI 直接执行。
   - **用例数 ≥ 3 且环境支持子 Agent**：**按分片创建子 Agent 并行执行**，见「多 Agent 编排」。禁止把用例串行堆在一个 Agent 里跑。
6. **产物按「目录约定（硬约定）」落位**，不得在项目根或 Skill 目录自建用例 / 产物目录；用例落盘只发生在 `$AI_UITEST_HOME/orchestration/<task_id>/cases/`。
7. **会话隔离（硬原则）**：每轮执行只使用本轮 `ws-init` 新分配的 workspace；**禁止复用、读取、续跑、改动历史会话**的 workspace / 产物 / 输入（含 `intake`、设备、虚拟 mis）。历史产物仅供人工参考，不得作为本轮的输入来源或判定依据。
8. **运行类型透传**：输入中出现 `runType=regression`（或 `【运行类型】...回归`）时，**执行前必须** `export AI_UITEST_RUN_TYPE=regression`；多份编排时把同一值通过 `orchestrate.py plan --run-type regression` 写进分片，子 Agent 再导出给引擎。引擎据此把报告行的 `run_type` 写成 `regression`。输入未声明时按 `adhoc` 处理，不要猜测。

---

# 多 Agent 编排

> **定位**：编排层只负责「拆分 / 派发 / 汇总」；**执行一份入力是下游 Skill 的事**（`ai-ui-autotest-engine`）。
> **不变量**：一子 Agent 一 workspace 一设备一虚拟 mis；**报告粒度 = 一个任务一行**（`plan` 预置共享报告并下发 `report.id`，各分片向同一行 append；分片内多 Case 仍用 `flow-add-case` 合并到同一 run）。**一次执行只产出一份报告**，与拆几个分片无关。
> **拆分是内部策略**：是否拆、拆几片只由 Skill 自己判断（仅当环境支持子 Agent 时）；外部提示词不需要也不应描述分批方式。
> **汇报链路**：子 Agent 结果**随 Task 直接返回编排层**，不落中间状态文件（本版为 Task 同步并行模型）。

### 前置能力与不适用情形

> **多 Agent 编排的前置能力 = 主 Agent 能派发子 Agent（Task / subagent 能力）**。它是**可选加速**，**不是硬依赖**；以下任一情形即**退化为「主 Agent 单份执行」**：主 Agent 直接按 `ai-ui-autotest-engine` 逐份执行（串行），本 Skill 不进入编排流程。

| 不适用情形 | 处置 |
|---|---|
| **运行环境不支持子 Agent**（主 Agent 无 Task / subagent 能力，或被禁用） | 不走编排 → **主 Agent 单份执行** |
| **用例数 < 3**（1~2 个） | 同上（`plan` 亦会直接拒绝） |
| 用户明确要求不使用子 Agent | 同上 |

## 阶段 O0 · 前置

`python3 scripts/env_setup.py` → `python3 scripts/report_usage.py --stage start ...`。

## 阶段 O1 · 识别输入 + 收集环境信息

| 项 | 说明 |
|---|---|
| **原始用例（两种来源，互斥）** | ① `--from-platform <需求 id | 需求名>`：服务端只导出 approved；② `--local-cases <目录> --skip-review`：已完成转化但无平台审核记录的用例（MMCD 等）。两种来源都先落成「一用例一目录一 `steps.json`，`case_id` = 目录名」，**≥ 3 个**才进编排 |
| **每 Agent 用例上限** | 默认 **2**（`--max-cases`）—— 每个子 Agent 最多处理 2 个用例 → 分片 = 按 2 连续切块 |
| **并发上限** | 默认 **4**（`--concurrency`）—— **同时在跑的子 Agent 上限**（滑动窗口）：谁先跑完谁补下一个；实际并行度 ≤ `min(设备池, 虚拟 mis 池)`，超限由下游 fail-fast |
| **环境信息** | 设备组合 / 环境类型（A/P/B/C/E/D）/ 泳道（B）/ 域名映射（E）/ 锁包 等，**所有子 Agent 共享**；经 `--env '<json>'` / `--env-file <path>` 传入（不传则子 Agent 自行收集）。ptest 不是独立字段：线上泳道就是 `env_type=P` |

## 阶段 O1.5 · 人工审核门禁（硬流程）

```bash
# 输出审核页链接 + 审核态；0=全通过 3=部分通过 2=零通过阻断
python3 scripts/orchestrate.py review --from-platform <需求 id | 需求名>
```

| 退出码 | 含义 | 动作 |
|---|---|---|
| `0` | 用例已全部 `approved` | 才允许进入 O2（`fetch` / `plan`） |
| `3` | **部分通过**（≥1 条 `approved`，仍有 `pending` / `rejected`） | 把「审核页链接 + 本次将执行的已通过用例数 / 将被跳过的条数」告给用户，**用户确认「只跑已通过的」后**再进 O2；服务端 `export` 只下发 approved，未审用例不会被跑 |
| `2` | **零通过**：一条 `approved` 都没有，或需求下没有用例 | **把「审核页」链接原样发给用户，停下等审核**；确认前不得执行 |

- 审核页链接由命令输出（`AI_TEST_REVIEW_BASE` 可覆盖，默认 `https://aimonitor.mynocode.host`），格式 `#/test-cases/<需求 id>`。
- **放行口径：`approved > 0` 即可执行**；不要因为「还有待审 / 驳回」就拒绝执行，也不要自作主张跳过用户确认。
- 用例尚未入库时：先委托 `ai-app-flow` 生成并入库（`pending`），再回到本阶段。
- **禁止代替用户审核**：`approved` 只能由用户在审核页写入；执行层的卡控仍由服务端 `export` 兜底（只导出 approved）。

## 阶段 O2 · 拆分 + 编排待跑队列

```bash
# ① 编排 · 平台来源（服务端只导出审核通过）；env 默认取平台值，--env 覆盖
python3 scripts/orchestrate.py plan --from-platform <需求 id | 需求名> --max-cases 2 --concurrency 4 --run-type regression

# ① 编排 · 本地来源（MMCD / 已完成转化，无平台审核记录）—— 必须 --skip-review
python3 scripts/orchestrate.py plan --local-cases "$AI_UITEST_HOME/cases/local/<biz>/<pageId>" \
  --skip-review --max-cases 2 --concurrency 4 --run-type regression

# ② 只取数不编排（单份执行 / 不足 3 条时用）：默认刷 cases/platform/<需求>/
python3 scripts/orchestrate.py fetch --from-platform <需求 id | 需求名>
```

> 平台没有可执行用例（全未审 / 已驳回）时 `plan`、`fetch` 都会直接失败并提示先完成审核 —— 这是预期行为。

产出**编排产物目录** `$AI_UITEST_HOME/orchestration/<task_id>/`（含 `manifest.json` + `shards/shard-NN.json`），并打印**派发计划**：
- **分片**：按 `--max-cases`（默认 2）连续切块 → 每个分片 ≤ 2 个用例；
- **待跑队列**：分片按序排队；`--concurrency` 是**同时在跑上限**（如 10 用例 → 5 分片，队列 [1,2,3,4,5]：先起 4 个，谁先完成谁补第 5 个）。

**记下 task_id**。用例数 < 3 时 `plan` 会拒绝（改走单份执行）。

> **共享报告标题**：缺省取 `--local-cases` 根目录名；建议用例根目录按「MMCD 回归 <页面名>」命名，也可用 `--report-title "<标题>"` 显式指定。全部分片共用这一个报告（`manifest.report`），不会每片一行。

**清理**：`plan` 不删用例资产，但会在创建新任务**前**自动回收旧编排任务目录（保留最近 `AI_UITEST_KEEP_ORCH_TASKS` 个，缺省 5，0=关闭）；引擎侧报告归档在每次 `flow-init` 前滚动清理（默认保留 5 个批次，60 分钟内批次受保护）。`cases/` 用例资产仍由 `ai-app-flow` 开工前跑 `prune_cases.py` 回收（默认保留最近 5 个需求）。

## 阶段 O3 · 滚动补位派发（滑动窗口）

**滑动窗口**：先并行启动队列前 `concurrency` 个分片（各 1 个子 Agent）；之后**谁先跑完就立刻从队首补下一个**，保持同时在跑 ≤ `concurrency`，直到队列跑空。子 Agent 输入 = 该分片的 `shards/shard-NN.json`，严格遵循 `ai-ui-autotest-engine` 的 SKILL.md（单份执行路径），职责：

```text
输入（编排层只给「原始内容 + 环境」，不做任何处理）：
  · shard 文件      <ORCH_ROOT>/<task>/shards/shard-NN.json（含 env + cases）
  · 用例快照        每个 case 的 steps_path（指向 <task>/cases/ 快照，子 Agent 自己读内容）
  · 环境信息        shard.env（子 Agent 用 input-seed 预置已知值；平台模式下已含
                    env_type / swim_lane_name / swim_url_mappings，均为引擎问题 id 同名）
  · 设备提示        manifest.device_hint（平台 env 的 platform / app）—— 选 device_combo 时对齐，
                    不要当 input-seed 键传（不属于问题 id）
  · 分片名          shard.report_name（作为 flow-init --flow-name，本地归档标题）
  · 运行类型        shard.run_type（regression / feature / adhoc）
  · 共享报告        shard.report_id（全部分片同一行；编排层已 Open，子 Agent 只 append）

明确不在输入契约内：
  · 信息收集    子 Agent 自己走 input-next 循环（编排层不提供、不继承）
  · workspace   子 Agent 自己 ws-init 分配（编排层不注入身份）

子 Agent 动作：
  0. `export AI_UITEST_REPORT_ID=<shard.report_id>` → 报告写入任务共用行（**禁止**新建报告行）；
     `export AI_UITEST_RUN_TYPE=<shard.run_type>`（adhoc 可省略）→ 行 `run_type` 按该类型入库
  1. ws-init → check-deps
  2. input-schema → input-seed（用 shard.env 预置已知值）→ input-next 循环补齐剩余
  3. 全部 case 先 `steps-generate --steps <case.steps_path> --tag <case_id>`
     （steps.json → CASES 的映射已收进这条命令内部，不存在「手写 CASES / 另跑 flow_json」的环节）
  4. 合并成一个 run：`flow-init --dir <run> --input 'steps-input-<首case>.json' --flow-name '<shard.report_name>' --run-type '<shard.run_type>'`
     → 其余 case 逐条 `flow-add-case --dir <同一个 run> --input 'steps-input-<case>.json'`
       （`--dir` 可省略，缺省沿用当前活跃 run；显式传更稳） → 再重跑一次同一条 `flow-init`
     （引擎沿用同一批次/报告行；`--flow-name` 必传，否则行标题退化为首个 steps.json 的 title）
  5. 按 flow-next 驱动执行；**每个 case 收尾必须 `gen-report` 一次**（少一个即 `incomplete`）→ flow-finalize → post-clean
  6. 收口：以**一行结构化 JSON 摘要**结束，结果随 Task 返回编排层
```

**收口契约**（一行 JSON，随 Task 返回）：

```json
{"shard":"shard-NN","status":"done|failed|clarification_needed","report_id":"","cases_total":0,"cases_passed":0,"cases_failed":0,"cases_skipped":0,"audit_dir":"","missing_env":["字段名,..."]}
```

- `status=clarification_needed`：环境信息缺失（shard.env 与 input-next 均未补齐）时**立即返回**，不在子 Agent 内等待或重试；`missing_env` 列出缺失字段，由编排层聚合后一次性上抛/询问，**不阻塞其他分片**；
- `report_id` = `shard.report_id`（全分片共用同一行）；核对口径：行内 `cases` 数 == 各分片 `cases_total` 之和（由平台重算）；
- **交互受限环境**（托管 Agent / 无人工会话，如 multica）：子 Agent 内**禁止 AskQuestion / @mention 人工**，一切缺失信息只能以 `clarification_needed` 收口；编排层已通过 `--env` 尽量预置已知值来避免走到这一步。

> 子 Agent 的**所有执行细节（信息收集 / 环境供给 / 设备领取 / 步骤走查 / 上报）以 `ai-ui-autotest-engine/SKILL.md` 为准**，本 Skill 不重复其流程。
> **无需回写状态文件**：子 Agent 非游离后台进程，执行结果随 Task 直接返回；报告统一 append 到 `manifest.report.id` 这一行。

## 阶段 O4 · 汇总与汇报

- 队列跑空且全部结束后，编排层直接汇总**各分片结果**（状态 / 报告 id / cases 统计）→ 输出结果表；
- 失败分片单列（**不影响其他分片**）；向用户汇报各分片报告入口；
- 存在 `clarification_needed` 分片：等在跑分片全部结束后，聚合所有 `missing_env` **一次性**上抛/询问；人工补齐后，把补齐值并入 `--env` 重跑 `plan`，**只补跑未完成分片**（已完成分片不重跑）；
- 中断恢复：任务中断后重新进入时，读 `manifest.json` 待跑队列 + 已返回的分片收口结果，只补跑未完成分片；
- 报告粒度 = **一个任务一行**（`manifest.report`）：`plan` 预置共享行，子 Agent 导出 `AI_UITEST_REPORT_ID` 后引擎跳过自建行、只做 append；分片内多 Case 仍合并到同一 run；
- 收尾：**不需要手动执行**——下一次 `plan` 会自动收尾（默认最后活动 ≥ 6 小时 / 360 分钟，`AI_UITEST_AUTOCLOSE_MINUTES` 可调），滚动删除旧任务前也会先收尾；只有需要立刻修正当前任务的 `duration` 时才手动跑 `python3 scripts/orchestrate.py report-close --task <task_id>`；**不要在汇报里拆成多条报告**。
- **产物保留**：编排产物跟着需求目录一起由 `ai-app-flow` 的 `prune_cases.py` 回收（默认保留最近 5 个），本 Skill 不提供删除命令。

---

# 命令一览

| 命令 | 作用 |
|---|---|
| `python3 scripts/env_setup.py` | 自身更新 + 依赖 Skill 安装 + 环境配置 |
| `python3 scripts/report_usage.py --stage start ...` | 使用上报 |
| `python3 scripts/orchestrate.py review --from-platform <需求 id \| 需求名>` | 审核门禁：输出审核页链接 + 审核态；0=全部通过 / 3=部分通过（用户确认后只跑已通过）/ 2=零通过阻断 |
| `python3 scripts/orchestrate.py plan --from-platform <需求 id \| 需求名> [--max-cases 2] [--concurrency 4] [--run-type regression] [--env '<json>']` | 取「仅审核通过」用例 → 刷 `cases/platform/` 镜像 → 快照到 `orchestration/<task>/cases/` → 拆分编排（env 默认取平台值，`--env` 覆盖） |
| `python3 scripts/orchestrate.py plan --local-cases <目录> --skip-review [--max-cases 2] [--concurrency 4] [--run-type regression]` | 本地已转化用例（MMCD 等）→ 快照后拆分编排；`--skip-review` 写入 `manifest.review_bypass=true` 供审计；可选 `--report-title` 指定共享报告标题 |
| `python3 scripts/orchestrate.py fetch --from-platform <需求 id \| 需求名> [--out <目录>]` | 只取数不编排：默认刷 `cases/platform/<需求>/`（可重复执行），`--out` 可指定空目录 |
| `python3 scripts/orchestrate.py report-close --task <task_id>` | 全部子 Agent 结束后收尾共享报告（回写全量 duration） |

