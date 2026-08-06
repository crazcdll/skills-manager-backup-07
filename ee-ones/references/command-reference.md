# 命令完整参数速查

> **加载时机**：当 SKILL.md 中的命令速查表和 Case 示例不够详细、Agent 需要查看某个命令的完整参数定义时，按需读取本文件。

---

## 查询类命令

```
ones issues                        查询指定空间的工作项列表
  -p, --project-id <id>            空间 ID（必填）
  -t, --type <type>                类型: REQUIREMENT | DEVTASK | DEFECT（默认 REQUIREMENT）
  -s, --state <state>              状态: ALL | TODO | DOING | DONE（默认 ALL）
  --page <n>                       页码（默认 1）
  --page-size <n>                  每页条数（默认 40）
  --json

ones ones-workitem-issues          查询指定空间的工作项列表（同 issues）
  -p, --project-id <id>            空间 ID（必填）
  -t, --type <type>                类型: REQUIREMENT | DEVTASK | DEFECT（默认 REQUIREMENT）
  -s, --state <state>              状态: ALL | TODO | DOING | DONE（默认 ALL）
  --page <n>                       页码（默认 1）
  --page-size <n>                  每页条数（默认 40）
  --json

ones filter-issues (别名: fi)      通过 DSL Query 筛选查询工作项
  -p, --project-id <id>            空间 ID（必填）
  -t, --type <type>                类型（逗号分隔多个）: REQUIREMENT | DEVTASK | DEFECT
                                   默认全部三种（需求/任务/缺陷）
  --query <json>                   DSL 筛选条件（JSON 对象或数组）
                                   示例: --query '[{"field":"name","type":"MATCH","value":"关键词"}]'
                                   详细说明见 filter-query-dsl.md
  -n, --name <keyword>             标题关键词（MATCH 全文搜索）
  --priority <priority>            优先级（逗号分隔）: 低/1、中/2、高/3、紧急/4
  -s, --state <state>              状态名称（逗号分隔）
  -a, --assigned <mis>             指派给（MIS 号，逗号分隔）
  -i, --iteration-id <id>          迭代 ID（启用迭代模式，支持多类型和树形展示）
  --iteration-mode                 强制迭代模式（displayType=ITERATIONITEM）
  --page <n>                       页码（默认 1）
  --page-size <n>                  每页条数（默认 40）
  -f, --fields <fields>            自定义展示字段（逗号分隔）
  --json                           输出 JSON（含完整 query DSL）

ones filter-views (别名: fv)       查询空间下的筛选视图列表
  -p, --project-id <id>            空间 ID（必填）
  -t, --type <type>                工作项类型: REQUIREMENT(R) | DEVTASK(D) | DEFECT(T)
                                   默认 REQUIREMENT
  -n, --name <name>                按视图名称筛选
  --json                           输出完整 JSON（含 query 条件和 columns 列表）

ones my                            查询我的待处理工作项（所有类型）
  -p, --project-id <id>            空间 ID（必填）
  --page <n> / --page-size <n> / --json

ones workbench (别名: wb)          获取工作台数据
  --json

ones search (别名: ws)             工作台交互式检索
  --json / --no-interactive

ones space-search (别名: ss)       空间内交互式检索
  -p, --project-id <id>            空间 ID（必填）
  -t, --type <type>                工作项类型（默认 REQUIREMENT）
  --page <n> / --page-size <n> / --json / --no-interactive
```

> **提示**：
> - `--no-interactive --json` 组合适合 agent 程序化解析，避免交互阻塞。
> - `filter-issues` 命令支持复杂的 DSL 查询，详见 [DSL Query 构建指南](./filter-query-dsl.md)。

---

## 详情与评论

```
ones workitem-detail               查询工作项详情
  -i, --issue-id <id>              工作项 ID（必填）
  -p, --project-id <id>            空间 ID（可选，加快查询）
  -t, --issue-type <type>          类型（可选）
  --json                           输出完整原始数据

ones workitem-comment (别名: wco)  工作项评论管理

  ones workitem-comment list       查询工作项评论
    -p, --project-id <id>          空间 ID（必填）
    -i, --issue-id <id>            工作项 ID（必填）
    -t, --issue-type <type>        类型（必填）: REQUIREMENT | DEVTASK | DEFECT
    --asc                          按时间升序排列（默认最新在前）
    --json

  ones workitem-comment add        添加评论 / 回复评论
    -p, --project-id <id>          空间 ID（必填）
    -i, --issue-id <id>            工作项 ID（必填）
    -t, --issue-type <type>        类型（必填）: REQUIREMENT | DEVTASK | DEFECT
    -m, --text <text>              评论内容（必填）
    -c, --comment-id <commentId>   被回复的评论 ID（传此参数时为回复评论，通过 list 子命令查询获取）
    --to-users <users>             @ 的用户 MIS（多个用逗号分隔）
    --json
```

> **@ 人功能说明**：`--to-users` 传入用户 MIS 后，CLI 会自动：
> 1. 调用用户搜索接口查询每个 MIS 的中文显示名（全局搜索，不限空间）
> 2. 在评论 HTML 中自动生成 `ct-mention` 标签（包含中文显示名）
> 3. 请求体中 `toUsers` 字段传入精确 MIS 列表
>
> **Agent 场景**：`--to-users` 必须传入精确的 MIS 号（如 `jiangshaowei`），不支持模糊关键字。若 MIS 精确匹配，全程无交互直接完成。若搜索不到或匹配多个结果，非交互模式下会报错并列出候选用户，Agent 应根据候选列表修正 MIS 后重试。
>
> **注意**：`workitem-detail --json` 返回的 `projectId`（空间 ID）、`iterationId` 等字段，是后续命令的关键输入来源。

---

## 工作项资产管理

