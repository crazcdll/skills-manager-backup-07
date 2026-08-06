# 指令编排完整示例

> **加载时机**：当 SKILL.md 中的精简 Case 示例不够详细、Agent 需要查看完整的多步骤编排流程时，按需读取本文件。

---

## Case 1: 「查看我这周的工时情况并补填」

**User input content:**
```text
帮我看看这周工时填了没，没填的帮我补上
```

```bash
# 1. 查本周汇总，找出缺填日期
ones wts
# 2. 搜索可填工时的工作项
ones wtsearch -n "关键词"
# 3. 对缺填日期逐天填写（ID 来自步骤 2）
ones wtadd -i <工作项ID> --hours 8h -d 2026-03-10
ones wtadd -i <工作项ID> --hours 8h -d 2026-03-11
```

---

## Case 2: 「为需求创建分支并开始开发」

**User input content:**
```text
帮我给需求 93833807 建个分支
```

```bash
# 0. 【优先】获取当前仓库 remote 地址（无需用户提供）
git remote get-url origin
# 输出示例: ssh://git@git.sankuai.com/ee/ones-cli.git
# → 直接使用完整地址，无需提取仓库名
# ⚠️ 若失败（不在 git 仓库 / 无 remote）→ 询问用户提供仓库名或 appkey

# 1. 获取工作项详情（含空间 ID）
ones workitem-detail -i <工作项ID> --json

# 2. 搜索空间应用，获取应用 ID（直接用步骤 0 获取的完整 remote 地址）
ones apps -p <空间ID> -n "ssh://git@git.sankuai.com/ee/ones-cli.git"
# → 从结果中取 id 字段作为应用 ID
# ⚠️ 搜索无结果 → 禁止换关键词重试，应询问用户提供准确的仓库名或 appkey

# 3. 生成分支名
ones bg -i <工作项ID> --copy

# 4. 创建分支并关联工作项（应用 ID 来自步骤 2）
ones bc -i <工作项ID> -a <应用ID> -y

# 5. 本地 checkout（分支名来自步骤 3）
git checkout -b <分支名>
```

---

## Case 3: 「创建需求并安排到迭代」

**User input content:**
```text
在商品中心空间新建一个高优需求"优化搜索性能"，放到 Sprint 26 迭代里
```

```bash
# 1. 查找空间（⚠️ 只会返回有权限的空间）
ones sp -n "商品中心"
# 2. 查询子类型（获取 subtypeId）
ones vs -p <空间ID> -s <子类型ID>
# 3. 创建工作项（⚠️ CLI 会前置校验空间权限，无权限直接阻断）
ones wc -t REQUIREMENT -p <空间ID> -s <子类型ID> --priority 高 --title "优化搜索性能" -y
# 4. 查找迭代
ones iter -p <空间ID> -n "Sprint 26"
# 5. 将工作项指派到迭代（ID 来自步骤 3、4）
ones si -i <工作项ID> -t <迭代ID>
```

---

## Case 4: 「查看需求关联的分支和提测状态」

**User input content:**
```text
查一下 93833807 这个需求的分支和提测情况
```

```bash
# 1. 获取工作项详情（含空间 ID）
ones workitem-detail -i 93833807 --json
# 2. 查关联分支
ones branch -p <空间ID> -i 93833807
# 3. 查该工作项关联的提测列表
ones submittest list -p <空间ID> -i 93833807 --json
# 4. 查提测详情（使用步骤 3 返回的提测单 ID）
ones st -p <空间ID> -i <提测单ID>
```

---

## Case 5: 「创建测试计划 → 轮次 → 添加用例 → 执行」

**User input content:**
```text
给需求 93833807 创建一套完整的测试流程
```

```bash
# 1. 创建测试计划
ones plan-c -c REQUIREMENT -p <空间ID> --title "回归测试" --requirement-ids "93833807"
# 2. 创建轮次（计划 ID 来自步骤 1）
ones round-c -p <空间ID> --plan-id <计划ID> -t FUNCTION_TEST --title "功能测试"
# 3. 向轮次添加用例（轮次 ID 来自步骤 2）
ones round-ca -p <空间ID> -r <轮次ID> --plan-id <计划ID> -a ADD
# 4. 标记用例执行结果
ones round-cu -p <空间ID> -r <轮次ID> -s SUCCESS
```

---

## Case 6: 「修改或删除某个工时记录」

