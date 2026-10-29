---
name: trade-ones-multica
description: "把每周「任务创建结果」表格里标记为 本周新增 的需求，在 Multica 工作区批量创建开发任务 Issue：owner 取表格里的开发人员、指派给 sdlc-ai-pmo、状态 backlog（创建后不触发执行）、ONES 字段填子需求链接、项目按涉及页面映射、任务简介放 PRD 链接。创建前先出一张确认表让用户核对补全，创建后把结果表回写到学城文档末尾。触发词：Multica 建任务、每周需求建 Multica、需求转 Multica、ONES 转 Multica、本周新增建任务、批量创建 Multica 任务、W4x 建任务、按需求建 Issue、需求排期建任务。"

metadata:
  skillhub.creator: "zhangce07"
  skillhub.updater: "zhangce07"
  skillhub.version: "V1"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "156015"
  skillhub.high_sensitive: "false"
---

# 每周新增需求 → Multica 开发任务

输入一张「任务创建结果」表格（学城文档或直接粘贴），筛出 `本周新增 = 是` 的需求，一个需求在 Multica 建一个 Issue，创建前出确认表让用户补全，创建后把结果回写到原文档末尾。

## 核心原则（不可越过）

1. **一个需求一个 Issue**：按「需求 ones」去重，同一需求的多个 devTask 行合并成一条，不按行建。
2. **PRD 是硬门槛**：PRD 为空的需求**不创建**，不进入创建清单，只在告警区红字列出。PRD 不做任何兜底（不拿 ONES 描述、不拿 ONES 链接凑）。
3. **只认 `本周新增 = 是`**：其余需求组一律不建，列出但不处理。
4. **不猜**：项目只有「提单页 / 单详页」两条映射，其他留空等用户填；ONES 只在能判定为**子需求**时才填，父需求/子任务/无法判定一律留空等用户补。
5. **创建后不触发执行**：状态用 `backlog`，由 owner 自己启动。
6. **先确认后创建**：确认表没得到「继续」之前，不执行任何创建动作。
7. **学城只走 citadel CLI**：不用 browser / web_fetch 动学城文档（会产生脏数据）。
8. **失败不静默**：任何一条解析失败、查询失败、创建失败，都在最终报告里逐条列出原因。

## 固定配置（运行时按名称查 ID，禁止硬编码 UUID）

| 项 | 取值 |
| --- | --- |
| 默认工作区 | slug = `hotel-trade-fullstack`；用户指定则用指定的 |
| Assignee | agent `sdlc-ai-pmo` |
| 创建状态 | `backlog` |
| 大象群聊 | `off`（`--daxiang-group off`） |
| 项目映射 | `涉及页面` 含「提单页」→ 项目 `酒店提单页`；含「单详页」→ 项目 `酒店订单详情页`；其余留空 |
| 标签 / 优先级 / 截止日期 | 不动，保持默认 |

项目映射按**项目标题精确匹配**取 ID，不要用模糊匹配，因为工作区里同时存在「酒店提单页」「酒店提单页（前端+后端API）」「住宿活包提单页」三个相似项目。

## 执行流程

### 第一步：解析参数与准备环境

```bash
WS=${WS:-$(multica workspace list --output json | jq -r '.[]|select(.slug=="hotel-trade-fullstack").id')}
PMO_ID=$(multica --workspace-id "$WS" agent list --output json | jq -r '.[]|select(.name=="sdlc-ai-pmo").id')
multica --workspace-id "$WS" project list --output json > /tmp/om-projects.json
multica --workspace-id "$WS" workspace member list --output json > /tmp/om-members.json
```

`PMO_ID` 查不到时终止并告知用户该工作区没有 `sdlc-ai-pmo`。

### 第二步：取表格

**学城文档**（优先，能拿到 mention 的 mis 和真实合并单元格）：

```bash
oa-skills citadel getDocumentJson --contentId <contentId> --mis "${MIS:-$SSO_USER_ID}" 2>/dev/null \
  | sed -n '/^{"type":"doc"/,$p' > /tmp/om-doc.json
python3 scripts/parse_table.py --doc-json /tmp/om-doc.json --json /tmp/om-parsed.json
```

**粘贴文本**：把用户给的表格原样写到 `/tmp/om-table.md`，再 `--md /tmp/om-table.md`（没有 mis，只能按姓名匹配成员）。

脚本会自动挑出含必需列（开发人员 / 需求 ones / 需求 PRD / 涉及页面 / 本周新增）的那张表。多张表都符合时用 `--table-index <n>` 指定；不确定就先看脚本 stderr 的候选提示再问用户。

**读结果**（`/tmp/om-parsed.json`）：

