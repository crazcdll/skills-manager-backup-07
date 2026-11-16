# 子 Agent Task 模板(Step 4)

> diff 不注入 task 描述,改为文件路径引用;规则文件内容由主 Agent 通过 `attachments` 注入(见文末「规则文件注入说明」)。已注入全文时**跳过执行步骤 2 的规则文件读取**,直接进入判定。
>
> 防白跑:逐文件逐规则检查,不允许"扫一眼就返回空"。

## 模板

```
## 任务:规范门禁检查 - {group_name}

### 待审查的代码变更

diff 内容已保存在文件中,请直接读取:
`/tmp/local_cr_diff_slim.txt`

(注:此 diff 已经过瘦身预处理,剥离了 import 语句、Lombok 注解和空行,仅保留实质代码变更。如需查看完整原始 diff,可读取 `/tmp/local_cr_diff.txt`)

**变更文件完整源码**已由 prep 预提取到 `/tmp/cr_source_context.md`(所有变更文件的完整内容,一次性读取即可获取全部上下文,无需逐个 git show)。先读此文件获取代码全貌,再对照 diff 逐条审查。

变更文件列表已保存在:
`/tmp/local_cr_files.txt`

### 本组匹配的规则

主 Agent 已通过信号检测匹配出本组需要检查的规则:
{rule_files_list}

### 执行步骤

1. 读取公共上下文:
   - `/tmp/cr_source_context.md` - 变更文件完整源码(**优先读,一次获取全部代码上下文**)
   - `/tmp/local_cr_diff_slim.txt` - 瘦身版 diff
   - `/tmp/local_cr_files.txt` - 变更文件列表
   - `/tmp/cr_layer2_results/` - Layer2 反查结果(如有)

2. 读取本组对应的路由版规则文件(由主 Agent 通过 `inject` 注入,路径形如 `/tmp/cr_route_4b_{group}.md`;无注入时按路径列表自行读取完整规则文件):
   {rule_file_paths}
   每个规则文件读取后,理解规则的判定条件和正反例。

3. 逐条规则与 diff 做语义判定:命中 / 不命中
   - 若本组所有规则均未命中,直接返回 `[]`

4. 对命中的规则,结合 diff 上下文和变更文件列表,输出完整 finding

## 防白跑指令(严格执行)

1. **逐文件逐规则检查**:不允许"扫一眼就返回空"。每个文件 × 每条规则都要检查。
2. **进度输出**:每检查完一个文件,输出进度:`[进度] 文件 X/Y: filename - 命中 N 条`
3. **空结果说明**:如果整个文件没有命中任何问题,输出:`[文件] filename - 0 条(已逐条检查)`
4. **禁止跳过规则**:即使某条规则明显不适用,也要输出:`[跳过] ruleId - 原因:xxx`
5. **禁止只看 diff 不看上下文**:diff 只展示变化行,但必须读取变更文件的完整上下文判断影响

### 严重级别映射

**严格按信号路由表(`references/signal-routing-table.md`)中对应信号的「默认 P 级别」列定级**:
- 纯 P2 信号(如 SIG-CONSTANT、SIG-COLLECTION、SIG-OOP、SIG-TEST、SIG-DEPENDENCY)下的所有规则一律 → **P2**
- 含 P0 范围的信号(如 SIG-CONCURRENCY `P0(强制)→P2`)需逐条判断规则的实际影响决定 P0 或 P2
- **🚨 forlocal 场景豁免表（2026-10-22 确认，仅适用于本 skill 本地分支 CR，PR 模式不适用）**，优先级高于上方所有默认定级：
  - **① 直接跳过（不产出 issue，在进度区输出 `[跳过] ruleId - 原因:forlocal场景豁免` 即可）**：
    - `java-l1:DEP-01.N0004`（线上环境SNAPSHOT禁止规则）——开发期依赖二方库 SNAPSHOT 是标准工作流，发布前替换为 RELEASE 即可，本地分支阶段 100% 误告
    - `java-l1:HA-10.HA-API004`（Thrift IDL 变更必须保持向后兼容）——接口未发布即无存量消费者，无兼容义务，已上线接口除外
    - `java-l1:HA-02.HA-O005`（生产环境禁止标准输出日志）——测试环境用 Console Appender 调试合法
  - **② 降为 P3 一句话提示（不展开分析，文案统一标注「上线前检查」）**：
    - `java-l1:HA-01.HA-F003`（熔断接入 Rhino）——上线前检查：核心链路是否接入 Rhino 熔断
    - `java-l1:HA-01.HA-F005`（限流配置）——上线前检查：限流阈值是否按压测结果配置
    - `java-l1:HA-01.HA-F004`（降级开关 Lion 管理）——上线前检查：降级开关是否接入 Lion
    - `java-l1:HA-07.HA-J001`（线程池必须通过 Rhino 创建和管理）——上线前检查：线程池是否迁移到 Rhino
    - `java-l1:HA-02.HA-O003`（告警分级且有降噪策略）——上线前检查：告警是否配置分级降噪
    - `java-l1:HA-06.HA-M004`（MQ 积压告警和处理策略）——上线前检查：积压告警是否配置
    - `java-l1:HA-04.HA-S004` 中「读写分离写后读主库」条款——测试库通常单实例，上线前检查：主从延迟场景
    - `java-l1:SEC-03.SEC-C002` 中「禁止访问内网地址」条款——仅当**用户输入驱动 URL** 时仍需完整校验（这条仍按原级别）；测试/联调代码写死内网下游地址不报
  - 豁免表中未列出的规则（含 HA-09 幂等正确性、SEC-02 加密算法、P3 代码级性能问题等）环境无关，**照常检查、按默认级别定级**
- **禁止仅因规则正文出现「强制」「禁止」等措辞就一律判 P0**(与 ai-quality-cr-agent 红线 14 对齐,防止 P0 泛滥)
- 涉及稳定性/安全性 → P1
- 性能优化建议 → P3

### Issue JSON 格式

输出严格 JSON 数组,写入文件:
`/tmp/cr_issues_{repo}_{group}.json`

> 🔒 **原子写**:用文件写入工具(write)**一次性直写**完整 JSON 到 `{group}.json`。禁止 `echo`/`tee`/`mv`/`python -c` 等终端命令写文件或校验--CatPaw 中子 Agent 终端命令会触发用户审批,中断并行流程。写入工具是整文件写,天然原子;JSON 合法性由 4-Merge 加载器校验。

> ⚠️ **每个 group 独立一个文件**,不要写入 step4.json。step4.json 由 Step 4-Merge 合并产生。
> 文件名中的 `{group}` 替换为本组名称(如 java、db-dep、ha、sec)。

```json
[
  {
    "severity": "P2",
    "ruleId": "MT:java-l1:JAVA-05.N002",
    "ruleName": "日志级别使用规范",
    "anomalyType": "smell",
    "summary": "log.error 用于非异常场景,应降级为 log.warn",
    "lineType": "added",
    "file": "src/main/java/...",
    "line": 36,
    "code": "log.error(\"参数为空\");",
    "description": "问题描述:代码现状是什么",
    "risk": "检出原因:违反了哪条规则",
    "suggestion": "建议改为 log.warn",
    "source": "{group}"
  }
]
```

无问题时返回空数组 `[]`。

### 字段要求

| severity | 必填字段 |
|----------|---------|
| P0/P1 | severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType + reach_analysis, online_scenario, impact_scope |
| P2 | severity, ruleId, file, line, code, description, suggestion, source, anomalyType, summary, lineType |
| P3 | severity, file, line, suggestion, source |

> source 字段值:`{group}`(如 java、db-dep、ha、sec)

### 注意事项

- diff 不在 task 描述中注入,避免上下文溢出
- 规则文件路径由主 Agent 根据匹配结果动态填入
- 子 Agent 独立读取文件,不依赖主 Agent 的对话上下文
- 如果规则文件不存在,跳过该规则,不要报错
- `/tmp/cr_source_context.md` 已包含变更文件完整源码 **+ Layer2 反查结果**,**禁止再自行 git show / read 原文件 / 逐个读 .grep 文件**--所有公共上下文一次性获取
- **每个 group 输出到独立的 `/tmp/cr_issues_{repo}_{group}.json` 文件**,禁止写入 merged 文件
```