```
ones workitem-asset (别名: wa)     工作项资产管理（查询/添加/更新/移除）

  ones workitem-asset list (别名: ls)  查询工作项资产列表
    -i, --workitem-id <workitemId>     工作项 ID（必填）
    --json                             以 JSON 格式输出

  ones workitem-asset add              添加工作项资产
    -i, --workitem-id <workitemId>     工作项 ID（必填）
    --title <title>                    资产标题（必填）
    --url <url>                        资产链接（必填）
    --type <type>                      资产类型（必填）: MRD | BRD | PRD | DESIGN_DRAFT | TD
                                       | TEST_DOCUMENT | TEST | MANUAL | OTHER
    --json                             以 JSON 格式输出

  ones workitem-asset update           更新工作项资产
    -i, --workitem-id <workitemId>     工作项 ID（必填）
    -a, --asset-id <assetId>           资产 ID（必填，通过 list 获取）
    --title <title>                    资产标题（必填）
    --url <url>                        资产链接（必填）
    --type <type>                      资产类型（必填）: MRD | BRD | PRD | DESIGN_DRAFT | TD
                                       | TEST_DOCUMENT | TEST | MANUAL | OTHER
    --json                             以 JSON 格式输出

  ones workitem-asset remove (别名: rm)  移除工作项资产
    -i, --workitem-id <workitemId>     工作项 ID（必填）
    -a, --asset-id <assetId>           资产 ID（必填，通过 list 获取）
```

> **资产类型说明**：MRD(市场需求文档)、BRD(商业需求文档)、PRD(产品需求文档)、DESIGN_DRAFT(设计稿)、TD(技术文档)、TEST_DOCUMENT(测试方案)、TEST(测试报告)、MANUAL(操作手册)、OTHER(其他)。
>
> **资产 ID 获取**：通过 `ones wa list -i <工作项ID>` 或 `ones wa list -i <工作项ID> --json` 查询。

---

## 工作项附件管理

```
ones workitem-attachment (别名: watt)  工作项附件管理（上传/删除）

  ones workitem-attachment upload         上传本地文件作为工作项附件
    -i, --issue-id <issueId>              工作项 ID（必填）
    -f, --file <filePath>                 本地文件路径（必填，支持绝对/相对路径）
    --json                                以 JSON 格式输出上传结果

  ones workitem-attachment delete (别名: rm)  删除工作项附件（❗ 强制二次确认，不可恢复）
    -i, --issue-id <issueId>              工作项 ID（必填，用于查询附件列表展示确认）
    -a, --attachment-id <attachmentId>    附件 ID（必填，从 workitem-detail 获取）
```

> **注意**：
> - 附件删除操作**强制二次确认**（需输入 `delete` 确认），无法通过 `-y` 跳过，不适合自动化流程
> - 附件 ID 通过 `ones workitem-detail -i <ID> --json` 返回的 `attachments` 字段获取
> - 上传文件支持绝对路径和相对于当前工作目录的相对路径

---

## 工作项 CRUD

```
ones workitem-create (别名: wc)    创建工作项（非交互式，全参数模式）
  -t, --type <type>                工作项类型（必填）: REQUIREMENT | DEVTASK | DEFECT（或: 需求/任务/缺陷/bug）
  -p, --project-id <id>            空间 ID（必填）
  -s, --subtype-id <id>            子类型 ID（必填，使用 ones vs 查询）
  --priority <priority>            优先级（必填）: 低(1) / 中(2) / 高(3) / 紧急(4)
  --title <title>                  工作项标题（必填）
  --desc <desc>                    描述（可选，支持 HTML）
  --assigned <mis>                 指派给（可选，用户 MIS 号）
  -F, --field <key=value>          自定义字段（可多次使用，如 -F customField13200=1773590400000）
                                   · 整数值自动转 number，如 -F customField23767=1330
                                   · JSON 数组，如 -F customField24988=["630^20040"]
                                   · 字符串，如 -F customField13031=1773590400000
  --json                           输出创建结果 JSON
  -y, --yes                        跳过确认直接创建

ones workitem-update (别名: wu)    更新工作项字段
  -i, --id <issueId>               工作项 ID（必填）
  --name <name>                    工作项标题
  --desc <desc>                    描述信息（支持 HTML）
  --priority <priority>            优先级: 低(1) / 中(2) / 高(3) / 紧急(4)
  --assigned <misId>               指派给（用户 MIS 号）
  --expect-time <value>            预计工作量（支持单位：8h / 1d / 0.5d / 纯数字）
                                   自动根据空间工时配置换算单位
  -F, --field <json>               自定义字段（WorkitemValueField JSON，可多次使用）
                                   示例: -F '{"variable":"customField13200","name":"截止时间","type":"component_time","multiple":false,"fieldValue":1773590400000}'
  -y, --yes                        跳过确认直接更新

ones workitem-delete (别名: wd)    删除工作项（⚠️ 不可恢复）
  -i, --id <issueId>               工作项 ID（必填）
  -c, --delete-children            同时删除所有子工作项（默认只删除本身）
  -y, --yes                        跳过确认
```

> **创建工作项典型用法**：
>
> ```bash
> # 基础创建
> ones wc -t REQUIREMENT -p 36351 -s 249741 --priority 中 --title "优化搜索性能" -y
>
> # 带可选参数
> ones wc -t REQUIREMENT -p 36351 -s 249741 --priority 高 --title "新功能" \
>   --assigned liqianlong --desc "<p>需求描述</p>" -y
>
> # 带自定义字段（通过 ones fs + ones fo 获取字段信息）
> ones wc -t REQUIREMENT -p 36351 -s 249741 --priority 中 --title "新需求" \
>   -F customField23767=1330 -F customField24988='["630^20040"]' -y
> ```
>
> **如何获取 subtypeId**：先用 `ones vs -p <空间ID> -s <任意数字> --help` 或直接运行 `ones vs -p <空间ID> -s 0` 报错提示可用子类型，也可通过 ONES 页面 URL 中的 subtype 参数获取。
>
> **如何获取自定义字段**：`ones fs -p <空间ID> -t REQUIREMENT` 查询字段列表，`ones fo -p <空间ID> -f <字段ID> -t <字段类型>` 查询可选值。

---

## 空间管理

