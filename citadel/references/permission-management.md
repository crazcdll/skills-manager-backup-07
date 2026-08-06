# 学城权限管理

`citadel` 的权限能力统一走 `oa-skills citadel`，由主 `SKILL.md` 路由到这里，再按命令落到统一的 [cli-reference.md](cli-reference.md)。

## 适用场景

用户提到下面这些诉求时，优先使用本页规则：

- 盘点空间、目录或单篇文档的权限
- 批量授权、改权、移权
- 移除或恢复权限继承
- 批量转移所有者
- 清空文档权限
- 设置链接分享权限
- 增加或移除空间管理员
- 盘点离职员工创建的文档

## URL / pageId 提取规则

文档类目标**二选一**，优先用完整 URL：

| 用户给的内容 | 传参方式 |
|---|---|
| `https://km.sankuai.com/collabpage/2750138424` | `--url <url>` |
| `https://km.sankuai.com/page/2750138424` | `--url <url>` |
| `https://km.sankuai.com/xtable/2750138424` | `--url <url>` |
| 纯数字 contentId（如 `2750138424`） | `--pageId 2750138424` |
| `https://km.sankuai.com/space/XOPEN` | `--url <url>`（仅 space-admin 使用） |
| `https://km.sankuai.com/space/38556` | `--url <url>`（仅 space-admin 使用） |

- `--url` 和 `--pageId` **二选一**，不要同时传。
- `space-admin` **只接受 `--url` 的空间 URL**，不支持 `--pageId`。
- 不要把 URL 拆成 `contentId` 再让用户补填；能从链接提取时直接传 `--url`。

## 意图路由

| 用户意图 | 命令 |
|---|---|
| 查权限分配、导出权限清单、盘点目录权限 | `audit` |
| 给人/部门/大象群/邮件组/应用/账号类型授权 | `grant` |
| 把已有权限改成另一档 | `modify` |
| 删除已有显式权限 | `revoke` |
| 去掉继承或恢复继承 | `inherit` |
| 查离职员工名下文档 | `audit-resigned` |
| 转移文档所有者 | `transfer-owner` |
| 清空权限只保留所有者和空间管理员 | `clear-perm` |
| 设置"获得链接的任何人"权限 | `share-perm` |
| 增删空间管理员 | `space-admin` |

## 执行约束

- `audit`、`audit-resigned` 会在学城创建报告文档，执行前要明确告知用户。
- `grant`、`modify`、`revoke`、`clear-perm` 会先将权限快照保存到本地备份文件（`~/.cache/oa-skills/perm-backups/`），再执行批量操作。每次执行时会自动清理超过 7 天的旧备份文件。
- `clear-perm` 是**高风险操作**，必须明确告诉用户"会清除除所有者和空间管理员外的全部显式权限"。
- `space-admin` 只接受空间 URL，不接受文档 URL 或 `--pageId`。
- `inherit`、`grant`、`modify`、`revoke`、`clear-perm`、`share-perm` 支持文档 URL 或目录 URL；如果是目录，会递归处理子文档。
- `share-perm` 不适用于学城 1.0 文档，遇到这类文档会自动跳过。

---

## 命令详解与 CLI 示例

### audit — 盘点权限

盘点指定空间、目录或单篇文档下所有文档的权限分配，**输出学城报告文档**。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 目标 URL 或文档 contentId（二选一） |
| `--secret-level` | — | 按文档密级过滤，范围 `0-5` |
| `--start-time` | — | 创建时间起始，格式 `YYYY-MM-DD` |
| `--end-time` | — | 创建时间截止，格式 `YYYY-MM-DD` |
| `--creators` | — | 按创建人 MIS 过滤，逗号分隔 |

```bash
# 盘点整个目录（URL 方式）
oa-skills citadel audit \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --mis "zhangsan"

# 盘点单篇文档（pageId 方式）
oa-skills citadel audit \
  --pageId "2750138424" \
  --mis "zhangsan"

# 盘点整个空间，仅统计 C3 及以上密级文档
oa-skills citadel audit \
  --url "https://km.sankuai.com/space/XOPEN" \
  --secret-level 3

# 按时间范围 + 创建人过滤
oa-skills citadel audit \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --start-time "2024-01-01" \
  --end-time "2024-12-31" \
  --creators "zhangsan,lisi"
```

**输出**：学城报告文档链接，报告中含每篇文档的权限清单。

---

### grant — 批量授权

