---
name: ai-ui-autotest-engine
version: 6.5.0
description: 移动端 UI 自动化测试。以 Flow 输入驱动，执行环境准备、步骤走查、证据归档与完整性报告。当前实现覆盖 Android 与 HarmonyOS 两个平台（sandbox 云模拟器 + local 本地真机）。

metadata:
  skillhub.creator: "wangshicheng05"
  skillhub.updater: "wangshicheng05"
  skillhub.version: "V179"
  skillhub.source: "FRIDAY Skillhub"
  skillhub.skill_id: "93069"
  skillhub.high_sensitive: "false"
---

# AI UI Autotest Engine

> **目录（作用域分层）**：`.run/tasks/<ws>/{config,inputs,tmp,runs/<run>}/`（workspace / run 级）；入口脚本 `.run/ws/<ws>/cli`；跨 workspace 共享的 `.device-pool/`（设备池）、`.credentials/`（凭据）、`.console/`（统一控制台服务，跨会话共享、常驻、不随收尾清理）；产物 `output/`。制品缓存 `.cache/artifacts/<platform>/<form>/<pkg>/` 也是跨 workspace / 跨子 Agent 共享，且**引擎永不自动清理**（post-clean / preflight-clean 不触碰它，仅用户手动清理 Skill 时消失）。
> **workspace 入口（每轮测试第一步）**：`python3 -B scripts/cli.py ws-init` 分配 workspace 并生成入口 `.run/ws/<ws>/cli`；**之后所有命令都必须通过该入口执行**（写作 `<入口> <命令>`），入口把 `AI_UITEST_TASK=<ws>` 注入进程以定位工作区。未经入口执行 → 直接报错，**无默认兜底**（避免静默落到共享目录）。入口与 `cli.py` 均已带 `python3 -B` + `PYTHONDONTWRITEBYTECODE=1`（源树零字节码，不做 pyc 缓存）；手工执行其它 python 入口（如 `scripts/dev/*.py`）同样加 `-B`。
> `--input` 支持**裸文件名**（按本 workspace 的 `.run/tasks/<ws>/tmp/` 解析）。

## 一、执行原则

1. **严格遵循 Skill 流程**：AI 必须严格按 SKILL.md 定义的阶段和子步骤顺序执行，不得跳过、合并或重排流程。
2. **禁止运行期改写已声明步骤**：steps 只依据 Flow 原文；页面不符走 hook 消歧并记 `needs_review`/finding，不得回改 cases/steps 或重跑 `steps-generate`/`flow-init` 掩盖。
3. 测试结果必须可追溯。环境、登录、落地页、步骤、视觉扫描、动态 Mock 和报告都写入运行事件与证据清单。失败记录真实结果，不伪造成功。
4. 一次运行串行控制一台设备。`device create` 从**设备池**领取设备（复用空闲实例，无空闲则新建）并登记本 run 的 owner 租约；`device release` 在收尾归还租约（**不销毁实例**，留给池复用）。每个 run 还会先 `mis acquire` 从**虚拟 mis 池**领取一个 AppMock 工作域（`mock_domain`，私有优先 → 公共兜底），所有 AppMock（规则 / 录制 / 环境 / 泳道）都以它为准，收尾 `mis release` 归还；它记录在 workspace 级 `intake.mock_domain`，与设备 / 报告归属的 `resource_mis` **恒定分离**。收尾阶段由 SOP 引擎自动处理，AI 只需执行 `flow-next` 返回的指令即可。共享设备（云模拟器）历次占用会在 `/data/local/tmp` 残留安装/传输中间产物（清数据不覆盖该目录），需要时可执行 `device clean-tmp`：只删白名单后缀的产物、**保留本 Skill 自己的设备侧缓存目录与临时文件**，不递归、不删目录。安装制品统一**先查 Skill 制品缓存**（`.cache/artifacts/`，唯一入口 `shared/artifact_cache.py`）：命中即免下载，未命中才下载一次，多个子 Agent 并行也只会下载一次。
5. 环境不可用时快速失败并收尾，不重试、不换数据对照、不深挖日志。
6. **先预置、后提问（硬门禁）**：用户已明确提供的值先经 `input-seed --answers` **一次性预置**（引擎按与作答同一套白名单 / 依赖校验入库，已预置的题不再下发）；剩余项才走 `input-next` → AskQuestion（原样传 `options`，每次只 1 题）→ `input-answer`（只提交刚下发的题 ID，禁止合并 / 跳答 / 未下发直接作答）；循环见 §二「阶段 0」。
7. **禁止复用历史产物**：每轮测试的判定依据必须全部来自**本次运行**的实时产物（`.run/`、`output/run-<ts>/`），不得引用历史 `output/` 下的截图、报告或日志作为判定依据。
8. **CASES 文件强制约定**：先 `cases-create --tag <tag>` 创建空文件，AI 再写入内容；写完 `wc -c` 确认非空后再 `steps-generate`。禁止用编辑器直接新建该文件。
9. **统一控制台（跨会话共享；链接须转达用户）**：`ws-init` 与 `ai-auto-ui-test` 的环境准备会自动**幂等启动** Web 控制台并打印访问链接（多设备实时画面 + 结构化动态日志）——**务必把该链接原样转达给用户**便于实时分析。服务**常驻、跨会话共享**：已启动则直接复用（其他会话据此跳过，**不要重启**）；`down` 一般不需要。控制台对测试执行**零侵入**（服务未启动时埋点不启用、零开销；启动后仅非阻塞落盘）。

