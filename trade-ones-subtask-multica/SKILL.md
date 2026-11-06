---
name: trade-ones-subtask-multica
description: "每周酒店交易排期文档 → 自动生成《Wxx 需求任务创建》子文档：复制父文档「三、人员分布一览表」、按排期批量创建 ONES 子任务并继承标签、按父文档多维表格汇总本周新增/待排期/跟进中/已排期与人力 pd、再按本周新增需求在 Multica 批量建开发任务并回写结果。触发词：需求任务创建、W4x 需求任务创建、排期文档建 ONES 子任务再建 Multica、每周任务创建、排期转任务、人员分布一览表建任务、ones+multica 一条龙。"

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "161353"
  skillhub.high_sensitive: "false"
---

# 每周「需求任务创建」一条龙（ONES 子任务 + Multica 任务）

输入父排期文档（如 `https://km.sankuai.com/collabpage/2793615111`，标题形如「W43酒店交易排期」），
在其下新建子文档 **`Wxx 需求任务创建`**（Wxx 与父文档标题同周），按下面 7 步把子文档填满：

| 子文档结构（自上而下） | 来源 |
| --- | --- |
| 父文档「三、人员分布一览表」表格（原样复制） | 父文档 XML 表格片段 |
| `## Ones 子任务创建结果` + 明细表 | ONES 批量创建结果（流程同 `ones-create-subtask`） |
| 汇总段两行（本周新增/待排期/跟进中/已排期 + 承接率 + pd 公式） | 父文档多维表格统计 |
| 人力投入汇总段 + 每人汇总表 | 同上 ONES 结果 |
| `## Multica 新任务创建输入` + 输入表（涉及页面留空，等用户填） | 本周新增需求 |
| `## Multica 新任务创建结果` + 结果表 | Multica 批量创建结果（流程同 `trade-ones-multica`） |

参考成品：`https://km.sankuai.com/collabpage/2793439441`

## 核心原则（不可越过）

1. **写入只走 citadel CLI**：读 XML、建文档、整篇覆盖都用 `oa-skills citadel`，绝不用 browser / web_fetch 动学城（会产生脏数据）。唯一用浏览器的是 ONES API（SSO Cookie 只在浏览器生效）。
2. **文档只有一个可写真相 `state.json`**：每次改文档都是「改 state → `render_doc.py` 整篇重渲染 → `updateDocumentByXml`」，不要手工在文档里插节点。
3. **不动父文档**：只读父文档；所有输出写在新建的子文档里。
4. **ones 子任务：issueId 不得替换**：排期表里解析出的 `issueId` 就是挂载目标（`parentId = issueId`），查询需求详情后也不能换成父需求 ID。
5. **任何创建动作前必须先拿到用户「继续」**：不管有没有 `colspan/Npd` 不一致或 PD>5，创建 ONES 子任务前都要把明细清单（人员 / 需求名 / 天数 / 日期）贴给用户并等确认；用户说「取消」就终止全流程。Multica 建 Issue 同理（第 5 步的涉及页面暂停就是这道门）。
6. **涉及页面必须等用户手填**：`Multica 新任务创建输入` 表除了「涉及页面」全填完后**停下来提醒用户填写**，收到用户回复后才继续建 Issue，并把填写内容合并回 state。
7. **PRD 是 Multica 的硬门槛**：`需求文档PRD` 为空的需求不建 Issue，只在结果表里记 `未创建·无PRD`，不做任何兜底。
8. **失败不静默**：查询失败、创建失败、标签继承失败、`found=false` 都要逐条写进报告与结果表备注。

## 环境与路径约定

```bash
MIS=${MIS:-$SSO_USER_ID}                    # 例：zhangce07
SKILL=<本 skill 的实际安装目录>               # 本文件所在目录，用绝对路径，不要硬编码机器相关路径
S=/tmp/osm-state.json                       # 唯一状态文件
catdesk browser-action '{"action":"navigate","url":"https://ones.sankuai.com"}'
```