```
ones spaces (别名: sp)             查询空间列表
  -n, --name <name>                按名称模糊搜索
  --page <n> / --page-size <n> / --json

ones space-apps (别名: apps)       搜索空间内应用（用于创建分支前选择目标仓库）
  -p, --project-id <id>            空间 ID（必填）
  -n, --name <name>                应用名称 / appkey / 仓库 repo 地址（必填）
                                   ★ Agent 策略：优先用当前仓库 remote 地址：
                                     git remote get-url origin → 将完整地址直接传入，无需提取仓库名
                                     若不在 git 仓库 / 无 remote → 再询问用户提供
                                   ⚠️ 搜索无结果时禁止自行更换关键词重试，应立即告知用户
```

> **实现细节**：
> - 命令内部**自动并发查询所有应用类型**（SERVER / MAVEN / WEB / APP / OTHER / DEV），无需手动指定 `--app-type`
> - 自动翻页直到取完所有匹配数据，无需手动分页
> - 输出固定为 JSON 格式（`SpaceAppItem[]`），关键字段：`id`（应用 ID）、`appkey`、`name`、`appType`、`repo`（SSH 地址）、`repoName`
> - 搜索无结果时 CLI 会输出引导提示并 `exit 1`，Agent 应将提示转达给用户

---

## 应用管理

```
ones app-search-server (别名: asr)  搜索空间内 SERVER 类型的关联应用
  -p, --project-id <projectId>      空间 ID（必填）
  -n, --name <name>                  应用名称关键词（必填），如: worktime
  --json                             以 JSON 格式输出（默认即为 JSON）

ones app-search-maven (别名: asm)   搜索 MAVEN 类型的应用（通过 git 仓库地址）
  -g, --git-repository <gitRepository>  Git 仓库地址（必填）
                                     提示：可通过 git remote get-url origin 获取当前仓库地址
                                     若地址没有 .git 后缀则自动补上
                                     示例: ssh://git@git.sankuai.com/ee/ones-worktime-service.git
  --json                             以 JSON 格式输出（默认即为 JSON）

ones app-search-web (别名: asw)     搜索 WEB 类型的应用信息（通过 appKey）
  -k, --app-key <appKey>             appKey（必填）
                                     示例: com.sankuai.epinfra.adminweb.static
  --json                             以 JSON 格式输出（默认即为 JSON）

ones app-search-app (别名: asa)     搜索 APP（客户端）类型的组件信息（通过 componentName）
  -p, --space-id <spaceId>           空间 ID（必填）
  -c, --component-name <componentName>  组件名称（必填）
                                     示例: com.meituan.android.dynamiclayout:test
  --json                             以 JSON 格式输出（默认即为 JSON）

ones app-search-dev (别名: asd)     搜索 DEV 类型的应用信息（通过名称关键词）
  -n, --name-filter <nameFilter>     名称关键词（必填），示例: ONES
  --page-number <pageNumber>         页码（默认 1）
  --page-size <pageSize>             每页条数（默认 50）
  --json                             以 JSON 格式输出（默认即为 JSON）

ones app-add-server (别名: aas)     关联 SERVER 类型应用到空间
  -p, --project-id <projectId>       空间 ID（必填）
  -a, --app-ids <appIds>             应用 ID，多个用逗号分隔（必填）
                                     可通过 app-search-server 命令获取 id 字段

ones app-relate-server (别名: ars)  关联 SERVER 类型应用到空间（同 app-add-server）
  -p, --project-id <projectId>       空间 ID（必填）
  -a, --app-ids <appIds>             应用 ID，多个用逗号分隔（必填）
                                     可通过 app-search-server 命令获取 id 字段

ones app-add-maven (别名: aam)      添加 MAVEN 类型应用到空间
  -p, --project-id <projectId>       目标空间 ID（必填）
  --id <id>                          应用 ID（必填，来自 app-search-maven 结果的 id 字段）
  --app-key <appKey>                 appKey（必填，来自 app-search-maven 结果的 appKey 字段）
  -n, --name <name>                  应用名称（必填，来自 app-search-maven 结果的 name 字段）
  --alias <alias>                    应用别名（必填，来自 app-search-maven 结果的 alias 字段）
  -g, --git-repository <gitRepository>  Git 仓库地址（必填，来自 app-search-maven 结果的 gitRepository 字段）

ones app-add-web (别名: aaw)        添加 WEB 类型应用到空间
  -p, --project-id <projectId>       目标空间 ID（必填，需用户确认）
  -k, --app-key <appKey>             appKey（必填，来自 app-search-web 结果的 appKey 字段）
  -n, --name <name>                  应用名称（必填，来自 app-search-web 结果的 name 字段）
  -r, --repo <repo>                  Git 仓库地址（必填，来自 app-search-web 结果的 gitRepository 字段）

ones app-add-app (别名: aaa)        添加 APP（客户端）类型应用到空间
  -p, --space-id <spaceId>           目标空间 ID（必填，需用户确认）
  -n, --name <name>                  组件名称（必填，来自 app-search-app 结果的 name 字段）
  -k, --kind <kind>                  组件类型（必填，来自 app-search-app 结果的 kind 字段，如 android）
  -b, --bu-info <buInfo>             BU 信息（必填，来自 app-search-app 结果的 buInfo 字段）
  -r, --repo-url <repoUrl>           Git 仓库地址（必填，来自 app-search-app 结果的 repoUrl 字段）
  -a, --admin <admin>                管理员 MIS（必填，来自 app-search-app 结果的 admin 字段）

ones app-add-dev (别名: aad)        添加 DEV 类型应用到空间
  -p, --space-id <spaceId>           空间 ID（必填）
  -n, --name <name>                  应用名称（必填，来自 app-search-dev 结果的 name 字段）
  -r, --repos <repos>                仓库地址列表，多个用逗号分隔（必填，来自 app-search-dev 结果的 repos 字段）
  -t, --project-type <projectType>   项目类型（必填，来自 app-search-dev 结果的 type 字段，如 NON_STANDARD_SRV）
  -a, --admin <admin>                管理员 misId（必填，来自 app-search-dev 结果的 admin 字段）

ones app-add-other (别名: aao)      添加 OTHER 类型应用到空间（手动录入）
  -p, --space-id <spaceId>           目标空间 ID（必填）
  -r, --repo-url <repoUrl>           Git 仓库地址（必填，可通过 git remote get-url origin 获取）
  -n, --name <name>                  应用名称（可选，默认从 repoUrl 中提取仓库名）
```

