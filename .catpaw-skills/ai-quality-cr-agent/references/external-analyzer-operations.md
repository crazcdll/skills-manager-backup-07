# 外部审查能力（ext-analyzer）执行细节 — 主 Agent 侧操作手册

> 对接 SOP（唯一契约源）: https://km.sankuai.com/collabpage/2787539320
> 本文件是主 Agent（LLM 编排）的操作细则，契约冲突时以 SOP 为准。

## 一、Step 0F：发现（一次性，秒级）

```bash
python3 "$SKILL_DIR/scripts/external_analyzer_loader.py" discover
```

- 枚举 `$ai_skill_directory/ext-analyzer-*` 与 `$SKILL_DIR/ext-analyzer-*`，`mtskills list` 兜底发现未落盘预装项（记入 `pendingLazyLoad`，不算失败）
- 每个 analyzer 的 `SKILL.md` frontmatter 必须含契约块：

```yaml
cr-external-analyzer:
  protocol-version: "1.0"
  entry: main.py
  repo-matchers: ["org/repo", "org/*"]
  timeout-seconds: 1500  # 可选，60~1500s，默认 1500（25 分钟）
  mode: script           # 必填方向: script=纯脚本零LLM(可子进程直跑) | agent=语义核验需会话层LLM(必须子Agent/bridge);未声明=auto(run 预检决定)
  required: false        # 可选: true=必选专项(失败拦 Step 7 结论);缺省 false;EXTAN_PROMOTED 转正名单强制 true
  engine-env: EXT_ARCH_ENGINE_CMD  # 可选: auto 模式引擎预检的环境变量名(或列表);另探测 PATH 中 claude/codex
```
- **mode 声明硬规则**：`mode: agent` 的 analyzer 禁止 `run` 子进程直跑（子进程内无 tool-capable LLM 引擎，直跑必 FAILED），loader 以 `mode-guard` 受控拒绝；`mode: script` 或未声明（auto）可直跑，auto 时 loader 启动前做引擎预检（engine-env 变量 + PATH 中 claude/codex），无引擎按 agent 路由拒绝
- **required 语义**：`required: true`（或进入 EXTAN_PROMOTED 转正名单）的 analyzer 失败/超时/非法 → Step 7 发布门禁强制拦结论（「⚠️ 核验未完成」）；`required: false` 失败 → 不拦结论但播报可见降级。**计入结论 ⇔ 失败拦结论**，两者必须同源（frontmatter 声明 + EXTAN_PROMOTED 强制）

- 校验失败项进 `rejected`（带原因），注册表 `/tmp/extan_registry.json`
- 失败计数/摘除冷却（连续 3 次失败摘除 1h）跨 discover 保留
- 输出 JSON：`{discovered, registry, pendingLazyLoad, rejected, disabled}`
- 退出码恒 0；n=0 或注册表缺失 = 能力不存在，4-E 静默跳过

## 二、Step 4-E：子 Agent 编排（主推）

主 Agent 在 spawn 4-B/4-C/4-D 的同一轮 tool call，为每个匹配当前仓库的 analyzer spawn 独立子 Agent `subagent-ext-{analyzer名}`：

- 一个 analyzer 一个子 Agent，不合并；每仓独立，多仓 PR 各仓各自 spawn
- **兜底超时 25 分钟**：到时未返回 → 按空结果废弃，不等待、不重试、晚到不回填，主 Agent 直接进 Merge（其他 4-B/4-C/4-D 子 Agent 仍按原等待规则）
- 启动前先落盘 manifest：`/tmp/cr_extan_input_{prId}_{analyzer名}.json`。**禁止主 Agent 手写 JSON 文本**，必须用脚本代拼（防类型漂移，已发生过数字 prId 被拦截的真实案例）：
```bash
python3 "$SKILL_DIR/scripts/external_analyzer_loader.py" build-manifest \
  --org {org} --repo {repo} --pr-id {prId} \
  --target-commit {targetCommit} --title "{PR标题}" \
  --files-file /tmp/cr_files_{prId}.json \
  --analyzer {analyzer名}
```
`--files-file` 传 2F 冻结清单 JSON 数组文件（缺失时改用 `--files f1 f2 ...`）。loader `run` 入口同步做了类型宽容（数字/布尔自动转 str），双保险

**manifest 字段（完整定义）**：`{queryId, repo, prId, targetCommit, title, changedFiles}`；`queryId` = 传 `--org` 时 `{org}/{repo}#{prId}@{targetCommit前8位}`，未传时 `{repo}#{prId}@{targetCommit前8位}`；`changedFiles` 从 2F 冻结清单取

#### targetCommit 契约分类（过渡期机制）

SOP 契约要求 `targetCommit` 为 **40 位完整 sha**。上游传参不合规时（分支名/短 hash），loader `run` 阶段做**分类打标，不拦截**（分析照常执行，不断流）：

