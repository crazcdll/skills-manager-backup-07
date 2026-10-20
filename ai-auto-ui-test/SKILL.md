---
name: ai-auto-ui-test
version: 6.0.0
description: 自动化 UI 测试编排入口。单份用例委托下游 Skill 执行；多份用例按分片派发 N 个子 Agent 并行执行并汇总。触发词：UI 自动化测试、端到端测试、回归测试、测试用例生成、Flow 用例、测试报告、批量测试、多 Agent、并行测试、ai-app-flow、ai-ui-autotest-engine。场景：需要生成测试用例时委托 ai-app-flow，需要执行测试时委托 ai-ui-autotest-engine（单份直接执行 / 多份走多 Agent 编排）。

metadata:
  skillhub.creator: "huangshuiqing"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V30"
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

> 产物归各自 Skill 内部；**禁止在项目根目录自建用例 / 产物目录**。

| 类别 | 规范位置 |
|------|---------|
| **用例资产**（源，Flow `.md`） | `<ai-app-flow>/.docs/{需求名}/flows/*.md` |
| **编排产物**（`manifest.json` / `cases/` 快照 / `shards/`） | `<本 Skill>/.orchestration/<task_id>/` |
| **执行运行态**（报告 / 截图） | `<ai-ui-autotest-engine>/{output,.run,.device-pool,.credentials}/` |

- `<某 Skill>` = 该 Skill 的安装目录；`{需求名}` 按 `ai-app-flow` 规则提取。
- **`--cases` 指向 `{需求名}/flows/`，不可指 `.docs/{需求名}/` 整包**（否则 `ec-cases/`、`review-report.md` 会被误扫成用例）。
- `plan` 把用例**快照**到 `<task_id>/cases/`，分片只引用快照 → 同一 task 各分片读同一份内容，源目录运行期被改不影响本任务。
- **滚动保留（keep-latest-N）**：`.orchestration/` 的一级 task 目录与 `<ai-app-flow>/.docs/` 的一级需求目录**各只保留最近 10 份**（按最近修改时间倒序）；`plan` 成功后自动清理超出记录，`--keep N` 可调、`--no-prune` 可关。本次任务的产物目录与 `--cases` 所在的需求目录**恒被保护**，永不清理；也可单独执行 `prune` 手动滚动清理（支持 `--dry-run` 预览）。

# 编排入口

本 Skill 是**编排层**，不做具体业务逻辑，也不含任何测试执行实现：

| 场景 | 委托 Skill | 说明 |
|------|-----------|------|
| 生成 Flow 用例 | `ai-app-flow` | 生成可执行的 Flow 测试文件 |
| 执行测试（单份） | `ai-ui-autotest-engine` | 端到端执行一份输入，产出报告 |
| 执行测试（多份） | `ai-ui-autotest-engine` × N | **本 Skill 拆分 + 派发 N 个子 Agent 并行**（需**用例 ≥ 3 且环境支持子 Agent**，否则退化为单份），见「多 Agent 编排」 |

## 执行规则

1. **全局依赖就绪**：进入执行前先运行 `python3 scripts/env_setup.py`，自动完成自身更新、依赖 Skill（`ai-app-flow`、`ai-ui-autotest-engine`）安装、运行时环境配置。
2. 委托前先读取并严格遵循下游 Skill 的 SKILL.md。
3. Flow 文件已存在时不得重新生成，除非用户明确要求更新。
4. 不重写下游 Skill 的流程，下游 Skill 的输出即最终结果。
5. **执行方式分流**：
   - **前置**：需当前运行环境支持派发子 Agent（Task / subagent）。**不支持时一律走「单份执行」**（详见「多 Agent 编排 › 前置能力与不适用情形」）。
   - **用例数 < 3（1~2 个）**：**不使用子 Agent**，由当前 AI 在本地直接执行 `ai-ui-autotest-engine`；委托 `ai-app-flow` 后，`ec-toolkit`、`citadel` 等 CLI 也由当前 AI 直接执行。
   - **用例数 ≥ 3 且环境支持子 Agent**：**按分片创建子 Agent 并行执行**，见「多 Agent 编排」。禁止把用例串行堆在一个 Agent 里跑。