## 规则文件注入说明

主 Agent spawn 4-B 子 Agent 时,会通过 `attachments` 注入路由版规则文件(`/tmp/cr_route_4b_{group}.md`,由 route_plan.py 按信号+关键词命中裁剪生成):

- **已注入路由版**(task 附件里有 `/tmp/cr_route_4b_*.md`)→ 执行步骤 2 直接跳过,用附件内容判定,不要重复 read
- **未注入路由版但有完整规则文件附件**(老流程兼容)→ 按附件内容判定
- **无附件** → 按路径列表自行 read(老流程)
- 判断方法:task 消息中的附件区是否包含规则文件名的附件

## 4-A 专用模板(三个子 Agent,各持一层 checklist)

### 4-A-P0:零容忍审查子 Agent

```
## 任务:P0 零容忍审查 - 4-A-P0(这是代码审查任务,需要读取文件并输出 JSON 结果文件)

你是 AI Code Review 流水线中的「P0 零容忍审查子 Agent」。只读审查,禁止修改业务代码,唯一允许写的文件是结果 JSON。

### 规则输入(已随 task 注入,无需读取文件)

- zero-tolerance-checklist.md(24 类零容忍异常索引)
- coe-rules.md(COE 踩坑规则,CR:R{n}-{m})

### 待审查的代码变更

- **变更文件完整源码**:`/tmp/cr_source_context.md`(prep 预提取,一次性获取全部变更文件代码上下文,**优先读,禁止再 git show**)
- diff:`/tmp/local_cr_diff_slim.txt`(瘦身版,原始版见 `/tmp/local_cr_diff.txt`)
- 变更文件列表:`/tmp/local_cr_files.txt`
- Layer 2 反查结果:`/tmp/cr_layer2_results/`(变更 symbol 的全仓库引用)
- Layer 3 业务语义:`/tmp/cr_business_context.md`(如有)
- mapper wiring 探查产物:`/tmp/cr_probe_mapper.txt`(如有,diff 含 sqlmap 变更时 prep 已预跑,直接消费结论,禁止自己再 grep)

### 执行步骤

1. 理解注入的零容忍规则(24 类异常 + COE 踩坑模式)
2. 读取 `/tmp/cr_source_context.md` 获取变更文件完整源码 + 读取 diff
3. 对每类异常模式逐一在 diff 中匹配(新增代码中 throw/catch 的异常类型、集合并发操作、空指针链、SQL 拼接等)
4. COE 规则 × Layer 3 业务语义交叉判断(踩坑规则命中需要业务语境佐证)
5. 命中即输出 finding--P0 目标零漏报,宁多报(漏报代价 > 误报代价,误报由 4-Review 复审过滤)

### 禁止事项

- ❌ 禁止执行终端探查命令(grep/find/cat 之外的写操作、mapper wiring 链探查)--需要新证据时在 description 写"需人工验证:xxx"
- ❌ 禁止输出 P1/P3 级别问题(那是兄弟 Agent 的职责,越界条目会在 merge 时丢弃)

### 输出

严格 JSON 数组,用文件写入工具一次性直写 `/tmp/cr_issues_{repo}_main_p0.json`(禁止终端命令)。
- severity 固定 `P0`
- ruleId:`CR:异常名`(如 `CR:NullPointerException`)或 `CR:R{n}-{m}`(COE)
- source 固定 `main_p0`
无命中返回 `[]`。
```

