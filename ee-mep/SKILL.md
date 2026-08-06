---
name: ee-mep
description: MEP DevOps 命令助手，基于 mep-cli 执行 ONES、Talos、Pipeline、MCD、FEDO、Cargo、HPX、Quake、Rassor、Lyrebird、Conan、Plus、云图与 Code 等平台操作。用于用户提到 mep、ones、发版、流水线、构建、压测、回归、抓包、云测设备、PR 等场景。
version: 2.2.0

skill-dependencies:
  mtsso-skills-official:
    user_access_token_placeholder: ${user_access_token}
    audience:
      - com.meituan.mep
    prompt: 本技能所需的用户身份 token，请参考 mtsso-skills-official 的相关说明进行获取和注入

metadata:
  skillhub.creator: "heyuzhi02"
  skillhub.updater: "heyuzhi02"
  skillhub.version: "V2"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "9045"
---

# MEP CLI 助手

本 Skill 通过 `mep-cli` 统一访问多个研发平台。收到需求后，先将用户意图映射到对应子命令，再执行具体操作。

## 全局规则

> ⚠️ **每次操作前必须重新获取当前状态**，绝不复用上一轮运行时数据（分支名、PR ID、任务 ID 等）。

1. 不确定参数时，先执行 `mep <product> --help`。
2. 写操作（创建/删除/发布/触发）前先和用户确认关键参数。
3. **ones2 写操作必须预填参数**（`--title`/`--set`/`-y`），否则命令阻塞等待交互输入。

## 子命令路由

- `mep ones`：工作项/需求/迭代/工时/提测/测试计划/版本；⚠️ 双系统时先执行 Step 0 消歧
- `mep cargo`：Cargo 测试环境（泳道创建/部署/状态/配置/删除）
- `mep hpx`：HPX 移动端构建（Android/iOS/HarmonyOS 构建、组件查询、版本管理）
- `mep quake`：Quake 压测（场景查询、录制、任务发起/停止、健康检查）
- `mep rassor`：Rassor 回归测试（精选用例回放、Diff 差异分析、接口管理）
- `mep code`：Code 代码托管（PR 创建/管理/评论修复）
- `mep talos`/`mep ppl`/`mep mcd`/`mep fedo`/`mep lyrebird`/`mep conan`/`mep plus`/`mep yuntu`：遇到再查 `--help`

---

## mep ones — ONES 需求协同

#### Step 0：双系统消歧

```bash
which ones 2>/dev/null && echo "DUAL_CLI" || echo "SINGLE_CLI"
ones2 config                        # 读取偏好
ones2 config --set-system MEP       # 设置偏好（DUAL_CLI 时）
```
- `preferredSystem=ONES` → 停止并提示用户切换；单 CLI 直接跳过

#### Step 1：版本检查（每次触发必做）

```bash
ones2 --version
npm view @ee/mep-ones-cli version --registry=http://r.npm.sankuai.com
# 不一致时：npm install -g @ee/mep-ones-cli@latest --registry=http://r.npm.sankuai.com
```

#### Step 2：认证

```bash
ones2 sso status / ones2 sso login / ones2 sso refresh   # Token 8小时有效
```

#### 查询命令选择

| 场景 | 命令 |
|------|------|
| 未提及空间（跨空间，"我参与的"） | `ones2 workitem-workbench --cond '...' --json` |
| 指定单个空间（全量，不限参与者） | `ones2 space-filter --space <ID> --cond '...' --json` |
| 指定多个空间 | `ones2 workitem-workbench --cond 'field:projectId,type:TERMS,valueList:<ID1>|<ID2>'` |
| "本周"工作项 | `ones2 my-week [--space <ID>] [--type requirement] --json` |
| 包含 mep.sankuai.com URL | `ones2 url "<url>" -y --json` |

#### 工作项管理

