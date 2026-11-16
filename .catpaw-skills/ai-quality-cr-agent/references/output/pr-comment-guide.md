# PR 评论操作指南（Step 7）

> **⚠️ 变量作用域红线（先读这个再操作）**：1024 平台每次 bash 调用是**独立 shell**，上一次调用里赋值的 `SKILL_DIR` / `CODE_CLI` 等变量**不会跨调用存活**——`$SKILL_DIR` 展开为空就变成 `/scripts/publish_results.py`（No such file or directory），`$CODE_CLI` 变成字面量（usage error）。变量赋值和使用必须在**同一条命令**内（`&&` 连接），或直接用平台注入的 `${ai_skill_directory}` 拼绝对路径。

所有评论由 `scripts/publish_results.py` 读取已校验的 Issue JSON 后,通过 `CommentClient` 发送。使用 SKILL.md Step 7 的安全参数数组调用方式,不要把 PR 标题、代码或评论正文拼进 shell 命令。

发布器在任何写入前执行公共 JSON/字段校验;损坏输入必须修复并重新通过门禁,不得当作零问题发布。

## 7A. P0/P1 行内评论

每个 P0/P1 问题单独一条行内评论，锚定到具体代码行。

仅限 FE 来源（`source=fe-ai-review`）的普通 `confirm` 参与行内限额竞争；后端四路（4-A/4-B/4-C/4-D）及复审存疑等来源的 confirm 项不发行内评论，仍完整保留在学城文档与全局摘要中。FE confirm 在合流时按业务影响与核实价值排序，同一根因合并，只保留有明确异常条件及核实问题的条目。发布器以本轮 mode_info 校正后的实际模式为准：full 最多选择 1 条风险最高的合格项，incremental 不发送普通 confirm 行内评论；因降级转为 full 时按全量规则执行。合格项须有有效文件、正整数行号、ADDED/REMOVED 锚点及完整确认字段。优先按 preReviewSeverity 的 P0 > P1 > P2 > P3 排序；同级或缺失时沿用主审按业务影响与核实价值排好的顺序，无有效锚点或字段不完整时顺延。FE 条目共用限额，不占 P0/P1 名额，不凑数。使用“🔎 待人工确认”及报告原 Q 编号，不附 P0/P1 标签或“无回复默认正确”。待确认项按完整路径、行号、行类型和正文指纹去重（忽略 Q 序号变化，兼容旧 ❓ 标题），复用发送流程；无锚点、超出限额或发送失败的条目仍保留在报告和上报中。全局摘要列出全部普通待确认项及核实问题，不预先声明发送成功。外部专项沿用原灰度发布策略。

**comment-add 全部 6 个参数逐项说明**：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 三选一（url / project+repo+pr-id） | PR 完整链接,含 project 与 repo 信息时最稳；含特殊字符时**必须用单引号或双引号整串包裹** |
| `--project` / `--repo` / `--pr-id` | 三选一 | 与 `--url` 二选一的定位方式;`--pr-id` 是整数 |
| `--text` / `-t` | ✅ 必填 | 评论正文。**必须整段引号包裹**；含引号/反引号/`$` 时用双引号包裹并把正文里的 `"` 转义为 `\"`,或改走参数数组/文件方式,禁止裸拼 |
| `--file` / `-f` | 行内评论必填 | diff 中的**完整文件路径**,不能只用 basename |
| `--line` / `-l` | 行内评论必填 | 正整数。`ADDED` 用新文件 dstN 行号,`REMOVED` 用旧文件 srcN 行号 |
| `--line-type` | 默认 ADDED | 仅允许 `ADDED` / `REMOVED`;禁止 `CONTEXT`、`MODIFIED` 或静默改锚点（另有 `--file-type` 默认 TO,一般不传） |

**完整可复制示例**（单条命令内变量赋值+使用,引号规则已示范）：

```bash
SKILL_DIR="${ai_skill_directory}/ai-quality-cr-agent" && \
python3 "$SKILL_DIR/scripts/code_cli.py" comment-add \
  --url "https://dev.sankuai.com/code/repo-detail/fun/scp-dzbiz-process-server/pr/1345/overview" \
  --file "src/main/java/com/meituan/scp/dzbiz/process/handler/SkuHandler.java" \
  --line 128 \
  --line-type ADDED \
  --text "[P1] 缺失空指针防护: entry.getValue() 可能为 null,建议先判空再解引用"
```

无法定位有效变更行时补证据或在人工复审要点中说明,不得捏造行号。若 lineType 非法的数据绕过门禁进入了发布器,P0/P1 不会静默丢弃,会降级拼入全局评论末尾的「无法行内锚定的 P0/P1 问题」清单(标注原因与文件行号)。

去重为三层宽容策略(与 `publish_results.py` 实现一致):①同 file+line+ruleId 精确匹配 ②同 file+ruleId 忽略行号(防 PR 新 push 后行号漂移导致重复评论) ③无规则编号时正文去首行序号后指纹匹配兜底。路径小写归一,两侧路径粒度不一致时回退 basename 兼容旧数据;同位置不同问题、不同路径均保留。已知折中(有意为之):同规则同位置严重级别升级会被旧锚点挡住、同规则正文变化不重发。具体请求重试由 `CommentClient` 负责,发布结果中保留失败信息。

**usage error 四种常见原因排查表**：

| 现象 | 根因 | 修复 |
|------|------|------|
| `No such file or directory: /scripts/xxx.py` | 变量赋值没跨调用存活,`$SKILL_DIR` 为空 | 同条命令内 `&&` 串联赋值,或直接写 `${ai_skill_directory}` 绝对路径 |
| `usage: ... error: unrecognized arguments` / 参数原样回显 | `$CODE_CLI` 为空串/字面量,或参数值含空格没引号包裹被拆成多个参数 | 同上修变量;所有含空格/中文/特殊字符的值整段加引号 |
| `error: argument --line: invalid int value` | 行号被空变量展开成空串,或传了 `dstN`/`srcN` 字面量 | 传解析后的纯数字行号;空变量先修作用域 |
| 命令回显正常但返回 usage/帮助文本 | 参数拼进了 `--text` 之外的非法位置（引号缺失导致正文参数错位） | 检查 `--text` 值的引号包裹,必要时改参数数组调用 |

## 7B. P2/P3/Cross-Repo 全局摘要

发布器生成全量发现与统计摘要。仅有 P2/P3 或零问题时也执行全局评论;同内容评论已存在时跳过重复发送。

多仓库时 Cross-Repo 问题同时写入所有涉及的 PR，注明「跨仓库问题，涉及 [{另一仓库}]」。

## 7C. 验证

发布器调用客户端验证,并返回 `inline_count`、`global_ok`、`error`。检查返回结果和 PR 中的实际锚点;部分成功时先核对已发布内容,再决定重试,避免重复评论。不得把代码审查结论“通过”当作发布成功。

## 评论内容格式

见 [inline-comment-template.md](inline-comment-template.md) 与 [global-comment-template.md](global-comment-template.md)。