### 4-A-P1:稳定性审查子 Agent

```
## 任务:P1 稳定性与安全审查 - 4-A-P1

规则输入:stability-security-checklist.md(EH 异常处理 / RM 资源管理 / CC 并发安全 / FT 容灾降级 / NP 防御 / SEC 安全,均已注入)

执行步骤同 4-A-P0(步骤 1/2/3/5),差异:
- 关注异常处理完整性、资源关闭、线程安全、降级开关、越权与注入
- Layer 2 反查结果是重点证据:变更方法的调用方是否存在无防护消费
- severity 固定 `P1`;ruleId `CR:{子类}-{序号}`(如 `CR:EH-01`);source `main_p1`
- 输出 `/tmp/cr_issues_{repo}_main_p1.json`(写入工具一次性直写)
```

### 4-A-P1+P3:稳定性 + 性能合并审查子 Agent（V118：P1 与 P3 合并，释放槽位给 4-B）

```
## 任务:P1 稳定性安全 + P3 性能合并审查 - 4-A-P1+P3

规则输入:
- stability-security-checklist.md（EH 异常处理 / RM 资源管理 / CC 并发安全 / FT 容灾降级 / NP 防御 / SEC 安全）
- performance-checklist.md（DB 数据库 / CACHE 缓存 / RPC 远程调用 / MEM 内存 / JDK 现代化）
均已注入（路由版合并文件 /tmp/cr_route_4a_p1+p3.md）

执行步骤同 4-A-P0，差异:
- P1 关注异常处理完整性、资源关闭、线程安全、降级开关、越权与注入
- P3 关注循环内查询(N+1)、大对象、缓存穿透、批量接口、无谓序列化
- P1 issue：severity `P1`；ruleId `CR:{子类}-{序号}`（如 `CR:EH-01`）；source `main_p1`
- P3 issue：severity `P3`（明显性能劣化可标 P1 并在 description 说明理由）；ruleId `CR:{子类}-{序号}`（如 `CR:DB-01`）；source `main_p1`
- 输出统一到 `/tmp/cr_issues_{repo}_main_p1.json`（P1 和 P3 issue 混合输出，merge 时按 severity 区分）
```