```bash
# ⚠️ 参数名是 --title（非 --name）
ones2 workitem-create -t 需求 -p <空间ID> --title "<标题>" \
  --priority 高/中/低/紧急 --assigned <MIS> [--desc "<描述>"] -y
ones2 workitem-detail -i "<工作项ID>" --json
ones2 workitem-update -i "<工作项ID>" --val "<字段>=<值>" -y   # 单字段
ones2 workitem-update -i "<工作项ID>" --set "<字段>=<值>" -y   # 批量
ones2 workitem-delete -i "<工作项ID>" -y

# 评论
ones2 workitem-comment list --workitem <ID> --type requirement
ones2 workitem-comment reply --workitem <ID> --type requirement --parent <评论ID> --comment "内容"
```

> ⚠️ `--cond` 时间戳必须 **13 位毫秒级**；`state`（具体值）vs `stateCategory`（`TODO/DOING/DONE`）区分使用。

#### 迭代管理

```bash
# ⚠️ 参数名：--space（非 -p），--iteration（非 -it）
ones2 iterations --space <空间ID> --page-size 200 --json           # 加 --page-size 防截断
ones2 iteration-workitems --space <空间ID> --iteration <迭代ID> --cond '...' --json
ones2 iteration-create --space <空间ID> -n "<名称>" --start <YYYY-MM-DD> --end <YYYY-MM-DD> -y
ones2 iteration-update --space <空间ID> --iteration <迭代ID> --set "<字段>=<值>" -y
ones2 iteration-add-workitem --space <空间ID> --workitem <WI_ID> --iteration <ITER_ID> -y
# 其他子命令：iteration-remove-workitem / iteration-delete / iteration-lock / iteration-unlock
```

> ⚠️ 当前迭代识别：`startTime ≤ now ≤ endTime`，同一空间可能有多个当前迭代。

#### 提测管理

```bash
# ⚠️ initiate/cancel 必须同时传 -s <空间ID> 和 -i <提测单ID>
ones2 submittest-create -p <空间ID> --title "提测: xxx" --workitem <ID> -y
ones2 submittest-list --space <空间ID> --json
ones2 submittest-initiate -s <空间ID> -i <提测单ID> -y
ones2 submittest-cancel -s <空间ID> -i <提测单ID> -r "取消原因" -y
```

#### 分支管理

```bash
ones2 apps -p "<空间ID>" -n "<应用名>" --json   # 先查应用 ID
ones2 branch-create -i "<工作项ID>" --type feature --branch master -y
ones2 workitem-branches -i "<工作项ID>" --json
ones2 branch-associate -i "<工作项ID>" -a "<应用ID>" -b "<分支名>" -y
```

#### 工时管理

```bash
# ⚠️ 参数：-i（非 --item-id）、--hours（非 --duration）、--record-id（非 --log-id）
# 仅 DEVTASK（任务）类型可填写工时

ones2 worktime-add -i <任务ID> --hours 8h --date 2026-03-17 -y
ones2 worktime-add -i <任务ID> --hours 16h --date "2026-03-17~2026-03-18" -y   # 跨日期自动平均
ones2 worktime-query --range 本周/上周/本月   # 工时汇总
ones2 worktime-list -i <任务ID> --space <空间ID> --json   # ⚠️ 必须传 --space

# 更新/删除：先查 record-id 再操作
ones2 worktime-update --record-id <记录ID> -i <任务ID> --hours 4h -y
ones2 worktime-delete --record-id <记录ID> -y
```

#### 测试管理

```bash
# 测试用例
ones2 test-case list --space <空间ID> --json
ones2 test-case create --space <空间ID> --name "<名称>" -y
ones2 test-case import --space <空间ID> -f "<文件路径>"

# 测试设计
ones2 test-design list --space <空间ID> --json
ones2 test-design ai-generate --space <空间ID> -i "<工作项ID>" -y   # AI 生成

# 测试计划（⚠️ add-case/set-result 必须传 -r <轮次ID>）
ones2 test-plan list --space <空间ID> --json
ones2 test-plan create --space <空间ID> --name "<名称>" --iteration <迭代ID> -y
ones2 test-plan rounds --space <空间ID> -p <计划ID> --json
ones2 test-plan add-case --space <空间ID> -p <计划ID> -r <轮次ID> -c "<用例IDs>" -y
ones2 test-plan set-result --space <空间ID> -p <计划ID> -r <轮次ID> \
  -e <执行用例ID> --result PASS/FAIL/BLOCKED/NOT_EXECUTED
```