> **应用管理编排流程**：
>
> 1. **搜索应用**：根据应用类型使用对应的搜索命令获取应用信息
>    - SERVER：`ones app-search-server -p <空间ID> -n <关键词>` → 返回 id、releaseName、repo
>    - MAVEN：`ones app-search-maven -g <git仓库地址>` → 返回 id、appKey、name、alias、gitRepository
>    - WEB：`ones app-search-web -k <appKey>` → 返回 appKey、gitRepository、name
>    - APP：`ones app-search-app -p <空间ID> -c <componentName>` → 返回 name、kind、buInfo、repoUrl、admin
>    - DEV：`ones app-search-dev -n <关键词>` → 返回 id、name、type、admin、repos
>
> 2. **添加应用**：将搜索结果中的字段传入对应的添加命令
>    - SERVER：`ones app-add-server -p <空间ID> -a <id>` 或 `ones app-relate-server -p <空间ID> -a <id>`
>    - MAVEN：`ones app-add-maven -p <空间ID> --id <id> --app-key <appKey> -n <name> --alias <alias> -g <gitRepository>`
>    - WEB：`ones app-add-web -p <空间ID> -k <appKey> -n <name> -r <gitRepository>`
>    - APP：`ones app-add-app -p <空间ID> -n <name> -k <kind> -b <buInfo> -r <repoUrl> -a <admin>`
>    - DEV：`ones app-add-dev -p <空间ID> -n <name> -r <repos> -t <type> -a <admin>`
>    - OTHER（手动录入）：`ones app-add-other -p <空间ID> -r <repoUrl> [-n <name>]`
>
> 3. **验证添加结果**：`ones space-apps -p <空间ID> -n <应用名称>`
>
> **Agent 策略**：
> - MAVEN 搜索时，优先通过 `git remote get-url origin` 获取当前仓库地址作为 `-g` 参数
> - OTHER 类型无需搜索，直接通过仓库地址手动录入
> - 添加操作完成后建议用 `space-apps` 验证是否添加成功

---

## 分支管理

```
ones branch-gen (别名: bg)         根据工作项 ID 生成 Git 分支名称
  -i, --issue-id <id>              工作项 ID（必填）
  -t, --type <type>                分支类型（默认: feature）
                                   可选: feature | bugfix | hotfix | release | test | develop
  --copy                           同时输出 git checkout -b 命令

ones branch (别名: br)             查询工作项关联的分支信息
  -p, --project-id <id>            空间 ID（必填）
  -i, --issue-id <id>              工作项 ID（必填）
  --no-include-children            不包含子工作项的分支（默认包含子工作项）
  --page <n> / --page-size <n> / --json

ones branch-create (别名: bc)      创建分支并关联工作项
  -i, --issue-id <id>              工作项 ID（必填）
  -t, --type <type>                分支类型（默认: feature）
  -a, --app-id <appId>             应用 ID（不传则交互选择）
  -b, --base-branch <name>         基础分支（默认: master）
  --json

ones branch-associate (别名: ba)   关联已有分支到工作项
  -n, --name <name>                分支名称（必填）
  -p, --project-id <id>            空间 ID（必填）
  -a, --app-id <appId>             应用 ID（必填）
  -t, --task-id <taskId>           工作项 ID（必填）
  --branch-type <type>             分支类型（默认: feature）
  --json

ones branch-search (别名: bs)      根据分支名称搜索
  -f, --filter <filter>            分支名称关键字（必填）
  -p, --project-id <id>            空间 ID（必填）
  -a, --app-id <appId>             应用 ID（必填）
  -s, --sn <sn>                    返回条数（默认: 25）
  --json

ones branch-disassociate (别名: bd)  取消分支关联
  -b, --branch-id <branchId>       分支 ID（必填）
  --json

ones branch-workitems (别名: bw)    根据仓库地址和分支名称查询关联的工作项
  -r, --repo <repo>                仓库 SSH 地址（必填），如 ssh://git@git.sankuai.com/ee/xxx.git
  -b, --branch-name <branchName>   分支名称（必填）
  --json
```

> **提示**：分支操作通常需要 appId，通过 `ones apps -p <空间ID> -n <仓库地址>` 查询获取。**Agent 应优先用当前仓库 remote 地址**（`git remote get-url origin` → 将完整地址直接传入）作为 `-n` 参数，避免询问用户。`branchId` 通过 `ones branch --json` 获取。

---

## 迭代管理

```
ones iterations (别名: iter)       查询空间下的迭代列表
  -p, --project-id <id>            空间 ID（必填）
  -n, --name <name>                按名称模糊搜索
  --page-size <n>                  每页条数（默认: 不搜索=100，搜索=20）
  --page <n>                       页码（仅搜索时生效）
  --json

ones create-iteration (别名: ci)   创建迭代（交互式引导）
  -p, --project-id <id>            空间 ID
  -n, --name <name>                迭代名称
  -s, --start-date <date>          开始日期（YYYY-MM-DD）
  -e, --end-date <date>            结束日期（YYYY-MM-DD）
  -d, --description <desc>         描述
  --hr <mode>                      人力配置: last（复制上一迭代，默认）| project（复制空间配置）
  -y, --yes                        跳过确认

ones update-iteration (别名: ui)   编辑迭代
  -p, --project-id <id>            空间 ID
  -i, --iteration-id <id>          迭代 ID
  -n, --name <name>                新名称
  -s, --start-date <date>          新开始日期
  -e, --end-date <date>            新结束日期
  -d, --description <desc>         新描述
  -y, --yes                        跳过确认

ones delete-iteration (别名: di)   删除迭代（⚠️ 不可恢复）
  -p, --project-id <id>            空间 ID
  -i, --iteration-id <id>          迭代 ID
  -y, --yes                        跳过确认

ones set-iteration (别名: si)      修改工作项所属迭代
  -i, --issue-id <id>              工作项 ID
  -t, --iteration-id <id>          目标迭代 ID
  --clear                          清空迭代
  --sync-child                     同步修改子工作项
  -y, --yes                        跳过确认

> **迭代工作项查询**：使用 `ones filter-issues -i <迭代ID>` 代替 `iteration-issues`，
> 支持多类型查询和树形展示。详见 filter-issues 命令说明。
```

