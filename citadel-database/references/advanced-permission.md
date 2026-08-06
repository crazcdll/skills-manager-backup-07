# 多维表格高级权限

多维表格高级权限是 XTable 自己的权限体系，不等同于学城文档权限。用户明确提到"多维表格高级权限"、"默认角色"、"自定义角色"、"多维表格管理员"、"给角色加人/删人/加组织/删组织/加群/删群/加邮件组/删邮件组/加应用/删应用"时，优先使用本页规则。

**当前能力口径：支持查询高级权限开关状态，支持开启/关闭高级权限，支持查询角色配置，支持给管理员和自定义角色添加成员，支持从自定义角色删除成员。** 如果用户要求删除管理员成员、给默认角色添加或删除成员、修改角色权限等能力，需要说明暂不支持，不要执行对应 CLI。

## 一期能力范围

当前支持：

- 查询高级权限开关状态
- 开启或关闭高级权限开关
- 查询管理员、默认角色、自定义角色配置详情
- 通过自定义角色名称精确匹配 `roleId`
- 给管理员、自定义角色添加人员
- 给管理员、自定义角色添加组织
- 给管理员、自定义角色添加大象群、邮件组、应用
- 从自定义角色删除人员
- 从自定义角色删除组织
- 从自定义角色删除大象群、邮件组、应用

暂不支持的能力见本文末尾"未完成能力记录"。

## 角色与成员枚举

角色类型：

| 参数值 | 含义 |
|---|---|
| `admin` / `0` | 管理员 |
| `default` / `1` | 默认角色，当前不支持添加或删除成员 |
| `custom` / `2` | 自定义角色 |
| `all` | 全部角色类型（当前不作为对外查询能力使用） |

权限组类型：

| 值 | 含义 |
|---|---|
| `0` | 无权限 |
| `1` | 仅浏览 |
| `2` | 可浏览、评论 |
| `3` | 可编辑 |
| `4` | 可管理 |

成员类型：

| 值 | 含义 |
|---|---|
| `0` | 组织 |
| `1` | 人员 |
| `2` | 账号类型 |
| `3` | 邮件组 |
| `4` | 大象群 |
| `5` | 应用 |

## 命令使用

### 添加角色成员

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

## 使用约束

- `--contentId` 必填，表示多维表格文档 ID。
- `updateAdvancedPermStatus --status` 只支持 `enabled`/`disabled`（也可用 `on`/`off`、`true`/`false`、`1`/`2`）。
- `--preserveOriginalRole` 只在开启高级权限时支持；关闭时不要传。
- 开启高级权限前必须检查 `listAdvancedPermRoles --roleType custom --raw`。如果存在历史自定义角色成员，开启命令必须显式传 `--preserveOriginalRole true` 或 `--preserveOriginalRole false`；不要省略。
- `--roleType` 添加成员时只支持 `admin` 或 `custom`；删除成员时只支持 `custom`。管理员和默认角色暂不支持删除成员。
- `--roleId` 和 `--roleName` 二选一；`--roleName` 仅用于自定义角色名称精确匹配。
- 如果自定义角色名称重复，必须改用 `--roleId`。
- `--person`、`--xmGroupIds`、`--mails`、`--appIds` 使用逗号分隔或 JSON 数组。
- `--mis` 是 CLI 通用执行人参数，不要用它传要操作的成员；添加/删除人员请使用 `--person`。
- `--orgs` 一期只支持 JSON 数组，避免把组织维度参数拆散后产生歧义。
- 添加/删除成员时如果用户提供 `--roleName`，CLI 会在内部解析自定义角色 `roleId`；不要把角色查询作为单独能力暴露给用户。

## 接口对应关系

- 角色名称解析：内部使用 `GET /api/permission/role/{contentId}/queryRoles?roleType={roleType}`，仅服务于添加/删除成员
- 查询高级权限开关：`GET /api/permission/content/{contentId}/getContentInfo`
- 开启高级权限：`POST /api/permission/xtable/{contentId}/advancedOn`，可选请求体 `{ "preserveOriginalRole": true|false }`
- 关闭高级权限：`POST /api/permission/xtable/{contentId}/advancedOff`
- 自定义角色添加成员：`POST /api/permission/role/addMembers`
- 自定义角色删除成员：先查询角色详情匹配成员，再 `POST /api/permission/role/deleteMembers`
- 管理员添加成员：走文档权限添加接口，固定 `permGroupType=4`

## 未完成能力记录

以下能力不在一期范围内，后续再补：

- 给默认角色添加成员
- 给管理员或默认角色删除成员
- 新增、删除、重命名自定义角色
- 修改默认角色或自定义角色的表级权限
- 修改行权限、列权限、视图权限等 `extraConfig` 结构化配置
- 更新某个成员绑定的角色列表
- 搜索某个成员当前属于哪些高级权限角色
- 查询当前用户在指定数据表上的实际生效权限
- 对 `extraConfig` 做中文摘要和差异对比
- 批量导入、批量校验、失败重试和操作审计
