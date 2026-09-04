# 多维表格高级权限

多维表格高级权限是 XTable 自己的权限体系，不等同于学城文档权限。用户明确提到"多维表格高级权限"、"默认角色"、"自定义角色"、"多维表格管理员"、"给角色加人/删人/加组织/删组织/加群/删群/加邮件组/删邮件组/加应用/删应用"时，优先使用本页规则。

> **禁止修改仪表盘高级权限**：当前 skill 的角色权限写入能力仅支持数据表。`createAdvancedPermRole`、`updateAdvancedPermRolePermissions` 的 `permissionDetails` 不得使用仪表盘 ID，也不得新增、修改或删除仪表盘权限项。查询接口可能返回既有仪表盘权限，这些内容只允许读取；用户要求修改时应告知当前不支持并停止写操作。

**原有稳定能力口径：支持查询高级权限开关状态，支持开启/关闭高级权限，支持查询角色配置，支持给管理员和自定义角色添加成员，支持从自定义角色删除成员。**

在原有能力基础上，新增自定义角色生命周期、数据表/行/列/视图权限配置、管理员及默认角色成员删除、默认角色成员添加、成员角色反查与调整，以及当前用户实际表权限查询。

## 一期能力范围

当前支持：

- 查询高级权限开关状态
- 开启或关闭高级权限开关
- 查询管理员、默认角色、自定义角色配置详情
- 通过自定义角色名称精确匹配 `roleId`
- 给管理员、默认角色、自定义角色添加人员
- 给管理员、默认角色、自定义角色添加组织
- 给管理员、默认角色、自定义角色添加大象群、邮件组、应用
- 从默认角色、自定义角色删除人员
- 从默认角色、自定义角色删除组织
- 从默认角色、自定义角色删除大象群、邮件组、应用

## 二期新增能力范围

- 新增、删除、重命名自定义角色
- 修改默认角色或自定义角色的数据表级权限
- 修改行权限、列权限、视图权限等 `extraConfig` 结构化配置
- 从管理员角色删除成员
- 给默认角色添加或删除成员
- 搜索某个成员当前属于哪些高级权限角色，并覆盖调整角色列表
- 查询当前用户在指定数据表上的实际生效权限

仍未完成的能力见本文末尾"未完成能力记录"。

## 角色与成员枚举

角色类型：

| 参数值 | 含义 |
|---|---|
| `admin` / `0` | 管理员 |
| `default` / `1` | 默认角色 |
| `custom` / `2` | 自定义角色 |
| `all` | 全部角色类型（当前不作为对外查询能力使用） |

权限组类型：

| 值 | 含义 |
|---|---|
| `-1` | 无权限 |
| `0` | 可浏览、评论 |
| `2` | 可编辑 |
| `4` | 可管理 |
| `5` | 仅浏览 |

> 此表对齐 Data API 消费的 XTable 高级权限模型。`1`、`3` 属于另一套通用文档权限枚举，不可用于多维表格高级权限角色配置。

## 命令使用

### 添加角色成员

默认角色不传 `--roleId` 时会自动查询唯一默认角色：

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType default \
  --person "zhangsan"
```

添加人员：

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --person "zhangsan,lisi"
```

添加组织（`orgId` 支持数字 ID 或部门全路径；传部门全路径时会自动解析为真实组织 ID）。组织还支持选择合同类型、岗位族、国家/地区：

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --orgs '[{"orgId":"美团/核心本地商业","contractTypes":["全日制"],"orgRoles":["行政"],"country":["CHN"]}]'
```

其中 `contractTypes` 支持合同类型 key 或名称，例如 `101`、`全日制`、`实习生`；`orgRoles` 支持岗位族 key 或名称，例如 `行政`，空数组表示所有职位；`country` 是国家/地区 code。未传时默认按前端新增组织逻辑补齐为 `contractTypes=["101"]`、`orgRoles=[]`、`country=["CHN"]`。

添加大象群、邮件组、应用：

```bash
oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --xmGroupIds "70411238253"

oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --mails "team@meituan.com"

oa-skills citadel-database addAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --appIds "appId1,appId2"
```

### 查询高级权限开关状态

```bash
oa-skills citadel-database getAdvancedPermStatus \
  --contentId "4295357904"
```

状态值含义：

| 值 | 含义 |
|---|---|
| `0` | 未初始化 |
| `1` | 已开启 |
| `2` | 已关闭 |

### 开启或关闭高级权限

开启高级权限：

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status enabled
```

开启前必须先查询高级权限状态：

```bash
oa-skills citadel-database getAdvancedPermStatus \
  --contentId "4295357904"
```

如果状态是 `0`（未初始化），表示首次开启，可以直接开启，不传 `--preserveOriginalRole`。

如果状态不是 `0`，表示不是首次开启，必须继续查询自定义角色内容：

```bash
oa-skills citadel-database listAdvancedPermRoles \
  --contentId "4295357904" \
  --roleType custom \
  --raw
```

如果没有自定义角色成员，开启时自动按保留处理，CLI 会拼接 `preserveOriginalRole=true`，也可以显式传 `--preserveOriginalRole true`。

如果存在任意自定义角色且 `members.length > 0`，说明已有历史角色成员，必须先询问用户是否保留。确认保留时传 `--preserveOriginalRole true`：

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status enabled \
  --preserveOriginalRole true
```

确认不保留时传 `--preserveOriginalRole false`：

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status enabled \
  --preserveOriginalRole false
```

CLI 也会做兜底保护：开启时如果未传 `--preserveOriginalRole`，会先查询高级权限状态；首次开启不带参数，非首次开启会继续查自定义角色。若无成员则自动补 `preserveOriginalRole=true`；若有成员则停止执行并要求显式传 `true` 或 `false`。

关闭高级权限：

```bash
oa-skills citadel-database updateAdvancedPermStatus \
  --contentId "4295357904" \
  --status disabled
```

**高风险确认要求**：开启或关闭高级权限会改变多维表格实际生效权限。Agent 执行前必须向用户复述目标多维表格 `contentId`、目标状态、已有自定义角色成员检查结果，以及关闭后角色权限将失效并按文档权限访问全部内容；用户明确确认后才执行。未确认时停止，不得调用写接口。

### 删除角色成员

删除默认角色成员（不传 `--roleId` 时自动查询唯一默认角色）：

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType default \
  --person "zhangsan"
```

删除自定义角色人员：

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --person "zhangsan,lisi"
```

删除自定义角色组织（`orgId` 支持数字 ID 或部门全路径）：

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --orgs '[{"orgId":"美团/核心本地商业"}]'
```

删除自定义角色大象群、邮件组、应用：

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --xmGroupIds "70411238253"

oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --mails "team@meituan.com"

oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "自定义角色1" \
  --appIds "appId1,appId2"
```

二期补充：支持删除管理员成员。删除前先读取角色详情，核对实际匹配成员并获得明确确认。

```bash
oa-skills citadel-database deleteAdvancedRoleMembers \
  --contentId "4295357904" \
  --roleType admin \
  --person "zhangsan"
```

## 二期新增命令

以下角色权限写入示例中的 `tableId` 必须是数据表 ID，不能是仪表盘 ID。

### 新增、重命名、删除自定义角色

```bash
oa-skills citadel-database createAdvancedPermRole \
  --contentId "4295357904" \
  --roleName "运营角色" \
  --permissionDetails '[{"tableId":123456,"permGroupType":5}]'

oa-skills citadel-database renameAdvancedPermRole \
  --contentId "4295357904" \
  --roleName "运营角色" \
  --newRoleName "运营只读"

oa-skills citadel-database deleteAdvancedPermRole \
  --contentId "4295357904" \
  --roleName "运营只读"
```

自定义角色可用 `--roleId` 或 `--roleName` 精确定位；名称重复时必须使用 `--roleId`。重命名或删除前先读取角色详情；删除必须获得明确确认。

