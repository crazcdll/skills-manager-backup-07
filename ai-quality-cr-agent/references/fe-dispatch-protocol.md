# FE 技术栈委托审查协议(2H)
> 本文件定义 ai-quality-cr-agent 如何识别前端变更、委托 fe-ai-review,并将结果合流到统一发布流程。
> 前端代码由 fe-ai-review 专业审查;主 Agent 负责范围冻结、通用上下文、混合审查协调、结果完整性和发布门禁。

## 委托触发条件(Step 2F 之后、Step 3 之前判定)

判定输入:Step 2F 本轮独立目录中的 `$CR_CHANGED_FILES_FILE`、`$CR_DIFF_FILE`、`$CR_MODE_INFO_FILE`,以及各文件所属 package 的 manifest 和实际用途。交接时传入实际绝对路径,不使用共享临时路径。

### 第一步:排除噪声

以下文件不计入代码改动行数,但清单保留供范围核对:

- lock 文件:`package-lock.json`、`pnpm-lock.yaml`、`yarn.lock`、`bun.lockb`
- 压缩产物:`*.min.js`、`*.min.css`
- 构建产物目录:`dist/`、`build/`、`out/` 下的文件
- 自动生成:`*.generated.*`、`__generated__/` 下的文件

清洗后没有实质代码变更时,继续检查 manifest、配置、依赖和生成来源的变化;标明实际覆盖范围,不得凭「全噪声」推导已完成 Java 或前端代码审查。

### 第二步:按文件所属 package 和用途分类

1. **frontend**:组件、页面、浏览器/小程序客户端及其样式、模板。`.tsx/.jsx/.vue/.svelte` 是候选信号,需要结合实际入口和用途确认。
2. **backend**:Java 服务端,或 Node/Nest/Express/Koa 等服务端入口、controller、数据库/RPC 访问逻辑。`.ts/.js` 不能仅凭后缀归入前端;按最近的 `package.json`、workspaces 归属、scripts、依赖和代码用途判断。
3. **native**:Android、iOS、鸿蒙等原生客户端及原生库。结合模块构建配置、平台 API 与调用方确认用途;`.java/.kt` 不等于 Java 服务端,`.ts/.ets` 不等于 Web 前端,`.m/.mm/.cpp` 也不能仅凭后缀确定平台。
4. **shared/unknown**:跨技术栈共用库、构建脚本或证据不足的文件。读取入口/调用方补齐归属;共享代码分配给相关审查方共同核对,证据不足的部分明确记录未覆盖。

`react`、`vue`、`react-native`、`@mrn/*`、`taro`、`rax`、`@mbc-components` 等 manifest 依赖仅佐证**所属 package**的前端属性。仓库根有 React 依赖不能覆盖其它 package 的后端证据,也不能短路为纯前端。

原生桥接实现按实现平台及模块用途归属。MRN/Max/DUO 名称或调用方不能使 Objective-C、Swift、Android、ArkTS 实现自动归入 frontend。Flutter 通过所属模块的 pubspec.yaml 中 Flutter SDK 声明及本轮 Dart 实现确认；纯 Flutter 复用下方 general 通用审查流程，注明缺少 Flutter 专项规则，不套用 Web/MRN 规则。含其它栈时逐模块核对承接能力，未覆盖部分按现有阻塞规则处理。

### 第三步:路由,覆盖完整性优先于占比

- 同时存在前端和后端实质变更 → **mixed**,无论二者行数占比多少。
- 已确认的实质业务代码只有前端,相关 shared 文件也可由前端审查覆盖 → **frontend**。
- 已确认的实质业务代码只有后端 → **backend**。现有 Java 主流程仅覆盖 Java 及其关联配置;Node 等非 Java 后端必须使用相应技术栈的审查能力,不得把 Java 检查通过当成该部分完成。
- 纯原生仓库 → **general**,主 Agent 按下方「原生通用审查」执行;没有专项能力或规则不阻断。本次仅支持纯原生仓库,暂不扩展原生与前后端耦合的审查流程。
- 原生部分已分配通用审查时视为有审查责任方。仍有未归属、无法获取必要代码或无人承接的实质变更时继续定位或报告阻塞,不得跳过这些文件后发布「通过」。