- ONES 接口必须用 `catdesk browser-action` 的 `evaluate` 触发（`~/.catpaw/bin/catdesk` 已废弃，直接用 PATH 里的 `catdesk`）。
- JS 模板在 `scripts/js/`，一律由 `scripts/run_js.py` 填参生成命令文件，**不要手抄一大段 JS 到命令行**。
- 批量创建 ONES 子任务时每批 **≤ 4 个**（浏览器 evaluate 会超时）。

脚本清单：

| 脚本 | 作用 |
| --- | --- |
| `scripts/schedule.py` | 解析父文档「三、人员分布一览表」→ 表格片段 + tasks + colspan 不一致 + 非 ONES 排期项 |
| `scripts/xtable_stats.py` | 读父文档三张多维表格 → 本周新增/待排期/跟进中/已排期/pd |
| `scripts/state_set.py` | 往 state.json 写字段（`--set path=@file.json`、`--get path`） |
| `scripts/render_doc.py` | 由 state.json 渲染整篇 CitadelXML（含 `--merge-pages-from` 回收涉及页面） |
| `scripts/multica_input.py` | 本周新增需求 → `multica.input`（只有涉及页面空着） |
| `scripts/multica_result.py` | Multica 创建回执 → `multica.results` |
| `scripts/map_page.py` | 「涉及页面」→ Multica 项目 ID（别名表 + 最长包含匹配） |
| `scripts/run_js.py` | 填 `scripts/js/*.js` 占位符 → browser-action 命令文件；`--extract` 回收结果 |
| `scripts/js/01-setup.js` | 查需求详情 + subtypeId + 项目迭代列表 |
| `scripts/js/02-prepare.js` | 定位本周迭代/周次、算日期、组 `allTasks`、每人 PD、迭代不一致清单 |
| `scripts/js/03-create.js` | 三层去重 + `fastIssue` 创建 + 继承标签（单批 ≤4） |
| `scripts/js/04-collect.js` | 回查子任务确认 `found`，输出 created/existing/missing |

---

## 第 0 步：前置检查

1. 用户给的必须是**父排期文档** URL（标题含 `Wxx`）。若给的是任务创建文档或模板（`2750103195` / `2750115624`），停下来让用户确认。
2. 确认 `oa-skills citadel`、`catdesk`、`ones`、`multica` 都可用。
3. 从标题取周次：`Wxx`。子文档标题 = `Wxx 需求任务创建`（与父文档同周，**不要**用迭代里的周次改写标题）。

## 第 1 步：读父文档并解析

```bash
oa-skills citadel getDocumentXml --contentId <父contentId> --mis "$MIS" --output /tmp/osm-parent.xml
python3 $SKILL/scripts/schedule.py --xml /tmp/osm-parent.xml \
  --out /tmp/osm-schedule.json --table-out /tmp/osm-schedule-table.xml
python3 $SKILL/scripts/xtable_stats.py --xml /tmp/osm-parent.xml --week <父文档周次，如 W43> \
  --mis "$MIS" --out /tmp/osm-stats.json
```

`schedule.py` 的 stderr 会打印解析摘要（周次/tasks 数/人数/不一致数/非 ONES 项/task 类型链接）。

拿到 `/tmp/osm-schedule.json` 后初始化状态：

```bash
python3 - <<'PY'
import json
s = json.load(open('/tmp/osm-schedule.json'))
json.dump({
    "week": s["week"], "parentTitle": s["parentTitle"],
    "parentUrl": "https://km.sankuai.com/collabpage/<父contentId>",
    "tableXmlPath": s["tableXmlPath"],
    "dates": s["dates"],
    "stats": json.load(open('/tmp/osm-stats.json')),
}, open('/tmp/osm-state.json', 'w'), ensure_ascii=False, indent=2)
PY
```

向用户展示解析结果（表格：人员 / 需求 issueId / 天数 / 日序）：