6. **目录按「目录约定（硬约定）」落位**，不得在项目根自建用例 / 产物目录（`plan` 对约定外目录告警）。
7. **会话隔离（硬原则）**：每轮执行只使用本轮 `ws-init` 新分配的 workspace；**禁止复用、读取、续跑、改动历史会话**的 workspace / 产物 / 输入（含 `intake`、设备、虚拟 mis）。历史产物仅供人工参考，不得作为本轮的输入来源或判定依据。

---

# 多 Agent 编排

> **定位**：编排层只负责「拆分 / 派发 / 汇总」；**执行一份入力是下游 Skill 的事**（`ai-ui-autotest-engine`）。
> **不变量**：一子 Agent 一 workspace 一设备一虚拟 mis；**不预置报告行、不聚合**（阶段 5 落地前，各子 Agent 报告各自独立）。
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
| **原始用例（单一标准）** | **一个「用例目录」**（递归），目录下每个 `.md` = 一个用例，`case_id` = 文件名去扩展名（**≥ 3 个才进编排**）。规范位置见「目录约定（硬约定）」 |
| **每 Agent 用例上限** | 默认 **2**（`--max-cases`）—— 每个子 Agent 最多处理 2 个用例 → 分片 = 按 2 连续切块 |
| **并发上限** | 默认 **4**（`--concurrency`）—— **同时在跑的子 Agent 上限**（滑动窗口）：谁先跑完谁补下一个；实际并行度 ≤ `min(设备池, 虚拟 mis 池)`，超限由下游 fail-fast |
| **环境信息** | 设备组合 / 环境 / 泳道 / URL 映射 / ptest / 锁包 等，**所有子 Agent 共享**；经 `--env '<json>'` / `--env-file <path>` 传入（不传则子 Agent 自行收集） |

## 阶段 O2 · 拆分 + 编排待跑队列

```bash
# 用例目录下每个 .md = 一个用例（默认 --keep 10：plan 成功后自动滚动保留）
python3 scripts/orchestrate.py plan --cases <用例目录> --max-cases 2 --concurrency 4 --env '<环境信息JSON>'
```

产出**编排产物目录** `.orchestration/<task_id>/`（含 `manifest.json` + `shards/shard-NN.json`），并打印**派发计划**：
- **分片**：按 `--max-cases`（默认 2）连续切块 → 每个分片 ≤ 2 个用例；
- **待跑队列**：分片按序排队；`--concurrency` 是**同时在跑上限**（如 10 用例 → 5 分片，队列 [1,2,3,4,5]：先起 4 个，谁先完成谁补第 5 个）。

**记下 task_id**。用例数 < 3 时 `plan` 会拒绝（改走单份执行）。

**滚动保留**：`plan` 成功后会同步执行 keep-latest-N —— `.orchestration/` 与 `<ai-app-flow>/.docs/` 各保留最近 **10** 份（`--keep N` 可调，`--no-prune` 可关），并打印实际保留/清理清单。

## 阶段 O3 · 滚动补位派发（滑动窗口）

**滑动窗口**：先并行启动队列前 `concurrency` 个分片（各 1 个子 Agent）；之后**谁先跑完就立刻从队首补下一个**，保持同时在跑 ≤ `concurrency`，直到队列跑空。子 Agent 输入 = 该分片的 `shards/shard-NN.json`，严格遵循 `ai-ui-autotest-engine` 的 SKILL.md（单份执行路径），职责：

