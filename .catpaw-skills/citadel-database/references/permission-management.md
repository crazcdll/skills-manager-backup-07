# 学城文档权限管理指南

创建多维表格文档后，如果是在大象群里创建的，必须执行两步授权：先为群成员授予浏览权限，再为群助理的管理员授予管理权限。统一使用 `oa-skills citadel` 进行权限管理。

如果用户说的是"多维表格高级权限"、"默认角色"、"自定义角色"、"多维表格管理员"或"给角色添加人员/组织/群/邮件组/应用"，不要使用本文档命令，改用 [advanced-permission.md](advanced-permission.md)。

## 目录

- [快速开始](#快速开始)
- [常用权限操作](#常用权限操作)
- [权限类型说明](#权限类型说明)
- [支持的授权对象](#支持的授权对象)
- [典型工作流](#典型工作流)
  - [场景1：创建表格并完成群权限初始化](#场景1创建表格并完成群权限初始化)
  - [场景2：把某人的权限从浏览升级到编辑](#场景2把某人的权限从浏览升级到编辑)
- [说明](#说明)

## 快速开始

### 最常用场景：群内建表后的两步授权

```bash
# 第一步：为大象群授予浏览权限
oa-skills citadel grant \
  --pageId "2750138424" \
  --xm-group-ids "70411238253" \
  --perm "仅浏览"

# 第二步：为群助理的管理员（mis）授予管理权限
oa-skills citadel grant \
  --pageId "2750138424" \
  --person "zhangsan" \
  --perm "可管理"
```

## 常用权限操作

```bash
# 1. 为大象群授予浏览权限
oa-skills citadel grant \
  --pageId "2750138424" \
  --xm-group-ids "70411238253" \
  --perm "仅浏览"

# 2. 为个人授予编辑权限
oa-skills citadel grant \
  --pageId "2750138424" \
  --person "zhangsan,lisi" \
  --perm "可编辑"

# 3. 为部门授予管理权限
oa-skills citadel grant \
  --pageId "2750138424" \
  --dept "美团/核心本地商业/基础研发平台" \
  --perm "可管理"

# 4. 修改权限等级
oa-skills citadel modify \
  --pageId "2750138424" \
  --person "zhangsan" \
  --perm "可编辑"

# 5. 移除权限
oa-skills citadel revoke \
  --pageId "2750138424" \
  --person "zhangsan"

# 6. 清空所有权限（仅保留所有者和空间管理员）
oa-skills citadel clear-perm \
  --pageId "2750138424"

# 7. 移除文档权限继承
oa-skills citadel inherit \
  --pageId "2750138424" \
  --action remove

# 8. 恢复文档权限继承
oa-skills citadel inherit \
  --pageId "2750138424" \
  --action restore \
  --keep-existing true
```

## 权限类型说明

| 权限类型 | 参数值 | 说明 |
|---------|--------|------|
| 仅浏览 | `仅浏览` | 只能查看文档内容，不能编辑或评论 |
| 可浏览、评论 | `可浏览、评论` | 可以查看和评论，但不能编辑内容 |
| 可编辑 | `可编辑` | 可以编辑文档内容和数据 |
| 可管理 | `可管理` | 拥有管理权限，包括权限管理 |

## 支持的授权对象

- `--person <mis,...>`：个人 MIS 列表
- `--dept <path>`：部门全路径
- `--xm-group-ids <id,...>`：大象群 ID 列表
- `--mails <mail,...>`：邮件组列表
- `--app-ids <id,...>`：应用 ID 列表
- `--account-types <type,...>`：账号类型列表
- 部门额外参数：`--org-roles`、`--contract-types`、`--country`

## 典型工作流

### 场景1：创建表格并完成群权限初始化

```bash
# 步骤1：创建多维表格
oa-skills citadel-database createDatabase \
  --contentTitle "项目数据表" \
  --tableTitle "任务列表"

# 步骤2：为群授予浏览权限（使用步骤1返回的 contentId）
oa-skills citadel grant \
  --pageId "返回的contentId" \
  --xm-group-ids "70411238253" \
  --perm "仅浏览"

# 步骤3：为群助理管理员授予管理权限
oa-skills citadel grant \
  --pageId "返回的contentId" \
  --person "zhangsan" \
  --perm "可管理"
```

### 场景2：把某人的权限从浏览升级到编辑

```bash
oa-skills citadel modify \
  --pageId "2750138424" \
  --person "zhangsan" \
  --perm "可编辑"
```

## 说明

- `oa-skills citadel` 的权限命令支持 `--pageId` 或 `--url` 二选一；如果你手上已经有 `contentId`，优先用 `--pageId`。
- 若要查看完整参数，执行 `oa-skills citadel grant --help` 或 `oa-skills citadel --help`。
- 如果是在目录或空间上执行 `grant` / `modify` / `revoke` / `inherit` / `clear-perm`，`citadel` 会递归处理子文档，请谨慎操作。
