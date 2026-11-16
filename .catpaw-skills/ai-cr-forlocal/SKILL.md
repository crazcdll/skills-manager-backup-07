---
name: ai-cr-forlocal
description: "AI-CR-ForLocal:本地分支模式代码审查 Skill,专为 AI-SDLC / CatPaw IDE 集成开发设计。路由表驱动多 Agent 审查:diff 信号→规则命中量→动态决定审查路数与每路注入内容,四层审查(P0零容忍/P1稳定性/P2规范/P3性能)+业务逻辑/SDD一致性,成本与 diff 风险对齐。用户提供本地仓库路径 + 分支名,通过本地 git diff 获取变更,输出结构化 JSON 供 AI-SDLC 渲染。触发:用户提到「本地CR」「本地cr」「本地分支CR」「本地代码审查」「全栈CR」「全栈cr」「全栈代码审查」「帮我CR」「CR一下」「cr一下」「代码审查」「review本地」「ai-cr-forlocal」「SDLC」「AI-SDLC」,或提供本地仓库路径 + 分支名。不适用:仅有 PR 链接但无本地路径的场景(请使用 ai-pr-code-review)。⚠️ 推荐使用 GLM 5.2 及以上模型。"

skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - com.sankuai.it.ead.citadel
    prompt: 本技能所需的 token 占位符,请参考 mtsso-skills-official 说明获取和注入

metadata:
  skillhub.creator: "mengmuzi"
  skillhub.updater: "mengmuzi"
  skillhub.version: "V88"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "24320"
  skillhub.high_sensitive: "false"
---

# AI-CR-ForLocal:本地分支 Code Review 自动化

> 路由表驱动多 Agent CR:diff 信号 → 规则命中量 → 动态决定开几路、每路带什么,成本与 diff 风险对齐。

> 🚨 **执行强制要求(违反则本次 CR 无效)**:
> 1. **每个 Step 开始和结束必须在对话中输出进度**,格式见"过程可见性规范",禁止静默执行
> 2. 格式:`▶️ Step N:xxx 开始...` → 执行 → `✅ Step N:xxx 完成 - 关键结果`
> 3. 用户反馈"没有进度输出"说明违反了本规则,必须在下次执行时严格遵守

> 🧠 **上下文节约原则(强制执行,防止上下文溢出导致后半段流程丢失)**:
> 1. **对话中只放结论和进度,过程和细节全写文件**。读文件内容、逐条分析过程、规则匹配细节等**禁止在对话中展开**
> 2. Step 4 各子 Agent 读取文件后,对话中只输出 `✅ 已读取 N 个文件`,文件内容保持在工具调用结果中(不要复述)
> 3. Step 4 审查过程中,逐条分析不要在对话中逐条展开,完成后只输出汇总:`✅ 审查完成:P0=N,P1=N,P2=N,P3=N`
> 4. 播报只保留 **Step 级别**(`▶️ Step N` / `✅ Step N`),子步骤不在对话中单独播报

## 使用说明

### 概述

本 Skill 为 forLocal 定位:**本地宽度审查**。

**不涉及**:PR 评论、大象群播、多维表格写入。

**四层审查模型**(主 Agent + 子 Agent 协同):

| 层级 | 名称 | 审查内容 | 规则来源 | 执行者 |
|------|------|----------|----------|--------|
| **P0** | 零容忍 | 代码 BUG、SQL 失败、Spring 异常等 24 类运行时异常 | `zero-tolerance-checklist.md` + COE 踩坑规则 | 子 Agent 4-A-P0 |
| **P1** | 稳定性安全 | 异常处理、资源管理、并发安全、容灾降级、安全漏洞 | `stability-security-checklist.md`(高可用规范 HA/SEC)| 子 Agent 4-A-P1 |
| **P2** | 规范架构 | SOLID、命名、架构分层、Spring Boot、MyBatis、日志、测试 | `checklists/mt-java-coding-standards/` | 子 Agent 4-B |
| **P3** | 性能现代化 | 数据库优化、缓存、集合、RPC、内存 | `performance-checklist.md` | 子 Agent 4-A-P3 |

**附加审查维度**(子 Agent 并行执行):

| 维度 | 名称 | 审查内容 | 规则来源 | 执行者 |
|------|------|----------|----------|--------|
| **CU/L2** | 仓库自定义 + 平台L2规范 | 团队/项目自定义规则(命名约定、禁用 API、业务约束等)+ 平台L2团队规则 | 仓库 `.mdp/rules/` + `.catpaw/rules/` + `/tmp/cr_l2_rules_{repo}.md`(均无则不 spawn)| 子 Agent 4-C(V117 恢复独立路) |
| **BL** | 业务逻辑审查 | 功能遗漏、逻辑偏离、边界缺失、业务规则冲突(三源验证:SDD+ONES+上下文)| SDD 产物 + ONES 需求 + 上下文代码 | 子 Agent 4-D(始终执行)|
| **COE** | 踩坑规则 | 历史故障复发模式 | `references/coe-rules.md` | 融入 P0/P1(Step 3)|

**输出**:Issue JSON → `publish_results_local.py` 一体化发布

### 触发场景

| 环境 | 识别方式 | 输出形式 |
|------|----------|----------|
| **AI-SDLC 模式** | `setup-plan.sh --json` 注入参数(`INVOKE_MODE=sdlc`)| 结构化 JSON 写入 `/tmp/*.json`(schema 禁止增删改字段)|
| **CatPaw IDE 模式** | 用户在对话中手动提供参数 | 完整 Markdown CR 报告 + 修复交互 |

> **AI-SDLC 模式 = 无人值守**:全流程禁止任何人工确认/暂停(无 read、无降级确认、无 Step 7 修复交互),环境降级时自动选择 fallback 继续执行,仅在参数缺失这类硬性阻断时 exit 1。

**输入参数:**
- **本地仓库路径**(必须)
- **分支名**(必须)
- **base 分支**(可选,默认 `master`)
- **ONES 需求 ID**(可选)
- 无需 PR、无需推送到远端,直接读本地 git 变更

### ⚠️ 推荐模型

| 场景 | 推荐 | 说明 |
|------|------|------|
| 正式需求 CR | **GLM 5.2**(强烈推荐) | P0/P1 检出率最高 |
| 简单改动(文件数 < 10) | 轻量模型 | 速度快 |

### 全链路重试规则

所有 I/O 操作均遵循:**最多重试 4 次,每次间隔 2s,全部失败则输出到对话,不阻塞后续步骤。**(学城文档创建为 4 轮 × 每轮 3 次内部重试,每次间隔 2s)

---

## 执行流程概览(Step 0~3/5/8 为 Orchestrator 单命令)