---

## 测试管理

### 用例

```
ones case-create (别名: case-c)    创建用例（指派人默认当前用户）
  -p, --project-id <id>            空间 ID（非交互模式必填）
  -s, --space-name <name>          空间名称关键字
  --title <title>                  标题（非交互模式下必填字段必须通过参数提供）
  --desc <desc>                    描述
  --priority <priority>            优先级: 低/中/高/紧急 或 1~4（非交互模式下必须在可选值范围内）
  -y, --yes                        非交互模式：跳过所有交互，字段值来自命令行参数和 API 默认值

ones case-update (别名: case-u)    更新用例（标题、优先级、状态）
  -i, --id <id>                    用例 ID
  --space <spaceId>                空间 ID（可选，自动从详情中提取）
  -f, --field <fieldName>          要修改的字段名（标题 / 优先级 / 状态）
  --val <value>                    新值（直接指定，跳过交互式选择）
  -y, --yes                        非交互模式：跳过确认，必须同时提供 -f 和 --val，值必须是 API 返回的合法值

ones case-delete (别名: case-d)    删除用例
  -i, --id <id>                    用例 ID
  -c, --delete-children            同时删除子项
  -y, --yes                        跳过确认

ones case-space-search (别名: case-ss)  空间内检索用例
  -p, --project-id <id>            空间 ID（必填）
  --page <n> / --page-size <n> / --json / --no-interactive

ones case-detail (别名: case-info)     查询测试用例详情（基础信息 + 测试步骤 + 可选关联需求 & 缺陷）
  -i, --issue-id <id>              测试用例 ID（必填）
  -p, --project-id <id>            所属空间 ID（关联查询时若详情未返回空间信息则必填）
  --with-requirements              同时查询关联需求列表
  --with-defects                   同时查询关联缺陷列表
  --all                            查询详情 + 关联需求 + 关联缺陷（等价于 --with-requirements --with-defects）
  --json                           以 JSON 格式输出原始数据

ones case-tree                         用例树浏览与用例查询：展示测试集目录树，或查询指定目录下的用例列表
  -p, --project-id <id>            空间 ID（必填）
  --dir-id <dirId>                 指定目录节点 ID，只查询该目录下的用例（不传则查全量）
  --list-dirs                      仅展示用例目录树，不查询用例列表
  --list-views                     仅展示空间下的用例视图列表（用于获取 --view-id）
  --view-id <viewId>               视图 ID：自动加载视图的预设筛选条件（使用 --list-views 查看可用视图）
  --query <json>                   DSL 筛选条件（JSON 对象或数组）
                                   示例: --query '[{"field":"name","type":"MATCH","value":"关键词"}]'
                                   支持: TERM / TERMS / MATCH / RANGE / TIME_RANGE / EXISTS / NOTEXISTS / NOTMATCH / MATCH_PHRASE
                                   常用字段: name(标题) / state(状态) / priority(优先级) / assigned(指派给)
  -n, --name <keyword>             标题关键词快捷筛选（MATCH 全文搜索）
  -s, --state <state>              状态快捷筛选（逗号分隔多个），如 --state 评审中,设计中
  -a, --assigned <mis>             指派给快捷筛选（MIS 号，逗号分隔多个）
  --priority <priority>            优先级快捷筛选（逗号分隔多个）：低/1、中/2、高/3、紧急/4
  --page <n>                       页码（查询模式，默认 1）
  --page-size <n>                  每页条数（查询模式，默认 40）
  --json                           以 JSON 格式输出原始数据（含完整 DSL 筛选条件）
  --no-interactive                 跳过交互式筛选器（保留视图/预设条件），直接查询
```

> **case-tree 典型用法**：
>
> ```bash
> # 浏览目录树（获取 dirId）
> ones case-tree -p <空间ID> --list-dirs
> # 查询指定目录下的用例（交互式筛选）
> ones case-tree -p <空间ID> --dir-id <目录ID>
> # 先看视图列表，再用视图条件查询
> ones case-tree -p <空间ID> --list-views
> ones case-tree -p <空间ID> --view-id <视图ID> --no-interactive
> # 直接关键词搜索（非交互）
> ones case-tree -p <空间ID> -n "登录" --no-interactive
> ```

### 计划

```
ones plan-create (别名: plan-c)    创建测试计划
  -c, --scene <scene>              场景: REQUIREMENT（需求类）| SCENE（场景类）（非交互模式必填）
  -p, --project-id <id>            空间 ID（非交互模式必填）
  -s, --space-name <name>          空间名称关键字
  --title <title>                  标题（非交互模式必填）
  --principal <mis>                测试主R（默认当前用户）
  --requirement-ids <ids>          关联需求 ID（逗号分隔，仅需求类）
  --desc <desc>                    描述
  --start-time <date>              预计开始时间（YYYY-MM-DD，非交互模式下无效格式会报错退出）
  --end-time <date>                预计结束时间（YYYY-MM-DD，非交互模式下无效格式会报错退出）
  -y, --yes                        非交互模式：跳过确认，必须提供 --scene、-p、--title

ones plan-update (别名: plan-u)    更新测试计划
  -i, --id <id>                    计划 ID
  -p, --project-id <id>            空间 ID
  -f, --field <fieldName>          要修改的字段名（标题/测试主R/描述/预计开始时间/预计结束时间）
  --val <value>                    新值（直接指定）
  -y, --yes                        非交互模式：跳过确认，必须同时提供 -i、-p、-f、--val

ones plan-search (别名: plan-s)    搜索测试计划
  -p, --project-id <id>            空间 ID（必填）
  --state <state>                  状态: WAITTEST | TESTING | TESTED | PAUSE
  --name <name>                    标题关键字
  --req-id <reqId>                 关联需求 ID
  --principal <mis>                测试主R
  --created-by <mis>               创建人
  --page <n> / --page-size <n> / --json / --no-interactive

ones plan-delete (别名: plan-d)    删除测试计划（支持批量）
  -i, --ids <ids>                  计划 ID（逗号分隔）
  -y, --yes                        跳过确认
```

> `-c REQUIREMENT` 必须关联至少一个需求；状态可选值：WAITTEST / TESTING / TESTED / PAUSE