## 二、运行模型

### 阶段 0：信息收集 → 流程初始化

```bash
# ① 分配 workspace + 生成入口（整轮测试只执行一次，之后 <入口> 固定不变）
python3 -B scripts/cli.py ws-init

# ② 之后所有命令都通过 <入口> 执行（<入口> 形如 .run/ws/<ws>/cli）
<入口> check-deps
<入口> flow-create --name <Flow名>     # 多 Flow 场景：每个 Flow 执行一次
# AI 写入完整 Flow 内容

# ③ 预置已知值：先看问题目录，再把「用户已明确提供」的值一次性 seed
#    用户没给的不写（留给 ④ 逐题问）；派生键（device_type/platform/app/auth_method）不写
#    bundle_lock：题面已前置 Flow「可测性环境」表里的声明值
#    场景 AppMock 不在此采集：case 级配置，flow-init 读各 Flow「可测性环境」表自动派生
<入口> input-schema                    # 问题目录：字段 id / 选项 / 依赖 / 派生键
<入口> input-seed --answers '{"env_type":"A","resource_mis":"<mis>","device_combo":"sandbox-android-meituan",...}'

# ④ 逐题收集剩余项（已 seed 的不再问）：一步一题循环 ——
#    input-next（下发 1 题 + next 指针）→ AskQuestion（只放这 1 题）
#    → input-answer（只提交刚下发的题 ID）→ 回 input-next，直到 done（规则见 §一.6）
<入口> input-next                     # 返回 question + progress + next 指针
<入口> input-answer --id <当前下发的ID> --value <值>

# 收集完成后初始化流程（多 Flow 只执行一次，所属 Flow 合入一个 cases 数组）
<入口> flow-convert --tag {tag}
<入口> cases-create --tag {tag}        # 先建空 CASES，AI 写入（wc -c 确认非空）
<入口> steps-generate --input 'cases-{tag}.json' --tag {tag}
<入口> flow-init --dir <run-name> --input 'steps-input-{tag}.json' --flow-name <Flow名>
<入口> flow-next                       # 阶段 1 入口
```

> **workspace 入口是硬门禁**：`ws-init` 是阶段 0 第一步，它输出的 `<入口>` 是整轮测试唯一的命令入口；漏用入口会被引擎直接拒绝（报“未指定 workspace”）。
> **预置优先（避免重复提问）**：先 `input-schema` 看字段与选项，把用户请求里**已明确给出**的值（设备组合 / 环境 / MIS / 账号密码 / ptest / 锁包等）用 `input-seed` 一次性入库；`input-seed` 返回 `remaining`（仍需问的题）与 `rejected`（非法 / 不适用的值），随后只需对 `remaining` 跑逐题循环。已给过的值绝不再问。`resource_mis` 能由当前身份（`HOTEL_UI_MIS` / 缓存 SSO 身份 / `git config user.email`）自动派生，此时会以 `source=derived` 出现、**不会下发提问**；只有当这些来源都拿不到时才是必答题，需指定其他 MIS 时仍可用 `input-seed` 覆盖。**场景 AppMock 不入采集**：它是 case 级配置 —— `flow-init` 直接读每个 case 的 Flow「可测性环境」AppMock 行派生到该 case 的 `mock_ids`，无需作答。
> **强指针**：`input-next` 输出 `progress` + `next` 指针（`ask` 带可直接执行的 `cmd`），逐条照抄直到 `done`；结果落 workspace 级 `intake.json`。**`flow-init` 是阶段 0/1 分界线**：它只做协议载入与 run 目录创建；其后的 B0（`mis acquire`）、B1（`device create/setup`）、B2（`env-prepare` 登录）均由 `flow-next`/`flow-advance` 逐条驱动，AI 按返回值执行，**不会在 flow-init 内自动执行**。