**User input content:**
```text
帮我把那个 93833807 工作项上填的工时改成 4 小时
```

```bash
# 1. 查工时日志，获取记录 ID
ones wtd -i 93833807
# 2. 修改工时（记录 ID 来自步骤 1）
ones wtu --id <记录ID> -i 93833807 --hours 4h
# 或删除
ones wtdel --id <记录ID>
```

---

## Case 7: 「一周批量填写工时」

**User input content:**
```text
帮我把这周工时都填上,填到"搜索优化"那个项目上
```

```bash
# 1. 搜索工作项
ones wtsearch -n "搜索优化"
# 2. 批量填写（日期范围 + -y 跳过确认，ID 来自步骤 1）
ones wtadd -i <工作项ID> --hours 8h -d 2026-03-10~2026-03-14 -y
```

---

## Case 8: 「创建工作项（需求/任务/缺陷）完整引导流程」

**User input content:**
```text
帮我创建一个需求
```

按以下步骤依次执行（⚠️ 步骤 3 前 CLI 会自动前置校验空间权限，无权限直接阻断）：

```bash
# 1. 确定空间：让用户提供关键词搜索（只返回有权限的空间）
ones sp -n "<关键词>"

# 2. 确定类型：询问用户要创建 REQUIREMENT / DEVTASK / BUG

# 3. 查子类型列表（字段ID 不确定时先用 fs 查出）
ones fo -p <spaceId> -f <子类型字段ID> -t component_issue_type -s <workitemType>
ones fs -p <spaceId> -t <workitemType> -n "子类型"   # 如不知字段ID

# 4. 查界面方案，提取 required=true 的必填字段
ones vs -p <spaceId> -s <subtypeId>

# 5. 补全字段元信息（view-scheme 未包含完整类型时）
ones fs -p <spaceId> -t <workitemType> -n "<字段名>"

# 6. 查必填字段可选值（枚举/用户/迭代等类型）
ones fo -p <spaceId> -f <字段ID> -t component_user
ones fo -p <spaceId> -f <字段ID> -t component_iteration -s <workitemType>

# 6a. 级联字段（cascader）：查可选值后只能选最末级节点，各层 value 用 ^ 拼接
ones fo -p <spaceId> -f <字段ID> -t cascader
# 假设返回 [{ value:"1", displayValue:"产品线A", children:[{ value:"2", ..., children:[{ value:"3", ... }] }] }]
# 传值 → fieldValue = "1^2^3"

# 6b. 组织字段（component_new_org，如需求提出部门 customField23388）：
#     提示用户提供完整部门链（可从大象个人名片中查找，如：美团/行政/行政BP中心）
#     → 调接口获取 ID → 用 ID 作为 fieldValue
#     接口: GET /api/proxy/org/getOrgByPath?path=<URL编码路径>

# 7. 拼接参数创建（所有 ID 来自前序查询，不可猜测）
# ⚠️ 注意：下拉字段统一使用 value（而非 displayValue）；级联字段用 ^ 拼接
ones wc -t <workitemType> -p <spaceId> -s <subtypeId> \
  --title "<标题>" --priority <优先级> --field-values '<必填字段JSON>' -y
```

> 步骤 3 若 `fo` 报错找不到字段 → 先用步骤 5 的 `fs` 查出字段 ID 再重试。步骤 6 只对有限可选值的字段调用 `fo`，自由文本字段直接询问用户。
> ⚠️ **字段取值关键规则**：所有下拉字段 fieldValue 必须使用接口返回的 `value`（非 `displayValue`）；**级联字段只能选最末级节点**，层级用 `^` 拼接（如 `"1^2^3"`）；组织字段需先用路径查询接口获取组织 ID。

---

## Case 9: 「查看我待开发/正在开发的工作项」（⚠️ 与我相关查询）

**⚠️ 此类查询必须带人员筛选**，查不到禁止自行扩大搜索。详细规则见 [DSL 筛选指南 - 策略 5](./filter-query-dsl.md)。