#### 版本管理

```bash
# ⚠️ product-version-workitems 需要 --product + --ver（非 -v）
ones2 version-list --product 266 -s "V1.0" --json
ones2 product-version-workitems --product 266 --ver <版本ID> --type requirement --state TODO,DOING --json
```

#### 字段与筛选

```bash
ones2 field search --space <空间ID> --name "优先级"           # 查字段 variable
ones2 filter-options query --type priority --space <空间ID>   # 查可选值
```

---

## mep code — PR 工作流

#### PR 创建（含前置智能校验）

```bash
# Step 1: -R 仅在无法从 git remote 自动解析时手动指定（⚠️ 非必填）
git remote get-url origin

# Step 2: 源分支 == 目标分支 → 立即拦截

# Step 3: 重复 PR 检测（⚠️ 已有 open PR 时绝不重复创建）
mep code pr list -H "<source_branch>" -s open --json
# 有未提交变更 → 询问是否提交到已有 PR → STOP
# 无未提交变更 → 展示已有 PR → STOP

# Step 4: 变更完整性（⚠️ 必须先 push 再比 remote，不能比本地）
git fetch origin && git push origin "<source_branch>"
git log origin/<target>..origin/<source> --oneline   # 无 diff → 拦截

# Step 5: ONES 绑定校验
mep code repo settings --json                         # 检查 requireIssueAssociated
mep code repo branch view "<branch>" --json           # issues 为空 → 拦截

# Step 6: 评审人推荐
mep code repo reviewers -t "<target_branch>" --json   # candidates 为空时去掉 -t 再试

# Step 7: 创建（标题优先级：用户提供 > ONES issue 名 > 最新 commit > 分支名）
mep code pr create -H "<source>" -B "<target>" -t "<标题>" [-r "<MIS>"] [-d] [--no-default-reviewers] --json
```

#### 自评禁止规则

```bash
mep code pr view "<pr_id>" --json    # 取 .author.mis
mep code auth status --json           # 取当前用户 .mis
# 相同 → 立即终止，提示添加评审人：
# mep code pr add-reviewer <pr_id> -r <mis> --json
```

#### PR 评论修复

```bash
# Step 1: 查未解决评论
mep code pr comments "<pr_id>" -s open --json

# Step 2: 分类处理
# ✅ CLEAR（明确修改点）→ 直接修复
# ⚠️ UNCLEAR/COMPLEX（含糊/架构决策）→ 先咨询用户

# Step 3: 提交推送
git add <files> && git commit -m "fix(pr-<id>): address review comments"
git push origin "<source_branch>"
# ⚠️ push 被拒时：git pull --rebase origin "<source_branch>" && git push

# Step 4: Resolve + 摘要评论
mep code pr resolve "<pr_id>" "<assignment_id>"
mep code pr comment "<pr_id>" -b "已修复 #456, #789；暂未处理 #790（原因: 需产品确认）"

# Step 5: 确认无遗漏
mep code pr comments "<pr_id>" -s open --json
```

#### 其他 PR 操作

```bash
mep code pr view/list/checks/approve/request-changes/merge/close "<id>" --json
mep code pr add-reviewer "<id>" -r "<MIS>" --json
```

#### 常见错误

| 错误 | 解决方案 |
|------|--------|
| `Source branch not found` | `git push origin <branch>` |
| `No diff / No commits` | 确认有新提交并已推送 |
| `ONES issue not bound` | MCode 分支管理页绑定 ONES issue |
| `Push rejected` | `git pull --rebase origin <branch>` 后再推 |

---

## mep hpx — 移动端构建

#### 认证（沙箱/无浏览器环境）

> ⚠️ `mep hpx` 走 hpx 独立登录体系，不接受 `--token` 参数。沙箱中需通过 MOA 换票 + 手动写 cache：