### 阶段 1：引擎驱动

AI 不再手动决定下一步，按 `flow-next` 返回的命令执行，确认用 `ack --key`。「推进阶段」只做两件事：① 仅当 `flow-next` 明确输出「执行 python3 scripts/cli.py flow-advance 推进到下一阶段」时才调用 `flow-advance`；② 其余情况（含条件不满足被自动跳过的阶段）一律继续执行 `flow-next` 给出的命令。

**关键规则**：
- 逐条执行 `flow-next` 返回的指令，禁止批量自动化
- **长任务命令**（引擎标注「长任务·后台执行」）：**后台启动并轮询日志**；超时/失败后先确认旧实例已终止再重跑，**禁止前台阻塞、或并发/重跑已在进行的长任务**
- **条件不满足的阶段由 `flow-next` 自动跳过**（如无场景 Mock 时跳过 `B0_mock_preflight` / `T0_mock_restore`），输出只陈述「已跳过」；此时**不要**再调 `flow-advance`，否则会对已跳过的阶段重复推进，误伤下一阶段（无 `completion_check` 的阶段会被直接标完成）
- 截图自动生成（统一归档于每个 Case 的 `frames/`），按 `[REVIEW]` 指示读图确认
- 步骤失败时按引擎输出 hooks 优先修复，确认无法修复再用 `skip-case` 跳过；禁止以"时间成本"等理由跳过低成本修复
- 环境不可恢复时 `flow-fail --cleanup` 终止

## 三、Flow 转换

### 流程

1. `flow-convert --tag <tag>` → 解析元数据，输出 `metadata-<TAG>.json`
   - 报告会显式列出「🌐 可测性环境（须映射到 CASES.env）」（覆盖范围 / 环境 / AppMock / 泳道 / 域名映射 / 锁包），即 env 声明清单
2. `cases-create --tag <tag>` → 创建空 CASES 文件占位（强制约定，写内容前必须先执行）
3. AI 写入 steps 内容（含 device/env/cases/steps），写完 `wc -c` 确认非空
   - **env 声明**：把 Flow「可测性环境」表映射进 `env` —— `环境` 行须与 `env_type` 一致；泳道/域名映射 → 对应 env 字段。**`AppMock` 不写进 env**：它是 **case 级**配置，`flow-init` 自动读每个 Flow 的 AppMock 行派生到该 case 的 `mock_ids`（声明即启用、未声明即不启用）
   - 场景 Mock 生命周期由 SOP 自动驱动：`B0_mock_preflight`（快照 union + 同 case 冲突检测 + 清场）→ 每 case `C1_mock_apply`（差量开关，保证任一时刻 AppMock 开启的场景规则 = 当前 case 集合）→ `T0_mock_restore`（恢复 union 到执行前状态）
4. `steps-generate --input 'cases-<tag>.json' --tag <tag>` → 输出 `steps-input-<TAG>.json`
5. `flow-init` → 载入引擎

### steps-input.json 结构