```
Step 0: 获取输入参数 + 环境检查(PID 级缓存 60min)+ GitNexus 后台建图
  ├── 0A-前置: 获取 LOCAL_REPO_PATH/LOCAL_BRANCH/BASE_BRANCH
  ├── 0A: 环境自检(PID 级缓存 60min)
  └── 0B: GitNexus 后台建图(非阻塞,PID 落文件,Step 2B 前 tail --pid 等待)
Step 1: 获取 Diff + ONES 上下文(并行点 P1)
  ├── 1A: 获取本地 git diff + 空校验(空 diff → 零问题 SDLC JSON 后提前退出)
  ├── 1B: 从分支名提取 ONES ID + 获取需求上下文(与 1A 并行)
  ├── 1C: 设置仓库/操作者变量
  └── 1D: 脚本按后缀筛选前端候选；prep 返回后由主 Agent 核对模块用途
      └── 1F: 纯前端改动委托 fe-ai-review(模块证据确认纯前端时:spawn 前端审查子 Agent → issues 写入 step4.json → Step 5 接回主线)
Step 2: 规则匹配 + 上下文感知(并行点 P2)
  ├── 2A: SDD 规范检测(轻量:specs/ 有无 .md → SDD_AVAILABLE)
  ├── 2B: Layer 2 反查(系统性,全量并行 xargs -P 8)
  └── 2C: Layer 3 业务语义(领域知识 + ONES + SDD)
Step 3: 审查路由准备(轻量,无审查动作)
  ├── 3A: SDD 产物检测
  ├── 3A2: 自定义规则探测+预合并(.mdp/rules + .catpaw/rules)
  ├── 3A3: 平台L2团队规则拉取(fetch_l2_rules.sh,never-block)+ 4-D 合并输入文件生成(cr_4d_input_core.md + cr_4d_input_code.md)
  ├── 3B: 信号检测 → 读取 signal-routing-table.md → 扫描 diff → ACTIVE_SIGNALS + 信号驱动文件映射 → /tmp/cr_signals_{repo}.md + /tmp/cr_signal_rules.json
  └── 3C: 路由计划生成(route_plan.py)→ /tmp/cr_route_plan.json + /tmp/cr_route_4a_*.md(路由版 checklist)
Step 4: 多路并行审查(并行点 P3,路数由路由计划决定)
  ├── 4-Parallel: 4-A-P0 / 4-A-P1 / 4-A-P3 / 4-B / 4-C / 4-D 一次性批量 spawn(主 Agent 零终端命令,硬上限 7 路审查 + 1 路复审)
  │   ├── 4-A: 代码缺陷审查(P0零容忍/P1稳定性/P3性能,按路由计划拆 1~3 路,路由版规则注入)
  │   │   └── 输出 /tmp/cr_issues_{repo}_main_{p0|p1|p3}.json
  │   ├── 4-B: 规范检查(按路由计划 0~3 路逻辑域,零命中域不 spawn,全档硬上限 5 路)
  │   ├── 4-C: 自定义规则+平台L2规则统一审查(V117 恢复独立路,CU∪L2 任一存在即开,两者均无不 spawn,输出 /tmp/cr_issues_{repo}_step4c*.json)
  │   └── 4-D: 业务逻辑 + SDD 文码一致性审查(始终执行,档位化:lite=全量 / standard=核心 / full=核心+逻辑拆分两路,回归纯业务边界)
  ├── 4-Merge: 合并去重 → /tmp/cr_issues_{repo}_step4.json
  ├── 4-Review: 错报过滤 + 漏报扫描(DISMISS需硬证据,dismissed可追溯;如 P0+P1>0)
  └── 降级策略: 子 Agent 不可用时,主 Agent 串行执行
Step 5: 发布结果(publish_results_local.py 一体化发布)
Step 6: 输出报告(AI-SDLC JSON / CatPaw Markdown)
Step 7: Fix 交互流程(CatPaw IDE 专属)
Step 8: /tmp 临时文件清理(含 Layer 2 结果、建图 pid/log)
```

---

## Step 0~3: 准备阶段(单命令,Orchestrator)

▶️ **Step 0~3 开始**

**一条命令跑完** Step 0(环境+GitNexus后台建图)/ 1(diff+ONES+变量)/ 2(规则匹配+Layer2反查)/ 3(SDD检测+信号路由):

```bash
bash "$SKILL_ROOT/tools/cr-cli.sh" prep \
  --repo "$LOCAL_REPO_PATH" \
  --branch "$LOCAL_BRANCH" \
  --base "$BASE_BRANCH"
```

**完成后读取摘要** `/tmp/cr_prep_{repo}.json`(stdout 末行同内容):

```json
{
 "env": "ok|degraded",          // 环境自检
 "gitnexus": "building|skipped", // 后台建图(prep 已等待+落 PID)
 "diff_lines": "3583",           // diff 行数
 "substantive_files": "57",      // 实质变更文件数
 "empty_reason": "",             // 非空=diff 空,流程提前结束
 "ones_id": "FEVUO-2019-xxx",    // 分支名提取
 "ones_status": "ok|failed|no-cli|skipped", // failed=4-D 降级双源
 "operator_mis": "mengmuzi",     // 触发用户>git校验>config>unknown
 "custom_rules": "none|N",  // 3A2: .mdp/rules + .catpaw/rules 预筛后保留的规则文件数(none=4-C 无 CU 输入)
 "l2_rules": "none|N",      // 3A3: 平台L2规则拉取结果(none=4-C 无 L2 输入;none(skill-missing)/none(fetch-failed)/none(no-team-rules)/none(no-remote)/none(disabled)/none(arg-error) 标注降级原因;数字=拉取成功规则数)
 "source_context_files": "12",     // 1A3: 变更文件完整源码包文件数
 "input_core_ready": "true|false", // 3A3: /tmp/cr_4d_input_core.md 是否就绪
 "input_code_ready": "true|false", // 3A3: /tmp/cr_4d_input_code.md 是否就绪
 "signals_status": "ok|failed",  // /tmp/cr_signal_rules.json
 "layer2_status": "ok|degraded", // /tmp/cr_layer2_results/
 "sdd_available": "true|false",  // specs/ 目录检测
 "route_plan_status": "ok|failed",   // /tmp/cr_route_plan.json + /tmp/cr_route_4a_*.md
 "frontend_only": "true|false",   // 后缀筛出的前端候选，需核对模块用途
 "frontend_files": "file1.vue,file2.tsx"  // 前端文件清单(逗号分隔,仅 frontend_only=true 时有值)
}
```

**Agent 判断点**(读摘要后决定,脚本不判断):
- `empty_reason` 非空 → 输出"✅ 无需审查",SDLC 模式补 `publish --empty-result` 后结束
- `ones_status=failed` → 4-D 子 Agent 用"SDD+上下文"双源(不阻塞)
- `l2_rules` 为 none 的任何降级形态(skill-missing/no-team-rules/fetch-failed/no-remote/disabled/arg-error) → 4-C 只消费 CU 输入(如有);`l2_rules` ≥ 1 → 4-C 消费 `/tmp/cr_l2_rules_{repo}.md`
  - **报告降级时必须告知用户原因**（不得静默省略）：
    - `none(skill-missing)` → 提示"平台 L2 规则未拉取：未安装 mt-code-standards-setup，可执行 `mtskills pull mt-code-standards-setup` 启用；不影响仓库内规则审查"
    - `none(no-team-rules)` → 提示"仓库未登记平台团队规则集，属正常状态（未订阅/纯公司层）"
    - `none(fetch-failed)` → 提示"平台 L2 规则拉取失败（认证/网络），详见 `/tmp/cr_l2_extract_{repo}.log`，本轮降级为无 L2 审查"
    - `none(no-remote)` / `none(disabled)` → 本地仓库无 remote / 灰度开关关闭，无需用户动作
- `custom_rules` 与 `l2_rules` 均为 none → 4-C 不 spawn(零成本);任一 ≥1 → route_plan 自动开 4-C lane
- `signals_status/route_plan_status` 任一 failed → 按附录手工路径补跑该步
- `layer2_meta.layer2_available=true` → 4-D 直接消费 `/tmp/cr_layer2_results/` 产物;`layer2_available=false` → 4-D 允许只读自行反查(禁止终端探查),不可错误声称已读取 Layer2 结果
- `frontend_only` 仅为脚本候选信号。按完整变更清单定位所属 package / workspace，核对依赖、构建入口及实际源码；JS/TS 不默认前端，Java/Kotlin 不默认 Java 服务端，配置和依赖变更也按所属模块判断。
- 模块证据确认纯前端后走 Step 1F（包括未被后缀筛中的 DUO 协议或纯依赖变更）；确认 Java 服务端则走主流程。候选提前返回但实际为 Java 服务端时，按脚本补齐尚未执行的 Step 1B~3，再进入审查。
- 原生桥接按实现平台归属，Flutter 结合 Flutter SDK 声明与 Dart 实现确认。Node 服务端、原生、Flutter 或混合范围缺少相应审查能力时，明确未覆盖范围并停止完整结果发布，不能套用 Java/前端流程或用 unknown 掩盖覆盖缺口。
- 信号驱动的 4-B 分组:读 `/tmp/cr_signal_rules.json` 的 `agents`/`agent_files`