批量授予显式权限。执行前会自动将操作前的权限快照保存到本地备份文件（`~/.cache/oa-skills/perm-backups/`），不再创建学城文档。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 目标 URL 或文档 contentId（二选一） |
| `--perm` | ✅ | 权限类型：`仅浏览` / `可浏览、评论` / `可编辑` / `可编辑、添加` / `可编辑、添加、删除` / `可管理` |
| `--person` | 条件 | 个人 MIS，逗号分隔 |
| `--dept` | 条件 | 部门全路径 |
| `--xm-group-ids` | 条件 | 大象群 ID，逗号分隔 |
| `--mails` | 条件 | 邮件组，逗号分隔 |
| `--app-ids` | 条件 | 应用 ID，逗号分隔 |
| `--account-types` | 条件 | 账号类型，逗号分隔 |
| `--org-roles` | — | 部门岗位族，逗号分隔（配合 `--dept` 使用） |
| `--contract-types` | — | 部门合同类型，默认 `101` |
| `--country` | — | 部门国家，默认 `CHN` |

> `--person` / `--dept` / `--xm-group-ids` / `--mails` / `--app-ids` / `--account-types` 六选一。

```bash
# 给个人授权（URL 方式）
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --person "lisi" \
  --perm "可编辑"

# 给个人授权（pageId 方式）
oa-skills citadel grant \
  --pageId "2750138424" \
  --person "lisi" \
  --perm "可编辑"

# 给大象群授浏览权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --xm-group-ids "70411238253" \
  --perm "仅浏览"

# 给多个人同时授权（逗号分隔）
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --person "lisi,wangwu" \
  --perm "可管理"

# 给部门授权（带岗位族 + 合同类型过滤）
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --dept "美团/到店事业群/商业技术部" \
  --org-roles "技术" \
  --contract-types "101" \
  --perm "仅浏览"

# 给邮件组授权
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --mails "team@meituan.com" \
  --perm "可浏览、评论"
```

**输出**：成功/失败统计、本地备份文件路径；有失败时附失败清单链接。

---

### modify — 批量改权

批量把目标对象**已有**的权限改为新权限。若目标对象对某篇文档没有权限记录，该文档会计入 `skipped`，不会新增权限。参数与 `grant` 完全一致（同样会保存本地备份文件）。

```bash
# 把 lisi 的权限从可编辑改为可管理
oa-skills citadel modify \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --person "lisi" \
  --perm "可管理"

# pageId 方式
oa-skills citadel modify \
  --pageId "2750138424" \
  --xm-group-ids "70411238253" \
  --perm "可编辑"
```

**输出**：成功/跳过/失败统计、本地备份文件路径；有失败时附失败清单链接。

---

### revoke — 批量移权

批量删除目标对象的显式权限。目标参数与 `grant` 相同，但**不需要 `--perm`**。会保存本地备份文件。

```bash
# 移除 lisi 在该文档的权限
oa-skills citadel revoke \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --person "lisi"

# pageId 方式
oa-skills citadel revoke \
  --pageId "2750138424" \
  --xm-group-ids "70411238253"
```

**输出**：成功/跳过/失败统计、本地备份文件路径；有失败时附失败清单链接。

---

### inherit — 移除或恢复权限继承

控制文档是否继承父文档的权限设置。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 文档或目录 URL / contentId（二选一） |
| `--action` | ✅ | `remove`（断开继承）或 `restore`（恢复继承） |
| `--keep-existing` | — | 恢复继承时是否保留已有显式权限，默认 `true` |

```bash
# 断开继承（子文档独立管理权限）
oa-skills citadel inherit \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --action remove

# 恢复继承，同时清空已有显式权限
oa-skills citadel inherit \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --action restore \
  --keep-existing false

# pageId 方式
oa-skills citadel inherit \
  --pageId "2750138424" \
  --action restore
```

---

### audit-resigned — 盘点离职员工文档

盘点指定范围内由**已离职员工**创建的文档，**输出学城报告文档**。支持与 `audit` 相同的过滤参数。

```bash
# 盘点整个空间的离职员工文档
oa-skills citadel audit-resigned \
  --url "https://km.sankuai.com/space/XOPEN"

# 盘点某目录，限制密级
oa-skills citadel audit-resigned \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --secret-level 3

# pageId 方式
oa-skills citadel audit-resigned \
  --pageId "2750138424"
```

**输出**：学城报告文档链接，报告中含离职员工姓名、文档列表。

---

### transfer-owner — 批量转移所有者