### 修改角色表级、行级、列级、视图权限

`--permissionDetails` 接受 JSON 数组，也可以使用 `--permissionDetailsFile <path>`；两者不能同时传。

详细权限结构必须与 `permGroupType` 对应：

| `permGroupType` | `rowOperation` | 指定行 `rowRanges` | `columnRanges` 值 | `viewOperation` |
|---|---:|---|---|---:|
| `0` 可浏览、评论 / `5` 仅浏览 | `1` | 只能包含 key `1` | `0/1` | `1` |
| `2` 可编辑 | `5/7/13/15` | 必须同时且仅包含 key `4/8` | `0/1/21` | `1/15` |
| `-1` 无权限 / `4` 可管理 | 不配置 | 不配置 | 不配置 | 不配置 |

可浏览、评论或仅浏览的指定行示例：

```json
{
  "tableId": 123456,
  "permGroupType": 5,
  "extraConfig": {
    "rowOperation": 1,
    "rowRanges": {
      "1": {
        "filter": ["and", [["notnull", 1001, null, 3]]],
        "others": 0
      }
    },
    "columnRanges": { "1001": 1, "1002": 0 },
    "viewOperation": 1
  }
}
```

可浏览权限中，`rowRanges.*.others` 省略时按学城端默认值补为 `0`；`0` 表示指定行外不可查看，`1` 表示指定行外可查看。

可编辑权限示例：

```json
[
  {
    "tableId": 123456,
    "permGroupType": 2,
    "extraConfig": {
      "rowOperation": 15,
      "rowRanges": {
        "4": {
          "filter": ["or", [["contains", 1001, "[2001]", 3]]],
          "others": 0
        },
        "8": {
          "filter": ["or", [["contains", 1001, "[2001]", 3]]],
          "others": 0
        }
      },
      "columnRanges": { "1001": 1, "1002": 21 },
      "viewOperation": 1
    }
  }
]
```

- `rowOperation`：可编辑权限仅支持 `5`（不勾选新增/删除）、`7`（可新增）、`13`（可删除）、`15`（可新增且可删除）。
- `rowRanges`：按操作位配置行过滤范围；可编辑角色的指定行范围必须同时且仅包含 key `4`（可编辑）和 `8`（可删除），两份配置必须一致。省略 `rowRanges` 表示全部行。
- `rowRanges.*.others`：`0` 表示指定行外不可查看，`1` 表示指定行外可查看；可编辑权限省略时按学城端默认值补为 `1`。
- 筛选连接符默认值：用户未指定“任一/全部”时，`rowOperation=7/15`（包含可新增）使用 `or`，`rowOperation=5/13` 以及可浏览权限使用 `and`；用户明确指定时以用户选择为准。
- `columnRanges`：key 为列 ID；可编辑权限的 value 仅支持 `0`（不可查看）、`1`（仅查看）、`21`（可查看、编辑及新增时编辑）。省略表示全部列。
- `viewOperation`：可编辑权限仅支持 `1`（关闭视图管理）或 `15`（打开视图管理）。
- 操作位：`0=None`、`1=Visible`、`2=Addable`、`4=Editable`、`8=Deletable`、`16=EditableOnAdd`；组合权限使用按位或后的数字。
- `permGroupType=-1/4`：不支持 `extraConfig`；更新时若要明确清除旧配置，可以传 `extraConfig:null`。

可编辑权限使用指定行范围且包含可新增操作时，CLI 会先读取 `/api/collaboration/xtable/{tableId}/meta?config=0`，自动查找创建人系统列，并把系统创建人条件放在 key `4` 和 `8` 的筛选第一条：

- `rowOperation=7/15`：创建人条件固定为“行创建人包含当前用户”，已有条件会移动到第一条；重复或修改固定条件时拒绝写入。
- `rowOperation=5/13`：没有可新增权限，不强制创建人条件，也不会自动补回已删除的默认条件；传入的筛选条件按原样保留。