> ⚡ **降级路径**:cr-cli.sh 不可用时,直接查看 `tools/cr-cli.sh` 脚本内容,按其内部逻辑逐命令执行。
> ⚡ **python 单行/脚本化**:所有多行 python 已收编进脚本;Agent 侧禁止 inline 多行 python(CatPaw 终端工具不支持换行)。

✅ **Step 0~3 完成** - 摘要见 `/tmp/cr_prep_{repo}.json`,中间产物:diff/文件清单/规则匹配/Layer2结果/信号路由

---

## Step 1F: 纯前端改动委托（模块证据确认后执行）

> **触发条件**:主 Agent 根据完整变更清单和所属模块证据确认纯前端。候选提前返回时无需补跑 Step 2~3；已完成的准备结果可复用。此路径**跳过 Step 4**,委托 `fe-ai-review` 审查前端变更,产出 Issue JSON 后**直接进入 Step 5**。
>
> **混合改动**:本地入口尚未接入完整混合分派；记录未覆盖模块并停止完整结果发布，不能仅审后端后标记全部完成。

### 1F-1: fe-ai-review 依赖检测

```bash
mtskills list 2>/dev/null | grep -q fe-ai-review || mtskills i fe-ai-review --target-dir ~/.openclaw/skills
```

### 1F-2: spawn fe-ai-review 子 Agent

spawn 一个子 Agent 执行 fe-ai-review 审查(`runTimeoutSeconds=1200`):

- **attachments**:`/tmp/local_cr_diff.txt` + `/tmp/local_cr_files.txt`
- **task 要点**:
  - 对仓库 `$LOCAL_REPO_PATH` 分支 `$BASE_BRANCH...$LOCAL_BRANCH` 的前端变更执行代码审查
  - 审查范围使用完整变更清单中已确认的前端模块及相关配置、测试和工具；`frontend_files` 仅为后缀筛选线索。
  - 回传技术栈集合、对应模块与证据、未识别部分及单值登记建议；遵循 fe-ai-review 的技术栈识别规则。此次为上层委托，不执行 FE 独立看板上报或 PR 评论。
  - 审查完成后输出 Issue JSON 到 `/tmp/cr_issues_{repo}_fe.json`
  - Issue 格式与主流程一致(severity/ruleId/file/line/description/suggestion/source/summary/anomalyType/lineType/rule_sources)，字段约定见 [Issue JSON 格式](references/issue-json-schema.md)。
  - 每条 finding 必填 `rule_sources`，纯上下文传 `[]`；平台命中保留 `upstream_rule_id`（如 `fe-l1:ASYNC-001`），fallback 带标题编号（如 `FB01`），L3 无明确 ID 可省略该 ID。`ruleId` 保留原始编号，FE 前缀由本地主流程归一化。`source` 字段值 `fe_review`,`anomalyType`:bug/risk/smell/style
  - P0/P1/P2/P3 分级与主流程一致
- **ONES 上下文**:优先使用已拉取的上下文；prep 因前端候选提前返回时尚未执行 Step 1B，如分支名含 ONES ID，子 Agent 可从 `$LOCAL_BRANCH` 自行提取。

### 1F-3: 桥接到主线

> **注意**:prep 因前端候选提前返回时，尚未执行 Step 1B(ONES)和 1C(操作者 MIS 完整计算)，`operator_mis` 仅从环境变量取值或 fallback 到 config/unknown。

fe-ai-review 子 Agent 返回后:

1. 核对 FE 回传的技术栈和模块证据；与初判不一致时按本轮范围重新确认，未覆盖部分先补齐或明确停止。将集合、证据及单值选择理由写入 `CR_OVERVIEW`，设置 `TECH_STACK`。读取 `/tmp/cr_issues_{repo}_fe.json`,校验格式(JSON 数组,每条含必填字段)
2. **直接写入** `/tmp/cr_issues_{repo}_step4.json`(主流程 Step 4 的合并产物路径,4-Merge 跳过)
3. SDD_CHECK_RESULT 输出空(前端不适用 SDD:`has_spec=false, completeness=N/A`)
4. 跳到 **Step 5**(publish_results_local.py 一体化发布,参数与正常路径一致)

### 1F 降级

- `fe-ai-review` 不可用或安装失败 → 向用户明确告知"前端改动本轮未审查",终止流程
- 子 Agent 超时/返回格式异常 → 重新 spawn 一次(1 次),仍失败则告知用户
- **不要把纯前端改动丢给后端审查链路**

### 1F 播报

- `▶️ Step 1D:纯前端检测...`
- `✅ Step 1D:纯前端改动({n} 文件),委托 fe-ai-review`
- `✅ Step 1F:fe-ai-review 审查完成,{n0} P0 / {n1} P1 / {n2} P2 / {n3} P3`
- `⚠️ Step 1F:fe-ai-review 不可用,前端改动本轮未审查`
- `✅ Step 1D:已确认 Java 服务端改动,继续主流程`

✅ **Step 1F 完成** - 前端审查 issues 已写入 `/tmp/cr_issues_{repo}_step4.json`,直接进入 Step 5

---

## Step 4: 多路并行审查(4-A×3 / 4-B / 4-C / 4-D 全部子 Agent)

▶️ **Step 4 开始**

> **路由原则**:Step 4 开几路、每路带什么规则,由 prep 产出的 **`/tmp/cr_route_plan.json`** 决定(信号路由表 + 规则命中量 + diff 规模三档分流)。主 Agent 读摘要后照单 spawn,不自行增减路数。
>
> **路由声明单一真源**:4-A 的信号权重、section→SIG 映射、checklist 清单全部声明在 `references/rule-index.json`(`signal_weights` + `checklist_routing` 字段);4-B 的信号→文件映射在信号检测脚本内置(对齐 signal-routing-table.md)。route_plan.py / 信号脚本均为纯执行器,调权重、加信号、改映射只改 rule-index.json + signal-routing-table.md。
>
> **三档分流**(行数定基础档 ⊕ 风险分加权,阀值在 cr-config.yaml):
> | 档 | 条件 | 4-A | 4-B | 典型总路数 |
> |---|---|---|---|---|
> | lite | diff <300 行 且低风险 | 合一(P0+P1+P3 一路) | 合一(各逻辑域规则并一路) | **3** |
> | standard | 300~1500 行,或低行数但风险分≥4 | P0 + P1+P3 合并(2 路) | 按逻辑域 2 路 | **5** |
> | full | >1500 行,或风险分≥8,或命中高危信号+行数 standard | P0 + P1+P3 合并(2 路) | 按逻辑域 2 路 | **6**(4-D 拆两路) |
>
> **风险分**(信号分布×权重):SIG-DDL/SECURITY=3,SQL/MQ/RPC/CACHE/CONCURRENCY/COMPATIBILITY/IDEMPOTENCY=2,其余=1;任一高危信号命中 → 至少 standard。
>
> **条目级过滤(4-A 注入用路由版)**:route_plan 按信号+条目触发关键词∩diff 生成 `/tmp/cr_route_4a_{p0|p1|p3|all}.md`(保留全局校验头+命中条目,未命中条目不注入)。4-A spawn 时 attachments 用 route_plan.four_a[].inject 指向的路由版文件,**不再注入完整 checklist**。条目无可评估关键词 → 保守保留;解析异常 → 该文件回退全量(plan.entry_stats[].fallback=true 会标注)。
>
> **并行原则**:4-A 始终 P0 + P1+P3 合并(2 路,V118 优化,P1 稳定性与 P3 性能合并释放槽位给 4-B);full 档 4-D 拆两路(4-D-core 疑点验证 + 4-D-logic 全量逻辑扫描)。全部**一次性批量 spawn**,`sessions_yield` 汇合后 4-Merge。主 Agent 在 Step 4 阶段**零终端命令、零逐条审批**。
>
> 启动方式:主 Agent 一个 turn 内连续 spawn 全部子 Agent(4-A×3/4-B/4-D 用 `runTimeoutSeconds=1200`),`sessions_yield` 汇合后直接 4-Merge。
>
> **主 Agent Step 4 仅做三件事**:1组装 spawn 参数(规则文件 attachments 注入)2yield 等待 34-Merge + 复审触发判断。

