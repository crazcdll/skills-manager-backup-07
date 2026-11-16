# domain 命令详细规则 — 域名管理

## 概述

管理作品的域名配置。支持查看当前域名（判断是否已绑定自有域名）、新增/修改/删除 Oceanus 自有域名、修改系统前缀域名。

## 核心概念：两类域名，语义完全不同

NoCode 的域名分为两大类，**操作规则截然不同，绝不可混淆**：

### 1. 系统前缀域名（prefix）

基于系统域名后缀的二级域名，形如 `https://f37zre.mynocode.host`。

| `domainType` | 说明 |
|---|---|
| `init_prefix_custom_domain` | 部署时系统自动创建的那一条 |
| `prefix_custom_domain` | 用户改过前缀后的那一条 |

**关键约束：**

- **由部署自动产生**，每个作品**有且只有一条**
- **只能改前缀**（`nocode domain modify`），**不能新增、不能删除**
- 修改后**直接生效**，无需在 Oceanus 配置任何映射规则
- 修改会同步更新作品的渲染链接（`t_deploy.external_url`）

### 2. Oceanus 自有域名（fully custom）

用户自带的独立域名，形如 `https://example.sankuai.com`，`domainType=fully_custom_domain`。

**关键约束：**

- **可新增多条、可删除**
- 新增/修改后**必须在 Oceanus 平台配置映射规则**才能真正访问
- 域名**不能落在系统后缀下**（`.mynocode.host` / `.nocode.host` 等）

### 3. 历史部署域名（只读）

`domainType=history_deploy_domain`，ID 为**负数**（如 `-1`、`-2`）。

- 这是后端依据部署信息中的历史访问地址（`t_deploy.external_url`）**合成的虚拟记录**，不是数据库真实行
- **不可修改、不可删除**
- 若出现异常的历史域名残留，可通过「把前缀域名改成它自己」触发后端刷新 `external_url` 来清除

### 其他字段

- **产品路径**（`productPath`）：域名下的访问路径，形如 `/path1/path2`，可选，后端要求非空时默认补 `/`
- **环境**（`env`）：`prod` 线上 / `test` 线下。线下域名由系统部署时自动分配，**用户只能维护线上环境**

## ⛔ 强制约束

1. **创建/修改前必须先执行 `domain list`**：确认目标域名的真实 `domainType`，据此判断该走 `create` 还是 `modify`
2. **禁止用 `create` 新增系统前缀域名**：`*.mynocode.host` 这类域名全局唯一、由部署产生，只能 `modify`。CLI 已内置拦截并给出正确指引
3. **禁止删除系统前缀域名**：删除后作品将无法访问。CLI 已内置拦截
4. **禁止在两类域名之间互转**：前缀域名不能改成外部域名，自有域名也不能改成系统后缀域名。CLI 已内置双向拦截
5. **删除操作必须经用户明确确认**：执行前必须展示将删除的域名 URL 并获得明确确认，`--confirm` 为必需参数
6. **仅自有域名需要提醒 Oceanus 配置**：前缀域名修改后直接生效，**不要**对前缀域名提示"请去 Oceanus 配置"

## 命令列表

### domain list — 查看域名列表

```bash
nocode domain list <chatId>
nocode domain list <chatId> --json    # JSON 格式输出
```

**返回字段：**

| 字段 | 说明 |
|------|------|
| `id` | 域名 ID，`modify` / `delete` 时需要。**负数表示只读虚拟记录** |
| `env` | 环境：`prod` 线上 / `test` 线下 |
| `domainType` | 域名类型，见上文「核心概念」 |
| `url` | 用户访问的 URL |
| `deployUrl` | 真实部署链接（内部使用，**禁止展示给用户**） |
| `status` | 状态，`SUCCESS` 表示配置成功 |
| `createTime` / `updateTime` | 创建/更新时间 |

**判断是否已绑定自有域名：** 列表中存在 `domainType=fully_custom_domain` 的记录即表示已绑定。

### domain create — 新增 Oceanus 自有域名

**⛔ 仅用于新增自有域名。系统前缀域名请用 `modify`。**

**⛔ 必须先询问用户**，禁止自行猜测或编造域名：

1. **完整域名是什么？**（如 `example.sankuai.com`，不含 `https://` 前缀）
2. **是否需要指定产品路径？**（如 `/path1/path2`，不需要则留空）