```json
{
  "batch_name": "{批次名称}",
  "device": { "type": "sandbox", "platform": "android", "app": "meituan", "auto_install": false },
  // env 由引擎从 intake 合成，无需 AI 手写
  "cases": [{
    "case_id": "{case标识}", "case_name": "{case描述}",
    "landing_scheme": "imeituan://...mrn_biz={biz}&mrn_entry={entry}&mrn_component={component}",
    "params": {"<占位符名>": "<真实值>"},  // 键=占位符名（不带宽括号）；日期 {T+N:format} 自动解析，无需写入
    "steps": [
      {"sid":"S1","kind":"ui","desc":"开：点击目标","action":"tap-text","action_arg":"目标","step-type":"interaction","page_ready":true,"asserts":[
        {"kind":"text","match":"present","expect":"就绪文案"}
      ]},
      {"sid":"S2","kind":"ui","desc":"向右滚动到目标","action":"scroll-until","action_arg":"目标","direction":"right","step-type":"interaction","asserts":[
        {"kind":"text","match":"present","expect":"就绪文案"}
      ]},
      {"sid":"S3","kind":"ui","desc":"看：断言内容","action":"assert-text","step-type":"assert","asserts":[
        {"kind":"text","match":"present","expect":"预期1"},
        {"kind":"text","match":"present","expect":"预期2"}
      ]},
      {"sid":"S4","kind":"ui","desc":"关：关闭","action":"back","step-type":"interaction","asserts":[
        {"kind":"text","match":"gone","expect":"原文案"}
      ]},
      {"sid":"S5","kind":"ui","desc":"操作：点击锚点邻近的无文案图标","action":"tap","action_anchor":"邻近文案","step-type":"interaction","asserts":[
        {"kind":"visual","expect":"AI 读截图确认预期效果呈现"}
      ]},
      {"sid":"A1","kind":"api","desc":"接口验证","api_assert":{
        "path":"/path/to/api",
        "expected_fields":[
          {"source":"request","field":"字段名","expected":"预期值"},
          {"source":"response","field":"字段名","expected":"预期值"}
        ]
      }},
      {"sid":"T1","kind":"track","desc":"埋点验证","track_assert":{"match":"事件名"}},
      {"sid":"T2","kind":"track","desc":"埋点参数校验","track_assert":{"match":"事件名","expected_fields":{"page_type":"全日房","button_name":"房型详情"}}}
    ]
  }]
}
```
`landing_scheme` 必须完整，日期占位符 `{T+N}` 执行时替换。支持 `{T+N:format}` 语法指定格式（如 `{T+4:%Y%m%d}` 输出 yyyyMMdd，`{T+4:%Y-%m-%d}` 输出 YYYY-MM-DD），不指定 format 时默认 `%Y-%m-%d`。`flow-init` 自动追加 debug 浮窗关闭参数，无需手动填写。UI / API / Track 步骤执行后均自动截图（命名 `case_NN_{sid}.png`），统一归档到当前 Case 的 `frames/` 目录。API/Track 步骤匹配成功后自动 PASS；**埋点 `match` 用 `val_cid`/`nm`（分类级标识）命中多条时转 PENDING**，生成 `verify_track_fields` hook（携带候选清单），需 AI 按 `nm`/`val_lab` 语义选定后用 `assert-fields --picked <序号>` 消歧；配了 `expected_fields` 也生成该 hook。`val_bid`（精确事件 ID）命中永不歧义。响应取值用 `response-search`。

**顶层字段**：

| 字段 | 说明 |
|---|---|
| `batch_name` | 批次名称，报告中展示 |
| `device` | 设备配置（可选，缺省走 sandbox-android-meituan 默认值，见下） |
| `env` | 环境配置。**收集字段**（type/auth_method/account/password/bundle_lock/ptest/swimline/url_mappings）由引擎从 intake 合成。**场景 Mock 不在 env**：为 case 级（`cases[].mock_ids`），由 flow-init 从各 Flow「可测性环境」表派生 |
| `cases` | Case 数组，一个 Flow 文件 = 一个 Case。**多 Flow 场景**：将所有 Flow 的 Case 合并到同一个数组，`flow-init` 只执行一次 |
| `cases[].params` | AI 手动填充的占位符映射。`{name: value}`，value 取值：`null`（需用户提供）、`"__date__"`（`{T+N}` 或 `{T+N:format}` 日期，引擎自动解析）、具体值字符串（从「测试数据参考」填入） |
| `cases[].mock_ids` | **可选**：该 Case 的场景 AppMock 规则 ID 列表（case 级）。缺省时由 `flow-init` 从该 Case 的 Flow「可测性环境」AppMock 行自动派生；显式填写则优先生效 |

**`device` 块字段**（可选，缺省时全部走默认值）：

| 字段 | 可选值 | 默认值 | 说明 |
|---|---|---|---|
| `type` | `sandbox` / `local` / `cloud_device` | `sandbox` | 云模拟器（从设备池领取：复用空闲实例，否则新建，登记 owner 租约）；本地真机（跳过创建/销毁）；云真机（待完善） |
| `platform` | `android` / `harmony` | `android` | 决定底层工具：Android 用 imeituan-cli，Harmony 用 hdc |
| `app` | `meituan` / `dianping` | `meituan` | `dianping` 暂不支持 |
| `auto_install` | `true` / `false` | `false` | 仅 `local` 生效：版本不符时自动卸载重装。`sandbox` 恒为 `true` |

`type`/`platform`/`app` 组合必须为 sandbox-android-meituan / local-harmony-meituan / local-android-meituan 之一，`flow-init` 硬校验。`local` 只允许 `auth_method=noop`。