- `groups[]`：按 requirement 链接去重的需求组，含 `persons`、`tasks[]`、`prd`、`pages`、`isNew`、`notes`
- `orphans[]`：没有 requirement 链接的行（`reqKind=devtask` 说明填的是子任务链接）
- `summary`：`reqGroups` / `newReqGroups` / `orphanRows`

若 `summary.reqGroups == 0`：说明表格里没有可识别的需求链接，停下来告诉用户「第 X 行列了 N 个任务但没有需求 ones 链接」，不要硬建。

### 第三步：查 ONES 需求详情

对每个 `groups[].reqId` 执行（最多 10 个可串行，超过则分批）：

```bash
ones workitem-detail -i <reqId> --json > /tmp/om-ones-<reqId>.json
```

取这些字段：

| 用途 | 字段 |
| --- | --- |
| 任务标题 | `name.displayValue` |
| 工作项类型 | `type`（`REQUIREMENT` / `DEVTASK`） |
| 父级 | `parentId.id`、`parentId.displayValue`、`parentId.extra.issueType` |
| 空间 | `projectId.value` |

**类型判定**（决定 ONES 字段填不填）：

| 判定 | 条件 | ONES 字段 |
| --- | --- | --- |
| 子需求 | `type == REQUIREMENT` 且 `parentId` 存在且 `parentId.extra.issueType == requirement` | **填** requirement 链接 |
| 父需求 | `type == REQUIREMENT` 且无 `parentId`（或父级不是 requirement） | 留空，待补 |
| 子任务 | `type == DEVTASK` 或 URL 是 `/workItem/devTask/detail/` | 留空，待补 |

ONES 链接统一用 `https://ones.sankuai.com/ones/product/<spaceId>/workItem/requirement/detail/<reqId>`，不要带 `?activeTabName=` 之类的尾巴。

### 第四步：算字段

| Multica 字段 | 取值 |
| --- | --- |
| 标题（`--title`） | ONES 需求名称，不加 `W43-` 之类前缀 |
| 简介（`--description-file`） | 第一行 PRD 链接；空行后可写备注（见下） |
| Owner（`--owner-id`） | 该需求的开发人员 user_id |
| 项目（`--project`） | 按 `涉及页面` 映射，未命中留空 |
| ONES（metadata `ones_url`） | 子需求链接，否则不写 |
| 状态 | `backlog` |

**Owner 解析**：用 `/tmp/om-members.json` 按 `name` 精确匹配，或按 `email` 前缀等于 mis 匹配。

- 一个需求只有一个开发人员且匹配成功 → 自动填
- 一个需求多人共担 → **留空**，确认表里等用户指定（owner 决定运行时落在谁机器上，不能替用户选）
- 匹配不到（如外部同学不在工作区）→ 留空，姓名写进简介备注，确认表标黄

**简介模板**（PRD 必须在第一行）：

```markdown
<PRD 链接>

负责人：王宇
待补充：子需求 ONES 链接（当前填的是父需求）
```

没有备注时只留 PRD 链接一行，不要写「PRD：」之类前缀。

### 第五步：出确认表（阻塞，等「继续」）

先给汇总：`表格共 N 行 → 识别 M 个需求组 → 本周新增=是 的 K 个 → 将创建 J 个`。然后给主表：

| # | 开发人员 | 需求 ONES | 需求名称 | 类型 | PRD | 涉及页面 | 项目 | Owner | 结论 |

`结论` 只有四种：`待创建` / `不创建·无PRD` / `待补 ONES` / `待确认(多人 owner)`。

主表之后按需追加四个清单（为空就不显示）：

- **无 PRD（不创建）**：红字列出需求名 + ONES 链接 + 影响的人，提示「这些需求这轮不会建，补 PRD 后重跑」。
- **ONES 留空（仍会创建）**：列出父需求/子任务/无链接的条目，说明「可以先补链接，不补也会建 Issue，但 ONES 字段为空，建完会再次提醒」。
- **Owner 待填**：多人共担的需求，列出人员与各自工作量（PD），让用户指定一个人或按人拆。
- **本周新增未标记（已跳过）**：列出没标 `是` 的需求组，避免用户漏标后以为建全了。

末尾明确写：**回复「继续」开始创建；要改哪条直接说「第 3 行项目改成酒店提单页」「第 2 行 owner 给刘欣」。** 收到「取消」或语义等价的否定就终止，不创建任何东西。

### 第六步：创建

**创建前置条件**（逐条判断，不满足就跳过，写进结果表 `未创建`）：

- 无 PRD → 跳过（硬门槛，无兜底）
- 多人共担且用户还没指定 owner → 跳过，结果表备注 `owner 待用户指定`，报告里再问一次；用户指定后只补这一条
- 其余 ONES 为空、owner 匹配不到的情况**照常创建**，靠简介备注 + 报告兜底