```bash
# Step 1: MOA 换票获取 ssoid（hpx SSO clientId: 9f397c0f0d）
SSOID=$(npx mtsso-moa-local-exchange --audience "9f397c0f0d" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 2: 用 ssoid 换 HPX token（注意是 access-token header，非 JSON body）
HPX_TOKEN=$(curl -s "https://hpx.sankuai.com/api/open/getToken" \
  -H "access-token: $SSOID" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# Step 3: 写入 cache.json
mkdir -p ~/.hpx-cli
python3 -c "
import json, os, time
cache = {'prod': {'ssoid': '$SSOID', 'hpxToken': '$HPX_TOKEN', 'hpxTokenTimestamp': int(time.time()*1000), 'userInfo': {'login': 'your_mis'}, 'timestamp': int(time.time()*1000)}}
json.dump(cache, open(os.path.expanduser('~/.hpx-cli/cache.json'), 'w'), indent=2)
"

# Step 4: 验证
hpx whoami
```

#### 常用应用名速查

| 应用 | Android | iOS | HarmonyOS |
|------|---------|-----|-----------|
| 美团 | `com.sankuai.meituan` | `imeituan` | `meituan-harmony` |
| 大众点评 | `com.dianping.v1` | `nova` | `harmony_nova` |
| 外卖 | `waimai_android` | `iwaimai` | `waimai_harmony` |
| 大象 | `xm_android` | `Elephant` | — |

#### 组件查询

```bash
mep hpx query component-version -c "<组件名>" -v "<版本>" [-o android|ios|harmonyos]
mep hpx query component-versions -c "<组件名>" [-a <app名>] [-b <分支>]
mep hpx query component-fuzzy -k "<关键词>" [-t <0=Android|1=iOS>] [-l <数量>]
# ⚠️ -t 接受数字：0=Android, 1=iOS（非字符串）
# ⚠️ Android 组件名必须包含冒号：packageName:moduleName
# ⚠️ iOS 查询必须加 -o ios，默认 android
```

#### 构建

```bash
# 简写命令（常用构建类型）
mep hpx build debug/release/gray/publish/feature-test-debug/feature-test-release \
  -a "<app名>" -b "<分支>"

# ⚠️ 不确定构建类型时，用通用命令（先查再构建）
mep hpx project list -o android -t APP               # Step 1: 查 projectId
mep hpx query build-type -p <projectId>              # Step 2: 查支持的构建类型
mep hpx build app -a "<app名>" -b "<分支>" -t "<构建类型名称>" [-o android|ios|harmonyos]
```

**构建类型 `-t` 取值（`build app` 时使用）：**

| 简写命令 | `-t` 参数值 |
|---------|------------|
| `build debug` | `"Debug打包"` |
| `build release` | `"Release打包"` |
| `build gray` | `"灰度包"` |
| `build publish` | `"全量发版"` |
| `build feature-test-*` | `"功能测试打包"` |
| 其他 | 从 `query build-type` 查到的 name |

#### 任务管理

```bash
mep hpx task list -a "<app名>" [-s running|success|failed]
mep hpx task info -i "<任务ID>"
mep hpx task branch-package -a "<app名>" -b "<分支>"
```

#### 项目查询

```bash
mep hpx project list [-o android|ios|harmonyos] [-t APP]
mep hpx project search -k <关键词> [-o android|ios|harmonyos]
mep hpx project by-repo -r "<repoUrl>"
```

---

## mep quake — 压测

> ⚠️ 以下命令**必须加 `-y`**：`stress start/stop/abort/changeQps`、`record start/stop`
> ⚠️ test 和 prod **共用 Prod SSO**，一次登录两环境均可用；`health` 无需登录直接执行

#### 认证

```bash
mep quake sso login                          # 标准登录
mep quake sso login --ciba --mis <mis-id>    # 沙箱/CI 环境
export QUAKE_ACCESS_TOKEN="AT_xxxxx" && export QUAKE_OPERATOR=your_mis   # CI 环境变量方式
```

#### 标准压测流程