### 4-Parallel: 按 route_plan 批量 spawn(动态路由)

#### 4-A: 三层审查子 Agent(P0 零容忍 / P1 稳定性 / P3 性能)

> 下表为 **full 档**默认形态;lite/standard 档由 route_plan 决定实际路数与清单组合--lite 档 4-A-all 输出仍写 `main_p0.json`(source=main_p0),merge glob 天然兼容。各路注入的规则文件一律用 route_plan 的 `inject` 字段(路由版),不用完整 checklist。

4-A 拆为两个独立子 Agent 并行执行(P1 稳定性与 P3 性能合并,V118 优化):

| 子 Agent | 规则输入(attachments 注入) | 输出文件 | 超时 |
|---|---|---|---|
| **4-A-P0** | 路由版 `/tmp/cr_route_4a_p0.md`(+ `coe-rules.md`) | `/tmp/cr_issues_{repo}_main_p0.json` | 1200s |
| **4-A-P1+P3** | 路由版 `/tmp/cr_route_4a_p1+p3.md`(P1+P3 合并) | `/tmp/cr_issues_{repo}_main_p1.json` | 1200s |

每个 4-A 子 Agent 的执行内容(task 模板见 `references/subagent-task-template.md` 4-A 节):
1. 规则文件已随 task 注入(跳过规则读取轮次),理解判定条件与正反例
2. 读取 `/tmp/cr_source_context.md`(变更文件完整源码包,prep 预提取)+ `/tmp/local_cr_diff_slim.txt`(瘦身 diff)+ `/tmp/cr_layer2_results/` 反查结果
3. P0 子 Agent 额外读取 `/tmp/cr_probe_mapper.txt`(prep 阶段 mapper wiring 探查产物,如有)与 Layer 3 业务语义 `/tmp/cr_business_context.md`(COE 规则 × 业务语义交叉判断)
4. 逐条规则与 diff 语义判定,命中输出 finding
5. **禁止执行终端探查命令**--探查类工作已在 prep 固化,子 Agent 只消费 `/tmp/cr_probe_*.txt` 产物;确需新证据时在 issue 的 description 里写明"需人工验证:xxx"
6. 输出 Issue JSON(文件写入工具一次性直写,禁止终端命令),格式参见 `references/issue-json-schema.md`,source 字段值 `main_p0` / `main_p1`(P1+P3 合并后统一用 `main_p1`)
7. **ruleId 规范(统一 `CR:` 前缀)**:
   - P0 零容忍:异常类型全名(如 `CR:NullPointerException`)或 COE 踩坑 `CR:R{n}-{m}`(如 `CR:R1-1`)
   - P1 稳定性/安全:`CR:{子类}-{序号}`(如 `CR:EH-01`、`CR:RM-03`、`CR:CC-02`、`CR:FT-01`、`CR:NP-01`、`CR:SEC-05`)
   - P3 性能:`CR:{子类}-{序号}`(如 `CR:DB-01`、`CR:CACHE-03`、`CR:RPC-02`、`CR:MEM-01`、`CR:JDK-01`)
   - **注意**:checklist 索引文件均已自带 `CR:` 前缀,照抄即可;SDD 文码一致性 `CR:SDD-ALIGN` 归 4-D

**Issue 必填字段**(P0/P1/P2):severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType, fix_type, fix_range, fix_code, fix_description
- `anomalyType`:异常类型(bug/risk/smell/style)
- `summary`:一句话摘要(≤50字),用于快速浏览
- `lineType`:行号类型(added/removed/context)

#### 4-B: 规范检查子 Agent(信号驱动逻辑域分组)

路数由 route_plan 决定:3 个逻辑域(code-data / runtime / security-search),按信号检测结果决定哪些域启动。子 Agent 读取路由版规则文件(route_plan 按信号+关键词命中裁剪,注入 `/tmp/cr_route_4b_{group}.md`),无路由版时回退读规则文件原文(`references/checklists/mt-java-coding-standards/` 下)。

| 逻辑域 | 包含规则 | 触发信号 |
|--------|---------|---------|
| **code-data** | JAVA-*、DB-*、DEP-01 | SIG-CONCURRENCY/EXCEPTION/LOG/COLLECTION/OOP/CONSTANT/INTERFACE/TEST/NPE/SQL/DDL/DEPENDENCY |
| **runtime** | HA-01~HA-11、HA-14 | SIG-RPC/CACHE/MQ/CONFIG/IDEMPOTENCY/COMPATIBILITY/ES/HBASE/RESOURCE/CONCURRENCY/EXCEPTION/SQL/NPE/LOG |
| **security-search** | SEC-01/02/03、HA-12、HA-13 | SIG-SECURITY/ES |

> 零信号兜底:ACTIVE_SIGNALS 为空时只启动 code-data 域(全规则),不四组齐开。
>
> **条目级裁剪(V116)**:route_plan 按信号+关键词命中生成 `/tmp/cr_route_4b_{group}.md` 路由版规则文件。4-B spawn 时用 `inject` 字段注入路由版,**不再注入完整规则文件**。无信号或解析异常 → 回退全量。

每个子 Agent:
- 读取 `/tmp/cr_source_context.md`(变更文件完整源码包,**优先读,禁止再 git show**)+ `/tmp/local_cr_diff_slim.txt`(瘦身 diff)
- **直接加载**:spawn 时注入 route_plan 路由版规则文件(`inject` 字段,`/tmp/cr_route_4b_{group}.md`),子 Agent 读取路由版规则进行审查;无路由版时按信号映射的规则文件路径列表读取完整规则文件原文
- 读取 `/tmp/cr_layer2_results/` 下的反查结果
- 输出到 `/tmp/cr_issues_{repo}_step4b_{group}.json`(文件写入工具一次性直写)
- source 字段值为 `{group}`
- **ruleId 规范**:直接使用规则文件中已定义的 `MT:` 前缀格式(如 `MT:java-l1:JAVA-02.N001`、`MT:java-l1:HA-01.HA-F001`、`MT:java-l1:DB-01.ORM001`、`MT:java-l1:SEC-01.SEC-A001`),照抄规则文件即可(规则文件内编号格式为 `java-l1:文件前缀编号.规则编号`)
- **severity 定级**:严格按信号路由表对应信号的「默认 P 级别」列定级,禁止仅因「强制」「禁止」措辞一律判 P0

子 Agent 的 task 描述参见 `references/subagent-task-template.md`。

