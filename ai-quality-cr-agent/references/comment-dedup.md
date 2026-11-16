# 评论去重：旧计算抽取与离线观察

## 边界

`publish_results.py` 保留旧接口/原日志，委托 `comment_dedup.py` 执行原计算；无新线上调用、发送策略、历史 fetch 改动。原粗过滤规则仍可能跳过独立问题，**本次抽取不修正该遗留策略**。观察 API 不接入发布器，不改变同轮合流、严重度、commentId、FE 或步骤。

```bash
python3 scripts/comment_dedup.py --input /tmp/observation.json
# 或 --input - 从 stdin 读取；只输出 JSON，不发送/更新评论。
```

仅本地离线输入；模块不导入 publisher/client，不执行网络请求、环境探测或业务写入。CLI 不加载插件、不信任 JSON 的 `verified=true`、`sameRootCause` 或历史 skip。CLI 没有独立 verifier，全部语义结果保守为 UNKNOWN。无候选不等于独立；basename、规则号、同行、指纹只能检索，不能证明语义。

## 输入契约（严格绑定）

顶层对象：

- `context`：`runId/org/repo` 非空字符串，`prId` 正整数或正整数字符串；`fromHash/toHash` 为冻结 PR 两端点的 40 位小写 commit hash；`diffSha256` 为本轮冻结 diff **原始字节**的 64 位 SHA-256。范围 commit 和 PR 双端点不可混用。调用者负责从真实冻结产物取得，不允许猜填；本模块只验形状和绑定，不能证明来源真实性。
- `findings`：最终 finding 完整 JSON 对象数组。所有字段（严重度、位置、完整摘要、证据、建议、来源、commentId 等）全部进入摘要，不截断、不投影、不改写。每条独立保留，不合并。
- `history.comments`：冻结历史完整原文对象数组（正文、锚点、id、replies、状态等原字段均保留）。
- `history.receipt`：显式完整性回执，规范化供观察 API 使用：`complete` 必须严格是布尔 `true`；`budgetExhausted` 必须严格是布尔 `false`；`org/repo/prId` 与 context 类型和值一致；`commentsSha256` 为 `content_digest(history.comments)`。缺失、1、"true"、未完成、预算耗尽均 UNKNOWN。
- raw source 绑定：收集 `history` 顶层及 `history.receipt` 内的 `sourceReceipt/raw/source` 槽位完整快照（保留槽位名、所在层级及所有字段）。
  - 摘要配对门禁：对容器（`history`、`history.receipt`）顶层及 dict 型槽位快照统一执行，仅对含 `source/sourceSha256/comments/commentsSha256` 任一键的 dict 生效（不误伤无 raw 语义的普通 dict）。
  - 配对规则：`source` 数据键与 `sourceSha256` 声明必须**成对出现**，且声明值等于对应内容的 `content_digest`——缺声明、缺数据、摘要不符均抛出 `ValueError`，binding 失效、语义 UNKNOWN。
  - 形状兼容：平铺形状（`receipt.source` 原始页与 `receipt.sourceSha256` 同级，`history` 顶层同理）与嵌套形状（`sourceReceipt/raw` 内部自带 `source/sourceSha256`）共用该门禁。
  - `comments` 特例：仅在数据与声明同时存在时校验一致。规范化回执的 `commentsSha256` 语义指向 `history.comments`（由完整性回执校验负责），允许不内嵌 `comments` 槽；内嵌 `comments` 的原始回执则必须自洽。
  - `binding.historyRawSha256` 为按层级/槽位收集的快照摘要；无上述槽位时为 `null`。该摘要不代替规范化完整性回执，也不证明来源真实性。
- `comparisons`：可选数组；非数组会记录 `comparisons must be an array`，视为无有效 comparisons，语义保持 UNKNOWN（包括完整空历史）；原值仍参与 binding 摘要。每项严格为 `findingIndex/historyIndex/evidence`。整数索引（非 bool）定位完整快照，不按 commentId 改写原数据。同一 pair 多条断言（即使相同）失效。未核实的比较仍完整保留在输出 `inputSnapshot`。