```bash
mep quake health --env <test|prod>

# 查场景（无 ID 时）
mep quake scenes --env test --bu "<BU名>" --product-line "<产品线名>"
# 场景类型：1=HTTP日志回放 2=HTTP组合日志 3=Pigeon日志 4=MTThrift日志 5=HTTP自定义 6/7=RPC自定义

# 启动
mep quake stress start <scene-id> --env prod --qps 1000 --duration 600 -y [--watch]

# 动态调整 QPS
mep quake stress changeQps <task-id> --qps 200 --env test -y
# ⚠️ --expected-qps 不填默认为 --qps 的两倍

# 查状态 / 报告
mep quake stress status <task-id> --env test
mep quake stress realtimeReport <task-id> --env test   # 实时报告
mep quake stress stop <task-id> --env prod -y
mep quake stress finalReport <task-id> --env test      # 最终报告

# 压测任务常用状态码：0=RUNNING  2=SUCCESS  1=FAILED  3=ABORT
```

#### 流量录制

```bash
mep quake record scene ls --env test --bu "<BU名>" --product-line "<产品线名>"
mep quake record start <job_id> --env test -y
mep quake record status <record-id> --env test
mep quake record stop <record-id> --env test -y
```

#### 平台链接

```
压测控制台: http://quake.sankuai.com/buildController/console.do?sceneTaskId=<taskId>
录制日志:   http://quake.sankuai.com/dataTaskController/dataTaskLog.do?dataTaskId=<recordId>
# test 环境：前缀改为 http://test.quake.sankuai.com
```

---

## mep rassor — 回归测试

#### 回放

```bash
mep rassor case-list -a "<appkey>" [-d "<YYYY-MM-DD>"] --json
mep rassor replay-by-cases -r <recordId> -i "<目标IP>" --esids "<caseId1,caseId2>"
mep rassor replay-by-tags -a "<appkey>" -i "<ip>" --tag-ids "<ids>"   # 或 --tag-names "<names>"
mep rassor replay-by-mtrace -m "<mtraceId>" -a "<appkey>" -i "<ip>"
```

**高级回放参数取值：**

```
--diff-type        0=去噪(默认)  1=自定义  2=去噪+黑白名单
--diff-ignore-order  0=忽略list顺序(默认)  1=不忽略
--mock-strict      0=模糊  1=严格(默认)
--request-type     0=Mock回放(默认)  2=非Mock回放
--auto-expire      1=是  0=否(默认)
--cross-service    1=是(同时传 --cross-appkey + --cross-ip)  0=否(默认)
--scroll true      大数据量时使用
```

#### 状态查询

```bash
mep rassor replay-status -r "<replayId>" --json   # 最常用
# 其他：replay-stat / replay-detail / replay-history / replay-stop
```

#### Diff 差异分析

```bash
mep rassor replay-diff-query -a "<appkey>" -d "<YYYY-MM-DD>" --diff-result 1
# diff-result: 1=有差异  0=无差异  -1=回放失败
mep rassor replay-diff-detail -r "<replayId>" -c "<caseEsId>"
mep rassor case-expire -a "<appkey>" --es-ids "<id1,id2>"
```

#### 接口和标签管理

```bash
mep rassor interface-list -a "<appkey>" --json
mep rassor interface-update-core -a "<appkey>" -s "<接口列表>" -y
mep rassor case-tags-list -a "<appkey>" --json
mep rassor tag-create-batch -a "<appkey>" -f "<tags.json>"
# tags.json 格式：[{"appkey": "com.sankuai.xxx", "name": "标签名"}]

mep rassor case-update -a "<appkey>" --case-file cases.json      # 批量更新 case
mep rassor case-mtds-add -a "<appkey>" -d "<YYYY-MM-DD>" --infra <test|prod> --case-ids "<ids>"
```

---

## mep cargo — 测试环境

> ⚠️ **泳道定位优先级**：`-s <泳道名>` > `-r <repoUrl> -b <branch>` > `--appkey <key> -b <branch>` > `-c`（自动检测）

#### 认证

```bash
mep cargo sso login [--ciba]   # --ciba 强制沙箱/无浏览器模式
export CARGO_SSOID=<ssoid>      # CI/CD 推荐，无需登录
```

#### 泳道创建与部署