#### 4-C: 自定义规则 + 平台L2规则审查子 Agent(V117 恢复独立路)

**核心目标**:统一消费两类规则输入,对变更代码逐条检查--
1. **CU(仓库自定义规则)**:`/tmp/cr_custom_rules_{repo}.md` -- prep 3A2 段自动探测并预合并(`.mdp/rules/team/` + `.mdp/rules/project/` + `.catpaw/rules/` 三目录,预筛除工作流/协作类后合并落盘,摘要字段 `custom_rules`)
2. **L2(平台团队规则)**:`/tmp/cr_l2_rules_{repo}.md` -- prep 3A3 段经 `fetch_l2_rules.sh` 从平台拉取(依赖 mt-code-standards-setup skill,never-block,降级不影响其余流程)

**启动条件**(route_plan 自动判断,主 Agent 按 plan 逐项 spawn):CU ∪ L2 任一可注入即开 4-C lane;两者均无则不 spawn(零成本)。槽位不足时 4-C 降级跳过(均显式写入 route_plan 输出的 `skipped_lanes`):①整路跳过(reason=slot_exhausted, agent=4-C)→规则检查本轮全跳过;②分片跳过(agent=4-C-shards, dropped=N)→保留的分片仍 spawn,超出槽位的分片跳过。主 Agent 需在综述中声明对应范围的跳过。

**分片护栏**(与 4-C 通用契约一致):两缓存合计 > 30KB → 按 `##` 段边界切分,上限 3 分片(route_plan 自动产出 `/tmp/cr_4c_shard_{repo}_{n}.md`,shard 输出 `/tmp/cr_issues_{repo}_step4c_{n}.json`)。

**去重防御**:本地 `.mdp/rules/team/` 规则集ID与平台 L2 重复 → 以平台为准(prep 已探测并 emit `l2_dup`,4-C 输入提示平台优先)。

**ruleId 规范**(采纳率分口径统计的关键,禁止混用):
- CU 规则 → 前缀 `CU:`(如 `CU:TEAM-001`、`CU:naming-01`)
- L2 规则 → 格式 `L2:{规则集ID}:{稳定标识}`(如 `L2:new-be-l2:FE-01.N001`);规则文件未提供稳定标识时用 `L2:{规则集ID}:{文件名去.md}` 占位;照抄规则文件已定义标识,禁止子 Agent 自行编号

**severity 定级**:
- CU 沿用既有定级:规则标注「P0」或「零容忍」→ P0;「建议」或「推荐」→ P2;未标注 → P3
- L2:「严重/高」→ P1;「中(建议修复)」→ P2;「低/提示」→ P3;未标注 → P3

**输出**: `/tmp/cr_issues_{repo}_step4c.json`(分片时为 `step4c_1/2/3`),`source` 固定填 `step4c`,`ruleFile` 带规则来源(L2 规则带规则集目录前缀,与分段标题一致)。任务模板见 `references/subagent-task-template.md` 4-C 节。

**返回校验**:每条 issue 的 ruleId 必须以 `CU:` 或 `L2:` 开头 → L2 来源标了 `CU:`(或反之) → 纠正前缀后落盘。

#### 4-D: 业务逻辑 + SDD 文码一致性审查子 Agent

**核心目标**:验证变更代码的业务逻辑正确性(功能遗漏/逻辑偏离/边界缺失/业务规则冲突)+ SDD 文码一致性(spec 覆盖 + 双向比对)。**有 SDD 产物时以 spec 为强依据**;**无 SDD 时基于上下文逻辑**(本地仓库完整代码 + ONES 语义),不因缺 SDD 降级跳过。

**边界**:只关注业务逻辑层面问题,不检查代码缺陷(4-A×3)、编码规范(4-B)、自定义/L2规则(归 4-C,V117 拆出)。**P1 证据链复核统一归 4-Review 复审**,4-D 只负责发现并输出。

**始终执行**:不因缺少 SDD 产物而跳过。经模块证据确认的纯前端路径不经过 Step 4。

**审查模式(V116)**:route_plan 按档位设置 `mode` 字段,full 档设 `split=true` 拆为两路--
- lite 档 → `mode=full_scan`,`split=false`:4-D 不拆,全量业务逻辑扫描 + SDD 完整比对 + 疑点清单验证
- standard 档 → `mode=core_only`,`split=false`:4-D 不拆,只验证疑点清单 + SDD 只查 `is_sdd=true` 条目 + Layer2 只看 `impact_depth >= 2` 高影响项;零疑点时只做契约变更检查(接口签名变化、数据结构字段增删),不做逐函数逻辑推演
- full 档 → `mode=core_only`,`split=true`:4-D 拆为 **4-D-core** + **4-D-logic** 两路并行--
  - **4-D-core**(`mode=core_only`):疑点清单验证 + SDD `is_sdd=true` 契约检查
  - **4-D-logic**(`mode=full_scan`):全量业务逻辑扫描 + SDD 完整比对(不消费疑点清单,疑点验证归 4-D-core)
> 大 PR 聚焦核心:疑点清单是 4-D-core 的唯一审查来源,主 Agent 组装疑点清单时需更充分(宁多勿漏)。4-D-logic 负责全量补漏,两路结果在 4-Merge 合并。
> 路数变化:full 档 `max_subagents≥7` 时最大 7 路审查(4-A×3 + 4-B×1 + 4-D-core + 4-D-logic + 4-C);`max_subagents<7` 时降级不拆分(4-D 单路 full_scan)。4-Merge 需合并 4-D-core + 4-D-logic 的 issues(如拆分)。

**输入源**(V117 合并版,6 源 → 2 文件 + 文件清单):
1. **核心上下文**(`/tmp/cr_4d_input_core.md`,prep 生成基础框架:业务上下文 + `<!-- SUSPECTS_PLACEHOLDER -->` + `<!-- SDD_ALIGN_PLACEHOLDER -->`,主 Agent spawn 4-D 前填充后两段;自定义规则已迁出至 4-C 输入,不再注入本文件)
2. **代码上下文**(`/tmp/cr_4d_input_code.md`,prep 生成:source_context 全量 + diff_slim 拼接)
3. 变更文件清单(`/tmp/local_cr_files.txt`)
> SDD 产物(`$LOCAL_REPO_PATH/specs/` 下的 spec 文件)不合并,4-D 单独读取

**主 Agent 疑点清单(spawn 4-D 前,结构化 JSON 准备)**:

主 Agent 在 spawn 4-D 前,将疑点写入 `/tmp/cr_suspects_{repo}.json`,格式:
```json
[
  {"id": "S1", "type": "domain_rule", "file": "src/Foo.java", "line_hint": "L42", "desc": "裸 shopId 传入,疑跨体系混用", "source": "domain_knowledge"},
  {"id": "S2", "type": "ones_verify", "file": "src/Bar.java", "line_hint": "", "desc": "ONES 验收条件要求校验金额非负,diff 未见校验", "source": "ones_acceptance"},
  {"id": "S3", "type": "sdd_align", "file": "src/Baz.java", "line_hint": "L100", "desc": "SDD 要求 is_sdd=true 对齐,方法签名不符", "source": "sdd_alignment"},
  {"id": "S4", "type": "layer2_impact", "file": "src/Qux.java", "line_hint": "", "desc": "Layer2 反查此方法被 3 个消费方调用,签名变更影响重大", "source": "layer2"}
]
```
来源:1领域知识库触发映射命中 2ONES 验收条件 × diff 交叉 3SDD alignment_issue 4Layer2 反查高影响项。
> 写入 `/tmp/cr_suspects_{repo}.json` 后,4-D 子 Agent 按结构化清单逐条验证。