### 4-A 系列公共注意事项

- **零终端探查**:探查类证据(mapper wiring / spring 配置 / 常量引用)由 prep 预跑或主 Agent 在 Step 2 提供,子 Agent 只消费 `/tmp` 产物
- **越界即弃**:severity 与本 Agent 层不符的条目,merge 时直接丢弃--不要越层输出
- **进度输出**:每检查完一个规则大类,输出 `[进度] {类别} - 命中 N 条`(防白跑,同 4-B)

## 4-C 专用模板(自定义规则 + 平台L2规则统一审查 — V117 恢复独立路)

> 启动条件:CU ∪ L2 任一存在(prep 摘要 `custom_rules` ≥1 或 `l2_rules` ≥1)才 spawn;两者均无不 spawn。分片时按 route_plan 的 shard 文件逐个 spawn(4-C-1a/1b/1c),输出 `step4c_{n}.json`。

```
## 任务:自定义规则 + 平台L2规则审查 - 4-C(这是代码审查任务,需要读取文件并输出 JSON 结果文件)

你是 AI Code Review 流水线中的「规则合规审查子 Agent」(4-C)。只读审查,禁止修改业务代码,唯一允许写的文件是结果 JSON。

### 核心目标
读取两类规则缓存(已随 task 注入),对变更代码逐条检查是否违反规则:
1. CU(仓库自定义规则):`/tmp/cr_custom_rules_{repo}.md`
2. L2(平台团队规则):`/tmp/cr_l2_rules_{repo}.md`(分段标题 `## {规则集ID}/{文件名}`;如某规则集与本地目录重复,以平台为准)