省略 `rowRanges` 表示全部行，不生成任何筛选条件。

#### 指定行筛选格式（写入前必读）

高级权限 `extraConfig.rowRanges.*.filter` 使用 Data API 消费的 XTable 权限模型存储结构，即 `FILTER_CONFIG` 元组：

```text
["and" | "or", [
  [operator, colId, value, colType],
  ["and" | "or", [...嵌套条件]]
]]
```

- `and` 表示“符合全部条件”，`or` 表示“符合任一条件”。
- 条件叶子为 `[operator, colId, value, colType]`；操作符、value 和 `colType` 应与 Data API 使用的目标列模型定义匹配。
- 普通数据查询命令 `queryTableData --filter` 使用 Data API 对外的 `{ "conjunction": ..., "conditions": ... }` 对象 DTO，Data API 会将它转换为 `FILTER_CONFIG`。该对象 DTO 不能未经转换直接写入高级权限 `extraConfig`。
- 构造普通列条件前，建议执行 `getTableMeta --tableId <id>` 获取真实 `colId`、列类型及选项信息。可编辑权限的指定行范围由 CLI 自动读取创建人列 ID 和类型，无需手工填写。
- CLI 会校验可编辑权限的行操作、行范围、列权限和视图权限结构，但不会校验普通筛选条件中的选项 ID 是否真实存在。

需要构造列筛选条件时，可先读取表结构和有效选项 ID：

```bash
oa-skills citadel-database getTableMeta \
  --tableId "123456" \
  --raw \
  --mis hekai13
```

例如“状态包含选项 2001，且满足全部条件”：

```bash
oa-skills citadel-database updateAdvancedPermRolePermissions \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "运营角色" \
  --permissionDetails '[{"tableId":123456,"permGroupType":2,"extraConfig":{"rowOperation":15,"rowRanges":{"4":{"filter":["or",[["contains",1001,"[2001]",3]]],"others":0},"8":{"filter":["or",[["contains",1001,"[2001]",3]]],"others":0}},"viewOperation":1}}]' \
  --mis hekai13
```

默认按 `tableId` 与现有权限合并，并保留没有传入的数据表：

- `permGroupType` 不变且省略 `extraConfig`：保留该表现有详细权限配置。
- 切换 `permGroupType` 且省略 `extraConfig`：清除与新权限组不兼容的旧详细配置，使用新权限组默认配置。
- 传入 JSON 对象：覆盖该表详细权限配置。
- 传入 `extraConfig: null`：删除该表整份详细权限配置；CLI 最终请求会省略该字段。

```bash
oa-skills citadel-database updateAdvancedPermRolePermissions \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "运营角色" \
  --permissionDetailsFile ./permission-details.json
```

删除某张表的整份行/列/视图详细权限配置，同时保留其表级权限：

```bash
oa-skills citadel-database updateAdvancedPermRolePermissions \
  --contentId "4295357904" \
  --roleType custom \
  --roleName "运营角色" \
  --permissionDetails '[{"tableId":123456,"permGroupType":2,"extraConfig":null}]'
```

`--replace true` 会完整替换权限列表。执行前必须读取当前角色详情；如果完整替换会新增、修改或删除任何仪表盘权限项，则禁止执行。只有确认不会改动既有仪表盘权限，且用户明确确认全部目标数据表权限后才能使用：

```bash
oa-skills citadel-database updateAdvancedPermRolePermissions \
  --contentId "4295357904" \
  --roleType default \
  --permissionDetailsFile ./all-tables.json \
  --replace true
```

### 搜索并调整成员角色

```bash
oa-skills citadel-database searchAdvancedMemberRoles \
  --contentId "4295357904" \
  --keyword "zhangsan" \
  --raw

oa-skills citadel-database updateAdvancedMemberRoles \
  --contentId "4295357904" \
  --userGroupId 10001 \
  --roleIds "88,89"
```

`updateAdvancedMemberRoles` 是覆盖语义，不是追加语义。移除全部可分配角色必须使用 `--clear true`，并在执行前获得用户明确确认。