```bash
# 查我的未完成需求（TODO+DOING）
ones fi -p <空间ID> -t REQUIREMENT --assigned <misId> --state TODO,DOING --json

# 查我的所有未完成工作项（需求+任务+缺陷）
ones fi -p <空间ID> --assigned <misId> --state TODO,DOING --json

# 查我是技术主R的需求（DSL 模式，customField24214 或别名 rdMasters 均可）
ones fi -p <空间ID> -t REQUIREMENT \
  --query '[{"field":"customField24214","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json

# 查我是开发人员的任务（DSL 模式，developer 或别名 developers 均可）
ones fi -p <空间ID> -t DEVTASK \
  --query '[{"field":"developer","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json

# 查我是产品主R的需求（customField13161）
ones fi -p <空间ID> -t REQUIREMENT \
  --query '[{"field":"customField13161","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json

# 查我是测试主R的需求（customField24215）
ones fi -p <空间ID> -t REQUIREMENT \
  --query '[{"field":"customField24215","type":"TERM","value":"<misId>"}]' \
  --state TODO,DOING --json
```

> **人员角色字段 variable（全局唯一，所有空间通用）**：产品主R=`customField13161`、技术主R=`customField24214`（别名 `rdMasters`）、测试主R=`customField24215`、开发人员=`developer`（别名 `developers`）。
> 结果为空 → 告知用户条件下无匹配，建议调整空间/状态范围，❌ 禁止去掉 --assigned 重试。

---

## Case 10: 「查询指定时间范围内开发/上线的工作项」

**User input content:**
```text
帮我查下本周预计开发的需求有哪些
今天我在开发哪些工作项
当月预计上线的需求进展怎么样
```

时间字段值可能为空，不能直接作为筛选条件（会漏项）。正确做法：先宽松拉取，再把时间字段带到 `-f` 展示列，在返回数据中做区间计算。时间字段 variable 全平台统一（`customField13641` 预计开发开始、`customField13642` 预计开发结束、`customField11681` 预计提测、`customField13200` 预计上线），无需查询，直接使用：

```bash
ones fi -p <空间ID> -t REQUIREMENT \
  --assigned <misId> \
  -f "name,state,priority,customField13641,customField13642,customField13200,customField11681" \
  --json
```

拿到结果后，从 JSON 中筛选开发区间与目标时间范围有交集的工作项（开发进展），或对应时间字段落在目标范围内的工作项（上线/提测进展）。

> 详细 DSL 示例及策略参见 [DSL 筛选指南 - 模板 4 & 策略 4](./filter-query-dsl.md)。

---

## Case 11: 「查询有延期风险的工作项」

**User input content:**
```text
帮我看看有哪些工作项有延期风险
本迭代有没有开发延期的需求
当前有哪些工作项可能会影响上线
```

先宽松拉取，再按 `stateCategory` 在返回数据中分层判断：`TODO`（开发前）检查所有时间节点；`DOING`（开发中）跳过已无意义的开发开始时间；进入测试/上线阶段后只看提测和上线时间；`DONE` 直接跳过。具体状态名因空间而异，以语义判断为准，不要硬编码。

```bash
# 需求风险（按指派人或迭代）
ones fi -p <空间ID> -t REQUIREMENT \
  --assigned <misId> \
  -f "name,state,stateCategory,priority,customField13641,customField13642,customField11681,customField13200" \
  --json

# 任务风险（expectStart/expectClose 全平台统一）
ones fi -p <空间ID> -t DEVTASK \
  --assigned <misId> \
  -f "name,state,stateCategory,priority,expectStart,expectClose" \
  --json
```

`--json` 输出采用 `TREE_MODE`，顶层需求的 `children` 直接包含子任务，可一次定位"哪个需求下的哪个任务"异常。时间字段为空时跳过该维度的风险判断。

> 详细分层判断规则及 DSL 初筛示例参见 [DSL 筛选指南 - 模板 8](./filter-query-dsl.md)。

---

## Case 12: 「管理工作项的关联文档/资产」

**User input content:**
```text
帮我查一下需求 93798766 关联了哪些文档
给这个需求挂一个 PRD 文档
```

```bash
# 1. 查询当前资产列表
ones wa list -i 93798766
# 2. 添加 PRD 资产（type 可选: MRD / BRD / PRD / DESIGN_DRAFT / TD / TEST_DOCUMENT / TEST / MANUAL / OTHER）
ones wa add -i 93798766 --title "搜索优化PRD" --url "https://km.sankuai.com/collabpage/12345" --type PRD
# 3. 更新资产信息（资产 ID 来自步骤 1 或 2）
ones wa update -i 93798766 -a <资产ID> --title "搜索优化PRD-v2" --url "https://km.sankuai.com/collabpage/67890" --type PRD
# 4. 移除资产
ones wa remove -i 93798766 -a <资产ID>
```