逐条创建（每条之间 sleep 1 秒），**一条失败不影响后续**：

```bash
cat > /tmp/om-desc.md <<'EOF'
<PRD 链接>

负责人：王宇
EOF

multica --workspace-id "$WS" issue create \
  --title "<需求名称>" \
  --description-file /tmp/om-desc.md \
  --assignee-id "$PMO_ID" \
  --owner-id "<owner user_id>" \
  --project "<project id>" \
  --status backlog \
  --daxiang-group off \
  --output json
```

再写 ONES：

```bash
multica --workspace-id "$WS" issue metadata set <issue-id> \
  --key ones_url --value "<子需求链接>" --type string --output json
```

注意：

- 没有 owner 时**不要**传 `--owner-id`（传空串会报错）；没有项目时**不要**传 `--project`。
- 描述含中文和换行，必须走 `--description-file`，不要内联 `--description`。
- `metadata set` 失败要单独记一条「Issue 已建但 ONES 未写入」，不要重试创建（会重复建）。
- 用户要求补 ONES、改 owner/项目时，用 `multica issue update` / `metadata set` 改同一条 Issue，不新建。

### 第七步：回写学城文档

只在**输入是学城文档**时执行；粘贴文本没有目标文档，跳过并说明。

```bash
# 1) 生成结果表片段（行顺序 = 主表顺序，未创建/跳过也要写进表并注明原因）
python3 scripts/render_result_table.py --input /tmp/om-result.json --output /tmp/om-result.xml

# 2) 取最新 XML 与 stepVersion
oa-skills citadel getDocumentXml --contentId <contentId> --mis "$MIS" --output /tmp/om-doc.xml
# 输出里会打印「文档版本（stepVersion）：N」，记下来

# 3) 把片段插到 </km-doc> 之前
python3 - <<'PY'
x = open('/tmp/om-doc.xml', encoding='utf-8').read()
add = open('/tmp/om-result.xml', encoding='utf-8').read()
i = x.rfind('</km-doc>')
open('/tmp/om-doc-new.xml', 'w', encoding='utf-8').write(x[:i] + add + x[i:])
PY

# 4) 回写
oa-skills citadel updateDocumentByXml --contentId <contentId> \
  --file /tmp/om-doc-new.xml --mis "$MIS" --step-version <N>
```

回写表列固定为：

`序号 | 开发人员 | 需求名称 | 需求 ONES | PRD | 涉及页面 | 项目 | Multica Issue | 状态 | 备注`

- 每次运行在文档末尾新增**一张**表，表头上方带一行日期小标题（如 `2026-10-21 W43 任务创建结果`），便于区分周次。
- 同一轮内的修改（补 owner、换项目、补 ONES、更新创建结果）**改这张表本身**，不要追加第二张。
- `状态` 用 `已创建` / `未创建` / `创建失败`；`备注` 写原因（无 PRD / ONES 待补 / owner 未匹配 等）。
- 文档有并发编辑时 `updateDocumentByXml` 会提示风险：先确认没人正在编辑，重新取 `stepVersion` 后再写，不要硬写。

### 第八步：报告

给用户三段：

1. **建了什么**：Issue 编号 + 链接 + 标题 + owner，一行一条。
2. **没建的**：无 PRD、创建失败、用户主动跳过，各写明原因。
3. **要你补的**：ONES 为空的 Issue（带链接，说明「补链接后告诉我，我写进 ones_url」）、owner 留空的 Issue（说明会回退到创建者/兜底 runtime）。

报告末尾固定提醒两句：这些 Issue 现在是 `backlog`，需要 owner 自己启动；同一份表格重复运行会重复创建 Issue（本 skill 不做跨次去重）。

## 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| 解析出 0 个需求组 | 表格里「需求 ones」列没填链接，先让用户补或确认列位置 |
| 大量 `orphans` | 该列只在每人/每组第一行填一次且不是合并单元格；逐条列给用户，不要自动猜 |
| 需求链接是 devTask | 用户填成了子任务链接，归入待补，不要拿 devTask 当需求 |
| `Invalid request: invalid agent id` | 用了 agent 名字而不是 UUID，先 `agent list` 取 id |
| 创建成功但 ONES 为空 | `metadata set` 失败或该需求不是子需求，按报告清单补 |
| 学城写回报并发保护 | 重新 `getDocumentXml` 取最新 `stepVersion` 再写 |

## 文件说明

- `scripts/parse_table.py`：把学城文档 JSON（或粘贴的 Markdown 表格）解析成需求组，处理 rowspan/colspan 合并单元格，输出 `groups` / `orphans`。
- `scripts/render_result_table.py`：把结果数据渲染成可追加到文档末尾的 CitadelXML 片段。
