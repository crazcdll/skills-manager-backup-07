# 搜索学城文档详细说明

## 基础用法

```bash
# 全文搜索（默认每次返回 20 条，offset=0）
searchContent --keyword <关键词>

# 仅搜索标题
searchContent --keyword <关键词> --searchTitle

# 分页（第 2 页）
searchContent --keyword <关键词> --offset 20 --limit 20
```

## 限定搜索范围

### 按空间搜索

```bash
# 通过空间链接指定（spaceKey 格式，如 /space/citadel）
searchContent --keyword <关键词> --space-url "https://km.sankuai.com/space/citadel"

# 通过空间链接指定（spaceId 格式，如 /space/27）
searchContent --keyword <关键词> --space-url "https://km.sankuai.com/space/27"

# 通过空间 ID 直接指定
searchContent --keyword <关键词> --space-id 27
```

**如何获取空间链接**：在学城打开目标空间，浏览器地址栏的 URL 即为空间链接，支持两种格式：
- `https://km.sankuai.com/space/<spaceKey>`（如 `/space/citadel`）
- `https://km.sankuai.com/space/<spaceId>`（如 `/space/27`，纯数字）

### 按文档目录搜索

```bash
# 通过文档链接指定搜索范围（含空间最多 5 个，逗号分隔）
searchContent --keyword <关键词> --parent-urls "https://km.sankuai.com/collabpage/1346135471,https://km.sankuai.com/collabpage/1343126899"

# 通过文档 ID 指定搜索范围（含空间最多 5 个，逗号分隔）
searchContent --keyword <关键词> --parent-ids "1346135471,1343126899"
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `--keyword` | 搜索关键词（必填） |
| `--searchTitle` | 仅匹配文档标题（不搜正文）；不加此参数则全文搜索 |
| `--offset` | 分页偏移量，从 0 开始，默认 0 |
| `--limit` | 每页返回数量，默认 20 |
| `--space-url` | 限定在指定空间内搜索（与 `--space-id` 二选一） |
| `--space-id` | 限定在指定空间内搜索（与 `--space-url` 二选一） |
| `--parent-urls` | 限定在指定文档目录内搜索，逗号分隔，最多 5 个（与 `--parent-ids` 二选一） |
| `--parent-ids` | 限定在指定文档目录内搜索，逗号分隔，最多 5 个（与 `--parent-urls` 二选一） |

## 返回说明

返回结果包含：文档 ID、标题、空间名、作者、更新时间和内容摘要。

> ⚠️ 该接口支持安全屋策略，**非安全屋模式下不会返回 C4 文档**。CLI 会在结果末尾自动提示"非安全屋模式下不会返回 C4 文档，如需查看完整结果请打开安全屋模式。"，安全屋模式下无此提示。