**Kind 字段白名单与互斥校验**（flow-init 自动校验，混合字段会直接报错）：

| kind | 必需字段 | 禁止字段 | 说明 |
|---|---|---|---|
| `ui` | `action` | — | UI 交互与断言步骤 |
| `api` | `api_assert`（含 `path` + 可选 `expected_fields`） | `action` / `step-type` / `screenshot` / `asserts` | 接口字段验证（从录制数据匹配，逐字段断言） |
| `track` | `track_assert`（含 `match` + 可选 `expected_fields`） | `action` / `step-type` / `screenshot` | 埋点事件验证；`match` 取值与多候选消歧见上文说明 |

**`api_assert` 语义规范**：

| 字段 | 必填 | 语义 |
|---|---|---|
| `path` | ✅ | Flow 原文路径，不补 `https://`；**后缀段匹配**（至少末尾一段一致即命中） |
| `expected_fields` | ❌ | **缺省 = 不校验字段**（匹配成功即自动 PASS）；配了才有字段级判定 |
| `[].source` | ❌ | `request` / `response` / `meta`（仅展示）；状态码固定写 `{"source":"meta","field":"http_code","expected":"200"}` |
| `[].field` | ✅ | **生成期可写语义名**（如「价格字段」）；真实路径 `response.<点号路径>` 由 `assert-fields` 解析后回写 |
| `[].expected` | ❌ | 允许直接引用 Flow 原文（含自然语言） |

### Action 选择映射表

AI 根据以下映射表选择 Flow 操作描述 → action + asserts。推定步骤按下方「模糊推定」规则走 `kind: "visual"`。

| Flow 描述关键词 | action | page_ready | asserts | 附加参数 |
|---|---|---|---|---|
| 进入页面 / 打开 Scheme / 跳转 | `open-url` | `false` | `[{"kind":"text","match":"present","expect":"就绪文案"}]` | |
| 点击有文案按钮（打开新页面） | `tap-text` | `true` | `[{"kind":"text","match":"present","expect":"轻量就绪标志"}]` | |
| 点击有文案按钮（当前页操作） | `tap-text` | `false` | `[{"kind":"text","match":"present","expect":"新内容"}]` | |
| 点击无文案图标 | `tap`（配 `action_anchor`=图标所在行文案） | `false` | `[{"kind":"visual","expect":"预期效果呈现"}]` | 引擎取**锚点行唯一可点击目标**自动点击（标待复核）；多 / 无可点击目标 → 走视觉通道消歧（读图 + 断言）；`find-icon --anchor` 可复核坐标 |
| 关闭弹窗 / 返回 | `back` | `false` | `[{"kind":"text","match":"gone","expect":"原文案"}]` | |
| 滚动到「xxx」 | `scroll-until` | `false` | `[{"kind":"text","match":"present","expect":"目标"}]` | `--direction`（可选，默认自动推断） |
| 滚动到底部 | `scroll-edge` | `false` | `[{"kind":"text","match":"present","expect":"底部标志"}]` | `--direction down` |
| 向右/左滚动到「xxx」 | `scroll-until` | `false` | `[{"kind":"text","match":"present","expect":"目标"}]` | `--direction right/left` |
| 快速滚动到 xxx 区域边界 | `scroll-edge` | `false` | `[{"kind":"visual","expect":"边界内容"}]` | `--direction up/down/left/right` |

> **方向统一约定**：所有 `--direction` 参数均采用 **用户语义**（想看的目标方向）：
> - `down` = 想看下方 → 引擎自动翻译为物理上滑（内容上移）
> - `up` = 想看上方 → 引擎自动翻译为物理下滑（内容下移）
> - `right` = 想看右侧 → 引擎自动翻译为物理左滑
> - `left` = 想看左侧 → 引擎自动翻译为物理右滑
> AI / SOP 只需表达「想看哪个方向」，物理手势由引擎内部处理。

| 输入「xxx」 | `input-text`（配 `action_anchor`） | `false` | `[{"kind":"text","match":"present","expect":"回显文案"}]` | |
| 断言出现 / 校验包含 | `assert-text` | `false` | `[{"kind":"text","match":"present","expect":"..."}]` | |
| 断言消失 | `assert-text` | `false` | `[{"kind":"text","match":"gone","expect":"..."}]` | |

**`page_ready` 布尔字段**：导航到新页面的操作设为 `true`（引擎会等待页面稳定后再截图）。