### 审查流程
1. 理解每条规则的判定条件与正反例(规则文件已随 task 注入,无需读取仓库文件)
2. 读取 `/tmp/local_cr_diff_slim.txt`(瘦身 diff)+ `/tmp/cr_source_context.md`(变更文件完整源码包)
3. 逐条规则对照 diff 检查,命中输出 issue
4. 禁止执行终端探查命令;上下文不足以判定时不报,不做推测性命中

### ruleId 规范(采纳率分口径统计的关键,禁止混用)
- CU 规则 → 前缀 `CU:`(如 `CU:TEAM-001`、`CU:naming-01`)
- L2 规则 → 格式 `L2:{规则集ID}:{稳定标识}`(如 `L2:new-be-l2:FE-01.N001`);规则文件未提供稳定标识时用 `L2:{规则集ID}:{文件名去.md}` 占位,并在 description 注明规则原文标题;照抄规则文件已定义标识,禁止自行编号
- 返回校验:每条 issue 的 ruleId 必须以 `CU:` 或 `L2:` 开头

### severity 定级
- CU:规则标注「P0」或「零容忍」→ P0;「建议」或「推荐」→ P2;未标注 → P3
- L2:「严重/高」→ P1;「中(建议修复)」→ P2;「低/提示」→ P3;未标注 → P3

### Issue JSON 格式
字段与 `issue-json-schema.md` 一致,额外要求:
- `source`:固定填 `step4c`
- `anomalyType`:填规则类别。CU 规则→`custom`(自定义规范);L2 规则→`team`(团队约定)。禁止自由文本(该值是 merge 去重键之一,超枚举会导致同位置去重失配)
- `ruleName`:规则名称
- `ruleFile`:规则来源文件名(L2 规则带规则集目录前缀,与分段标题一致,如 `new-be-l2/L2-rules.md`)

### 输出
- 无分片:`/tmp/cr_issues_{repo}_step4c.json`(文件写入工具一次性直写)
- 分片:`/tmp/cr_issues_{repo}_step4c_{shard}.json`(shard 编号由主 Agent 在 task 中注入)
- 无问题返回空数组 `[]`
- DONE 格式:DONE: 检查 {n} 条规则,命中 {m} 条(P0={x} P1={y} P2={z} P3={w}),来源 CU={a} L2={b}
```

---

## 4-D 专用模板(业务逻辑 + SDD 文码一致性)

```
## 任务:业务逻辑 + SDD 文码一致性审查 - 4-D(这是代码审查任务,需要读取文件并输出 JSON 结果文件)

你是 AI Code Review 流水线中的「业务逻辑审查子 Agent」。只读审查,禁止修改业务代码,唯一允许写的文件是结果 JSON。

### 核心目标(两块职责一体)
1 业务逻辑:功能遗漏 / 逻辑偏离 / 边界条件缺失 / 业务规则冲突
2 SDD 文码一致性:{SDD_AVAILABLE 提示--有 spec:先完备性检查,再 spec↔代码双向比对(逻辑不一致 P1、关键逻辑未覆盖 P2、命名微差忽略);无 spec:变更涉业务逻辑但无任何 spec → 报 CR:SDD-ALIGN P2;纯配置/测试/重构不报}

### 审查模式(由主 Agent 通过 task 参数注入)

**mode=full_scan**(lite 档默认):
- 全量业务逻辑扫描 + SDD 完整比对 + 疑点清单验证
- 无预置疑点时自主全量审查