### 轮次

```
ones round-create (别名: round-c)         创建轮次
  -p, --project-id <id>                   空间 ID
  -s, --space-name <name>                 空间名称关键字
  --plan-id <planId>                      所属计划 ID
  -t, --type <type>                       类型: SMOKE_TEST | FUNCTION_TEST | REGRESSION_TEST
  --title <title>                         名称

ones round-update (别名: round-u)         更新轮次名称
  -i, --id <id> / -p, --project-id <id> / --name <name>

ones round-delete (别名: round-d)         删除轮次
  -i, --id <id> / -p, --project-id <id> / -y, --yes

ones round-case (别名: round-ca)          添加/删除轮次用例
  -p, --project-id <id>                   空间 ID
  -r, --round-id <id>                     轮次 ID
  --plan-id <planId>                      计划 ID
  -a, --action <action>                   操作: ADD | DEL
  --case-ids <ids>                        用例 ID 列表（逗号分隔，仅 ADD 操作，配合 -y 使用）
  --items <pairs>                         执行用例ID:用例ID 对（逗号分隔，仅 DEL 操作，配合 -y 使用，如 "100:200,101:201"）
  -y, --yes                               非交互模式：跳过确认，必须提供 -a 和 --case-ids/--items

ones round-case-update (别名: round-cu)   更新执行用例状态
  -p, --project-id <id>                   空间 ID
  -r, --round-id <id>                     轮次 ID
  -s, --state <state>                     目标状态: UNDONE | SUCCESS | FAIL | LATER
  --items <pairs>                         执行用例ID:用例ID 对（逗号分隔，配合 -y 使用，如 "100:200,101:201"）
  -y, --yes                               非交互模式：跳过确认，必须提供 -s 和 --items

ones round-case-executor (别名: round-ce) 更新执行用例执行人
  -r, --round-id <id>                     轮次 ID
  --items <pairs>                         用例ID:执行人 对（逗号分隔，配合 -y 使用，如 "100:zhangsan,101:lisi"）
  -y, --yes                               非交互模式：跳过确认，必须提供 -r 和 --items

ones round-case-search (别名: round-cs)   查询轮次内执行用例
  -p, --project-id <id>                   空间 ID
  -r, --round-id <id>                     轮次 ID
  -s, --state <state>                     状态过滤
  --priority <n>                          优先级: 1~4
  --executor <mis>                        执行人
  -n, --name <name>                       标题关键字
  --page <n> / --page-size <n> / --json / -i, --interactive

ones round-case-link-issue (别名: round-cli)  关联缺陷
  -p, --project-id <id>                   空间 ID
  --plan-id <planId>                      计划 ID
  -r, --round-id <id>                     轮次 ID
  -c, --plan-case-id <id>                 执行用例 ID
  -i, --issue-id <id>                     缺陷 ID
```

> 轮次类型：SMOKE_TEST（冒烟）/ FUNCTION_TEST（功能）/ REGRESSION_TEST（回归）

---

## 提测管理

```
ones submit-test (别名: st)        查询提测详情
  -p, --project-id <id>            空间 ID（必填）
  -i, --issue-id <id>              提测单 ID（必填）
  --json

ones submit-test-create (别名: stc)  创建提测单（交互式引导）
  -p, --project-id <id>            空间 ID（跳过空间选择）
  -s, --space-name <name>          空间名称关键字
  --title <title>                  标题（预填）
  -y, --yes                        跳过确认
  --json

ones submit-test-update (别名: stu)  更新提测状态
  -p, --project-id <id>            空间 ID（必填）
  -i, --issue-id <id>              提测单 ID（必填）
  -s, --state <state>              目标状态名称（支持模糊匹配）
  -y, --yes                        跳过确认

ones submittest list (别名: ls)     根据工作项 ID 查询关联的提测列表
  -p, --project-id <id>            空间 ID（必填，可通过 ones workitem-detail -i <工作项ID> 查询获取）
  -i, --issue-id <id>              工作项 ID（必填，需求/任务/缺陷的 ID）
  --page <n>                       页码（默认 1）
  --page-size <n>                  每页条数（默认 20）
  --json
```

---

## 工时管理

```
ones worktime-list (别名: wtl)     查询已填工时的工作项
  -s, --start <date>               开始日期（YYYY-MM-DD），默认本周一
  -e, --end <date>                 结束日期（YYYY-MM-DD），默认本周日
  --page <n> / --page-size <n> / --json

ones worktime-detail (别名: wtd)   查询工作项的工时日志
  -i, --issue-id <id>              工作项 ID（必填）
  --page <n> / --json

ones worktime-summary (别名: wts)  查询每天的工时汇总
  -s, --start <date>               开始日期，默认本周一
  -e, --end <date>                 结束日期，默认本周日
  --json

ones worktime-search (别名: wtsearch)  检索可填工时的工作项
  -n, --name <keyword>             名称关键字（模糊搜索）
  -s, --start <date>               开始日期，默认本周一
  -e, --end <date>                 结束日期，默认本周日
  -t, --type <type>                类型（需求/任务/缺陷）
  --page <n> / --page-size <n> / --json

ones worktime-save (别名: wtadd)   填写工时
  -i, --issue-id <id>              工作项 ID（必填）
  --hours <value>                  工时数（必填），格式: 8h / 1d / 纯数字
  -d, --date <date>                日期，默认今天；范围: YYYY-MM-DD~YYYY-MM-DD
  -t, --issue-type <type>          工作项类型（自动获取）
  -p, --space-id <id>              空间 ID（自动获取）
  --add-type <type>                填写类型，默认 TOTAL
  --desc <desc>                    工时描述
  --include-weekend                包含周末（默认 false）
  -y, --yes                        跳过确认
  --json

ones worktime-update (别名: wtu)   修改工时
  --id <id>                        工时记录 ID（必填，通过 wtd 获取）
  -i, --issue-id <id>              工作项 ID（必填）
  --hours <value>                  新的工时数
  -d, --date <date>                日期
  -t, --issue-type <type>          工作项类型（自动获取）
  -p, --space-id <id>              空间 ID（自动获取）
  --add-type <type>                填写类型
  --desc <desc>                    描述
  --include-weekend / -y, --yes / --json

ones worktime-delete (别名: wtdel) 删除工时记录
  --id <id>                        工时记录 ID（通过 wtd 获取）
  -y, --yes                        跳过确认

ones worktime-save-for (别名: wtadd-for)  替他人填写工时
  --operator <misId>               被填工时人的 MIS 号（必填）
  -i, --issue-id <id>              工作项 ID（必填）
  --hours <value>                  工时数，格式: 8h(人时) / 1d(人天) / 纯数字
  -d, --date <date>                日期，默认今天；范围: YYYY-MM-DD~YYYY-MM-DD
  -t, --issue-type <type>          工作项类型（自动获取，一般无需指定）
  -p, --space-id <id>              空间 ID（自动获取，一般无需指定）
  --add-type <type>                填写类型，默认 TOTAL
  --desc <desc>                    工时描述
  --include-weekend                包含周末（默认 false，跨周末时会交互确认）
  -y, --yes                        跳过交互确认（周末默认不包含）
  --json

ones worktime-team (别名: wtteam)  查看团队实际工作量（周维度）
  --offset <n>                     周偏移量（0=本周，-1=上周，-2=上上周），默认 0
  --page-size <n>                  每次查询返回的成员条数（默认 200）
  --member <misIds>                查看指定成员的工作项工时明细（逗号分隔多个 MIS 号）
                                   不传则展示团队汇总
  --detail                         详细模式：逐人展示每天工时行（仅汇总模式生效）
  --json
```