- **`colspanDurationMismatches` 非空 → 阻塞**：列出「人员、行号、colspan、标注 PD、issueId」，请用户回复「继续」或「取消」。
- `skippedTaskLinks` 非空：说明这些是 task 类型链接，不能挂子任务，将跳过。
- `nonOnesItems` 非空：**必须逐条点名**（人员 / 日期 / pd / 该单元格实际链接），不能只写一句「有 N 个非 ONES 项」。按链接类型分两类报给用户，并给出影响：
  - 链接指向学城文档（`km.sankuai.com/collabpage/...`，典型是 PRD）或 `wiki`：属于**填错列/填错链接**，排期表这一格本该填 ONES 需求。要说清它对应哪个需求（可用多维表格同需求的行反查）、因此不会建子任务、这 Npd 在子任务层面缺一条，并请用户确认是否换成 ONES 链接后补建。
  - 值班 / 团建 / 请假 / E2E 等无链接纯文本：正常不进 ONES，只需列出。
- 报告里凡是有 pd 却没建子任务的项，都要在「未创建原因」里出现一次，不允许静默跳过。

即使有阻塞项，也可以先把第 2 步（建子文档 + 复制表格）做完再等确认；但**创建 ONES 子任务前必须拿到「继续」**。

## 第 2 步：新建子文档并复制排期表

```bash
python3 $SKILL/scripts/render_doc.py --state $S --out /tmp/osm-newdoc.xml
oa-skills citadel createDocument --title "Wxx 需求任务创建" \
  --file /tmp/osm-newdoc.xml --parentId <父contentId> --mis "$MIS"
# 记录返回的 contentId → state.newDocId / newDocUrl
python3 $SKILL/scripts/state_set.py --state $S \
  --set newDocId=<子contentId> --set newDocUrl=https://km.sankuai.com/collabpage/<子contentId>
```

- 表格是**原样复制的 XML 片段**，mention 的 `uid/empId`、ONES 卡片、`colspan` 全部保留；这段 XML 里 nodeId 与父文档相同是正常的，学城允许跨文档重复。
- 此时文档里只有那张表 + 标题，后续小节由各步骤逐步渲染进去。

## 第 3 步：创建 ONES 子任务（同 ones-create-subtask 流程）

### 3.1 查需求详情 / subtype / 迭代

```bash
python3 - <<'PY'
import json
s = json.load(open('/tmp/osm-schedule.json'))
keys = ("issueId", "projectId", "uid", "empId", "name", "duration", "colStart", "colEnd", "rowIndex", "pdSource")
tasks = [{k: t[k] for k in keys} for t in s["tasks"]]
bad = [t for t in tasks if not t.get("projectId")]        # 链接里没有 /product/<spaceId>/ 的需求查不了详情
tasks = [t for t in tasks if t.get("projectId")]
json.dump(tasks, open('/tmp/osm-tasks.json', 'w'), ensure_ascii=False)
print(json.dumps({"tasks": len(tasks), "noProjectId": [t["issueId"] for t in bad]}, ensure_ascii=False))
PY
python3 $SKILL/scripts/run_js.py --template $SKILL/scripts/js/01-setup.js \
  --set TASKS=@/tmp/osm-tasks.json --cmd-out /tmp/osm-cmd.json
catdesk browser-action "$(cat /tmp/osm-cmd.json)" > /tmp/osm-out.json
python3 $SKILL/scripts/run_js.py --extract /tmp/osm-out.json --save /tmp/osm-setup.json
```

产出 `issueMap`（需求名/迭代/标签/pmis）、`subtypeMap`、`iterations`（项目迭代列表）、`errors`。`errors` 非空要逐条报告。

### 3.2 算日期、定位本周迭代、组任务