疑点来源详述:
1. **领域知识库触发映射命中**:读 `/tmp/cr_business_context.md` 的「CR 触发规则映射」节,对照 diff 命中项(裸 `shopId` 无前缀、`dpShopId` 传美团接口、`SYS_SKU_SHOPS` 写入等)→ 每项一个疑点
2. **ONES 验收条件 × diff 交叉**:验收点在 diff 中找不到对应实现 → 疑点(潜在 BL:FUNC-MISS)
3. **SDD alignment_issue**:spec 有但代码没做的条目(仅 has_spec=true 时)
4. **Layer2 反查暴露的消费方变更**:高影响消费方且 diff 改了其依赖的契约 → 疑点
> 疑点宁多勿漏(4-D 会逐条验证并丢弃不成立的),但每条要写明触发来源。零疑点时写空数组 `[]`。
>
> **standard/full 档加强**:`mode=core_only` 时 4-D-core 不做自主全量扫描,疑点清单是唯一审查来源。主 Agent 组装时需更充分:1领域知识库映射逐条过 2ONES 验收条件逐条交叉 3Layer2 高影响项(`impact_depth >= 2`)逐个生成疑点。

**检出范围(严格限定)**:
- ✅ 只报:功能遗漏、逻辑偏离、边界条件缺失、业务规则冲突
- ❌ 禁止报:代码级缺陷(NPE/异常处理/资源泄露/线程安全)、编码规范、自定义/L2规则(归 4-C)

**证据链定级(强制)**:
- 三源一致(SDD+需求+上下文)→ P0/P1
- 两源一致 → P1/P2
- 仅单源推断 → `confirm`(人工复审)
- 禁止输出无依据的推断

**输出**:
- lite/standard 档:`/tmp/cr_issues_{repo}_step4d.json`(4-D 单文件)
- full 档:`/tmp/cr_issues_{repo}_d_core.json`(4-D-core)+ `/tmp/cr_issues_{repo}_d_logic.json`(4-D-logic),merge glob 天然兼容

SDD 问题也进对应输出文件,`ruleId` 用 `CR:SDD-ALIGN`。业务问题四分类 `BL:FUNC-MISS` / `BL:LOGIC-DEVIATE` / `BL:BOUNDARY-MISS` / `BL:RULE-CONFLICT`,`source` 字段值为 `step4d_core`(4-D-core)/ `step4d_logic`(4-D-logic)。**另输出 SDD 结论块**(主 Agent 从最终回复文本解析,不单独落盘):`[SDD_CHECK_RESULT] has_spec/ completeness/ alignment_rate/ alignment_issues/ suggestions [/SDD_CHECK_RESULT]`(格式见 sdd-check-guide.md,供学城文档 SDD 章节 + publish 的 is_sdd/alignment 参数)

**SDD 校验部分(轻量,非独立步骤)**:
- 完备性:变更涉及业务逻辑但无 spec → 输出 `CR:SDD-ALIGN` P2;纯配置/测试/重构 → 不报
- 文码比对(仅有 spec 时):spec 关键设计决策 vs 代码实现双向比对,逻辑性不一致 P1、新增关键逻辑未覆盖 P2、命名微差忽略
- alignment_issue 同时是业务疑点线索:spec 有但代码没做 → 大概率 `BL:FUNC-MISS`,两项合并报一条(SDD-ALIGN 附注),不重复计两条
- 校验规则详见 `references/sdd-check-guide.md`(SDD-1/SDD-2)

**去重原则**:与 4-A/B/C 命中同一 file+line+同类问题时,丢弃 4-D 的重复项。full 档 4-D-core + 4-D-logic 命中同位置时,保留信息更丰富的一方。

**full 档 4-D 拆分对照表**:

| 子 Agent | mode | 职责 | 输出文件 | source |
|---|---|---|---|---|
| **4-D-core** | core_only | 疑点清单验证 + SDD `is_sdd=true` 契约检查 | `/tmp/cr_issues_{repo}_d_core.json` | `step4d_core` |
| **4-D-logic** | full_scan | 全量业务逻辑扫描 + SDD 完整比对(不消费疑点清单) | `/tmp/cr_issues_{repo}_d_logic.json` | `step4d_logic` |
| **4-C**(如 CU∪L2 任一存在) | - | 自定义规则(CU) + 平台L2规则统一审查 | `/tmp/cr_issues_{repo}_step4c.json`(分片时 `step4c_1/2/3`) | `step4c` |

### 4-Merge: 合并去重

合并所有 Issue JSON 文件并去重:

```bash
bash "$SKILL_ROOT/tools/cr-cli.sh" merge-review --repo "$REPO_PATH"
```

> 一条命令完成 4-Merge 合并去重 + 复审触发判定(P0+P1 ≥ 3 才走复审)+ 复审预处理与 spawn 指令输出。子 Agent 复审完成后另跑 `cr-review-apply.sh`。

脚本自动处理:
- 加载 `/tmp/cr_issues_{repo}_*.json`(4-A×3 / 4-B / 4-D 或 4-D-core+4-D-logic 输出),跳过 step4/merged 产物
- 原子写兜底:`.tmp` 文件恢复
- **三级去重**:
  1. **4-D 优先丢弃**:4-D 与 4-A/B/C 命中同 file+line+anomalyType → 保留 4-A/B/C 的,丢弃 4-D 的重复项
  2. **精确重复**(同 file + line + ruleId 完全相同)→ 保留首个
  3. **完全重叠**(同 file + line + anomalyType 相同)→ 合并为一条:ruleId 加号拼接(顺序 `CR:xxx + MT:yyy + L2:zzz + CU:www + FE:xxx`,BL: 不参与拼装但记入 mergedRuleIds);severity 取更高者;description/risk/suggestion/code 取内容更丰富的一方。注:4-C 的 anomalyType 枚举为 custom/team,与 4-A 的 bug/risk/smell/style 不同 → 同位置 4-A 与 4-C 命中不合并(各自保留,不算重复计数)
- **部分重叠**(同 file + line 但 anomalyType 不同)→ 各自独立保留,不合并
- 格式校验:缺必填字段的条目跳过并告警
- 输出 `/tmp/cr_issues_{repo}_step4.json` + P0/P1/P2/P3 计数

**返回校验(防白跑)**:
- **格式校验**:每个子 Agent 输出必须是 JSON 数组(`[]` 或 `[{...}]`),非法格式 → 重新 spawn(最多 1 次)
- **空数组校验**:返回 `[]` 但分配了 ≥3 个规则文件 → 疑似白跑 → 重新 spawn,task 强调"必须逐文件逐规则检查"
- **ruleId 校验**:4-B 每条 issue ruleId 必须以 `MT:` 开头 → 缺失前缀补上;4-A×3 必须以 `CR:` 开头 → 裸编号补 `CR:` 前缀;自定义 `CU:`;业务逻辑 `BL:`
- **必填字段校验**:severity/ruleId/anomalyType/summary/file/line/description/suggestion/source 齐全 → 缺字段重新 spawn。P0/P1 额外校验 fix_type/fix_range/fix_code/fix_description
- **原子写规范**:子 Agent 必须用文件写入工具**一次性直写**完整 JSON。禁止 `echo`/`tee`/`mv`/`python -c` 等终端命令。校验时发现 JSON 解析失败 → 检查同名 `.tmp` 遗留 → 存在则按 `.tmp` 内容恢复;不存在则重新 spawn

> ⚠️ **必须写入文件**,不能只在对话中合并。Step 5 的 `publish_results_local.py --issues-file` 需要读取此文件。

### 4-Review: P0/P1 快速复审(脚本化)