### 查询当前用户实际表权限

```bash
oa-skills citadel-database getAdvancedUserTablePermissions \
  --contentId "4295357904" \
  --tableIds "123456,123457" \
  --raw
```

该命令查询当前认证用户在指定表上的实际生效权限，不等同于某一个角色的静态配置。

## 使用约束

- `--contentId` 必填，表示多维表格文档 ID。
- 角色权限写入仅支持数据表；不得在 `permissionDetails` 中传入仪表盘 ID，也不得通过 `--replace true` 删除或覆盖既有仪表盘权限。
- `updateAdvancedPermStatus --status` 只支持 `enabled`/`disabled`（也可用 `on`/`off`、`true`/`false`、`1`/`2`）。
- `--preserveOriginalRole` 只在开启高级权限时支持；关闭时不要传。
- 开启高级权限前必须检查 `listAdvancedPermRoles --roleType custom --raw`。如果存在历史自定义角色成员，开启命令必须显式传 `--preserveOriginalRole true` 或 `--preserveOriginalRole false`；不要省略。
- `--roleType` 添加或删除成员时支持 `admin`、`default` 或 `custom`。
- `--roleId` 和 `--roleName` 二选一；`--roleName` 仅用于自定义角色名称精确匹配。
- 如果自定义角色名称重复，必须改用 `--roleId`。
- `--person`、`--xmGroupIds`、`--mails`、`--appIds` 使用逗号分隔或 JSON 数组。
- `--mis` 是 CLI 通用执行人参数，不要用它传要操作的成员；添加/删除人员请使用 `--person`。
- `--orgs` 一期只支持 JSON 数组，避免把组织维度参数拆散后产生歧义。
- 添加/删除成员时如果用户提供 `--roleName`，CLI 会在内部解析自定义角色 `roleId`；不要把角色查询作为单独能力暴露给用户。
- 所有删除操作先读取目标详情并核对对象；删除角色、`--replace true` 和 `--clear true` 必须获得明确确认。

## 接口对应关系

高级权限角色及成员写入调用 `/api/permission/*`，Data API 随后按 XTable 高级权限模型消费已存储的 `permissionDetails.extraConfig`。因此这里使用 Data API 消费的模型存储结构；`/xtable/data-api/s` 数据查询接口公开的 `filterConfig` 对象 DTO 不适用于高级权限写入。

- 角色名称解析：内部使用 `GET /api/permission/role/{contentId}/queryRoles?roleType={roleType}`，服务于成员管理及二期按角色名定位
- 查询高级权限开关：`GET /api/permission/content/{contentId}/getContentInfo`
- 开启高级权限：`POST /api/permission/xtable/{contentId}/advancedOn`，可选请求体 `{ "preserveOriginalRole": true|false }`
- 关闭高级权限：`POST /api/permission/xtable/{contentId}/advancedOff`
- 默认角色添加/删除成员：`POST /api/permission/role/modify`，分别使用 `addMembers` / `deleteUserGroupIds`
- 自定义角色添加成员：`POST /api/permission/role/addMembers`
- 自定义角色删除成员：先查询角色详情匹配成员，再 `POST /api/permission/role/deleteMembers`
- 管理员添加成员：走文档权限添加接口，固定 `permGroupType=4`
- 管理员删除成员：`POST /api/permission/content/{contentId}/delete`
- 创建/重命名/删除角色：`POST /api/permission/role/add`、`POST /api/permission/role/rename`、`DELETE /api/permission/role/delete/{roleId}`
- 修改权限：`POST /api/permission/role/modify`
- 成员角色：`GET /api/permission/role/searchUserRole`、`POST /api/permission/role/updateUserRole`
- 当前用户表权限：`GET /api/permission/xtable/queryUserTablePermission`

## 未完成能力记录

以下能力仍未完成，后续再补：

- 对 `extraConfig` 做中文摘要和差异对比
- 批量导入、批量校验、失败重试和操作审计