```text
输入（编排层只给「原始内容 + 环境」，不做任何处理）：
  · shard 文件      .orchestration/<task>/shards/shard-NN.json（含 env + cases）
  · 用例快照        每个 case 的 flow_path（指向 <task>/cases/ 快照，子 Agent 自己读内容）
  · 环境信息        shard.env（子 Agent 用 input-seed 预置已知值）

明确不在输入契约内：
  · 信息收集    子 Agent 自己走 input-next 循环（编排层不提供、不继承）
  · workspace   子 Agent 自己 ws-init 分配（编排层不注入身份）
  · 报告 id      本轮各自独立（阶段 5 后再改为注入统一 id）

子 Agent 动作：
  1. ws-init → check-deps
  2. input-schema → input-seed（用 shard.env 预置已知值）→ input-next 循环补齐剩余
  3. 逐个 case：flow-create → 写入 Flow 内容 → cases-create → steps-generate → 审校
  4. flow-init → 按 flow-next 驱动执行 → flow-finalize → post-clean
  5. 收口：以**一行结构化 JSON 摘要**结束，结果随 Task 返回编排层
```

**收口契约**（一行 JSON，随 Task 返回）：

```json
{"shard":"shard-NN","status":"done|failed|clarification_needed","report_id":"","cases_total":0,"cases_passed":0,"cases_failed":0,"cases_skipped":0,"audit_dir":"","missing_env":["字段名,..."]}
```

- `status=clarification_needed`：环境信息缺失（shard.env 与 input-next 均未补齐）时**立即返回**，不在子 Agent 内等待或重试；`missing_env` 列出缺失字段，由编排层聚合后一次性上抛/询问，**不阻塞其他分片**；
- **交互受限环境**（托管 Agent / 无人工会话，如 multica）：子 Agent 内**禁止 AskQuestion / @mention 人工**，一切缺失信息只能以 `clarification_needed` 收口；编排层已通过 `--env` 尽量预置已知值来避免走到这一步。

> 子 Agent 的**所有执行细节（信息收集 / 环境供给 / 设备领取 / 步骤走查 / 上报）以 `ai-ui-autotest-engine/SKILL.md` 为准**，本 Skill 不重复其流程。
> **无需回写状态文件**：子 Agent 非游离后台进程，执行结果随 Task 直接返回；报告已由引擎各自入库。

## 阶段 O4 · 汇总与汇报

- 队列跑空且全部结束后，编排层直接汇总**各分片结果**（状态 / 报告 id / cases 统计）→ 输出结果表；
- 失败分片单列（**不影响其他分片**）；向用户汇报各分片报告入口；
- 存在 `clarification_needed` 分片：等在跑分片全部结束后，聚合所有 `missing_env` **一次性**上抛/询问；人工补齐后，把补齐值并入 `--env` 重跑 `plan`，**只补跑未完成分片**（已完成分片不重跑）；
- 中断恢复：任务中断后重新进入时，读 `manifest.json` 待跑队列 + 已返回的分片收口结果，只补跑未完成分片；
- 报告本期**各自独立入库**（不预置、不聚合）；阶段 5 的「原子追加 / 汇总成一份」落地后再切换（编排层预置空行 → 子 Agent 追加）。
- **产物保留**：编排产物与用例资产由 `plan` 自动 keep-latest-N 滚动保留（默认 10 份）；如需立即回收执行 `python3 scripts/orchestrate.py prune [--keep N] [--dry-run]`。

---

# 命令一览

| 命令 | 作用 |
|---|---|
| `python3 scripts/env_setup.py` | 自身更新 + 依赖 Skill 安装 + 环境配置 |
| `python3 scripts/report_usage.py --stage start ...` | 使用上报 |
| `python3 scripts/orchestrate.py plan --cases <用例目录> [--max-cases 2] [--concurrency 4] [--env '<json>'] [--keep 10] [--no-prune]` | 拆分（≤max-cases/分片）+ 编排待跑队列 + 自动滚动保留（编排层唯一脚本） |
| `python3 scripts/orchestrate.py prune [--keep 10] [--dry-run]` | 滚动保留最近 N 份：编排产物 `.orchestration/` + 用例资产 `.docs/` |
