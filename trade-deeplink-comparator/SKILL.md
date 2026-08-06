---
name: trade-deeplink-comparator
description: 解析并对比学城 KM 文档中的 iOS 和 Android 跳链参数差异。从文档表格中提取双端跳链，解析 URL 参数，生成参数对比表格和汇总报告，并可自动创建学城文档输出结果。Use when comparing iOS and Android deeplinks from KM documents, analyzing URL parameters, or generating deeplink comparison reports.
---

# 交易跳链参数对比分析器

从学城文档中提取 iOS 和 Android 跳链，解析参数并对比双端差异，支持自动创建输出文档。

## 前置要求

确保使用 Node.js 24+ 运行 oa-skills：

```bash
nvm use 24
```

## 使用方法

### 完整流程

用户提供学城文档 URL 和目标位置后，执行以下步骤：

#### Step 1: 提取表格数据

使用 browser 工具访问 KM 文档，提取表格内容：

```bash
catdesk browser-action "extract_table" --url "<KM文档URL>" --selector "table"
```

#### Step 2: 解析跳链参数

运行 Python 脚本解析跳链 URL：

```bash
python3 scripts/parse_deeplinks.py --input <extracted_data.json> --output report.md
```

#### Step 3: 自动创建学城文档

**创建新文档：**

```bash
nvm use 24 && oa-skills citadel createDocument \
  --parentId <父文档ID> \
  --title "跳链参数对比报告" \
  --content "$(cat report.md)" \
  --mis <你的MIS>
```

**更新现有文档：**

```bash
nvm use 24 && oa-skills citadel updateDocumentByMd \
  --contentId <文档ID> \
  --file report.md \
  --mis <你的MIS>
```

## 核心功能

### parse_deeplinks.py 脚本

解析跳链并生成对比报告：

```python
from parse_deeplinks import parse_deeplink, generate_page_report

# 解析单个 URL
result = parse_deeplink("imeituan://...")
# 返回: {scheme, netloc, path, params, raw_url}

# 生成页面报告
report = generate_page_report(
    page_num=1,
    page_name="首页",
    ios_before=ios_before_dict,
    ios_after=ios_after_dict,
    android_before=android_before_dict,
    android_after=android_after_dict
)
```

## 输出格式

生成如下结构的报告：

```markdown
## 第 X 页：页面名称

### 页面名称-iOS

替换前跳链地址：
```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id=xxx&biz_type=1&mrn_min_version=3.62.0&from_cashier=0
```

替换后跳链地址：
```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id=xxx&biz_type=1&mrn_min_version=3.62.0&from_cashier=0
```

#### iOS 跳链参数

| 参数名 | 替换前值 | 替换后值 | 变化 |
|--------|----------|----------|------|
| param1 | value1   | value2   | ❓ |

### 页面名称-Android

替换前跳链地址：
```
imeituan://www.meituan.com/mrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id=xxx&biz_type=1&mrn_min_version=3.62.0&from_cashier=0
```

替换后跳链地址：
```
imeituan://www.meituan.com/standardmrn?mrn_biz=hotel&mrn_entry=hotelchannel-order-detail&mrn_component=hotelchannel-order-detail&order_id=xxx&biz_type=1&mrn_min_version=3.62.0&mrn_identify_key=xxx
```

#### Android 跳链参数

| 参数名 | 替换前值 | 替换后值 | 变化 |
|--------|----------|----------|------|
| param1 | value1   | value2   | ✅ |

### iOS vs Android 对比

| 参数名 | iOS替换后 | Android替换后 | 是否一致 | 备注 |
|--------|-----------|---------------|----------|------|
| param1 | value1    | value1        | ✅       |      |
```

## 关键命令参考

| 命令 | 用途 |
|------|------|
| `getMarkdown` | 获取文档 Markdown 内容 |
| `createDocument` | 创建新文档 |
| `updateDocumentByMd` | 通过 CitadelMD 更新文档 |
| `getDocumentMetaInfo` | 获取文档元信息 |

## 注意事项

1. **Node 版本**：必须使用 Node 24+ 运行 oa-skills
2. **URL 解码**：跳链参数需要 URL 解码后对比
3. **Android 特有参数**：`mrn_identify_key` 通常只在 Android 端存在
4. **数值等价**：`0` 和 `false` 视为等价
5. **Scheme 差异**：`mrn` vs `standardmrn` 属于正常迁移差异