```bash
nocode domain create <chatId> <customDomain>                          # 新增自有域名
nocode domain create <chatId> <customDomain> --path /path1/path2      # 指定产品路径
```

**规则：**

- `customDomain` 传域名主体，不含协议前缀（`https://` 会被自动去除）
- 域名**不能落在系统后缀下**，否则 CLI 会拦截并提示改用 `modify`
- 创建成功后返回 `domainId`，可用于后续 `modify` / `delete`
- 成功后**必须提醒用户前往 Oceanus 配置映射规则**

### domain modify — 修改域名

```bash
nocode domain modify <chatId> <domainId> <newCustomDomain>
nocode domain modify <chatId> <domainId> <newCustomDomain> --path /path1/path2
```

**规则：**

- `domainId` 从 `domain list` 获取
- CLI 会**自动回读真实 `domainType` 并回传后端**（后端据此决定是否同步作品渲染链接，传错会导致修改不生效）
- **改前缀域名**：新域名必须是同后缀的另一个前缀，如 `f37zre.mynocode.host` → `new-prefix.mynocode.host`
- **改自有域名**：新域名不能落在系统后缀下
- 修改可能生成新的 `domainId`，修改后建议重新 `domain list` 确认

### domain delete — 删除 Oceanus 自有域名

**⛔ 删除前必须经用户明确确认。**

```bash
nocode domain delete <chatId> <domainId> --confirm
```

**规则：**

- `--confirm` 为必需参数
- **只能删除 `fully_custom_domain`**；前缀域名和历史只读记录均被 CLI 拦截
- 删除后该域名立即无法访问，不可恢复
- 若 `domainId` 为负数，shell 中需用 `--` 分隔：`nocode domain delete <chatId> --confirm -- -2`

## 典型流程

```bash
# 1. 先查看当前域名配置，确认各条记录的真实类型
nocode domain list <chatId>

# 2a. 改系统前缀域名（只有一条，改前缀，直接生效）
nocode domain modify <chatId> 946225 new-prefix.mynocode.host --path /

# 2b. 新增自有域名（域名和路径需先询问用户）
nocode domain create <chatId> example.sankuai.com --path /app

# 2c. 改已有自有域名
nocode domain modify <chatId> 123456 new-example.sankuai.com

# 3. 确认配置结果
nocode domain list <chatId>

# 4. 仅当操作对象是自有域名时，提醒用户前往 Oceanus 完成映射规则配置
```

## ⚠️ 注意事项

- **仅线上环境（prod）支持维护域名**，线下环境域名在部署到线下时由系统自动分配
- 自有域名配置成功（`status=SUCCESS`）后，仍需在 Oceanus 平台完成映射规则配置才能真正访问
- 展示域名给用户时使用 `[{url}]({url})` 可点击链接格式；**`deployUrl` 仅供内部使用，严禁展示给用户**
- 域名操作不影响已部署版本，无需重新部署

## ⚠️ 常见错误

| 错误信息 | 处理方式 |
|---------|---------|
| `「xxx.mynocode.host」属于系统前缀域名，不支持新增` | 改用 `domain modify` 修改已有的那一条前缀域名 |
| `系统前缀域名 xxx 不可删除` | 前缀域名全局唯一且由部署产生，只能改前缀 |
| `目标是系统前缀域名，只能改为同后缀的域名` | 若要绑自有域名，改用 `domain create` |
| `不能将自有域名修改为系统前缀域名` | 前缀域名请直接修改那一条，不要从自有域名转过去 |
| `由部署历史自动生成（只读），不可删除` | 负数 ID 是虚拟记录；可通过修改前缀域名刷新 `external_url` 来清除残留 |
| `域名已被占用` | 该域名已被其他作品绑定，请用户更换域名 |
| `域名格式不正确` | 检查域名是否包含协议前缀或非法字符，只传域名主体 |
| `域名不存在` | 先执行 `nocode domain list <chatId>` 确认 `domainId` |
| `unknown option '-2'` | 负数 ID 需用 `--` 分隔：`domain delete <chatId> --confirm -- -2` |
| `无权限操作` | 当前用户非作品所有者或管理者，需联系作品所有者操作 |
| 自有域名配置成功但无法访问 | 提醒用户前往 Oceanus 平台完成映射规则配置 |