**定位**:只干一件事--**拿注入的现成证据做判定**(有硬证据的误报剔除 + 拿不准的转人工)。上下文不足直接 `to_human`,不追代码(追代码验证是 4-D 的职责)。DISMISS 须硬证据:已有防护/规则不适用/路径不可达。

**执行方式**:已由 `cr-cli.sh merge-review` 自动执行(P0+P1 ≥ 3 时输出 spawn 指令;< 3 输出 `REVIEW_STATUS=skipped` 直接进 Step 5)。

脚本内部逻辑:
1. 读取 `/tmp/cr_issues_{repo}_step4.json`,统计 P0+P1 数量
2. **P0+P1 < 3** → 跳过复审,输出 `REVIEW_STATUS=skipped`
3. **P0+P1 ≥ 3** → 调用 `prep_review_input.py` 预处理(上下文预切 + 仓库预读)
4. 按 issue 数量和文件数分流(small/large),输出 spawn 指令
5. 主 Agent 据指令 spawn 子 Agent,完成后执行 `cr-review-apply.sh` 应用结果

**漏报扫描(第二轮)**:默认关闭(config `review_miss_scan: false`)。

**预处理(脚本内自动调用,子 Agent 零 diff 读取)**:
- 每条 P0/P1 issue 的 5 字段(file/line/ruleId/severity/summary)+ **预切好的 ±30 行上下文**直接进输入 JSON;**文件不在 diff 中时预读仓库源码 ±30 行注入**
- 规则文件按 distinct ruleId 去重后拼成合集,spawn 时随 `attachments` 注入

**执行方式(按规模分流,`runTimeoutSeconds=1200`)**:
- **小规模**(P0+P1 ≤ 8 条 且 涉及文件 ≤ 3 个):spawn 1 个子 Agent 串行两轮
- **大规模**(超过阈值):第一轮按 file 分片(k = min(4, 文件数))并行;第二轮漏报扫描独立子 Agent 同时 spawn

参见 `references/step4-review-guide.md`,两轮工作:
- **第一轮·快速判定(三态,零仓库读取)**:每个 P0/P1 issue 只给 5 字段 + 预切上下文。**禁止读取仓库/diff 文件,上下文不足直接 to_human**。verdict:**confirmed** / **dismissed**(须引用具体代码证据) / **to_human**
- **第二轮·漏报扫描**(默认关):对未覆盖文件 hunks 扫描高风险模式
- **平衡原则**:dismissed 记录保留可追溯;to_human 一律转 confirm 不硬删;复审超时/失败默认 confirmed

**应用复审结果**:
```bash
bash "$SKILL_ROOT/scripts/cr-review-apply.sh" --repo "$REPO_NAME"
```

### 降级策略(子 Agent 不可用或超时时)

**硬超时规则**：所有子 Agent `runTimeoutSeconds=1200`（20 分钟）。超时后该路结果缺失，**不等待、不重试**，直接进入 4-Merge 继续。缺失路的输出文件为空，merge 自动跳过。

如果子 Agent 不可用（spawn 失败、超时）：
- **超时处理**：某路超时后跳过该路，已有结果正常 merge，在最终报告标注「4-A-P1 超时未完成」等
- spawn 失败时逐组串行执行：先 4-A-P0 → 4-A-P1 → 4-A-P3 → 4-B 各逻辑域 → 4-D（full 档先 4-D-core 再 4-D-logic）
- 串行模式下 4-A 仍输出三个独立文件（`main_p0/p1/p3.json`），merge 逻辑不变
- full 档 4-D 拆分路降级为串行：先 4-D-core 再 4-D-logic，各自输出独立文件
- 降级场景不受红线第 13 条约束（因无子 Agent 在运行）

✅ **Step 4 完成** - 各路审查完毕(路数见路由计划),合并后共 {N} 条 issue

---

## Step 5: 发布结果(单命令)

▶️ **Step 5 开始**

```bash
bash "$SKILL_ROOT/tools/cr-cli.sh" publish \
  --repo "$LOCAL_REPO_PATH" \
  --branch "$LOCAL_BRANCH" \
  --base "$BASE_BRANCH" \
  --operator-mis "$OPERATOR_MIS" \
  --issues-file /tmp/cr_issues_${REPO_NAME}_step4.json \
  --overview "$CR_OVERVIEW" \
  -- --tech-stack "$TECH_STACK"
```

脚本内部:publish_results_local.py 一把跑(学城→DB submit-task→SDLC JSON→本地报告)。

> **前端路径接入**:已确认纯前端并完成 Step 1F 时,issues 来自 Step 1F,已写入 `/tmp/cr_issues_{repo}_step4.json`。publish 脚本无需区分来源,按统一 schema 处理。SDD 参数固定 `--no-sdd`。

**日志分离**:进度日志 → `/tmp/cr_publish_{repo}.log`;报告 → stdout(+ `/tmp/cr_publish_{repo}.stdout`)。
**空结果模式**:diff 空时传 `-- --empty-result --reason "diff 为空"`。
**SDD 参数**:4-D 的 SDD_CHECK_RESULT 解析后透传--`has_spec=true` 加 `--is-sdd --alignment-rate "92%"`,否则省略(默认 --no-sdd)。前端路径固定 `--no-sdd`。
**技术栈上报**：按本轮模块证据与 FE 回传结论设置 `TECH_STACK`，值域为 `java/nodejs/mrn/max/miniprogram/duo/react/android/ios/harmony/native/flutter/unknown`。已确认栈仅涉及 DUO、Max、MRN、React 时，按 `DUO > Max > MRN > React` 取最高项；其它组合按本次实质变更确定主导栈，无法确定、框架未支持或证据不足时填 `unknown`，不将 Vue 等框架登记为 React。完整栈集合、模块证据及覆盖边界写入 `CR_OVERVIEW`。发布脚本只规范化和校验显式值，缺失或非法值登记 `unknown`；`frontend_only` 不决定框架，登记值也不替代审查覆盖检查。

> 建议在 Step 4 合并完成后,主 Agent 生成变更综述(1~2 句)赋给 `CR_OVERVIEW` 再执行。

✅ **Step 5 完成** - 状态摘要已输出(学城/DB/SDLC 各一行),报告见 stdout

---

## Step 6: 输出报告

▶️ **Step 6 开始**

### AI-SDLC 模式

读取 `/tmp/ai_cr_result_${REPO_NAME}_${BRANCH_SAFE}.json`(`BRANCH_SAFE=${LOCAL_BRANCH//\//-}`,与 Step 5 `write_dlc_json` 的分支名处理一致),输出给 AI-SDLC 渲染。

**DLC JSON Schema(字段冻结,禁止增删改)**:
```json
{
  "cr_result": "PASS | PASS_WITH_SUGGESTION | NEED_FIX | NEED_REDESIGN",
  "p0_count": 0,
  "p1_count": 0,
  "p2_count": 0,
  "p3_count": 0,
  "km_doc_url": "https://km.sankuai.com/collabpage/xxx",
  "pr_url": null,
  "repo": "org/repo-name",
  "branch": "feature/xxx",
  "changed_files": 12,
  "cr_at": "2026-08-24T22:35:00+08:00",
  "issues": [
    {
      "level": "P0|P1",
      "file": "src/main/java/com/xx/Foo.java",
      "line": 42,
      "title": "问题标题(不超过50字)",
      "suggestion": "修复建议(自然语言,供人工理解)",
      "fix_type": "REPLACE|INSERT|DELETE|REFACTOR",
      "fix_range": { "startLine": 40, "endLine": 45 },
      "fix_code": "// 完整可粘贴的修复代码,保持原有缩进",
      "fix_description": "一句话说明改了什么、为什么"
    }
  ]
}
```