外部取数入口：由用户/取数 Agent 在独立授权下执行 `code_cli.py pr-comments --url "PR_URL" --with-metadata` 获取带显式完整性元数据的回执。本观察 CLI **不会执行它**；该 flag 由本版本 `code_cli.py` 提供。适配器要求：
  - 保留原回执在 history（如 `sourceReceipt`）。
  - 仅当 `complete is True`、`incomplete is False`、两分支 Complete 严格 True 且 `truncated is False` 均明确满足，才可映射 `complete=true/budgetExhausted=false`；不能把字段缺失当 false。
  - 失败或预算相关 note 应保守留 UNKNOWN；不能为了满足 schema 把旧 list、长度小于90、重复ID或计数推断填成 complete=true；没有可靠适配时留缺字段并得到 UNKNOWN。
  - 回执字段清单（`comments/complete/incomplete/activitiesComplete/assignmentsComplete/truncated/note/pages/next_cursor`）以 `code_cli.py` 实现为准。

`complete=true` 的判定口径（分页契约）：两通道均须在**已读取范围内**收到 `isLastPage` 严格为布尔 `True`，且范围内无解析错误、无畸形记录、无空非末页、无非法游标、未触发 20 页安全阀。它至多标记**本次端点返回范围的遍历与结构完整**，绝不宣称整个 PR、所有时点的全量快照或"不存在更多评论"的证明，也不证明 assignments 5.0 专属分页/嵌套分组契约完整（该专属接口无正式全量契约，`start/limit` 被服务端忽略，单次返回全量分组）。末页返回合法 `nextPageStart`（严格 int 且递增）是 Code 官方通用分页（1280163608）与终页示例（1315646744）的正常并存形状，仅记录为 `next_cursor` 游标供续取，不据此反推还有未读页、不跟随请求。**非法** `nextPageStart`（非 int、bool、不递增、伪值）或存在 `nextPage` 对象（实质后页描述）时仍保守判 `next_page_present`→incomplete；非布尔 `isLastPage`（字符串/数字）判 `pagination_missing_or_invalid`→incomplete。assignments 分组总数与 `size/total` 不做数量推导（9 组 14 条评论的真实形状不能由 total>size 判缺页）。不放宽：非末页、缺 `isLastPage`、空非末页、游标异常、错误、预算耗尽。

`content_digest` 使用 UTF-8、JSON sort_keys=true、ensure_ascii=false、紧凑 separators、拒绝 NaN；列表顺序保留。binding 同时包含上下文、最终 findings、全 history（含原回执）、comparisons 及整个输入的完整内容摘要。`binding_valid(binding,payload)` 重算且全等校验；run/PR/端点/diff/任何 finding 或历史字段/证据变化及缺字段均失效。旧决定或 skip 不被读取。哈希是防陈旧，不是认证签名，不证明用户输入属实。

非有限数（包括 `1e400` 解析成的 inf）导致完整输出不能严格 JSON 序列化时，观察 API/CLI 降级为结构化错误对象：`schemaVersion=1`、`actualAction=observe_only`、`error=serialization_failed`，原始 `errors` 保留；此时不输出不可序列化的完整快照，CLI 退出码为 1。未配对代理字符导致 `content_digest` 抛出含 UTF-8 编码诊断的 `ValueError`，归入 `errors`，binding 无效且语义 UNKNOWN；CLI 以 JSON 转义保留代理字符，避免 stdout 编码崩溃。非对象 finding 同样使 binding 无效且保持 UNKNOWN；`findings=[]` 与完整空历史合法输出 `results=[]`。

## 结构化证据与独立 verifier

仅纯 Python API `observe(payload, verifier=...)` 支持**由离线测试/独立审查方显式注入的可信、无副作用 verifier**。JSON 中的 verifier 身份/结论不等于信任；没有注入时 UNKNOWN。此版本没有生产语义 verifier，不声称实现自动语义证明。

每个 comparison 的 `evidence` 必须恰有以下六维：
`responsibilityCode/rootCause/trigger/failure/impact/recommendation`。
每维恰有 `current/historical`；每侧恰有 `claim`（非空）和 `references`（非空数组）。每个 reference 恰含：

```json
{"file":"src/A.java","symbol":"A.save","commit":"0123456789012345678901234567890123456789","startLine":12,"endLine":15,"quote":"checkable exact responsibility code quote"}
```

六维分别核对责任代码/根因/触发条件/实际失效/业务影响/修复建议；schema 成功只表明资料齐备，**不是已证实等价**。verifier 须独立核对真实引用、历史/当前责任代码与因果链，逐项比较新增/改变的证据（含位置、规则、严重度、影响与建议变化）；不能通过 claim 字符串相等、同根因标签或用户自己填的 verified=true 授权。无法核对一项则不返回有效结论。