**「开 → 看 → 关」拆分**：交互步骤（`step-type=interaction`，含 `tap-text`/`back`）的 `asserts` 只用页面标题等**轻量标志**，禁止放深层内容；Flow 声明的**全部**预期字段一律拆到独立的 `assert-text`（`step-type=assert`）步骤。弹窗类按「开（`tap-text` + `page_ready:true`）→ 看（`assert-text`）→ 关（`back`）」三段拆。

### 注意事项

- **`landing_scheme` 禁止重复**：不要为第一步写 `open-url`，引擎已通过 scheme 自动跳转
- **action_arg 文案口径**：`tap-text` / `scroll-until` 优先精确匹配；当页面文案与 action_arg 存在**唯一子串/重叠关系**时（如页面「已优惠¥175」vs action_arg「已优惠」），引擎运行期**唯一子串兜底**直接命中，并记录 `action_hit`（verdict=semantic）→ 该步标记 `needs_review`、evidence 记录 `text_mismatch`，**不额外产生 hook**；多形态候选不兜底，仍转 `resolve_text_not_found`（tap）/ `SUBSTRING_AMBIGUOUS`（scroll）hook 交 AI 消歧。
- **input-text 的锚点语义**：`action_anchor` 只是「输入框附近的锚点」或一句语义描述，引擎会在锚点所在**同一视觉行**内自行定位 `role=input` 目标；定位不到（行内无输入框 / 需先点击展开 / 是选择器）转专用 hook `resolve_input_box`，由 AI 用**截图 + 锚点行成员（含宽度）**推断坐标后以坐标形态重跑（输入动作禁止用坐标点击替代）。
- **场景 Mock 是 case 级（`cases[].mock_ids`）**：Flow「可测性环境」AppMock 行 → 该 case 的 mockId 集合，`flow-init` 自动派生，无需写入 env / 不需作答。AppMock 对同一请求「命中即短路」，因此同一 case 内**不允许**两个 mockId 命中同一接口（`B0_mock_preflight` fail-fast）；跳 case 由 `C1_mock_apply` 差量开关隔离，绝不共存。
- **自检**：按 `references/review-rules.md` 逐条审校 steps（R-STR → R-ACT → R-AST → R-SEM → R-PAR → R-CFL），**P0 全部通过后再执行 steps-generate**

### 模糊推定

Flow 含 `pending`/`待审校`/`以实际为准` 时：操作推定最合理文案（上下文优先→美团常识回退），标注 `"inferred": true`，asserts 全走 `kind: "visual"`。推定不违反 R-SEM-001。

## 四、命令一览

`step` 命令的 `--help` 会列出每个 action 子命令及其必填参数（缺失会直接报错并给出标准用法）。本节只做命令分类导航，不重复列参数。**阶段 1 中 AI 不应手动构造命令，直接执行 `flow-next` 返回的指令即可。**

- **Flow 转换与审校**：`flow-convert`（轻量模式：解析 Flow .md 元数据，供 AI 写步骤参考） `cases-create`（创建空 CASES 文件，写内容前必须先执行） `steps-generate`（接收 AI 编写的 CASES JSON，完成 sid 编号/校验/占位符替换，输出 steps-input.json）
- **交互与断言**：`screenshot`（`--out` 为纯文件名时归档到当前 Case 的 `frames/`；为路径时按原路径） `open-url` `tap-text` `tap` `scroll-until` `scroll-edge` `input-text` `blur-input` `assert-multi` `swipe` `dismiss-recce`（`assert-text` 合并至 `step assert-text`）
- **元素定位**：`find-text --text <文案>` `find-icon --anchor <邻近文案>` `find-input --anchor <邻近文案>` `probe-status` `inspect-tree`
- **Flow 引擎驱动**：`step` `log-record` `override-step-result` `assert-fields`（API/Track 字段判定；埋点多候选用 `--picked <序号>` 消歧） `response-search`（API 响应按需视图：`--skeleton` 结构总览 / `--query` 关键字定位 / `--path` 精确取值） `flow-init` `flow-status`（`--sid <SID>` 查单步精简详情）`flow-case-status` `flow-next` `flow-advance` `hook-info`（`--hook-id <ID> [--sid <SID>]` 按需查询单个 hook 的完整操作指引）`ack` `skip-case` `flow-fail` `flow-finalize` `gen-report`
- **异常终止**：`report-error`（异常终止收尾前调用，上报 AI 分析结论和解决方案）
- **workspace / 环境与设备**：`ws-init`（分配 workspace + 生成入口） `check-deps` `preflight-clean` `post-clean` `install-app` `force-stop` `launch` `set-location` `mock`（含 `mock effective`：聚合 ptest + 场景 Mock 的生效集并判定是否仍被 ptest 全量规则遮蔽） `mock-preflight`（场景 Mock 预检：快照 union + 冲突检测 + 清场） `mock-apply --case-index <i>`（把场景 Mock 收敛到指定 case） `mock-restore`（恢复 union 到执行前状态） `mis`（虚拟 mis 池：`mis acquire` 领虚拟 mis / `mis status` 查看 / `mis release` 释放 / `mis release-stale --hours N`） `input-schema` `input-seed` `input-next` `input-answer` `input-status` `env-prepare` `validate` `case-init`

