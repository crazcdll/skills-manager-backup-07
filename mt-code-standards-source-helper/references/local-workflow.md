# 本地工作流与草稿格式

Node.js 24；无需模型 API Key 或第三方 ZIP/Markdown 依赖。Git 读取使用官方 @ee/code-cli 的本人会话并在线 whoami 核验，再读取固定 commit 的 raw 原件；学城使用官方 oa-skills CLI。Git 会话失效时运行 `code-cli auth login --browser` 完成本人登录，不通过其他产品缓存或 SSH archive 降级。工具缺失时提示用户按其环境安装/登录，不猜测凭据。

## 命令

以下 `<skill>` 为当前 Skill 目录，`<work>` 为本次新建的独立本地目录。不要直接写原材料仓库。

```shell
node <skill>/scripts/source-helper.mjs plan --source '<来源URL>'
node <skill>/scripts/source-helper.mjs prepare --request <request.json> --workspace <work>
node <skill>/scripts/source-helper.mjs preview --workspace <work> --draft <draft.json>
node <skill>/scripts/source-helper.mjs status --workspace <work>
```

确认前向用户展示 preview.html，说明其当前待确认项。以下命令只在用户明确确认当前预览后执行：

```shell
node <skill>/scripts/source-helper.mjs confirm --workspace <work> --preview-digest <当前preview_digest> --user-confirmed
node <skill>/scripts/source-helper.mjs package --workspace <work> --output <新的包路径.zip>
node <skill>/scripts/source-helper.mjs validate --package <包路径.zip>
```

`package` 不覆盖已存在的输出。`prepare --resume` 仅恢复冻结来源，不重新读取当前分支或学城最新版本；来源更新请用新任务目录。任务目录内有排他锁，不能并发修改；异常遗留锁须确认前次进程结束后由用户处理，不盲目删除。

## request.json

```json
{
  "schema_version": "source-helper-request/v1",
  "source_url": "https://dev.sankuai.com/code/repo-detail/team/repository/file/detail?path=rules.md&branch=refs%2Fheads%2Frules",
  "selection_type": "file",
  "actor_mis": "your.mis",
  "standard_domain": "frontend",
  "rule_set": {
    "name": "team-rules",
    "display_name": "团队规范",
    "description": "本次规范覆盖的问题域",
    "owner_mis": "当前确认的维护人MIS",
    "applicability_scope": "明确适用的团队和业务范围"
  }
}
```

示例值需替换为用户已提供的信息。source_url 支持 dev.sankuai.com 文件/目录地址，以及带 path/branch 的 git/code.sankuai.com 仓库地址。SSH clone URL 和无查询参数的仓库地址也可输入，但必须另填 path 和 branch；显式值不能与链接中的值冲突。branch 可显式单独传入 request，但不能与用户意图冲突；缺少分支会报错，工具不猜默认分支。目录选择使用 selection_type=directory，仅该目录内文件；AGENTS.md/agents.md 在所选根目录作为索引分离。

Git 和学城均需填写 actor_mis（当前本人登录用户），不能直接使用 Owner 冒充。学城 source_url 使用真实文档地址，可选 step_version。未指定时工具从官方历史列表选择最高有效 stepVersion 并在来源回执中展示；类型 1 不支持，不降级当前正文。类型 3/7 原件均用历史 data.body 原始字符串；类型 7 尚需真实样本验收，不声称已线上可用。

## 固定单元与草稿

prepare 生成 source.json、sources/ 原件、source-receipt.json、semantic-input.json 和待填写 draft.json。不要改写来源文件、单元标识或字节边界。

草稿顶层：

- schema_version 固定 `source-helper-draft/v1`。
- content 仅包含 documents、rules、coverage、resolutions。
- index_entries 包含 `{group,name,scene,document_ref}`，用于生成主题分组索引；名称、场景由实际材料支持。
- open_questions 包含 `{question_ref,message}`，有任何未解决问题都不能确认或封包。