verifier 签名 `(pair, binding, finding, comment) -> result`，收到深拷贝。result 严格包含：
- `state`：SAME_UNCHANGED / SAME_CHANGED / INDEPENDENT；
- `verifier`：恰含非空 `id/version/method`，标明独立核查身份、版本、方法；
- `basis`：上述六维各为非空字符串数组（`list of str`），至少一项且每项去除空白后非空；逐项登记并说明新增/变化证据，不能略去。旧格式（每维单字符串）、空数组或含空白/非字符串项均无效，返回 UNKNOWN；
- `bindingSha256/pairSha256/findingSha256/commentSha256/evidenceSha256`：各完整对象 `content_digest`。
- 可选 `ledger`：恰含六维，每维恰含 `status/references`。
  - 结构要求：status 为 `covered/new/changed/unconfirmed`；references 恰含 `current/historical` 非空数组，每项必须是 64 位小写十六进制 SHA-256，值为对应 evidence reference **完整六字段对象**的 `content_digest(ref)`。
  - 映射规则：逐维逐侧要求 `Counter(ledger[dimension].references[side]) == Counter(content_digest(ref) for ref in pair.evidence[dimension][side].references)`，即严格一一映射、不得漏项或额外项；顺序可不同，但不接受重复占位、伪造摘要或用另一侧/另一维不同内容的引用补足。
  - 多重集合语义：证据自身有完全重复对象时明确采用多重集合，digest 必须按其精确出现次数登记；相同完整内容自然产生相同 digest，不额外加入侧/维盐值。
  - 失败行为：非法类型、摘要不可计算或多重集合不一致使整条核验失效并保持 UNKNOWN/NEW；原 finding、source 和证据仍原样保留。此契约取代旧的不少于数量/任意非空字符串映射，旧 verifier 须重算 digest 后才能通过。
  - 可复算方式沿用上文 `content_digest`：UTF-8、`sort_keys=true`、`ensure_ascii=false`、紧凑 separators、拒绝 NaN；只规范 JSON 对象键序/序列化，不裁剪字段，不改字符串空白、行号或 quote。此门禁只验证引用整对象的内容映射，**不验证引用真假，也不证明语义等价**；独立 verifier 仍须核对真实引用及因果链。REUSE 必须有匹配的 SAME_UNCHANGED pair 自身完整 ledger 且全 covered；其他 pair 的 ledger 不能补足。唯一同问题匹配时，任一 pair 的 new/unconfirmed 阻断同问题结论，任一 pair 的 changed 不得产生 SAME_UNCHANGED→REUSE。

异常、缺字段、摘要不匹配、多重匹配冲突均 UNKNOWN。所有历史评论必须逐对有效核查；无匹配且所有历史均核实独立才可判 INDEPENDENT，完整历史为空且显式注入可信 verifier、finding 非空时才判 INDEPENDENT；未注入时仍 UNKNOWN。只核查候选/部分历史不能推荐 REUSE。

## 两轴输出与保全

| semanticState | recommendedAction | 含义 |
|---|---|---|
| SAME_UNCHANGED | REUSE | 独立 verifier 证实同问题且无实质变化 |
| SAME_CHANGED | GLOBAL_SUPPLEMENT | 同问题有新增/变化，保留每项新增证据，建议全局补充 |
| INDEPENDENT | NEW | 完整历史核查无同问题 |
| UNKNOWN | NEW | 证据/绑定/完整性/预算/核查不足，不沿用 skip |

所有结果实际动作固定 `observe_only`，只推荐，不执行 NEW/REUSE/GLOBAL_SUPPLEMENT。`finding` 和整个 `inputSnapshot` 深拷贝原样保留；evidence 的每项 reference 按输入顺序保留，未验证证据也保留。`verifications` 独立标注核验依据，未核实的不装成语义结论。UNKNOWN 不是删 finding 或线上发送指令。

## 保留的风险

1. 旧 fetch 多次调用 pr-comments 无 start，按 <90 或重复 ID 停取，max_pages 截断；不能证明历史完整，本轮不变更默认行为。
2. 旧规则号/忽略行号/basename/指纹粗过滤可能漏独立问题；观察模式不纠正线上旧策略，不声称已消除误去重或竞态。
3. publisher 顶部既有跨 tenant glob 回退和认证常量未改；测试只 AST 提取白名单计算，禁止触发回退/真实 import 副作用。不要上传包含既有认证常量的完整源文件。
4. 外部回执、冻结 diff、注入 verifier 的可信来源是调用方边界；摘要/schema 不能代替认证或语义核查。离线 mock 测试不等于全链路 PASS。
5. 新模块需随 skill 同目录分发；仅复制 publisher 单文件的历史用法可能缺依赖，不新增扫描回退。未发布、未真实评论、未业务写入。