```bash
# 创建泳道（仅创建，不触发构建）
mep cargo stack create --appkey <appkey> -b <branch>   # 推荐
mep cargo stack create -c                               # 自动检测当前 Git 仓库

# 部署
# ⚠️ --appkey 模式自动部署所有发布项，无需指定 --releases
mep cargo stack deploy --appkey <appkey> -b <branch>

# 仓库模式：先列出发布项，再指定 --releases
mep cargo stack deploy -c                              # 列出可用发布项（不触发）
mep cargo stack deploy -c --releases "rel1,rel2"       # 指定后触发
```

#### 泳道管理

```bash
mep cargo stack status --appkey <appkey> -b <branch>    # 推荐（或 -s <泳道名>）
mep cargo stack search <appkey> [-b <branch>]           # 查询关联泳道
mep cargo stack delete --appkey <appkey> -b <branch>    # ⚠️ 执行前二次确认
```

#### 修改资源配置

```bash
mep cargo stack update-config --release-name <name> --appkey <appkey> -b <branch> \
  [--replicas 2] [--cpu 4] [--mem 8192] [--harddisk 20] \
  [--region beijing|shanghai|cnhl|default] [--deploy-type rolling|normal|fixed_ip] \
  [--without-replicas-deploy]   # 仅改配置，不触发部署
```

---

## 端到端链路示例

### 链路 1：需求到发布验证

```bash
ones2 workitem-create -t 需求 -p "<空间ID>" --title "<标题>" -y        # 创建需求
ones2 apps -p "<空间ID>" -n "<应用名>" --json                           # 查应用 ID
ones2 branch-create -i "<需求ID>" --type feature --branch master -y    # 关联分支
# 开发完成后...
mep code pr create -H "<feature-branch>" -B "master" -t "<标题>" --json
mep cargo stack create --appkey "<appkey>" -b "<branch>"
mep cargo stack deploy --appkey "<appkey>" -b "<branch>"
mep rassor replay-by-cases -r <recordId> --esids "<caseIds>" -i "<泳道IP>"
mep rassor replay-diff-query -a "<appkey>" -d "<今日>" --diff-result 1
ones2 submittest-create -p "<空间ID>" --workitem "<需求ID>" -y
ones2 submittest-initiate -s "<空间ID>" -i "<提测单ID>" -y
```

### 链路 2：移动端构建

```bash
mep hpx project list -o android -t APP                                    # 查 projectId
mep hpx query build-type -p <projectId>                                   # 查构建类型
mep hpx build app -a "com.sankuai.meituan" -b "<分支>" -t "Debug打包" -o android
mep hpx task branch-package -a "com.sankuai.meituan" -b "<分支>"         # 查包状态
```

### 链路 3：压测验证

```bash
mep quake health --env prod
mep quake scenes --env prod --bu "<BU名>" --product-line "<产品线名>"
mep quake stress start "<scene-id>" --env prod --qps 1000 -y --watch
mep quake stress finalReport "<task-id>" --env prod
```

---

## 故障排查

| 问题 | 解决方案 |
|------|--------|
| `401` / SSO 过期 | `mep <product> sso status && mep <product> sso login`（rassor 用 `sso-login`；code 用 `auth login`；hpx 用 `login`） |
| `403` / 无权限 | ones: 立即停止并告知「请联系 MEP 团队」；其他: 确认账号角色 |
| 参数错误/命令不存在 | `mep <product> <subcommand> --help` |
| ones2 命令阻塞 | 必须预填 `--title`/`--set`/`-y` |
| hpx: Android 组件返回空 | 检查组件名是否含冒号（`packageName:moduleName`） |
| hpx: iOS 查询返回空 | 忘加 `-o ios`，默认 android |
| hpx: 构建类型不存在 | 先 `mep hpx query build-type -p <projectId>` |
| ones: 时间戳异常 | 必须 13 位毫秒级（Java 时间戳） |
| quake: QPS 调整失败 | 不重试，告知用户自行排查 |
| cargo: 沙箱无浏览器 | `mep cargo sso login --ciba` 或 `CARGO_SSOID` 环境变量 |