documents/rules 与机器 Schema 相同，唯块 provenance 使用 `{origin,unit_refs,reason}`，不手填 source_spans。coverage 只写 `{unit_ref,disposition,targets,reason}`，工具从固定单元补 source_ref、范围与 Hash。content 的 schema_version、content_contract、agents_index 由工具生成，不能在草稿中手填。

原文块示意（替换真实单元与内容）：

```json
{
  "type": "markdown",
  "text": "固定单元里的原文或唯一匹配摘录",
  "provenance": {
    "origin": "source_extract",
    "unit_refs": ["固定读取器输出的unit_ref"],
    "reason": ""
  }
}
```

Git 可从单个或连续单元唯一匹配精确摘录；工具计算原始字节范围。学城仅从固定历史 JSON 的节点/文本值映射，不以原始 JSON Hash 代替文本验证。多位置相同文本需要缩小单元范围；不得随便取第一个。

生成或用户修改内容需要 origin=agent_generated/user_modified、非空原因和相关 unit_refs。示例块另含 role=good/bad/neutral、language、code、caption。规则至少一个要求 markdown 块；缺少 good/bad 时分别填写 omissions，并在 resolutions 记录用户决定。

每个源单元恰好一条 coverage：included/support 关联本来源文档或规则；support 要说明用途；excluded 没有 targets 且需要原因和 exclusion resolution。每条规则必须被覆盖目标关联。不可识别的学城组件显示为 unsupported，不能默默作为已解析内容纳入；应说明并让用户补成支持的文字来源，或明确排除。

## 预览与确认

preview 输出正文卡片、示例语言与高亮、来源标识、索引、排除决定和待确认项。超过十条规则按页展示，确认针对完整内容。HTML 不加载外部资源，用户提供内容经转义；Markdown 为本地受限展示，不是新事实来源。

待确认规则可以暂留 execution_level 为空或暂缺省略原因，preview 会显示校验问题；最终 confirm 必须通过全部校验，不能将暂缺值带入标准包。请求元信息也进入 content_digest，改名称、Owner 或适用范围需重新预览确认。

confirm 验证当前内容与已显示 preview_digest 相符，未回复或旧版本确认不能使用。确认记录仅证明本地流程绑定，不是身份签名。package 会重新生成并验证载荷、检查确认 Hash、写 STORE ZIP，再解包回读检查；不触发任何平台请求。

## 正式 Markdown 的支持边界

形成可审核候选前，本地检查文档/规则标题和正文的输出语义。支持 ATX/setext、CR/LF/CRLF、合法顶层代码围栏、非容器简单缩进代码及常见标题格式/数值与 ASCII 实体。普通无标题结构的 Rule ID 引用和代码示例可保留；如果正文标题会被误认成另一条正式规则，需要用户明确调整后重新确认。

本版本不是完整 CommonMark 实现。原始 HTML 块、标题中的原始 HTML/未知命名实体、引用或列表内部的围栏，以及含容器的缩进代码/标题歧义会给出明确提示。不能为绕过校验自动删改或转义用户已确认内容；应说明具体位置，让用户决定改为明确文字或独立代码块。

Markdown 标题资源预算：ATX/setext 的原始标题文本在任何复杂 inline 正则之前最多允许 2048 个 Unicode codepoint。超限明确拒绝并要求本地整理、重新确认，不截断或改写原文；这不降低普通正文块或代码示例的既有大小上限。中文与 emoji 按 codepoint 计数。

来源失败提示区分认证与权限：401 登录失效返回 SOURCE_AUTH_REQUIRED；403 或代码平台明确的 REPO_GUEST 权限拒绝返回 SOURCE_PERMISSION_DENIED，提示申请访问授权而非反复登录。学城安全屋错误保留经脱敏的明确恢复指引（如“请携带安全屋Token后重试”），不输出票据值、SQL、堆栈或完整原始错误流。

## 职责与确认边界

本 Skill 负责规范接入材料准备；平台校验并进入现有审核流程，发布与下载权限由平台既有流程管理。未明确确认当前预览，不生成 confirmation 或最终包；工具不自动上传或发布，本地内容确认不能替代平台审核。