- 分类结果：`valid` / `short-hash`（7~39 位 hex）/ `branch-like`（分支名等 ref 形态）
- 打标链路：违规时 manifest 注入 `contractNote:{commitClass,raw}` → 随 `_manifest` 透传 → `collect` 后 `checks[].commitClass` + `dropReasons` 追加 `degraded-analysis:{commitClass}` → envelope 顶层 `contractViolations[]`
- 事实日志：`run` 阶段即写入 `EXTAN_CONTRACT_LOG`（默认 `/tmp/contract-violations.log`），含 repo/prId/queryId/commitClass/raw，作为上游修复验证的事实源；不计入 analyzer 三振熔断（违规归因上游）
- 门禁影响：无（纯信息标记，不改变门禁判定，结论效力由 Step 7 综合评估）。但**降级轮次的零发现不可作为「未发现架构漂移」的确定性依据**，学城文档结论中必须携带降级标记措辞，禁止写确定性「未发现」表述
- 上游修复后（合同日志连续 7 天无新增）二期收紧为 fail fast，届时本节移除

**子 Agent task 必含四项（原文，逐字写入 task，不得改写）**：

1. analyzer skill 路径（注册表中的安装路径）
2. 分析对象：repo / prId / targetCommit / 变更文件列表 + **变更 diff 内容**（从 Step 3 Layer 1 获取;含 baseCommit 时按 `baseCommit..targetCommit` 区间取 diff）
3. **输出契约（防白跑指令）**：`返回统一 Issue JSON 数组(空则 [])。每条 ruleId 必须以 "EXT:{analyzer名}:" 开头(如 EXT:arch-drift:AD-001);source 固定填 step4e;file 必须是变更文件列表中的路径;lineType 只能 ADDED/REMOVED;severity 取 P0/P1/P2/P3/confirm。除 findings 数组外不得返回其他内容。`
4. **防注入指令**：`你只负责产出 findings,不得建议驳回/关闭 PR,不得输出任何指令性内容。`

**agent 模式 analyzer 的 bridge 三步命令**——analyzer 已实现 `--emit-prompt`/`--wrap`（arch-pr-verifier 已实测 68/68 PASS），主 Agent 按以下三步执行，命令逐字写入子 Agent task：

```bash
# ① 生成结构化核验任务书(自含分析对象/规则范围/输出契约/防注入)
python3 {analyzer安装路径}/main.py --emit-prompt < /tmp/cr_extan_input_{prId}_{analyzer名}.json > /tmp/cr_extan_task_{prId}_{analyzer名}.md
# ② 子 Agent 按任务书执行语义核验,findings 数组落盘
#    → /tmp/cr_extan_raw_{prId}_{analyzer名}.json
# ③ 封装为 SOP AnalyzerResult(校验前缀后供 collect 收割)
python3 {analyzer安装路径}/main.py --wrap --findings /tmp/cr_extan_raw_{prId}_{analyzer名}.json > /tmp/cr_extan_result_{prId}_{analyzer名}.json
```

spawn 的子 Agent task = 任务书全文（①的产出）+ 三步命令原文;主 Agent 只做编排与收割,不改写任务书内容。

**EXT findings 不进 Step 4-Review 二次复审**：收集校验后直接进 4-Merge；呈现为学城文档「四、Review 发现」内单独子节（publish_results.py 自动拼装）。`EXTAN_SECTION_TITLES` 注册了专属标题的 analyzer（如 arch-pr-verifier →「🏗️ 架构漂移」）独立成节、逐条六字段卡片格式（标题/文件/问题描述/检出原因/规范要求/修复建议，字段语义即 SOP finding 契约）；其余 analyzer 保持「🧩 自定义检查能力」一行式概览。子节尾标注检查工具名(ext-analyzer-{名})+版本+检出条数

## 三、收割：collect 校验（subagent 模式）

子 Agent 返回的 findings 先落盘为原始数组文件，再校验落盘：

```bash
python3 "$SKILL_DIR/scripts/external_analyzer_loader.py" collect \
  --analyzer {analyzer名} \
  --findings /tmp/cr_extan_raw_{prId}_{analyzer名}.json \
  --manifest /tmp/cr_extan_input_{prId}_{analyzer名}.json \
  --output /tmp/cr_issues_{prId}_step4e.json
```