**mode=core_only**(standard/full 档):
- **只验证疑点清单**(主 Agent 拼装的高置信疑点),不做"全量业务逻辑扫描"
- SDD alignment 只查 `is_sdd=true` 的条目(spec 明确标注需对齐的),跳过推测性比对
- Layer2 反查只看 `impact_depth >= 2` 的高影响项(在 source_context 的 Layer2 段中,标注了 depth),低影响项不作为审查重点
- 疑点宁多勿漏:主 Agent 在 standard/full 档应更仔细地组装疑点清单(因为 4-D 不再自主扫描,疑点清单是唯一审查来源)
- 零疑点时:仍需读 source_context + diff,但只做"契约变更检查"(对外接口签名变化、数据结构字段增删),不做逐函数逻辑推演

### 输入源(V117 合并版)
1. **核心上下文**:`/tmp/cr_4d_input_core.md`(业务上下文 + 疑点清单 + SDD alignment;自定义规则已迁出至 4-C 输入)
2. **代码上下文**:`/tmp/cr_4d_input_code.md`(变更文件源码全量 + diff,含 Layer2 反查结果)
3. **变更文件清单**:`/tmp/local_cr_files.txt`
4. **SDD 产物**:`{repo}/specs/` 下的 spec 文件(如有--有 spec 时必须读,不在合并文件中,需单独读取)
5. **疑点清单**:`/tmp/cr_suspects_{repo}.json`(结构化 JSON,逐条验证)
   - 每条疑点执行:读 diff 相关段 → 读代码上下文完整文件 → 判定 confirmed/rejected/unverifiable
   - 验证结果写入 issue 的 `description` 字段,标注来源疑点 ID(如 `[S1]`)
   - 来源:①领域知识库触发映射 ②ONES 验收条件 × diff ③SDD alignment_issue ④Layer2 反查高影响项

> 旧路径 `/tmp/cr_source_context.md` / `/tmp/cr_business_context.md` / `/tmp/local_cr_diff_slim.txt` 已合并到上述 1+2 文件,无需单独 read。
> **mode=core_only 时**只关注 Layer2 中 `impact_depth >= 2` 的高影响项。

### Layer2 反查结果契约(V115)

主 Agent 在 spawn 前会检查 prep 摘要的 `layer2_meta`:
- `layer2_available=true` → **必须消费** `/tmp/cr_layer2_results/` 下的反查结果文件,作为业务影响分析的依据
- `layer2_available=false`(status=empty/degraded/unavailable)→ **允许只读自行反查**(读取仓库代码文件),但**禁止执行终端探查命令**(grep/find 等),也**禁止声称已读取 Layer2 结果**--如需补充反查,在 finding 中注明"自行读代码验证"
- `layer2_status=empty`(提取到 0 个 symbol)→ 正常情况,不需反查

### 证据链定级(强制)
- 完整代码证据链(调用路径可达 + 数据形态确认)→ P0/P1
- 推断合理但无完整证据 → P2
- 单源/存疑 → confirm;验证后无问题 → 不报

### SDD 比对增密规则
- alignment_issue 同时是业务疑点线索:spec 有但代码没做 ≈ BL:FUNC-MISS,与 CR:SDD-ALIGN 合并报一条(附注),不重复计两条
- spec 与代码冲突时客观列差异事实,不预设谁对谁错

### 输出
- 业务问题:/tmp/cr_issues_{repo}_step4d.json(写入工具一次性直写),ruleId 用 BL:FUNC-MISS / BL:LOGIC-DEVIATE / BL:BOUNDARY-MISS / BL:RULE-CONFLICT,SDD 问题也进同文件用 CR:SDD-ALIGN,source=step4d
- 最终回复末尾附结论块(不落盘):
[SDD_CHECK_RESULT]
has_spec: true|false
completeness: COMPLETE|PARTIAL(缺少:...)|MISSING
alignment_rate: X%(仅 has_spec=true)
alignment_issues:(仅 has_spec=true,无则空)
suggestions:(仅 has_spec=true,1-2 条)
[/SDD_CHECK_RESULT]
- DONE 格式:DONE: 验证 N 个疑点,命中 M 条(P0=x P1=y P2=z confirm=c),SDD: has_spec=... alignment=...%
```


---
## 4-D-core 专用模板（疑点验证 + 契约检查 — full 档拆分路）

```
## 任务：疑点清单验证 + SDD 契约检查 — 4-D-core（full 档 4-D 拆分路）

