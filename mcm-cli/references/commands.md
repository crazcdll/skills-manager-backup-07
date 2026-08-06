# MCM 命令行工具命令参考

## 目录

- [认证命令](#认证命令)
- [plan list - 计划列表](#plan-list---计划列表)
- [plan my - 我的计划](#plan-my---我的计划)
- [plan detail - 计划详情](#plan-detail---计划详情)
- [plan steps - 计划步骤](#plan-steps---计划步骤)
- [plan progress - 计划进展](#plan-progress---计划进展)
- [plan search - 搜索计划](#plan-search---搜索计划)
- [plan calendar - 变更日历](#plan-calendar---变更日历)
- [plan count - 计划统计](#plan-count---计划统计)
- [plan status - 状态列表](#plan-status---状态列表)
- [plan notice-preview - 周知详情](#plan-notice-preview---周知详情)
- [plan start - 启动计划](#plan-start---启动计划)
- [plan step-check - 步骤执行前检查](#plan-step-check---步骤执行前检查)
- [plan step-start - 开始步骤](#plan-step-start---开始步骤)
- [plan step-finish - 结束步骤](#plan-step-finish---结束步骤)
- [template list - 模板列表](#template-list---模板列表)
- [template detail - 模板详情](#template-detail---模板详情)
- [template preview - 模板预览](#template-preview---模板预览)
- [template history - 模板历史](#template-history---模板历史)
- [template used - 最近使用的模板](#template-used---最近使用的模板)
- [plan create - 创建计划草稿](#plan-create---创建计划草稿)
- [plan update - 更新计划草稿](#plan-update---更新计划草稿)
- [plan validate - 校验计划草稿](#plan-validate---校验计划草稿)
- [plan submit - 提交变更计划](#plan-submit---提交变更计划)
- [plan approve - 审核通过变更计划](#plan-approve---审核通过变更计划)
- [plan reject - 审核驳回变更计划](#plan-reject---审核驳回变更计划)
- [plan delete - 删除计划草稿](#plan-delete---删除计划草稿)
- [plan revoke - 撤销变更计划](#plan-revoke---撤销变更计划)
- [plan rebuild - 重建变更计划](#plan-rebuild---重建变更计划)
- [template create - 创建模板](#template-create---创建模板)
- [template update - 更新模板](#template-update---更新模板)
- [step update - 更新变更步骤](#step-update---更新变更步骤)
- [event list - 变更事件列表](#event-list---变更事件列表)
- [event detail - 变更事件模型详情](#event-detail---变更事件模型详情)
- [event get - 变更详情](#event-get---变更详情)
- [event accept - 通过变更审批](#event-accept---通过变更审批)
- [event reject - 驳回变更](#event-reject---驳回变更)
- [event skip-audit - 跳过变更审批](#event-skip-audit---跳过变更审批)
- [cloudtrail list - 追溯事件列表](#cloudtrail-list---追溯事件列表)
  - [user-org 快速追溯团队变更](#user-org---按团队组织查询变更事件)
- [cloudtrail detail - 追溯事件详情](#cloudtrail-detail---追溯事件详情)
- [user my - 当前用户信息](#user-my---当前用户信息)

---

## 认证命令

| 命令 | 说明 |
|---|---|
| `mcm login --mis <mis>` | CIBA 认证（推荐）：大象 App 确认授权，token 有效期 3 天，支持 refresh_token 自动续期 |
| `mcm login` | 交互式提示输入 MIS 号，然后走 CIBA 流程 |
| `mcm login --token <ssoid>` | 手动指定 ssoid（从浏览器 DevTools 复制） |
| `mcm logout` | 清除本地认证缓存 |
| `mcm whoami` | 查看当前认证状态（认证方式、用户信息、有效期剩余） |
| `mcm refresh` | 强制刷新（优先用 refresh_token，失败则从浏览器 Cookie fallback） |

### 认证机制说明

执行任何业务命令时，鉴权优先级依次为：

1. **本地缓存 token**（未过期）
2. **refresh_token 静默续期**（CIBA 模式下自动触发）
3. **浏览器 Cookie 自动读取**（fallback，需提前在 Chrome/Edge 中登录 https://mcm.mws.sankuai.com）
4. **以上均失败**：提示用户执行 `mcm login --mis <mis>`

配置文件存储在 `~/.mcm-cli/config.json`。


---

## plan list - 计划列表

查询变更计划列表。

```
mcm plan list [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-t, --type <查询类型>` | 查询类型（LAUNCHED/TODO/DONE/ORG/ALL） | ALL |
| `-n, --name <名称>` | 计划名称（模糊匹配） | - |
| `-c, --creator <MIS号>` | 创建人 MIS 号 | - |
| `--status <状态>` | 状态筛选，多个用逗号分隔（见[计划状态枚举](#计划状态枚举值)） | - |
| `--org <组织路径>` | 组织路径 ID 链路（如 "100046-150042-1573"） | - |
| `--risk <风险等级>` | 风险等级，多个用逗号分隔（见[风险等级枚举](#风险等级枚举值)） | - |
| `--env <环境>` | 环境，多个用逗号分隔（见[环境枚举](#环境枚举值)） | - |
| `--start <开始时间>` | 计划开始时间起（yyyy-MM-dd HH:mm:ss） | - |
| `--end <结束时间>` | 计划开始时间止（yyyy-MM-dd HH:mm:ss） | - |
| `--change-mode <变更方式>` | 变更方式（1=仅白屏变更，2=含黑屏变更） | - |
| `--scene <变更场景>` | 变更场景，多个用逗号分隔（见[变更场景枚举](#变更场景枚举值)） | - |
| `--change-type <变更类型>` | 变更类型，多个用逗号分隔（见[变更类型枚举](#变更类型枚举值)） | - |
| `--app-key <appKey>` | 变更服务 appKey | - |
| `--create-time-begin <时间>` | 创建时间起（yyyy-MM-dd HH:mm:ss） | - |
| `--create-time-end <时间>` | 创建时间止（yyyy-MM-dd HH:mm:ss） | - |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | json |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 计划ID |
| name | String | 计划名称 |
| changeMode | Integer | 变更方式（见[变更方式枚举](#变更方式枚举值)） |
| templateId | Integer | 模板ID |
| templateName | String | 模板名称 |
| status | String | 状态（字符串枚举值，如 RUNNING、SUCCEED，见[计划状态枚举](#计划状态枚举值)） |
| riskLevel | String | 风险等级（如 "高风险"、"低风险"） |
| env | List\<String\> | 环境列表 |
| changeType | String | 变更类型（常规变更、紧急变更） |
| scene | String | 变更场景（逗号分隔的多场景字符串） |
| sceneList | List\<String\> | 变更场景列表（同 scene，拆分后的数组形式） |
| tool | List\<String\> | 变更关联工具列表 |
| appKey | List\<String\> | 关联服务 appKey 列表 |
| application | List\<Object\> | 应用列表，每项含 name（应用名）、chName（中文名） |
| content | String | 变更内容描述 |
| domain | String | 变更域名（可为 null） |
| stepIndex | Integer | 当前步骤索引（从 1 开始） |
| totalStep | Integer | 全部步骤数量 |
| orgName | String | 归属部门名称 |
| orgPath | String | 归属部门路径 |
| effectOrgPath | String | 影响范围部门路径（可为 null） |
| effectOrgNamePath | String | 影响范围部门名称路径（可为 null） |
| createUser | String | 创建人 MIS 号 |
| cnCreateUser | String | 创建人中文名 |
| ccUsers | List\<String\> | 抄送人 MIS 号列表 |
| operatedUsers | List\<String\> | 已操作人 MIS 号列表（已审核 + 已完成步骤的人） |
| operatingUsers | List\<String\> | 当前待操作人 MIS 号列表（当前审核人 / 步骤操作人） |
| auditors | List\<String\> | 全部审核人 MIS 号列表 |
| commonEditor | List\<String\> | 协同处理人 MIS 号列表 |
| noticeGroups | List\<String\> | 周知大象群 ID 列表 |
| actualStartTime | Date | 实际开始时间 |
| actualEndTime | Date | 实际结束时间（进行中时为 null） |
| planStartTime | Date | 预计开始时间 |
| planEndTime | Date | 预计结束时间 |
| searchStartTime | Date | ES 检索开始时间（同 actualStartTime，用于索引分片） |
| searchEndTime | Date | ES 检索结束时间 |
| createTime | Date | 计划创建时间 |
| updateTime | Date | 计划最后更新时间 |

### 示例

```bash
# 查询进行中的计划
mcm plan list --status RUNNING -f json

# 按创建人和时间范围查询
mcm plan list -c zhangsan --start "2026-03-01 00:00:00" --end "2026-03-31 23:59:59" -s 50 -f json
```

---

## plan my - 我的计划

查看当前登录用户相关的变更计划，自动使用认证用户身份。

```
mcm plan my [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-t, --type <查询类型>` | 查询类型（见下表） | LAUNCHED |
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-n, --name <名称>` | 计划名称 | - |
| `--status <状态列表>` | 状态筛选（多个用逗号分隔，见[计划状态枚举](#计划状态枚举值)） | - |
| `--risk <风险等级列表>` | 风险等级（多个用逗号分隔，见[风险等级枚举](#风险等级枚举值)） | - |
| `--start <开始时间>` | 计划开始时间起 | - |
| `--end <结束时间>` | 计划开始时间止 | - |
| `-f, --format <格式>` | 输出格式 | json |

### 查询类型枚举值

| 值 | 含义 |
|---|---|
| LAUNCHED | 我发起的（默认） |
| TODO | 待我处理 |
| DONE | 我已处理 |
| ORG | 我团队的 |
| ALL | 全部 |

### 返回字段

同 [plan list 返回字段](#返回字段说明)

### 示例

```bash
# 查看团队本周计划
mcm plan my -t ORG --start "2026-03-09 00:00:00" --end "2026-03-15 23:59:59" -s 100 -f json

# 查看待我处理的计划
mcm plan my -t TODO -f json
```

---

## plan detail - 计划详情

查看指定计划的详细信息。

```
mcm plan detail <计划ID> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 计划ID | 计划的唯一标识 | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 计划ID |
| name | String | 计划名称 |
| orgPath | String | 归属部门路径 |
| creator | Object | 创建人信息，含 mis、name、orgId、orgName、orgPath、orgNamePath、avatarUrl |
| approveLevel | Integer | 当前审批节点级别（从 1 开始） |
| status | Integer | 状态数字码（见[计划状态枚举](#计划状态枚举值)） |
| changeMode | Integer | 变更方式（见[变更方式枚举](#变更方式枚举值)） |
| templateId | Integer | 模板ID |
| planBase | Object | 计划基本信息，含 env（环境列表）、changeType（变更类型）、riskLevel（风险等级）、scene（变更场景）、background（变更背景） |
| planContent | Object | 变更内容，含 appkey、description、effect、rollbackPlan、testReport、onesLink、domain、gitAddr、verify、checklist、sop、grayPlan、observationIndicators |
| planApproves | List\<Object\> | 审批人列表，每项含 user（审批人信息）、level（审批级别）、status（审批状态，见[审批状态枚举](#审批状态枚举值)）、remark、type（审批类型，见[审批类型枚举](#审批类型枚举值)）、operateTime |
| planNotice | Object | 周知信息，含 groups（群组列表）、content（周知内容）、handleGroup（处理群） |
| planSteps | List\<Object\> | 步骤列表，字段同 [plan steps 返回字段](#返回字段说明-2) |
| planStepChanges | List\<Object\> | 步骤变更详情，含 planId、stepId、env、tool、type、resource、appKey、operator、status（0=待执行 1=进行中 2=成功 3=失败）、changeDetails |
| onesIds | List\<Integer\> | 关联的 Ones 工作项ID列表 |
| planStartTime | Date | 预计开始时间 |
| planEndTime | Date | 预计结束时间 |
| createTime | Date | 创建时间 |
| updateTime | Date | 最后更新时间 |

---

## plan steps - 计划步骤

查看计划的步骤列表。

```
mcm plan steps <计划ID> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 计划ID | 计划的唯一标识 | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

返回数组，每个元素包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 步骤ID |
| seq | Integer | 步骤序号（内部排序用，可为 null） |
| index | Integer | 步骤展示序号（从 1 开始） |
| title | String | 步骤名称 |
| tool | String | 步骤关联工具名称（如 "Plus"、"Lion"、"Rds"，可为空） |
| stepType | String | 步骤类型（见[步骤类型枚举](#步骤类型枚举值)） |
| action | String | 步骤操作内容描述（HTML 格式） |
| status | Integer | 步骤状态数字码（见[步骤状态枚举](#步骤状态枚举值)） |
| allowedOperator | List\<String\> | 允许操作的人员 MIS 号列表 |
| operator | String | 实际操作人 MIS 号（步骤开始后填入） |
| inspector | String | 验收人 MIS 号 |
| autoFinish | Boolean | 是否自动完成（如 Plus 步骤发布完成后自动结束） |
| autoStart | Boolean | 是否自动开始 |
| forbiddenDeleteStep | Boolean | 是否禁止删除该步骤 |
| stepOperation | Object | 步骤内的操作项详情（工具相关数据，如 Plus 的发布项、Lion 的配置项等） |
| stepDependence | List\<Object\> | 步骤依赖关系（可为 null） |
| remark | String | 步骤备注（可为 null） |
| estimateStartTime | Date | 预计开始时间（可为 null） |
| estimateEndTime | Date | 预计结束时间（可为 null） |
| actualStartTime | Date | 实际开始时间（步骤开始后填入） |
| actualEndTime | Date | 实际结束时间（步骤完成后填入） |
| createTime | Date | 步骤创建时间 |
| updateTime | Date | 步骤最后更新时间 |

---

## plan progress - 计划进展

查看计划的进展流程，包括审批流程和操作记录。

```
mcm plan progress <计划ID> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 计划ID | 计划的唯一标识 | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

返回数组，每个阶段节点包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| name | String | 阶段名称（如 "提交人"、"1级审核人"、"变更步骤(共N步)"、"完成"） |
| status | String | 阶段状态枚举值（见[进展阶段状态枚举](#进展阶段状态枚举值)，可为 null） |
| statusCn | String | 阶段状态中文名称（如 "已提交"、"已通过"、"进行中"） |
| description | String | 阶段描述（可为 null） |
| operateTime | Date | 阶段操作时间（可为 null） |
| approveType | String | 审批类型（见[审批类型枚举](#审批类型枚举值)，仅审核阶段有值，其他为 null） |
| userOperations | List\<Object\> | 各用户的操作记录，每项含：operator（操作人对象，含 mis、uid、name、orgNamePath）、status（操作状态枚举值，见[进展阶段状态枚举](#进展阶段状态枚举值)，可为 null）、comment（备注内容，撤销/驳回理由）、operateTime（操作时间） |

### 如何提取撤销/驳回理由

遍历返回数组中每个阶段的 `userOperations` 数组，查找 `comment` 字段。终止计划的撤销理由格式为 `撤销理由:xxx`，驳回理由格式为 `驳回理由:xxx`。

---

## plan search - 搜索计划

通过开放接口搜索变更计划，需指定用户。

```
mcm plan search -u <MIS号> [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-u, --user <MIS号>` | 用户 MIS 号（**必填**） | - |
| `-t, --type <查询类型>` | 查询类型（见下表） | ALL |
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-f, --format <格式>` | 输出格式 | json |

### 查询类型枚举值

| 值 | 含义 |
|---|---|
| ALL | 全部 |
| CREATED | 该用户创建的 |
| OPERATING | 该用户操作中的 |
| CC | 抄送给该用户的 |

### 返回字段

同 [plan list 返回字段](#返回字段说明)

---

## plan calendar - 变更日历

按组织和时间范围查询变更日历，三个必填参数。

```
mcm plan calendar --org <组织路径> --start <开始时间> --end <结束时间> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `--org <组织路径>` | 组织路径 ID 链路（如 "100046-150042-1573"） | 是 | - |
| `--start <开始时间>` | 开始时间 | 是 | - |
| `--end <结束时间>` | 结束时间 | 是 | - |
| `--status <状态列表>` | 状态列表（多个用逗号分隔，见[计划状态枚举](#计划状态枚举值)） | 否 | - |
| `--risk <风险等级列表>` | 风险等级列表（多个用逗号分隔，见[风险等级枚举](#风险等级枚举值)） | 否 | - |
| `--change-mode <变更方式>` | 变更方式（1=仅白屏变更，2=含黑屏变更） | 否 | - |
| `-p, --page <页码>` | 页码 | 否 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 否 | 10 |
| `-f, --format <格式>` | 输出格式 | 否 | json |

### 返回字段

同 [plan list 返回字段](#返回字段说明)

---

## plan count - 计划统计

查看当前用户的计划数量统计。

```
mcm plan count -f json
```

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| launched | Long | 我发起的数量 |
| todo | Long | 待我处理的数量 |
| done | Long | 我已处理的数量 |
| org | Long | 我团队发起的数量 |
| all | Long | 全部变更数量 |

---

## plan status - 状态列表

查看所有可用的计划状态值及描述。

```
mcm plan status -f json
```

### 返回字段说明

返回数组，每个元素包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| code | Integer | 状态数字码 |
| status | String | 状态枚举值（如 AUDITING、REJECTED） |
| statusCn | String | 状态中文名称 |

---

## plan notice-preview - 周知详情

查询变更计划的周知详情，包含周知群列表、处理群信息、抄送人列表及周知预览内容。

```
mcm plan notice-preview <计划ID> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 计划ID | 计划的唯一标识 | 是 |
| `-f, --format <格式>` | 输出格式（json/table/md） | 否 |

### 返回字段说明（`PlanNoticePreviewVO`）

| 字段名 | 类型 | 说明 |
|---|---|---|
| planId | Integer | 变更计划 ID |
| noticeGroup | List\<NoticeGroupVO\> | 周知群列表 |
| handleGroup | NoticeGroupVO | 变更处理群信息 |
| isInHandleGroup | Boolean | 当前用户是否在处理群中 |
| content | String | 周知消息原始内容（模板变量替换前） |
| previewContent | String | 周知消息预览内容（模板变量替换后的渲染结果） |
| cc | List\<UserDTO\> | 抄送人列表 |
| nginxCluster | String | Nginx 集群标识 |
| handleGroupStatus | Integer | 处理群状态：`0`=未建群 / `1`=已删除 / `2`=群存在 |

#### 嵌套对象：`NoticeGroupVO`

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | String | 大象群 ID |
| name | String | 群名称 |
| size | Integer | 群成员数量 |

#### 嵌套对象：`UserDTO`

| 字段名 | 类型 | 说明 |
|---|---|---|
| mis | String | 用户 MIS 号 |
| uid | String | 员工 ID |
| name | String | 姓名 |
| orgId | String | 部门 ID |
| orgName | String | 部门名称 |
| orgPath | String | 组织路径（ID路径） |
| orgNamePath | String | 组织名称路径 |
| avatarUrl | String | 头像 URL |
| jobStatusId | Integer | 在职状态：`15`=在职 / `16`=离职 |
| isMaoyan | Boolean | 是否为猫眼员工 |

### 示例

```bash
# 查询计划 981629 的周知详情
mcm plan notice-preview 981629 -f json

# 以表格形式查看
mcm plan notice-preview 981629 -f table
```

---

## plan start - 启动计划

启动变更计划，使计划从「待变更(WAIT_RUNNING)」进入「变更中(RUNNING)」状态。

```
mcm plan start <planId> [-y]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| planId | 计划 ID | 是 |
| `-y, --yes` | 跳过交互式确认 | 否 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 示例

```bash
mcm plan start 12345 -y
```

---

## plan step-check - 步骤执行前检查

在开始某个步骤之前，先调用此命令检查是否满足执行条件（例如依赖步骤是否已完成、配置是否合规等）。

```
mcm plan step-check <stepId>
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| stepId | 步骤 ID | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

返回数组，每个检查项包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| result | Boolean | 该检查项是否通过 |
| level | String | 检查等级：`ERROR`（阻塞，必须处理）/ `WARNING`（警告，可确认继续） |
| msg | String | 检查结果描述 |

**使用规则**：
- 返回空数组 → 检查全部通过，可直接调用 `plan step-start`
- 存在 `level: "ERROR"` 项 → **必须先解决**，不能强行开始步骤
- 仅存在 `level: "WARNING"` 项 → 告知用户风险，用户确认后可继续

### 示例

```bash
mcm plan step-check 67890 -f json
```

---

## plan step-start - 开始步骤

将步骤状态从「待执行(WAIT_EXECUTING)」推进到「执行中(EXECUTING)」。执行前请先调用 `plan step-check` 确认无 ERROR 级别阻塞项。

```
mcm plan step-start <stepId> [-y]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| stepId | 步骤 ID | 是 |
| `-y, --yes` | 跳过交互式确认 | 否 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 示例

```bash
mcm plan step-start 67890 -y
```

---

## plan step-finish - 结束步骤

将步骤从「执行中(EXECUTING)」标记为成功或失败。

```
mcm plan step-finish <stepId> --code <3|4> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| stepId | 步骤 ID | 是 | - |
| `--code <code>` | 执行结果码：`3`=成功(EXECUTE_SUCCEED)，`4`=失败(EXECUTE_FAILED) | 是 | - |
| `--comment <comment>` | 执行备注（摘要或失败原因） | 否 | - |
| `--notice` | 发送步骤周知消息（默认不周知） | 否 | false |
| `--notice-content <content>` | 周知消息内容（仅 `--notice` 时有效） | 否 | - |
| `--co-work <coWork>` | 协作方标识，写入备注末尾 | 否 | `mcm-ai` |
| `--data <json>` | 完整请求体 JSON（覆盖其他参数） | 否 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |
| `-f, --format <格式>` | 输出格式 | 否 | - |

### 请求体结构（`--data` 用法）

```json
{
  "code": 3,
  "comment": "执行摘要",
  "coWork": "mcm-ai",
  "stepNotice": {
    "isNotice": false,
    "content": ""
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | Integer | `3`=EXECUTE_SUCCEED（成功），`4`=EXECUTE_FAILED（失败） |
| `comment` | String | 执行备注，后端会自动追加 ` --Co-Worked-By: <coWork>` |
| `coWork` | String | 协作方标识（如 `mcm-ai`），可为空 |
| `stepNotice.isNotice` | Boolean | 是否发送周知，**默认 false** |
| `stepNotice.content` | String | 周知内容（`isNotice=true` 时填写） |

### 示例

```bash
# 标记步骤成功，附带摘要
mcm plan step-finish 67890 --code 3 --comment "部署完成，服务正常" -y

# 标记步骤失败，附带原因
mcm plan step-finish 67890 --code 4 --comment "部署超时，回滚中" -y

# 使用 --data 传入完整结构
mcm plan step-finish 67890 --data '{"code":3,"comment":"执行完成","coWork":"mcm-ai","stepNotice":{"isNotice":false}}' -y
```

---

## template list - 模板列表

查询变更模板列表。

```
mcm template list [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-n, --name <名称>` | 模板名称（模糊匹配） | - |
| `--org <组织路径>` | 组织路径 ID 链路（如 "100046-150042-1573"） | - |
| `--admin <管理员>` | 模板管理员 MIS 号 | - |
| `--type <模板类型>` | 模板类型（见[模板类型枚举](#模板类型枚举值)） | - |
| `-f, --format <格式>` | 输出格式 | json |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 模板ID |
| name | String | 模板名称 |
| orgPath | String | 归属部门路径 |
| orgName | String | 归属部门名称 |
| type | Integer | 模板类型（见[模板类型枚举](#模板类型枚举值)） |
| changeMode | Integer | 变更方式（见[变更方式枚举](#变更方式枚举值)） |
| description | String | 模板描述 |
| admins | List\<Object\> | 管理员列表，每项含 mis、name |
| createTime | Date | 创建时间 |
| updateTime | Date | 最后更新时间 |

---

## template detail - 模板详情

查看模板的详细信息，包括步骤模板。

```
mcm template detail <模板ID> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 模板ID | 模板的唯一标识 | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 模板ID |
| name | String | 模板名称 |
| orgPath | String | 归属部门路径 |
| orgName | String | 归属部门名称 |
| type | Integer | 模板类型（见[模板类型枚举](#模板类型枚举值)） |
| changeMode | Integer | 变更方式（见[变更方式枚举](#变更方式枚举值)） |
| description | String | 模板描述 |
| advanceSettings | Object | 高级设置（包含审批逾期提醒、周知策略等配置） |
| admins | List\<String\> | 管理员 MIS 号列表 |
| baseFields | List\<Object\> | 基础信息字段配置列表 |
| approveFields | List\<Object\> | 审核字段配置列表 |
| noticeFields | List\<Object\> | 周知字段配置列表 |
| contentFields | List\<Object\> | 变更内容字段配置列表 |
| steps | List\<Object\> | 步骤模板列表，每项含 id、title、tool、stepType（见[步骤类型枚举](#步骤类型枚举值)）、action、allowedOperator、forbiddenDeleteStep、stepOperation |
| templateContent | Object | 变更内容模板 |
| createTime | Date | 创建时间 |
| updateTime | Date | 最后更新时间 |

---

## template preview - 模板预览

预览变更模板详情，支持传入 ONES 工作项或 Pipeline Job 上下文参数，用于动态步骤填充。

```
mcm template preview <模板ID> [--ones-app-id <onesAppId>] [--ones-issue-id <onesIssueId>] [--pipeline-job-id <pipelineJobId>] [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| 模板ID | 模板的唯一标识 | 是 |
| `--ones-app-id <onesAppId>` | ONES 应用 ID，用于动态步骤填充 | 否 |
| `--ones-issue-id <onesIssueId>` | ONES 工作项 ID，用于动态步骤填充 | 否 |
| `--pipeline-job-id <pipelineJobId>` | Pipeline Job ID，用于动态步骤填充 | 否 |
| `-f, --format <格式>` | 输出格式（json/table/md） | 否 |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 模板 ID |
| name | String | 模板名称 |
| orgName | String | 所属组织名称 |
| type | Integer | 模板类型 |
| description | String | 模板描述 |
| createTime | Date | 创建时间 |
| updateTime | Date | 更新时间 |
| admins | List\<UserDTO\> | 管理员列表 |
| baseFields | List\<FieldVO\> | 基础字段列表（变更方式、变更环境、风险等级等） |
| approveFields | List\<FieldVO\> | 审核字段列表（一/二/三级审核人） |
| noticeFields | List\<FieldVO\> | 通知字段列表（周知群、处理群、抄送人等） |
| contentFields | List\<FieldVO\> | 内容字段列表（变更描述、影响、回滚方案等） |
| steps | List\<StepVO\> | 步骤模板列表 |

#### 嵌套对象：`StepVO`

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 步骤 ID |
| title | String | 步骤名称 |
| stepType | String | 步骤类型（PLUS=Plus 发布步骤，NORMAL=普通步骤） |
| tool | String | 使用的工具（如 Plus） |
| action | String | 步骤操作描述 |
| allowedOperator | List\<String\> | 允许操作的人员（SPONSOR=发起人） |
| stepOperation | Object | 步骤操作配置（灰度分组等） |

### 示例

```bash
# 基本预览
mcm template preview 5681

# 传入 ONES 上下文参数（用于动态步骤填充）
mcm template preview 5681 --ones-app-id 140802 --ones-issue-id 95039085

# 传入 Pipeline Job 参数
mcm template preview 5681 --pipeline-job-id 123456

# 以表格形式查看
mcm template preview 5681 --ones-app-id 140802 --ones-issue-id 95039085 -f table

# 获取完整 JSON 数据
mcm template preview 5681 --ones-app-id 140802 --ones-issue-id 95039085 -f json
```

---

## template history - 模板历史

查看模板的历史版本记录。

```
mcm template history <模板ID> [-p 页码] [-s 每页条数] [-f json]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| 模板ID | 模板的唯一标识（**必填**） | - |
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-f, --format <格式>` | 输出格式 | json |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 历史记录ID |
| operator | String | 操作人 MIS 号 |
| operationType | String | 操作类型（CREATE=创建，UPDATE=更新） |
| createTime | Date | 操作时间 |
| remark | String | 备注说明 |

---

## template used - 最近使用的模板

查看指定用户最近使用的模板。

```
mcm template used -u <MIS号> [-f json]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `-u, --user <MIS号>` | 用户 MIS 号 | 是 |
| `-f, --format <格式>` | 输出格式 | 否 |

### 返回字段说明

返回数组，每个元素包含：

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 模板ID |
| name | String | 模板名称 |
| orgPath | String | 归属部门路径 |
| orgName | String | 归属部门名称 |
| type | Integer | 模板类型（见[模板类型枚举](#模板类型枚举值)） |

---

## plan create - 创建计划草稿

创建变更计划草稿，计划默认为**规划中**状态，发起人从当前登录 SSO 中自动获取。

```
mcm plan create --data <完整JSON> [-y]
```

> ⚠️ **注意**：`plan create` 现在**仅支持 `--data` 模式**，`--data` 为必填参数。

**创建计划前校验**（推荐）：
- **创建计划前可先调用 `mcm plan validate` 校验参数**
- 校验通过后再执行 `mcm plan create` 创建计划
- 如果校验失败，根据返回的错误信息修改参数后重新校验，直到通过后再创建

### 参数

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `--data <json>` | 完整请求体 JSON 字符串（见下方结构说明） | 是 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |
| `-f, --format <格式>` | 输出格式 | 否 | json |

### 请求体结构（`--data` 必填）
使用 `--data` 参数创建计划时，JSON 请求体**必须包含**以下字段：
| 字段路径 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `name` | String | 是 | 计划名称（最多100字符） |
| `templateId` | Number | 是 | 模板ID |
| `baseFields` | Array | 是 | 基础信息字段数组，**必须包含以下5个identify**： |
| ├─ `env` | String | 是 | 环境：`prod`/`staging`/`test`/`dev` |
| ├─ `riskLevel` | String | 是 | 风险等级：`低风险`/`高风险` |
| ├─ `changeType` | String | 是 | 变更类型：`常规变更`/`紧急变更` |
| ├─ `scene` | String | 是 | 变更场景：`代码发布`/`配置变更`/`数据变更`等 |
| └─ `period` | String | 是 | 变更时段：`yyyy-MM-dd HH:mm:ss,yyyy-MM-dd HH:mm:ss` |
| `approveFields` | Array | 是 | 审批人字段数组，**必须包含**： |
| └─ `firstAuditor` | String | 是 | 一级审批人MIS，多个用逗号分隔 |
| `noticeFields` | Array | 是 | 周知字段数组，**必须包含以下4个identify**： |
| ├─ `noticeObject` | String | 是 | 周知群ID，多个用逗号分隔 |
| ├─ `noticeContent` | String | 是 | 变更内容周知 |
| ├─ `cc` | String | 是 | 抄送人MIS（可为空字符串 `""`） |
| └─ `handleGroup` | String | 是 | 处理群策略：`2`=按计划建群，`1`=不建群 |
| `contentFields` | Array | 是 | 变更内容字段数组，**必须包含**： |
| └─ `description` | String | 是 | 变更描述，HTML格式如 `<p>描述内容</p>` |
| `commonEditor` | Object | 否 | 协同处理人配置（可选）： |
| ├─ `isAllowCommonEdit` | Boolean | 否 | 是否允许协同编辑，默认 `true` |
| └─ `editor` | Array | 否 | 协同处理人数组，每项为 `{ "mis": "用户MIS号" }` 格式，可为空 |
| `steps` | Array | 是 | 步骤数组，**至少包含一个步骤**，详见下方示例 |

> ⚠️ **常见错误**：缺少 `period`、`cc`、`handleGroup` 或 `steps` 会导致创建失败。即使某些字段无实际值，也需传入空字符串或空数组占位。

`--data` 直接传递完整 JSON 请求体，contentFields中支持的identify类型较多，可按需传递，JSON结构示例如下：

```json
{
  "name": "应用发布-2026-03-17",
  "templateId": 123,
  "baseFields": [
    { "identify": "env",        "value": "prod" },
    { "identify": "riskLevel",  "value": "低风险" },
    { "identify": "changeType", "value": "常规变更" },
    { "identify": "scene",      "value": "代码发布" },
    { "identify": "period",     "value": "2026-03-17 22:00:00,2026-03-17 23:00:00" }
  ],
  "approveFields": [
    { "identify": "firstAuditor",  "value": "zhangsan,lisi" },
    { "identify": "secondAuditor", "value": "lisi" },
    { "identify": "thirdAuditor",  "value": "wangwu" }
  ],
  "noticeFields": [
    { "identify": "noticeObject",  "value": "64011214985" },
    { "identify": "noticeContent", "value": "测试变更内容周知" },
    { "identify": "cc",            "value": "qinwei05" },
    { "identify": "handleGroup",   "value": "2" }
  ],
  "contentFields": [
    { "identify": "description",   "value": "<p>变更描述内容</p>" },
    { "identify": "effect",        "value": "{\"hasEffect\":false,\"effect\":\"<p>变更影响说明</p>\",\"effectScope\":[]}" },
    { "identify": "testReport",    "value": "{\"radioValue\":true,\"textValue\":\"<p>测试结论：通过</p>\"}" },
    { "identify": "rollbackPlan",  "value": "{\"radioValue\":true,\"textValue\":\"<p>回滚方案说明</p>\"}" },
    { "identify": "grayPlan",      "value": "{\"radioValue\":true,\"textValue\":\"<p>灰度方案说明</p>\"}" }
  ],
  "commonEditor": {
    "isAllowCommonEdit": true,
    "editor": [
      { "mis": "zhangsan" },
      { "mis": "lisi" }
    ]
  },
  "steps": [
    {
      "title": "步骤标题",
      "tool": "Avatar",
      "action": "变更说明",
      "stepType": "NORMAL",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": []
      }
    }
  ]
}
```

**`steps` 字段说明：**

步骤参数详见 [plan-create-api-schema.md](plan-create-api-schema.md#steps) 文档。

**`contentFields` 字段说明：**

当前 `plan create` 命令在 `--data` 模式下，现支持以下 identify：

| identify | value 格式 | 说明 |
|---|---|---|
| `description` | HTML 字符串 | 变更描述，如 `"<p>变更描述内容</p>"` |
| `effect` | **JSON 字符串** | 变更影响，格式：`{"hasEffect":false,"effect":"<p>影响说明</p>","effectScope":[]}`。`effectScope` 为影响的部门 OrgID 列表 |
| `testReport` | **JSON 字符串** | 测试结果，格式：`{"radioValue":true,"textValue":"<p>测试结论</p>"}` |
| `rollbackPlan` | **JSON 字符串** | 回滚方案，格式：`{"radioValue":true,"textValue":"<p>回滚方案</p>"}` |
| `grayPlan` | **JSON 字符串** | 灰度方案，格式：`{"radioValue":true,"textValue":"<p>灰度方案</p>"}` |
| `background` | HTML 字符串 | 变更背景说明 |
| `onesLink` | String | Ones需求链接，如 `https://ones.sankuai.com/xxx` |
| `onesIssue` | String | Ones工作项ID，如 `93823019` |
| `domain` | String | 变更域名，如 `mcm.mws.sankuai.com` |
| `gitAddr` | String | 代码仓库地址，如 `ssh://git@git.sankuai.com/xxx/xxx.git` |
| `verify` | HTML 字符串 | 发布验证步骤说明 |
| `sop` | String | 操作SOP文档链接或说明 |
| `checkList` | **JSON 字符串** | 通用自检项，格式：`[{"checked":true,"label":"检查项1"}]` |
| `checkListAfterChange` | **JSON 字符串** | 变更后检查项，格式同 `checkList` |
| `changeServiceDetail` | **JSON 字符串** | 变更服务详情，服务列表配置 |
| `nginxCluster` | String | Nginx集群名称，多个用逗号分隔 |
| `observationIndicators` | String | 观测指标配置 |
| `alarmMonitor` | **JSON 字符串** | 告警监控配置，格式：`{"type":"AUTO_BY_PLAN","levels":["P0","P1"],"enableAppKeyAlarm":true}` |

**注意**：`effect`、`testReport`、`rollbackPlan`、`grayPlan`、`alarmMonitor`、`checkList`、`checkListAfterChange`、`changeServiceDetail` 的 value 必须是 JSON 字符串（需序列化后传递），而非普通文本。

**`noticeFields` 字段说明：**

| identify | value 格式 | 说明 |
|---|---|---|
| `noticeObject` | String | 周知群 ID，多个用逗号分隔 |
| `noticeContent` | String | 变更内容说明 |
| `cc` | String | 抄送人 MIS，多个用逗号分隔 |
| `handleGroup` | String | 处理群策略：`"2"`=按计划建群，`"1"`=不建群 |

### 返回字段说明

返回创建成功的完整计划详情（同 [plan detail 返回字段](#返回字段说明-1)），关键字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 创建的计划 ID |
| name | String | 计划名称 |
| status | Integer | 计划状态（创建后为 9=规划中） |
| templateId | Integer | 所用模板 ID |

### 示例

```bash
# 使用 --data 传入完整 JSON 请求体
mcm plan create --data '{"name":"应用发布-2026-03-17","templateId":123,"baseFields":[{"identify":"env","value":"prod"},{"identify":"riskLevel","value":"低风险"},{"identify":"changeType","value":"常规变更"},{"identify":"scene","value":"代码发布"},{"identify":"period","value":"2026-03-17 22:00:00,2026-03-17 23:00:00"}],"approveFields":[{"identify":"firstAuditor","value":"zhangsan"}],"noticeFields":[{"identify":"noticeContent","value":"发布说明"}],"contentFields":[{"identify":"description","value":"变更描述"}]}' -y

# 使用 --data 传入包含协同处理人的完整 JSON 请求体
mcm plan create --data '{"name":"应用发布-2026-03-17","templateId":123,"baseFields":[{"identify":"env","value":"prod"},{"identify":"riskLevel","value":"低风险"},{"identify":"changeType","value":"常规变更"},{"identify":"scene","value":"代码发布"},{"identify":"period","value":"2026-03-17 22:00:00,2026-03-17 23:00:00"}],"approveFields":[{"identify":"firstAuditor","value":"zhangsan"}],"noticeFields":[{"identify":"noticeContent","value":"发布说明"}],"contentFields":[{"identify":"description","value":"变更描述"}],"commonEditor":{"isAllowCommonEdit":true,"editor":[{"mis":"zhangsan"},{"mis":"lisi"}]}}' -y
```

> 📝 **协同处理人说明**：
> - `commonEditor` 字段可选，用于设置可以协同编辑该计划的人员
> - `isAllowCommonEdit` 默认为 `true`，允许协同处理人修改计划内容
> - `editor` 是一个数组，每个元素为 `{ "mis": "用户MIS号" }` 格式
> - 如果不需要设置协同处理人，可以省略 `commonEditor` 字段或传入空对象 `{}`

---

## plan update - 更新计划草稿

更新已存在的变更计划草稿，planId 必填，其余字段均可选。支持更新步骤配置（`--steps` 或 `--data` 模式下）。

```
mcm plan update -p <计划ID> [选项]
```

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `-p, --plan-id <id>` | 计划 ID | 是 | - |
| `-n, --name <名称>` | 计划名称（最多 100 字符） | 否 | - |
| `--env <env>` | 变更环境（见[环境枚举](#环境枚举值)） | 否 | - |
| `--risk <risk>` | 风险等级（见[风险等级枚举](#风险等级枚举值)） | 否 | - |
| `--type <type>` | 变更类型（见[变更类型枚举](#变更类型枚举值)） | 否 | - |
| `--scene <scene>` | 变更场景，多个用逗号分隔（见[变更场景枚举](#变更场景枚举值)） | 否 | - |
| `--change-mode <mode>` | 变更方式（`仅白屏变更` \| `含黑屏变更`） | 否 | - |
| `--start <时间>` | 计划开始时间（yyyy-MM-dd HH:mm:ss），须与 `--end` 同时提供 | 否 | - |
| `--end <时间>` | 计划结束时间（yyyy-MM-dd HH:mm:ss），须与 `--start` 同时提供 | 否 | - |
| `--first-auditor <mis>` | 一级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--second-auditor <mis>` | 二级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--third-auditor <mis>` | 三级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--notice-group <groupId>` | 周知群 ID，多个用逗号分隔 | 否 | - |
| `--notice-content <content>` | 变更内容周知 | 否 | - |
| `--cc <mis>` | 抄送人 MIS，多个用逗号分隔 | 否 | - |
| `--common-editor <mis>` | 协同处理人 MIS，多个用逗号分隔；`isAllowCommonEdit` 默认为 `true` | 否 | - |
| `--description <desc>` | 变更描述（支持 HTML） | 否 | - |
| `--test-report <json>` | 测试结果，**JSON 字符串**格式：`{"radioValue":true,"textValue":"<p>测试结论</p>"}` | 否 | - |
| `--effect <effect>` | 变更影响，**JSON 字符串**格式：`{"hasEffect":false,"effect":"<p>影响说明</p>","effectScope":[]}` | 否 | - |
| `--rollback <plan>` | 回滚方案，**JSON 字符串**格式：`{"radioValue":true,"textValue":"<p>回滚方案说明</p>"}` | 否 | - |
| `--gray-plan <json>` | 灰度方案，**JSON 字符串**格式：`{"radioValue":true,"textValue":"<p>灰度方案说明</p>"}` | 否 | - |
| `--background <text>` | 变更背景（纯文本） | 否 | - |
| `--verify <html>` | 发布验证步骤（支持 HTML） | 否 | - |
| `--observation-indicators <html>` | 观测指标（支持 HTML） | 否 | - |
| `--check-list-after-change <html>` | 变更后检查项（支持 HTML） | 否 | - |
| `--domain <urls>` | 变更域名，多个用逗号分隔 | 否 | - |
| `--git-addr <urls>` | 代码地址 PR 链接，多个用逗号分隔 | 否 | - |
| `--appkey <keys>` | 变更服务 AppKey，多个用逗号分隔 | 否 | - |
| `--sop <urls>` | 操作 SOP 链接，多个用逗号分隔 | 否 | - |
| `--ones-issue <ids>` | 关联 Ones 工作项 ID，多个用逗号分隔 | 否 | - |
| `--checklist <json>` | 通用自检项，JSON 字符串 | 否 | - |
| `--alarm-monitor <json>` | 告警监控配置，JSON 字符串 | 否 | - |
| `--steps <json>` | 步骤列表 JSON 字符串（见[步骤参数文档](plan-create-api-schema.md#steps)） | 否 | - |
| `--data <json>` | 完整请求体 JSON 字符串（覆盖其他参数） | 否 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |
| `-f, --format <format>` | 输出格式：`json`（默认）、`table`、`md` | 否 | json |

### 请求体结构（`--data` 用法）

> ⚠️ **CLI 限制**：即使使用 `--data` 传入完整 JSON，`-p <计划ID>` 参数仍然**必须显式提供**。

与 `plan create` 结构相同。`--plan-id` 参数必填（会自动注入到请求体）。后端支持部分字段更新，未传递的字段将保留原有数据：

```json
{
  "name": "更新后的计划名称",
  "baseFields": [
    { "identify": "riskLevel", "value": "高风险" }
  ],
  "commonEditor": {
    "isAllowCommonEdit": true,
    "editor": [
      { "mis": "zhangsan" },
      { "mis": "lisi" }
    ]
  },
  "steps": [
    {
      "title": "更新后的步骤",
      "tool": "Plus",
      "stepType": "PLUS",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": { "items": [] }
    }
  ]
}
```

### 示例

```bash
# 更新计划时间
mcm plan update -p 456 --start "2026-03-17 22:00:00" --end "2026-03-17 23:00:00" -y

# 更新风险等级和审批人
mcm plan update -p 456 --risk 高风险 --first-auditor zhangsan -y

# 更新协同处理人
mcm plan update -p 456 --common-editor "zhangsan,lisi" -y

# 更新变更方式
mcm plan update -p 456 --change-mode "含黑屏变更" -y

# 更新 SOP 链接
mcm plan update -p 456 --sop "https://km.sankuai.com/collabpage/xxxxxxxx" -y

# 更新变更服务 AppKey 和代码地址
mcm plan update -p 456 --appkey "com.sankuai.xxx" --git-addr "https://dev.sankuai.com/code/..." -y

# 更新灰度方案
mcm plan update -p 456 --gray-plan '{"radioValue":true,"textValue":"<p>基于Plus分组灰度发布</p>"}' -y

# 更新测试结果
mcm plan update -p 456 --test-report '{"radioValue":true,"textValue":"<p>【测试结论】通过</p>"}' -y

# 更新变更背景（纯文本）
mcm plan update -p 456 --background "本次变更用于修复线上 xxx 问题" -y

# 更新发布验证步骤
mcm plan update -p 456 --verify "<p>1. 验证接口返回正常</p><p>2. 检查监控无异常</p>" -y

# 更新观测指标
mcm plan update -p 456 --observation-indicators "<p>QPS、成功率、TP99</p>" -y

# 更新关联 Ones 工作项
mcm plan update -p 456 --ones-issue "abc123" -y

# 使用 --data 更新步骤
mcm plan update -p 456 --data '{"steps":[{"title":"新步骤","tool":"Plus","stepType":"PLUS","allowedOperator":["SPONSOR"],"stepOperation":{"items":[]}}]}' -y

# 使用 --data 更新协同处理人配置
mcm plan update -p 456 --data '{"commonEditor":{"isAllowCommonEdit":true,"editor":[{"mis":"zhangsan"},{"mis":"lisi"}]}}' -y
```

---

## plan validate - 校验计划草稿

校验变更计划草稿是否符合要求，不会创建计划。

```
mcm plan validate --data <完整JSON>
```

> ⚠️ **注意**：`plan validate` 现在**仅支持 `--data` 模式**，`--data` 为必填参数。

### 参数

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `--data <json>` | 完整请求体 JSON 字符串（见下方结构说明） | 是 | - |
| `-f, --format <格式>` | 输出格式 | 否 | json |

### 请求体结构（`--data` 必填）

与 `plan create` 相同，参考上方 `plan create` 章节的请求体结构说明。

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| passed / success / valid | Boolean | 是否通过校验 |
| message | String | 失败原因（如有） |
| errors | Array | 错误详情数组（如有） |

### 示例

```bash
# 使用 --data 校验完整请求体
mcm plan validate --data '{"name":"测试计划","templateId":123,"baseFields":[{"identify":"env","value":"prod"},{"identify":"riskLevel","value":"低风险"},{"identify":"changeType","value":"常规变更"},{"identify":"scene","value":"代码发布"},{"identify":"period","value":"2026-03-17 22:00:00,2026-03-17 23:00:00"}],"approveFields":[{"identify":"firstAuditor","value":"zhangsan"}],"noticeFields":[{"identify":"noticeContent","value":"发布说明"}],"contentFields":[{"identify":"description","value":"变更描述"}]}'
```

---

## plan submit - 提交变更计划

将变更计划从「规划中(PLANNING)」状态提交，进入「待审核(AUDITING)」流程。

```
mcm plan submit <id> [-y]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| id | 计划 ID | 是 |
| `-y, --yes` | 跳过交互式确认 | 否 |
| `-f, --format <格式>` | 输出格式（json/table/md） | 否 |

### 说明

- 计划必须处于**规划中(PLANNING)**状态才能提交，否则接口会返回错误
- 提交后计划状态变为**待审核(AUDITING)**，进入审批流程
- 提交前建议先用 `mcm plan validate` 校验计划草稿，确认无误后再提交

### 示例

```bash
# 提交计划（带确认提示）
mcm plan submit 12345

# 跳过确认直接提交
mcm plan submit 12345 -y

# 以 JSON 格式输出结果
mcm plan submit 12345 -y -f json
```

---

## plan approve - 审核通过变更计划

审核通过变更计划，将计划推进到下一审核阶段或进入已批准状态。

```
mcm plan approve <id> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| id | 计划 ID | 是 |
| `--creator <mis>` | 操作人 MIS 号（服务间调用时必填，MIS 用户登录时可不填） | 否 |
| `--comment <评论>` | 审核评论 | 否 |
| `--approve-level <层级>` | 审核层级 | **是** |
| `-y, --yes` | 跳过交互式确认 | 否 |
| `-f, --format <格式>` | 输出格式（json/table/md） | 否 |

### 示例

```bash
mcm plan approve 12345 --approve-level 1 -y
mcm plan approve 12345 --approve-level 1 --comment "LGTM" -y
mcm plan approve 12345 --approve-level 1 --creator zhangsan -y
```

---

## plan reject - 审核驳回变更计划

驳回变更计划，计划状态将回退并通知创建人修改。

```
mcm plan reject <id> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| id | 计划 ID | 是 |
| `--creator <mis>` | 操作人 MIS 号（服务间调用时必填，MIS 用户登录时可不填） | 否 |
| `--comment <评论>` | 驳回原因/评论 | **是** |
| `--approve-level <层级>` | 审核层级 | 否 |
| `-y, --yes` | 跳过交互式确认 | 否 |
| `-f, --format <格式>` | 输出格式（json/table/md） | 否 |

### 示例

```bash
mcm plan reject 12345 --comment "请补充变更影响范围" -y
mcm plan reject 12345 --comment "请补充变更影响范围" --approve-level 1 --creator zhangsan -y
```

---

## plan delete - 删除计划草稿

删除指定的变更计划草稿（仅限 **规划中 PLANNING** 状态的计划）。

```
mcm plan delete <id> [-y]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `<id>` | 变更计划 ID（必填） | - |
| `-y, --yes` | 跳过确认直接删除 | false |

### 注意事项

- 仅能删除处于**规划中（PLANNING）**状态的计划草稿，其他状态的计划无法删除
- 删除前会先查询计划详情确认计划存在，不存在时直接报错退出
- 删除操作**不可逆**，请确认后再执行

### 返回字段说明

成功时输出删除成功提示，失败时输出错误信息并以非零状态退出。

### 示例

```bash
# 删除计划（带确认提示）
mcm plan delete 12345

# 跳过确认直接删除
mcm plan delete 12345 -y
```

---

## plan revoke - 撤销变更计划

撤销变更计划，将计划从 AUDITING/WAIT_RUNNING/RUNNING 状态变更为 STOPPED(4)。

```
mcm plan revoke <id> [-y]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `<id>` | 变更计划 ID（必填） | - |
| `-y, --yes` | 跳过确认直接撤销 | false |
| `-f, --format <format>` | 输出格式（json/table/md） | json |

### 适用状态

| 状态码 | 状态名 | 说明 |
|--------|--------|------|
| 1 | AUDITING | 待审核，撤销后进入 STOPPED(4) |
| 5 | WAIT_RUNNING | 待变更，撤销后进入 STOPPED(4) |
| 6 | RUNNING | 变更中，⚠️ 撤销将中断正在执行的变更，需额外确认 |

### 注意事项

- PLANNING(9) 状态**不支持**撤销，该状态直接编辑即可
- STOPPED(4)、REJECTED(2) 状态不支持撤销（需执行 rebuild）
- 终态（SUCCEED/FAILED）不支持撤销
- 撤销操作**不可逆**（撤销后需通过 `rebuild` 重建为 PLANNING 草稿才能编辑）
- RUNNING(6) 状态下 Agent 调用前**必须**额外提示用户当前计划正在执行，不得静默加 `-y` 执行

### 返回字段说明

成功时输出撤销成功提示，`-f json` 时额外输出 API 返回的 JSON 结果；失败时输出错误信息并以非零状态退出。

### 示例

```bash
# 撤销计划（带确认提示）
mcm plan revoke 12345

# 跳过确认直接撤销（需用户已在 Agent 对话层面确认）
mcm plan revoke 12345 -y

# 撤销并输出 JSON 结果
mcm plan revoke 12345 -y -f json
```

---

## plan rebuild - 重建变更计划

将 STOPPED 或 REJECTED 状态的变更计划重建为 PLANNING 草稿，可继续编辑。

```
mcm plan rebuild <id> [-y]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `<id>` | 变更计划 ID（必填） | - |
| `-y, --yes` | 跳过确认直接重建 | false |
| `-f, --format <format>` | 输出格式（json/table/md） | json |

### 适用状态

| 状态码 | 状态名 | 说明 |
|--------|--------|------|
| 2 | REJECTED | 审核驳回，可直接重建为 PLANNING 草稿 |
| 4 | STOPPED | 撤销后的中间态，可直接重建为 PLANNING 草稿 |

### 注意事项

- 重建时先调用 `GET /api/v1/cf/plan/{id}/restart/preview` 获取预览数据，再调用 `POST /api/v1/cf/plan/draft/save` 完成重建
- 重建后会生成**新的草稿 ID**（原 ID 不变，内容复制到新草稿）
- 其他状态（PLANNING/AUDITING/WAIT_RUNNING/RUNNING 等）不支持重建

### 返回字段说明

成功时输出重建成功提示及新草稿 ID，`-f json` 时额外输出 API 返回的 JSON 结果；失败时输出错误信息并以非零状态退出。

### 示例

```bash
# 重建计划（带确认提示）
mcm plan rebuild 12345

# 跳过确认直接重建（需用户已在 Agent 对话层面确认）
mcm plan rebuild 12345 -y

# 重建并输出 JSON 结果
mcm plan rebuild 12345 -y -f json
```

---

## template create - 创建模板

专用接口创建变更模板。`baseFields`、`approveFields`、`noticeFields`、`contentFields`、`steps` 等字段结构与 `plan create` 一致。

```
mcm template create -n <模板名称> [选项]
```

### 参数

> `--data` 用法：直接传递完整 JSON 请求体覆盖以上所有参数，见下方请求体结构说明。`name` 在 `--data` 模式下为必填。
> ⚠️ **CLI 限制**：即使使用 `--data` 传入完整 JSON，`-n <名称>` 参数仍然**必须显式提供**。

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `-n, --name <名称>` | 模板名称（最多 100 字符） | 是 | - |
| `-d, --description <描述>` | 模板描述（最多 200 字符） | 否 | - |
| `--env <env>` | 变更环境（见[环境枚举](#环境枚举值)） | 否 | - |
| `--risk <risk>` | 风险等级（见[风险等级枚举](#风险等级枚举值)） | 否 | - |
| `--type <type>` | 变更类型（见[变更类型枚举](#变更类型枚举值)） | 否 | - |
| `--scene <scene>` | 变更场景，多个用逗号分隔（见[变更场景枚举](#变更场景枚举值)） | 否 | - |
| `--first-auditor <mis>` | 一级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--second-auditor <mis>` | 二级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--third-auditor <mis>` | 三级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--notice-group <groupId>` | 周知群 ID，多个用逗号分隔 | 否 | - |
| `--notice-content <content>` | 变更内容周知 | 否 | - |
| `--cc <mis>` | 抄送人 MIS，多个用逗号分隔 | 否 | - |
| `--description-field <desc>` | 变更描述（注意区别于 `-d`） | 否 | - |
| `--effect <effect>` | 变更影响，**必须是 JSON 字符串**格式：`{"hasEffect":false,"effect":"<p>影响说明</p>","effectScope":[]}` | 否 | - |
| `--rollback <plan>` | 回滚方案，**必须是 JSON 字符串**格式：`{"radioValue":true,"textValue":"<p>回滚方案说明</p>"}` | 否 | - |
| `--steps <json>` | 步骤列表 JSON 字符串（见[步骤参数文档](plan-create-api-schema.md#steps)） | 否 | - |
| `--data <json>` | 完整请求体 JSON 字符串（覆盖其他参数） | 否 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |

### 请求体结构（`--data` 用法）

与 `plan create` 相同，字段包括：`name`、`description`、`baseFields`、`approveFields`、`noticeFields`、`contentFields`、`steps`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | String | 是 | 模板名称（最多 100 字符） |
| description | String | 否 | 模板描述（最多 200 字符） |
| baseFields | Array | 否 | 基础信息字段数组（identify/value 格式） |
| approveFields | Array | 否 | 审批人字段数组 |
| noticeFields | Array | 否 | 周知字段数组 |
| contentFields | Array | 否 | 变更内容字段数组 |
| steps | Array | 否 | 步骤配置数组（见[步骤参数文档](plan-create-api-schema.md#steps)） |

### 示例

```bash
# 创建最简模板
mcm template create -n "代码发布模板" -d "标准代码发布模板" -y

# 使用 --data 创建带步骤的模板
mcm template create --data '{"name":"代码发布模板","description":"标准代码发布模板","baseFields":[{"identify":"env","value":"prod"},{"identify":"riskLevel","value":"低风险"},{"identify":"changeType","value":"常规变更"},{"identify":"scene","value":"代码发布"}],"steps":[{"title":"Plus发布","tool":"Plus","stepType":"PLUS","allowedOperator":["SPONSOR"],"stepOperation":{"items":[]}}]}' -y
```

---

## template update - 更新模板

更新已存在的变更模板，`--template-id` 为必填参数。支持通过 CLI 参数或 `--data` 传入完整请求体。

```
mcm template update --template-id <模板ID> [选项]
```

### 参数

> `--data` 用法：直接传递完整 JSON 请求体覆盖以上所有参数，见下方请求体结构说明。`templateId` 在 `--data` 模式下为必填。
> ⚠️ **CLI 限制**：即使使用 `--data` 传入完整 JSON，`--template-id <id>` 参数仍然**必须显式提供**。

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `--template-id <id>` | 模板 ID | 是 | - |
| `-n, --name <名称>` | 模板名称（最多 100 字符） | 否 | - |
| `-d, --description <描述>` | 模板描述（最多 200 字符） | 否 | - |
| `--admins <mis>` | 模板管理员 MIS，多个用逗号分隔 | 否 | - |
| `--env <env>` | 变更环境（见[环境枚举](#环境枚举值)） | 否 | - |
| `--risk <risk>` | 风险等级（见[风险等级枚举](#风险等级枚举值)） | 否 | - |
| `--type <type>` | 变更类型（见[变更类型枚举](#变更类型枚举值)） | 否 | - |
| `--scene <scene>` | 变更场景，多个用逗号分隔（见[变更场景枚举](#变更场景枚举值)） | 否 | - |
| `--first-auditor <mis>` | 一级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--second-auditor <mis>` | 二级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--third-auditor <mis>` | 三级审批人 MIS，多个用逗号分隔 | 否 | - |
| `--notice-group <groupId>` | 周知群 ID，多个用逗号分隔 | 否 | - |
| `--notice-content <content>` | 变更内容周知 | 否 | - |
| `--cc <mis>` | 抄送人 MIS，多个用逗号分隔 | 否 | - |
| `--description-field <desc>` | 变更描述 | 否 | - |
| `--effect <effect>` | 变更影响，**必须是 JSON 字符串**格式：`{"hasEffect":false,"effect":"<p>影响说明</p>","effectScope":[]}` | 否 | - |
| `--rollback <plan>` | 回滚方案，**必须是 JSON 字符串**格式：`{"radioValue":true,"textValue":"<p>回滚方案说明</p>"}` | 否 | - |
| `--steps <json>` | 步骤列表 JSON 字符串（见[步骤参数文档](plan-create-api-schema.md#steps)） | 否 | - |
| `--data <json>` | 完整请求体 JSON 字符串（覆盖其他参数） | 否 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |

### 请求体结构（`--data` 用法）

`--data` 直接传递完整 JSON 请求体，结构如下。`templateId` 为必填，其他字段可选：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| templateId | Number | 是 | 模板 ID |
| name | String | 否 | 模板名称（最多 100 字符） |
| description | String | 否 | 模板描述（最多 200 字符） |
| admins | Array | 否 | 模板管理员 MIS 数组 |
| baseFields | Array | 否 | 基础信息字段数组（identify/value 格式） |
| approveFields | Array | 否 | 审批人字段数组 |
| noticeFields | Array | 否 | 周知字段数组 |
| contentFields | Array | 否 | 变更内容字段数组 |
| steps | Array | 否 | 步骤配置数组（见[步骤参数文档](plan-create-api-schema.md#steps)） |

**注意**：使用 `--data` 时，支持部分更新，未传递的字段将保持原值不变。

### 示例

```bash
# 更新模板名称和描述
mcm template update --template-id 123 -n "新模板名称" -d "新描述" -y

# 使用 --data 更新模板步骤
mcm template update --template-id 123 --data '{"steps":[{"title":"新步骤","tool":"Plus","stepType":"PLUS","allowedOperator":["SPONSOR"],"stepOperation":{"items":[]}}]}' -y
```

---

## step update - 更新变更步骤

更新变更计划中的**某一个**步骤。每次调用只能操作单个步骤，`-p` 和 `-s` 在两种模式下均为必填：

- **CLI 参数模式**（`-t`/`-a`/`-o`/`--start`）：只更新所传参数对应的字段，其他字段保持不变
- **`--data` 模式**：`--data` 与其他 CLI 参数**互斥**，以 `--data` 为准，会**全量覆盖**该步骤的字段；`-p`/`-s` 仍需传入，若 JSON 中未包含 `planId`/`stepId` 会自动从参数注入

```
mcm step update -p <计划ID> -s <步骤ID> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 | 默认值 |
|---|---|---|---|
| `-p, --plan-id <planId>` | 计划 ID | 是 | - |
| `-s, --step-id <stepId>` | 步骤 ID | 是 | - |
| `-t, --title <title>` | 步骤标题（最多 100 字符） | 否 | - |
| `-a, --action <action>` | 操作详情/内容 | 否 | - |
| `-o, --allowed-operator <operator>` | 可执行人，多个用逗号分隔 | 否 | - |
| `--start <time>` | 预计开始时间（yyyy-MM-dd HH:mm:ss） | 否 | - |
| `--data <json>` | 完整请求体 JSON 字符串，与其他参数互斥，以此为准 | 否 | - |
| `-y, --yes` | 跳过交互式确认 | 否 | - |
| `-f, --format <格式>` | 输出格式 | 否 | json |

### 请求体结构（`--data` 模式）

> ⚠️ **注意**：即使使用 `--data`，`-p <计划ID>` 和 `-s <步骤ID>` 仍然**必须显式提供**；若 JSON 中未包含 `planId`/`stepId`，会自动从参数注入。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `planId` | Number | 是 | 计划 ID（由 `-p` 自动注入） |
| `stepId` | Number | 是 | 步骤 ID |
| `title` | String | 否 | 步骤标题 |
| `action` | String | 否 | 操作详情/内容 |
| `allowedOperator` | String | 否 | 可执行人，多个用逗号分隔 |
| `estimateStartTime` | String | 否 | 预计开始时间（yyyy-MM-dd HH:mm:ss），可为空字符串 `""` |

### 返回字段说明

返回更新后的步骤详情（同 [plan steps 返回字段](#返回字段说明-2)）。

### 示例

```bash
# CLI 参数模式：仅更新指定步骤的标题和操作人
mcm step update -p 456 -s 789 -t "新步骤标题" -o "zhangsan,lisi" -y

# CLI 参数模式：更新预计开始时间
mcm step update -p 456 -s 789 --start "2026-03-17 22:00:00" -y

# --data 模式：覆盖该步骤全部字段（与 CLI 参数互斥，-p/-s 仍需传入）
mcm step update -p 456 -s 789 --data '{"planId":456,"stepId":789,"title":"新步骤标题","allowedOperator":"zhangsan","estimateStartTime":""}' -y
```

---

## 典型场景

### 场景 1：查看团队本周变更

```bash
# Step 1: 查询团队计划列表
mcm plan my -t ORG --start "2026-03-09 00:00:00" --end "2026-03-15 23:59:59" -s 100 -f json

# Step 2: 针对某个计划查看详情
mcm plan detail <计划ID> -f json
```

`-t` 可选：LAUNCHED（我发起的）、TODO（待我处理）、DONE（我已处理）、ORG（我团队的）、ALL（全部）

---

### 场景 2：分析被驳回的计划

```bash
# Step 1: 筛选已驳回的计划
mcm plan list --status REJECTED -s 50 -f json

# Step 2: 查看驳回理由
mcm plan progress <计划ID> -f json
# 驳回理由在返回数据的 userOperations[].comment 字段中，格式为 "驳回理由:xxx"
```

---

### 场景 3：按组织查变更日历

```bash
# --org、--start、--end 三个参数均为必填
mcm plan calendar --org "100046-150042-1573" --start "2026-03-01 00:00:00" --end "2026-03-31 23:59:59" -s 100 -f json
```

---

### 场景 4：查找特定用户的变更计划

```bash
mcm plan search -u zhangsan -t CREATED -f json
```

`-t` 可选：ALL（全部）、CREATED（该用户创建的）、OPERATING（该用户操作中的）、CC（抄送给该用户的）

---

---

## event list - 变更事件列表

搜索变更管控事件列表（管控流程中的事件，非 CloudTrail 追溯事件）。

```
mcm event list [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--operator <mis>` | 操作人 MIS（默认从本地 SSO 配置自动获取） | 自动获取 |
| `-t, --query-type <type>` | 查询类型（见下表） | TODO |
| `-n, --name <name>` | 变更名称（模糊匹配） | - |
| `--source <source>` | 变更来源（如 Lion、Plus、OCTO 等） | - |
| `--target <target>` | 变更对象（如服务 appkey） | - |
| `--launcher <mis>` | 发起人 MIS | - |
| `--status <status>` | 变更状态，多个用逗号分隔（见[管控事件状态枚举](#管控事件状态枚举值)） | - |
| `--uuid <uuid>` | 事件 UUID，精确查询 | - |
| `--create-time-begin <time>` | 发起时间开始（yyyy-MM-dd HH:mm:ss） | - |
| `--create-time-end <time>` | 发起时间结束（yyyy-MM-dd HH:mm:ss） | - |
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数 | 10 |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | json |

### query-type 枚举值

| 值 | 说明 |
|---|---|
| TODO | 待我处理的变更 |
| LAUNCHED | 我发起的变更 |
| DONE | 我已处理的变更 |
| ORG | 我团队的变更 |
| ALL | 全部变更 |

### 返回字段说明（items 数组元素）

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 变更 ID（用于 event get / accept / reject / skip-audit） |
| eventUuid | String | 事件 UUID |
| accountName | String | 变更来源系统英文名（如 Lion、Plus） |
| accountNameCn | String | 变更来源系统中文名 |
| eventName | String | 事件英文名称 |
| eventNameCn | String | 事件中文名称 |
| target | String | 变更对象（通常为服务 appkey） |
| orgPath | String | 所属团队路径 |
| status | String | 变更状态（见[管控事件状态枚举](#管控事件状态枚举值)） |
| createUser | Object | 发起人信息，包含 `mis`（用户 MIS）字段 |
| createTime | String | 创建时间（ISO 格式） |

### 示例

```bash
# 查看待我处理的变更（默认）
mcm event list -f table

# 查看我发起的变更，按时间范围过滤
mcm event list -t LAUNCHED --create-time-begin "2026-06-01 00:00:00" --create-time-end "2026-06-10 23:59:59" -f table

# 按来源和状态过滤
mcm event list -t ALL --source Lion --status PRECHECKING -s 20 -f json

# 查看我团队的变更
mcm event list -t ORG -s 50 -f table
```

---

## event detail - 变更事件模型详情

查询某个变更来源系统的事件模型定义（非具体变更实例，是模型元数据）。

```
mcm event detail --account-name <系统名称> --event-name <事件名称> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `--account-name <name>` | 变更来源系统名称（如 Lion、Plus、OCTO） | ✅ 必填 |
| `--event-name <name>` | 事件名称（如 UpdateConfig、Deploy、AuthApply） | ✅ 必填 |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | 可选 |

### 返回字段说明

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | Integer | 事件模型 ID |
| accountName | String | 所属系统英文名 |
| name | String | 事件英文名称 |
| nameCn | String | 事件中文名称 |
| changeEnabled | Boolean | 是否开启变更管控 |
| rank | Integer | 事件级别 |
| description | String | 事件描述 |
| effect | String | 影响范围描述 |

### 示例

```bash
# 查询 Lion 配置变更的事件模型
mcm event detail --account-name Lion --event-name UpdateConfig -f table

# 查询 Plus 部署事件模型
mcm event detail --account-name Plus --event-name Deploy -f md
```

---

## event get - 变更详情

查询某个具体变更实例的完整详情，包括事件上下文、变更详情和预检结果。

```
mcm event get <changeId> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `<changeId>` | 变更 ID（从 event list 返回的 id 字段获取） | ✅ 必填 |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | 可选 |

### 返回字段说明

返回对象包含以下三个顶级字段：

**eventContext（事件上下文）**

| 字段名 | 说明 |
|---|---|
| eventName | 事件英文名称 |
| eventNameCn | 事件中文名称 |
| eventStartTime | 事件开始时间 |
| eventUuid | 事件 UUID |
| accountName | 来源系统英文名 |
| accountNameCn | 来源系统中文名 |
| env | 环境（prod/test/dev） |
| userIdentity | 操作人信息（含 name/mis） |
| resources | 变更涉及的资源（appkey、host 等） |
| requestParameters | 具体变更参数（因事件类型而异） |
| extraInfo | 扩展信息（可读的 input 键值对列表） |

**changeDetail（管控详情）**

| 字段名 | 说明 |
|---|---|
| id | 变更 ID |
| status | 管控状态（见[管控事件状态枚举](#管控事件状态枚举值)） |
| url | MCM 变更详情页链接 |
| createUser | 发起人 MIS |
| createTime | 创建时间 |

**preCheckResponse（预检结果）**

| 字段名 | 说明 |
|---|---|
| decision | 总体预检决策（ACCEPT/REJECT） |
| items | 命中的拦截规则列表 |
| fullItems | 全部预检规则结果列表 |

### 示例

```bash
# 查询变更详情（json 格式，适合脚本解析）
mcm event get 65654624 -f json

# 查询变更详情（表格格式，适合人工查看）
mcm event get 65654624 -f table

# 查询变更详情（md 格式，含完整 JSON 代码块）
mcm event get 65654624 -f md
```

---

## event accept - 通过变更审批

对处于 AUDITING（待审核）状态的变更执行审核通过操作。

```
mcm event accept <changeId> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `<changeId>` | 变更 ID | ✅ 必填 |
| `--operator <mis>` | 操作人 MIS（默认从本地 SSO 配置自动获取） | 可选 |
| `--comment <意见>` | 审核意见（可不填） | 可选 |
| `-f, --format <格式>` | 输出格式 | 可选 |

### 示例

```bash
# 审核通过
mcm event accept 65497288

# 带审核意见
mcm event accept 65497288 --comment "符合变更规范，通过"
```

---

## event reject - 驳回变更

对处于 AUDITING（待审核）状态的变更执行驳回操作。

```
mcm event reject <changeId> --comment <驳回原因> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `<changeId>` | 变更 ID | ✅ 必填 |
| `--comment <驳回原因>` | 驳回原因 | ✅ **必填**，缺少时命令直接报错退出 |
| `--operator <mis>` | 操作人 MIS（默认从本地 SSO 配置自动获取） | 可选 |
| `-f, --format <格式>` | 输出格式 | 可选 |

### 示例

```bash
mcm event reject 65497288 --comment "变更时间不合适，请调整至非高峰期"
```

---

## event skip-audit - 跳过变更审批

跳过变更的审批流程（需有相应权限）。

```
mcm event skip-audit <changeId> --comment <跳过理由> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `<changeId>` | 变更 ID | ✅ 必填 |
| `--comment <跳过理由>` | 跳过理由 | ✅ **必填**，缺少时命令直接报错退出 |
| `--operator <mis>` | 操作人 MIS（默认从本地 SSO 配置自动获取） | 可选 |
| `-f, --format <格式>` | 输出格式 | 可选 |

### 示例

```bash
mcm event skip-audit 65497288 --comment "紧急故障修复，已获得口头审批"
```

---

## cloudtrail list - 追溯事件列表

查询 CloudTrail 追溯事件列表（覆盖全平台系统的变更操作记录，通过 MCP Hub SSE 协议调用）。

`cloudtrail list` 默认走 MCP Hub `get_mcm_event_http` 完成查询，与上述认证体系一致，无需额外票据。

### CloudTrail 全局通用规则（调用前必读，对 cloudtrail-list 和 paas-trace.sh 均适用）

> ⚠️⚠️⚠️ **"变更"一词的歧义消解，禁止联想成变更计划**：MCM 里"变更计划"（`plan` 系列命令，管控中的审批流程）和"变更记录/变更追溯"（本节 `cloudtrail list`/`paas-trace.sh`，已发生的操作日志）是两套独立功能，字面上都含"变更"二字，但**不能因为字面相同就默认两个都查**。判断只看请求里有没有"计划"相关字样（"变更计划""草稿""审批中的计划"等）：没有出现，只是"XX 服务/appkey 近 N 天的变更/变更记录/变更历史"这类以服务或时间范围为主语的问法，唯一对应本节 CloudTrail 追溯查询，**禁止额外并行调用 `plan list`/`plan search` 等变更计划接口，禁止把回复自造拆分为"变更计划""CloudTrail 追溯事件""PaaS 资源变更"三个维度展示**。真实反面案例：请求"查 `com.sankuai.xxx.server` 服务近 1 天内的变更"，AI 额外调用了 `plan list` 并在回复中新增"一、变更计划"小节，这是被本条严令禁止的错误行为，该请求应仅执行下方 `cloudtrail list`（+按需 `paas-trace.sh`）并直接展示追溯事件结果。
>
> ⚠️⚠️⚠️ **本节规则没有"简单场景可以简化"这一说，禁止任何自由裁量**：不允许以"用户只是随口问问""没要求特定格式""先查个大概看看"等理由，对下方任何一条规则做打折、简化、跳过或"先执行看看再补"处理。这些规则的存在本身就是为了防止在看似简单的查询中出现漏查/输出跑偏，**规则的约束力不因请求听起来简单而减弱**。真实反面案例：曾有请求"查 `com.sankuai.xxx.server` 近 1 天变更"，AI 内心已识别出规则要求同时调用 `paas-trace.sh`，但以"用户只是简单查询"为由仅执行了 `cloudtrail list` 且改用 `-f json --page-size 100`，导致拿到 244 条原始 JSON 大数据后无法直接展示，进而自行用 jq 分析、生成"按环境/系统/事件类型分布"的文字汇总——这是被本节严令禁止的错误链条，本例中的每一步都违反了下方对应规则。

> ⚠️⚠️⚠️ **第一步永远是判断要不要调用 `paas-trace.sh`，这是最容易被跳过/误判的一步**："点没点名系统"专指有没有指定 `--account-name`（Lion、Plus、Squirrel 等变更来源系统名），**与 `--appkey`（业务服务名，如 `com.sankuai.xxx.server`）是两码事，appkey 本身不算"点名系统"**。只要用户没有提供任何 `--account-name` 取值（哪怕给了 appkey/操作人/团队等其他条件），就必须同时执行下面两条命令并行查询，**只调用第一条、漏掉第二条是最常见的错误**：
>
> ```bash
> mcm cloudtrail list --appkey <appkey> --begin <开始时间> --end <结束时间> -s 20 -f md
> bash <skill_dir>/scripts/paas-trace.sh --appkey <appkey> --begin <开始时间> --end <结束时间> -f md
> ```
>
> 两路结果分别展示为两张独立表格，禁止只展示第一条命令的结果。**但此处"两张表"指的是两条命令都必须实际执行、不能漏调用，不代表两条命令的结果都必须在回复里"看得见"**——若 `paas-trace.sh` 查到 0 条（stdout 为空），第二张表天然不存在，回复中只会剩下第一张表，这不属于"只展示第一条命令的结果"（因为第二条命令确实执行了，只是它没有产出需要展示的内容），**不能为了凑够"两张表"而编造任何文字**。用户点名了具体系统（如"查 Lion、Plus 的变更"）时不适用本条，改查下方 [「Squirrel/Mafka/RDS/Eagle 变更追溯」](#squirrelmafkardseagle-变更追溯针对-cloudtrail-list-命令通过-appkey-查不到某些系统变更的场景) 的路由判断表；完整展示规则（标题、说明文案）见 [「未点名任何系统场景」](#未点名任何系统场景)。

> ⚠️⚠️⚠️ **相对时间换算，算出精确时间点后禁止再自行"取整"改写**：`--begin`/`--end` 仅支持 `yyyy-MM-dd HH:mm:ss`、10 位秒级、13 位毫秒级时间戳三种格式，不支持"最近7天"等自然语言/相对时间表达式，传入无法识别的格式会立即报错。用户说"最近 N 天/小时"时，必须以**当前时刻为终点往前推算**出具体值，如 `--begin "$(date -v-1d '+%Y-%m-%d %H:%M:%S')" --end "$(date '+%Y-%m-%d %H:%M:%S')"`；**禁止取整日边界写法**（如 `00:00:00`/`23:59:59`），那样会漏掉当天 00:00 到当前时刻的数据，也不符合"最近 N 天/小时"的真实诉求（这与用户明确指定具体自然日期区间的场景不冲突，那种场景允许写整日边界）。`--begin`/`--end` 不可省略，不传默认仅查最近 24 小时。**算出精确时间点之后必须原样使用，禁止以"范围更完整/更保险"为由自行拓宽成整日边界**——这不是格式选择题，是本条规则唯一禁止的行为。真实反面案例：当前时间 `2026-07-29 17:56:37`，用户要求"近 3 天"，AI 已正确算出 begin 应为 `2026-07-26 17:56:37`，却在思考过程中以"用稍宽一点的范围"为由擅自改写为 `begin="2026-07-26 00:00:00", end="2026-07-29 23:59:59"`，这正是本条严令禁止的取整日边界行为，即使 AI 内心先算对了精确值，最终传参环节也必须原样使用该精确值，不得二次"优化"。

> ⚠️ **最大支持查询 180 天时间跨度**：若 `--begin`/`--end` 跨度超过 180 天（如用户要求"近一年"），命令会直接报错退出（"查询的时间跨度超过限制（最大 180 天），请缩小 --begin/--end 范围后重试"），**不会静默截断返回部分数据**，行为与 MCM Web 页面「变更检索」超限时一致。遇到该报错应如实告知用户已超限，建议缩小范围或分批查询，不要自行截断范围重试后把结果当作完整数据呈现。

> ⚠️ **固定调用参数（先于输出规则，决定能不能拿到"可直接展示"的结果）**：任何 `cloudtrail list` 查询（无论是否带 `--account-name`/`--user-org`）都必须固定加 `-s 20 -f md` 调用，**禁止用 `-f json` 拉全量数据后自行用 jq/代码处理，也禁止省略 `-s` 或改用更大的 `-s` 值**。`-f md` 直接返回现成的、无需二次加工的 Markdown 表格，是保证下方"原样输出"能够执行的前提；一旦改用 `json` 格式或不限条数拉取，就会拿到大批量原始数据，进而诱发按字段自行分组/统计/精简的错误行为。
>
> ⚠️ **熔断机制：拿到的结果如果大到需要 jq/代码/`read_file` 分批读取才能看完，本身就说明命令参数已经调错，禁止继续往下分析**——正确调用 `-s 20 -f md` 时返回的必然是 20 行以内的现成 Markdown 表格，不可能出现"输出过大被截断""需要读取临时文件""需要 jq 提取字段"这类情况。一旦出现，必须立即停止当前分析路径，回头检查命令是不是误用了 `-f json`/省略了 `-s`/`--page-size` 改大了，改正后按 `-s 20 -f md` 重新调用，而不是将错就错继续对大数据做统计。**发现即终止**：此时禁止基于已读到的错误参数结果输出任何正文（含表格、叙述、总结），必须先重新调用再回复。
>
> ⚠️ **点名具体系统时禁止先广查再过滤**：只要用户点名了一个或多个具体系统（如"查 XX 服务近 7 天 Lion、Plus 的变更"），必须直接把系统名传给 `--account-name` 精确查询，**禁止先不带 `--account-name` 查该 appkey 下的全量变更、再自行用 jq/代码按系统名过滤**——这不仅绕开了 `--account-name` 自带的精确查询能力，一旦点到的系统里含 Squirrel/Mafka/RDS/Eagle，还会因为这 4 个系统不上报业务 appkey 而直接漏查（必须改走/额外调用 `paas-trace.sh`）。点到的系统具体该怎么调用，一律先查 [「Squirrel/Mafka/RDS/Eagle 变更追溯」](#squirrelmafkardseagle-变更追溯针对-cloudtrail-list-命令通过-appkey-查不到某些系统变更的场景) 开头的路由判断表，不得凭经验臆断。
>
> ⚠️ **输出规则（本节及以下所有子场景统一遵守，子场景仅补充标题/表头差异，不重复定义）**：
>
> | 规则项 | 说明 |
> |---|---|
> | 展示内容 | 命令 stdout 原样渲染：标题行（如有）+ Markdown 表格 + 分页提示行（如有），不多不少；UUID 列固定为 `[完整36位UUID](https://mcm.mws.sankuai.com/#/event-review/detail/完整36位UUID)` 格式的跳转链接，禁止截短、拆解成裸文本或改写链接地址 |
> | 结尾位置 | 回复正文以分页提示行（或表格最后一行，若该场景无分页提示）结束，其后不得追加任何内容 |
> | 禁止内容 | 统计句（如"涉及 X 位操作人""覆盖 Y 个系统"）、总结句（如"整体来看""以上就是全部"）、引导句（如"如需查看更多请告诉我"）、自行增删表格列、按批次/系统归纳成新表格、编造 stdout 未提供的跳转链接 |
> | 例外 | 仅当用户在本轮明确要求"总结/分析/统计"时，才可在表格之后追加分析；未提出该要求时不适用 |
>
> 判断是否违规只看"表格之后是否还有内容"，与内容本身是否客观、统计数字是否正确无关——即使数字完全正确，只要出现在表格之后，也视为违规。
>
> ⚠️ **不确定回复格式是否合规时，直接照抄下方模板 A/B 逐项填空**：模板对 UUID 列、分页行为都有明确规定（UUID 列与其余列同等必填；未经用户明确要求翻页/要全部时只输出一次）。这套模板 A/B **是唯一的一套标题/表格/结尾行格式，不区分查询入口**——无论是按 `--appkey`、`--account-name`，还是按 `--user-org`/`--user-org-id` 查询，只要是 `cloudtrail list -f md` 的输出，一律用同一套模板填空，标题统一为 `## 追溯事件列表（共 N 条）`，不允许任何场景下自拟其他标题措辞（如"查询到 N 条相关变更"）。
>
> ⚠️ **只按"查询路径"分表，不按"系统"分表；标题改写只有一种写法**：无论用户点名了几个系统、是否混合了常规系统与 Squirrel/Mafka/RDS/Eagle，展示时永远只区分**两条查询路径**——`cloudtrail list` 直查路径（同一路径命中的多个常规系统名逗号拼接进一次调用，合并展示为**一张表**）与 `paas-trace.sh` 补充查询路径（同样合并展示为**一张表**）。命中几条路径就展示几张表（1 或 2 张），**不按 `accountName` 把同一路径的结果拆成多张/多小节表格**。**"命中几条路径展示几张表"是上限约束（不能超过 2 张、不能拆成更多小节），不是下限承诺——某条路径实际查到 0 条时，直接减少为该场景应展示的表格数量，不需要凑数字，也不需要为 0 条的那条路径写任何说明文字。**
>
> `paas-trace.sh` 的输出标题固定即为脚本自带的 `## 补充查询结果（共 N 条）`，无需 AI 改写。`cloudtrail list -f md` 的输出**直接照抄下方对应模板填空，禁止再自行推理"要不要删/要不要保留某一行"**：
>
> **模板 A（N ≤ 20，从 stdout 末尾行提取 N）**：
>
> > ## 追溯事件列表（共 `{N}` 条）
> >
> > | 开始时间 | 事件名称 | 系统 | 操作人 | 环境 | UUID |
> > |---|---|---|---|---|---|
> > | {stdout 第 1 行} |
> > | {stdout 第 2 行} |
> > | ...（逐行填入 stdout 表格的每一行，有多少行填多少行，不得省略、不得跳行）... |
> >
> > `> 共 {N} 条，第 {P} 页，每页 {S} 条`
>
> **模板 B（N > 20）**：
>
> > ## 追溯事件列表（共 `{N}` 条）
> >
> > `> 当前展示前 20 条`
> >
> > | 开始时间 | 事件名称 | 系统 | 操作人 | 环境 | UUID |
> > |---|---|---|---|---|---|
> > | {stdout 第 1 行} |
> > | {stdout 第 2 行} |
> > | ...（逐行填入 stdout 表格的每一行，有多少行填多少行，不得省略、不得跳行）... |
> >
> > `> 共 {N} 条，第 {P} 页，每页 {S} 条`
>
> 两个模板的唯一区别是模板 B 在表格上方多一行 `> 当前展示前 20 条`；**两个模板结尾都保留 `> 共 {N} 条，第 {P} 页，每页 {S} 条` 这一行，任何情况下都不删除**。`{N}`/`{P}`/`{S}` 直接抄 stdout 原始末尾行的数字，不做计算推断；UUID 列与其余列同等必填，逐字保留 stdout 原始的 `[uuid](链接)` Markdown 格式。除标题里的 `{N}` 和按需插入的 `> 当前展示前 20 条` 外，**表格本身与 stdout 末尾行逐字保留，禁止再做任何其他增删改写**——这就是唯一允许的改写范围，不存在第三种写法。禁止自行发明"{系统名} 变更""XX 服务变更"等按系统命名的标题，也不得对命中的多个常规系统逐个单独调用 `cloudtrail list` 后拼出多个小节——这些都属于按系统拆分展示，是需要规避的错误方式。
>
> Squirrel/Mafka/RDS/Eagle 只是普通的 `--account-name` 取值，唯一特殊点是这 4 个系统的变更事件不上报业务 appkey，所以本命令 `--appkey` + `--account-name` 查不到/查不全，需改用 `paas-trace.sh`。判断只看 `--account-name` 是否**仅包含**这 4 个系统（不含其他系统）：仅包含→只需 `paas-trace.sh`，不需要再调用本命令；为空、或包含这 4 个系统之一同时也包含其他系统→两者都要调用。完整判断规则、调用方式、结果展示规则详见下方 [Squirrel/Mafka/RDS/Eagle 变更追溯](#squirrelmafkardseagle-变更追溯针对-cloudtrail-list-命令通过-appkey-查不到某些系统变更的场景)。
>
> ⚠️ **禁止仅凭返回的 `total` 字段判断"已查全/已查完整"**：`cloudtrail list --appkey`（不带 `--account-name`）返回的 `total` 只是「业务 appkey 直查」这一路能查到的总数，天然不含 Squirrel/Mafka/RDS/Eagle 这 4 个系统的数据。即使用户后续追问"这个 total 是不是没包含 XX 系统"，也不能仅凭直觉回答，必须实际并行跑一次 `paas-trace.sh` 拿到这 4 个系统的真实条数（含 `_failedPaas`/`_truncatedPaas` 是否为空）后再回复，禁止凭经验直接断言"是/不是"而不做实际验证。

```
mcm cloudtrail list [选项]
```

### 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--begin <time>` | 开始时间（yyyy-MM-dd HH:mm:ss，或 10/13 位时间戳） | 近 24 小时 |
| `--end <time>` | 结束时间（yyyy-MM-dd HH:mm:ss，或 10/13 位时间戳） | 当前时间 |
| `--env <env>` | 环境（prod\|test） | - |
| `--appkey <appkey>` | 服务 appkey，多个用逗号分隔 | - |
| `--username <mis>` | 操作人 MIS | - |
| `--event-name <name>` | 事件名称（如 Deploy、UpdateConfig） | - |
| `--account-name <name>` | 追溯系统名称（如 Lion、Plus），多个用逗号分隔 | - |
| `--user-type <type>` | 用户类型（user=人工操作 \| api=系统自动） | - |
| `--event-uuid <uuid>` | 精确查询某个事件 UUID | - |
| `--event-parent-id <id>` | 查询某父事件下的子事件 | - |
| `--org-id <orgId>` | 资源归属部门 ID，查询该部门下所有变更（包含人工和API自动） | - |
| `--user-org-id <userOrgId>` | 变更人归属部门 ID，查询该部门成员发起的变更（对应页面"变更人归属组织"筛选）；⚠️ 使用前必须先看下方 [「user-org - 按团队/组织查询变更事件」](#user-org---按团队组织查询变更事件) 固定命令模板和输出格式，禁止只按本表参数含义自行拼参数 | - |
| `--user-org` | 自动使用当前登录用户的变更人归属组织查询（等价于 `--user-org-id <当前用户orgId>`，无需手动查询 orgId）；最常用形式，⚠️ 规则同上，见下方 [「user-org - 按团队/组织查询变更事件」](#user-org---按团队组织查询变更事件) | - |
| `--custom-resource-type <type>` | 自定义资源类型（如 `Squirrel::clusterName`），需与 `--custom-resource-names` 配合使用 | - |
| `--custom-resource-names <names>` | 自定义资源名称，多个逗号分隔，需与 `--custom-resource-type` 配合使用 | - |
| `-p, --page <页码>` | 页码 | 1 |
| `-s, --page-size <条数>` | 每页条数（最大 1000） | 20 |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | json |

> 指定 `--custom-resource-type` + `--custom-resource-names` 时，CLI 以两个独立 string 参数（`customResourceType` / `customResourceNames`）传入 MCP Hub `get_mcm_event_http`（GET query string），后端 `fillRawWithMcp` 将其组装为 `Map<String,List<String>>` 传入 ES 过滤，按自定义资源标识（如 Squirrel 集群名、Mafka Topic 名）精确过滤，与标准查询路径认证方式一致；批量查询业务 appkey 在 Squirrel/Mafka/RDS/Eagle 的全部变更，请使用下方 [Squirrel/Mafka/RDS/Eagle 变更追溯](#squirrelmafkardseagle-变更追溯针对-cloudtrail-list-命令通过-appkey-查不到某些系统变更的场景)。

### 返回字段说明（data 数组元素）

| 字段名 | 类型 | 说明 |
|---|---|---|
| eventUuid | String | 事件唯一标识 UUID |
| eventName | String | 事件英文名称 |
| eventNameCn | String | 事件中文名称 |
| accountName | String | 来源系统英文名 |
| accountNameCn | String | 来源系统中文名 |
| env | String | 环境（prod/test/dev） |
| eventStartTime | String | 事件开始时间 |
| eventEndTime | String | 事件结束时间 |
| eventParentId | String | 父事件 ID |
| userIdentity | Object | 操作人信息（name/type/invokeBy） |
| resources | Object | 涉及资源（app/host/domain/db/lion 等子对象） |
| customResources | Array | 自定义资源列表 |
| eventUrl | String | 事件详情页跳转链接 |
| mcmUrl | String | 关联 MCM 变更计划链接 |

**分页响应结构**

| 字段名 | 说明 |
|---|---|
| currentPage | 当前页码 |
| pageSize | 每页条数 |
| total | 总条数 |
| data | 事件列表 |

### 示例

> ⚠️ 以下示例仅用于人工在终端探索参数；Agent 调用规则以「CloudTrail 全局通用规则」为准。

```bash
# 查询近 24 小时的追溯事件（默认）
mcm cloudtrail list -f table

# 按 appkey 和时间范围查询
mcm cloudtrail list --appkey com.sankuai.xxx --begin "2026-06-09 00:00:00" --end "2026-06-10 00:00:00" -f table

# 只看人工操作的变更
mcm cloudtrail list --user-type user -s 50 -f json

# 精确查询某个事件
mcm cloudtrail list --event-uuid 82f47822-ec18-4edb-a4c4-e64218886860 -f table

# 查询我的团队成员发起的变更（变更人归属组织，自动获取当前用户 orgId，最常用）
mcm cloudtrail list --user-org -s 20 -f md

# 指定任意部门（变更人归属）查询（⚠️ 用户未要求"只看人工操作"时禁止加 --user-type，下方示例查全部人为+API）
mcm cloudtrail list --user-org-id 40047078 -s 20 -f md

mcm cloudtrail list --custom-resource-type "Squirrel::clusterName" --custom-resource-names "redis-op-mcm" -f table
```

### user-org - 按团队/组织查询变更事件

**触发识别**："我/我们团队""orgid 为 xxx""XX 部门/组织/团队成员"等 + "变更"的问法（无论是否指定 orgId、是否带时间范围），均属于本场景，直接映射为下方固定命令模板执行，**禁止当作开放式统计/分析类问题自由发挥总结、禁止按操作人/系统等维度手工分组罗列**。

> ⚠️ **禁止额外调用 `paas-trace.sh` 补查**： `--user-org`/`--user-org-id` 是按**操作人的组织归属**过滤，不依赖 appkey，已覆盖包括 Squirrel/Mafka/RDS/Eagle 在内的全部系统。执行完下方固定命令拿到结果后**必须直接结束回复**，禁止额外再跑一次 `paas-trace.sh`"补充查询"。

**参数选择**：查团队/组织成员发起的变更，优先用 `--user-org`（最常用，自动取当前登录用户所在部门，无需手动查 orgId）；只有当用户明确给出了别人/别的部门的 orgId 时，才改用 `--user-org-id <orgId>`。两者语义相同（均按变更人归属部门过滤），`--org-id` 是另一个完全不同语义的参数（按资源归属部门），会混入非团队成员发起的变更，不要混用。

| 参数 | 语义 | 适用场景 |
|---|---|---|
| `--user-org` | 查当前登录用户所在部门【团队成员发起】的变更，自动取 orgId | 最常用，未指定 orgId，查"我们/我的团队" |
| `--user-org-id <orgId>` | 同上，但按指定的 orgId 查询 | 用户明确给出了 orgId（如查其他部门） |

```bash
mcm cloudtrail list --user-org [--begin <时间>] [--end <时间>] [--user-type <user|api>] -s 20 -f md
mcm cloudtrail list --user-org-id <orgId> [--begin <时间>] [--end <时间>] [--user-type <user|api>] -s 20 -f md
```

**固定约束（本命令专用，与全局通用规则叠加）**：

| 约束项 | 规则 |
|---|---|
| 年份 | 用户输入仅含月日（如"6月30日"）时取当前年份，用 `$(date +%Y)` 动态获取，禁止写死年份数字 |
| 分页 | 只执行一次，固定 `--page 1 -s 20`；`N` 只能原样出现在「共 N 条」这一行里，**不得被用作任何统计句的依据**（如"涉及 X 位操作人"），因为当页最多 20 条，天然无法支撑对 N 条全量数据的人数/系统数归纳；不触发自动翻页，仅当用户明确要求"下一页/第 N 页/全部"时才执行单次换页查询；`-s` 只能为 `20`，禁止改用其他数值 |
| `--user-type` | 默认省略（查全部人工+API变更）；仅当用户逐字提到"人工/人为操作"或"非人为操作/API"时，才分别添加 `--user-type user`/`--user-type api`；不得因"团队成员"等措辞联想成人工操作而擅自添加，否则会静默漏查一半数据 |
| 并行查询 | 不触发 `paas-trace.sh`，详见上方「禁止额外调用 paas-trace.sh 补查」 |
| 输出格式 | 固定 `-f md` |

**时间约束**：用户说"近 N 天/小时"时，`--begin`/`--end` 必须按全局规则从当前时刻精确回推并原样传入，不得写成 `00:00:00`/`23:59:59` 的整日边界。

**输出**：使用全局[模板 A/B](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)原样展示，标题固定为 `## 追溯事件列表（共 N 条）`。本场景只执行当前请求页；仅当用户明确要求"下一页/第 N 页/给我全部/继续"时，才执行一次相应页码查询，不与前页合并、不额外汇总，也不得基于 `total` 对操作人或系统做统计。

---

## cloudtrail detail - 追溯事件详情

按事件 UUID 查询 CloudTrail 追溯事件的完整详情。

```
mcm cloudtrail detail <eventUuid> [选项]
```

### 参数

| 参数 | 说明 | 是否必填 |
|---|---|---|
| `<eventUuid>` | 事件 UUID（从 cloudtrail list 返回的 eventUuid 字段获取） | ✅ 必填 |
| `--begin <time>` | 事件时间范围起（yyyy-MM-dd HH:mm:ss），可选，传入可加速 ES 检索 | 可选 |
| `--end <time>` | 事件时间范围止（yyyy-MM-dd HH:mm:ss），可选，传入可加速 ES 检索 | 可选 |
| `-f, --format <格式>` | 输出格式：json（默认）、table、md | 可选 |

### 返回字段说明

在 `cloudtrail list` 返回字段基础上，detail 还包含以下完整字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| duration | Integer | 持续时长（毫秒） |
| sdkVersion | String | 上报 SDK 版本 |
| eventSourceAppkey | String | 来源 appkey |
| eventSource | String | 来源标识 |
| sourceIpAddress | String | 来源 IP |
| relatedPlanId | Integer | 关联变更计划 ID |
| requestParameters | Object | 变更入参（因事件类型而异） |
| responseElements | Object | 变更出参 |
| extraInfo | Object | 扩展信息 |
| eventResultState | String | 事件结果（SUCCEED/FAILED/TIMEOUT/EXCEPTION/CANCEL） |
| errorCode | String | 错误码 |
| errorMessage | String | 错误信息 |

### 示例

```bash
# 查询事件详情
mcm cloudtrail detail 82f47822-ec18-4edb-a4c4-e64218886860 -f table

# 指定时间范围加速检索
mcm cloudtrail detail 82f47822-ec18-4edb-a4c4-e64218886860 --begin "2026-06-10 00:00:00" --end "2026-06-11 00:00:00" -f md
```

---

## Squirrel/Mafka/RDS/Eagle 变更追溯（针对 cloudtrail list 命令通过 appkey 查不到某些系统变更的场景）

**背景**：Squirrel/Mafka/RDS/Eagle 是普通的 `--account-name` 取值，唯一特殊点是这 4 个系统的变更事件不上报业务 appkey，因此 `mcm cloudtrail list --appkey <appkey> --account-name <系统名>` 对这 4 个系统查不到/查不全，必须改用本节的 `paas-trace.sh`：脚本内部先把业务 appkey 换成该系统自身的资源标识（paasAppkey/Topic 短名/clusterAppkey），再调用 `cloudtrail list` 查询，一次调用即拿到完整结果。

**路由判断**（只看 `--account-name` 是否命中这 4 个系统，与 `--appkey` 本身的值无关）：

| `--account-name` 情况 | 调用方式 |
|---|---|
| 命中 Squirrel/Mafka/RDS/Eagle 之一或多个（未混其他系统） | 仅调用 `paas-trace.sh` |
| 命中「常规系统」（Lion、Plus、Crane、Turing、Rocket、HULK、OCTO 等，仅为举例非穷举） | 仅调用 `mcm cloudtrail list --appkey <appkey> --account-name <系统名，逗号分隔多值> --begin <开始时间> --end <结束时间> -s 20 -f md` |
| 同时命中「Squirrel/Mafka/RDS/Eagle」和「常规系统」，或未传 `--account-name`（系统范围未知） | 两路都调用，见下方「混合场景」/「未点名系统场景」 |

> ⚠️ 「常规系统」是纯粹的补集判断（不是 Squirrel/Mafka/RDS/Eagle 即为「常规系统」），不存在第三类系统需要特殊处理。

### 未点名任何系统场景

用户只给了 appkey（如"查 com.sankuai.xxx 近 7 天变更"）、未点名具体系统时，`cloudtrail list --appkey`（不带 `--account-name`）覆盖不到 Squirrel/Mafka/RDS/Eagle，必须**并行**执行两路查询并**分别展示为两张独立表格**（不做去重/排序/合并）：

| 路径 | 命令 |
|---|---|
| 第一路：业务 appkey 直查 | `mcm cloudtrail list --appkey <appkey> --begin <开始时间> --end <结束时间> -s 20 -f md` |
| 第二路：Squirrel/Mafka/RDS/Eagle 专项补查 | `bash skill/mcm-cli/scripts/paas-trace.sh --appkey <appkey> --begin <开始时间> --end <结束时间> -f md`（不传 `--account-name` 时默认查全部 4 个系统） |

展示规则（遵循上方全局[输出规则](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)，以下仅补充本场景的标题/拼接差异）：

1. 第一张表按上方 [「只按查询路径分表」](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用) 的模板 A/B 直接照抄填空（N ≤ 20 用模板 A，N > 20 用模板 B，结尾 `> 共 N 条，第 P 页，每页 S 条` 保留不删除）。
2. 第二张表标题即为 `paas-trace.sh` 输出自带的 `## 补充查询结果（共 N 条）`（N 为 Squirrel/Mafka/RDS/Eagle 合并去重后的总条数，脚本已按开始时间倒序排列成单一表格，不按系统分表，无需 AI 二次改写）。标题正下方脚本已固定自带一行说明：`⚠️ Squirrel/Mafka/RDS/Eagle 变更无法通过业务Appkey直查，已自动换标识补充查询`——该提示位于标题与「当前展示前 N 条/分页」提示之间，**必须让用户第一时间看到**，AI 只需原样保留、不得删除/改写/挪到表格下方或末尾，其后紧跟的表格内容同样原样保留。
3. 两张表直接换行分隔，不做跨表去重/排序/合并/取值口径对齐。
4. 第一路（业务 appkey 直查）结果为空时仍需保留标题 + 一句"未查到相关变更"说明；**第二路（`paas-trace.sh` 补充查询）结果为 0 条时，回复中必须完全不出现这一路的任何文字，包括但不限于：标题（无论是脚本自带的 `## 补充查询结果（共 0 条）` 还是自拟的 `## 补充查询结果（Squirrel/Mafka/RDS/Eagle）`）、⚠️ 提示、"未查到相关变更"/"该服务在 XX 系统近一天内无变更记录"等任何自然语言总结句、把 stderr 过程日志（如 `[paas-trace] 共 0 条变更事件（appkey=...）`）改写/去前缀/换个说法后转述成正文**。判断标准只有一个：`paas-trace.sh` 的 **stdout 是否为空**——脚本内部已在 `total == 0` 时不产生任何 stdout 输出，AI 看到 stdout 为空就直接当作"这一路完全不存在"处理，绝不允许因为在 stderr 里看到了 `共 0 条变更事件` 之类的过程日志、就误以为"有信息可以总结展示"而据此生成任何一句话；回复中只保留第一路的表格。

### 单一路径场景

用户只问「常规系统」（未涉及 Squirrel/Mafka/RDS/Eagle）：多个系统名逗号拼接进同一个 `--account-name` 一次性查询（如 `--account-name Lion,Plus`），一次调用、一张表、原样展示。

- 禁止对每个系统分别单独调用 `cloudtrail list`（那是按系统拆分的错误方式，见上方 [「只按查询路径分表」](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)，误用会导致标题未被替换、直接暴露原始通用标题 `## 追溯事件列表`，还会产生多余的接口调用）。
- 必须固定加 `-s 20`，与 `paas-trace.sh` 合并后列表前 20 条的展示条数对齐；不加 `-s` 会把接口返回的全部当页数据展示出来。
- `--begin`/`--end` 不可省略：`cloudtrail list` 默认仅查最近 24 小时（`paas-trace.sh` 默认 7 天），用户说"近 N 天"时必须显式换算传入，否则会把查询窗口静默收窄，产生假阴性。

### 混合场景

用户一次性问的系统**同时包含**「Squirrel/Mafka/RDS/Eagle 组」和「常规系统组」（如同时问 Lion、Squirrel、Mafka）时才适用本节；若全部落在「常规系统」（如只问 Lion、Crane、Plus），按上方「单一路径场景」处理，**不因为系统数量多就拆成多次调用**。

固定执行步骤：

0. **先计算好 `--begin`/`--end`**：用户提了具体时间范围（如"近 7 天/30 天"）时，在此步换算出唯一一对值，后续每次调用原样传入，不依赖各自默认值（`paas-trace.sh` 默认 7 天、`cloudtrail list` 默认 24 小时，混用会导致两组数据时间窗口不一致）；未提时间范围则两步都不传。
1. 按路由判断表把用户提到的系统名分成两组：Squirrel/Mafka/RDS/Eagle 组、常规系统组。
2. 特殊系统组非空时，把组内系统名逗号拼接，**只调用一次** `paas-trace.sh --account-name <逗号拼接的系统名> [--begin <开始时间> --end <结束时间>] -f md`（只传用户点名的系统，`--begin`/`--end` 取步骤 0 的值），得到「补充查询结果」这一张表，标题即脚本自带的 `## 补充查询结果（共 N 条）`，无需改写；**若结果为 0 条，直接不展示这一张表**（不出现标题、⚠️ 提示等任何内容）。
3. 常规系统组非空时，同样把组内系统名逗号拼接，**只调用一次** `mcm cloudtrail list --account-name <逗号拼接的系统名> [--begin <开始时间> --end <结束时间>] -s 20 -f md`（**不按系统拆分成多次调用**；`-s 20` 固定不可省略或改值；`--begin`/`--end` 取步骤 0 的同一对值，省略会导致直查组查询窗口比脚本组窄），得到「追溯事件列表」这一张表，按上方 [「只按查询路径分表」](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用) 的模板 A/B 直接照抄填空。
4. **拼接**：两组均非空时才会有两张表，顺序无所谓；直接把步骤 2、步骤 3 的 stdout（各自整体不拆分）依次首尾拼接，不加过渡句、开头引导句、结尾总结句；只命中一组时只展示对应那一张表，不得为了"凑两张表"而空跑另一路。
5. 每张表的表格内容必须逐字展示：直接复用工具调用返回的原始 stdout 文本做拼接改写（如用 `sed` 替换标题行后整体读出），禁止手工转录/重新打字（易漏行、漏列，或把 36 位 UUID 误截成前 8 位、拆散 Markdown 链接语法），确保表格行数、列数、单元格内容（含链接语法）逐字符与源数据一致。

> ⚠️ **输出规则同上**：本节混合场景与上方单一路径场景一样，遵循「CloudTrail 全局通用规则」中的[输出规则](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)表，标题只按本节步骤 3 改写「追溯事件列表」一处，`paas-trace.sh` 标题无需改写，表格内容（含 UUID 链接）逐字原样展示，不另行归纳，也不按 `accountName` 把常规系统组拆成多张/多小节表格。

**`paas-trace.sh` 内部如何补全资源标识**：`paas-trace.sh` 不是 `mcm-cli` 内置子命令，是纯 Shell 编排脚本，内部分两步：

1. **换标识**：调用 Avatar 及各系统自身 API，把业务 appkey 换成该系统的资源标识（Squirrel/RDS 取各自 paasAppkey；Mafka 取 Topic 短名，Avatar 依赖记录仅供参考、不作前置判断，即使 Avatar 未返回也照常查询；Eagle 经 Avatar+OpenAPI 映射取 clusterAppkey）。
2. **查变更**：拿换到的资源标识调用 `mcm cloudtrail list`（Squirrel/RDS/Eagle 走标准 `--appkey`/`--account-name` 直查；Mafka 路径 A 用业务 appkey 直查、路径 B 精确过滤场景用 `--custom-resource-type`/`--custom-resource-names`），最后按 `eventUuid` 去重、开始时间倒序合并多系统结果。

若后续发现其他系统也存在"业务 appkey 直查不全"的问题，需先扩展脚本才能支持，不能假设其他系统都能用 `cloudtrail list` 直查。

> ⚠️ **路径规则**：脚本路径必须相对 `SKILL.md` 所在的 skill 安装目录（`<skill_dir>/scripts/paas-trace.sh`）定位，禁止假设当前工作目录就是 skill 目录或 mcm-cli 源码仓库根目录。skill 可能安装在全局（如 `~/.catpaw/skills/skills-market/mcm-cli/`）或项目级（如 `{workspace}/.catpaw/skills/skills-market/mcm-cli/`），执行前请先确认 `SKILL.md` 文件自身的实际路径，再据此拼接出 `scripts/paas-trace.sh` 的绝对路径后调用。

> ⚠️ **脚本失败时严禁降级（最重要）**：`paas-trace.sh` 若因 MWS SSO 认证失败（输出含"无法获取 MWS 认证票据"）而退出，**必须停下来告知用户认证失败，并引导用户按脚本提示完成认证后重试，绝对禁止自行降级改用 `mcm cloudtrail list --appkey` 直查 Squirrel/Mafka/RDS/Eagle 作为替代**（该命令用业务 appkey 直查这 4 个系统会混入 Rocket/HULK/OCTO 等主机运维平台的变更，且查不到真正的完整变更记录；注意此限制仅针对这 4 个已验证需要先换取资源标识的系统，常规系统按上表直接用 `cloudtrail list --appkey` 查即可）。正确处理：**步骤一（优先）**：读取并执行 `mtsso-skills-official` skill 换取用户身份票据，执行 `mcm login --token "${user_access_token}"` 完成无感登录后重试脚本；**步骤二（仅步骤一失败时）**：将脚本 stderr 原文展示给用户，引导执行 `mcm login --mis <MIS号>` 完成 CIBA 登录（大象确认）后重试。

> ⚠️ **stdout/stderr 区分**：脚本执行过程中打印的 `[paas-trace] ...` 系列日志均输出到 **stderr**，是过程日志，**不属于展示内容，必须完全忽略**——"完全忽略"不仅指禁止原文复述/粘贴到回复正文，也**禁止提炼其含义、换个说法、去掉 `[paas-trace]` 前缀后改写成"看起来更像正文"的句子**（例如把 stderr 里的 `[paas-trace] 共 0 条变更事件（appkey=xxx）` 改写成"该服务在 XX 系统近一天内无变更记录"这类总结句，同样违规）；只有 **stdout**（以 `>` 开头的条数提示行 + Markdown 表格）才是要展示给用户的结果，按上方全局[输出规则](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)表逐字粘贴渲染即可，stdout 为空就是零展示、禁止在表格前后插入 stderr 日志或基于 stderr 生成的任何替代性描述。
>
> ⚠️ **内容特征优先于流归属的兜底判断**：若执行环境未严格区分 stdout/stderr（如工具调用把两路合并返回），**只要看到 `[AI 指令]`、`[paas-trace]` 这类前缀开头的文本，无论它出现在结果的什么位置，一律直接判定为内部过程提示、必须排除，不属于"stdout 展示内容"**——不要因为"规则要求原样展示 stdout、不能截断"而纠结是否要把这类前缀文本也展示给用户；这类前缀本身就是过程日志的强特征标识，识别到即排除，无需反复推理。

```
bash skill/mcm-cli/scripts/paas-trace.sh --appkey <业务appkey> [选项]
```

### 参数

| 参数 | 说明                                                                                                                                                                         | 是否必填                                                                                                                                                       |
|---|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--appkey <appkey>` | 业务服务 appkey                                                                                                                                                                | ✅ 必填                                                                                                                                                       |
| `--account-name <name>` | 限定系统（`Squirrel`\|`Mafka`\|`RDS`\|`Eagle`，即目前脚本已支持的全部系统），不填则查询这 4 个系统。**若需查的系统不在本脚本支持范围内，请勿传给本脚本，先按默认原则改用上方的 `mcm cloudtrail list --appkey ... --account-name <系统名>` 直查命令** | 可选                                                                                                                                                         |
| `--begin <time>` | 开始时间（yyyy-MM-dd HH:mm:ss 或毫秒时间戳）。MCM 查询接口最大支持 180 天，脚本会在发起任何子查询前先做前置校验，超出 180 天会直接报错退出（不会静默截断返回部分数据，也不会先跑完所有平台子查询才报错）                                                      | 默认近 **7 天**（脚本自身设置的默认值，未指定时会在 stderr 提示实际使用的起点时间；区别于底层 `mcm cloudtrail list` 命令本身「未指定时间默认最近 24 小时」的默认行为——paas-trace.sh 定位是追溯/排查场景，24 小时明显偏短，故脚本层单独兜底为 7 天） |
| `--end <time>` | 结束时间（yyyy-MM-dd HH:mm:ss 或毫秒时间戳）                                                                                                                                           | 默认当前时间                                                                                                                                                     |
| `--env <env>` | 环境（prod\|test）                                                                                                                                                             | 可选                                                                                                                                                         |
| `--username <mis>` | 操作人 MIS，进一步过滤                                                                                                                                                              | 可选                                                                                                                                                         |
| `--user-type <type>` | 用户类型（user=人工\|api=非人工）。**⚠️ 除非用户明确说"只查人为操作"，否则禁止加此参数，默认查全部（人为+API自动）**                                                                                                     | 可选                                                                                                                                                         |
| `--event-name <name>` | 事件名称过滤，如 `CategoryQuery`、`TopicCreate`，多个用逗号分隔（OR 语义）                                                                                                                      | 可选                                                                                                                                                         |
| `-f, --format <格式>` | 输出格式：md、table、json                                                                                                                                                        | 默认 **md**（区别于 `mcm cloudtrail list` 默认 json，本脚本默认直接产出可展示的 Markdown 表格）                                                                                            |
| `-p, --page <页码>` | 展示分页页码，与 `mcm cloudtrail list` 的 `-p` 语义/命名对齐。**不传时不触发分页展示**，仅展示合并后列表前 20 条（与内置 `mcm cloudtrail list` 默认每页 20 条保持一致）；一旦显式传入（哪怕只传 `-p` 或只传 `-s`），才切换为真分页模式                   | 不传时默认展示前 20 条                                                                                                                                              |
| `-s, --page-size <条数>` | 每页展示条数，与 `mcm cloudtrail list` 的 `-s` 语义/命名对齐，同样仅在显式传参后才影响分页展示                                                                                                             | 不传时默认展示前 20 条                                                                                                                                              |


> 自然语言参数映射：“只看人工/人为操作”→ `--user-type user`；“只看非人为操作/API”→ `--user-type api`；“某个系统”→ `--account-name <系统名>`（大小写不敏感）；结果中 `accountNameCn`/`accountName` 字段可区分来源系统（Squirrel/Mafka/RDS/Eagle）。

### 输出说明

`-f md` 不按系统（`accountName`）分组，而是把命中系统（Squirrel/Mafka/RDS/Eagle 之一或多个）的结果**合并为单一列表**，按开始时间倒序排列后输出为**一个标题 + 一行固定提示 + 一张 Markdown 表格**（标题固定为 `## 补充查询结果（共 N 条）`），列结构固定为 `["开始时间","事件名称","系统","操作人","环境","UUID"]`，与 `mcm cloudtrail list -f md` 完全对齐；「系统」列保留每行的来源系统名，用于区分记录属于哪个系统。两条查询路径（本脚本 + `cloudtrail list`）的结果可直接拼接展示，无需改写。

标题正下方脚本固定自带一行 ⚠️ 提示：`⚠️ Squirrel/Mafka/RDS/Eagle 变更无法通过业务Appkey直查，已自动换标识补充查询`。该提示始终展示（**结果为 0 条时整张表连同此提示一起不展示**，见下），**必须让用户第一时间感知**，AI 原样保留、不得删除/改写/挪动位置（尤其不得移到表格下方或回复末尾）。

`-p`/`-s` 对**合并后的整个列表统一生效**：一次查多个系统（如 `--account-name Squirrel,Mafka` 或不传查全部 4 个系统）时，不区分来自哪个系统，统一按同一页码/条数整体翻页。**不区分是否显式传 `-p`/`-s`，展示行为统一**（未显式传参时等价于隐式 `-p 1 -s 20`），与 `cloudtrail list -f md` 模板 A/B 完全对齐：

| 情形 | 触发条件 | ⚠️ 提示下方紧跟的提示 | 结尾固定行 |
|---|---|---|---|
| 结果为 0 条 | 合并后总条数为 0 | **整张表（标题/⚠️ 提示/表头/结尾）都不展示**，详见下方「结果为 0 条」小节 | 不展示 |
| 当前页有数据 | 总条数 > 0 | 仅当总条数 > 每页条数时追加 `> 当前展示前 N 条` | `> 共 N 条，第 P 页，每页 S 条`（始终展示，不因是否显式传 `-p`/`-s` 而省略） |
| 翻页超出范围 | 显式传 `-p` 且页码 > 总页数 | `> 第 P 页超出范围（共 M 页），以下为空` | 同上，`P` 为用户传入的页码 |

**输出示例（Squirrel + RDS 合并后共 31 条，超过每页 20 条；UUID 列为 `[uuid](详情页链接)` 格式的 Markdown 链接，与 `cloudtrail list -f md` 一致，原样展示）**：

## 补充查询结果（共 31 条）

> ⚠️ Squirrel/Mafka/RDS/Eagle 变更无法通过业务Appkey直查，已自动换标识补充查询

> 当前展示前 20 条

| 开始时间 | 事件名称 | 系统 | 操作人 | 环境 | UUID |
|---|---|---|---|---|---|
| 2026-07-21 12:17:24 | 修改category负责人 | Squirrel | API调用 | prod | [xxx-uuid-1](https://mcm.mws.sankuai.com/#/event-review/detail/xxx-uuid-1) |
| 2026-07-20 09:10:00 | 实例重启 | RDS | 张三 | prod | [xxx-uuid-4](https://mcm.mws.sankuai.com/#/event-review/detail/xxx-uuid-4) |
| 2026-07-08 14:25:24 | 删除Key | Squirrel | 魏春荣 | prod | [xxx-uuid-3](https://mcm.mws.sankuai.com/#/event-review/detail/xxx-uuid-3) |

> 共 31 条，第 1 页，每页 20 条

显式传 `-p 2 -s 20` 时沿用同一结构，仅替换为第 2 页数据和对应页码；其余输出规则均以全局规则为准。

**结果为 0 条**：脚本内部已判断 `total == 0` 时不生成 md 输出（不出现标题、⚠️ 提示、表头、结尾行等任何内容，**stdout 为空字符串**）。AI 判断这一路是否有结果，**只看 stdout 是否为空这一个标准**，不看 stderr 里有没有信息：stdout 为空就直接当这一路完全不存在，禁止做任何形式的补充说明——不得自拟标题（如 `## 补充查询结果（Squirrel/Mafka/RDS/Eagle）`）、不得写"未查到相关变更"/"该服务在 XX 系统近一天内无变更记录"这类总结句，也**不得把 stderr 中的过程日志（如 `[paas-trace] 共 0 条变更事件（appkey=...）`）改写、去掉 `[paas-trace]` 前缀、或换一种说法后当作正文转述**——哪怕内容看起来是"如实反映了 0 条这个事实"，只要它源自 stderr 且经过了任何形式的转述包装，就是违规。直接按[全局规则](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用)"结果为 0 条时不展示这一路"处理，回复中不出现这一路的任何痕迹（一个字都不出现）。

**查看"剩余的/更早的/第 N 页"数据**：用户明确要求查看下一页或指定页码时，重新执行同一条 `paas-trace.sh` 命令（`--account-name` 不变），加上或调整 `-p` 为所需页码即可，脚本对合并后的单一列表返回该页数据，不需改用 `-f json` + `jq` 手工切片，也**禁止**改用 `cloudtrail list` 重查同一 appkey（会查不全）。合并结果超过展示上限、或当前页未展示完时，脚本会在 stderr 额外打印 `[paas-trace] ℹ ...` 提示 + 完整翻页命令；按上方 [stdout/stderr 区分](#cloudtrail-全局通用规则调用前必读对-cloudtrail-list-和-paas-tracesh-均适用) 规则，该内容仅供内部参考、下次翻页直接照抄参数，**禁止出现在回复正文**。当前页结果以 `> 共 N 条，第 P 页，每页 S 条` 结束，不追加下一页提示或其他文字。

**`-f json` 结构**：顶层固定为 `{ data, _failedPaas, _truncatedPaas }`。`data` 为按 `eventUuid` 去重、按开始时间倒序排列的**完整**事件数组（不做任何截断）；`_failedPaas` 为查询失败的系统名数组（全部成功时为 `[]`）；`_truncatedPaas` 为结果被截断的系统名数组（全部完整时为 `[]`）。`table` 格式同样不按系统分组，输出为合并排序后的单一 TSV 表格（失败/截断提示仅打印到 stderr）。

**结果完整性判断**：脚本对 Squirrel/Mafka/RDS/Eagle 各自发起独立子查询，以下两类情况会导致结果不完整：

| 情况 | 触发条件 | stderr 提示 | `-f json` 字段 | 退出码 |
|---|---|---|---|---|
| 子查询失败 | 网络异常、鉴权失效、超时等 | 显式打印失败原因，末尾汇总"N 个子查询失败，以下结果可能不完整" | `_failedPaas` 含失败系统名 | exit 1 |
| 数据量超上限 | 单系统查询命中分页安全上限（每页 100 条，最多翻 100 页 = 10000 条） | `⚠ ${desc}：查询数据已超过 10000 条，仅按前 10000 条数据进行展示和聚合`（文案对齐 MCM Web 页面既有提示） | `_truncatedPaas` 含被截断系统名 | exit 0（非失败，仅数据量提示） |

消费方应结合退出码、`_failedPaas`、`_truncatedPaas` 判断结果是否完整，**不能仅凭 `data` 为空数组断言"该服务在 Squirrel/Mafka/RDS/Eagle 无变更"**：

- exit 非 0 或 `_failedPaas` 非空：建议设置 `MCM_DEBUG=1` 重新执行排查（常见原因：登录态过期、网络超时）；
- `_truncatedPaas` 非空：说明该系统在当前时间范围内变更量超过 10000 条，建议缩小时间范围（如按月/按周拆分）或补充 `--user-type`/`--event-name` 等过滤条件降低单次数据量。

**Mafka Topic 精确过滤兜底提示**：脚本在路径 B 加了 `--filter-account-name Mafka` 客户端双重保险，若后端 `customResourcesFilter` 出现异常退化（如回滚），会在过滤掉噪音时打印 stderr 提示：`⚠ Mafka(Topic精确过滤)：后端 customResourcesFilter 过滤异常，本页 ${raw_count} 条中已客户端过滤掉 ${noise_count} 条非 Mafka 噪音`。正常情况下（后端过滤生效）噪音为 0，该提示不会出现。最终 `data` 始终是过滤后的真实 Mafka 记录，不影响 `_failedPaas`/`_truncatedPaas` 结果。

**环境自检**：脚本启动时会检测 `PATH` 中解析到的 `mcm` 命令是否为 Node.js 实现（即 mcm-cli 本体）。部分开发机可能安装了其他同名的 `mcm` 工具（如某些 Python 脚手架）且 PATH 优先级更高，此时步骤二的所有查询会被静默路由到错误命令、返回空结果且不报错。脚本检测到疑似此类冲突时会打印警告提示，建议按提示检查 `PATH` 优先级或使用绝对路径调用 `mcm`。

### 示例

> ⚠️ 以下示例均固定用 `-f md`，与上方全局规则保持一致：`-f md` 才会触发脚本内部的 `[AI 指令]` 强提示（要求原样逐字展示、禁止总结/引导句），`table` 仅适合人工在终端自行查看，AI 调用时禁止改用 `table`。

```bash
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery -f md

# 只看 Squirrel 配置变更
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --account-name Squirrel -f md

# 只看 Mafka 消息队列变更
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --account-name Mafka -f md

# 只看 RDS 数据库变更（按集群维度返回，非仅当前 appkey 一方发起）
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --account-name RDS -f md

# 只看 Eagle（ES）索引变更（按集群维度返回，非仅当前 appkey 一方发起）
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --account-name Eagle -f md

# 查常规系统（如 Lion）：不走本脚本，直接用内置命令，务必固定加 -s 20 -f md
# ⚠️ 若用户要求"近 N 天"等具体范围，务必显式加 --begin/--end；不加时 cloudtrail list 默认只查最近 24 小时，
# 而非本脚本的 7 天默认值，容易把有数据的时间段漏查成"暂无数据"
mcm cloudtrail list --appkey com.sankuai.mall.product.consumerquery --account-name Lion --begin "$(date -v-7d '+%Y-%m-%d %H:%M:%S')" --end "$(date '+%Y-%m-%d %H:%M:%S')" -s 20 -f md

# 混合场景示例：用户问"查一下近 7 天 Lion、Plus、Squirrel、Mafka 的变更"，按路由判断表分成
# 「常规系统组」（Lion、Plus）和「特殊系统组」（Squirrel、Mafka）各只调用一次，同组内多个系统名
# 逗号拼接进同一次调用，不按系统逐个单独查询，最终各自合并展示为一张表（两条路径=两张表）
# ⚠️ 两条命令均须固定加 -f md；两条命令的 --begin/--end 必须传同一个时间范围，
# cloudtrail list 一侧尤其不能漏传（默认仅 24 小时），否则时间窗口比 paas-trace.sh 一侧窄
mcm cloudtrail list --appkey com.sankuai.mall.product.consumerquery --account-name Lion,Plus --begin "$(date -v-7d '+%Y-%m-%d %H:%M:%S')" --end "$(date '+%Y-%m-%d %H:%M:%S')" -s 20 -f md
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --account-name Squirrel,Mafka --begin "$(date -v-7d '+%Y-%m-%d %H:%M:%S')" --end "$(date '+%Y-%m-%d %H:%M:%S')" -f md

# 指定时间范围（跨度超过 180 天会直接报错退出，不会静默截断）
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery \
  --account-name Squirrel --begin "2026-07-01 00:00:00" --end "2026-07-15 23:59:59" -f md

# 只看人工操作
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --user-type user -f md

# 只看某类事件（多个用逗号分隔，OR 语义）
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --event-name CategoryQuery -f md
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery --event-name CategoryQuery,CategoryDelete -f md

# 分页查看第 2 页（-p/-s 对合并后的单一列表整体生效，单系统/多系统/不传 --account-name 均可用）
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery \
  --account-name Squirrel -p 2 -s 20 -f md
bash skill/mcm-cli/scripts/paas-trace.sh --appkey com.sankuai.mall.product.consumerquery \
  --account-name Squirrel,Mafka -p 2 -s 20 -f md
```

---

## 附录：枚举值参考

### 计划状态枚举值

> `plan list` / `plan my` / `plan search` / `plan calendar` 的 `status` 字段返回字符串枚举值；`plan detail` 的 `status` 字段返回数字码。

| 枚举值 | 中文名称 | 数字码 |
|---|---|---|
| PLANNING | 规划中 | 9 |
| AUDITING | 待审核 | 1 |
| REJECTED | 已驳回 | 2 |
| WAIT_RUNNING | 待变更 | 5 |
| RUNNING | 变更中 | 6 |
| SUCCEED | 变更完成 | 8 |
| STOPPED | 变更终止 | 4 |
| FAILED | 变更失败 | 7 |

### 步骤状态枚举值

> `plan steps` 返回的 `status` 字段为数字码。

| 数字码 | 中文含义 |
|---|---|
| 0 | 未开始 |
| 1 | 待执行 |
| 2 | 执行中 |
| 3 | 执行成功 |
| 4 | 执行失败 |
| 5 | 已撤销 |

### 步骤类型枚举值

> `plan steps` / `template detail` 返回的 `stepType` 字段为字符串枚举值。

| 枚举值（name） | 数字码（value） | 中文说明 |
|---|---|---|
| Normal | 0 | 常规步骤（手动操作） |
| Lion | 1 | Lion 配置变更步骤 |
| Plus | 2 | Plus 代码发布步骤 |
| Rds | 3 | RDS 数据库变更步骤 |
| Terminal | 4 | 黑屏（终端命令行）变更步骤 |
| Crane | 5 | Crane 定时任务变更步骤 |
| Turing | 6 | 图灵算法包变更步骤 |
| Observation | 7 | 观测步骤 |

### 进展阶段状态枚举值

> `plan progress` 返回的 `status` 及 `userOperations[].status` 字段为字符串枚举值。

| 枚举值 | 中文名称 | 说明 |
|---|---|---|
| LAUNCHED | 已提交 | 计划已提交，非草稿状态 |
| AUDITING | 审核中 | 审核节点待审核 |
| ACCEPTED | 已通过 | 审核节点通过 |
| REJECTED | 已驳回 | 审核节点被驳回 |
| CANCELED | 已撤销 | 计划已撤销 |
| UN_START | 未开始 | 审批通过但未开始变更 |
| RUNNING | 进行中 | 变更步骤执行中 |
| FINISHED | 已完成 | 变更执行结束 |
| EXECUTE_SUCCEED | 执行成功 | 变更执行成功 |
| EXECUTE_FAILED | 执行失败 | 变更执行失败 |
| DRAFT_SAVED | 已保存 | 草稿状态 |

### 审批状态枚举值

> `plan detail` 中 `planApproves[].status` 字段。

| 数字码 | 枚举值 | 中文名称 |
|---|---|---|
| 0 | AUDITING | 待审核 |
| 1 | ACCEPTED | 审核通过 |
| 2 | REJECTED | 审核驳回 |

### 审批类型枚举值

> `plan progress` 返回的 `approveType` 字段，表示该审核阶段的通过规则。

| 值 | 说明 |
|---|---|
| OR | 任一审核人通过即可 |
| AND | 所有审核人均需通过 |

### 风险等级枚举值

| 值 | 说明 |
|---|---|
| 低风险 | 日常低风险变更 |
| 高风险 | 需要重点审批的高风险变更 |

### 环境枚举值

| 值 | 说明 |
|---|---|
| prod | 生产环境 |
| staging | 预发布环境 |
| test | 测试环境 |
| dev | 开发环境 |

### 变更场景枚举值

| 值 | 说明 |
|---|---|
| 代码发布 | 应用代码部署 |
| 配置变更 | 配置中心配置修改 |
| 数据变更 | 数据库数据修改 |
| 运维操作 | 运维脚本执行 |
| 定时任务 | 定时任务管理 |
| 算法模型 | 算法模型更新 |
| 业务运营 | 业务配置运营 |
| 特征变更 | 特征工程变更 |
| 实验变更 | 实验平台变更 |
| 黑屏变更 | 终端命令行变更 |
| 境外变更 | 海外地区变更 |

### 变更类型枚举值

| 值 | 说明 |
|---|---|
| 常规变更 | 按正常流程进行的变更 |
| 紧急变更 | 需要紧急处理的变更 |

### 变更方式枚举值

| 数字码 | 说明 |
|---|---|
| 1 | 仅白屏变更（通过 Web 界面操作） |
| 2 | 含黑屏变更（涉及终端命令行操作） |

### 模板类型枚举值

| 数字码 | 说明 |
|---|---|
| 1 | 自定义变更 |
| 2 | 运维变更 |
| 3 | Ones发布 |

### 管控事件状态枚举值

> `event list` / `event get` 返回的 `status` 字段为字符串枚举值。可执行审批操作的状态为 **AUDITING**。

| 枚举值 | 中文说明 |
|---|---|
| PRECHECKING | 预检中 |
| PRE_CHECK_ACCEPT | 预检通过 |
| PRE_CHECK_REJECT | 预检拦截 |
| PRECHECKED | 预检完成（待审核） |
| AUDITING | 待审核（可执行 accept / reject / skip-audit） |
| AFTERCHECKING | 后检中 |
| SUCCEED | 变更成功 |
| FAILED | 变更失败 |
| WARNING | 警告 |
| CANCELED | 已取消 |

### CloudTrail 事件结果枚举值

> `cloudtrail detail` 返回的 `eventResultState` 字段。

| 枚举值 | 中文说明 |
|---|---|
| SUCCEED | 执行成功 |
| FAILED | 执行失败 |
| TIMEOUT | 执行超时 |
| EXCEPTION | 执行异常 |
| CANCEL | 已取消 |

---

## user my - 当前用户信息

获取当前认证用户的基本信息，包含 orgPath（组织路径），可用于模板查询时的 `--org-path` 参数。

```
mcm user my [选项]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `-f, --format <format>` | string | 否 | 输出格式：`json`（默认）、`table`、`md` |

### 示例

```bash
# 默认 JSON 格式
mcm user my

# 人类可读的键值对格式
mcm user my --format table

# Markdown 格式
mcm user my --format md
```

### 返回字段

| 字段 | 说明 |
|---|---|
| `mis` / `loginName` | 用户 MIS 号 |
| `name` | 用户姓名 |
| `orgId` | 部门 ID |
| `orgPath` | 组织路径（如 `/1/2/3/12345`），可直接用于 `mcm template list --org-path` |
| `orgNamePath` | 组织名称路径（如 `美团/技术/平台/某团队`） |
