# 变更计划 API 数据结构参考

`mcm plan create`、`mcm plan update` 命令 `--data` 参数的完整 JSON 结构说明；`mcm template create`、`mcm template update` 的 `--data` 参数结构与此类似，可作为参考。

---

## 顶层结构

#### `name` — 计划名称
- 值类型：字符串，最多 100 个字符
- 示例：`"2026031920-测试计划模板"`

#### `templateId` — 模板 ID
- 值类型：整数
- 示例：`14018`

#### `baseFields` — 基础信息
- 值类型：字段对象数组，每项格式 `{"identify": "字段标识", "value": "字段值"}`
- 说明：**数组本身必须存在且非空**，但内部字段不需要全部提供，只传需要设置的字段即可，见下方 [baseFields 详解](#basefields)

#### `approveFields` — 审批人
- 值类型：字段对象数组，每项格式 `{"identify": "字段标识", "value": "字段值"}`
- 说明：**数组本身必须存在且非空**，但内部字段不需要全部提供，只传需要设置的字段即可，见下方 [approveFields 详解](#approvefields)

#### `noticeFields` — 周知信息
- 值类型：字段对象数组，每项格式 `{"identify": "字段标识", "value": "字段值"}`
- 说明：**数组本身必须存在且非空**，但内部字段不需要全部提供，只传需要设置的字段即可，见下方 [noticeFields 详解](#noticefields)

#### `contentFields` — 变更内容
- 值类型：字段对象数组，每项格式 `{"identify": "字段标识", "value": "字段值"}`
- 说明：**数组本身必须存在且非空**，但内部字段不需要全部提供，只传需要设置的字段即可，见下方 [contentFields 详解](#contentfields)

#### `steps` — 发布步骤
- 值类型：步骤对象数组
- 说明：**数组本身必须存在且非空**，见下方 [steps 详解](#steps)

#### `commonEditor` — 协同处理人（可选）
- 值类型：对象，包含 `isAllowCommonEdit` 和 `editor` 两个字段
- 说明：设置变更计划的协同处理人，允许多人协同编辑处理计划
- 示例：
```json
{
  "commonEditor": {
    "isAllowCommonEdit": true,
    "editor": [
      { "mis": "qinwei05" },
      { "mis": "weichunrong" }
    ]
  }
}
```
- 字段说明：
  - `isAllowCommonEdit`：是否允许协同编辑，布尔值，**默认为 true**
  - `editor`：协同处理人数组，每项包含 `mis` 字段（用户 MIS 号）

---

## baseFields

#### `env` — 变更环境
- 值类型：**支持多选，多个值用英文逗号分隔**。可选值：`prod`、`staging`、`test`、`dev`
- 示例：`"prod"`、`"prod,staging"`

#### `riskLevel` — 风险等级
- 值类型：单选。可选值：`低风险`、`高风险`
- 示例：`"低风险"`

#### `changeType` — 变更类型
- 值类型：单选。可选值：`常规变更`、`紧急变更`
- 示例：`"常规变更"`

#### `scene` — 变更场景
- 值类型：**支持多选，多个值用英文逗号分隔**。可选值：`代码发布`、`配置变更`、`数据变更`、`运维操作`、`定时任务`、`算法模型`、`业务运营`、`特征变更`、`实验变更`、`黑屏变更`
- 示例：`"代码发布"`、`"代码发布,配置变更,数据变更"`

#### `period` — 变更时间窗口
- 值类型：纯文本，开始和结束时间用英文逗号连接，无空格，格式 `yyyy-MM-dd HH:mm:ss,yyyy-MM-dd HH:mm:ss`
- 示例：`"2026-03-18 20:00:00,2026-03-18 22:00:00"`

#### `changeMode` — 变更方式
- 值类型：单选，通常由系统根据步骤类型自动推断，手动传时注意与步骤内容保持一致。可选值：`仅白屏变更`、`含黑屏变更`
- 示例：`"含黑屏变更"`

#### `changeArea` — 变更地区
- 值类型：单选，通常由系统根据步骤内容自动推断。可选值：`境内变更`、`境外变更`
- 示例：`"境内变更"`

---

## approveFields

#### `firstAuditor` — 一级审批人
- 值类型：**纯文本**，MIS 号，多人用英文逗号分隔
- 示例：`"zhangsan"`、`"zhangsan,lisi"`

#### `secondAuditor` — 二级审批人
- 值类型：**纯文本**，MIS 号，多人用英文逗号分隔；不传时传 `""`
- 示例：`"lisi"`

#### `thirdAuditor` — 三级审批人
- 值类型：**纯文本**，MIS 号，多人用英文逗号分隔；不传时传 `""`
- 示例：`"wangwu"`

---

## noticeFields

#### `noticeObject` — 周知大象群
- 值类型：**纯文本**，大象群 ID，**支持多个，多个值用英文逗号分隔**
- 示例：`"123456789"`、`"123456789,987654321"`

#### `noticeContent` — 周知内容
- 值类型：**富文本，支持 HTML**
- 示例：`"2026031820-cf-rule-server 优化"`

#### `cc` — 抄送人
- 值类型：**纯文本**，MIS 号，多人用英文逗号分隔；无抄送人传 `""`
- 示例：`"wangwu,zhaoliu"`

#### `handleGroup` — 处理群策略
- 值类型：枚举字符串。`"1"` 不建群，`"2"` 按计划建群
- 示例：`"2"`

---

## contentFields

---

#### `description` — 变更描述
- 值类型：**富文本，支持 HTML**
- 示例：`"<p>请描述变更的内容，涉及的范围</p>"`

---

#### `testReport` — 测试结果
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `radioValue`：`true` 测试通过，`false` 未通过
    - `textValue`：测试报告详细描述，**富文本，支持 HTML**
- 示例：
```json
{
  "identify": "testReport",
  "value": {
    "radioValue": true,
    "textValue": "<p>【测试结论】通过</p><p>【测试报告】请提供wiki链接</p>"
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

#### `effect` — 变更影响
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `hasEffect`：是否有影响，`true` / `false`
    - `effect`：影响描述，**富文本，支持 HTML**
    - `effectScope`：影响范围组织列表，仅用于前端展示；无范围传 `[]`。每项含以下字段，其中 `orgPath`、`orgNamePath` 为可选，系统后端不会解析此数组：
        - `orgId`：部门 ID（必传）
        - `orgPath`：多级部门 ID 路径，如 `"88888-153262-1456"`（可选）
        - `orgNamePath`：多级部门名称路径，如 `"核心本地商业/业务研发平台/外卖技术部"`（可选）
- 示例：
```json
{
  "identify": "effect",
  "value": {
    "hasEffect": true,
    "effect": "<p>【对下游的影响】是或否</p>",
    "effectScope": [
      {
        "orgId": "1456",
        "orgPath": "88888-153262-1456",
        "orgNamePath": "核心本地商业/业务研发平台/外卖技术部"
      }
    ]
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

#### `rollbackPlan` — 回滚方案
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `radioValue`：`true` 可回滚，`false` 不可回滚
    - `textValue`：回滚方案详细描述，**富文本，支持 HTML**
- 示例：
```json
{
  "identify": "rollbackPlan",
  "value": {
    "radioValue": true,
    "textValue": "<p>【是否可回滚】是</p><p>【回滚措施】...</p>"
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

#### `grayPlan` — 灰度方案
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `radioValue`：`true` 有灰度方案，`false` 无
    - `textValue`：灰度方案详细描述，**富文本，支持 HTML**；无灰度方案时传 `""`
- 示例：
```json
{
  "identify": "grayPlan",
  "value": {
    "radioValue": false,
    "textValue": ""
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

#### `background` — 变更背景
- 值类型：**纯文本**
- 示例：`"本次变更背景说明"`

---

#### `verify` — 发布验证步骤
- 值类型：**富文本，支持 HTML**
- 示例：`"<p>灰度验证：分批发布，观察各项监控指标</p>"`

---

#### `observationIndicators` — 观测指标
- 值类型：**富文本，支持 HTML**
- 示例：`"<p>关注 QPS、错误率</p>"`

---

#### `checkListAfterChange` — 变更后检查项
- 值类型：**富文本，支持 HTML**
- 示例：`"<p>确认服务状态正常</p>"`

---

#### `domain` — 变更域名
- 值类型：**纯文本**，多个用英文逗号分隔
- 示例：`"https://a.sankuai.com"`、`"https://a.sankuai.com,https://b.sankuai.com"`

---

#### `gitAddr` — 代码地址（PR 链接）
- 值类型：**纯文本**，多个用英文逗号分隔
- 示例：`"https://dev.sankuai.com/code/repo-detail/dpop-app/mcm-cli/pr/12/overview"`

---

#### `appkey` — 变更服务 AppKey
- 值类型：**纯文本**，多个用英文逗号分隔
- 示例：`"com.sankuai.cf.rule.server"`、`"com.sankuai.cf.rule.server,com.sankuai.cf.component.server,com.sankuai.mcm.cli"`

---

#### `sop` — 操作 SOP 链接
- 值类型：**纯文本**，多个用英文逗号分隔
- 示例：`"https://km.sankuai.com/collabpage/2750207309"`、`"https://km.sankuai.com/collabpage/2750207309,https://km.sankuai.com/collabpage/2750207310"`

---

#### `onesIssue` — 关联 Ones 工作项
- 值类型：**纯文本**，多个 ID 用英文逗号分隔
- 示例：`"93836074"`、`"93836074,93819416"`

---

#### `checklist` — 通用自检项
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `title`：自检项标题，固定传 `"通用自检项"`
    - `type`：固定传 `"SELF_CHECK"`
    - `items`：检查项列表，每项含：
        - `title`：检查项名称
        - `status`：`"NO_CONFIRM"`（待确认）、`"CONFIRMED"`（已确认）、`"NO_NEED"`（不需要）
        - `content`：检查项内容
        - `desc`：补充说明，可传 `""`
        - `fontId`：序号，从 1 递增
- 示例：
```json
{
  "identify": "checklist",
  "value": {
    "title": "通用自检项",
    "type": "SELF_CHECK",
    "items": [
      {
        "title": "检查项1",
        "status": "NO_CONFIRM",
        "content": "检查内容",
        "desc": "",
        "fontId": 1
      }
    ]
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

#### `alarmMonitor` — 告警监控配置
- 值类型：**JSON 序列化字符串**
- JSON 内部结构：
    - `planId`：传 `null` 即可
    - `dashboards`：关联大盘列表，每项含 `id`、`name`、`url`、`isCore`、`chartCount`、`nameSpace`；无大盘传 `[]`
    - `enableAppKeyAlarm`：是否开启 AppKey 关联告警，`true` / `false`
    - `type`：告警关联类型，如 `"AUTO_BY_PLAN"`
    - `levels`：关注的告警级别，如 `["P0", "P1", "P9"]`
- 示例：
```json
{
  "identify": "alarmMonitor",
  "value": {
    "planId": null,
    "dashboards": [
      {
        "id": 116670,
        "name": "MCM-变更计划-使用大盘",
        "url": "https://raptor.mws.sankuai.com/dashboard/list?dashboard=116670&isCore=false",
        "isCore": false,
        "chartCount": 8,
        "nameSpace": "基础研发平台/服务运维部"
      }
    ],
    "enableAppKeyAlarm": true,
    "type": "AUTO_BY_PLAN",
    "levels": ["P0", "P1", "P9"]
  }
}
```
> 注意：实际传参时 `value` 为 JSON 序列化字符串，上方为展开示意。

---

## steps

### 步骤顶层字段

#### `title` — 步骤标题
- 是否必填：**必填**
- 值类型：字符串，最多 100 个字符
- 示例：`"Plus发布-第一批"`

#### `tool` — 工具名称
- 是否必填：**必填**
- 值类型：字符串，须与 `stepType` 对应，见下方 stepType 枚举
- 示例：`"Plus"`

#### `stepType` — 步骤类型
- 是否必填：**必填**
- 值类型：枚举字符串，见下方 stepType 与 tool 对应关系
- 示例：`"PLUS"`

#### `allowedOperator` — 允许操作人
- 是否必填：**必填**
- 值类型：字符串数组，默认使用`"SPONSOR"` 表示计划发起人，也可指定具体 MIS 号，最多 20 人
- 示例：`["SPONSOR"]`、`["SPONSOR", "zhangsan"]`

#### `action` — 步骤说明
- 是否必填：**必填**
- 值类型：**富文本，支持 HTML**；可为空字符串 `""`，但是不建议留空，最佳实践为结合本次步骤的实际变更内容进行具体描述，确保审批人和执行人能够从步骤说明中直接了解本次该步骤的发布内容和目的。
- 示例：`"<p>灰度发布第一批</p>"`

#### `estimateStartTime` — 预计开始时间
- 是否必填：选填
- 值类型：纯文本，格式 `yyyy-MM-dd HH:mm:ss`，须为将来时间
- 示例：`"2026-03-19 20:00:00"`

#### `stepOperation` — 步骤操作配置
- 是否必填：**必填**（NORMAL 步骤传 `{"items": []}`，其他类型步骤须传）
- 值类型：对象，包含 `items` 数组，不同 `stepType` 的 `items` 结构不同，见下方各步骤类型说明
- 示例：`{"items": [...]}`

### stepType 与 tool 对应关系

- `NORMAL` → `tool: ""` 或任意工具名，无工具集成
- `PLUS` → `tool: "Plus"`：Plus 代码发布
- `LION` → `tool: "Lion"`：Lion 配置变更
- `RDS` → `tool: "RDS"`：RDS 数据库变更
- `TERMINAL` → `tool: "Terminal"`：黑屏命令执行
- `CRANE` → `tool: "Crane"`：Crane 定时任务变更
- `TURING` → `tool: "Turing"`：图灵算法包变更
- `OBSERVATION` → `tool: "Raptor"` 或 `"Observation"`：观测步骤

---

### NORMAL — 常规步骤

`stepOperation` 传 `{"items": []}` 即可。

```json
{
  "title": "普通步骤",
  "tool": "",
  "action": "<p>步骤说明</p>",
  "stepType": "NORMAL",
  "allowedOperator": ["SPONSOR"],
  "stepOperation": {"items": []}
}
```

---

### PLUS — Plus 发布步骤

`stepOperation.items` 每个 item 的字段：

#### `operationType` — 发布类型
- 是否必填：**必填**
- 值类型：枚举字符串。`"GRAY_DEPLOY"` 全量发布，`"GRAY_GROUP_DEPLOY"` 分组发布
- 示例：`"GRAY_DEPLOY"`

#### `appKey` — 服务 AppKey
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"com.sankuai.cf.rule.server"`

#### `env` — 发布环境
- 是否必填：**必填**
- 值类型：纯文本，单值
- 示例：`"prod"`

#### `repos` — 仓库路径
- 是否必填：**必填**
- 值类型：纯文本。格式为：PROJECT/REPO
- 示例：`"dpop-app/cf"`

#### `releaseType` — 发布类型
- 是否必填：**必填**
- 值类型：枚举字符串。`"BRANCH"` 分支发布，`"TAG"` tag 发布
- 示例：`"BRANCH"`

#### `releaseValue` — 发布值
- 是否必填：**必填**
- 值类型：纯文本，分支名或 tag 名
- 示例：`"master"`、`"release-tag.20260318190527520.limingze07"`

#### `groupRuleName` — 分组规则名
- 是否必填：**必填**
- 值类型：纯文本，三种场景值不同，见下方说明
- 示例：`""`（全量）、`"分组发布"`（系统分组）、`"自定义分组"`（自定义）

#### `groups` — 分组编号列表
- 是否必填：**必填**
- 值类型：整数数组，三种场景值不同，见下方说明；最后一批剩余机器用 `[-1]` 表示
- 示例：`[]`（全量）、`[1]`（第一批）、`[-1]`（剩余批次）

#### `groupNames` — 分组显示名列表
- 是否必填：**必填**
- 值类型：字符串数组，系统分组时由系统填充，全量和自定义分组传 `[]`
- 示例：`[]`、`["批次1"]`

#### `groupsDesc` — 分组描述列表
- 是否必填：**必填**
- 值类型：字符串数组，系统分组时由系统填充，全量和自定义分组传 `[]`
- 示例：`[]`、`["批次1：并发度，按全局百分比机器分布20.0%"]`

#### `prList` — 关联 PR 列表
- 是否必填：选填
- 值类型：对象数组，每项含 `id`、`title`、`sourceBranch`、`targetBranch`、`link`、`pipelineLink`、`state`；无关联 PR 传 `[]`
- 示例1：`[]`
- 示例2：

#### 三种发布场景

**① 全量发布（`GRAY_DEPLOY`）**：一次性发布所有机器
- `groupRuleName`: `""`，`groups`: `[]`，`groupNames`: `[]`，`groupsDesc`: `[]`

```json
{
  "operationType": "GRAY_DEPLOY",
  "appKey": "com.sankuai.cf.rule.server",
  "env": "prod",
  "repos": "dpop-app/cf",
  "releaseType": "BRANCH",
  "releaseValue": "master",
  "groupRuleName": "",
  "groups": [],
  "groupNames": [],
  "groupsDesc": [],
  "prList": []
}
```

**② 系统分组（`GRAY_GROUP_DEPLOY`）**：按 Plus 预置的命名分组规则分批
- `groupRuleName`: 从Plus发布系统分组信息获取， 规则名（如 `"分组发布"`），`groupNames` 和 `groupsDesc` 也由Plus系统数据提供。也可从该 appKey 历史计划中取值，之前存在Plus分组数据写入，每个Appkey发布分组数据不同，不可跨 appKey 复用

```json
{
  "operationType": "GRAY_GROUP_DEPLOY",
  "appKey": "com.sankuai.cf.schedule.server",
  "env": "prod",
  "repos": "dpop-app/cf",
  "releaseType": "BRANCH",
  "releaseValue": "master",
  "groupRuleName": "分组发布",
  "groups": [1],
  "groupNames": ["批次1"],
  "groupsDesc": ["批次1：并发度，按全局百分比机器分布20.0%"],
  "prList": []
}
```

**③ 自定义分组（`GRAY_GROUP_DEPLOY`）**：想分为几个分组发布，可自定义填写
- `groupRuleName` 固定为 `"自定义分组"`，`groupNames` 和 `groupsDesc` 始终为 `[]`
- 最后一批用 `[-1]` 表示剩余所有机器

```json
{
  "operationType": "GRAY_GROUP_DEPLOY",
  "appKey": "com.sankuai.cf.rule.server",
  "env": "prod",
  "repos": "dpop-app/cf",
  "releaseType": "BRANCH",
  "releaseValue": "master",
  "groupRuleName": "自定义分组",
  "groups": [1],
  "groupNames": [],
  "groupsDesc": [],
  "prList": []
}
```

---

### LION — Lion 配置变更步骤

`stepOperation.items` 每个 item 的字段：

#### `operationType` — 操作类型
- 是否必填：**必填**
- 值类型：枚举字符串。`"ADD_CONFIG"` 新增，`"UPDATE_CONFIG"` 修改，`"DELETE_CONFIG"` 删除
- 示例：`"ADD_CONFIG"`

#### `appKey` — 服务 AppKey
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"com.sankuai.cf.component.server"`

#### `env` — 环境
- 是否必填：**必填**
- 值类型：纯文本，单值
- 示例：`"prod"`

#### `key` — 配置 Key
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"CONFIG_KEY"`

#### `dataType` — 配置值类型
- 是否必填：**必填**
- 值类型：枚举字符串。可选值：`String`、`Number`、`Boolean`、`Integer`、`Float`、`Double`、`JSON`、`List`、`Map`
- 示例：`"String"`

#### `value` — 配置值
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"123123"`

#### `set` — SET
- 是否必填：选填
- 值类型：纯文本，默认 `"default"`
- 示例：`"default"`

#### `group` — 当前分组
- 是否必填：选填
- 值类型：纯文本，默认 `"default"`
- 示例：`"default"`

#### `groupTags` — 业务分组
- 是否必填：选填
- 值类型：纯文本，默认 `"La:default"`
- 示例：`"La:default"`

#### `swimLane` — 泳道
- 是否必填：选填
- 值类型：纯文本，默认 `"default"`
- 示例：`"default"`

#### `region` — 地域
- 是否必填：选填
- 值类型：纯文本，默认 `"default"`
- 示例：`"default"`

#### `desc` — 配置描述
- 是否必填：选填
- 值类型：纯文本，支持 `\n` 换行
- 示例：`"【使用场景】xxx\n【值描述】\n【关联需求】"`

```json
{
  "title": "Lion变更",
  "tool": "Lion",
  "action": "<p>新增配置项</p>",
  "stepType": "LION",
  "allowedOperator": ["SPONSOR"],
  "stepOperation": {
    "items": [
      {
        "operationType": "ADD_CONFIG",
        "appKey": "com.sankuai.cf.component.server",
        "env": "prod",
        "key": "ETST",
        "dataType": "String",
        "value": "123123",
        "set": "default",
        "group": "default",
        "groupTags": "La:default",
        "swimLane": "default",
        "region": "default",
        "desc": "【使用场景】xxx\n【值描述】\n【关联需求】"
      }
    ]
  }
}
```

---

### RDS — RDS 数据库变更步骤

`stepOperation.items` 每个 item 的字段：

#### `operationType` — 操作类型
- 是否必填：**必填**
- 值类型：固定传 `"SQL_EXECUTE"`
- 示例：`"SQL_EXECUTE"`

#### `env` — 环境
- 是否必填：**必填**
- 值类型：纯文本，单值
- 示例：`"prod"`

#### `clusterName` — 数据库集群名
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"cf"`

#### `dbName` — 数据库名
- 是否必填：**必填**
- 值类型：纯文本
- 示例：`"cf"`

#### `sql` — SQL 语句
- 是否必填：**必填**
- 值类型：纯文本，系统会自动计算 `sqlMd5`
- 示例：`"select * from event;"`


#### `rollbackSql` — 回滚 SQL
- 是否必填：选填
- 值类型：纯文本
- 示例：`"select * from event;"`

```json
{
  "title": "RDS变更",
  "tool": "RDS",
  "action": "<p>执行SQL</p>",
  "stepType": "RDS",
  "allowedOperator": ["SPONSOR"],
  "stepOperation": {
    "items": [
      {
        "operationType": "SQL_EXECUTE",
        "env": "prod",
        "clusterName": "cf",
        "dbName": "cf",
        "sql": "select * from event;",
        "rollbackSql": "select * from event;"
      }
    ]
  }
}
```

---

### TERMINAL — 黑屏变更步骤

> ⚠️ `allowedOperator` 通常需要包含至少 2 名操作人（双人操作安全要求）。

`stepOperation.items` 每个 item 的字段：

#### `appKey` — 主要变更服务 AppKey
- 是否必填：**必填**
- 值类型：纯文本,多个服务逗号分隔
- 示例：`"com.sankuai.avatar.gateway.server,com.sankuai.avatar.gateway"`

#### `appkeyList` — 变更 AppKey 列表
- 是否必填：**必填**
- 值类型：字符串数组
- 示例：`["com.sankuai.avatar.gateway.server","com.sankuai.avatar.gateway"]`

#### `command` — 执行命令
- 是否必填：**必填**
- 值类型：纯文本，系统会自动计算 `commandMd5`
- 示例：`"ls"`

```json
{
  "title": "黑屏变更",
  "tool": "Terminal",
  "action": "<p>执行运维命令</p>",
  "stepType": "TERMINAL",
  "allowedOperator": ["SPONSOR", "jinweilong02"],
  "stepOperation": {
    "items": [
      {
        "appKey": "com.sankuai.avatar.gateway.server",
        "appkeyList": ["com.sankuai.avatar.gateway.server"],
        "command": "ls"
      }
    ]
  }
}
```

---

### OBSERVATION — 观测步骤

`stepOperation.items` 每个 item 的字段：

#### `operationType` — 操作类型
- 是否必填：**必填**
- 值类型：固定传 `"OBSERVATION"`
- 示例：`"OBSERVATION"`

#### `duration` — 观测时长
- 是否必填：**必填**
- 值类型：整数
- 示例：`30`

#### `durationUnit` — 时长单位
- 是否必填：**必填**
- 值类型：枚举字符串。`"MINUTE"` 分钟，`"HOUR"` 小时，`"DAY"` 天
- 示例：`"MINUTE"`

```json
{
  "title": "变更后观测和验收",
  "tool": "Raptor",
  "action": "",
  "stepType": "OBSERVATION",
  "allowedOperator": ["SPONSOR"],
  "stepOperation": {
    "items": [
      {
        "operationType": "OBSERVATION",
        "duration": 30,
        "durationUnit": "MINUTE"
      }
    ]
  }
}
```

---

## 完整 JSON 示例
包含 NORMAL、LION、PLUS（系统分组）、PLUS（自定义分组）、PLUS（全量）、RDS、TERMINAL、OBSERVATION 八种步骤类型：
```json
{
  "name": "2026031920-测试计划模板",
  "templateId": 14018,
  "baseFields": [
    { "identify": "env",        "value": "prod" },
    { "identify": "riskLevel",  "value": "低风险" },
    { "identify": "changeType", "value": "常规变更" },
    { "identify": "scene",      "value": "代码发布,配置变更,数据变更,黑屏变更" },
    { "identify": "period",     "value": "2026-03-19 20:00:00,2026-03-19 22:00:00" }
  ],

  "approveFields": [
    { "identify": "firstAuditor",  "value": "yangkaiqi04,jie.li.sh" },
    { "identify": "secondAuditor", "value": "" },
    { "identify": "thirdAuditor",  "value": "" }
  ],

  "noticeFields": [
    { "identify": "noticeObject",  "value": "123,345" },
    { "identify": "handleGroup",   "value": "2" },
    { "identify": "noticeContent", "value": "2026031920-测试计划模板" },
    { "identify": "cc",            "value": "qinwei05,jinweilong02,jie.li.sh" }
  ],

  "contentFields": [
    { "identify": "description",  "value": "<p>请描述变更的内容，涉及的范围</p>" },
    { "identify": "testReport",   "value": "{\"radioValue\":true,\"textValue\":\"<p>【测试结论】通过</p>\"}" },
    { "identify": "rollbackPlan", "value": "{\"radioValue\":true,\"textValue\":\"<p>【是否可回滚】是</p>\"}" },
    { "identify": "appkey",       "value": "com.sankuai.cf.component.server,com.sankuai.cf.rule.server" },
    { "identify": "grayPlan",     "value": "{\"radioValue\":false,\"textValue\":\"\"}" },
    { "identify": "onesIssue",    "value": "93836074,93819416" },
    { "identify": "effect",       "value": "{\"hasEffect\":true,\"effect\":\"<p>影响说明</p>\",\"effectScope\":[]}" },
    { "identify": "background",   "value": "变更背景说明" },
    { "identify": "domain",       "value": "https://example.com" },
    { "identify": "gitAddr",      "value": "https://dev.sankuai.com/code/repo-detail/dpop-app/cf/pr/1/overview" },
    { "identify": "verify",       "value": "观察日志，确认无异常" },
    { "identify": "observationIndicators", "value": "<p>关注 QPS、错误率</p>" },
    { "identify": "checkListAfterChange",  "value": "<p>确认服务正常</p>" }
  ],

  "commonEditor": {
    "isAllowCommonEdit": true,
    "editor": [
      { "mis": "qinwei05" },
      { "mis": "weichunrong" }
    ]
  },

  "steps": [
    {
      "title": "普通步骤",
      "tool": "Avatar",
      "action": "<p>步骤说明</p>",
      "stepType": "NORMAL",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {"items": []}
    },
    {
      "title": "Lion变更",
      "tool": "Lion",
      "action": "<p>新增配置</p>",
      "stepType": "LION",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "ADD_CONFIG",
            "appKey": "com.sankuai.cf.component.server",
            "env": "prod",
            "key": "ETST",
            "dataType": "String",
            "value": "123123",
            "set": "default",
            "group": "default",
            "groupTags": "La:default",
            "swimLane": "default",
            "region": "default",
            "desc": "【使用场景】123123\n【值描述】\n【关联需求】"
          }
        ]
      }
    },
    {
      "title": "Plus发布（系统分组-批次1）",
      "tool": "Plus",
      "action": "<p>系统分组发布第一批</p>",
      "stepType": "PLUS",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "GRAY_GROUP_DEPLOY",
            "appKey": "com.sankuai.cf.schedule.server",
            "env": "prod",
            "repos": "dpop-app/cf",
            "releaseType": "BRANCH",
            "releaseValue": "master",
            "groupRuleName": "分组发布",
            "groups": [1],
            "groupNames": ["批次1"],
            "groupsDesc": ["批次1：并发度，按全局百分比机器分布20.0%"],
            "prList": []
          }
        ]
      }
    },
    {
      "title": "Plus发布（自定义分组-第一批）",
      "tool": "Plus",
      "action": "<p>自定义分组发布第一批</p>",
      "stepType": "PLUS",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "GRAY_GROUP_DEPLOY",
            "appKey": "com.sankuai.cf.rule.server",
            "env": "prod",
            "repos": "dpop-app/cf",
            "releaseType": "BRANCH",
            "releaseValue": "master",
            "groupRuleName": "自定义分组",
            "groups": [1],
            "groupNames": [],
            "groupsDesc": [],
            "prList": []
          }
        ]
      }
    },
    {
      "title": "Plus发布（全量）",
      "tool": "Plus",
      "action": "<p>全量发布</p>",
      "stepType": "PLUS",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "GRAY_DEPLOY",
            "appKey": "com.sankuai.cf.component.server",
            "env": "prod",
            "repos": "dpop-app/cf",
            "releaseType": "BRANCH",
            "releaseValue": "master",
            "groupRuleName": "",
            "groups": [],
            "groupNames": [],
            "groupsDesc": [],
            "prList": []
          }
        ]
      }
    },
    {
      "title": "RDS变更",
      "tool": "RDS",
      "action": "<p>执行SQL</p>",
      "stepType": "RDS",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "SQL_EXECUTE",
            "env": "prod",
            "clusterName": "cf",
            "dbName": "cf",
            "tableName": "event",
            "sql": "select * from event;",
            "rollbackSql": "select * from event;"
          }
        ]
      }
    },
    {
      "title": "黑屏变更",
      "tool": "Terminal",
      "action": "<p>执行运维命令</p>",
      "stepType": "TERMINAL",
      "allowedOperator": ["SPONSOR", "jinweilong02"],
      "stepOperation": {
        "items": [
          {
            "appKey": "com.sankuai.avatar.gateway.server",
            "appkeyList": ["com.sankuai.avatar.gateway.server"],
            "command": "ls"
          }
        ]
      }
    },
    {
      "title": "变更后观测和验收",
      "tool": "Raptor",
      "action": "",
      "stepType": "OBSERVATION",
      "allowedOperator": ["SPONSOR"],
      "stepOperation": {
        "items": [
          {
            "operationType": "OBSERVATION",
            "duration": 30,
            "durationUnit": "MINUTE"
          }
        ]
      }
    }
  ]
}
```