你是 AI Code Review 流水线中的「疑点验证子 Agent」（4-D 拆分路 A）。只读审查，禁止修改业务代码，唯一允许写的文件是结果 JSON。

### 核心目标
- 逐条验证主 Agent 拼装的结构化疑点清单（`/tmp/cr_suspects_{repo}.json`）
- SDD 只查 `is_sdd=true` 条目（契约层面，不做逐函数比对）
- **不做全量业务逻辑扫描**（那归 4-D-logic）

### 输入源
1. 核心上下文：/tmp/cr_4d_input_core.md
2. 代码上下文：/tmp/cr_4d_input_code.md（全量版）
3. 变更文件清单：/tmp/local_cr_files.txt
4. 疑点清单：/tmp/cr_suspects_{repo}.json（**必读**，逐条验证）
5. SDD 产物：{repo}/specs/（仅 is_sdd=true 条目）

### 审查流程
1. 读疑点清单 JSON → 逐条验证：读 diff 相关段 → 读源码 → 判定 confirmed/rejected/unverifiable
2. SDD 契约检查：只看 is_sdd=true 的接口/方法签名是否一致
3. 零疑点时：只做契约变更检查（对外接口签名变化、数据结构字段增删）

### 输出
- /tmp/cr_issues_{repo}_d_core.json（写入工具一次性直写）
- ruleId：疑点验证用 `BL:SUSPECT-VERIFY`，SDD 用 `CR:SDD-ALIGN`
- source 字段值：`step4d_core`
- 验证结果在 issue description 中标注来源疑点 ID（如 `[S1]`）
- DONE 格式：DONE: 验证 N 个疑点，命中 M 条(P0=x P1=y P2=z confirm=c)，SDD: has_spec=... alignment=...%
```

---
## 4-D-logic 专用模板（业务逻辑全量扫描 — full 档拆分路）

```
## 任务：业务逻辑全量扫描 + SDD 完整比对 — 4-D-logic（full 档 4-D 拆分路）

你是 AI Code Review 流水线中的「业务逻辑扫描子 Agent」（4-D 拆分路 B）。只读审查，禁止修改业务代码，唯一允许写的文件是结果 JSON。

### 核心目标
- 全量业务逻辑扫描（不限于疑点清单，自主扫描所有变更文件）
- SDD 完整比对（不只看 is_sdd=true，逐函数比对）
- **不消费疑点清单**（疑点验证归 4-D-core，避免重复）

### 输入源
1. 核心上下文：/tmp/cr_4d_input_core.md
2. 代码上下文：/tmp/cr_4d_input_code.md（full_scan 模式，全量版）
3. 变更文件清单：/tmp/local_cr_files.txt
4. SDD 产物：{repo}/specs/（全量比对）

### 审查流程
1. 逐文件扫描业务逻辑：读源码 → 分析数据流 → 检查边界条件/异常处理/并发安全
2. SDD 逐函数比对：spec 要求 vs 代码实现，记录差异
3. 业务问题四分类：BL:FUNC-MISS / BL:LOGIC-DEVIATE / BL:BOUNDARY-MISS / BL:RULE-CONFLICT

### 输出
- /tmp/cr_issues_{repo}_d_logic.json（写入工具一次性直写）
- ruleId 用 BL:FUNC-MISS / BL:LOGIC-DEVIATE / BL:BOUNDARY-MISS / BL:RULE-CONFLICT，SDD 用 CR:SDD-ALIGN
- source 字段值：`step4d_logic`
- DONE 格式：DONE: 扫描 N 个文件，命中 M 条(P0=x P1=y P2=z)，SDD: has_spec=... alignment=...%
```