```bash
# 先拆出各参数文件
python3 - <<'PY'
import json
s = json.load(open('/tmp/osm-schedule.json'))
setup = json.load(open('/tmp/osm-setup.json'))
json.dump(s['dates'], open('/tmp/osm-dates.json','w'), ensure_ascii=False)
json.dump(setup['issueMap'], open('/tmp/osm-issuemap.json','w'), ensure_ascii=False)
json.dump(setup['subtypeMap'], open('/tmp/osm-subtypemap.json','w'), ensure_ascii=False)
json.dump(setup['iterations'], open('/tmp/osm-iterations.json','w'), ensure_ascii=False)
PY

python3 $SKILL/scripts/run_js.py --template $SKILL/scripts/js/02-prepare.js \
  --set TASKS=@/tmp/osm-tasks.json --set DATES=@/tmp/osm-dates.json \
  --set ISSUE_MAP=@/tmp/osm-issuemap.json --set SUBTYPE_MAP=@/tmp/osm-subtypemap.json \
  --set ITERATIONS=@/tmp/osm-iterations.json --cmd-out /tmp/osm-cmd.json
catdesk browser-action "$(cat /tmp/osm-cmd.json)" > /tmp/osm-out.json
python3 $SKILL/scripts/run_js.py --extract /tmp/osm-out.json --save /tmp/osm-prepared.json
```

关键口径：

- **本周迭代**优先按「排期表头第一天 == 项目迭代的起始日」在 `iterations` 里精确匹配（取单周迭代，排除「双周/专用」），`weekIterationSource=iteration-list`；匹配不到才退回需求自身迭代（`issue-iteration`）或出现最多的迭代（`most-frequent`）。原因：需求常被提前挪到下周迭代，只看需求迭代会把任务建到下一周、并绕过本周去重。
- **任务名** = `W{weekNum}-{需求名}`；`weekNum` 来自匹配到的本周迭代。
- **任务迭代** = 本周迭代（不是需求自身迭代）；需求自身迭代与之不同时进 `iterationMismatches`，**仅提示不阻塞**。
- 日期优先取表头（如「周一 10.26」），无日期时按迭代起始日 + 工作日偏移推算。

### 3.3 创建前确认（强制阻塞）

**不论有没有异常，都要先确认再建。** 把 `/tmp/osm-prepared.json` 的 `allTasks` 贴成清单让用户核对：

```
本周迭代：住宿-2026W45（1109-1115) / weekIterationId=126577 / 周次 W45
共 18 条，45 人天；colspan/Npd 不一致 0 条，新建候选 18 条

| # | 开发人员 | 需求 | 工作量 | 日期 | 状态 |
...

确认后回复「继续」创建；要改哪条直接说（如「第 3 条天数改成 2」「第 5 条不建」）。
```

- `colspanDurationMismatches` 非空时在清单前面单独列一块告警。
- `personPd` 里有 `over=true` 的人也在清单里标出来（`⚠️ 张策 6 人天`）。
- 用户没回复就**不能**进入 3.4；用户说「取消」直接结束，不创建、不写文档。

### 3.4 分批创建（每批 ≤ 4）

```bash
# 取 allTasks 作为分批源，再按批切片（每批 ≤ 4）
python3 -c "import json;d=json.load(open('/tmp/osm-prepared.json'));json.dump(d['allTasks'],open('/tmp/osm-alltasks.json','w'),ensure_ascii=False)"

python3 $SKILL/scripts/run_js.py --template $SKILL/scripts/js/03-create.js \
  --set TASKS=@/tmp/osm-alltasks.json --slice-key TASKS --from 1 --to 4 \
  --set WEEK_NUM='"43"' --set WEEK_ITERATION_ID=126575 --cmd-out /tmp/osm-cmd.json
catdesk browser-action "$(cat /tmp/osm-cmd.json)" > /tmp/osm-out.json
python3 $SKILL/scripts/run_js.py --extract /tmp/osm-out.json --save /tmp/osm-batch.json --append
```