> **注意**：工时记录 ID 只能通过 `wtd` 命令获取，不能猜测。
> **wtteam 说明**：团队汇总模式需登录用户所在直属组权限，orgId 自动探测并缓存。

---

## 字段管理

```
ones field-search (别名: fs)   查询空间字段列表
  -p, --project-id <id>            空间 ID（必填）
  -t, --issue-type <type>          工作项类型: REQUIREMENT | DEVTASK | DEFECT（默认 REQUIREMENT）
  -n, --name <name>                字段名称关键字（模糊搜索）
  --page <n>                       页码（默认 1）
  --page-size <n>                  每页条数（默认 20）
  --is-work-time-group             查询工时字段（预计/实际工作量等）
  --json

ones field-options (别名: fo)  查询字段的可选值列表
  -p, --project-id <id>            空间 ID（必填）
  -f, --field-id <id>              字段 ID（必填，通过 fs 获取）
  -t, --field-type <type>          字段类型（必填，如 component_user、component_iteration、list 等）
  -i, --issue-id <id>              工作项 ID（component_state 类型必传）
  -s, --sub-type <type>            工作项类型: REQUIREMENT | DEVTASK | DEFECT（不传则交互选择）
  -u, --username <keyword>         用户名关键字（仅 component_user 类型有效）
  --page-size <n>                  每页条数（默认 50）
  --json                           以 JSON 格式输出原始接口数据
```

> **提示**：字段管理命令主要用于创建/更新工作项时的字段参考。`fs` 查询字段列表获取 `variable` 和 `type`，然后用 `fo` 查询具体字段的可选值。默认以表格/树形结构友好展示，传 `--json` 输出原始 JSON 便于程序化解析。

---

## 排期管理

```
ones schedule-query (别名: sq)       查询工作项排期信息（含各阶段排期事项）
  -p, --space-id <id>                空间 ID（必填）
  -i, --issue-id <id>                工作项 ID（必填）
  -s, --stage <stage>                指定阶段: DESIGNING(规划) / DEVELOPING(开发) / TESTING(测试) / PUBLISHING(发布)（可选，不传则查全部）
  --json                             以 JSON 格式输出（含排期详情、统计、各阶段事项）

ones schedule-item-create (别名: sic)  在排期阶段下新建排期事项
  -p, --space-id <id>                空间 ID（必填）
  -i, --issue-id <id>                工作项 ID（必填）
  -s, --stage <stage>                排期阶段（必填）: DESIGNING(规划) / DEVELOPING(开发) / TESTING(测试) / PUBLISHING(发布)
  --index <index>                    排序索引（默认 0）
  --json                             以 JSON 格式输出

ones schedule-item-update (别名: siu)  更新排期事项（名称/指派给/工作量/预计时间）
  -p, --space-id <id>                空间 ID（必填）
  -i, --issue-id <id>                工作项 ID（必填）
  --item-id <itemId>                 排期事项 ID（必填，通过 sq --json 获取）
  --name <name>                      事项名称（可选）
  --assigned <mis>                   指派给（MIS 号，可选，仅父事项可改，子事项/工序不允许修改指派人）
  --expect-time <hours>              预计工作量（可选，单位小时，建议设置在子事项上）
  --expect-start <date>              预计开始时间（可选，YYYY-MM-DD，建议设置在子事项上）
  --expect-close <date>              预计结束时间（可选，YYYY-MM-DD，建议设置在子事项上）
  --json                             以 JSON 格式输出

ones schedule-item-delete (别名: sid)  删除排期事项（⚠️ 不可恢复）
  -p, --space-id <id>                空间 ID（必填）
  -i, --issue-id <id>                工作项 ID（必填）
  --item-id <itemId>                 排期事项 ID（必填，通过 sq --json 获取）
  -y, --yes                          跳过二次确认直接删除

ones schedule-time-update (别名: sctu)  修改排期字段（时间/人员/实现类型/研发自测，字段由排期模板配置决定）
  -p, --space-id <id>                空间 ID（必填）
  -i, --issue-id <id>                工作项 ID（必填）
  --design-time <date>               UI 交付时间（可选，YYYY-MM-DD）
  --test-time <date>                 提测时间（可选，YYYY-MM-DD）
  --release-time <date>              上线时间（可选，YYYY-MM-DD）
  --develop-start-time <date>        开发开始时间（可选，YYYY-MM-DD）
  --complete-time <date>             完成时间（可选，YYYY-MM-DD）
  --rd-masters <mis>                 技术主R（可选，MIS 号，多人用逗号分隔）
  --qa-masters <mis>                 测试主R（可选，MIS 号，多人用逗号分隔）
  --implement-type <type>            技术实现方式（可选，传可选值名称或 ID）
  --rd-self-test <value>             研发自测（可选，是/否）
  --json                             以 JSON 格式输出
```

