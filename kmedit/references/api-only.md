# API-only 默认工作流

编辑器传输使用 KM HTTP + Pike WSS，本地认证复用已有 SSO；命令不连接 Chrome 编辑器。
本地 OIDC 首次登录可能打开认证页面，这与 CDP 编辑传输无关。

## 默认入口

- inspect / check / patch / full / rename：API 路径；2.0 full 支持带原生节点、表格及评论保留标记的 Markdown，详见 [全文编辑](full-edit.md)。
- schema：不带 doc-id 时本地查询 Parker schema；带 doc-id 时读取文档 feature flags。
- copy：只读 snapshot + 最新 tail，无需编辑权限、Pike 在线或 CDP。
- insert-html / edit-html / insert-image：默认 API；--transport cdp 选择兼容路径。
- drawio-session：本地草稿 start/apply/commit/discard；apply 无远端写入。

## 富文本与文件粘贴

```json
{"operations":[{"op":"paste","target":{"nodeId":"<anchor>"},"clipboard":{"textMarkdown":"## 标题\n\n**粗体**、列表、表格、代码、![图片](<image-url>)"}}]}
```

textHtml 优先于 textMarkdown，随后 textPlain；原生 custom capsule 优先于文本。
正文 HTML 用官方 Parker parseDOM 解析结构，Markdown 先转 HTML；不执行 script、加载样式或嵌入 iframe。
主动 HTML 应使用可信的 insert_html 宏；不要用宏替代可编辑正文。
files 接受 path 或 url，图片/音视频按 MIME 上传为对应原生节点，其他文件生成 attachment。
attachment 的 `size` 必须是字符串；`"35"` 可渲染，上传生成路径统一使用 `35B`、`1.00KB` 等展示格式。数字字节数会使网页渲染器报错，写入预检会拦截。
单文件最大 20 MiB；DrawIO/Minder SVG 需用专用 operation 保留原生语义。

## 跨文档复制

```bash
kmedit copy --spec-file /tmp/copy-sources.json --output-file /tmp/copy-result.json
```

spec-file：

```json
{"sources":[{"docId":"<sourceDocId>","targets":[{"nodeId":"<nodeId>"}]}]}
```

paste.source.type=copy_result 的 result 是上述文件的 JSON；也可直接用 copy_refs：

```json
{"operations":[{"op":"paste","target":{"nodeId":"<targetAnchor>"},"source":{"type":"copy_refs","sources":[{"docId":"<sourceDocId>","targets":[{"nodeId":"<nodeId>"}]}]}}]}
```

按 source/targets 的顺序插入；节点和 heading/code/link ID 重新生成。
图片的 src/small/origin、附件、音视频、DrawIO、Minder 会重新上传到目标文档；DrawIO/Minder 完整 SVG 保留。
Mermaid 读取官方源并创建目标文档附件；Data2Chart 重新创建 chart/datasource，提交前读回校验。
源文档 C4 需要该文档的明确确认，不能自动传 --confirm-c4。

只接受已知原生 MIME application/x-kmedit-nodes+json。未知 custom MIME、XTable、同步块、OpenCard、
Gantt、OpenLink、WPS 和脚注等专属 Provider 不会被当成普通节点复制；按对应工具的生命周期操作。普通外链使用 link 节点，不能猜测 OpenLink 的 type。
学城下载策略可能要求文枢客户端，API 会返回 resource_download_restricted，不修改白名单、不上传下载引导页。
持有原文件时可给 paste 加 resources：

```json
{"resources":[{"src":"<source-KM-resource-url>","file":{"path":"/tmp/task/original-file","name":"original.txt"}}]}
```

src 必须精确匹配被复制节点的 URL；本地原文件通过目标文档上传接口重新落地。

源内容仍须符合本地 Parker schema；schema 漂移时停止。

## 共享语义校验

```bash
kmedit schema --nodes attachment,heading,note,code_block,table_cell,xtable
```

API schema 的 attrs 包含 type、required、nonEmpty、enum、minimum/maximum、singleLine、example 等约束（适用时返回）；rules 描述节点之间的约束。
默认属性先由 Parker 补齐，再验证最终输出。不要从默认值猜类型，尤其不要把数字字节数写入 attachment.size。

- heading.level 为整数 1–6；note.type 为 info/note/warning/tip。link.href、mention.uid、emoji.name 等必填字符串不能空白。
- time.date 为有效的非零毫秒时间戳或 YYYY-MM-DD 日期；代码 language/theme 为非空字符串，保留 ts/js 等语言别名。
- 标题和代码块 title 不能换行；普通正文的换行使用 hard_break 或分段。代码块正文允许换行；保留标题已有的 quote 评论标记。
- 表格检查完整网格、跨行/跨列边界及列宽；colspan/rowspan 为正整数；写出的 colwidth 必须是与 colspan 等长的正数数组。null、缺失及数组内的 null/0 在写入前按逻辑列补齐：优先复用表内已有宽度，否则使用 Parker schema 默认宽度；有效显式宽度和 responsive 不变。被跨行单元格完全覆盖的空行合法。schema 接受 null 仅是历史读取兼容，不代表编辑器可渲染；不要生成 null 列宽。
- image.src/small/origin、附件、音视频和图形文件必须使用目标文档的永久 KM CDN 地址；外链或源文档地址应通过 paste 的资源迁移上传。专用 insert_yuntu 支持合法的 Yuntu iframe 地址。
- 通用 insert/replace/set_node_attrs 不能创建或改写托管宏资源；full 必须保留已有节点的 Provider 标识。新增资源走专用命令，不能仅填一个看似合法的 ID。
- 同一 xtableId 的新增或加剧重复会被拦截；存量重复允许保留或减少。新内容嵌套最多 100 层。

check 不上传、不注册 Pike；patch 在这些外部动作前预检，并在实际写入前重新验证。full 的 dry-run 同样执行校验。
semantic_validation_failed 返回 path/expected/actual；资源或生命周期错误使用 attachment_ownership_invalid/provider_lifecycle_required，通用托管宏创建返回 browserless_capability_unavailable。
已有异常字段保持不变时允许编辑其他内容或修复该字段；不要用新 ID 搬运异常数据。只读 inspect/copy 仍能导出存量数据，paste 作为新增内容执行严格校验。

## XLSX 与 DrawIO

Data2Chart data.path 支持 CSV/XLSX；data.sheet 指定工作表，默认第一张。
第一行必须匹配 data.header，读取日期、富文本、数字和公式缓存值；不执行公式，缺少缓存结果时停止。
DrawIO 多次编辑用 references/drawio.md 的本地草稿流程。复杂图形可在 converter 生成完整可编辑 SVG 后
API-only commit；本地子集 renderer 不承诺所有 draw.io stencil 的视觉等价。

## 预检与恢复

check 只读并使用假上传器/假 Provider，不创建附件、图表或协作 step；允许只读下载源资源以校验。
patch 重做完整预检后才创建资源。失败结果的 orphanedResources/providerStateDrift 必须保留用于处理。
commit_unverified 或 retrySafe=false 时先 inspect 当前文档，禁止自动重投。
草稿提交绑定 start 时版本，提交未知状态的草稿保持关闭；先读回判断结果，再开新草稿。