批量将文档所有者转移给指定用户。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 目标 URL 或 contentId（二选一） |
| `--target-mis` | ✅ | 新所有者 MIS |
| `--secret-level` | — | 密级过滤 |
| `--start-time` | — | 创建时间起始 |
| `--end-time` | — | 创建时间截止 |
| `--creators` | — | 按原创建人 MIS 过滤，逗号分隔（只转移这些人创建的文档） |

```bash
# 将某目录下所有文档所有者转给 lisi
oa-skills citadel transfer-owner \
  --url "https://km.sankuai.com/space/XOPEN" \
  --target-mis "lisi"

# 只转移由离职员工 wangwu 创建的文档
oa-skills citadel transfer-owner \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --target-mis "lisi" \
  --creators "wangwu"

# pageId 方式
oa-skills citadel transfer-owner \
  --pageId "2750138424" \
  --target-mis "lisi"
```

---

### clear-perm — 一键清空权限

⚠️ **高风险操作**：清除指定范围内所有文档的**全部显式权限**（仅保留所有者和空间管理员），并关闭链接分享权限。执行前必须向用户明确说明后果，并获得确认。会自动将操作前的权限快照保存到本地备份文件（`~/.cache/oa-skills/perm-backups/`）。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 目标 URL 或 contentId（二选一） |
| `--secret-level` | — | 密级过滤 |
| `--start-time` | — | 创建时间起始 |
| `--end-time` | — | 创建时间截止 |
| `--creators` | — | 按创建人 MIS 过滤 |

```bash
# 清空某文档的所有权限
oa-skills citadel clear-perm \
  --url "https://km.sankuai.com/collabpage/2750138424"

# 只清空 C3 及以上密级文档的权限
oa-skills citadel clear-perm \
  --url "https://km.sankuai.com/space/XOPEN" \
  --secret-level 3

# pageId 方式
oa-skills citadel clear-perm \
  --pageId "2750138424"
```

**输出**：成功/失败统计、本地备份文件路径。

---

### share-perm — 批量设置链接分享权限

批量设置"获得链接的任何人"的访问权限。不适用于学城 1.0 文档（会自动跳过）。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` \| `--pageId` | ✅ | 目标 URL 或 contentId（二选一） |
| `--status` | ✅ | `0` 关闭，`1` 开启 |
| `--perm` | 条件 | 开启时必填：`0=可浏览、评论`，`1=可编辑`，`5=仅浏览` |

```bash
# 开启链接分享，权限为仅浏览
oa-skills citadel share-perm \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --status 1 \
  --perm 5

# 开启链接分享，权限为可编辑
oa-skills citadel share-perm \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --status 1 \
  --perm 1

# 关闭链接分享
oa-skills citadel share-perm \
  --url "https://km.sankuai.com/collabpage/2750138424" \
  --status 0

# pageId 方式
oa-skills citadel share-perm \
  --pageId "2750138424" \
  --status 0
```

---

### space-admin — 增删空间管理员

增加或移除空间管理员。**仅支持空间 URL**（`/space/...`），不支持文档 URL 或 `--pageId`。

| 参数 | 必填 | 说明 |
|---|---|---|
| `--url` | ✅ | 空间 URL，格式 `https://km.sankuai.com/space/<key 或 id>` |
| `--action` | ✅ | `add` 增加 / `remove` 移除 |
| `--person` | ✅ | 目标管理员 MIS，逗号分隔（支持批量） |

```bash
# 增加空间管理员
oa-skills citadel space-admin \
  --url "https://km.sankuai.com/space/XOPEN" \
  --action add \
  --person "lisi"

# 同时增加多个空间管理员
oa-skills citadel space-admin \
  --url "https://km.sankuai.com/space/XOPEN" \
  --action add \
  --person "lisi,wangwu"

# 移除空间管理员
oa-skills citadel space-admin \
  --url "https://km.sankuai.com/space/XOPEN" \
  --action remove \
  --person "lisi"

# 通过空间数字 ID
oa-skills citadel space-admin \
  --url "https://km.sankuai.com/space/38556" \
  --action add \
  --person "lisi"
```

---

## 群文档权限补充规则

如果用户是在**大象群**里创建文档，创建完成后默认补两步权限：

```bash
# 第一步：给大象群授浏览权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/<新文档id>" \
  --xm-group-ids "<群ID>" \
  --perm "仅浏览"

# 第二步：给群助理的管理员授管理权限
oa-skills citadel grant \
  --url "https://km.sankuai.com/collabpage/<新文档id>" \
  --person "<管理员mis>" \
  --perm "可管理"
```