- `WEEK_NUM` / `WEEK_ITERATION_ID` 用 `/tmp/osm-prepared.json` 里的同名值（`WEEK_NUM` 要带引号，按字符串传入）。
- 循环 `--from 5 --to 8`、`--from 9 --to 12` … 直到覆盖全部 `allTasks`，每次都 `--append` 累加到 `/tmp/osm-batch.json`。
- `03-create.js` 内部：创建前实时查该需求的直接子任务（`includeOtherFatherAndSon=false`），三层去重（本周 iterationId → `W{weekNum}-` 前缀（仅无迭代的老任务）→ 任务名完全一致，且必须同一负责人）→ `fastIssue` → 等 200ms 用 `PUT /api/proxy/issue/{newId}` 继承标签 → 每条间隔 500ms。命中已有任务时返回 `已存在` + `skipReason`，**不会重复创建**。

### 3.5 回查确认

```bash
python3 $SKILL/scripts/run_js.py --template $SKILL/scripts/js/04-collect.js \
  --set RESULTS=@/tmp/osm-batch.json --set WEEK_ITERATION_ID=126575 --cmd-out /tmp/osm-cmd.json
catdesk browser-action "$(cat /tmp/osm-cmd.json)" > /tmp/osm-out.json
python3 $SKILL/scripts/run_js.py --extract /tmp/osm-out.json --save /tmp/osm-verified.json
```

`counts.missing > 0`（`found=false`）说明接口返回成功但实际没建上，必须重跑该批或人工补建，并在报告里点名。

### 3.6 写回子文档

```bash
# 回查结果里的 verified 就是文档明细表的行来源
python3 -c "import json;d=json.load(open('/tmp/osm-verified.json'));json.dump(d['verified'],open('/tmp/osm-ones-results.json','w'),ensure_ascii=False)"
python3 $SKILL/scripts/state_set.py --state $S --set ones.results=@/tmp/osm-ones-results.json
python3 $SKILL/scripts/render_doc.py --state $S --out /tmp/osm-newdoc.xml
oa-skills citadel getDocumentXml --contentId <子contentId> --mis "$MIS" --output /tmp/osm-cur.xml   # 记下 stepVersion
oa-skills citadel updateDocumentByXml --contentId <子contentId> --file /tmp/osm-newdoc.xml \
  --mis "$MIS" --step-version <N>
```

渲染结果（顺序固定）：

1. 复制来的排期表
2. `## Ones 子任务创建结果` + 明细表（开发人员 | 任务标题 | 工作量 | 日期 | 状态 | 标签 | 任务ID）
3. 汇总两行（见第 4 步口径）
4. `人力投入汇总：总任务 X 个（新创建 a 个，已存在 b 个），总人力 Y 人天，参与 Z 人` + 每人汇总表
5. `## Multica 新任务创建输入`

## 第 4 步：汇总段口径（脚本已实现，核对即可）

统计来自 `stats`（`xtable_stats.py` 对父文档 1.1 国内 / 1.2 境外 / 1.3 民宿 三张多维表格求值）：

| 指标 | 口径 |
| --- | --- |
| 本周新增需求 | `需求ones` 列含 `Wxx新增` 的行，**排除** `需求排期=已完成/不涉及` |
| 已评审待排期 | 计数前先按 `研发状态` 过滤：`已上线` / `已归档` / **空** 的行一律不计；剩下的按 `需求排期 = 已评待排期` 计数 |
| 跟进中 | 同上过滤后，`需求排期 = 跟进中` 的行数 |
| 已排期 | 同上过滤后，`需求排期 = 本周需求池` 的行数 |
| 需求承接率 | **自动计算**：`(境内+境外 本周需求池行数) / (境内+境外 本周需求池 + 已评待排期行数)`，**民宿整段不计**，计数前同样按 `研发状态` 过滤；分母为 0 时退回 `{人工填写}`。值在 `stats.rateAuto`，分子分母在 `stats.rateDetail.num/den` |
| pd 公式 | **只取 `需求排期 = 本周需求池` 的行**，把 `下周投入` 单元格里**所有** `Npd` 都相加（一格内并列多人时必须累加，只取第一个会少算），按境内/境外/民宿分列；`本周借调` 同样整列全值求和作为括号注 |

