# 模板操作详细说明

## 获取模板内容

根据使用意图选择命令：

```bash
# 仅阅读/理解模板结构（推荐，token 消耗更低，不可用于编辑回传）
getTemplateSimpleMarkdown --templateId <id>

# 基于模板修改内容再创建文档（完整 XML，保留 nodeId，可编辑后通过 createDocument --file 创建）
getTemplateXml --templateId <id>
```

**选择规则**：
- 用户只是"查看/了解模板"→ 用 `getTemplateSimpleMarkdown`
- 用户要"按模板修改内容后创建文档" → 用 `getTemplateXml`，AI 修改 XML 后写入临时文件，再 `createDocument --file /tmp/new-doc.xml`

## 获取个人/公共模板列表

当用户说"我的模板"、"个人模板"、"分享给我的模板"、"公共模板"、"查看模板列表"时，执行：

```bash
# 查看我创建的模板（默认）
listPersonalTemplates

# 查看分享给我的模板
listPersonalTemplates --type shared

# 查看公共模板
listPersonalTemplates --type public

# 分页
listPersonalTemplates --type personal --pageNo 2 --pageSize 16
```

**参数说明**：

| 参数 | 说明 |
|------|------|
| `--type` | `personal`=我创建的（默认），`shared`=分享给我的，`public`=公共模板 |
| `--pageNo` | 页码，从 1 开始，默认 1 |
| `--pageSize` | 每页数量，默认 16 |

**输出内容**：模板总数、模板 ID（`templateId`）、模板标题、创建者、修改者、创建/修改时间。获得 `templateId` 后可传给 `getTemplateSimpleMarkdown` 或 `getTemplateXml` 查看模板内容，或传给 `createDocument --templateId` 基于模板创建文档。

## 从模板创建文档

```bash
# 从模板中心链接创建（提取 templateId，忽略 query 参数）
createDocument --title <标题> --templateId <id>

# 示例：
# https://km.sankuai.com/template-center/2751442505 → --templateId 2751442505
# https://km.sankuai.com/template-center/2751442505?isRelease=1 → --templateId 2751442505
```

## 复制文档创建（适合学城 2.0 文档）

当用户说"先复制模板再填充内容""按模板生成"等，并且模板给的是 `km.sankuai.com/collabpage/<id>` / `km.sankuai.com/page/<id>` 链接（尤其学城文档 2.0）时，默认使用复制命令，不要先读取模板内容再重建：

```bash
createDocument --title <标题> --copyFrom <模板id> --parentId <目录id>
```

示例：
- 目录：`https://km.sankuai.com/collabpage/1234567890` → `--parentId 1234567890`
- 模板：`https://km.sankuai.com/collabpage/1234567890` → `--copyFrom 1234567890`
- 命令：`createDocument --title "测试文档" --copyFrom 1234567890 --parentId 1234567890`