> **排期事项结构说明**：
> - 排期事项分为**父事项（阶段容器）**和**子事项（工序）**，通过 `sq --json` 可查看嵌套结构
> - 预计工作量（`expectTime`）、预计开始/结束时间（`expectStart` / `expectClose`）应设置在**子事项**上，父事项的这些字段由系统自动汇总
> - 子事项（工序）的**指派人不允许修改**，只有父事项可以修改指派人
> - 阶段取值：`DESIGNING`（规划/UI 设计）、`DEVELOPING`（开发）、`TESTING`（测试）、`PUBLISHING`（发布）

---

## 大象群管理

```
ones workitem-xmgroup (别名: wxg)  工作项大象群管理（查询关联群 / 查可选字段 / 创建群）

  ones workitem-xmgroup query      查询工作项已关联的大象群列表（群 ID + 群名称 + 状态）
    -i, --issue-id <issueId>       工作项 ID（必填）
    -t, --issue-type <issueType>   工作项类型（必填）: REQUIREMENT | DEVTASK | DEFECT | PRODUCT_DOCUMENT
    --json                         以 JSON 格式输出（仅返回 groupId、name、active 字段）

  ones workitem-xmgroup roles      查询可选字段列表（创建者/指派给/抄送等）及对应成员 MIS
    -i, --issue-id <issueId>       工作项 ID（必填）
    -t, --issue-type <issueType>   工作项类型（必填）: REQUIREMENT | DEVTASK | DEFECT | PRODUCT_DOCUMENT
    --include-children             是否包含子工作项成员（可选，默认 false）
    --json                         以 JSON 格式输出完整原始数据（含 fields 和 members）

  ones workitem-xmgroup create     为工作项创建大象群（含前置幂等检查，已关联则直接展示）
    -i, --issue-id <issueId>       工作项 ID（必填）
    -t, --issue-type <issueType>   工作项类型（必填）: REQUIREMENT | DEVTASK | DEFECT | PRODUCT_DOCUMENT
    --users <users>                手动指定成员 MIS（逗号分隔）；不传则自动从工作项默认勾选字段查询
    --admins <admins>              群管理员 MIS（逗号分隔，默认取成员列表中首个）
    --owner <owner>                群主 MIS（默认取成员列表中首个）
    --user-fields <fields>         群名/备注中展示的字段名称（逗号分隔），默认使用默认勾选字段名
    --include-children             是否包含子工作项成员（可选，默认 false）
    --json                         以 JSON 格式输出创建结果
```

> **自动创建流程**（不传 `--users` 时）：
> 1. 调用 `associateXMGroup` 检查是否已关联 → 若已关联直接展示已有群聊并退出
> 2. 调用 `entity/roles` 获取可选字段列表，筛选 `isSelected=true` 的字段
> 3. 调用 `entity/members` 查询勾选字段对应的实际成员 MIS 列表
> 4. 调用 `xmGroup` 接口创建大象群
>
> **说明**：群主和管理员不在成员列表时会自动追加。`--user-fields` 不传时取默认勾选字段名作为群备注中的角色标识。

---

## 发布计划管理

```
ones releaseplan list (别名: rp-ls)      查询空间下的发布计划列表
  --space <spaceId>                      空间 ID（必填）
  --json                                 以 JSON 格式输出（含 planId、title、状态、时间范围）

ones releaseplan detail (别名: rp-d)      查询发布计划详情
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填，通过 rp-ls 获取）
  --json                                 以 JSON 格式输出

ones releaseplan create (别名: rp-c)      创建发布计划
  --space <spaceId>                      空间 ID（必填）
  -n, --name <name>                      发布计划名称（必填）
  --start <date>                         开始时间（可选，YYYY-MM-DD）
  --end <date>                           结束时间（可选，YYYY-MM-DD）
  -y, --yes                              跳过二次确认
  --json                                 以 JSON 格式输出

ones releaseplan delete (别名: rp-del)    删除发布计划（⚠️ 不可恢复）
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  -y, --yes                              跳过二次确认

ones releaseplan lock (别名: rp-l)        锁定发布计划（锁定后不可增删工作项）
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  -y, --yes                              跳过二次确认

ones releaseplan unlock (别名: rp-ul)     解锁发布计划
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  -y, --yes                              跳过二次确认

ones releaseplan issues (别名: rp-i)      查询发布计划内的工作项列表
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  --json                                 以 JSON 格式输出

ones releaseplan apps (别名: rp-a)        查询发布计划内的应用/服务列表
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  --json                                 以 JSON 格式输出

ones releaseplan addable-issues (别名: rp-adi)  查询空间下可添加到发布计划的工作项
  --space <spaceId>                      空间 ID（必填）
  --json                                 以 JSON 格式输出（仅返回有关联分支的工作项）

ones releaseplan add-issues (别名: rp-ai)  添加工作项到发布计划
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  --issues <issueIds>                    工作项 ID（必填，逗号分隔多个）
  -y, --yes                              跳过二次确认
  --json                                 以 JSON 格式输出

ones releaseplan remove-issues (别名: rp-ri)  从发布计划移除工作项
  --space <spaceId>                      空间 ID（必填）
  --plan <planId>                        发布计划 ID（必填）
  --issues <issueIds>                    工作项 ID（必填，逗号分隔多个）
  -y, --yes                              跳过二次确认
```

> **发布计划使用说明**：
> - **计划 ID 获取**：先执行 `ones releaseplan list --space <空间ID>` 获取计划列表中的 `planId`
> - **添加工作项前置条件**：工作项必须**已关联分支**才能添加到发布计划；可用 `ones releaseplan addable-issues --space <空间ID>` 查询当前可添加的工作项
> - **锁定状态**：锁定后的发布计划无法增删工作项，需先执行 `unlock` 解锁
> - **空间权限**：所有发布计划操作均会前置校验空间权限，无权限直接阻断
> - 常见编排：`rp-ls` → `rp-c` → `rp-ai` → `rp-i`（查列表→建计划→添加工作项→查计划内工作项）