> 计数与 pd 必须是两套过滤：计数丢掉 `研发状态` 已结束/为空的行，pd 不丢（那些行的下周投入本来多为空或 0，所以结果通常一致）。实测 W45 只有按此口径才能同时得到 `2/2/11/12` 与 `境内25.5 + 境外12 + 民宿7 = 44.5pd`。

> 承接率口径可用历史文档反验：父文档 W44 写的 `83.3%` 正好是 `已排期10 / (已排期10 + 已评审待排期2)`，即分母是「本周评审过、进了排期流程的需求」，不是表格全量行（境内 137 + 境外 32 行会把比例压到个位数，明显不对）。分母只算 `本周需求池 + 已评待排期`，`已完成/跟进中/暂停中` 不进分母。

> 分母天然不含「已标记完成、其实不需要排期」的需求（典型如 W45 迭代里挂着的「组合订能力建设一期」）：`研发状态 ∈ {已上线, 已归档}` 的行在计数前就被丢掉了。所以自动值（W45 = 80.0%）与人填值（81%）之间的差**不是**这类需求造成的，**人填值仍然优先、不要用自动值覆盖**；`--use-rate-auto` 只在用户明确说要换成自动值时用。

输出模板（`render_doc.summary_para`）：

```
本周新增需求2个，已评审待排期 0个，跟进中14个，已排期15个。需求承接率: <stats.rate 手填值，没有则 rateAuto>。详细排期情况见<父文档链接>
境内 16pd + 境外 11pd + 民宿 7.5pd = 34.5pd（借调4.5pd）
```

承接率取值的优先级：`stats.rate`（人已在文档里手填过的） > `stats.rateAuto`（排期表自动算） > `{人工填写}`。

```bash
# 重渲染时保留文档里手填的值
python3 $SKILL/scripts/render_doc.py --state $S --keep-rate-from /tmp/osm-cur.xml --out /tmp/osm-newdoc.xml
# 手填值与自动计算不一致，脚本会往 stderr 打 [rate] 手填 81% ≠ 排期表自动计算 80.0%（分子 8 / 分母 10）
# 要用自动值覆盖手填值
python3 $SKILL/scripts/render_doc.py --state $S --use-rate-auto --out /tmp/osm-newdoc.xml
```

> ⚠️ 口径说明：多维表格是**人工持续维护**的，历史文档里的数字可能与脚本实时聚合结果不一致（例如参考文档写 16/11/7.5pd，脚本按同一周表格实时算可能得到别的值）。**脚本数字为准，不要为了对齐历史文档去改算法**；差异明显时在完成报告里点一句「表格实时数据与历史文档不一致，建议核对表格」。`已完成/不涉及` 行不计入本周新增是既定口径。

## 第 5 步：Multica 输入表 → 停下来等用户选「涉及页面」

```bash
python3 $SKILL/scripts/multica_input.py --state $S --stats /tmp/osm-stats.json
python3 $SKILL/scripts/render_doc.py --state $S --out /tmp/osm-newdoc.xml
oa-skills citadel updateDocumentByXml --contentId <子contentId> --file /tmp/osm-newdoc.xml --mis "$MIS"
```

- `multica.input` 每行：开发人员（该需求在 ONES 结果里的人员，没有则退回表格 `需求主R`）、任务标题（需求名）、需求 ones、需求 PRD、涉及页面（**空**）。
- `multica_input.py` 的 stdout 会给 `noPrd` 清单——这些需求后面**不会**建 Issue，此处就告知用户。

### 5.1 先查项目列表，让用户选（不要让他自由填）

**每次都要实时查**，不能用上一周的缓存（工作区会新增项目，如「超团提单」）：

```bash
WS=${WS:-$(multica workspace list --output json | jq -r '.[]|select(.slug=="hotel-trade-fullstack").id')}
multica --workspace-id "$WS" project list --output json > /tmp/osm-projects.json
python3 -c "import json;[print('%2d. %s'%(i,p['title'])) for i,p in enumerate(json.load(open('/tmp/osm-projects.json')),1)]"
```