以下是 `--help` 之外仍需要说明的行为语义（不属于参数，`--help` 不会体现）：
- `back` 是 Flow action，单独执行用 `step back`。
- `step` 的独立操作（不绑定声明步骤）若未提供 `--desc`，引擎按 action + 参数自动派生描述，不会写入 desc 为空的孤立记录。
- `dismiss-recce` 检测并拖离 Recce 调试浮层（`tap-text` 遇遮挡时自动调用，也可手动使用）。
- `log-record / override-step-result --img` 可指定已有截图（`frames/` 下的文件名；不传时自动截当前画面并归档到 `frames/`）。
- `log-record` 是唯一能写「无判定备注」的入口：传 `--note` 且不带 `--pass/--fail/--ok` → 记录 `ok=None`，带 `--sid` 归步骤 `annotations`、不带则归 Case `notes`，均不计入通过/失败统计。
- **兜底操作必须归属父步骤**：`step --for-sid <SID> tap --action-x … --action-y …` 把坐标兜底等补救动作绑到已声明步骤 —— 记录进该步证据/attempts，**不改其结论**（结论权在断言与 AI override）；禁止裸写 `step tap`（会落成脱离步骤的孤立 finding 并覆盖证据截图）。`--for-sid` 与 `--sid` 互斥。
- **不可原地重跑的动作**：`back` / `input-text` 有不可撤销副作用（back 多退一页、input 重复叠加），**已执行过的步骤禁止原地重跑**（引擎直接 `STEP ABORT`）；确需再执行请换新 sid（`step --sid S3b back …`，记为父步骤 retry），页面已偏离时用 `open-url` 恢复。
- **hook 指引按需查询**：`flow-next` / `[AI_CHECKLIST]` 只给 hook id + 一行摘要 + 查询/标记命令；需要完整操作指引时执行 `hook-info --hook-id <ID> --sid <SID>`。

## 五、异常处理

0. **异常终止闭环**：运行时异常已由引擎自动写入时间线，随报告入库，无需手动处理。**平台级归因诊断的唯一上报入口是 `report-error`**，由 AI 在异常终止收尾前调用。异常终止时按 3 步闭环：
   **第 1 步 — 分析原因**：结合日志、执行产物、Skill 实现代码，定位失败根因。
   **第 2 步 — 给出方案**：向用户说明失败原因和解决方案。
   **第 3 步 — 上报诊断**：收尾前调用 `<入口> report-error --help` 查看参数并上报。

1. **断言**：`kind: "text"` 断言先由引擎做程序化判定 —— 精确匹配 → `pass/exact`；`expect` 与页面节点文案互为子串且**形态唯一** → `pass/semantic`（如 `expect`「没有更多了」/ 页面「- 没有更多了 -」）。**待复核唯一口径**：`needs_review = 通过且判定方式非字面精确（verdict ≠ exact）` —— `semantic`（引擎唯一子串推断 / AI 语义确认）与 `visual` 均标记待人工复核，仅 `exact` 属确定性结论；实现见 `assertions.engine.compute_needs_review`，动作层同口径（唯一子串兜底记 `action_hit.verdict=semantic`），报告在步骤（`steps[].needs_review`）与批次（`step_needs_review` / `assert_needs_review`）打标。两者都不成立才构建元素目录交 AI 语义确认，逐条按 **断言 id（A1/A2…）** 判定；`kind: "visual"` 用于纯视觉判断，可配 `targets` 拆开多条硬性验收点；`match: "gone"` 用于排除异常值（如 `{"kind":"text","match":"gone","expect":"https"}`），引擎会同时确认文本未以子串形态残留。判定口径与写回命令由 hook 提示给出（`hook-info`）。`step-type=assert` 步骤必须提供至少一项断言，否则 `flow-init` 报错。
   - action 文案口径差异（TEXT_NOT_FOUND）只记备注，既不判失败也不额外记一条 PASS：`log-record --desc "<摘要>" --note "<口径差异说明>"`（不带 `--pass/--fail/--ok` → 写一条无判定 note，归入 Case `notes` 或步骤 `annotations`，不计入统计）。
   - 一个步骤只写一次 `--assert-verdict`（同时覆盖文本断言与视觉复核）。