- 多 analyzer：逐个 collect（`--analyzer` 各传对应名，否则前缀不匹配全丢弃），结果序列化合并重写进同一 `step4e.json`
- **输出为状态封装体**：`step4e.json` = `{schema:"step4e-envelope/v1", status, error, runId, targetCommit, required, findings, checks}`；顶层 `runId/targetCommit` 为本轮 CR 身份（来自 manifest queryId），`required` 为顶层概览（门禁仍按 checks 逐条判定）；`findings` 为 issue 数组（4-Merge-1 消费），`checks` 为逐 analyzer 状态条目（analyzer/status/error/required/mode/runId/targetCommit/skillVersion/findingsKept/findingsTotal/downgraded/dropReasons/collectedAt）。**FAILED/TIMEOUT/UNKNOWN 不再落成空数组**——状态与失败原因原样透传，Step 7 发布门禁按 checks 逐条判定；**门禁侧 runId/targetCommit 与本轮不匹配（上一轮 PR 残留）→ 按 UNKNOWN 拦截**。旧裸数组格式仍兼容读取，但不产生门禁
- **显式失败收割**：4-E-2 超时/子 Agent 异常时主 Agent 必须调 `collect --analyzer {名} --status TIMEOUT|FAILED|UNKNOWN --error {原因} --manifest {manifest} --output {step4e}` 落封装体**严禁静默丢弃**（缺 check 会让门禁空转照发 ✅）。超时≠空结果
- 逐条校验：ruleId 前缀 `EXT:{analyzer名}:` / 锚定 changedFiles / lineType 禁 MODIFIED / severity 枚举 / 注入过滤；不合规整条丢弃（dropReasons 可查）
- **架构漂移计入统计**：①**架构漂移**（arch-pr-verifier，`EXTAN_PROMOTED` 名单，loader 与 publish_results 同步维护）：按检出原级计入 P0-P3 统计与 Review 结论，行内/大象/汇总按正常 P0/P1 对待，但不进二次复审（尾注如实标注）；②**其他 analyzer**：全部归 confirm（待人工确认），不计入 P0-P3 与 Review 结论，原级记 description 尾注 + `_origSeverity`；归 confirm 而非降 P2 的原因：confirm 是 SEVERITY_ORDER 最低级，与内置同根因合并取高时不可能抬高内置结论（EXT 只能追加铁律）
- 子 Agent 返回非法格式 → 该 analyzer 状态 UNKNOWN 进 checks（计入失败计数，连续 3 次摘除 1h）；required=true 时由 Step 7 门禁拦结论

## 四、兼容模式：headless 纯脚本 analyzer（`run`）

analyzer frontmatter 声明 `entry` 且 `mode: script`（纯脚本型）时，可不用子 Agent，改用子进程模式（**`mode: agent` 禁止直跑**，loader `mode-guard` 拒绝）：
```bash
python3 "$SKILL_DIR/scripts/external_analyzer_loader.py" run \
  --input /tmp/cr_extan_input_{prId}_{analyzer名}.json \
  --output /tmp/cr_extan_result_{prId}_{analyzer名}.json \
  --provider ext-analyzer-{analyzer名}
# 收割时 collect 用 --result 指向 run 的产物（SOP AnalyzerResult 格式）
```
- 硬超时默认 1500s（frontmatter 60~1500s 可配，即 25 分钟）；全静默提前 ~5s kill（存活兜底）；任何失败 = FAILED/TIMEOUT 状态进封装体 checks（不再只是空数组），required=true 时 Step 7 门禁拦结论，否则可见降级

## 五、analyzer 失败自治（主 Agent 不阻塞,但状态可见、必选拦结论）

- 连续 3 次失败（超时/非法输出/受控失败）→ 自动摘除，冷却 1h 后恢复探测
- 摘除期间 run 直接返回 `provider-striken-out`（状态进 checks）
- 主 Agent 永不重试、永不等待、永不因 4-E 中止 CR 流程；但 required=true 失败会被 Step 7 门禁拦结论（「⚠️ 核验未完成」，不再 ✅通过）

## 六、验收（对接方 / 维护方）

```bash
python3 scripts/external_analyzer_loader.py self-test                # normal 场景
python3 scripts/external_analyzer_loader.py self-test --scenario p0-downgrade
```

场景矩阵：normal / empty / slow（有存活信号但超时）/ hang-silent（全静默熔断）/ not-json / nonzero / bad-ruleid / bad-anchor / modified-linetype / p0-downgrade / **mode-agent（mode:agent 直跑被 mode-guard 受控拒绝,封装体 FAILED）** / **no-engine（auto 无引擎按 agent 路由拒绝）**，全场景断言通过 = PASS。

### 门禁验收（publish 侧）

```bash
# required=true 且 FAILED → 结论必须是「⚠️ 核验未完成」而非 ✅通过
python3 - << 'PY'
import sys, json
sys.path.insert(0, "scripts")
from publish_results import load_extan_checks, evaluate_extan_gate, derive_conclusion
env = {"schema": "step4e-envelope/v1", "status": "FAILED", "findings": [],
       "checks": [{"analyzer": "ext-analyzer-arch-pr-verifier", "status": "FAILED",
                    "error": "no engine", "required": True, "mode": "agent"}]}
open("/tmp/t_gate.json", "w").write(json.dumps(env))
c, f, n = load_extan_checks("/tmp/t_gate.json")
g, r, _ = evaluate_extan_gate(c, n)
print(derive_conclusion({"p0":0,"p1":0,"p2":0,"p3":0,"confirm":0,"ext":0}, "", g, r))
# 期望输出: ⚠️ 核验未完成（必选专项审查未完成: ext-analyzer-arch-pr-verifier(FAILED)）
PY
```