然后在对话里把**项目清单带编号**贴给用户，每条需求给一行，让他选编号：

```
Multica 输入表已写入文档。工作区现有项目：
 1. 超团提单   2. 消费券   3. 取消流程一致性   4. 非房二期
 5. 住宿活包提单页   6. 酒店提单页   7. 酒店订单详情页
 8. 退款详情页（前端+后端API）   9. 酒店提单页（前端+后端API）   10. 退款页面

请给下面每一行选一个项目编号（可留空 = 不指定项目）：
| # | 需求 | 开发人员 | PRD | 选项目 |
| 1 | 超团放开价格限制&非房放开标题字数限制 | 李定成 | ✅ | ? |
| 2 | 提单页权益勾选取消toast常驻问题修复 | 李炎炎 | ❌ | ? |
```

- 用户回复编号 / 项目名 / 「第 1 行选超团提单」都行；也可以直接去文档的「涉及页面」列填，两种都收。
- **必须停下等用户回复**，不要自己猜页面，也不要拿历史映射表替他定。
- 用户如果只写了页面口语（如「主提单」），用 `map_page.py` 校验后把结论回读给他确认，确认后再建。
- **页面在工作区里找不到对应项目时，不要凑一个**，按这个口径回给用户：
  > 「XXX」在 Multica 项目列表里没有对应项目。要么找 **zhangce07** 新增该项目；如果是**一个大需求横跨多个页面**，也可以新增一个以需求名命名的「需求组」项目来统一承接，避免被拆到多个页面项目里。
  等用户确认走哪条，不要自己在相近项目里挑。

## 第 6 步：创建 Multica 任务（同 trade-ones-multica 流程）

用户回复后，先回收页面：

```bash
oa-skills citadel getDocumentXml --contentId <子contentId> --mis "$MIS" --output /tmp/osm-cur.xml
python3 $SKILL/scripts/render_doc.py --state $S --merge-pages-from /tmp/osm-cur.xml --out /tmp/osm-check.xml
python3 $SKILL/scripts/state_set.py --state $S --get multica.input    # 确认 pages 已回填
```

回收后用映射脚本把「涉及页面」落到项目 ID，**不靠眼判断**：

```bash
python3 $SKILL/scripts/map_page.py --projects /tmp/osm-projects.json \
  --json "$(python3 -c "import json;print(json.dumps([i.get('pages','') for i in json.load(open('$S'))['multica']['input']],ensure_ascii=False))")" --pretty
```

- `match=exact|contains` → 直接用那个 `projectId`。
- `match=none` 或 `conflict` → 该行不传 `--project`，结果表备注写「项目缺失：<页面>，需找 zhangce07 新增项目」，并在报告里点名；若是大需求跳多页面，建议新增一个需求组项目承载，不要落到最相近的页面项目。

准备环境：

```bash
WS=${WS:-$(multica workspace list --output json | jq -r '.[]|select(.slug=="hotel-trade-fullstack").id')}
PMO_ID=$(multica --workspace-id "$WS" agent list --output json | jq -r '.[]|select(.name=="sdlc-ai-pmo").id')
multica --workspace-id "$WS" project list --output json > /tmp/osm-projects.json
multica --workspace-id "$WS" workspace member list --output json > /tmp/osm-members.json
```

逐条创建（每条之间 sleep 1 秒，一条失败不影响后续）：

```bash
cat > /tmp/osm-desc.md <<'EOF'
<PRD 链接>

负责人：王宇
EOF

multica --workspace-id "$WS" issue create \
  --title "<需求名>" \
  --description-file /tmp/osm-desc.md \
  --assignee-id "$PMO_ID" \
  --owner-id "<owner user_id>" \
  --project "<project id>" \
  --status backlog \
  --daxiang-group off \
  --output json
```