行数加权占比 `已确认前端代码改动行数 / 全部实质代码改动行数` 仅用于播报和任务分配,不作为忽略少数技术栈的阈值。改动行数为 diff 中 `+` 与 `-` 行之和。

| 验证场景 | 必须得到的路由/处理 |
|---|---|
| 1 行 TSX + 10000 行 Java,根 package 有 React | mixed;两侧分别专业审查 |
| 100 个 TSX + 1 个 Java 服务方法变更 | mixed;不能忽略 Java |
| 仅 Nest controller/service 的 `.ts`,根 package 同时有 React | backend(Node);不能委托纯 FE 或宣称 Java 已覆盖 |
| 仅 React package 的组件和客户端 `.ts` | frontend |
| 前后端共用 `.ts` 类型发生变更 | 读取消费方;两侧消费时 mixed 并核对同一契约 |
| Android Java/Kotlin 或 iOS Swift/Objective-C,无专项规则 | general;主 Agent 执行通用审查,不因规则缺失停止 |
| MRN 桥接目录下仅有 Objective-C 实现变更 | 按 iOS 模块证据归属，纯原生走 general；不因目录名委托 FE |
| Flutter SDK 声明与 Dart 实现变更 | 纯 Flutter 走 general，登记 flutter；Dart 后缀本身不足以确认 Flutter |
| 原生变更有适用仓库规则 | general;通用审查同时执行适用规则,保留真实规则来源 |
| 只有 lock/生成产物或无法判定用途的脚本 | 检查来源/用途,明确范围;不自动认定任一业务技术栈完成 |

## 公共准备与范围冻结(所有路由必做)