2. **设备创建失败**：云模拟器失败=基础设施不可用，**直接终止**（不重试不换参数），按第 0 条 3 步闭环。本地真机异常若带 `guidance` 则按步骤引导重试。

3. **本地真机安装/信任弹窗**：`local` 未安装 App 时自动补装（鸿蒙约 2-3 分钟），`important_notices` **原样转述给用户**。鸿蒙首次启动被"企业应用未受信任"拦截时，`device setup` 会暂停并携带 `guidance`：引导用户手动信任后重试，不要判为不可恢复。

4. **测试数据变更**：先用 Flow 原始参数完成首次落地验证，确认链路健康后再切换用户指定数据。

5. **感知通道适用范围**：文本断言与元素定位走探针链。视图树由 App 端按页面注入 dump 能力，业务容器页（MRN / Recce / Mach / 动态布局）可用；首页（MainActivity）未注入，`inspect-tree` 必然超时，须改用截图或 Activity 焦点判断。

6. **元素定位按目标选命令**：有文案用 `find-text --text <文案>`（直接返回坐标）；**无文案图标（箭头、图标按钮）声明步骤用 Flow action `tap` + `action_anchor`（锚点行唯一可点击目标 → 引擎自动点击；多/无 → 走视觉通道消歧）**；`find-icon --anchor <邻近文案>` 用于复核与坐标兜底（返回**锚点祖先链 + 该行候选**，结合周边文案判断点哪个 `clickable`，其 `tap` 字段即坐标）；输入框用 `find-input --anchor <邻近文案>`（同上，按 `role=input` 过滤）。`tap --action-x/--action-y` 坐标必须来自以上命令或截图取证。`inspect_tree.json` **禁止自行写脚本解析**（直读顶层字段全为空，会得「页面无节点」假象）。

7. **WebView（H5）页面元素定位**：WebView DOM 由 Chromium 绘制，不向 Android View 树注册子节点，`inspect-tree` 采不到其内部节点（正常现象）。**但 H5 已被统一目标模型覆盖**：webview 探针经 CDP 导出 DOM 节点（`dump_nodes`），`get_current_nodes` 会把 native 与各渲染层的节点合并去重（H5 节点在目录/候选中标注 `(webview)`），因此 **目录（sidecar）、候选清单、邻域查询、`find-icon`/`find-input` 都能看到 H5 元素**；`find-text` 走探针链（native 未命中回退 DOM，命中标注 `[webview]`）。前提是 App 已开启 WebView 调试开关，未开启时探针不可用并自动退化为纯 native（此时才需要 `find-text` + 截图目测）。排查首选 `probe-status` 确认探针链与目标页面。

8. **滚动未命中（SCROLL_TARGET_NOT_FOUND）**：引擎先精确/子串定位，均未命中才盲滑搜索；一旦滑动后页面内容无变化（已到边界/加载完）立即停止，不再跑满 5 次。hook 会同时给出截图与元素目录 —— **重试必须用目录里匹配到的真实节点文案**，拿原目标文案原样重试必然再失败。

## 六、产物

`flow-finalize` 将本 workspace 归档到 `output/run-<ts>/run/`，随后 `post-clean` **删除本 workspace 与其入口**。`output/` 保留 report.json（批次/Case 报告）、frames/（截图 S3 URL）和 run/（全部原始执行产物）供数据分析。批量报告必须包含全部声明的 Case，缺失则 `run_status: incomplete`。

Case 报告的 `steps` 是已声明步骤结论，`findings` 是独立判定，`notes` 是无判定备注。任何 fail 都会使 Case 状态为 failed，不存在"有失败但显示全绿"的情况。

## 七、时间线记录

`record-event` 用于向 `audit/run-events.jsonl` 记录 AI 分析过程（读图、重试、环境诊断等）。传 `--evidence-type` 即按证据格式记录，详情见 `--help`。