> 资产类型对应关系：MRD、BRD、PRD、DESIGN_DRAFT(设计稿)、TD(技术文档)、TEST_DOCUMENT(测试方案)、TEST(测试报告)、MANUAL(操作手册)、OTHER(其他)

---

## Case 13: 「为工作项创建大象群 / 查询已关联群聊」

**User input content:**
```text
帮我给需求 93802049 拉一个大象群
查一下工作项 93802049 关联了哪些大象群
帮我创建群聊把需求相关人员加进去
```

```bash
# 1. 先查询是否已有关联群聊（create 命令会自动检查，也可手动查询）
ones wxg query -i 93802049 -t REQUIREMENT

# 2. 查看默认入群成员（可选，了解哪些字段的人员会被自动拉入）
ones wxg roles -i 93802049 -t REQUIREMENT

# 3. 创建大象群（自动从工作项默认字段查询成员；若已关联则直接展示已有群聊，不重复创建）
ones wxg create -i 93802049 -t REQUIREMENT

# 3b. 手动指定成员（覆盖自动查询结果）
ones wxg create -i 93802049 -t REQUIREMENT --users hequanchuan,jiangshaowei

# 3c. 指定群主和管理员
ones wxg create -i 93802049 -t REQUIREMENT --owner hequanchuan --admins hequanchuan
```

> **注意**：`create` 命令会自动执行前置检查（associateXMGroup → roles → members → 创建）。若工作项已关联群聊则直接展示，不会重复创建。工作项类型支持 `REQUIREMENT | DEVTASK | DEFECT | PRODUCT_DOCUMENT`。

---

## Case 14: 「查看工作项排期并设置排期时间」

**User input content:**
```text
帮我看下需求 93876903 的排期信息，把上线时间设到 4 月 15 号
```

```bash
# 1. 查询排期信息（含三个阶段的事项列表）
ones sq -p <空间ID> -i 93876903
# 2. 设置上线时间（ID 来自步骤 1 的排期）
ones stu -p <空间ID> -i 93876903 --release-time 2026-04-15
# 3. 验证更新结果
ones sq -p <空间ID> -i 93876903
```

---

## Case 15: 「为工作项新建排期事项并设置工作量」

**User input content:**
```text
帮我在需求 93876903 的开发阶段新建一个排期事项，预计 16 小时工作量
```

```bash
# 1. 查询排期获取当前事项（确认排期已存在）
ones sq -p <空间ID> -i 93876903 -s DEVELOPING
# 2. 新建开发阶段排期事项
ones sic -p <空间ID> -i 93876903 -s DEVELOPING --json
# 3. 更新事项的预计工作量和时间（事项 ID 来自步骤 2）
ones siu -p <空间ID> -i 93876903 --item-id <事项ID> --expect-time 16 --expect-start 2026-04-01 --expect-close 2026-04-10
```

> **注意**：排期事项分为**父事项（阶段容器）**和**子事项（工序）**。预计工作量（`--expect-time`）、预计开始/结束时间（`--expect-start` / `--expect-close`）应设置在子事项上，父事项的这些字段由系统自动汇总。排期工序的指派人不允许修改。

---

## Case 16: 「收到 ONES 链接，快速获取关键信息」

**User input content:**
```text
帮我看看这个链接是什么工作项
https://ones.sankuai.com/ones/product/46036/workItem/requirement/detail/93876903
```

```bash
# 1. 解析 URL，提取空间 ID、工作项 ID、类型
ones url-parse -u "https://ones.sankuai.com/ones/product/46036/workItem/requirement/detail/93876903"
# 输出：spaceId=46036, issueType=REQUIREMENT, issueId=93876903

# 2. 查工作项详情（ID 来自步骤 1）
ones workitem-detail -i 93876903 --table

# 3. 按需进一步操作（分支/提测/迭代，ID 来自步骤 1）
ones branch -p 46036 -i 93876903
ones st -p 46036 -i 93876903
```

> `url-parse` 支持所有 ONES V1（`ones/product/`）URL 格式，包括工作项、迭代、空间页面链接。
> ⚠️ **若 URL 为 V2 格式**（含 `app/ones/space/`），命令会直接中止并提示使用 `ones2` 命令（ee-mep-ones Skill），**不做字段解析**。