1. Step 2F 从首次拉取起即将 **diff、范围 JSON、变更文件清单** 写入本轮独立 `$CR_RUN_DIR`,复用其 runId 和配对路径,不经共享暂存文件转存。主 Agent 核对范围文件绑定的 org/repo/prId,冻结 **CR_MODE、BASE_COMMIT、TARGET_COMMIT、COMMIT_COUNT**;后续只读该快照,不得被其它 PR 的文件覆盖。全量 base/count 为空,增量必须完整;target 必须是实际审查目标 hash。
2. 主 Agent 执行 Step 3D 的 spec 发现/完备性检查(发布字段的结构化来源,保留在主流程)。
3. 有前端委托时，主 Agent 在委托前执行[前端规则准备](#前端规则准备)。纯前端的上下文感知和审查由 fe-ai-review 承接，主流程保留范围冻结、SDD、前端规则准备和合流发布。混合 PR 按下文分配范围执行 Step 4-C/4-D。

### 前端规则准备

主 Agent 在每个有 FE 委托的 PR 上执行以下命令（纯前端和混合均适用）。范围文件中的 `targetCommit` 是本轮实际审查的源提交；`TARGET_BRANCH` 是合入分支，仅在主流程查存量 spec、反查或准备 Step 4-C 规则时使用。

```bash
FE_RULE_RC=0
FE_RULE_RECEIPT=$(python3 "$SKILL_DIR/scripts/collect_custom_rules.py" \
  --run-dir "$CR_RUN_DIR" --repo "$ORG/$REPO" --pr-id "$PR_ID" \
  --fe-snapshot "$CR_MODE_INFO_FILE") || FE_RULE_RC=$?
```

脚本核对本轮仓库、PR 和范围文件，从同一源提交列举、读取规则，默认写 `$CR_RUN_DIR/fe_rule_harvest.json` 和 `$CR_RUN_DIR/fe_custom_rules.md`。主 Agent 只读取本次命令返回的 FE 回执（退出码 0 或 3），核对 `sourceCommit` 与 `TARGET_COMMIT` 一致后交接原文；`ruleFilesLoaded` 非空时，传入回执的 `rulesPath` 供 FE 直接使用。FE 信任上游交接，无需重复核对这份缓存。

`exit 0` 且无已读文件表示本次扫描的规则目录没有可用规则；`exit 3` 时传入同一源提交已读规则，并标注回执中未读取的目录或文件；输入无效或拿不到本轮有效回执时，标注仓库规则获取未完成。把缺口写入汇总的人工复审要点，禁止用合入分支、`master`、其他提交或其他轮次的缓存填补缺口。

## 委托与混合审查

### frontend

**委托方式(三代演进后的定型范式)**:优先启动独立子 Agent(sessions_spawn 或 task),仅载入并执行 fe-ai-review;若当前环境不支持子 Agent,则在主 Agent 上下文内串行:先按需加载 fe-ai-review 的规则与步骤说明,再按其流程完成前端专项审查。**严格禁止「摘要式评审」简化其完整流程,禁止只喂处理过的 diff 让它出 JSON(旧范式,会导致技术栈规则同步/符号反查/复查全部丢失)。节省的是本 Skill 在对话中的逐条复述,不是 fe-ai-review 的工作量。**

**传给 fe-ai-review 的是原始信息,不是加工产物**:
- PR URL、org/repo/prId、前端文件清单、提交人 mis、本轮 runId；已知的业务仓库路径（如有，供 fe 核对并复用）
- 本轮冻结范围标识:crMode / BASE_COMMIT / TARGET_COMMIT / COMMIT_COUNT
- 委托方式以自然语言描述范围(参考 ai-pr-code-review 的 task 模板),fe-ai-review 按自己的 PR-only SOP 拉取 diff、识别技术栈、同步规则、执行反查与复查

**范围一致性核对(新增, PR 中途更新会导致审查范围≠发布范围)**:fe-ai-review 用自己 SOP 拉到 diff 后,必须与传入的冻结范围标识核对;不一致时以冻结范围为准并在返回中报告差异,禁止用 fe 重拉的结果替换冻结范围。增量模式 fe 无法执行时显式标注降级,不得静默切全量。

**返回后回接主流程**:fe 跑完后不会终结在它自己的报告里,主 Agent 接回执行:结果转换(见下节) → Step 4-Merge 统一合流 → issue_io 门禁 → Step 6 发布(学城/PR评论/大象/DB)。fe 不管发布,主 Agent 不重复审查。

纯前端 PR 省略主流程的 Step 3A/3B/3C/3E/3F 和 Step 4-A/4-B/4-C/4-D。前端存量代码读取、调用影响分析和规则检查由 fe-ai-review 负责；主 Agent 保留前端规则准备和统一合流。

### mixed

按文件/模块分配专业审查责任:前端部分委托 fe-ai-review,Java 后端部分执行主流程 Step 3~4,共享文件交由相关双方核对。Node 等后端需有对应专业审查方,缺少时终止完整发布并说明未覆盖范围。

主 Agent 将完整 diff 和跨端接口上下文交给审查方。Step 4-D 对完整变更检查业务逻辑；Step 4-C 的合入分支仓库规则仅用于后端侧分配的文件，共享文件仅检查适用于后端侧的约束。FE 使用源提交规则检查前端侧。**全部审查方返回后**，由主 Agent 执行 Step 4-Merge 合并为一份 PR 结果，只发布一次。

### 原生通用审查（纯原生仓库,general）

- 原生代码由主 Agent 执行通用审查,不委托 fe-ai-review。基于冻结的 diff 和目标 commit 补读上下文、调用方与需求,检查逻辑、契约、边界、异常流、并发、生命周期及资源释放。执行 Step 3 的适用上下文准备、Step 4-A 通用审查和适用的 4-C/4-D。
- 当前未接入原生专项规则,**仍执行 Step 2I 规则包预取**,但继续跳过 Step 3E/4-B,不将 Java 服务端、Web、MRN 规则套用原生代码。平台 L2 规则交给 4-C 判断适用性;仓库已有且明确适用的自定义规则继续由 4-C 检查,没有可用规则时才跳过。
- 通用代码发现写入 `step4a.json`,使用 `source=step4a`。未命中实际规则时 `ruleId=""`,保留代码证据;命中规则时使用真实编号及对应来源。P0/P1 仍需完整证据并进入 Step 4-Review,不能因无规则编号而丢弃或自动降级。
- 合流时检查实际适用和已启动的审查结果;general 必须有通过校验的 `step4a.json`（无发现也写 `[]`）,并收口本轮 L2 状态；`not_started`、`fetch_failed`、`domain_unresolved` 记录规则获取缺口,不能改写成无订阅或无规则。不等待已记录不适用的原生专项规则审查。
- 在 summary 总体评价中注明原生部分已执行通用审查、实际使用的规则;缺少专项规则时明确说明,实际未验证事项写入人工复审要点。完成通用审查后继续合流、复查、报告、评论和结果回写;不将规则缺失本身作为缺陷或失败结论。
- 原生平台明确时显式上报 `android` / `ios` / `harmony`;已确认原生库但平台不明时传 `native`。

### 必传交接上下文

- PR URL、prId、org/repo、标题、提交人和本轮 runId。
- 冻结的完整 diff、变更文件清单、分配文件清单、CR_MODE、BASE_COMMIT、TARGET_COMMIT、COMMIT_COUNT。
- 按[前端规则准备](#前端规则准备)交接本轮源提交的规则回执及已读规则缓存。
- ONES/PR 需求、spec、冻结业务知识，以及需要核对的跨端契约。混合 PR 在 Step 2I 确认可用后，将本轮回执 `rules_path` 指向的 **平台 L2 团队规范** 原样透传；纯前端由 FE 自行获取平台规则。

**fe-ai-review 按自己 SOP 拉取的 diff 仅作审查输入,必须与委托时传入的冻结范围标识核对;不一致时以冻结范围为准并报告,禁止以 fe-ai-review 的 PR-only 默认拉取结果替换本轮冻结范围。** 读取存量代码必须定位 TARGET_COMMIT;增量审查必须保持 BASE_COMMIT → TARGET_COMMIT。委托方需返回实际使用的范围标识,主 Agent 与快照核对一致后才接收结果。若工具无法按该范围执行,终止并说明原因;若确需全量重审,必须重新开始范围判定并将所有产出统一标为全量,不能用全量发现配增量标签。

## 结果回收与合流

先回收前端专项识别的技术栈集合、每个栈对应的变更模块、证据文件及未识别部分。与 Step 2H 初判比对；若涉及分派变化，先补齐审查再合流。summary 的变更综述保留这些证据及上报单值的选择理由。已确认技术栈仅涉及 DUO、Max、MRN、React 时，按专项技术栈优先级 `DUO > Max > MRN > React` 取最高项登记（DUO+Max→`duo`、Max+MRN→`max`、MRN+React→`mrn`）。完整集合和各模块审查覆盖仍需保留；相关测试和构建工具不能遗漏。小程序、Java、Node 服务端、原生、Flutter 等不参与此排序，涉及这些栈时按本轮实质变更的主导模块取值，无法确定则传 `unknown`。证据不全时先补齐，不能靠优先级跳过未归属文件。

1. **转换 findings**:使用[统一 Issue JSON 格式](output/issue-json-schema.md),FE 专业结果先写 `/tmp/cr_issues_{prId}_fe.json`,`source` 填 `fe-ai-review`。字段必须完整,无发现时也要有经确认的 `[]`。公共 SDD/自定义规则/业务逻辑检查即使物理合入此文件,仍分别保留 `source=step4a/step4c/step4d` 和真实 CR:/CU:/BL: 规则来源;文件名不决定来源。
   - 仅允许最终 `severity` 为 `P0/P1/P2/P3/confirm`。报告的明确 P0/P1/P2/P3 直接映射;`P2-P3` 等范围标签必须回到证据逐条定级,不得取首个、猜级别或丢弃。仍无法定级的项转 `confirm`,保留原标签和缺失证据说明。
   - `Open Question`/待确认项统一转 `confirm`,补齐 `confirm_reason`、`possible_risk`、`confirm_suggestion` 和所有通用必填字段。无法给出可核对的文件/行号或实质内容时返回补齐,不能伪造位置或静默跳过。
   - **规则编号与来源**：原样保留全部 `rule_sources`，纯上下文传 `[]`。主 Agent 从每项 `upstream_rule_id` 生成可读 `ruleId`：平台去掉 `fe-l1:` / `fe-l2:` 后加 `FE:`；L3 使用 `FE:L3_<id>`，无 ID 使用 `FE:L3_custom`；fallback 使用 `FE:<标题编号>`。FE 编号以 `rule_sources` 为准；多规则去重后以 ` + ` 连接，原 `ruleId` 仅保留混合审查中的非 FE 前缀。`mergedRuleIds` 如提供，按最终编号列表重建。脚本幂等校验与归一化，不修改来源 hash，也不猜测旧前端编号。
2. **完整合并**:主 Agent 按当前路由合并适用审查结果及 SDD findings,遵守 Step 4-Merge。相同位置不代表同一问题,空 ruleId 不作去重依据。只有证据确认根因和行为相同的重复发现才合并,保留最高严重级别及各方证据。最终写 `/tmp/cr_issues_{prId}_step4.json`。
3. **summary**:写 `/tmp/cr_summary_{prId}.md`,包含 `## 变更综述`、`## 总体评价`、`## 人工复审要点`,记录实际覆盖范围和未覆盖项。
4. **SDD**:必须回收 Step 3D 的结构化 `[SDD_CHECK_RESULT]`,包含布尔 `has_spec`、`completeness`、`alignment_rate`、`alignment_issues`。`has_spec=false` 时一致率为空;有 spec 但未完成一致性检查时补齐检查,不能猜百分比或伪装无 spec。混合 PR 由主 Agent 汇总全部 spec 检查项形成唯一结果,不能直接平均两个百分比。SDD findings 进入 issues JSON,同时写 `/tmp/cr_sdd_{prId}.md`;发布时 `--is-sdd` 和 `--consistency-rate` 从结构化结果直接传递,不得从 Markdown 反推。
5. **写入门禁**:所有 issues 文件用 `json.dump()` 或 `JSON.stringify()` 序列化写入,保留文案中的正常引号/反引号。写入后运行 `python3 "${SKILL_DIR}/scripts/issue_io.py" /tmp/cr_issues_{prId}_step4.json`;该门禁同时校验 JSON 语法、数组结构和字段。失败必须修复后重验,禁止用 `[]` 覆盖损坏输入。
6. FE 自带复查覆盖纯前端 PR 的全部 findings。混合 PR 中 Step 4-C/4-D 或后端结果出现 P0/P1 时仍执行主流程 Step 4-Review;FE 自带复查未完成也不能视为已复查。Step 6 等全部适用审查、复查与校验通过后,由 Step 7 统一发布。

## Cross-Repo 与异常

- 当前 FE 委托**不提供跨仓前后端契约检查**。多仓任务仍对支持的后端仓库执行 Step 5,涉及 FE 的跨仓边界在 summary/人工复审要点中明确标为「未覆盖,需人工核对」,不能写已检查通过或不适用;单仓 mixed 的共享契约核对仍需完成。
- fe-ai-review 未安装、读取失败、执行异常或结果不完整 → 终止发布并说明原因,不降级为 Java 规则审查前端。
- 范围不一致、审查方未全部返回、JSON 校验失败、实质文件无人负责 → 终止发布,保留现场以便修复或重试,不得输出完整审查已通过。