**字段映射**(Issue JSON → DLC JSON):
- `severity` → `level`
- `summary` → `title`
- `description` 合并入 `suggestion`
- `ruleId` / `source` / `anomalyType` / `lineType` / `code` **不写入** DLC JSON
- `fix_type` / `fix_range` / `fix_code` / `fix_description` 直接透传
- `pr_url`:本地分支模式固定 `null`
- `issues`:仅含 P0/P1,P2/P3 只计数不列详情
- `km_doc_url`:学城文档创建失败时为 `null`

### CatPaw IDE 模式

读取 `publish_results_local.py` 输出的 local_report(stdout),在对话中展示完整 Markdown 报告。

✅ **Step 6 完成** - 报告已输出

---

## Step 7: Fix 交互流程(CatPaw IDE 专属)

▶️ **Step 7 开始**

> 仅在 CatPaw IDE 模式下执行。AI-SDLC 模式跳过此步。

### 7A. 报告展示与选择引导

Step 6 报告输出后,主动引导用户:

```
📋 CR 报告已生成(P0 {n0} / P1 {n1} / P2 {n2} / P3 {n3} / confirm {nc})
如需修复,请回复:
- 【修复 P0】/【修复 P1】- 按严重级批量修复
- 【修复 1 2 5】- 按编号指定修复(空格分隔,可混合不同级别)
- 【修复全部】- 除 confirm/dismissed 外全部修复
- 【跳过】- 不修复,仅保留报告
> confirm 类需先人工判断是否真问题(回复 confirm 编号可展开详情)
```

### 7B. 逐个修复循环

> 前端路径的 issue(`source=fe_review`)同样适用此流程,`catpaw apply` 对前端文件生效。

对用户选中的每个 issue(按严重级从高到低排序执行):

1. **展示修复计划**:issue 编号 + ruleId + 一句话摘要 + 修复思路
2. **执行修复**:使用 `catpaw apply` 修复对应 issue
3. **验证变更**:`git diff` 展示修复后 diff,确认变更范围与预期一致
4. **单 issue 确认**(用户可选):若一次修复多个,中途可回复【跳过这个】/【停下】

### 7C. 修复收尾

1. 汇总本次修复:成功 {a} / 跳过 {b} / 失败 {c}
2. 修复全部完成后提示:
   - `git add -A && git commit -m "fix: AI-CR 修复 {n} 处问题"`(用户确认后执行,或用户自行提交)
3. 如有失败项,说明失败原因,建议人工处理
4. confirm 类问题如有展开需求,逐条展示代码上下文供人工判断

✅ **Step 7 完成** - 修复闭环(修复 {a} / 跳过 {b} / 失败 {c})

---

## Step 8: 清理(单命令)

▶️ **Step 8 开始**

```bash
bash "$SKILL_ROOT/tools/cr-cli.sh" clean --repo "$REPO_PATH"
```

> `--repo` 指定时同时清理仓库内 GitNexus 产物(`.gitnexus/`、`.claude/skills/gitnexus/`)并检查 `.gitignore`;不传只清 /tmp。

清理两部分:

**1. /tmp 中间产物**(无条件执行):diff/规则路由版/Layer2/信号/issues/prep摘要/publish日志/建图残留等。
> ⚠️ **保留最终产物**:`/tmp/ai_cr_result_*.json`(SDLC JSON)不在 Step 8 清理范围内,CR 完成后保留。

**2. 仓库内 GitNexus 产物**(`$LOCAL_REPO_PATH` 存在时执行):
- `$REPO_ROOT/.gitnexus/` - 索引数据目录
- `$REPO_ROOT/.claude/skills/gitnexus/` - 6 个 SKILL.md

清理完成后检查 `.gitignore`,若缺少 GitNexus 相关条目则提醒添加。

> ⚠️ 不清理 `~/.gitnexus/registry.json`(全局注册表)。
> ⚠️ **prep 已内置预清理**:`cr-cli.sh prep` 开头会自动执行一遍相同的清理逻辑。Step 8 的显式清理仍保留,用于 publish/fix 完成后释放空间。

✅ **Step 8 完成** - 清理完毕

---

## 附录 A:文件清单与并行点

| 文件 | 用途 |
|------|------|
| 文件 | 用途 | 说明 |
|------|------|------|
| `SKILL.md` | 主流程 | 本文件 |
| `scripts/env-check.sh` | Step 0 | 环境自检 + PID 级缓存 |
| `scripts/merge_issues.py` | Step 4-Merge | 合并去重子 Agent Issue JSON(两级去重 + 格式校验) |
| `scripts/cr-review.sh` | Step 4-Review | 复审编排(预处理 + 分流判定 + spawn 指令输出) |
| `scripts/cr-review-apply.sh` | Step 4-Review | 应用复审结果到 issues 文件 |
| `scripts/publish_results_local.py` | Step 5 | 一体化发布脚本 |
| `scripts/route_plan.py` | Step 3C | 路由计划生成器(信号驱动 + 风险分档) |
| `scripts/prep_review_input.py` | Step 4-Review | 复审预处理(上下文预切 + 仓库预读) |
| `scripts/cr_record.py` | Step 5 | DB 上报 |
| `references/rule-index.json` | Step 2A | 规则分组配置 |
| `references/issue-json-schema.md` | Step 3/4 | Issue JSON 格式定义 |
| `references/zero-tolerance-checklist.md` | P0 | 规则索引 |
| `references/stability-security-checklist.md` | P1 | 规则索引 |
| `references/coding-standards-checklist.md` | P2 | 规则索引 |
| `references/performance-checklist.md` | P3 | 规则索引 |
| `references/layer2-impact-analysis.md` | Step 2B | Layer 2 反查指南 |
| `references/subagent-task-template.md` | Step 4 | 子 Agent Task 模板 |
| `references/comment-templates.md` | Step 6 | 报告模板 |
| `references/domain-knowledge.md` | Step 2C | 领域知识 |
| `references/local-git-diff-guide.md` | Step 1 | 本地 diff 指南 |
| `references/gitnexus-setup-guide.md` | Step 0 | GitNexus 安装指南 |
| `references/citadel-write-guide.md` | Step 5 | 学城文档写入指南 |
| `references/sdd-check-guide.md` | Step 3 | SDD 校验指南 |
| `references/coe-rules.md` | - | COE 规则参考 |
| `references/layer3-business-context.md` | Step 2C | Layer 3 业务上下文 |
| `references/signal-routing-table.md` | Step 3B | 信号路由表 |
| `references/step4-review-guide.md` | Step 4-Review | 错报过滤+漏报扫描指南 |
| `references/checklists/mt-java-coding-standards/` | P2 | 完整规则文件目录 |
| `cr-config.yaml` | - | 团队配置文件 |
| `tools/cr-cli.sh` | - | CLI 入口 |
| `tools/cr-hook.sh` | - | Git Hook 入口 |
| `tools/cr-ide-adapter.sh` | - | IDE 适配器 |
| `fe-ai-review`(外部 skill) | Step 1F | 前端代码审查(skill_id: 50498) |

### 并行点

| 并行点 | 位置 | 说明 |
|--------|------|------|
| P0 | Step 0B | GitNexus 建图后台运行,与 Step 1~3 并行(Step 2B 前 tail --pid 等待,90s 兜底) |
| P1 | Step 1 | git diff 与 ONES 需求获取并行 |
| P2 | Step 2 | 规则匹配与 Layer 2 反查并行 |
| P3 | Step 4 | 4-A×3 / 4-B / 4-D 多路并行审查 |
| P4 | Step 2B | Layer 2 反查全量并行(`xargs -P 8`,无批次限制) |