- 项目映射（**映射表在 `trade-ones-multica/SKILL.md` 维护，脚本 `scripts/map_page.py` 实现，两边各一份必须同步**），按顺序判定：
  1. **别名精确匹配**：`涉及页面` 归一化后与某个别名/项目标题整串相等（如 `主提单` / `新提单` / `DUO提单` / `主流程提单页` / `提单页` → `酒店提单页`）。
  2. **最长别名包含**：页面名里含某个别名，取最长的那条（`主提单页改版` → `酒店提单页`）。
  3. **未命中/冲突 → 留空**：不传 `--project`，结果表「项目」列留空，备注写「项目待确认」，并在对话里问用户。
  - **禁止按关键词联想**：`超团提单` 不含「提单页」，是独立项目；`酒店提单页` 与 `酒店提单页（前端+后端API）`、`住宿活包提单页` 互不相干。别名表里不出现「提单」这种通用短词，否则会把「超团提单」抢走。
- owner 用成员列表按 `name` 精确匹配或 `email` 前缀 = mis；多人共担且用户没指定就留空并在报告里问。
- 子需求才写 ONES：`multica issue metadata set <id> --key ones_url --value "<子需求链接>" --type string`；父需求/子任务/无法判定留空。
- 没有 PRD → 直接跳过，结果表记 `未创建·无PRD`。
- 创建回执里取 `id`、`identifier`（如 `WS-206`），URL 用 `https://mlt.sankuai.com/hotel-trade-fullstack/issues/<identifier>`。

把每条回执写成 `/tmp/osm-multica-result.json`（`[{reqId, issue, issueUrl, project, status, note}]`），然后：

```bash
python3 $SKILL/scripts/multica_result.py --state $S --input /tmp/osm-multica-result.json
python3 $SKILL/scripts/render_doc.py --state $S --out /tmp/osm-newdoc.xml
oa-skills citadel updateDocumentByXml --contentId <子contentId> --file /tmp/osm-newdoc.xml --mis "$MIS"
```

## 第 7 步：结果表与完成报告

`## Multica 新任务创建结果` 表列固定：

`序号 | 开发人员 | 需求名称 | 需求 ONES | PRD | 涉及页面 | 项目 | Multica Issue | 状态 | 备注`

对话里给完成报告，必须包含：

1. 子文档链接（`https://km.sankuai.com/collabpage/<子contentId>`）。
2. ONES：总 X 个（新创建 a / 已存在 b / 失败 c），`missing` 条目点名。
3. 汇总段数字（与文档一致），承接率报出自动计算值并带分子分母，如「承接率 80.0%（境内+境外 本周需求池 8 / 已进排期流程 10，不含民宿）」；若文档里有手填值且与自动值不同，两个都写出来让用户定。
4. Multica：创建成功 n 个，跳过 m 个（逐条原因：无 PRD / owner 未定 / 其他）。
5. 未解决项：`errors`、`iterationMismatches`（需求还没挪到本周迭代的人）、`nonOnesItems`、`skippedTaskLinks`。

## 失败处理

| 现象 | 处理 |
| --- | --- |
| `01-setup` 返回 `errors` 里 `issue` 失败 | 该需求详情查不到（issueId 错/无权限），让它进 `invalid`，不参与创建，报告里点名 |
| `fastIssue` 返回非 200/201 | 记 `创建失败(code)`，不重试同一批（重试前先跑 `03-create` 的去重，`已存在` 会挡掉） |
| 标签 `PUT` 返回非 200 | 任务已建但无标签，结果表备注「标签未继承」，单独报告 |
| `04-collect` 有 `found=false` | 重跑对应批次（去重会命中已建的），仍失败则人工补建并写进报告 |
| `updateDocumentByXml` 报 mention 缺 `uid` | 检查 state 里 mention 用的是 `uid` 字段（`mis` 也会被 `render_doc.cell` 兼容），不要手写 xml |
| 迭代匹配落到 `most-frequent` | 说明排期表头没有日期或迭代列表里没有同起始日的迭代，先看 `dates` 是否为空，必要时人工指定 `weekIterationId` 重跑 3.2 |
